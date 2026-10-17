"""FSM 전이 결정의 MC/DC 보강 테스트 — docs/verification/MCDC_FSM.md.

기존 test_fsm.py로 unique-cause 쌍이 확인되지 않은 조건 3개만 추가한다(측정: docs/verification/mcdc/mcdc_trace.py).
각 테스트는 쌍(참 사례·거짓 사례)을 함께 실행하고, (1) 결정의 조건 벡터가 대상 조건 하나만 다른지,
(2) step() 출력이 전이/유지로 뒤집히는지를 함께 검사한다. 조건 벡터는 SPEC(REQ-FSM-02a/02d/02e, 03a)을
config 상수로 다시 적은 것이다(fsm.py 내부를 쓰지 않음).
"""
from thesis_v2.baseline import config
from thesis_v2.baseline.fsm import FSM, FSMState, SensorReadings, step

T0 = 10.0


def _cond_d1(f, sr, t):
    """fsm.py:55 KEEP_L2→EVADE_L: cooldown_ok ∧ front_gap<G_TRIG ∧ left_clear."""
    return ((t - f.last_change_t) >= config.COOLDOWN, sr.front_gap < config.G_TRIG, sr.left_clear)


def _cond_d3(f, sr, t):
    """fsm.py:64 KEEP_L1→RETURN_TO_L2: cooldown_ok ∧ elapsed>T_KEEP_L1_MIN ∧ right_clear."""
    return ((t - f.last_change_t) >= config.COOLDOWN, (t - f.state_enter_t) > config.T_KEEP_L1_MIN, sr.right_clear)


def _cond_d4(f, y, psi_deg, t):
    """fsm.py:68 RETURN_TO_L2→KEEP_L2: cooldown_ok ∧ |y|≤NEAR_L2 ∧ |psi|≤PSI_L2_LIMIT_DEG."""
    return ((t - f.last_change_t) >= config.COOLDOWN, abs(y) <= config.NEAR_L2,
            abs(psi_deg) <= config.PSI_L2_LIMIT_DEG)


def _assert_unique_cause(v_true, v_false, idx):
    assert all(v_true), v_true
    assert v_true[idx] != v_false[idx]
    assert [i for i in range(len(v_true)) if v_true[i] != v_false[i]] == [idx], (v_true, v_false)


def test_mcdc_d1_front_gap_lt_g_trig():
    """REQ-FSM-02a: D1 조건 'front_gap < G_TRIG'의 독립 영향. 거짓 사례는 경계값 front_gap = G_TRIG(엄격 부등호)."""
    f = FSM(state=FSMState.KEEP_L2, last_change_t=T0 - 1.0, state_enter_t=T0 - 1.0)
    sr_t = SensorReadings(front_gap=config.G_TRIG - 0.01, left_clear=True, right_clear=True)
    sr_f = SensorReadings(front_gap=config.G_TRIG, left_clear=True, right_clear=True)
    _assert_unique_cause(_cond_d1(f, sr_t, T0), _cond_d1(f, sr_f, T0), idx=1)
    assert step(f, sr_t, y=0.0, psi_deg=0.0, t=T0).state == FSMState.EVADE_L
    assert step(f, sr_f, y=0.0, psi_deg=0.0, t=T0).state == FSMState.KEEP_L2


def test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form():
    """REQ-FSM-02d: D3 조건 't - state_enter_t > T_KEEP_L1_MIN'의 독립 영향.
    step()으로 도달 가능한 형태(last_change_t == state_enter_t, fsm.py:74)로 만든다 — 거짓 사례도 경과 0.5 s라
    쿨다운(0.3 s)은 참으로 유지된다. 경계 부동소수 오차를 피하려고 경계에서 ±0.1 s 떨어진 값을 쓴다."""
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    enter_t = T0 - (config.T_KEEP_L1_MIN + 0.1)
    enter_f = T0 - (config.T_KEEP_L1_MIN - 0.1)
    f_t = FSM(state=FSMState.KEEP_L1, last_change_t=enter_t, state_enter_t=enter_t)
    f_f = FSM(state=FSMState.KEEP_L1, last_change_t=enter_f, state_enter_t=enter_f)
    _assert_unique_cause(_cond_d3(f_t, sr, T0), _cond_d3(f_f, sr, T0), idx=1)
    assert step(f_t, sr, y=config.W, psi_deg=0.0, t=T0).state == FSMState.RETURN_TO_L2
    assert step(f_f, sr, y=config.W, psi_deg=0.0, t=T0).state == FSMState.KEEP_L1


def test_mcdc_d4_abs_y_le_near_l2():
    """REQ-FSM-02e([개정] NEAR_L2=0.08): D4 조건 '|y| <= NEAR_L2'의 독립 영향(ψ=0으로 헤딩 조건은 참 유지)."""
    f = FSM(state=FSMState.RETURN_TO_L2, last_change_t=T0 - 1.0, state_enter_t=T0 - 1.0)
    sr = SensorReadings(front_gap=5.0, left_clear=True, right_clear=True)
    y_t, y_f = config.NEAR_L2 - 0.01, config.NEAR_L2 + 0.01
    _assert_unique_cause(_cond_d4(f, y_t, 0.0, T0), _cond_d4(f, y_f, 0.0, T0), idx=1)
    assert step(f, sr, y=y_t, psi_deg=0.0, t=T0).state == FSMState.KEEP_L2
    assert step(f, sr, y=y_f, psi_deg=0.0, t=T0).state == FSMState.RETURN_TO_L2
