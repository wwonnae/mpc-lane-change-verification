"""
I4 MAE 평가(DESIGN_I4 §3-1, 개정 1). eval paper seed 200~299에서 v2 MPC를 주행시키며 각 MPC 호출
입력을 캡처하고, 같은 입력으로 (주) v2 MPC δ, (참고) baseline v1.1 MPC δ(그림자 호출, 조향에
미사용)와 Student δ를 비교한다. δ 중심, v_target은 참고 지표. 옛 MPC(12-04)는 쓰지 않는다.

사용(저장소 루트): python -m thesis_v2.improved.student_i4.evaluate_mae --run-dir <run>
"""
import argparse
import json
from pathlib import Path

import numpy as np

from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

from . import config as i4_config
from .features import SolveRecorder, pair_calls_with_log, MPC_STATES, extend_features
from .model import Predictor


def collect_eval_samples(seeds):
    mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    rec = SolveRecorder(mpc)
    base = OSQPMPC()
    rows = []
    for s in seeds:
        res = improved_run_episode(generate_scenario(s), mpc=mpc)
        for smp in pair_calls_with_log(rec.pop(), res.logger.rows):
            b = base.solve(y0=smp["y0"], psi0_rad=smp["psi0_rad"], v0=smp["v0"],
                           target_y=smp["target_y"], state_name=smp["state"])
            smp["delta_base_deg"] = float(b.delta_deg)
            smp["seed"] = s
            rows.append(smp)
    return rows


def _err_stats(e):
    a = np.abs(e)
    return dict(n=int(a.size), mae=float(a.mean()), p95=float(np.percentile(a, 95)),
                max=float(a.max())) if a.size else dict(n=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, required=True,
                    help="결과 기준 폴더. --model 미지정 시 이 폴더의 모델 1개를 평가(I4 방식)")
    ap.add_argument("--seeds", choices=["eval", "eval3", "smoke"], default="eval",
                    help="eval: 200~299(I4), eval3: 2000~2099(Student v2 최종 확인, 1회만), smoke: dev 100~102")
    ap.add_argument("--smoke", action="store_true", help="--seeds smoke와 같음(하위 호환)")
    ap.add_argument("--model", action="append", default=[],
                    help="NAME=DIR 형식, 여러 번 지정 가능(같은 입력으로 함께 평가, DESIGN_I4 §6-5)")
    args = ap.parse_args()
    run = Path(args.run_dir)
    which = "smoke" if args.smoke else args.seeds
    seeds = {"smoke": [100, 101, 102], "eval": i4_config.EVAL_PAPER_SEEDS,
             "eval3": i4_config.EVAL3_PAPER_SEEDS}[which]
    out_dir = run / {"smoke": "eval_smoke", "eval": "eval", "eval3": "eval3"}[which]
    out_dir.mkdir(parents=True, exist_ok=True)
    models = dict(m.split("=", 1) for m in args.model) if args.model else {"student": str(run)}

    rows = collect_eval_samples(seeds)
    X9 = np.stack([r["x"] for r in rows])
    psi = np.array([r["psi_deg"] for r in rows])
    dprev = np.array([r["delta_prev_deg"] for r in rows])
    d_v2 = np.array([r["delta_deg"] for r in rows])
    d_base = np.array([r["delta_base_deg"] for r in rows])
    v_t = np.array([r["v_target"] for r in rows])
    states = np.array([r["state"] for r in rows])

    result = dict(
        data=f"paper seed {seeds[0]}~{seeds[-1]} ({which}), v2 MPC 주행 궤적의 MPC 호출 스텝 전부(선별 없음)",
        baseline_reference="thesis_v2.baseline.mpc.OSQPMPC 그림자 호출(같은 입력, 조향 미사용)",
        v2_vs_baseline_ref={st: _err_stats(d_v2[states == st] - d_base[states == st]) for st in MPC_STATES},
        models={},
    )
    preds_out = {}
    for name, md in models.items():
        md = Path(md)
        pred = Predictor(md / "checkpoints" / "policy_i4_best.pt", md / "normalization_stats.json")
        X = extend_features(X9, pred.variant, psi, dprev)
        Yp = pred.predict_batch(X)
        preds_out[name] = Yp
        z = np.abs((X[:, :4] - pred.X_mean[:4]) / pred.X_std[:4])
        ood = (z > 3).any(axis=1)

        def block(mask):
            return dict(
                n=int(mask.sum()),
                delta_vs_v2=_err_stats(Yp[mask, 0] - d_v2[mask]),
                delta_vs_baseline_ref=_err_stats(Yp[mask, 0] - d_base[mask]),
                v2_vs_baseline_ref=_err_stats(d_v2[mask] - d_base[mask]),
                v_target_mae_ref=float(np.abs(Yp[mask, 1] - v_t[mask]).mean()) if mask.any() else None,
                raw_over_25=float((np.abs(Yp[mask, 0]) > 25 + 1e-9).mean()) if mask.any() else None,
                ood_rate=float(ood[mask].mean()) if mask.any() else None,
                ey_fallback_rate=float(np.mean([rows[i]["ey_is_fallback"] for i in np.nonzero(mask)[0]]))
                if mask.any() else None,
            )

        result["models"][name] = dict(dir=str(md), variant=pred.variant,
                                      overall=block(np.ones(len(rows), bool)),
                                      by_state={st: block(states == st) for st in MPC_STATES})
    if not args.model:  # I4 방식 하위 호환(단일 모델 결과를 최상위에)
        result.update(overall=result["models"]["student"]["overall"],
                      by_state=result["models"]["student"]["by_state"])
    fname = "mae.json" if not args.model else "mae_models.json"
    with open(out_dir / fname, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    np.savez_compressed(out_dir / fname.replace(".json", "_samples.npz"), X9=X9, psi_deg=psi,
                        delta_prev_deg=dprev, delta_v2=d_v2, delta_base=d_base, state=states,
                        seed=np.array([r["seed"] for r in rows]),
                        **{f"pred_{k}": v for k, v in preds_out.items()})
    print(json.dumps({k: {"ALL_mae_vs_v2": v["overall"]["delta_vs_v2"]["mae"]} for k, v in result["models"].items()},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
