"""탐지기 A(모델 잔차 + CUSUM) 단위 테스트 — DESIGN.md §4, §13-2·§13-3.
dev 대역(3200~)과 기존 paper seed만 쓴다(평가 대역 4000~·5000~ 사용 금지)."""
import math

import numpy as np
import pytest

from thesis_v2.baseline import config as base_config
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.common import threshold_from_episode_max, run_anomaly_episode
from thesis_v2.anomaly.detector_a import (DetectorA, CHANNELS, LLR_MISMATCH, LLR_MATCH, TRACK_GATE_Z,
                                           SIGMA_FG)
from thesis_v2.anomaly.faults import FaultSpec
from thesis_v2.anomaly.runner import run_episode
from thesis_v2.anomaly.scenarios import generate_anomaly_scenario, estimated_trigger_step
from thesis_v2.anomaly.tests.test_golden_equivalence import _assert_same


def _clean_run(seed, fault=None, left=False, det=None):
    """노이즈·자이로 노이즈 없음 — 정상 잔차가 수치 오차 수준이어야 한다."""
    sc = generate_anomaly_scenario(seed, left_obstacle=left)
    det = det or DetectorA()
    res = run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), fault=fault, detector=det,
                      max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)
    return sc, det, res


def test_llr_constants():
    assert LLR_MISMATCH == pytest.approx(math.log(50.0))
    assert LLR_MATCH == pytest.approx(math.log(0.5 / 0.99))


def test_threshold_quantile_higher():
    v = list(range(1, 201))
    h = threshold_from_episode_max(v)
    assert h == 197.0
    assert sum(x > h for x in v) == 3  # 3/200 = 1.5% ≤ 2%


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_detector_a_with_gyro_does_not_change_control(seed):
    """탐지기 A + 자이로 난수 스트림을 붙여도 improved v2와 스텝 로그가 완전히 같다(§3 golden)."""
    sc = generate_scenario(seed)
    ref = improved_run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS))
    got = run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), detector=DetectorA(threshold=0.0),
                      gyro_rng=np.random.default_rng((seed, an_config.GYRO_STREAM_ID)), sigma_gyro_deg=1.0)
    _assert_same(ref, got)


def test_gyro_without_noise_is_finite_difference():
    _, _, res = _clean_run(3200)
    a = res.alog
    assert a[0]["yaw_rate_meas"] is None
    for p, q in zip(a[:-1], a[1:]):
        assert q["yaw_rate_meas"] == pytest.approx((q["psi"] - p["psi"]) / base_config.DT, abs=1e-12)


@pytest.mark.parametrize("left", [False, True])
def test_normal_residuals_are_zero_without_noise(left):
    """플랜트와 같은 Euler식 예측 → 노이즈가 없으면 연속 잔차 ≈ 0, 이산 불일치 0, 점수 0."""
    _, _, res = _clean_run(3201, left=left)
    for a in res.alog:
        for c, r in a["det_residuals"].items():
            if r is None:
                continue
            if c in ("fg", "ey", "psi"):
                assert abs(r) < 1e-6, (a["step"], c, r)
            else:
                assert r == 0.0, (a["step"], c)
        assert a["det_score"] < 1e-6


def test_normal_noise_residuals_are_standardized():
    """S4-low + σ_gyro: 연속 잔차 z의 표준편차가 1 근처(해석적 정규화 A1 확인)."""
    zs = {c: [] for c in ("fg", "ey", "psi")}
    for s in (3202, 3203, 3204):
        res = run_anomaly_episode(s, detector=DetectorA())
        for a in res.alog:
            for c in zs:
                if a["det_residuals"][c] is not None:
                    zs[c].append(a["det_residuals"][c])
    for c, v in zs.items():
        assert len(v) > 100
        assert 0.85 < float(np.std(v)) < 1.15, (c, np.std(v))


def _onset(sc):
    return max(an_config.WARMUP_STEPS, estimated_trigger_step(sc) - 8)


@pytest.mark.parametrize("kind,channel,extra", [
    ("lidar_freeze", "fg", {}),
    ("lidar_dropout", "trk", {"duration_steps": 30}),
    ("ir_stuck", "ey", {"pattern": (1, 0, 0)}),
    ("steer_delay", "psi", {"magnitude": 6.0}),
    ("ir_dropout", "ir_miss", {}),  # iteration 3(§18): r_ey는 측정 None에서 마스크되므로 ir_miss로 잡는다
])
def test_fault_raises_expected_channel(kind, channel, extra):
    sc = generate_anomaly_scenario(3205)
    on = _onset(sc)
    dur = extra.pop("duration_steps", None)
    spec = FaultSpec(kind, onset_step=on, duration_steps=dur, **extra)
    _, _, res = _clean_run(3205, fault=spec)
    pre = [a for a in res.alog if a["step"] < on]
    post = [a for a in res.alog if a["step"] >= on]
    assert max(a["det_score"] for a in pre) < 1e-6
    best = max(post, key=lambda a: a["det_score"])
    assert best["det_channel"] == channel
    assert best["det_score"] > 20.0


def test_ir_dropout_masks_ey_but_not_ir_miss():
    """iteration 3 사유 그대로 확인: ir_dropout 중 측정 ey_line=None이라 ey 잔차는 계속 마스크되지만
    (r["ey"] is None), ir_miss는 예상 검출·측정 미검출 불일치를 매 step 잡는다(§18)."""
    sc = generate_anomaly_scenario(3205)
    on = _onset(sc)
    spec = FaultSpec("ir_dropout", onset_step=on, duration_steps=None)
    _, _, res = _clean_run(3205, fault=spec)
    during = [a for a in res.alog if a["step"] >= on]
    assert during  # 고장 구간이 관찰됨
    assert all(a["det_residuals"]["ey"] is None for a in during)
    assert all(a["det_residuals"]["ir_miss"] == 1.0 for a in during if a["det_residuals"]["ir_miss"] is not None)
    assert any(a["det_residuals"]["ir_miss"] is not None for a in during)


def test_right_clear_stuck_raises_rc():
    sc = generate_anomaly_scenario(3206)
    spec = FaultSpec("right_clear_stuck", onset_step=estimated_trigger_step(sc), duration_steps=None, value=True)
    _, _, res = _clean_run(3206, fault=spec)
    assert max(a["det_channel_scores"]["rc"] for a in res.alog) > 20.0


def test_tracker_not_contaminated_by_frozen_lidar():
    """A3(1): 멈춘 측정은 예측과의 차이가 step마다 v·dt(2.5 cm)씩 커져, 4σ 게이트(5.7 cm) 안인 처음 2 step만
    수용되고 그 뒤로는 갱신되지 않는다 → 추적 오차는 게이트 폭 이하로 제한된다(DESIGN.md §13-3)."""
    sc = generate_anomaly_scenario(3207)
    on = _onset(sc)
    spec = FaultSpec("lidar_freeze", onset_step=on, duration_steps=None)
    sc, det, res = _clean_run(3207, fault=spec)
    assert len(det.tracks) == 1
    first_seen = next(a["step"] for a in res.alog if a["obs_gap_near"] is not None)
    assert det.tracks[0].n == (on - first_seen) + 2  # onset 전 전부 + 멈춘 측정 2개
    assert abs(det.tracks[0].x_near - sc.obstacles[0].x_near) < TRACK_GATE_Z * SIGMA_FG


def test_tracker_keeps_obstacles_per_lane():
    """A3(2): 좌측 장애물 시나리오에서 left_clear 고착 → 회피하며 L1 장애물이 별도 추적으로 잡히고 lc 채널 상승."""
    sc = generate_anomaly_scenario(3208, left_obstacle=True)
    spec = FaultSpec("left_clear_stuck", onset_step=an_config.WARMUP_STEPS, duration_steps=None, value=True)
    sc, det, res = _clean_run(3208, fault=spec, left=True)
    centers = sorted(round(t.y_center, 3) for t in det.tracks)
    assert centers == [0.0, round(base_config.W, 3)]
    assert max(a["det_channel_scores"]["lc"] for a in res.alog) > 20.0
    first_evade = next(t.step for t in res.transitions if t.to_state == "EVADE_L")
    first_lc = next(a["step"] for a in res.alog if a["det_residuals"]["lc"] is not None)
    assert first_lc > first_evade  # §13-3 사전 예상: 회피 시작 후에야 L1 장애물이 스캔에 잡힘


def test_channel_scores_cover_all_channels():
    _, _, res = _clean_run(3209)
    assert set(res.alog[-1]["det_channel_scores"]) == set(CHANNELS)


# ---- 추적기 게이트: 천천히 변하는 고장에도 추적 오차 ≤ 게이트 (DESIGN.md §13-3, 2026-10-01 확인 요청) ----
from thesis_v2.anomaly.faults import SensorFrame
from thesis_v2.anomaly.runner import DetectorObs
from thesis_v2.improved.sensors import FrontObstacleInfo

_GATE = TRACK_GATE_Z * SIGMA_FG
_OBS_X, _OBS_LEN = 8.0, 0.2


def _synthetic_drift_errors(drift_per_step, n_normal=20, n_total=250):
    """직선 정속(v=0.5, ψ=0, y=0) 주행, 정지 장애물 x_near=8.0. n_normal step 뒤부터 front_gap 측정이
    step마다 drift_per_step씩 실제보다 커지는(=장애물이 멀어지는 것처럼 보이는) 합성 고장. 노이즈 없음.
    drift_per_step = v·dt(2.5 cm)이면 멈춤과 같은 신호다. step마다 추적 오차 |x̂_near − 8.0|를 돌려준다."""
    det = DetectorA()
    errs = []
    for k in range(1, n_total + 1):
        x = 0.025 * (k - 1)
        fx = x + base_config.L
        true_gap = _OBS_X - fx
        if true_gap <= 0.3:
            break
        gap = true_gap + drift_per_step * max(0, k - n_normal)
        info = FrontObstacleInfo(gap_near=gap, gap_far=gap + _OBS_LEN, y_lo=-0.075, y_hi=0.075)
        frame = SensorFrame(front_gap=gap, left_clear=True, right_clear=False, ir_pattern=(0, 1, 0),
                            ey_line=0.0, obstacle_info=info)
        det.update(DetectorObs(step=k, t=k * base_config.DT, frame=frame, y=0.0, psi=0.0, v=0.5,
                               fsm_state="KEEP_L2", delta_prev_cmd_deg=0.0,
                               yaw_rate_meas=(0.0 if k > 1 else None)))
        assert len(det.tracks) == 1
        errs.append(abs(det.tracks[0].x_near - _OBS_X))
    return errs


@pytest.mark.parametrize("drift_cm", [0.1, 0.5, 1.0, 2.5, 4.0, 5.5])
def test_tracker_error_bounded_by_gate_under_slow_drift(drift_cm):
    """스텝당 변화가 게이트(5.66 cm)보다 작아도, 추적은 수용 측정의 평균이라 측정과의 차이가 누적되어 결국 게이트를
    넘는다(오프셋 m·d에 대해 평균은 ≤ m·d/2 → 차이 ≥ m·d/2). 거부 시점까지 추적 오차 ≤ m·d/2 ≤ 게이트."""
    errs = _synthetic_drift_errors(drift_cm / 100.0)
    assert max(errs) <= _GATE
    assert errs[-1] == errs[-30]  # 끝부분에서는 거부만 일어나 추적이 고정됨


def test_tracker_error_bounded_during_50_step_freeze_with_noise():
    """실제 에피소드(S4-low 노이즈 + 자이로), 50 step 멈춤: 매 step 추적 오차 ≤ 게이트, 멈춤 해제 후 다시 수용."""
    sc = generate_anomaly_scenario(3207)
    on = _onset(sc)
    spec = FaultSpec("lidar_freeze", onset_step=on, duration_steps=50)

    class _Rec(DetectorA):
        def update(self, obs):
            out = super().update(obs)
            self.hist.append((obs.step, [(t.x_near, t.n) for t in self.tracks]))
            return out

        def reset(self):
            super().reset()
            self.hist = []

    det = _Rec()
    res = run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), fault=spec, detector=det,
                      noise_profile=__import__("thesis_v2.baseline.sensors", fromlist=["x"]).NOISE_PROFILES["low"],
                      noise_rng=np.random.default_rng((3207, an_config.NOISE_STREAM_ID)),
                      gyro_rng=np.random.default_rng((3207, an_config.GYRO_STREAM_ID)), sigma_gyro_deg=1.0,
                      max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)
    true_x = sc.obstacles[0].x_near
    errs = [abs(tr[0][0] - true_x) for _, tr in det.hist if tr]
    assert max(errs) <= _GATE
    n_by_step = {k: tr[0][1] for k, tr in det.hist if tr}
    frozen = [n_by_step[k] for k in range(on + 3, min(on + 50, res.total_steps)) if k in n_by_step]
    assert len(set(frozen)) == 1  # 멈춤 3 step째부터 해제까지 수용 없음
