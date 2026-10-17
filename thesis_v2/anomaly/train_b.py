"""
3단계: 탐지기 B 학습 (DESIGN.md §13-4). 정상(고장 없음) 에피소드만 사용한다.

- 학습 seed 3300~3379: 정규화 통계, IF 학습, AE 학습
- 검증 seed 3380~3399: AE 조기 종료만
- PC 간 IF 동일성 확인용 고정 입력: 정상 dev seed 3200~3209(원거리)의 윈도우(점수 비교에만 쓰고 학습·임계값에 쓰지 않음)
- iteration 2(§17)부터 학습·검증 정상 데이터 = 원거리 + 좌측 장애물 시나리오(config.NORMAL_SCENARIOS)

사용:
  python -m thesis_v2.anomaly.train_b --out-root thesis_v2/results/anomaly          # 노트북에서 1회(IF+AE)
  python -m thesis_v2.anomaly.train_b --if-identity-check <학습 결과 폴더>          # 다른 PC: IF만 다시 학습해 점수 비교
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
from .features_b import Norm, ObsRecorder, episode_step_matrix, windows, window_stats, N_CH, W, CHANNEL_NAMES

IF_PARAMS = dict(n_estimators=200, max_samples="auto", max_features=1.0, bootstrap=False, random_state=0, n_jobs=1)
IDENTITY_SEEDS = list(range(3200, 3210))  # 정상 dev — 고정 입력
assert set(IDENTITY_SEEDS) <= set(an_config.SEEDS_FAULT_DEV)


def collect_steps(seeds, scenarios=an_config.NORMAL_SCENARIOS_IT1):
    """(시나리오, seed)별 step 특징 행렬(정규화 전) 목록."""
    out = []
    for sc, s in normal_runs(seeds, scenarios):
        rec = ObsRecorder()
        run_anomaly_episode(s, left_obstacle=is_leftobs(sc), detector=rec, record_alog=False)
        out.append(episode_step_matrix(rec.obs))
    return out


def build(seeds_train, seeds_val, scenarios=an_config.NORMAL_SCENARIOS_IT1):
    tr = collect_steps(seeds_train, scenarios)
    norm = Norm.fit(np.concatenate(tr))
    win_tr = np.concatenate([windows(norm.apply(X)) for X in tr])
    win_va = np.concatenate([windows(norm.apply(X)) for X in collect_steps(seeds_val, scenarios)])
    win_id = np.concatenate([windows(norm.apply(X)) for X in collect_steps(IDENTITY_SEEDS)])  # 원거리만(고정)
    return norm, win_tr, win_va, win_id


def fit_if(win_tr):
    from sklearn.ensemble import IsolationForest
    return IsolationForest(**IF_PARAMS).fit(window_stats(win_tr))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--if-identity-check", default=None, help="노트북 학습 결과 폴더(IF만 다시 학습해 비교)")
    args = ap.parse_args()
    seeds_tr, seeds_va = an_config.SEEDS_B_TRAIN, an_config.SEEDS_B_VAL

    scenarios = an_config.NORMAL_SCENARIOS
    if args.if_identity_check:
        ref_meta = json.loads((Path(args.if_identity_check) / "meta.json").read_text(encoding="utf-8"))
        scenarios = tuple(ref_meta.get("scenarios", an_config.NORMAL_SCENARIOS_IT1))
    t0 = time.time()
    norm, win_tr, win_va, win_id = build(seeds_tr, seeds_va, scenarios)
    print(f"윈도우: 학습 {len(win_tr)}, 검증 {len(win_va)}, 동일성 확인 {len(win_id)} ({time.time() - t0:.0f}s)", flush=True)

    if args.if_identity_check:
        ref = Path(args.if_identity_check)
        meta = json.loads((ref / "meta.json").read_text(encoding="utf-8"))
        same_data = array_sha(win_tr) == meta["train_windows_sha256"]
        ref_scores = np.loadtxt(ref / "if_identity_scores.csv", delimiter=",", skiprows=1, usecols=1)
        scores = -fit_if(win_tr).score_samples(window_stats(win_id))
        diff = float(np.max(np.abs(scores - ref_scores)))
        out = new_out_dir(args.out_root, "stage3_if_identity_check")
        res = dict(reference=str(ref), same_train_windows=same_data, n=len(scores), max_abs_diff=diff,
                   identical=bool(diff == 0.0))
        (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        write_env(out, dict(purpose="IF PC 간 동일성 확인"))
        print(f"학습 윈도우 동일: {same_data}, IF 점수 최대 차이 {diff!r} ({'동일' if diff == 0 else '다름'}) → {out}")
        sys.exit(0 if (same_data and diff == 0.0) else 1)

    out = new_out_dir(args.out_root, f"it{an_config.ITERATION}_train_b")
    norm.to_json(out / "norm.json")

    t1 = time.time()
    iso = fit_if(win_tr)
    with open(out / "if_model.pkl", "wb") as f:
        pickle.dump(iso, f)
    id_scores = -iso.score_samples(window_stats(win_id))
    write_csv(out / "if_identity_scores.csv", ["i", "score"], [dict(i=i, score=float(v)) for i, v in enumerate(id_scores)])
    t_if = time.time() - t1
    print(f"IF 학습 {t_if:.1f}s", flush=True)

    import torch
    from .ae_model import train_ae, LATENT, LR, BATCH, MAX_EPOCHS, PATIENCE, SEED, N_THREADS
    t2 = time.time()
    model, log, best_epoch = train_ae(win_tr, win_va)
    torch.save(model.state_dict(), out / "ae_model.pt")
    t_ae = time.time() - t2
    write_csv(out / "train_log.csv", ["epoch", "train_mse", "val_mse", "best"], log)
    print(f"AE 학습 {t_ae:.1f}s, epoch {len(log)}, 최적 epoch {best_epoch}, 검증 MSE {log[best_epoch - 1]['val_mse']:.6f}")

    meta = dict(
        purpose="3단계 탐지기 B 학습(정상 데이터만)", iteration=an_config.ITERATION, scenarios=list(scenarios),
        seeds_train=[seeds_tr[0], seeds_tr[-1]],
        seeds_val=[seeds_va[0], seeds_va[-1]], seeds_identity=[IDENTITY_SEEDS[0], IDENTITY_SEEDS[-1]],
        n_windows=dict(train=len(win_tr), val=len(win_va), identity=len(win_id)), window=W, channels=list(CHANNEL_NAMES),
        train_windows_sha256=array_sha(win_tr), sigma_gyro_deg=an_config.SIGMA_GYRO_DEG,
        if_params=IF_PARAMS, if_model_sha256=sha256(out / "if_model.pkl"), if_train_seconds=t_if,
        ae=dict(latent=LATENT, lr=LR, batch=BATCH, max_epochs=MAX_EPOCHS, patience=PATIENCE, seed=SEED,
                torch_threads=N_THREADS, deterministic=True, epochs_run=len(log), best_epoch=best_epoch,
                best_val_mse=log[best_epoch - 1]["val_mse"], train_seconds=t_ae),
        ae_model_sha256=sha256(out / "ae_model.pt"), norm_sha256=sha256(out / "norm.json"))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_env(out, dict(purpose=meta["purpose"], torch_num_threads=torch.get_num_threads(),
                        torch_version=torch.__version__))
    print("saved:", out)


if __name__ == "__main__":
    main()
