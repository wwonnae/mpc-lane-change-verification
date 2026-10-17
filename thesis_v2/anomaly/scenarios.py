"""
이상탐지 전용 시나리오 (DESIGN.md §10 D3).

baseline `world.generate_scenario`와 같은 난수 소비 순서(front_gap0 → v0 → y0)를 따르되,
장애물 초기 전단거리 범위만 `ANOMALY_FRONT_GAP_RANGE`로 바꾼다. baseline world.py는 수정하지
않고 그 안의 도우미(_make_obstacle, _sample_truncated_y0)를 그대로 재사용한다.
"""
import numpy as np

from thesis_v2.baseline import config as base_config
from thesis_v2.baseline.world import Scenario, _make_obstacle, _sample_truncated_y0

from . import config as an_config


def generate_anomaly_scenario(seed: int, left_obstacle: bool = False) -> Scenario:
    """left_obstacle=False: L2 장애물 1개(논문 시나리오와 같은 구조, 거리만 멀리).
    left_obstacle=True: 같은 종방향 구간 L1에도 장애물(→ 정상이면 SAFE_STOP,
    baseline generate_left_obstacle_scenario와 같은 구조)."""
    rng = np.random.default_rng(seed)
    front_gap0 = rng.uniform(*an_config.ANOMALY_FRONT_GAP_RANGE)
    x_near = base_config.L + front_gap0  # t=0 전단 위치(L) + front_gap0 (REQ-SIM-02a §12)
    obstacles = [_make_obstacle(x_near, y_center=0.0)]
    if left_obstacle:
        obstacles.append(_make_obstacle(x_near, y_center=base_config.W))
    v0 = rng.uniform(*base_config.INITIAL_V_RANGE)
    y0 = _sample_truncated_y0(rng)
    name = "anomaly_far_leftobs" if left_obstacle else "anomaly_far"
    return Scenario(obstacles=obstacles, v0=v0, y0=y0, psi0_deg=0.0, seed=seed, name=name)


def initial_front_gap(scenario: Scenario) -> float:
    """t=0 기준 첫 장애물 전단거리(시나리오 생성값 복원, 고장 onset 범위 계산용)."""
    return scenario.obstacles[0].x_near - base_config.L


def estimated_trigger_step(scenario: Scenario) -> int:
    """정상 주행 시 front_gap이 G_TRIG에 닿는 step 추정치(고장 onset 범위 계산용, 제어에 쓰지 않음).
    v는 첫 step만 v0이고 이후 V_MAX(REQ-VEH-05, longitudinal.py) — 첫 step 이동은 v0·dt."""
    fg0 = initial_front_gap(scenario)
    remaining = fg0 - scenario.v0 * base_config.DT - base_config.G_TRIG
    return 1 + max(0, int(np.ceil(remaining / (base_config.V_MAX * base_config.DT))))
