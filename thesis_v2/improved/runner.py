"""
개선판 에피소드 루프. baseline `runner.py`(v1.1, 관찰구간 FSM 상시 갱신 포함)와 스텝
순서는 동일하다. 차이: 센서에서 `FrontObstacleInfo`(I2용)도 함께 읽고, MPC에
`delta_prev_deg`·`obstacle_info`를 넘긴다. baseline 파일은 전혀 import하지 않는
`sensors.py`/`mpc.py`/`lateral.py`만 새로 작성했고, 나머지(vehicle/fsm/postprocess/
longitudinal/collision/metrics/logger/world)는 baseline에서 그대로 가져다 쓴다
(repro/docs/WORK_RULES.md 3단계 확정 사항 -- improved는 baseline 모듈을 import할 수 있으나 baseline
파일 자체는 수정하지 않는다).
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional

from thesis_v2.baseline import config, postprocess, longitudinal, collision, metrics
from thesis_v2.baseline.vehicle import VehicleState, initial_state, step as vehicle_step
from thesis_v2.baseline.fsm import FSM, FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.world import Scenario
from thesis_v2.baseline.logger import StepLogger
from thesis_v2.baseline import sensors as base_sensors

from . import sensors as improved_sensors
from .mpc import ImprovedMPC
from .lateral import compute_lateral

_RAD2DEG = 180.0 / math.pi


@dataclass
class Transition:
    step: int
    t: float
    from_state: str
    to_state: str


@dataclass
class EpisodeResult:
    seed: int
    scenario_name: str
    outcome: str
    finish_step: Optional[int]
    total_steps: int
    transitions: List[Transition]
    state_duration_steps: dict
    solver_fail_count: int
    fallback_count: int
    warm_start_shift_count: int
    max_iter_count: int             # solver_status=="maximum iterations reached" 발생 횟수
    max_iter_rejected_count: int    # 그 중 하드 제약 위반해 폐기(fallback 경로로 감)된 횟수
    time_limit_count: int           # I5: 안전망(time_limit) 발동 횟수 -- mpc.time_limit_fingerprint 판정(2026-10-14 정정 전: status=="run time limit reached"만)
    time_limit_rejected_count: int  # 그 중 하드 제약 위반해 폐기된 횟수
    rate_limit_count: int
    clip_count: int
    clip_numerical_count: int
    clip_violation_count: int
    delta_checked_count: int
    delta_violation_count: int
    psi_violation_count: int
    y_checked_count: int
    y_violation_count: int
    y_max_abs_violation_m: float   # 위반 크기(최대), REQ 없음 -- 판정기준 §5 신규
    y_cumulative_violation_m: float  # 위반 크기(누적)
    saturation_steps: dict
    mpc_solve_times_ms: List[float]
    observed_settle_violation: bool
    observed_transition_departure: bool
    violation_breakdown: dict  # 2026-09-23 검토: 제약 종류별 분해(차로/헤딩/조향/I2 슬랙)
    notable_step_log: List[dict]  # I5(v2) 검토용: solver_status/반복횟수/위반 스텝만 선별 기록
    max_derived_tol_deg: float  # SETTINGS_DECISION.md §19 검증용: 스텝별 실측 노름으로 계산한
    # 실제 허용오차(eps_abs+eps_rel*(||Ax||+prim_res))의 에피소드 내 최댓값 -- §19가 쓴
    # Z_max=1.396rad(80deg) 가정에서 나온 0.006530deg와 비교해 가정이 실측을 벗어나는지 확인
    steering_angle_violation_rigorous_count: int  # angle_excess가 그 스텝 자신의
    # derived_tol_deg(가정 없는 실측 상한)를 넘긴 횟수 -- 고정 상수(§19 0.006530deg)가
    # 아니라 스텝마다 다른 실측값과 비교하는 더 엄밀한 재확인(§19 가정 자체의 타당성 검증)
    steering_rate_violation_rigorous_count: int  # 위와 동일, 조향변화율(rate) 대상
    logger: StepLogger


_BREAKDOWN_CATEGORIES = ("lane", "heading", "steering_angle", "steering_rate",
                          "i2_y_deficit", "i2_psi_deficit")


def _new_breakdown() -> dict:
    return {cat: {"count": 0, "max": 0.0, "cum": 0.0, "states": []} for cat in _BREAKDOWN_CATEGORIES}


def _record(breakdown: dict, category: str, excess: float, state_name: str):
    if excess <= 0.0:
        return
    b = breakdown[category]
    b["count"] += 1
    b["max"] = max(b["max"], excess)
    b["cum"] += excess
    if state_name not in b["states"]:
        b["states"].append(state_name)


def run_episode(scenario: Scenario, mpc: Optional[ImprovedMPC] = None,
                 noise_profile=None, noise_rng=None,
                 control_delay_steps: int = 0) -> EpisodeResult:
    """control_delay_steps: S5(제어 지연, ROBUSTNESS_PLAN.md)와 동일한 정의 --
    baseline/runner.py의 delay_queue 메커니즘을 그대로 재사용(postprocess 이후 최종
    조향 명령이 차량에 반영되는 시점만 지연, 기본값 0은 지연 없음과 완전히 동일)."""
    mpc = mpc if mpc is not None else ImprovedMPC()
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    delay_queue: List[float] = []
    logger = StepLogger()
    transitions: List[Transition] = []
    state_duration = {s.value: 0 for s in FSMState}
    solver_fail_count = 0
    fallback_count = 0
    warm_start_shift_count = 0
    max_iter_count = 0
    max_iter_rejected_count = 0
    time_limit_count = 0
    time_limit_rejected_count = 0
    rate_limit_count = 0
    clip_count = 0
    clip_numerical_count = 0
    clip_violation_count = 0
    delta_checked_count = 0
    delta_violation_count = 0
    psi_violation_count = 0
    y_checked_count = 0
    y_violation_count = 0
    y_max_abs_violation = 0.0
    y_cumulative_violation = 0.0
    saturation_steps = {s.value: 0 for s in FSMState}
    mpc_times: List[float] = []
    visited_evade = False
    outcome = None
    finish_step = None
    observed_settle_violation = False
    observed_transition_departure = False
    breakdown = _new_breakdown()
    notable_step_log: List[dict] = []
    max_derived_tol_deg = 0.0
    steering_angle_violation_rigorous_count = 0
    steering_rate_violation_rigorous_count = 0

    step_idx = 0
    max_iter = config.MAX_STEPS + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None

    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT

        if noise_profile is None:
            fg = base_sensors.front_gap(vehicle, scenario.obstacles)
            lc = base_sensors.left_clear(vehicle, scenario.obstacles)
            rc = base_sensors.right_clear(vehicle, scenario.obstacles)
            pattern = base_sensors.ir_pattern(vehicle)
            ey = base_sensors.ey_line(pattern)
        else:
            fg = base_sensors.front_gap_noisy(vehicle, scenario.obstacles, noise_rng,
                                               noise_profile.sigma_front_gap)
            lc = base_sensors.left_clear_noisy(vehicle, scenario.obstacles, noise_rng,
                                                noise_profile.flip_p)
            rc = base_sensors.right_clear_noisy(vehicle, scenario.obstacles, noise_rng,
                                                 noise_profile.flip_p)
            pattern = base_sensors.ir_pattern(vehicle)
            ey = base_sensors.ey_line_noisy(base_sensors.ey_line(pattern), noise_rng,
                                             noise_profile.sigma_ey)
        obstacle_info = improved_sensors.front_obstacle_info(vehicle, scenario.obstacles)

        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append(Transition(step_idx, t, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
        fsm = fsm_new

        state_duration[fsm.state.value] += 1

        lat = compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc, delta_prev,
                               obstacle_info=obstacle_info)
        delta_desired = lat.delta_desired_deg
        angle_excess = 0.0
        rate_excess = 0.0
        if lat.mpc_result is not None:
            mpc_times.append(lat.mpc_result.compute_time_ms)
            if not lat.mpc_result.ok:
                solver_fail_count += 1
            if lat.mpc_result.fallback_used:
                fallback_count += 1
            if lat.mpc_result.warm_start_shift_used:
                warm_start_shift_count += 1
            if lat.mpc_result.solver_status == "maximum iterations reached":
                max_iter_count += 1
                if lat.mpc_result.approx_rejected:
                    max_iter_rejected_count += 1
            if lat.mpc_result.time_limit_hit:
                # I5(DESIGN_IMPROVED_V2.md §1-2) 안전망 발동 -- 반복 상한이 정상적으로
                # 훨씬 먼저 걸리므로 정상 dev/eval에서는 0건이 기대값이다.
                # 2026-10-14 정정(run #6 조사): status=="run time limit reached"만 세면 "solved"/
                # "solved inaccurate"로 보고된 절단을 놓친다 -> mpc.time_limit_fingerprint 판정으로 센다.
                # time_limit_rejected_count는 지금처럼 approx_rejected(하드체크 폐기, "run time limit
                # reached" 분기에서만 생김) 기준이다. 기록 전용 -- 제어에 쓰이지 않는다.
                time_limit_count += 1
                if lat.mpc_result.approx_rejected:
                    time_limit_rejected_count += 1
            # 조향각(원 MPC 출력, 후처리 전) 하드 제약(|delta|<=25deg) 위반 크기.
            # MEASURE_PLAN.md 기준(허용오차=OSQP eps_abs, TOL_DELTA_DEG≈0.0057deg)을
            # 그대로 적용 -- 그 이내는 위반으로 세지 않는다(2026-09-23 검토에서 정정:
            # 이전 "수치오차 수준"이라는 표현은 이 임계값을 적용하지 않은 채 쓴 것이었음).
            angle_excess = abs(lat.delta_desired_deg) - config.DELTA_MAX_DEG
            if angle_excess > metrics.TOL_DELTA_DEG:
                _record(breakdown, "steering_angle", angle_excess, fsm.state.value)
            # 조향 변화율(I1 하드 제약, |delta_0-delta_prev|<=10deg/step) 위반 크기 --
            # I1이 켜져 있고 MPC 경로일 때만 의미 있음(I1 꺼짐/line_follow는 이 제약
            # 자체가 없어 "위반"이라는 개념이 성립하지 않음). 같은 QP·같은 eps_abs이므로
            # 동일한 TOL_DELTA_DEG를 허용오차로 재사용한다.
            if lat.mode == "mpc" and mpc.enable_i1:
                rate_excess = (abs(lat.delta_desired_deg - delta_prev)
                               - config.DELTA_RATE_MAX_PER_STEP_DEG)
                if rate_excess > metrics.TOL_DELTA_DEG:
                    _record(breakdown, "steering_rate", rate_excess, fsm.state.value)
            # SETTINGS_DECISION.md §19 검증(제어 로직 아님): 고정 상수(TOL_DELTA_DEG)가
            # 아니라 이 스텝 자신의 실측 노름으로 구한 derived_tol_deg(가정 없음)와 비교.
            if lat.mpc_result is not None:
                max_derived_tol_deg = max(max_derived_tol_deg, lat.mpc_result.derived_tol_deg)
                if angle_excess > lat.mpc_result.derived_tol_deg:
                    steering_angle_violation_rigorous_count += 1
                if rate_excess > lat.mpc_result.derived_tol_deg:
                    steering_rate_violation_rigorous_count += 1

        v_cmd = longitudinal.compute_v_cmd(fsm.state)

        pp = postprocess.apply(delta_desired, delta_prev)
        if pp.rate_limit_active:
            rate_limit_count += 1
        if pp.clip_active:
            clip_count += 1
            clip_kind = metrics.classify_clip(pp.after_rate_deg)
            if clip_kind == "clip_numerical":
                clip_numerical_count += 1
            elif clip_kind == "clip_violation":
                clip_violation_count += 1
        delta_prev = pp.delta_final_deg

        delta_checked_count += 1
        if not metrics.delta_within_tolerance(delta_desired):
            delta_violation_count += 1
        if metrics.is_saturated(pp.delta_final_deg):
            saturation_steps[fsm.state.value] += 1

        delay_queue.append(pp.delta_final_deg)
        delta_to_vehicle = (delay_queue.pop(0) if len(delay_queue) > control_delay_steps
                             else 0.0)
        vehicle_new = vehicle_step(vehicle, delta_to_vehicle, v_cmd, config.DT)

        collided = collision.check_collision(vehicle_new, scenario.obstacles)

        psi_new_deg = vehicle_new.psi * _RAD2DEG
        if not metrics.psi_within_tolerance(psi_new_deg):
            psi_violation_count += 1
        # 헤딩(REQ-MPC-04 원래 범위 +-80deg) 위반 크기 -- I2'의 -20deg 하한은 I2 활성
        # 구간에서만 쓰는 QP 내부 보조 제약이고, "원래 제약" 판정은 항상 80deg 기준.
        # MEASURE_PLAN.md 허용오차(TOL_PSI_DEG=eps_abs 기준) 적용.
        heading_excess = abs(psi_new_deg) - config.PSI_LIMIT_DEG
        if heading_excess > metrics.TOL_PSI_DEG:
            _record(breakdown, "heading", heading_excess, fsm.state.value)

        y_ok = metrics.y_within_tolerance(vehicle_new.y, fsm.state)
        if y_ok is not None:
            y_checked_count += 1
            if not y_ok:
                y_violation_count += 1
                lo, hi = config.POSITION_CONSTRAINTS[fsm.state.value]
                excess = max(lo - vehicle_new.y, vehicle_new.y - hi, 0.0)
                y_max_abs_violation = max(y_max_abs_violation, excess)
                y_cumulative_violation += excess
                _record(breakdown, "lane", excess, fsm.state.value)

        # I2/I2' 장애물 여유 미달: 이번 step에 적용된 하한(있었다면)보다 실제 y/psi가
        # 못 미쳤는지(원래 REQ-MPC-04 범위 안에는 있어도 I2가 원하는 여유엔 못 미칠 수 있음)
        if lat.mpc_result is not None and lat.mpc_result.i2_active:
            if lat.mpc_result.i2_y_lower_bound is not None:
                y_deficit = max(0.0, lat.mpc_result.i2_y_lower_bound - vehicle_new.y)
                _record(breakdown, "i2_y_deficit", y_deficit, fsm.state.value)
            if lat.mpc_result.i2_psi_lower_bound is not None:
                psi_deficit_deg = max(0.0, lat.mpc_result.i2_psi_lower_bound * _RAD2DEG - psi_new_deg)
                _record(breakdown, "i2_psi_deficit", psi_deficit_deg, fsm.state.value)

        # I5(v2) 검토용 스텝별 상세 로그(DESIGN_IMPROVED_V2.md §1-3, 제어 로직 아님) --
        # 용량을 줄이기 위해 solver_status가 반복/시간 상한이거나, 원래 제약 중 하나라도
        # 허용오차를 넘긴 "주목할 만한" 스텝만 기록한다.
        if lat.mpc_result is not None:
            lane_excess_this_step = excess if (y_ok is not None and not y_ok) else 0.0
            notable_needed = (
                lat.mpc_result.solver_status in ("maximum iterations reached", "run time limit reached")
                or lat.mpc_result.time_limit_hit  # 2026-10-14: 다른 status로 보고된 절단도 남긴다
                or angle_excess > metrics.TOL_DELTA_DEG
                or rate_excess > metrics.TOL_DELTA_DEG
                or lane_excess_this_step > 0.0
                or heading_excess > metrics.TOL_PSI_DEG
            )
            if notable_needed:
                notable_step_log.append(dict(
                    step=step_idx, state=fsm.state.value,
                    solver_status=lat.mpc_result.solver_status,
                    iterations=lat.mpc_result.iterations,
                    time_limit_hit=lat.mpc_result.time_limit_hit,
                    approx_rejected=lat.mpc_result.approx_rejected,
                    fallback_used=lat.mpc_result.fallback_used,
                    warm_start_shift_used=lat.mpc_result.warm_start_shift_used,
                    angle_excess_deg=max(0.0, angle_excess),
                    rate_excess_deg=max(0.0, rate_excess),
                    lane_excess_m=lane_excess_this_step,
                    heading_excess_deg=max(0.0, heading_excess),
                ))

        logger.log(
            t=t, x=vehicle_new.x, y=vehicle_new.y, psi=vehicle_new.psi, v=vehicle_new.v,
            delta_mpc_raw=delta_desired, delta_after_rate=pp.delta_final_deg,
            delta_final=pp.delta_final_deg, v_cmd=v_cmd, state=fsm.state.value,
            front_gap=fg, left_clear=lc, right_clear=rc, ir_pattern=pattern, ey_line=ey,
            solver_status=(lat.mpc_result.solver_status if lat.mpc_result else "N/A"),
            fallback_used=(lat.mpc_result.fallback_used if lat.mpc_result else False),
            t_mpc_solve_ms=(lat.mpc_result.compute_time_ms if lat.mpc_result else 0.0),
            t_step_ms=0.0, rate_limit_active=pp.rate_limit_active, clip_active=pp.clip_active,
        )

        vehicle = vehicle_new

        if observing:
            if abs(vehicle.y) > 0.15:
                observed_settle_violation = True
            if observed_transition_departure:
                outcome = "관찰 중 상태 이탈"
                break
            if step_idx - observe_start >= config.OBSERVE_STEPS:
                outcome = "미정착" if observed_settle_violation else "성공"
                break
            continue

        if collided:
            outcome = "충돌"
            finish_step = step_idx
            break
        if fsm.state == FSMState.SAFE_STOP:
            outcome = "SAFE_STOP"
            finish_step = step_idx
            break
        if fsm.state == FSMState.KEEP_L2 and visited_evade and len(transitions) > 0 \
                and transitions[-1].to_state == FSMState.KEEP_L2.value \
                and transitions[-1].step == step_idx:
            finish_step = step_idx
            observing = True
            observe_start = step_idx
            continue
        if step_idx >= config.MAX_STEPS:
            outcome = "타임아웃"
            finish_step = None
            break

    if outcome is None:
        outcome = "타임아웃"

    return EpisodeResult(
        seed=scenario.seed, scenario_name=scenario.name, outcome=outcome,
        finish_step=finish_step, total_steps=step_idx, transitions=transitions,
        state_duration_steps=state_duration, solver_fail_count=solver_fail_count,
        fallback_count=fallback_count, warm_start_shift_count=warm_start_shift_count,
        max_iter_count=max_iter_count, max_iter_rejected_count=max_iter_rejected_count,
        time_limit_count=time_limit_count, time_limit_rejected_count=time_limit_rejected_count,
        rate_limit_count=rate_limit_count,
        clip_count=clip_count, clip_numerical_count=clip_numerical_count,
        clip_violation_count=clip_violation_count, delta_checked_count=delta_checked_count,
        delta_violation_count=delta_violation_count, psi_violation_count=psi_violation_count,
        y_checked_count=y_checked_count, y_violation_count=y_violation_count,
        y_max_abs_violation_m=y_max_abs_violation, y_cumulative_violation_m=y_cumulative_violation,
        saturation_steps=saturation_steps, mpc_solve_times_ms=mpc_times,
        observed_settle_violation=observed_settle_violation,
        observed_transition_departure=observed_transition_departure,
        violation_breakdown=breakdown, notable_step_log=notable_step_log,
        max_derived_tol_deg=max_derived_tol_deg,
        steering_angle_violation_rigorous_count=steering_angle_violation_rigorous_count,
        steering_rate_violation_rigorous_count=steering_rate_violation_rigorous_count,
        logger=logger,
    )
