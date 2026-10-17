"""
M/C트랙 전용: legacy_2025/final_hierarchical_backup_thesis_1204.py(5단계 재정리 전 위치 code_backup/final_hierarchical_backup.py,
2025-12-04 04:17, STAGE1_FACTS.md에서
확인된 "실험 당시 코드")의 OSQPMPC를 그대로 불러와 옛 MPC 출력을 구한다.
repro/docs/WORK_RULES.md 예외 허용 위치(thesis_v2/tests/compare/만 기존 코드 import 허용) — 이 파일만
이 옛 코드를 import한다. baseline/은 이 모듈을 참조하지 않는다.

옛 MPC 생성자 시그니처(확인됨, legacy_2025/final_hierarchical_backup_thesis_1204.py:855):
    OSQPMPC(vp: VehicleParams, rp: RoadParams, N, dt, qy, qpsi, rdelta, rddelta)
    solve(y0, psi0_rad, v0, target_y) -> (delta_deg, ok)
vp/rp는 코드 기본값(L=0.20, DELTA_MAX_DEG=25.0, V_MAX=0.5, W=0.30, MAX_Y_DEVIATION=0.45)을
그대로 사용 — repro/docs/WORK_RULES.md 고정 파라미터와 일치(assert로 확인).
N,dt,qy,qpsi,rdelta,rddelta는 baseline과 동일한 고정값을 사용(같은 입력 비교가 목적이므로
가중치 자체를 다르게 하면 "MPC 구현 차이"와 "가중치 차이"가 섞임 — MEASURE_PLAN.md C트랙 원칙).
"""
import importlib.util
import sys
from pathlib import Path
from typing import Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
OLD_CODE_PATH = REPO_ROOT / "legacy_2025" / "final_hierarchical_backup_thesis_1204.py"

_module = None


def _load_old_module():
    global _module
    if _module is not None:
        return _module
    spec = importlib.util.spec_from_file_location("_old_final_hierarchical_backup", OLD_CODE_PATH)
    mod = importlib.util.module_from_spec(spec)
    # 옛 코드가 자기 자신을 이름으로 재참조하지 않으므로 sys.modules 등록은
    # 필수는 아니지만, dataclass/typing 내부에서 모듈을 찾는 경우를 대비해 등록해둔다.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _module = mod
    return mod


def build_old_mpc(N: int, dt: float, qy: float, qpsi: float, rdelta: float, rddelta: float):
    """옛 코드의 OSQPMPC 인스턴스를 생성. vp/rp는 옛 코드 기본값(변경하지 않음)."""
    mod = _load_old_module()
    vp = mod.VehicleParams()
    rp = mod.RoadParams()
    assert vp.L == 0.20 and vp.DELTA_MAX_DEG == 25.0 and vp.V_MAX == 0.5
    assert rp.W == 0.30 and rp.MAX_Y_DEVIATION == 0.45
    return mod.OSQPMPC(vp=vp, rp=rp, N=N, dt=dt, qy=qy, qpsi=qpsi, rdelta=rdelta, rddelta=rddelta)


def solve_old(mpc, y0: float, psi0_rad: float, v0: float, target_y: float) -> Tuple[float, bool]:
    return mpc.solve(y0, psi0_rad, v0, target_y)
