"""
2단계: 탐지기 A 임계값 결정 (DESIGN.md §4, §13-3·§13-4).

정상(고장 없음) seed 3000~3199(SEEDS_NORMAL_TRAIN)만 사용한다. iteration 2(§17)부터 원거리·좌측 장애물 두 시나리오를 합친다. 고장 데이터·평가 데이터로 임계값을 정하지 않는다.
에피소드마다 최대 점수(채널 최대)와 채널별 최대 점수를 기록하고, h = 98% 분위수(method="higher")로 정한다.
채널별 분포는 기록용이다(임계값은 단일 h).

사용:
  python -m thesis_v2.anomaly.calibrate_a --out-root thesis_v2/results/anomaly [--sigma-gyro 1.0]
  python -m thesis_v2.anomaly.calibrate_a --check <결과 폴더>   # 다시 계산해 episodes.csv·thresholds.json 일치 확인
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import config as an_config
from .common import (run_anomaly_episode, threshold_from_episode_max, new_out_dir, write_env, write_csv,
                     read_csv_text, is_leftobs, normal_runs)
from .detector_a import DetectorA, CHANNELS

HEADER = ["seed", "outcome", "total_steps", "max_score", "max_channel", "max_step"] + \
         [f"max_{c}" for c in CHANNELS]


def header_for(scenarios) -> list:
    return HEADER if tuple(scenarios) == an_config.NORMAL_SCENARIOS_IT1 else ["scenario"] + HEADER


def episode_row(scenario: str, seed: int, sigma_gyro_deg: float) -> dict:
    res = run_anomaly_episode(seed, left_obstacle=is_leftobs(scenario), detector=DetectorA(sigma_gyro_deg=sigma_gyro_deg),
                              sigma_gyro_deg=sigma_gyro_deg)
    best = max(res.alog, key=lambda a: a["det_score"])  # 동점이면 먼저 나온 step
    row = dict(scenario=scenario, seed=seed, outcome=res.outcome, total_steps=res.total_steps, max_score=float(best["det_score"]),
               max_channel=best["det_channel"], max_step=best["step"])
    for c in CHANNELS:
        row[f"max_{c}"] = float(max(a["det_channel_scores"][c] for a in res.alog))
    return row


def compute(sigma_gyro_deg: float, seeds, scenarios=an_config.NORMAL_SCENARIOS_IT1):
    rows = [episode_row(sc, s, sigma_gyro_deg) for sc, s in normal_runs(seeds, scenarios)]
    h = threshold_from_episode_max([r["max_score"] for r in rows])
    n = len(rows)
    q = an_config.THRESHOLD_QUANTILE
    per_channel = {}
    for c in CHANNELS:
        v = np.array([r[f"max_{c}"] for r in rows])
        per_channel[c] = dict(q98_higher=threshold_from_episode_max(v), max=float(v.max()),
                              median=float(np.median(v)), n_positive=int((v > 0).sum()),
                              n_episodes_argmax=sum(r["max_channel"] == c for r in rows))
    thresholds = dict(
        detector="A", h=h, quantile=q, quantile_method="higher", alarm_rule="score > h",
        sigma_gyro_deg=sigma_gyro_deg, seeds=[seeds[0], seeds[-1]], n_episodes=n,
        train_episodes_over_h=sum(r["max_score"] > h for r in rows),
        outcomes={o: sum(r["outcome"] == o for r in rows) for o in sorted({r["outcome"] for r in rows})},
        per_channel=per_channel,
        per_scenario={sc: dict(n=sum(r["scenario"] == sc for r in rows),
                               over_h=sum(r["scenario"] == sc and r["max_score"] > h for r in rows))
                      for sc in scenarios},
        note="정상 seed만 사용. 모든 고장은 시뮬레이션 주입 고장(이 파일에는 고장 없음).")
    return rows, thresholds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--sigma-gyro", type=float, default=an_config.SIGMA_GYRO_DEG)
    ap.add_argument("--n", type=int, default=len(an_config.SEEDS_NORMAL_TRAIN))
    ap.add_argument("--check", default=None, help="기존 결과 폴더를 다시 계산해 비교")
    args = ap.parse_args()

    if args.check:
        d = Path(args.check)
        old = json.loads((d / "thresholds.json").read_text(encoding="utf-8"))
        seeds = list(range(old["seeds"][0], old["seeds"][1] + 1))
        scenarios = tuple(old.get("scenarios", an_config.NORMAL_SCENARIOS_IT1))
        rows, thr = compute(old["sigma_gyro_deg"], seeds, scenarios)
        tmp = d / "_check_episodes.csv"
        write_csv(tmp, header_for(scenarios), rows)
        same_csv = read_csv_text(tmp) == read_csv_text(d / "episodes.csv")
        tmp.unlink()
        same_h = thr["h"] == old["h"]
        print(f"--check {d}: episodes.csv {'일치' if same_csv else '불일치'}, h {'일치' if same_h else '불일치'}"
              f" ({old['h']!r} vs {thr['h']!r})")
        sys.exit(0 if (same_csv and same_h) else 1)

    seeds = an_config.SEEDS_NORMAL_TRAIN[:args.n]
    scenarios = an_config.NORMAL_SCENARIOS
    rows, thr = compute(args.sigma_gyro, seeds, scenarios)
    thr.update(iteration=an_config.ITERATION, scenarios=list(scenarios))
    tag = f"it{an_config.ITERATION}_threshold_a" +         ("" if args.sigma_gyro == an_config.SIGMA_GYRO_DEG else f"_sg{args.sigma_gyro:g}")
    out = new_out_dir(args.out_root, tag)
    write_csv(out / "episodes.csv", header_for(scenarios), rows)
    (out / "thresholds.json").write_text(json.dumps(thr, ensure_ascii=False, indent=2), encoding="utf-8")
    write_env(out, dict(purpose="2단계 탐지기 A 임계값(정상 seed만)"))
    print(f"h = {thr['h']:.4f} (σ_gyro={args.sigma_gyro} deg/s, n={thr['n_episodes']}, "
          f"학습 에피소드 중 h 초과 {thr['train_episodes_over_h']}/{thr['n_episodes']}, 시나리오별 {thr['per_scenario']})")
    for c, s in thr["per_channel"].items():
        print(f"  {c:4s} q98 {s['q98_higher']:8.3f}  max {s['max']:8.3f}  median {s['median']:7.3f}  "
              f"argmax {s['n_episodes_argmax']}")
    print("saved:", out)


if __name__ == "__main__":
    main()
