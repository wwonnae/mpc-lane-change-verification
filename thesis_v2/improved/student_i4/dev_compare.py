"""
Student v2 dev 비교·선택(DESIGN_I4 §6-7). 대상: 기존 9입력(I4 모델 그대로) / S10(+ψ) / S11(+ψ+δ_prev).
eval 데이터는 쓰지 않는다(dev 전용).

- 개루프: 학습 데이터 val split(세 모델 공통, 같은 split) 상태별 δ MAE vs v2 MPC 라벨.
- 폐루프: dev paper seed 100~199 + dev S3 격자 900. closed_loop.run_episode 그대로(Student가 MPC 자리만 대체).
- 보조: 원출력 ±25° 초과율, clip·rate 개입률, 분포 이탈률(상태 조건부 |z|>3, 학습 split 통계 — (i) 모델 자신의
  연속 입력, (ii) 공통: 연속 4개+ψ).
- 선택 규칙(실행 전 확정, DESIGN_I4 §6-7): dev 폐루프 1,000 에피소드 페어 비교로 S10 vs S11.
  S11 선택 조건: (성공 McNemar p<0.05 & S11 성공 많음 & 충돌 S11≤S10) 또는 (충돌 McNemar p<0.05 & S11 충돌 적음
  & 성공 S11≥S10). 그 외 전부 S10.

사용(저장소 루트): python -m thesis_v2.improved.student_i4.dev_compare --v2-dir <i4_student_v2 run> --i4-dir <i4 run>
"""
import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from thesis_v2.baseline import config, postprocess
from thesis_v2.baseline.summary import wilson_ci

from .closed_loop import StudentLateral, run_episode, scenarios_for
from .features import MPC_STATES, extend_features
from .model import Predictor

CONT_IDX_BASE = [0, 1, 2, 3]  # v, ey_line, front_gap, left_clear


class RecStudent(StudentLateral):
    def __init__(self, pred):
        super().__init__(pred)
        self.calls = []

    def solve(self, y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0, obstacle_info=None):
        res = super().solve(y0, psi0_rad, v0, target_y, state_name, delta_prev_deg, obstacle_info)
        v, ey, y, fg, lc = self._ctx
        x11 = extend_features(self.pred.build(v, ey, y, state_name, fg, lc, 0.0, 0.0)[:9], "S11",
                              psi0_rad * 180.0 / math.pi, delta_prev_deg)
        self.calls.append(dict(state=state_name, raw=res.delta_deg, x11=x11, delta_prev=delta_prev_deg))
        return res


def mcnemar(a_flags, b_flags):
    """페어 이진 결과. b(=a만 참) / c(=b만 참) 불일치 쌍의 정확 이항검정(양측)."""
    only_a = int(np.sum(a_flags & ~b_flags))
    only_b = int(np.sum(~a_flags & b_flags))
    n = only_a + only_b
    p = 1.0 if n == 0 else float(binomtest(only_a, n, 0.5).pvalue)
    return dict(only_a=only_a, only_b=only_b, p_value=p)


def train_state_stats(ds):
    tr = ds["split"] == "train"
    X11 = extend_features(ds["X"], "S11", ds["psi_deg"], ds["delta_prev_deg"])[tr]
    st = ds["state"][tr]
    out = {}
    for s in MPC_STATES:
        m = st == s
        sd = X11[m].std(0)
        out[s] = (X11[m].mean(0), np.where(sd == 0, 1.0, sd))
    return out


def open_loop(pred, ds):
    va = ds["split"] == "val"
    X = extend_features(ds["X"], pred.variant, ds["psi_deg"], ds["delta_prev_deg"])[va]
    Yp = pred.predict_batch(X)
    d = ds["Y"][va, 0]
    st = ds["state"][va]
    out = {}
    for name, m in [("ALL", np.ones(len(d), bool))] + [(s, st == s) for s in MPC_STATES]:
        e = np.abs(Yp[m, 0] - d[m])
        out[name] = dict(n=int(m.sum()), mae=float(e.mean()), p95=float(np.percentile(e, 95)),
                         max=float(e.max()), v_target_mae_ref=float(np.abs(Yp[m, 1] - ds["Y"][va][m, 1]).mean()),
                         raw_over_25=float((np.abs(Yp[m, 0]) > config.DELTA_MAX_DEG + 1e-9).mean()))
    return out


def closed_loop(pred, track, stats):
    ctrl = RecStudent(pred)
    eps = []
    calls_all = []
    clip_n = rate_n = 0
    for key, sc in scenarios_for(track):
        ctrl.calls = []
        r = run_episode(sc, ctrl, is_student=True)
        prev = 0.0
        for row in r["traj"]:
            pp = postprocess.apply(row[5], prev)
            if row[7] == "mpc":
                clip_n += pp.clip_active
                rate_n += pp.rate_limit_active
            prev = row[6]
        calls_all += ctrl.calls
        eps.append(dict(key=key, outcome=r["outcome"], nonfinite=r["nonfinite_delta"]))
    n_calls = len(calls_all)
    st = np.array([c["state"] for c in calls_all])
    raw = np.array([c["raw"] for c in calls_all])
    X11 = np.stack([c["x11"] for c in calls_all])
    own_idx = CONT_IDX_BASE + ([9] if pred.variant in ("S10", "S11") else []) + ([10] if pred.variant == "S11" else [])
    common_idx = CONT_IDX_BASE + [9]
    ood_own = np.zeros(n_calls, bool)
    ood_common = np.zeros(n_calls, bool)
    for s in MPC_STATES:
        m = st == s
        if not m.any():
            continue
        mu, sd = stats[s]
        z = np.abs((X11[m] - mu) / sd)
        ood_own[m] = (z[:, own_idx] > 3).any(1)
        ood_common[m] = (z[:, common_idx] > 3).any(1)
    oc = Counter(e["outcome"] for e in eps)
    n = len(eps)

    def ci(k):
        c = wilson_ci(k, n)
        return f"{k}/{n} (95% CI {c['lo']*100:.1f}~{c['hi']*100:.1f}%)"

    by_state = {}
    for s in MPC_STATES:
        m = st == s
        if m.any():
            by_state[s] = dict(n=int(m.sum()), raw_over_25=float((np.abs(raw[m]) > 25 + 1e-9).mean()),
                               ood_own=float(ood_own[m].mean()), ood_common=float(ood_common[m].mean()))
    return dict(
        n_episodes=n, success=oc.get("성공", 0), collision=oc.get("충돌", 0), timeout=oc.get("타임아웃", 0),
        other=n - oc.get("성공", 0) - oc.get("충돌", 0) - oc.get("타임아웃", 0),
        success_ci=ci(oc.get("성공", 0)), collision_ci=ci(oc.get("충돌", 0)),
        nonfinite_total=sum(e["nonfinite"] for e in eps), n_student_calls=n_calls,
        raw_over_25=float((np.abs(raw) > 25 + 1e-9).mean()), raw_max_abs=float(np.abs(raw).max()),
        clip_rate=clip_n / n_calls, rate_limit_rate=rate_n / n_calls,
        ood_own=float(ood_own.mean()), ood_common=float(ood_common.mean()), by_state=by_state,
    ), eps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2-dir", required=True)
    ap.add_argument("--i4-dir", required=True)
    args = ap.parse_args()
    v2 = Path(args.v2_dir)
    i4 = Path(args.i4_dir)
    out_dir = v2 / "dev_compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    ds = dict(np.load(v2 / "dataset" / "dataset.npz", allow_pickle=True))
    stats = train_state_stats(ds)
    models = {"9": i4, "S10": v2 / "S10", "S11": v2 / "S11"}
    t0 = time.perf_counter()
    result = dict(models={k: str(p) for k, p in models.items()}, open_loop={}, closed_loop={})
    outcomes = {}
    for name, md in models.items():
        pred = Predictor(md / "checkpoints" / "policy_i4_best.pt", md / "normalization_stats.json")
        assert pred.variant == name
        result["open_loop"][name] = open_loop(pred, ds)
        result["closed_loop"][name] = {}
        outcomes[name] = []
        for track in ("dev_paper", "dev_s3"):
            summ, eps = closed_loop(pred, track, stats)
            result["closed_loop"][name][track] = summ
            outcomes[name] += [e["outcome"] for e in eps]
            with open(out_dir / f"episodes_{name}_{track}.json", "w", encoding="utf-8") as f:
                json.dump(eps, f, ensure_ascii=False, default=str)
            print(f"[{name}][{track}] S/C/T = {summ['success']}/{summ['collision']}/{summ['timeout']}", flush=True)

    # 선택 규칙(DESIGN_I4 §6-7)
    o10, o11 = np.array(outcomes["S10"]), np.array(outcomes["S11"])
    s10, s11 = o10 == "성공", o11 == "성공"
    c10, c11 = o10 == "충돌", o11 == "충돌"
    m_succ = mcnemar(s11, s10)  # only_a = S11만 성공
    m_coll = mcnemar(c10, c11)  # only_a = S10만 충돌(=S11이 충돌 피함)
    cond1 = m_succ["p_value"] < 0.05 and s11.sum() > s10.sum() and c11.sum() <= c10.sum()
    cond2 = m_coll["p_value"] < 0.05 and c11.sum() < c10.sum() and s11.sum() >= s10.sum()
    selected = "S11" if (cond1 or cond2) else "S10"
    o9 = np.array(outcomes["9"])
    result["selection"] = dict(
        rule="DESIGN_I4 §6-7: S11 if (success McNemar p<0.05 & S11 more successes & collisions S11<=S10) "
             "or (collision McNemar p<0.05 & S11 fewer collisions & successes S11>=S10); else S10",
        n_pairs=int(len(o10)),
        S10_success=int(s10.sum()), S11_success=int(s11.sum()),
        S10_collision=int(c10.sum()), S11_collision=int(c11.sum()),
        mcnemar_success_S11_only_vs_S10_only=m_succ, mcnemar_collision_S10_only_vs_S11_only=m_coll,
        cond1=bool(cond1), cond2=bool(cond2), selected=selected,
        reference_9input=dict(success=int((o9 == "성공").sum()), collision=int((o9 == "충돌").sum()),
                              mcnemar_success_selected_vs_9=mcnemar(
                                  (o11 if selected == "S11" else o10) == "성공", o9 == "성공")),
    )
    result["wall_time_sec"] = time.perf_counter() - t0
    with open(out_dir / "dev_compare.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(result["selection"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
