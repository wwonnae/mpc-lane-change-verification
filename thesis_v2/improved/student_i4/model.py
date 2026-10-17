"""
I4 Student 신경망(REQ-STU-01 구조 그대로: 9 -> 256 -> 256 -> 128 -> 2, Linear+BatchNorm+ReLU+
Dropout(0.15) 블록 반복). tests/compare/student_model.py와 같은 구조이지만 improved/는 tests/를
import하지 않으므로 여기서 새로 정의한다. 가중치·정규화 통계는 I4 결과 폴더의 것만 쓴다.
"""
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
import torch.nn as nn

from . import config as i4_config
from .features import FEATURE_NAMES, LABEL_NAMES, INPUT_VARIANTS, extend_features, build_feature_vector


class StudentPolicy(nn.Module):
    def __init__(self, input_dim: int = 9, hidden_dims=i4_config.HIDDEN_DIMS, output_dim: int = 2,
                 dropout: float = i4_config.DROPOUT):
        super().__init__()
        layers: List[nn.Module] = []
        prev = input_dim
        for h in hidden_dims:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, output_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)


def compute_norm_stats(X: np.ndarray, Y: np.ndarray, feature_names=FEATURE_NAMES) -> Dict:
    """학습 split만으로 계산(DESIGN_I4 §2-1). std=0 차원은 분모 1(0 나눗셈 방지)."""
    x_std = X.std(axis=0)
    y_std = Y.std(axis=0)
    return {
        "feature_names": list(feature_names), "label_names": LABEL_NAMES,
        "X_mean": X.mean(axis=0).tolist(), "X_std": x_std.tolist(),
        "Y_mean": Y.mean(axis=0).tolist(), "Y_std": y_std.tolist(),
        "X_std_safe": np.where(x_std == 0, 1.0, x_std).tolist(),
        "Y_std_safe": np.where(y_std == 0, 1.0, y_std).tolist(),
    }


class Predictor:
    """정규화 포함 단건 추론(PyTorch). 폐루프·MAE·계산시간 공통 경로."""

    def __init__(self, checkpoint_path: Path, stats_path: Path):
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        with open(stats_path, "r", encoding="utf-8") as f:
            st = json.load(f)
        assert st["label_names"] == LABEL_NAMES
        self.variant = next(k for k, v in INPUT_VARIANTS.items() if v == st["feature_names"])
        self.input_dim = len(st["feature_names"])
        self.model = StudentPolicy(input_dim=self.input_dim)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        self.X_mean = np.array(st["X_mean"], dtype=np.float32)
        self.X_std = np.array(st["X_std_safe"], dtype=np.float32)
        self.Y_mean = np.array(st["Y_mean"], dtype=np.float32)
        self.Y_std = np.array(st["Y_std_safe"], dtype=np.float32)

    def build(self, v, ey, y, state, front_gap, left_clear, psi_deg, delta_prev_deg) -> np.ndarray:
        """변형(9/S10/S11)에 맞는 입력 벡터. 폐루프·계산시간 공통."""
        return extend_features(build_feature_vector(v, ey, y, state, front_gap, left_clear),
                               self.variant, psi_deg, delta_prev_deg)

    def normalize(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.X_mean) / self.X_std).astype(np.float32)

    def denormalize(self, Yn: np.ndarray) -> np.ndarray:
        return Yn * self.Y_std + self.Y_mean

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            yn = self.model(torch.from_numpy(self.normalize(X))).numpy()
        return self.denormalize(yn)

    def predict(self, x: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            yn = self.model(torch.from_numpy(self.normalize(x).reshape(1, -1))).numpy()[0]
        return self.denormalize(yn)
