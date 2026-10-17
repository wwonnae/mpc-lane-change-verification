import argparse
import csv
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, List, Deque, Dict
from collections import deque

try:
    import numpy as np
except Exception:
    print("[ERR] numpy is required.")
    sys.exit(1)

# CAN 통신
try:
    import can  # pip install python-can
except Exception:
    can = None

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

# Optional deps
try:
    import onnxruntime as ort  # type: ignore
except Exception:
    ort = None
try:
    import torch  # type: ignore
except Exception:
    torch = None
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# =============================
# Optimized inline functions (remove function call overhead)
# =============================
# 상수 캐싱
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
    DECEL_L2 = auto()
    SAFE_STOP = auto()

class RunMode(Enum):
    TEACHER = auto()
    SHADOW = auto()
    STUDENT = auto()

@dataclass
class VehicleParams:
    L: float = 0.20
    B: float = 0.15
    V_MAX: float = 1.0
    V_MIN: float = 0.0
    DELTA_MAX_DEG: float = 20.0
    DELTA_RATE_MAX_DEGPS: float = 200.0
    A_MAX: float = 2.0
    A_MIN: float = -3.0
    WHEEL_RATE_MAX: float = 3.0
    # 캐싱용
    _delta_max_rad: Optional[float] = None
    
    def __post_init__(self):
        self._delta_max_rad = self.DELTA_MAX_DEG * _DEG2RAD

@dataclass
class RoadParams:
    W: float = 0.25
    MAX_Y_DEVIATION: float = 3.0

@dataclass
class BehaviorParams:
    G_TRIG: float = 1.8
    TTC_TRIG: float = 2.0
    TTC_MIN: float = 0.8
    TTC_EVADE_MIN: float = 1.2
    T_KEEP_L1_MIN: float = 1.0
    G_RETURN_SAFE: float = 2.5
    K_TTC: float = 1.5
    COOLDOWN: float = 0.3
    NEAR_BAND_L1: float = 0.12

@dataclass
class ControllerParams:
    k_ey_keep: float = 1.2
    k_ey_evade: float = 1.8
    k_ey_return: float = 1.8
    k_delta_rate: float = 0.05
    # P제어 추가 게인들
    k_psi_keep: float = 0.3
    k_psi_evade: float = 0.4
    k_psi_return: float = 0.5

@dataclass
class AppConfig:
    hz: float = 20.0
    run_mode: RunMode = RunMode.TEACHER
    assume_straight_nominal: int = 1
    comm: str = "dummy"
    hb_period: float = 0.5
    log_dir: str = "./runs"
    export_dataset: int = 0
    dataset_dir: str = "./dataset"
    merge_shards: int = 0
    merged_out: Optional[str] = None
    tau_ms: float = 0.0
    tau_jitter_ms: float = 0.0
    policy_onnx: Optional[str] = None
    policy_ts: Optional[str] = None
    yaml_path: Optional[str] = None
    debug_print: int = 0

@dataclass
class InfraROI:
    front_gap: Optional[float] = None
    rel_speed: Optional[float] = None
    roi_left_clear: bool = True
    timestamp: float = 0.0

# =============================
# Utils (keeping only what's needed)
# =============================
def validate_sensor(value: Optional[float], min_val: float, max_val: float, name: str = "sensor") -> Optional[float]:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        print(f"{Colors.YELLOW}[WARN] {name}: Invalid type{Colors.RESET}")
        return None
    if not (min_val <= value <= max_val):
        print(f"{Colors.YELLOW}[WARN] {name}: Out of range {value:.2f}{Colors.RESET}")
        return None
    return value

def print_state_change(old_state: str, new_state: str):
    color_map = {
        'KEEP_L2': Colors.GREEN,
        'EVADE_L': Colors.YELLOW,
        'KEEP_L1': Colors.CYAN,
        'RETURN_TO_L2': Colors.BLUE,
        'DECEL_L2': Colors.RED,
        'SAFE_STOP': Colors.MAGENTA
    }
    old_color = color_map.get(old_state, '')
    new_color = color_map.get(new_state, '')
    print(f"{Colors.BOLD}[STATE]{Colors.RESET} {old_color}{old_state}{Colors.RESET} → {new_color}{new_state}{Colors.RESET}")

# =============================
# Param Server
# =============================
class ParamServer:
    def __init__(self, path: Optional[str]):
        self.path = path
        self.mtime = 0.0
        self.data: Dict[str, Dict] = {}
        
    def load(self):
        if self.path and yaml is not None and os.path.isfile(self.path):
            m = os.path.getmtime(self.path)
            if m != self.mtime:
                with open(self.path, 'r', encoding='utf-8') as fp:
                    self.data = yaml.safe_load(fp) or {}
                self.mtime = m
                print(f"[YAML] reloaded {self.path}")
                
    def apply(self, vp: VehicleParams, rp: RoadParams, bp: BehaviorParams, cp: ControllerParams):
        def upd(obj, name):
            if name in self.data:
                for k, v in self.data[name].items():
                    if hasattr(obj, k):
                        setattr(obj, k, v)
        upd(vp, 'vehicle')
        upd(rp, 'road')
        upd(bp, 'behavior')
        upd(cp, 'ctrl')
        # 캐시 업데이트
        vp._delta_max_rad = vp.DELTA_MAX_DEG * _DEG2RAD

# =============================
# Pose Estimator
# =============================
class PoseEstimator:
    def __init__(self, L: float):
        self.x = 0.0
        self.y = 0.0
        self.psi = 0.0
        self.L = L
        self._L_safe = max(L, 1e-3)
        
    def step(self, v_cmd: float, delta_cmd_deg: float, dt: float):
        delta_rad = delta_cmd_deg * _DEG2RAD
        psi_dot = (v_cmd / self._L_safe) * math.tan(delta_rad)
        self.psi += psi_dot * dt
        # inline clamp
        psi_max = 60.0 * _DEG2RAD
        self.psi = psi_max if self.psi > psi_max else -psi_max if self.psi < -psi_max else self.psi
        self.x += v_cmd * math.cos(self.psi) * dt
        self.y += v_cmd * math.sin(self.psi) * dt
        return self.x, self.y, self.psi

# =============================
# Filters
# =============================
class EMA:
    def __init__(self, alpha: float):
        self.a = alpha
        self.v: Optional[float] = None
        self._1ma = 1.0 - alpha  # 캐시
        
    def step(self, x: Optional[float]) -> Optional[float]:
        if x is None:
            return self.v
        self.v = x if self.v is None else self._1ma * self.v + self.a * x
        return self.v

class Signal:
    def __init__(self, alpha=0.3, max_age=0.5):
        self.ema = EMA(alpha)
        self.ts = 0.0
        self.max_age = max_age
        
    def update(self, x: Optional[float]) -> Optional[float]:
        v = self.ema.step(x)
        if x is not None:
            self.ts = time.time()
        return v
    
    def is_valid(self) -> bool:
        return (time.time() - self.ts) <= self.max_age

# =============================
# Sensors
# =============================
class LineTraceSensor:
    def __init__(self, lane_width: float = 0.6):
        self.sig_ey_L2 = EMA(alpha=0.3)
        self._ey_L2: Optional[float] = None
        self.last_update_L2 = 0.0
        self.sig_ey_L1 = EMA(alpha=0.3)
        self._ey_L1: Optional[float] = None
        self.last_update_L1 = 0.0
        self.max_age = 0.5
        self.lane_width = lane_width  # 차선 간격
        
    def update_L2_from_sensors(self, sensor_values: List[int]):
        if not sensor_values or len(sensor_values) < 3:
            return
        n = len(sensor_values)
        positions = list(range(n))
        center = (n - 1) / 2
        total_weight = sum(sensor_values)
        if total_weight > 0:
            weighted_pos = sum(p * v for p, v in zip(positions, sensor_values)) / total_weight
            ey = (weighted_pos - center) * 0.01
            self._ey_L2 = ey
            self.last_update_L2 = time.time()
    
    def update_L1_from_sensors(self, sensor_values: List[int]):
        if not sensor_values or len(sensor_values) < 3:
            return
        n = len(sensor_values)
        positions = list(range(n))
        center = (n - 1) / 2
        total_weight = sum(sensor_values)
        if total_weight > 0:
            weighted_pos = sum(p * v for p, v in zip(positions, sensor_values)) / total_weight
            ey = (weighted_pos - center) * 0.01
            self._ey_L1 = ey
            self.last_update_L1 = time.time()
    
    def update_L2(self, ey: Optional[float]):
        if ey is not None:
            self._ey_L2 = ey
            self.last_update_L2 = time.time()
    
    def update_L1(self, ey: Optional[float]):
        if ey is not None:
            self._ey_L1 = ey
            self.last_update_L1 = time.time()
            
    def read_L2(self) -> Tuple[float, bool]:
        """L2 차선 읽기 (실제 센서 값만 신뢰)"""
        age_L2 = time.time() - self.last_update_L2
        valid_L2 = age_L2 <= self.max_age and self._ey_L2 is not None
        
        if valid_L2:
            ey = self.sig_ey_L2.step(self._ey_L2)
            return ey or 0.0, True
        
        return 0.0, False
    
    def read_L1(self) -> Tuple[float, bool]:
        """L1 차선 읽기 (실제 센서 값만 신뢰)"""
        age_L1 = time.time() - self.last_update_L1
        valid_L1 = age_L1 <= self.max_age and self._ey_L1 is not None
        
        if valid_L1:
            ey = self.sig_ey_L1.step(self._ey_L1)
            return ey or 0.0, True
        
        return 0.0, False

class SpeedSensor:
    def __init__(self):
        self.sig = Signal(alpha=0.2, max_age=0.5)
        self._v = 0.5
        
    def update_from_command(self, v_cmd: float, dt: float):
        self._v = v_cmd
    
    def read(self) -> float:
        return self.sig.update(self._v) or 0.5

# =============================
# Lanes
# =============================
LANE_HOME = 2

# 캐시된 lane center 값들 (자주 쓰이므로)
_LANE_CENTERS = {}

def lane_center_y(lane_idx: int, W: float = 0.25, home: int = LANE_HOME) -> float:
    key = (lane_idx, W, home)
    if key not in _LANE_CENTERS:
        _LANE_CENTERS[key] = (home - lane_idx) * W
    return _LANE_CENTERS[key]

# =============================
# Controllers - PROPORTIONAL ONLY VERSION
# =============================
class LateralController:
    """순수 Proportional 제어기 (heading 보상 포함)"""
    def __init__(self, cp: ControllerParams, vp: VehicleParams):
        self.cp = cp
        self.vp = vp
        self.delta_prev = 0.0
        self._1mk = 1.0 - cp.k_delta_rate  # 캐시
        
    def delta_cmd_deg(self, ey: float, psi: float, v: float, state: State) -> float:
        """
        ey: lateral error (목표 y - 현재 y)
        psi: heading error (rad)
        v: speed
        """
        # 상태별 게인 선택
        if state == State.EVADE_L:
            k_ey = self.cp.k_ey_evade
            k_psi = self.cp.k_psi_evade
        elif state == State.RETURN_TO_L2:
            k_ey = self.cp.k_ey_return
            k_psi = self.cp.k_psi_return
        else:
            k_ey = self.cp.k_ey_keep
            k_psi = self.cp.k_psi_keep
        
        # P제어: atan2(k_ey * ey, v) - k_psi * psi
        v_safe = 0.1 if v < 0.1 else v
        delta = math.atan2(k_ey * ey, v_safe) - k_psi * psi
        
        # 부드러운 전환
        delta = self._1mk * delta + self.cp.k_delta_rate * self.delta_prev
        self.delta_prev = delta
        
        # inline clamp
        delta_deg = delta * _RAD2DEG
        dmax = self.vp.DELTA_MAX_DEG
        return dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg

class LongitudinalController:
    def __init__(self, bp: BehaviorParams, vp: VehicleParams):
        self.bp = bp
        self.vp = vp
        self._dt = 1.0 / 20.0  # 캐시
        
    def advisory_speed(self, v_now: float, front_gap: Optional[float], rel_speed: Optional[float]) -> float:
        if front_gap is None:
            return self.vp.V_MAX
        if rel_speed is not None and rel_speed > 0:
            ttc = front_gap / rel_speed
        else:
            return 0.5 if v_now < 0.5 else self.vp.V_MAX if v_now > self.vp.V_MAX else v_now
        
        ttc_safe = 1e-3 if ttc < 1e-3 else ttc
        a_cmd = -self.bp.K_TTC / ttc_safe
        # inline clamp
        a_cmd = self.vp.A_MAX if a_cmd > self.vp.A_MAX else self.vp.A_MIN if a_cmd < self.vp.A_MIN else a_cmd
        v_target = v_now + a_cmd * self._dt
        # inline clamp
        v_target = self.vp.V_MAX if v_target > self.vp.V_MAX else self.vp.V_MIN if v_target < self.vp.V_MIN else v_target
        
        if ttc < self.bp.TTC_MIN:
            v_target = 0.2 if v_target > 0.2 else v_target
        return v_target

class RateLimiter:
    def __init__(self, rate_max_degps: float):
        self.rate_max = rate_max_degps
        self.last_val: Optional[float] = None
        self.last_t: Optional[float] = None
        self._min_dt = 1.0 / 200.0  # 캐시
        
    def step(self, target_deg: float) -> float:
        now = time.time()
        if self.last_val is None:
            self.last_val = target_deg
            self.last_t = now
            return target_deg
        dt = now - self.last_t
        dt = self._min_dt if dt < self._min_dt else dt
        max_step = self.rate_max * dt
        # inline clamp
        lo = self.last_val - max_step
        hi = self.last_val + max_step
        val = hi if target_deg > hi else lo if target_deg < lo else target_deg
        self.last_val = val
        self.last_t = now
        return val

class SafetyGuard:
    def __init__(self, vp: VehicleParams, bp: BehaviorParams):
        self.vp = vp
        self.bp = bp
        self.rate = RateLimiter(vp.DELTA_RATE_MAX_DEGPS)
        self.interventions = 0
        self.min_ttc = float('inf')
        
    def apply(self, v_cmd: float, delta_cmd_deg: float, v_now: float, front_gap: Optional[float], rel_speed: Optional[float]) -> Tuple[float, float]:
        v0 = v_cmd
        d0 = delta_cmd_deg
        
        # inline clamp v_cmd
        v_cmd = self.vp.V_MAX if v_cmd > self.vp.V_MAX else self.vp.V_MIN if v_cmd < self.vp.V_MIN else v_cmd
        
        if front_gap is not None:
            front_gap = validate_sensor(front_gap, 0.0, 50.0, "front_gap")
            if front_gap is not None:
                if rel_speed is not None and rel_speed > 0:
                    ttc = front_gap / rel_speed
                else:
                    ttc = front_gap / (0.1 if v_now < 0.1 else v_now)
                self.min_ttc = ttc if ttc < self.min_ttc else self.min_ttc
                if ttc < self.bp.TTC_MIN:
                    v_cmd = 0.2 if v_cmd > 0.2 else v_cmd
        
        # inline clamp delta
        dmax = self.vp.DELTA_MAX_DEG
        delta_cmd_deg = dmax if delta_cmd_deg > dmax else -dmax if delta_cmd_deg < -dmax else delta_cmd_deg
        delta_cmd_deg = self.rate.step(delta_cmd_deg)
        
        if abs(v_cmd - v0) > 1e-3 or abs(d0 - delta_cmd_deg) > 1e-3:
            self.interventions += 1
        
        return v_cmd, delta_cmd_deg

class Watchdog:
    def __init__(self, dt: float):
        self.dt = dt
        self.overruns = 0
        self.state = 'OK'
        self._thr = 0.7 * dt * 1000.0  # 캐시
        
    def step(self, loop_ms: float) -> str:
        if loop_ms > self._thr:
            self.overruns += 1
        else:
            self.overruns = 0 if self.overruns == 0 else self.overruns - 1
        if self.overruns > 5:
            self.state = 'DEGRADE'
        if self.overruns > 15:
            self.state = 'STOP'
        return self.state

# =============================
# Differential Drive
# =============================
class DiffMapper:
    def __init__(self, vp: VehicleParams):
        self.vp = vp
        self._half_B = 0.5 * vp.B  # 캐시
        self._L_safe = max(vp.L, 1e-3)  # 캐시
        
    def to_diff(self, v_cmd: float, delta_cmd_deg: float) -> Tuple[float, float]:
        delta_rad = delta_cmd_deg * _DEG2RAD
        omega = (v_cmd / self._L_safe) * math.tan(delta_rad)
        d_omega = self._half_B * omega
        vL = v_cmd - d_omega
        vR = v_cmd + d_omega
        return vL, vR

class WheelRateLimiter:
    def __init__(self, rate_max_mps2: float):
        self.rate = rate_max_mps2
        self.vL_last: Optional[float] = None
        self.vR_last: Optional[float] = None
        self._min_dt = 1e-3  # 캐시
        
    def step(self, vL_tgt: float, vR_tgt: float, dt: float) -> Tuple[float, float]:
        if self.vL_last is None:
            self.vL_last = vL_tgt
            self.vR_last = vR_tgt
            return vL_tgt, vR_tgt
        dt_safe = self._min_dt if dt < self._min_dt else dt
        dv = self.rate * dt_safe
        # inline clamp
        vL = self.vL_last + dv if vL_tgt > self.vL_last + dv else self.vL_last - dv if vL_tgt < self.vL_last - dv else vL_tgt
        vR = self.vR_last + dv if vR_tgt > self.vR_last + dv else self.vR_last - dv if vR_tgt < self.vR_last - dv else vR_tgt
        self.vL_last = vL
        self.vR_last = vR
        return vL, vR

# =============================
# Communication
# =============================
class Comm:
    def __init__(self, mode: str, hb_period: float, can_channel: str = 'can0', can_bitrate: int = 500000):
        self.mode = mode
        self.hb_period = hb_period
        self.last_hb = 0.0
        self.ok = True
        self.can_bus = None
        
        # CAN 초기화
        if mode == "can":
            if can is None:
                print(f"{Colors.RED}[ERR] python-can not installed. Install: pip install python-can{Colors.RESET}")
                print(f"{Colors.YELLOW}[WARN] Falling back to dummy mode{Colors.RESET}")
                self.mode = "dummy"
            else:
                try:
                    self.can_bus = can.interface.Bus(channel=can_channel, bustype='socketcan', bitrate=can_bitrate)
                    print(f"{Colors.GREEN}[CAN] Initialized: {can_channel} @ {can_bitrate}bps{Colors.RESET}")
                except Exception as e:
                    print(f"{Colors.RED}[CAN] Init failed: {e}{Colors.RESET}")
                    print(f"{Colors.YELLOW}[WARN] Falling back to dummy mode{Colors.RESET}")
                    self.mode = "dummy"
        
        print(f"[INFO] Comm={self.mode}, hb={hb_period}s")
        
    def _hb(self):
        now = time.time()
        if now - self.last_hb >= self.hb_period:
            self.last_hb = now
            if self.mode == 'dummy':
                print("HB")
                
    def send(self, v_cmd: float, steer_deg: float) -> bool:
        try:
            self._hb()
            
            if self.mode == "can" and self.can_bus is not None:
                # 데이터 변환: 속도(0.01 m/s 단위) + 조향각(0.1도 단위)
                v_int = int(v_cmd * 100)           # 1.20 m/s → 120
                delta_int = int(steer_deg * 10)    # 5.5 deg → 55
                
                # CAN 메시지 전송 (ackermann only)
                msg = can.Message(arbitration_id=0x100, data=[v_int & 0xFF, (v_int >> 8) & 0xFF, 
                                                               delta_int & 0xFF, (delta_int >> 8) & 0xFF],
                                 is_extended_id=False)
                self.can_bus.send(msg)
            
            return True
        except Exception as e:
            print(f"{Colors.RED}[COMM] send error: {e}{Colors.RESET}")
            return False
    
    def close(self):
        if self.can_bus is not None:
            try:
                self.can_bus.shutdown()
            except:
                pass

# =============================
# Dataset Export (dummy - not used in P control version)
# =============================
class DatasetShard:
    def __init__(self, path: str):
        self.path = path
        self.samples: List = []
        
    def push(self, obs, act, meta):
        self.samples.append((obs, act, meta))
        
    def flush(self):
        if not self.samples:
            return
        print(f"[DATASET] Would save {len(self.samples)} samples to {self.path}")
        self.samples.clear()

class TauLogger:
    def __init__(self):
        self.values: List[int] = []
    
    def add(self, val: int):
        self.values.append(val)
    
    def write(self, base_dir: str, dt: float):
        if self.values:
            print(f"[TAU] Logged {len(self.values)} tau values")

def merge_shards(dataset_dir: str, output_path: str):
    print(f"[MERGE] Placeholder: would merge shards from {dataset_dir} to {output_path}")

# =============================
# TEST HARNESS
# =============================
class SensorSimulator:
    def __init__(self):
        self.timeline: List[Tuple[int, dict]] = []
        
    def add_timeline(self, timeline: List[Tuple[int, dict]]):
        self.timeline = sorted(timeline, key=lambda x: x[0])
        
    def get_values(self, step: int) -> dict:
        if not self.timeline:
            return {
                'roi': InfraROI(front_gap=None, rel_speed=None, roi_left_clear=True),
                'v': 1.2,
                'line_ey_L2': 0.0,
                'line_ey_L1': None
            }
        prev_values = self.timeline[0][1]
        for t_step, values in self.timeline:
            if t_step <= step:
                prev_values = values
            else:
                break
        return prev_values

class TestHarness:
    def __init__(self, app):
        self.app = app
        self.results = []
        
    def run_scenario(self, name: str, timeline: List[Tuple[int, dict]], expected_states: List[Tuple[int, str]]):
        print(f"\n{'=' * 60}")
        print(f"{Colors.CYAN}🧪 Testing: {name}{Colors.RESET}")
        print(f"{'=' * 60}")
        
        sim = SensorSimulator()
        sim.add_timeline(timeline)
        self.reset_app_state()
        expected_dict = {step: state for step, state in expected_states}
        max_step = max(step for step, _ in expected_states)
        base_time = time.time()
        
        for step in range(max_step + 1):
            step_time = base_time + (step * self.app.dt)
            self.app._test_time = step_time
            sensor_data = sim.get_values(step)
            self.inject_sensors(sensor_data)
            
            try:
                self.app.step_once()
                
                # 테스트 데이터 유지 (step_once가 pose를 업데이트하므로 다시 설정)
                if 'y' in sensor_data:
                    self.app.pose.y = sensor_data['y']
                
            except Exception as e:
                print(f"{Colors.RED}❌ Step {step}: ERROR - {e}{Colors.RESET}")
                import traceback
                traceback.print_exc()
                self.results.append({
                    'scenario': name,
                    'step': step,
                    'expected': expected_dict.get(step, 'N/A'),
                    'actual': 'ERROR',
                    'passed': False
                })
                continue
            
            if step in expected_dict:
                actual = self.app.state.name
                expected = expected_dict[step]
                passed = (actual == expected)
                status = f"{Colors.GREEN}✅{Colors.RESET}" if passed else f"{Colors.RED}❌{Colors.RESET}"
                roi = sensor_data.get('roi', InfraROI())
                fg = roi.front_gap
                fg_str = f"{fg:.1f}" if fg else "N/A"
                lc = "Clear" if sensor_data.get('left_clear', True) else "Block"
                print(f"{status} Step {step:3d}: Exp {expected:15s} | Got {actual:15s} | "
                      f"y={self.app.pose.y:5.2f} | fg={fg_str:>5s} | L={lc:5s}")
                self.results.append({
                    'scenario': name,
                    'step': step,
                    'expected': expected,
                    'actual': actual,
                    'passed': passed
                })
        
        self.app._test_time = None
        print()
    
    def reset_app_state(self):
        self.app._stop = False
        self.app._stop_flag = False
        self.app.state = State.KEEP_L2
        self.app.pose.x = 0.0
        self.app.pose.y = 0.0
        self.app.pose.psi = 0.0
        now = time.time()
        self.app.last_state_change = now
        self.app.delta_prev = 0.0
        self.app.left_clear_override = None
        
    def inject_sensors(self, data: dict):
        now = time.time()
        roi = data.get('roi', InfraROI())
        self.app.infra_roi = roi
        
        if 'left_clear' in data:
            self.app.left_clear_override = data['left_clear']
            self.app.infra_roi.roi_left_clear = data['left_clear']
        
        if 'v' in data:
            self.app.speed._v = data['v']
            self.app.speed.sig.ema.v = data['v']
            self.app.speed.sig.ts = now
        
        # 테스트용 pose.y 업데이트
        if 'y' in data:
            self.app.pose.y = data['y']
        
        if 'line_ey_L2' in data:
            self.app.lines.update_L2(data['line_ey_L2'])
            if data['line_ey_L2'] is not None:
                self.app.lines.sig_ey_L2.v = data['line_ey_L2']
        
        if 'line_ey_L1' in data:
            self.app.lines.update_L1(data['line_ey_L1'])
            if data['line_ey_L1'] is not None:
                self.app.lines.sig_ey_L1.v = data['line_ey_L1']
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print(f"{Colors.BOLD}📊 TEST SUMMARY{Colors.RESET}")
        print("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        
        by_scenario = {}
        for r in self.results:
            s = r['scenario']
            if s not in by_scenario:
                by_scenario[s] = {'total': 0, 'passed': 0}
            by_scenario[s]['total'] += 1
            if r['passed']:
                by_scenario[s]['passed'] += 1
        
        for scenario, counts in by_scenario.items():
            p = counts['passed']
            t = counts['total']
            pct = 100.0 * p / t if t > 0 else 0.0
            status_color = Colors.GREEN if pct == 100.0 else Colors.YELLOW if pct >= 50.0 else Colors.RED
            print(f"{status_color}  {scenario}: {p}/{t} ({pct:.1f}%){Colors.RESET}")
        
        overall_pct = 100.0 * passed / total if total > 0 else 0.0
        overall_color = Colors.GREEN if overall_pct == 100.0 else Colors.YELLOW if overall_pct >= 50.0 else Colors.RED
        print(f"\n{overall_color}{Colors.BOLD}Overall: {passed}/{total} ({overall_pct:.1f}%){Colors.RESET}\n")

def create_test_scenarios():
    """
    P제어용 테스트 시나리오
    - 차선 위에 있을 때: 해당 차선 라인 보임 → P제어 우선
    - 차선 사이 기동 시: 라인 안 보임 → pose 기반 P제어
    """
    scenarios = []
    
    # =============================
    # 시나리오 1: 완전한 회피 기동 (라인 전환 포함)
    # =============================
    timeline1 = [
        # 초기: L2 주행 (y=0.0, L2 선 보임)
        (0, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
             'v': 1.2, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
        
        # 장애물 감지
        (10, {'roi': InfraROI(front_gap=1.8, rel_speed=0.6, roi_left_clear=True),
              'v': 1.2, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
        
        # EVADE 트리거
        (50, {'roi': InfraROI(front_gap=1.5, rel_speed=0.5, roi_left_clear=True),
              'v': 1.0, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
        
        # 회피 시작: L2 벗어남
        (55, {'roi': InfraROI(front_gap=1.6, rel_speed=0.4, roi_left_clear=True),
              'v': 0.9, 'y': 0.1, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        # 차선 사이
        (70, {'roi': InfraROI(front_gap=1.8, rel_speed=0.3, roi_left_clear=True),
              'v': 0.8, 'y': 0.2, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        (85, {'roi': InfraROI(front_gap=2.0, rel_speed=0.2, roi_left_clear=True),
              'v': 0.8, 'y': 0.35, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        # L1 접근 (L1 선 보이기 시작)
        (100, {'roi': InfraROI(front_gap=2.3, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.5, 'line_ey_L2': None, 'line_ey_L1': 0.1, 'left_clear': True}),
        
        # L1 거의 도달
        (115, {'roi': InfraROI(front_gap=2.5, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.28, 'line_ey_L2': None, 'line_ey_L1': 0.02, 'left_clear': True}),
        
        # L1 중심
        (130, {'roi': InfraROI(front_gap=3.0, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.25, 'line_ey_L2': None, 'line_ey_L1': 0.0, 'left_clear': True}),
        
        # L1 유지
        (150, {'roi': InfraROI(front_gap=3.5, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.25, 'line_ey_L2': None, 'line_ey_L1': 0.0, 'left_clear': True}),
        
        (180, {'roi': InfraROI(front_gap=4.0, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.25, 'line_ey_L2': None, 'line_ey_L1': 0.0, 'left_clear': True}),
        
        # 복귀 시작: L1 벗어남
        (200, {'roi': InfraROI(front_gap=4.5, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.5, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        # 차선 사이 복귀 중
        (220, {'roi': InfraROI(front_gap=4.8, rel_speed=0.0, roi_left_clear=True),
               'v': 0.8, 'y': 0.35, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        # L2 접근 (L2 선 보이기 시작)
        (240, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
               'v': 0.9, 'y': 0.2, 'line_ey_L2': 0.2, 'line_ey_L1': None, 'left_clear': True}),
        
        # L2 거의 도달
        (260, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
               'v': 0.9, 'y': 0.02, 'line_ey_L2': 0.02, 'line_ey_L1': None, 'left_clear': True}),
        
        # L2 중심 복귀
        (280, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
               'v': 1.0, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
        
        # L2 완전 안정화
        (300, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
               'v': 1.0, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
    ]
    
    expected1 = [
        (0, 'KEEP_L2'),
        (50, 'EVADE_L'),
        (280, 'KEEP_L2')
    ]
    scenarios.append(('full_evade_proportional', timeline1, expected1))
    
    # =============================
    # 시나리오 2: 좌측 차단 시 감속
    # =============================
    timeline2 = [
        (0, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
             'v': 1.2, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
        
        (10, {'roi': InfraROI(front_gap=1.7, rel_speed=0.8, roi_left_clear=False),
              'v': 1.2, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': False}),
        
        (20, {'roi': InfraROI(front_gap=2.0, rel_speed=0.5, roi_left_clear=False),
              'v': 0.9, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': False}),
        
        (30, {'roi': InfraROI(front_gap=3.0, rel_speed=0.0, roi_left_clear=False),
              'v': 0.8, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': False}),
    ]
    expected2 = [(0, 'KEEP_L2'), (11, 'DECEL_L2'), (31, 'KEEP_L2')]
    scenarios.append(('decel_line_tracking', timeline2, expected2))
    
    # =============================
    # 시나리오 3: 라인 손실 시 pose 기반 P제어 전환
    # =============================
    timeline3 = [
        # 초기: L2 라인트레이싱
        (0, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
             'v': 1.2, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
        
        # L2 선 일시 손실 → pose 기반 P제어로 자동 전환
        (20, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
              'v': 1.2, 'y': 0.0, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        # pose 기반 P제어로 L2 유지
        (40, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
              'v': 1.2, 'y': 0.0, 'line_ey_L2': None, 'line_ey_L1': None, 'left_clear': True}),
        
        # L2 선 복구 → 라인트레이싱 재개
        (60, {'roi': InfraROI(front_gap=5.0, rel_speed=0.0, roi_left_clear=True),
              'v': 1.2, 'y': 0.0, 'line_ey_L2': 0.0, 'line_ey_L1': None, 'left_clear': True}),
    ]
    expected3 = [(0, 'KEEP_L2'), (20, 'KEEP_L2'), (60, 'KEEP_L2')]
    scenarios.append(('line_loss_pose_fallback', timeline3, expected3))
    
    return scenarios

# =============================
# Main App - PROPORTIONAL VERSION
# =============================
class App:
    def __init__(self, cfg: AppConfig, vp: VehicleParams, rp: RoadParams, bp: BehaviorParams, cp: ControllerParams):
        print(f"{Colors.CYAN}[INIT] Proportional Control Version{Colors.RESET}")
        
        self.cfg = cfg
        self.vp = vp
        self.rp = rp
        self.bp = bp
        self.cp = cp
        
        self.dt = 1.0 / cfg.hz
        self.state = State.KEEP_L2
        self.last_state_change = time.time()
        
        # Controllers - P제어만 사용
        self.lat = LateralController(cp, vp)
        self.lon = LongitudinalController(bp, vp)
        self.guard = SafetyGuard(vp, bp)
        self.watchdog = Watchdog(self.dt)
        
        # Pose & Sensors
        self.pose = PoseEstimator(vp.L)
        self.lines = LineTraceSensor(rp.W)
        self.speed = SpeedSensor()
        self.infra_roi = InfraROI()
        self.left_clear_override: Optional[bool] = None
        
        # Comm
        self.comm = Comm(cfg.comm, cfg.hb_period)
        
        # State tracking
        self.delta_prev = 0.0
        self.front_gap: Optional[float] = None
        
        # Logging
        os.makedirs(cfg.log_dir, exist_ok=True)
        log_file = os.path.join(cfg.log_dir, f"run_{int(time.time())}.csv")
        self.fp = open(log_file, 'w', newline='')
        self.logger = csv.writer(self.fp)
        self.logger.writerow(["t", "mode", "state", "x", "y", "psi_deg", "v", 
                             "front_gap", "ttc", "left_clear", "v_cmd", "delta_deg",
                             "loop_ms", "wd", "guard_intv", "min_ttc", "stop_reason"])
        print(f"[LOG] {log_file}")
        
        # Dataset (dummy)
        self.shard = None
        self.label_fifo: Deque = deque()
        self.tau_steps = 0
        self.tau_logger = TauLogger()
        
        # Param server
        self.param_srv = ParamServer(cfg.yaml_path)
        self.last_yaml_check = 0.0
        
        # Control
        self._stop = False
        self._stop_flag = False
        self._stop_reason = ""
        self._test_time: Optional[float] = None  # For test harness
        self.last_log: Dict = {}
        
        # Signal handler
        def sig_handler(signum, frame):
            print(f"\n{Colors.YELLOW}[SIG] Received signal {signum}{Colors.RESET}")
            self._stop = True
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
    
    def _current_time(self) -> float:
        return self._test_time if self._test_time is not None else time.time()
    
    def time_in_state(self) -> float:
        return self._current_time() - self.last_state_change
    
    def set_state(self, new_state: State):
        if new_state == self.state:
            return
        old = self.state.name
        self.state = new_state
        self.last_state_change = self._current_time()
        print_state_change(old, new_state.name)
        
        # 상태별 초기화
        if new_state == State.EVADE_L:
            self.evade_timeout = self._current_time() + 2.0
        elif new_state == State.KEEP_L1:
            self.keep_l1_earliest_return = self._current_time() + self.bp.T_KEEP_L1_MIN
        elif new_state == State.RETURN_TO_L2:
            self._rt2_stable = 0
            self._last_return_y = self.pose.y
        elif new_state == State.KEEP_L2:
            self.cooldown_until = self._current_time() + self.bp.COOLDOWN
    
    def _proportional_control(self, target_lane: int, v_now: float) -> float:
        """
        순수 P제어 (라인센서 우선, 없으면 pose 기반)
        """
        # 1. 라인 센서 체크
        ey_line, valid_line = (self.lines.read_L2() if target_lane == 2 else self.lines.read_L1())
        
        if valid_line:
            # 라인이 보이면 라인 기준으로 제어
            return self.lat.delta_cmd_deg(ey_line, self.pose.psi, v_now, self.state)
        
        # 2. 라인이 안 보이면 pose 기반 제어
        yc = lane_center_y(target_lane, self.rp.W)
        ey = yc - self.pose.y  # 목표와의 lateral error
        
        return self.lat.delta_cmd_deg(ey, self.pose.psi, v_now, self.state)
    
    def teacher_action(self, v_now: float, v_ref: float, left_clear: bool) -> Tuple[float, float]:
        """Teacher policy - Proportional Control"""
        v_teacher = v_ref
        
        # 캐시된 lane center 사용
        l1_center = lane_center_y(1, self.rp.W)
        l2_center = lane_center_y(2, self.rp.W)
        
        # 상태별 전환 로직
        if self.state == State.EVADE_L:
            temp_delta = self._proportional_control(1, v_now)
            y_next, psi_next = self._predict_next_pose(v_now, temp_delta)
            
            near_l1 = abs(y_next - l1_center) <= 0.15  # 0.30 → 0.15로 엄격화
            heading_ok = abs(psi_next) < 15.0 * _DEG2RAD  # 25 → 15도로 엄격화
            overshoot = (y_next > l1_center + 0.35)  # L1을 지나쳐서 더 왼쪽으로
            time_expired = hasattr(self, "evade_timeout") and (self._current_time() >= self.evade_timeout)
            early_switch = abs(self.pose.y - l1_center) <= 0.10 and self.time_in_state() > 0.5  # 0.15 → 0.10
            min_time = self.time_in_state() > 0.3  # 최소 0.3초는 EVADE_L 유지
            
            if (near_l1 and heading_ok and min_time) or overshoot or time_expired or (early_switch and min_time):
                if self.cfg.debug_print:
                    print(f"{Colors.BLUE}[PREDICT] EVADE→KEEP_L1: y_next={y_next:.3f}, "
                          f"psi_next={psi_next * _RAD2DEG:.1f}°{Colors.RESET}")
                self.set_state(State.KEEP_L1)
        
        elif self.state == State.KEEP_L1:
            dist_from_l1 = abs(self.pose.y - l1_center)
            
            if dist_from_l1 > 0.40:
                print(f"{Colors.YELLOW}[WARN] L1 overshoot (dist={dist_from_l1:.3f}m){Colors.RESET}")
                self.set_state(State.RETURN_TO_L2)
            else:
                temp_delta = self._proportional_control(1, v_now)
                y_next, psi_next = self._predict_next_pose(v_now, temp_delta)
                dist_next_L1 = abs(y_next - l1_center)
                
                near = dist_next_L1 < 0.35
                head_ok = abs(psi_next) < 20.0 * _DEG2RAD
                
                front_gap_val = self.front_gap if self.front_gap is not None else math.inf
                rel_speed_val = self.infra_roi.rel_speed
                
                if front_gap_val != math.inf and rel_speed_val is not None and rel_speed_val > 0:
                    ttc = front_gap_val / rel_speed_val
                else:
                    ttc = math.inf
                
                safe_return = (front_gap_val >= 2.0) and (ttc > 1.5) and left_clear
                cooldown_ok = self._current_time() >= getattr(self, "cooldown_until", 0.0)
                stay_ok = self._current_time() >= getattr(self, "keep_l1_earliest_return", 0.0)
                time_in_L1 = self.time_in_state()
                
                if stay_ok and cooldown_ok and safe_return and (near and head_ok):
                    if self.cfg.debug_print:
                        print(f"{Colors.BLUE}[PREDICT] KEEP_L1→RETURN: dist_next={dist_next_L1:.3f}{Colors.RESET}")
                    self.set_state(State.RETURN_TO_L2)
                elif time_in_L1 > 2.5 and safe_return:
                    self.set_state(State.RETURN_TO_L2)
        
        # 상태별 제어 계산
        if self.state == State.SAFE_STOP:
            delta_deg = 0.0
            v_ref = 0.0
        elif self.state == State.EVADE_L:
            delta_deg = self._proportional_control(1, v_now)
            
            # Rate limiting for EVADE_L
            max_delta_change = 1.5  # 1.5도/스텝 = 30도/초 (20Hz 기준)
            lo = self.delta_prev - max_delta_change
            hi = self.delta_prev + max_delta_change
            delta_deg = hi if delta_deg > hi else lo if delta_deg < lo else delta_deg
            
            dmax = self.vp.DELTA_MAX_DEG
            delta_deg = dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg
        elif self.state == State.KEEP_L1:
            delta_deg = self._proportional_control(1, v_now)
            
            # Rate limiting for KEEP_L1
            max_delta_change = 1.5  # 1.5도/스텝 = 30도/초 (20Hz 기준)
            lo = self.delta_prev - max_delta_change
            hi = self.delta_prev + max_delta_change
            delta_deg = hi if delta_deg > hi else lo if delta_deg < lo else delta_deg
            
            dmax = self.vp.DELTA_MAX_DEG
            delta_deg = dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg
        elif self.state == State.DECEL_L2:
            # ey = 차선 중심 - 차량 위치 (라인이 왼쪽이면 ey>0)
            ey = l2_center - self.pose.y
            delta_deg = 0.8 * ey
            dmax_lim = self.vp.DELTA_MAX_DEG * 0.4
            delta_deg = dmax_lim if delta_deg > dmax_lim else -dmax_lim if delta_deg < -dmax_lim else delta_deg
        elif self.state == State.RETURN_TO_L2:
            delta_deg = self._proportional_control(2, v_now)
            
            # Rate limiting for RETURN_TO_L2
            max_delta_change = 1.5  # 1.5도/스텝 = 30도/초 (20Hz 기준)
            lo = self.delta_prev - max_delta_change
            hi = self.delta_prev + max_delta_change
            delta_deg = hi if delta_deg > hi else lo if delta_deg < lo else delta_deg
            
            v_teacher = v_now * 1.1 if v_ref > v_now * 1.1 else v_ref
        elif self.state == State.KEEP_L2:
            delta_deg = self._proportional_control(2, v_now)
            dmax = self.vp.DELTA_MAX_DEG
            delta_deg = dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg
        else:
            delta_deg = self._proportional_control(2, v_now)
            dmax = self.vp.DELTA_MAX_DEG
            delta_deg = dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg
        
        dmax = self.vp.DELTA_MAX_DEG
        delta_deg = dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg
        self.delta_prev = delta_deg
        
        return delta_deg, (v_teacher if self.state == State.RETURN_TO_L2 else v_ref)
    
    def _return_complete_guard(self):
        """RETURN_TO_L2 완료 판정"""
        if self.state != State.RETURN_TO_L2:
            return
        
        l2_center = lane_center_y(2, self.rp.W)
        y_next, psi_next = self._predict_next_pose(self.speed._v, self.delta_prev)
        dist_next = abs(y_next - l2_center)
        
        near_center = dist_next <= 0.20
        heading_ok = abs(psi_next) <= 20.0 * _DEG2RAD
        steer_ok = abs(self.delta_prev) <= 12.0
        
        if near_center and heading_ok and steer_ok:
            self._rt2_stable = getattr(self, "_rt2_stable", 0) + 1
        else:
            self._rt2_stable = 0
        
        required_stable = 1
        
        if self._rt2_stable >= required_stable:
            if self.cfg.debug_print:
                print(f"{Colors.GREEN}[COMPLETE] Stable: y_next={y_next:.3f}, "
                      f"psi={psi_next * _RAD2DEG:.1f}°, steps={self._rt2_stable}{Colors.RESET}")
            self.set_state(State.KEEP_L2)
            self._rt2_stable = 0
            return
        
        t_in_return = self._current_time() - self.last_state_change
        if t_in_return > 1.0:
            if hasattr(self, '_last_return_y'):
                crossed = (self._last_return_y * y_next) < 0
                cross_near = dist_next <= 0.30
                cross_heading = abs(psi_next) <= 25.0 * _DEG2RAD
                
                if crossed and cross_near and cross_heading:
                    if self.cfg.debug_print:
                        print(f"{Colors.GREEN}[COMPLETE] Crossing: y_next={y_next:.3f}{Colors.RESET}")
                    self.set_state(State.KEEP_L2)
                    self._rt2_stable = 0
                    return
        
        self._last_return_y = y_next
        
        if t_in_return > 1.6 and dist_next <= 0.35 and abs(psi_next) <= 25.0 * _DEG2RAD:
            if self.cfg.debug_print:
                print(f"{Colors.GREEN}[COMPLETE] Timeout: t={t_in_return:.1f}s{Colors.RESET}")
            self.set_state(State.KEEP_L2)
            self._rt2_stable = 0
            return
        
        if abs(psi_next) > 40.0 * _DEG2RAD and t_in_return > 1.2:
            print(f"{Colors.RED}[ABORT] Heading runaway (psi={psi_next * _RAD2DEG:.1f}°){Colors.RESET}")
            self.set_state(State.KEEP_L2)
            self._rt2_stable = 0
    
    def _predict_next_pose(self, v_cmd: float, delta_cmd_deg: float) -> Tuple[float, float]:
        """1-step ahead pose prediction"""
        delta_rad = delta_cmd_deg * _DEG2RAD
        L_safe = self.vp.L if self.vp.L > 1e-6 else 1e-6
        psi_dot = (v_cmd / L_safe) * math.tan(delta_rad)
        psi_next = self.pose.psi + psi_dot * self.dt
        y_next = self.pose.y + v_cmd * math.sin(psi_next) * self.dt
        return y_next, psi_next
    
    def hot_reload_params(self):
        if not self.cfg.yaml_path:
            return
        now = self._current_time()
        if now - self.last_yaml_check < 0.5:
            return
        self.last_yaml_check = now
        self.param_srv.load()
        self.param_srv.apply(self.vp, self.rp, self.bp, self.cp)
    
    def step_once(self):
        try:
            t0 = self._current_time()
            
            if abs(self.pose.y) > self.rp.MAX_Y_DEVIATION:
                print(f"{Colors.RED}[SAFETY] Out of bounds (y={self.pose.y:.2f}m){Colors.RESET}")
                self.set_state(State.SAFE_STOP)
                self._stop_flag = True
                self._stop_reason = "OUT_OF_BOUNDS"
                return
            
            v_now = self.speed.read()
            
            roi = self.infra_roi
            front_gap = validate_sensor(roi.front_gap, 0.0, 10.0, "front_gap") if roi.front_gap is not None else None
            rel_speed = roi.rel_speed
            roi_left_clear = roi.roi_left_clear
            
            self.front_gap = front_gap
            left_clear = self.left_clear_override if self.left_clear_override is not None else roi_left_clear
            
            if front_gap is None:
                ttc = float('inf')
            elif rel_speed is not None and rel_speed > 0:
                ttc = front_gap / rel_speed
            else:
                ttc = float('inf')
            
            need_action = (front_gap is not None and front_gap < self.bp.G_TRIG) or (ttc < self.bp.TTC_TRIG)
            
            # 캐시된 lane center 사용
            y_L1 = lane_center_y(1, self.rp.W)
            y_L2 = lane_center_y(2, self.rp.W)
            dist_to_L1 = abs(self.pose.y - y_L1)
            dist_to_L2 = abs(self.pose.y - y_L2)
            
            # STATE MACHINE
            if self.state == State.KEEP_L2:
                if need_action:
                    if left_clear and ttc > self.bp.TTC_EVADE_MIN:
                        if self.cfg.debug_print:
                            print(f"{Colors.YELLOW}[EVADE] fg={front_gap:.2f}, ttc={ttc:.2f}, "
                                  f"left_clear={left_clear}{Colors.RESET}")
                        self.set_state(State.EVADE_L)
                    else:
                        if self.cfg.debug_print:
                            print(f"{Colors.RED}[DECEL] fg={front_gap:.2f}, ttc={ttc:.2f}, "
                                  f"left_clear={left_clear}{Colors.RESET}")
                        self.set_state(State.DECEL_L2)
            
            elif self.state == State.DECEL_L2:
                if (front_gap is None) or (front_gap >= self.bp.G_TRIG and ttc >= self.bp.TTC_TRIG):
                    self.set_state(State.KEEP_L2)
            
            elif self.state == State.EVADE_L:
                if self.pose.y < y_L1 - 0.4:
                    print(f"{Colors.RED}[ABORT] Overshoot detected (y={self.pose.y:.2f}m){Colors.RESET}")
                    self.set_state(State.KEEP_L1)
                elif ttc < self.bp.TTC_MIN:
                    print(f"{Colors.RED}[ABORT] Evasion aborted{Colors.RESET}")
                    self.set_state(State.DECEL_L2)
            
            elif self.state == State.RETURN_TO_L2:
                self._return_complete_guard()
                if ttc < self.bp.TTC_MIN:
                    print(f"{Colors.RED}[ABORT] Return aborted{Colors.RESET}")
                    self.set_state(State.KEEP_L1)
            
            elif self.state == State.SAFE_STOP:
                pass
            
            # Longitudinal control
            v_ref = self.lon.advisory_speed(v_now, front_gap, rel_speed)
            
            # Teacher action (P control)
            use_teacher = (self.cfg.run_mode in (RunMode.TEACHER, RunMode.SHADOW))
            
            if use_teacher:
                delta_teacher_deg, v_teacher = self.teacher_action(v_now, v_ref, left_clear)
            else:
                delta_teacher_deg = 0.0
                v_teacher = v_ref
            
            delta_student_deg = 0.0
            
            if self.cfg.run_mode == RunMode.STUDENT:
                delta_deg = delta_student_deg
                v_cmd = v_ref
            elif self.cfg.run_mode == RunMode.SHADOW:
                delta_deg = delta_teacher_deg
                v_cmd = v_teacher
            else:
                delta_deg = delta_teacher_deg
                v_cmd = v_teacher
            
            # Safety guard
            v_cmd, delta_deg = self.guard.apply(v_cmd, delta_deg, v_now, front_gap, rel_speed)
            
            # Send command
            ok = self.comm.send(v_cmd, delta_deg)
            
            # Update pose
            self.pose.step(v_cmd, delta_deg, self.dt)
            self.speed.update_from_command(v_cmd, self.dt)
            
            if not ok:
                self._stop_flag = True
                self._stop_reason = "COMM_FAIL"
            
            loop_ms = (self._current_time() - t0) * 1000.0
            wd_state = self.watchdog.step(loop_ms)
            
            if wd_state == 'DEGRADE':
                v_ref = 0.8 if v_ref > 0.8 else v_ref
            elif wd_state == 'STOP':
                self.set_state(State.SAFE_STOP)
                self._stop_flag = True
                self._stop_reason = "WD_BREACH"
            
            self.last_log = {
                "t": t0, "mode": self.cfg.run_mode.name, "state": self.state.name,
                "x": self.pose.x, "y": self.pose.y, "psi_deg": self.pose.psi * _RAD2DEG,
                "v": v_now, "front_gap": front_gap,
                "ttc": ttc if ttc != float('inf') else float('inf'),
                "left_clear": int(left_clear), "v_cmd": v_cmd, "delta_deg": delta_deg,
                "loop_ms": loop_ms, "wd": wd_state, "guard_intv": self.guard.interventions,
                "min_ttc": self.guard.min_ttc if self.guard.min_ttc != float('inf') else float('inf'),
                "stop_reason": ""
            }
            
        except Exception as e:
            print(f"{Colors.RED}[ERROR] step_once failed: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
            self._stop = True
    
    def run(self):
        print(f"{Colors.CYAN}[RUN] mode={self.cfg.run_mode.name}, hz={1.0 / self.dt:.1f}{Colors.RESET}")
        next_t = time.time()
        
        try:
            while not (self._stop or self._stop_flag):
                t0 = time.time()
                self.hot_reload_params()
                self.step_once()
                
                if self.last_log:
                    rec = [
                        f"{self.last_log.get('t'):.3f}",
                        str(self.last_log.get("mode")),
                        str(self.last_log.get("state")),
                        f"{self.last_log.get('x', 0.0):.2f}",
                        f"{self.last_log.get('y', 0.0):.2f}",
                        f"{self.last_log.get('psi_deg', 0.0):.1f}",
                        f"{self.last_log.get('v', 0.0):.2f}",
                        "NA" if self.last_log.get('front_gap') is None else f"{self.last_log.get('front_gap'):.2f}",
                        "INF" if self.last_log.get('ttc') == float('inf') else f"{self.last_log.get('ttc'):.2f}",
                        int(self.last_log.get('left_clear', 1)),
                        f"{self.last_log.get('v_cmd', 0.0):.2f}",
                        f"{self.last_log.get('delta_deg', 0.0):.1f}",
                        f"{self.last_log.get('loop_ms', 0.0):.1f}",
                        str(self.last_log.get('wd', 'OK')),
                        int(self.last_log.get('guard_intv', 0)),
                        "INF" if self.last_log.get('min_ttc') == float('inf') else f"{self.last_log.get('min_ttc'):.2f}",
                        str(self.last_log.get('stop_reason', ''))
                    ]
                    self.logger.writerow(rec)
                    self.fp.flush()
                
                next_t += self.dt
                sleep_t = next_t - time.time()
                if sleep_t > 0:
                    time.sleep(sleep_t)
                else:
                    next_t = time.time()
            
            v_now = self.speed.read()
            reason = self._stop_reason if self._stop_reason else "STOP"
            min_ttc_val = self.guard.min_ttc if self.guard.min_ttc != float('inf') else float('inf')
            
            self.logger.writerow([
                f"{time.time():.3f}", self.cfg.run_mode.name, "STOP",
                f"{self.pose.x:.2f}", f"{self.pose.y:.2f}", f"{self.pose.psi * _RAD2DEG:.1f}",
                f"{v_now:.2f}", "NA", "INF", 1, "0.00", "0.0", "0.0", "STOP",
                self.guard.interventions,
                f"{min_ttc_val if min_ttc_val != float('inf') else 'INF'}",
                reason
            ])
            self.fp.flush()
        
        finally:
            if hasattr(self, 'fp') and self.fp:
                self.fp.close()
        
        print(f"{Colors.GREEN}[RUN] Stopped.{Colors.RESET}")

# =============================
# CLI
# =============================
def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RC Car Lane Change - Proportional Control Version")
    p.add_argument("--hz", type=float, default=20.0)
    p.add_argument("--run_mode", type=str, default="teacher", choices=["teacher", "shadow", "student"])
    p.add_argument("--comm", type=str, default="dummy", choices=["dummy", "can"])
    p.add_argument("--hb_period", type=float, default=0.5)
    p.add_argument("--log_dir", type=str, default="./runs")
    p.add_argument("--yaml", type=str, default=None)
    p.add_argument("--debug", action="store_true", help="Enable debug output")
    p.add_argument("--test", action="store_true", help="Run test scenarios")
    
    # Behavior params
    p.add_argument("--g_trig", type=float, default=1.8)
    p.add_argument("--ttc_trig", type=float, default=2.0)
    p.add_argument("--ttc_min", type=float, default=0.8)
    p.add_argument("--ttc_evade_min", type=float, default=1.2)
    p.add_argument("--t_keep_l1_min", type=float, default=1.0)
    p.add_argument("--g_return_safe", type=float, default=2.5)
    p.add_argument("--k_ttc", type=float, default=1.5)
    
    # Gate params
    # Vehicle params
    p.add_argument("--L", type=float, default=0.20)
    p.add_argument("--B", type=float, default=0.15)
    p.add_argument("--v_max", type=float, default=1.0)
    p.add_argument("--delta_max", type=float, default=20.0)
    p.add_argument("--delta_rate", type=float, default=200.0)
    p.add_argument("--a_max", type=float, default=2.0)
    p.add_argument("--a_min", type=float, default=-3.0)
    p.add_argument("--wheel_rate", type=float, default=3.0)
    
    # Road params
    p.add_argument("--lane_width", type=float, default=0.25)
    p.add_argument("--max_y_deviation", type=float, default=3.0)
    
    # Controller params
    p.add_argument("--k_ey_keep", type=float, default=1.2)
    p.add_argument("--k_ey_evade", type=float, default=1.8)
    p.add_argument("--k_ey_return", type=float, default=1.8)
    p.add_argument("--k_delta_rate", type=float, default=0.05)
    p.add_argument("--k_psi_keep", type=float, default=0.3)
    p.add_argument("--k_psi_evade", type=float, default=0.4)
    p.add_argument("--k_psi_return", type=float, default=0.5)
    
    p.add_argument("--assume_straight_nominal", type=int, default=1)
    return p.parse_args()

def main():
    args = build_args()
    
    cfg = AppConfig(
        hz=args.hz, run_mode=RunMode[args.run_mode.upper()],
        assume_straight_nominal=args.assume_straight_nominal,
        comm=args.comm, hb_period=args.hb_period,
        log_dir=args.log_dir, yaml_path=args.yaml,
        debug_print=1 if args.debug else 0
    )
    
    vp = VehicleParams(L=args.L, B=args.B, V_MAX=args.v_max,
                       DELTA_MAX_DEG=args.delta_max, DELTA_RATE_MAX_DEGPS=args.delta_rate,
                       A_MAX=args.a_max, A_MIN=args.a_min, WHEEL_RATE_MAX=args.wheel_rate)
    
    rp = RoadParams(W=args.lane_width, MAX_Y_DEVIATION=args.max_y_deviation)
    
    bp = BehaviorParams(G_TRIG=args.g_trig, TTC_TRIG=args.ttc_trig, TTC_MIN=args.ttc_min,
                        TTC_EVADE_MIN=args.ttc_evade_min, T_KEEP_L1_MIN=args.t_keep_l1_min,
                        G_RETURN_SAFE=args.g_return_safe, K_TTC=args.k_ttc)
    
    cp = ControllerParams(k_ey_keep=args.k_ey_keep, k_ey_evade=args.k_ey_evade,
                         k_ey_return=args.k_ey_return, k_delta_rate=args.k_delta_rate,
                         k_psi_keep=args.k_psi_keep, k_psi_evade=args.k_psi_evade,
                         k_psi_return=args.k_psi_return)
    
    app = App(cfg, vp, rp, bp, cp)
    
    if args.test:
        print("\n" + "=" * 60)
        print(f"{Colors.CYAN}{Colors.BOLD}🧪 RUNNING TEST MODE (Proportional Control){Colors.RESET}")
        print("=" * 60 + "\n")
        harness = TestHarness(app)
        scenarios = create_test_scenarios()
        for scenario_name, timeline, expected_states in scenarios:
            harness.run_scenario(scenario_name, timeline, expected_states)
        harness.print_summary()
    else:
        print(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}  PROPORTIONAL CONTROL VERSION{Colors.RESET}")
        print(f"{Colors.GREEN}{'='*60}{Colors.RESET}\n")
        
        app.run()

if __name__ == "__main__":
    main()