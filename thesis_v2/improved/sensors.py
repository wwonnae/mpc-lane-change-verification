"""
개선판 센서 계층. baseline `sensors.py`의 기존 함수(front_gap/left_clear/right_clear/
ir_pattern/ey_line)는 수정 없이 그대로 재사용(재정의하지 않음, import). I2용 신규 함수
`front_obstacle_info()`만 추가한다 -- DESIGN_IMPROVED.md §2.

PDF p.7 "LiDAR 센서는 2D 스캔을 수행하여 주변 장애물까지의 거리를 측정" 근거: 2D 스캔은
개념적으로 거리뿐 아니라 방위(횡방향 범위)도 포함하므로, front_gap()이 이미 내부적으로
찾는 "가장 가까운 전방 장애물"의 나머지 정보(먼 쪽 면 거리, 좌우 경계)를 함께 반환하는
것은 새 센서가 아니라 같은 스캔에서 더 읽는 것이다. 제어기(improved MPC)는 이 함수의
반환값(스칼라 4개)만 받고 `Obstacle`/시뮬레이터 좌표를 직접 참조하지 않는다.
"""
from dataclasses import dataclass
from typing import List, Optional

# baseline 함수는 재정의하지 않고 그대로 재노출한다(단일 출처 유지).
from thesis_v2.baseline.sensors import (  # noqa: F401
    front_gap, left_clear, right_clear, ir_pattern, ey_line,
)
from thesis_v2.baseline.vehicle import VehicleState, front_x
from thesis_v2.baseline.world import Obstacle


@dataclass(frozen=True)
class FrontObstacleInfo:
    gap_near: float  # front_gap()과 동일한 값(가장 가까운 면까지 거리)
    gap_far: float   # 장애물 먼 쪽 면까지 거리
    y_lo: float      # 장애물 좌측 경계
    y_hi: float      # 장애물 우측 경계


def front_obstacle_info(state: VehicleState, obstacles: List[Obstacle]) -> Optional[FrontObstacleInfo]:
    """front_gap()과 같은 탐색(차량 횡방향 통로와 겹치고 아직 안 지나친 장애물 중 가장
    가까운 것)을 재사용해 근/원 거리와 좌우 경계까지 함께 반환한다. baseline
    front_gap()과 완전히 같은 원칙(REQ-SEN-01, v1.1 방향 필터 포함)을 그대로 따른다."""
    import thesis_v2.baseline.config as base_config

    fx = front_x(state)
    y_lo_corridor, y_hi_corridor = state.y - base_config.B / 2, state.y + base_config.B / 2
    best: Optional[FrontObstacleInfo] = None
    best_gap = base_config.LIDAR_MAX_RANGE
    for obs in obstacles:
        if obs.y_hi < y_lo_corridor or obs.y_lo > y_hi_corridor:
            continue
        if obs.x_far < fx:
            continue
        gap_near = max(0.0, obs.x_near - fx)
        if gap_near < best_gap:
            best_gap = gap_near
            gap_far = max(gap_near, obs.x_far - fx)
            best = FrontObstacleInfo(gap_near=gap_near, gap_far=gap_far,
                                      y_lo=obs.y_lo, y_hi=obs.y_hi)
    return best
