"""
2단계-D: M트랙(신경망 적용 여지) 측정. repro/docs/MEASURE_PLAN.md M트랙 절 기준.

- (a) 사전 확인: policy_best.pth 로드/eval(), normalization_stats.json 순서 확인,
  baseline 실행 로그(steps)에서 Student 9차원 입력을 구성할 수 있는지 매핑.
- (b) 계산시간: baseline MPC(thesis_v2.baseline.mpc.OSQPMPC) solve() vs Student 추론
  (단건, batch=1), "추론만"/"정규화 포함" 분리, 논문 표본수(Teacher 3,000/Student 6,000,
  THESIS_PAGES.md Table 8/16) 그대로 사용.
- (c) 조향 오차: 1순위 옛 MPC(legacy_2025/final_hierarchical_backup_thesis_1204.py, thesis_v2/tests/compare/old_mpc_wrapper.py)
  대비, 2순위(참고) baseline MPC 대비. 입력 집합은 baseline P트랙 실행 로그 중 실제로
  MPC가 호출된 스텝 전부(seed 0~99, paper+left_obstacle, 표본 선별 없음).

이 파일은 thesis_v2/tests/compare/ 예외 위치에서만 옛 코드(legacy_2025/final_hierarchical_backup_thesis_1204.py)를 import한다(old_mpc_wrapper
경유). baseline/ 쪽은 이 파일을 참조하지 않는다.
"""
import glob
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from thesis_v2.baseline import config as bcfg
from thesis_v2.baseline import envinfo
from thesis_v2.baseline.fsm import FSMState, target_line_y
from thesis_v2.baseline.mpc import OSQPMPC as BaselineMPC
from thesis_v2.tests.compare.old_mpc_wrapper import build_old_mpc, solve_old
from thesis_v2.tests.compare.student_model import (
    StudentPredictor, build_feature_vector, STATE_ORDER, EXPECTED_FEATURE_NAMES,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "thesis_v2" / "results"

# 입력 집합: 이미 완료된 100 에피소드 x 2 시나리오 실행(RESULT_BASELINE.md §5b, AC 조건
# 최선의 참고 실행). 여기서 발췌만 하고 재실행하지 않는다(표본 선별 금지 -- 전부 사용).
PAPER_DIR = RESULTS_DIR / "20260917_224259_DESKTOP-MDCKRJS_baseline_P_AC"
LEFTOBS_DIR = RESULTS_DIR / "20260917_224302_DESKTOP-MDCKRJS_baseline_P_leftobs_AC"

N_MPC_TIMING = 3000     # THESIS_PAGES.md Table 8 (Teacher 3,000회) 표본수만 맞춤
N_STUDENT_TIMING = 6000  # THESIS_PAGES.md Table 16 (Student 6,000회) 표본수만 맞춤
TIMING_SEED = 42
WARMUP = 50

_RAD2DEG = 180.0 / math.pi


def _load_step_records(result_dir: Path, scenario_glob: str) -> List[Dict[str, Any]]:
    """MPC가 실제로 호출된(solver_status != 'N/A') 스텝만 골라 레코드로 반환.
    ey_line이 None(NaN)인 스텝은 legacy_2025/final_hierarchical_backup_thesis_1204.py:1874의
    get_student_features() fallback 규칙(y - target_y)을 그대로 적용한다(확인된 사실,
    임의 가정 아님)."""
    records = []
    files = sorted(glob.glob(str(result_dir / scenario_glob)))
    if not files:
        raise RuntimeError(f"입력 파일을 찾을 수 없음: {result_dir / scenario_glob}")
    for fp in files:
        d = np.load(fp, allow_pickle=True)
        solved_mask = d["solver_status"] != "N/A"
        idx = np.nonzero(solved_mask)[0]
        for i in idx:
            state = str(d["state"][i])
            if state not in bcfg.POSITION_CONSTRAINTS:
                continue  # SAFE_STOP 등 MPC 미호출 상태(방어적, 실제로는 안 걸림)
            y = float(d["y"][i])
            psi = float(d["psi"][i])
            v = float(d["v"][i])
            ey_raw = float(d["ey_line"][i])
            target_y = target_line_y(FSMState(state))
            ey_is_fallback = bool(np.isnan(ey_raw))
            ey = ey_raw if not ey_is_fallback else (y - target_y)
            records.append({
                "y": y, "psi_rad": psi, "v": v, "state": state,
                "ey": ey, "ey_is_fallback": ey_is_fallback,
                "front_gap": float(d["front_gap"][i]),
                "left_clear": bool(d["left_clear"][i]),
                "target_y": target_y,
                "delta_baseline_mpc_deg": float(d["delta_mpc_raw"][i]),
                "source": Path(fp).name,
            })
    return records


def build_input_pool() -> List[Dict[str, Any]]:
    recs = _load_step_records(PAPER_DIR, "paper_seed*_steps.npz")
    recs += _load_step_records(LEFTOBS_DIR, "left_obstacle_seed*_steps.npz")
    return recs


# ---------------- (a) 사전 확인 ----------------

def run_sanity_checks(predictor: StudentPredictor, pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    mapping_table = [
        {"student_feature": "v", "source": "steps.v (baseline logger, m/s)"},
        {"student_feature": "ey_line",
         "source": "steps.ey_line (m); NaN(라인 미검출) 시 y - target_line_y(state)로 대체"
                    "(legacy_2025/final_hierarchical_backup_thesis_1204.py:1874 fallback 규칙과 동일)"},
        {"student_feature": "front_gap", "source": "steps.front_gap (m)"},
        {"student_feature": "left_clear", "source": "steps.left_clear (bool -> 0/1)"},
        {"student_feature": "state_one_hot(5)", "source": "steps.state (문자열) -> one-hot, "
                                                            f"순서={STATE_ORDER}"},
    ]
    return {
        "checkpoint": str((REPO_ROOT / "legacy_2025" / "models" / "policy_best.pth")),
        "eval_mode_applied": not predictor.model.training,
        "normalization_stats_feature_order_ok": True,  # StudentPredictor 생성자에서 assert됨
        "expected_feature_order": EXPECTED_FEATURE_NAMES,
        "mapping_table": mapping_table,
        "input_pool_size": len(pool),
        "ey_fallback_fraction": sum(1 for r in pool if r["ey_is_fallback"]) / len(pool),
        "blocked": False,
    }


# ---------------- (b) 계산시간 ----------------

def _percentiles(times_ms: List[float]) -> Dict[str, float]:
    arr = np.array(times_ms)
    return {
        "mean": float(arr.mean()), "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)), "p99": float(np.percentile(arr, 99)),
        "max": float(arr.max()), "min": float(arr.min()), "count": int(len(arr)),
    }


def run_timing_benchmark(pool: List[Dict[str, Any]], predictor: StudentPredictor) -> Dict[str, Any]:
    rng = np.random.RandomState(TIMING_SEED)
    n = len(pool)
    idx_all = rng.randint(0, n, size=N_STUDENT_TIMING)  # student 6000개 뽑고 mpc는 앞 3000개 재사용(쌍)
    idx_mpc = idx_all[:N_MPC_TIMING]

    baseline_mpc = BaselineMPC()
    mpc_times = []
    for k, i in enumerate(idx_mpc):
        r = pool[i]
        t0 = time.perf_counter()
        baseline_mpc.solve(y0=r["y"], psi0_rad=r["psi_rad"], v0=r["v"], target_y=r["target_y"],
                            state_name=r["state"])
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            mpc_times.append(dt_ms)

    # Student: "추론만"(정규화 이미 끝난 텐서) vs "정규화 포함"(feature 조립+정규화+추론+역정규화)
    feats = [build_feature_vector(v=pool[i]["v"], ey=pool[i]["ey"], front_gap=pool[i]["front_gap"],
                                   left_clear=pool[i]["left_clear"], state=pool[i]["state"])
             for i in idx_all]
    norm_tensors = [torch.from_numpy(predictor.normalize(f).astype(np.float32).reshape(1, -1))
                    for f in feats]

    infer_only_times = []
    for k, xt in enumerate(norm_tensors):
        t0 = time.perf_counter()
        with torch.no_grad():
            predictor.model(xt)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            infer_only_times.append(dt_ms)

    incl_norm_times = []
    for k, f in enumerate(feats):
        t0 = time.perf_counter()
        predictor.predict(f)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            incl_norm_times.append(dt_ms)

    mpc_stats = _percentiles(mpc_times)
    infer_only_stats = _percentiles(infer_only_times)
    incl_norm_stats = _percentiles(incl_norm_times)

    return {
        "n_mpc_requested": N_MPC_TIMING, "n_student_requested": N_STUDENT_TIMING,
        "warmup_excluded": WARMUP, "timing_seed": TIMING_SEED,
        "torch_num_threads": torch.get_num_threads(),
        "mpc_solve_ms": mpc_stats,
        "student_infer_only_ms": infer_only_stats,
        "student_incl_normalization_ms": incl_norm_stats,
        "speedup_median_infer_only": mpc_stats["p50"] / infer_only_stats["p50"],
        "speedup_median_incl_normalization": mpc_stats["p50"] / incl_norm_stats["p50"],
    }


# ---------------- (c) 조향 오차 ----------------

def run_mae_analysis(pool: List[Dict[str, Any]], predictor: StudentPredictor) -> Dict[str, Any]:
    old_mpc = build_old_mpc(N=bcfg.N, dt=bcfg.DT, qy=bcfg.QY, qpsi=bcfg.QPSI,
                             rdelta=bcfg.RDELTA, rddelta=bcfg.RDDELTA)

    per_state: Dict[str, Dict[str, Any]] = {}
    abs_err_old_all, abs_err_baseline_all = [], []
    ood_count = 0

    for r in pool:
        feat = build_feature_vector(v=r["v"], ey=r["ey"], front_gap=r["front_gap"],
                                     left_clear=r["left_clear"], state=r["state"])
        pred = predictor.predict(feat)
        delta_student_deg = float(pred[0])

        delta_old_deg, old_ok = solve_old(old_mpc, y0=r["y"], psi0_rad=r["psi_rad"], v0=r["v"],
                                           target_y=r["target_y"])
        delta_baseline_deg = r["delta_baseline_mpc_deg"]

        err_old = abs(delta_student_deg - delta_old_deg)
        err_baseline = abs(delta_student_deg - delta_baseline_deg)
        abs_err_old_all.append(err_old)
        abs_err_baseline_all.append(err_baseline)

        z = predictor.z_scores(feat)
        is_ood = bool(np.any(np.abs(z[:4]) > 3.0))  # 연속형 4개(v,ey,front_gap,left_clear)만 검사
        if is_ood:
            ood_count += 1

        s = r["state"]
        if s not in per_state:
            per_state[s] = {"n": 0, "abs_err_old_sum": 0.0, "abs_err_baseline_sum": 0.0,
                             "old_solve_ok_count": 0, "ood_count": 0}
        ps = per_state[s]
        ps["n"] += 1
        ps["abs_err_old_sum"] += err_old
        ps["abs_err_baseline_sum"] += err_baseline
        ps["old_solve_ok_count"] += int(old_ok)
        ps["ood_count"] += int(is_ood)

    per_state_out = {}
    for s, ps in per_state.items():
        per_state_out[s] = {
            "n": ps["n"],
            "mae_vs_old_mpc_deg": ps["abs_err_old_sum"] / ps["n"],
            "mae_vs_baseline_mpc_deg": ps["abs_err_baseline_sum"] / ps["n"],
            "old_mpc_solved_fraction": ps["old_solve_ok_count"] / ps["n"],
            "ood_fraction": ps["ood_count"] / ps["n"],
        }

    return {
        "n_total": len(pool),
        "mae_vs_old_mpc_deg": float(np.mean(abs_err_old_all)),
        "mae_vs_baseline_mpc_deg": float(np.mean(abs_err_baseline_all)),
        "ood_fraction_overall": ood_count / len(pool),
        "per_state": per_state_out,
        "note": "1순위=옛 MPC(legacy_2025/final_hierarchical_backup_thesis_1204.py, 12-04) 대비, 2순위(참고)=baseline MPC 대비"
                "(baseline은 REQ-MPC-02/03a/04/05 등에서 옛 코드와 명세 차이가 있어 "
                "'제어기 차이'가 섞임, SPEC_VS_OLDCODE.md). "
                "논문 Table15(MAE 1.20도)와는 다른 데이터셋 대체 측정이라 직접 비교하지 않음.",
    }


def main():
    bcfg.assert_fixed_params()
    predictor = StudentPredictor()
    pool = build_input_pool()

    sanity = run_sanity_checks(predictor, pool)
    print(json.dumps(sanity, ensure_ascii=False, indent=2))
    if sanity["blocked"]:
        return

    timing = run_timing_benchmark(pool, predictor)
    print(json.dumps(timing, ensure_ascii=False, indent=2))

    mae = run_mae_analysis(pool, predictor)
    print(json.dumps(mae, ensure_ascii=False, indent=2))

    env = envinfo.collect_env_info()
    env["torch"] = torch.__version__
    env["torch_cuda_available"] = torch.cuda.is_available()
    env["torch_num_threads"] = torch.get_num_threads()

    out_dir = RESULTS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{env['hostname']}_m_track"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "env.json", "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    with open(out_dir / "sanity.json", "w", encoding="utf-8") as f:
        json.dump(sanity, f, ensure_ascii=False, indent=2)
    with open(out_dir / "timing.json", "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)
    with open(out_dir / "mae.json", "w", encoding="utf-8") as f:
        json.dump(mae, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_dir}")


if __name__ == "__main__":
    main()
