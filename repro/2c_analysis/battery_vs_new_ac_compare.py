"""
2단계-C 재검토 (5): 충전기 연결 후 재실행한 2개 결과 폴더(가장 최근 생성, 2026-09-17
22:42~22:43)를 배터리 실행과 비교해 "공식 계산시간" 후보로 검토한다. 읽기 전용 분석 --
결과 폴더·baseline 코드를 수정하지 않는다.

이전 "_AC" 폴더(22:16)는 실제로는 배터리 구동이었음이 이미 확인됨(battery_vs_ac_compare.py)
-- 이번 폴더는 사용자가 충전기를 연결한 뒤 재실행한 것으로, env.json 실측으로 다시 확인한다.

사용(저장소 루트에서): .venv\\Scripts\\python.exe repro\\2c_analysis\\battery_vs_new_ac_compare.py
"""
import json
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).resolve().parents[2] / "thesis_v2" / "results"
OUT_DIR = Path(__file__).resolve().parent / "out"

PAIRS = [
    ("paper", "20260917_221415_DESKTOP-MDCKRJS_baseline_P",
     "20260917_224259_DESKTOP-MDCKRJS_baseline_P_AC"),
    ("left_obstacle", "20260917_221418_DESKTOP-MDCKRJS_baseline_P_leftobs",
     "20260917_224302_DESKTOP-MDCKRJS_baseline_P_leftobs_AC"),
]


def _load_episodes(folder, scenario):
    with open(RESULTS_DIR / folder / f"{scenario}_episodes.json", "r", encoding="utf-8") as f:
        return {ep["seed"]: ep for ep in json.load(f)}


def _load_env(folder):
    with open(RESULTS_DIR / folder / "env.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _timing_and_max_info(folder, scenario, seeds):
    all_times = []
    best = None  # (t_ms, seed, idx0based, t, state)
    first_idx_by_seed = {}
    for seed in seeds:
        npz = np.load(RESULTS_DIR / folder / f"{scenario}_seed{seed}_steps.npz", allow_pickle=True)
        times = npz["t_mpc_solve_ms"]
        states = npz["state"]
        ts = npz["t"]
        nz = np.nonzero(times > 0.0)[0]
        first_idx_by_seed[seed] = int(nz[0]) if len(nz) > 0 else None
        all_times.extend(times[times > 0.0].tolist())
        idx = int(np.argmax(times))
        t_ms = float(times[idx])
        if best is None or t_ms > best[0]:
            best = (t_ms, seed, idx, float(ts[idx]), str(states[idx]))

    stats = {"mean": None, "p50": None, "p95": None, "p99": None, "max": None, "n": 0}
    if all_times:
        arr = np.array(all_times)
        p50, p95, p99 = np.percentile(arr, [50, 95, 99])
        stats = {"mean": float(arr.mean()), "p50": float(p50), "p95": float(p95),
                  "p99": float(p99), "max": float(arr.max()), "n": len(all_times)}

    max_info = None
    max_excl_first = None
    if best is not None:
        t_ms, seed, idx, t, state = best
        is_first = (first_idx_by_seed.get(seed) == idx)
        max_info = {"t_mpc_solve_ms": t_ms, "seed": seed, "step": idx + 1, "t": t,
                    "state": state, "is_first_mpc_call_of_episode": is_first}
        # 첫 호출 제외 max: 전 seed 재스캔(첫 호출 인덱스 제외)
        best_excl = None
        for seed in seeds:
            npz = np.load(RESULTS_DIR / folder / f"{scenario}_seed{seed}_steps.npz", allow_pickle=True)
            times = npz["t_mpc_solve_ms"]
            fi = first_idx_by_seed.get(seed)
            for i, tv in enumerate(times):
                if i == fi:
                    continue
                if tv > 0.0 and (best_excl is None or tv > best_excl):
                    best_excl = float(tv)
        max_excl_first = best_excl
    return stats, max_info, max_excl_first


def check_official_condition(folder: str) -> dict:
    env = _load_env(folder)
    power = env.get("power", {})
    ac_status = power.get("ac_status")
    plan = power.get("power_plan")
    overlay = power.get("power_mode_overlay")  # 이번 실행 시점엔 없을 수 있음(기능 추가 전)
    is_ac = ac_status == "AC"
    return {
        "folder": folder, "hostname": env.get("hostname"),
        "is_official_measurement_host": env.get("is_official_measurement_host"),
        "ac_status": ac_status, "power_plan": plan, "power_mode_overlay": overlay,
        "meets_ac_condition": is_ac,
        "power_mode_overlay_recorded": overlay is not None,
        "meets_full_official_condition_determinable": (overlay is not None),
    }


def compare_pair(scenario, folder_a, folder_b):
    eps_a = _load_episodes(folder_a, scenario)
    eps_b = _load_episodes(folder_b, scenario)
    seeds = sorted(set(eps_a) & set(eps_b))
    first_diff = None
    n_diff = 0
    for seed in seeds:
        a, b = eps_a[seed], eps_b[seed]
        same = (a["outcome"] == b["outcome"] and a["finish_step"] == b["finish_step"]
                and a["transitions"] == b["transitions"])
        if not same:
            n_diff += 1
            if first_diff is None:
                first_diff = {"seed": seed, "a": a, "b": b}

    stats_a, max_a, max_excl_a = _timing_and_max_info(folder_a, scenario, seeds)
    stats_b, max_b, max_excl_b = _timing_and_max_info(folder_b, scenario, seeds)

    return {
        "scenario": scenario, "folder_battery": folder_a, "folder_new_ac": folder_b,
        "n_common_seeds": len(seeds), "n_differences": n_diff,
        "identical_control_results": (n_diff == 0),
        "first_difference": first_diff,
        "timing_battery": {**stats_a, "max_excluding_first_call": max_excl_a, "max_call_info": max_a},
        "timing_new_ac": {**stats_b, "max_excluding_first_call": max_excl_b, "max_call_info": max_b},
        "official_condition_battery": check_official_condition(folder_a),
        "official_condition_new_ac": check_official_condition(folder_b),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for scenario, folder_a, folder_b in PAIRS:
        r = compare_pair(scenario, folder_a, folder_b)
        reports.append(r)
        print(f"=== {scenario}: battery({folder_a}) vs NEW-AC({folder_b}) ===")
        print(f"  동일 seed={r['n_common_seeds']}, 차이={r['n_differences']}, "
              f"제어결과 완전동일={r['identical_control_results']}")
        if r["first_difference"]:
            print(f"  첫 차이: {r['first_difference']}")
        ta, tb = r["timing_battery"], r["timing_new_ac"]
        print(f"  timing battery: mean={ta['mean']:.4f} p50={ta['p50']:.4f} p95={ta['p95']:.4f} "
              f"p99={ta['p99']:.4f} max={ta['max']:.4f} max_excl_first={ta['max_excluding_first_call']}")
        print(f"  timing new-AC : mean={tb['mean']:.4f} p50={tb['p50']:.4f} p95={tb['p95']:.4f} "
              f"p99={tb['p99']:.4f} max={tb['max']:.4f} max_excl_first={tb['max_excluding_first_call']}")
        print(f"  official_condition(battery)={r['official_condition_battery']}")
        print(f"  official_condition(new_ac) ={r['official_condition_new_ac']}")
        print()

    out_path = OUT_DIR / "battery_vs_new_ac_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
