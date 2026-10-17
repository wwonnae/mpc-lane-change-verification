"""
종방향(속도) 제어. 논문 제출 이후 작성.
REQ-SPD-01~05: 속도는 FSM 상태로만 결정, front_gap이 직접 결정하지 않음.
"""
from . import config
from .fsm import FSMState


def compute_v_cmd(state: FSMState) -> float:
    if state == FSMState.SAFE_STOP:
        return 0.0  # REQ-SPD-02/03: 즉시 0
    return config.V_MAX  # REQ-SPD-01: v_ref, 모든 비-SAFE_STOP 상태
