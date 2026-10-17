"""
dev 점검(2단계 A, 3단계 B1·B2): 확정된 임계값 h로 탐지기가 고장 dev 데이터(seed 3200~3299)에서 어떻게 반응하는지 본다.
**보고서 수치가 아니다**(평가는 4000~4099에서 1회). 이 결과로 h·κ·σ·모델 등 어떤 값도 바꾸지 않는다 —
바꾸려면 사유를 기록하고 정상 데이터로 임계값을 다시 정한다. 모든 고장은 시뮬레이션 주입 고장이다.

사용:
  python -m thesis_v2.anomaly.dev_detect --detector A --thresholds <stage2_threshold_a 폴더>
  python -m thesis_v2.anomaly.dev_detect --detector B1 --thresholds <stage3_threshold_b 폴더>   (B2 같음, 모델은 thresholds_b.json의 model_dir)
  python -m thesis_v2.anomaly.dev_detect --check <결과 폴더>
  (dev_detect_a는 --detector A의 호환용 진입점 — 2단계 기록의 명령 유지)
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from thesis_v2.baseline.summary import wilson_ci

from . import config as an_config
from .common import run_anomaly_episode, new_out_dir, write_env, write_csv, read_csv_text
from .detector_a import DetectorA
from .detector_b import load_scorer, score_episode
from .features_b import Norm, ObsRecorder
from . import hybrid as hybrid_mod

KINDS = ["lidar_freeze", "lidar_spike", "lidar_dropout", "ir_stuck", "ir_dropout", "right_clear_stuck",
         "steer_delay", "steer_stuck", "left_clear_stuck"]
LEFTOBS_KINDS = {"left_clear_stuck"}
RUNS = ["none", "none_leftobs"] + KINDS
GRACE_STEPS = 10  # §13-5 탐지 유예: onset+duration+10 (영구 고장은 에피소드 끝까지)
FAILURE_OUTCOMES = {"충돌", "이탈"}

HEADER = ["run", "seed", "outcome", "total_steps", "finish_step", "onset", "duration", "first_alarm",
          "first_alarm_channel", "alarm_before_onset", "detected", "delay_steps", "alarm_before_failure",
          "max_score"]


def _episode_scores(run: str, seed: int, det_cfg: dict):
    """(결과, step별 점수, step별 경보 채널). A는 온라인 실행, B는 관측을 기록해 저장 모델로 오프라인 점수
    (탐지기는 관찰 전용이므로 두 방식의 점수가 같다 — tests/test_detector_b.py)."""
    kind = None if run.startswith("none") else run
    left = run == "none_leftobs" or run in LEFTOBS_KINDS
    if det_cfg["detector"] == "A":
        res = run_anomaly_episode(seed, kind=kind, left_obstacle=left,
                                  detector=DetectorA(threshold=det_cfg["h"], sigma_gyro_deg=det_cfg["sigma"]),
                                  sigma_gyro_deg=det_cfg["sigma"])
        return res, [a["det_score"] for a in res.alog], [a["det_channel"] for a in res.alog]
    if det_cfg["detector"] == "HYBRID":
        rec = hybrid_mod.HybridObsRecorder()
        res = run_anomaly_episode(seed, kind=kind, left_obstacle=left, detector=rec, record_alog=False)
        scores = hybrid_mod.score_episode(det_cfg["scorer"], det_cfg["norm"], rec.obs, rec.a_res)
        return res, [float(v) for v in scores], [""] * len(scores)
    rec = ObsRecorder()
    res = run_anomaly_episode(seed, kind=kind, left_obstacle=left, detector=rec, record_alog=False)
    scores = score_episode(det_cfg["scorer"], det_cfg["norm"], rec.obs)
    return res, [float(v) for v in scores], [""] * len(scores)


def episode_row(run: str, seed: int, det_cfg: dict) -> dict:
    h = det_cfg["h"]
    res, scores, chans = _episode_scores(run, seed, det_cfg)
    alarm_steps = [k + 1 for k, v in enumerate(scores) if v > h]
    fa = alarm_steps[0] if alarm_steps else None
    fa_ch = chans[fa - 1] if fa else None
    row = dict(run=run, seed=seed, outcome=res.outcome, total_steps=res.total_steps, finish_step=res.finish_step,
               onset=None, duration=None, first_alarm=fa, first_alarm_channel=fa_ch, alarm_before_onset=None,
               detected=None, delay_steps=None, alarm_before_failure=None,
               max_score=float(max(scores)))
    if res.fault is not None:
        on, dur = res.fault["onset_step"], res.fault["duration_steps"]
        end = res.total_steps if dur is None else min(res.total_steps, on + dur - 1 + GRACE_STEPS)
        in_win = [k for k in alarm_steps if on <= k <= end]
        row.update(onset=on, duration=dur, alarm_before_onset=bool(fa is not None and fa < on),
                   detected=bool(in_win), delay_steps=(in_win[0] - on) if in_win else None)
        if res.outcome in FAILURE_OUTCOMES:
            row["alarm_before_failure"] = bool(in_win and in_win[0] <= res.total_steps - 1)
    return row


def summarize(rows):
    out = {}
    for run in RUNS:
        rs = [r for r in rows if r["run"] == run]
        if not rs:
            continue
        n = len(rs)
        s = dict(n=n, outcomes=dict(Counter(r["outcome"] for r in rs)))
        if run.startswith("none"):
            k = sum(r["first_alarm"] is not None for r in rs)
            ci = wilson_ci(k, n)
            s["false_alarm_episodes"] = dict(k=k, n=n, ci95=[ci["lo"], ci["hi"]] if ci else None)
        else:
            started = [r for r in rs if r["onset"] <= r["total_steps"]]
            k = sum(bool(r["detected"]) for r in started)
            ci = wilson_ci(k, len(started))
            delays = sorted(r["delay_steps"] for r in started if r["detected"])
            fail = [r for r in rs if r["outcome"] in FAILURE_OUTCOMES]
            s.update(fault_started=len(started), detected=k,
                     detected_ci95=[ci["lo"], ci["hi"]] if ci else None,
                     delay_median=(delays[len(delays) // 2] if delays else None),
                     delay_p90=(delays[min(len(delays) - 1, int(0.9 * len(delays)))] if delays else None),
                     alarm_before_onset=sum(bool(r["alarm_before_onset"]) for r in rs),
                     first_alarm_channels=dict(Counter(r["first_alarm_channel"] for r in rs if r["detected"])),
                     failures=len(fail), alarm_before_failure=sum(bool(r["alarm_before_failure"]) for r in fail))
        out[run] = s
    return out


def make_det_cfg(detector: str, h: float, sigma: float, model_dir=None) -> dict:
    cfg = dict(detector=detector, h=h, sigma=sigma)
    if detector == "HYBRID":
        assert sigma == an_config.SIGMA_GYRO_DEG  # B·하이브리드는 σ=1에서만 학습(§13-5·§20)
        from .detector_b import IFScorer
        cfg.update(scorer=IFScorer.load(Path(model_dir)), norm=hybrid_mod.Norm.from_json(Path(model_dir) / "norm.json"))
    elif detector != "A":
        assert sigma == an_config.SIGMA_GYRO_DEG  # B는 σ=1에서만 학습(§13-5)
        cfg.update(scorer=load_scorer(detector, Path(model_dir)), norm=Norm.from_json(Path(model_dir) / "norm.json"))
    return cfg


def compute(det_cfg: dict, seeds):
    return [episode_row(run, s, det_cfg) for run in RUNS for s in seeds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", default="A", choices=["A", "B1", "B2", "HYBRID"])
    ap.add_argument("--thresholds", help="calibrate_a(A), calibrate_b(B1·B2) 또는 calibrate_hybrid(HYBRID) 결과 폴더")
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--n", type=int, default=len(an_config.SEEDS_FAULT_DEV))
    ap.add_argument("--check", default=None)
    args = ap.parse_args()

    if args.check:
        d = Path(args.check)
        meta = json.loads((d / "summary.json").read_text(encoding="utf-8"))["meta"]
        seeds = list(range(meta["seeds"][0], meta["seeds"][1] + 1))
        rows = compute(make_det_cfg(meta.get("detector", "A"), meta["h"], meta["sigma_gyro_deg"],
                                    meta.get("model_dir")), seeds)
        tmp = d / "_check_episodes.csv"
        write_csv(tmp, HEADER, rows)
        same = read_csv_text(tmp) == read_csv_text(d / "episodes.csv")
        tmp.unlink()
        print(f"--check {d}: episodes.csv {'일치' if same else '불일치'}")
        sys.exit(0 if same else 1)

    model_dir = None
    if args.detector == "A":
        thr = json.loads((Path(args.thresholds) / "thresholds.json").read_text(encoding="utf-8"))
        h, sigma = thr["h"], thr["sigma_gyro_deg"]
    elif args.detector == "HYBRID":
        thr = json.loads((Path(args.thresholds) / "thresholds_hybrid.json").read_text(encoding="utf-8"))
        h, sigma, model_dir = thr["h"], thr["sigma_gyro_deg"], thr["model_dir"]
    else:
        thr = json.loads((Path(args.thresholds) / "thresholds_b.json").read_text(encoding="utf-8"))
        h, sigma, model_dir = thr["detectors"][args.detector]["h"], thr["sigma_gyro_deg"], thr["model_dir"]
    seeds = an_config.SEEDS_FAULT_DEV[:args.n]
    assert set(seeds) <= set(an_config.SEEDS_FAULT_DEV)
    rows = compute(make_det_cfg(args.detector, h, sigma, model_dir), seeds)
    summary = summarize(rows)
    it = thr.get("iteration", 1)
    if it == 1:
        stage = "stage2_dev_detect_a" if args.detector == "A" else f"stage3_dev_detect_{args.detector.lower()}"
    else:
        stage = f"it{it}_dev_detect_{args.detector.lower()}"
    out = new_out_dir(args.out_root, stage)
    write_csv(out / "episodes.csv", HEADER, rows)
    meta = dict(purpose="dev 점검(보고서 수치 아님) — 시뮬레이션 주입 고장", detector=args.detector, h=h,
                sigma_gyro_deg=sigma, thresholds_dir=str(args.thresholds), seeds=[seeds[0], seeds[-1]],
                grace_steps=GRACE_STEPS, model_dir=model_dir, iteration=it)
    (out / "summary.json").write_text(json.dumps(dict(meta=meta, summary=summary), ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    write_env(out, dict(purpose=meta["purpose"]))
    for run, s in summary.items():
        if run.startswith("none"):
            print(f"{run:18s} 정상 {s['n']}회 중 경보 {s['false_alarm_episodes']['k']}회  결과 {s['outcomes']}")
        else:
            print(f"{run:18s} 고장 시작 {s['fault_started']}회 중 탐지 {s['detected']}회, 지연 중앙값 {s['delay_median']} "
                  f"p90 {s['delay_p90']} step, onset 전 경보 {s['alarm_before_onset']}, 채널 {s['first_alarm_channels']}, "
                  f"충돌·이탈 {s['failures']} 중 그 전 경보 {s['alarm_before_failure']}")
    print("saved:", out)


if __name__ == "__main__":
    main()
