"""
Stage 5: eval 1회 실행. DESIGN_IMPROVED.md §4/§7, 커밋 4652e32(고정) 기준.

**eval 데이터만 사용**(dev 아님): paper/left_obstacle seed 0~99, 기존 S3 961격자
(front_gap0 0.50~2.00/0.05, y0 -0.15~0.15/0.01), 기존 S4~S7 설정
(`ROBUSTNESS_PLAN.md`/`thesis_v2/tests/robustness/run_s3_s7.py`와 동일 파라미터).

baseline과 improved(최종 조합 I1+I1b+I2'+I3)를 이 스크립트 안에서 함께 실행해 같은
세션에서 페어(pair) 비교를 만든다 -- baseline은 결정론적이라 재실행해도 기존 저장된
값과 동일(이미 golden으로 확인됨), 재실행 자체가 "새 조건"을 만들지 않는다.

판정 기준(MEASURE_PLAN.md 그대로, 2026-09-23 3단계 해석 보완 포함): 원래 제약(차로/
헤딩/조향/변화율) 위반은 baseline과 동일(0)이어야 하고, I2 여유 미달은 정보성 지표.

사용(저장소 루트에서): python -m thesis_v2.improved.run_eval --out-root <dir>
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
    generate_scenario as base_generate_scenario,
    generate_left_obstacle_scenario,
    generate_grid_scenario,
    generate_scenario_custom_obstacle,
    generate_front_rear_scenario,
)
from thesis_v2.baseline.runner import run_episode as base_run_episode
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode
from avoidance_feasibility_recheck import min_feasible_front_gap

EVAL_SEEDS = list(range(100))
EVAL_S3_FRONT_GAPS = np.round(np.arange(0.50, 2.0001, 0.05), 4)
EVAL_S3_Y0S = np.round(np.arange(-0.15, 0.1501, 0.01), 4)

FINAL_COMBO = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                    i2_variant="narrow")


def _fmt_ci(k, n):
    if n == 0:
        return "n=0"
    ci = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {ci['lo']*100:.1f}~{ci['hi']*100:.1f}%)"


def _ci_overlap(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0:
        return None
    c1, c2 = wilson_ci(k1, n1), wilson_ci(k2, n2)
    return not (c1["hi"] < c2["lo"] or c2["hi"] < c1["lo"])


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
        "n_episodes": n, "n_success": n_success, "n_collision": n_collision,
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
        out["max_iter_count"] = sum(r.max_iter_count for r in results)
        out["max_iter_rejected_count"] = sum(r.max_iter_rejected_count for r in results)
        cats = ("lane", "heading", "steering_angle", "steering_rate", "i2_y_deficit", "i2_psi_deficit")
        bd = {c: {"count": 0, "max": 0.0, "cum": 0.0, "episodes": 0} for c in cats}
        for r in results:
            for c in cats:
                b = r.violation_breakdown[c]
                if b["count"] == 0:
                    continue
                bd[c]["count"] += b["count"]
                bd[c]["max"] = max(bd[c]["max"], b["max"])
                bd[c]["cum"] += b["cum"]
                bd[c]["episodes"] += 1
        out["violation_breakdown"] = bd
    return out


def _paired(baseline_results, improved_results):
    """seed(또는 격자 index) 순서가 같다고 가정하고 outcome을 페어 비교."""
    n = len(baseline_results)
    b2i_success = sum(1 for b, i in zip(baseline_results, improved_results)
                       if b.outcome != "성공" and i.outcome == "성공")
    i2b_success = sum(1 for b, i in zip(baseline_results, improved_results)
                       if b.outcome == "성공" and i.outcome != "성공")
    both_success = sum(1 for b, i in zip(baseline_results, improved_results)
                        if b.outcome == "성공" and i.outcome == "성공")
    both_fail = sum(1 for b, i in zip(baseline_results, improved_results)
                     if b.outcome != "성공" and i.outcome != "성공")
    return {"n": n, "baseline_fail_improved_success": b2i_success,
            "baseline_success_improved_fail": i2b_success,
            "both_success": both_success, "both_fail": both_fail}


def run_paper(out_dir):
    mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
    rb = [base_run_episode(base_generate_scenario(s), mpc=mpc_b) for s in EVAL_SEEDS]
    ri = [improved_run_episode(base_generate_scenario(s), mpc=mpc_i) for s in EVAL_SEEDS]
    return {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
            "paired": _paired(rb, ri)}


def run_left_obstacle(out_dir):
    mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
    rb = [base_run_episode(generate_left_obstacle_scenario(s), mpc=mpc_b) for s in EVAL_SEEDS]
    ri = [improved_run_episode(generate_left_obstacle_scenario(s), mpc=mpc_i) for s in EVAL_SEEDS]
    n = len(rb)
    n_safe_b = sum(1 for r in rb if r.outcome == "SAFE_STOP")
    n_safe_i = sum(1 for r in ri if r.outcome == "SAFE_STOP")
    return {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
            "paired": _paired(rb, ri),
            "safe_stop_rate_baseline": _fmt_ci(n_safe_b, n),
            "safe_stop_rate_improved": _fmt_ci(n_safe_i, n)}


def run_s3(out_dir):
    mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
    grid_b = np.empty((len(EVAL_S3_FRONT_GAPS), len(EVAL_S3_Y0S)), dtype=object)
    grid_i = np.empty_like(grid_b)
    for i, fg0 in enumerate(EVAL_S3_FRONT_GAPS):
        for j, y0 in enumerate(EVAL_S3_Y0S):
            sc = generate_grid_scenario(float(fg0), float(y0))
            grid_b[i, j] = base_run_episode(sc, mpc=mpc_b).outcome
            grid_i[i, j] = improved_run_episode(sc, mpc=mpc_i).outcome
    n_total = grid_b.size
    n_fail_b = int(np.sum(grid_b != "성공"))
    n_fail_i = int(np.sum(grid_i != "성공"))
    b2i = int(np.sum((grid_b != "성공") & (grid_i == "성공")))
    i2b = int(np.sum((grid_b == "성공") & (grid_i != "성공")))
    physical_limit = {float(y0): min_feasible_front_gap(float(y0), v=config.V_MAX, psi0_deg=0.0)
                       for y0 in EVAL_S3_Y0S}
    with open(out_dir / "s3_grid_baseline.json", "w", encoding="utf-8") as f:
        json.dump(grid_b.tolist(), f, ensure_ascii=False)
    with open(out_dir / "s3_grid_improved.json", "w", encoding="utf-8") as f:
        json.dump(grid_i.tolist(), f, ensure_ascii=False)
    return {
        "n_total": n_total, "n_fail_baseline": n_fail_b, "n_fail_improved": n_fail_i,
        "fail_ratio_baseline": n_fail_b / n_total, "fail_ratio_improved": n_fail_i / n_total,
        "baseline_fail_improved_success": b2i, "baseline_success_improved_fail": i2b,
        "physical_limit_curve": physical_limit,
    }


_S4_PROFILE_IDS = {"low": 1, "medium": 2, "high": 3}


def run_s4(out_dir):
    out = {}
    for name, profile in base_sensors.NOISE_PROFILES.items():
        mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
        rb, ri = [], []
        for s in EVAL_SEEDS:
            sc = base_generate_scenario(s)
            rng_b = np.random.default_rng((s, _S4_PROFILE_IDS[name]))
            rng_i = np.random.default_rng((s, _S4_PROFILE_IDS[name]))
            rb.append(base_run_episode(sc, mpc=mpc_b, noise_profile=profile, noise_rng=rng_b))
            ri.append(improved_run_episode(sc, mpc=mpc_i, noise_profile=profile, noise_rng=rng_i))
        out[name] = {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
                     "paired": _paired(rb, ri)}
    return out


def run_s5(out_dir):
    out = {}
    for delay in (1, 2):
        mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
        rb = [base_run_episode(base_generate_scenario(s), mpc=mpc_b, control_delay_steps=delay)
              for s in EVAL_SEEDS]
        ri = [improved_run_episode(base_generate_scenario(s), mpc=mpc_i, control_delay_steps=delay)
              for s in EVAL_SEEDS]
        out[f"delay_{delay}step"] = {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
                                      "paired": _paired(rb, ri)}
    return out


def run_s6(out_dir):
    out = {}
    for psi0 in (-15, -10, -5, 0, 5, 10, 15):
        mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
        rb = [base_run_episode(base_generate_scenario(s, psi0_deg=float(psi0)), mpc=mpc_b)
              for s in EVAL_SEEDS]
        ri = [improved_run_episode(base_generate_scenario(s, psi0_deg=float(psi0)), mpc=mpc_i)
              for s in EVAL_SEEDS]
        out[f"psi0_{psi0}deg"] = {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
                                   "paired": _paired(rb, ri)}
    return out


def run_s7a(out_dir):
    out = {}
    for length in (0.10, 0.15, 0.20, 0.30, 0.40):
        mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
        rb = [base_run_episode(generate_scenario_custom_obstacle(s, obstacle_length=length), mpc=mpc_b)
              for s in EVAL_SEEDS]
        ri = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_length=length), mpc=mpc_i)
              for s in EVAL_SEEDS]
        out[f"length_{length:.2f}m"] = {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
                                         "paired": _paired(rb, ri)}
    for width in (0.075, 0.10, 0.20, 0.30):
        mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
        rb = [base_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=width), mpc=mpc_b)
              for s in EVAL_SEEDS]
        ri = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=width), mpc=mpc_i)
              for s in EVAL_SEEDS]
        out[f"width_{width:.3f}m"] = {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
                                       "paired": _paired(rb, ri)}
    return out


def run_s7b(out_dir):
    out = {}
    for rear_gap in (0.1, 0.3, 0.5, 1.0):
        mpc_b, mpc_i = OSQPMPC(), ImprovedMPC(**FINAL_COMBO)
        rb = [base_run_episode(generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap), mpc=mpc_b)
              for s in EVAL_SEEDS]
        ri = [improved_run_episode(generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap), mpc=mpc_i)
              for s in EVAL_SEEDS]
        out[f"rear_gap_{rear_gap:.1f}m"] = {"baseline": _aggregate(rb, False), "improved": _aggregate(ri, True),
                                             "paired": _paired(rb, ri)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True)
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for name, fn in (("paper", run_paper), ("left_obstacle", run_left_obstacle), ("S3", run_s3),
                      ("S4", run_s4), ("S5", run_s5), ("S6", run_s6), ("S7a", run_s7a), ("S7b", run_s7b)):
        t0 = time.perf_counter()
        result = fn(out_root)
        t1 = time.perf_counter()
        all_results[name] = result
        print(f"[{name}] {t1-t0:.1f}s")
        with open(out_root / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    with open(out_root / "all_eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
