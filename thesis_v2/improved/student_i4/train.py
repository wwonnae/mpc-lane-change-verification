"""
I4 학습(DESIGN_I4 §2, 개정 1). Table 5: Adam, lr=1e-3, batch=256, epoch=50(전부 실행, 조기 종료
없음), 85/15 split(dataset_gen의 계층 분할 그대로). 손실: 정규화된 [δ, v_target] MSE, 가중 없음.
검증 손실 최저 epoch의 체크포인트를 채택한다.

사용(저장소 루트): python -m thesis_v2.improved.student_i4.train --run-dir <run> --seed 7
"""
import argparse
import json
import platform
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from . import config as i4_config
from .features import INPUT_VARIANTS, extend_features
from .model import StudentPolicy, compute_norm_stats


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, required=True)
    ap.add_argument("--seed", type=int, default=i4_config.DEFAULT_TRAIN_SEED)
    ap.add_argument("--inputs", choices=list(INPUT_VARIANTS), default="9",
                    help="입력 변형: 9(REQ-STU-02, I4) / S10(+ψ, [개정]) / S11(+ψ+δ_prev) -- DESIGN_I4 §6-7")
    ap.add_argument("--dataset-dir", type=str, default=None, help="기본값 <run-dir>/dataset")
    ap.add_argument("--epochs", type=int, default=i4_config.EPOCHS,
                    help="스모크 테스트용으로만 줄인다. 보고용 학습은 기본값 50")
    args = ap.parse_args()
    run = Path(args.run_dir)
    ckpt_dir = run / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    set_seed(args.seed)
    ds_dir = Path(args.dataset_dir) if args.dataset_dir else run / "dataset"
    d = np.load(ds_dir / "dataset.npz", allow_pickle=True)
    if args.inputs == "9":
        X_all = d["X"]
    else:
        X_all = extend_features(d["X"], args.inputs, d["psi_deg"], d["delta_prev_deg"])
    tr = d["split"] == "train"
    va = d["split"] == "val"
    X_tr, Y_tr, X_va, Y_va = X_all[tr], d["Y"][tr], X_all[va], d["Y"][va]

    stats = compute_norm_stats(X_tr, Y_tr, INPUT_VARIANTS[args.inputs])
    with open(run / "normalization_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    xm, xs = np.array(stats["X_mean"], np.float32), np.array(stats["X_std_safe"], np.float32)
    ym, ys = np.array(stats["Y_mean"], np.float32), np.array(stats["Y_std_safe"], np.float32)
    Xn_tr = torch.from_numpy((X_tr - xm) / xs)
    Yn_tr = torch.from_numpy((Y_tr - ym) / ys)
    Xn_va = torch.from_numpy((X_va - xm) / xs)
    Yn_va = torch.from_numpy((Y_va - ym) / ys)

    model = StudentPolicy(input_dim=X_all.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=i4_config.LEARNING_RATE)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min",
                                                       factor=i4_config.LR_PLATEAU_FACTOR,
                                                       patience=i4_config.LR_PLATEAU_PATIENCE)
    loss_fn = nn.MSELoss()
    gen = torch.Generator().manual_seed(args.seed)
    n = len(Xn_tr)

    history = []
    best = dict(val_loss=float("inf"), epoch=None)
    t0 = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(n, generator=gen)
        tot, cnt = 0.0, 0
        for i in range(0, n, i4_config.BATCH_SIZE):
            idx = perm[i:i + i4_config.BATCH_SIZE]
            if len(idx) < 2:
                continue  # BatchNorm은 배치 1에서 학습 불가 -- 마지막 1개짜리 배치만 건너뜀
            opt.zero_grad()
            loss = loss_fn(model(Xn_tr[idx]), Yn_tr[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), i4_config.GRAD_CLIP_NORM)
            opt.step()
            tot += loss.item() * len(idx)
            cnt += len(idx)
        train_loss = tot / cnt

        model.eval()
        with torch.no_grad():
            pred = model(Xn_va)
            val_loss = loss_fn(pred, Yn_va).item()
            pred_d = pred.numpy() * ys + ym
        err = pred_d - Y_va
        rec = dict(epoch=epoch, train_loss=train_loss, val_loss=val_loss,
                   lr=opt.param_groups[0]["lr"],
                   val_mae_delta_deg=float(np.abs(err[:, 0]).mean()),
                   val_rmse_delta_deg=float(np.sqrt((err[:, 0] ** 2).mean())),
                   val_mae_v=float(np.abs(err[:, 1]).mean()),
                   elapsed_sec=time.perf_counter() - t0)
        history.append(rec)
        sched.step(val_loss)
        state = dict(epoch=epoch, model_state_dict=model.state_dict(),
                     optimizer_state_dict=opt.state_dict(),
                     scheduler_state_dict=sched.state_dict(),
                     val_loss=val_loss, history=history, args=vars(args))
        torch.save(state, ckpt_dir / "last.pt")
        if val_loss < best["val_loss"]:
            best = dict(val_loss=val_loss, epoch=epoch)
            torch.save(dict(state, best_val_loss=val_loss, best_epoch=epoch),
                       ckpt_dir / "policy_i4_best.pt")
        print(f"epoch {epoch:2d} train={train_loss:.5f} val={val_loss:.5f} "
              f"valMAEδ={rec['val_mae_delta_deg']:.3f}° lr={rec['lr']:.1e}", flush=True)

    log = dict(seed=args.seed, epochs=args.epochs, inputs=args.inputs,
               feature_names=INPUT_VARIANTS[args.inputs], dataset_dir=str(ds_dir), n_train=int(n), n_val=int(len(Xn_va)),
               hyperparams=dict(lr=i4_config.LEARNING_RATE, batch=i4_config.BATCH_SIZE,
                                dropout=i4_config.DROPOUT, grad_clip=i4_config.GRAD_CLIP_NORM,
                                plateau_factor=i4_config.LR_PLATEAU_FACTOR,
                                plateau_patience=i4_config.LR_PLATEAU_PATIENCE, loss="MSE(unweighted)"),
               best_epoch=best["epoch"], best_val_loss=best["val_loss"],
               final_val_loss=history[-1]["val_loss"], history=history,
               env=dict(torch=torch.__version__, python=platform.python_version(),
                        device="cpu", cuda_available=torch.cuda.is_available(),
                        host=platform.node()))
    with open(run / "train_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"best epoch={best['epoch']} val_loss={best['val_loss']:.6f}")


if __name__ == "__main__":
    main()
