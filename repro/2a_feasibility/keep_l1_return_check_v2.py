"""
2단계-A 재계산(v2): KEEP_L1->RETURN_TO_L2 전이를 "right_clear AND t>0.6s"로 계산한다.
right_clear은 시뮬레이터 좌표를 직접 읽지 않고, 센서 모델(장애물 풋프린트 vs 탐지 윈도우)로만
계산한다 - repro/docs/WORK_RULES.md 원칙(제어기는 센서 출력만 입력) 준수. 증명용 계산, baseline 코드 아님.
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
NEAR_L2 = 0.08
PSI_L2_LIMIT = 20.0
L2_RANGE = (-0.15, 0.15)   # REQ-MPC-04 "L2 주행" 제약 재사용

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

def sensor_right_clear(x_rear, x_front, obstacle_near_x, obstacle_far_x, obstacle_y_range):
    """LiDAR 2D 스캔 모사: L2 범위[-0.15,0.15] AND 종방향 윈도우
    [x_rear-G_SAFE_MIN, x_front+G_TRIG] 안에 장애물 풋프린트가 있으면 False."""
    window_lo, window_hi = x_rear - G_SAFE_MIN, x_front + G_TRIG
    lat_overlap = not (obstacle_y_range[1] < L2_RANGE[0] or obstacle_y_range[0] > L2_RANGE[1])
    lon_overlap = not (obstacle_far_x < window_lo or obstacle_near_x > window_hi)
    if lat_overlap and lon_overlap:
        return False
    return True

def run(front_gap0, max_steps=400):
    # front_gap0: 차체 전단 -> 장애물 가까운 쪽 면(근접단) 거리 (§12 정의)
    obstacle_near_x = L + front_gap0          # 장애물 근접단(차량이 실제로 다가가는 면)
    obstacle_far_x = obstacle_near_x + L       # 장애물 먼 쪽 끝 (obstacle length = L 가정)
    obstacle_center_x = (obstacle_near_x + obstacle_far_x) / 2
    obstacle_y_range = (-B/2, B/2)             # 장애물 폭 = B(차체와 동일 풋프린트, §8)
    ob_poly = rect_corners(obstacle_center_x, 0.0, 0.0, L, B, rear_at_origin=False)

    x = y = psi = 0.0
    delta_prev = 0.0
    state = "KEEP_L2"
    cooldown_steps = int(round(0.3/DT))
    last_change_step = -cooldown_steps
    events = []
    collided_any = False
    finished = False
    settle_violation = False
    finish_step = None
    for step in range(1, max_steps+1):
        x_front = x + L*math.cos(psi)
        x_rear = x
        front_gap = max(0.0, obstacle_near_x - x_front) if not (obstacle_y_range[1] < y-B/2 or obstacle_y_range[0] > y+B/2) else 10.0
        right_clear = sensor_right_clear(x_rear, x_front, obstacle_near_x, obstacle_far_x, obstacle_y_range)
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
            time_ok = (step - last_change_step)*DT > T_KEEP_L1_MIN
            if time_ok and right_clear:
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
            finish_step = step
            # 관찰 20 step 추가
            for extra in range(1, 21):
                s2 = finish_step + extra
                err2 = 0.0 - y
                desired2 = max(-DELTA_MAX, min(DELTA_MAX, err2*200.0 - math.degrees(psi)*2.0))
                delta_cmd2 = max(delta_prev-RATE_PER_STEP, min(delta_prev+RATE_PER_STEP, desired2))
                delta_cmd2 = max(-DELTA_MAX, min(DELTA_MAX, delta_cmd2))
                delta_prev = delta_cmd2
                dr2 = math.radians(delta_cmd2)
                x += V*math.cos(psi)*DT
                y += V*math.sin(psi)*DT
                psi += (V/L)*math.tan(dr2)*DT
                if abs(y) > 0.15:
                    settle_violation = True
                step = s2
            break

    return events, collided_any, finished, finish_step, step, settle_violation

print(f"{'front_gap0':>10} | {'collided':>8} | {'finish_step':>11} | {'total(+20obs)':>13} | {'<=200?':>6} | {'settle_violation':>16}")
for fg0 in [0.5, 0.8, 1.2, 1.6, 2.0]:
    ev, col, fin, fstep, total_step, sv = run(fg0)
    ok200 = total_step <= 200
    print(f"{fg0:>10} | {col!s:>8} | {fstep!s:>11} | {total_step!s:>13} | {ok200!s:>6} | {sv!s:>16}")
    if not ok200:
        print(f"  *** 200 step 초과! fg0={fg0} 상세 이벤트:")
        for e in ev:
            print("   ", e)
