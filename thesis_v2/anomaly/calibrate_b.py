"""
3단계: 탐지기 B1(IF)·B2(AE) 임계값 결정 (DESIGN.md §13-4) — A와 같은 정상 seed 3000~3199, 같은 절차
(에피소드 최대 점수의 98% 분위수, method="higher", 경보는 score > h). 저장된 학습 모델로만 점수를 낸다.
iteration 2(§17)부터 원거리·좌측 장애물 정상 주행을 합쳐 하나의 h를 정한다.

사용:
  python -m thesis_v2.anomaly.calibrate_b --model-dir <stage3_train_b 폴더> --out-root thesis_v2/results/anomaly
  python -m thesis_v2.anomaly.calibrate_b --check <결과 폴더>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import config as an_config
from .common import (run_anomaly_episode, threshold_from_episode_max, new_out_dir, write_env, write_csv,
                     read_csv_text, is_leftobs, normal_runs)
from .detector_b import load_scorer, score_episode
from .features_b import Norm, ObsRecorder

KINDS = ("B1", "B2")
HEADER = ["seed", "outcome", "total_steps"] + [f"{p}_{k}" for k in KINDS for p in ("max", "max_step")]


def header_for(scenarios) -> list:
    return HEADER if tuple(scenarios) == an_config.NORMAL_SCENARIOS_IT1 else ["scenario"] + HEADER


def compute(model_dir: Path, seeds, scenarios=an_config.NORMAL_SCENARIOS_IT1):
    norm = Norm.from_json(model_dir / "norm.json")
    scorers = {k: load_scorer(k, model_dir) for k in KINDS}
    rows = []
    for scn, s in normal_runs(seeds, scenarios):
        rec = ObsRecorder()
        res = run_anomaly_episode(s, left_obstacle=is_leftobs(scn), detector=rec, record_alog=False)
        row = dict(scenario=scn, seed=s, outcome=res.outcome, total_steps=res.total_steps)
        for k, sc in scorers.items():
            v = score_episode(sc, norm, rec.obs)
            i = int(np.argmax(v))
            row[f"max_{k}"], row[f"max_step_{k}"] = float(v[i]), i + 1
        rows.append(row)
    thr = {}
    for k in KINDS:
        v = [r[f"max_{k}"] for r in rows]
        h = threshold_from_episode_max(v)
        thr[k] = dict(h=h, train_episodes_over_h=sum(x > h for x in v), max=float(max(v)), median=float(np.median(v)),
                      per_scenario={sc: dict(n=sum(r["scenario"] == sc for r in rows),
                                             over_h=sum(r["scenario"] == sc and r[f"max_{k}"] > h for r in rows))
                                    for sc in scenarios})
    meta = json.loads((model_dir / "meta.json").read_text(encoding="utf-8"))
    return rows, dict(detectors=thr, quantile=an_config.THRESHOLD_QUANTILE, quantile_method="higher",
                      alarm_rule="score > h", seeds=[seeds[0], seeds[-1]], n_episodes=len(rows),
                      model_dir=str(model_dir), if_model_sha256=meta["if_model_sha256"],
                      ae_model_sha256=meta["ae_model_sha256"], norm_sha256=meta["norm_sha256"],
                      sigma_gyro_deg=an_config.SIGMA_GYRO_DEG)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir")
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--check", default=None)
    args = ap.parse_args()

    if args.check:
        d = Path(args.check)
        old = json.loads((d / "thresholds_b.json").read_text(encoding="utf-8"))
        seeds = list(range(old["seeds"][0], old["seeds"][1] + 1))
        scenarios = tuple(old.get("scenarios", an_config.NORMAL_SCENARIOS_IT1))
        rows, thr = compute(Path(old["model_dir"]), seeds, scenarios)
        tmp = d / "_check_episodes.csv"
        write_csv(tmp, header_for(scenarios), rows)
        same = read_csv_text(tmp) == read_csv_text(d / "episodes.csv")
        tmp.unlink()
        same_h = all(thr["detectors"][k]["h"] == old["detectors"][k]["h"] for k in KINDS)
        print(f"--check {d}: episodes.csv {'일치' if same else '불일치'}, h {'일치' if same_h else '불일치'}")
        sys.exit(0 if (same and same_h) else 1)

    seeds = an_config.SEEDS_NORMAL_TRAIN
    scenarios = an_config.NORMAL_SCENARIOS
    meta = json.loads((Path(args.model_dir) / "meta.json").read_text(encoding="utf-8"))
    assert tuple(meta.get("scenarios", an_config.NORMAL_SCENARIOS_IT1)) == scenarios, "모델 학습 시나리오와 다름"
    rows, thr = compute(Path(args.model_dir), seeds, scenarios)
    thr.update(iteration=an_config.ITERATION, scenarios=list(scenarios))
    out = new_out_dir(args.out_root, f"it{an_config.ITERATION}_threshold_b")
    write_csv(out / "episodes.csv", header_for(scenarios), rows)
    (out / "thresholds_b.json").write_text(json.dumps(thr, ensure_ascii=False, indent=2), encoding="utf-8")
    write_env(out, dict(purpose="3단계 탐지기 B 임계값(정상 seed만)"))
    for k in KINDS:
        t = thr["detectors"][k]
        print(f"{k}: h = {t['h']!r}, 정상 {thr['n_episodes']}회 중 h 초과 {t['train_episodes_over_h']}회, "
              f"최대 {t['max']:.5f}, 중앙값 {t['median']:.5f}, 시나리오별 {t.get('per_scenario')}")
    print("saved:", out)


if __name__ == "__main__":
    main()
