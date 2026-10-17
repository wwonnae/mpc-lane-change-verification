"""
summary.json 집계. MEASURE_PLAN.md P트랙 지표(제약 만족률, clip 세분류, 조향 포화 비율,
계산시간, QP 실패/fallback 총계, 시나리오별 기대 결과 달성률, 성공률/충돌률 Wilson 95%
신뢰구간)를 여러 EpisodeResult에서 모아 계산한다. 순수 집계 -- 제어 로직과 무관.
2단계-C 결과 분석(repro/2c_analysis/)에서 누락이 확인되어 추가(solver_fail_total,
fallback_total, p50/p95/p99, 최대 계산시간 위치 + 첫 호출 제외 max, Wilson CI).
"""
import math
import statistics
from typing import Any, Dict, List, Optional

import numpy as np

from .fsm import FSMState
from .runner import EpisodeResult

_Z_95 = 1.96  # 95% 신뢰수준 z값


def wilson_ci(k: int, n: int, z: float = _Z_95) -> Optional[Dict[str, float]]:
    """Wilson score interval. k=성공(또는 해당 사건) 횟수, n=전체 시행 수."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return {"point": p, "lo": max(0.0, center - margin), "hi": min(1.0, center + margin), "z": z}


def _format_rate_ci(k: int, n: int, ci: Optional[Dict[str, float]]) -> Optional[str]:
    """요청 형식: "k/n (95% CI a~b%)". "단독 %" 표기 금지(MEASURE_PLAN.md 보고 규칙)."""
    if ci is None:
        return None
    return f"{k}/{n} (95% CI {ci['lo'] * 100:.1f}~{ci['hi'] * 100:.1f}%)"

# MEASURE_PLAN.md §"실행 규모와 예상 시간": 20Hz 예산(50ms)
STEP_BUDGET_MS = 50.0

# 시나리오별 "기대 결과"(REQ-SIM-07: paper는 SAFE_STOP 발생 안 함이 기대값, left_obstacle은
# REQ-FSM-02b 검증용으로 SAFE_STOP 발생 자체가 기대값 -- MEASURE_PLAN.md P트랙 참고)
EXPECTED_OUTCOME = {"paper": "성공", "left_obstacle": "SAFE_STOP"}


def _rate(violations: int, checked: int):
    if checked == 0:
        return None
    return 1.0 - violations / checked


def _percentiles(data: List[float]) -> Dict[str, Optional[float]]:
    if not data:
        return {"p50": None, "p95": None, "p99": None}
    p50, p95, p99 = np.percentile(np.array(data), [50, 95, 99])
    return {"p50": float(p50), "p95": float(p95), "p99": float(p99)}


def _first_mpc_call_idx(r: EpisodeResult) -> Optional[int]:
    return next(
        (i for i, row in enumerate(r.logger.rows) if (row.get("t_mpc_solve_ms") or 0.0) > 0.0),
        None,
    )


def _max_row_info(results: List[EpisodeResult], field: str,
                   exclude_first_mpc_call: bool = False) -> Optional[Dict[str, Any]]:
    """`field`(t_mpc_solve_ms 또는 t_step_ms) 최댓값이 발생한 step/seed/state.
    exclude_first_mpc_call=True면 각 episode의 첫 MPC 호출 step(warm-up 가능성)은 제외."""
    first_idx_cache: Dict[int, Optional[int]] = {}
    best = None  # (value, seed, row_idx0based, t, state)
    for r in results:
        first_idx = _first_mpc_call_idx(r)
        first_idx_cache[r.seed] = first_idx
        for i, row in enumerate(r.logger.rows):
            if exclude_first_mpc_call and i == first_idx:
                continue
            val = row.get(field) or 0.0
            if best is None or val > best[0]:
                best = (val, r.seed, i, row.get("t"), row.get("state"))
    if best is None:
        return None
    val, seed, idx, t, state = best
    first_idx = first_idx_cache.get(seed)
    return {
        field: val,
        "seed": seed,
        "step": idx + 1,
        "t": t,
        "state": state,
        "is_first_mpc_call_of_episode": (first_idx == idx),
    }


def _max_mpc_call_info(results: List[EpisodeResult],
                        exclude_first_call: bool = False) -> Optional[Dict[str, Any]]:
    return _max_row_info(results, "t_mpc_solve_ms", exclude_first_mpc_call=exclude_first_call)


def _step_time_stats(results: List[EpisodeResult]) -> Dict[str, Any]:
    """REQ-EVAL-03/MEASURE_PLAN.md "t_step_ms"(스텝 1개 전체 소요시간, 센서~종료판정)
    통계. mpc_solve_time_ms와 나란히 두되 별도 블록(§4 계산시간 최댓값 요청과 동일 형식)."""
    all_ms: List[float] = []
    for r in results:
        all_ms.extend((row.get("t_step_ms") or 0.0) for row in r.logger.rows)
    if all_ms:
        mean = statistics.mean(all_ms)
        mx = max(all_ms)
        stdev = statistics.pstdev(all_ms) if len(all_ms) > 1 else 0.0
    else:
        mean = mx = stdev = 0.0
    pct = _percentiles(all_ms)
    max_info = _max_row_info(results, "t_step_ms")
    max_info_excl_first = _max_row_info(results, "t_step_ms", exclude_first_mpc_call=True)
    max_excl_first = max_info_excl_first["t_step_ms"] if max_info_excl_first else None
    return {
        "mean": mean, "max": mx, "stdev": stdev,
        "p50": pct["p50"], "p95": pct["p95"], "p99": pct["p99"],
        "max_call_info": max_info,
        "max_excluding_first_call": max_excl_first,
        "max_call_info_excluding_first_call": max_info_excl_first,
        "n_steps": len(all_ms),
        "budget_ms_20hz": STEP_BUDGET_MS,
        "mean_pct_of_budget": (mean / STEP_BUDGET_MS * 100.0) if all_ms else None,
        "note": ("스텝 1개 전체 소요시간(센서~종료판정, runner.py 1~8번). MPC solve 시간"
                 "(mpc_solve_time_ms)을 포함한다 -- t_step_ms >= t_mpc_solve_ms. "
                 "\"첫 호출 제외 max\"는 그 episode의 첫 MPC 호출이 일어난 step을 제외."),
    }


def build_summary(results: List[EpisodeResult], scenario_name: str,
                   env_info: Dict[str, Any]) -> Dict[str, Any]:
    n = len(results)
    outcome_counts: Dict[str, int] = {}
    for r in results:
        outcome_counts[r.outcome] = outcome_counts.get(r.outcome, 0) + 1

    delta_violation = sum(r.delta_violation_count for r in results)
    delta_checked = sum(r.delta_checked_count for r in results)
    psi_violation = sum(r.psi_violation_count for r in results)
    y_violation = sum(r.y_violation_count for r in results)
    y_checked = sum(r.y_checked_count for r in results)

    clip_total = sum(r.clip_count for r in results)
    clip_numerical = sum(r.clip_numerical_count for r in results)
    clip_violation = sum(r.clip_violation_count for r in results)

    state_duration_total: Dict[str, int] = {s.value: 0 for s in FSMState}
    saturation_total: Dict[str, int] = {s.value: 0 for s in FSMState}
    for r in results:
        for s, cnt in r.state_duration_steps.items():
            state_duration_total[s] += cnt
        for s, cnt in r.saturation_steps.items():
            saturation_total[s] += cnt
    saturation_ratio_by_state = {
        s: (saturation_total[s] / state_duration_total[s] if state_duration_total[s] > 0 else None)
        for s in state_duration_total
    }

    solver_fail_total = sum(r.solver_fail_count for r in results)
    fallback_total = sum(r.fallback_count for r in results)

    all_mpc_ms: List[float] = []
    for r in results:
        all_mpc_ms.extend(r.mpc_solve_times_ms)
    if all_mpc_ms:
        mpc_mean = statistics.mean(all_mpc_ms)
        mpc_max = max(all_mpc_ms)
        mpc_stdev = statistics.pstdev(all_mpc_ms) if len(all_mpc_ms) > 1 else 0.0
    else:
        mpc_mean = mpc_max = mpc_stdev = 0.0
    mpc_percentiles = _percentiles(all_mpc_ms)
    max_call_info = _max_mpc_call_info(results)
    max_call_info_excl_first = _max_mpc_call_info(results, exclude_first_call=True)
    max_excl_first_call = (max_call_info_excl_first["t_mpc_solve_ms"]
                            if max_call_info_excl_first else None)

    expected_outcome = EXPECTED_OUTCOME.get(scenario_name)
    n_expected = outcome_counts.get(expected_outcome, 0) if expected_outcome else 0
    expected_outcome_achievement_rate = (n_expected / n) if (n and expected_outcome) else None
    expected_outcome_ci = wilson_ci(n_expected, n) if (n and expected_outcome) else None

    n_success = outcome_counts.get("성공", 0)
    n_collision = outcome_counts.get("충돌", 0)
    success_ci = wilson_ci(n_success, n) if n else None
    collision_ci = wilson_ci(n_collision, n) if n else None

    # MEASURE_PLAN.md 공통 원칙(2026-09-17 변경, envinfo.py collect_env_info()에서 계산):
    # 공식 계산시간 = 공식 호스트(노트북) + power.meets_official_condition(AC 전원 AND
    # (overlay가 최고 성능을 가리키거나 OR 사용자가 --power-mode-confirmed로 육안 확인)).
    is_official_host = bool(env_info.get("is_official_measurement_host"))
    power = env_info.get("power", {})
    meets_official = bool(power.get("meets_official_condition"))
    if is_official_host and meets_official:
        confirmed_by = ("overlay 감지" if power.get("power_mode_overlay_confirms_best_performance")
                         else "사용자 육안 확인(--power-mode-confirmed)")
        measurement_status = f"공식({env_info.get('hostname', '?')}, AC+최고성능 확인: {confirmed_by})"
    elif is_official_host and power.get("ac_status") == "AC":
        measurement_status = (f"참고({env_info.get('hostname', '?')}, AC는 확인되나 최고 성능 "
                               f"모드 미확인 -- --power-mode-confirmed 없이 실행됨)")
    elif is_official_host:
        measurement_status = f"참고({env_info.get('hostname', '?')}, 배터리 구동 -- 공식 호스트지만 AC 조건 미충족)"
    else:
        measurement_status = f"참고({env_info.get('hostname', '?')})"

    return {
        "scenario_name": scenario_name,
        "n_episodes": n,
        "outcome_counts": outcome_counts,
        "collision_count": n_collision,
        "collision_rate": (n_collision / n) if n else None,
        "collision_rate_ci95": collision_ci,
        "collision_rate_formatted": _format_rate_ci(n_collision, n, collision_ci),
        "safe_stop_count": outcome_counts.get("SAFE_STOP", 0),
        "success_rate": (n_success / n) if n else None,
        "success_rate_ci95": success_ci,
        "success_rate_formatted": _format_rate_ci(n_success, n, success_ci),
        "expected_outcome": expected_outcome,
        "expected_outcome_achievement_rate": expected_outcome_achievement_rate,
        "expected_outcome_achievement_rate_ci95": expected_outcome_ci,
        "expected_outcome_achievement_rate_formatted": (
            _format_rate_ci(n_expected, n, expected_outcome_ci) if expected_outcome else None
        ),
        "success_rate_note": (
            "success_rate는 항상 outcome=='성공' 라벨 기준. 시나리오별 '기대 결과'는 다를 수 "
            "있음(paper=성공, left_obstacle=SAFE_STOP -- REQ-FSM-02b 검증 목적) -- "
            "expected_outcome_achievement_rate가 시나리오 기대 결과 기준 지표. 모든 비율은 "
            "Wilson 95% 신뢰구간과 함께 보고한다(단독 % 표기 금지, MEASURE_PLAN.md 보고 규칙)."
        ),
        "solver_fail_total": solver_fail_total,
        "fallback_total": fallback_total,
        "constraint_satisfaction": {
            "delta_within_tolerance_rate": _rate(delta_violation, delta_checked),
            "psi_within_tolerance_rate": _rate(psi_violation, delta_checked),
            "y_within_tolerance_rate": _rate(y_violation, y_checked),
            "delta_checked_steps": delta_checked,
            "delta_violation_steps": delta_violation,
            "psi_violation_steps": psi_violation,
            "y_checked_steps": y_checked,
            "y_violation_steps": y_violation,
            "note": "허용오차 = OSQP eps_abs(SETTINGS_DECISION.md §18). y는 SAFE_STOP 스텝 제외(REQ-LAT-05, 위치제약 미정의)",
        },
        "clip_breakdown": {
            "clip_total": clip_total,
            "clip_numerical": clip_numerical,
            "clip_violation": clip_violation,
            "note": "clip_numerical=eps_abs 이내 초과(솔버 수치오차), clip_violation=eps_abs 초과(버그 후보, §16 판정 기준과 동일)",
        },
        "saturation_ratio_by_state": saturation_ratio_by_state,
        "state_duration_steps_total": state_duration_total,
        "mpc_solve_time_ms": {
            "mean": mpc_mean,
            "max": mpc_max,
            "stdev": mpc_stdev,
            "p50": mpc_percentiles["p50"],
            "p95": mpc_percentiles["p95"],
            "p99": mpc_percentiles["p99"],
            "max_call_info": max_call_info,
            "max_excluding_first_call": max_excl_first_call,
            "max_call_info_excluding_first_call": max_call_info_excl_first,
            "n_calls": len(all_mpc_ms),
            "budget_ms_20hz": STEP_BUDGET_MS,
            "mean_pct_of_budget": (mpc_mean / STEP_BUDGET_MS * 100.0) if all_mpc_ms else None,
            "measurement_status": measurement_status,
            "note": "MEASURE_PLAN.md 공통 원칙(2026-09-17 변경): 공식 측정 환경은 노트북(hostname DESKTOP-MDCKRJS) + AC 전원 + Windows 최고 성능 모드. 그 외(SSAFY PC, 배터리 구동 등)는 참고용으로만 보고(절대수치는 하드웨어 종속).",
        },
        "step_time_ms": {**_step_time_stats(results), "measurement_status": measurement_status},
        "env": env_info,
    }
