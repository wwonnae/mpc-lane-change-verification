"""
REQ-SEN-01 회귀 테스트 (v1.1 버그 수정, 원래는 ROBUSTNESS_PLAN.md S7b 사전 확인용 진단
테스트로 작성됨).

이력: front_gap()의 `gap = max(0.0, obs.x_near - fx)`가 차체 전단을 완전히 지나친
장애물을 방향 구분 없이 0.0으로 보고하던 결함을 2026-09-22에 발견(코드 검토 + 100
에피소드 관찰구간 재분석, `THESIS_REVISION_LOG.md` 2026-09-22 REQ-SEN-01)했고, 사용자
승인 후 `sensors.py`에 `if obs.x_far < fx: continue` 방향 필터를 추가해 수정했다([정합]
버그 수정). 아래 첫 테스트는 원래 "현재(버그) 동작 문서화"였던 것을 "수정 후 정상 동작"
기대값으로 전환한 회귀 테스트다.
"""
import pytest

from thesis_v2.baseline import config, sensors
from thesis_v2.baseline.vehicle import VehicleState
from thesis_v2.baseline.world import Obstacle


def test_front_gap_obstacle_fully_behind_rear_is_excluded():
    """장애물이 차체 전단보다 완전히 뒤(같은 차로, 통로 겹침)일 때: '장애물 없음'과
    동등하게 LIDAR_MAX_RANGE를 반환해야 한다(v1.1 수정 후).
    x=1.0 -> rear_x=1.0, front_x=1.2(L=0.2). 장애물 x_near=0.0,x_far=0.2로 완전히 후방
    (obs.x_far=0.2 < fx=1.2)."""
    state = VehicleState(x=1.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=0.0, x_far=0.2, y_lo=-0.075, y_hi=0.075)
    gap = sensors.front_gap(state, [obs])
    assert gap == config.LIDAR_MAX_RANGE


def test_front_gap_obstacle_overlapping_vehicle_body_is_zero():
    """장애물이 차체와 x구간이 겹칠 때(obs.x_far>=fx, 사실상 접촉/중첩): gap=0.0 유지
    (일부라도 아직 전방에 걸쳐 있으므로 제외 대상이 아님 -- 수정 전후 동작 동일)."""
    state = VehicleState(x=1.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=1.05, x_far=1.25, y_lo=-0.075, y_hi=0.075)
    gap = sensors.front_gap(state, [obs])
    assert gap == 0.0


def test_front_gap_obstacle_directly_ahead_is_normal_positive_gap():
    """장애물이 바로 앞일 때: 정상적으로 양의 거리 반환(기존 test_sensors.py와 동일 원칙,
    이 파일의 대조군, 수정 전후 동작 동일)."""
    state = VehicleState(x=1.0, y=0.0, psi=0.0, v=0.4)
    obs = Obstacle(x_near=2.0, x_far=2.2, y_lo=-0.075, y_hi=0.075)
    gap = sensors.front_gap(state, [obs])
    assert gap == pytest.approx(0.8)
