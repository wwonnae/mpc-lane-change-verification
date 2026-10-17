"""
측정 지표 분류 함수(제약 만족/위반, clip 세분류, 조향 포화). 순수 함수, 제어 로직에 영향
없음(로그된 값을 사후 분류만 함) -- MEASURE_PLAN.md P트랙, SETTINGS_DECISION.md §18(eps_abs
기반 허용오차 원칙).
"""
import math
from typing import Optional

from . import config
from .fsm import FSMState

_RAD2DEG = 180.0 / math.pi

# §18: OSQP eps_abs(rad/m 단위, QP 변수 native 단위)를 그대로 "수치 허용오차"로 재사용.
# delta·psi는 QP 변수가 rad이므로 deg로 변환, y는 QP 변수가 이미 m이라 변환 없음.
TOL_DELTA_DEG = config.OSQP_EPS_ABS * _RAD2DEG
TOL_PSI_DEG = config.OSQP_EPS_ABS * _RAD2DEG
TOL_Y_M = config.OSQP_EPS_ABS


def classify_clip(after_rate_deg: float) -> Optional[str]:
    """postprocess.apply()의 after_rate_deg(rate limit 후, clip 전) 기준으로 clip 사유 분류.
    None: clip 자체가 없었음(|after_rate|<=25). "clip_numerical": eps_abs 이내로 초과(솔버
    수치오차 수준). "clip_violation": eps_abs를 넘는 초과(§16 버그 판정 기준과 동일 원칙)."""
    excess = abs(after_rate_deg) - config.DELTA_MAX_DEG
    if excess <= 0:
        return None
    if excess <= TOL_DELTA_DEG:
        return "clip_numerical"
    return "clip_violation"


def delta_within_tolerance(delta_raw_deg: float) -> bool:
    """REQ-MPC-04: |delta|<=25deg, eps_abs만큼 허용오차."""
    return abs(delta_raw_deg) <= config.DELTA_MAX_DEG + TOL_DELTA_DEG


def psi_within_tolerance(psi_deg: float) -> bool:
    """REQ-MPC-04: |psi|<=80deg, eps_abs만큼 허용오차."""
    return abs(psi_deg) <= config.PSI_LIMIT_DEG + TOL_PSI_DEG


def y_within_tolerance(y: float, state: FSMState) -> Optional[bool]:
    """REQ-MPC-05: 상태별 y 위치제약, eps_abs만큼 허용오차. SAFE_STOP은 위치제약이 정의되지
    않음(REQ-LAT-05, §16 -- POSITION_CONSTRAINTS에 키 없음)이라 None(해당없음)을 반환한다."""
    if state == FSMState.SAFE_STOP:
        return None
    lo, hi = config.POSITION_CONSTRAINTS[state.value]
    return (lo - TOL_Y_M) <= y <= (hi + TOL_Y_M)


def is_saturated(delta_final_deg: float) -> bool:
    """조향 포화: |delta_final|>=25-0.01deg."""
    return abs(delta_final_deg) >= config.DELTA_MAX_DEG - 0.01
