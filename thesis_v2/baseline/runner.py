"""
에피소드 루프. 논문 제출 이후 작성.
스텝 순서: 센서 -> FSM -> 횡/종방향 제어 -> 후처리 -> 차량갱신 -> 충돌판정 -> 종료판정.
(repro/docs/DESIGN_BASELINE.md §2). REQ-SIM-04/05, §6(6분류, 2026-09-22 "관찰 중 상태
이탈" 추가).

**측정 정의 정정(2026-09-22, MEASURE_PLAN.md 참고)**: 이전 버전은 완료 후 관찰구간
(OBSERVE_STEPS)에서 FSM을 갱신하지 않았다(진단용 관찰이라는 이유). 이 동결이
REQ-SEN-01 front_gap 버그(지나친 장애물을 방향 구분 없이 0으로 계산)를 우연히 가려
100 에피소드 결과에 영향이 없는 것처럼 보이게 했다(`THESIS_REVISION_LOG.md` 2026-09-22
REQ-SEN-01). 실제 연속 주행을 재현하려면 관찰구간에도 FSM이 계속 갱신되어야 하므로,
이제 매 스텝 FSM을 갱신하고 관찰 중 상태 이탈을 별도로 분류한다. **제어기(FSM·MPC·속도
제어) 로직 자체는 바꾸지 않았다** -- 언제 갱신을 멈추는지(측정 하네스의 시점 정의)만
정정.

**S5 제어 지연(`control_delay_steps`, ROBUSTNESS_PLAN.md)**: postprocess 이후 최종
조향 명령이 차량 모델에 "반영되는 시점"만 지연시킨다(센서·FSM·MPC·후처리는 지연 없이
매 스텝 정상 수행). 기본값 0은 큐에 넣었다가 그 자리에서 바로 꺼내는 것과 같아 기존
경로와 완전히 동일하다(회귀 없음).
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional

from . import config, sensors, postprocess, longitudinal, collision, metrics
from .vehicle import VehicleState, initial_state, step as vehicle_step
from .fsm import FSM, FSMState, initial_fsm, step as fsm_step, SensorReadings
from .mpc import OSQPMPC
from .lateral import compute_lateral
from .world import Scenario
from .logger import StepLogger

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
    outcome: str  # 성공 | 충돌 | SAFE_STOP | 타임아웃 | 미정착 | 조기복귀 | 관찰 중 상태 이탈
    finish_step: Optional[int]
    total_steps: int
    transitions: List[Transition]
    state_duration_steps: dict
    solver_fail_count: int
    fallback_count: int
    rate_limit_count: int
    clip_count: int
    clip_numerical_count: int
    clip_violation_count: int
    delta_checked_count: int
    delta_violation_count: int
    psi_violation_count: int
    y_checked_count: int
    y_violation_count: int
    saturation_steps: dict  # state -> 포화 스텝 수 (분모는 state_duration_steps)
    mpc_solve_times_ms: List[float]
    observed_settle_violation: bool
    observed_transition_departure: bool  # 관찰구간 중 FSM이 KEEP_L2를 벗어났는지(2026-09-22)
    logger: StepLogger


def run_episode(scenario: Scenario, mpc: Optional[OSQPMPC] = None,
                 control_delay_steps: int = 0, noise_profile=None,
                 noise_rng=None) -> EpisodeResult:
    """control_delay_steps: S5(제어 지연, ROBUSTNESS_PLAN.md). 0(기본값)은 지연 없음과
    완전히 동일한 경로(회귀 없음).
    noise_profile/noise_rng: S4(센서 노이즈, ROBUSTNESS_PLAN.md). noise_profile=None(기본값)이면
    기존과 완전히 동일한 경로(회귀 없음). noise_profile을 주면 noise_rng(전용 스트림, world
    생성용 rng와 분리)도 함께 줘야 한다."""
    mpc = mpc if mpc is not None else OSQPMPC()
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    logger = StepLogger()
    transitions: List[Transition] = []
    state_duration = {s.value: 0 for s in FSMState}
    solver_fail_count = 0
    fallback_count = 0
    rate_limit_count = 0
    clip_count = 0
    clip_numerical_count = 0
    clip_violation_count = 0
    delta_checked_count = 0
    delta_violation_count = 0
    psi_violation_count = 0
    y_checked_count = 0
    y_violation_count = 0
    saturation_steps = {s.value: 0 for s in FSMState}
    mpc_times: List[float] = []
    visited_evade = False
    outcome = None
    finish_step = None
    observed_settle_violation = False
    observed_transition_departure = False
    delay_queue: List[float] = []

    step_idx = 0
    max_iter = config.MAX_STEPS + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None

    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT
        t_step_start_ns = _now_ns()

        # 1. 센서 (noise_profile=None이면 기존과 완전히 동일한 경로, S4 ROBUSTNESS_PLAN.md)
        if noise_profile is None:
            fg = sensors.front_gap(vehicle, scenario.obstacles)
            lc = sensors.left_clear(vehicle, scenario.obstacles)
            rc = sensors.right_clear(vehicle, scenario.obstacles)
            pattern = sensors.ir_pattern(vehicle)
            ey = sensors.ey_line(pattern)
        else:
            fg = sensors.front_gap_noisy(vehicle, scenario.obstacles, noise_rng,
                                          noise_profile.sigma_front_gap)
            lc = sensors.left_clear_noisy(vehicle, scenario.obstacles, noise_rng,
                                           noise_profile.flip_p)
            rc = sensors.right_clear_noisy(vehicle, scenario.obstacles, noise_rng,
                                            noise_profile.flip_p)
            pattern = sensors.ir_pattern(vehicle)
            ey = sensors.ey_line_noisy(sensors.ey_line(pattern), noise_rng, noise_profile.sigma_ey)

        # 2. FSM (관찰구간에서도 갱신 -- 2026-09-22 정정, 위 모듈 docstring 참고)
        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y,
                            vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append(Transition(step_idx, t, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
        fsm = fsm_new

        state_duration[fsm.state.value] += 1

        # 3. 횡방향 제어 (SAFE_STOP은 직전 최종 조향각 유지, REQ-LAT-05 §16)
        lat = compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc, delta_prev)
        delta_desired = lat.delta_desired_deg
        if lat.mpc_result is not None:
            mpc_times.append(lat.mpc_result.compute_time_ms)
            if not lat.mpc_result.ok:
                solver_fail_count += 1
            if lat.mpc_result.fallback_used:
                fallback_count += 1

        # 4. 종방향 제어
        v_cmd = longitudinal.compute_v_cmd(fsm.state)

        # 5. 후처리
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

        # 측정: REQ-MPC-04 제약 만족률(§18 eps_abs 허용오차, MEASURE_PLAN.md P트랙)
        delta_checked_count += 1
        if not metrics.delta_within_tolerance(delta_desired):
            delta_violation_count += 1
        if metrics.is_saturated(pp.delta_final_deg):
            saturation_steps[fsm.state.value] += 1

        # 6. 차량 갱신 (S5: control_delay_steps>0이면 차량에 반영되는 시점만 지연)
        delay_queue.append(pp.delta_final_deg)
        delta_to_vehicle = (delay_queue.pop(0) if len(delay_queue) > control_delay_steps
                             else 0.0)
        vehicle_new = vehicle_step(vehicle, delta_to_vehicle, v_cmd, config.DT)

        # 7. 충돌 판정 (차량 갱신 직후)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)

        # 측정: psi/y 제약 만족률(갱신 후 실제 상태 기준, §18)
        if not metrics.psi_within_tolerance(vehicle_new.psi * _RAD2DEG):
            psi_violation_count += 1
        y_ok = metrics.y_within_tolerance(vehicle_new.y, fsm.state)
        if y_ok is not None:
            y_checked_count += 1
            if not y_ok:
                y_violation_count += 1

        t_step_ms = (_now_ns() - t_step_start_ns) / 1e6

        logger.log(
            t=t, x=vehicle_new.x, y=vehicle_new.y, psi=vehicle_new.psi, v=vehicle_new.v,
            delta_mpc_raw=delta_desired, delta_after_rate=pp.delta_final_deg,
            delta_final=pp.delta_final_deg, v_cmd=v_cmd, state=fsm.state.value,
            front_gap=fg, left_clear=lc, right_clear=rc, ir_pattern=pattern, ey_line=ey,
            solver_status=(lat.mpc_result.solver_status if lat.mpc_result else "N/A"),
            fallback_used=(lat.mpc_result.fallback_used if lat.mpc_result else False),
            t_mpc_solve_ms=(lat.mpc_result.compute_time_ms if lat.mpc_result else 0.0),
            t_step_ms=t_step_ms, rate_limit_active=pp.rate_limit_active, clip_active=pp.clip_active,
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

        # 8. 종료 판정 (충돌 최우선)
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
        fallback_count=fallback_count, rate_limit_count=rate_limit_count,
        clip_count=clip_count, clip_numerical_count=clip_numerical_count,
        clip_violation_count=clip_violation_count, delta_checked_count=delta_checked_count,
        delta_violation_count=delta_violation_count, psi_violation_count=psi_violation_count,
        y_checked_count=y_checked_count, y_violation_count=y_violation_count,
        saturation_steps=saturation_steps, mpc_solve_times_ms=mpc_times,
        observed_settle_violation=observed_settle_violation,
        observed_transition_departure=observed_transition_departure, logger=logger,
    )


def _now_ns() -> int:
    import time
    return time.perf_counter_ns()
