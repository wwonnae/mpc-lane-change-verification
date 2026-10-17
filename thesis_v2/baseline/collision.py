"""
회전 사각형 SAT 충돌 판정. 논문 제출 이후 작성.
REQ-SIM-08, §8: 차체(L x B, 헤딩 반영) vs 장애물(L x B, 축정렬) 겹침 검사.
"""
import math
from typing import List, Tuple

from . import config
from .vehicle import VehicleState
from .world import Obstacle

Point = Tuple[float, float]


def _vehicle_corners(state: VehicleState) -> List[Point]:
    """후륜을 원점으로 종방향 [0,L], 횡방향 [-B/2,B/2]를 psi만큼 회전."""
    L, B = config.L, config.B
    local = [(0, -B / 2), (L, -B / 2), (L, B / 2), (0, B / 2)]
    ch, sh = math.cos(state.psi), math.sin(state.psi)
    return [(state.x + lx * ch - ly * sh, state.y + lx * sh + ly * ch) for lx, ly in local]


def _obstacle_corners(obs: Obstacle) -> List[Point]:
    return [
        (obs.x_near, obs.y_lo), (obs.x_far, obs.y_lo),
        (obs.x_far, obs.y_hi), (obs.x_near, obs.y_hi),
    ]


def _sat_overlap(p1: List[Point], p2: List[Point]) -> bool:
    for poly in (p1, p2):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            nx, ny = -(y2 - y1), (x2 - x1)
            norm = math.hypot(nx, ny)
            if norm < 1e-12:
                continue
            nx, ny = nx / norm, ny / norm
            proj1 = [px * nx + py * ny for px, py in p1]
            proj2 = [px * nx + py * ny for px, py in p2]
            if max(proj1) < min(proj2) or max(proj2) < min(proj1):
                return False
    return True


def check_collision(state: VehicleState, obstacles: List[Obstacle]) -> bool:
    veh = _vehicle_corners(state)
    for obs in obstacles:
        if _sat_overlap(veh, _obstacle_corners(obs)):
            return True
    return False
