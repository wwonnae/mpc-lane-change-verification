import pytest

from thesis_v2.baseline import config
from thesis_v2.baseline.postprocess import apply

RATE = config.DELTA_RATE_MAX_PER_STEP_DEG  # 10.0 deg/step


def test_rate_limit_boundary_exact_not_active():
    res = apply(delta_desired_deg=RATE, delta_prev_deg=0.0)
    assert res.rate_limit_active is False
    assert res.delta_final_deg == pytest.approx(RATE)


def test_rate_limit_boundary_just_over_active():
    res = apply(delta_desired_deg=RATE + 0.001, delta_prev_deg=0.0)
    assert res.rate_limit_active is True
    assert res.delta_final_deg == pytest.approx(RATE)


def test_clip_boundary_exact_not_active():
    res = apply(delta_desired_deg=config.DELTA_MAX_DEG, delta_prev_deg=config.DELTA_MAX_DEG)
    assert res.clip_active is False
    assert res.delta_final_deg == pytest.approx(config.DELTA_MAX_DEG)


def test_clip_boundary_just_over_active():
    res = apply(delta_desired_deg=config.DELTA_MAX_DEG + 1.0, delta_prev_deg=config.DELTA_MAX_DEG)
    assert res.clip_active is True
    assert res.delta_final_deg == pytest.approx(config.DELTA_MAX_DEG)


def test_order_is_rate_limit_then_clip():
    """§15: rate limit 먼저, 그다음 clip. rate 적용 후 값을 기준으로 clip 판정해야 한다."""
    res = apply(delta_desired_deg=40.0, delta_prev_deg=24.0)
    # rate: clamp(40, 14, 34) = 34 -> rate_active True
    # clip: clamp(34, -25, 25) = 25 -> clip_active True
    assert res.rate_limit_active is True
    assert res.clip_active is True
    assert res.delta_final_deg == pytest.approx(config.DELTA_MAX_DEG)
