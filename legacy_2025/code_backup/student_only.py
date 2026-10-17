"""
Lightweight Student-only Lane Change Controller

MPC 제거, 학습된 신경망만 사용
- OSQP, scipy 의존성 제거
- 데이터 수집 기능 제거
- 순수 추론 모드만 지원

필요한 패키지:
- numpy
- onnxruntime
- python-can (선택)
"""

import argparse
import csv
import json
import math
import os
import signal
import socket
import struct
import sys
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, List, Deque

import numpy as np

try:
    import can
except Exception:
    can = None

try:
    import onnxruntime as ort
except Exception:
    ort = None


# =============================
# Terminal Colors
# =============================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


# =============================
# Constants
# =============================
_RAD2DEG = 180.0 / math.pi
_DEG2RAD = math.pi / 180.0


# =============================
# Enums & Dataclasses
# =============================
class State(Enum):
    KEEP_L2 = auto()
    EVADE_L = auto()
    KEEP_L1 = auto()
    RETURN_TO_L2 = auto()
    SAFE_STOP = auto()


@dataclass
class VehicleParams:
    L: float = 0.20
    B: float = 0.15
    V_MAX: float = 0.5
    V_MIN: float = 0.0
    DELTA_MAX_DEG: float = 25.0
    DELTA_RATE_MAX_DEGPS: float = 200.0
    A_MAX: float = 2.0
    A_MIN: float = -3.0
    _delta_max_rad: Optional[float] = None
    
    def __post_init__(self):
        self._delta_max_rad = self.DELTA_MAX_DEG * _DEG2RAD


@dataclass
class RoadParams:
    W: float = 0.30
    MAX_Y_DEVIATION: float = 3.0


@dataclass
class BehaviorParams:
    G_TRIG: float = 0.3
    TTC_TRIG: float = 2.0
    TTC_MIN: float = 1.0
    TAU_TARGET: float = 1.5
    TAU_MIN: float = 1.0
    COOLDOWN: float = 0.3
    NEAR_BAND_L1: float = 0.12


@dataclass
class AppConfig:
    hz: float = 20.0
    comm: str = "dummy"
    hb_period: float = 0.5
    log_dir: str = "./runs"
    policy_onnx: str = ""
    policy_stats: str = ""
    lidar_port: int = 8000
    ir_sensor_spacing: float = 0.05


# =============================
# Infrastructure
# =============================
@dataclass
class InfraROI:
    front_gap: Optional[float] = None
    roi_left_clear: bool = True
    timestamp: float = 0.0


# =============================
# Student Policy (ONNX)
# =============================
class StudentPolicy:
    """ONNX 기반 학생 정책"""
    
    def __init__(self, onnx_path: str, stats_path: str):
        if ort is None:
            raise ImportError("onnxruntime required. Install: pip install onnxruntime")
        
        self.session = ort.InferenceSession(onnx_path)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [out.name for out in self.session.get_outputs()]
        
        with open(stats_path, 'r') as f:
            stats = json.load(f)
        
        self.X_mean = np.array(stats['X_mean'], dtype=np.float32)
        self.X_std = np.array(stats['X_std'], dtype=np.float32)
        self.Y_mean = np.array(stats['Y_mean'], dtype=np.float32)
        self.Y_std = np.array(stats['Y_std'], dtype=np.float32)
        
        print(f"{Colors.CYAN}[STUDENT] Loaded ONNX: {onnx_path}{Colors.RESET}")
        print(f"{Colors.CYAN}[STUDENT] Input: {self.input_name} -> Outputs: {self.output_names}{Colors.RESET}")
    
    def predict(self, features: np.ndarray) -> Tuple[float, float]:
        """
        예측 수행
        
        Args:
            features: (10,) [v_cmd, ey, fg, ttc, left_clear, state_onehot[5]]
        
        Returns:
            (delta_deg, v_cmd)
        """
        # Normalize
        features_norm = (features - self.X_mean) / self.X_std
        features_batch = features_norm.reshape(1, -1).astype(np.float32)
        
        # Inference
        outputs = self.session.run(self.output_names, {self.input_name: features_batch})
        
        # Denormalize
        pred_norm = outputs[0][0]
        pred = pred_norm * self.Y_std + self.Y_mean
        
        return float(pred[0]), float(pred[1])


# =============================
# Utils
# =============================
def validate_sensor(value: Optional[float], min_val: float, max_val: float, 
                   name: str = "sensor") -> Optional[float]:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    if not (min_val <= value <= max_val):
        return None
    return value


def print_state_change(old_state: str, new_state: str):
    color_map = {
        'KEEP_L2': Colors.GREEN,
        'EVADE_L': Colors.YELLOW,
        'KEEP_L1': Colors.CYAN,
        'RETURN_TO_L2': Colors.BLUE,
        'SAFE_STOP': Colors.MAGENTA
    }
    old_color = color_map.get(old_state, '')
    new_color = color_map.get(new_state, '')
    print(f"{Colors.BOLD}[STATE]{Colors.RESET} {old_color}{old_state}{Colors.RESET} -> {new_color}{new_state}{Colors.RESET}")


# =============================
# IR Sensor Processing
# =============================
def ir_to_y_position(ir_left: int, ir_center: int, ir_right: int, 
                    sensor_spacing: float = 0.05) -> Optional[float]:
    """IR 센서 -> 차선 편차"""
    if ir_center == 1:
        if ir_left == 1 and ir_right == 0:
            return sensor_spacing * 0.5
        elif ir_left == 0 and ir_right == 1:
            return -sensor_spacing * 0.5
        else:
            return 0.0
    elif ir_left == 1 and ir_center == 0 and ir_right == 0:
        return sensor_spacing
    elif ir_right == 1 and ir_center == 0 and ir_left == 0:
        return -sensor_spacing
    else:
        return None


# =============================
# LiDAR Processing
# =============================
class YDLidarWiFi:
    """YDLidar WiFi 수신"""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', port))
        self.sock.settimeout(0.05)
        print(f"[LIDAR] Listening on port {port}")
    
    def receive(self) -> Optional[List[Tuple[float, float]]]:
        """수신된 스캔 포인트 반환"""
        try:
            data, _ = self.sock.recvfrom(65535)
            if len(data) < 12:
                return None
            
            points = []
            i = 0
            while i + 12 <= len(data):
                angle_deg, distance_mm = struct.unpack('<fI', data[i:i+8])
                angle_rad = angle_deg * _DEG2RAD
                distance_m = distance_mm / 1000.0
                points.append((angle_rad, distance_m))
                i += 8
            
            return points if points else None
        except socket.timeout:
            return None
        except Exception:
            return None


def process_lidar_roi(points: List[Tuple[float, float]], 
                     car_x_W: float, car_y_W: float, car_yaw_W: float,
                     roi_ahead: float = 1.5, roi_lateral: float = 0.4) -> InfraROI:
    """LiDAR 데이터 -> ROI 처리"""
    roi = InfraROI()
    
    if not points:
        return roi
    
    front_obstacles = []
    left_obstacles = []
    
    for angle_rad, dist_m in points:
        # Local frame
        x_local = dist_m * math.cos(angle_rad)
        y_local = dist_m * math.sin(angle_rad)
        
        # Front ROI
        if 0 < x_local < roi_ahead and abs(y_local) < roi_lateral:
            front_obstacles.append(x_local)
        
        # Left ROI
        if -0.2 < x_local < 0.5 and 0.3 < y_local < 0.8:
            left_obstacles.append(dist_m)
    
    roi.front_gap = min(front_obstacles) if front_obstacles else None
    roi.roi_left_clear = len(left_obstacles) == 0
    roi.timestamp = time.time()
    
    return roi


# =============================
# Line Sensor Fusion
# =============================
class LineSensorFusion:
    """EMA 기반 라인 센서 융합"""
    
    def __init__(self, alpha: float = 0.6, timeout: float = 0.2):
        self.alpha = alpha
        self.timeout = timeout
        self.ey_filtered: Optional[float] = None
        self.last_update = 0.0
    
    def update(self, ey_raw: float) -> None:
        now = time.time()
        if self.ey_filtered is None:
            self.ey_filtered = ey_raw
        else:
            self.ey_filtered = self.alpha * ey_raw + (1 - self.alpha) * self.ey_filtered
        self.last_update = now
    
    def get_ey(self) -> Optional[float]:
        if self.ey_filtered is None:
            return None
        if time.time() - self.last_update > self.timeout:
            return None
        return self.ey_filtered


# =============================
# Safety Guard
# =============================
class RateLimit:
    """조향각 변화율 제한"""
    
    def __init__(self, max_rate_per_step: float):
        self.max_rate = max_rate_per_step
        self.prev = 0.0
    
    def step(self, delta_cmd: float) -> float:
        delta_diff = delta_cmd - self.prev
        if delta_diff > self.max_rate:
            delta_diff = self.max_rate
        elif delta_diff < -self.max_rate:
            delta_diff = -self.max_rate
        
        delta_out = self.prev + delta_diff
        self.prev = delta_out
        return delta_out


class SafetyGuard:
    """안전 제약 검사"""
    
    def __init__(self, vp: VehicleParams, bp: BehaviorParams, dt: float):
        self.vp = vp
        self.bp = bp
        self.dt = dt
        self.interventions = 0
        self.min_ttc = float('inf')
        
        max_rate_per_step = vp.DELTA_RATE_MAX_DEGPS * dt
        self.rate = RateLimit(max_rate_per_step=max_rate_per_step)
    
    def check(self, v_cmd: float, delta_deg: float, ttc: float) -> Tuple[float, float]:
        # TTC 기록
        if ttc < self.min_ttc:
            self.min_ttc = ttc
        
        # 속도 제약
        v_cmd = max(self.vp.V_MIN, min(v_cmd, self.vp.V_MAX))
        
        # 조향각 제약
        dmax = self.vp.DELTA_MAX_DEG
        delta_cmd_deg = max(-dmax, min(delta_deg, dmax))
        delta_cmd_deg = self.rate.step(delta_cmd_deg)
        
        if abs(v_cmd - v_cmd) > 1e-6 or abs(delta_cmd_deg - delta_deg) > 1e-6:
            self.interventions += 1
        
        return v_cmd, delta_cmd_deg


# =============================
# Vehicle Model
# =============================
class Pose:
    """Bicycle model pose"""
    
    def __init__(self, x: float = 0.0, y: float = 0.0, psi: float = 0.0):
        self.x = x
        self.y = y
        self.psi = psi
    
    def update(self, v: float, delta_rad: float, dt: float, L: float = 0.2):
        """Kinematic bicycle model update"""
        self.x += v * math.cos(self.psi) * dt
        self.y += v * math.sin(self.psi) * dt
        self.psi += (v / L) * math.tan(delta_rad) * dt


# =============================
# Communication
# =============================
class DummyComm:
    """Dummy communication"""
    
    def send(self, v: float, theta: float) -> bool:
        return True
    
    def get_line_position(self) -> Optional[float]:
        return None
    
    def get_lidar_data(self, car_x_W: float, car_y_W: float, 
                       car_yaw_W: float) -> InfraROI:
        return InfraROI()


class CANComm:
    """CAN communication"""
    
    def __init__(self):
        if can is None:
            raise ImportError("python-can required")
        
        self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
        print("[CAN] Initialized on can0")
    
    def send(self, v: float, theta: float) -> bool:
        try:
            v_int = int(v * 100)
            theta_int = int(theta * 10)
            
            data = [
                (v_int >> 8) & 0xFF,
                v_int & 0xFF,
                (theta_int >> 8) & 0xFF,
                theta_int & 0xFF,
                0, 0, 0, 0
            ]
            
            msg = can.Message(arbitration_id=0x123, data=data, is_extended_id=False)
            self.bus.send(msg)
            return True
        except Exception:
            return False
    
    def get_line_position(self) -> Optional[float]:
        try:
            msg = self.bus.recv(timeout=0.01)
            if msg and msg.arbitration_id == 0x200 and len(msg.data) >= 4:
                ir_left = msg.data[0]
                ir_center = msg.data[1]
                ir_right = msg.data[2]
                return ir_to_y_position(ir_left, ir_center, ir_right)
        except Exception:
            pass
        return None
    
    def get_lidar_data(self, car_x_W: float, car_y_W: float, 
                       car_yaw_W: float) -> InfraROI:
        return InfraROI()


# =============================
# Main Controller
# =============================
class Controller:
    """Student-only lightweight controller"""
    
    def __init__(self, cfg: AppConfig, vp: VehicleParams, rp: RoadParams, bp: BehaviorParams):
        self.cfg = cfg
        self.vp = vp
        self.rp = rp
        self.bp = bp
        self.dt = 1.0 / cfg.hz
        
        # Student policy (required)
        if not cfg.policy_onnx or not cfg.policy_stats:
            raise ValueError("Student mode requires --policy_onnx and --policy_stats")
        
        self.student_policy = StudentPolicy(cfg.policy_onnx, cfg.policy_stats)
        
        # Communication
        if cfg.comm == "can":
            self.comm = CANComm()
        else:
            self.comm = DummyComm()
        
        # LiDAR (optional)
        try:
            self.lidar = YDLidarWiFi(port=cfg.lidar_port)
        except Exception:
            self.lidar = None
        
        # State
        self.state = State.KEEP_L2
        self.target_lane = 2
        self.last_state_change = time.time()
        self.delta_filtered = 0.0
        self.v_cmd_prev = 0.0
        self.front_gap: Optional[float] = None
        self.infra = InfraROI()
        
        # Sensors
        self.lines = LineSensorFusion(alpha=0.6, timeout=0.2)
        
        # Safety
        self.guard = SafetyGuard(vp, bp, self.dt)
        
        # Vehicle model
        self.pose = Pose()
        
        # Steering calibration
        self.steer_ratio = 10.0
        self.steer_offset_deg = 0.0
        
        # Control
        self._stop = False
        self._stop_flag = False
        self._stop_reason = ""
        
        # Logging
        os.makedirs(cfg.log_dir, exist_ok=True)
        log_path = os.path.join(cfg.log_dir, f"student_{int(time.time())}.csv")
        self.fp = open(log_path, 'w', newline='', encoding='utf-8')
        self.logger = csv.writer(self.fp)
        self.logger.writerow([
            "t", "state", "x", "y", "psi_deg", "v", "front_gap", "ttc",
            "left_clear", "v_cmd", "delta_deg", "loop_ms", "guard_intv", "min_ttc"
        ])
        
        def sig_handler(sig, frame):
            print(f"\n{Colors.YELLOW}[SIG] Stopping...{Colors.RESET}")
            self._stop = True
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
        
        print(f"{Colors.GREEN}[CTRL] Student-only controller initialized{Colors.RESET}")
        print(f"{Colors.GREEN}[CTRL] Running at {cfg.hz} Hz{Colors.RESET}")
    
    def set_state(self, new_state: State):
        if new_state != self.state:
            print_state_change(self.state.name, new_state.name)
            self.state = new_state
            self.last_state_change = time.time()
    
    def step_once(self):
        try:
            t0 = time.time()
            
            # Read sensors
            y_line = self.comm.get_line_position()
            
            # LiDAR
            if self.lidar:
                lidar_points = self.lidar.receive()
                if lidar_points:
                    self.infra = process_lidar_roi(
                        lidar_points, self.pose.x, self.pose.y, self.pose.psi
                    )
            
            # Update line sensor
            if y_line is not None:
                y_line = validate_sensor(y_line, -0.6, 0.6, "y_position")
                if y_line is not None:
                    self.lines.update(y_line)
            
            self.front_gap = self.infra.front_gap
            left_clear = self.infra.roi_left_clear
            
            # Current velocity
            v_now = self.v_cmd_prev if self.v_cmd_prev > 0.0 else self.vp.V_MAX
            ey_line = self.lines.get_ey()
            
            # Filter front_gap based on state
            front_gap = self.front_gap
            if self.state in (State.EVADE_L, State.KEEP_L1, State.RETURN_TO_L2):
                front_gap = None
            
            # TTC
            if front_gap is not None and front_gap > 0.0:
                closing_v = v_now if v_now > 0.01 else 0.01
                ttc = front_gap / closing_v
            else:
                ttc = float('inf')
            
            # Emergency stop
            if (front_gap is not None and ttc < self.bp.TTC_MIN and not left_clear):
                print(f"{Colors.RED}[SAFE_STOP] TTC_EMERGENCY: fg={front_gap:.2f}m, ttc={ttc:.2f}s{Colors.RESET}")
                self.set_state(State.SAFE_STOP)
                self.comm.send(0.0, 0.0)
                self._stop_flag = True
                self._stop_reason = "TTC_EMERGENCY"
                return
            
            # FSM
            if self.state == State.KEEP_L2:
                if front_gap is not None and front_gap < self.bp.G_TRIG and ttc < self.bp.TTC_TRIG:
                    if left_clear:
                        self.set_state(State.EVADE_L)
                        self.target_lane = 1
            
            elif self.state == State.EVADE_L:
                if ey_line is not None:
                    arrived_l1 = abs(ey_line - self.rp.W) < self.bp.NEAR_BAND_L1
                else:
                    arrived_l1 = self.pose.y > 0.85 * self.rp.W
                
                if arrived_l1:
                    self.set_state(State.KEEP_L1)
                    self.target_lane = 1
            
            elif self.state == State.KEEP_L1:
                since_evade = time.time() - self.last_state_change
                if since_evade > self.bp.COOLDOWN:
                    self.set_state(State.RETURN_TO_L2)
                    self.target_lane = 2
            
            elif self.state == State.RETURN_TO_L2:
                if ey_line is not None:
                    arrived_l2 = abs(ey_line) < self.bp.NEAR_BAND_L1
                else:
                    arrived_l2 = self.pose.y < 0.15 * self.rp.W
                
                if arrived_l2:
                    self.set_state(State.KEEP_L2)
                    self.target_lane = 2
            
            # Compute features for NN
            v_ref = self.vp.V_MAX
            
            if ey_line is None:
                ey_effective = self.pose.y - (self.rp.W if self.target_lane == 1 else 0.0)
            else:
                ey_effective = ey_line - (self.rp.W if self.target_lane == 1 else 0.0)
            
            feats = np.array([
                v_ref,
                ey_effective,
                front_gap if front_gap is not None else 10.0,
                ttc if math.isfinite(ttc) else 10.0,
                float(left_clear)
            ], dtype=np.float32)
            
            state_one_hot = np.zeros(len(State), dtype=np.float32)
            state_idx = max(0, min(len(State) - 1, self.state.value - 1))
            state_one_hot[state_idx] = 1.0
            feats = np.concatenate([feats, state_one_hot])
            
            # Student policy prediction
            delta_deg, v_cmd = self.student_policy.predict(feats)
            
            # Low-pass filter
            alpha = 0.3
            self.delta_filtered = alpha * delta_deg + (1 - alpha) * self.delta_filtered
            delta_deg = self.delta_filtered
            
            # Safety guard
            v_cmd, delta_deg = self.guard.check(v_cmd, delta_deg, ttc)
            
            # Update vehicle model
            delta_rad = delta_deg * _DEG2RAD
            self.pose.update(v_cmd, delta_rad, self.dt, self.vp.L)
            self.v_cmd_prev = v_cmd
            
            # Convert to motor angle
            theta_deg = delta_deg * self.steer_ratio + self.steer_offset_deg
            
            # Send command
            if not self.comm.send(v_cmd, theta_deg):
                self._stop_flag = True
                self._stop_reason = "COMM_FAIL"
            
            # Log
            loop_ms = (time.time() - t0) * 1000.0
            
            self.logger.writerow([
                f"{t0:.3f}",
                self.state.name,
                f"{self.pose.x:.2f}",
                f"{self.pose.y:.2f}",
                f"{self.pose.psi * _RAD2DEG:.1f}",
                f"{v_cmd:.2f}",
                "NA" if front_gap is None else f"{front_gap:.2f}",
                "INF" if ttc == float('inf') else f"{ttc:.2f}",
                int(left_clear),
                f"{v_cmd:.2f}",
                f"{delta_deg:.1f}",
                f"{loop_ms:.2f}",
                self.guard.interventions,
                "INF" if self.guard.min_ttc == float('inf') else f"{self.guard.min_ttc:.2f}"
            ])
            
        except Exception as e:
            print(f"{Colors.RED}[ERROR] step_once failed: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
            self._stop = True
    
    def run(self):
        print(f"{Colors.CYAN}[RUN] Starting student-only controller at {self.cfg.hz} Hz{Colors.RESET}")
        
        try:
            while not (self._stop or self._stop_flag):
                t0 = time.time()
                self.step_once()
                
                # Sleep to maintain loop rate
                elapsed = time.time() - t0
                sleep_time = (1.0 / self.cfg.hz) - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}[STOP] Interrupted{Colors.RESET}")
        finally:
            self.comm.send(0.0, 0.0)
            self.fp.close()
            print(f"{Colors.GREEN}[STOP] Stopped. Reason: {self._stop_reason or 'normal'}{Colors.RESET}")


# =============================
# Main
# =============================
def main():
    parser = argparse.ArgumentParser(description='Student-only Lane Change Controller')
    
    # Required
    parser.add_argument("--policy_onnx", type=str, required=True, help="Path to ONNX model")
    parser.add_argument("--policy_stats", type=str, required=True, help="Path to stats JSON")
    
    # Optional
    parser.add_argument("--hz", type=float, default=20.0, help="Control frequency")
    parser.add_argument("--comm", type=str, default="dummy", choices=["dummy", "can"])
    parser.add_argument("--log_dir", type=str, default="./runs")
    parser.add_argument("--lidar_port", type=int, default=8000)
    parser.add_argument("--ir_spacing", type=float, default=0.05)
    
    # Vehicle params
    parser.add_argument("--L", type=float, default=0.20, help="Wheelbase (m)")
    parser.add_argument("--B", type=float, default=0.15, help="Track width (m)")
    parser.add_argument("--v_max", type=float, default=0.5, help="Max velocity (m/s)")
    
    # Road params
    parser.add_argument("--lane_width", type=float, default=0.30, help="Lane width (m)")
    
    args = parser.parse_args()
    
    # Config
    cfg = AppConfig(
        hz=args.hz,
        comm=args.comm,
        log_dir=args.log_dir,
        policy_onnx=args.policy_onnx,
        policy_stats=args.policy_stats,
        lidar_port=args.lidar_port,
        ir_sensor_spacing=args.ir_spacing
    )
    
    vp = VehicleParams(L=args.L, B=args.B, V_MAX=args.v_max)
    rp = RoadParams(W=args.lane_width)
    bp = BehaviorParams()
    
    # Run
    controller = Controller(cfg, vp, rp, bp)
    controller.run()


if __name__ == '__main__':
    main()