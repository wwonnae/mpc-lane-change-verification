"""
RESULT_IMPROVED.md 검토(1번): "26개 조건 역전 0건 = 합산 증거" 서술 정정을 위한 재확인.
eval 커밋(4652e32)의 baseline 코드를 그대로 재실행(읽기 전용, improved 미수정)해 조건별
baseline 실패(충돌) seed 목록을 뽑고, 서로 다른 조건에 같은 seed가 얼마나 반복되는지
확인한다. S3는 seed가 아니라 결정론적 격자(cell index)라 별도 취급(seed 기반 조건과
합산하지 않음).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline.world import (
    generate_scenario, generate_left_obstacle_scenario,
    generate_scenario_custom_obstacle, generate_front_rear_scenario,
)
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.mpc import OSQPMPC

EVAL_SEEDS = list(range(100))
OUT = Path(__file__).resolve().parent / "out" / "eval_independent_evidence.json"


def failing_seeds(scenarios):
    mpc = OSQPMPC()
    fails = []
    for seed, sc in scenarios:
        r = run_episode(sc, mpc=mpc)
        if r.outcome == "충돌":
            fails.append(seed)
    return fails


def main():
    conditions = {}

    conditions["paper"] = failing_seeds([(s, generate_scenario(s)) for s in EVAL_SEEDS])

    for name, profile_key in [("S4_low", "low"), ("S4_medium", "medium"), ("S4_high", "high")]:
        from thesis_v2.baseline import sensors as base_sensors
        import numpy as np
        profile = base_sensors.NOISE_PROFILES[profile_key]
        ids = {"low": 1, "medium": 2, "high": 3}
        mpc = OSQPMPC()
        fails = []
        for s in EVAL_SEEDS:
            rng = np.random.default_rng((s, ids[profile_key]))
            r = run_episode(generate_scenario(s), mpc=mpc, noise_profile=profile, noise_rng=rng)
            if r.outcome == "충돌":
                fails.append(s)
        conditions[name] = fails

    for delay in (1, 2):
        mpc = OSQPMPC()
        fails = []
        for s in EVAL_SEEDS:
            r = run_episode(generate_scenario(s), mpc=mpc, control_delay_steps=delay)
            if r.outcome == "충돌":
                fails.append(s)
        conditions[f"S5_delay{delay}"] = fails

    for psi0 in (-15, -10, -5, 0, 5, 10, 15):
        conditions[f"S6_psi{psi0}"] = failing_seeds(
            [(s, generate_scenario(s, psi0_deg=float(psi0))) for s in EVAL_SEEDS])

    for length in (0.10, 0.15, 0.20, 0.30, 0.40):
        conditions[f"S7a_length{length:.2f}"] = failing_seeds(
            [(s, generate_scenario_custom_obstacle(s, obstacle_length=length)) for s in EVAL_SEEDS])
    for width in (0.075, 0.10, 0.20, 0.30):
        conditions[f"S7a_width{width:.3f}"] = failing_seeds(
            [(s, generate_scenario_custom_obstacle(s, obstacle_width=width)) for s in EVAL_SEEDS])

    for rear_gap in (0.1, 0.3, 0.5, 1.0):
        conditions[f"S7b_reargap{rear_gap:.1f}"] = failing_seeds(
            [(s, generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap)) for s in EVAL_SEEDS])

    all_seeds = set()
    for name, seeds in conditions.items():
        all_seeds |= set(seeds)

    per_seed_conditions = {seed: [name for name, seeds in conditions.items() if seed in seeds]
                            for seed in sorted(all_seeds)}

    out = {
        "conditions": {k: v for k, v in conditions.items()},
        "n_conditions": len(conditions),
        "n_distinct_seeds_failing_somewhere": len(all_seeds),
        "distinct_failing_seeds": sorted(all_seeds),
        "per_seed_conditions": per_seed_conditions,
        "naive_sum_of_counts": sum(len(v) for v in conditions.values()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("조건별 baseline 충돌 seed:")
    for k, v in conditions.items():
        print(f"  {k}: {v}")
    print()
    print("naive_sum_of_counts(중복 포함 단순합):", out["naive_sum_of_counts"])
    print("distinct seeds(중복 제외):", out["n_distinct_seeds_failing_someven" if False else "n_distinct_seeds_failing_somewhere"], "=", out["n_distinct_seeds_failing_somewhere"])
    print("seed별 실패 조건 수:")
    for seed, conds in per_seed_conditions.items():
        print(f"  seed={seed}: {len(conds)}개 조건 {conds}")


if __name__ == "__main__":
    main()
