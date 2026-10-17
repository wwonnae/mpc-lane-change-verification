"""
M트랙(2단계-D) 전용: legacy_2025/models/policy_best.pth 로드 유틸.
REQ-STU-02/03/04. 재학습 없음, legacy_2025/models/ 수정 없음(repro/docs/WORK_RULES.md 핵심 주장 3).

네트워크 구조는 legacy_2025/models/policy_best.pth의 state_dict shape로부터 확인된 사실
(MEASURE_PLAN.md M트랙 §"전제 조건 사전 확인": network.0=(256,9), network.4=(256,256),
network.8=(128,256), network.12=(2,128), BatchNorm 3곳)을 그대로 재구현한 것이다.
legacy_2025/code_backup/train_student_v2.py의 StudentPolicy(input_dim=9, hidden_dims=[256,256,128],
output_dim=2, use_batchnorm=True)와 동일 구조 — import는 하지 않고(thesis_v2는 기존 코드
import 금지, tests/compare/만 예외지만 이 구조 자체는 모델 파일에서 직접 확인 가능하므로
import 없이 shape만 근거로 재작성) 독립적으로 재정의한다.
"""
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
import torch.nn as nn

MODELS_DIR = Path(__file__).resolve().parents[3] / "legacy_2025" / "models"
CHECKPOINT_PATH = MODELS_DIR / "policy_best.pth"
STATS_PATH = MODELS_DIR / "normalization_stats.json"

# REQ-STU-02: 입력 9차원, 순서 고정 (normalization_stats.json feature_names과 일치해야 함)
EXPECTED_FEATURE_NAMES = [
    "v", "ey_line", "front_gap", "left_clear",
    "state_KEEP_L2", "state_EVADE_L", "state_KEEP_L1", "state_RETURN_TO_L2", "state_SAFE_STOP",
]
EXPECTED_LABEL_NAMES = ["delta", "v"]

STATE_ORDER = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2", "SAFE_STOP"]


class StudentPolicy(nn.Module):
    """checkpoint shape로 확인된 구조: 9 -> 256 -> 256 -> 128 -> 2, BatchNorm1d x3."""

    def __init__(self, input_dim: int = 9, hidden_dims=(256, 256, 128), output_dim: int = 2,
                 dropout: float = 0.15):
        super().__init__()
        # 체크포인트 키 인덱스(network.0/1/2/3, network.4/5/6/7, ...)가 Linear,BatchNorm,ReLU,
        # Dropout 4개 단위로 반복되므로(legacy_2025/code_backup/train_student_v2.py:StudentPolicy와 동일
        # 구조), eval()에서 항등 함수인 Dropout도 인덱스 정렬을 위해 그대로 포함한다.
        layers: List[nn.Module] = []
        prev = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.BatchNorm1d(h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, output_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)


def load_normalization_stats() -> Dict[str, Any]:
    with open(STATS_PATH, "r", encoding="utf-8") as f:
        stats = json.load(f)
    if stats["feature_names"] != EXPECTED_FEATURE_NAMES:
        raise RuntimeError(
            "normalization_stats.json feature_names이 REQ-STU-02 순서와 다릅니다: "
            f"{stats['feature_names']}"
        )
    if stats["label_names"] != EXPECTED_LABEL_NAMES:
        raise RuntimeError(
            f"normalization_stats.json label_names이 REQ-STU-03 순서와 다릅니다: {stats['label_names']}"
        )
    return stats


def load_student_model() -> nn.Module:
    """weights_only=False 필요(체크포인트에 args 등 비텐서 객체 포함,
    MEASURE_PLAN.md M트랙 §"전제 조건 사전 확인" 실측 확인 사항)."""
    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
    model = StudentPolicy()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()  # BatchNorm running stats 사용 필수(배치=1 추론 시 필수)
    return model


class StudentPredictor:
    """정규화 포함 end-to-end 추론과, 정규화 제외 "추론만" 측정을 분리 지원."""

    def __init__(self):
        self.model = load_student_model()
        stats = load_normalization_stats()
        self.X_mean = np.array(stats["X_mean"], dtype=np.float32)
        self.X_std = np.array(stats["X_std"], dtype=np.float32)
        self.Y_mean = np.array(stats["Y_mean"], dtype=np.float32)
        self.Y_std = np.array(stats["Y_std"], dtype=np.float32)
        # X_std의 마지막 두 원소(state_RETURN_TO_L2, state_SAFE_STOP)가 0인 경우 분모가 0이
        # 되므로(REQ-STU-04 "정규화 통계 그대로 사용" 원칙 하에 나눗셈만 안전 가드) 안전 처리.
        self._x_std_safe = np.where(self.X_std == 0, 1.0, self.X_std)

    def normalize(self, features: np.ndarray) -> np.ndarray:
        return (features - self.X_mean) / self._x_std_safe

    def z_scores(self, features: np.ndarray) -> np.ndarray:
        return (features - self.X_mean) / self._x_std_safe

    def infer_only(self, x_norm_tensor: torch.Tensor) -> torch.Tensor:
        """정규화가 이미 끝난 텐서를 받아 순전파만 수행(추론시간 "추론만" 측정용)."""
        with torch.no_grad():
            return self.model(x_norm_tensor)

    def predict(self, features: np.ndarray) -> np.ndarray:
        """정규화 전처리 포함 end-to-end 추론(측정용 "정규화 포함" 경로와 동일 코드 경로)."""
        x = self.normalize(features).astype(np.float32).reshape(1, -1)
        x_t = torch.from_numpy(x)
        with torch.no_grad():
            y_norm = self.model(x_t).numpy()[0]
        return y_norm * self.Y_std + self.Y_mean


def build_feature_vector(v: float, ey: float, front_gap: float, left_clear: bool,
                          state: str) -> np.ndarray:
    """REQ-STU-02 순서: [v, ey, front_gap, left_clear, state_one_hot(5)].
    state_one_hot 순서는 STATE_ORDER(=normalization_stats.json feature_names 순서)."""
    one_hot = [1.0 if state == s else 0.0 for s in STATE_ORDER]
    return np.array([float(v), float(ey), float(front_gap), 1.0 if left_clear else 0.0,
                      *one_hot], dtype=np.float32)
