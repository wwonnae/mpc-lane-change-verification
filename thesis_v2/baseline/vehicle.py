"""
차량 kinematic bicycle model. 논문 제출 이후 작성.
REQ-VEH-01 (eq 1-3, p.7), REQ-VEH-04 (Euler 적분), REQ-VEH-05 (속도 동역학 없음),
REQ-MPC-07b (부호 규약: +y=좌측, +psi=좌회전, +delta=좌회전).
"""
import math
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class VehicleState:
    x: float    # m, 후륜 중심
    y: float    # m, +=좌측
    psi: float  # rad, +=좌회전(반시계)
    v: float    # m/s


def step(state: VehicleState, delta_deg: float, v_cmd: float, dt: float) -> VehicleState:
    """REQ-VEH-01: dx=v cos(psi), dy=v sin(psi), dpsi=(v/L) tan(delta).
    REQ-VEH-04: Euler 적분. REQ-VEH-05: v는 다음 스텝에 v_cmd로 즉시 대입(동역학 없음)."""
    delta_rad = math.radians(delta_deg)
    x = state.x + state.v * math.cos(state.psi) * dt
    y = state.y + state.v * math.sin(state.psi) * dt
    psi = state.psi + (state.v / config.L) * math.tan(delta_rad) * dt
    return VehicleState(x=x, y=y, psi=psi, v=v_cmd)


def front_x(state: VehicleState) -> float:
    """차체 전단 x좌표 (§12 기준점)."""
    return state.x + config.L * math.cos(state.psi)


def rear_x(state: VehicleState) -> float:
    """차체 후단(=후륜 중심) x좌표."""
    return state.x


def initial_state(v0: float, y0: float, psi0_deg: float = 0.0) -> VehicleState:
    return VehicleState(x=0.0, y=y0, psi=math.radians(psi0_deg), v=v0)
