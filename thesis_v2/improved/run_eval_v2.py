"""
Stage 4(v2, DESIGN_IMPROVED_V2.md §4/§9) eval 2회차. baseline v1.1 / improved v1
(I1+I1b+I2'+I3, I5 없음) / improved v2(v1+I5, i5_max_iter=972, 2026-09-24 채택,
config.py 기본값) 세 조합을 비교한다. eval 1회차(`run_eval.py`, 커밋 4652e32 고정,
수정하지 않음)를 그대로 재사용하지 않고 새 파일로 분리 — 1회차 스크립트/결과는
그대로 둔다("확정된 코드에 eval은 1회만 실행" 원칙, repro/docs/WORK_RULES.md 3단계 발전 원칙).

**새 eval 데이터**(DESIGN_IMPROVED_V2.md §4, 이번 실행 직전 확정 — dev/기존 eval과
전부 겹치지 않음, 아래 스크립트 안에서 직접 검증):
- paper/left_obstacle/S4~S7b: seed 200~299(신규, dev 1000번대·기존 eval 0~99와 무관)
- S3: front_gap0 0.5025~1.9975/0.05, y0 -0.1475~0.1475/0.01 (30x30=900) — 원래 간격
  (0.05/0.01) 유지, 1회차 dev 격자(반 칸 오프셋)와도 겹치지 않는 1/4칸 추가 오프셋
  (DESIGN_IMPROVED_V2.md §4 "완전히 새로운 좌표" 대안 채택 — 이번 실행 직전 확정)

**기존 eval(seed 0~99, 원래 961격자, S3 원래 간격)도 "연속성 참고"로 함께
재실행**한다(1회차와 동일 조건에서 baseline·v1이 그대로 재현되는지 확인용).
스크립트 구조상 v2도 같은 seed로 함께 실행되지만(baseline/v1/v2를 항상 같은 세
combo로 도는 공용 함수 구조), **legacy_continuity의 v2 결과는 정보성 참고일
뿐 판정 근거가 아니다** — v2 판정은 new_eval(신규 seed) 결과만으로 한다.

**노름 검증**(SETTINGS_DECISION.md §19): improved(v1·v2) 각 에피소드의
`max_derived_tol_deg`(가정 없이 그 solve의 실제 A,x,prim_res로 계산한 스텝별
실제 허용오차의 최댓값)와, 고정 상수(0.006530°, §19의 Z_max=1.396rad 가정) 대신
그 스텝 자신의 실측값과 비교한 `steering_angle/rate_violation_rigorous_count`를
집계에 포함한다.

사용(저장소 루트에서): python -m thesis_v2.improved.run_eval_v2 --out-root <dir>
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
from thesis_v2.improved import config as improved_config
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode
from avoidance_feasibility_recheck import min_feasible_front_gap

EVAL2_SEEDS = list(range(200, 300))
EVAL2_S3_FRONT_GAPS = np.round(np.arange(0.5025, 1.9975 + 0.0001, 0.05), 4)
EVAL2_S3_Y0S = np.round(np.arange(-0.1475, 0.1475 + 0.0001, 0.01), 4)
assert len(EVAL2_S3_FRONT_GAPS) == 30 and len(EVAL2_S3_Y0S) == 30

LEGACY_SEEDS = list(range(100))
LEGACY_S3_FRONT_GAPS = np.round(np.arange(0.50, 2.0001, 0.05), 4)
LEGACY_S3_Y0S = np.round(np.arange(-0.15, 0.1501, 0.01), 4)

# 겹침 없음을 실행 시점에도 재확인(§4 "실행 전 좌표 고정" 원칙 — 우연한 재도입 방지)
_DEV_S3_FG = set(np.round(np.arange(0.525, 1.9751, 0.05), 4))
_DEV_S3_Y0 = set(np.round(np.arange(-0.145, 0.1451, 0.01), 4))
assert not (set(EVAL2_S3_FRONT_GAPS) & set(LEGACY_S3_FRONT_GAPS) & _DEV_S3_FG)
assert not (set(EVAL2_S3_FRONT_GAPS) & _DEV_S3_FG)
assert not (set(EVAL2_S3_Y0S) & _DEV_S3_Y0)

COMBO_V1 = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                 i2_variant="narrow")
COMBO_V2 = dict(COMBO_V1, enable_i5=True, i5_max_iter=improved_config.I5_MAX_ITER)
assert improved_config.I5_MAX_ITER == 972, \
    "채택된 반복 상한(972)과 config.py 기본값이 어긋남 -- eval 실행 전 확인 필요"


def _fmt_ci(k, n):
    if n == 0:
        return "n=0"
    ci = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {ci['lo']*100:.1f}~{ci['hi']*100:.1f}%)"


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
        out["time_limit_count"] = sum(r.time_limit_count for r in results)
        out["time_limit_rejected_count"] = sum(r.time_limit_rejected_count for r in results)
        mpc_solve_all = [t for r in results for t in r.mpc_solve_times_ms]
        out["n_mpc_calls"] = len(mpc_solve_all)
        out["mpc_solve_ms_max"] = max(mpc_solve_all) if mpc_solve_all else None
        out["mpc_solve_ms_p99"] = (float(np.percentile(mpc_solve_all, 99))
                                    if mpc_solve_all else None)
        out["mpc_solve_ms_all"] = [round(t, 4) for t in mpc_solve_all]
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
        # SETTINGS_DECISION.md §19 검증(제어 로직 아님): 고정 가정(0.006530deg)이 아니라
        # 에피소드별 실측 노름으로 구한 스텝별 실제 허용오차와 직접 비교한 결과.
        out["max_derived_tol_deg"] = (max((r.max_derived_tol_deg for r in results), default=0.0))
        out["steering_angle_violation_rigorous_count"] = sum(
            r.steering_angle_violation_rigorous_count for r in results)
        out["steering_rate_violation_rigorous_count"] = sum(
            r.steering_rate_violation_rigorous_count for r in results)
    return out


def _paired(a_results, b_results):
    """seed(또는 격자 index) 순서가 같다고 가정하고 outcome을 페어 비교. a->b 방향."""
    n = len(a_results)
    a2b_success = sum(1 for a, b in zip(a_results, b_results)
                       if a.outcome != "성공" and b.outcome == "성공")
    b2a_success = sum(1 for a, b in zip(a_results, b_results)
                       if a.outcome == "성공" and b.outcome != "성공")
    both_success = sum(1 for a, b in zip(a_results, b_results)
                        if a.outcome == "성공" and b.outcome == "성공")
    both_fail = sum(1 for a, b in zip(a_results, b_results)
                     if a.outcome != "성공" and b.outcome != "성공")
    return {"n": n, "a_fail_b_success": a2b_success, "a_success_b_fail": b2a_success,
            "both_success": both_success, "both_fail": both_fail}


def _three_way(rb, r1, r2):
    return {
        "baseline": _aggregate(rb, False), "v1": _aggregate(r1, True), "v2": _aggregate(r2, True),
        "paired_baseline_vs_v1": _paired(rb, r1),
        "paired_baseline_vs_v2": _paired(rb, r2),
        "paired_v1_vs_v2": _paired(r1, r2),
    }


def run_paper(seeds):
    mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
    rb = [base_run_episode(base_generate_scenario(s), mpc=mpc_b) for s in seeds]
    r1 = [improved_run_episode(base_generate_scenario(s), mpc=mpc_1) for s in seeds]
    r2 = [improved_run_episode(base_generate_scenario(s), mpc=mpc_2) for s in seeds]
    return _three_way(rb, r1, r2)


def run_left_obstacle(seeds):
    mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
    rb = [base_run_episode(generate_left_obstacle_scenario(s), mpc=mpc_b) for s in seeds]
    r1 = [improved_run_episode(generate_left_obstacle_scenario(s), mpc=mpc_1) for s in seeds]
    r2 = [improved_run_episode(generate_left_obstacle_scenario(s), mpc=mpc_2) for s in seeds]
    out = _three_way(rb, r1, r2)
    n = len(rb)
    out["safe_stop_rate_baseline"] = _fmt_ci(sum(1 for r in rb if r.outcome == "SAFE_STOP"), n)
    out["safe_stop_rate_v1"] = _fmt_ci(sum(1 for r in r1 if r.outcome == "SAFE_STOP"), n)
    out["safe_stop_rate_v2"] = _fmt_ci(sum(1 for r in r2 if r.outcome == "SAFE_STOP"), n)
    return out


def run_s3(front_gaps, y0s, out_dir, tag):
    mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
    grid_b = np.empty((len(front_gaps), len(y0s)), dtype=object)
    grid_1, grid_2 = np.empty_like(grid_b), np.empty_like(grid_b)
    for i, fg0 in enumerate(front_gaps):
        for j, y0 in enumerate(y0s):
            sc = generate_grid_scenario(float(fg0), float(y0))
            grid_b[i, j] = base_run_episode(sc, mpc=mpc_b).outcome
            grid_1[i, j] = improved_run_episode(sc, mpc=mpc_1).outcome
            grid_2[i, j] = improved_run_episode(sc, mpc=mpc_2).outcome
    n_total = grid_b.size
    physical_limit = {float(y0): min_feasible_front_gap(float(y0), v=config.V_MAX, psi0_deg=0.0)
                       for y0 in y0s}
    for name, grid in (("baseline", grid_b), ("v1", grid_1), ("v2", grid_2)):
        with open(out_dir / f"s3_grid_{tag}_{name}.json", "w", encoding="utf-8") as f:
            json.dump(grid.tolist(), f, ensure_ascii=False)
    return {
        "n_total": n_total,
        "n_fail_baseline": int(np.sum(grid_b != "성공")),
        "n_fail_v1": int(np.sum(grid_1 != "성공")),
        "n_fail_v2": int(np.sum(grid_2 != "성공")),
        "fail_ratio_baseline": float(np.sum(grid_b != "성공")) / n_total,
        "fail_ratio_v1": float(np.sum(grid_1 != "성공")) / n_total,
        "fail_ratio_v2": float(np.sum(grid_2 != "성공")) / n_total,
        "baseline_fail_v2_success": int(np.sum((grid_b != "성공") & (grid_2 == "성공"))),
        "baseline_success_v2_fail": int(np.sum((grid_b == "성공") & (grid_2 != "성공"))),
        "v1_fail_v2_success": int(np.sum((grid_1 != "성공") & (grid_2 == "성공"))),
        "v1_success_v2_fail": int(np.sum((grid_1 == "성공") & (grid_2 != "성공"))),
        "physical_limit_curve": physical_limit,
    }


_S4_PROFILE_IDS = {"low": 1, "medium": 2, "high": 3}


def run_s4(seeds):
    out = {}
    for name, profile in base_sensors.NOISE_PROFILES.items():
        mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
        rb, r1, r2 = [], [], []
        for s in seeds:
            sc = base_generate_scenario(s)
            rng_b = np.random.default_rng((s, _S4_PROFILE_IDS[name]))
            rng_1 = np.random.default_rng((s, _S4_PROFILE_IDS[name]))
            rng_2 = np.random.default_rng((s, _S4_PROFILE_IDS[name]))
            rb.append(base_run_episode(sc, mpc=mpc_b, noise_profile=profile, noise_rng=rng_b))
            r1.append(improved_run_episode(sc, mpc=mpc_1, noise_profile=profile, noise_rng=rng_1))
            r2.append(improved_run_episode(sc, mpc=mpc_2, noise_profile=profile, noise_rng=rng_2))
        out[name] = _three_way(rb, r1, r2)
    return out


def run_s5(seeds):
    out = {}
    for delay in (1, 2):
        mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
        rb = [base_run_episode(base_generate_scenario(s), mpc=mpc_b, control_delay_steps=delay)
              for s in seeds]
        r1 = [improved_run_episode(base_generate_scenario(s), mpc=mpc_1, control_delay_steps=delay)
              for s in seeds]
        r2 = [improved_run_episode(base_generate_scenario(s), mpc=mpc_2, control_delay_steps=delay)
              for s in seeds]
        out[f"delay_{delay}step"] = _three_way(rb, r1, r2)
    return out


def run_s6(seeds):
    out = {}
    for psi0 in (-15, -10, -5, 0, 5, 10, 15):
        mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
        rb = [base_run_episode(base_generate_scenario(s, psi0_deg=float(psi0)), mpc=mpc_b)
              for s in seeds]
        r1 = [improved_run_episode(base_generate_scenario(s, psi0_deg=float(psi0)), mpc=mpc_1)
              for s in seeds]
        r2 = [improved_run_episode(base_generate_scenario(s, psi0_deg=float(psi0)), mpc=mpc_2)
              for s in seeds]
        out[f"psi0_{psi0}deg"] = _three_way(rb, r1, r2)
    return out


def run_s7a(seeds):
    out = {}
    for length in (0.10, 0.15, 0.20, 0.30, 0.40):
        mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
        rb = [base_run_episode(generate_scenario_custom_obstacle(s, obstacle_length=length), mpc=mpc_b)
              for s in seeds]
        r1 = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_length=length), mpc=mpc_1)
              for s in seeds]
        r2 = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_length=length), mpc=mpc_2)
              for s in seeds]
        out[f"length_{length:.2f}m"] = _three_way(rb, r1, r2)
    for width in (0.075, 0.10, 0.20, 0.30):
        mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
        rb = [base_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=width), mpc=mpc_b)
              for s in seeds]
        r1 = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=width), mpc=mpc_1)
              for s in seeds]
        r2 = [improved_run_episode(generate_scenario_custom_obstacle(s, obstacle_width=width), mpc=mpc_2)
              for s in seeds]
        out[f"width_{width:.3f}m"] = _three_way(rb, r1, r2)
    return out


def run_s7b(seeds):
    out = {}
    for rear_gap in (0.1, 0.3, 0.5, 1.0):
        mpc_b, mpc_1, mpc_2 = OSQPMPC(), ImprovedMPC(**COMBO_V1), ImprovedMPC(**COMBO_V2)
        rb = [base_run_episode(generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap), mpc=mpc_b)
              for s in seeds]
        r1 = [improved_run_episode(generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap), mpc=mpc_1)
              for s in seeds]
        r2 = [improved_run_episode(generate_front_rear_scenario(s, front_gap0=1.0, rear_gap=rear_gap), mpc=mpc_2)
              for s in seeds]
        out[f"rear_gap_{rear_gap:.1f}m"] = _three_way(rb, r1, r2)
    return out


# ===== 판정용 그룹 분리(집계만, 제어 로직과 무관) =====
# 논문 정합(paper, left_obstacle: REQ-SIM 그대로 psi0=0) vs 강건성([발전], REQ-SIM
# 범위 밖 -- ROBUSTNESS_PLAN.md 제목 자체가 "S3~S7"을 강건성/[발전]으로 묶어
# 분리한다: psi0!=0(S6), 노이즈(S4), 지연(S5), 장애물 크기/배치(S7a/S7b)뿐 아니라
# S3(경계 지도 격자)도 "신규 S3~S7은 [발전] 강건성 검증으로 완전히 분리"라고
# 명시돼 있어 이 그룹에 포함한다.
PAPER_COMPLIANT_TRACKS = ("paper", "left_obstacle")
ROBUSTNESS_TRACKS = ("S4", "S5", "S6", "S7a", "S7b")  # S3은 구조가 달라 별도 처리(아래)

_BD_CATS = ("lane", "heading", "steering_angle", "steering_rate", "i2_y_deficit", "i2_psi_deficit")


def _collect_combo_aggs(eval_results, track_names, combo_key):
    aggs = []
    for t in track_names:
        td = eval_results[t]
        if "baseline" in td:  # paper/left_obstacle: 단일 _three_way 결과
            aggs.append(td[combo_key])
        else:  # S4/S5/S6/S7a/S7b: {서브그룹명: _three_way 결과}
            for sub_result in td.values():
                aggs.append(sub_result[combo_key])
    return aggs


def _sum_collision(aggs):
    n = sum(a["n_episodes"] for a in aggs)
    k = sum(a["n_collision"] for a in aggs)
    return {"n_episodes": n, "n_collision": k, "collision_rate_formatted": _fmt_ci(k, n)}


def _sum_violation_breakdown(aggs):
    out = {c: {"count": 0, "max": 0.0, "cum": 0.0} for c in _BD_CATS}
    for a in aggs:
        bd = a.get("violation_breakdown")
        if not bd:
            continue
        for c in _BD_CATS:
            out[c]["count"] += bd[c]["count"]
            out[c]["max"] = max(out[c]["max"], bd[c]["max"])
            out[c]["cum"] += bd[c]["cum"]
    return out


def compute_scope_summary(eval_results):
    """DESIGN_IMPROVED_V2.md §2 판정 기준을 "논문 정합 조건"과 "강건성 조건"으로
    나눠서도 읽을 수 있도록 재집계(트랙별 원자료는 그대로 두고 추가만 한다)."""
    out = {}
    for scope_name, tracks in (("paper_compliant", PAPER_COMPLIANT_TRACKS),
                                ("robustness", ROBUSTNESS_TRACKS)):
        scope_out = {}
        for combo_key in ("baseline", "v1", "v2"):
            aggs = _collect_combo_aggs(eval_results, tracks, combo_key)
            entry = _sum_collision(aggs)
            if combo_key != "baseline":  # baseline은 violation_breakdown을 안 남김(추적 대상 아님)
                entry["violation_breakdown"] = _sum_violation_breakdown(aggs)
            scope_out[combo_key] = entry
        out[scope_name] = scope_out
    # S3(경계 지도 격자)는 outcome 성공/실패만 있고 violation_breakdown 구조가 달라
    # 위 집계에 못 섞는다 -- robustness 그룹에 참고 필드로만 별도 추가.
    s3 = eval_results["S3"]
    out["robustness"]["S3_grid_reference"] = {
        "n_total": s3["n_total"],
        "fail_ratio_baseline": s3["fail_ratio_baseline"],
        "fail_ratio_v1": s3["fail_ratio_v1"],
        "fail_ratio_v2": s3["fail_ratio_v2"],
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True)
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    all_results = {"new_eval": {}, "legacy_continuity": {}}

    # --- 신규 eval(seed 200~299, S3 1/4칸 오프셋 900격자) -- 판정 근거 ---
    for name, fn in (("paper", run_paper), ("left_obstacle", run_left_obstacle),
                      ("S4", run_s4), ("S5", run_s5), ("S6", run_s6),
                      ("S7a", run_s7a), ("S7b", run_s7b)):
        t0 = time.perf_counter()
        result = fn(EVAL2_SEEDS)
        t1 = time.perf_counter()
        all_results["new_eval"][name] = result
        print(f"[new_eval/{name}] {t1-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    all_results["new_eval"]["S3"] = run_s3(EVAL2_S3_FRONT_GAPS, EVAL2_S3_Y0S, out_root, "new")
    print(f"[new_eval/S3] {time.perf_counter()-t0:.1f}s", flush=True)

    # --- 기존 eval(seed 0~99, 원래 961격자) -- 연속성 참고(v2 결과 포함되지만 정보성) ---
    for name, fn in (("paper", run_paper), ("left_obstacle", run_left_obstacle),
                      ("S4", run_s4), ("S5", run_s5), ("S6", run_s6),
                      ("S7a", run_s7a), ("S7b", run_s7b)):
        t0 = time.perf_counter()
        result = fn(LEGACY_SEEDS)
        t1 = time.perf_counter()
        all_results["legacy_continuity"][name] = result
        print(f"[legacy_continuity/{name}] {t1-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    all_results["legacy_continuity"]["S3"] = run_s3(
        LEGACY_S3_FRONT_GAPS, LEGACY_S3_Y0S, out_root, "legacy")
    print(f"[legacy_continuity/S3] {time.perf_counter()-t0:.1f}s", flush=True)

    # 판정용 그룹 분리 집계(제어 로직과 무관, 트랙별 원자료는 그대로 둔 채 추가만 함)
    all_results["new_eval_scope_summary"] = compute_scope_summary(all_results["new_eval"])
    all_results["legacy_continuity_scope_summary"] = compute_scope_summary(
        all_results["legacy_continuity"])

    with open(out_root / "all_eval_v2_summary.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
