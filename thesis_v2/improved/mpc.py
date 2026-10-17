"""
개선판 OSQP MPC. DESIGN_IMPROVED.md I1/I1b/I2/I3 참고. baseline `mpc.py`를 건드리지
않고 새로 작성(구조는 baseline과 같은 동역학·비용함수를 그대로 쓰되, 아래 3가지를
확장한다):

- I1(하드, `ENABLE_I1_RATE_AWARE_MPC`): delta_prev 인지 + rate limit(10deg/step) 하드
  제약 2종류 추가.
- I1b(소프트, `ENABLE_I1B_SOFT_CONSTRAINTS`): y_i, psi_i 위치제약을 슬랙 변수 +
  ell-1 벌점(SOFT_CONSTRAINT_PENALTY)으로 소프트화. 조향각(delta)·rate limit은 항상
  하드.
- I2(`ENABLE_I2_OBSTACLE_AWARE_MPC`): 장애물이 예측 구간 안에 있을 때 그 step의 y
  하한을 장애물 우측 경계 + MARGIN_I2로 올림.
- I3(`ENABLE_I3_WARM_START_FALLBACK`): QP 실패 시 직전 성공 해를 한 칸 shift해 재사용
  (없으면 baseline과 같은 비례 fallback).
- I5(`ENABLE_I5_ITER_CAP_MPC`, DESIGN_IMPROVED_V2.md): 반복 상한(`max_iter`)을 주
  메커니즘으로 낮추고 `time_limit`은 안전망으로 둔다. 반복 상한 경로는 warm-start·문제
  데이터가 같으면 항상 같은 반복에서 멈춘다(결정론). "maximum iterations reached"/"run
  time limit reached" 모두 I3와 동일한 하드 제약 재확인 분기로 처리한다.
  정정(2026-10-14, run #6 조사 docs/verification/ci/run6_cause/): time_limit은 벽시계
  기준이라, 실행 환경이 한 solve 안에서 45 ms 넘게 멈추면 발동해 같은 입력의 결과를
  바꾼다(결정론은 time_limit 미발동일 때만 성립). 또 시간으로 끊긴 solve는 "run time
  limit reached"만이 아니라 "solved inaccurate"/"solved"로도 보고되므로, 발동 여부
  (`time_limit_hit`)는 status 문자열이 아니라 `time_limit_fingerprint`(status+반복 수)로
  판정한다. 이 판정은 기록용이며 제어 분기는 지금처럼 status로만 갈린다.

플래그가 전부 False이면 구조상 baseline의 하드 제약 QP와 수학적으로 동일한 문제가
된다(슬랙 상한 0, rate 행 비활성) -- Stage 0 동치성 테스트로 확인한다.

변수 순서: z = [y_1,psi_1,...,y_N,psi_N, delta_0,...,delta_{N-1},
                s_y_1,...,s_y_N, s_psi_1,...,s_psi_N]
"""
import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import scipy.sparse as sp
import osqp

from thesis_v2.baseline import config as base_config
from . import config as improved_config
from .sensors import FrontObstacleInfo

_DEG2RAD = math.pi / 180.0
_RAD2DEG = 180.0 / math.pi

# I1b(슬랙+ell-1 벌점, rho=10000)는 baseline의 하드 제약 QP보다 문제가 커지고
# 조건도 나빠져(rho가 다른 계수보다 훨씬 큼) 기본 max_iter(4000, base_config와 동일)로는
# 수렴하지 못하는 경우를 확인했다(S6 seed=6류 어려운 사례, 8000에서는 수렴, 4000은
# "maximum iterations reached"). 정상 입력에서는 warm-start로 반복이 훨씬 적게 걸리므로
# (실측 평균 0.18ms/call) 계산시간 예산(50ms)에 영향 없이 여유 있게 20000으로 올린다.
_MAX_ITER = 20000

# 2026-09-23 검토(0번): I1+I1b+I2' dev 재실행에서 raw MPC 출력(delta_0)이 |delta|<=25deg를
# eps_abs(1e-4 rad~0.0057deg) 허용오차보다 크게(최대 0.0073deg) 벗어나는 사례를 발견.
# 원인 진단: 전부 solver_status="solved"(maximum iterations reached 아님) -- OSQP의
# 종료 판정은 "abs+rel" 결합 기준(||r|| <= eps_abs + eps_rel*max(||Ax||,||z||))을 쓰는데,
# I1b의 슬랙 변수가 상한 +inf라 한 번의 solve 안에서 다른 행(y/psi 슬랙)의 값이 커지면
# max(||Ax||,||z||)가 커져, delta 경계처럼 무관한 행의 "실질 허용오차"까지 eps_rel 항을
# 통해 함께 느슨해짐(이 solve 자체는 baseline과 같은 eps_abs=eps_rel=1e-4를 그대로 썼음).
# 해결: eps_rel만 10배 타이트하게(1e-5) 낮춤(eps_abs는 baseline과 동일하게 유지) --
# dev 재실행 결과 위반 0건(eps_rel=1e-4: 4~5건, 1e-6/1e-8도 0건이지만 최악 계산시간이
# 59ms로 20Hz 예산(50ms) 초과 -- 1e-5가 위반 0·최대 계산시간 42ms로 예산 안쪽인 최적점).
_EPS_REL = 1e-5


def time_limit_fingerprint(status: str, iterations: int, max_iter: int, check_termination: int) -> bool:
    """OSQP time_limit으로 끊긴 solve인지 status와 반복 수로 판정한다(기록용, 제어 로직 아님).

    근거: OSQP C v1.0.0 `src/osqp_api.c` -- 시간 검사는 매 반복의 ADMM 단계 직후, 수렴 검사보다
    먼저 한다(:741-757). 정상 종료는 수렴 검사 반복(iter % check_termination == 0, iter >= 1)이나
    max_iter에서만 일어난다(:764-765, :860-865, :907-931). 따라서 아래는 절단에서만 나온다
    (docs/verification/ci/run6_cause/STATIC_ANALYSIS.md §3-3과 정정, raw/S6_fingerprint_check/).
    - "run time limit reached": 근사 검사(:960-965)도 통과하지 못한 절단
    - "solved inaccurate"이고 iter < max_iter: 절단 후 근사 검사(eps×10) 통과
    - "solved"이고 iter가 check_termination의 배수가 아니며 max_iter도 아님: 절단 후 iter-1에서
      정상 eps 검사 통과(:908-931)
    - "solved"이고 iter == 0: 첫 반복에서 끊긴 뒤 update_info(0) 검사 통과(정상 종료는 iter 0으로
      "solved"를 낼 수 없다)
    """
    if status == "run time limit reached":
        return True
    if status == "solved inaccurate" and iterations < max_iter:
        return True
    if status == "solved" and iterations != max_iter and (
            iterations == 0 or (check_termination and iterations % check_termination != 0)):
        return True
    return False


@dataclass
class MPCResult:
    delta_deg: float
    solver_status: str
    ok: bool
    fallback_used: bool
    warm_start_shift_used: bool
    compute_time_ms: float
    approx_rejected: bool = False  # "maximum iterations reached"인데 하드 제약 위반해 폐기함
    i2_active: bool = False        # step i=1에 I2(또는 I2') 하한이 실제로 적용됐는지
    i2_y_lower_bound: Optional[float] = None   # 적용된 y 하한(참고용, 미적용시 None)
    i2_psi_lower_bound: Optional[float] = None  # I2'에서 적용된 psi 하한(미적용시 None)
    iterations: int = 0            # res.info.iter (I5 설계용, DESIGN_IMPROVED_V2.md §1-3)
    time_limit_hit: bool = False   # I5 안전망(time_limit) 발동 -- time_limit_fingerprint(status+반복 수) 판정
    # (2026-10-14 정정 전에는 solver_status=="run time limit reached"만 셌다 -- 절단의 일부를 놓침)
    ax_inf_norm: float = 0.0       # ||Ax||_inf(현재 solve의 실제 A,x로 계산, 근사 아님)
    prim_res: float = 0.0          # res.info.prim_res(OSQP이 보고하는 ||Ax-z||_inf 그 자체)
    derived_tol_deg: float = 0.0   # eps_abs+eps_rel*(ax_inf_norm+prim_res), deg 환산 --
    # SETTINGS_DECISION.md §19가 쓴 "해석적 상한"(Z_max=1.396rad 가정)이 실측으로
    # 뒷받침되는지 검증하기 위한 스텝별 실제 허용오차(≥ Z_max 가정 없이 그 solve의
    # A/x/prim_res만으로 계산, ||z||<=ax_inf_norm+prim_res는 삼각부등식으로 항상 성립)


def _idx_y(i: int) -> int:
    return 2 * (i - 1)


def _idx_psi(i: int) -> int:
    return 2 * (i - 1) + 1


class ImprovedMPC:
    def __init__(self, enable_i1: Optional[bool] = None, enable_i1b: Optional[bool] = None,
                 enable_i2: Optional[bool] = None, enable_i3: Optional[bool] = None,
                 i2_variant: str = "wide", enable_i5: Optional[bool] = None,
                 i5_max_iter: Optional[int] = None):
        """플래그를 생략하면 improved/config.py의 현재 값을 사용한다(ablation 실행 시
        인스턴스별로 명시적으로 넘기는 것을 권장).
        i2_variant: "wide"(기존 I2, MARGIN_I2=0.272m, 헤딩 제약 추가 없음) 또는
        "narrow"(I2', MARGIN_I2_PRIME=0.143m + I2 활성 구간에 psi>=-20deg 하한 추가,
        DESIGN_IMPROVED.md I2' 참고). enable_i2=False면 이 값은 쓰이지 않는다.
        enable_i5/i5_max_iter: DESIGN_IMPROVED_V2.md I5(반복 상한, 주 메커니즘) --
        enable_i5=False(기본)면 OSQP setup() kwargs가 I5 도입 이전(1회차)과 완전히
        동일하다(max_iter=20000, time_limit 미지정)."""
        self.enable_i1 = improved_config.ENABLE_I1_RATE_AWARE_MPC if enable_i1 is None else enable_i1
        self.enable_i1b = improved_config.ENABLE_I1B_SOFT_CONSTRAINTS if enable_i1b is None else enable_i1b
        self.enable_i2 = improved_config.ENABLE_I2_OBSTACLE_AWARE_MPC if enable_i2 is None else enable_i2
        self.enable_i3 = improved_config.ENABLE_I3_WARM_START_FALLBACK if enable_i3 is None else enable_i3
        assert i2_variant in ("wide", "narrow")
        self.i2_variant = i2_variant
        self.enable_i5 = improved_config.ENABLE_I5_ITER_CAP_MPC if enable_i5 is None else enable_i5
        self.i5_max_iter = improved_config.I5_MAX_ITER if i5_max_iter is None else i5_max_iter
        if self.enable_i5:
            assert self.i5_max_iter is not None and self.i5_max_iter > 0, \
                "enable_i5=True면 i5_max_iter(또는 improved_config.I5_MAX_ITER)를 양의 정수로 지정해야 함"

        N = base_config.N
        self.N = N
        self.n_state = 2 * N
        self.n_delta = N
        self.n_slack = 2 * N  # slack_y(N) + slack_psi(N)
        self.n_vars = self.n_state + self.n_delta + self.n_slack

        self._idx_delta0 = self.n_state
        self._idx_slack_y0 = self.n_state + self.n_delta
        self._idx_slack_psi0 = self._idx_slack_y0 + N

        self.n_eq = 2 * N
        self.n_y_rows = 2 * N   # lo/hi 한쪽씩
        self.n_psi_rows = 2 * N
        self.n_delta_rows = N
        self.n_rate_rows = N
        self.n_slack_rows = 2 * N
        self.n_rows = (self.n_eq + self.n_y_rows + self.n_psi_rows + self.n_delta_rows
                       + self.n_rate_rows + self.n_slack_rows)

        self._build_P()
        self._build_A_template()

        self.prob = osqp.OSQP()
        setup_kwargs = dict(
            P=self.P, q=self._base_q(), A=self.A, l=self.l, u=self.u,
            verbose=base_config.OSQP_VERBOSE, warm_starting=base_config.OSQP_WARM_STARTING,
            polishing=base_config.OSQP_POLISHING,
            eps_abs=base_config.OSQP_EPS_ABS, eps_rel=_EPS_REL,
        )
        if self.enable_i5:
            # I5(DESIGN_IMPROVED_V2.md §1): 반복 상한을 주 메커니즘으로 낮추고,
            # time_limit은 안전망으로 둔다(반복 상한은 warm-start·문제 데이터가 같으면 항상
            # 같은 반복에서 멈춘다 -- 결정론. time_limit은 벽시계 기준이라 발동하면 결정론이
            # 깨진다: 2026-10-14 정정, docs/verification/ci/run6_cause/).
            setup_kwargs["max_iter"] = self.i5_max_iter
            setup_kwargs["time_limit"] = improved_config.I5_TIME_LIMIT_SEC
        else:
            # I5 비활성 시 1회차와 kwargs가 완전히 동일(= 동일 동작 보장).
            setup_kwargs["max_iter"] = _MAX_ITER
        self.prob.setup(**setup_kwargs)
        # time_limit_fingerprint용(기록 전용): OSQP가 실제로 쓰는 반복 상한·수렴 검사 간격
        self._osqp_max_iter = int(self.prob.settings.max_iter)
        self._osqp_check_termination = int(self.prob.settings.check_termination)
        self._fail_count = 0
        self._last_solution_deltas: Optional[np.ndarray] = None  # I3용(rad), 길이 N

    def _idx_delta(self, k: int) -> int:
        return self._idx_delta0 + k

    def _idx_slack_y(self, i: int) -> int:
        return self._idx_slack_y0 + (i - 1)

    def _idx_slack_psi(self, i: int) -> int:
        return self._idx_slack_psi0 + (i - 1)

    # ---------------- construction ----------------

    def _build_P(self):
        """y/psi/delta 블록은 baseline mpc.py의 _build_P와 동일(REQ-MPC-02/03a).
        슬랙 블록은 이차항 없음(ell-1 벌점은 q에만 들어감)."""
        N = self.N
        rows, cols, vals = [], [], []
        for i in range(1, N + 1):
            rows.append(_idx_y(i)); cols.append(_idx_y(i)); vals.append(2 * base_config.QY)
            rows.append(_idx_psi(i)); cols.append(_idx_psi(i)); vals.append(2 * base_config.QPSI)

        diag = np.zeros(N)
        diag[0] += base_config.RDELTA
        for i in range(1, N):
            diag[i] += base_config.RDDELTA
            diag[i - 1] += base_config.RDDELTA
        for k in range(N):
            rows.append(self._idx_delta(k)); cols.append(self._idx_delta(k)); vals.append(2 * diag[k])
        for i in range(1, N):
            c = -2 * base_config.RDDELTA
            rows.append(self._idx_delta(i)); cols.append(self._idx_delta(i - 1)); vals.append(c)
            rows.append(self._idx_delta(i - 1)); cols.append(self._idx_delta(i)); vals.append(c)

        full = sp.coo_matrix((vals, (rows, cols)), shape=(self.n_vars, self.n_vars)).tocsc()
        self.P = sp.triu(full, format="csc")

    def _base_q(self) -> np.ndarray:
        q = np.zeros(self.n_vars)
        rho = improved_config.SOFT_CONSTRAINT_PENALTY
        for i in range(1, self.N + 1):
            q[self._idx_slack_y(i)] = rho
            q[self._idx_slack_psi(i)] = rho
        return q

    def _build_A_template(self):
        N = self.N
        rows, cols, vals = [], [], []
        self._v_entries = []

        r = 0
        rows.append(r); cols.append(_idx_y(1)); vals.append(1.0)
        self._row_y1 = r
        r += 1
        rows.append(r); cols.append(_idx_psi(1)); vals.append(1.0)
        rows.append(r); cols.append(self._idx_delta(0)); vals.append(0.0)
        self._v_entries.append((len(vals) - 1, "psi_delta"))
        self._row_psi1 = r
        r += 1

        self._row_dyn0 = r
        for i in range(2, N + 1):
            rows.append(r); cols.append(_idx_y(i)); vals.append(1.0)
            rows.append(r); cols.append(_idx_y(i - 1)); vals.append(-1.0)
            rows.append(r); cols.append(_idx_psi(i - 1)); vals.append(0.0)
            self._v_entries.append((len(vals) - 1, "y_psi"))
            r += 1
            rows.append(r); cols.append(_idx_psi(i)); vals.append(1.0)
            rows.append(r); cols.append(_idx_psi(i - 1)); vals.append(-1.0)
            rows.append(r); cols.append(self._idx_delta(i - 1)); vals.append(0.0)
            self._v_entries.append((len(vals) - 1, "psi_delta"))
            r += 1
        assert r == self.n_eq

        # --- y 위치제약 (소프트: lo/hi 한쪽씩, I1b§) ---
        self._row_y_lo0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(_idx_y(i)); vals.append(1.0)
            rows.append(r); cols.append(self._idx_slack_y(i)); vals.append(1.0)
            r += 1
        self._row_y_hi0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(_idx_y(i)); vals.append(1.0)
            rows.append(r); cols.append(self._idx_slack_y(i)); vals.append(-1.0)
            r += 1

        # --- psi 위치제약 (소프트, 고정 +-80deg) ---
        self._row_psi_lo0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(_idx_psi(i)); vals.append(1.0)
            rows.append(r); cols.append(self._idx_slack_psi(i)); vals.append(1.0)
            r += 1
        self._row_psi_hi0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(_idx_psi(i)); vals.append(1.0)
            rows.append(r); cols.append(self._idx_slack_psi(i)); vals.append(-1.0)
            r += 1

        # --- delta 제약 (항상 하드) ---
        self._row_delta0 = r
        for k in range(N):
            rows.append(r); cols.append(self._idx_delta(k)); vals.append(1.0)
            r += 1

        # --- rate limit (I1, 온/오프는 l/u로 토글) ---
        self._row_rate0 = r
        rows.append(r); cols.append(self._idx_delta(0)); vals.append(1.0)
        r += 1
        for k in range(1, N):
            rows.append(r); cols.append(self._idx_delta(k)); vals.append(1.0)
            rows.append(r); cols.append(self._idx_delta(k - 1)); vals.append(-1.0)
            r += 1

        # --- 슬랙 하한(>=0), 상한은 I1b 온/오프로 토글 ---
        self._row_slack_y0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(self._idx_slack_y(i)); vals.append(1.0)
            r += 1
        self._row_slack_psi0 = r
        for i in range(1, N + 1):
            rows.append(r); cols.append(self._idx_slack_psi(i)); vals.append(1.0)
            r += 1

        assert r == self.n_rows

        coo = sp.coo_matrix((vals, (rows, cols)), shape=(self.n_rows, self.n_vars))
        self._A_coo_rows = np.array(rows)
        self._A_coo_cols = np.array(cols)
        csc = coo.tocsc()
        self.A = csc
        self._rc_to_dataidx = {}
        for col in range(self.n_vars):
            start, end = csc.indptr[col], csc.indptr[col + 1]
            for k in range(start, end):
                self._rc_to_dataidx[(csc.indices[k], col)] = k

        self.l = np.full(self.n_rows, -np.inf)
        self.u = np.full(self.n_rows, np.inf)

        for i in range(2, N + 1):
            row_y = self._row_dyn0 + 2 * (i - 2)
            row_psi = row_y + 1
            self.l[row_y] = self.u[row_y] = 0.0
            self.l[row_psi] = self.u[row_psi] = 0.0
        self.l[self._row_y1] = self.u[self._row_y1] = 0.0
        self.l[self._row_psi1] = self.u[self._row_psi1] = 0.0

        # y 행: solve()마다 상태별로 갱신(placeholder)
        for i in range(1, N + 1):
            self.l[self._row_y_lo0 + (i - 1)] = -np.inf
            self.u[self._row_y_hi0 + (i - 1)] = np.inf

        # psi 행: 고정 +-80deg (I1b와 무관하게 이 값 자체는 고정)
        psi_lo = -base_config.PSI_LIMIT_DEG * _DEG2RAD
        psi_hi = base_config.PSI_LIMIT_DEG * _DEG2RAD
        for i in range(1, N + 1):
            self.l[self._row_psi_lo0 + (i - 1)] = psi_lo
            self.u[self._row_psi_hi0 + (i - 1)] = psi_hi

        # delta 행: 고정 +-25deg (항상 하드)
        d_lo = -base_config.DELTA_MAX_DEG * _DEG2RAD
        d_hi = base_config.DELTA_MAX_DEG * _DEG2RAD
        for k in range(N):
            self.l[self._row_delta0 + k] = d_lo
            self.u[self._row_delta0 + k] = d_hi

        # rate 행: I1 온/오프로 고정폭 결정(k=0 행은 delta_prev 의존이라 solve()에서 매번 갱신)
        rate = base_config.DELTA_RATE_MAX_PER_STEP_DEG * _DEG2RAD
        if self.enable_i1:
            for k in range(1, N):
                self.l[self._row_rate0 + k] = -rate
                self.u[self._row_rate0 + k] = rate
        # k=0 행은 항상 solve()에서 갱신(플래그 off면 -inf/inf로 설정)

        # 슬랙 행: I1b 온/오프로 상한 결정(하한은 항상 0)
        slack_hi = np.inf if self.enable_i1b else 0.0
        for i in range(1, N + 1):
            self.l[self._row_slack_y0 + (i - 1)] = 0.0
            self.u[self._row_slack_y0 + (i - 1)] = slack_hi
            self.l[self._row_slack_psi0 + (i - 1)] = 0.0
            self.u[self._row_slack_psi0 + (i - 1)] = slack_hi

    # ---------------- solve ----------------

    def solve(self, y0: float, psi0_rad: float, v0: float, target_y: float,
              state_name: str, delta_prev_deg: float = 0.0,
              obstacle_info: Optional[FrontObstacleInfo] = None) -> MPCResult:
        t_start = time.perf_counter()
        N = self.N
        v = max(0.05, min(base_config.V_MAX, abs(v0)))

        Ax_idx = []
        Ax_val = []
        row, col = self._row_psi1, self._idx_delta(0)
        Ax_idx.append(self._rc_to_dataidx[(row, col)])
        Ax_val.append(-(v / base_config.L) * base_config.DT)
        for i in range(2, N + 1):
            row_y = self._row_dyn0 + 2 * (i - 2)
            row_psi = row_y + 1
            Ax_idx.append(self._rc_to_dataidx[(row_y, _idx_psi(i - 1))])
            Ax_val.append(-v * base_config.DT)
            Ax_idx.append(self._rc_to_dataidx[(row_psi, self._idx_delta(i - 1))])
            Ax_val.append(-(v / base_config.L) * base_config.DT)

        l = self.l.copy()
        u = self.u.copy()
        y1_val = y0 + v * base_config.DT * psi0_rad
        l[self._row_y1] = u[self._row_y1] = y1_val
        l[self._row_psi1] = u[self._row_psi1] = psi0_rad

        lo, hi = base_config.POSITION_CONSTRAINTS[state_name]
        psi_lo_fixed = -base_config.PSI_LIMIT_DEG * _DEG2RAD
        i2_active_step1 = False
        i2_y_lo_step1 = None
        i2_psi_lo_step1 = None
        if self.enable_i2 and obstacle_info is not None:
            y_lo_per_step, psi_lo_per_step, active_per_step = self._i2_bounds(lo, v, obstacle_info)
            i2_active_step1 = active_per_step[0]
            if i2_active_step1:
                i2_y_lo_step1 = y_lo_per_step[0]
                if self.i2_variant == "narrow":
                    i2_psi_lo_step1 = psi_lo_per_step[0]
        else:
            y_lo_per_step = [lo] * N
            psi_lo_per_step = [psi_lo_fixed] * N
        for i in range(1, N + 1):
            l[self._row_y_lo0 + (i - 1)] = y_lo_per_step[i - 1]
            u[self._row_y_hi0 + (i - 1)] = hi
            l[self._row_psi_lo0 + (i - 1)] = psi_lo_per_step[i - 1]

        rate = base_config.DELTA_RATE_MAX_PER_STEP_DEG * _DEG2RAD
        if self.enable_i1:
            delta_prev_rad = delta_prev_deg * _DEG2RAD
            l[self._row_rate0] = delta_prev_rad - rate
            u[self._row_rate0] = delta_prev_rad + rate
        else:
            l[self._row_rate0] = -np.inf
            u[self._row_rate0] = np.inf

        q = self._base_q()
        for i in range(1, N + 1):
            q[_idx_y(i)] = -2.0 * base_config.QY * target_y

        Ax_idx_arr = np.array(Ax_idx, dtype=np.int64)
        Ax_val_arr = np.array(Ax_val)
        self.prob.update(q=q, l=l, u=u, Ax=Ax_val_arr, Ax_idx=Ax_idx_arr)
        res = self.prob.solve(raise_error=base_config.OSQP_RAISE_ERROR)
        status = res.info.status
        iterations = int(res.info.iter)
        # 기록 전용(제어 분기는 아래에서 status로만 갈린다). I5 off는 time_limit을 넘기지 않으므로
        # (OSQP 기본 1e10) 지금처럼 status만 본다.
        if self.enable_i5:
            time_limit_hit = time_limit_fingerprint(status, iterations, self._osqp_max_iter,
                                                    self._osqp_check_termination)
        else:
            time_limit_hit = (status == "run time limit reached")
        approx_rejected = False

        # SETTINGS_DECISION.md §19 검증용 노름 로깅(제어 로직 아님): 이번 solve에 실제로
        # 쓰인 A(템플릿 self.A에 v-의존 항목만 Ax_idx/Ax_val로 반영)로 Ax를 직접
        # 계산한다(가정·근사 없이 그 solve의 실제 A,x). z는 osqp 파이썬 바인딩이
        # 반환하지 않지만, "solved"류 상태에서는 ||Ax-z||_inf<=res.info.prim_res(OSQP
        # 자신이 보고하는 실측 잔차)이므로 삼각부등식으로 ||z||_inf<=ax_inf_norm+prim_res
        # -- 따라서 max(||Ax||,||z||)<=ax_inf_norm+prim_res는 항상(가정 없이) 성립.
        A_data = self.A.data.copy()
        A_data[Ax_idx_arr] = Ax_val_arr
        A_cur = sp.csc_matrix((A_data, self.A.indices, self.A.indptr), shape=self.A.shape)
        ax_full = A_cur @ res.x
        ax_inf_norm = float(np.max(np.abs(ax_full))) if ax_full.size else 0.0
        prim_res = float(getattr(res.info, "prim_res", 0.0))
        derived_tol_rad = base_config.OSQP_EPS_ABS + _EPS_REL * (ax_inf_norm + prim_res)
        derived_tol_deg = derived_tol_rad * _RAD2DEG

        if status in ("solved", "solved inaccurate"):
            ok = True
        elif status in ("maximum iterations reached", "run time limit reached"):
            # I5(DESIGN_IMPROVED_V2.md §1-2): "run time limit reached"(안전망 발동)도
            # "maximum iterations reached"와 동일하게 처리한다 -- I1b(슬랙)가 켜져
            # 있으면 문제는 항상 수학적으로 feasible(볼록, 슬랙 상한 +inf)이므로 이
            # 상태는 true infeasible이 아니라 반복/시간 예산을 다 쓴 것뿐일 수 있다.
            # 그렇다고 res.x를 무조건 믿지는 않고, "실제로 이번 step에 적용될 하드
            # 제약"(|delta_0|<=25deg, I1이면 |delta_0-delta_prev|<=10deg/step)만이라도
            # 만족하는지 검사해서 통과하면 사용하고, 실패하면 폐기하고 fallback으로
            # 보낸다(3단계 검토 반영).
            delta0_rad = res.x[self._idx_delta(0)]
            dmax_rad = base_config.DELTA_MAX_DEG * _DEG2RAD
            hard_ok = abs(delta0_rad) <= dmax_rad + base_config.OSQP_EPS_ABS
            if self.enable_i1:
                delta_prev_rad_check = delta_prev_deg * _DEG2RAD
                hard_ok = hard_ok and (abs(delta0_rad - delta_prev_rad_check)
                                        <= rate + base_config.OSQP_EPS_ABS)
            ok = hard_ok
            approx_rejected = not hard_ok
        else:
            ok = False

        if ok:
            deltas_rad = np.array([res.x[self._idx_delta(k)] for k in range(N)])
            self._last_solution_deltas = deltas_rad
            delta_deg = float(deltas_rad[0] * _RAD2DEG)
            compute_ms = (time.perf_counter() - t_start) * 1000.0
            return MPCResult(delta_deg=delta_deg, solver_status=status, ok=True,
                              fallback_used=False, warm_start_shift_used=False,
                              compute_time_ms=compute_ms, approx_rejected=False,
                              i2_active=i2_active_step1, i2_y_lower_bound=i2_y_lo_step1,
                              i2_psi_lower_bound=i2_psi_lo_step1,
                              iterations=iterations, time_limit_hit=time_limit_hit,
                              ax_inf_norm=ax_inf_norm, prim_res=prim_res,
                              derived_tol_deg=derived_tol_deg)

        self._fail_count += 1
        compute_ms = (time.perf_counter() - t_start) * 1000.0
        if self.enable_i3 and self._last_solution_deltas is not None:
            prev = self._last_solution_deltas
            shifted = np.concatenate([prev[1:], prev[-1:]])
            self._last_solution_deltas = shifted
            delta_deg = float(shifted[0] * _RAD2DEG)
            return MPCResult(delta_deg=delta_deg, solver_status=status, ok=False,
                              fallback_used=True, warm_start_shift_used=True,
                              compute_time_ms=compute_ms, approx_rejected=approx_rejected,
                              i2_active=i2_active_step1, i2_y_lower_bound=i2_y_lo_step1,
                              i2_psi_lower_bound=i2_psi_lo_step1,
                              iterations=iterations, time_limit_hit=time_limit_hit,
                              ax_inf_norm=ax_inf_norm, prim_res=prim_res,
                              derived_tol_deg=derived_tol_deg)

        delta_fallback_rad = -base_config.K_P_FALLBACK * (y0 - target_y)
        delta_fallback_deg = delta_fallback_rad * _RAD2DEG
        delta_fallback_deg = max(-base_config.DELTA_MAX_DEG,
                                  min(base_config.DELTA_MAX_DEG, delta_fallback_deg))
        return MPCResult(delta_deg=float(delta_fallback_deg), solver_status=status, ok=False,
                          fallback_used=True, warm_start_shift_used=False,
                          compute_time_ms=compute_ms, approx_rejected=approx_rejected,
                          i2_active=i2_active_step1, i2_y_lower_bound=i2_y_lo_step1,
                          i2_psi_lower_bound=i2_psi_lo_step1,
                          iterations=iterations, time_limit_hit=time_limit_hit,
                          ax_inf_norm=ax_inf_norm, prim_res=prim_res,
                          derived_tol_deg=derived_tol_deg)

    def _i2_bounds(self, base_lo: float, v: float, obstacle_info: FrontObstacleInfo):
        """DESIGN_IMPROVED.md I2/I2': 예측 스텝 i의 전단 위치가 장애물 종방향 구간
        [gap_near, gap_far+L] 안에 들면 그 step의 y 하한을 obs_y_hi+margin으로 올린다.
        i2_variant="narrow"(I2')면 같은 구간에서 psi 하한도 -20도로 함께 올린다(margin은
        MARGIN_I2_PRIME=B/2+L*sin(20deg)로 더 작게 잡을 수 있는 근거).
        반환: (y_lo_per_step, psi_lo_per_step, active_per_step)."""
        N = self.N
        if self.i2_variant == "narrow":
            margin = improved_config.MARGIN_I2_PRIME
            psi_floor = -20.0 * _DEG2RAD
        else:
            margin = improved_config.MARGIN_I2
            psi_floor = None
        raised_lo = obstacle_info.y_hi + margin
        psi_lo_fixed = -base_config.PSI_LIMIT_DEG * _DEG2RAD
        y_lo_per_step, psi_lo_per_step, active_per_step = [], [], []
        for i in range(1, N + 1):
            advance = v * i * base_config.DT
            in_window = obstacle_info.gap_near <= advance <= obstacle_info.gap_far + base_config.L
            y_lo_per_step.append(max(base_lo, raised_lo) if in_window else base_lo)
            if in_window and psi_floor is not None:
                psi_lo_per_step.append(max(psi_lo_fixed, psi_floor))
            else:
                psi_lo_per_step.append(psi_lo_fixed)
            active_per_step.append(in_window)
        return y_lo_per_step, psi_lo_per_step, active_per_step
