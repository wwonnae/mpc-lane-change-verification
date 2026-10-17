"""
I4 폐루프 평가(DESIGN_I4 §3-2, 개정 1). Student가 실제로 조향한다: improved/runner.py(동결,
미수정)의 스텝 순서를 그대로 복제하되, MPC가 호출될 자리(compute_lateral의 mode=="mpc")에서만
δ를 Student 출력으로 바꾼다. 라인추종·SAFE_STOP hold_last·FSM·후처리(rate limit+clip)·종방향
규칙 기반 속도·충돌 판정은 그대로다(v_target 출력은 쓰지 않음, 핵심 주장 2 유지). 제어기
입력은 센서 모델 출력과 차량 상태뿐이다.

`--policy mpc`는 같은 루프를 v2 MPC로 돌리는 동등성 확인용(improved.runner와 결과가 같아야 함).

단계(개정 1): 1차 --track paper(eval seed 200~299), 1차에 문제없을 때만 2차 --track s3(eval 격자).
사용(저장소 루트): python -m thesis_v2.improved.student_i4.closed_loop --run-dir <run> --track paper
"""
import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from thesis_v2.baseline import config, postprocess, longitudinal, collision, metrics
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.baseline.vehicle import initial_state, step as vehicle_step
from thesis_v2.baseline.world import generate_scenario, generate_grid_scenario
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.lateral import compute_lateral as improved_compute_lateral
from thesis_v2.improved.mpc import ImprovedMPC

from . import config as i4_config
from .features import build_feature_vector
from .model import Predictor

_RAD2DEG = 180.0 / math.pi


class StudentLateral:
    """MPC 자리에만 Student δ를 넣는다. 선택 로직은 lateral.compute_lateral과 같게 하기 위해
    compute_lateral을 그대로 부르고, MPC 인자 자리에 이 객체의 solve 대체물을 넘긴다."""

    def __init__(self, predictor: Predictor):
        self.pred = predictor
        self.enable_i1 = False  # runner의 rate 위반 판정 분기용 속성(Student는 QP 제약 없음)
        self._ctx = None

    def set_context(self, v, ey, y, fg, lc):
        self._ctx = (v, ey, y, fg, lc)

    def solve(self, y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0, obstacle_info=None):
        v, ey, y, fg, lc = self._ctx
        x = self.pred.build(v, ey, y, state_name, fg, lc, psi0_rad * 180.0 / math.pi, delta_prev_deg)
        t0 = time.perf_counter()
        d = float(self.pred.predict(x)[0])
        return _StudentResult(delta_deg=d, compute_time_ms=(time.perf_counter() - t0) * 1000.0)


class _StudentResult:
    def __init__(self, delta_deg, compute_time_ms):
        self.delta_deg = delta_deg
        self.compute_time_ms = compute_time_ms


def run_episode(scenario, controller, is_student: bool):
    """improved/runner.py run_episode와 같은 스텝 순서(노이즈·지연 없음 경로)."""
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    transitions = []
    state_duration = {s.value: 0 for s in FSMState}
    visited_evade = False
    outcome, finish_step = None, None
    observing, observe_start = False, None
    observed_settle_violation = False
    observed_transition_departure = False
    n_policy_calls = rate_limit_count = clip_count = clip_violation_count = 0
    nonfinite_delta = 0
    y_checked = y_viol = psi_viol = 0
    y_max_abs_violation = 0.0
    policy_ms = []
    traj = []
    step_idx = 0
    max_iter = config.MAX_STEPS + config.OBSERVE_STEPS + 5
    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT
        fg = base_sensors.front_gap(vehicle, scenario.obstacles)
        lc = base_sensors.left_clear(vehicle, scenario.obstacles)
        rc = base_sensors.right_clear(vehicle, scenario.obstacles)
        ey = base_sensors.ey_line(base_sensors.ir_pattern(vehicle))
        obstacle_info = improved_sensors.front_obstacle_info(vehicle, scenario.obstacles)

        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append((step_idx, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
        fsm = fsm_new
        state_duration[fsm.state.value] += 1

        if is_student:
            controller.set_context(vehicle.v, ey, vehicle.y, fg, lc)
        lat = improved_compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, controller,
                                       delta_prev, obstacle_info=obstacle_info)
        delta_desired = lat.delta_desired_deg
        if lat.mpc_result is not None:
            n_policy_calls += 1
            policy_ms.append(lat.mpc_result.compute_time_ms)
            if not math.isfinite(delta_desired):
                nonfinite_delta += 1
        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(delta_desired, delta_prev)
        if pp.rate_limit_active:
            rate_limit_count += 1
        if pp.clip_active:
            clip_count += 1
            if metrics.classify_clip(pp.after_rate_deg) == "clip_violation":
                clip_violation_count += 1
        delta_prev = pp.delta_final_deg
        vehicle_new = vehicle_step(vehicle, pp.delta_final_deg, v_cmd, config.DT)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)
        if not metrics.psi_within_tolerance(vehicle_new.psi * _RAD2DEG):
            psi_viol += 1
        y_ok = metrics.y_within_tolerance(vehicle_new.y, fsm.state)
        if y_ok is not None:
            y_checked += 1
            if not y_ok:
                y_viol += 1
                lo, hi = config.POSITION_CONSTRAINTS[fsm.state.value]
                y_max_abs_violation = max(y_max_abs_violation,
                                          max(lo - vehicle_new.y, vehicle_new.y - hi, 0.0))
        traj.append((t, vehicle_new.x, vehicle_new.y, vehicle_new.psi, fsm.state.value,
                     delta_desired, pp.delta_final_deg, lat.mode))
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
            outcome, finish_step = "충돌", step_idx
            break
        if fsm.state == FSMState.SAFE_STOP:
            outcome, finish_step = "SAFE_STOP", step_idx
            break
        if fsm.state == FSMState.KEEP_L2 and visited_evade and transitions \
                and transitions[-1][2] == FSMState.KEEP_L2.value and transitions[-1][0] == step_idx:
            finish_step = step_idx
            observing, observe_start = True, step_idx
            continue
        if step_idx >= config.MAX_STEPS:
            outcome = "타임아웃"
            break
    if outcome is None:
        outcome = "타임아웃"
    return dict(outcome=outcome, finish_step=finish_step, total_steps=step_idx,
                transitions=transitions, state_duration=state_duration,
                n_policy_calls=n_policy_calls, nonfinite_delta=nonfinite_delta,
                rate_limit_count=rate_limit_count, clip_count=clip_count,
                clip_violation_count=clip_violation_count, y_checked=y_checked,
                y_violation=y_viol, y_max_abs_violation_m=y_max_abs_violation,
                psi_violation=psi_viol, policy_ms=policy_ms, traj=traj)


def scenarios_for(track: str):
    if track == "paper":
        return [(s, generate_scenario(s)) for s in i4_config.EVAL_PAPER_SEEDS]
    if track == "s3":
        return [((float(fg), float(y0)), generate_grid_scenario(float(fg), float(y0)))
                for fg in i4_config.EVAL_S3_FRONT_GAPS for y0 in i4_config.EVAL_S3_Y0S]
    if track == "dev_paper":  # DESIGN_I4 §6-7 dev 선택용
        return [(s, generate_scenario(s)) for s in i4_config.DEV_PAPER_SEEDS]
    if track == "dev_s3":
        return [((float(fg), float(y0)), generate_grid_scenario(float(fg), float(y0)))
                for fg in i4_config.DEV_S3_FRONT_GAPS for y0 in i4_config.DEV_S3_Y0S]
    if track == "eval3_paper":  # DESIGN_I4 §6-4, 선택 후 1회만
        return [(s, generate_scenario(s)) for s in i4_config.EVAL3_PAPER_SEEDS]
    if track == "eval3_s3":
        return [((float(fg), float(y0)), generate_grid_scenario(float(fg), float(y0)))
                for fg in i4_config.EVAL3_S3_FRONT_GAPS for y0 in i4_config.EVAL3_S3_Y0S]
    if track == "smoke_dev":  # 스크립트 동작 확인 전용(dev seed, eval 데이터 아님)
        return [(s, generate_scenario(s)) for s in (100, 101, 102)]
    raise ValueError(track)


def _ci(k, n):
    c = wilson_ci(k, n)
    return dict(k=k, n=n, rate=k / n if n else None, ci95=[c["lo"], c["hi"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, required=True)
    ap.add_argument("--track", choices=["paper", "s3", "dev_paper", "dev_s3", "eval3_paper", "eval3_s3",
                                        "smoke_dev"], required=True)
    ap.add_argument("--model-dir", type=str, default=None,
                    help="모델 폴더(checkpoints/, normalization_stats.json). 기본값 <run-dir>")
    ap.add_argument("--out-tag", type=str, default="", help="결과 파일 이름 접미사(모델 구분용)")
    ap.add_argument("--policy", choices=["student", "mpc"], default="student")
    args = ap.parse_args()
    run = Path(args.run_dir)
    out = run / "eval" / "closed_loop"
    out.mkdir(parents=True, exist_ok=True)

    if args.policy == "student":
        md = Path(args.model_dir) if args.model_dir else run
        ctrl = StudentLateral(Predictor(md / "checkpoints" / "policy_i4_best.pt",
                                        md / "normalization_stats.json"))
    else:
        ctrl = ImprovedMPC(**i4_config.TEACHER_FLAGS)

    t0 = time.perf_counter()
    eps = []
    for key, sc in scenarios_for(args.track):
        r = run_episode(sc, ctrl, is_student=(args.policy == "student"))
        r["key"] = key
        eps.append(r)
    wall = time.perf_counter() - t0

    n = len(eps)
    oc = Counter(e["outcome"] for e in eps)
    calls = sum(e["n_policy_calls"] for e in eps)
    steps = sum(e["total_steps"] for e in eps)
    y_checked = sum(e["y_checked"] for e in eps)
    summary = dict(
        track=args.track, policy=args.policy, n_episodes=n, wall_time_sec=wall,
        outcomes=dict(oc),
        collision=_ci(oc.get("충돌", 0), n), success=_ci(oc.get("성공", 0), n),
        fail_non_success=_ci(n - oc.get("성공", 0), n),
        nonfinite_delta_total=sum(e["nonfinite_delta"] for e in eps),
        n_policy_calls=calls,
        clip_rate_per_policy_call=(sum(e["clip_count"] for e in eps) / calls) if calls else None,
        clip_rate_per_step=sum(e["clip_count"] for e in eps) / steps,
        clip_violation_total=sum(e["clip_violation_count"] for e in eps),
        rate_limit_rate_per_step=sum(e["rate_limit_count"] for e in eps) / steps,
        y_within_tolerance_rate=(1 - sum(e["y_violation"] for e in eps) / y_checked) if y_checked else None,
        y_max_abs_violation_m=max(e["y_max_abs_violation_m"] for e in eps),
        psi_violation_total=sum(e["psi_violation"] for e in eps),
        per_episode=[dict(key=e["key"], outcome=e["outcome"], finish_step=e["finish_step"],
                          total_steps=e["total_steps"], n_policy_calls=e["n_policy_calls"],
                          clip_count=e["clip_count"], y_violation=e["y_violation"],
                          transitions=e["transitions"]) for e in eps],
    )
    tag = f"{args.track}_{args.policy}{args.out_tag}"
    with open(out / f"closed_loop_{tag}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    np.savez_compressed(out / f"traj_{tag}.npz",
                        **{f"ep{i}": np.array([row[:4] for row in e["traj"]], dtype=float)
                           for i, e in enumerate(eps)})
    print(json.dumps({k: summary[k] for k in ("track", "policy", "n_episodes", "outcomes",
                                              "nonfinite_delta_total", "wall_time_sec")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
