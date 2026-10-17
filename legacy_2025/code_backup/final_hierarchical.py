import argparse
import csv
import json
import math
import os
import signal
import socket
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, List, Deque, Dict

try:
    import numpy as np
except Exception:
    print("[ERR] numpy is required.")
    sys.exit(1)

# PyTorch for Student Policy
try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None
    print("[WARN] PyTorch not available. Student policy will be disabled.")

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
    import osqp  # type: ignore
    import scipy.sparse as sp  # type: ignore
except Exception:
    osqp = None
    sp = None
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# =============================
# Optimized inline functions
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

class RunMode(Enum):
    TEACHER = auto()
    SHADOW = auto()
    STUDENT = auto()

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
    WHEEL_RATE_MAX: float = 3.0
    _delta_max_rad: Optional[float] = None
    
    def __post_init__(self):
        self._delta_max_rad = self.DELTA_MAX_DEG * _DEG2RAD

@dataclass
class RoadParams:
    W: float = 0.30
    MAX_Y_DEVIATION: float = 3.0

@dataclass
class BehaviorParams:
    # Conservative parameters validated in simulation (100% success rate)
    G_TRIG: float = 1.2  # Evade trigger distance (m) - increased for earlier detection
    G_SAFE_MIN: float = 0.20  # Emergency stop distance (m) - increased for larger safety margin
    # NOTE: G_RETURN_SAFE removed - return based on time only (T_KEEP_L1_MIN)
    T_KEEP_L1_MIN: float = 0.6  # Minimum time in L1 before returning (s) - increased for safer maneuver
    COOLDOWN: float = 0.3  # State transition cooldown (s)
    NEAR_BAND_L1: float = 0.08  # Arrival threshold for L1 (m)

@dataclass
class ControllerParams:
    k_ey_keep: float = 1.5
    k_ey_evade: float = 2.0
    k_ey_return: float = 1.8
    k_delta_rate: float = 0.05

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
    lidar_port: int = 8000
    ir_sensor_spacing: float = 0.04
    # Hierarchical mode: Student policy paths
    student_model_path: str = "models/policy_best.pth"
    student_stats_path: str = "models/normalization_stats.json"

@dataclass
class InfraROI:
    front_gap: Optional[float] = None
    roi_left_clear: bool = True
    timestamp: float = 0.0

# =============================
# Utils
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
        'SAFE_STOP': Colors.MAGENTA
    }
    old_color = color_map.get(old_state, '')
    new_color = color_map.get(new_state, '')
    print(f"{Colors.BOLD}[STATE]{Colors.RESET} {old_color}{old_state}{Colors.RESET} -> {new_color}{new_state}{Colors.RESET}")

# =============================
# IR Sensor Processing
# =============================
def ir_to_y_position(ir_left: int, ir_center: int, ir_right: int, sensor_spacing: float = 0.05) -> Optional[float]:
    """
    IR 센서 3개 binary 값으로 차선 중심으로부터 y 편차 계산
    
    Args:
        ir_left, ir_center, ir_right: 0 or 1 (1=라인 감지)
        sensor_spacing: 센서 간격 (m) - 실측 필요
    
    Returns:
        y: 차선 중심 기준 좌우 편차 (m)
            음수(-) = 오른쪽으로 치우침
            양수(+) = 왼쪽으로 치우침
            None = 라인 감지 실패
    """
    # 패턴별 위치 추정
    if ir_center == 1:
        # 중앙 센서가 라인 위 = 거의 중심
        if ir_left == 1 and ir_right == 0:
            return sensor_spacing * 0.5  # 약간 왼쪽
        elif ir_left == 0 and ir_right == 1:
            return -sensor_spacing * 0.5  # 약간 오른쪽
        else:
            return 0.0  # 정중앙
    
    elif ir_left == 1 and ir_center == 0 and ir_right == 0:
        return sensor_spacing  # 왼쪽으로 많이 치우침
    
    elif ir_right == 1 and ir_center == 0 and ir_left == 0:
        return -sensor_spacing  # 오른쪽으로 많이 치우침
    
    else:
        # 라인 없음 or 이상 패턴
        return None

# =============================
# LiDAR WiFi Processing
# =============================
class YDLidarWiFi:
    """YDLidar WiFi 통신 수신 클래스"""
    
    def __init__(self, port: int = 8000):
        """
        Args:
            port: UDP 포트 (YDLidar 설정에 따라 다름, 기본 8000)
        """
        self.port = port
        self.sock = None
        self.points = []  # [(x, y, intensity), ...]
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        
    def start(self):
        """백그라운드 수신 시작"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self.sock.bind(('', self.port))
            self.sock.settimeout(0.1)  # 100ms timeout
            
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.thread.start()
            print(f"{Colors.GREEN}[LiDAR] WiFi receiver started on port {self.port}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[LiDAR] Failed to start: {e}{Colors.RESET}")
            self.running = False
    
    def stop(self):
        """수신 중지"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.sock:
            self.sock.close()
    
    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                print(f"[DEBUG] Recv {len(data)} bytes from {addr}")

                points = self._parse_packet(data)
                print(f"[DEBUG] Parsed points {len(points)}")
                
                if points:
                    with self.lock:
                        self.points = points  # 최신 프레임으로 교체
            
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:  # 정상 종료가 아닐 때만 출력
                    print(f"{Colors.YELLOW}[LiDAR] Receive error: {e}{Colors.RESET}")
    
    def _parse_packet(self, data: bytes) -> List[Tuple[float, float, float]]:
        """
        패킷 파싱 (YDLidar 형식)
        
        일반적인 포맷 예시:
        - 헤더 (4바이트): 0xAA 0x55 + 포인트 개수 (uint16)
        - 포인트: x(float32), y(float32), intensity(uint8) 반복
        
        실제 형식은 YDLidar 문서 확인 필요!
        """
        if len(data) < 4:
            return []
        
        # 헤더 체크 (실제 형식에 맞게 수정 필요)
        if data[0] != 0xAA or data[1] != 0x55:
            return []
        
        num_points = struct.unpack('<H', data[2:4])[0]  # little-endian uint16
        points = []
        
        offset = 4
        point_size = 9  # float(4) + float(4) + uint8(1)
        
        for i in range(num_points):
            if offset + point_size > len(data):
                break
            
            x = struct.unpack('<f', data[offset:offset+4])[0]
            y = struct.unpack('<f', data[offset+4:offset+8])[0]
            intensity = data[offset+8]
            
            points.append((x, y, intensity))
            offset += point_size
        
        return points
    
    def get_points(self) -> List[Tuple[float, float, float]]:
        """최신 포인트클라우드 반환"""
        with self.lock:
            return self.points.copy()


class InfraLidarProcessor:
    """
    인프라 라이다 포인트클라우드 처리 (2차로 갓길 설치)
    
    좌표계:
    - W (월드/도로): x_W = 전방(+), y_W = 왼쪽(+), 오른쪽(-)
    - R (차량): x_R = 전방(+), y_R = 왼쪽(+), 오른쪽(-)
    - L (라이다): x_L = 라이다 정면, y_L = 좌/우
    
    라이다 위치: 2차로 갓길 (y_W = -(lane_width/2 + margin))
    """
    
    def __init__(self, vehicle_width: float = 0.15, vehicle_length: float = 0.20,
                 lane_width: float = 0.30, lidar_margin: float = 0.05):
        self.vehicle_width = vehicle_width
        self.vehicle_length = vehicle_length
        self.lane_width = lane_width
        self.lidar_margin = lidar_margin
        
        # 라이다 위치 (월드 좌표계)
        # 도로 옆 1.5m 위치, 높이 1m, 도로와 평행
        self.lidar_x_W = 0.0  # 도로 시작점
        self.lidar_y_W = 1.5  # 트랙 옆 1.5m 위치
        self.lidar_z_W = 1.0  # 높이 1m (RC카 전체 보이게)
        self.lidar_yaw_W = 0.0  # 도로 방향과 평행
    
    def lidar_to_world(self, points_L: List[Tuple[float, float, float]]) -> np.ndarray:
        """
        라이다 좌표계(L) → 월드 좌표계(W) 변환
        
        Args:
            points_L: [(x_L, y_L, z_L), ...] 라이다 좌표계 포인트
        
        Returns:
            points_W: (N, 3) 월드 좌표계 포인트
        """
        if not points_L:
            return np.array([]).reshape(0, 3)
        
        pc_L = np.array(points_L)  # (N, 3)
        
        # 회전 행렬 (라이다 yaw만 고려, roll/pitch 무시)
        yaw = self.lidar_yaw_W
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        R_WL = np.array([
            [cos_yaw, -sin_yaw, 0],
            [sin_yaw,  cos_yaw, 0],
            [0,        0,       1]
        ])
        
        # 변환: p_W = R_WL @ p_L + p_LW
        pc_W = (R_WL @ pc_L.T).T  # (N, 3)
        pc_W[:, 0] += self.lidar_x_W
        pc_W[:, 1] += self.lidar_y_W
        pc_W[:, 2] += self.lidar_z_W
        
        return pc_W
    
    def world_to_car(self, points_W: np.ndarray, car_x_W: float, car_y_W: float, car_yaw_W: float) -> np.ndarray:
        """
        월드 좌표계(W) → 차량 좌표계(R) 변환
        
        Args:
            points_W: (N, 3) 월드 좌표계 포인트
            car_x_W, car_y_W, car_yaw_W: 차량 pose (월드 좌표계)
        
        Returns:
            points_R: (N, 2) 차량 좌표계 포인트 (x_R, y_R)
        """
        if points_W.shape[0] == 0:
            return np.array([]).reshape(0, 2)
        
        # 평행이동: 차량 위치로 이동
        p_shift = points_W[:, :2].copy()
        p_shift[:, 0] -= car_x_W
        p_shift[:, 1] -= car_y_W
        
        # 회전: 차량 프레임으로 정렬
        cos_psi = math.cos(car_yaw_W)
        sin_psi = math.sin(car_yaw_W)
        R_RW = np.array([
            [cos_psi,  sin_psi],
            [-sin_psi, cos_psi]
        ])
        
        pc_R = (R_RW @ p_shift.T).T  # (N, 2)
        
        return pc_R
    
    def check_vehicle_occlusion(self, points_R: np.ndarray, 
                                car_x_W: float, car_y_W: float, car_yaw_W: float) -> Tuple[np.ndarray, List[Tuple[float, float]]]:
        """
        차량이 가리는 영역(occlusion) 체크
        
        라이다 → 차량 사이에 있는 각도 범위는 그 뒤쪽 1차선 영역을 "모름 = 점유"로 처리
        
        Args:
            points_R: (N, 2) 차량 좌표계 포인트
            car_x_W, car_y_W, car_yaw_W: 차량 pose (월드 좌표계)
        
        Returns:
            visible_mask: (N,) 가시 영역 포인트 마스크
            occluded_angle_ranges: 가려진 각도 범위 리스트 [(min_angle, max_angle), ...]
        """
        if points_R.shape[0] == 0:
            return np.array([], dtype=bool), []
        
        # 라이다 위치를 차량 좌표계로 변환
        lidar_pos_W = np.array([self.lidar_x_W, self.lidar_y_W])
        lidar_pos_R = self.world_to_car(
            np.array([[lidar_pos_W[0], lidar_pos_W[1], 0.0]]),
            car_x_W, car_y_W, car_yaw_W
        )[0]  # (2,)
        
        # 차량 바운딩 박스 (차량 좌표계 기준, 차량 중심이 원점)
        car_half_length = self.vehicle_length / 2.0
        car_half_width = self.vehicle_width / 2.0
        
        # 차량 바운딩 박스의 4개 모서리 (차량 좌표계)
        car_corners_R = np.array([
            [car_half_length, car_half_width],   # 전방 우측
            [car_half_length, -car_half_width], # 전방 좌측
            [-car_half_length, -car_half_width], # 후방 좌측
            [-car_half_length, car_half_width]   # 후방 우측
        ])
        
        # 라이다에서 차량 모서리까지의 각도 계산
        corners_from_lidar = car_corners_R - lidar_pos_R
        corner_angles = np.arctan2(corners_from_lidar[:, 1], corners_from_lidar[:, 0])
        
        # 가려진 각도 범위 계산 (최소/최대 각도)
        min_occluded_angle = np.min(corner_angles)
        max_occluded_angle = np.max(corner_angles)
        
        # 각 포인트의 각도 계산 (라이다 기준)
        points_from_lidar = points_R - lidar_pos_R
        point_angles = np.arctan2(points_from_lidar[:, 1], points_from_lidar[:, 0])
        point_distances = np.linalg.norm(points_from_lidar, axis=1)
        
        # 차량까지의 거리 (각도별 최소 거리)
        # 간단한 근사: 차량 중심까지 거리
        car_center_R = np.array([0.0, 0.0])
        car_center_from_lidar = car_center_R - lidar_pos_R
        car_center_dist = np.linalg.norm(car_center_from_lidar)
        car_center_angle = np.arctan2(car_center_from_lidar[1], car_center_from_lidar[0])
        
        # 가시성 체크: 각도가 가려진 범위에 있고, 거리가 차량보다 가까우면 가려짐
        # 하지만 실제로는 더 정교한 기하학적 계산 필요
        # 여기서는 간단히: 가려진 각도 범위 내의 포인트는 제외하지 않고,
        # 대신 left_clear 판단 시 보수적으로 처리
        
        # 일단 모든 포인트를 가시로 간주
        # (실제 occlusion은 left_clear 판단 시 보수적으로 처리)
        visible_mask = np.ones(points_R.shape[0], dtype=bool)
        
        occluded_angle_ranges = [(min_occluded_angle, max_occluded_angle)]
        
        return visible_mask, occluded_angle_ranges
    
    def process(self, points_L: List[Tuple[float, float, float]], 
                car_x_W: float, car_y_W: float, car_yaw_W: float) -> Tuple[Optional[float], bool]:
        """
        인프라 라이다 포인트클라우드 처리
        
        Args:
            points_L: 라이다 좌표계 포인트 [(x_L, y_L, z_L), ...]
            car_x_W, car_y_W, car_yaw_W: 차량 pose (월드 좌표계)
        
        Returns:
            (front_gap, left_clear)
        """
        if not points_L:
            return None, True
        
        # 1. L → W 변환
        points_W = self.lidar_to_world(points_L)
        
        # 2. W → R 변환
        points_R = self.world_to_car(points_W, car_x_W, car_y_W, car_yaw_W)
        
        # 3. 차량 가림 체크
        visible_mask, occluded_ranges = self.check_vehicle_occlusion(
            points_R, car_x_W, car_y_W, car_yaw_W
        )
        points_R_visible = points_R[visible_mask]
        
        if points_R_visible.shape[0] == 0:
            return None, True  # 가시 포인트 없음 → 보수적으로 left_clear=True (안전)
        
        # 4. front_gap: 전방 ±10cm 범위 최소 거리
        margin = 0.1
        front_mask = (points_R_visible[:, 0] > 0) & (np.abs(points_R_visible[:, 1]) < self.vehicle_width/2 + margin)
        
        if front_mask.any():
            front_distances = np.linalg.norm(points_R_visible[front_mask], axis=1)
            front_gap = float(np.min(front_distances))
        else:
            front_gap = None
        
        # 5. left_clear: 좌측 차선 영역 장애물 체크
        # 짧은 도로용: 전방 0.3~1.5m, 좌측 0.15~0.6m 범위
        left_mask = (
            (points_R_visible[:, 0] > 0.3) & (points_R_visible[:, 0] < 1.5) &
            (points_R_visible[:, 1] > 0.15) & (points_R_visible[:, 1] < 0.6)
        )
        
        # 가려진 영역이 있으면 보수적으로 left_clear=False
        # (현재는 간단히 포인트 기반만 체크, 추후 occlusion 고려)
        left_clear = not left_mask.any()
        
        return front_gap, left_clear


class LidarProcessor:
    """기존 LiDAR 포인트클라우드 처리 (하위 호환용)"""
    
    def __init__(self, vehicle_width: float = 0.15, lane_width: float = 0.30):
        self.vehicle_width = vehicle_width
        self.lane_width = lane_width
    
    def process(self, points: List[Tuple[float, float, float]]) -> Tuple[Optional[float], bool]:
        """
        포인트클라우드에서 front_gap, left_clear 추출
        
        좌표계: 차량 중심 기준
        - x: 전방(+), 후방(-)
        - y: 좌측(+), 우측(-)
        
        Returns:
            (front_gap, left_clear)
        """
        if not points:
            return None, True
        
        pc = np.array([(p[0], p[1]) for p in points])
        
        # 1. front_gap: 전방 ±10cm 범위 최소 거리
        margin = 0.1
        front_mask = (pc[:, 0] > 0) & (np.abs(pc[:, 1]) < self.vehicle_width/2 + margin)
        
        if front_mask.any():
            front_distances = np.linalg.norm(pc[front_mask], axis=1)
            front_gap = float(np.min(front_distances))
        else:
            front_gap = None
        
        # 2. left_clear: 좌측 차선 영역 장애물 체크
        # 짧은 도로용: 전방 0.3~1.5m, 좌측 0.15~0.6m 범위
        left_mask = (
            (pc[:, 0] > 0.3) & (pc[:, 0] < 1.5) &
            (pc[:, 1] > 0.15) & (pc[:, 1] < 0.6)
        )
        
        left_clear = not left_mask.any()
        
        return front_gap, left_clear

# =============================
# Param Server
# =============================
class ParamServer:
    def __init__(self, path: Optional[str]):
        self.path = path
        self.mtime = 0.0
        self.data: Dict[str, Dict] = {}
        
    def load(self) -> bool:
        changed = False
        if self.path and yaml is not None and os.path.isfile(self.path):
            m = os.path.getmtime(self.path)
            if m != self.mtime:
                with open(self.path, 'r', encoding='utf-8') as fp:
                    self.data = yaml.safe_load(fp) or {}
                self.mtime = m
                changed = True
                print(f"[YAML] reloaded {self.path}")
        return changed
                
    def apply(self, vp: VehicleParams, rp: RoadParams, bp: BehaviorParams, cp: ControllerParams) -> bool:
        changed = False
        def upd(obj, name):
            nonlocal changed
            if name in self.data:
                for k, v in self.data[name].items():
                    if hasattr(obj, k):
                        setattr(obj, k, v)
                        changed = True
        upd(vp, 'vehicle')
        upd(rp, 'road')
        upd(bp, 'behavior')
        upd(cp, 'controller')
        return changed

# =============================
# Signal Processing
# =============================
class EMA:
    def __init__(self, alpha: float, init: float = 0.0):
        self.alpha = alpha
        self.v = init
        
    def step(self, x: float) -> float:
        self.v = self.alpha * x + (1 - self.alpha) * self.v
        return self.v

class SignalValidator:
    def __init__(self, timeout: float):
        self.ema = EMA(alpha=0.3)
        self.timeout = timeout
        self.ts = 0.0
        self.v = 0.0
        
    def is_valid(self, now: float) -> bool:
        return (now - self.ts) < self.timeout

class RateLimit:
    def __init__(self, max_rate_per_step: float):
        self.max_rate = max_rate_per_step
        self.prev = 0.0
        
    def step(self, desired: float) -> float:
        d = desired - self.prev
        d = self.max_rate if d > self.max_rate else -self.max_rate if d < -self.max_rate else d
        self.prev = self.prev + d
        return self.prev

# =============================
# Sensors (기존 코드 유지)
# =============================
class PoseEstimator:
    def __init__(self, L: float):
        self.L = L
        self.x = 0.0
        self.y = 0.0
        self.psi = 0.0
        
    def update(self, v: float, delta_rad: float, dt: float):
        self.x += v * math.cos(self.psi) * dt
        self.y += v * math.sin(self.psi) * dt
        self.psi += (v / self.L) * math.tan(delta_rad) * dt

class LineTraceSensor:
    def __init__(self, lane_width: float):
        self.W = lane_width
        self.sig_ey = SignalValidator(timeout=0.2)
        
    def update(self, ey: Optional[float]):
        if ey is not None:
            self.sig_ey.ema.step(ey)
            self.sig_ey.ts = time.time()
            self.sig_ey.v = ey
            
    def get_ey(self) -> Optional[float]:
        now = time.time()
        return self.sig_ey.v if self.sig_ey.is_valid(now) else None

class SpeedSensor:
    def __init__(self):
        self.sig = SignalValidator(timeout=0.2)
        self._v = 1.2

    def update(self, v_meas: float):
        now = time.time()
        self.sig.ema.step(v_meas)
        self.sig.ts = now
        self.sig.v = v_meas
        self._v = v_meas
        
    def read(self) -> float:
        now = time.time()
        return self.sig.v if self.sig.is_valid(now) else self._v

# =============================
# Behavior Gates
# =============================
# =============================
# Controllers
# =============================
class LateralController:
    def __init__(self, cp: ControllerParams, vp: VehicleParams):
        self.cp = cp
        self.vp = vp
        
    def compute(self, ey: float, heading: float, mode: str) -> float:
        """
        PD Controller: lateral error + heading error
        
        Args:
            ey: Lateral error (m)
            heading: Current heading angle (radians)
            mode: 'keep', 'evade', or 'return'
        """
        # Position gain
        k = self.cp.k_ey_keep if mode == 'keep' else self.cp.k_ey_evade if mode == 'evade' else self.cp.k_ey_return
        
        # Heading gain (for KEEP states only) - increased to 1.0 for faster heading convergence
        k_heading = 1.0 if mode == 'keep' else 0.0
        
        # PD control: position error + heading error
        heading_deg = heading * _RAD2DEG
        delta_deg = -k * ey * _RAD2DEG - k_heading * heading_deg
        
        dmax = self.vp.DELTA_MAX_DEG
        return dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg

# =============================
# Student Policy (Neural Network)
# =============================
if torch is not None and nn is not None:
    class StudentPolicy(nn.Module):
        """Student Policy Network - Replaces MPC for low-level control"""
        def __init__(self, input_dim=9, hidden_dims=[256, 256, 128], 
                     output_dim=2, use_batchnorm=True, dropout=0.15):
            super().__init__()
            
            layers = []
            prev_dim = input_dim
            
            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(prev_dim, hidden_dim))
                if use_batchnorm:
                    layers.append(nn.BatchNorm1d(hidden_dim))
                layers.append(nn.ReLU())
                if dropout > 0:
                    layers.append(nn.Dropout(dropout))
                prev_dim = hidden_dim
            
            layers.append(nn.Linear(prev_dim, output_dim))
            self.network = nn.Sequential(*layers)
        
        def forward(self, x):
            return self.network(x)

    class StudentPolicyWrapper:
        """Wrapper for Student Policy with normalization and deployment utilities"""
        def __init__(self, model_path: str, stats_path: str, device='cpu'):
            if torch is None or nn is None:
                raise RuntimeError("PyTorch is required for Student Policy")
            
            self.device = torch.device(device)
            
            # Load normalization stats (support multiple formats)
            with open(stats_path, 'r') as f:
                stats = json.load(f)
            
            # Try different possible formats
            if 'X_mean' in stats and ('y_mean' in stats or 'Y_mean' in stats):
                # New format (from updated train_policy.py)
                self.X_mean = np.array(stats['X_mean'], dtype=np.float32)
                self.X_std = np.array(stats['X_std'], dtype=np.float32)
                # Support both lowercase and uppercase Y
                self.y_mean = np.array(stats.get('y_mean', stats.get('Y_mean')), dtype=np.float32)
                self.y_std = np.array(stats.get('y_std', stats.get('Y_std')), dtype=np.float32)
            elif 'mean' in stats and 'std' in stats:
                # Old format (might need splitting)
                mean = np.array(stats['mean'], dtype=np.float32)
                std = np.array(stats['std'], dtype=np.float32)
                # Assume last 2 are outputs (delta, v)
                self.X_mean = mean[:-2]
                self.X_std = std[:-2]
                self.y_mean = mean[-2:]
                self.y_std = std[-2:]
            else:
                raise ValueError(f"Unknown stats format. Keys: {list(stats.keys())}")
            
            # Validate shapes
            if len(self.X_mean) != 9:
                raise ValueError(f"X_mean should have 9 elements, got {len(self.X_mean)}")
            if len(self.y_mean) != 2:
                raise ValueError(f"y_mean should have 2 elements, got {len(self.y_mean)}")
            
            # Create model
            self.model = StudentPolicy(
                input_dim=9,
                hidden_dims=[256, 256, 128],
                output_dim=2,
                use_batchnorm=True,
                dropout=0.15
            ).to(self.device)
            
            # Load weights (weights_only=False for numpy compatibility in PyTorch 2.6+)
            checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()
            
            print(f"{Colors.GREEN}[STUDENT] Model loaded: {model_path}{Colors.RESET}")
            print(f"{Colors.GREEN}[STUDENT] Stats loaded: {stats_path}{Colors.RESET}")
            print(f"{Colors.GREEN}[STUDENT] Device: {self.device}{Colors.RESET}")
            print(f"{Colors.GREEN}[STUDENT] Input dim: {len(self.X_mean)}, Output dim: {len(self.y_mean)}{Colors.RESET}")
        
        def predict(self, features: np.ndarray) -> Tuple[float, float]:
            """Predict steering and velocity from features
            
            Args:
                features: [v, ey, gap, left_clear, state_one_hot(5)] (9-dim)
            
            Returns:
                (delta_deg, v_cmd)
            """
            # Normalize input
            features_norm = (features - self.X_mean) / (self.X_std + 1e-9)
            
            # Convert to tensor
            x = torch.from_numpy(features_norm).float().unsqueeze(0).to(self.device)
            
            # Inference
            with torch.no_grad():
                y_norm = self.model(x).cpu().numpy()[0]
            
            # Denormalize output
            y = y_norm * self.y_std + self.y_mean
            
            delta_deg = float(y[0])
            v_cmd = float(y[1])
            
            return delta_deg, v_cmd
else:
    # Dummy classes when PyTorch is not available
    StudentPolicy = None
    StudentPolicyWrapper = None

# =============================
# MPC
# =============================

# =============================
# OSQPMPC - FIXED VERSION
# =============================
class OSQPMPC:
    """
    Lightweight OSQP-based MPC that keeps only the lateral error (y) and heading (psi)
    states. This avoids over-constraining the problem and has proven numerically stable
    for aggressive evasive manoeuvres.
    """
    
    def __init__(self, vp: VehicleParams, rp: RoadParams, N: int, dt: float,
                 qy: float, qpsi: float, rdelta: float, rddelta: float):
        if osqp is None or sp is None:
            raise RuntimeError("osqp/scipy required")
        self.vp = vp
        self.rp = rp
        self.N = N
        self.dt = dt
        self.qy = qy
        self.qpsi = qpsi
        self.rdelta = rdelta
        self.rddelta = rddelta
        self.nx = 2  # [y, psi]
        self.n_ctrl = N - 1  # first control is applied immediately
        self.n_vars = self.nx * N + self.n_ctrl
        self.y_limit = max(self.rp.MAX_Y_DEVIATION, 10.0)
        self.psi_limit = math.radians(80.0)
        self._fail_reports = 0
        
        # Quadratic cost (constant part)
        P_diag: List[float] = []
        for _ in range(N):
            P_diag.append(qy)
            P_diag.append(qpsi)
        for i in range(self.n_ctrl):
            P_diag.append(rdelta if i == 0 else rddelta)
        self.P = sp.diags(P_diag, format='csc')
        
        # Variable bounds
        self.lb = np.full(self.n_vars, -np.inf)
        self.ub = np.full(self.n_vars, np.inf)
        for i in range(N):
            self.lb[self._idx_y(i)] = -self.y_limit
            self.ub[self._idx_y(i)] = self.y_limit
        dmax = vp.DELTA_MAX_DEG * _DEG2RAD
        for k in range(self.n_ctrl):
            idx = self._idx_u(k)
            self.lb[idx] = -dmax
            self.ub[idx] = dmax
        
        self.I_bounds = sp.eye(self.n_vars, format='csc')
    
    def _idx_y(self, i: int) -> int:
        return self.nx * i
    
    def _idx_psi(self, i: int) -> int:
        return self.nx * i + 1
    
    def _idx_u(self, i: int) -> int:
        return self.nx * self.N + i
    
    def solve(self, y0: float, psi0: float, v0: float, target_y: float) -> Tuple[float, bool]:
        v = max(0.05, min(self.vp.V_MAX, abs(v0)))
        gain_y = v * self.dt
        gain_psi = (v / max(self.vp.L, 1e-3)) * self.dt
        
        rows: List[int] = []
        cols: List[int] = []
        data: List[float] = []
        l_eq: List[float] = []
        u_eq: List[float] = []
        row_idx = 0
        
        # Initial state constraints
        rows.append(row_idx); cols.append(self._idx_y(0)); data.append(1.0)
        l_eq.append(y0); u_eq.append(y0); row_idx += 1
        psi_init = max(-self.psi_limit, min(self.psi_limit, psi0))
        rows.append(row_idx); cols.append(self._idx_psi(0)); data.append(1.0)
        l_eq.append(psi_init); u_eq.append(psi_init); row_idx += 1
        
        # Dynamics
        for k in range(self.N - 1):
            # y_{k+1} = y_k + v*psi_k*dt
            rows.extend([row_idx, row_idx, row_idx])
            cols.extend([self._idx_y(k + 1), self._idx_y(k), self._idx_psi(k)])
            data.extend([1.0, -1.0, -gain_y])
            l_eq.append(0.0); u_eq.append(0.0); row_idx += 1
            
            # psi_{k+1} = psi_k + (v/L)*delta_k*dt
            rows.extend([row_idx, row_idx, row_idx])
            cols.extend([self._idx_psi(k + 1), self._idx_psi(k), self._idx_u(k)])
            data.extend([1.0, -1.0, -gain_psi])
            l_eq.append(0.0); u_eq.append(0.0); row_idx += 1
        
        A_eq = sp.csc_matrix((data, (rows, cols)), shape=(row_idx, self.n_vars))
        A = sp.vstack([A_eq, self.I_bounds], format='csc')
        l = np.concatenate([np.array(l_eq), self.lb])
        u = np.concatenate([np.array(u_eq), self.ub])
        
        q = np.zeros(self.n_vars)
        for i in range(self.N):
            q[self._idx_y(i)] = -2.0 * self.qy * target_y
        
        solver = osqp.OSQP()
        solver.setup(P=self.P, q=q, A=A, l=l, u=u,
                     verbose=False, polish=True,
                     eps_abs=1e-5, eps_rel=1e-5, max_iter=8000)
        res = solver.solve()
        if res.info.status != 'solved':
            if self._fail_reports < 5:
                print(f"{Colors.YELLOW}[MPC] solver status={res.info.status}, obj={res.info.obj_val}, "
                      f"y0={y0:.3f}, psi0={psi0:.3f}, tgt={target_y:.3f}, v={v:.2f}{Colors.RESET}")
                self._fail_reports += 1
            # Fallback: simple proportional steering to keep system alive
            delta_fallback = np.clip(-self.qy * (y0 - target_y) * _RAD2DEG,
                                     -self.vp.DELTA_MAX_DEG, self.vp.DELTA_MAX_DEG)
            return delta_fallback, False
        
        delta_rad = res.x[self._idx_u(0)]
        return float(delta_rad * _RAD2DEG), True


# =============================
# Safety
# =============================
class SafetyGuard:
    def __init__(self, vp: VehicleParams, bp: BehaviorParams, dt: float):
        self.vp = vp
        self.bp = bp
        self.dt = dt
        self.interventions = 0
        self.min_gap = float('inf')  # Track minimum front_gap instead of TTC
        # VehicleParams의 DELTA_RATE_MAX_DEGPS를 deg/step으로 변환
        max_rate_per_step = vp.DELTA_RATE_MAX_DEGPS * dt
        self.rate = RateLimit(max_rate_per_step=max_rate_per_step)
        
    def check(self, v_cmd: float, delta_deg: float, front_gap: Optional[float]) -> Tuple[float, float]:
        v0 = v_cmd
        d0 = delta_deg
        
        # 최소 front_gap 기록
        if front_gap is not None and front_gap < self.min_gap:
            self.min_gap = front_gap
        
        # 속도는 단순 박스 제약만
        if v_cmd < self.vp.V_MIN:
            v_cmd = self.vp.V_MIN
        elif v_cmd > self.vp.V_MAX:
            v_cmd = self.vp.V_MAX
        
        dmax = self.vp.DELTA_MAX_DEG
        delta_cmd_deg = dmax if delta_deg > dmax else -dmax if delta_deg < -dmax else delta_deg
        delta_cmd_deg = self.rate.step(delta_cmd_deg)
        
        if abs(v_cmd - v0) > 1e-3 or abs(d0 - delta_cmd_deg) > 1e-3:
            self.interventions += 1
        
        return v_cmd, delta_cmd_deg

class Watchdog:
    def __init__(self, dt: float):
        self.dt = dt
        self.overruns = 0
        self.state = 'OK'
        self._thr = 0.7 * dt * 1000.0
        
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
# Communication with Sensor Integration
# =============================
class Comm:
    def __init__(self, mode: str, hb_period: float, cfg: AppConfig, can_channel: str = 'can0', can_bitrate: int = 500000):
        self.mode = mode
        self.hb_period = hb_period
        self.last_hb = 0.0
        self.ok = True
        self.can_bus = None
        self.cfg = cfg
        
        # 센서 데이터 저장
        self.ir_sensors = [0, 0, 0]  # [Left, Center, Right]
        
        # LiDAR WiFi
        self.lidar_wifi = None
        self.lidar_proc = None
        
        # Infra ROI (external feed)
        self._infra_roi: Optional[InfraROI] = None
        self._infra_lock = threading.Lock()
        
        # Speed feedback (optional)
        self._speed_meas: Optional[float] = None
        self._speed_ts: float = 0.0
        
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
        
        # LiDAR WiFi 초기화
        if cfg.lidar_port > 0:
            try:
                self.lidar_wifi = YDLidarWiFi(port=cfg.lidar_port)
                # 인프라 라이다 프로세서 (2차로 갓길 설치)
                self.lidar_proc = InfraLidarProcessor(
                    vehicle_width=0.15, 
                    vehicle_length=0.20,
                    lane_width=0.30,
                    lidar_margin=0.05
                )
                self.lidar_wifi.start()
            except Exception as e:
                print(f"{Colors.YELLOW}[WARN] LiDAR WiFi init failed: {e}{Colors.RESET}")
        
        print(f"[INFO] Comm={self.mode}, hb={hb_period}s, LiDAR_port={cfg.lidar_port}")
        
    def _hb(self):
        now = time.time()
        if now - self.last_hb >= self.hb_period:
            self.last_hb = now
            if self.mode == 'dummy':
                print("HB")
    
    def read_sensors(self):
        """CAN 버스에서 센서 메시지 읽기 (non-blocking)"""
        if self.mode != "can" or self.can_bus is None:
            return
        
        try:
            # Non-blocking read with short timeout
            msg = self.can_bus.recv(timeout=0.001)
            
            if msg is None:
                return
            
            if msg.arbitration_id == 0x200:  # IR 센서 메시지
                if len(msg.data) >= 3:
                    self.ir_sensors = [
                        1 if msg.data[0] > 0 else 0,
                        1 if msg.data[1] > 0 else 0,
                        1 if msg.data[2] > 0 else 0
                    ]
        
        except Exception as e:
            pass  # timeout은 정상
    
    def get_line_position(self) -> Optional[float]:
        """IR 센서 3개 → y 위치 변환"""
        self.read_sensors()  # 최신 데이터 읽기
        return ir_to_y_position(*self.ir_sensors, sensor_spacing=self.cfg.ir_sensor_spacing)
    
    def get_lidar_data(self, car_x_W: float = 0.0, car_y_W: float = 0.0, car_yaw_W: float = 0.0) -> InfraROI:
        """
        LiDAR에서 추정한 InfraROI 반환
        
        Args:
            car_x_W, car_y_W, car_yaw_W: 차량 pose (월드 좌표계)
        
        Returns:
            InfraROI
        """
        now = time.time()
        if self.lidar_wifi is None or self.lidar_proc is None:
            with self._infra_lock:
                if self._infra_roi is not None:
                    return InfraROI(front_gap=self._infra_roi.front_gap,
                                    roi_left_clear=self._infra_roi.roi_left_clear,
                                    timestamp=self._infra_roi.timestamp)
            return InfraROI(timestamp=now)
        
        points = self.lidar_wifi.get_points()
        
        try:
            if isinstance(self.lidar_proc, InfraLidarProcessor):
                front_gap, left_clear = self.lidar_proc.process(points, car_x_W, car_y_W, car_yaw_W)
            else:
                # 기존 LidarProcessor (하위 호환)
                front_gap, left_clear = self.lidar_proc.process(points)
        except Exception as e:
            print(f"{Colors.YELLOW}[WARN] LiDAR process failed: {e}{Colors.RESET}")
            return InfraROI(timestamp=now)
        
        roi = InfraROI(front_gap=front_gap, roi_left_clear=left_clear, timestamp=now)
        with self._infra_lock:
            self._infra_roi = roi
        return roi
    
    def update_speed(self, v_meas: float):
        """외부에서 측정한 속도(m/s)를 갱신"""
        self._speed_meas = v_meas
        self._speed_ts = time.time()
    
    def get_speed(self) -> Optional[float]:
        """최근 갱신된 속도(m/s) 반환"""
        if self._speed_meas is None:
            return None
        if time.time() - self._speed_ts > 0.5:
            return None
        return self._speed_meas
    
    def update_infra_roi(self, roi: InfraROI):
        """외부 센서에서 받은 InfraROI 값을 최신으로 갱신"""
        roi.timestamp = time.time()
        with self._infra_lock:
            self._infra_roi = roi
    
    def get_infra_roi(self) -> Optional[InfraROI]:
        """가장 최근 수신된 InfraROI 반환"""
        with self._infra_lock:
            if self._infra_roi is None:
                return None
            roi = self._infra_roi
        return InfraROI(front_gap=roi.front_gap,
                        roi_left_clear=roi.roi_left_clear,
                        timestamp=roi.timestamp)
                
    def send(self, v_cmd: float, steer_deg: float) -> bool:
        try:
            self._hb()
            
            if self.mode == "can" and self.can_bus is not None:
                # 데이터 변환: 속도(0.01 m/s 단위) + 조향각(0.1도 단위)
                v_int = int(v_cmd * 100)
                delta_int = int(steer_deg * 10)
                
                # 부호 처리 (16비트 signed)
                v_int = max(-32768, min(32767, v_int))
                delta_int = max(-32768, min(32767, delta_int))
                
                # 2의 보수 변환
                v_uint = v_int if v_int >= 0 else (1 << 16) + v_int
                delta_uint = delta_int if delta_int >= 0 else (1 << 16) + delta_int
                
                # 4바이트 데이터 생성
                data = [
                    (v_uint >> 8) & 0xFF,
                    v_uint & 0xFF,
                    (delta_uint >> 8) & 0xFF,
                    delta_uint & 0xFF
                ]
                
                # CAN 메시지 전송 (ID: 0x123)
                msg = can.Message(arbitration_id=0x123, data=data, is_extended_id=False)
                self.can_bus.send(msg)
                
                if self.cfg.debug_print:
                    print(f"TX CAN: v={v_cmd:.2f} m/s, steer={steer_deg:.1f} deg")
                    
            elif self.mode == "dummy":
                if self.cfg.debug_print:
                    print(f"TX ACK: v={v_cmd:.2f} m/s, steer={steer_deg:.1f} deg")
                
            self.ok = True
        except Exception as e:
            print(f"{Colors.RED}[CAN] send error: {e}{Colors.RESET}")
            self.ok = False
        return self.ok
    
    def close(self):
        """리소스 정리"""
        if self.can_bus is not None:
            try:
                self.can_bus.shutdown()
                print(f"{Colors.GREEN}[CAN] Bus closed{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.YELLOW}[CAN] Close error: {e}{Colors.RESET}")
        
        if self.lidar_wifi is not None:
            self.lidar_wifi.stop()

# =============================
# Dataset
# =============================
class TauLogger:
    def __init__(self):
        self.counts: Dict[int, int] = {}
        
    def add(self, tau_steps: int):
        self.counts[tau_steps] = self.counts.get(tau_steps, 0) + 1
        
    def write(self, out_dir: str, dt: float):
        if not self.counts:
            return
        total = sum(self.counts.values())
        items = sorted(self.counts.items())
        cdf = []
        s = 0
        for k, v in items:
            s += v
            cdf.append({'tau_steps': k, 'tau_sec': k * dt, 'cdf': s / total})
        with open(os.path.join(out_dir, 'tau_cdf.json'), 'w', encoding='utf-8') as fp:
            json.dump({'total': total, 'cdf': cdf}, fp, ensure_ascii=False, indent=2)
        print(f"[DATA] wrote tau_cdf.json (N={total})")

class ShardWriter:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.X: List[np.ndarray] = []
        self.Y: List[np.ndarray] = []
        self.M: List[dict] = []
        self.count = 0
        
    def push(self, feats: np.ndarray, label: np.ndarray, meta: dict):
        self.X.append(feats.astype(np.float32))
        self.Y.append(label.astype(np.float32))
        self.M.append(meta)
        
    def flush(self) -> Optional[str]:
        if not self.X:
            return None
        idx = self.count
        X = np.stack(self.X)
        Y = np.stack(self.Y)
        path = os.path.join(self.out_dir, f"shard_{idx:05d}.npz")
        np.savez_compressed(path, features=X, labels=Y, meta=np.array(self.M, dtype=object))
        self.X.clear()
        self.Y.clear()
        self.M.clear()
        self.count += 1
        print(f"[DATA] wrote {path}")
        return path

def merge_shards(dataset_dir: str, merged_out: str):
    files = [os.path.join(dataset_dir, f) for f in os.listdir(dataset_dir) if f.endswith('.npz')]
    if not files:
        print("[DATA] no shards found.")
        return
    Xs = []
    Ys = []
    for f in files:
        z = np.load(f, allow_pickle=True)
        Xs.append(z['features'])
        Ys.append(z['labels'])
    X = np.concatenate(Xs, axis=0)
    Y = np.concatenate(Ys, axis=0)
    np.savez_compressed(merged_out, features=X, labels=Y)
    stats = {
        'N': int(X.shape[0]),
        'feat_mean': X.mean(axis=0).tolist(),
        'feat_std': (X.std(axis=0) + 1e-9).tolist(),
        'label_mean': Y.mean(axis=0).tolist(),
        'label_std': (Y.std(axis=0) + 1e-9).tolist(),
    }
    with open(os.path.join(dataset_dir, 'dataset_stats.json'), 'w', encoding='utf-8') as fp:
        json.dump(stats, fp, ensure_ascii=False, indent=2)
    print(f"[DATA] merged -> {merged_out} (N={stats['N']})")

# =============================
# TEST HARNESS (원본 유지)
# =============================
class SensorSimulator:
    def __init__(self):
        self.timeline: List[Tuple[int, dict]] = []
        
    def add_timeline(self, timeline: List[Tuple[int, dict]]):
        self.timeline = sorted(timeline, key=lambda x: x[0])
        
    def get_values(self, step: int) -> dict:
        if not self.timeline:
            return {
                'roi': InfraROI(front_gap=None, roi_left_clear=True),
                'v': 1.2,
                'line_ey': 0.0
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
        self._pose_seeded = False
        
    def run_scenario(self, name: str, timeline: List[Tuple[int, dict]], expected_states: List[Tuple[int, str]]):
        print(f"\n{'=' * 60}")
        print(f"{Colors.CYAN}[TEST] Scenario: {name}{Colors.RESET}")
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
            except Exception as e:
                print(f"{Colors.RED}[FAIL] Step {step}: ERROR - {e}{Colors.RESET}")
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
            
            # SAFE_STOP 등으로 루프가 종료된 경우
            if self.app._stop_flag:
                # 마지막 상태 확인
                if step in expected_dict or self.app.state == State.SAFE_STOP:
                    actual = self.app.state.name
                    expected = expected_dict.get(step, 'SAFE_STOP')
                    passed = (actual == expected)
                    status = f"{Colors.GREEN}[PASS]{Colors.RESET}" if passed else f"{Colors.RED}[FAIL]{Colors.RESET}"
                    roi = sensor_data.get('roi', InfraROI())
                    fg = roi.front_gap
                    fg_str = f"{fg:.1f}" if fg else "N/A"
                    lc = "Clear" if sensor_data.get('left_clear', True) else "Block"
                    
                    if hasattr(self.app, 'last_log') and self.app.last_log:
                        v_cmd = self.app.last_log.get('v_cmd', 0.0)
                        delta = self.app.last_log.get('delta_deg', 0.0)
                        print(f"{status} Step {step:3d}: Exp {expected:15s} | Got {actual:15s} | "
                              f"y={self.app.pose.y:5.2f} | fg={fg_str:>5s} | L={lc:5s} | "
                              f"v={v_cmd:.2f} delta={delta:+.1f}deg | STOP_REASON={self.app._stop_reason}")
                    else:
                        print(f"{status} Step {step:3d}: Exp {expected:15s} | Got {actual:15s} | "
                              f"y={self.app.pose.y:5.2f} | fg={fg_str:>5s} | L={lc:5s} | STOP_REASON={self.app._stop_reason}")
                    
                    self.results.append({
                        'scenario': name,
                        'step': step,
                        'expected': expected,
                        'actual': actual,
                        'passed': passed
                    })
                break
            
            if step in expected_dict:
                actual = self.app.state.name
                expected = expected_dict[step]
                passed = (actual == expected)
                status = f"{Colors.GREEN}[PASS]{Colors.RESET}" if passed else f"{Colors.RED}[FAIL]{Colors.RESET}"
                roi = sensor_data.get('roi', InfraROI())
                fg = roi.front_gap
                fg_str = f"{fg:.1f}" if fg else "N/A"
                lc = "Clear" if sensor_data.get('left_clear', True) else "Block"
                
                # 제어 명령 출력 (마지막 step_once에서 계산된 값)
                if hasattr(self.app, 'last_log') and self.app.last_log:
                    v_cmd = self.app.last_log.get('v_cmd', 0.0)
                    delta = self.app.last_log.get('delta_deg', 0.0)
                    print(f"{status} Step {step:3d}: Exp {expected:15s} | Got {actual:15s} | "
                          f"y={self.app.pose.y:5.2f} | fg={fg_str:>5s} | L={lc:5s} | "
                          f"v={v_cmd:.2f} delta={delta:+.1f}deg")
                else:
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
        self.app.target_lane = 2
        self.app.pose.x = 0.0
        self.app.pose.y = 0.0
        self.app.pose.psi = 0.0
        self._pose_seeded = False
        now = time.time()
        self.app.last_state_change = now
        self.app.delta_prev = 0.0
        self.app.v_cmd_prev = 0.0
        self.app.left_clear_override = None
        
    def inject_sensors(self, data: dict):
        now = self.app._current_time()  # _test_time 사용
        roi = data.get('roi', InfraROI())
        self.app.infra = roi
        
        if 'left_clear' in data:
            self.app.left_clear_override = data['left_clear']
            self.app.infra.roi_left_clear = data['left_clear']
        
        if 'v' in data:
            self.app.speed.update(data['v'])
        
        if 'y' in data and not self._pose_seeded:
            self.app.pose.y = data['y']
            self._pose_seeded = True
        
        if 'line_ey' in data:
            self.app.lines.update(data['line_ey'])
            if data['line_ey'] is not None:
                self.app.lines.sig_ey.v = data['line_ey']
                self.app.lines.sig_ey.ts = now
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print(f"{Colors.BOLD}[TEST] SUMMARY{Colors.RESET}")
        print("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        
        print(f"Total: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
        if failed > 0:
            print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
        
        if failed > 0:
            print(f"\n{Colors.RED}[FAIL] Failed Tests:{Colors.RESET}")
            for r in self.results:
                if not r['passed']:
                    print(f"  - {r['scenario']} @ step {r['step']}: "
                          f"Expected {r['expected']}, got {r['actual']}")

def create_test_scenarios():
    scenarios = []
    
    # 시나리오 1: 전체 차선변경 (라인센서 우선)
    # 보수적 파라미터 기준: G_TRIG=1.2m, G_SAFE_MIN=0.20m, T_KEEP_L1_MIN=0.6s
    # line_ey 설명:
    # - KEEP_L2: L2 차선 기준 편차 (0.0 = L2 중심)
    # - EVADE_L: 차선 변경 중이므로 라인 감지 불안정 → None 또는 L2 기준으로 점점 증가
    # - KEEP_L1: L1 차선 기준 편차 (0.0 = L1 중심, 0.25m)
    # - RETURN_TO_L2: L1 기준으로 점점 증가하다가 L2 라인 감지 시 L2 기준으로 전환
    timeline1 = [
        # KEEP_L2: L2 중심 유지
        (0, {'roi': InfraROI(front_gap=5.0, roi_left_clear=True),
             'v': 1.2, 'y': 0.0, 'line_ey': 0.0, 'left_clear': True}),
        
        # EVADE_L 시작: front_gap < G_TRIG(1.2m) → 회피 시작
        (30, {'roi': InfraROI(front_gap=1.0, roi_left_clear=True),
              'v': 1.2, 'line_ey': 0.0, 'left_clear': True}),
        
        # EVADE_L 중반: 차선 변경 시작, 라인 감지 불안정하므로 None
        (50, {'roi': InfraROI(front_gap=0.8, roi_left_clear=True),
              'v': 1.2, 'line_ey': None, 'left_clear': True}),
        
        # EVADE_L 계속: L1 라인을 감지하기 시작 (L1 기준으로 작은 값)
        # pose.y가 약 0.125m (차선 폭의 절반)를 넘어서야 L1 라인 감지 가능
        (80, {'roi': InfraROI(front_gap=0.9, roi_left_clear=True),
              'v': 1.2, 'line_ey': None, 'left_clear': True}),
        
        # KEEP_L1 도착 직전: L1 라인 감지 시작 (L1 기준 작은 편차)
        (110, {'roi': InfraROI(front_gap=1.0, roi_left_clear=True),
               'v': 1.2, 'line_ey': 0.04, 'left_clear': True}),
        
        # KEEP_L1: L1 중심 유지
        (140, {'roi': InfraROI(front_gap=1.5, roi_left_clear=True),
               'v': 1.2, 'line_ey': 0.0, 'left_clear': True}),
        
        (180, {'roi': InfraROI(front_gap=2.0, roi_left_clear=True),
               'v': 1.0, 'line_ey': 0.0, 'left_clear': True}),
        
        # RETURN_TO_L2 시작: T_KEEP_L1_MIN(0.6s) 경과 → 자동 복귀
        # L1 기준으로 오른쪽 편차 증가 (L2로 이동 중)
        (210, {'roi': InfraROI(front_gap=2.5, roi_left_clear=True),
               'v': 1.0, 'line_ey': None, 'left_clear': True}),
        
        # RETURN_TO_L2 중반: L2 라인 감지 시작 (L2 기준 작은 편차)
        (240, {'roi': InfraROI(front_gap=3.0, roi_left_clear=True),
               'v': 1.0, 'line_ey': 0.02, 'left_clear': True}),
        
        # KEEP_L2 복귀: L2 중심 유지
        (270, {'roi': InfraROI(front_gap=4.0, roi_left_clear=True),
               'v': 1.0, 'line_ey': 0.0, 'left_clear': True}),
        
        (300, {'roi': InfraROI(front_gap=5.0, roi_left_clear=True),
               'v': 1.0, 'line_ey': 0.0, 'left_clear': True}),
    ]
    
    expected1 = [
        (0, 'KEEP_L2'),
        (30, 'EVADE_L'),      # gap=1.0m < G_TRIG(1.2m) → 회피 시작
        (280, 'KEEP_L2')
    ]
    scenarios.append(('full_evade_line_priority', timeline1, expected1))
    
    # 시나리오 2: SAFE_STOP 비상정지
    # 보수적 파라미터: G_SAFE_MIN=0.20m, G_TRIG=1.2m
    # 조건: front_gap < G_SAFE_MIN(0.20m) AND left_clear == False
    # Gap-based decision: 거리만으로 판단
    timeline2 = [
        # KEEP_L2: 정상 주행
        (0, {'roi': InfraROI(front_gap=3.0, roi_left_clear=True),
             'v': 1.2, 'y': 0.0, 'line_ey': 0.0, 'left_clear': True}),
        
        # 전방 장애물 접근, 좌측은 아직 비어있음
        # gap=1.0m < G_TRIG(1.2m) → EVADE_L 시작
        (20, {'roi': InfraROI(front_gap=1.0, roi_left_clear=True),
              'v': 1.2, 'line_ey': 0.0, 'left_clear': True}),
        
        # 전방 장애물 더 가까워짐, 좌측도 막힘 시작
        (40, {'roi': InfraROI(front_gap=0.25, roi_left_clear=False),
              'v': 1.2, 'line_ey': 0.0, 'left_clear': False}),
        
        # 비상정지 발동: front_gap < G_SAFE_MIN(0.20m) AND left_clear=False
        # gap=0.15m < 0.20m → SAFE_STOP
        (60, {'roi': InfraROI(front_gap=0.15, roi_left_clear=False),
              'v': 1.2, 'line_ey': 0.0, 'left_clear': False}),
    ]
    
    expected2 = [
        (0, 'KEEP_L2'),
        (60, 'SAFE_STOP')  # gap < G_SAFE_MIN(0.20m) + 좌측 막힘 → SAFE_STOP
    ]
    scenarios.append(('safe_stop_emergency', timeline2, expected2))
    
    return scenarios

# =============================
# Main App
# =============================
class App:
    def __init__(self, cfg: AppConfig, vp: VehicleParams, rp: RoadParams, bp: BehaviorParams, cp: ControllerParams):
        self.cfg = cfg
        self.vp = vp
        self.rp = rp
        self.bp = bp
        self.cp = cp
        self.dt = 1.0 / cfg.hz
        
        self.pose = PoseEstimator(vp.L)
        self.lines = LineTraceSensor(lane_width=rp.W)
        self.speed = SpeedSensor()
        self.lat = LateralController(cp, vp)
        
        # Main MPC for EVADE and normal operation
        # Improved parameters: higher qy for better tracking, higher rdelta/rddelta for smoother steering
        self.mpc = OSQPMPC(vp, rp, N=15, dt=self.dt, 
                          qy=100.0,    # Increased from 50.0 for better position tracking
                          qpsi=25.0,   # Increased from 20.0 for better heading control
                          rdelta=2.0,  # Increased from 0.5 to reduce steering oscillations
                          rddelta=5.0) # Increased from 2.0 to prevent abrupt steering changes
        
        # Separate MPC for smooth return to L2
        # Lower qy/qpsi for gentler corrections, higher rdelta/rddelta for smoother trajectory
        self.mpc_return = OSQPMPC(vp, rp, N=15, dt=self.dt,
                                 qy=40.0,     # Lower for gradual position correction
                                 qpsi=15.0,   # Lower for gradual heading correction
                                 rdelta=3.0,  # Higher to smooth out steering
                                 rddelta=8.0) # Higher to prevent overshoot
        
        self.guard = SafetyGuard(vp, bp, dt=self.dt)
        self.watchdog = Watchdog(self.dt)
        self.comm = Comm(cfg.comm, cfg.hb_period, cfg)
        
        # Hierarchical mode: Load Student Policy (replaces MPC for control)
        self.student = None
        self.use_student = False
        
        if torch is not None and nn is not None:
            try:
                model_path = cfg.student_model_path if hasattr(cfg, 'student_model_path') else 'models/policy_best.pth'
                stats_path = cfg.student_stats_path if hasattr(cfg, 'student_stats_path') else 'models/normalization_stats.json'
                
                if os.path.exists(model_path) and os.path.exists(stats_path):
                    self.student = StudentPolicyWrapper(model_path, stats_path)
                    self.use_student = True
                    print(f"{Colors.CYAN}[HIERARCHICAL] Student policy loaded - MPC replaced with NN{Colors.RESET}")
                    print(f"{Colors.CYAN}[HIERARCHICAL] High-level: Teacher FSM (state transitions){Colors.RESET}")
                    print(f"{Colors.CYAN}[HIERARCHICAL] Low-level: Student NN (steering/velocity control){Colors.RESET}")
                else:
                    print(f"{Colors.YELLOW}[WARN] Student model not found. Using Teacher MPC.{Colors.RESET}")
                    print(f"{Colors.YELLOW}[WARN] Expected: {model_path}, {stats_path}{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.YELLOW}[WARN] Failed to load student policy: {e}{Colors.RESET}")
                print(f"{Colors.YELLOW}[WARN] Falling back to Teacher MPC{Colors.RESET}")
                self.student = None
                self.use_student = False
        else:
            print(f"{Colors.YELLOW}[WARN] PyTorch not available. Using Teacher MPC.{Colors.RESET}")


        
        self.state = State.KEEP_L2
        self.target_lane = 2
        self.last_state_change = time.time()
        self.delta_prev = 0.0
        self.delta_filtered = 0.0
        self.v_cmd_prev = 0.0  # 이전 스텝의 v_cmd (TTC 계산용)
        self.debug_target_y = 0.0
        self.front_gap: Optional[float] = None
        self.infra = InfraROI()
        self.left_clear_override: Optional[bool] = None
        
        self._stop = False
        self._stop_flag = False
        self._stop_reason = ""
        self._test_time: Optional[float] = None
        
        self.param_srv = ParamServer(cfg.yaml_path)
        self.last_yaml_check = 0.0
        
        self.tau_steps = int(cfg.tau_ms / (self.dt * 1000.0)) if cfg.tau_ms > 0 else 0
        self.shard: Optional[ShardWriter] = None
        self.label_fifo: Deque[Tuple[np.ndarray, np.ndarray]] = deque()
        self.tau_logger = TauLogger()
        
        if cfg.export_dataset:
            self.shard = ShardWriter(cfg.dataset_dir)
        
        os.makedirs(cfg.log_dir, exist_ok=True)
        log_path = os.path.join(cfg.log_dir, f"run_{int(time.time())}.csv")
        self.fp = open(log_path, 'w', newline='', encoding='utf-8')
        self.logger = csv.writer(self.fp)
        self.logger.writerow([
            "t", "mode", "state", "x", "y", "psi_deg", "v", "front_gap",
            "left_clear", "v_cmd", "delta_deg", "loop_ms", "wd", "guard_intv", "min_gap", "stop_reason"
        ])
        self.last_log: Optional[dict] = None
        
        def sig_handler(sig, frame):
            print(f"\n{Colors.YELLOW}[SIG] Caught signal {sig}, stopping...{Colors.RESET}")
            self._stop = True
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
        
    def _current_time(self) -> float:
        return self._test_time if self._test_time is not None else time.time()
    
    def set_state(self, new_state: State):
        if new_state != self.state:
            print_state_change(self.state.name, new_state.name)
            self.state = new_state
            self.last_state_change = self._current_time()
    
    def _on_params_updated(self):
        self.lat = LateralController(self.cp, self.vp)
        self.guard = SafetyGuard(self.vp, self.bp, dt=self.dt)
        # Recreate both MPCs with improved parameters
        self.mpc = OSQPMPC(self.vp, self.rp, N=15, dt=self.dt,
                          qy=100.0, qpsi=25.0, rdelta=2.0, rddelta=5.0)
        self.mpc_return = OSQPMPC(self.vp, self.rp, N=15, dt=self.dt,
                                 qy=40.0, qpsi=15.0, rdelta=3.0, rddelta=8.0)
        print("[YAML] runtime params applied.")
    
    def hot_reload_params(self):
        now = self._current_time()
        if now - self.last_yaml_check > 1.0:
            self.last_yaml_check = now
            reloaded = self.param_srv.load()
            changed = self.param_srv.apply(self.vp, self.rp, self.bp, self.cp)
            if reloaded or changed:
                self._on_params_updated()
    
    def step_once(self):
        try:
            t0 = self._current_time()
            
            # === 센서 읽기 ===
            # 테스트 모드가 아닐 때만 실제 센서 읽기
            if self._test_time is None:
                # 실제 주행 모드
                y_line = self.comm.get_line_position()  # IR 센서
                # LiDAR: 차량 pose 전달 (월드 좌표계)
                lidar_roi = self.comm.get_lidar_data(
                    car_x_W=self.pose.x,
                    car_y_W=self.pose.y,
                    car_yaw_W=self.pose.psi
                )
                self.infra = lidar_roi
                
                # 센서 데이터 통합
                if y_line is not None:
                    # y_line 검증 범위: ±0.6m
                    # 이유: 차선 폭(0.3m) + 차 폭(0.15m) + 센서 노이즈 + 차선 변경 중 넓은 범위
                    # - 정상 범위: ±0.15m (차선 폭의 절반)
                    # - 차선 변경 중: 0 ~ 0.3m (L2 → L1)
                    # - 안전 마진: 2배 (실제 환경 노이즈 고려)
                    y_line = validate_sensor(y_line, -0.6, 0.6, "y_position")
                    if y_line is not None:
                        self.lines.update(y_line)
                
                self.front_gap = self.infra.front_gap
                
                # front_gap 검증: 0~10m 범위 내, 음수/inf/NaN 제거
                if self.front_gap is not None:
                    self.front_gap = validate_sensor(self.front_gap, 0.0, 10.0, "front_gap")
                
                # left_clear: Infra ROI (override for tests if needed)
                left_clear = self.left_clear_override if self.left_clear_override is not None else self.infra.roi_left_clear
            else:
                # 테스트 모드: inject_sensors()에서 이미 설정됨
                self.front_gap = self.infra.front_gap
                
                # 테스트 모드에서도 front_gap 검증
                if self.front_gap is not None:
                    self.front_gap = validate_sensor(self.front_gap, 0.0, 10.0, "front_gap")
                
                left_clear = self.left_clear_override if self.left_clear_override is not None else self.infra.roi_left_clear
            
            # "현재 속도 = 가장 최근에 보낸 속도" 가정
            # "현재 속도 = 가장 최근에 보낸 속도" 가정
            v_now = self.v_cmd_prev if self.v_cmd_prev > 0.0 else self.vp.V_MAX
            front_gap = self.front_gap
            ey_line = self.lines.get_ey()
            
            if self.cfg.debug_print and front_gap is not None:
                print(f"[DEBUG] Front Gap: {front_gap:.2f} m")
            
            # ============================
            # ⚠ Emergency stop condition (SAFE_STOP)
            # - front_gap exists and very close (< G_SAFE_MIN)
            # - Cannot evade left (left_clear == False)
            # ============================
            if (front_gap is not None
                and front_gap < self.bp.G_SAFE_MIN
                and not left_clear):
                
                print(f"{Colors.RED}[SAFE_STOP] EMERGENCY: fg={front_gap:.2f}m < {self.bp.G_SAFE_MIN:.2f}m, left_clear={left_clear}{Colors.RESET}")
                # Set state to SAFE_STOP
                self.set_state(State.SAFE_STOP)
                
                # NOTE: No _stop_flag set → recoverable SAFE_STOP
                # SAFE_STOP controls with v_cmd=0, auto-resumes when recovery condition met
            
            # FSM
            if self.state.value == State.KEEP_L2.value:
                if front_gap is not None and front_gap < self.bp.G_TRIG:
                    if left_clear:
                        # 좌측이 비어 있으면 회피 시작
                        self.set_state(State.EVADE_L)
                        self.target_lane = 1
                    else:
                        # 좌측 막혀 있으면 일단 KEEP_L2 유지
                        # (거리가 더 가까워지면 위 SAFE_STOP 로직에서 처리)
                        pass
            
            elif self.state.value == State.EVADE_L.value:
                # IR 센서가 있으면 IR 기반으로 우선 판정 (드리프트 없음)
                if ey_line is not None and self.pose.y > 0.5 * self.rp.W:
                    arrived_l1 = abs(ey_line) < (self.bp.NEAR_BAND_L1 * 0.5)
                else:
                    # IR 없으면 pose.y 기반 (dead-reckoning, 드리프트 가능)
                    pose_err_l1 = self.pose.y - self.rp.W
                    arrived_l1 = abs(pose_err_l1) < self.bp.NEAR_BAND_L1
                if arrived_l1:
                    self.set_state(State.KEEP_L1)
                # Note: Emergency stop for close obstacles handled by SAFE_STOP condition above
            
            elif self.state.value == State.KEEP_L1.value:
                elapsed = t0 - self.last_state_change
                if elapsed > self.bp.T_KEEP_L1_MIN:
                    # 시간만 지나면 바로 복귀 (front_gap 무관)
                    # 이유: 회피했으면 이미 장애물을 지나쳤으므로
                    self.set_state(State.RETURN_TO_L2)
                    self.target_lane = 2
            
            elif self.state.value == State.RETURN_TO_L2.value:
                # IR 센서와 pose.y 모두 확인 (둘 다 L2 근처여야 전환)
                if ey_line is not None:
                    # ey_line으로 L2 라인 근처인지 확인
                    line_near_l2 = abs(ey_line) < (self.bp.NEAR_BAND_L1 * 0.5)
                    # pose.y로 실제 차량이 L2 근처인지 확인
                    pose_near_l2 = abs(self.pose.y) < self.bp.NEAR_BAND_L1
                    arrived_l2 = line_near_l2 and pose_near_l2
                else:
                    # IR 없으면 pose.y 기반 (dead-reckoning, 드리프트 가능)
                    pose_err_l2 = self.pose.y
                    arrived_l2 = abs(pose_err_l2) < self.bp.NEAR_BAND_L1
                if arrived_l2:
                    self.set_state(State.KEEP_L2)
            
            # Control
            v_ref = self.vp.V_MAX
            target_display = 0.0
            
            # Extract features for Student Policy (if needed)
            # Features: [v, ey, gap, left_clear, state_one_hot(5)]
            def get_student_features():
                feats = np.array([
                    v_now,
                    ey_line if ey_line is not None else (self.pose.y - (self.rp.W if self.target_lane == 1 else 0.0)),
                    front_gap if front_gap is not None else 10.0,
                    float(left_clear)
                ], dtype=np.float32)
                state_one_hot = np.zeros(len(State), dtype=np.float32)
                state_idx = max(0, min(len(State) - 1, self.state.value - 1))
                state_one_hot[state_idx] = 1.0
                return np.concatenate([feats, state_one_hot])
            
            if self.state.value == State.KEEP_L2.value:
                if ey_line is not None:
                    # Line following (hybrid control)
                    alpha = 0.5
                    target_y = 0.0 + ey_line
                    self.pose.y = (1.0 - alpha) * self.pose.y + alpha * target_y
                    delta_deg = self.lat.compute(ey_line, self.pose.psi, 'keep')
                    target_display = 0.0
                    v_cmd = v_ref  # Line following uses max speed
                else:
                    # No line sensor - use Student (Hierarchical) or MPC (Teacher)
                    target_y = 0.0
                    if self.use_student and self.student is not None:
                        # Student NN (Hierarchical mode)
                        features = get_student_features()
                        delta_deg, v_cmd_student = self.student.predict(features)
                        # Use Student's velocity too
                        v_cmd = v_cmd_student
                    else:
                        # Teacher MPC (fallback)
                        delta_deg, ok = self.mpc.solve(self.pose.y, self.pose.psi, v_now, target_y)
                        if not ok:
                            if self._test_time is not None:
                                print(f"[WARN] MPC solve failed in KEEP_L2")
                            delta_deg = 0.0
                        v_cmd = v_ref  # MPC uses max speed
                    target_display = target_y
            
            elif self.state.value == State.EVADE_L.value:
                target_y = self.rp.W
                if self.cfg.debug_print:
                    print(f"[CONTROL_EVADE] y={self.pose.y:.3f}, target={target_y:.3f}, psi={self.pose.psi * _RAD2DEG:.1f}°")
                
                if self.use_student and self.student is not None:
                    # Student NN (Hierarchical mode)
                    features = get_student_features()
                    delta_deg, v_cmd = self.student.predict(features)
                else:
                    # Teacher MPC (fallback)
                    delta_deg, ok = self.mpc.solve(self.pose.y, self.pose.psi, v_now, target_y)
                    if not ok:
                        print(f"[WARN] MPC solve failed in EVADE_L: y={self.pose.y:.3f}, target={target_y:.3f}")
                        delta_deg = 0.0
                    elif abs(delta_deg) < 0.1:
                        print(f"[WARN] MPC delta too small: y={self.pose.y:.3f}, target={target_y:.3f}, delta={delta_deg:.3f}")
                    v_cmd = v_ref
                
                if self.cfg.debug_print:
                    print(f"[CONTROL_EVADE] delta={delta_deg:.1f}°, v={v_cmd:.2f}")
                target_display = target_y
            
            elif self.state.value == State.KEEP_L1.value:
                if ey_line is not None:
                    # Line following (hybrid control)
                    alpha = 0.5
                    target_y = self.rp.W + ey_line
                    self.pose.y = (1.0 - alpha) * self.pose.y + alpha * target_y
                    delta_deg = self.lat.compute(ey_line, self.pose.psi, 'keep')
                    v_cmd = v_ref  # Line following uses max speed
                else:
                    # No line sensor - use Student (Hierarchical) or MPC (Teacher)
                    target_y = self.rp.W
                    if self.use_student and self.student is not None:
                        # Student NN (Hierarchical mode)
                        features = get_student_features()
                        delta_deg, v_cmd_student = self.student.predict(features)
                        v_cmd = v_cmd_student
                    else:
                        # Teacher MPC (fallback)
                        delta_deg, ok = self.mpc.solve(self.pose.y, self.pose.psi, v_now, target_y)
                        if not ok:
                            if self._test_time is not None:
                                print(f"[WARN] MPC solve failed in KEEP_L1")
                            delta_deg = 0.0
                        v_cmd = v_ref  # MPC uses max speed
                target_display = self.rp.W
            
            elif self.state.value == State.RETURN_TO_L2.value:
                # ========================================
                # HYBRID STRATEGY: Always use Teacher MPC for RETURN_TO_L2
                # ========================================
                # Reason: Student NN shows poor performance with large lateral deviations (0.3~1.0m)
                # - Raw delta = -0.24deg is insufficient for y=0.3~1.0m errors
                # - MPC provides aggressive recovery: raw delta = -25deg for y=0.32m
                # - Safe and reliable return to L2 center line
                # 
                # Performance impact: RETURN_TO_L2 uses MPC (50-100ms), but only ~10% of total time
                # Other states (KEEP_L2, EVADE_L, KEEP_L1) still use fast Student NN (2-5ms)
                target_y = 0.0
                delta_deg, ok = self.mpc.solve(self.pose.y, self.pose.psi, v_now, target_y)
                if not ok:
                    if self._test_time is not None:
                        print(f"[WARN] MPC solve failed in RETURN_TO_L2")
                    delta_deg = 0.0
                v_cmd = v_ref
                target_display = target_y
            
            elif self.state.value == State.SAFE_STOP.value:
                # SAFE_STOP: Emergency stop due to imminent collision
                delta_deg = 0.0
                v_cmd = 0.0
                target_display = self.pose.y
                
                # Recovery condition: Front obstacle cleared OR left lane available for evasion
                # Use hysteresis to prevent oscillation (G_SAFE_MIN * 3.0 for recovery)
                recovery_gap = self.bp.G_SAFE_MIN * 3.0
                if front_gap is None or front_gap > recovery_gap:
                    # Obstacle cleared, resume from last lane
                    if self.target_lane == 1:
                        self.set_state(State.KEEP_L1)
                    else:
                        self.set_state(State.KEEP_L2)
                    print(f"{Colors.GREEN}[RECOVERY] Resuming from SAFE_STOP (fg={front_gap:.2f}m > {recovery_gap:.2f}m){Colors.RESET}")
                elif left_clear and front_gap is not None and front_gap < self.bp.G_TRIG:
                    # Left lane now clear, attempt evasion
                    self.set_state(State.EVADE_L)
                    self.target_lane = 1
                    print(f"{Colors.YELLOW}[RECOVERY] Emergency evasion from SAFE_STOP{Colors.RESET}")
            
            else:
                # Fallback for unknown states
                delta_deg = 0.0
                v_cmd = 0.0
                target_display = self.pose.y
            
            self.debug_target_y = target_display
            
            # Low-pass filter (before filtering, save raw value)
            delta_raw = delta_deg
            alpha = 0.5  # Increased from 0.3 for better responsiveness (SafetyGuard already has rate limiting)
            self.delta_filtered = alpha * delta_deg + (1 - alpha) * self.delta_filtered
            delta_deg = self.delta_filtered
            
            # 테스트 모드에서 매 step 출력
            if self._test_time is not None:
                print(f"[STEP] t={t0-self._test_time:.2f}s state={self.state.name:12s} "
                      f"y={self.pose.y:+.3f} target={self.debug_target_y:+.3f} "
                      f"raw_delta={delta_raw:+.2f}deg filt_delta={delta_deg:+.2f}deg v={v_cmd:.2f}")
            
            # feats 계산: 제어 계산 후이므로 v_cmd 사용
            feats = np.array([
                v_cmd,  # "현재 속도 = 가장 최근에 보낸 속도" 가정
                ey_line if ey_line is not None else (self.pose.y - (self.rp.W if self.target_lane == 1 else 0.0)),
                front_gap if front_gap is not None else 10.0,
                float(left_clear)
            ], dtype=np.float32)
            state_one_hot = np.zeros(len(State), dtype=np.float32)
            state_idx = max(0, min(len(State) - 1, self.state.value - 1))
            state_one_hot[state_idx] = 1.0
            feats = np.concatenate([feats, state_one_hot])
            
            # Student policy (B-option: teacher-only, student disabled)
            use_teacher = True
            delta_teacher_deg = delta_deg
            v_teacher = v_cmd
            
            # Safety guard
            v_cmd, delta_deg = self.guard.check(v_cmd, delta_deg, front_gap)
            
            # "현재 속도 = 가장 최근에 보낸 속도" 가정 적용
            v_now = v_cmd
            
            # Send command
            delta_rad = delta_deg * _DEG2RAD
            self.pose.update(v_now, delta_rad, self.dt)
            
            # 다음 스텝을 위해 저장
            self.v_cmd_prev = v_cmd
            self.delta_prev = delta_deg  # CRITICAL: Update delta_prev for next iteration
            
            if not self.comm.send(v_cmd, delta_deg):
                self._stop_flag = True
                self._stop_reason = "COMM_FAIL"
            
            # Dataset
            if self.shard is not None:
                teacher_u = np.array([delta_teacher_deg, v_teacher], dtype=np.float32)
                self.label_fifo.append((feats.copy(), teacher_u))
                if len(self.label_fifo) > self.tau_steps:
                    old_feats, future_u = self.label_fifo.popleft()
                    meta = {'state': self.state.name, 'left_clear': bool(left_clear),
                            'tau_steps': int(self.tau_steps), 'mode': self.cfg.run_mode.name,
                            't': t0, 'use_teacher': bool(use_teacher)}
                    alpha = 0.2
                    smoothed = (1 - alpha) * future_u + alpha * np.array([0.0, v_ref], dtype=np.float32)
                    self.shard.push(old_feats, smoothed, meta)
                    self.tau_logger.add(self.tau_steps)
            
            loop_ms = (self._current_time() - t0) * 1000.0
            wd_state = self.watchdog.step(loop_ms)

            print(f"[LOOP] {loop_ms:.2f} ms")

            
            if wd_state == 'DEGRADE':
                v_ref = 0.8 if v_ref > 0.8 else v_ref
            elif wd_state == 'STOP':

                # UPDATE: Watchdog Logic Error Fix 
                # self.set_state(State.SAFE_STOP)
                # self._stop_flag = False

                self._stop_reason = "WD_BREACH"
            
            self.last_log = {
                "t": t0, "mode": self.cfg.run_mode.name, "state": self.state.name,
                "x": self.pose.x, "y": self.pose.y, "psi_deg": self.pose.psi * _RAD2DEG,
                "v": v_now, "front_gap": front_gap,
                "left_clear": int(left_clear), "v_cmd": v_cmd, "delta_deg": delta_deg,
                "loop_ms": loop_ms, "wd": wd_state, "guard_intv": self.guard.interventions,
                "min_gap": self.guard.min_gap if self.guard.min_gap != float('inf') else float('inf'),
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
                        int(self.last_log.get('left_clear', 1)),
                        f"{self.last_log.get('v_cmd', 0.0):.2f}",
                        f"{self.last_log.get('delta_deg', 0.0):.1f}",
                        f"{self.last_log.get('loop_ms', 0.0):.1f}",
                        str(self.last_log.get('wd', 'OK')),
                        int(self.last_log.get('guard_intv', 0)),
                        "INF" if self.last_log.get('min_gap') == float('inf') else f"{self.last_log.get('min_gap'):.2f}",
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
            min_gap_val = self.guard.min_gap if self.guard.min_gap != float('inf') else float('inf')
            
            self.logger.writerow([
                f"{time.time():.3f}", self.cfg.run_mode.name, "STOP",
                f"{self.pose.x:.2f}", f"{self.pose.y:.2f}", f"{self.pose.psi * _RAD2DEG:.1f}",
                f"{v_now:.2f}", "NA", 1, "0.00", "0.0", "0.0", "STOP",
                self.guard.interventions,
                f"{min_gap_val if min_gap_val != float('inf') else 'INF'}",
                reason
            ])
            self.fp.flush()
            
            if self.shard is not None:
                self.shard.flush()
                self.tau_logger.write(self.cfg.dataset_dir, self.dt)
        
        finally:
            if hasattr(self, 'fp') and self.fp:
                self.fp.close()
            if hasattr(self, 'comm'):
                self.comm.close()
        
        print(f"{Colors.GREEN}[RUN] Stopped.{Colors.RESET}")

# =============================
# CLI
# =============================
def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RC Car Lane Change MPC - Sensor Integrated")
    p.add_argument("--hz", type=float, default=20.0)
    p.add_argument("--run_mode", type=str, default="teacher", choices=["teacher", "shadow", "student"])
    p.add_argument("--comm", type=str, default="dummy", choices=["dummy", "can"])
    p.add_argument("--hb_period", type=float, default=0.5)
    p.add_argument("--log_dir", type=str, default="./runs")
    p.add_argument("--export_dataset", type=int, default=0)
    p.add_argument("--dataset_dir", type=str, default="./dataset")
    p.add_argument("--merge_shards", type=int, default=0)
    p.add_argument("--merged_out", type=str, default="./dataset_all.npz")
    p.add_argument("--tau_ms", type=float, default=0.0)
    p.add_argument("--tau_jitter_ms", type=float, default=0.0)
    p.add_argument("--policy_onnx", type=str, default=None)
    p.add_argument("--policy_ts", type=str, default=None)
    p.add_argument("--yaml", type=str, default=None)
    p.add_argument("--test", action="store_true")
    p.add_argument("--debug", action="store_true", help="Enable debug output")
    
    # Sensor parameters
    p.add_argument("--lidar_port", type=int, default=8000, help="LiDAR WiFi UDP port (0=disable)")
    p.add_argument("--ir_spacing", type=float, default=0.04, help="IR sensor spacing (m)")
    
    # Behavior parameters (Conservative validated values - 100% success rate in sim)
    p.add_argument("--g_trig", type=float, default=1.2, help="Evade trigger distance (m)")
    p.add_argument("--g_safe_min", type=float, default=0.20, help="Emergency stop distance (m)")
    p.add_argument("--t_keep_l1_min", type=float, default=0.6, help="Minimum time in L1 (s)")
    # NOTE: g_return_safe removed - return based on time only
    # Vehicle parameters
    p.add_argument("--L", type=float, default=0.20)
    p.add_argument("--B", type=float, default=0.15)
    p.add_argument("--v_max", type=float, default=0.5)
    p.add_argument("--delta_max", type=float, default=25.0)
    p.add_argument("--delta_rate", type=float, default=200.0)
    p.add_argument("--a_max", type=float, default=2.0)
    p.add_argument("--a_min", type=float, default=-3.0)
    p.add_argument("--wheel_rate", type=float, default=3.0)
    
    # Road parameters
    p.add_argument("--lane_width", type=float, default=0.30)
    p.add_argument("--max_y_deviation", type=float, default=3.0)
    
    # Controller parameters
    p.add_argument("--k_ey_keep", type=float, default=1.5)
    p.add_argument("--k_ey_evade", type=float, default=2.0)
    p.add_argument("--k_ey_return", type=float, default=1.8)
    p.add_argument("--k_delta_rate", type=float, default=0.05)
    p.add_argument("--assume_straight_nominal", type=int, default=1)
    
    p.add_argument("--random_env", action="store_true",
                        help="랜덤 환경 시뮬레이션으로 teacher 데이터 생성")
    p.add_argument("--num_train_episodes", type=int, default=800)
    p.add_argument("--num_test_episodes", type=int, default=200)
    p.add_argument("--steps_per_episode", type=int, default=200)
    
    # Hierarchical mode: Student policy paths
    p.add_argument("--student_model", type=str, default="models/policy_best.pth",
                   help="Path to Student policy model (.pth)")
    p.add_argument("--student_stats", type=str, default="models/normalization_stats.json",
                   help="Path to Student normalization stats (.json)")

    return p.parse_args()

def main():
    args = build_args()
    
    if int(args.merge_shards) == 1:
        merge_shards(args.dataset_dir, args.merged_out)
        return
    
    cfg = AppConfig(
        hz=args.hz, run_mode=RunMode[args.run_mode.upper()],
        assume_straight_nominal=args.assume_straight_nominal,
        comm=args.comm, hb_period=args.hb_period,
        log_dir=args.log_dir, export_dataset=int(args.export_dataset),
        dataset_dir=args.dataset_dir, merge_shards=int(args.merge_shards),
        merged_out=args.merged_out, tau_ms=args.tau_ms, tau_jitter_ms=args.tau_jitter_ms,
        policy_onnx=args.policy_onnx, policy_ts=args.policy_ts, yaml_path=args.yaml,
        debug_print=1 if args.debug else 0,
        lidar_port=args.lidar_port, ir_sensor_spacing=args.ir_spacing,
        student_model_path=args.student_model, student_stats_path=args.student_stats
    )

    # B-option: STUDENT mode disabled, fallback to SHADOW
    if cfg.run_mode == RunMode.STUDENT:
        print("[WARN] STUDENT mode is disabled in this build. Falling back to SHADOW mode.")
        cfg.run_mode = RunMode.SHADOW

    
    vp = VehicleParams(L=args.L, B=args.B, V_MAX=args.v_max,
                       DELTA_MAX_DEG=args.delta_max, DELTA_RATE_MAX_DEGPS=args.delta_rate,
                       A_MAX=args.a_max, A_MIN=args.a_min, WHEEL_RATE_MAX=args.wheel_rate)
    
    rp = RoadParams(W=args.lane_width, MAX_Y_DEVIATION=args.max_y_deviation)
    
    bp = BehaviorParams(G_TRIG=args.g_trig, G_SAFE_MIN=args.g_safe_min,
                        T_KEEP_L1_MIN=args.t_keep_l1_min)
    
    cp = ControllerParams(k_ey_keep=args.k_ey_keep, k_ey_evade=args.k_ey_evade,
                         k_ey_return=args.k_ey_return, k_delta_rate=args.k_delta_rate)
    
    app = App(cfg, vp, rp, bp, cp)
    
    if args.test:
        print("\n" + "=" * 60)
        print(f"{Colors.CYAN}{Colors.BOLD}[TEST] RUNNING TEST MODE{Colors.RESET}")
        print("=" * 60 + "\n")
        harness = TestHarness(app)
        scenarios = create_test_scenarios()
        for scenario_name, timeline, expected_states in scenarios:
            harness.run_scenario(scenario_name, timeline, expected_states)
        harness.print_summary()
    else:
        app.run()

if __name__ == "__main__":
    main()