import math

from thesis_v2.baseline import config
from thesis_v2.baseline.collision import check_collision
from thesis_v2.baseline.vehicle import VehicleState
from thesis_v2.baseline.world import Obstacle


def test_no_overlap_far_obstacle():
    state = VehicleState(x=0.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=5.0, x_far=5.2, y_lo=-0.075, y_hi=0.075)
    assert check_collision(state, [obs]) is False


def test_full_overlap_same_footprint():
    state = VehicleState(x=0.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=0.0, x_far=config.L, y_lo=-config.B / 2, y_hi=config.B / 2)
    assert check_collision(state, [obs]) is True


def test_partial_overlap():
    state = VehicleState(x=0.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=config.L / 2, x_far=config.L / 2 + config.L, y_lo=-config.B / 2, y_hi=config.B / 2)
    assert check_collision(state, [obs]) is True


def test_rotated_vehicle_corner_pokes_into_obstacle():
    """헤딩이 있는 상태에서 축정렬 바운딩박스로는 안 걸리지만 회전 사각형으로는 겹치는 경우."""
    state = VehicleState(x=0.0, y=0.0, psi=math.radians(60.0), v=0.4)
    # 회전으로 인해 전방 모서리가 y방향으로 크게 튀어나옴. 그 모서리 위치에 작은 장애물을 둔다.
    front_x = config.L * math.cos(state.psi)
    front_y = config.L * math.sin(state.psi)
    obs = Obstacle(x_near=front_x - 0.02, x_far=front_x + 0.02,
                   y_lo=front_y - 0.02, y_hi=front_y + 0.02)
    assert check_collision(state, [obs]) is True
