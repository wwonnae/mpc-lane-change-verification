"""
2단계-C 결과 분석 (3): 배터리 구동 실행 vs "AC" 실행(사용자가 전원 연결 + 최고 성능으로
전환했다고 밝힌 실행) 비교. 읽기 전용 -- 결과 폴더·baseline 코드를 수정하지 않는다.

- 에피소드별 결과 분류·전이 목록·완료 step이 완전히 같은지(다르면 첫 차이 seed/step)
- 계산시간 mean/p50/p95/p99/max 비교표
- "AC" 폴더의 env.json이 실제로 공식 조건(ac_status=="AC", 전원 계획="고성능"류)으로
  기록됐는지 검증(중요: 폴더 이름이 아니라 env.json 실측값을 기준으로 판단)

사용(저장소 루트에서): .venv\\Scripts\\python.exe repro\\2c_analysis\\battery_vs_ac_compare.py
"""
import json
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).resolve().parents[2] / "thesis_v2" / "results"
OUT_DIR = Path(__file__).resolve().parent / "out"

PAIRS = [
    ("paper", "20260917_221415_DESKTOP-MDCKRJS_baseline_P",
     "20260917_221615_DESKTOP-MDCKRJS_baseline_P_AC"),
    ("left_obstacle", "20260917_221418_DESKTOP-MDCKRJS_baseline_P_leftobs",
     "20260917_221618_DESKTOP-MDCKRJS_baseline_P_leftobs_AC"),
]


def _load_episodes(folder, scenario):
    with open(RESULTS_DIR / folder / f"{scenario}_episodes.json", "r", encoding="utf-8") as f:
        return {ep["seed"]: ep for ep in json.load(f)}


def _load_env(folder):
    with open(RESULTS_DIR / folder / "env.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _all_mpc_times(folder, scenario, seeds):
    out = []
    for seed in seeds:
        npz = np.load(RESULTS_DIR / folder / f"{scenario}_seed{seed}_steps.npz", allow_pickle=True)
        times = npz["t_mpc_solve_ms"]
        out.extend(times[times > 0.0].tolist())
    return out


def _timing_stats(times):
    if not times:
        return {"mean": None, "p50": None, "p95": None, "p99": None, "max": None, "n": 0}
    arr = np.array(times)
    p50, p95, p99 = np.percentile(arr, [50, 95, 99])
    return {"mean": float(arr.mean()), "p50": float(p50), "p95": float(p95),
            "p99": float(p99), "max": float(arr.max()), "n": len(times)}


def check_official_condition(folder: str) -> dict:
    env = _load_env(folder)
    power = env.get("power", {})
    ac_status = power.get("ac_status")
    plan = power.get("power_plan")
    is_ac = ac_status == "AC"
    # "고성능" 계열 이름(로캘 무관 대략 매칭) -- 참고용 판정, 최종 확인은 사람이 plan 문자열로.
    looks_high_perf = plan is not None and any(
        k in plan for k in ("고성능", "High performance", "최고 성능", "Ultimate", "울트라"))
    return {
        "folder": folder, "hostname": env.get("hostname"),
        "is_official_measurement_host": env.get("is_official_measurement_host"),
        "ac_status": ac_status, "power_plan": plan,
        "meets_ac_condition": is_ac,
        "power_plan_looks_high_performance": looks_high_perf,
        "meets_full_official_condition": bool(env.get("is_official_measurement_host") and is_ac),
    }


def compare_pair(scenario, folder_a, folder_b):
    eps_a = _load_episodes(folder_a, scenario)
    eps_b = _load_episodes(folder_b, scenario)
    seeds = sorted(set(eps_a) & set(eps_b))
    missing_a = sorted(set(eps_b) - set(eps_a))
    missing_b = sorted(set(eps_a) - set(eps_b))

    first_diff = None
    n_diff = 0
    for seed in seeds:
        a, b = eps_a[seed], eps_b[seed]
        same = (a["outcome"] == b["outcome"] and a["finish_step"] == b["finish_step"]
                and a["transitions"] == b["transitions"])
        if not same:
            n_diff += 1
            if first_diff is None:
                first_diff = {
                    "seed": seed,
                    "a_outcome": a["outcome"], "b_outcome": b["outcome"],
                    "a_finish_step": a["finish_step"], "b_finish_step": b["finish_step"],
                    "a_transitions": a["transitions"], "b_transitions": b["transitions"],
                }

    times_a = _all_mpc_times(folder_a, scenario, seeds)
    times_b = _all_mpc_times(folder_b, scenario, seeds)

    return {
        "scenario": scenario,
        "folder_a_battery": folder_a,
        "folder_b_ac": folder_b,
        "n_common_seeds": len(seeds),
        "missing_in_a": missing_a,
        "missing_in_b": missing_b,
        "n_differences": n_diff,
        "identical_control_results": (n_diff == 0 and not missing_a and not missing_b),
        "first_difference": first_diff,
        "timing_battery": _timing_stats(times_a),
        "timing_ac": _timing_stats(times_b),
        "official_condition_a": check_official_condition(folder_a),
        "official_condition_b": check_official_condition(folder_b),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for scenario, folder_a, folder_b in PAIRS:
        r = compare_pair(scenario, folder_a, folder_b)
        reports.append(r)
        print(f"=== {scenario}: battery({folder_a}) vs AC({folder_b}) ===")
        print(f"  동일 seed 수={r['n_common_seeds']}, 다른 seed 수={r['n_differences']}, "
              f"제어결과 완전동일={r['identical_control_results']}")
        if r["first_difference"]:
            print(f"  첫 차이: {r['first_difference']}")
        ta, tb = r["timing_battery"], r["timing_ac"]
        print(f"  timing battery: mean={ta['mean']:.4f} p50={ta['p50']:.4f} p95={ta['p95']:.4f} "
              f"p99={ta['p99']:.4f} max={ta['max']:.4f} (n={ta['n']})")
        print(f"  timing AC     : mean={tb['mean']:.4f} p50={tb['p50']:.4f} p95={tb['p95']:.4f} "
              f"p99={tb['p99']:.4f} max={tb['max']:.4f} (n={tb['n']})")
        print(f"  official_condition(A, battery folder)={r['official_condition_a']}")
        print(f"  official_condition(B, 'AC' folder)   ={r['official_condition_b']}")
        print()

    out_path = OUT_DIR / "battery_vs_ac_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
