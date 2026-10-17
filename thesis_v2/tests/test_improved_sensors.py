"""
Stage 2(I2) 센서 확장 단위 테스트. DESIGN_IMPROVED.md §2.
"""
from thesis_v2.baseline import config
from thesis_v2.baseline.vehicle import initial_state
from thesis_v2.baseline.world import Obstacle
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.improved.sensors import front_obstacle_info


def test_front_obstacle_info_matches_front_gap_and_reports_bounds():
    state = initial_state(v0=0.4, y0=0.0)
    obs = Obstacle(x_near=1.0, x_far=1.2, y_lo=-0.075, y_hi=0.075)
    info = front_obstacle_info(state, [obs])
    assert info is not None
    expected_gap = base_sensors.front_gap(state, [obs])
    assert abs(info.gap_near - expected_gap) < 1e-9
    assert abs(info.gap_far - (expected_gap + 0.2)) < 1e-9  # 장애물 길이 0.2
    assert info.y_lo == -0.075 and info.y_hi == 0.075


def test_front_obstacle_info_none_when_out_of_corridor():
    state = initial_state(v0=0.4, y0=0.0)
    obs = Obstacle(x_near=0.5, x_far=0.7, y_lo=0.5, y_hi=0.65)  # 통로 밖
    assert front_obstacle_info(state, [obs]) is None


def test_front_obstacle_info_excludes_passed_obstacle():
    """v1.1 front_gap 방향 필터(REQ-SEN-01)와 동일 원칙: 완전히 지나친 장애물 제외."""
    from thesis_v2.baseline.vehicle import VehicleState
    state = VehicleState(x=1.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=0.0, x_far=0.2, y_lo=-0.075, y_hi=0.075)  # front_x=1.2보다 뒤
    assert front_obstacle_info(state, [obs]) is None


def test_front_obstacle_info_picks_nearest():
    state = initial_state(v0=0.4, y0=0.0)
    near = Obstacle(x_near=1.0, x_far=1.2, y_lo=-0.075, y_hi=0.075)
    far = Obstacle(x_near=2.0, x_far=2.2, y_lo=-0.075, y_hi=0.075)
    info = front_obstacle_info(state, [far, near])
    assert abs(info.gap_near - (1.0 - config.L)) < 1e-9
