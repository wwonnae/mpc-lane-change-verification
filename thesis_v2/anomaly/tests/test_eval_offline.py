"""오프라인 평가 스크립트(eval_offline.py) 단위·소규모 통합 테스트. dev seed만, 작은 모델로 빠르게 돈다."""
import numpy as np
import pytest

from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly import eval_offline as ev
from thesis_v2.anomaly.features_b import windows as windows_b, window_stats as window_stats_b
from thesis_v2.anomaly.hybrid import episode_step_matrix as hybrid_matrix
from thesis_v2.anomaly.hybrid import Norm as HybridNorm


def test_wilson_matches_module():
    assert ev.wilson(3, 200) is not None


def test_freeze_ok_requires_clean_and_tagged():
    ok, _ = ev.freeze_ok({"dirty": True, "tag": None, "commit": "x"})
    assert not ok
    ok, _ = ev.freeze_ok({"dirty": False, "tag": None, "commit": "x"})
    assert not ok
    ok, _ = ev.freeze_ok({"dirty": False, "tag": "some-other-tag", "commit": "x"})
    assert not ok
    ok, _ = ev.freeze_ok({"dirty": False, "tag": ev.EVAL_FREEZE_TAG, "commit": "x"})
    assert ok


def test_main_refuses_eval_seeds_without_freeze(monkeypatch, capsys):
    """git_info를 가짜로 dirty/태그없음으로 만들어도(실제 저장소 상태와 무관하게) --seeds eval이 임계값 인자
    없이도 바로 거부되는지 확인 — main()이 freeze_ok를 먼저 확인하고 나머지 인자 로딩 전에 종료해야 한다."""
    import sys as _sys
    monkeypatch.setattr(ev, "git_info", lambda: {"dirty": True, "tag": None, "commit": "x"})
    monkeypatch.setattr(_sys, "argv", ["eval_offline.py", "--seeds", "eval"])
    with pytest.raises(SystemExit) as e:
        ev.main()
    assert e.value.code != 0
    assert "거부" in capsys.readouterr().err

    monkeypatch.setattr(ev, "git_info", lambda: {"dirty": False, "tag": ev.EVAL_FREEZE_TAG, "commit": "x"})
    monkeypatch.setattr(_sys, "argv", ["eval_offline.py", "--seeds", "eval", "--a-thresholds", "nope"])
    with pytest.raises(FileNotFoundError):  # freeze 통과 후 임계값 로딩에서 실패 — 거부는 아니었다는 뜻
        ev.main()


def test_auc_perfect_separation():
    assert ev.auc_from_scores(np.array([5.0, 6.0]), np.array([1.0, 2.0])) == 1.0
    assert ev.auc_from_scores(np.array([1.0, 2.0]), np.array([5.0, 6.0])) == 0.0


def test_auc_ties_are_half():
    assert ev.auc_from_scores(np.array([1.0, 1.0]), np.array([1.0, 1.0])) == pytest.approx(0.5)


def test_ap_perfect_ranking():
    labels = np.array([1, 1, 0, 0])
    scores = np.array([4.0, 3.0, 2.0, 1.0])
    assert ev.ap_from_scores(labels, scores) == pytest.approx(1.0)


def test_ap_no_positive_is_none():
    assert ev.ap_from_scores(np.zeros(5), np.arange(5.0)) is None


def test_step_prf1_basic():
    lab = [np.array([0, 0, 1, 1])]
    sc = [np.array([0.0, 0.0, 2.0, 0.0])]
    r = ev.step_prf1(lab, sc, h=1.0)
    assert r == dict(tp=1, fp=0, fn=1, precision=1.0, recall=0.5, f1=pytest.approx(2 / 3))


def test_label_array_permanent_and_bounded():
    rec = dict(total_steps=10, fault=dict(onset_step=3, duration_steps=None))
    lab = ev.label_array(rec)
    assert lab.tolist() == [0, 0, 1, 1, 1, 1, 1, 1, 1, 1]
    rec2 = dict(total_steps=10, fault=dict(onset_step=3, duration_steps=2))
    assert ev.label_array(rec2).tolist() == [0, 0, 1, 1, 0, 0, 0, 0, 0, 0]


def test_expected_fine_spike_direction():
    assert ev._expected_fine("lidar_spike", {"up": 1.0}) == "trk"
    assert ev._expected_fine("lidar_spike", {"up": 0.0}) == "fg"
    assert ev._expected_fine("ir_dropout", {}) == "ir_miss"


def test_bootstrap_episode_stat_deterministic():
    a = ev.bootstrap_episode_stat(5, lambda idx: float(np.mean(idx)), n_boot=50, seed=0)
    b = ev.bootstrap_episode_stat(5, lambda idx: float(np.mean(idx)), n_boot=50, seed=0)
    assert a == b and len(a) == 2


@pytest.fixture(scope="module")
def tiny_models(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("eval_offline_models")
    b_mats, hy_mats = [], []
    for s in (3200, 3201):
        rec = ev.FullRecorder()
        res = ev.run_anomaly_episode(s, detector=rec, record_alog=False)
        from thesis_v2.anomaly.features_b import episode_step_matrix as b_matrix
        b_mats.append(b_matrix(rec.obs))
        hy_mats.append(hybrid_matrix(rec.obs, rec.a_res))
    from thesis_v2.anomaly.features_b import Norm as BNorm
    b_norm = BNorm.fit(np.concatenate(b_mats))
    b_win = np.concatenate([windows_b(b_norm.apply(X)) for X in b_mats])
    from sklearn.ensemble import IsolationForest
    import torch
    from thesis_v2.anomaly.ae_model import ConvAE
    torch.manual_seed(0)
    iso_b = IsolationForest(n_estimators=10, random_state=0, n_jobs=1).fit(window_stats_b(b_win))
    b_dir = tmp / "b"
    b_dir.mkdir()
    b_norm.to_json(b_dir / "norm.json")
    import pickle
    with open(b_dir / "if_model.pkl", "wb") as f:
        pickle.dump(iso_b, f)
    torch.save(ConvAE().state_dict(), b_dir / "ae_model.pt")

    hy_norm = HybridNorm.fit(np.concatenate(hy_mats))
    hy_win = np.concatenate([windows_b(hy_norm.apply(X)) for X in hy_mats])
    iso_hy = IsolationForest(n_estimators=10, random_state=0, n_jobs=1).fit(window_stats_b(hy_win))
    hy_dir = tmp / "hybrid"
    hy_dir.mkdir()
    hy_norm.to_json(hy_dir / "norm.json")
    with open(hy_dir / "if_model.pkl", "wb") as f:
        pickle.dump(iso_hy, f)
    return str(b_dir), str(hy_dir)


def test_compute_and_summarize_small(tiny_models, monkeypatch):
    """compute()+summarize() 전체 파이프라인이 작은 seed·모델로 끝까지 돌고, 재실행해도 같은 결과를 낸다."""
    b_dir, hy_dir = tiny_models
    monkeypatch.setattr(ev, "KINDS", ["lidar_freeze"])
    monkeypatch.setattr(ev, "RUNS", ["none", "lidar_freeze"])
    seeds = [3200, 3201]
    h_by_detector = {"A": 5.0, "B1": 0.3, "B2": 0.3, "HYBRID": 0.3, "A_sg0.05": 5.0, "A_sg5": 5.0}
    model_dirs = {"B": b_dir, "HYBRID": hy_dir}
    sigma_variants = {"main": an_config.SIGMA_GYRO_DEG, "sg0.05": 0.05, "sg5": 5.0}

    bundle1 = ev.compute(seeds, h_by_detector, model_dirs, sigma_variants)
    summary1 = ev.summarize(bundle1, h_by_detector)
    bundle2 = ev.compute(seeds, h_by_detector, model_dirs, sigma_variants)
    summary2 = ev.summarize(bundle2, h_by_detector)

    import json
    assert json.dumps(summary1, sort_keys=True, default=str) == json.dumps(summary2, sort_keys=True, default=str)
    for det in ev.DETECTORS:
        assert len(bundle1["rows"][det]) == 2 * 2  # 2 runs x 2 seeds
        assert "lidar_freeze" in summary1[det]["per_kind"]
    assert set(bundle1["sens_rows"].keys()) == {"sg0.05", "sg5"}
    assert set(bundle1["mismatch_rows"].keys()) == set(ev.MISMATCH_SIGMA_TRUE)
    for tag, rs in bundle1["mismatch_rows"].items():
        assert len(rs) == 2 * 2  # 2 runs x 2 seeds
    assert set(summary1["A_sigma_mismatch_sensitivity"]) == set(ev.MISMATCH_SIGMA_TRUE)
    for s in summary1["A_sigma_mismatch_sensitivity"].values():
        assert "delay_median" in s and "fault_detected" in s and "normal_false_alarm" in s


def test_run_record_decouples_inject_and_assumed_sigma():
    """§22-1: sigma_assumed을 생략하면 sigma_inject와 같게(기존 "σ 일치") — 이때는 psi z가 표준정규라 h가
    σ-불변(§22에서 확인). 둘을 다르게 주면(같은 주입 노이즈, 다른 정규화) psi 잔차가 비율만큼 정확히 달라진다."""
    rec_match = ev.run_record("none", 3200, sigma_inject=0.05, sigma_assumed=0.05)
    rec_mismatch = ev.run_record("none", 3200, sigma_inject=0.05, sigma_assumed=an_config.SIGMA_GYRO_DEG)
    ratio = an_config.SIGMA_GYRO_DEG / 0.05  # sigma_assumed(mismatch)/sigma_assumed(match) = 20
    compared = 0
    for r_m, r_x in zip(rec_match["a_res"], rec_mismatch["a_res"]):
        if r_m["psi"] is not None and r_x["psi"] is not None and abs(r_m["psi"]) > 1e-9:
            assert r_x["psi"] == pytest.approx(r_m["psi"] / ratio, rel=1e-9)
            compared += 1
    assert compared > 50  # 대부분 step에서 비교됐는지(마스크 거의 없음)

    rec_default = ev.run_record("none", 3200, sigma_inject=0.05)
    assert rec_default["a_score"] == rec_match["a_score"]
