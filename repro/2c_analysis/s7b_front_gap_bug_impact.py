"""
버그 영향 수치화 (분석 전용, repro/2c_analysis/에서만). 2026-09-22.

목적: REQ-SEN-01 front_gap 버그(v1.0, "지나친 장애물"을 방향 구분 없이 0.0으로 계산)가
"관찰구간에도 FSM이 계속 갱신되는" 상황(v1.1의 관찰구간 정정, 실제 연속 주행 재현)과
결합했다면 어떤 일이 벌어졌을지 사후 재현한다. baseline v1.1(현재 저장소 상태, 버그
수정됨)은 전혀 건드리지 않는다 -- 이 스크립트를 실행하는 프로세스 안에서만
`thesis_v2.baseline.sensors.front_gap`을 v1.0 버그 버전으로 임시 교체(monkeypatch)하고,
디스크의 파일은 수정하지 않는다.

**이 결과는 "버그가 있었다면"의 증거로만 쓴다 -- baseline v1.1의 공식 결과로 보고하지
않는다** (`THESIS_REVISION_LOG.md` 2026-09-22 REQ-SEN-01, `NEXT_SESSION.md` 2026-09-22
지시 3번).

방법: `thesis_v2.baseline.runner.run_episode`는 "완료"(KEEP_L2 재진입) 시점에 20 step만
관찰하고 끝낸다. 실제 연속 주행에서 이 버그가 어떻게 전개되는지 보려면 그보다 긴 지평선이
필요하므로, 이 스크립트는 runner.py를 수정하지 않고 같은 원시 함수(sensors/fsm/lateral/
longitudinal/postprocess/vehicle/collision)를 그대로 재사용해 "완료 후에도 멈추지 않고
계속 시뮬레이션하는" 확장 루프를 이 스크립트 안에서만 구현한다(총 600 step=30s, MAX_STEPS
200의 3배 -- 재진입 후 진동이 반복되는지 볼 수 있는 여유).

산출물: `repro/2c_analysis/out/s7b_front_gap_bug_impact.json` (에피소드별 상세),
콘솔에 요약 출력.

사용(저장소 루트에서): python repro/2c_analysis/s7b_front_gap_bug_impact.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config, sensors, postprocess, longitudinal, collision, metrics
from thesis_v2.baseline.vehicle import initial_state, front_x, step as vehicle_step
from thesis_v2.baseline.fsm import FSMState, initial_fsm, step as fsm_step, SensorReadings
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.lateral import compute_lateral
from thesis_v2.baseline.world import generate_scenario

_RAD2DEG = 180.0 / math.pi
OUT_DIR = Path(__file__).resolve().parent / "out"
EXTENDED_STEPS = 600  # 30s @ 20Hz, MAX_STEPS(200)의 3배 -- 재진입 후 진동 반복 관찰용
N_EPISODES = 100

_FIXED_FRONT_GAP = sensors.front_gap  # v1.1(현재, 수정됨) 백업 -- 스크립트 종료 시 원복


def _buggy_front_gap_v1_0(state, obstacles):
    """v1.0 버그 재현: obs.x_far<fx 방향 필터 없이 그대로(수정 전 sensors.py:22-32)."""
    fx = front_x(state)
    y_lo, y_hi = state.y - config.B / 2, state.y + config.B / 2
    best = config.LIDAR_MAX_RANGE
    for obs in obstacles:
        if obs.y_hi < y_lo or obs.y_lo > y_hi:
            continue
        gap = max(0.0, obs.x_near - fx)
        best = min(best, gap)
    return best


def run_extended_episode(scenario, mpc):
    """runner.run_episode과 같은 파이프라인(센서->FSM->횡/종방향->후처리->차량갱신->충돌판정)을
    "완료해도 멈추지 않고" EXTENDED_STEPS까지 계속 실행. FSM은 매 스텝 갱신(v1.1 정정과 동일)."""
    vehicle = initial_state(scenario.v0, scenario.y0, scenario.psi0_deg)
    fsm = initial_fsm()
    delta_prev = 0.0
    transitions = []  # (step, from, to)
    visited_evade = False
    first_keep_l2_return_step = None
    collided_step = None

    for step_idx in range(1, EXTENDED_STEPS + 1):
        t = step_idx * config.DT
        fg = sensors.front_gap(vehicle, scenario.obstacles)
        lc = sensors.left_clear(vehicle, scenario.obstacles)
        rc = sensors.right_clear(vehicle, scenario.obstacles)
        pattern = sensors.ir_pattern(vehicle)
        ey = sensors.ey_line(pattern)

        fsm_new = fsm_step(fsm, SensorReadings(fg, lc, rc), vehicle.y, vehicle.psi * _RAD2DEG, t)
        if fsm_new.state != fsm.state:
            transitions.append((step_idx, fsm.state.value, fsm_new.state.value))
            if fsm_new.state == FSMState.EVADE_L:
                visited_evade = True
            if (fsm_new.state == FSMState.KEEP_L2 and visited_evade
                    and first_keep_l2_return_step is None):
                first_keep_l2_return_step = step_idx
        fsm = fsm_new

        lat = compute_lateral(fsm.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc, delta_prev)
        v_cmd = longitudinal.compute_v_cmd(fsm.state)
        pp = postprocess.apply(lat.delta_desired_deg, delta_prev)
        delta_prev = pp.delta_final_deg
        vehicle_new = vehicle_step(vehicle, pp.delta_final_deg, v_cmd, config.DT)

        if collision.check_collision(vehicle_new, scenario.obstacles):
            collided_step = step_idx
            vehicle = vehicle_new
            break
        vehicle = vehicle_new

    # 최초 KEEP_L2 복귀 이후의 재진입(EVADE_L) 이벤트만 집계
    reentries = [tr for tr in transitions
                 if first_keep_l2_return_step is not None
                 and tr[0] > first_keep_l2_return_step and tr[2] == FSMState.EVADE_L.value]
    return {
        "seed": scenario.seed,
        "first_keep_l2_return_step": first_keep_l2_return_step,
        "n_transitions_total": len(transitions),
        "n_evade_reentries_after_return": len(reentries),
        "steps_to_first_reentry": (reentries[0][0] - first_keep_l2_return_step) if reentries else None,
        "reentry_steps": [tr[0] for tr in reentries],
        "collided_step": collided_step,
        "transitions": transitions,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sensors.front_gap = _buggy_front_gap_v1_0
    try:
        mpc = OSQPMPC()
        episodes = []
        for seed in range(N_EPISODES):
            scenario = generate_scenario(seed)
            episodes.append(run_extended_episode(scenario, mpc))
    finally:
        sensors.front_gap = _FIXED_FRONT_GAP  # 원복(이 프로세스 한정이었지만 명시적으로 되돌림)

    n_returned = sum(1 for e in episodes if e["first_keep_l2_return_step"] is not None)
    n_reentry = sum(1 for e in episodes if e["n_evade_reentries_after_return"] > 0)
    n_collided_after_return = sum(
        1 for e in episodes
        if e["collided_step"] is not None and e["first_keep_l2_return_step"] is not None
        and e["collided_step"] > e["first_keep_l2_return_step"]
    )
    steps_to_reentry = [e["steps_to_first_reentry"] for e in episodes
                         if e["steps_to_first_reentry"] is not None]
    reentry_counts = [e["n_evade_reentries_after_return"] for e in episodes if n_returned]

    summary = {
        "n_episodes": N_EPISODES,
        "extended_steps": EXTENDED_STEPS,
        "n_episodes_returned_to_keep_l2": n_returned,
        "n_episodes_with_evade_reentry_after_return": n_reentry,
        "reentry_rate_among_returned": (n_reentry / n_returned) if n_returned else None,
        "n_episodes_collided_after_return": n_collided_after_return,
        "steps_to_first_reentry_min": min(steps_to_reentry) if steps_to_reentry else None,
        "steps_to_first_reentry_max": max(steps_to_reentry) if steps_to_reentry else None,
        "steps_to_first_reentry_mean": (sum(steps_to_reentry) / len(steps_to_reentry)
                                         if steps_to_reentry else None),
        "reentry_count_distribution": sorted(reentry_counts),
        "note": ("v1.0 front_gap 버그 + v1.1 관찰구간(FSM 계속 갱신) 조합을 이 스크립트 "
                 "프로세스 안에서만 재현한 결과. baseline v1.1 공식 결과 아님."),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    with open(OUT_DIR / "s7b_front_gap_bug_impact.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "episodes": episodes}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
