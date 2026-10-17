"""
CLI 진입점. 논문 제출 이후 작성.
사용(개별 seed 목록): python -m thesis_v2.baseline.run --scenario paper --seeds 0 1 2 --out out_dir
사용(연속 범위, 100 에피소드 벤치마크용): python -m thesis_v2.baseline.run --scenario paper
    --seed-start 0 --n-episodes 100 --out out_dir  (--seeds와 동시 사용 불가)
"""
import argparse
import json
from pathlib import Path

from . import world
from .mpc import OSQPMPC
from .runner import run_episode
from .logger import save_json
from .envinfo import collect_env_info
from .summary import build_summary

SCENARIOS = {
    "paper": world.generate_scenario,
    "left_obstacle": world.generate_left_obstacle_scenario,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=list(SCENARIOS.keys()), required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=None,
                     help="개별 seed 목록 (--seed-start/--n-episodes와 동시 사용 불가)")
    ap.add_argument("--seed-start", type=int, default=None,
                     help="연속 범위 시작 seed (--n-episodes와 함께 사용)")
    ap.add_argument("--n-episodes", type=int, default=None,
                     help="연속 범위 개수 (--seed-start와 함께 사용)")
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--power-mode-confirmed", action="store_true",
                     help="Windows 설정 > 시스템 > 전원 > \"전원 모드\"가 \"최고 성능\"임을 "
                          "육안으로 확인했음을 env.json에 기록(공식 계산시간 조건 성립에 "
                          "필요 -- MEASURE_PLAN.md 공통 원칙, power_mode_overlay 자동 감지가 "
                          "안 되는 기기에서 이 플래그가 유일한 경로)")
    ap.add_argument("--control-delay-steps", type=int, default=0,
                     help="S5(제어 지연, ROBUSTNESS_PLAN.md). 기본값 0=지연 없음(기존과 동일)")
    args = ap.parse_args()

    if args.seeds is not None and (args.seed_start is not None or args.n_episodes is not None):
        ap.error("--seeds와 --seed-start/--n-episodes는 동시에 쓸 수 없습니다.")
    if args.seeds is not None:
        seeds = args.seeds
    elif args.seed_start is not None and args.n_episodes is not None:
        seeds = list(range(args.seed_start, args.seed_start + args.n_episodes))
    else:
        ap.error("--seeds 또는 (--seed-start와 --n-episodes) 중 하나를 지정해야 합니다.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    gen = SCENARIOS[args.scenario]
    mpc = OSQPMPC()

    env_info = collect_env_info(power_mode_confirmed=args.power_mode_confirmed)
    save_json(env_info, out_dir / "env.json")

    summaries = []
    episode_results = []
    for seed in seeds:
        scenario = gen(seed)
        result = run_episode(scenario, mpc=mpc, control_delay_steps=args.control_delay_steps)
        episode_results.append(result)
        result.logger.save_npz(out_dir / f"{args.scenario}_seed{seed}_steps.npz")
        summary = {
            "seed": result.seed,
            "scenario_name": result.scenario_name,
            "outcome": result.outcome,
            "finish_step": result.finish_step,
            "total_steps": result.total_steps,
            "transitions": [f"{tr.from_state}->{tr.to_state}@{tr.step}" for tr in result.transitions],
            "state_duration_steps": result.state_duration_steps,
            "solver_fail_count": result.solver_fail_count,
            "fallback_count": result.fallback_count,
            "rate_limit_count": result.rate_limit_count,
            "clip_count": result.clip_count,
            "clip_numerical_count": result.clip_numerical_count,
            "clip_violation_count": result.clip_violation_count,
            "delta_violation_count": result.delta_violation_count,
            "psi_violation_count": result.psi_violation_count,
            "y_violation_count": result.y_violation_count,
            "mpc_solve_ms_mean": (sum(result.mpc_solve_times_ms) / len(result.mpc_solve_times_ms)
                                   if result.mpc_solve_times_ms else 0.0),
            "mpc_solve_ms_max": (max(result.mpc_solve_times_ms) if result.mpc_solve_times_ms else 0.0),
            "observed_settle_violation": result.observed_settle_violation,
            "observed_transition_departure": result.observed_transition_departure,
        }
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False))

    save_json(summaries, out_dir / f"{args.scenario}_episodes.json")
    summary_doc = build_summary(episode_results, args.scenario, env_info)
    save_json(summary_doc, out_dir / f"{args.scenario}_summary.json")


if __name__ == "__main__":
    main()
