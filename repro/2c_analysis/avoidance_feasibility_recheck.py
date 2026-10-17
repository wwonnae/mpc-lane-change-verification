"""
2단계-C 재검토: seed=85 충돌 원인 재분류를 위한 "최대 조향 노력(bang-bang)" 회피 가능성
재계산. 사용자 수기 검산(델타<=25도, 10도/step, 회전 사각형, 차선경계 0.45, 초기 psi=0)을
독립적으로 재현·검증한다. baseline 로직(FSM/MPC/lateral 등)은 전혀 쓰지 않고, 실제
물리(vehicle.step)·충돌판정(collision.check_collision)·상수(config)만 그대로 재사용한다
(baseline 코드 수정 없음, 읽기 전용 재사용).

정책: 항상 delta_desired=+25deg(최대 좌회전, 10deg/step 레이트 제한만 적용) -- 목표
추종이 전혀 없는 순수 최대노력 정책이라, MPC(REQ-MPC-02 비용함수 기반, 헤딩 가중치로
완만해짐)보다 훨씬 공격적인 상한(best-case) 회피 궤적이다.

사용(저장소 루트에서): .venv\\Scripts\\python.exe repro\\2c_analysis\\avoidance_feasibility_recheck.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config
from thesis_v2.baseline.vehicle import VehicleState, step as vehicle_step
from thesis_v2.baseline.collision import check_collision
from thesis_v2.baseline.world import Obstacle
from thesis_v2.baseline.world import generate_scenario

LANE_BOUND_HI = 0.45  # "차선 변경 구간" 위치제약 상한(REQ-MPC-05)
MAX_STEPS = 400


def _make_obstacle(front_gap0: float) -> Obstacle:
    x_near = config.L + front_gap0
    return Obstacle(x_near=x_near, x_far=x_near + config.L,
                     y_lo=-config.B / 2, y_hi=config.B / 2)


def bang_bang_collision(front_gap0: float, y0: float, v: float, psi0_deg: float = 0.0):
    """최대노력(+25deg, rate limit만 적용) 정책으로 시뮬레이션, 장애물과 한 번이라도
    겹치면 True(충돌). 차선경계(0.45) 도달 시에도 계속 최대조향 유지(상한선 확인용,
    도달 여부는 별도로 기록)."""
    obstacle = _make_obstacle(front_gap0)
    state = VehicleState(x=0.0, y=y0, psi=math.radians(psi0_deg), v=v)
    delta_prev = 0.0
    hit_lane_bound = False
    collided = False
    trace = []
    for step in range(1, MAX_STEPS + 1):
        desired = config.DELTA_MAX_DEG  # 항상 최대 좌회전(+y 방향, 목표추종 없는 순수 bang-bang)
        rate = config.DELTA_RATE_MAX_PER_STEP_DEG
        delta_cmd = max(delta_prev - rate, min(delta_prev + rate, desired))
        delta_cmd = max(-config.DELTA_MAX_DEG, min(config.DELTA_MAX_DEG, delta_cmd))
        delta_prev = delta_cmd
        state = vehicle_step(state, delta_cmd, v, config.DT)
        trace.append((step, state.x, state.y, math.degrees(state.psi), delta_cmd))
        if state.y >= LANE_BOUND_HI:
            hit_lane_bound = True
        if check_collision(state, [obstacle]):
            collided = True
            break
        if state.x > obstacle.x_far + 0.5:
            break  # 완전히 지나침, 더 볼 필요 없음
    return collided, hit_lane_bound, trace


def min_feasible_front_gap(y0: float, v: float, psi0_deg: float = 0.0,
                            lo: float = 0.0, hi: float = 1.0, tol: float = 1e-4) -> float:
    """이분탐색으로 '충돌 없이 회피 가능한 최소 front_gap0'을 찾는다.
    hi는 반드시 feasible(충돌없음)이어야 하고, lo는 반드시 infeasible(충돌)이어야 한다."""
    collided_hi, _, _ = bang_bang_collision(hi, y0, v, psi0_deg)
    if collided_hi:
        raise ValueError(f"hi={hi}도 충돌함 -- 탐색 상한을 늘려야 함(y0={y0}, v={v})")
    collided_lo, _, _ = bang_bang_collision(lo, y0, v, psi0_deg)
    if not collided_lo:
        return lo  # lo에서 이미 feasible
    while hi - lo > tol:
        mid = (lo + hi) / 2
        collided, _, _ = bang_bang_collision(mid, y0, v, psi0_deg)
        if collided:
            lo = mid
        else:
            hi = mid
    return hi


def main():
    print("=== 1) 사용자 수기 검산 재현: y0 스윕 (v=0.5, REQ-SPD-01 worst-case, psi0=0) ===")
    print("PDF/코드 원칙과 동일하게 v=V_MAX=0.5 고정(다른 2a_feasibility 스크립트와 동일 관례).")
    for y0 in [0.0, -0.046, -0.10, -0.15]:
        min_fg = min_feasible_front_gap(y0, v=config.V_MAX)
        print(f"  y0={y0:+.3f}: 최소 feasible front_gap0 = {min_fg:.4f} m")
    print()

    print("=== 2) seed=85 실제 초기조건으로 직접 검증(v0·y0·psi0 전부 실측값) ===")
    sc85 = generate_scenario(85)
    y0_85 = sc85.y0
    v0_85 = sc85.v0
    psi0_85 = sc85.psi0_deg
    fg0_85 = sc85.obstacles[0].x_near - config.L
    min_fg_85 = min_feasible_front_gap(y0_85, v=v0_85, psi0_deg=psi0_85)
    collided_at_actual, hit_bound, _ = bang_bang_collision(fg0_85, y0_85, v0_85, psi0_85)
    print(f"  seed85 실제: y0={y0_85:.4f} v0={v0_85:.4f} psi0={psi0_85:.4f} "
          f"front_gap0(실제)={fg0_85:.4f}")
    print(f"  이 초기조건에서 최소 feasible front_gap0 = {min_fg_85:.4f} m")
    print(f"  실제 front_gap0({fg0_85:.4f})으로 bang-bang 시뮬레이션 시 충돌 여부 = {collided_at_actual}")
    print(f"  (참고) 최대노력 궤적이 차선경계 0.45 도달 여부 = {hit_bound}")
    print(f"  => 여유(margin) = 실제({fg0_85:.4f}) - 최소필요({min_fg_85:.4f}) = "
          f"{fg0_85 - min_fg_85:.4f} m")
    print()
    print("결론: 실제 front_gap0이 '최소 feasible' 값보다 크면(margin>0), 최대노력(bang-bang)")
    print("정책으로는 seed=85도 회피 가능한 궤적이 존재함 -- 즉 '논문 로직상(물리적으로) 불가피")
    print("한 충돌'이 아니라, MPC가 그 여유를 다 쓰지 않는 제어기 설계(비용함수) 문제임을 의미.")

    return {
        "y0_sweep": {
            str(y0): min_feasible_front_gap(y0, v=config.V_MAX)
            for y0 in [0.0, -0.046, -0.10, -0.15]
        },
        "seed85": {
            "y0": y0_85, "v0": v0_85, "psi0_deg": psi0_85, "front_gap0_actual": fg0_85,
            "min_feasible_front_gap0": min_fg_85,
            "collided_at_actual_front_gap": collided_at_actual,
            "hit_lane_bound_0_45": hit_bound,
            "margin_m": fg0_85 - min_fg_85,
        },
    }


if __name__ == "__main__":
    import json
    result = main()
    out_dir = Path(__file__).resolve().parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "avoidance_feasibility_recheck.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nsaved: {out_dir / 'avoidance_feasibility_recheck.json'}")
