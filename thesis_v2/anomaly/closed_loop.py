"""
폐루프(5단계) — DESIGN.md §13-6·§24. 탐지 결과가 실제로 제어를 바꾸는 유일한 지점.

`anomaly/runner.py`(관찰 전용, §3)의 루프를 베이스로 하되, 탐지기 호출 직후에 **정책 층**을 끼워 넣는다.
제어 모듈(FSM·MPC·lateral·postprocess·longitudinal·vehicle·collision)은 import만 하고 한 글자도 바꾸지 않는다 —
정책은 "그 모듈들에 들어가는 입력을 덮어쓰는" 방식으로만 개입한다(§3 원칙, §24).

정책:
  P0 없음 — 정책은 아무것도 하지 않는다(탐지기가 있어도 제어는 평소와 같다).
  P1 — 첫 경보(score>h) step에 그 즉시 v_cmd=0·직전 조향 유지로 덮어쓰고(그 step의 FSM·횡방향·종방향·후처리는
       건너뜀) 차량을 한 번 갱신한 뒤 에피소드를 끝낸다. 단 그 한 step으로 충돌·이탈이 나면 결과는 그쪽으로 분류.
  P2(A만) — 첫 경보 채널로 분기, 그 이후 에피소드 끝까지 유지: fg·trk·psi → P1과 같은 즉시 정지 /
       ey·ir_miss → ey=None 덮어씀 / rc → right_clear=False / lc → left_clear=False. 덮어쓴 값은 탐지기에는
       전달하지 않는다(탐지기는 계속 원래 주입된 값을 본다).

`policy="P0"`이면 이 루프는 `anomaly.runner.run_episode`와 **결과(outcome·total_steps·transitions·
first_alarm_step)가 완전히 같아야 한다**(golden, `tests/test_closed_loop.py`).
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from thesis_v2.baseline import config, postprocess, longitudinal, collision
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.baseline.vehicle import VehicleState, initial_state, step as vehicle_step
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.world import Scenario
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.lateral import compute_lateral

from . import config as an_config
from . import hybrid as hybrid_mod
from .common import new_out_dir, write_env, write_csv, read_csv_text, git_info
from .detector_a import DetectorA
from .detector_b import DetectorB, IFScorer, AEScorer, load_scorer
from .dev_detect import KINDS, LEFTOBS_KINDS, RUNS
from .faults import FaultInjector, FaultSpec, SensorFrame, sample_fault
from .features_b import Norm as NormB
from .runner import DetectorObs, DetectorOutput, Detector, Transition, vehicle_off_road
from .scenarios import generate_anomaly_scenario

import numpy as np

_RAD2DEG = 180.0 / math.pi

POLICIES = ("P0", "P1", "P2")
STOP_CHANNELS = ("fg", "trk", "psi")          # P2: 즉시 정지(P1과 같음)
OVERRIDE_EY_CHANNELS = ("ey", "ir_miss")       # P2: ey=None 덮어씀
OVERRIDE_RC_CHANNELS = ("rc",)                 # P2: right_clear=False
OVERRIDE_LC_CHANNELS = ("lc",)                 # P2: left_clear=False


@dataclass
class ClosedLoopResult:
    seed: int
    scenario_name: str
    outcome: str  # 충돌/이탈/탐지 정지/SAFE_STOP/성공/타임아웃(/미정착·관찰 중 상태 이탈 — §24 "기타 없음" 확인용)
    finish_step: Optional[int]
    total_steps: int
    transitions: List[Transition]
    fault: Optional[Dict[str, Any]]
    first_alarm_step: Optional[int]
    first_alarm_channel: Optional[str]
    policy_action: Optional[str]  # None | "stop" | "override_ey" | "override_rc" | "override_lc"
    # 진단 전용(§24-2): 실행 PC 부하에 따라 달라질 수 있는 값 — episodes CSV·--check 비교 대상이 아니다.
    mpc_time_limit_hits: int = 0
    mpc_max_solve_ms: float = 0.0


class _MPCTimingRecorder:
    """§24-2 진단: `mpc.solve()`를 그대로 호출하고 결과의 `time_limit_hit`·`compute_time_ms`만 집계한다
    (MPC의 입력·출력·설정은 건드리지 않는다 — compute_lateral은 solve()만 쓴다)."""

    def __init__(self, mpc: ImprovedMPC):
        self._mpc = mpc
        self.time_limit_hits = 0
        self.max_solve_ms = 0.0

    def solve(self, *args, **kwargs):
        res = self._mpc.solve(*args, **kwargs)
        if res.time_limit_hit:
            self.time_limit_hits += 1
        self.max_solve_ms = max(self.max_solve_ms, res.compute_time_ms)
        return res


def run_closed_loop_episode(scenario: Scenario, mpc: Optional[ImprovedMPC] = None,
                            fault: Optional[FaultSpec] = None, detector: Optional[Detector] = None,
                            policy: str = "P0",
                            noise_profile=None, noise_rng=None,
                            gyro_rng=None, sigma_gyro_deg: float = 0.0,
                            max_steps: int = config.MAX_STEPS,
                            terminate_on_departure: bool = False) -> ClosedLoopResult:
    assert policy in POLICIES
    if policy == "P2" and detector is None:
        raise ValueError("P2는 탐지기(A)가 필요하다")
    mpc = _MPCTimingRecorder(mpc if mpc is not None else ImprovedMPC(**an_config.V2_MPC_FLAGS))
    injector = FaultInjector(fault)
    if detector is not None:
        detector.reset()
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    transitions: List[Transition] = []
    visited_evade = False
    outcome = None
    finish_step = None
    observed_settle_violation = False
    observed_transition_departure = False
    first_alarm_step = None
    first_alarm_channel = None
    policy_action = None
    psi_prev = None

    # 정책 상태(한 번 정해지면 에피소드 끝까지 유지, §24)
    override_ey = False
    override_rc = False
    override_lc = False

    step_idx = 0
    max_iter = max_steps + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None

    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT

        # 1. 센서
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

        # 2. 고장 주입
        frame = injector.apply_sensors(step_idx, clean)
        fg, lc, rc = frame.front_gap, frame.left_clear, frame.right_clear
        pattern, ey, obstacle_info = frame.ir_pattern, frame.ey_line, frame.obstacle_info

        # 2b. 탐지기 전용 자이로
        yaw_rate_meas = None
        if psi_prev is not None:
            yaw_rate_meas = (vehicle.psi - psi_prev) / config.DT
            if gyro_rng is not None:
                yaw_rate_meas += gyro_rng.normal(0.0, math.radians(sigma_gyro_deg))
        psi_prev = vehicle.psi

        # 3. 탐지기 — **탐지기는 항상 주입된 원래 값(fg/lc/rc/ey)을 본다**(정책이 바꾼 값을 보지 않음, §24).
        det_out = None
        if detector is not None:
            det_out = detector.update(DetectorObs(
                step=step_idx, t=t, frame=frame, y=vehicle.y, psi=vehicle.psi, v=vehicle.v,
                fsm_state=fsm.state.value, delta_prev_cmd_deg=delta_prev,
                yaw_rate_meas=yaw_rate_meas))
            if det_out.alarm and first_alarm_step is None:
                first_alarm_step = step_idx
                first_alarm_channel = det_out.channel or None
                if policy == "P1":
                    policy_action = "stop"
                elif policy == "P2":
                    ch = first_alarm_channel
                    if ch in OVERRIDE_EY_CHANNELS:
                        override_ey = True
                        policy_action = "override_ey"
                    elif ch in OVERRIDE_RC_CHANNELS:
                        override_rc = True
                        policy_action = "override_rc"
                    elif ch in OVERRIDE_LC_CHANNELS:
                        override_lc = True
                        policy_action = "override_lc"
                    else:  # fg, trk, psi, 또는 그 외(기본값) — 즉시 정지
                        policy_action = "stop"

        # 즉시 정지(P1, 또는 P2의 fg·trk·psi): 이번 step에서 FSM·횡방향·종방향·후처리를 건너뛰고
        # v_cmd=0·직전 조향 유지로 차량을 한 번 갱신한 뒤 에피소드를 끝낸다.
        if policy_action == "stop":
            v_cmd = 0.0
            delta_to_vehicle = delta_prev
            vehicle_new = vehicle_step(vehicle, delta_to_vehicle, v_cmd, config.DT)
            collided = collision.check_collision(vehicle_new, scenario.obstacles)
            off_road = vehicle_off_road(vehicle_new)
            vehicle = vehicle_new
            if collided:
                outcome = "충돌"
            elif terminate_on_departure and off_road:
                outcome = "이탈"
            else:
                outcome = "탐지 정지"
            finish_step = step_idx
            break

        # 정책에 따른 제어 입력 덮어쓰기(지속 — §24 "그 이후 에피소드 끝까지 유지")
        ctrl_ey = None if override_ey else ey
        ctrl_rc = False if override_rc else rc
        ctrl_lc = False if override_lc else lc

        # 4. FSM
        fsm_new = fsm_step(fsm, SensorReadings(fg, ctrl_lc, ctrl_rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append(Transition(step_idx, t, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
        fsm = fsm_new

        # 5. 횡방향(v2 MPC) · 종방향 · 후처리
        lat = compute_lateral(fsm.state, ctrl_ey, vehicle.y, vehicle.psi, vehicle.v, mpc, delta_prev,
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

    return ClosedLoopResult(
        seed=scenario.seed, scenario_name=scenario.name, outcome=outcome, finish_step=finish_step,
        total_steps=step_idx, transitions=transitions, fault=(fault.to_dict() if fault else None),
        first_alarm_step=first_alarm_step, first_alarm_channel=first_alarm_channel,
        policy_action=policy_action,
        mpc_time_limit_hits=mpc.time_limit_hits, mpc_max_solve_ms=mpc.max_solve_ms)


# ---------------- 평가 하네스(§24) ----------------

OUTCOME_LIST = ["충돌", "이탈", "탐지 정지", "SAFE_STOP", "성공", "타임아웃"]
FAILURE_OUTCOMES = {"충돌", "이탈"}
HARMFUL_KINDS = {"lidar_freeze", "lidar_dropout", "ir_stuck", "steer_delay", "steer_stuck", "left_clear_stuck"}
HARMLESS_KINDS = {"lidar_spike", "ir_dropout", "right_clear_stuck"}  # §19-2
COMBO_NAMES = ["P0", "P1_A", "P1_B1", "P1_B2", "P1_HYBRID", "P2_A"]  # §24 "6개 실행 조합"
HEADER = ["run", "seed", "outcome", "total_steps", "finish_step", "onset", "duration",
          "first_alarm_step", "first_alarm_channel", "policy_action", "unnecessary_stop"]
# §24-2: 실행 PC 부하에 따라 달라질 수 있는 진단값 — episodes CSV와 분리, --check 비교 대상 아님.
DIAG_FILE = "diag_timing.csv"
DIAG_HEADER = ["combo", "run", "seed", "time_limit_hits", "max_solve_ms"]
EVAL_FREEZE_TAG = "anomaly-cl-freeze"


def run_closed_loop_from_seed(run: str, seed: int, policy: str, detector,
                              sigma_gyro_deg: float = an_config.SIGMA_GYRO_DEG) -> ClosedLoopResult:
    """common.run_anomaly_episode와 같은 시나리오·고장·노이즈 생성(§10·§13) — run_closed_loop_episode로 실행."""
    kind = None if run.startswith("none") else run
    left = run == "none_leftobs" or run in LEFTOBS_KINDS
    sc = generate_anomaly_scenario(seed, left_obstacle=left)
    spec = None if kind is None else sample_fault(kind, sc)
    profile = base_sensors.NOISE_PROFILES[an_config.NORMAL_NOISE_PROFILE]
    return run_closed_loop_episode(
        sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), fault=spec, detector=detector, policy=policy,
        noise_profile=profile, noise_rng=np.random.default_rng((seed, an_config.NOISE_STREAM_ID)),
        gyro_rng=np.random.default_rng((seed, an_config.GYRO_STREAM_ID)), sigma_gyro_deg=sigma_gyro_deg,
        max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)


def build_detector(name: str, h_by_detector: Dict[str, float], model_dirs: dict):
    if name == "P0":
        return None
    if name in ("P1_A", "P2_A"):
        return DetectorA(threshold=h_by_detector["A"])
    if name == "P1_B1":
        b_dir = Path(model_dirs["B"])
        return DetectorB(IFScorer.load(b_dir), NormB.from_json(b_dir / "norm.json"), threshold=h_by_detector["B1"])
    if name == "P1_B2":
        b_dir = Path(model_dirs["B"])
        return DetectorB(AEScorer.load(b_dir), NormB.from_json(b_dir / "norm.json"), threshold=h_by_detector["B2"])
    if name == "P1_HYBRID":
        hy_dir = Path(model_dirs["HYBRID"])
        return hybrid_mod.DetectorHybrid(IFScorer.load(hy_dir), hybrid_mod.Norm.from_json(hy_dir / "norm.json"),
                                        threshold=h_by_detector["HYBRID"])
    raise AssertionError(name)


def policy_of(name: str) -> str:
    return {"P0": "P0", "P1_A": "P1", "P1_B1": "P1", "P1_B2": "P1", "P1_HYBRID": "P1", "P2_A": "P2"}[name]


def episode_row(res: ClosedLoopResult, run: str, seed: int) -> dict:
    f = res.fault
    onset = f["onset_step"] if f else None
    duration = f["duration_steps"] if f else None
    is_normal = run in ("none", "none_leftobs")
    unnecessary_stop = None
    if res.outcome == "탐지 정지":
        if is_normal:
            unnecessary_stop = "normal"
        elif run in HARMLESS_KINDS:
            unnecessary_stop = "harmless"
        elif onset is not None and res.first_alarm_step is not None and res.first_alarm_step < onset:
            unnecessary_stop = "before_onset"
        # 유해 고장 onset 이후 정지는 §24대로 "불필요"가 아니다 — None으로 둔다.
    return dict(run=run, seed=seed, outcome=res.outcome, total_steps=res.total_steps,
               finish_step=res.finish_step, onset=onset, duration=duration,
               first_alarm_step=res.first_alarm_step, first_alarm_channel=res.first_alarm_channel,
               policy_action=res.policy_action, unnecessary_stop=unnecessary_stop)


def diag_row(res: ClosedLoopResult, name: str, run: str, seed: int) -> dict:
    return dict(combo=name, run=run, seed=seed, time_limit_hits=res.mpc_time_limit_hits,
                max_solve_ms=round(res.mpc_max_solve_ms, 3))


def compute(seeds: List[int], h_by_detector: Dict[str, float], model_dirs: dict,
            combos: Optional[List[str]] = None) -> "tuple[Dict[str, List[dict]], List[dict]]":
    """반환: (조합별 episodes 행, 진단 행). 진단 행은 §24-2대로 --check 비교 대상이 아니다.
    combos: 계산할 조합(COMBO_NAMES 순서로 실행). None이면 전체. 조합끼리는 상태를 공유하지 않는다
    (조합마다 탐지기, 에피소드마다 MPC를 새로 만든다) — 일부만 계산해도 그 조합의 값은 전체 실행과 같다."""
    names = COMBO_NAMES if combos is None else [n for n in COMBO_NAMES if n in combos]
    rows = {}
    diag = []
    for name in names:
        det = build_detector(name, h_by_detector, model_dirs)
        policy = policy_of(name)
        rs = []
        for run in RUNS:
            for s in seeds:
                res = run_closed_loop_from_seed(run, s, policy, det)
                rs.append(episode_row(res, run, s))
                diag.append(diag_row(res, name, run, s))
        rows[name] = rs
    return rows, diag


def summarize_timing(diag: List[dict]) -> dict:
    """§24-2: time_limit_hit 총합과 발동 에피소드 목록, 전체 최대 solve 시간(ms). summary.json에 넣지 않는다."""
    hit_eps = [dict(combo=d["combo"], run=d["run"], seed=d["seed"], time_limit_hits=d["time_limit_hits"])
               for d in diag if d["time_limit_hits"] > 0]
    return dict(time_limit_hit_total=sum(d["time_limit_hits"] for d in diag),
                time_limit_hit_episodes=hit_eps,
                max_solve_ms=max((d["max_solve_ms"] for d in diag), default=None))


def print_timing(timing: dict) -> None:
    print(f"[진단] MPC time_limit_hit 총합 {timing['time_limit_hit_total']}, "
          f"최대 solve {timing['max_solve_ms']} ms (비교 대상 아님, §24-2)")
    for e in timing["time_limit_hit_episodes"]:
        print(f"  !!time_limit_hit: {e['combo']} {e['run']} seed={e['seed']} ({e['time_limit_hits']}회)")


def wilson(k: int, n: int) -> Optional[list]:
    ci = wilson_ci(k, n)
    return [ci["lo"], ci["hi"]] if ci else None


def summarize(rows: Dict[str, List[dict]], baseline_rows: Optional[List[dict]] = None) -> dict:
    """baseline_rows: P0 대비 비교의 기준 행. None이면 rows["P0"](평가 실행은 항상 이쪽)."""
    out = {}
    baseline = {(r["run"], r["seed"]): r["outcome"]
                for r in (rows["P0"] if baseline_rows is None else baseline_rows)}
    for name, rs in rows.items():
        n = len(rs)
        outcome_counts = {o: sum(r["outcome"] == o for r in rs) for o in OUTCOME_LIST}
        unexpected = sorted(set(r["outcome"] for r in rs if r["outcome"] not in OUTCOME_LIST))
        collisions = outcome_counts["충돌"]
        completed = outcome_counts["성공"] + outcome_counts["SAFE_STOP"]
        unnecessary = {k: sum(r["unnecessary_stop"] == k for r in rs) for k in ("normal", "harmless", "before_onset")}
        collisions_p0 = sum(baseline[(r["run"], r["seed"])] == "충돌" for r in rs)
        completed_p0 = sum(baseline[(r["run"], r["seed"])] in ("성공", "SAFE_STOP") for r in rs)
        per_kind = {}
        for kind in KINDS:
            krs = [r for r in rs if r["run"] == kind]
            per_kind[kind] = dict(n=len(krs), outcome_counts={o: sum(r["outcome"] == o for r in krs)
                                                               for o in OUTCOME_LIST})
        out[name] = dict(
            n=n, outcome_counts=outcome_counts, unexpected_outcomes=unexpected,
            collisions=collisions, collisions_ci95=wilson(collisions, n),
            completion_rate=(completed / n if n else None),
            unnecessary_stops=dict(**unnecessary, total=sum(unnecessary.values())),
            vs_p0=dict(collisions_p0=collisions_p0, collision_delta=collisions - collisions_p0,
                      completed_p0=completed_p0, completion_delta=completed - completed_p0),
            per_kind=per_kind)
    return out


# ---------------- CLI ----------------

def freeze_ok(info: dict) -> "tuple[bool, str]":
    if info.get("dirty"):
        return False, "git 작업 트리가 dirty함(커밋되지 않은 변경 있음) — 평가 전 커밋 필요"
    if info.get("tag") != EVAL_FREEZE_TAG:
        return False, f"HEAD에 '{EVAL_FREEZE_TAG}' 태그 없음(현재 태그: {info.get('tag')!r}) — 커밋 후 태그 필요"
    return True, "ok"


def _load_thresholds(args) -> "tuple[dict, dict, dict]":
    a_thr = json.loads((Path(args.a_thresholds) / "thresholds.json").read_text(encoding="utf-8"))
    b_thr = json.loads((Path(args.b_thresholds) / "thresholds_b.json").read_text(encoding="utf-8"))
    hy_thr = json.loads((Path(args.hybrid_thresholds) / "thresholds_hybrid.json").read_text(encoding="utf-8"))
    assert a_thr["sigma_gyro_deg"] == an_config.SIGMA_GYRO_DEG == b_thr["sigma_gyro_deg"] == hy_thr["sigma_gyro_deg"]
    h_by_detector = {"A": a_thr["h"], "B1": b_thr["detectors"]["B1"]["h"], "B2": b_thr["detectors"]["B2"]["h"],
                     "HYBRID": hy_thr["h"]}
    model_dirs = {"B": b_thr["model_dir"], "HYBRID": hy_thr["model_dir"]}
    thr_paths = dict(A=str(args.a_thresholds), B=str(args.b_thresholds), HYBRID=str(args.hybrid_thresholds))
    return h_by_detector, model_dirs, thr_paths


def _run_and_save(seeds_mode: str, seeds: list, h_by_detector: dict, model_dirs: dict, thr_paths: dict,
                  out_root: str) -> "tuple[Path, List[dict]]":
    rows, diag = compute(seeds, h_by_detector, model_dirs)
    summary = summarize(rows)
    out = new_out_dir(out_root, f"it{an_config.ITERATION}_closed_loop_{seeds_mode}")
    for name in COMBO_NAMES:
        write_csv(out / f"episodes_{name}.csv", HEADER, rows[name])
    write_csv(out / DIAG_FILE, DIAG_HEADER, diag)
    meta = dict(purpose="폐루프 평가(DESIGN.md §13-6·§24)" + ("" if seeds_mode == "eval" else " — dev 대역 테스트, 보고서 수치 아님"),
               seeds_mode=seeds_mode, seeds=[seeds[0], seeds[-1]], iteration=an_config.ITERATION,
               threshold_dirs=thr_paths, model_dirs=model_dirs, h_by_detector=h_by_detector,
               combos=COMBO_NAMES)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_env(out, dict(purpose=meta["purpose"]))
    return out, diag


def _print_summary(summary: dict) -> None:
    for name in COMBO_NAMES:
        s = summary[name]
        print(f"[{name}] n={s['n']} 충돌 {s['collisions']}(P0대비 {s['vs_p0']['collision_delta']:+d}) "
              f"완료율 {s['completion_rate']:.3f}(P0대비 델타 {s['vs_p0']['completion_delta']:+d}건) "
              f"불필요정지 {s['unnecessary_stops']['total']} {s['unnecessary_stops']} "
              f"결과분포 {s['outcome_counts']}"
              + (f"  !!예상 밖 결과:{s['unexpected_outcomes']}" if s['unexpected_outcomes'] else ""))


def diff_csv_text(saved: str, recomputed: str) -> List[str]:
    """§24-2: 두 CSV 텍스트의 차이를 "행 번호(헤더 제외 1부터)·열 이름·저장본 vs 재계산" 문장 목록으로 돌려준다."""
    import csv as _csv
    a = list(_csv.reader(saved.splitlines()))
    b = list(_csv.reader(recomputed.splitlines()))
    lines = []
    if not a or not b:
        return [f"빈 파일(저장본 {len(a)}줄, 재계산 {len(b)}줄)"]
    if a[0] != b[0]:
        lines.append(f"헤더 다름: 저장본 {a[0]} vs 재계산 {b[0]}")
        return lines
    header = a[0]
    if len(a) != len(b):
        lines.append(f"행 수 다름: 저장본 {len(a) - 1} vs 재계산 {len(b) - 1}")
    key_cols = [header.index(k) for k in ("run", "seed") if k in header]
    for i, (ra, rb) in enumerate(zip(a[1:], b[1:]), start=1):
        if ra == rb:
            continue
        key = " ".join(f"{header[c]}={ra[c] if c < len(ra) else '?'}" for c in key_cols)
        for c, col in enumerate(header):
            va = ra[c] if c < len(ra) else "<없음>"
            vb = rb[c] if c < len(rb) else "<없음>"
            if va != vb:
                lines.append(f"행 {i} ({key}) 열 {col}: 저장본 {va!r} vs 재계산 {vb!r}")
    return lines


def parse_check_only(text: Optional[str]) -> Optional[List[str]]:
    """--check-only "P0,P2_A" → ["P0", "P2_A"](COMBO_NAMES 순서). None이면 전체(None)."""
    if text is None:
        return None
    names = [s.strip() for s in text.split(",") if s.strip()]
    bad = [n for n in names if n not in COMBO_NAMES]
    if not names or bad:
        raise ValueError(f"--check-only: 알 수 없는 조합 {bad or text!r} (가능: {','.join(COMBO_NAMES)})")
    return [n for n in COMBO_NAMES if n in names]


def _check(path: Path, combos: Optional[List[str]] = None) -> None:
    """저장된 결과를 재계산해 episodes_*.csv·summary.json을 비교한다. 불일치하면 재계산 임시 파일(_check_*)을
    남기고 차이(행·열·값)를 출력한다(§24-2). diag_timing.csv는 비교하지 않고, 재계산의 진단값은
    `_check_diag_timing.csv`로 항상 남긴다(덮어씀).

    combos(--check-only, §24-2 "부분 확인"): 지정한 조합만 재계산해 그 조합의 episodes CSV와 summary.json의 그
    조합 항목만 비교한다. P0를 고르지 않았으면 P0 대비 비교(vs_p0)의 기준은 **저장본** episodes_P0.csv다.
    부분 확인은 동결 전 전체 --check를 대신하지 않는다."""
    partial = combos is not None and list(combos) != COMBO_NAMES
    names = COMBO_NAMES if combos is None else list(combos)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    seeds = list(range(meta["seeds"][0], meta["seeds"][1] + 1))
    rows, diag = compute(seeds, meta["h_by_detector"], meta["model_dirs"], combos=names)
    baseline_rows = None
    if "P0" not in rows:
        import csv as _csv
        with open(path / "episodes_P0.csv", encoding="utf-8", newline="") as f:
            baseline_rows = [dict(r, seed=int(r["seed"])) for r in _csv.DictReader(f)]
        print("  (P0 미선택 — P0 대비 비교의 기준은 저장본 episodes_P0.csv)")
    summary = summarize(rows, baseline_rows=baseline_rows)
    write_csv(path / f"_check_{DIAG_FILE}", DIAG_HEADER, diag)
    if partial:
        print(f"  부분 확인: {','.join(names)} (전체 --check를 대신하지 않음, §24-2)")
    ok = True
    for name in names:
        tmp = path / f"_check_episodes_{name}.csv"
        write_csv(tmp, HEADER, rows[name])
        saved = read_csv_text(path / f"episodes_{name}.csv")
        recomputed = read_csv_text(tmp)
        same = recomputed == saved
        print(f"  episodes_{name}.csv: {'일치' if same else '불일치'}")
        if same:
            tmp.unlink()
        else:
            for line in diff_csv_text(saved, recomputed):
                print(f"    {line}")
            print(f"    (재계산본 보존: {tmp})")
        ok = ok and same
    summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
    saved_summary_text = (path / "summary.json").read_text(encoding="utf-8")
    if partial:
        # 부분 확인: 저장본 summary.json의 해당 조합 항목만 비교(값 비교 — float는 json 왕복으로 정확히 복원된다).
        saved_summary = json.loads(saved_summary_text)
        diffs = [n for n in names if json.loads(json.dumps(summary[n], ensure_ascii=False)) != saved_summary.get(n)]
        same_summary = not diffs
        print(f"  summary.json[{','.join(names)}]: {'일치' if same_summary else '불일치 ' + ','.join(diffs)}")
    else:
        same_summary = summary_text == saved_summary_text
        print(f"  summary.json: {'일치' if same_summary else '불일치'}")
    if not same_summary:
        tmp = path / "_check_summary.json"
        tmp.write_text(summary_text, encoding="utf-8")
        print(f"    (재계산본 보존: {tmp})")
    ok = ok and same_summary
    print_timing(summarize_timing(diag))
    if partial:
        print(f"--check {path} (부분 확인 {','.join(names)}): {'선택 조합 일치' if ok else '불일치 있음'}")
    else:
        print(f"--check {path}: {'전체 일치' if ok else '불일치 있음'}")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", choices=["dev", "eval"], default="dev")
    ap.add_argument("--a-thresholds")
    ap.add_argument("--b-thresholds")
    ap.add_argument("--hybrid-thresholds")
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--check", default=None)
    ap.add_argument("--check-only", default=None,
                    help="--check와 함께: 비교할 조합(쉼표 구분, 예: P0,P2_A). 생략하면 전체. 부분 확인은 전체 --check를 대신하지 않음(§24-2)")
    args = ap.parse_args()

    if args.check_only is not None and not args.check:
        ap.error("--check-only는 --check와 함께만 쓴다")
    if args.check:
        try:
            combos = parse_check_only(args.check_only)
        except ValueError as e:
            ap.error(str(e))
        _check(Path(args.check), combos=combos)
        return

    if args.seeds == "eval":
        ok, reason = freeze_ok(git_info())
        if not ok:
            print(f"거부: --seeds eval은 '{EVAL_FREEZE_TAG}' 태그가 붙은 깨끗한 커밋에서만 실행한다 — {reason}",
                  file=sys.stderr)
            sys.exit(1)

    seeds = list(an_config.SEEDS_FAULT_DEV if args.seeds == "dev" else an_config.SEEDS_CLOSED_LOOP)
    h_by_detector, model_dirs, thr_paths = _load_thresholds(args)
    out, diag = _run_and_save(args.seeds, seeds, h_by_detector, model_dirs, thr_paths, args.out_root)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    _print_summary(summary)
    print_timing(summarize_timing(diag))
    print("saved:", out)


if __name__ == "__main__":
    main()
