"""
개선판 횡방향 제어. baseline `lateral.py`와 선택 로직은 동일(REQ-LAT-01~05) -- 다른 점은
MPC 호출 시 delta_prev(I1)·obstacle_info(I2)를 함께 넘긴다는 것뿐이다.
"""
import math
from dataclasses import dataclass
from typing import Optional

from thesis_v2.baseline import config
from thesis_v2.baseline.fsm import FSMState, target_line_y
from .mpc import ImprovedMPC, MPCResult
from .sensors import FrontObstacleInfo

_RAD2DEG = 180.0 / math.pi


@dataclass
class LateralResult:
    delta_desired_deg: float
    mode: str
    mpc_result: Optional[MPCResult]


def compute_lateral(state: FSMState, ey: Optional[float], y: float, psi_rad: float,
                     v: float, mpc: ImprovedMPC, delta_prev_deg: float,
                     obstacle_info: Optional[FrontObstacleInfo] = None) -> LateralResult:
    if state == FSMState.SAFE_STOP:
        return LateralResult(delta_desired_deg=delta_prev_deg, mode="hold_last", mpc_result=None)

    target_y = target_line_y(state)

    if state in (FSMState.KEEP_L2, FSMState.KEEP_L1) and ey is not None:
        delta_rad = -config.K_EY * ey
        delta_deg = delta_rad * _RAD2DEG
        return LateralResult(delta_desired_deg=delta_deg, mode="line_follow", mpc_result=None)

    result = mpc.solve(y0=y, psi0_rad=psi_rad, v0=v, target_y=target_y, state_name=state.value,
                        delta_prev_deg=delta_prev_deg, obstacle_info=obstacle_info)
    return LateralResult(delta_desired_deg=result.delta_deg, mode="mpc", mpc_result=result)
