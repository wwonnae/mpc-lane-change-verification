"""
Stage 4: dev 전용 ablation 실행. DESIGN_IMPROVED.md §3/§4/§5/§7.

**eval 데이터(seed 0~99, 기존 S3/S4~S7 설정)는 이 스크립트에서 절대 쓰지 않는다.**
dev 전용: paper류 seed 100~199, S3는 반 칸 어긋난 격자, S4는 seed 1000~1099.

8개 조합: baseline(참고, thesis_v2.baseline 그대로) / I1 / I1b / I1+I1b / I1+I1b+I2 /
I1+I1b+I2+I3(전체) / I2(단독) / I3(단독).

사용(저장소 루트에서): python -m thesis_v2.improved.run_dev_ablation --out-root <dir>
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "repro" / "2c_analysis"))

from thesis_v2.baseline import config, sensors as base_sensors
from thesis_v2.baseline.world import generate_scenario as base_generate_scenario, generate_grid_scenario
from thesis_v2.baseline.runner import run_episode as base_run_episode
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode
from avoidance_feasibility_recheck import min_feasible_front_gap  # repro/2c_analysis 재사용

DEV_PAPER_SEEDS = list(range(100, 200))
DEV_S4_SEEDS = list(range(1000, 1100))
DEV_S3_FRONT_GAPS = np.round(np.arange(0.525, 1.9751, 0.05), 4)
DEV_S3_Y0S = np.round(np.arange(-0.145, 0.1451, 0.01), 4)

COMBOS = {
    "baseline": None,
    "I1": dict(enable_i1=True, enable_i1b=False, enable_i2=False, enable_i3=False),
    "I1b": dict(enable_i1=False, enable_i1b=True, enable_i2=False, enable_i3=False),
    "I1+I1b": dict(enable_i1=True, enable_i1b=True, enable_i2=False, enable_i3=False),
    "I1+I1b+I2": dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=False,
                       i2_variant="wide"),
    "I1+I1b+I2+I3(전체)": dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                              i2_variant="wide"),
    "I2(단독)": dict(enable_i1=False, enable_i1b=False, enable_i2=True, enable_i3=False,
                    i2_variant="wide"),
    "I3(단독)": dict(enable_i1=False, enable_i1b=False, enable_i2=False, enable_i3=True),
    # 2026-09-23 검토 반영: I2' (narrow, MARGIN_I2_PRIME + psi>=-20deg 하한)
    "I1+I1b+I2'": dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=False,
                        i2_variant="narrow"),
    "I1+I1b+I2'+I3(전체)": dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                               i2_variant="narrow"),
}


def _fmt_ci(k, n):
    if n == 0:
        return "n=0"
    ci = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {ci['lo']*100:.1f}~{ci['hi']*100:.1f}%)"


def _aggregate_breakdown(results):
    """제약 종류별 분해(2026-09-23 검토): 위반 스텝 수 | 최대 | 누적 | 발생 에피소드 수 | 상태."""
    cats = ("lane", "heading", "steering_angle", "steering_rate", "i2_y_deficit", "i2_psi_deficit")
    agg = {c: {"count": 0, "max": 0.0, "cum": 0.0, "episodes": 0, "states": []} for c in cats}
    for r in results:
        for c in cats:
            b = r.violation_breakdown[c]
            if b["count"] == 0:
                continue
            a = agg[c]
            a["count"] += b["count"]
            a["max"] = max(a["max"], b["max"])
            a["cum"] += b["cum"]
            a["episodes"] += 1
            for s in b["states"]:
                if s not in a["states"]:
                    a["states"].append(s)
    return agg


def _aggregate(results, is_improved: bool):
    n = len(results)
    n_success = sum(1 for r in results if r.outcome == "성공")
    n_collision = sum(1 for r in results if r.outcome == "충돌")
    n_safe_stop = sum(1 for r in results if r.outcome == "SAFE_STOP")
    delta_violation = sum(r.delta_violation_count for r in results)
    delta_checked = sum(r.delta_checked_count for r in results)
    psi_violation = sum(r.psi_violation_count for r in results)
    y_violation = sum(r.y_violation_count for r in results)
    y_checked = sum(r.y_checked_count for r in results)
    solver_fail = sum(r.solver_fail_count for r in results)
    fallback = sum(r.fallback_count for r in results)
    out = {
        "n_episodes": n,
        "collision_rate_formatted": _fmt_ci(n_collision, n),
        "success_rate_formatted": _fmt_ci(n_success, n),
        "safe_stop_count": n_safe_stop,
        "delta_within_tolerance_rate": (1 - delta_violation / delta_checked) if delta_checked else None,
        "psi_within_tolerance_rate": (1 - psi_violation / delta_checked) if delta_checked else None,
        "y_within_tolerance_rate": (1 - y_violation / y_checked) if y_checked else None,
        "solver_fail_count": solver_fail,
        "fallback_count": fallback,
    }
    if is_improved:
        out["warm_start_shift_count"] = sum(r.warm_start_shift_count for r in results)
        out["y_max_abs_violation_m"] = max((r.y_max_abs_violation_m for r in results), default=0.0)
        out["y_cumulative_violation_m"] = sum(r.y_cumulative_violation_m for r in results)
        out["max_iter_count"] = sum(r.max_iter_count for r in results)
        out["max_iter_rejected_count"] = sum(r.max_iter_rejected_count for r in results)
        out["violation_breakdown"] = _aggregate_breakdown(results)
    else:
        out["y_max_abs_violation_m"] = None
        out["y_cumulative_violation_m"] = None
        out["max_iter_count"] = None
        out["max_iter_rejected_count"] = None
        out["violation_breakdown"] = None
    return out


def run_paper_dev(combo_name, flags):
    if flags is None:
        mpc = OSQPMPC()
        results = [base_run_episode(base_generate_scenario(seed), mpc=mpc) for seed in DEV_PAPER_SEEDS]
        return _aggregate(results, is_improved=False)
    mpc = ImprovedMPC(**flags)
    results = [improved_run_episode(base_generate_scenario(seed), mpc=mpc) for seed in DEV_PAPER_SEEDS]
    return _aggregate(results, is_improved=True)


def run_s3_dev(combo_name, flags):
    grid_outcome = np.empty((len(DEV_S3_FRONT_GAPS), len(DEV_S3_Y0S)), dtype=object)
    mpc = OSQPMPC() if flags is None else ImprovedMPC(**flags)
    for i, fg0 in enumerate(DEV_S3_FRONT_GAPS):
        for j, y0 in enumerate(DEV_S3_Y0S):
            scenario = generate_grid_scenario(float(fg0), float(y0))
            if flags is None:
                result = base_run_episode(scenario, mpc=mpc)
            else:
                result = improved_run_episode(scenario, mpc=mpc)
            grid_outcome[i, j] = result.outcome
    n_total = grid_outcome.size
    n_fail = int(np.sum(grid_outcome != "성공"))
    return {
        "n_total": n_total, "n_fail": n_fail, "fail_ratio": n_fail / n_total,
        "grid": grid_outcome.tolist(),
    }


_S4_PROFILE_IDS = {"low": 1, "medium": 2, "high": 3}


def run_s4_dev(combo_name, flags):
    out = {}
    for profile_name, profile in base_sensors.NOISE_PROFILES.items():
        mpc = OSQPMPC() if flags is None else ImprovedMPC(**flags)
        results = []
        for idx, seed in enumerate(DEV_S4_SEEDS):
            scenario = base_generate_scenario(seed)
            noise_rng = np.random.default_rng((seed, _S4_PROFILE_IDS[profile_name]))
            if flags is None:
                result = base_run_episode(scenario, mpc=mpc, noise_profile=profile, noise_rng=noise_rng)
            else:
                result = improved_run_episode(scenario, mpc=mpc, noise_profile=profile, noise_rng=noise_rng)
            results.append(result)
        out[profile_name] = _aggregate(results, is_improved=(flags is not None))
    return out


def _physical_limit_curve():
    return {float(y0): min_feasible_front_gap(float(y0), v=config.V_MAX, psi0_deg=0.0)
            for y0 in DEV_S3_Y0S}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True)
    ap.add_argument("--combos", type=str, nargs="*", default=None,
                     help="실행할 조합 이름만 선택(생략하면 COMBOS 전체)")
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    physical_limit = _physical_limit_curve()
    with open(out_root / "physical_limit_curve.json", "w", encoding="utf-8") as f:
        json.dump(physical_limit, f, ensure_ascii=False, indent=2)

    combos = COMBOS if not args.combos else {k: COMBOS[k] for k in args.combos}
    all_summary_path = out_root / "all_summary.json"
    all_summary = json.load(open(all_summary_path, encoding="utf-8")) if all_summary_path.exists() else {}
    for combo_name, flags in combos.items():
        t0 = time.perf_counter()
        paper = run_paper_dev(combo_name, flags)
        t1 = time.perf_counter()
        s3 = run_s3_dev(combo_name, flags)
        t2 = time.perf_counter()
        s4 = run_s4_dev(combo_name, flags)
        t3 = time.perf_counter()
        all_summary[combo_name] = {"paper_dev": paper, "s3_dev": s3, "s4_dev": s4}
        print(f"[{combo_name}] paper={t1-t0:.1f}s s3={t2-t1:.1f}s s4={t3-t2:.1f}s")
        with open(out_root / f"{combo_name.replace('/', '_')}.json", "w", encoding="utf-8") as f:
            json.dump(all_summary[combo_name], f, ensure_ascii=False, indent=2)

    with open(all_summary_path, "w", encoding="utf-8") as f:
        json.dump(all_summary, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
