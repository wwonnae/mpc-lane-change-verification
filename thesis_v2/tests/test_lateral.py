import pytest

from thesis_v2.baseline.fsm import FSMState
from thesis_v2.baseline.lateral import compute_lateral
from thesis_v2.baseline.mpc import OSQPMPC


@pytest.fixture(scope="module")
def mpc():
    return OSQPMPC()


@pytest.mark.parametrize("state", [FSMState.KEEP_L2, FSMState.KEEP_L1])
def test_keep_state_line_follow_when_detected(mpc, state):
    res = compute_lateral(state, ey=0.02, y=0.0, psi_rad=0.0, v=0.4, mpc=mpc, delta_prev_deg=0.0)
    assert res.mode == "line_follow"
    assert res.mpc_result is None


@pytest.mark.parametrize("state", [FSMState.KEEP_L2, FSMState.KEEP_L1])
def test_keep_state_mpc_when_not_detected(mpc, state):
    res = compute_lateral(state, ey=None, y=0.0, psi_rad=0.0, v=0.4, mpc=mpc, delta_prev_deg=0.0)
    assert res.mode == "mpc"
    assert res.mpc_result is not None


@pytest.mark.parametrize("state", [FSMState.EVADE_L, FSMState.RETURN_TO_L2])
def test_evade_return_always_mpc_when_detected(mpc, state):
    res = compute_lateral(state, ey=0.02, y=0.0, psi_rad=0.0, v=0.4, mpc=mpc, delta_prev_deg=0.0)
    assert res.mode == "mpc"
    assert res.mpc_result is not None


@pytest.mark.parametrize("state", [FSMState.EVADE_L, FSMState.RETURN_TO_L2])
def test_evade_return_always_mpc_when_not_detected(mpc, state):
    res = compute_lateral(state, ey=None, y=0.0, psi_rad=0.0, v=0.4, mpc=mpc, delta_prev_deg=0.0)
    assert res.mode == "mpc"
    assert res.mpc_result is not None


# ---------- SAFE_STOP: 직전 최종 조향각 유지 (REQ-LAT-05, §16) ----------

@pytest.mark.parametrize("ey", [None, 0.02, -0.04])
def test_safe_stop_holds_last_delta_regardless_of_ey(mpc, ey):
    res = compute_lateral(FSMState.SAFE_STOP, ey=ey, y=0.3, psi_rad=0.1, v=0.0, mpc=mpc,
                           delta_prev_deg=7.5)
    assert res.mode == "hold_last"
    assert res.mpc_result is None
    assert res.delta_desired_deg == pytest.approx(7.5)


def test_safe_stop_does_not_call_mpc(mpc):
    """SAFE_STOP은 POSITION_CONSTRAINTS에 키가 없으므로(SETTINGS_DECISION §16), MPC가
    호출되면 KeyError가 나야 한다 -- 즉 호출되지 않음을 간접 확인."""
    from unittest.mock import patch
    with patch.object(mpc, "solve", side_effect=AssertionError("MPC must not be called in SAFE_STOP")):
        res = compute_lateral(FSMState.SAFE_STOP, ey=None, y=0.0, psi_rad=0.0, v=0.0, mpc=mpc,
                               delta_prev_deg=-3.0)
    assert res.delta_desired_deg == pytest.approx(-3.0)
