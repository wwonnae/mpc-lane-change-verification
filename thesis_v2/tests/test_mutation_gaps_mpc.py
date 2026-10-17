"""baseline MPC 테스트 보강 — mutation testing 1차 생존 변이 중 테스트 공백·명백한 공백(docs/verification/mutation/equivalence.json).

이 파일의 테스트는 LLM(Claude Code)이 제안했다. 수락 기준과 검토 기록은 docs/verification/mutation/RESULTS.md,
llm_tests_log.json에 있다(PREREGISTRATION.md §8).

- 계산 시간: MEASURE_PLAN.md "MPC 계산시간 — time.perf_counter()로 solve() 앞뒤 측정"(REQ-EVAL-03). 시계를 가짜로 바꿔
  정확한 값을 확인한다(실제 시간에 의존하지 않음).
- ψ 제약: golden 시나리오에서는 활성되지 않는다(RESULTS.md 발견 사항 2). 제약이 실제로 걸리는 입력을 만든다.
- QP 구조: SPEC 식(REQ-MPC-01~04)을 이 파일 안에서 따로 구현해(밀집 행렬 + scipy SLSQP) δ_0을 비교한다. thesis_v2.baseline.mpc의
  행렬을 읽지 않는다.
"""
import math
import types

import numpy as np
import pytest
from scipy.optimize import minimize

from thesis_v2.baseline import config
from thesis_v2.baseline import mpc as mpc_mod
from thesis_v2.baseline.mpc import OSQPMPC


class _FakeClock:
    """perf_counter 대용: 부를 때마다 정해진 값을 차례로 돌려준다."""

    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def perf_counter(self):
        v = self.values[self.calls]
        self.calls += 1
        return v


@pytest.mark.parametrize("path", ["solved", "fallback"])
def test_compute_time_ms_is_elapsed_perf_counter_in_milliseconds(monkeypatch, path):
    """REQ-EVAL-03(계산시간 지표), MEASURE_PLAN.md MPC 계산시간 정의: compute_time_ms = solve() 앞뒤 perf_counter 차이 × 1000.
    성공 경로와 fallback 경로(REQ-MPC-07) 모두 같은 정의를 따른다."""
    clock = _FakeClock([100.0, 100.0125])
    monkeypatch.setattr(mpc_mod, "time", types.SimpleNamespace(perf_counter=clock.perf_counter))
    m = OSQPMPC()
    if path == "solved":
        res = m.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.0, state_name="KEEP_L2")
        assert res.ok
    else:
        # KEEP_L2 위치제약(|y| ≤ 0.15) 밖에서 y_1이 고정되는 입력 → infeasible → fallback
        res = m.solve(y0=0.45, psi0_rad=0.0, v0=0.4, target_y=0.0, state_name="KEEP_L2")
        assert res.fallback_used
    assert clock.calls == 2
    assert res.compute_time_ms == pytest.approx((100.0125 - 100.0) * 1000.0, rel=1e-9)


def test_heading_constraint_binds_when_optimum_would_exceed_limit():
    """REQ-MPC-04: 헤딩 제약 −80° ≤ ψ_i ≤ 80°. ψ0 = 79°에서 먼 좌측 목표를 주면 비용은 ψ를 더 키우려 하지만,
    예측 ψ_1 = ψ0 + (v/L)·dt·δ_0(REQ-MPC-01)은 80°를 넘으면 안 된다. 허용오차는 OSQP eps(1e-4, config) 수준."""
    psi0 = math.radians(79.0)
    v = 0.5
    res = OSQPMPC().solve(y0=-0.15, psi0_rad=psi0, v0=v, target_y=5.0, state_name="EVADE_L")
    assert res.ok
    psi1 = psi0 + (v / config.L) * config.DT * math.radians(res.delta_deg)
    assert psi1 <= math.radians(config.PSI_LIMIT_DEG) + 1e-3
    assert res.delta_deg < config.DELTA_MAX_DEG - 1.0  # 전제: δ 상한이 아니라 ψ 제약이 δ_0을 막고 있다


def _reference_delta0_deg(y0, psi0, v, target, state):
    """SPEC REQ-MPC-01~04 QP의 독립 구현. 결정변수 δ_0..δ_{N−1}, 상태는 REQ-MPC-01 식으로 전개."""
    N, dt, L = config.N, config.DT, config.L

    def roll(d):
        y, p, ys, ps = y0, psi0, [], []
        for k in range(N):
            y = y + v * dt * p
            p = p + (v / L) * dt * d[k]
            ys.append(y)
            ps.append(p)
        return np.array(ys), np.array(ps)

    def cost(d):
        ys, ps = roll(d)
        return (config.QY * np.sum((ys - target) ** 2) + config.QPSI * np.sum(ps ** 2)
                + config.RDELTA * d[0] ** 2 + config.RDDELTA * np.sum(np.diff(d) ** 2))

    lo, hi = config.POSITION_CONSTRAINTS[state]
    plim, dlim = math.radians(config.PSI_LIMIT_DEG), math.radians(config.DELTA_MAX_DEG)
    cons = [dict(type="ineq", fun=lambda d: roll(d)[0] - lo), dict(type="ineq", fun=lambda d: hi - roll(d)[0]),
            dict(type="ineq", fun=lambda d: plim - roll(d)[1]), dict(type="ineq", fun=lambda d: roll(d)[1] + plim)]
    r = minimize(cost, np.zeros(N), method="SLSQP", bounds=[(-dlim, dlim)] * N, constraints=cons,
                 options=dict(ftol=1e-14, maxiter=2000))
    assert r.success
    return math.degrees(r.x[0])


@pytest.mark.filterwarnings("ignore:Values in x were outside bounds")  # SLSQP 내부 클리핑 알림(결과 무관)
@pytest.mark.parametrize("y0,v0,target,state", [
    (0.4, 0.05, 0.0, "KEEP_L1"),
    (0.4, 0.05, 0.3, "KEEP_L1"),
    (0.3, 0.05, 0.3, "KEEP_L1"),
    (0.4, 0.1, 0.0, "EVADE_L"),
    (0.1, 0.05, 0.3, "KEEP_L2"),
    (0.0, 0.3, 0.3, "EVADE_L"),
    (0.3, 0.5, 0.0, "EVADE_L"),
])
def test_delta0_matches_independent_spec_qp(y0, v0, target, state):
    """REQ-MPC-01~04·06: solve()의 δ_0은 SPEC의 모델·비용·제약으로 정의한 QP의 최적해 δ_0과 같다(독립 구현과 비교).
    허용오차 0.05°: OSQP(eps 1e-4, polishing 끔, config) 해와 독립 해의 차이는 64개 입력에서 최대 0.0067°였다(2026-10-13 측정).
    저속(v0 = 0.05 m/s)에서는 예측 구간 끝의 동역학이 δ_0에 더 크게 드러난다."""
    res = OSQPMPC().solve(y0=y0, psi0_rad=0.0, v0=v0, target_y=target, state_name=state)
    assert res.ok
    assert res.delta_deg == pytest.approx(_reference_delta0_deg(y0, 0.0, v0, target, state), abs=0.05)
