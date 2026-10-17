"""
하이브리드 탐지기(B1 + A 잔차) 학습 — DESIGN.md §20. IF만(B2 AE 확장 없음). 정상(고장 없음) 에피소드만 쓴다.

- 학습 seed 3300~3379 × {원거리, 좌측 장애물}(train_b.py와 같은 대역) — IF는 조기 종료가 없어 검증 seed는 쓰지 않음.
- PC 간 IF 동일성 확인용 고정 입력: 정상 dev seed 3200~3209(원거리) — train_b.py와 같은 대역.

사용:
  python -m thesis_v2.anomaly.train_hybrid --out-root thesis_v2/results/anomaly
  python -m thesis_v2.anomaly.train_hybrid --if-identity-check <학습 결과 폴더>
"""
import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from . import config as an_config
from .common import run_anomaly_episode, new_out_dir, write_env, write_csv, is_leftobs, normal_runs
from .hybrid import HybridObsRecorder, Norm, episode_step_matrix, CHANNEL_NAMES
from .features_b import windows, window_stats
from .train_b import IF_PARAMS, IDENTITY_SEEDS, sha256, array_sha, fit_if


def collect_steps(seeds, scenarios=an_config.NORMAL_SCENARIOS_IT1):
    out = []
    for sc, s in normal_runs(seeds, scenarios):
        rec = HybridObsRecorder()
        run_anomaly_episode(s, left_obstacle=is_leftobs(sc), detector=rec, record_alog=False)
        out.append(episode_step_matrix(rec.obs, rec.a_res))
    return out


def build(seeds_train, scenarios=an_config.NORMAL_SCENARIOS_IT1):
    tr = collect_steps(seeds_train, scenarios)
    norm = Norm.fit(np.concatenate(tr))
    win_tr = np.concatenate([windows(norm.apply(X)) for X in tr])
    win_id = np.concatenate([windows(norm.apply(X)) for X in collect_steps(IDENTITY_SEEDS)])  # 원거리만(고정)
    return norm, win_tr, win_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--if-identity-check", default=None, help="노트북/다른 PC 학습 결과 폴더(IF만 다시 학습해 비교)")
    args = ap.parse_args()
    seeds_tr = an_config.SEEDS_B_TRAIN

    scenarios = an_config.NORMAL_SCENARIOS
    if args.if_identity_check:
        ref_meta = json.loads((Path(args.if_identity_check) / "meta.json").read_text(encoding="utf-8"))
        scenarios = tuple(ref_meta.get("scenarios", an_config.NORMAL_SCENARIOS_IT1))
    t0 = time.time()
    norm, win_tr, win_id = build(seeds_tr, scenarios)
    print(f"윈도우: 학습 {len(win_tr)}, 동일성 확인 {len(win_id)} ({time.time() - t0:.0f}s)", flush=True)

    if args.if_identity_check:
        ref = Path(args.if_identity_check)
        meta = json.loads((ref / "meta.json").read_text(encoding="utf-8"))
        same_data = array_sha(win_tr) == meta["train_windows_sha256"]
        ref_scores = np.loadtxt(ref / "if_identity_scores.csv", delimiter=",", skiprows=1, usecols=1)
        scores = -fit_if(win_tr).score_samples(window_stats(win_id))
        diff = float(np.max(np.abs(scores - ref_scores)))
        out = new_out_dir(args.out_root, "hybrid_if_identity_check")
        res = dict(reference=str(ref), same_train_windows=same_data, n=len(scores), max_abs_diff=diff,
                   identical=bool(diff == 0.0))
        (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        write_env(out, dict(purpose="하이브리드 IF PC 간 동일성 확인"))
        print(f"학습 윈도우 동일: {same_data}, IF 점수 최대 차이 {diff!r} ({'동일' if diff == 0 else '다름'}) → {out}")
        sys.exit(0 if (same_data and diff == 0.0) else 1)

    out = new_out_dir(args.out_root, f"it{an_config.ITERATION}_train_hybrid")
    norm.to_json(out / "norm.json")

    t1 = time.time()
    iso = fit_if(win_tr)
    with open(out / "if_model.pkl", "wb") as f:
        pickle.dump(iso, f)
    id_scores = -iso.score_samples(window_stats(win_id))
    write_csv(out / "if_identity_scores.csv", ["i", "score"],
              [dict(i=i, score=float(v)) for i, v in enumerate(id_scores)])
    t_if = time.time() - t1
    print(f"IF 학습 {t_if:.1f}s", flush=True)

    meta = dict(
        purpose="하이브리드 탐지기 학습(B1 특징 + A 잔차, 정상 데이터만, §20)", iteration=an_config.ITERATION,
        scenarios=list(scenarios), seeds_train=[seeds_tr[0], seeds_tr[-1]],
        seeds_identity=[IDENTITY_SEEDS[0], IDENTITY_SEEDS[-1]],
        n_windows=dict(train=len(win_tr), identity=len(win_id)), window=10, channels=list(CHANNEL_NAMES),
        train_windows_sha256=array_sha(win_tr),
        sigma_gyro_deg=an_config.SIGMA_GYRO_DEG, if_params=IF_PARAMS,
        if_model_sha256=sha256(out / "if_model.pkl"), if_train_seconds=t_if,
        norm_sha256=sha256(out / "norm.json"))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_env(out, dict(purpose=meta["purpose"]))
    print("saved:", out)


if __name__ == "__main__":
    main()
