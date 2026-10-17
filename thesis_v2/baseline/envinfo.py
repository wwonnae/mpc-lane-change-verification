"""
실행 환경 기록. 교차 환경(노트북/SSAFY PC) 재현성 확인용(repro/docs/DESIGN_BASELINE.md §3
env.json, SETTINGS_DECISION.md §18). 제어 로직과 무관 — run.py/check_golden.py에서만 쓴다.
전원 상태 기록은 MEASURE_PLAN.md 공통 원칙(공식 계산시간 측정은 AC 전원 + Windows 최고
성능 모드에서만 인정, 2026-09-17 환경 결정 변경)의 사후 확인용.
"""
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from . import config

# 공식 계산시간 측정 환경(MEASURE_PLAN.md 공통 원칙, 2026-09-17 변경: SSAFY PC -> 노트북)
OFFICIAL_MEASUREMENT_HOSTNAME = "DESKTOP-MDCKRJS"

# Windows 전원 모드 overlay의 "최고 성능"(Best/Max Performance) 표준 GUID(로캘 무관, Microsoft
# 공개 문서 기준 well-known 값). 이 GUID가 power_mode_overlay 문자열에 포함되면
# "최고 성능"으로 판정한다(이름 문자열 매칭은 로캘에 따라 달라 신뢰할 수 없음).
BEST_PERFORMANCE_OVERLAY_GUID = "ded574b5-45a0-4f42-8737-46345c09c238"


def _get_power_plan_name() -> str:
    """`powercfg /getactivescheme` 출력에서 괄호 안 계획 이름을 추출. 실패 시 "unknown"."""
    try:
        result = subprocess.run(
            ["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            start = result.stdout.find("(")
            end = result.stdout.find(")")
            if start != -1 and end != -1 and end > start:
                return result.stdout[start + 1:end].strip()
        return "unknown"
    except Exception:
        return "unknown"


def _get_power_mode_overlay() -> str:
    """Windows 11 "전원 모드"(최고 절전/균형/최고 성능) 슬라이더는 레지스트리상 별도
    "overlay scheme"으로 저장된다(전원 계획=powercfg /getactivescheme과는 다른 값).
    HKLM\\SYSTEM\\CurrentControlSet\\Control\\Power\\User\\PowerSchemes의
    ActiveOverlayAcPowerScheme(GUID)을 읽고, 같은 트리의 <GUID>\\FriendlyName으로 이름을
    붙인다. 이 키·값이 없는 기기(예: OEM 전원관리 소프트웨어가 대신 제어하는 경우)에서는
    "감지 불가"를 반환한다(MEASURE_PLAN.md에 수동 확인 항목으로 기록됨)."""
    try:
        import winreg

        base = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as key:
            try:
                guid, _ = winreg.QueryValueEx(key, "ActiveOverlayAcPowerScheme")
            except FileNotFoundError:
                return "감지 불가(ActiveOverlayAcPowerScheme 값 없음 -- 이 기기는 Windows " \
                       "전원 모드 슬라이더를 registry overlay로 노출하지 않을 수 있음)"
        friendly = None
        for root, sub in (
            (winreg.HKEY_LOCAL_MACHINE, f"{base}\\{guid}"),
            (winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Control\\Power\\User\\Default\\PowerSchemes\\{guid}"),
        ):
            try:
                with winreg.OpenKey(root, sub) as gkey:
                    friendly, _ = winreg.QueryValueEx(gkey, "FriendlyName")
                    break
            except FileNotFoundError:
                continue
        if friendly and friendly.startswith("@") and "," in friendly:
            # MUI 간접 문자열(@dll,-resID,FallbackText) -- FallbackText만 취함(로캘 무관)
            friendly = friendly.rsplit(",", 1)[-1].strip()
        return f"{friendly or guid} ({guid})"
    except Exception:
        return "감지 불가(레지스트리 조회 실패)"


def _get_ac_status() -> str:
    """Windows `GetSystemPowerStatus` API의 ACLineStatus. 실패/비-Windows 시 "unknown"."""
    try:
        import ctypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("Reserved1", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = SYSTEM_POWER_STATUS()
        ok = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))  # type: ignore[attr-defined]
        if not ok:
            return "unknown"
        return {0: "battery", 1: "AC", 255: "unknown"}.get(status.ACLineStatus, "unknown")
    except Exception:
        return "unknown"


def _overlay_is_best_performance(overlay_str: str) -> bool:
    return BEST_PERFORMANCE_OVERLAY_GUID in (overlay_str or "")


def collect_env_info(power_mode_confirmed: bool = False) -> Dict[str, Any]:
    """power_mode_confirmed: 사용자가 Windows 설정 > 시스템 > 전원 > "전원 모드"가
    "최고 성능"임을 육안으로 확인했다는 표시(run.py --power-mode-confirmed). 자동 감지가
    안 되는 기기(이 노트북 포함, §3)에서 공식 조건을 성립시키는 유일한 경로다."""
    import numpy
    import scipy
    import osqp

    hostname = socket.gethostname()
    ac_status = _get_ac_status()
    overlay = _get_power_mode_overlay()
    overlay_confirms_best_performance = _overlay_is_best_performance(overlay)
    meets_official_condition = (
        ac_status == "AC" and (overlay_confirms_best_performance or power_mode_confirmed)
    )

    power = {
        "ac_status": ac_status,
        "power_plan": _get_power_plan_name(),
        "power_mode_overlay": overlay,
        "power_mode_overlay_confirms_best_performance": overlay_confirms_best_performance,
        "power_mode_user_confirmed": power_mode_confirmed,
        "power_mode_user_confirmed_at": (
            datetime.now(timezone.utc).isoformat() if power_mode_confirmed else None
        ),
        "meets_official_condition": meets_official_condition,
        "meets_official_condition_note": (
            "ac_status=='AC' AND (power_mode_overlay가 최고 성능 GUID를 가리키거나 OR "
            "power_mode_user_confirmed==true). MEASURE_PLAN.md 공통 원칙 참고."
        ),
    }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": hostname,
        "is_official_measurement_host": hostname == OFFICIAL_MEASUREMENT_HOSTNAME,
        "executable": sys.executable,
        "python": sys.version,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "osqp": osqp.__version__,
        "os": platform.platform(),
        "cpu": platform.processor(),
        "power": power,
        "osqp_settings": {
            "eps_abs": config.OSQP_EPS_ABS,
            "eps_rel": config.OSQP_EPS_REL,
            "max_iter": config.OSQP_MAX_ITER,
            "polishing": config.OSQP_POLISHING,
            "warm_starting": config.OSQP_WARM_STARTING,
            "raise_error": config.OSQP_RAISE_ERROR,
        },
    }
