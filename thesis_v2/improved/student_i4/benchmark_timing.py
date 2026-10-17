"""
I4 계산시간·변동성 비교(DESIGN_I4 §3-3/§3-4, 개정 1). official_timing_benchmark_v3.py와 같은
조건: 같은 호스트, 시나리오 paper / left_obstacle / S6(psi0=-15deg) x seed 0~99, v2 MPC 인스턴스
1개를 시나리오 내 전체 seed에서 재사용, MPC 시간 = MPCResult.compute_time_ms, 주 지표 p99.

한 프로세스에서 (1) v2 MPC 주행(스텝 루프는 v3 스크립트의 timed_improved_episode와 같은 순서,
원본 runner 미수정)으로 MPC 시간과 그 호출의 Student 입력을 모으고, (2) 같은 입력 목록 전체에
대해 PyTorch -> ONNX Runtime 순으로 batch=1 추론 시간을 잰다(warmup 50 제외). 스레드는 torch·ORT
모두 1(RESULT_STUDENT.md §6-3 선례). 변동성: 시나리오별 CV(std/mean).

사용(저장소 루트, Git Bash):
  python -m thesis_v2.improved.student_i4.benchmark_timing --run-dir <run> [--power-mode-confirmed]
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from thesis_v2.baseline import config, postprocess, longitudinal, collision
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.logger import save_json
from thesis_v2.baseline.vehicle import initial_state, step as vehicle_step
from thesis_v2.baseline.world import generate_scenario, generate_left_obstacle_scenario
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.lateral import compute_lateral as improved_compute_lateral
from thesis_v2.improved.mpc import ImprovedMPC

from . import config as i4_config
from .features import build_feature_vector, extend_features
from .model import Predictor

_RAD2DEG = 180.0 / math.pi
BUDGET_MS = 50.0

SCENARIOS = {
    "paper": (generate_scenario, {}),
    "left_obstacle": (generate_left_obstacle_scenario, {}),
    "S6_psi-15": (generate_scenario, {"psi0_deg": -15.0}),
}


def timed_v2_episode(scenario, mpc):
    """official_timing_benchmark_v3.timed_improved_episode와 같은 스텝 순서. MPC 호출 스텝의
    Student 입력을 추가로 기록한다(기록은 MPC 시간 측정 구간 밖)."""
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    visited_evade = False
    step_idx = 0
    max_iter = config.MAX_STEPS + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None
    transitions_last_to = None
    mpc_ms, iters, feats = [], [], []
    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT
        fg = base_sensors.front_gap(vehicle, scenario.obstacles)
        lc = base_sensors.left_clear(vehicle, scenario.obstacles)
        rc = base_sensors.right_clear(vehicle, scenario.obstacles)
        ey = base_sensors.ey_line(base_sensors.ir_pattern(vehicle))
        obstacle_info = improved_sensors.front_obstacle_info(vehicle, scenario.obstacles)
        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            transitions_last_to = (fsm_new.state.value, step_idx)
        fsm = fsm_new
        lat = improved_compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc,
                                       delta_prev, obstacle_info=obstacle_info)
        if lat.mpc_result is not None:
            mpc_ms.append(lat.mpc_result.compute_time_ms)
            iters.append(lat.mpc_result.iterations)
            feats.append((build_feature_vector(vehicle.v, ey, vehicle.y, fsm.state.value, fg, lc),
                          vehicle.psi * _RAD2DEG, delta_prev))
        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(lat.delta_desired_deg, delta_prev)
        delta_prev = pp.delta_final_deg
        vehicle_new = vehicle_step(vehicle, pp.delta_final_deg, v_cmd, config.DT)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)
        vehicle = vehicle_new
        if observing:
            if step_idx - observe_start >= config.OBSERVE_STEPS:
                break
            continue
        if collided or fsm.state == FSMState.SAFE_STOP:
            break
        if fsm.state == FSMState.KEEP_L2 and visited_evade and transitions_last_to is not None \
                and transitions_last_to == (FSMState.KEEP_L2.value, step_idx):
            observing = True
            observe_start = step_idx
            continue
        if step_idx >= config.MAX_STEPS:
            break
    return mpc_ms, iters, feats


def _stats(arr):
    a = np.asarray(arr, dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size), "mean": float(a.mean()), "std": float(a.std()),
            "cv": float(a.std() / a.mean()), "p50": float(np.percentile(a, 50)),
            "p95": float(np.percentile(a, 95)), "p99": float(np.percentile(a, 99)),
            "max": float(a.max()), "p99_pct_of_budget": float(np.percentile(a, 99) / BUDGET_MS * 100)}


def export_onnx(pred: Predictor, path: Path):
    dummy = torch.zeros(1, pred.input_dim, dtype=torch.float32)
    torch.onnx.export(pred.model, dummy, str(path), opset_version=17, dynamo=False,
                      input_names=["input"], output_names=["output"],
                      dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, required=True)
    ap.add_argument("--power-mode-confirmed", action="store_true")
    ap.add_argument("--n-episodes", type=int, default=len(i4_config.TIMING_SEEDS))
    ap.add_argument("--model-dir", type=str, default=None, help="기본값 <run-dir>")
    args = ap.parse_args()
    run = Path(args.run_dir)
    md = Path(args.model_dir) if args.model_dir else run
    out = md / "eval" / "timing"
    out.mkdir(parents=True, exist_ok=True)

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    import onnxruntime as ort

    env = collect_env_info(power_mode_confirmed=args.power_mode_confirmed)
    env.update(torch=torch.__version__, onnxruntime=ort.__version__, torch_threads=1, ort_threads=1,
               onnxruntime_note=("2단계-D ONNX 측정(RESULT_STUDENT.md §6)은 SSAFY PC(3층PC108)의 "
                                 "onnxruntime 1.29.0, 이번 I4는 노트북(DESKTOP-MDCKRJS) .venv의 "
                                 f"onnxruntime {ort.__version__}(py3.9 호환 버전으로 재설치) -- "
                                 "호스트·런타임 버전이 달라 2단계-D 수치(0.039ms 등)와 직접 비교 금지"))
    save_json(env, out / "env.json")

    pred = Predictor(md / "checkpoints" / "policy_i4_best.pt", md / "normalization_stats.json")
    onnx_path = md / "checkpoints" / "policy_i4_best.onnx"
    export_onnx(pred, onnx_path)
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(str(onnx_path), so, providers=["CPUExecutionProvider"])

    seeds = i4_config.TIMING_SEEDS[:args.n_episodes]
    results = {"n_episodes": len(seeds), "seeds": f"{seeds[0]}~{seeds[-1]}",
               "env_meets_official_condition": env["power"]["meets_official_condition"],
               "teacher_flags": i4_config.TEACHER_FLAGS, "warmup_excluded": i4_config.TIMING_WARMUP}
    all_feats = []
    for name, (gen_fn, kw) in SCENARIOS.items():
        mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
        mpc_ms, iters, feats = [], [], []
        for s in seeds:
            m, it, f = timed_v2_episode(gen_fn(s, **kw), mpc)
            mpc_ms += m
            iters += it
            feats += f
        if not feats:
            results[name] = {"n_mpc_calls": 0}
            continue
        X = extend_features(np.stack([f[0] for f in feats]), pred.variant,
                            np.array([f[1] for f in feats]), np.array([f[2] for f in feats])).astype(np.float32)
        all_feats.append(X)
        Xn = pred.normalize(X)

        def time_loop(fn, inputs):
            ts = []
            for x in inputs:
                t0 = time.perf_counter()
                fn(x)
                ts.append((time.perf_counter() - t0) * 1000.0)
            return ts[i4_config.TIMING_WARMUP:]

        def pt_infer(xn):
            with torch.no_grad():
                pred.model(torch.from_numpy(xn.reshape(1, -1)))

        def pt_e2e(x):
            pred.predict(x)

        def ort_infer(xn):
            sess.run(None, {"input": xn.reshape(1, -1)})

        def ort_e2e(x):
            xn = pred.normalize(x).reshape(1, -1)
            pred.denormalize(sess.run(None, {"input": xn})[0][0])

        # warmup 구간 확보를 위해 입력 앞쪽 50개를 한 번 더 앞에 붙인다(표본 수는 입력 수와 같게)
        pad_x = np.concatenate([X[:i4_config.TIMING_WARMUP], X])
        pad_xn = np.concatenate([Xn[:i4_config.TIMING_WARMUP], Xn])
        res = {
            "n_mpc_calls": len(mpc_ms),
            "v2_mpc_solve_ms": _stats(mpc_ms),
            "v2_mpc_iterations": _stats(iters),
            "pytorch_infer_only_ms": _stats(time_loop(pt_infer, pad_xn)),
            "pytorch_e2e_ms": _stats(time_loop(pt_e2e, pad_x)),
            "onnx_infer_only_ms": _stats(time_loop(ort_infer, pad_xn)),
            "onnx_e2e_ms": _stats(time_loop(ort_e2e, pad_x)),
        }
        results[name] = res
        print(f"[{name}] n={len(mpc_ms)} v2 p99={res['v2_mpc_solve_ms']['p99']:.4f} "
              f"pt p99={res['pytorch_e2e_ms']['p99']:.4f} onnx p99={res['onnx_e2e_ms']['p99']:.4f}",
              flush=True)

    Xall = np.concatenate(all_feats)[:1000]
    y_pt = pred.model(torch.from_numpy(pred.normalize(Xall))).detach().numpy()
    y_ort = sess.run(None, {"input": pred.normalize(Xall)})[0]
    results["onnx_conversion_check"] = {
        "n": int(len(Xall)),
        "max_abs_diff_normalized": float(np.abs(y_pt - y_ort).max()),
        "max_abs_diff_delta_deg": float(np.abs((y_pt - y_ort)[:, 0] * pred.Y_std[0]).max()),
    }
    with open(out / "timing.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results["onnx_conversion_check"]))


if __name__ == "__main__":
    main()
