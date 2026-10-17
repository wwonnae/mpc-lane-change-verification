"""
2단계-C 결과 분석 (1): 이미 실행된 4개 결과 폴더(paper/left_obstacle x 배터리/AC)의
summary.json에 없는 지표를 원본 steps.npz/episodes.json에서 사후 집계한다.

- QP 실패 수, fallback 사용 수 (시나리오별 합계)
- 계산시간 p50/p95/p99, 최댓값이 발생한 step·에피소드(seed)·상태, 그 episode의 첫 MPC
  호출 여부
- left_obstacle 시나리오의 "기대 결과(SAFE_STOP) 달성률" (thesis_v2.baseline.summary의
  EXPECTED_OUTCOME 정책을 그대로 재사용 -- 판정 기준 이중화 방지)

주의: 원본 결과 폴더(steps.npz, episodes.json, env.json)는 수정하지 않는다(읽기 전용 분석).
baseline 코드(thesis_v2/baseline/)는 수정하지 않는다 -- 이 스크립트는 순수 분석 스크립트.

사용(저장소 루트에서): .venv\\Scripts\\python.exe repro\\2c_analysis\\missing_metrics.py
("2c_analysis"는 숫자로 시작해 `-m` 패키지 경로로 못 씀 -- 직접 경로 실행 + sys.path 보정)
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from thesis_v2.baseline.summary import EXPECTED_OUTCOME

RESULTS_DIR = Path(__file__).resolve().parents[2] / "thesis_v2" / "results"
OUT_DIR = Path(__file__).resolve().parent / "out"

FOLDERS = [
    ("20260917_221415_DESKTOP-MDCKRJS_baseline_P", "paper"),
    ("20260917_221418_DESKTOP-MDCKRJS_baseline_P_leftobs", "left_obstacle"),
    ("20260917_221615_DESKTOP-MDCKRJS_baseline_P_AC", "paper"),
    ("20260917_221618_DESKTOP-MDCKRJS_baseline_P_leftobs_AC", "left_obstacle"),
]


def _load_episodes(folder: Path, scenario: str):
    with open(folder / f"{scenario}_episodes.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _max_call_info(folder: Path, scenario: str, episodes: list):
    best = None  # (t_ms, seed, idx0based, t, state)
    for ep in episodes:
        seed = ep["seed"]
        npz = np.load(folder / f"{scenario}_seed{seed}_steps.npz", allow_pickle=True)
        times = npz["t_mpc_solve_ms"]
        states = npz["state"]
        ts = npz["t"]
        idx = int(np.argmax(times))
        t_ms = float(times[idx])
        if best is None or t_ms > best[0]:
            best = (t_ms, seed, idx, float(ts[idx]), str(states[idx]), times)
    if best is None:
        return None
    t_ms, seed, idx, t, state, times = best
    nonzero_idx = np.nonzero(times > 0.0)[0]
    first_idx = int(nonzero_idx[0]) if len(nonzero_idx) > 0 else None
    return {
        "t_mpc_solve_ms": t_ms, "seed": seed, "step": idx + 1, "t": t, "state": state,
        "is_first_mpc_call_of_episode": (first_idx == idx),
    }


def analyze_folder(folder_name: str, scenario: str) -> dict:
    folder = RESULTS_DIR / folder_name
    episodes = _load_episodes(folder, scenario)
    n = len(episodes)

    solver_fail_total = sum(ep["solver_fail_count"] for ep in episodes)
    fallback_total = sum(ep["fallback_count"] for ep in episodes)

    all_times = []
    for ep in episodes:
        npz = np.load(folder / f"{scenario}_seed{ep['seed']}_steps.npz", allow_pickle=True)
        times = npz["t_mpc_solve_ms"]
        all_times.extend(times[times > 0.0].tolist())

    if all_times:
        arr = np.array(all_times)
        p50, p95, p99 = np.percentile(arr, [50, 95, 99])
        mean, mx = float(arr.mean()), float(arr.max())
    else:
        p50 = p95 = p99 = mean = mx = None

    max_info = _max_call_info(folder, scenario, episodes)

    outcome_counts = {}
    for ep in episodes:
        outcome_counts[ep["outcome"]] = outcome_counts.get(ep["outcome"], 0) + 1
    expected = EXPECTED_OUTCOME.get(scenario)
    expected_rate = (outcome_counts.get(expected, 0) / n) if (n and expected) else None

    return {
        "folder": folder_name,
        "scenario": scenario,
        "n_episodes": n,
        "solver_fail_total": solver_fail_total,
        "fallback_total": fallback_total,
        "outcome_counts": outcome_counts,
        "expected_outcome": expected,
        "expected_outcome_achievement_rate": expected_rate,
        "mpc_solve_time_ms": {
            "mean": mean, "p50": p50, "p95": p95, "p99": p99, "max": mx,
            "n_calls": len(all_times),
        },
        "max_call_info": max_info,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for folder_name, scenario in FOLDERS:
        report = analyze_folder(folder_name, scenario)
        reports.append(report)
        print(f"=== {folder_name} ({scenario}) ===")
        print(f"  n_episodes={report['n_episodes']} solver_fail_total={report['solver_fail_total']} "
              f"fallback_total={report['fallback_total']}")
        print(f"  outcome_counts={report['outcome_counts']}")
        print(f"  expected_outcome={report['expected_outcome']} "
              f"achievement_rate={report['expected_outcome_achievement_rate']}")
        m = report["mpc_solve_time_ms"]
        print(f"  mpc_ms mean={m['mean']:.4f} p50={m['p50']:.4f} p95={m['p95']:.4f} "
              f"p99={m['p99']:.4f} max={m['max']:.4f} (n_calls={m['n_calls']})")
        print(f"  max_call_info={report['max_call_info']}")
        print()

    out_path = OUT_DIR / "missing_metrics_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
