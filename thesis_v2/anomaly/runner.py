"""
이상탐지 확장용 에피소드 루프 (DESIGN.md §3).

improved/runner.py(v2 루프)와 **제어 관련 순서·호출이 같다**:
센서(+S4 노이즈) → **[고장 주입]** → **[탐지기: 관찰 전용]** → FSM → 횡방향(v2 MPC) → 종방향 →
후처리 → **[액추에이터 고장]** → 차량 갱신 → 충돌 판정 → (선택) 이탈 판정 → 종료 판정.

- 제어 모듈(FSM·MPC·lateral·postprocess·longitudinal·vehicle·collision)은 import만 하고 수정하지 않는다.
- improved/runner.py의 제약 위반 집계·notable 로그 등 측정 전용 부분은 제어에 영향이 없어 생략했다.
- 고장·탐지기 없음 + terminate_on_departure=False + max_steps=200이면 improved.runner.run_episode와
  스텝 로그·결과가 완전히 같아야 한다(golden: anomaly/tests/test_golden_equivalence.py).
- 탐지기는 관측값을 읽기만 한다. 탐지 결과로 제어를 바꾸는 대응 정책은 5단계에서 추가한다.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from thesis_v2.baseline import config, postprocess, longitudinal, collision
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.vehicle import VehicleState, initial_state, step as vehicle_step
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.world import Scenario
from thesis_v2.baseline.logger import StepLogger
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.lateral import compute_lateral

from . import config as an_config
from .faults import FaultInjector, FaultSpec, SensorFrame

_RAD2DEG = 180.0 / math.pi


@dataclass(frozen=True)
class DetectorObs:
    """탐지기가 step k에 받는 값 = 제어기가 받는 값(고장 주입 후) + 차량 자기 상태 + 직전 명령.
    시뮬레이터 내부(장애물 좌표·고장 라벨·정상값)는 넣지 않는다."""
    step: int
    t: float
    frame: SensorFrame
    y: float
    psi: float
    v: float
    fsm_state: str          # 직전 step 종료 시점 FSM 상태(이번 step FSM 갱신 전)
    delta_prev_cmd_deg: float  # 직전 step 후처리 최종 조향 명령(차량 반영 전)
    # 탐지기 전용 자이로(DESIGN.md §13-2): (psi_k - psi_{k-1})/dt + 노이즈. k=1이면 None. 제어기 입력 아님.
    yaw_rate_meas: Optional[float] = None


@dataclass
class DetectorOutput:
    score: float
    alarm: bool
    channel: str = ""       # 어느 잔차/센서에서 경보가 났는지(탐지기 A만 의미 있음)
    channel_scores: Optional[Dict[str, float]] = None  # 채널별 현재 점수(탐지기 A)
    residuals: Optional[Dict[str, Optional[float]]] = None  # 채널별 이번 step 잔차(마스크면 None)


class Detector(Protocol):
    def reset(self) -> None: ...
    def update(self, obs: DetectorObs) -> DetectorOutput: ...


@dataclass
class Transition:
    step: int
    t: float
    from_state: str
    to_state: str


@dataclass
class AnomalyEpisodeResult:
    seed: int
    scenario_name: str
    outcome: str  # improved와 같은 분류 + "이탈"(terminate_on_departure=True일 때)
    finish_step: Optional[int]
    total_steps: int
    transitions: List[Transition]
    fault: Optional[Dict[str, Any]]
    first_alarm_step: Optional[int]
    departed: bool
    logger: StepLogger                     # improved와 같은 스키마(golden 비교용)
    alog: List[Dict[str, Any]] = field(default_factory=list)  # 이상탐지용 스텝 기록


def vehicle_off_road(state: VehicleState, mode: str = None) -> bool:
    """D5: 도로 [y_lo, y_hi] 밖이면 이탈. mode="corner"(네 모서리 중 하나) | "center"(차체 기하 중심).
    기본값은 config.DEPARTURE_MODE."""
    mode = mode or an_config.DEPARTURE_MODE
    lo, hi = an_config.ROAD_Y_RANGE
    if mode == "corner":
        corners = collision._vehicle_corners(state)
        return any(cy < lo or cy > hi for _, cy in corners)
    if mode == "center":
        cy = state.y + 0.5 * config.L * math.sin(state.psi)
        return cy < lo or cy > hi
    raise ValueError(mode)


def run_episode(scenario: Scenario, mpc: Optional[ImprovedMPC] = None,
                fault: Optional[FaultSpec] = None, detector: Optional[Detector] = None,
                noise_profile=None, noise_rng=None,
                gyro_rng=None, sigma_gyro_deg: float = 0.0,
                max_steps: int = config.MAX_STEPS,
                terminate_on_departure: bool = False,
                record_alog: bool = True) -> AnomalyEpisodeResult:
    mpc = mpc if mpc is not None else ImprovedMPC(**an_config.V2_MPC_FLAGS)
    injector = FaultInjector(fault)
    if detector is not None:
        detector.reset()
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    logger = StepLogger()
    alog: List[Dict[str, Any]] = []
    transitions: List[Transition] = []
    visited_evade = False
    outcome = None
    finish_step = None
    observed_settle_violation = False
    observed_transition_departure = False
    first_alarm_step = None
    departed = False
    psi_prev = None  # 자이로용 직전 step 시작 시점 psi

    step_idx = 0
    max_iter = max_steps + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None

    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT

        # 1. 센서 (improved/runner.py와 같은 호출 순서 — 노이즈 rng 소비 순서 유지)
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
        clean = SensorFrame(fg, lc, rc, pattern, ey, obstacle_info)

        # 2. 고장 주입 (spec 없음 또는 비활성 step이면 항등)
        frame = injector.apply_sensors(step_idx, clean)
        fg, lc, rc = frame.front_gap, frame.left_clear, frame.right_clear
        pattern, ey, obstacle_info = frame.ir_pattern, frame.ey_line, frame.obstacle_info

        # 2b. 탐지기 전용 자이로 (별도 난수 스트림 — 제어 경로의 난수 소비를 바꾸지 않는다)
        yaw_rate_meas = None
        if psi_prev is not None:
            yaw_rate_meas = (vehicle.psi - psi_prev) / config.DT
            if gyro_rng is not None:
                yaw_rate_meas += gyro_rng.normal(0.0, math.radians(sigma_gyro_deg))
        psi_prev = vehicle.psi

        # 3. 탐지기 (관찰 전용 — 반환값은 기록만 하고 제어에 쓰지 않는다)
        det_out = None
        if detector is not None:
            det_out = detector.update(DetectorObs(
                step=step_idx, t=t, frame=frame, y=vehicle.y, psi=vehicle.psi, v=vehicle.v,
                fsm_state=fsm.state.value, delta_prev_cmd_deg=delta_prev,
                yaw_rate_meas=yaw_rate_meas))
            if det_out.alarm and first_alarm_step is None:
                first_alarm_step = step_idx

        # 4. FSM
        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append(Transition(step_idx, t, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
        fsm = fsm_new

        # 5. 횡방향(v2 MPC) · 종방향 · 후처리
        lat = compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc, delta_prev,
                              obstacle_info=obstacle_info)
        delta_desired = lat.delta_desired_deg
        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(delta_desired, delta_prev)
        delta_prev = pp.delta_final_deg

        # 6. 액추에이터 고장 → 차량 갱신 → 충돌
        delta_to_vehicle = injector.apply_actuator(step_idx, pp.delta_final_deg)
        vehicle_new = vehicle_step(vehicle, delta_to_vehicle, v_cmd, config.DT)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)
        off_road = vehicle_off_road(vehicle_new)
        departed = departed or off_road

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
        if record_alog:
            alog.append(dict(
                step=step_idx, label=injector.label(step_idx),
                effective=int(frame != clean or delta_to_vehicle != pp.delta_final_deg),
                # 탐지기가 본 값(= 주입 후 센서, step 시작 시 차량 상태)
                front_gap=fg, left_clear=lc, right_clear=rc,
                ir_pattern="".join(map(str, pattern)), ey_line=ey,
                obs_gap_near=(obstacle_info.gap_near if obstacle_info else None),
                obs_gap_far=(obstacle_info.gap_far if obstacle_info else None),
                obs_y_lo=(obstacle_info.y_lo if obstacle_info else None),
                obs_y_hi=(obstacle_info.y_hi if obstacle_info else None),
                y=vehicle.y, psi=vehicle.psi, v=vehicle.v, yaw_rate_meas=yaw_rate_meas,
                # 정상값(분석·라벨 검증용 — 탐지기 입력으로 쓰지 않음)
                clean_front_gap=clean.front_gap, clean_right_clear=clean.right_clear,
                clean_left_clear=clean.left_clear, clean_ey_line=clean.ey_line,
                # 제어 결과
                fsm_state=fsm.state.value, delta_cmd=pp.delta_final_deg,
                delta_applied=delta_to_vehicle, v_cmd=v_cmd,
                det_score=(det_out.score if det_out else None),
                det_alarm=(bool(det_out.alarm) if det_out else None),
                det_channel=(det_out.channel if det_out else None),
                det_channel_scores=(det_out.channel_scores if det_out else None),
                det_residuals=(det_out.residuals if det_out else None),
            ))

        vehicle = vehicle_new

        if observing:
            if abs(vehicle.y) > 0.15:
                observed_settle_violation = True
            if observed_transition_departure:
                outcome = "관찰 중 상태 이탈"
                break
            if terminate_on_departure and off_road:
                outcome = "이탈"
                break
            if step_idx - observe_start >= config.OBSERVE_STEPS:
                outcome = "미정착" if observed_settle_violation else "성공"
                break
            continue

        if collided:
            outcome = "충돌"
            finish_step = step_idx
            break
        if terminate_on_departure and off_road:
            outcome = "이탈"
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
        if step_idx >= max_steps:
            outcome = "타임아웃"
            finish_step = None
            break

    if outcome is None:
        outcome = "타임아웃"

    return AnomalyEpisodeResult(
        seed=scenario.seed, scenario_name=scenario.name, outcome=outcome,
        finish_step=finish_step, total_steps=step_idx, transitions=transitions,
        fault=(fault.to_dict() if fault else None), first_alarm_step=first_alarm_step,
        departed=departed, logger=logger, alog=alog)
