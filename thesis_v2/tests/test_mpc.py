import math
from unittest.mock import patch

import numpy as np
import pytest

from thesis_v2.baseline import config
from thesis_v2.baseline.mpc import OSQPMPC, _idx_delta, _idx_psi, _idx_y

_DEG2RAD = math.pi / 180.0


@pytest.fixture(scope="module")
def mpc():
    return OSQPMPC()


def test_hessian_has_offdiagonal_rddelta_terms(mpc):
    """REQ-MPC-03a: rddelta는 (delta_i,delta_{i-1}) 차분항 -> Hessian 비대각 성분 존재."""
    full = (mpc.P + mpc.P.T).toarray()
    N = config.N
    found_offdiag = False
    for i in range(1, N):
        row, col = _idx_delta(i), _idx_delta(i - 1)
        val = full[row, col]
        assert val == pytest.approx(-2 * config.RDDELTA)
        if val != 0:
            found_offdiag = True
    assert found_offdiag


@pytest.mark.parametrize("state_name", ["KEEP_L2", "KEEP_L1", "EVADE_L", "RETURN_TO_L2"])
def test_position_constraints_per_state(mpc, state_name):
    """REQ-MPC-05: 상태별 y 위치제약이 prob.update()에 전달되는 l,u에 정확히 반영."""
    captured = {}
    orig_update = mpc.prob.update

    def spy_update(**kwargs):
        captured.update(kwargs)
        return orig_update(**kwargs)

    with patch.object(mpc.prob, "update", side_effect=spy_update):
        mpc.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.0, state_name=state_name)

    lo, hi = config.POSITION_CONSTRAINTS[state_name]
    N = config.N
    for i in range(1, N + 1):
        row = mpc._row_ybound0 + (i - 1)
        assert captured["l"][row] == pytest.approx(lo)
        assert captured["u"][row] == pytest.approx(hi)


def test_heading_and_steering_bound_constants(mpc):
    """REQ-MPC-04: psi 제약 ±80deg, delta 제약 ±25deg (고정, 상태 무관)."""
    N = config.N
    psi_lo = -config.PSI_LIMIT_DEG * _DEG2RAD
    psi_hi = config.PSI_LIMIT_DEG * _DEG2RAD
    for i in range(1, N + 1):
        row = mpc._row_ybound0 + N + (i - 1)
        assert mpc.l[row] == pytest.approx(psi_lo)
        assert mpc.u[row] == pytest.approx(psi_hi)
    d_lo = -config.DELTA_MAX_DEG * _DEG2RAD
    d_hi = config.DELTA_MAX_DEG * _DEG2RAD
    for k in range(N):
        row = mpc._row_ybound0 + 2 * N + k
        assert mpc.l[row] == pytest.approx(d_lo)
        assert mpc.u[row] == pytest.approx(d_hi)


def test_sign_convention_steers_toward_positive_target(mpc):
    """+y=좌측, +delta=좌회전 -> target_y>y0 이면 delta>0 이어야 한다 (REQ-MPC-07b)."""
    res = mpc.solve(y0=0.0, psi0_rad=0.0, v0=0.4, target_y=0.3, state_name="EVADE_L")
    assert res.ok
    assert res.delta_deg > 0


def test_sign_convention_steers_toward_negative_target(mpc):
    res = mpc.solve(y0=0.3, psi0_rad=0.0, v0=0.4, target_y=0.0, state_name="EVADE_L")
    assert res.ok
    assert res.delta_deg < 0


def test_fallback_unit_is_rad_per_meter(mpc):
    """REQ-MPC-07/07a: solver 실패 시 fallback = -K_p*(y0-target_y), K_p=1.0 rad/m."""
    class FakeInfo:
        status = "primal infeasible"

    class FakeRes:
        info = FakeInfo()
        x = np.zeros(mpc.n_vars)

    with patch.object(mpc.prob, "solve", return_value=FakeRes()):
        result = mpc.solve(y0=0.1, psi0_rad=0.0, v0=0.4, target_y=0.4, state_name="EVADE_L")

    assert result.fallback_used is True
    assert result.ok is False
    expected_rad = -config.K_P_FALLBACK * (0.1 - 0.4)
    expected_deg = expected_rad * (180.0 / math.pi)
    assert result.delta_deg == pytest.approx(expected_deg)
