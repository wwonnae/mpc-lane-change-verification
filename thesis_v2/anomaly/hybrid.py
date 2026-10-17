"""
하이브리드 탐지기(B1 + A 잔차) — DESIGN.md §20(2026-10-02, 학습 전 기록). 확장 항목.

B1(features_b.py)의 15채널에 탐지기 A(detector_a.py, iteration 3 — ir_miss 포함)의 `_residuals()` 원시값
7채널을 이어붙인다(마스크 None→0.0, 별도 플래그 채널 없음, §20). A의 CUSUM·추적기 코드는 한 글자도 바꾸지
않는다 — `HybridObsRecorder`가 내부에서 보통의 `DetectorA()`를 돌려 `DetectorOutput.residuals`만 가져온다.
모델은 B1과 같은 IsolationForest(§13-4), 하이브리드는 B2(AE) 확장이 없다.
"""
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from .detector_a import DetectorA, CHANNELS as A_CHANNELS
from .features_b import (CHANNEL_NAMES as B_CHANNEL_NAMES, step_features as _b_step_features,
                         windows, window_stats, W)
from .runner import DetectorObs, DetectorOutput

CHANNEL_NAMES = B_CHANNEL_NAMES + A_CHANNELS
N_CH = len(CHANNEL_NAMES)
assert N_CH == 22


def _a_vec(res: dict) -> np.ndarray:
    return np.array([0.0 if res[c] is None else res[c] for c in A_CHANNELS], dtype=np.float64)


def episode_step_matrix(obs_list: List[DetectorObs], a_res_list: List[dict]) -> np.ndarray:
    assert len(obs_list) == len(a_res_list)
    rows, prev = [], None
    for o, r in zip(obs_list, a_res_list):
        rows.append(np.concatenate([_b_step_features(o, prev), _a_vec(r)]))
        prev = o
    return np.asarray(rows, dtype=np.float64).reshape(-1, N_CH)


@dataclass
class Norm:
    """features_b.Norm과 같은 구조이되 채널이 22개(하이브리드 전용) — 서로 혼용되면 안 되므로 분리."""
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
        import json
        Path(path).write_text(json.dumps(dict(channels=list(CHANNEL_NAMES), mean=[float(v) for v in self.mean],
                                              std=[float(v) for v in self.std]), indent=2), encoding="utf-8")

    @staticmethod
    def from_json(path: Path) -> "Norm":
        import json
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        assert tuple(d["channels"]) == CHANNEL_NAMES
        return Norm(np.asarray(d["mean"], dtype=np.float64), np.asarray(d["std"], dtype=np.float64))


class HybridObsRecorder:
    """관측 + 탐지기 A 원시 잔차를 같이 기록하는 관찰 전용 탐지기(경보를 내지 않음, features_b.ObsRecorder와 대응).
    내부 DetectorA는 threshold=inf로 돌리되 추적기·CUSUM은 정상적으로 진행시킨다(§20)."""

    def __init__(self):
        self._det_a = DetectorA()
        self.obs: List[DetectorObs] = []
        self.a_res: List[dict] = []

    def reset(self) -> None:
        self._det_a.reset()
        self.obs = []
        self.a_res = []

    def update(self, obs: DetectorObs) -> DetectorOutput:
        out = self._det_a.update(obs)
        self.obs.append(obs)
        self.a_res.append(out.residuals)
        return DetectorOutput(score=0.0, alarm=False)


def score_episode(scorer, norm: Norm, obs_list: List[DetectorObs], a_res_list: List[dict]) -> np.ndarray:
    """에피소드 step별 점수(길이 T). k<W(1-based)는 0. detector_b.score_episode와 같은 규칙."""
    X = norm.apply(episode_step_matrix(obs_list, a_res_list))
    s = np.zeros(len(obs_list))
    if len(obs_list) >= W:
        s[W - 1:] = scorer.score(windows(X))
    return s


class DetectorHybrid:
    """온라인 하이브리드 탐지기(5단계 폐루프용, §24) — `detector_b.DetectorB`와 같은 구조이되 특징이
    22채널(§20: B1 15채널 + A 잔차 7채널)이다. 내부 `DetectorA()`로 매 step 잔차를 얻는다(threshold=inf —
    CUSUM 경보는 쓰지 않고 `_residuals()`만 쓴다). `score_episode`(오프라인 일괄)와 같은 값을 step별로 낸다."""

    def __init__(self, scorer, norm: Norm, threshold: float = float("inf")):
        self.scorer, self.norm, self.threshold = scorer, norm, threshold
        self.reset()

    def reset(self) -> None:
        self._det_a = DetectorA()
        self.prev: Optional[DetectorObs] = None
        self.buf = deque(maxlen=W)

    def update(self, obs: DetectorObs) -> DetectorOutput:
        a_out = self._det_a.update(obs)
        x = self.norm.apply(np.concatenate([_b_step_features(obs, self.prev), _a_vec(a_out.residuals)])[None])[0]
        self.prev = obs
        self.buf.append(x)
        score = 0.0
        if len(self.buf) == W:
            score = float(self.scorer.score(np.asarray(self.buf).reshape(1, W, N_CH))[0])
        return DetectorOutput(score=score, alarm=score > self.threshold, channel="")
