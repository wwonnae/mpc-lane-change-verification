"""탐지기 B 특징·점수 단위 테스트 (DESIGN.md §13-4). 작은 모델을 테스트 안에서 학습한다(dev 정상 seed만)."""
import numpy as np
import pytest

from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.common import run_anomaly_episode
from thesis_v2.anomaly.detector_b import IFScorer, AEScorer, DetectorB, score_episode
from thesis_v2.anomaly.features_b import (Norm, ObsRecorder, episode_step_matrix, windows, window_stats, W, N_CH,
                                          FSM_ORDER, CHANNEL_NAMES)
from thesis_v2.anomaly.faults import FaultSpec


def _obs(seed, kind=None):
    rec = ObsRecorder()
    res = run_anomaly_episode(seed, kind=kind, detector=rec, record_alog=False)
    return rec.obs, res


@pytest.fixture(scope="module")
def trained():
    mats = [episode_step_matrix(_obs(s)[0]) for s in (3200, 3201)]
    norm = Norm.fit(np.concatenate(mats))
    win = np.concatenate([windows(norm.apply(X)) for X in mats])
    from sklearn.ensemble import IsolationForest
    iso = IsolationForest(n_estimators=20, random_state=0, n_jobs=1).fit(window_stats(win))
    import torch
    from thesis_v2.anomaly.ae_model import ConvAE
    torch.manual_seed(0)
    torch.set_num_threads(1)
    return norm, IFScorer(iso), AEScorer(ConvAE())


def test_step_features_shape_and_onehot():
    obs, _ = _obs(3202)
    X = episode_step_matrix(obs)
    assert X.shape == (len(obs), N_CH) and len(CHANNEL_NAMES) == N_CH
    assert np.all(X[:, 10:].sum(axis=1) == 1.0)
    assert X[0, 8] == 0.0  # k=1 자이로 없음
    for k, o in enumerate(obs):
        assert X[k, 10 + FSM_ORDER.index(o.fsm_state)] == 1.0


def test_features_reflect_dropout_flag():
    obs, res = _obs(3203, kind="lidar_dropout")
    X = episode_step_matrix(obs)
    on, dur = res.fault["onset_step"], res.fault["duration_steps"]
    assert np.all(X[on - 1:min(on - 1 + dur, len(obs)), 1] == 1.0)  # 무반사 플래그
    assert np.all(X[on - 1:min(on - 1 + dur, len(obs)), 0] == 0.0)


def test_windows_and_stats():
    X = np.arange(30 * N_CH, dtype=float).reshape(30, N_CH)
    win = windows(X)
    assert win.shape == (30 - W + 1, W, N_CH)
    assert np.array_equal(win[-1], X[-W:])
    st = window_stats(win)
    assert st.shape == (len(win), 5 * N_CH)
    assert np.allclose(st[:, 4 * N_CH:], X[W - 1:] - X[:30 - W + 1])


def test_norm_zero_std_safe():
    X = np.ones((5, N_CH))
    n = Norm.fit(X)
    assert np.all(n.std == 1.0) and np.all(n.apply(X) == 0.0)


@pytest.mark.parametrize("which", ["if", "ae"])
def test_online_equals_offline(trained, which):
    """온라인(DetectorB step별)과 오프라인(score_episode 일괄) 점수가 완전히 같다."""
    norm, sif, sae = trained
    scorer = sif if which == "if" else sae
    obs, _ = _obs(3204, kind="steer_delay")
    off = score_episode(scorer, norm, obs)
    det = DetectorB(scorer, norm)
    det.reset()
    on = np.array([det.update(o).score for o in obs])
    assert np.all(off[:W - 1] == 0.0)
    assert np.array_equal(on, off)


def test_detector_b_does_not_change_control(trained):
    """B를 붙여도 제어 결과(스텝 로그)가 탐지기 없음과 같다."""
    norm, sif, _ = trained
    a = run_anomaly_episode(3205)
    b = run_anomaly_episode(3205, detector=DetectorB(sif, norm, threshold=0.0))
    assert a.outcome == b.outcome and a.total_steps == b.total_steps
    strip = lambda rows: [{k: v for k, v in r.items() if k != "t_mpc_solve_ms"} for r in rows]  # noqa: E731
    assert strip(a.logger.rows) == strip(b.logger.rows)
    assert b.first_alarm_step == W
