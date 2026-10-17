"""
2단계-A 사전 계산: KEEP_L2->EVADE_L->KEEP_L1->RETURN_TO_L2->KEEP_L2 흐름이
논문 서술(고정 파라미터 + REQ-FSM/REQ-MPC 확정값) 만으로 물리적으로 막히는지 검증.
baseline 코드가 아님(2단계-A는 "코드 없음" 원칙, 이 스크립트는 실행 전 증명용 계산만).
원본 파일 참조 없음, code_backup import 없음.
"""
import math

DT = 0.05
V = 0.5          # REQ-SPD-01 v_ref
L = 0.20         # REQ-VEH-02
B = 0.15         # REQ-VEH-02
DELTA_MAX = 25.0     # deg
RATE_MAX = 200.0     # deg/s
RATE_PER_STEP = RATE_MAX * DT   # 10 deg/step
HALF_B = B / 2.0

def simulate(delta_policy, x0=0.0, y0=0.0, psi0=0.0, x_stop=None, max_steps=400):
    x, y, psi = x0, y0, math.radians(psi0)
    delta_prev = 0.0
    log = []
    for step in range(1, max_steps + 1):
        delta_desired = delta_policy(step, x, y, psi)
        delta_cmd = max(delta_prev - RATE_PER_STEP, min(delta_prev + RATE_PER_STEP, delta_desired))
        delta_cmd = max(-DELTA_MAX, min(DELTA_MAX, delta_cmd))
        delta_prev = delta_cmd
        dr = math.radians(delta_cmd)
        x += V * math.cos(psi) * DT
        y += V * math.sin(psi) * DT
        psi += (V / L) * math.tan(dr) * DT
        log.append((step, step * DT, x, y, math.degrees(psi), delta_cmd))
        if x_stop is not None and x >= x_stop:
            break
    return log

# ---------------------------------------------------------------
# 1) 최악의 경우: 장애물 X_obs=0.5m(REQ-SIM-02 하한), v=0.5 고정(REQ-SPD-01, EVADE_L도 v_ref 유지)
#    "target-tracking" 정책: 목표 y=0.30 방향으로 헤딩을 잡되, 목표 근처에서 되돌아오는
#    간단한 비례조향(순수 bang-bang이 아니라 좀 더 현실적인 하한을 보기 위함)
# ---------------------------------------------------------------
X_OBS = 0.5
TARGET_Y = 0.30

def policy_track(step, x, y, psi):
    err = TARGET_Y - y
    # 단순 비례: 오차가 크면 최대 조향, 가까워지면 줄임(헤딩도 감안한 순수 비례가 아니라
    # "적어도 이 정도는 된다"를 보이기 위한 보수적 하한용 정책)
    desired = max(-DELTA_MAX, min(DELTA_MAX, err * 200.0))
    return desired

log = simulate(policy_track, x_stop=X_OBS + 1.0)
t_clear = None
t_evade_target = None
for step, t, x, y, psi_deg, d in log:
    if t_clear is None and abs(y) >= HALF_B:
        t_clear = (step, t, x, y)
    if t_evade_target is None and abs(y - TARGET_Y) <= 0.08:
        t_evade_target = (step, t, x, y, psi_deg)
    if x >= X_OBS:
        x_at_obs = (step, t, x, y, psi_deg)
        break
else:
    x_at_obs = None

print("=== 1) 최악 케이스 장애물(X_obs=0.5m) 회피 타이밍 (비례조향 정책) ===")
print("clearance(|y|>=B/2=0.075) 도달:", t_clear)
print("EVADE_L->KEEP_L1 임계(|y-0.30|<=0.08) 도달:", t_evade_target)
print("x가 X_obs(0.5)에 도달한 순간의 상태:", x_at_obs)
print("=> collision(§8 A′): x>=X_obs 시점에 |y|<0.075 이면 충돌. 위 값으로 판정.")
print()

# ---------------------------------------------------------------
# 2) RETURN_TO_L2->KEEP_L2 경계 텐션 확인:
#    전이 조건은 |y|<=0.20, |psi|<=20 (REQ-FSM-02e).
#    KEEP_L2 MPC 위치 제약은 |y_i|<=0.15, i=1..N (REQ-MPC-04, REQ-MPC-05).
#    y0=0.20, psi0=20deg(둘 다 전이 허용 경계)에서 한 스텝 만에 y1<=0.15로
#    갈 수 있는지 계산.
# ---------------------------------------------------------------
y0 = 0.20
psi0_deg = 20.0
# 최선의 경우: 남은 헤딩(20도, 부호가 y를 줄이는 방향)만으로 한 스텝 이동
psi0 = math.radians(-psi0_deg)  # y를 줄이는 방향(음의 psi)으로 이미 정렬돼 있다고 가정(가장 유리한 경우)
dy_one_step_best_case = V * math.sin(psi0) * DT
y1_best_case = y0 + dy_one_step_best_case

# 추가로 이번 스텝에 조향을 더 걸어 psi를 더 키울 수 있는 여유(한 스텝 delta rate)까지 반영한 상한
extra_psi_rad = math.radians(RATE_PER_STEP)  # 한 스텝 동안 delta가 더 꺾일 수 있는 최대치를 헤딩 변화로 낙관적으로 흡수(상한 추정용)
psi0_opt = psi0 - extra_psi_rad
dy_one_step_opt = V * math.sin(psi0_opt) * DT
y1_opt = y0 + dy_one_step_opt

print("=== 2) RETURN_TO_L2->KEEP_L2 경계 텐션 ===")
print(f"y0={y0}, psi0=-{psi0_deg}deg(가장 유리한 방향으로 이미 정렬된 경우)")
print(f"한 스텝 최대 |dy| (현재 헤딩 유지) = {abs(dy_one_step_best_case):.4f} m  -> y1={y1_best_case:.4f}")
print(f"한 스텝 최대 |dy| (헤딩을 그 스텝에 더 꺾는 낙관적 상한) = {abs(dy_one_step_opt):.4f} m -> y1={y1_opt:.4f}")
print(f"필요한 dy = y0-0.15 = {y0-0.15:.4f} m")
print(f"=> KEEP_L2 제약(y1<=0.15) 충족 여부(최유리 케이스): {y1_best_case <= 0.15}")
print(f"=> KEEP_L2 제약(y1<=0.15) 충족 여부(낙관적 상한 케이스): {y1_opt <= 0.15}")
