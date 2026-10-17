"""
횡방향 제어 (라인추종/MPC 선택). 논문 제출 이후 작성.
REQ-LAT-01~05. B-2 확정: KEEP_L2/KEEP_L1은 라인 감지 시 라인추종, 아니면 MPC.
EVADE_L/RETURN_TO_L2는 감지 여부와 무관하게 항상 MPC(REQ-LAT-02).
SAFE_STOP은 MPC·라인추종을 호출하지 않고 직전 최종 조향각을 유지한다
(REQ-LAT-05 [공백], SETTINGS_DECISION.md §16, 수정안 a).

선택표(상태 -> 횡방향 제어 모드):

| 상태          | ey 감지됨      | ey 미감지 |
|---------------|----------------|-----------|
| KEEP_L2       | line_follow    | mpc       |
| KEEP_L1       | line_follow    | mpc       |
| EVADE_L       | mpc            | mpc       |
| RETURN_TO_L2  | mpc            | mpc       |
| SAFE_STOP     | hold_last (ey 무관, MPC·라인추종 호출 안 함) |
"""
import math
from dataclasses import dataclass
from typing import Optional

from . import config
from .fsm import FSMState, target_line_y
from .mpc import OSQPMPC, MPCResult

_RAD2DEG = 180.0 / math.pi


@dataclass
class LateralResult:
    delta_desired_deg: float
    mode: str  # "line_follow" | "mpc" | "hold_last"
    mpc_result: Optional[MPCResult]


def compute_lateral(state: FSMState, ey: Optional[float], y: float, psi_rad: float,
                     v: float, mpc: OSQPMPC, delta_prev_deg: float) -> LateralResult:
    # REQ-LAT-05 [공백](§16): SAFE_STOP은 MPC·라인추종을 호출하지 않고 직전 최종 조향각을
    # 그대로 유지한다(후처리의 rate limit·clip은 그대로 통과시켜 기록 일관성을 유지 — 이미
    # 최종값이므로 rate limit는 항상 비활성, clip도 항상 비활성이 되어야 정상).
    if state == FSMState.SAFE_STOP:
        return LateralResult(delta_desired_deg=delta_prev_deg, mode="hold_last", mpc_result=None)

    target_y = target_line_y(state)

    if state in (FSMState.KEEP_L2, FSMState.KEEP_L1) and ey is not None:
        # REQ-LAT-01: delta = -K_ey * ey_line. PDF(p.10 식8)에 단위 명시 없음 — REQ-MPC-07a와
        # 같은 원칙(§11)으로 rad/m 채택([해석], SETTINGS_DECISION.md §17).
        delta_rad = -config.K_EY * ey
        delta_deg = delta_rad * _RAD2DEG
        return LateralResult(delta_desired_deg=delta_deg, mode="line_follow", mpc_result=None)

    # REQ-LAT-02/03/04: MPC (KEEP_L2/KEEP_L1 라인 미검출 시, EVADE_L/RETURN_TO_L2는 항상)
    result = mpc.solve(y0=y, psi0_rad=psi_rad, v0=v, target_y=target_y, state_name=state.value)
    return LateralResult(delta_desired_deg=result.delta_deg, mode="mpc", mpc_result=result)
