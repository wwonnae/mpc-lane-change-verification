"""
탐지기 B 입력 특징 (DESIGN.md §13-4). DetectorObs만 사용한다(탐지기 A와 같은 관측 + 자이로 g_k).

step 특징 15채널 → 학습 seed 정규화 → 길이 W=10 윈도우(step k에서 끝나는 윈도우의 점수를 step k에 둔다).
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from .detector_a import _no_return
from .runner import DetectorObs, DetectorOutput

W = 10
FSM_ORDER = ("KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2", "SAFE_STOP")
CHANNEL_NAMES = ("fg", "fg_noret", "dfg", "ey", "ey_none", "left_clear", "right_clear", "delta_prev_cmd_deg",
                 "yaw_rate_meas", "v") + tuple(f"fsm_{s}" for s in FSM_ORDER)
N_CH = len(CHANNEL_NAMES)
assert N_CH == 15
STAT_NAMES = ("mean", "std", "min", "max", "last_minus_first")


def step_features(obs: DetectorObs, prev: Optional[DetectorObs]) -> np.ndarray:
    fr = obs.frame
    x = np.zeros(N_CH, dtype=np.float64)
    noret = _no_return(fr.front_gap)
    x[0] = 0.0 if noret else fr.front_gap
    x[1] = 1.0 if noret else 0.0
    if prev is not None and not noret and not _no_return(prev.frame.front_gap):
        x[2] = fr.front_gap - prev.frame.front_gap
    x[3] = 0.0 if fr.ey_line is None else fr.ey_line
    x[4] = 1.0 if fr.ey_line is None else 0.0
    x[5] = 1.0 if fr.left_clear else 0.0
    x[6] = 1.0 if fr.right_clear else 0.0
    x[7] = obs.delta_prev_cmd_deg
    x[8] = 0.0 if obs.yaw_rate_meas is None else obs.yaw_rate_meas
    x[9] = obs.v
    x[10 + FSM_ORDER.index(obs.fsm_state)] = 1.0
    return x


def episode_step_matrix(obs_list: List[DetectorObs]) -> np.ndarray:
    rows, prev = [], None
    for o in obs_list:
        rows.append(step_features(o, prev))
        prev = o
    return np.asarray(rows, dtype=np.float64).reshape(-1, N_CH)


def windows(X: np.ndarray) -> np.ndarray:
    """(T, C) → (T−W+1, W, C). i번째 윈도우는 step i+W(1-based)에서 끝난다."""
    T = X.shape[0]
    if T < W:
        return np.zeros((0, W, X.shape[1]), dtype=X.dtype)
    return np.stack([X[i:i + W] for i in range(T - W + 1)])


def window_stats(win: np.ndarray) -> np.ndarray:
    """(n, W, C) → (n, 5·C): 통계 순서 STAT_NAMES, 각 통계 안에서 채널 순서."""
    return np.concatenate([win.mean(axis=1), win.std(axis=1), win.min(axis=1), win.max(axis=1),
                           win[:, -1, :] - win[:, 0, :]], axis=1)


@dataclass
class Norm:
    mean: np.ndarray
    std: np.ndarray

    @staticmethod
    def fit(X: np.ndarray) -> "Norm":
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std = np.where(std < 1e-12, 1.0, std)
        return Norm(mean, std)

    def apply(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean) / self.std

    def to_json(self, path: Path) -> None:
        Path(path).write_text(json.dumps(dict(channels=list(CHANNEL_NAMES), mean=[float(v) for v in self.mean],
                                              std=[float(v) for v in self.std]), indent=2), encoding="utf-8")

    @staticmethod
    def from_json(path: Path) -> "Norm":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        assert tuple(d["channels"]) == CHANNEL_NAMES
        return Norm(np.asarray(d["mean"], dtype=np.float64), np.asarray(d["std"], dtype=np.float64))


class ObsRecorder:
    """관측만 저장하는 관찰 전용 탐지기(오프라인 탐지기 적용용). 경보를 내지 않는다."""

    def __init__(self):
        self.obs: List[DetectorObs] = []

    def reset(self) -> None:
        self.obs = []

    def update(self, obs: DetectorObs) -> DetectorOutput:
        self.obs.append(obs)
        return DetectorOutput(score=0.0, alarm=False)
