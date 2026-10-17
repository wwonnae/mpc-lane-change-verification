"""
노트북 공식 계산시간 일괄 측정(3단계 최종, DESIGN_IMPROVED_V2.md §5/§11 준비).
대상: baseline v1.1 / improved v1(I5 없음) / improved v2(I5, i5_max_iter=972).
시나리오: paper, left_obstacle, S6 psi0=-15deg(최악 조건, RESULT_IMPROVED.md §9).

측정: MPC solve 시간 + "제어 1스텝 전체" 시간 각각 mean/p50/p95/p99/max/
"첫 호출 제외 max"(콜드스타트 1회성 이상치 배제), 20Hz 예산(50ms) 대비 %(mean·p99
기준), 반복 횟수 분포(mean/p50/p95/max). MEASURE_PLAN.md(2026-09-25 정정)에 따라
**p99를 주 지표**로 보고하고 max는 참고로 병기한다.

원본 파일은 건드리지 않는다. baseline은 `run_episode`(이미 t_step_ms를 기록)를 그대로
쓰고, improved(v1/v2)는 `eval_timing_analysis.py`와 같은 방식으로 `runner.py`의 스텝
루프를 이 스크립트 안에서만 복제(원본 미수정, t_step_ms를 improved runner.py가 갖고
있지 않기 때문 -- 동결 이후 수정 금지). MPC 인스턴스는 버전당 하나만 만들어 시나리오의
전체 seed에서 재사용한다(warm-start 조건을 실제 eval/dev와 동일하게 유지 -- 2026-09-25
진단에서 seed마다 새 인스턴스를 쓰면 반복 횟수가 부풀려짐을 확인했음).

`--power-mode-confirmed`로 실행하면 env.json에 `power.meets_official_condition`이
기록된다(AC 전원 + Windows 전원 모드 "최고 성능" 확인, `thesis_v2/baseline/envinfo.py`
재사용). 이 플래그 없이 실행한 결과는 참고치로만 취급한다(MEASURE_PLAN.md 공통 원칙).

버전별로 분리 실행한다(`--version {baseline,v1,v2}` 중 하나만 지정) -- 같은 프로세스
안에서 여러 버전을 연달아 돌리면 앞선 버전의 캐시/스로틀링 상태가 다음 버전 측정에
섞일 수 있어서다. `--cooldown-before-sec`으로 측정 시작 전 대기(초)를 줄 수 있다
(직전 버전 실행이 끝난 뒤 CPU가 식을 시간을 벌기 위함, 기본 0=대기 없음).

사용(저장소 루트, Git Bash):
  python repro/2c_analysis/official_timing_benchmark_v3.py --version baseline \\
      --n-episodes 100 --power-mode-confirmed --cooldown-before-sec 60 \\
      --out-root thesis_v2/results/timing_v3/$(date +%Y%m%d_%H%M%S)_$(hostname)_baseline
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config, postprocess, longitudinal, collision
from thesis_v2.baseline.vehicle import initial_state, step as vehicle_step
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.world import generate_scenario, generate_left_obstacle_scenario
from thesis_v2.baseline.runner import run_episode as base_run_episode
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.baseline.logger import save_json
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.lateral import compute_lateral as improved_compute_lateral

_RAD2DEG = 180.0 / math.pi
BUDGET_MS = 50.0  # 20Hz

COMBO_V1 = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True, i2_variant="narrow")
COMBO_V2 = dict(COMBO_V1, enable_i5=True, i5_max_iter=972)

SCENARIOS = {
    "paper": (generate_scenario, {}),
    "left_obstacle": (generate_left_obstacle_scenario, {}),
    "S6_psi-15": (generate_scenario, {"psi0_deg": -15.0}),
}
SEED_START = 0  # 논문/dev/eval과 무관한 순수 계산시간 측정용 -- 안전성 판정에 안 씀


def _stats(arr):
    a = np.asarray(arr, dtype=float)
    if a.size == 0:
        return {"n": 0, "mean": None, "p50": None, "p95": None, "p99": None, "max": None,
                "max_excl_first": None}
    return {
        "n": int(a.size),
        "mean": float(a.mean()), "p50": float(np.percentile(a, 50)),
        "p95": float(np.percentile(a, 95)), "p99": float(np.percentile(a, 99)),
        "max": float(a.max()),
        "max_excl_first": float(a[1:].max()) if a.size > 1 else None,
    }


def _budget_pct(stats):
    if stats["mean"] is None:
        return {}
    return {"mean_pct_of_budget": stats["mean"] / BUDGET_MS * 100.0,
            "p99_pct_of_budget": stats["p99"] / BUDGET_MS * 100.0}


# ---------------- baseline ----------------

def run_baseline_scenario(gen_fn, gen_kwargs, seeds):
    mpc = OSQPMPC()
    iters = []
    orig_solve = mpc.prob.solve

    def wrapped(*a, **kw):
        res = orig_solve(*a, **kw)
        iters.append(int(res.info.iter))
        return res

    mpc.prob.solve = wrapped

    mpc_ms, step_ms = [], []
    for s in seeds:
        sc = gen_fn(s, **gen_kwargs)
        result = base_run_episode(sc, mpc=mpc)
        for row in result.logger.rows:
            step_ms.append(row["t_step_ms"])
            if row["solver_status"] != "N/A":
                mpc_ms.append(row["t_mpc_solve_ms"])
    return mpc_ms, step_ms, iters


# ---------------- improved v1/v2 (runner.py 스텝 루프 복제, 원본 미수정) ----------------

def timed_improved_episode(scenario, mpc):
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
    mpc_times, step_times, iters = [], [], []
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
        if lat.mpc_result is not None:
            mpc_times.append(lat.mpc_result.compute_time_ms)
            iters.append(lat.mpc_result.iterations)

        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(delta_desired, delta_prev)
        delta_prev = pp.delta_final_deg
        vehicle_new = vehicle_step(vehicle, pp.delta_final_deg, v_cmd, config.DT)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)
        vehicle = vehicle_new

        step_times.append((time.perf_counter() - t0) * 1000.0)

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

    return mpc_times, step_times, iters, outcome


def run_improved_scenario(combo_flags, gen_fn, gen_kwargs, seeds):
    mpc = ImprovedMPC(**combo_flags)
    mpc_ms, step_ms, iters = [], [], []
    for s in seeds:
        sc = gen_fn(s, **gen_kwargs)
        m, st, it, _ = timed_improved_episode(sc, mpc)
        mpc_ms.extend(m)
        step_ms.extend(st)
        iters.extend(it)
    return mpc_ms, step_ms, iters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["baseline", "v1", "v2"], required=True)
    ap.add_argument("--n-episodes", type=int, default=100)
    ap.add_argument("--out-root", type=str, required=True)
    ap.add_argument("--power-mode-confirmed", action="store_true")
    ap.add_argument("--cooldown-before-sec", type=int, default=0,
                     help="측정 시작 전 대기(초) -- 직전 버전 실행 직후 CPU를 식히고 싶을 때")
    args = ap.parse_args()

    if args.cooldown_before_sec > 0:
        print(f"cooldown {args.cooldown_before_sec}s ...", flush=True)
        time.sleep(args.cooldown_before_sec)

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    env_info = collect_env_info(power_mode_confirmed=args.power_mode_confirmed)
    save_json(env_info, out_root / "env.json")
    print(f"meets_official_condition = {env_info['power']['meets_official_condition']}", flush=True)

    seeds = list(range(SEED_START, SEED_START + args.n_episodes))
    results = {"version": args.version, "n_episodes": args.n_episodes,
               "env_meets_official_condition": env_info["power"]["meets_official_condition"]}

    for name, (gen_fn, gen_kwargs) in SCENARIOS.items():
        t0 = time.perf_counter()
        if args.version == "baseline":
            mpc_ms, step_ms, iters = run_baseline_scenario(gen_fn, gen_kwargs, seeds)
        else:
            combo = COMBO_V1 if args.version == "v1" else COMBO_V2
            mpc_ms, step_ms, iters = run_improved_scenario(combo, gen_fn, gen_kwargs, seeds)
        t1 = time.perf_counter()

        mpc_stats = _stats(mpc_ms)
        step_stats = _stats(step_ms)
        iter_stats = _stats(iters)
        results[name] = {
            "wall_time_sec": t1 - t0,
            "n_mpc_calls": len(mpc_ms),
            "mpc_solve_ms": {**mpc_stats, **_budget_pct(mpc_stats)},
            "step_total_ms": {**step_stats, **_budget_pct(step_stats)},
            "iterations": iter_stats,
        }
        print(f"[{args.version}/{name}] {t1-t0:.1f}s  "
              f"mpc p99={mpc_stats['p99']}ms  step p99={step_stats['p99']}ms", flush=True)

    with open(out_root / f"timing_{args.version}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
