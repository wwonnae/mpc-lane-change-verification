"""
유한상태기계. 논문 제출 이후 작성.
REQ-FSM-01~04. 입력은 센서 출력 + 차량 자신의 y,psi(자기 상태, 시뮬레이터 장애물 좌표 아님).
"""
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from . import config


class FSMState(Enum):
    KEEP_L2 = "KEEP_L2"
    EVADE_L = "EVADE_L"
    KEEP_L1 = "KEEP_L1"
    RETURN_TO_L2 = "RETURN_TO_L2"
    SAFE_STOP = "SAFE_STOP"


class SensorReadings(NamedTuple):
    front_gap: float
    left_clear: bool
    right_clear: bool


@dataclass(frozen=True)
class FSM:
    state: FSMState
    last_change_t: float   # REQ-FSM-03: 마지막 전이 시각(쿨다운 기준)
    state_enter_t: float   # REQ-FSM-02d: 현재 상태 진입 시각(T_KEEP_L1_MIN 기준)


def initial_fsm() -> FSM:
    """REQ-FSM-03b(§13): 쿨다운이 이미 만료된 것으로 초기화(첫 전이를 막지 않음)."""
    return FSM(state=FSMState.KEEP_L2, last_change_t=-config.COOLDOWN, state_enter_t=0.0)


def target_line_y(state: FSMState) -> float:
    """REQ-LAT: 상태별 목표 차선 중심(라인추종/MPC target 공통)."""
    if state in (FSMState.KEEP_L2, FSMState.RETURN_TO_L2):
        return 0.0
    return config.W


def step(fsm: FSM, sensors: SensorReadings, y: float, psi_deg: float, t: float) -> FSM:
    """REQ-FSM-02a~02e, REQ-FSM-03a(쿨다운 5개 전이 전부 적용)."""
    cooldown_ok = (t - fsm.last_change_t) >= config.COOLDOWN
    new_state = fsm.state

    # REQ-FSM-02b: 모든 상태 -> SAFE_STOP, 예외 없음 (우선 체크)
    if cooldown_ok and sensors.front_gap < config.G_SAFE_MIN and not sensors.left_clear:
        new_state = FSMState.SAFE_STOP
    elif fsm.state == FSMState.KEEP_L2:
        # REQ-FSM-02a
        if cooldown_ok and sensors.front_gap < config.G_TRIG and sensors.left_clear:
            new_state = FSMState.EVADE_L
    elif fsm.state == FSMState.EVADE_L:
        # REQ-FSM-02c
        if cooldown_ok and abs(y - config.W) <= config.NEAR_L1:
            new_state = FSMState.KEEP_L1
    elif fsm.state == FSMState.KEEP_L1:
        # REQ-FSM-02d (§14: right_clear AND t>T_KEEP_L1_MIN)
        elapsed = t - fsm.state_enter_t
        if cooldown_ok and elapsed > config.T_KEEP_L1_MIN and sensors.right_clear:
            new_state = FSMState.RETURN_TO_L2
    elif fsm.state == FSMState.RETURN_TO_L2:
        # REQ-FSM-02e [개정]: NEAR_L2=0.08 (원문 0.20)
        if cooldown_ok and abs(y) <= config.NEAR_L2 and abs(psi_deg) <= config.PSI_L2_LIMIT_DEG:
            new_state = FSMState.KEEP_L2
    elif fsm.state == FSMState.SAFE_STOP:
        pass  # REQ-FSM-04 (§1): 종단 상태, 복귀 없음

    if new_state != fsm.state:
        return FSM(state=new_state, last_change_t=t, state_enter_t=t)
    return fsm
