"""
센서 모델 (LiDAR: front_gap/left_clear/right_clear, IR: ey_line). 논문 제출 이후 작성.
REQ-SEN-01~04. repro/docs/WORK_RULES.md: 제어기는 이 모듈의 출력만 입력으로 받는다(시뮬레이터 좌표 직접 참조 금지).

**v1.1 버그 수정(2026-09-22, [정합])**: front_gap()이 차체 전단보다 완전히 뒤로 지나친
장애물(obs.x_far < fx)을 제외하지 않아 방향 구분 없이 0.0(장애물이 바로 앞이라는 뜻)을
반환하던 결함을 수정. PDF p.7 "전방 장애물까지의 거리(front_gap)" 정의상 후방 장애물은
애초에 대상이 아니므로 [정합] 버그 수정([발전] 아님). 근거·영향:
`THESIS_REVISION_LOG.md` 2026-09-22 REQ-SEN-01, `SETTINGS_DECISION.md` §7 개정 이력.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from . import config
from .vehicle import VehicleState, front_x, rear_x
from .world import Obstacle

Pattern = Tuple[int, int, int]  # (left, center, right)

_IR_TABLE = {
    (0, 1, 0): 0.0,
    (1, 1, 0): -0.02,
    (1, 0, 0): -0.04,
    (0, 1, 1): 0.02,
    (0, 0, 1): 0.04,
}


def front_gap(state: VehicleState, obstacles: List[Obstacle]) -> float:
    """REQ-SEN-01, §7: 차량 횡방향 통로[y-B/2,y+B/2]와 겹치고, 차체 전단을 아직 완전히
    지나치지 않은(obs.x_far>=fx) 장애물만 대상 (v1.1: 방향 필터 추가, 위 모듈 docstring 참고)."""
    fx = front_x(state)
    y_lo, y_hi = state.y - config.B / 2, state.y + config.B / 2
    best = config.LIDAR_MAX_RANGE
    for obs in obstacles:
        if obs.y_hi < y_lo or obs.y_lo > y_hi:
            continue
        if obs.x_far < fx:
            continue
        gap = max(0.0, obs.x_near - fx)
        best = min(best, gap)
    return best


def _window_clear(state: VehicleState, obstacles: List[Obstacle], y_lo: float, y_hi: float) -> bool:
    """REQ-SEN-02/04: 지정 차로 범위 x 종방향 윈도우[rear-G_SAFE_MIN, front+G_TRIG]에
    장애물이 없으면 True."""
    rx = rear_x(state)
    fx = front_x(state)
    win_lo, win_hi = rx - config.G_SAFE_MIN, fx + config.G_TRIG
    for obs in obstacles:
        lat_overlap = not (obs.y_hi < y_lo or obs.y_lo > y_hi)
        lon_overlap = not (obs.x_far < win_lo or obs.x_near > win_hi)
        if lat_overlap and lon_overlap:
            return False
    return True


def left_clear(state: VehicleState, obstacles: List[Obstacle]) -> bool:
    """REQ-SEN-02: L1 범위[0.15,0.45]."""
    return _window_clear(state, obstacles, 0.15, 0.45)


def right_clear(state: VehicleState, obstacles: List[Obstacle]) -> bool:
    """REQ-SEN-04: L2 범위[-0.15,0.15]."""
    return _window_clear(state, obstacles, -0.15, 0.15)


def ir_pattern(state: VehicleState, candidate_lines: Tuple[float, ...] = None) -> Pattern:
    """REQ-SEN-03: 3센서(좌+0.04/중0/우-0.04, vehicle-frame), 라인폭 0.06m.
    두 후보 라인(L2 중심 0, L1 중심 W) 중 감지범위 안에 든 것 중 더 가까운 쪽 채택."""
    if candidate_lines is None:
        candidate_lines = (0.0, config.W)
    half_w = config.LINE_WIDTH / 2.0
    best_pattern: Pattern = (0, 0, 0)
    best_dist = None
    for line_y in candidate_lines:
        rel = line_y - state.y  # vehicle-frame 상대위치
        left = 1 if abs(rel - config.SENSOR_SPACING) <= half_w else 0
        center = 1 if abs(rel - 0.0) <= half_w else 0
        right = 1 if abs(rel - (-config.SENSOR_SPACING)) <= half_w else 0
        pattern = (left, center, right)
        if pattern != (0, 0, 0):
            dist = abs(rel)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_pattern = pattern
    return best_pattern


def ey_line(pattern: Pattern) -> Optional[float]:
    """REQ-SEN-03: 패턴->ey_line. 000 및 비정상 패턴은 None(미검출, REQ-LAT-03)."""
    if pattern == (0, 0, 0):
        return None
    return _IR_TABLE.get(pattern, None)


# ===== S4 센서 노이즈([발전], ROBUSTNESS_PLAN.md) =====
# 아래 4개 함수는 위 정상 함수를 그대로 호출해 감싸는 wrapper다 -- 정상 함수(front_gap 등)
# 내부는 한 글자도 바꾸지 않았고, 제어기(FSM/MPC/postprocess/종방향)도 이 노이즈 유무를
# 모른다(runner.py가 어느 쪽을 부를지만 선택). 노이즈 rng는 world 생성용 rng와 분리된
# 별도 스트림을 호출부에서 넘겨받는다(ROBUSTNESS_PLAN.md S4).

def front_gap_noisy(state: VehicleState, obstacles: List[Obstacle], rng: np.random.Generator,
                     sigma: float) -> float:
    clean = front_gap(state, obstacles)
    noisy = clean + rng.normal(0.0, sigma)
    return float(np.clip(noisy, 0.0, config.LIDAR_MAX_RANGE))


def ey_line_noisy(clean_value: Optional[float], rng: np.random.Generator,
                   sigma: float) -> Optional[float]:
    """검출된 경우(clean_value가 None이 아닐 때)만 노이즈를 더한다(미검출 자체는 유지)."""
    if clean_value is None:
        return None
    return float(clean_value + rng.normal(0.0, sigma))


def left_clear_noisy(state: VehicleState, obstacles: List[Obstacle], rng: np.random.Generator,
                      flip_p: float) -> bool:
    clean = left_clear(state, obstacles)
    return (not clean) if rng.uniform() < flip_p else clean


def right_clear_noisy(state: VehicleState, obstacles: List[Obstacle], rng: np.random.Generator,
                       flip_p: float) -> bool:
    clean = right_clear(state, obstacles)
    return (not clean) if rng.uniform() < flip_p else clean


@dataclass(frozen=True)
class NoiseProfile:
    name: str
    sigma_front_gap: float  # m
    sigma_ey: float         # m
    flip_p: float           # left_clear/right_clear 오판정 확률


NOISE_PROFILES = {
    "low": NoiseProfile("low", sigma_front_gap=0.01, sigma_ey=0.005, flip_p=0.01),
    "medium": NoiseProfile("medium", sigma_front_gap=0.03, sigma_ey=0.01, flip_p=0.03),
    "high": NoiseProfile("high", sigma_front_gap=0.05, sigma_ey=0.02, flip_p=0.05),
}
