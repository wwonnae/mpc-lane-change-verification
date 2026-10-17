"""
탐지기 B — 정상 데이터로만 학습한 ML 탐지기 (DESIGN.md §5, §13-4).
B1: Isolation Forest(윈도우 통계 75특징), B2: 1D 합성곱 오토인코더(재구성 MSE).

같은 점수 함수를 온라인(`DetectorB.update`, step별)과 오프라인(`score_episode`, 에피소드 일괄)에서 쓴다.
B는 고장 센서를 분리하지 못하므로 channel은 비워 둔다.
"""
import pickle
from collections import deque
from pathlib import Path
from typing import List, Optional

import numpy as np

from .features_b import W, N_CH, Norm, step_features, episode_step_matrix, windows, window_stats
from .runner import DetectorObs, DetectorOutput


class IFScorer:
    name = "B1"

    def __init__(self, model):
        self.model = model

    def score(self, win_norm: np.ndarray) -> np.ndarray:
        """(n, W, C) 정규화 윈도우 → (n,) 이상 점수(= −score_samples, 클수록 이상). 일괄·단건 결과가 같다(테스트)."""
        if len(win_norm) == 0:
            return np.zeros(0)
        return -self.model.score_samples(window_stats(win_norm))

    @staticmethod
    def load(model_dir: Path) -> "IFScorer":
        with open(Path(model_dir) / "if_model.pkl", "rb") as f:
            return IFScorer(pickle.load(f))


class AEScorer:
    name = "B2"

    def __init__(self, model):
        import torch
        self.torch = torch
        self.model = model.eval()

    def score(self, win_norm: np.ndarray) -> np.ndarray:
        """윈도우 하나씩 계산한다(일괄 크기에 따른 부동소수점 차이를 없애 온라인·오프라인 점수를 같게)."""
        torch = self.torch
        out = np.zeros(len(win_norm))
        with torch.no_grad():
            for i, w in enumerate(win_norm):
                x = torch.from_numpy(np.ascontiguousarray(w.T, dtype=np.float32))[None]  # (1, C, W)
                out[i] = float(((self.model(x) - x) ** 2).mean())
        return out

    @staticmethod
    def load(model_dir: Path) -> "AEScorer":
        import torch
        from .ae_model import ConvAE
        torch.set_num_threads(1)
        m = ConvAE()
        m.load_state_dict(torch.load(Path(model_dir) / "ae_model.pt", map_location="cpu"))
        return AEScorer(m)


def load_scorer(kind: str, model_dir: Path):
    return {"B1": IFScorer, "B2": AEScorer}[kind].load(model_dir)


def score_episode(scorer, norm: Norm, obs_list: List[DetectorObs]) -> np.ndarray:
    """에피소드 step별 점수(길이 T). k<W(1-based)는 0."""
    X = norm.apply(episode_step_matrix(obs_list))
    s = np.zeros(len(obs_list))
    if len(obs_list) >= W:
        s[W - 1:] = scorer.score(windows(X))
    return s


class DetectorB:
    """온라인 탐지기(폐루프용). score_episode와 같은 값을 step별로 낸다."""

    def __init__(self, scorer, norm: Norm, threshold: float = float("inf")):
        self.scorer, self.norm, self.threshold = scorer, norm, threshold
        self.reset()

    def reset(self) -> None:
        self.prev: Optional[DetectorObs] = None
        self.buf = deque(maxlen=W)

    def update(self, obs: DetectorObs) -> DetectorOutput:
        x = self.norm.apply(step_features(obs, self.prev)[None])[0]
        self.prev = obs
        self.buf.append(x)
        score = 0.0
        if len(self.buf) == W:
            score = float(self.scorer.score(np.asarray(self.buf).reshape(1, W, N_CH))[0])
        return DetectorOutput(score=score, alarm=score > self.threshold, channel="")
