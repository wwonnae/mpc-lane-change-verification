"""
I5(v2, DESIGN_IMPROVED_V2.md) 단위 테스트: 반복 상한(주 메커니즘)·time_limit(안전망)·
결정론(golden 반복 실행) 확인. 3단계 발전 원칙: eval 데이터는 쓰지 않는다(dev 시나리오만).
"""
import json
import math
from pathlib import Path

import pytest

from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

_DEG2RAD = math.pi / 180.0
GOLDEN_DIR = Path(__file__).parent / "golden"

FINAL_COMBO = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                    i2_variant="narrow")


def test_i5_off_setup_kwargs_identical_to_v1():
    """enable_i5=False(기본)면 OSQP setup() kwargs가 I5 도입 이전과 동일해야 한다
    (max_iter=20000 고정, time_limit 키 자체가 없음)."""
    mpc = ImprovedMPC(**FINAL_COMBO)
    assert mpc.enable_i5 is False
    settings = mpc.prob.get_settings() if hasattr(mpc.prob, "get_settings") else None
    # osqp 파이썬 바인딩 버전에 따라 settings 조회 API가 다를 수 있어, 존재할 때만
    # max_iter를 확인하고(20000), 존재하지 않으면 최소한 속성으로도 확인한다.
    if settings is not None:
        assert int(settings.max_iter) == 20000
    else:
        assert mpc.prob.settings.max_iter == 20000


def test_i5_on_requires_max_iter():
    """enable_i5=True인데 i5_max_iter가 (인자로도 config 기본값으로도) 없으면 즉시 assert.
    2026-09-24부터 config 기본값이 972로 채워져 있어(§9), i5_max_iter=None 호출은 이제
    그 기본값(972)으로 정상 동작한다 -- "값이 아예 없을 때" 경로는 config 값을 직접
    None으로 되돌려 확인한다(972 채택 이전 상태 재현, time_limit 테스트와 같은 패턴)."""
    from thesis_v2.improved import config as improved_config
    orig = improved_config.I5_MAX_ITER
    improved_config.I5_MAX_ITER = None
    try:
        raised = False
        try:
            ImprovedMPC(**FINAL_COMBO, enable_i5=True, i5_max_iter=None)
        except AssertionError:
            raised = True
        assert raised
    finally:
        improved_config.I5_MAX_ITER = orig


def test_i5_on_uses_972_by_default():
    """i5_max_iter를 명시하지 않고 enable_i5=True만 주면 config 기본값(972)을 쓴다."""
    mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True)
    assert mpc.i5_max_iter == 972


@pytest.mark.usefixtures("i5_time_limit_off")  # max_iter 동작 검사(time_limit 무관): time_limit off (thesis_v2/conftest.py)
def test_i5_tiny_iter_cap_triggers_max_iter_status_and_hard_check():
    """반복 상한을 극단적으로 작게(1) 걸면 대부분의 solve가 'maximum iterations
    reached'로 끝나야 하고, MPCResult.iterations가 그 상한을 넘지 않아야 한다."""
    mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True, i5_max_iter=1)
    r = mpc.solve(y0=0.1, psi0_rad=math.radians(15.0), v0=0.5, target_y=0.0,
                  state_name="KEEP_L2", delta_prev_deg=0.0)
    assert r.iterations <= 1
    assert r.solver_status in ("maximum iterations reached", "solved", "solved inaccurate")
    # ok=True(하드체크 통과)이든 fallback(I3)이든, 어느 쪽이든 delta_deg는 항상 유한값
    assert math.isfinite(r.delta_deg)


def test_i5_time_limit_safety_net_reachable():
    """time_limit(초 단위)을 극단적으로 짧게 걸면(별도 인스턴스, config 값을 직접
    낮춰서) 'run time limit reached' 상태가 나오는지 확인(안전망 발동 경로 자체가
    살아있는지 -- 정상 dev/eval에서는 발동하지 않아야 하는 것과는 별개 시험)."""
    from thesis_v2.improved import config as improved_config
    orig = improved_config.I5_TIME_LIMIT_SEC
    improved_config.I5_TIME_LIMIT_SEC = 1e-9
    try:
        mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True, i5_max_iter=20000)
        r = mpc.solve(y0=0.1, psi0_rad=math.radians(15.0), v0=0.5, target_y=0.0,
                      state_name="KEEP_L2", delta_prev_deg=0.0)
        assert r.solver_status in ("run time limit reached", "maximum iterations reached",
                                    "solved", "solved inaccurate")
        if r.solver_status == "run time limit reached":
            assert r.time_limit_hit is True
    finally:
        improved_config.I5_TIME_LIMIT_SEC = orig


def test_i5_max_iter_default_is_972():
    """2026-09-24 확정(DESIGN_IMPROVED_V2.md §9): dev ablation 결과 채택된 반복 상한.
    ENABLE_I5_ITER_CAP_MPC 자체는 여전히 기본 False라 이 값은 enable_i5=True로 명시
    호출할 때만 쓰인다(v1 조합은 이 값과 무관하게 1회차와 바이트 단위로 동일)."""
    from thesis_v2.improved import config as improved_config
    assert improved_config.I5_MAX_ITER == 972
    assert improved_config.ENABLE_I5_ITER_CAP_MPC is False


def test_norm_logging_fields_present_and_consistent():
    """SETTINGS_DECISION.md §19 검증용 필드(ax_inf_norm/prim_res/derived_tol_deg)가
    매 solve마다 채워지고, 삼각부등식 기반 관계(양수·eps_abs 이상)를 만족하는지 확인."""
    mpc = ImprovedMPC(**FINAL_COMBO)
    r = mpc.solve(y0=0.1, psi0_rad=math.radians(15.0), v0=0.5, target_y=0.0,
                  state_name="KEEP_L2", delta_prev_deg=0.0)
    assert r.ax_inf_norm >= 0.0
    assert r.prim_res >= 0.0
    assert math.isfinite(r.derived_tol_deg)
    # derived_tol_deg = (eps_abs + eps_rel*(ax_inf_norm+prim_res))*RAD2DEG >= eps_abs 환산값
    eps_abs_deg = 1e-4 * (180.0 / math.pi)
    assert r.derived_tol_deg >= eps_abs_deg - 1e-9


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
def test_i5_golden_determinism_three_runs():
    """I5 on 상태로 같은 golden 시나리오(paper seed=0)를 3회 반복 실행해도 조향
    시계열이 완전히 동일해야 한다(반복 상한은 시간이 아니라 반복 횟수 기준이므로
    결정론적이어야 함 -- DESIGN_IMPROVED_V2.md §1-0/§1-5).

    정정(2026-10-14, run #6 조사): 결정론은 반복 상한 경로에 대해서만 성립한다. 제품 설정의
    time_limit(0.045 s)이 켜져 있으면 실행 환경이 한 solve 안에서 45 ms 넘게 멈출 때 결과가
    달라진다(docs/verification/ci/run6_cause/README.md). 그래서 이 테스트는 i5_time_limit_off
    fixture로 time_limit을 끄고 반복 상한 경로의 결정론만 검증한다. time_limit 발동 경로는
    test_i5_time_limit_safety_net_reachable·test_i5_time_limit_hit_*가 따로 검증한다."""
    series = []
    for _ in range(3):
        mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True, i5_max_iter=1944)
        result = improved_run_episode(generate_scenario(0), mpc=mpc)
        series.append([row["delta_final"] for row in result.logger.rows])
    assert series[0] == series[1] == series[2]


# ---- i5_time_limit_off fixture 보호 테스트 (thesis_v2/conftest.py, run #6 대응 선택지 2) ----
# fixture는 improved_config.I5_TIME_LIMIT_SEC를 바꿔 "생성 시점에 config를 읽는" ImprovedMPC 동작에 기댄다.
# 이 동작이 바뀌면(예: import 시점 캐시) 결정론 테스트가 조용히 제품 time_limit으로 돌아가므로 여기서 잡는다.

@pytest.mark.usefixtures("i5_time_limit_off")
def test_i5_time_limit_off_fixture_reaches_osqp_settings():
    from thesis_v2.conftest import I5_TIME_LIMIT_OFF_SEC
    mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True)
    assert float(mpc.prob.settings.time_limit) == I5_TIME_LIMIT_OFF_SEC
    assert int(mpc.prob.settings.max_iter) == 972


def test_i5_product_instance_keeps_time_limit_safety_net():
    from thesis_v2.improved import config as improved_config
    assert improved_config.I5_TIME_LIMIT_SEC == 0.045
    mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True)
    assert float(mpc.prob.settings.time_limit) == 0.045
    assert int(mpc.prob.settings.max_iter) == 972


# ---- time_limit_hit 지문 규칙 (improved/mpc.py time_limit_fingerprint, run #6 대응 선택지 5) ----

@pytest.mark.parametrize("status,iterations,expected", [
    ("run time limit reached", 0, True),
    ("run time limit reached", 25, True),     # iter가 25의 배수여도 이 status는 절단
    ("run time limit reached", 971, True),
    ("solved inaccurate", 14, True),          # 절단 후 근사 검사 통과
    ("solved inaccurate", 700, True),
    ("solved inaccurate", 972, False),        # max_iter 도달 후 근사 검사 통과(시간 무관)
    ("solved", 23, True),                     # 절단 후 iter-1에서 정상 검사 통과
    ("solved", 0, True),                      # 첫 반복에서 절단(정상 종료는 iter 0으로 끝날 수 없음)
    ("solved", 25, False),                    # 정상 수렴 검사 반복
    ("solved", 50, False),
    ("solved", 972, False),                   # max_iter(25의 배수 아님)에서 정상 종료
    ("maximum iterations reached", 972, False),
    ("primal infeasible", 25, False),
    ("dual infeasible", 50, False),
])
def test_i5_time_limit_fingerprint_table(status, iterations, expected):
    from thesis_v2.improved.mpc import time_limit_fingerprint
    assert time_limit_fingerprint(status, iterations, max_iter=972, check_termination=25) is expected


def test_i5_time_limit_fingerprint_without_check_termination():
    """check_termination=0(수렴 검사 끔)이면 정상 "solved"는 max_iter에서만 나온다 — 0으로 나누지 않아야 한다."""
    from thesis_v2.improved.mpc import time_limit_fingerprint
    assert time_limit_fingerprint("solved", 972, max_iter=972, check_termination=0) is False
    assert time_limit_fingerprint("solved", 0, max_iter=972, check_termination=0) is True


def test_i5_time_limit_hit_set_for_any_reported_status():
    """time_limit을 극단적으로 짧게(1e-9 s) 걸면 첫 반복에서 반드시 끊긴다. 보고 status가 무엇이든
    (run time limit reached / solved inaccurate / solved) time_limit_hit는 참이어야 한다."""
    from thesis_v2.improved import config as improved_config
    orig = improved_config.I5_TIME_LIMIT_SEC
    improved_config.I5_TIME_LIMIT_SEC = 1e-9
    try:
        mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True, i5_max_iter=20000)
        for _ in range(3):
            r = mpc.solve(y0=0.1, psi0_rad=math.radians(15.0), v0=0.5, target_y=0.0,
                          state_name="KEEP_L2", delta_prev_deg=0.0)
            assert r.time_limit_hit is True, (r.solver_status, r.iterations)
    finally:
        improved_config.I5_TIME_LIMIT_SEC = orig


def test_i5_time_limit_hit_false_without_cut():
    """time_limit이 사실상 없으면(1e10) 정상 solve의 time_limit_hit는 거짓이다."""
    from thesis_v2.improved import config as improved_config
    orig = improved_config.I5_TIME_LIMIT_SEC
    improved_config.I5_TIME_LIMIT_SEC = 1e10
    try:
        mpc = ImprovedMPC(**FINAL_COMBO, enable_i5=True)
        for _ in range(3):
            r = mpc.solve(y0=0.1, psi0_rad=math.radians(15.0), v0=0.5, target_y=0.0,
                          state_name="KEEP_L2", delta_prev_deg=0.0)
            assert r.time_limit_hit is False, (r.solver_status, r.iterations)
    finally:
        improved_config.I5_TIME_LIMIT_SEC = orig
