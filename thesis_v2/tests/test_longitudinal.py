import pytest

from thesis_v2.baseline import config
from thesis_v2.baseline.fsm import FSMState
from thesis_v2.baseline.longitudinal import compute_v_cmd


@pytest.mark.parametrize("state,expected", [
    (FSMState.KEEP_L2, config.V_MAX),
    (FSMState.EVADE_L, config.V_MAX),
    (FSMState.KEEP_L1, config.V_MAX),
    (FSMState.RETURN_TO_L2, config.V_MAX),
    (FSMState.SAFE_STOP, 0.0),
])
def test_v_cmd_per_state(state, expected):
    assert compute_v_cmd(state) == expected
