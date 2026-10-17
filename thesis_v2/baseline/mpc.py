"""
OSQP 기반 2-state(y,psi) MPC + fallback. 논문 제출 이후 작성.
REQ-MPC-01~08, REQ-MPC-03a(rdelta/rddelta 항 구분), REQ-MPC-04/05(상태별 위치제약),
REQ-MPC-07/07a/07b(fallback, 단위 rad/m, 부호규약).

z = [y_1,psi_1, y_2,psi_2, ..., y_N,psi_N, delta_0, delta_1, ..., delta_{N-1}]
(REQ-MPC-06의 z를 상태블록+제어블록으로 재정렬한 것 — 변수의 의미·개수는 동일, 구현 편의상 순서만 다름)

시간 t=0.05초, N=15 -> 변수 3N=45개.
행(A): 동역학 등식 2N개(y N개+psi N개) + y 위치제약 N개 + psi 제약 N개 + delta 제약 N개 = 5N=75개.

P(Hessian)는 v/타깃과 무관한 상수 -> 최초 1회만 구성. A의 sparsity도 고정.
매 solve()마다 update()로 갱신하는 것: q(타깃 y_ref), l/u(동역학 초기조건 2개 행 + y위치제약
N개 행), A의 v-의존 항목(동역학 등식의 -v*dt, -(v/L)*dt 계수, Ax로 갱신).
"""
import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import scipy.sparse as sp
import osqp

from . import config

_DEG2RAD = math.pi / 180.0
_RAD2DEG = 180.0 / math.pi


@dataclass
class MPCResult:
    delta_deg: float
    solver_status: str
    ok: bool
    fallback_used: bool
    compute_time_ms: float


def _idx_y(i: int) -> int:
    """i=1..N -> 0-based 변수 인덱스."""
    return 2 * (i - 1)


def _idx_psi(i: int) -> int:
    return 2 * (i - 1) + 1


def _idx_delta(k: int) -> int:
    """k=0..N-1."""
    return 2 * config.N + k


class OSQPMPC:
    def __init__(self):
        N = config.N
        self.N = N
        self.n_vars = 3 * N
        self.n_eq = 2 * N
        self.n_ineq = 3 * N
        self.n_rows = self.n_eq + self.n_ineq

        self._build_P()
        self._build_A_template()

        self.prob = osqp.OSQP()
        self.prob.setup(
            P=self.P, q=np.zeros(self.n_vars),
            A=self.A, l=self.l, u=self.u,
            verbose=config.OSQP_VERBOSE, warm_starting=config.OSQP_WARM_STARTING,
            polishing=config.OSQP_POLISHING,
            eps_abs=config.OSQP_EPS_ABS, eps_rel=config.OSQP_EPS_REL,
            max_iter=config.OSQP_MAX_ITER,
        )
        self._fail_count = 0

    # ---------------- construction ----------------

    def _build_P(self):
        """REQ-MPC-02/03a: qy,qpsi는 대각, rdelta/rddelta는 delta 블록에 차분항(비대각) 포함."""
        N = self.N
        rows, cols, vals = [], [], []
        for i in range(1, N + 1):
            rows.append(_idx_y(i)); cols.append(_idx_y(i)); vals.append(2 * config.QY)
            rows.append(_idx_psi(i)); cols.append(_idx_psi(i)); vals.append(2 * config.QPSI)

        # delta_0^2 * rdelta + sum_{i=1}^{N-1} rddelta*(delta_i-delta_{i-1})^2
        diag = np.zeros(N)
        diag[0] += config.RDELTA
        for i in range(1, N):
            diag[i] += config.RDDELTA
            diag[i - 1] += config.RDDELTA
        for k in range(N):
            rows.append(_idx_delta(k)); cols.append(_idx_delta(k)); vals.append(2 * diag[k])
        for i in range(1, N):
            c = -2 * config.RDDELTA
            rows.append(_idx_delta(i)); cols.append(_idx_delta(i - 1)); vals.append(c)
            rows.append(_idx_delta(i - 1)); cols.append(_idx_delta(i)); vals.append(c)

        full = sp.coo_matrix((vals, (rows, cols)), shape=(self.n_vars, self.n_vars)).tocsc()
        self.P = sp.triu(full, format="csc")

    def _build_A_template(self):
        """A 구조(sparsity) 1회 구성. v-의존 항목의 (row,col)을 기록해뒀다가 매 solve에서 갱신."""
        N = self.N
        rows, cols, vals = [], [], []
        self._v_entries = []  # list of (row_idx_in_A, col, kind) kind in {"y","psi"} for -v*dt / -(v/L)*dt

        r = 0
        # --- 동역학 등식: i=1 ---
        # y_1 = y0 + v*dt*psi0  (계수: y_1=1, RHS는 l,u로) -- v 의존 계수 없음(RHS만 v의존)
        rows.append(r); cols.append(_idx_y(1)); vals.append(1.0)
        self._row_y1 = r
        r += 1
        # psi_1 - (v/L)*dt*delta_0 = psi0
        rows.append(r); cols.append(_idx_psi(1)); vals.append(1.0)
        c_idx = len(rows)
        rows.append(r); cols.append(_idx_delta(0)); vals.append(0.0)  # placeholder, v-dependent
        self._v_entries.append((len(vals) - 1, "psi_delta"))
        self._row_psi1 = r
        r += 1

        # --- i=2..N ---
        self._row_dyn0 = r  # 이 시점부터 l=u=0 로 고정되는 행들의 시작
        for i in range(2, N + 1):
            # y_i - y_{i-1} - v*dt*psi_{i-1} = 0
            rows.append(r); cols.append(_idx_y(i)); vals.append(1.0)
            rows.append(r); cols.append(_idx_y(i - 1)); vals.append(-1.0)
            rows.append(r); cols.append(_idx_psi(i - 1)); vals.append(0.0)
            self._v_entries.append((len(vals) - 1, "y_psi"))
            r += 1
            # psi_i - psi_{i-1} - (v/L)*dt*delta_{i-1} = 0
            rows.append(r); cols.append(_idx_psi(i)); vals.append(1.0)
            rows.append(r); cols.append(_idx_psi(i - 1)); vals.append(-1.0)
            rows.append(r); cols.append(_idx_delta(i - 1)); vals.append(0.0)
            self._v_entries.append((len(vals) - 1, "psi_delta"))
            r += 1

        assert r == self.n_eq

        # --- 부등식: y_i 위치제약 (상태별로 l,u만 바뀜) ---
        self._row_ybound0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(_idx_y(i)); vals.append(1.0)
            r += 1

        # --- 부등식: psi_i 제약 (고정, REQ-MPC-04) ---
        for i in range(1, N + 1):
            rows.append(r); cols.append(_idx_psi(i)); vals.append(1.0)
            r += 1

        # --- 부등식: delta_k 제약 (고정, REQ-MPC-04) ---
        for k in range(N):
            rows.append(r); cols.append(_idx_delta(k)); vals.append(1.0)
            r += 1

        assert r == self.n_rows

        self.A = sp.csc_matrix((vals, (rows, cols)), shape=(self.n_rows, self.n_vars))
        # v-의존 항목의 CSC data 배열 내 위치를 찾기 위해 COO->CSC 변환 후 인덱스 매핑이 필요.
        # 간단화를 위해 COO 순서대로 다시 CSC를 만들고, tocsc()가 중복 없는 좌표라 순서를 보존한다고
        # 가정하지 않고, 각 v-의존 (row,col) 쌍의 CSC 내 데이터 인덱스를 명시적으로 찾는다.
        coo = sp.coo_matrix((vals, (rows, cols)), shape=(self.n_rows, self.n_vars))
        self._A_coo_rows = np.array(rows)
        self._A_coo_cols = np.array(cols)
        csc = coo.tocsc()
        self.A = csc
        # (row,col) -> data index in csc.data, using indptr/indices
        self._rc_to_dataidx = {}
        for col in range(self.n_vars):
            start, end = csc.indptr[col], csc.indptr[col + 1]
            for k in range(start, end):
                self._rc_to_dataidx[(csc.indices[k], col)] = k

        self.l = np.full(self.n_rows, -np.inf)
        self.u = np.full(self.n_rows, np.inf)
        # dynamics rows i=2..N: l=u=0 (fixed forever)
        for i in range(2, self.N + 1):
            row_y = self._row_dyn0 + 2 * (i - 2)
            row_psi = row_y + 1
            self.l[row_y] = self.u[row_y] = 0.0
            self.l[row_psi] = self.u[row_psi] = 0.0
        # psi bound rows (fixed)
        psi_lo = -config.PSI_LIMIT_DEG * _DEG2RAD
        psi_hi = config.PSI_LIMIT_DEG * _DEG2RAD
        for i in range(1, self.N + 1):
            row = self._row_ybound0 + self.N + (i - 1)
            self.l[row], self.u[row] = psi_lo, psi_hi
        # delta bound rows (fixed)
        d_lo = -config.DELTA_MAX_DEG * _DEG2RAD
        d_hi = config.DELTA_MAX_DEG * _DEG2RAD
        for k in range(self.N):
            row = self._row_ybound0 + 2 * self.N + k
            self.l[row], self.u[row] = d_lo, d_hi
        # row_y1,row_psi1, y-bound rows: set later per-solve (l=u placeholder for now)
        self.l[self._row_y1] = self.u[self._row_y1] = 0.0
        self.l[self._row_psi1] = self.u[self._row_psi1] = 0.0
        for i in range(1, self.N + 1):
            row = self._row_ybound0 + (i - 1)
            self.l[row], self.u[row] = -np.inf, np.inf

    # ---------------- solve ----------------

    def solve(self, y0: float, psi0_rad: float, v0: float, target_y: float,
              state_name: str) -> MPCResult:
        t_start = time.perf_counter()
        N = self.N
        v = max(0.05, min(config.V_MAX, abs(v0)))  # 수치안정: 0 근처 방지

        # --- A의 v-의존 항목 갱신 (Ax) ---
        Ax_idx = []
        Ax_val = []
        vi = 0
        # i=1: psi_1 항의 delta_0 계수 = -(v/L)*dt
        row, col = self._row_psi1, _idx_delta(0)
        Ax_idx.append(self._rc_to_dataidx[(row, col)])
        Ax_val.append(-(v / config.L) * config.DT)
        # i=2..N
        for i in range(2, N + 1):
            row_y = self._row_dyn0 + 2 * (i - 2)
            row_psi = row_y + 1
            Ax_idx.append(self._rc_to_dataidx[(row_y, _idx_psi(i - 1))])
            Ax_val.append(-v * config.DT)
            Ax_idx.append(self._rc_to_dataidx[(row_psi, _idx_delta(i - 1))])
            Ax_val.append(-(v / config.L) * config.DT)

        # --- l,u 갱신: 초기조건(row_y1,row_psi1) + y 위치제약 ---
        l = self.l.copy()
        u = self.u.copy()
        y1_val = y0 + v * config.DT * psi0_rad
        l[self._row_y1] = u[self._row_y1] = y1_val
        l[self._row_psi1] = u[self._row_psi1] = psi0_rad
        lo, hi = config.POSITION_CONSTRAINTS[state_name]
        for i in range(1, N + 1):
            row = self._row_ybound0 + (i - 1)
            l[row], u[row] = lo, hi

        # --- q 갱신: y_i 타깃 선형항 ---
        q = np.zeros(self.n_vars)
        for i in range(1, N + 1):
            q[_idx_y(i)] = -2.0 * config.QY * target_y

        self.prob.update(q=q, l=l, u=u,
                          Ax=np.array(Ax_val), Ax_idx=np.array(Ax_idx, dtype=np.int64))

        res = self.prob.solve(raise_error=config.OSQP_RAISE_ERROR)
        status = res.info.status
        ok = status in ("solved", "solved inaccurate")

        if ok:
            delta0_rad = res.x[_idx_delta(0)]
            delta_deg = float(delta0_rad * _RAD2DEG)
            compute_ms = (time.perf_counter() - t_start) * 1000.0
            return MPCResult(delta_deg=delta_deg, solver_status=status, ok=True,
                              fallback_used=False, compute_time_ms=compute_ms)

        # --- REQ-MPC-07/07a: fallback, K_p=1.0 rad/m ---
        self._fail_count += 1
        delta_fallback_rad = -config.K_P_FALLBACK * (y0 - target_y)
        delta_fallback_deg = delta_fallback_rad * _RAD2DEG
        delta_fallback_deg = max(-config.DELTA_MAX_DEG, min(config.DELTA_MAX_DEG, delta_fallback_deg))
        compute_ms = (time.perf_counter() - t_start) * 1000.0
        return MPCResult(delta_deg=float(delta_fallback_deg), solver_status=status, ok=False,
                          fallback_used=True, compute_time_ms=compute_ms)
