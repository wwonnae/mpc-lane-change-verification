"""
탐지기 계산 시간 — 공식 조건 측정(검증 산출물 보강 0단계, 2026-10-12 지시). 제어·탐지 로직·평가 결과는 바꾸지 않는다.

관례(`improved/student_i4/benchmark_timing.py`, `docs/revision/scripts/r2_timing_supplement.py`와 같음):
- 공식 조건 = 노트북 DESKTOP-MDCKRJS, AC 전원 + Windows 전원 모드 "최고 성능"(MEASURE_PLAN.md 공통 원칙).
  `--power-mode-confirmed`를 주면 env.json의 `power.meets_official_condition`에 반영된다(`baseline/envinfo.py`).
- 주 지표 p99, 20 Hz 예산 50 ms 대비 비율. 시간은 `time.perf_counter()`.

측정 대상(탐지기마다 별도 패스 — 한 패스에는 탐지기 하나만 붙인다, 폐루프의 실제 배치와 같음):
  A(`DetectorA`), B1(`DetectorB`+IF), B2(`DetectorB`+AE), HYBRID(`DetectorHybrid`, 내부에 DetectorA 포함).
  모델·임계값은 폐루프 평가 결과 폴더의 meta.json(`--cl-meta`)에서 읽고 `closed_loop.build_detector`로 만든다
  (폐루프 평가와 같은 파일). 임계값은 경보 여부에만 쓰이며 시간에는 영향이 없다.

데이터: 정상 seed 3000~3199(`SEEDS_NORMAL_TRAIN`, 임계값 대역 — 평가 seed 아님) × 정상 시나리오 2종(원거리, 좌측 장애물)
= 400 에피소드/패스, 고장 없음. 조건은 `common.run_anomaly_episode`와 같다(v2 MPC 에피소드마다 새로 생성, S4-low 노이즈,
자이로 σ=1°/s, 상한 300 step, 이탈 시 종료). 탐지기는 관찰 전용(P0)이라 제어 결과는 탐지기와 무관하다.

스텝 루프는 `anomaly/runner.run_episode`와 같은 순서·호출이다(제어 모듈은 import만). 시간 구간:
- control_ms = [센서(+S4 노이즈)·front_obstacle_info] + [FSM → 횡방향(v2 MPC) → 종방향 → 후처리 → 액추에이터 주입(정상에서는
  항등) → 차량 갱신 → 충돌 판정]. timing_v3·student_i4 benchmark의 "제어 1스텝"(센서~충돌 판정) 정의에 노이즈만 더한 것.
  고장 센서 주입·탐지기 전용 자이로 생성·DetectorObs 생성·이탈 판정·기록은 시뮬레이션 측이라 포함하지 않는다.
- detector_ms = `detector.update(obs)` 호출 하나.
- combined_ms = 같은 step의 control_ms + detector_ms(스텝별 합의 분포).
- mpc_solve_ms = `MPCResult.compute_time_ms`(MPC를 호출한 step만).
각 패스 시작 전에 seed 3000 원거리 1 에피소드를 워밍업으로 돌리고 버린다. gc는 기본값(켜짐) 그대로다.

결정성: 이 루프의 결과(outcome·total_steps·first_alarm_step·전이)는 `runner.run_episode`와 같아야 한다
(`tests/test_detector_timing.py`). 시간 값 자체는 실행마다 다르다.

사용(저장소 루트):
  python -m thesis_v2.anomaly.benchmark_detector_timing --power-mode-confirmed --cooldown-before-sec 60
  (스모크: --n-seeds 2 --out-root <스크래치 폴더>, 보고 수치로 쓰지 않음)
"""
from . import common  # noqa: F401  — git 스냅샷을 결과 파일 쓰기 전에 잡는다(common.py §23 수정 참고)

import argparse
import gc
import json
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from thesis_v2.baseline import config, postprocess, longitudinal, collision
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.vehicle import initial_state, step as vehicle_step
from thesis_v2.baseline.world import Scenario
from thesis_v2.improved import sensors as improved_sensors
from thesis_v2.improved.lateral import compute_lateral
from thesis_v2.improved.mpc import ImprovedMPC

from . import config as an_config
from .closed_loop import build_detector
from .common import new_out_dir, write_csv, _GIT_SNAPSHOT
from .faults import FaultInjector, SensorFrame
from .runner import DetectorObs, Transition, vehicle_off_road
from .scenarios import generate_anomaly_scenario

_RAD2DEG = 180.0 / math.pi
BUDGET_MS = 1000.0 * config.DT  # 20 Hz 제어 주기 = 50 ms
assert BUDGET_MS == 50.0

DETECTORS = ("A", "B1", "B2", "HYBRID")
_COMBO_OF = {"A": "P1_A", "B1": "P1_B1", "B2": "P1_B2", "HYBRID": "P1_HYBRID"}  # build_detector 이름(정책과 무관)
DEFAULT_CL_META = "thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval/meta.json"
SEEDS = an_config.SEEDS_NORMAL_TRAIN            # 3000~3199
SCENARIOS = an_config.NORMAL_SCENARIOS          # ("far", "leftobs")
WARMUP = ("far", SEEDS[0])
EPISODE_HEADER = ["scenario", "seed", "outcome", "total_steps", "first_alarm_step", "n_mpc_calls"]


def timed_episode(scenario: Scenario, detector, mpc: ImprovedMPC, noise_profile, noise_rng, gyro_rng,
                  sigma_gyro_deg: float, max_steps: int, terminate_on_departure: bool = True) -> dict:
    """`runner.run_episode`(고장 없음, 관찰 전용 탐지기)와 같은 스텝 순서·호출. 측정 구간은 모듈 docstring 참고."""
    injector = FaultInjector(None)
    detector.reset()
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    transitions: List[Transition] = []
    visited_evade = False
    outcome = None
    observed_settle_violation = False
    observed_transition_departure = False
    first_alarm_step = None
    psi_prev = None
    control_ms: List[float] = []
    detector_ms: List[float] = []
    mpc_ms: List[float] = []

    step_idx = 0
    max_iter = max_steps + config.OBSERVE_STEPS + 5
    observing = False
    observe_start = None
    pc = time.perf_counter

    while step_idx < max_iter:
        step_idx += 1
        t = step_idx * config.DT

        # [제어 구간 1] 센서
        t0 = pc()
        fg = base_sensors.front_gap_noisy(vehicle, scenario.obstacles, noise_rng, noise_profile.sigma_front_gap)
        lc = base_sensors.left_clear_noisy(vehicle, scenario.obstacles, noise_rng, noise_profile.flip_p)
        rc = base_sensors.right_clear_noisy(vehicle, scenario.obstacles, noise_rng, noise_profile.flip_p)
        pattern = base_sensors.ir_pattern(vehicle)
        ey = base_sensors.ey_line_noisy(base_sensors.ey_line(pattern), noise_rng, noise_profile.sigma_ey)
        obstacle_info = improved_sensors.front_obstacle_info(vehicle, scenario.obstacles)
        t1 = pc()

        # (시뮬레이션 측, 미측정) 고장 주입(정상 → 항등)·탐지기 전용 자이로·관측 묶음
        clean = SensorFrame(fg, lc, rc, pattern, ey, obstacle_info)
        frame = injector.apply_sensors(step_idx, clean)
        fg, lc, rc = frame.front_gap, frame.left_clear, frame.right_clear
        pattern, ey, obstacle_info = frame.ir_pattern, frame.ey_line, frame.obstacle_info
        yaw_rate_meas = None
        if psi_prev is not None:
            yaw_rate_meas = (vehicle.psi - psi_prev) / config.DT
            yaw_rate_meas += gyro_rng.normal(0.0, math.radians(sigma_gyro_deg))
        psi_prev = vehicle.psi
        obs = DetectorObs(step=step_idx, t=t, frame=frame, y=vehicle.y, psi=vehicle.psi, v=vehicle.v,
                          fsm_state=fsm.state.value, delta_prev_cmd_deg=delta_prev, yaw_rate_meas=yaw_rate_meas)

        # [탐지기 구간] (관찰 전용 — 반환값은 첫 경보 step 기록에만 쓴다)
        t2 = pc()
        det_out = detector.update(obs)
        t3 = pc()
        if det_out.alarm and first_alarm_step is None:
            first_alarm_step = step_idx

        # [제어 구간 2] FSM → 횡방향 → 종방향 → 후처리 → (액추에이터 주입, 정상 → 항등) → 차량 갱신 → 충돌 판정
        t4 = pc()
        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append(Transition(step_idx, t, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if observing:
                observed_transition_departure = True
        fsm = fsm_new
        lat = compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc, delta_prev,
                              obstacle_info=obstacle_info)
        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(lat.delta_desired_deg, delta_prev)
        delta_prev = pp.delta_final_deg
        delta_to_vehicle = injector.apply_actuator(step_idx, pp.delta_final_deg)
        vehicle_new = vehicle_step(vehicle, delta_to_vehicle, v_cmd, config.DT)
        collided = collision.check_collision(vehicle_new, scenario.obstacles)
        t5 = pc()

        control_ms.append(((t1 - t0) + (t5 - t4)) * 1000.0)
        detector_ms.append((t3 - t2) * 1000.0)
        if lat.mpc_result is not None:
            mpc_ms.append(lat.mpc_result.compute_time_ms)

        # (시뮬레이션 측, 미측정) 이탈 판정·종료 판정 — runner.run_episode와 같은 규칙
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
            break
        if terminate_on_departure and off_road:
            outcome = "이탈"
            break
        if fsm.state == FSMState.SAFE_STOP:
            outcome = "SAFE_STOP"
            break
        if fsm.state == FSMState.KEEP_L2 and visited_evade and len(transitions) > 0 \
                and transitions[-1].to_state == FSMState.KEEP_L2.value \
                and transitions[-1].step == step_idx:
            observing = True
            observe_start = step_idx
            continue
        if step_idx >= max_steps:
            outcome = "타임아웃"
            break
    if outcome is None:
        outcome = "타임아웃"
    return dict(outcome=outcome, total_steps=step_idx, first_alarm_step=first_alarm_step,
                transitions=transitions, control_ms=control_ms, detector_ms=detector_ms, mpc_ms=mpc_ms)


def run_normal_episode(scenario_kind: str, seed: int, detector) -> dict:
    """`common.run_anomaly_episode`(kind=None)와 같은 시나리오·노이즈·자이로·MPC 생성."""
    sc = generate_anomaly_scenario(seed, left_obstacle=(scenario_kind == "leftobs"))
    return timed_episode(
        sc, detector, ImprovedMPC(**an_config.V2_MPC_FLAGS),
        noise_profile=base_sensors.NOISE_PROFILES[an_config.NORMAL_NOISE_PROFILE],
        noise_rng=np.random.default_rng((seed, an_config.NOISE_STREAM_ID)),
        gyro_rng=np.random.default_rng((seed, an_config.GYRO_STREAM_ID)),
        sigma_gyro_deg=an_config.SIGMA_GYRO_DEG, max_steps=an_config.ANOMALY_MAX_STEPS)


def stats(values) -> Optional[dict]:
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        return None
    p50, p95, p99 = (float(np.percentile(a, q)) for q in (50, 95, 99))
    mx = float(a.max())
    return dict(n=int(a.size), mean=float(a.mean()), std=float(a.std()), min=float(a.min()),
                p50=p50, p95=p95, p99=p99, max=mx,
                p50_pct_of_budget=p50 / BUDGET_MS * 100.0, p99_pct_of_budget=p99 / BUDGET_MS * 100.0,
                max_pct_of_budget=mx / BUDGET_MS * 100.0, n_over_budget=int((a > BUDGET_MS).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--power-mode-confirmed", action="store_true",
                    help="Windows 전원 모드 '최고 성능'을 사용자가 육안 확인함(envinfo 관례)")
    ap.add_argument("--cooldown-before-sec", type=int, default=0)
    ap.add_argument("--n-seeds", type=int, default=len(SEEDS), help="스모크 테스트용으로만 줄임(보고용은 기본 200)")
    ap.add_argument("--detectors", default=",".join(DETECTORS), help="쉼표 구분(기본 전체, 스모크용)")
    ap.add_argument("--cl-meta", default=DEFAULT_CL_META, help="모델·임계값 출처(폐루프 평가 meta.json)")
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    args = ap.parse_args()
    dets = [d.strip() for d in args.detectors.split(",") if d.strip()]
    assert dets and all(d in DETECTORS for d in dets), dets
    seeds = SEEDS[:args.n_seeds]
    official_run = args.n_seeds == len(SEEDS) and dets == list(DETECTORS)

    if args.cooldown_before_sec > 0:
        print(f"cooldown {args.cooldown_before_sec}s ...", flush=True)
        time.sleep(args.cooldown_before_sec)

    meta = json.loads(Path(args.cl_meta).read_text(encoding="utf-8"))
    h_by_detector, model_dirs = meta["h_by_detector"], meta["model_dirs"]
    detectors = {d: build_detector(_COMBO_OF[d], h_by_detector, model_dirs) for d in dets}

    import torch
    out = new_out_dir(args.out_root, "detector_timing" + ("" if official_run else "_smoke"))
    env = collect_env_info(power_mode_confirmed=args.power_mode_confirmed)
    pk = {}
    for name in ("sklearn", "pandas", "torch"):
        try:
            pk[name] = __import__(name).__version__
        except ImportError:
            pk[name] = None
    env.update(anomaly_packages=pk, git=_GIT_SNAPSHOT, torch_threads=torch.get_num_threads(),
               torch_interop_threads=torch.get_num_interop_threads(), gc_enabled=gc.isenabled(),
               thread_env={k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
               cpu_count=os.cpu_count(),
               purpose="탐지기 계산 시간 공식 조건 측정(검증 산출물 보강 0단계)" + ("" if official_run else " — 스모크, 보고 수치 아님"))
    (out / "env.json").write_text(json.dumps(env, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"hostname={env['hostname']} official_host={env['is_official_measurement_host']} "
          f"meets_official_condition={env['power']['meets_official_condition']} "
          f"git={_GIT_SNAPSHOT}", flush=True)

    results = dict(budget_ms=BUDGET_MS, seeds=[seeds[0], seeds[-1]], scenarios=list(SCENARIOS),
                   n_episodes_per_detector=len(seeds) * len(SCENARIOS), warmup_episode=list(WARMUP),
                   cl_meta=args.cl_meta, h_by_detector=h_by_detector, model_dirs=model_dirs,
                   meets_official_condition=env["power"]["meets_official_condition"],
                   is_official_measurement_host=env["is_official_measurement_host"],
                   official_run=official_run, detectors={})
    raw = {}
    for d in dets:
        det = detectors[d]
        run_normal_episode(WARMUP[0], WARMUP[1], det)  # 워밍업(버림)
        t_wall = time.perf_counter()
        ctrl, dms, comb, mpc, ep_rows = [], [], [], [], []
        for sk in SCENARIOS:
            for s in seeds:
                r = run_normal_episode(sk, s, det)
                c = np.asarray(r["control_ms"])
                m = np.asarray(r["detector_ms"])
                ctrl.append(c)
                dms.append(m)
                comb.append(c + m)
                mpc += r["mpc_ms"]
                ep_rows.append(dict(scenario=sk, seed=s, outcome=r["outcome"], total_steps=r["total_steps"],
                                    first_alarm_step=r["first_alarm_step"], n_mpc_calls=len(r["mpc_ms"])))
        wall = time.perf_counter() - t_wall
        ctrl, dms, comb = np.concatenate(ctrl), np.concatenate(dms), np.concatenate(comb)
        write_csv(out / f"episodes_{d}.csv", EPISODE_HEADER, ep_rows)
        raw[f"{d}_control_ms"], raw[f"{d}_detector_ms"] = ctrl, dms
        res = dict(n_steps=int(ctrl.size), wall_time_sec=wall,
                   detector_ms=stats(dms), control_ms=stats(ctrl), combined_ms=stats(comb), mpc_solve_ms=stats(mpc))
        results["detectors"][d] = res
        print(f"[{d}] steps={ctrl.size} wall={wall:.1f}s  detector p50/p99/max = "
              f"{res['detector_ms']['p50']:.4f}/{res['detector_ms']['p99']:.4f}/{res['detector_ms']['max']:.4f} ms  "
              f"control+detector p99 = {res['combined_ms']['p99']:.4f} ms ({res['combined_ms']['p99_pct_of_budget']:.2f}% of 50 ms)",
              flush=True)

    np.savez_compressed(out / "step_times_ms.npz", **raw)
    (out / "timing.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved:", out)


if __name__ == "__main__":
    main()
