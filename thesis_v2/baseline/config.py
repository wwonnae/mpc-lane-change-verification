"""
baseline 설정값 — 논문 제출 이후 작성.
기준: repro/docs/SPEC.md, repro/docs/SETTINGS_DECISION.md.
고정 파라미터(REQ-VEH-02, REQ-MPC-03, REQ-FSM-03)는 여기서만 정의하고 절대 바꾸지 않는다.
"""

# ===== 고정 파라미터 (변경 금지, repro/docs/WORK_RULES.md) =====
N = 15                          # REQ-MPC-03
DT = 0.05                       # REQ-VEH-01 등
QY = 100.0                      # REQ-MPC-03
QPSI = 25.0                     # REQ-MPC-03
RDELTA = 2.0                    # REQ-MPC-03
RDDELTA = 5.0                   # REQ-MPC-03
DELTA_MAX_DEG = 25.0            # REQ-VEH-02
DELTA_RATE_MAX_DEGPS = 200.0    # REQ-VEH-02
G_TRIG = 1.2                    # REQ-FSM-02a
G_SAFE_MIN = 0.20               # REQ-FSM-02b
COOLDOWN = 0.3                  # REQ-FSM-03
W = 0.30                        # REQ-SIM-01 (차선폭)
L = 0.20                        # REQ-VEH-02 (축간거리)
B = 0.15                        # REQ-VEH-02 (차폭)

# ===== 결정표 값 (SETTINGS_DECISION.md) =====
T_KEEP_L1_MIN = 0.6                     # REQ-FSM-02d, PDF Table2
NEAR_L1 = 0.08                          # REQ-FSM-02c [정합]
NEAR_L2 = 0.08                          # REQ-FSM-02e [개정](원문 0.20 -> 0.08)
PSI_L2_LIMIT_DEG = 20.0                 # REQ-FSM-02e [정합]
K_P_FALLBACK = 1.0                      # REQ-MPC-07, 단위 rad/m (§11)
K_EY = 1.5                              # REQ-LAT-01
LINE_WIDTH = 0.06                       # REQ-SEN-03 [공백] 확정값 (§9)
SENSOR_SPACING = 0.04                   # REQ-SEN-03 [정합]
LIDAR_MAX_RANGE = 10.0                  # REQ-SEN-01 [공백] (§7)
PSI_LIMIT_DEG = 80.0                    # REQ-MPC-04
DELTA_RATE_MAX_PER_STEP_DEG = DELTA_RATE_MAX_DEGPS * DT  # REQ-VEH-03: 10 deg/step

# REQ-MPC-05: 상태별 횡방향 위치 제약 (m)
POSITION_CONSTRAINTS = {
    "KEEP_L2": (-0.15, 0.15),
    "KEEP_L1": (0.15, 0.45),
    "EVADE_L": (-0.15, 0.45),
    "RETURN_TO_L2": (-0.15, 0.45),
}

# REQ-SIM-02/02a/03, [개정]2: 시나리오 생성 범위
OBSTACLE_FRONT_GAP_RANGE = (0.5, 2.0)   # REQ-SIM-02, §12(전단 기준)
INITIAL_V_RANGE = (0.3, 0.5)            # REQ-SIM-03
INITIAL_Y_STD = 0.05                    # REQ-SIM-03
INITIAL_Y_TRUNC = (-0.15, 0.15)         # REQ-SIM-03 [개정]
OBSTACLE_LENGTH = L                     # REQ-SIM-08 §8 (장애물 = 차체와 동일 풋프린트)
OBSTACLE_WIDTH = B

# REQ-SIM-04/05, §6: 에피소드 구조
MAX_STEPS = 200
OBSERVE_STEPS = 20

V_MAX = 0.5                             # REQ-VEH-02 (=REQ-SPD-01 v_ref)

# ===== OSQP 솔버 설정 (SETTINGS_DECISION.md §18, [공백] — 버전 간 기본값 차이 제거용) =====
# osqp>=1.0 API 기준(0.6.x 이하는 requirements.txt로 배제). 값 자체는 기존 B-2 구현이 이미
# 쓰던 값을 그대로 명문화(동작 변경 없음) — eps_abs/eps_rel/max_iter는 원래 mpc.py에 있던
# 값, polishing/warm_starting은 osqp 1.x 기본값과 동일(명시적으로 고정해 향후 버전이 기본값을
# 바꿔도 baseline 동작이 변하지 않도록 함).
OSQP_EPS_ABS = 1e-4
OSQP_EPS_REL = 1e-4
OSQP_MAX_ITER = 4000
OSQP_POLISHING = False
OSQP_WARM_STARTING = True
OSQP_VERBOSE = False
# osqp>=1.x는 solve(raise_error=None)의 기본값이 향후 True로 바뀔 예정(PendingDeprecationWarning
# 확인됨) -- True가 되면 infeasible/실패 시 예외가 던져져 REQ-MPC-07 fallback 분기(현재
# res.info.status를 읽어 처리)가 깨진다. False로 고정해 "예외 없이 상태만 반환받아 fallback
# 분기로 처리"하는 현재 동작을 버전에 관계없이 유지한다.
OSQP_RAISE_ERROR = False


def assert_fixed_params():
    """repro/docs/WORK_RULES.md: 시작 시 고정 파라미터 일치 확인."""
    assert N == 15
    assert DT == 0.05
    assert QY == 100.0
    assert QPSI == 25.0
    assert RDELTA == 2.0
    assert RDDELTA == 5.0
    assert DELTA_MAX_DEG == 25.0
    assert DELTA_RATE_MAX_DEGPS == 200.0
    assert G_TRIG == 1.2
    assert G_SAFE_MIN == 0.20
    assert COOLDOWN == 0.3
    assert W == 0.30
    assert L == 0.20
    assert B == 0.15


assert_fixed_params()
