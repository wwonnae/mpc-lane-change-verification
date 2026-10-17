"""
1단계 dev 점검: 탐지기 없이 고장만 주입했을 때 제어 결과가 어떻게 되는지(DESIGN.md §2 "고장
크기·범위는 dev seed에서만 결정"). seed 3200~3299(SEEDS_FAULT_DEV)만 사용 — 임계값 결정에는
쓰지 않는다. 모든 고장은 시뮬레이션 주입 고장이다.

사용: python -m thesis_v2.anomaly.run_fault_dev --out-root thesis_v2/results/anomaly [--n 100]
"""
import argparse
import json
import socket
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.improved.mpc import ImprovedMPC

from . import config as an_config
from .faults import FAULT_IDS, sample_fault
from .runner import run_episode
from .scenarios import generate_anomaly_scenario

# 고장 종류별 시나리오: left_clear 고착만 좌측 장애물 시나리오(정상이면 SAFE_STOP)에서 의미가 있다
LEFTOBS_KINDS = {"left_clear_stuck"}


def run_one(seed: int, kind: str, left_obstacle: bool):
    sc = generate_anomaly_scenario(seed, left_obstacle=left_obstacle)
    spec = None if kind == "none" else sample_fault(kind, sc)
    profile = base_sensors.NOISE_PROFILES[an_config.NORMAL_NOISE_PROFILE]
    rng = np.random.default_rng((seed, an_config.NOISE_STREAM_ID))
    res = run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), fault=spec,
                      noise_profile=profile, noise_rng=rng,
                      max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)
    n_label = sum(r["label"] for r in res.alog)
    n_eff = sum(r["effective"] for r in res.alog)
    first_evade = next((t.step for t in res.transitions if t.to_state == "EVADE_L"), None)
    return dict(seed=seed, kind=kind, scenario=sc.name, outcome=res.outcome,
                total_steps=res.total_steps, finish_step=res.finish_step,
                fault=res.fault, label_steps=n_label, effective_steps=n_eff,
                first_evade_step=first_evade,
                fault_started=bool(spec is not None and spec.onset_step <= res.total_steps))


def summarize(rows):
    n = len(rows)
    c = Counter(r["outcome"] for r in rows)
    out = {"n": n, "outcomes": dict(c)}
    for key in ("충돌", "이탈", "SAFE_STOP", "타임아웃", "성공"):
        k = c.get(key, 0)
        ci = wilson_ci(k, n)
        out[key] = {"k": k, "n": n, "ci95": [ci["lo"], ci["hi"]] if ci else None}
    out["fault_started"] = sum(r["fault_started"] for r in rows)
    out["episodes_with_effective_fault"] = sum(r["effective_steps"] > 0 for r in rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--n", type=int, default=len(an_config.SEEDS_FAULT_DEV))
    ap.add_argument("--kinds", default="none,none_leftobs," + ",".join(sorted(FAULT_IDS)))
    args = ap.parse_args()
    seeds = an_config.SEEDS_FAULT_DEV[:args.n]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out_root) / f"{stamp}_{socket.gethostname()}_dev_faults"
    out.mkdir(parents=True, exist_ok=True)
    all_rows, summary = [], {}
    for kind in args.kinds.split(","):
        left = kind == "none_leftobs" or kind in LEFTOBS_KINDS
        k = "none" if kind == "none_leftobs" else kind
        rows = [run_one(s, k, left) for s in seeds]
        summary[kind] = summarize(rows)
        all_rows += [dict(r, run=kind) for r in rows]
        s = summary[kind]
        print(f"{kind:20s} n={s['n']} 충돌 {s['충돌']['k']} 이탈 {s['이탈']['k']} "
              f"SAFE_STOP {s['SAFE_STOP']['k']} 타임아웃 {s['타임아웃']['k']} 성공 {s['성공']['k']} "
              f"기타 {s['n'] - sum(s[x]['k'] for x in ('충돌','이탈','SAFE_STOP','타임아웃','성공'))} "
              f"| 고장시작 {s['fault_started']} 실효 {s['episodes_with_effective_fault']}", flush=True)
    meta = dict(purpose="1단계 dev 점검(탐지기 없음) — 시뮬레이션 주입 고장", seeds=[seeds[0], seeds[-1]],
                noise_profile=an_config.NORMAL_NOISE_PROFILE, max_steps=an_config.ANOMALY_MAX_STEPS,
                front_gap_range=an_config.ANOMALY_FRONT_GAP_RANGE, controller="improved v2")
    (out / "summary.json").write_text(json.dumps(dict(meta=meta, summary=summary), ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    (out / "episodes.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    (out / "env.json").write_text(json.dumps(collect_env_info(), ensure_ascii=False, indent=2, default=str),
                                  encoding="utf-8")
    print("saved:", out)


if __name__ == "__main__":
    main()
