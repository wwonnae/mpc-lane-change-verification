"""
2단계-D 후속(SSAFY PC 마지막 실행): ONNX 재측정. MEASURE_PLAN.md M트랙 절차를 그대로 따르되
런타임만 PyTorch eager -> ONNX Runtime으로 바꿔 같은 조건에서 비교한다.
legacy_2025/models/policy_best.pth 가중치는 읽기만 하고 수정하지 않는다(ONNX 파일은 thesis_v2/results/
아래에만 쓴다). baseline 제어 로직(thesis_v2/baseline/)은 이 파일에서 import하지 않는다
(MPC 계산시간 비교를 위해서만 thesis_v2.baseline.mpc를 사용 -- 로직 수정 없음, 호출만 함).
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from thesis_v2.baseline import config as bcfg
from thesis_v2.baseline import envinfo
from thesis_v2.baseline.mpc import OSQPMPC as BaselineMPC
from thesis_v2.tests.compare.old_mpc_wrapper import build_old_mpc, solve_old
from thesis_v2.tests.compare.run_m_track import build_input_pool, N_MPC_TIMING, N_STUDENT_TIMING, \
    TIMING_SEED, WARMUP, _percentiles
from thesis_v2.tests.compare.student_model import StudentPredictor, build_feature_vector

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "thesis_v2" / "results"

ONNX_OPSET = 17
FIXED_THREADS = 1  # torch/onnxruntime 둘 다 단일 스레드로 고정(임베디드 단일코어 가정, 스레딩 오버헤드 배제)
N_VALIDATION = 1000
VALIDATION_SEED = 7


def try_import_onnxruntime():
    try:
        import onnxruntime as ort  # noqa: F401
        return ort, None
    except Exception as e:  # pragma: no cover
        return None, f"{type(e).__name__}: {e}"


def export_to_onnx(predictor: StudentPredictor, out_path: Path) -> Dict[str, Any]:
    dummy = torch.zeros(1, 9, dtype=torch.float32)
    predictor.model.eval()
    torch.onnx.export(
        predictor.model, dummy, str(out_path),
        input_names=["input"], output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=ONNX_OPSET,
        dynamo=False,  # torch>=2.x 기본(dynamo=True)은 onnxscript 요구(미설치, ImportError
                       # 확인됨) -- 레거시 TorchScript 기반 exporter로 전환, 결과 그래프는 동등
    )
    return {
        "path": str(out_path), "opset_version": ONNX_OPSET,
        "input_shape_used_for_export": [1, 9], "input_names": ["input"],
        "output_names": ["output"], "dynamic_batch_axis": True,
    }


def validate_onnx_vs_torch(predictor: StudentPredictor, ort_session, pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    rng = np.random.RandomState(VALIDATION_SEED)
    idx = rng.randint(0, len(pool), size=N_VALIDATION)
    max_diff_raw_output = 0.0  # 정규화된 네트워크 출력(2차원, 역정규화 전) 기준
    max_diff_delta_deg = 0.0   # 역정규화 후 delta(도) 기준(실사용 관점)
    for i in idx:
        r = pool[i]
        feat = build_feature_vector(v=r["v"], ey=r["ey"], front_gap=r["front_gap"],
                                     left_clear=r["left_clear"], state=r["state"])
        x_norm = predictor.normalize(feat).astype(np.float32).reshape(1, -1)
        with torch.no_grad():
            y_torch = predictor.model(torch.from_numpy(x_norm)).numpy()[0]
        y_onnx = ort_session.run(None, {"input": x_norm})[0][0]
        diff_raw = np.abs(y_torch - y_onnx)
        max_diff_raw_output = max(max_diff_raw_output, float(diff_raw.max()))

        delta_torch = y_torch[0] * predictor.Y_std[0] + predictor.Y_mean[0]
        delta_onnx = y_onnx[0] * predictor.Y_std[0] + predictor.Y_mean[0]
        max_diff_delta_deg = max(max_diff_delta_deg, float(abs(delta_torch - delta_onnx)))

    return {
        "n_samples": N_VALIDATION, "seed": VALIDATION_SEED,
        "max_abs_diff_normalized_output": max_diff_raw_output,
        "max_abs_diff_delta_deg": max_diff_delta_deg,
    }


def run_benchmark(pool: List[Dict[str, Any]], predictor: StudentPredictor, ort_session) -> Dict[str, Any]:
    rng = np.random.RandomState(TIMING_SEED)
    idx_all = rng.randint(0, len(pool), size=N_STUDENT_TIMING)
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

    # 옛 MPC(legacy_2025/final_hierarchical_backup_thesis_1204.py, 12-04)는 매 solve()마다 P/A를 파이썬 리스트로 새로 구성 -- baseline은
    # 구조를 1회만 만들고 update()만 호출. 논문 Table8(Teacher 평균 1.091ms)이 이 "매번 재구성"
    # 비용 때문인지 확인하기 위해 같은 입력·같은 하드웨어에서 옛 MPC도 함께 측정한다.
    old_mpc = build_old_mpc(N=bcfg.N, dt=bcfg.DT, qy=bcfg.QY, qpsi=bcfg.QPSI,
                             rdelta=bcfg.RDELTA, rddelta=bcfg.RDDELTA)
    old_mpc_times = []
    for k, i in enumerate(idx_mpc):
        r = pool[i]
        t0 = time.perf_counter()
        solve_old(old_mpc, y0=r["y"], psi0_rad=r["psi_rad"], v0=r["v"], target_y=r["target_y"])
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            old_mpc_times.append(dt_ms)

    feats = [build_feature_vector(v=pool[i]["v"], ey=pool[i]["ey"], front_gap=pool[i]["front_gap"],
                                   left_clear=pool[i]["left_clear"], state=pool[i]["state"])
             for i in idx_all]
    norm_feats = [predictor.normalize(f).astype(np.float32).reshape(1, -1) for f in feats]
    norm_tensors = [torch.from_numpy(nf) for nf in norm_feats]

    torch_infer_only = []
    for k, xt in enumerate(norm_tensors):
        t0 = time.perf_counter()
        with torch.no_grad():
            predictor.model(xt)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            torch_infer_only.append(dt_ms)

    torch_incl_norm = []
    for k, f in enumerate(feats):
        t0 = time.perf_counter()
        predictor.predict(f)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            torch_incl_norm.append(dt_ms)

    onnx_infer_only = []
    for k, nf in enumerate(norm_feats):
        t0 = time.perf_counter()
        ort_session.run(None, {"input": nf})
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            onnx_infer_only.append(dt_ms)

    onnx_incl_norm = []
    for k, f in enumerate(feats):
        t0 = time.perf_counter()
        x_norm = predictor.normalize(f).astype(np.float32).reshape(1, -1)
        y_onnx = ort_session.run(None, {"input": x_norm})[0][0]
        _ = y_onnx * predictor.Y_std + predictor.Y_mean
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if k >= WARMUP:
            onnx_incl_norm.append(dt_ms)

    mpc_stats = _percentiles(mpc_times)
    old_mpc_stats = _percentiles(old_mpc_times)
    torch_only_stats = _percentiles(torch_infer_only)
    torch_norm_stats = _percentiles(torch_incl_norm)
    onnx_only_stats = _percentiles(onnx_infer_only)
    onnx_norm_stats = _percentiles(onnx_incl_norm)

    return {
        "n_mpc": N_MPC_TIMING, "n_student": N_STUDENT_TIMING, "warmup_excluded": WARMUP,
        "timing_seed": TIMING_SEED, "fixed_threads": FIXED_THREADS,
        "mpc_solve_ms": mpc_stats,
        "old_mpc_solve_ms": old_mpc_stats,
        "torch_infer_only_ms": torch_only_stats,
        "torch_incl_normalization_ms": torch_norm_stats,
        "onnx_infer_only_ms": onnx_only_stats,
        "onnx_incl_normalization_ms": onnx_norm_stats,
        "speedup_mpc_over_torch_incl_norm": mpc_stats["p50"] / torch_norm_stats["p50"],
        "speedup_mpc_over_onnx_incl_norm": mpc_stats["p50"] / onnx_norm_stats["p50"],
        "speedup_torch_over_onnx_incl_norm": torch_norm_stats["p50"] / onnx_norm_stats["p50"],
        "speedup_mpc_over_torch_infer_only": mpc_stats["p50"] / torch_only_stats["p50"],
        "speedup_mpc_over_onnx_infer_only": mpc_stats["p50"] / onnx_only_stats["p50"],
        "speedup_torch_over_onnx_infer_only": torch_only_stats["p50"] / onnx_only_stats["p50"],
        "speedup_old_mpc_over_torch_incl_norm": old_mpc_stats["p50"] / torch_norm_stats["p50"],
        "speedup_old_mpc_over_onnx_incl_norm": old_mpc_stats["p50"] / onnx_norm_stats["p50"],
    }


def main():
    bcfg.assert_fixed_params()
    ort, import_error = try_import_onnxruntime()

    result: Dict[str, Any] = {"onnxruntime_available": ort is not None}
    if ort is None:
        result["import_error"] = import_error
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    import onnxruntime as ort_mod
    result["onnxruntime_version"] = ort_mod.__version__
    try:
        import onnx
        result["onnx_version"] = onnx.__version__
    except Exception as e:
        result["onnx_version"] = None
        result["onnx_import_error"] = f"{type(e).__name__}: {e}"

    torch.set_num_threads(FIXED_THREADS)

    predictor = StudentPredictor()
    pool = build_input_pool()

    env = envinfo.collect_env_info()
    env["torch"] = torch.__version__
    env["torch_num_threads_fixed"] = torch.get_num_threads()
    env["onnxruntime"] = ort_mod.__version__

    out_dir = RESULTS_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{env['hostname']}_onnx_benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / "policy_student.onnx"

    export_info = export_to_onnx(predictor, onnx_path)
    result["export"] = export_info

    so = ort_mod.SessionOptions()
    so.intra_op_num_threads = FIXED_THREADS
    so.inter_op_num_threads = FIXED_THREADS
    ort_session = ort_mod.InferenceSession(str(onnx_path), sess_options=so,
                                            providers=["CPUExecutionProvider"])
    result["onnxruntime_providers_used"] = ort_session.get_providers()
    result["onnxruntime_intra_op_num_threads"] = FIXED_THREADS
    result["onnxruntime_inter_op_num_threads"] = FIXED_THREADS

    validation = validate_onnx_vs_torch(predictor, ort_session, pool)
    result["validation"] = validation
    print(json.dumps({"validation": validation}, ensure_ascii=False, indent=2))

    benchmark = run_benchmark(pool, predictor, ort_session)
    result["benchmark"] = benchmark
    print(json.dumps({"benchmark": benchmark}, ensure_ascii=False, indent=2))

    with open(out_dir / "env.json", "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    with open(out_dir / "onnx_benchmark_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_dir}")


if __name__ == "__main__":
    main()
