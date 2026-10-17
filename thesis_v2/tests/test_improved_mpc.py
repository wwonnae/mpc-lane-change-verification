"""
Stage 1(I1, I1b) 단위 테스트. DESIGN_IMPROVED.md I1/I1b 참고.
"""
import math

from thesis_v2.baseline import config
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved import config as improved_config

_DEG2RAD = math.pi / 180.0
RATE = config.DELTA_RATE_MAX_PER_STEP_DEG  # 10 deg/step


# ---------- I1: rate limit·delta_prev 인지 ----------

def test_i1_off_allows_immediate_large_jump():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=False)
    r = mpc.solve(y0=0.0, psi0_rad=math.radians(-15.0), v0=0.5, target_y=0.0,
                  state_name="KEEP_L2", delta_prev_deg=0.0)
    assert r.ok
    assert abs(r.delta_deg) > RATE  # I1 없으면 rate와 무관하게 QP가 원하는 값을 그대로 냄


def test_i1_on_clamps_to_rate_from_delta_prev():
    mpc = ImprovedMPC(enable_i1=True, enable_i1b=False, enable_i2=False, enable_i3=False)
    r = mpc.solve(y0=0.0, psi0_rad=math.radians(-15.0), v0=0.5, target_y=0.0,
                  state_name="KEEP_L2", delta_prev_deg=0.0)
    assert r.ok
    assert abs(r.delta_deg) <= RATE + 1e-6  # delta_prev=0 -> |delta_0-0|<=10deg


def test_i1_on_clamps_relative_to_nonzero_delta_prev():
    mpc = ImprovedMPC(enable_i1=True, enable_i1b=False, enable_i2=False, enable_i3=False)
    r = mpc.solve(y0=0.0, psi0_rad=math.radians(-15.0), v0=0.5, target_y=0.0,
                  state_name="KEEP_L2", delta_prev_deg=15.0)
    assert r.ok
    assert 15.0 - RATE - 1e-6 <= r.delta_deg <= 15.0 + RATE + 1e-6


# ---------- I1b: 위치제약 소프트화 ----------

# seed=6(S6 psi0=-15deg) 재검증에서 실제로 infeasible이 발생한 시점의 상태
# (THESIS_REVISION_LOG.md 2026-09-22 정정 항목, repro/2c_analysis/s6_psi15_step0_reverify.py)
_INFEASIBLE_Y = -0.13851
_INFEASIBLE_PSI_DEG = -11.462
_INFEASIBLE_V = 0.5


def test_i1b_off_reports_infeasible_on_known_hard_case():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=False)
    r = mpc.solve(y0=_INFEASIBLE_Y, psi0_rad=math.radians(_INFEASIBLE_PSI_DEG), v0=_INFEASIBLE_V,
                  target_y=0.0, state_name="KEEP_L2")
    assert not r.ok
    assert r.solver_status == "primal infeasible"


def test_i1b_on_solves_the_same_known_hard_case():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=True, enable_i2=False, enable_i3=False)
    r = mpc.solve(y0=_INFEASIBLE_Y, psi0_rad=math.radians(_INFEASIBLE_PSI_DEG), v0=_INFEASIBLE_V,
                  target_y=0.0, state_name="KEEP_L2")
    assert r.ok  # 슬랙이 있으면 항상 feasible(볼록 QP, 슬랙 상한 +inf)


def test_i1b_zero_violation_when_feasible():
    """실현 가능한(정상) 입력에서는 소프트 제약도 위반=0(exact penalty)이어야 한다 --
    간접 확인: I1b on/off 결과가 실현 가능한 입력에서는 사실상 같아야 함."""
    mpc_hard = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=False)
    mpc_soft = ImprovedMPC(enable_i1=False, enable_i1b=True, enable_i2=False, enable_i3=False)
    r_hard = mpc_hard.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.30, state_name="EVADE_L")
    r_soft = mpc_soft.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.30, state_name="EVADE_L")
    assert r_hard.ok and r_soft.ok
    assert abs(r_hard.delta_deg - r_soft.delta_deg) <= 1e-2


# ---------- I2: margin/설정값 확인 ----------

def test_margin_i2_value():
    expected = config.B / 2 + config.L * math.sin(math.radians(config.PSI_LIMIT_DEG))
    assert abs(improved_config.MARGIN_I2 - expected) < 1e-9
    assert 0.27 < improved_config.MARGIN_I2 < 0.28


# ---------- I2: 예측 구간 y 하한 ----------

from thesis_v2.improved.sensors import FrontObstacleInfo  # noqa: E402


def test_i2_raises_lower_bound_within_obstacle_window():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=True, enable_i3=False)
    obs = FrontObstacleInfo(gap_near=0.3, gap_far=0.5, y_lo=-0.075, y_hi=0.075)
    v = 0.5
    y_lo_per_step, psi_lo_per_step, active = mpc._i2_bounds(base_lo=-0.15, v=v, obstacle_info=obs)
    dt = config.DT
    for i in range(1, mpc.N + 1):
        advance = v * i * dt
        in_window = obs.gap_near <= advance <= obs.gap_far + config.L
        assert active[i - 1] == in_window
        if in_window:
            assert y_lo_per_step[i - 1] == obs.y_hi + improved_config.MARGIN_I2
        else:
            assert y_lo_per_step[i - 1] == -0.15
        # wide 변형은 psi 하한을 건드리지 않음(고정 -80deg 그대로)
        assert psi_lo_per_step[i - 1] == -math.radians(config.PSI_LIMIT_DEG)


def test_i2_no_effect_when_obstacle_far_away():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=True, enable_i3=False)
    obs = FrontObstacleInfo(gap_near=10.0, gap_far=10.2, y_lo=-0.075, y_hi=0.075)
    y_lo_per_step, _, active = mpc._i2_bounds(base_lo=-0.15, v=0.5, obstacle_info=obs)
    assert all(v == -0.15 for v in y_lo_per_step)
    assert not any(active)


def test_i2_prime_narrow_variant_raises_psi_lower_bound_and_uses_smaller_margin():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=True, enable_i3=False,
                       i2_variant="narrow")
    obs = FrontObstacleInfo(gap_near=0.3, gap_far=0.5, y_lo=-0.075, y_hi=0.075)
    v = 0.5
    y_lo_per_step, psi_lo_per_step, active = mpc._i2_bounds(base_lo=-0.15, v=v, obstacle_info=obs)
    for i in range(1, mpc.N + 1):
        if active[i - 1]:
            assert y_lo_per_step[i - 1] == obs.y_hi + improved_config.MARGIN_I2_PRIME
            assert psi_lo_per_step[i - 1] == -math.radians(20.0)
        else:
            assert y_lo_per_step[i - 1] == -0.15
            assert psi_lo_per_step[i - 1] == -math.radians(config.PSI_LIMIT_DEG)
    assert improved_config.MARGIN_I2_PRIME < improved_config.MARGIN_I2


def test_i2_solve_pushes_higher_than_without_i2_when_obstacle_adjacent():
    """I2 단독은 하한을 더 좁혀 오히려 infeasible을 만들 수도 있음(설계상 예상된 위험,
    DESIGN_IMPROVED.md I2 부작용 위험 참고) -- 그래서 이 통합 테스트는 I1b(소프트 제약)와
    함께 켜서(ablation 조합 I1b+I2에 해당) feasibility를 보장한 채 방향성만 확인한다."""
    obs = FrontObstacleInfo(gap_near=0.05, gap_far=0.25, y_lo=-0.075, y_hi=0.075)
    mpc_off = ImprovedMPC(enable_i1=False, enable_i1b=True, enable_i2=False, enable_i3=False)
    mpc_on = ImprovedMPC(enable_i1=False, enable_i1b=True, enable_i2=True, enable_i3=False)
    kwargs = dict(y0=0.20, psi0_rad=0.0, v0=0.5, target_y=0.30, state_name="EVADE_L")
    r_off = mpc_off.solve(**kwargs, obstacle_info=obs)
    r_on = mpc_on.solve(**kwargs, obstacle_info=obs)
    assert r_off.ok and r_on.ok
    assert r_on.delta_deg > r_off.delta_deg  # 더 적극적으로(+y 쪽으로) 회피


# ---------- I3: 직전 성공 해 shift fallback ----------

def test_i3_uses_proportional_fallback_when_no_prior_solution():
    """직전 성공 해가 아예 없으면(첫 호출부터 실패) 기존 비례 fallback으로 폴백."""
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=True)
    r = mpc.solve(y0=_INFEASIBLE_Y, psi0_rad=math.radians(_INFEASIBLE_PSI_DEG), v0=_INFEASIBLE_V,
                  target_y=0.0, state_name="KEEP_L2")
    assert not r.ok
    assert r.fallback_used and not r.warm_start_shift_used
    expected = max(-config.DELTA_MAX_DEG, min(config.DELTA_MAX_DEG,
                   -config.K_P_FALLBACK * (_INFEASIBLE_Y - 0.0) * (180.0 / math.pi)))
    assert abs(r.delta_deg - expected) < 1e-6


def test_i3_shifts_previous_successful_solution_on_failure():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=True)
    r_ok = mpc.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.0, state_name="KEEP_L2")
    assert r_ok.ok
    prev_deltas = mpc._last_solution_deltas.copy()

    r_fail = mpc.solve(y0=_INFEASIBLE_Y, psi0_rad=math.radians(_INFEASIBLE_PSI_DEG),
                        v0=_INFEASIBLE_V, target_y=0.0, state_name="KEEP_L2")
    assert not r_fail.ok
    assert r_fail.fallback_used and r_fail.warm_start_shift_used
    expected_deg = prev_deltas[1] * (180.0 / math.pi)
    assert abs(r_fail.delta_deg - expected_deg) < 1e-9


def test_i3_off_never_sets_warm_start_shift_used():
    mpc = ImprovedMPC(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=False)
    mpc.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.0, state_name="KEEP_L2")
    r_fail = mpc.solve(y0=_INFEASIBLE_Y, psi0_rad=math.radians(_INFEASIBLE_PSI_DEG),
                        v0=_INFEASIBLE_V, target_y=0.0, state_name="KEEP_L2")
    assert not r_fail.ok
    assert r_fail.fallback_used and not r_fail.warm_start_shift_used
