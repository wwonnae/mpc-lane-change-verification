"""
RESULT_IMPROVED.md 검토(4번): 계산시간 트레이드오프. eval 데이터(seed 0~99, S3 961격자,
S4~S7)를 baseline/improved 양쪽으로 다시 실행하며 MPC solve 시간과 "제어 1스텝 전체"
시간을 함께 측정한다. baseline은 이미 t_step_ms를 기록하지만 improved runner.py는
t_step_ms=0.0으로 미구현 상태라(2026-09-23 검토에서 code freeze 이후 -- 코드 수정
금지), 이 스크립트 안에서만 improved의 루프를 그대로 복제(원본 파일 미수정, 읽기
전용 재사용)해 스텝 전체 시간을 별도로 측정한다. 참고값(호스트 3층PC104), 공식
판정은 노트북 일괄측정(NEXT_SESSION.md).
"""
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config, postprocess, longitudinal, collision, metrics
from thesis_v2.baseline.vehicle import initial_state, step as vehicle_step
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.world import (
    generate_scenario, generate_left_obstacle_scenario, generate_grid_scenario,
    generate_scenario_custom_obstacle, generate_front_rear_scenario,
)
from thesis_v2.baseline.runner import run_episode as base_run_episode
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.lateral import compute_lateral as improved_compute_lateral

_RAD2DEG = 180.0 / math.pi
FINAL_COMBO = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                    i2_variant="narrow")


def timed_improved_episode(scenario, mpc):
    """thesis_v2/improved/runner.py의 run_episode와 동일한 스텝 순서를 그대로
    재사용(원본 파일 미수정)하되, 매 스텝 전체 소요시간(t_step_ms)을 추가로 측정."""
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    visited_evade = False
    outcome = None
    step_idx = 0
    max_iter = config.MAX_STEPS + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None
    observed_transition_departure = False
    mpc_times, step_times, step_meta = [], [], []
    transitions_last_to = None

    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT
        t0 = time.perf_counter()

        fg = base_sensors.front_gap(vehicle, scenario.obstacles)
        lc = base_sensors.left_clear(vehicle, scenario.obstacles)
        rc = base_sensors.right_clear(vehicle, scenario.obstacles)
        pattern = base_sensors.ir_pattern(vehicle)
        ey = base_sensors.ey_line(pattern)
        obstacle_info = improved_sensors.front_obstacle_info(vehicle, scenario.obstacles)

        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
            transitions_last_to = (fsm_new.state.value, step_idx)
        fsm = fsm_new

        lat = improved_compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc,
                                        delta_prev, obstacle_info=obstacle_info)
        delta_desired = lat.delta_desired_deg
        mpc_ms = lat.mpc_result.compute_time_ms if lat.mpc_result else 0.0
        is_max_iter = bool(lat.mpc_result and lat.mpc_result.solver_status == "maximum iterations reached")
        if lat.mpc_result is not None:
            mpc_times.append(mpc_ms)

        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(delta_desired, delta_prev)
        delta_prev = pp.delta_final_deg
        vehicle_new = vehicle_step(vehicle, pp.delta_final_deg, v_cmd, config.DT)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)
        vehicle = vehicle_new

        t_step_ms = (time.perf_counter() - t0) * 1000.0
        step_times.append(t_step_ms)
        step_meta.append((step_idx, fsm.state.value, is_max_iter, mpc_ms, t_step_ms))

        if observing:
            if step_idx - observe_start >= config.OBSERVE_STEPS:
                outcome = "성공"
                break
            continue
        if collided:
            outcome = "충돌"
            break
        if fsm.state == FSMState.SAFE_STOP:
            outcome = "SAFE_STOP"
            break
        if fsm.state == FSMState.KEEP_L2 and visited_evade and transitions_last_to is not None \
                and transitions_last_to == (FSMState.KEEP_L2.value, step_idx):
            observing = True
            observe_start = step_idx
            continue
        if step_idx >= config.MAX_STEPS:
            outcome = "타임아웃"
            break

    return mpc_times, step_times, step_meta, outcome


def collect(scenarios_and_seeds, label):
    """scenarios_and_seeds: list of (seed, scenario). baseline/improved 둘 다 측정."""
    mpc_b = OSQPMPC()
    mpc_i = ImprovedMPC(**FINAL_COMBO)
    base_mpc_all, base_step_all = [], []
    imp_mpc_all, imp_step_all = [], []
    imp_worst = None  # (t_step_ms, seed, step, state, is_max_iter)
    base_worst = None
    for seed, sc in scenarios_and_seeds:
        rb = base_run_episode(sc, mpc=mpc_b)
        base_mpc_all.extend(rb.mpc_solve_times_ms)
        step_ms_list = [row["t_step_ms"] for row in rb.logger.rows]
        base_step_all.extend(step_ms_list)
        for i, v in enumerate(step_ms_list):
            if base_worst is None or v > base_worst[0]:
                base_worst = (v, seed, i + 1, rb.logger.rows[i]["state"], False)

        mpc_times, step_times, step_meta, _ = timed_improved_episode(sc, mpc_i)
        imp_mpc_all.extend(mpc_times)
        imp_step_all.extend(step_times)
        for step_idx, state_name, is_max_iter, mpc_ms, t_step_ms in step_meta:
            if imp_worst is None or t_step_ms > imp_worst[0]:
                imp_worst = (t_step_ms, seed, step_idx, state_name, is_max_iter)

    return {
        "label": label,
        "baseline": _stats(base_mpc_all, base_step_all, base_worst),
        "improved": _stats(imp_mpc_all, imp_step_all, imp_worst),
    }


def _stats(mpc_all, step_all, worst):
    def pct(arr, p):
        return float(np.percentile(arr, p)) if arr else None
    return {
        "n_mpc_calls": len(mpc_all), "n_steps": len(step_all),
        "mpc_mean_ms": float(np.mean(mpc_all)) if mpc_all else None,
        "mpc_p50_ms": pct(mpc_all, 50), "mpc_p95_ms": pct(mpc_all, 95),
        "mpc_p99_ms": pct(mpc_all, 99), "mpc_max_ms": max(mpc_all) if mpc_all else None,
        "step_mean_ms": float(np.mean(step_all)) if step_all else None,
        "step_p50_ms": pct(step_all, 50), "step_p95_ms": pct(step_all, 95),
        "step_p99_ms": pct(step_all, 99), "step_max_ms": max(step_all) if step_all else None,
        "n_step_over_40ms": sum(1 for v in step_all if v > 40),
        "n_step_over_50ms": sum(1 for v in step_all if v > 50),
        "worst_step_context(ms,seed,step,state,max_iter)": worst,
    }


def main():
    import json
    EVAL_SEEDS = list(range(100))
    results = {}

    results["paper"] = collect([(s, generate_scenario(s)) for s in EVAL_SEEDS], "paper")
    results["S6_psi-15"] = collect(
        [(s, generate_scenario(s, psi0_deg=-15.0)) for s in EVAL_SEEDS], "S6_psi-15")
    results["S6_psi15"] = collect(
        [(s, generate_scenario(s, psi0_deg=15.0)) for s in EVAL_SEEDS], "S6_psi15")
    results["S7a_width0.20"] = collect(
        [(s, generate_scenario_custom_obstacle(s, obstacle_width=0.20)) for s in EVAL_SEEDS],
        "S7a_width0.20")

    # S3: 961격자는 규모가 크므로 대표 서브샘플(front_gap 5칸, y0 5칸=25 cell)로 근사
    grid_scenarios = []
    fgs = np.round(np.linspace(0.5, 2.0, 5), 4)
    y0s = np.round(np.linspace(-0.15, 0.15, 5), 4)
    for idx, (fg, y0) in enumerate([(f, y) for f in fgs for y in y0s]):
        grid_scenarios.append((idx, generate_grid_scenario(float(fg), float(y0))))
    results["S3_subsample25"] = collect(grid_scenarios, "S3_subsample25")

    out = Path(__file__).resolve().parent / "out" / "eval_timing_analysis.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    for name, r in results.items():
        print("===", name, "===")
        for who in ("baseline", "improved"):
            s = r[who]
            print(f"  {who}: mpc mean={s['mpc_mean_ms']:.4f} p50={s['mpc_p50_ms']:.4f} "
                  f"p95={s['mpc_p95_ms']:.4f} p99={s['mpc_p99_ms']:.4f} max={s['mpc_max_ms']:.4f} | "
                  f"step mean={s['step_mean_ms']:.4f} p50={s['step_p50_ms']:.4f} "
                  f"p95={s['step_p95_ms']:.4f} p99={s['step_p99_ms']:.4f} max={s['step_max_ms']:.4f} | "
                  f"over40={s['n_step_over_40ms']} over50={s['n_step_over_50ms']} "
                  f"worst={s['worst_step_context(ms,seed,step,state,max_iter)']}")


if __name__ == "__main__":
    main()
