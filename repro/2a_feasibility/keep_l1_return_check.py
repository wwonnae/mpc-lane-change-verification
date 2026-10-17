"""
2단계-A 재계산: KEEP_L1->RETURN_TO_L2 전이 조건을
(A) t>0.6s 단독 vs (B) "장애물 완전 통과(차체 후단 x > 장애물 후단 x) AND t>0.6s"
로 각각 적용했을 때, 전단거리 0.5/0.8/1.2/1.6/2.0m에서 전체 사이클이
충돌 없이 완료되는지 비교한다. 증명용 계산, baseline 코드 아님. 기존 코드 import 없음.
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
G_SAFE_MIN = 0.20
NEAR_L1 = 0.08
T_KEEP_L1_MIN = 0.6
NEAR_L2 = 0.08  # [개정] 반영
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

def run(front_gap0, require_pass, max_steps=400):
    obstacle_center_x = L + front_gap0 + L/2
    obstacle_far_x = obstacle_center_x + L/2   # 장애물 후단(원거리 쪽 끝)
    ob_poly = rect_corners(obstacle_center_x, 0.0, 0.0, L, B, rear_at_origin=False)

    x = y = psi = 0.0
    delta_prev = 0.0
    state = "KEEP_L2"
    cooldown_steps = int(round(0.3/DT))
    last_change_step = -cooldown_steps
    keep_l1_enter_step = None
    events = []
    collided_any = False
    finished = False
    for step in range(1, max_steps+1):
        front_x = x + L*math.cos(psi)
        front_gap = obstacle_center_x - L/2 - front_x
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
                keep_l1_enter_step = step
        elif state == "KEEP_L1":
            target_y = W
            time_ok = (step - last_change_step)*DT > T_KEEP_L1_MIN
            passed_ok = x > obstacle_far_x  # 차체 후단(rear axle, rear_at_origin 기준) > 장애물 후단
            if require_pass:
                if time_ok and passed_ok:
                    state = "RETURN_TO_L2"
            else:
                if time_ok:
                    state = "RETURN_TO_L2"
        elif state == "RETURN_TO_L2":
            target_y = 0.0
            if cooldown_ok and abs(y) <= NEAR_L2 and abs(math.degrees(psi)) <= PSI_L2_LIMIT:
                state = "KEEP_L2"
        if state != prev_state:
            events.append((step, round(step*DT,2), prev_state, state, round(x,3), round(y,3), round(math.degrees(psi),2)))
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

        if state == "KEEP_L2" and prev_state == "RETURN_TO_L2":
            finished = True
            break

    return events, collided_any, finished, step

print(f"{'front_gap0':>10} | {'time-only: collided/finished/steps':>34} | {'pass&time: collided/finished/steps':>34}")
for fg0 in [0.5, 0.8, 1.2, 1.6, 2.0]:
    ev_a, col_a, fin_a, st_a = run(fg0, require_pass=False)
    ev_b, col_b, fin_b, st_b = run(fg0, require_pass=True)
    print(f"{fg0:>10} | collided={col_a!s:5} finished={fin_a!s:5} steps={st_a:4d}       | collided={col_b!s:5} finished={fin_b!s:5} steps={st_b:4d}")

print()
print("=== 상세: front_gap0=2.0, pass&time 조건 ===")
ev, col, fin, st = run(2.0, require_pass=True)
for e in ev:
    print(" ", e)
print("collided=", col, "finished=", fin, "steps=", st)

print()
print("=== 상세: front_gap0=1.2, time-only 조건 (충돌 시점 근처) ===")
ev, col, fin, st = run(1.2, require_pass=False)
for e in ev:
    print(" ", e)
print("collided=", col, "finished=", fin, "steps=", st)
