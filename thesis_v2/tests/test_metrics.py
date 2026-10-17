import pytest

from thesis_v2.baseline import config, metrics
from thesis_v2.baseline.fsm import FSMState

TOL = metrics.TOL_DELTA_DEG  # eps_abs(rad) -> deg, §18


def test_classify_clip_none_when_within_bound():
    assert metrics.classify_clip(24.0) is None
    assert metrics.classify_clip(-25.0) is None


def test_classify_clip_numerical_within_eps():
    assert metrics.classify_clip(config.DELTA_MAX_DEG + TOL * 0.5) == "clip_numerical"
    assert metrics.classify_clip(-(config.DELTA_MAX_DEG + TOL)) == "clip_numerical"


def test_classify_clip_violation_beyond_eps():
    assert metrics.classify_clip(config.DELTA_MAX_DEG + TOL + 1.0) == "clip_violation"
    assert metrics.classify_clip(40.0) == "clip_violation"


def test_delta_within_tolerance_boundary():
    assert metrics.delta_within_tolerance(config.DELTA_MAX_DEG) is True
    assert metrics.delta_within_tolerance(config.DELTA_MAX_DEG + TOL) is True
    assert metrics.delta_within_tolerance(config.DELTA_MAX_DEG + TOL + 0.01) is False


def test_psi_within_tolerance_boundary():
    assert metrics.psi_within_tolerance(config.PSI_LIMIT_DEG) is True
    assert metrics.psi_within_tolerance(config.PSI_LIMIT_DEG + TOL + 0.01) is False


@pytest.mark.parametrize("state", [FSMState.KEEP_L2, FSMState.KEEP_L1,
                                    FSMState.EVADE_L, FSMState.RETURN_TO_L2])
def test_y_within_tolerance_per_state(state):
    lo, hi = config.POSITION_CONSTRAINTS[state.value]
    assert metrics.y_within_tolerance(lo, state) is True
    assert metrics.y_within_tolerance(hi, state) is True
    assert metrics.y_within_tolerance(lo - metrics.TOL_Y_M - 0.01, state) is False
    assert metrics.y_within_tolerance(hi + metrics.TOL_Y_M + 0.01, state) is False


def test_y_within_tolerance_safe_stop_is_not_applicable():
    """REQ-LAT-05(§16): SAFE_STOP엔 위치제약이 정의되지 않음 -> None(해당없음)."""
    assert metrics.y_within_tolerance(0.0, FSMState.SAFE_STOP) is None


def test_is_saturated_boundary():
    assert metrics.is_saturated(config.DELTA_MAX_DEG - 0.01) is True
    assert metrics.is_saturated(config.DELTA_MAX_DEG - 0.02) is False
    assert metrics.is_saturated(-(config.DELTA_MAX_DEG - 0.01)) is True
