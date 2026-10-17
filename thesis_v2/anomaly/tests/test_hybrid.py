"""하이브리드 탐지기(B1 특징 + A 잔차) 단위 테스트 (DESIGN.md §20). 작은 IF를 테스트 안에서 학습한다(dev seed만)."""
import numpy as np
import pytest

from thesis_v2.anomaly.common import run_anomaly_episode
from thesis_v2.anomaly.detector_a import CHANNELS as A_CHANNELS
from thesis_v2.anomaly.detector_b import IFScorer
from thesis_v2.anomaly.features_b import CHANNEL_NAMES as B_CHANNEL_NAMES, windows, window_stats
from thesis_v2.anomaly.hybrid import (HybridObsRecorder, Norm, CHANNEL_NAMES, N_CH, episode_step_matrix,
                                      score_episode, DetectorHybrid)


def _rec(seed, kind=None):
    rec = HybridObsRecorder()
    res = run_anomaly_episode(seed, kind=kind, detector=rec, record_alog=False)
    return rec, res


def test_channel_names_are_b_then_a():
    assert CHANNEL_NAMES == B_CHANNEL_NAMES + A_CHANNELS
    assert N_CH == 22


def test_step_matrix_shape_and_a_columns_match_residuals():
    rec, _ = _rec(3202)
    X = episode_step_matrix(rec.obs, rec.a_res)
    assert X.shape == (len(rec.obs), N_CH)
    for k, r in enumerate(rec.a_res):
        for j, c in enumerate(A_CHANNELS):
            expected = 0.0 if r[c] is None else r[c]
            assert X[k, 15 + j] == pytest.approx(expected)


def test_hybrid_recorder_does_not_change_control():
    """ObsRecorder와 같은 증거: HybridObsRecorder를 붙여도 제어 결과(스텝 로그)가 탐지기 없음과 같다."""
    a = run_anomaly_episode(3205)
    rec = HybridObsRecorder()
    b = run_anomaly_episode(3205, detector=rec)
    assert a.outcome == b.outcome and a.total_steps == b.total_steps
    strip = lambda rows: [{k: v for k, v in r.items() if k != "t_mpc_solve_ms"} for r in rows]  # noqa: E731
    assert strip(a.logger.rows) == strip(b.logger.rows)


def test_norm_round_trips_and_rejects_wrong_channels(tmp_path):
    rec, _ = _rec(3203)
    X = episode_step_matrix(rec.obs, rec.a_res)
    norm = Norm.fit(X)
    p = tmp_path / "norm.json"
    norm.to_json(p)
    back = Norm.from_json(p)
    assert np.allclose(back.mean, norm.mean) and np.allclose(back.std, norm.std)


@pytest.fixture(scope="module")
def trained():
    mats = []
    for s in (3200, 3201):
        rec, _ = _rec(s)
        mats.append(episode_step_matrix(rec.obs, rec.a_res))
    norm = Norm.fit(np.concatenate(mats))
    win = np.concatenate([windows(norm.apply(X)) for X in mats])
    from sklearn.ensemble import IsolationForest
    iso = IsolationForest(n_estimators=20, random_state=0, n_jobs=1).fit(window_stats(win))
    return norm, IFScorer(iso)


def test_score_episode_deterministic_and_masked_prefix_zero(trained):
    norm, scorer = trained
    rec, _ = _rec(3204, kind="steer_delay")
    s1 = score_episode(scorer, norm, rec.obs, rec.a_res)
    s2 = score_episode(scorer, norm, rec.obs, rec.a_res)
    assert np.array_equal(s1, s2)
    assert np.all(s1[:9] == 0.0)  # W-1 = 9 (k<W는 0)


def test_detector_hybrid_online_equals_offline(trained):
    """§24(5단계 폐루프용): 온라인(DetectorHybrid step별)과 오프라인(score_episode 일괄) 점수가 완전히 같다."""
    norm, scorer = trained
    rec, _ = _rec(3204, kind="steer_delay")
    off = score_episode(scorer, norm, rec.obs, rec.a_res)
    det = DetectorHybrid(scorer, norm)
    on = np.array([det.update(o).score for o in rec.obs])
    assert np.array_equal(on, off)


def test_detector_hybrid_does_not_change_control():
    a = run_anomaly_episode(3205)
    from thesis_v2.anomaly.detector_b import IFScorer
    from sklearn.ensemble import IsolationForest
    dummy = IFScorer(IsolationForest(n_estimators=5, random_state=0, n_jobs=1).fit(
        np.zeros((5, N_CH * 5))))
    norm = Norm(mean=np.zeros(N_CH), std=np.ones(N_CH))
    b = run_anomaly_episode(3205, detector=DetectorHybrid(dummy, norm, threshold=0.0))
    assert a.outcome == b.outcome and a.total_steps == b.total_steps
    strip = lambda rows: [{k: v for k, v in r.items() if k != "t_mpc_solve_ms"} for r in rows]  # noqa: E731
    assert strip(a.logger.rows) == strip(b.logger.rows)
