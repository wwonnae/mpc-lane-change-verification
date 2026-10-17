"""
S6 psi0=-15deg(seed=6) 불가능 증명 재검증 -- step 0(진짜 초기조건)부터 다시 계산.
읽기 전용, baseline 미수정. vehicle.step(실제 비선형 모델)·config만 재사용
(avoidance_feasibility_recheck.py와 같은 원칙: rate limit 포함 실제 물리로 재현).

1) step 0~3 표: 실제 에피소드 로그에서 상태/제어경로/ey_line/y/psi/delta_cmd/delta_final 추출
2) step 0(y0,psi0)부터, 실제 제약(|delta|<=25deg, rate limit 10deg/step, 초기 delta_prev=0)
   하의 "이론상 최선"(매 step 가능한 한 빨리 +25deg로 램프업) 궤적으로 15 step 안에
   위치제약(KEEP_L2, |y|<=0.15)을 지킬 수 있는지 확인. 실제 v 스케줄 반영(REQ-SPD-01:
   step 1은 v0, step 2부터 V_MAX -- vehicle_step의 실제 동작과 동일).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config
from thesis_v2.baseline.vehicle import VehicleState, step as vehicle_step
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.mpc import OSQPMPC

SEED = 6
PSI0_DEG = -15.0


def print_step0_3_table():
    scenario = generate_scenario(SEED, psi0_deg=PSI0_DEG)
    print(f"step0(초기조건): y0={scenario.y0:.5f} psi0_deg={scenario.psi0_deg:.3f} "
          f"v0={scenario.v0:.5f}")
    mpc = OSQPMPC()
    result = run_episode(scenario, mpc=mpc)
    print(f"{'step':>4} {'state':>10} {'path':>11} {'ey_line':>8} {'y':>10} {'psi_deg':>9} "
          f"{'delta_cmd':>10} {'delta_final':>11} {'solver':>18} {'fallback':>8}")
    for i in range(4):
        row = result.logger.rows[i]
        path = "line_follow" if row["solver_status"] == "N/A" else "mpc"
        ey = row["ey_line"]
        ey_str = f"{ey:.4f}" if ey is not None else "None"
        print(f"{i+1:>4} {row['state']:>10} {path:>11} {ey_str:>8} {row['y']:>10.5f} "
              f"{row['psi']*180/math.pi:>9.3f} {row['delta_mpc_raw']:>10.4f} "
              f"{row['delta_final']:>11.4f} {row['solver_status']:>18} "
              f"{str(bool(row['fallback_used'])):>8}")
    return scenario


def best_case_from_step0(scenario):
    """실제 제약 하 이론상 최선: 매 step 가능한 한 빨리 +25deg로 램프업(10deg/step),
    실제 비선형 vehicle.step + 실제 v 스케줄(REQ-SPD-01) 사용."""
    state = VehicleState(x=0.0, y=scenario.y0, psi=math.radians(scenario.psi0_deg), v=scenario.v0)
    delta_prev = 0.0
    rate = config.DELTA_RATE_MAX_PER_STEP_DEG  # 10 deg/step
    dmax = config.DELTA_MAX_DEG  # 25 deg
    lo, hi = config.POSITION_CONSTRAINTS["KEEP_L2"]
    rows = []
    violated = False
    for step in range(1, 16):
        delta_cmd = min(delta_prev + rate, dmax)  # 초기 0에서 최대한 빨리 +25로 램프업
        delta_prev = delta_cmd
        v_cmd = config.V_MAX  # REQ-SPD-01: KEEP_L2(비-SAFE_STOP)는 항상 V_MAX
        state = vehicle_step(state, delta_cmd, v_cmd, config.DT)
        ok = lo <= state.y <= hi
        if not ok:
            violated = True
        rows.append((step, state.y, math.degrees(state.psi), delta_cmd, ok))
    return rows, violated


def main():
    scenario = print_step0_3_table()
    print()
    print("=== step 0(y0,psi0)부터 실제 제약(|delta|<=25, rate limit 10/step, delta_prev=0) "
          "하 이론상 최선 궤적, 15 step ===")
    rows, violated = best_case_from_step0(scenario)
    for step, y, psi_deg, delta_cmd, ok in rows:
        print(f"step={step:2d} y={y:9.5f} psi_deg={psi_deg:8.3f} delta_cmd={delta_cmd:6.2f} "
              f"ok(|y|<=0.15)={ok}")
    print()
    print("결론:", "step 0부터 이미 불가능(위반 발생)" if violated
          else "step 0부터는 가능(위반 없음) -- 실제로는 다른 원인으로 infeasible 발생")


if __name__ == "__main__":
    main()
