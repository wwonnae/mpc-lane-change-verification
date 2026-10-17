import pytest

from thesis_v2.baseline import config
from thesis_v2.baseline.fsm import FSM, FSMState, SensorReadings, initial_fsm, step, target_line_y

T0 = 10.0  # 임의의 기준 시각(쿨다운 항상 만료되도록 last_change_t=T0-COOLDOWN 이하로 설정)


def _fsm(state, t=T0):
    return FSM(state=state, last_change_t=t - config.COOLDOWN - 0.01, state_enter_t=t - 1.0)


# ---------- 5개 주요 전이 x 2(양성/음성) = 10 ----------

def test_keep_l2_to_evade_l_positive():
    fsm = _fsm(FSMState.KEEP_L2)
    sr = SensorReadings(front_gap=config.G_TRIG - 0.1, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.EVADE_L


def test_keep_l2_to_evade_l_negative_not_left_clear():
    fsm = _fsm(FSMState.KEEP_L2)
    sr = SensorReadings(front_gap=config.G_TRIG - 0.1, left_clear=False, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L2


def test_evade_l_to_keep_l1_positive():
    fsm = _fsm(FSMState.EVADE_L)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=config.W, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L1


def test_evade_l_to_keep_l1_negative_far_from_l1():
    fsm = _fsm(FSMState.EVADE_L)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=config.W - config.NEAR_L1 - 0.05, psi_deg=0.0, t=T0)
    assert out.state == FSMState.EVADE_L


def test_keep_l1_to_return_positive():
    fsm = FSM(state=FSMState.KEEP_L1, last_change_t=T0 - 10, state_enter_t=T0 - config.T_KEEP_L1_MIN - 0.1)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=config.W, psi_deg=0.0, t=T0)
    assert out.state == FSMState.RETURN_TO_L2


def test_keep_l1_to_return_negative_right_not_clear():
    fsm = FSM(state=FSMState.KEEP_L1, last_change_t=T0 - 10, state_enter_t=T0 - config.T_KEEP_L1_MIN - 0.1)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=False)
    out = step(fsm, sr, y=config.W, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L1


def test_return_to_keep_l2_positive():
    fsm = _fsm(FSMState.RETURN_TO_L2)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=config.NEAR_L2 - 0.01, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L2


def test_return_to_keep_l2_negative_psi_too_large():
    fsm = _fsm(FSMState.RETURN_TO_L2)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=config.PSI_L2_LIMIT_DEG + 5.0, t=T0)
    assert out.state == FSMState.RETURN_TO_L2


def test_any_state_to_safe_stop_positive():
    fsm = _fsm(FSMState.KEEP_L2)
    sr = SensorReadings(front_gap=config.G_SAFE_MIN - 0.01, left_clear=False, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.SAFE_STOP


def test_safe_stop_condition_negative_left_clear_true():
    fsm = _fsm(FSMState.KEEP_L2)
    sr = SensorReadings(front_gap=config.G_SAFE_MIN - 0.01, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state != FSMState.SAFE_STOP


# ---------- 쿨다운 (5개 전이 차단 + 초기화 상태 1) = 6 ----------

def _fsm_cooldown_blocked(state, t=T0):
    return FSM(state=state, last_change_t=t - config.COOLDOWN + 0.05, state_enter_t=t - 1.0)


def test_cooldown_blocks_keep_l2_to_evade():
    fsm = _fsm_cooldown_blocked(FSMState.KEEP_L2)
    sr = SensorReadings(front_gap=config.G_TRIG - 0.1, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L2


def test_cooldown_blocks_evade_to_keep_l1():
    fsm = _fsm_cooldown_blocked(FSMState.EVADE_L)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=config.W, psi_deg=0.0, t=T0)
    assert out.state == FSMState.EVADE_L


def test_cooldown_blocks_keep_l1_to_return():
    fsm = FSM(state=FSMState.KEEP_L1, last_change_t=T0 - config.COOLDOWN + 0.05,
              state_enter_t=T0 - config.T_KEEP_L1_MIN - 0.1)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=config.W, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L1


def test_cooldown_blocks_return_to_keep_l2():
    fsm = _fsm_cooldown_blocked(FSMState.RETURN_TO_L2)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.RETURN_TO_L2


def test_cooldown_blocks_safe_stop():
    fsm = _fsm_cooldown_blocked(FSMState.KEEP_L2)
    sr = SensorReadings(front_gap=config.G_SAFE_MIN - 0.01, left_clear=False, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.KEEP_L2


def test_initial_fsm_cooldown_pre_expired():
    """§13: 초기화 시 쿨다운이 이미 만료된 것으로 취급 -> 첫 전이를 막지 않는다."""
    fsm = initial_fsm()
    sr = SensorReadings(front_gap=config.G_TRIG - 0.1, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=0.0)
    assert out.state == FSMState.EVADE_L


# ---------- SAFE_STOP 진입: 5개 모든 상태 ----------

@pytest.mark.parametrize("src_state", list(FSMState))
def test_safe_stop_from_every_state(src_state):
    fsm = _fsm(src_state)
    sr = SensorReadings(front_gap=config.G_SAFE_MIN - 0.01, left_clear=False, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.SAFE_STOP


# ---------- SAFE_STOP은 종단 상태(REQ-FSM-04, §1): 어떤 센서값에도 벗어나지 않음 ----------

def test_safe_stop_is_terminal_no_recovery():
    fsm = _fsm(FSMState.SAFE_STOP)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    out = step(fsm, sr, y=0.0, psi_deg=0.0, t=T0)
    assert out.state == FSMState.SAFE_STOP
    assert out is fsm  # 상태 불변이므로 새 FSM을 만들지 않고 그대로 반환
