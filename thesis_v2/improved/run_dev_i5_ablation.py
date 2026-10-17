"""
DESIGN_IMPROVED_V2.md §3/§7 Stage 2~3: I5(반복 상한) dev ablation. 1회차 최종 조합
(I1+I1b+I2'+I3) vs 그 위에 I5 반복 상한 4개 후보(972/1944/3888/5832, §1-1 계산)를
paper/S3/S4/S5/S6/S7a/S7b dev 전체(1회차의 S5~S7 dev 재검증 공백 재발 방지)에서 비교한다.

**eval 데이터(seed 0~99, 기존 S3 961격자/기존 S4~S7 설정)는 이 스크립트에서 절대
쓰지 않는다.** dev 전용: paper seed 100~199, S3는 1회차 dev와 동일한 반 칸 오프셋
격자(30x30=900), S4~S7은 seed 1000~1099(DESIGN_IMPROVED.md §4 dev 정의 재사용).

left_obstacle은 SAFE_STOP 경로만 쓰고 MPC(따라서 I5)를 호출하지 않으므로 이번
ablation에서는 생략한다(§3 각주).

사용(저장소 루트에서): python -m thesis_v2.improved.run_dev_i5_ablation --out-root <dir>
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "repro" / "2c_analysis"))

from thesis_v2.baseline import config, sensors as base_sensors
from thesis_v2.baseline.world import (
    generate_scenario, generate_grid_scenario, generate_scenario_custom_obstacle,
    generate_front_rear_scenario,
)
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

DEV_PAPER_SEEDS = list(range(100, 200))
DEV_SEEDS_1000 = list(range(1000, 1100))
DEV_S3_FRONT_GAPS = np.round(np.arange(0.525, 1.9751, 0.05), 4)
DEV_S3_Y0S = np.round(np.arange(-0.145, 0.1451, 0.01), 4)

FINAL_COMBO_V1 = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                       i2_variant="narrow")

I5_MAX_ITER_CANDIDATES = {
    "budget_5ms": 972,
    "budget_10ms": 1944,
    "budget_20ms": 3888,
    "budget_30ms": 5832,
}

COMBOS = {"v1(I1+I1b+I2'+I3)": dict(FINAL_COMBO_V1)}
for name, cap in I5_MAX_ITER_CANDIDATES.items():
    COMBOS[f"+I5({name},cap={cap})"] = dict(FINAL_COMBO_V1, enable_i5=True, i5_max_iter=cap)


def _fmt_ci(k, n):
    if n == 0:
        return "n=0"
    ci = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {ci['lo']*100:.1f}~{ci['hi']*100:.1f}%)"


_BD_CATS = ("lane", "heading", "steering_angle", "steering_rate", "i2_y_deficit", "i2_psi_deficit")


def _aggregate_breakdown(results):
    agg = {c: {"count": 0, "max": 0.0, "cum": 0.0, "episodes": 0} for c in _BD_CATS}
    for r in results:
        for c in _BD_CATS:
            b = r.violation_breakdown[c]
            if b["count"] == 0:
                continue
            agg[c]["count"] += b["count"]
            agg[c]["max"] = max(agg[c]["max"], b["max"])
            agg[c]["cum"] += b["cum"]
            agg[c]["episodes"] += 1
    return agg


def _aggregate(results):
    n = len(results)
    n_success = sum(1 for r in results if r.outcome == "성공")
    n_collision = sum(1 for r in results if r.outcome == "충돌")
    delta_violation = sum(r.delta_violation_count for r in results)
    delta_checked = sum(r.delta_checked_count for r in results)
    psi_violation = sum(r.psi_violation_count for r in results)
    y_violation = sum(r.y_violation_count for r in results)
    y_checked = sum(r.y_checked_count for r in results)
    mpc_solve_all = [t for r in results for t in r.mpc_solve_times_ms]
    n_mpc_calls = len(mpc_solve_all)
    max_iter_total = sum(r.max_iter_count for r in results)
    max_iter_rejected_total = sum(r.max_iter_rejected_count for r in results)
    time_limit_total = sum(r.time_limit_count for r in results)
    time_limit_rejected_total = sum(r.time_limit_rejected_count for r in results)
    warm_start_total = sum(r.warm_start_shift_count for r in results)

    def pct(a, p):
        return float(np.percentile(a, p)) if a else None

    return {
        "n_episodes": n,
        "collision_rate_formatted": _fmt_ci(n_collision, n),
        "success_rate_formatted": _fmt_ci(n_success, n),
        "delta_within_tolerance_rate": (1 - delta_violation / delta_checked) if delta_checked else None,
        "psi_within_tolerance_rate": (1 - psi_violation / delta_checked) if delta_checked else None,
        "y_within_tolerance_rate": (1 - y_violation / y_checked) if y_checked else None,
        "n_mpc_calls": n_mpc_calls,
        "mpc_solve_ms_mean": (float(np.mean(mpc_solve_all)) if mpc_solve_all else None),
        "mpc_solve_ms_p99": pct(mpc_solve_all, 99),
        "mpc_solve_ms_max": (max(mpc_solve_all) if mpc_solve_all else None),
        # 2026-09-24 보강: 서브그룹별 p99/max만으로는 트랙·조합 전체를 합친 "진짜" 전체
        # p99를 재계산할 수 없다(percentile은 단순 평균으로 합쳐지지 않음). 이후 실행부터는
        # 원시 배열도 저장해 상위 집계에서 정확한 전체 p99를 계산할 수 있게 한다.
        "mpc_solve_ms_all": [round(t, 4) for t in mpc_solve_all],
        "max_iter_count": max_iter_total,
        "max_iter_rejected_count": max_iter_rejected_total,
        "max_iter_hit_rate": (max_iter_total / n_mpc_calls) if n_mpc_calls else None,
        "time_limit_count": time_limit_total,
        "time_limit_rejected_count": time_limit_rejected_total,
        "warm_start_shift_count": warm_start_total,
        "i3_activation_rate_among_cap_hits": (
            warm_start_total / (max_iter_total + time_limit_total)
            if (max_iter_total + time_limit_total) else None),
        "violation_breakdown": _aggregate_breakdown(results),
        "notable_step_sample": [r.notable_step_log for r in results if r.notable_step_log][:5],
    }


def run_paper(flags):
    mpc = ImprovedMPC(**flags)
    results = [improved_run_episode(generate_scenario(s), mpc=mpc) for s in DEV_PAPER_SEEDS]
    return _aggregate(results)


def run_s3(flags):
    mpc = ImprovedMPC(**flags)
    outcomes = []
    for fg0 in DEV_S3_FRONT_GAPS:
        for y0 in DEV_S3_Y0S:
            outcomes.append(improved_run_episode(generate_grid_scenario(float(fg0), float(y0)),
                                                  mpc=mpc).outcome)
    n_total = len(outcomes)
    n_fail = sum(1 for o in outcomes if o != "성공")
    return {"n_total": n_total, "n_fail": n_fail, "fail_ratio": n_fail / n_total}


_S4_PROFILE_IDS = {"low": 1, "medium": 2, "high": 3}


def run_s4(flags):
    out = {}
    for name, profile in base_sensors.NOISE_PROFILES.items():
        mpc = ImprovedMPC(**flags)
        results = []
        for s in DEV_SEEDS_1000:
            rng = np.random.default_rng((s, _S4_PROFILE_IDS[name]))
            results.append(improved_run_episode(generate_scenario(s), mpc=mpc,
                                                  noise_profile=profile, noise_rng=rng))
        out[name] = _aggregate(results)
    return out


def run_s5(flags):
    out = {}
    for delay in (1, 2):
        mpc = ImprovedMPC(**flags)
        results = [improved_run_episode(generate_scenario(s), mpc=mpc, control_delay_steps=delay)
                   for s in DEV_SEEDS_1000]
        out[f"delay_{delay}step"] = _aggregate(results)
    return out


def run_s6(flags):
    out = {}
    for psi0 in (-15, -10, -5, 0, 5, 10, 15):
        mpc = ImprovedMPC(**flags)
        results = [improved_run_episode(generate_scenario(s, psi0_deg=float(psi0)), mpc=mpc)
                   for s in DEV_SEEDS_1000]
        out[f"psi0_{psi0}deg"] = _aggregate(results)
    return out


def run_s7a(flags):
    out = {}
    for length in (0.10, 0.15, 0.20, 0.30, 0.40):
        mpc = ImprovedMPC(**flags)
        results = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_length=length),
                                         mpc=mpc) for s in DEV_SEEDS_1000]
        out[f"length_{length:.2f}m"] = _aggregate(results)
    for width in (0.075, 0.10, 0.20, 0.30):
        mpc = ImprovedMPC(**flags)
        results = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=width),
                                         mpc=mpc) for s in DEV_SEEDS_1000]
        out[f"width_{width:.3f}m"] = _aggregate(results)
    return out


def run_s7b(flags):
    out = {}
    for rear_gap in (0.1, 0.3, 0.5, 1.0):
        mpc = ImprovedMPC(**flags)
        results = [improved_run_episode(
            generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap), mpc=mpc)
            for s in DEV_SEEDS_1000]
        out[f"rear_gap_{rear_gap:.1f}m"] = _aggregate(results)
    return out


TRACKS = (("paper", run_paper), ("S3", run_s3), ("S4", run_s4), ("S5", run_s5),
          ("S6", run_s6), ("S7a", run_s7a), ("S7b", run_s7b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True)
    ap.add_argument("--combos", type=str, nargs="*", default=None)
    ap.add_argument("--tracks", type=str, nargs="*", default=None)
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    combos = COMBOS if not args.combos else {k: COMBOS[k] for k in args.combos}
    tracks = TRACKS if not args.tracks else [(n, f) for n, f in TRACKS if n in args.tracks]

    all_summary = {}
    for combo_name, flags in combos.items():
        all_summary[combo_name] = {}
        for track_name, fn in tracks:
            t0 = time.perf_counter()
            all_summary[combo_name][track_name] = fn(flags)
            t1 = time.perf_counter()
            print(f"[{combo_name}][{track_name}] {t1 - t0:.1f}s", flush=True)
        with open(out_root / f"{combo_name.replace('/', '_').replace(chr(39), '')}.json",
                  "w", encoding="utf-8") as f:
            json.dump(all_summary[combo_name], f, ensure_ascii=False, indent=2)

    with open(out_root / "all_summary.json", "w", encoding="utf-8") as f:
        json.dump(all_summary, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
