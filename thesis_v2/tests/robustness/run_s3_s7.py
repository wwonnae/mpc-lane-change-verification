"""
S3~S7 강건성 검증 실행 ([발전], ROBUSTNESS_PLAN.md). 승인됨(2026-09-22).

논문 정합 결과(paper/left_obstacle)와 완전히 분리된 별도 트랙이다 -- 여기서 나오는
성공률·충돌률 등은 RESULT_BASELINE.md의 100 에피소드 결과와 합산하지 않는다.

baseline(thesis_v2/baseline/) 제어 로직은 이 스크립트로 수정하지 않는다. world.py/
sensors.py/runner.py에 이미 추가된 옵션(generate_grid_scenario 등, NoiseProfile,
control_delay_steps)만 사용한다.

사용(저장소 루트에서): python -m thesis_v2.tests.robustness.run_s3_s7 --out-root thesis_v2/results/<ts>_<host>_baseline_v1.1
"""
import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

from thesis_v2.baseline import config, sensors
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.runner import run_episode, EpisodeResult
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.baseline import world

SEEDS_100 = list(range(100))


def _fmt_ci(k: int, n: int) -> str:
    if n == 0:
        return "n=0"
    ci = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {ci['lo']*100:.1f}~{ci['hi']*100:.1f}%)"


def aggregate(results: List[EpisodeResult]) -> Dict:
    n = len(results)
    n_success = sum(1 for r in results if r.outcome == "성공")
    n_collision = sum(1 for r in results if r.outcome == "충돌")
    n_safe_stop = sum(1 for r in results if r.outcome == "SAFE_STOP")
    n_departure = sum(1 for r in results if r.observed_transition_departure)
    outcome_counts: Dict[str, int] = {}
    for r in results:
        outcome_counts[r.outcome] = outcome_counts.get(r.outcome, 0) + 1

    delta_violation = sum(r.delta_violation_count for r in results)
    delta_checked = sum(r.delta_checked_count for r in results)
    psi_violation = sum(r.psi_violation_count for r in results)
    y_violation = sum(r.y_violation_count for r in results)
    y_checked = sum(r.y_checked_count for r in results)

    stop_gaps = []
    for r in results:
        if r.outcome == "SAFE_STOP" and r.finish_step:
            row = r.logger.rows[r.finish_step - 1]
            stop_gaps.append(row["front_gap"])

    return {
        "n_episodes": n,
        "outcome_counts": outcome_counts,
        "collision_rate_formatted": _fmt_ci(n_collision, n),
        "success_rate_formatted": _fmt_ci(n_success, n),
        "safe_stop_count": n_safe_stop,
        "observed_transition_departure_count": n_departure,
        "delta_within_tolerance_rate": (1 - delta_violation / delta_checked) if delta_checked else None,
        "psi_within_tolerance_rate": (1 - psi_violation / delta_checked) if delta_checked else None,
        "y_within_tolerance_rate": (1 - y_violation / y_checked) if y_checked else None,
        "stop_gap_mean": (sum(stop_gaps) / len(stop_gaps)) if stop_gaps else None,
        "stop_gap_min": min(stop_gaps) if stop_gaps else None,
        "stop_gap_note": "해당없음(SAFE_STOP 미발생)" if not stop_gaps else None,
    }


def run_s3(out_dir: Path, mpc: OSQPMPC) -> Dict:
    """S3: front_gap0 x y0 결정론적 격자, v0=V_MAX, psi0=0."""
    front_gaps = np.round(np.arange(0.50, 2.0001, 0.05), 4)
    y0s = np.round(np.arange(-0.15, 0.1501, 0.01), 4)
    grid_outcome = np.empty((len(front_gaps), len(y0s)), dtype=object)
    n_fail = 0
    for i, fg0 in enumerate(front_gaps):
        for j, y0 in enumerate(y0s):
            scenario = world.generate_grid_scenario(float(fg0), float(y0))
            result = run_episode(scenario, mpc=mpc)
            grid_outcome[i, j] = result.outcome
            if result.outcome != "성공":
                n_fail += 1
    total = len(front_gaps) * len(y0s)
    fail_ratio = n_fail / total

    # 히트맵
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 그림에는 영문 라벨만 사용(폰트에 한글 글리프가 없어 깨짐) -- JSON(s3_grid.json)에는
    # 원래 한글 outcome 문자열 그대로 저장됨(이 매핑은 표시 전용).
    _EN = {"성공": "success", "충돌": "collision", "SAFE_STOP": "SAFE_STOP",
           "타임아웃": "timeout", "미정착": "unsettled", "관찰 중 상태 이탈": "departure_in_observe"}
    outcome_labels = sorted(set(grid_outcome.flatten()))
    label_to_idx = {lab: k for k, lab in enumerate(outcome_labels)}
    numeric = np.vectorize(lambda v: label_to_idx[v])(grid_outcome)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(numeric.T, origin="lower", aspect="auto",
                    extent=[front_gaps[0], front_gaps[-1], y0s[0], y0s[-1]],
                    cmap="tab10")
    ax.set_xlabel("front_gap0 (m)")
    ax.set_ylabel("y0 (m)")
    ax.set_title(f"S3 boundary map (fail ratio={fail_ratio:.3f}, n={total})")
    cbar = fig.colorbar(im, ticks=list(label_to_idx.values()))
    cbar.ax.set_yticklabels([_EN.get(lab, lab) for lab in outcome_labels])
    fig.tight_layout()
    heatmap_path = out_dir / "s3_heatmap.png"
    fig.savefig(heatmap_path, dpi=120)
    plt.close(fig)

    grid_json = {
        "front_gap0_values": front_gaps.tolist(),
        "y0_values": y0s.tolist(),
        "outcome_grid": grid_outcome.tolist(),  # [i][j] = front_gaps[i], y0s[j]
        "n_total": total,
        "n_fail": n_fail,
        "fail_ratio": fail_ratio,
        "v0_fixed": config.V_MAX,
        "psi0_fixed_deg": 0.0,
    }
    with open(out_dir / "s3_grid.json", "w", encoding="utf-8") as f:
        json.dump(grid_json, f, ensure_ascii=False, indent=2)

    return {
        "n_cells": total,
        "n_fail": n_fail,
        "fail_ratio": fail_ratio,
        "heatmap_path": str(heatmap_path),
        "grid_json_path": str(out_dir / "s3_grid.json"),
    }


_S4_PROFILE_IDS = {"low": 1, "medium": 2, "high": 3}  # np.random.default_rng seed 조합용(정수만 허용)


def run_s4(out_dir: Path, mpc: OSQPMPC) -> Dict:
    """S4: 센서 노이즈 3단계, paper 기반 seed 0~99."""
    out = {}
    for name, profile in sensors.NOISE_PROFILES.items():
        results = []
        for seed in SEEDS_100:
            scenario = world.generate_scenario(seed)
            noise_rng = np.random.default_rng((seed, _S4_PROFILE_IDS[name]))
            result = run_episode(scenario, mpc=mpc, noise_profile=profile, noise_rng=noise_rng)
            results.append(result)
        out[name] = aggregate(results)
    return out


def run_s5(out_dir: Path, mpc: OSQPMPC) -> Dict:
    """S5: 제어 지연 1/2 step, paper 기반 seed 0~99."""
    out = {}
    for delay in (1, 2):
        results = [run_episode(world.generate_scenario(seed), mpc=mpc, control_delay_steps=delay)
                   for seed in SEEDS_100]
        out[f"delay_{delay}step"] = aggregate(results)
    return out


def run_s6(out_dir: Path, mpc: OSQPMPC) -> Dict:
    """S6: 초기 헤딩 오차 -15~15deg(5deg 간격), paper 기반 seed 0~99."""
    out = {}
    for psi0 in (-15, -10, -5, 0, 5, 10, 15):
        results = [run_episode(world.generate_scenario(seed, psi0_deg=float(psi0)), mpc=mpc)
                   for seed in SEEDS_100]
        out[f"psi0_{psi0}deg"] = aggregate(results)
    return out


def run_s7a(out_dir: Path, mpc: OSQPMPC) -> Dict:
    """S7a: 장애물 크기 변화(길이 스윕, 폭 스윕), paper 기반 seed 0~99."""
    out = {}
    for length in (0.10, 0.15, 0.20, 0.30, 0.40):
        results = [run_episode(world.generate_scenario_custom_obstacle(seed, obstacle_length=length),
                                mpc=mpc) for seed in SEEDS_100]
        out[f"length_{length:.2f}m"] = aggregate(results)
    for width in (0.075, 0.10, 0.20, 0.30):  # 0.15(baseline)는 길이 스윕에 이미 포함
        results = [run_episode(world.generate_scenario_custom_obstacle(seed, obstacle_width=width),
                                mpc=mpc) for seed in SEEDS_100]
        out[f"width_{width:.3f}m"] = aggregate(results)
    return out


def run_s7b(out_dir: Path, mpc: OSQPMPC) -> Dict:
    """S7b: 전방 고정(1.0m) + 후방 장애물 rear_gap 스윕, paper 기반 seed 0~99."""
    out = {}
    for rear_gap in (0.1, 0.3, 0.5, 1.0):
        results = [run_episode(world.generate_front_rear_scenario(seed, front_gap0=1.0,
                                                                    rear_gap=rear_gap), mpc=mpc)
                   for seed in SEEDS_100]
        out[f"rear_gap_{rear_gap:.1f}m"] = aggregate(results)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True)
    args = ap.parse_args()
    out_root = Path(args.out_root)

    mpc = OSQPMPC()
    all_summary = {}
    timings = {}
    for tag, fn in (("R3_s3_grid", run_s3), ("R4_s4_noise", run_s4), ("R5_s5_delay", run_s5),
                    ("R6_s6_heading", run_s6), ("R7_s7a_size", run_s7a), ("R7_s7b_frontrear", run_s7b)):
        out_dir = out_root / tag
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        result = fn(out_dir, mpc)
        t1 = time.perf_counter()
        timings[tag] = t1 - t0
        all_summary[tag] = result
        with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[{tag}] {t1 - t0:.1f}s")

    with open(out_root / "all_summary.json", "w", encoding="utf-8") as f:
        json.dump({"summary": all_summary, "timings_sec": timings}, f, ensure_ascii=False, indent=2)
    print("total:", sum(timings.values()), "s")


if __name__ == "__main__":
    main()
