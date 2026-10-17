"""
2단계-A 재계산: 회전 사각형(차체 L x B, 헤딩 반영) vs 장애물 사각형(L x B) 충돌 판정으로
장애물 위치 하한(0.5m)의 실현 가능성을 다시 확인한다. baseline 코드가 아님(증명용 계산).
기존 코드 import 없음.
"""
import math

DT = 0.05
V = 0.5
L = 0.20      # 차체 길이 근사(후륜->전방), REQ-VEH-02
B = 0.15      # 차체 폭
RATE_PER_STEP = 200.0 * DT   # 10 deg/step
DELTA_MAX = 25.0
W = 0.30      # 차선폭 (L1 중심 y=0.30, 차선 경계 y=0.45가 L1 바깥쪽 한계)

def rect_corners(cx, cy, heading_rad, length, width, rear_at_origin=False):
    """cx,cy = 사각형이 놓이는 기준점(회전축). rear_at_origin=True면 기준점이 사각형의
    '뒤쪽 변 중앙'(차량 후륜), False면 사각형 중심."""
    if rear_at_origin:
        # local coords: x in [0, length], y in [-width/2, width/2]
        local = [(0, -width/2), (length, -width/2), (length, width/2), (0, width/2)]
    else:
        local = [(-length/2, -width/2), (length/2, -width/2), (length/2, width/2), (-length/2, width/2)]
    cos_h, sin_h = math.cos(heading_rad), math.sin(heading_rad)
    return [(cx + lx*cos_h - ly*sin_h, cy + lx*sin_h + ly*cos_h) for lx, ly in local]

def sat_overlap(poly1, poly2):
    """Separating Axis Theorem: 두 볼록다각형이 겹치면 True."""
    for poly in (poly1, poly2):
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i+1) % len(poly)]
            # edge normal
            nx, ny = -(y2-y1), (x2-x1)
            norm = math.hypot(nx, ny)
            if norm < 1e-12:
                continue
            nx, ny = nx/norm, ny/norm
            proj1 = [px*nx+py*ny for px, py in poly1]
            proj2 = [px*nx+py*ny for px, py in poly2]
            if max(proj1) < min(proj2) or max(proj2) < min(proj1):
                return False  # separating axis found -> no overlap
    return True

def max_left_extent(x, y, heading_rad, length, width):
    """차체 사각형(후륜 기준)의 좌측(y+) 최외곽 코너의 y좌표(차선 경계 y<=0.45 확인용)."""
    corners = rect_corners(x, y, heading_rad, length, width, rear_at_origin=True)
    return max(c[1] for c in corners)

def simulate(obstacle_center_x, controller="prop", target_y=0.30, max_steps=200, log=False):
    x = y = psi = 0.0
    delta_prev = 0.0
    collided = False
    max_left = -999
    trace = []
    ob_corners = rect_corners(obstacle_center_x, 0.0, 0.0, L, B, rear_at_origin=False)
    for step in range(1, max_steps+1):
        if controller == "prop":
            err = target_y - y
            desired = max(-DELTA_MAX, min(DELTA_MAX, err*200.0 - math.degrees(psi)*2.0))
        delta_cmd = max(delta_prev-RATE_PER_STEP, min(delta_prev+RATE_PER_STEP, desired))
        delta_cmd = max(-DELTA_MAX, min(DELTA_MAX, delta_cmd))
        delta_prev = delta_cmd
        dr = math.radians(delta_cmd)
        x += V*math.cos(psi)*DT
        y += V*math.sin(psi)*DT
        psi += (V/L)*math.tan(dr)*DT

        veh_corners = rect_corners(x, y, psi, L, B, rear_at_origin=True)
        if sat_overlap(veh_corners, ob_corners):
            collided = True
        left_ext = max_left_extent(x, y, psi, L, B)
        max_left = max(max_left, left_ext)
        if log:
            trace.append((step, step*DT, x, y, math.degrees(psi), delta_cmd, left_ext))
        # front of vehicle passed obstacle's far edge -> maneuver phase over
        front_x = x + L*math.cos(psi)
        if front_x > obstacle_center_x + L/2 + 0.3 and step > 5:
            break
    return collided, max_left, step, trace

def check_feasible(obstacle_center_x):
    collided, max_left, steps, _ = simulate(obstacle_center_x)
    lane_ok = max_left <= 0.45 + 1e-9
    return (not collided) and lane_ok, collided, max_left, steps

print("=== 해석 1: 후륜 기준 (X_obs = 장애물 중심의 절대좌표, t=0 후륜 위치가 원점) ===")
for X_obs in [0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1]:
    ok, collided, max_left, steps = check_feasible(X_obs)
    front_gap_t0 = (X_obs - L/2) - 0.0  # 후륜(0)과 장애물 근접단 사이, front_gap 정의는 아래서 별도 환산
    print(f"X_obs(장애물 중심, 후륜기준)={X_obs:.2f}  feasible={ok}  collided={collided}  max_left_y={max_left:.4f}  steps={steps}")

print()
print("=== 해석 2: 전단(차체 전방) 기준 — X_obs = t=0 시점 전단~장애물 근접단 거리(front_gap) ===")
for fg0 in [0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1]:
    # t=0 전단 위치 = L(전방 오프셋), 장애물 근접단 = L + fg0, 장애물 중심 = L + fg0 + L/2
    obstacle_center_x = L + fg0 + L/2
    ok, collided, max_left, steps = check_feasible(obstacle_center_x)
    print(f"front_gap(t=0)={fg0:.2f}  obstacle_center_x={obstacle_center_x:.2f}  feasible={ok}  collided={collided}  max_left_y={max_left:.4f}  steps={steps}")

print()
print("=== 이진 탐색으로 최소 feasible front_gap(t=0) 찾기 (해석 2 기준) ===")
lo, hi = 0.05, 0.6
for _ in range(30):
    mid = (lo+hi)/2
    obstacle_center_x = L + mid + L/2
    ok, *_ = check_feasible(obstacle_center_x)
    if ok:
        hi = mid
    else:
        lo = mid
print(f"최소 feasible front_gap(t=0) ~= {hi:.4f} m  (그 아래는 infeasible ~= {lo:.4f} m)")

print()
print("=== 이진 탐색으로 최소 feasible 장애물 중심 절대좌표 찾기 (해석 1 기준, X_obs 자체) ===")
lo, hi = 0.05, 0.6
for _ in range(30):
    mid = (lo+hi)/2
    ok, *_ = check_feasible(mid)
    if ok:
        hi = mid
    else:
        lo = mid
print(f"최소 feasible X_obs(후륜기준 절대좌표) ~= {hi:.4f} m  (infeasible ~= {lo:.4f} m)")
