"""
eval 2회차 최악 계산시간 성격 규명(사용자 요청, 2026-09-25). thesis_v2/improved/ 파일은
전혀 수정하지 않고(ImprovedMPC/run_episode를 run_eval_v2.py와 동일하게 그대로 호출),
mpc.solve만 이 스크립트 안에서 읽기 전용으로 monkeypatch해 매 solve 호출의
(seed, step, state, iterations, solver_status, time_limit_hit, run_time_ms)를 기록한다
(`i5_iter_time_benchmark.py`와 같은 방식 -- run_time_ms는 OSQP 자신이 보고하는
res.info.run_time, python 레벨 time.perf_counter 오버헤드 없는 순수 solve 시간).

이미 커밋·승인된 eval 2회차(신규 seed 200~299) 판정 자체를 다시 만드는 게 아니라,
그 결과(288,000+ solve)의 최댓값이 왜 나왔는지 설명하기 위한 진단 재실행이다(결정론
이므로 같은 콤보·같은 seed·같은 노이즈/지연 조건은 저장된 결과와 동일한 solve
시계열을 재현한다 -- 판정 데이터를 새로 만드는 것이 아님).

표본(전체 27개 서브그룹 중 대표 7개, 저장된 결과의 서브그룹별 max로 선정):
- v1: max가 전 서브그룹에서 27~37ms로 거의 균일(시나리오 난이도와 무관해 보임) --
  paper/left_obstacle/S4(high)/S5(delay=2)/S6(psi0=-15)/S7a(length=0.20)/S7b(rear=0.3)
- v2: max가 소수 서브그룹에 집중 -- 그 상위 4개(S7b rear=0.5/S6 psi0=0/S7a width=0.075/
  S5 delay=1) + 비교용 3개(paper/S6 psi0=-15/S7a length=0.20)

사용: python repro/2c_analysis/eval_v2_timing_diagnosis.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline.world import (
    generate_scenario, generate_left_obstacle_scenario,
    generate_scenario_custom_obstacle, generate_front_rear_scenario,
)
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

COMBO_V1 = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True, i2_variant="narrow")
COMBO_V2 = dict(COMBO_V1, enable_i5=True, i5_max_iter=972)
SEEDS = list(range(200, 300))


def run_subgroup(label, combo_flags, gen_fn, gen_kwargs=None, noise_name=None,
                  control_delay_steps=0):
    """label에 해당하는 서브그룹을 run_eval_v2.py와 동일 조건으로 재실행하며,
    mpc.solve를 감싸 매 호출의 (seed, step, state, iterations, status, ms)를 기록한다.
    run_eval_v2.py와 마찬가지로 **ImprovedMPC 인스턴스 하나를 서브그룹의 100개 seed
    전체에서 재사용**한다(warm-start가 seed 경계를 넘어 이어짐 -- 원래 eval과 동일한
    조건이어야 반복 횟수 분포가 재현된다. 최초 판에서 seed마다 새 인스턴스를 만들었더니
    warm-start가 매번 끊겨 반복 횟수가 실제보다 부풀려지는 것을 발견해 수정함)."""
    gen_kwargs = gen_kwargs or {}
    profile_ids = {"low": 1, "medium": 2, "high": 3}
    records = []

    mpc = ImprovedMPC(**combo_flags)
    step_counter = [0]

    orig_solve = mpc.solve

    def instrumented_solve(*a, **kw):
        step_counter[0] += 1
        state_name = kw.get("state_name", a[4] if len(a) > 4 else "")
        r = orig_solve(*a, **kw)
        records.append(dict(
            subgroup=label, seed=records_seed[0], step_in_episode=step_counter[0],
            state=state_name, iterations=r.iterations, solver_status=r.solver_status,
            time_limit_hit=r.time_limit_hit, run_time_ms=r.compute_time_ms,
        ))
        return r

    mpc.solve = instrumented_solve
    records_seed = [None]

    for s in SEEDS:
        records_seed[0] = s
        step_counter[0] = 0
        sc = gen_fn(s, **gen_kwargs)
        kw = {}
        if noise_name is not None:
            kw["noise_profile"] = base_sensors.NOISE_PROFILES[noise_name]
            kw["noise_rng"] = np.random.default_rng((s, profile_ids[noise_name]))
        if control_delay_steps:
            kw["control_delay_steps"] = control_delay_steps
        improved_run_episode(sc, mpc=mpc, **kw)

    return records


# (label, gen_fn, gen_kwargs, noise_name, control_delay_steps)
TARGETS = {
    "v1": [
        ("paper", generate_scenario, {}, None, 0),
        ("left_obstacle", generate_left_obstacle_scenario, {}, None, 0),
        ("S4/high", generate_scenario, {}, "high", 0),
        ("S5/delay_2step", generate_scenario, {}, None, 2),
        ("S6/psi0_-15deg", generate_scenario, {"psi0_deg": -15.0}, None, 0),
        ("S7a/length_0.20m", generate_scenario_custom_obstacle, {"obstacle_length": 0.20}, None, 0),
        ("S7b/rear_gap_0.3m", generate_front_rear_scenario, {"front_gap0": 1.0, "rear_gap": 0.3}, None, 0),
    ],
    "v2": [
        ("paper", generate_scenario, {}, None, 0),
        ("S6/psi0_-15deg", generate_scenario, {"psi0_deg": -15.0}, None, 0),
        ("S7a/length_0.20m", generate_scenario_custom_obstacle, {"obstacle_length": 0.20}, None, 0),
        ("S7b/rear_gap_0.5m", generate_front_rear_scenario, {"front_gap0": 1.0, "rear_gap": 0.5}, None, 0),
        ("S6/psi0_0deg", generate_scenario, {"psi0_deg": 0.0}, None, 0),
        ("S7a/width_0.075m", generate_scenario_custom_obstacle, {"obstacle_width": 0.075}, None, 0),
        ("S5/delay_1step", generate_scenario, {}, None, 1),
    ],
}


def main():
    out = {}
    for combo_name, targets in TARGETS.items():
        combo_flags = COMBO_V1 if combo_name == "v1" else COMBO_V2
        recs = []
        for label, gen_fn, gen_kwargs, noise_name, delay in targets:
            sub_recs = run_subgroup(label, combo_flags, gen_fn, gen_kwargs, noise_name, delay)
            recs.extend(sub_recs)
            print(f"[{combo_name}/{label}] {len(sub_recs)} solve calls", flush=True)

        times = np.array([r["run_time_ms"] for r in recs])
        iters = np.array([r["iterations"] for r in recs])
        corr = float(np.corrcoef(iters, times)[0, 1])
        top20 = sorted(recs, key=lambda r: -r["run_time_ms"])[:20]
        cap_hit_records = [r for r in recs if r["solver_status"] in
                            ("maximum iterations reached", "run time limit reached")]
        cap_hit_times = np.array([r["run_time_ms"] for r in cap_hit_records]) if cap_hit_records else np.array([])
        out[combo_name] = {
            "n_calls": len(recs),
            "corr_iterations_vs_time": corr,
            "top20": top20,
            "cap_hit_count": len(cap_hit_records),
            "cap_hit_time_stats_ms": (
                {"mean": float(cap_hit_times.mean()), "p50": float(np.percentile(cap_hit_times, 50)),
                 "p95": float(np.percentile(cap_hit_times, 95)), "max": float(cap_hit_times.max())}
                if len(cap_hit_times) else None
            ),
            "overall_max_ms": float(times.max()),
            "overall_p99_ms": float(np.percentile(times, 99)),
        }

    out_path = Path(__file__).resolve().parent / "out" / "eval_v2_timing_diagnosis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    for combo_name, o in out.items():
        print(f"\n===== {combo_name} =====")
        print(f"n_calls={o['n_calls']} corr(iter,time)={o['corr_iterations_vs_time']:.4f} "
              f"overall_max={o['overall_max_ms']:.3f}ms overall_p99={o['overall_p99_ms']:.3f}ms")
        print(f"cap_hit_count={o['cap_hit_count']} cap_hit_time_stats={o['cap_hit_time_stats_ms']}")
        print("top20 (subgroup, seed, step_in_ep, state, iterations, status, time_limit_hit, ms):")
        for r in o["top20"]:
            print(f"  {r['subgroup']:22s} seed={r['seed']:3d} step={r['step_in_episode']:3d} "
                  f"state={r['state']:14s} iter={r['iterations']:5d} status={r['solver_status']:28s} "
                  f"tl_hit={r['time_limit_hit']} ms={r['run_time_ms']:.3f}")


if __name__ == "__main__":
    main()
