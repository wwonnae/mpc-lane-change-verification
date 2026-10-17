"""
golden 기준 데이터 생성(교차 환경 재현성, SETTINGS_DECISION.md §18). 사람이 baseline을
의도적으로 바꾼 뒤에만 수동으로 재실행합니다 -- 결과를 보고 baseline을 바꾸지 않는다는
원칙(repro/docs/WORK_RULES.md 금지 목록)과 마찬가지로, golden도 "결과가 다르니 golden을 바꾼다"의 방향이
아니라 "코드를 의도적으로 바꿨으니 새 기준을 세운다"의 방향으로만 갱신합니다.

사용: python -m thesis_v2.tests.golden.generate_golden
"""
import json
import math
from pathlib import Path

from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.world import generate_scenario, generate_left_obstacle_scenario

_DEG2RAD = math.pi / 180.0

SCENARIOS = {
    "paper": generate_scenario,
    "left_obstacle": generate_left_obstacle_scenario,
}
SEEDS = [0, 1, 2]

GOLDEN_DIR = Path(__file__).parent


def _episode_to_golden(result) -> dict:
    rows = result.logger.rows
    return {
        "seed": result.seed,
        "scenario_name": result.scenario_name,
        "outcome": result.outcome,
        "finish_step": result.finish_step,
        "total_steps": result.total_steps,
        "transitions": [f"{tr.from_state}->{tr.to_state}@{tr.step}" for tr in result.transitions],
        "final_state": {
            "x": rows[-1]["x"], "y": rows[-1]["y"],
            "psi": rows[-1]["psi"], "v": rows[-1]["v"],
        } if rows else None,
        "delta_final_rad": [row["delta_final"] * _DEG2RAD for row in rows],
    }


def main():
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for scenario_name, gen in SCENARIOS.items():
        for seed in SEEDS:
            scenario = gen(seed)
            result = run_episode(scenario)
            golden = _episode_to_golden(result)
            path = GOLDEN_DIR / f"{scenario_name}_seed{seed}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(golden, f, ensure_ascii=False, indent=2)
            print(f"wrote {path}")

    env_path = GOLDEN_DIR / "env.json"
    with open(env_path, "w", encoding="utf-8") as f:
        json.dump(collect_env_info(), f, ensure_ascii=False, indent=2, default=str)
    print(f"wrote {env_path}")


if __name__ == "__main__":
    main()
