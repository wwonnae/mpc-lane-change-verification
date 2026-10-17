"""FSM 경계 테스트 보강 — mutation testing 1차 생존 변이 중 테스트 공백(docs/verification/mutation/equivalence.json).

이 파일의 테스트는 LLM(Claude Code)이 제안했다. 수락 기준과 검토 기록은 docs/verification/mutation/RESULTS.md,
llm_tests_log.json에 있다(PREREGISTRATION.md §8).

SPEC은 전이 조건의 엄격/비엄격 부등호를 구분한다. 각 테스트는 경계값을 정확히 넣고, 전제 assert로 그 값이 부동소수점에서도
정확히 경계임을 확인한다. FSM은 도달 가능한 형태(last_change_t == state_enter_t, fsm.py:74)로 만든다.
"""
from thesis_v2.baseline import config
from thesis_v2.baseline.fsm import FSM, FSMState, SensorReadings, step


def _entered(state, t_enter):
    """t_enter에 state로 전이한 직후의 FSM(fsm.py:74와 같은 형태)."""
    return FSM(state=state, last_change_t=t_enter, state_enter_t=t_enter)


def test_safe_stop_requires_front_gap_strictly_below_g_safe_min():
    """REQ-FSM-02b: SAFE_STOP 조건은 front_gap < 0.20(엄격) AND left_clear=False. front_gap = 0.20이면 전이하지 않는다."""
    fsm = _entered(FSMState.KEEP_L2, 0.0)
    t = 1.0
    assert t - fsm.last_change_t >= config.COOLDOWN
    out = step(fsm, SensorReadings(front_gap=config.G_SAFE_MIN, left_clear=False, right_clear=True), y=0.0, psi_deg=0.0, t=t)
    assert out.state == FSMState.KEEP_L2
    below = step(fsm, SensorReadings(front_gap=0.19, left_clear=False, right_clear=True), y=0.0, psi_deg=0.0, t=t)
    assert below.state == FSMState.SAFE_STOP


def test_keep_l1_return_requires_elapsed_strictly_above_t_keep_l1_min():
    """REQ-FSM-02d: KEEP_L1→RETURN_TO_L2는 right_clear AND t > 0.6 s(엄격). 진입 뒤 정확히 0.6 s이면 전이하지 않는다."""
    fsm = _entered(FSMState.KEEP_L1, 0.0)
    t = 0.6
    assert t - fsm.state_enter_t == config.T_KEEP_L1_MIN
    assert t - fsm.last_change_t >= config.COOLDOWN
    sr = SensorReadings(front_gap=10.0, left_clear=True, right_clear=True)
    assert step(fsm, sr, y=config.W, psi_deg=0.0, t=t).state == FSMState.KEEP_L1
    assert step(fsm, sr, y=config.W, psi_deg=0.0, t=0.65).state == FSMState.RETURN_TO_L2


def test_return_to_keep_l2_accepts_y_exactly_near_l2():
    """REQ-FSM-02e: RETURN_TO_L2→KEEP_L2는 |y| ≤ 0.08 m(비엄격) AND |ψ| ≤ 20°. |y| = 0.08이면 전이한다."""
    fsm = _entered(FSMState.RETURN_TO_L2, 0.0)
    y = config.NEAR_L2
    assert abs(y) == config.NEAR_L2
    sr = SensorReadings(front_gap=10.0, left_clear=True, right_clear=True)
    assert step(fsm, sr, y=y, psi_deg=0.0, t=1.0).state == FSMState.KEEP_L2
    assert step(fsm, sr, y=-y, psi_deg=0.0, t=1.0).state == FSMState.KEEP_L2


def test_return_to_keep_l2_accepts_psi_exactly_limit():
    """REQ-FSM-02e: RETURN_TO_L2→KEEP_L2는 |ψ| ≤ 20°(비엄격). |ψ| = 20°이면 전이한다."""
    fsm = _entered(FSMState.RETURN_TO_L2, 0.0)
    psi = config.PSI_L2_LIMIT_DEG
    assert abs(-psi) == config.PSI_L2_LIMIT_DEG
    sr = SensorReadings(front_gap=10.0, left_clear=True, right_clear=True)
    assert step(fsm, sr, y=0.0, psi_deg=psi, t=1.0).state == FSMState.KEEP_L2
    assert step(fsm, sr, y=0.0, psi_deg=-psi, t=1.0).state == FSMState.KEEP_L2
