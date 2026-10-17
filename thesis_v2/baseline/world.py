"""
도로·장애물·시나리오 생성. 논문 제출 이후 작성.
REQ-SIM-01(도로), REQ-SIM-02/02a(장애물 위치, 전단 기준), REQ-SIM-03(초기조건, [개정]2 절단),
REQ-SIM-08(장애물 풋프린트 L x B).

**[발전] 강건성 검증(S3/S6/S7a/S7b) 추가(2026-09-22, ROBUSTNESS_PLAN.md)**: 아래
`generate_scenario`는 기본값이 기존과 동일한 `psi0_deg` 키워드 인자만 추가했고(S6),
`generate_grid_scenario`(S3)·`generate_scenario_custom_obstacle`(S7a)·
`generate_front_rear_scenario`(S7b)는 전부 신규 함수다. 기존 두 함수
(`generate_scenario`/`generate_left_obstacle_scenario`)의 내부 로직은 한 글자도
바꾸지 않았다(회귀 확인: `thesis_v2/tests/check_golden.py`, `thesis_v2/tests/test_run_cli.py`).
"""
from dataclasses import dataclass, field
from typing import List
import numpy as np

from . import config


@dataclass(frozen=True)
class Obstacle:
    x_near: float  # m, 차량에 가까운 쪽 면 (§12)
    x_far: float   # m, 먼 쪽 면
    y_lo: float    # m
    y_hi: float    # m


@dataclass(frozen=True)
class Scenario:
    obstacles: List[Obstacle]
    v0: float
    y0: float
    psi0_deg: float
    seed: int
    name: str = "paper"


def _make_obstacle(x_near: float, y_center: float, length: float = config.OBSTACLE_LENGTH,
                    width: float = config.OBSTACLE_WIDTH) -> Obstacle:
    return Obstacle(
        x_near=x_near,
        x_far=x_near + length,
        y_lo=y_center - width / 2,
        y_hi=y_center + width / 2,
    )


def _sample_truncated_y0(rng: np.random.Generator) -> float:
    """REQ-SIM-03 [개정]2: N(0, INITIAL_Y_STD^2)를 INITIAL_Y_TRUNC 범위로 절단."""
    lo, hi = config.INITIAL_Y_TRUNC
    for _ in range(1000):
        y0 = rng.normal(0.0, config.INITIAL_Y_STD)
        if lo <= y0 <= hi:
            return y0
    return 0.0  # 극히 낮은 확률의 폴백(사실상 도달 안 함)


def generate_scenario(seed: int, psi0_deg: float = 0.0) -> Scenario:
    """REQ-SIM-02: 장애물 1개, L2(y=0) 차선, front_gap0 ~ U(0.5,2.0) (§12 전단 기준).
    psi0_deg: S6(초기 헤딩 오차, ROBUSTNESS_PLAN.md) -- 기본값 0.0은 기존과 동일(REQ-SIM-03 [공백])."""
    rng = np.random.default_rng(seed)
    front_gap0 = rng.uniform(*config.OBSTACLE_FRONT_GAP_RANGE)
    x_near = config.L + front_gap0  # t=0 전단 위치(L) + front_gap0
    obstacle = _make_obstacle(x_near, y_center=0.0)
    v0 = rng.uniform(*config.INITIAL_V_RANGE)
    y0 = _sample_truncated_y0(rng)
    return Scenario(obstacles=[obstacle], v0=v0, y0=y0, psi0_deg=psi0_deg, seed=seed, name="paper")


def generate_grid_scenario(front_gap0: float, y0: float, v0: float = config.V_MAX,
                            psi0_deg: float = 0.0, seed: int = 0) -> Scenario:
    """S3(경계 지도, ROBUSTNESS_PLAN.md, [발전]): front_gap0 x y0 결정론적 격자용, 난수
    없음. v0=V_MAX·psi0=0 고정이 기본값(최소 반응시간 worst case, RESULT_BASELINE.md §4
    관례)."""
    x_near = config.L + front_gap0
    obstacle = _make_obstacle(x_near, y_center=0.0)
    return Scenario(obstacles=[obstacle], v0=v0, y0=y0, psi0_deg=psi0_deg, seed=seed,
                     name="robustness_s3_grid")


def generate_scenario_custom_obstacle(seed: int, obstacle_length: float = config.OBSTACLE_LENGTH,
                                       obstacle_width: float = config.OBSTACLE_WIDTH) -> Scenario:
    """S7a(장애물 크기 변화, ROBUSTNESS_PLAN.md, [발전]): generate_scenario와 동일한 난수
    샘플링 순서(front_gap0, v0, y0)를 따르되 장애물 크기만 다르게 만든다."""
    rng = np.random.default_rng(seed)
    front_gap0 = rng.uniform(*config.OBSTACLE_FRONT_GAP_RANGE)
    x_near = config.L + front_gap0
    obstacle = _make_obstacle(x_near, y_center=0.0, length=obstacle_length, width=obstacle_width)
    v0 = rng.uniform(*config.INITIAL_V_RANGE)
    y0 = _sample_truncated_y0(rng)
    return Scenario(obstacles=[obstacle], v0=v0, y0=y0, psi0_deg=0.0, seed=seed,
                     name="robustness_s7a_size")


def generate_front_rear_scenario(seed: int, front_gap0: float, rear_gap: float) -> Scenario:
    """S7b(전후 장애물 배치, ROBUSTNESS_PLAN.md, [발전]): 전방 장애물(front_gap0 고정) +
    같은 차로(L2) 후방 장애물(rear_gap, 차량 후단 기준 뒤쪽 거리). v0/y0는 generate_scenario와
    동일한 난수 샘플링 순서를 따른다."""
    rng = np.random.default_rng(seed)
    _ = rng.uniform(*config.OBSTACLE_FRONT_GAP_RANGE)  # generate_scenario와 같은 소비 순서 유지
    x_near = config.L + front_gap0
    obstacle_front = _make_obstacle(x_near, y_center=0.0)
    rear_x_far = 0.0 - rear_gap  # 초기 후륜 x=0 기준 rear_gap만큼 뒤(REQ-SIM-02a 전단 기준과
    # 대칭으로, 후방 장애물은 "가까운 면"(x_far, 차량에 더 가까운 쪽)을 기준으로 배치)
    obstacle_rear = Obstacle(x_near=rear_x_far - config.OBSTACLE_LENGTH, x_far=rear_x_far,
                              y_lo=-config.OBSTACLE_WIDTH / 2, y_hi=config.OBSTACLE_WIDTH / 2)
    v0 = rng.uniform(*config.INITIAL_V_RANGE)
    y0 = _sample_truncated_y0(rng)
    return Scenario(obstacles=[obstacle_front, obstacle_rear], v0=v0, y0=y0, psi0_deg=0.0,
                     seed=seed, name="robustness_s7b_frontrear")


def generate_left_obstacle_scenario(seed: int) -> Scenario:
    """추가 검증 시나리오: L2 장애물(회피 유발) + L1 장애물(같은 종방향 구간, left_clear=False
    유도) -> SAFE_STOP 검증용 (REQ-SEN-02, REQ-FSM-02b)."""
    rng = np.random.default_rng(seed)
    front_gap0 = rng.uniform(*config.OBSTACLE_FRONT_GAP_RANGE)
    x_near = config.L + front_gap0
    obstacle_front = _make_obstacle(x_near, y_center=0.0)
    obstacle_left = _make_obstacle(x_near, y_center=config.W)  # 같은 구간, L1(좌측 차로)
    v0 = rng.uniform(*config.INITIAL_V_RANGE)
    y0 = _sample_truncated_y0(rng)
    return Scenario(
        obstacles=[obstacle_front, obstacle_left],
        v0=v0, y0=y0, psi0_deg=0.0, seed=seed, name="left_obstacle",
    )
