"""B2 1D 합성곱 오토인코더 구조와 학습 루프 — DESIGN.md §13-4에 학습 전 확정한 설정 그대로."""
import copy
from typing import Dict, List, Tuple

import numpy as np
import torch
from torch import nn

from .features_b import N_CH, W

LATENT = 8
LR = 1e-3
BATCH = 256
MAX_EPOCHS = 100
PATIENCE = 10
SEED = 0
N_THREADS = 1


class ConvAE(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(N_CH, 32, 3, padding=1), nn.ReLU(),
            nn.Conv1d(32, 16, 3, padding=1), nn.ReLU(),
            nn.Flatten(), nn.Linear(16 * W, LATENT))
        self.decoder = nn.Sequential(
            nn.Linear(LATENT, 16 * W), nn.ReLU(), nn.Unflatten(1, (16, W)),
            nn.Conv1d(16, 32, 3, padding=1), nn.ReLU(),
            nn.Conv1d(32, N_CH, 3, padding=1))

    def forward(self, x):  # x: (n, C, W)
        return self.decoder(self.encoder(x))


def set_determinism() -> None:
    torch.manual_seed(SEED)
    torch.set_num_threads(N_THREADS)
    torch.use_deterministic_algorithms(True)


def _to_tensor(win: np.ndarray) -> torch.Tensor:
    """(n, W, C) float64 → (n, C, W) float32."""
    return torch.from_numpy(np.ascontiguousarray(win.transpose(0, 2, 1), dtype=np.float32))


def _mean_mse(model: nn.Module, X: torch.Tensor, chunk: int = 4096) -> float:
    model.eval()
    tot = 0.0
    with torch.no_grad():
        for i in range(0, len(X), chunk):
            xb = X[i:i + chunk]
            tot += float(((model(xb) - xb) ** 2).mean(dim=(1, 2)).sum())
    return tot / len(X)


def train_ae(win_train: np.ndarray, win_val: np.ndarray) -> Tuple[ConvAE, List[Dict], int]:
    set_determinism()
    Xtr, Xva = _to_tensor(win_train), _to_tensor(win_val)
    model = ConvAE()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    gen = torch.Generator().manual_seed(SEED)
    best, best_state, best_epoch, bad = float("inf"), None, 0, 0
    log = []
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(Xtr), generator=gen)
        tot = 0.0
        for i in range(0, len(Xtr), BATCH):
            xb = Xtr[perm[i:i + BATCH]]
            loss = ((model(xb) - xb) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(xb)
        val = _mean_mse(model, Xva)
        improved = val < best
        if improved:
            best, best_state, best_epoch, bad = val, copy.deepcopy(model.state_dict()), epoch, 0
        else:
            bad += 1
        log.append(dict(epoch=epoch, train_mse=tot / len(Xtr), val_mse=val, best=improved))
        if bad >= PATIENCE:
            break
    model.load_state_dict(best_state)
    return model.eval(), log, best_epoch
