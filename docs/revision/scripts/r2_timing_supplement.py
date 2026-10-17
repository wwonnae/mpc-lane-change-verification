"""
R2 — 공식 조건 계산시간 보충 측정(DESIGN_REVISION §3-1, 남은 결정 E2(a)). **사용자가 전원 모드 "최고 성능"에서 실행**.

timing_v3·S10 timing에 저장되지 않은 통계를 같은 조건(DESKTOP-MDCKRJS, AC, seed 0~99 paper, 인스턴스 재사용, 스레드 1)으로 잰다:
1. baseline v1.1 MPC solve: 표준편차·최소(제출본 표 8), 제어 1스텝 전체 시간의 상태별 평균·최대(제출본 본문 "차선 변경 구간 평균 3.71ms",
   "EVADE_L 최대 5.64ms" 대응) — baseline runner가 이미 기록하는 t_mpc_solve_ms·t_step_ms 사용(원본 미수정).
2. v2 MPC solve와 S10 PyTorch·ONNX 추론(정규화 포함 e2e): 최소 포함 전체 통계(제출본 표 16·18 "최소" 대응) — 같은 MPC 호출 입력,
   benchmark_timing.py와 같은 방식(warmup 50 제외).
출력: docs/revision/data/r2_timing_supplement/{env.json, r2_timing.json}

사용(저장소 루트, Git Bash):
  python docs/revision/scripts/r2_timing_supplement.py --power-mode-confirmed --cooldown-before-sec 60
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import torch

from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.baseline.logger import save_json
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.runner import run_episode as base_run_episode
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.student_i4 import config as i4_config
from thesis_v2.improved.student_i4.benchmark_timing import timed_v2_episode, export_onnx
from thesis_v2.improved.student_i4.features import extend_features
from thesis_v2.improved.student_i4.model import Predictor

V2 = ROOT / "thesis_v2/results/i4_student_v2/20260925_092109_DESKTOP-MDCKRJS"
OUT = ROOT / "docs/revision/data/r2_timing_supplement"
SEEDS = list(range(0, 100))
LANE_CHANGE = ("EVADE_L", "KEEP_L1", "RETURN_TO_L2")


def st(a):
    a = np.asarray(a, float)
    if a.size == 0:
        return None
    return dict(n=int(a.size), mean=float(a.mean()), std=float(a.std()), min=float(a.min()),
                p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), p99=float(np.percentile(a, 99)),
                max=float(a.max()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--power-mode-confirmed", action="store_true")
    ap.add_argument("--cooldown-before-sec", type=int, default=0)
    ap.add_argument("--n-episodes", type=int, default=len(SEEDS), help="스모크 테스트용으로만 줄임(보고용은 기본 100)")
    ap.add_argument("--out", type=str, default=str(OUT))
    args = ap.parse_args()
    out_dir = Path(args.out)
    seeds = SEEDS[:args.n_episodes]
    if args.cooldown_before_sec > 0:
        print(f"cooldown {args.cooldown_before_sec}s ...", flush=True)
        time.sleep(args.cooldown_before_sec)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    import onnxruntime as ort
    env = collect_env_info(power_mode_confirmed=args.power_mode_confirmed)
    env.update(torch=torch.__version__, onnxruntime=ort.__version__, torch_threads=1, ort_threads=1)
    save_json(env, out_dir / "env.json")
    print("meets_official_condition =", env["power"]["meets_official_condition"], flush=True)

    # 1. baseline v1.1
    mpc = OSQPMPC()
    solve, step_by_state, step_all = [], {}, []
    for s in seeds:
        r = base_run_episode(generate_scenario(s), mpc=mpc)
        for row in r.logger.rows:
            step_all.append(row["t_step_ms"])
            step_by_state.setdefault(row["state"], []).append(row["t_step_ms"])
            if row["solver_status"] != "N/A":
                solve.append(row["t_mpc_solve_ms"])
    lane = [t for s_ in LANE_CHANGE for t in step_by_state.get(s_, [])]
    base = dict(mpc_solve_ms=st(solve), step_total_ms=st(step_all),
                step_by_state_ms={k: st(v) for k, v in step_by_state.items()}, step_lane_change_states_ms=st(lane))
    print("baseline done", flush=True)

    # 2. v2 MPC + S10 PyTorch/ONNX (같은 입력)
    pred = Predictor(V2 / "S10/checkpoints/policy_i4_best.pt", V2 / "S10/normalization_stats.json")
    onnx_path = out_dir / "s10.onnx"
    export_onnx(pred, onnx_path)
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(str(onnx_path), so, providers=["CPUExecutionProvider"])
    mpc2 = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    v2_ms, feats = [], []
    for s in seeds:
        m, _, f = timed_v2_episode(generate_scenario(s), mpc2)
        v2_ms += m
        feats += f
    X = extend_features(np.stack([f[0] for f in feats]), pred.variant,
                        np.array([f[1] for f in feats]), np.array([f[2] for f in feats])).astype(np.float32)
    pad = np.concatenate([X[:i4_config.TIMING_WARMUP], X])

    def loop(fn):
        ts = []
        for x in pad:
            t0 = time.perf_counter()
            fn(x)
            ts.append((time.perf_counter() - t0) * 1000.0)
        return ts[i4_config.TIMING_WARMUP:]

    pt = loop(lambda x: pred.predict(x))
    ox = loop(lambda x: pred.denormalize(sess.run(None, {"input": pred.normalize(x).reshape(1, -1)})[0][0]))
    res = dict(seeds=f"{seeds[0]}~{seeds[-1]} paper", baseline_v11=base, v2_mpc_solve_ms=st(v2_ms), s10_pytorch_e2e_ms=st(pt),
               s10_onnx_e2e_ms=st(ox), meets_official_condition=env["power"]["meets_official_condition"])
    with open(out_dir / "r2_timing.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: res[k] for k in ("v2_mpc_solve_ms", "s10_pytorch_e2e_ms", "s10_onnx_e2e_ms")}, indent=1))
    print("saved", out_dir)


if __name__ == "__main__":
    main()
