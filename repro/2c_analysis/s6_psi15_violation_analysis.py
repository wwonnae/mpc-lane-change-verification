"""
S6 psi0=-15deg y 제약 위반 분석 (읽기 전용, ROBUSTNESS_PLAN.md 검토 항목 1).
baseline 코드는 수정하지 않는다 -- generate_scenario(seed, psi0_deg=-15.0)로 재실행해
step별 로그(logger.rows)에서 y 위반 스텝을 뽑는다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config, metrics
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.fsm import FSMState

OUT = Path(__file__).resolve().parent / "out" / "s6_psi15_violations.json"


def main():
    mpc = OSQPMPC()
    violations = []
    scenario_info = {}
    for seed in range(100):
        scenario = generate_scenario(seed, psi0_deg=-15.0)
        scenario_info[seed] = {"v0": scenario.v0, "y0": scenario.y0,
                                "front_gap0_x_near": scenario.obstacles[0].x_near}
        result = run_episode(scenario, mpc=mpc)
        for i, row in enumerate(result.logger.rows):
            step = i + 1
            state_str = row["state"]
            y = row["y"]
            if state_str == FSMState.SAFE_STOP.value:
                continue  # 위치제약 미정의(REQ-LAT-05)
            lo, hi = config.POSITION_CONSTRAINTS[state_str]
            ok = (lo - metrics.TOL_Y_M) <= y <= (hi + metrics.TOL_Y_M)
            if not ok:
                violations.append({
                    "seed": seed, "step": step, "state": state_str, "y": y,
                    "bound_lo": lo, "bound_hi": hi,
                    "solver_status": row["solver_status"],
                    "fallback_used": bool(row["fallback_used"]),
                    "delta_mpc_raw": row["delta_mpc_raw"],
                    "delta_final": row["delta_final"],
                    "psi_deg": row["psi"] * 180.0 / 3.141592653589793,
                    "v0": scenario.v0, "y0": scenario.y0,
                })

    seeds_with_violation = sorted(set(v["seed"] for v in violations))
    out = {
        "n_violation_steps": len(violations),
        "n_episodes_with_violation": len(seeds_with_violation),
        "seeds_with_violation": seeds_with_violation,
        "violations": violations,
        "scenario_info_for_violated_seeds": {s: scenario_info[s] for s in seeds_with_violation},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "violations"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
