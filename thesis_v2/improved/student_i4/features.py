"""
I4: Student 입력 9차원(REQ-STU-02 [정합])·라벨 2차원(REQ-STU-03 [정합]) 조립과, v2 MPC
호출 입력 캡처(DESIGN_I4 §1-3 개정 1).

캡처 방식: improved/runner.py(동결)를 수정하지 않고, MPC 인스턴스의 solve만 감싸
실제로 들어간 갱신 전 (y0, psi0, v0, target_y, state)와 출력 δ를 기록한다. ey_line/
front_gap/left_clear는 같은 스텝 로그 행(갱신 전 센서 판독)에서 가져와 호출 순서대로
페어링한다.
"""
import math
from typing import Dict, List, Optional

import numpy as np

from thesis_v2.baseline import longitudinal
from thesis_v2.baseline.fsm import FSMState, target_line_y

FEATURE_NAMES = [
    "v", "ey_line", "front_gap", "left_clear",
    "state_KEEP_L2", "state_EVADE_L", "state_KEEP_L1", "state_RETURN_TO_L2", "state_SAFE_STOP",
]
LABEL_NAMES = ["delta", "v"]
STATE_ORDER = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2", "SAFE_STOP"]
# Student v2 입력 변형(DESIGN_I4 §6, SETTINGS_DECISION §20). 기존 9개 순서 유지, 뒤에 추가.
#   "9"  : REQ-STU-02 그대로(I4)
#   "S10": + psi_deg([개정])
#   "S11": + psi_deg, delta_prev_deg([개정]+[발전])
INPUT_VARIANTS = {
    "9": FEATURE_NAMES,
    "S10": FEATURE_NAMES + ["psi_deg"],
    "S11": FEATURE_NAMES + ["psi_deg", "delta_prev_deg"],
}


def extend_features(x9, variant: str, psi_deg, delta_prev_deg) -> np.ndarray:
    """9차원 벡터(또는 (n,9) 행렬)에 변형별 추가 입력을 붙인다."""
    x9 = np.asarray(x9, dtype=np.float32)
    extra = []
    if variant in ("S10", "S11"):
        extra.append(psi_deg)
    if variant == "S11":
        extra.append(delta_prev_deg)
    if not extra:
        return x9
    if x9.ndim == 1:
        return np.concatenate([x9, np.array(extra, dtype=np.float32)])
    return np.hstack([x9] + [np.asarray(e, dtype=np.float32).reshape(-1, 1) for e in extra])


# MPC가 호출될 수 있는 상태(REQ-LAT-02/03). SAFE_STOP은 hold_last(REQ-LAT-05)라 교사 라벨 없음.
MPC_STATES = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2"]


def build_feature_vector(v: float, ey: Optional[float], y: float, state: str,
                         front_gap: float, left_clear: bool) -> np.ndarray:
    """REQ-STU-02. ey 미검출(None/NaN)이면 y - target_line_y(state)로 대체 --
    RESULT_STUDENT.md §2 매핑표(code_backup get_student_features fallback과 같은 규칙)."""
    if ey is None or (isinstance(ey, float) and math.isnan(ey)):
        ey_val = y - target_line_y(FSMState(state))
    else:
        ey_val = float(ey)
    one_hot = [1.0 if state == s else 0.0 for s in STATE_ORDER]
    return np.array([float(v), ey_val, float(front_gap), 1.0 if left_clear else 0.0, *one_hot],
                    dtype=np.float32)


def v_target_label(state: str) -> float:
    """REQ-STU-03 v_target: 종방향 규칙 기반 출력(REQ-SPD-01/02) 그대로 -- MPC는 속도를 내지 않음."""
    return float(longitudinal.compute_v_cmd(FSMState(state)))


class SolveRecorder:
    """MPC 인스턴스의 solve를 감싸 호출 입력·출력을 순서대로 기록한다(제어 결과는 그대로 반환)."""

    def __init__(self, mpc):
        self.mpc = mpc
        self.calls: List[Dict] = []
        self._orig = mpc.solve
        mpc.solve = self._wrapped

    def _wrapped(self, y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0,
                 obstacle_info=None):
        res = self._orig(y0=y0, psi0_rad=psi0_rad, v0=v0, target_y=target_y,
                         state_name=state_name, delta_prev_deg=delta_prev_deg,
                         obstacle_info=obstacle_info)
        self.calls.append(dict(y0=float(y0), psi0_rad=float(psi0_rad), v0=float(v0),
                               target_y=float(target_y), state=state_name,
                               delta_prev_deg=float(delta_prev_deg),
                               delta_deg=float(res.delta_deg),
                               iterations=int(res.iterations),
                               solver_status=res.solver_status,
                               fallback_used=bool(res.fallback_used)))
        return res

    def pop(self) -> List[Dict]:
        out, self.calls = self.calls, []
        return out


def pair_calls_with_log(calls: List[Dict], log_rows: List[Dict]) -> List[Dict]:
    """MPC가 호출된 로그 행(solver_status != 'N/A')과 캡처된 호출을 순서대로 짝짓는다."""
    mpc_rows = [r for r in log_rows if r["solver_status"] != "N/A"]
    if len(mpc_rows) != len(calls):
        raise RuntimeError(f"MPC 호출 수 불일치: log={len(mpc_rows)} captured={len(calls)}")
    out = []
    for c, r in zip(calls, mpc_rows):
        if r["state"] != c["state"]:
            raise RuntimeError(f"상태 불일치: log={r['state']} captured={c['state']}")
        if abs(r["delta_mpc_raw"] - c["delta_deg"]) > 1e-12:
            raise RuntimeError("δ 불일치(로그 vs 캡처)")
        x = build_feature_vector(c["v0"], r["ey_line"], c["y0"], c["state"],
                                 r["front_gap"], r["left_clear"])
        out.append(dict(c, x=x, ey_is_fallback=r["ey_line"] is None,
                        psi_deg=c["psi0_rad"] * 180.0 / math.pi,
                        v_target=v_target_label(c["state"])))
    return out
