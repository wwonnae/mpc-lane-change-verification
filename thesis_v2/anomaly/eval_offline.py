"""
오프라인 평가 — DESIGN.md §7·§13-5(+§19 보완). seed 4000~4099(SEEDS_OFFLINE_EVAL)에 확정 코드로 **1회만** 실행한다.
그 전에 `--seeds dev`로 dev 대역(3200~3299, SEEDS_FAULT_DEV)에 돌려 단위 테스트·결정성(`--check`)을 확인한다.

**관찰 전용(P0)으로 에피소드당 시뮬레이션을 1회만 실행**하고(§13-5), 같은 로그(관측 + 탐지기 A의 원시 잔차 +
A의 온라인 CUSUM 점수/채널 — `FullRecorder`)에 B1·B2·하이브리드를 오프라인으로 적용한다. A는 그 자체로 이미
이번 1회 시뮬레이션 안에서 정상적으로 동작한 결과(threshold=inf로 경보만 내지 않을 뿐 CUSUM은 그대로 진행)를
쓰므로 "탐지기 간 같은 데이터"(§13-5) 조건을 만족한다.

탐지기 4종: A(iteration 3, §18, σ_gyro=1.0 주 조건) / B1·B2(iteration 2, §17, 건드리지 않음) / HYBRID(iteration 3, §20).
σ_gyro 민감도 확장(§13-5, {0.05, 1, 5}°/s)은 **A만**(오늘 지시 [2], §13-3 민감도는 A·하이브리드만이라 했으나
하이브리드는 σ별 재학습을 오늘 하지 않았으므로 이번 구현은 A로 한정 — 이 축소를 아래 env.json·출력에 명시한다).

사용:
  python -m thesis_v2.anomaly.eval_offline --seeds dev \
      --a-thresholds <it3_threshold_a> --a-thresholds-sg0.05 <...> --a-thresholds-sg5 <...> \
      --b-thresholds <it2_threshold_b> --hybrid-thresholds <it3_threshold_hybrid> \
      --out-root thesis_v2/results/anomaly
  python -m thesis_v2.anomaly.eval_offline --check <결과 폴더>
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from thesis_v2.baseline.summary import wilson_ci

from . import config as an_config
from .common import run_anomaly_episode, new_out_dir, write_env, write_csv, read_csv_text, git_info
from .detector_a import DetectorA, CHANNELS as A_CHANNELS
from .detector_b import load_scorer
from .detector_b import score_episode as score_episode_b
from .features_b import Norm as NormB, ObsRecorder
from . import hybrid as hybrid_mod
from .dev_detect import KINDS, LEFTOBS_KINDS, RUNS, GRACE_STEPS, FAILURE_OUTCOMES
from .runner import DetectorObs, DetectorOutput

DETECTORS = ["A", "B1", "B2", "HYBRID"]
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 0
HEADER = ["run", "seed", "outcome", "total_steps", "onset", "duration", "first_alarm", "first_alarm_channel",
          "alarm_before_onset", "detected", "delay_steps", "alarm_before_failure", "max_score", "separation_ok"]

# ---- §13-5 "분리 기대 채널 표" 동결(2026-10-01, ir_dropout 추가는 §19-6: iteration 3, 평가 실행 전) ----
EXPECTED_SENSOR = {
    "lidar_freeze": {"fg", "trk"}, "lidar_spike": {"fg", "trk"}, "lidar_dropout": {"fg", "trk"},
    "ir_stuck": {"ey", "ir_miss"}, "ir_dropout": {"ey", "ir_miss"},
    "right_clear_stuck": {"rc"}, "left_clear_stuck": {"lc"},
    "steer_delay": {"psi"}, "steer_stuck": {"psi"},
}


def _expected_fine(kind: str, fault_meta: dict) -> str:
    if kind == "lidar_freeze":
        return "fg"
    if kind == "lidar_dropout":
        return "trk"
    if kind == "lidar_spike":
        return "trk" if fault_meta.get("up") else "fg"
    if kind == "ir_stuck":
        return "ey"
    if kind == "ir_dropout":
        return "ir_miss"  # iteration 3, §18·§19-6
    if kind == "right_clear_stuck":
        return "rc"
    if kind == "left_clear_stuck":
        return "lc"
    if kind in ("steer_delay", "steer_stuck"):
        return "psi"
    raise AssertionError(kind)


class FullRecorder:
    """관찰 전용 탐지기. 1회 시뮬레이션으로 (1) A의 실제 온라인 점수·채널(§18 그대로, threshold=inf라 경보만
    안 낼 뿐 CUSUM·추적기는 정상 진행) (2) A의 원시 잔차(하이브리드 특징용) (3) B1·B2·HYBRID 오프라인 채점에
    필요한 관측(obs)을 전부 기록한다 — "같은 로그에 모든 탐지기 적용"(§13-5)."""

    def __init__(self, sigma_gyro_deg: float = an_config.SIGMA_GYRO_DEG):
        self._det_a = DetectorA(sigma_gyro_deg=sigma_gyro_deg)
        self.obs: List[DetectorObs] = []
        self.a_res: List[dict] = []
        self.a_score: List[float] = []
        self.a_channel: List[str] = []

    def reset(self) -> None:
        self._det_a.reset()
        self.obs, self.a_res, self.a_score, self.a_channel = [], [], [], []

    def update(self, obs: DetectorObs) -> DetectorOutput:
        out = self._det_a.update(obs)
        self.obs.append(obs)
        self.a_res.append(out.residuals)
        self.a_score.append(out.score)
        self.a_channel.append(out.channel)
        return DetectorOutput(score=0.0, alarm=False)


def run_record(run: str, seed: int, sigma_inject: float = an_config.SIGMA_GYRO_DEG,
              sigma_assumed: Optional[float] = None) -> dict:
    """sigma_inject: 실제 주입 자이로 노이즈(`run_anomaly_episode`의 `sigma_gyro_deg`, 시뮬레이션).
    sigma_assumed: 탐지기 정규화(`DetectorA(sigma_gyro_deg=...)`) — None이면 sigma_inject와 같게(§22 "σ 일치").
    둘을 다르게 주면 §22-1 "σ 불일치 민감도"(탐지기는 1.0 가정 고정, 실제 주입만 바꿈)가 된다."""
    if sigma_assumed is None:
        sigma_assumed = sigma_inject
    kind = None if run.startswith("none") else run
    left = run == "none_leftobs" or run in LEFTOBS_KINDS
    rec = FullRecorder(sigma_gyro_deg=sigma_assumed)
    res = run_anomaly_episode(seed, kind=kind, left_obstacle=left, detector=rec, record_alog=False,
                              sigma_gyro_deg=sigma_inject)
    return dict(run=run, seed=seed, outcome=res.outcome, total_steps=res.total_steps, fault=res.fault,
               obs=rec.obs, a_res=rec.a_res, a_score=rec.a_score, a_channel=rec.a_channel)


def label_array(rec: dict) -> np.ndarray:
    n = rec["total_steps"]
    lab = np.zeros(n, dtype=np.int64)
    f = rec["fault"]
    if f is not None:
        on, dur = f["onset_step"], f["duration_steps"]
        end = n + 1 if dur is None else on + dur  # k < end
        for k in range(on, min(end, n + 1)):
            lab[k - 1] = 1
    return lab


def detector_scores(rec: dict, detector: str, models: dict) -> np.ndarray:
    if detector == "A":
        return np.asarray(rec["a_score"], dtype=np.float64)
    if detector == "HYBRID":
        return hybrid_mod.score_episode(models["HYBRID"]["scorer"], models["HYBRID"]["norm"],
                                        rec["obs"], rec["a_res"])
    return score_episode_b(models[detector]["scorer"], models[detector]["norm"], rec["obs"])


def episode_row(rec: dict, detector: str, models: dict, h: float) -> dict:
    scores = detector_scores(rec, detector, models)
    channels = rec["a_channel"] if detector == "A" else [""] * len(scores)
    alarm_steps = [k + 1 for k, v in enumerate(scores) if v > h]
    fa = alarm_steps[0] if alarm_steps else None
    fa_ch = channels[fa - 1] if (fa and detector == "A") else None
    row = dict(run=rec["run"], seed=rec["seed"], outcome=rec["outcome"], total_steps=rec["total_steps"],
               onset=None, duration=None, first_alarm=fa, first_alarm_channel=fa_ch,
               alarm_before_onset=None, detected=None, delay_steps=None, alarm_before_failure=None,
               max_score=float(np.max(scores)) if len(scores) else 0.0,
               separation_ok=None)
    f = rec["fault"]
    if f is not None:
        on, dur = f["onset_step"], f["duration_steps"]
        end = rec["total_steps"] if dur is None else min(rec["total_steps"], on + dur - 1 + GRACE_STEPS)
        in_win = [k for k in alarm_steps if on <= k <= end]
        row.update(onset=on, duration=dur, alarm_before_onset=bool(fa is not None and fa < on),
                   detected=bool(in_win), delay_steps=(in_win[0] - on) if in_win else None)
        if rec["outcome"] in FAILURE_OUTCOMES:
            row["alarm_before_failure"] = bool(in_win and in_win[0] <= rec["total_steps"] - 1)
        if detector == "A" and in_win:
            exp_fine = _expected_fine(rec["run"], f.get("meta", {}))
            first_ch = channels[in_win[0] - 1]
            row["separation_ok"] = bool(first_ch == exp_fine)
    return row


# ---------------- 집계 ----------------

def wilson(k: int, n: int) -> Optional[list]:
    ci = wilson_ci(k, n)
    return [ci["lo"], ci["hi"]] if ci else None


def bootstrap_episode_stat(n_episodes: int, stat_fn, n_boot: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED):
    """stat_fn(idx: np.ndarray[int]) -> float, idx는 에피소드 인덱스(복원추출). 2.5/97.5 분위수를 돌려준다."""
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_episodes, size=n_episodes)
        v = stat_fn(idx)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vals.append(v)
    if not vals:
        return None
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def step_prf1(labels_list: List[np.ndarray], scores_list: List[np.ndarray], h: float, idx=None):
    if idx is not None:
        labels_list = [labels_list[i] for i in idx]
        scores_list = [scores_list[i] for i in idx]
    lab = np.concatenate(labels_list) if labels_list else np.zeros(0)
    sc = np.concatenate(scores_list) if scores_list else np.zeros(0)
    pred = sc > h
    tp = int(np.sum((lab == 1) & pred))
    fp = int(np.sum((lab == 0) & pred))
    fn = int(np.sum((lab == 1) & ~pred))
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * prec * rec / (prec + rec)) if (prec is not None and rec is not None and (prec + rec) > 0) else None
    return dict(tp=tp, fp=fp, fn=fn, precision=prec, recall=rec, f1=f1)


def delay_stats(rows: List[dict]):
    delays = sorted(r["delay_steps"] for r in rows if r.get("detected") and r["delay_steps"] is not None)
    if not delays:
        return None, None
    med = delays[len(delays) // 2]
    p90 = delays[min(len(delays) - 1, int(np.ceil(0.9 * len(delays))) - 1)]
    return med, p90


def auc_from_scores(pos: np.ndarray, neg: np.ndarray) -> Optional[float]:
    """Mann-Whitney U 기반 AUC(외부 라이브러리 없이). pos·neg는 점수 배열."""
    if len(pos) == 0 or len(neg) == 0:
        return None
    all_s = np.concatenate([pos, neg])
    order = np.argsort(all_s, kind="mergesort")
    ranks = np.empty(len(all_s))
    ranks[order] = np.arange(1, len(all_s) + 1)
    # 동점 처리: 평균 랭크
    sorted_s = all_s[order]
    i = 0
    while i < len(sorted_s):
        j = i
        while j + 1 < len(sorted_s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        if j > i:
            avg = ranks[order[i:j + 1]].mean()
            ranks[order[i:j + 1]] = avg
        i = j + 1
    r_pos = ranks[:len(pos)].sum()
    n1, n2 = len(pos), len(neg)
    u1 = r_pos - n1 * (n1 + 1) / 2.0
    return float(u1 / (n1 * n2))


def ap_from_scores(labels: np.ndarray, scores: np.ndarray) -> Optional[float]:
    """Average precision(= PR 곡선 아래 면적, 표준 랭킹 기반 정의). 외부 라이브러리 없이."""
    n_pos = int(labels.sum())
    if n_pos == 0:
        return None
    order = np.argsort(-scores, kind="mergesort")
    lab_sorted = labels[order]
    tp_cum = np.cumsum(lab_sorted)
    precision = tp_cum / (np.arange(len(lab_sorted)) + 1)
    return float(np.sum(precision * lab_sorted) / n_pos)


def load_models(b_dir: str, hybrid_dir: str) -> dict:
    """B1·B2는 같은 norm.json(train_b.py 산출, 하나뿐)을 쓴다(calibrate_b.py와 같은 관례)."""
    b_norm = NormB.from_json(Path(b_dir) / "norm.json")
    hy_norm = hybrid_mod.Norm.from_json(Path(hybrid_dir) / "norm.json")
    return {
        "B1": dict(scorer=load_scorer("B1", Path(b_dir)), norm=b_norm),
        "B2": dict(scorer=load_scorer("B2", Path(b_dir)), norm=b_norm),
        "HYBRID": dict(scorer=load_scorer("B1", Path(hybrid_dir)), norm=hy_norm),
    }


MISMATCH_SIGMA_TRUE = {"mismatch0.5": 0.5, "mismatch2": 2.0, "mismatch5": 5.0}  # §22-1, 오늘 지시


def compute(seeds: List[int], h_by_detector: Dict[str, float], model_dirs: dict,
           sigma_variants: Dict[str, float]) -> dict:
    """sigma_variants: {"main": 1.0, "sg0.05": 0.05, "sg5": 5.0} — σ 일치 민감도(A만, §13-5·오늘 지시 [2]).
    §22-1 "σ 불일치 민감도"(탐지기 가정 σ=1.0·임계값 고정, 실제 주입만 {0.5,2,5}로 바꿈)는 별도로 계산한다."""
    models = load_models(model_dirs["B"], model_dirs["HYBRID"])
    # 메인(σ=1.0) 1회 실행으로 A·B1·B2·HYBRID 전부 채점(§13-5 "같은 로그").
    records = {(run, s): run_record(run, s, sigma_inject=an_config.SIGMA_GYRO_DEG)
              for run in RUNS for s in seeds}
    rows = {det: [] for det in DETECTORS}
    labels_by_kind_det: Dict[str, Dict[str, list]] = {det: defaultdict(list) for det in DETECTORS}
    scores_by_kind_det: Dict[str, Dict[str, list]] = {det: defaultdict(list) for det in DETECTORS}
    for (run, s), rec in records.items():
        lab = label_array(rec)
        for det in DETECTORS:
            r = episode_row(rec, det, models, h_by_detector[det])
            rows[det].append(r)
            sc = detector_scores(rec, det, models)
            labels_by_kind_det[det][run].append(lab)
            scores_by_kind_det[det][run].append(sc)

    # A의 σ 일치 민감도(추가 실행 — §13-5 확장, 오늘 지시 [2]: A만. 정규화·임계값도 같이 바꿈)
    sens_rows = {}
    for tag, sigma in sigma_variants.items():
        if tag == "main":
            continue
        h = h_by_detector[f"A_{tag}"]
        rs = []
        for run in RUNS:
            for s in seeds:
                rec = run_record(run, s, sigma_inject=sigma, sigma_assumed=sigma)
                rs.append(episode_row(rec, "A", {}, h))
        sens_rows[tag] = rs

    # A의 σ 불일치 민감도(§22-1, 추가 실행): 정규화·임계값은 1.0 고정, 실제 주입만 바꿈
    mismatch_rows = {}
    h_main = h_by_detector["A"]
    for tag, sigma_true in MISMATCH_SIGMA_TRUE.items():
        rs = []
        for run in RUNS:
            for s in seeds:
                rec = run_record(run, s, sigma_inject=sigma_true, sigma_assumed=an_config.SIGMA_GYRO_DEG)
                rs.append(episode_row(rec, "A", {}, h_main))
        mismatch_rows[tag] = rs

    return dict(rows=rows, labels=labels_by_kind_det, scores=scores_by_kind_det, sens_rows=sens_rows,
               mismatch_rows=mismatch_rows, records=records)


# ---------------- 요약(§7·§13-5 지표) ----------------

HARMFUL_KINDS = {"lidar_freeze", "lidar_dropout", "ir_stuck", "steer_delay", "steer_stuck", "left_clear_stuck"}
HARMLESS_KINDS = {"lidar_spike", "ir_dropout", "right_clear_stuck"}  # §19-2


def _pool(labels_list, scores_list):
    return (np.concatenate(labels_list) if labels_list else np.zeros(0),
            np.concatenate(scores_list) if scores_list else np.zeros(0))


def summarize_detector(det: str, h: float, rows: List[dict], labels_by_kind: Dict[str, list],
                       scores_by_kind: Dict[str, list], records: dict) -> dict:
    out = {"h": h}
    # 정상 오경보(에피소드 단위 + 스텝 단위)
    for run, key in (("none", "normal_far"), ("none_leftobs", "normal_leftobs")):
        rs = [r for r in rows if r["run"] == run]
        k = sum(r["first_alarm"] is not None for r in rs)
        lab, sc = _pool(labels_by_kind[run], scores_by_kind[run])
        out[key] = dict(episodes=dict(k=k, n=len(rs), ci95=wilson(k, len(rs))),
                        step_false_alarm_rate=float(np.mean(sc > h)) if len(sc) else None,
                        step_n=int(len(sc)))

    per_kind = {}
    for kind in KINDS:
        rs = [r for r in rows if r["run"] == kind]
        started = [r for r in rs if r["onset"] is not None and r["onset"] <= r["total_steps"]]
        k_det = sum(bool(r["detected"]) for r in started)
        n_started = len(started)
        med, p90 = delay_stats(started)
        lab_list, sc_list = labels_by_kind[kind], scores_by_kind[kind]
        prf1 = step_prf1(lab_list, sc_list, h)

        def _f1_stat(idx):
            return step_prf1(lab_list, sc_list, h, idx)["f1"]

        def _delay_stat(idx):
            sub = [started[i] for i in idx if i < len(started)]
            m, _ = delay_stats(sub)
            return float(m) if m is not None else None

        f1_ci = bootstrap_episode_stat(len(lab_list), _f1_stat) if lab_list else None
        delay_ci = bootstrap_episode_stat(len(started), _delay_stat) if started else None

        fail = [r for r in rs if r["outcome"] in FAILURE_OUTCOMES]
        lead_times, no_warning = [], 0
        for r in fail:
            if r["detected"] and r["onset"] is not None:
                first_in_win = r["onset"] + r["delay_steps"]
                lead = r["total_steps"] - first_in_win
                if lead >= 0:
                    lead_times.append(lead)
                else:
                    no_warning += 1  # 경보가 사고 이후
            else:
                no_warning += 1
        sep = [r["separation_ok"] for r in started if r.get("separation_ok") is not None]
        per_kind[kind] = dict(
            harmful=(kind in HARMFUL_KINDS),
            fault_started=n_started, detected=k_det, detected_ci95=wilson(k_det, n_started),
            delay_median=med, delay_p90=p90, delay_median_ci95=delay_ci,
            alarm_before_onset=sum(bool(r["alarm_before_onset"]) for r in rs),
            step_prf1=prf1, step_f1_ci95=f1_ci,
            failures=len(fail), alarm_before_failure=sum(bool(r["alarm_before_failure"]) for r in fail),
            lead_time_steps=dict(n=len(lead_times), median=(float(np.median(lead_times)) if lead_times else None),
                                 min=(float(np.min(lead_times)) if lead_times else None), no_warning=no_warning),
            separation_accuracy=(dict(k=sum(sep), n=len(sep), ci95=wilson(sum(sep), len(sep)))
                                 if (det == "A" and sep) else None),
        )
    out["per_kind"] = per_kind
    out["harmful_detected"] = _combine_rate(per_kind, HARMFUL_KINDS)
    out["harmless_detected"] = _combine_rate(per_kind, HARMLESS_KINDS)

    # ROC(에피소드, 정상 vs 고장 최대점수)·PR(스텝) — 확장, 전체 풀링
    pos_ep = [r["max_score"] for r in rows if r["run"] in KINDS]
    neg_ep = [r["max_score"] for r in rows if r["run"] in ("none", "none_leftobs")]
    auc = auc_from_scores(np.asarray(pos_ep), np.asarray(neg_ep))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    auc_vals = []
    pos_a, neg_a = np.asarray(pos_ep), np.asarray(neg_ep)
    for _ in range(N_BOOTSTRAP):
        pi = rng.integers(0, len(pos_a), size=len(pos_a)) if len(pos_a) else np.zeros(0, dtype=int)
        ni = rng.integers(0, len(neg_a), size=len(neg_a)) if len(neg_a) else np.zeros(0, dtype=int)
        v = auc_from_scores(pos_a[pi], neg_a[ni]) if len(pos_a) and len(neg_a) else None
        if v is not None:
            auc_vals.append(v)
    auc_ci = [float(np.percentile(auc_vals, 2.5)), float(np.percentile(auc_vals, 97.5))] if auc_vals else None

    all_lab_list = sum((labels_by_kind[r] for r in RUNS), [])
    all_sc_list = sum((scores_by_kind[r] for r in RUNS), [])
    lab_all, sc_all = _pool(all_lab_list, all_sc_list)
    ap = ap_from_scores(lab_all, sc_all)
    ap_vals = []
    n_ep_all = len(all_lab_list)
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n_ep_all, size=n_ep_all)
        lab_b, sc_b = _pool([all_lab_list[i] for i in idx], [all_sc_list[i] for i in idx])
        v = ap_from_scores(lab_b, sc_b)
        if v is not None:
            ap_vals.append(v)
    ap_ci = [float(np.percentile(ap_vals, 2.5)), float(np.percentile(ap_vals, 97.5))] if ap_vals else None
    out["roc_pr"] = dict(episode_auc=auc, episode_auc_ci95=auc_ci, step_ap=ap, step_ap_ci95=ap_ci,
                         n_pos_episodes=len(pos_ep), n_neg_episodes=len(neg_ep))

    # 고장 크기·지속시간별 지연 곡선(§13-5, 추가 실행 없음)
    out["delay_by_magnitude"] = _delay_by_magnitude(det, rows, records)
    return out


def _combine_rate(per_kind: dict, kinds: set) -> dict:
    k = sum(per_kind[x]["detected"] for x in kinds if x in per_kind)
    n = sum(per_kind[x]["fault_started"] for x in kinds if x in per_kind)
    return dict(k=k, n=n, ci95=wilson(k, n))


def _bucket(kind: str, rec: dict) -> Optional[str]:
    f = rec["fault"]
    if f is None or rec["run"] != kind:
        return None
    if kind == "steer_delay":
        return f"delay={int(f['magnitude'])}step"
    if kind == "steer_stuck":
        d = f["duration_steps"]
        return "dur10-19" if 10 <= d <= 19 else ("dur20-30" if 20 <= d <= 30 else f"dur{d}")
    if kind == "lidar_dropout":
        d = f["duration_steps"]
        if 20 <= d <= 33:
            return "dur20-33"
        if 34 <= d <= 47:
            return "dur34-47"
        if 48 <= d <= 60:
            return "dur48-60"
        return f"dur{d}"
    if kind == "lidar_spike":
        return "up" if f.get("meta", {}).get("up") else "down"
    return None


def _delay_by_magnitude(det: str, rows: List[dict], records: dict) -> dict:
    out = {}
    for kind in ("steer_delay", "steer_stuck", "lidar_dropout", "lidar_spike"):
        buckets: Dict[str, list] = defaultdict(list)
        for r in rows:
            if r["run"] != kind:
                continue
            rec = records[(r["run"], r["seed"])]
            b = _bucket(kind, rec)
            if b is not None and r["onset"] is not None and r["onset"] <= r["total_steps"]:
                buckets[b].append(r)
        out[kind] = {}
        for b, rs in sorted(buckets.items()):
            k = sum(bool(r["detected"]) for r in rs)
            med, p90 = delay_stats(rs)
            out[kind][b] = dict(n=len(rs), detected=k, detected_ci95=wilson(k, len(rs)),
                                delay_median=med, delay_p90=p90)
    return out


def _sigma_variant_summary(rs: List[dict]) -> dict:
    """σ 민감도류(일치/불일치) 공통 요약: 정상 오경보율 + 고장 탐지율·지연(전체 고장 종류 합산)."""
    normal = [r for r in rs if r["run"].startswith("none")]
    fault = [r for r in rs if not r["run"].startswith("none")]
    k_fa = sum(r["first_alarm"] is not None for r in normal)
    started = [r for r in fault if r["onset"] is not None and r["onset"] <= r["total_steps"]]
    k_det = sum(bool(r["detected"]) for r in started)
    med, p90 = delay_stats(started)
    return dict(normal_false_alarm=dict(k=k_fa, n=len(normal), ci95=wilson(k_fa, len(normal))),
               fault_detected=dict(k=k_det, n=len(started), ci95=wilson(k_det, len(started))),
               delay_median=med, delay_p90=p90)


def summarize(bundle: dict, h_by_detector: Dict[str, float]) -> dict:
    out = {}
    for det in DETECTORS:
        out[det] = summarize_detector(det, h_by_detector[det], bundle["rows"][det], bundle["labels"][det],
                                      bundle["scores"][det], bundle["records"])
    # A σ 일치 민감도(확장, 오늘 지시 [2]: A만. 정규화·임계값도 σ마다 다시 계산됨)
    out["A_sigma_sensitivity"] = {tag: _sigma_variant_summary(rs) for tag, rs in bundle["sens_rows"].items()}
    # A σ 불일치 민감도(§22-1, 2026-10-02 지시: 정규화·임계값 1.0 고정, 실제 주입만 바꿈)
    out["A_sigma_mismatch_sensitivity"] = {tag: _sigma_variant_summary(rs)
                                          for tag, rs in bundle["mismatch_rows"].items()}
    return out


# ---------------- CLI ----------------

def _load_thresholds(args) -> dict:
    a_thr = json.loads((Path(args.a_thresholds) / "thresholds.json").read_text(encoding="utf-8"))
    a005 = json.loads((Path(args.a_thresholds_sg005) / "thresholds.json").read_text(encoding="utf-8"))
    a5 = json.loads((Path(args.a_thresholds_sg5) / "thresholds.json").read_text(encoding="utf-8"))
    b_thr = json.loads((Path(args.b_thresholds) / "thresholds_b.json").read_text(encoding="utf-8"))
    hy_thr = json.loads((Path(args.hybrid_thresholds) / "thresholds_hybrid.json").read_text(encoding="utf-8"))
    assert a005["sigma_gyro_deg"] == 0.05 and a5["sigma_gyro_deg"] == 5.0
    assert a_thr["sigma_gyro_deg"] == an_config.SIGMA_GYRO_DEG == b_thr["sigma_gyro_deg"] == hy_thr["sigma_gyro_deg"]
    h_by_detector = {
        "A": a_thr["h"], "B1": b_thr["detectors"]["B1"]["h"], "B2": b_thr["detectors"]["B2"]["h"],
        "HYBRID": hy_thr["h"], "A_sg0.05": a005["h"], "A_sg5": a5["h"],
    }
    model_dirs = {"B": b_thr["model_dir"], "HYBRID": hy_thr["model_dir"]}
    thr_paths = dict(A=str(args.a_thresholds), A_sg0_05=str(args.a_thresholds_sg005),
                     A_sg5=str(args.a_thresholds_sg5), B=str(args.b_thresholds),
                     HYBRID=str(args.hybrid_thresholds))
    return h_by_detector, model_dirs, thr_paths


def _run_and_save(seeds_mode: str, seeds: list, h_by_detector: dict, model_dirs: dict, thr_paths: dict,
                  out_root: str) -> Path:
    sigma_variants = {"main": an_config.SIGMA_GYRO_DEG, "sg0.05": 0.05, "sg5": 5.0}
    bundle = compute(seeds, h_by_detector, model_dirs, sigma_variants)
    summary = summarize(bundle, h_by_detector)

    out = new_out_dir(out_root, f"it{an_config.ITERATION}_eval_offline_{seeds_mode}")
    for det in DETECTORS:
        write_csv(out / f"episodes_{det}.csv", HEADER, bundle["rows"][det])
    for tag, rs in bundle["sens_rows"].items():
        write_csv(out / f"episodes_A_{tag}.csv", HEADER, rs)
    for tag, rs in bundle["mismatch_rows"].items():
        write_csv(out / f"episodes_A_{tag}.csv", HEADER, rs)
    meta = dict(purpose="오프라인 평가(DESIGN.md §7·§13-5, 핵심+확장)" + ("" if seeds_mode == "eval" else " — dev 대역 테스트, 보고서 수치 아님"),
               seeds_mode=seeds_mode, seeds=[seeds[0], seeds[-1]], iteration=an_config.ITERATION,
               threshold_dirs=thr_paths, model_dirs=model_dirs, h_by_detector=h_by_detector,
               n_bootstrap=N_BOOTSTRAP, bootstrap_seed=BOOTSTRAP_SEED)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_env(out, dict(purpose=meta["purpose"]))
    return out


def _print_summary(summary: dict) -> None:
    for det in DETECTORS:
        s = summary[det]
        print(f"[{det}] h={s['h']!r} 정상 원거리 경보 {s['normal_far']['episodes']['k']}/{s['normal_far']['episodes']['n']}"
              f"  정상 좌측 경보 {s['normal_leftobs']['episodes']['k']}/{s['normal_leftobs']['episodes']['n']}"
              f"  ROC AUC {s['roc_pr']['episode_auc']!r}  PR AP {s['roc_pr']['step_ap']!r}")
        for kind, pk in s["per_kind"].items():
            print(f"    {kind:18s} 탐지 {pk['detected']}/{pk['fault_started']}  지연중앙 {pk['delay_median']}"
                  f"  F1 {pk['step_prf1']['f1']}")
    print("A σ 일치 민감도:", summary["A_sigma_sensitivity"])
    print("A σ 불일치 민감도(§22-1):", summary["A_sigma_mismatch_sensitivity"])


def _check(path: Path) -> None:
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    seeds = list(range(meta["seeds"][0], meta["seeds"][1] + 1))
    h_by_detector = meta["h_by_detector"]
    model_dirs = meta["model_dirs"]
    sigma_variants = {"main": an_config.SIGMA_GYRO_DEG, "sg0.05": 0.05, "sg5": 5.0}
    bundle = compute(seeds, h_by_detector, model_dirs, sigma_variants)
    summary = summarize(bundle, h_by_detector)

    ok = True
    for det in DETECTORS:
        tmp = path / f"_check_episodes_{det}.csv"
        write_csv(tmp, HEADER, bundle["rows"][det])
        same = read_csv_text(tmp) == read_csv_text(path / f"episodes_{det}.csv")
        tmp.unlink()
        print(f"  episodes_{det}.csv: {'일치' if same else '불일치'}")
        ok = ok and same
    for tag, rs in bundle["sens_rows"].items():
        tmp = path / f"_check_episodes_A_{tag}.csv"
        write_csv(tmp, HEADER, rs)
        same = read_csv_text(tmp) == read_csv_text(path / f"episodes_A_{tag}.csv")
        tmp.unlink()
        print(f"  episodes_A_{tag}.csv: {'일치' if same else '불일치'}")
        ok = ok and same
    for tag, rs in bundle["mismatch_rows"].items():
        tmp = path / f"_check_episodes_A_{tag}.csv"
        write_csv(tmp, HEADER, rs)
        same = read_csv_text(tmp) == read_csv_text(path / f"episodes_A_{tag}.csv")
        tmp.unlink()
        print(f"  episodes_A_{tag}.csv: {'일치' if same else '불일치'}")
        ok = ok and same
    same_summary = json.dumps(summary, ensure_ascii=False, indent=2) == (path / "summary.json").read_text(encoding="utf-8")
    print(f"  summary.json: {'일치' if same_summary else '불일치'}")
    ok = ok and same_summary
    print(f"--check {path}: {'전체 일치' if ok else '불일치 있음'}")
    sys.exit(0 if ok else 1)


EVAL_FREEZE_TAG = "anomaly-eval-freeze"


def freeze_ok(info: dict) -> "tuple[bool, str]":
    """평가 seed(4000~) 실행 조건(오늘 지시): git이 깨끗하고 HEAD에 EVAL_FREEZE_TAG가 있어야 한다."""
    if info.get("dirty"):
        return False, "git 작업 트리가 dirty함(커밋되지 않은 변경 있음) — 평가 전 커밋 필요"
    if info.get("tag") != EVAL_FREEZE_TAG:
        return False, f"HEAD에 '{EVAL_FREEZE_TAG}' 태그 없음(현재 태그: {info.get('tag')!r}) — 커밋 후 태그 필요"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", choices=["dev", "eval"], default="dev")
    ap.add_argument("--a-thresholds")
    ap.add_argument("--a-thresholds-sg005", dest="a_thresholds_sg005")
    ap.add_argument("--a-thresholds-sg5", dest="a_thresholds_sg5")
    ap.add_argument("--b-thresholds")
    ap.add_argument("--hybrid-thresholds")
    ap.add_argument("--out-root", default="thesis_v2/results/anomaly")
    ap.add_argument("--check", default=None)
    args = ap.parse_args()

    if args.check:
        _check(Path(args.check))
        return

    if args.seeds == "eval":
        ok, reason = freeze_ok(git_info())
        if not ok:
            print(f"거부: --seeds eval은 '{EVAL_FREEZE_TAG}' 태그가 붙은 깨끗한 커밋에서만 실행한다 — {reason}",
                  file=sys.stderr)
            sys.exit(1)

    seeds = list(an_config.SEEDS_FAULT_DEV if args.seeds == "dev" else an_config.SEEDS_OFFLINE_EVAL)
    h_by_detector, model_dirs, thr_paths = _load_thresholds(args)
    out = _run_and_save(args.seeds, seeds, h_by_detector, model_dirs, thr_paths, args.out_root)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    _print_summary(summary)
    print("saved:", out)


if __name__ == "__main__":
    main()
