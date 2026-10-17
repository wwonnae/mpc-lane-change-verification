"""탐지기 A 테스트 보강 — mutation testing 1차 생존 변이 중 테스트 공백(docs/verification/mutation/equivalence.json).

이 파일의 테스트는 LLM(Claude Code)이 제안했다. 수락 기준과 검토 기록은 docs/verification/mutation/RESULTS.md,
llm_tests_log.json에 있다(PREREGISTRATION.md §8).

입력은 합성 DetectorObs다(기존 test_detector_a.py의 추적기 게이트 테스트와 같은 방식, 노이즈 없음).
정지 장애물과 자차 x는 플랜트와 같은 식(vehicle.py:24·30-32)으로 만든다. 확인은 가능한 한 DetectorOutput(residuals·alarm)으로 하고,
추적 위치처럼 출력에 직접 나오지 않는 값은 기존 테스트(test_detector_a.py:144-219)와 같이 det.tracks로 확인한다.
"""
import math

import pytest

from thesis_v2.baseline import config as base_config
from thesis_v2.anomaly.detector_a import DetectorA, LLR_MISMATCH, TRACK_GATE_Z, SIGMA_FG
from thesis_v2.anomaly.faults import SensorFrame
from thesis_v2.anomaly.runner import DetectorObs
from thesis_v2.improved.sensors import FrontObstacleInfo

_L2 = (-0.075, 0.075)   # L2 중심 장애물의 y 경계(OBSTACLE_WIDTH = B = 0.15)
_L1 = (0.225, 0.375)    # L1 중심 장애물
_LEN = base_config.OBSTACLE_LENGTH


class _Drive:
    """합성 주행: 매 step 자차 x를 플랜트 Euler식(x_k = x_{k−1} + v_{k−1}·cosψ_{k−1}·dt)으로 진행하고 DetectorObs를 만든다."""

    def __init__(self, det):
        self.det, self.k, self.x, self.prev = det, 0, 0.0, None

    def step(self, *, y=0.0, psi=0.0, v=0.5, obstacle=None, front_gap=None, left_clear=True, right_clear=True,
             ey_line=0.0, info="auto"):
        """obstacle = (x_near, (y_lo, y_hi)): 차량 통로에 있는 정지 장애물. front_gap·info는 기본으로 그 장애물에서 계산한다."""
        self.k += 1
        if self.prev is not None:
            self.x += self.prev[0] * math.cos(self.prev[1]) * base_config.DT
        fx = self.x + base_config.L * math.cos(psi)
        if obstacle is not None:
            gap = obstacle[0] - fx
            auto_info = FrontObstacleInfo(gap_near=gap, gap_far=gap + _LEN, y_lo=obstacle[1][0], y_hi=obstacle[1][1])
        else:
            gap, auto_info = base_config.LIDAR_MAX_RANGE, None
        fg = gap if front_gap is None else front_gap
        oi = auto_info if info == "auto" else info
        frame = SensorFrame(front_gap=fg, left_clear=left_clear, right_clear=right_clear, ir_pattern=(0, 1, 0),
                            ey_line=ey_line, obstacle_info=oi)
        yaw = None if self.prev is None else 0.0
        out = self.det.update(DetectorObs(step=self.k, t=self.k * base_config.DT, frame=frame, y=y, psi=psi, v=v,
                                          fsm_state="KEEP_L2", delta_prev_cmd_deg=0.0, yaw_rate_meas=yaw))
        self.prev = (v, psi)
        return out


# ---------------- 이산 채널: 윈도우·통로 판정(DESIGN.md §13-3 A3) ----------------

def test_l1_obstacle_is_evaluated_in_l1_window_only():
    """DESIGN.md §4·§13-3: r_rc는 L2 윈도우, r_lc는 L1 윈도우에 추적 장애물이 확실히 있을 때만 평가한다(윈도우 차로 범위는
    REQ-SEN-02/04). L1 차로를 달리며 앞의 L1 장애물을 추적하면, L2 윈도우에는 장애물이 없으므로 r_rc는 평가하지 않고(None),
    L1 윈도우의 r_lc는 측정 left_clear=False와 일치(0.0)한다."""
    d = _Drive(DetectorA())
    obstacle = (1.0, _L1)
    outs = [d.step(y=base_config.W, obstacle=obstacle, left_clear=False, right_clear=True) for _ in range(3)]
    for out in outs[1:]:   # 첫 step 뒤부터 추적이 있다
        assert out.residuals["rc"] is None
        assert out.residuals["lc"] == 0.0


def test_window_extends_g_safe_min_behind_rear_axle():
    """DESIGN.md §13-3 + REQ-SEN-04: L2 윈도우 종방향 범위는 [후단 − G_SAFE_MIN, 전단 + G_TRIG]이다(sensors.py:49-50과 같음).
    L2 장애물을 본 뒤 L1로 옮겨 장애물 옆을 지날 때, 장애물 끝이 후단보다 약간 뒤(0.0~0.15 m)여도 윈도우 안이므로 r_rc가 평가된다
    (측정 right_clear=False와 일치 → 0.0).
    합성 입력: 장애물을 본 다음 step에 차량 y를 0 → W로 순간이동시킨다(차로 변경 궤적 없음)."""
    d = _Drive(DetectorA())
    d.step(obstacle=(1.0, _L2))
    out = None
    while True:
        rx_next = d.x + 0.5 * base_config.DT
        if rx_next > 1.0 + _LEN + 0.12:   # 다음 step 후단 = 장애물 끝 + 0.12 m
            break
        out = d.step(y=base_config.W, right_clear=False)
    assert d.x - (1.0 + _LEN) > 0.05      # 전제: 후단이 장애물 끝을 지났다(G_SAFE_MIN 덕분에 윈도우 안)
    assert out.residuals["rc"] == 0.0


@pytest.mark.parametrize("y,expect_evaluated", [(0.1, True), (-0.2, False)])
def test_corridor_is_vehicle_width_around_y(y, expect_evaluated):
    """DESIGN.md §4·§13-3: r_trk는 추적 장애물이 전방 통로에 확실히 있을 때만 평가한다. 통로는 front_gap과 같은 [y − B/2, y + B/2]
    (REQ-SEN-01, sensors.py:35). L2 장애물(|y| ≤ 0.075)은 y = 0.1이면 통로와 겹치고(평가 → 반사가 있으니 0.0),
    y = −0.2이면 겹치지 않는다(평가 안 함 → None).
    합성 입력: 장애물을 본 다음 step에 차량 y를 0 → 0.1 또는 −0.2로 순간이동시킨다."""
    d = _Drive(DetectorA())
    d.step(obstacle=(3.0, _L2))
    if expect_evaluated:
        out = d.step(y=y, obstacle=(3.0, _L2))
        assert out.residuals["trk"] == 0.0
    else:
        out = d.step(y=y)   # 통로 밖 → 반사 없음
        assert out.residuals["trk"] is None


def test_corridor_longitudinal_margin_near_obstacle_end():
    """DESIGN.md §13-3: 종방향 경계 ±0.05 m 안은 판정하지 않는다. 추적 장애물 끝(x_far)이 전단과 0.05 m 안이면(이미 거의 지나침)
    r_trk를 평가하지 않는다(None). 그 전까지는 통로에 확실히 있는데 무반사이므로 불일치 1.0이다.
    합성 입력: 장애물을 한 번 본 뒤 측정 없이(무반사) 같은 차로로 계속 직진해 장애물 위치를 통과시킨다(물리적으로는 충돌)."""
    d = _Drive(DetectorA())
    d.step(obstacle=(1.0, _L2))
    x_far = 1.0 + _LEN
    while True:
        out = d.step()   # 무반사(측정 없음)
        fx = d.x + base_config.L
        if fx >= x_far - 0.02:
            break
        if fx <= x_far - 0.06:
            assert out.residuals["trk"] == 1.0
    assert abs(fx - x_far) < 0.05           # 전제: 경계 여유 안
    assert out.residuals["trk"] is None


def test_corridor_ignores_tracks_beyond_lidar_range():
    """DESIGN.md §4·§13-3: r_trk = 추적 장애물이 통로에 남아 있어야 하는데 최대거리를 반환할 때의 불일치. 추적 근거리까지 거리가
    라이다 무반사 판정(≥ 9.95 m) 이상이면 반사가 없는 것이 정상이라 평가하지 않는다(None).
    합성 입력: 정지 상태(v=0)에서 ψ를 0 → 0.5 rad로 한 step에 바꾼다(정지 중 회전). 전단 x(x + L·cosψ)가 줄어 거리가 9.94 → 9.96 m가 된다."""
    d = _Drive(DetectorA())
    fx0 = base_config.L
    d.step(v=0.0, obstacle=(fx0 + 9.94, _L2))
    out = d.step(v=0.0, psi=0.5)   # 무반사
    assert (fx0 + 9.94) - (d.x + base_config.L * math.cos(0.5)) >= 9.95   # 전제
    assert out.residuals["trk"] is None


def test_corridor_range_uses_distance_ahead_of_front():
    """DESIGN.md §13-3: 통로 판정의 거리는 추적 근거리 − 전단 x다. 약 9.5 m를 달린 뒤 1 m 앞 장애물을 보면 통로에 확실히 있어
    r_trk가 평가된다(반사가 있으니 0.0).
    합성 입력: 장애물 없이 380 step 달린 뒤 1 m 앞에 장애물이 갑자기 나타난다."""
    d = _Drive(DetectorA())
    for _ in range(380):
        d.step()
    obstacle = (d.x + 0.5 * base_config.DT + base_config.L + 1.0, _L2)
    d.step(obstacle=obstacle)
    out = d.step(obstacle=obstacle)
    assert d.x > 9.0                        # 전제: 자차가 충분히 멀리 왔다
    assert out.residuals["trk"] == 0.0


# ---------------- 추적기(DESIGN.md §13-3 A3) ----------------

def test_front_gap_without_obstacle_info_does_not_create_track():
    """DESIGN.md §13-3 A3: 추적은 front_obstacle_info로만 만든다. 장애물이 없는데 front_gap만 튄 측정(lidar_spike의 허위 반사,
    faults.py:86-87)은 추적을 만들지 않고 예외도 내지 않는다."""
    d = _Drive(DetectorA())
    d.step()
    out = d.step(front_gap=1.0, info=None)
    assert d.det.tracks == []
    assert out.residuals["trk"] is None


def test_no_return_measurement_does_not_create_track():
    """DESIGN.md §13-3 구현 상수: front_gap ≥ 9.95 m는 무반사로 본다. 그 거리의 장애물 정보가 함께 와도 추적에 쓰지 않는다."""
    d = _Drive(DetectorA())
    d.step(obstacle=(base_config.L + 9.97, _L2))
    assert d.det.tracks == []


def test_track_position_is_mean_of_accepted_measurements():
    """DESIGN.md §13-3 A3(추가 승인 1): 갱신은 교체가 아니라 수용한 측정 전체의 평균이다. 게이트(4σ_fg = 5.66 cm) 안의
    측정 오차 +2, −2, +3, −1 cm를 주면 추적 위치 = 측정 평균, 수용 수 = 4.
    합성 입력: 측정 오차를 정해진 값으로 주입한다(노이즈 모델 아님)."""
    d = _Drive(DetectorA())
    x_obs, errs = 2.0, [0.02, -0.02, 0.03, -0.01]
    for e in errs:
        fx = d.x + (0.5 * base_config.DT if d.prev else 0.0) + base_config.L
        d.step(obstacle=(x_obs, _L2), front_gap=x_obs - fx + e,
               info=FrontObstacleInfo(gap_near=x_obs - fx + e, gap_far=x_obs - fx + e + _LEN, y_lo=_L2[0], y_hi=_L2[1]))
    running = [sum(errs[:i]) / i for i in range(1, len(errs))]
    assert all(abs(e - m) < TRACK_GATE_Z * SIGMA_FG for e, m in zip(errs[1:], running))   # 전제: 매 측정이 그때 평균의 게이트 안
    (tr,) = d.det.tracks
    assert tr.n == len(errs)
    assert tr.x_near == pytest.approx(x_obs + sum(errs) / len(errs), abs=1e-12)


def test_dead_reckoning_and_front_point_match_plant_while_heading_is_nonzero():
    """DESIGN.md §13-3 A3: 자차 이동량은 플랜트와 같은 Euler식(x_k = x_{k−1} + v·cosψ·dt), 전단 기준점은 x + L·cosψ(§4 r_fg 식,
    vehicle.py:24·30-32). 노이즈 없는 정지 장애물을 ψ = 0.3 rad로 다가가며 보면 모든 측정이 같은 위치를 가리켜 전부 수용되고,
    추적 위치 = 실제 장애물 위치다."""
    d = _Drive(DetectorA())
    x_obs, n = 3.0, 30
    for _ in range(n):
        d.step(psi=0.3, obstacle=(x_obs, _L2))
    (tr,) = d.det.tracks
    assert tr.n == n
    assert tr.x_near == pytest.approx(x_obs, abs=1e-9)


# ---------------- 연속 채널 마스크(DESIGN.md §4 표) ----------------

def test_fg_residual_valid_only_if_previous_gap_positive():
    """DESIGN.md §4: r_fg의 유효 조건은 두 값 모두 < 최대거리이고 fg_{k−1} > 0. 직전 front_gap이 0(접촉)이면 마스크(None),
    0보다 크면(예: 0.8 m) 계산한다."""
    d = _Drive(DetectorA())
    d.step(v=0.0, front_gap=0.8, info=None)
    out = d.step(v=0.0, front_gap=0.8, info=None)
    assert out.residuals["fg"] == pytest.approx(0.0, abs=1e-12)
    d2 = _Drive(DetectorA())
    d2.step(v=0.0, front_gap=0.0, info=None)
    assert d2.step(v=0.0, front_gap=0.0, info=None).residuals["fg"] is None


def test_psi_residual_masked_when_previous_speed_is_zero():
    """DESIGN.md §4·§13 A4: r_ψ의 유효 조건은 v > 0. 직전 속도가 0이면 마스크(None), 0보다 크면 계산한다."""
    d = _Drive(DetectorA())
    d.step(v=0.0)
    assert d.step(v=0.0).residuals["psi"] is None
    d2 = _Drive(DetectorA())
    d2.step(v=0.5)
    assert d2.step(v=0.5).residuals["psi"] == pytest.approx(0.0, abs=1e-12)


# ---------------- 경보 ----------------

def test_alarm_requires_score_strictly_above_threshold():
    """DESIGN.md §4·§24: 경보는 S > h(엄격). ir_miss 불일치 한 번이면 점수 = LLR_MISMATCH(정확히)이고, h가 그 값이면 경보가 아니다.
    불일치가 한 번 더 나면 경보다."""
    d = _Drive(DetectorA(threshold=LLR_MISMATCH))
    out = d.step(ey_line=None)
    assert out.score == LLR_MISMATCH
    assert out.alarm is False
    assert d.step(ey_line=None).alarm is True
