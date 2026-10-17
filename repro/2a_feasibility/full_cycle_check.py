"""
2단계-A 재계산: 전체 5상태 사이클(KEEP_L2->EVADE_L->KEEP_L1->RETURN_TO_L2->KEEP_L2)을
끝까지 시뮬레이션해서, KEEP_L1->RETURN_TO_L2(t>0.6s, 장애물 통과 조건 없음)가 실제로
장애물을 완전히 지나친 후에 일어나는지, 복귀 중 장애물과 재충돌하지 않는지 확인한다.
회전 사각형 충돌 판정(collision_box_check.py와 동일 로직)을 그대로 씀. 증명용 계산,
baseline 코드 아님. 기존 코드 import 없음.
"""
import math

DT = 0.05
V = 0.5
L = 0.20
B = 0.15
RATE_PER_STEP = 200.0 * DT
DELTA_MAX = 25.0
W = 0.30
G_TRIG = 1.2
NEAR_L1 = 0.08          # EVADE_L->KEEP_L1 (PDF 그대로)
T_KEEP_L1_MIN = 0.6
NEAR_L2_REVISED = 0.08  # [개정] RETURN_TO_L2->KEEP_L2 (0.20 -> 0.08)
PSI_L2_LIMIT = 20.0

def rect_corners(cx, cy, heading_rad, length, width, rear_at_origin=False):
    if rear_at_origin:
        local = [(0, -width/2), (length, -width/2), (length, width/2), (0, width/2)]
    else:
        local = [(-length/2, -width/2), (length/2, -width/2), (length/2, width/2), (-length/2, width/2)]
    ch, sh = math.cos(heading_rad), math.sin(heading_rad)
    return [(cx+lx*ch-ly*sh, cy+lx*sh+ly*ch) for lx, ly in local]

def sat_overlap(p1, p2):
    for poly in (p1, p2):
        for i in range(len(poly)):
            x1, y1 = poly[i]; x2, y2 = poly[(i+1) % len(poly)]
            nx, ny = -(y2-y1), (x2-x1)
            n = math.hypot(nx, ny)
            if n < 1e-12:
                continue
            nx, ny = nx/n, ny/n
            a = [px*nx+py*ny for px, py in p1]
            b = [px*nx+py*ny for px, py in p2]
            if max(a) < min(b) or max(b) < min(a):
                return False
    return True

def run(front_gap0, max_steps=200):
    # front_gap0: t=0 시점 전단-장애물 거리 (해석 2, 추천)
    obstacle_center_x = L + front_gap0 + L/2
    ob_poly = rect_corners(obstacle_center_x, 0.0, 0.0, L, B, rear_at_origin=False)

    x = y = psi = 0.0
    delta_prev = 0.0
    state = "KEEP_L2"
    cooldown_steps = int(round(0.3/DT))  # 6 steps
    last_change_step = -cooldown_steps  # [공백] 쿨다운 초기값: 첫 전이를 막지 않도록 초기화(추천안)
    events = []
    collided_any = False
    for step in range(1, max_steps+1):
        front_gap = obstacle_center_x - L/2 - (x + L*math.cos(psi))  # 전단 기준 front_gap
        cooldown_ok = (step - last_change_step) >= cooldown_steps

        prev_state = state
        if state == "KEEP_L2":
            target_y = 0.0
            if cooldown_ok and front_gap < G_TRIG:
                state = "EVADE_L"
        elif state == "EVADE_L":
            target_y = W
            if cooldown_ok and abs(y - W) <= NEAR_L1:
                state = "KEEP_L1"
        elif state == "KEEP_L1":
            target_y = W
            if (step - last_change_step)*DT > T_KEEP_L1_MIN:
                state = "RETURN_TO_L2"
        elif state == "RETURN_TO_L2":
            target_y = 0.0
            if cooldown_ok and abs(y) <= NEAR_L2_REVISED and abs(math.degrees(psi)) <= PSI_L2_LIMIT:
                state = "KEEP_L2"
        if state != prev_state:
            events.append((step, step*DT, prev_state, state, x, y, math.degrees(psi), front_gap))
            last_change_step = step

        err = target_y - y
        desired = max(-DELTA_MAX, min(DELTA_MAX, err*200.0 - math.degrees(psi)*2.0))
        delta_cmd = max(delta_prev-RATE_PER_STEP, min(delta_prev+RATE_PER_STEP, desired))
        delta_cmd = max(-DELTA_MAX, min(DELTA_MAX, delta_cmd))
        delta_prev = delta_cmd
        dr = math.radians(delta_cmd)
        x += V*math.cos(psi)*DT
        y += V*math.sin(psi)*DT
        psi += (V/L)*math.tan(dr)*DT

        veh_poly = rect_corners(x, y, psi, L, B, rear_at_origin=True)
        if sat_overlap(veh_poly, ob_poly):
            collided_any = True
            events.append((step, step*DT, "COLLISION", "COLLISION", x, y, math.degrees(psi), front_gap))

        if state == "KEEP_L2" and prev_state == "RETURN_TO_L2":
            # 완전히 한 사이클 종료
            break

    return events, collided_any, step

for fg0 in [0.5, 0.35, 0.30, 0.295]:
    events, collided, total_steps = run(fg0)
    print(f"--- front_gap0={fg0} ---")
    for e in events:
        print("  ", e)
    print(f"  collided_any={collided}, total_steps_used={total_steps}/200")
    print()
