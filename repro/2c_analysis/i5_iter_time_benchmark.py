"""
DESIGN_IMPROVED_V2.md I5(반복 상한 방식) 설계용: 참고 호스트에서 I1+I1b+I2'(1회차 최종
조합, I3 포함) QP의 "반복 1회당 시간"을 측정해 시간 예산(5/10/20/30ms) -> 반복 상한을
계산으로 결정하기 위한 벤치마크. thesis_v2/improved/ 코드는 전혀 수정하지 않고(이 시점
아직 I5 미구현), ImprovedMPC.prob.solve를 읽기 전용으로 감싸(monkeypatch, 이 스크립트
안에서만) 매 호출의 (iter, run_time)을 기록한다.

표본: paper dev seed(100~199, 평상시 케이스) + S6 psi0=+-15 dev seed(1000~1099, 1회차에서
max_iter가 가장 많이 나온 어려운 케이스) + S7a width=0.20 dev seed(1000~1099, 마찬가지로
어려운 케이스) -- 쉬운 케이스와 어려운 케이스를 함께 포함해 p99가 "어려운 반복" 쪽을
대표하게 한다.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline.world import generate_scenario, generate_scenario_custom_obstacle
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

FINAL_COMBO = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                    i2_variant="narrow")

DEV_PAPER_SEEDS = list(range(100, 200))
DEV_S6_SEEDS = list(range(1000, 1100))
DEV_S7A_SEEDS = list(range(1000, 1100))


def instrument(mpc: ImprovedMPC):
    calls = []
    orig_solve = mpc.prob.solve

    def wrapped(*args, **kwargs):
        res = orig_solve(*args, **kwargs)
        calls.append((int(res.info.iter), float(res.info.run_time), res.info.status))
        return res

    mpc.prob.solve = wrapped
    return calls


def main():
    mpc = ImprovedMPC(**FINAL_COMBO)
    calls = instrument(mpc)

    t0 = time.perf_counter()
    for s in DEV_PAPER_SEEDS:
        improved_run_episode(generate_scenario(s), mpc=mpc)
    for s in DEV_S6_SEEDS:
        improved_run_episode(generate_scenario(s, psi0_deg=-15.0), mpc=mpc)
        improved_run_episode(generate_scenario(s, psi0_deg=15.0), mpc=mpc)
    for s in DEV_S7A_SEEDS:
        improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=0.20), mpc=mpc)
    t1 = time.perf_counter()

    iters = np.array([c[0] for c in calls])
    run_time_ms = np.array([c[1] for c in calls]) * 1000.0
    mask = iters > 0
    per_iter_ms = run_time_ms[mask] / iters[mask]

    def pct(a, p):
        return float(np.percentile(a, p)) if len(a) else None

    stats = {
        "n_solve_calls": len(calls),
        "n_calls_iter_gt_0": int(mask.sum()),
        "wall_time_sec": t1 - t0,
        "iter": {
            "mean": float(np.mean(iters)), "p50": pct(iters, 50), "p95": pct(iters, 95),
            "p99": pct(iters, 99), "max": int(np.max(iters)),
        },
        "run_time_ms": {
            "mean": float(np.mean(run_time_ms)), "p50": pct(run_time_ms, 50),
            "p95": pct(run_time_ms, 95), "p99": pct(run_time_ms, 99),
            "max": float(np.max(run_time_ms)),
        },
        "per_iter_time_ms": {
            "mean": float(np.mean(per_iter_ms)), "p50": pct(per_iter_ms, 50),
            "p95": pct(per_iter_ms, 95), "p99": pct(per_iter_ms, 99),
            "max": float(np.max(per_iter_ms)),
        },
        "status_counts": {},
    }
    for c in calls:
        stats["status_counts"][c[2]] = stats["status_counts"].get(c[2], 0) + 1

    per_iter_p99 = stats["per_iter_time_ms"]["p99"]
    candidates = {}
    for budget_ms in (5, 10, 20, 30):
        candidates[f"budget_{budget_ms}ms"] = {
            "budget_ms": budget_ms,
            "max_iter_candidate": int(budget_ms / per_iter_p99),
        }
    stats["max_iter_candidates"] = candidates

    out = Path(__file__).resolve().parent / "out" / "i5_iter_time_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
