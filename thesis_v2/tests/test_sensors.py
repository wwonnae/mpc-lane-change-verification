import pytest

from thesis_v2.baseline import config, sensors
from thesis_v2.baseline.vehicle import initial_state
from thesis_v2.baseline.world import Obstacle


# ---------- IR 6패턴 -> ey_line ----------

@pytest.mark.parametrize("pattern,expected", [
    ((0, 1, 0), 0.0),
    ((1, 1, 0), -0.02),
    ((1, 0, 0), -0.04),
    ((0, 1, 1), 0.02),
    ((0, 0, 1), 0.04),
    ((0, 0, 0), None),
])
def test_ir_pattern_to_ey_line(pattern, expected):
    assert sensors.ey_line(pattern) == expected


# ---------- front_gap 통로 판정 (3) ----------

def test_front_gap_obstacle_in_corridor():
    state = initial_state(v0=0.4, y0=0.0)
    obs = Obstacle(x_near=1.0, x_far=1.2, y_lo=-0.075, y_hi=0.075)
    gap = sensors.front_gap(state, [obs])
    assert gap == pytest.approx(1.0 - config.L)


def test_front_gap_obstacle_outside_corridor_ignored():
    state = initial_state(v0=0.4, y0=0.0)
    obs = Obstacle(x_near=0.5, x_far=0.7, y_lo=0.5, y_hi=0.65)  # 차량 통로[-0.075,0.075] 밖
    gap = sensors.front_gap(state, [obs])
    assert gap == config.LIDAR_MAX_RANGE


def test_front_gap_picks_nearest_of_multiple():
    state = initial_state(v0=0.4, y0=0.0)
    near = Obstacle(x_near=1.0, x_far=1.2, y_lo=-0.075, y_hi=0.075)
    far = Obstacle(x_near=2.0, x_far=2.2, y_lo=-0.075, y_hi=0.075)
    gap = sensors.front_gap(state, [far, near])
    assert gap == pytest.approx(1.0 - config.L)


# ---------- left_clear / right_clear 윈도우 (4) ----------

def test_left_clear_blocked_by_obstacle_in_l1():
    state = initial_state(v0=0.4, y0=0.0)
    obs = Obstacle(x_near=0.5, x_far=0.7, y_lo=0.15, y_hi=0.45)
    assert sensors.left_clear(state, [obs]) is False


def test_left_clear_unaffected_by_obstacle_in_l2_only():
    state = initial_state(v0=0.4, y0=0.0)
    obs = Obstacle(x_near=0.5, x_far=0.7, y_lo=-0.075, y_hi=0.075)
    assert sensors.left_clear(state, [obs]) is True


def test_right_clear_blocked_by_obstacle_in_l2():
    state = initial_state(v0=0.4, y0=config.W)
    obs = Obstacle(x_near=0.5, x_far=0.7, y_lo=-0.15, y_hi=0.15)
    assert sensors.right_clear(state, [obs]) is False


def test_right_clear_unaffected_by_obstacle_in_l1_only():
    state = initial_state(v0=0.4, y0=config.W)
    obs = Obstacle(x_near=0.5, x_far=0.7, y_lo=0.20, y_hi=0.40)  # L2 경계(0.15)와 겹치지 않게
    assert sensors.right_clear(state, [obs]) is True
