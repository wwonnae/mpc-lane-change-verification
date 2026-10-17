"""
Student v2 eval3 판정·추가 집계(분석 전용, DESIGN_I4 §6-5/§6-7 사전 기준 그대로 적용, 모델·기준 변경 없음).
eval3 기준 커밋: ab5b021.

1. 판정: 사용자 실행 결과 파일(eval/closed_loop/closed_loop_eval3_*.json)의 에피소드별 outcome으로
   - S10 vs v2 MPC 페어 비교 → (a) 통과: 충돌 ≤ v2 & 성공 ≥ v2 (paper·S3 각각)
   - S10 vs 9입력 McNemar 정확검정(양측) → (b) 부분 개선 판단용
   - dev(dev_compare.json) 대비 eval3 비교(일반화, 정보)
2. 상태별 집계(원출력 ±25° 초과·clip·rate 개입·분포 이탈): 원시 δ가 로그에 저장되지 않아(traj에는 t,x,y,ψ만)
   동결 모델로 결정론적 재생 — **재생 outcome이 저장 결과와 에피소드 단위로 완전히 같을 때만** 집계에 사용.
   분포 이탈 = 상태 조건부 |z|>3(dev 학습 split 통계), (i) 모델 자신의 연속 입력, (ii) 공통(연속 4개+ψ).
3. 계산시간: S10/S11 timing.json(--power-mode-confirmed)와 timing_v3 공식 v2 측정 비교, CV.

사용(저장소 루트): python repro/2c_analysis/i4_eval3_judgement.py
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline import config, postprocess
from thesis_v2.baseline.summary import wilson_ci
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.student_i4 import config as i4_config
from thesis_v2.improved.student_i4.closed_loop import StudentLateral, run_episode, scenarios_for
from thesis_v2.improved.student_i4.dev_compare import train_state_stats
from thesis_v2.improved.student_i4.features import MPC_STATES, build_feature_vector, extend_features
from thesis_v2.improved.student_i4.model import Predictor

V2 = ROOT / "thesis_v2/results/i4_student_v2/20260925_092109_DESKTOP-MDCKRJS"
I4 = ROOT / "thesis_v2/results/i4_student/20260925_075822_DESKTOP-MDCKRJS"
CL = V2 / "eval/closed_loop"
OUT = ROOT / "repro/2c_analysis/out/i4_eval3_judgement"
TAGS = {"v2mpc": "mpc_v2mpc", "9input": "student_9input", "S10": "student_S10", "S11": "student_S11"}
MODEL_DIRS = {"9input": I4, "S10": V2 / "S10", "S11": V2 / "S11"}
TRACKS = {"paper": "eval3_paper", "S3": "eval3_s3"}


def load_saved(track, tag):
    return json.load(open(CL / f"closed_loop_{TRACKS[track]}_{tag}.json", encoding="utf-8"))


def mcnemar(a, b):
    only_a, only_b = int(np.sum(a & ~b)), int(np.sum(~a & b))
    n = only_a + only_b
    return dict(only_a=only_a, only_b=only_b, p_value=1.0 if n == 0 else float(binomtest(only_a, n, 0.5).pvalue))


def ci(k, n):
    c = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {c['lo']*100:.1f}~{c['hi']*100:.1f}%)"


def judgement():
    out = {}
    oc = {}
    for track in TRACKS:
        out[track] = {}
        for name, tag in TAGS.items():
            d = load_saved(track, tag)
            o = np.array([e["outcome"] for e in d["per_episode"]])
            keys = [str(e["key"]) for e in d["per_episode"]]
            oc[(track, name)] = (o, keys)
            n = len(o)
            out[track][name] = dict(success=ci(int((o == "성공").sum()), n), collision=ci(int((o == "충돌").sum()), n),
                                    timeout=int((o == "타임아웃").sum()), nonfinite=d["nonfinite_delta_total"])
        for name in TAGS:
            assert oc[(track, name)][1] == oc[(track, "v2mpc")][1], "에피소드 순서 불일치"
    res = dict(counts=out, pass_check={}, mcnemar_S10_vs_9input={}, paired_S10_vs_v2={})
    allS10, all9 = [], []
    for track in TRACKS:
        s10, _ = oc[(track, "S10")]
        v2, _ = oc[(track, "v2mpc")]
        n9, _ = oc[(track, "9input")]
        res["paired_S10_vs_v2"][track] = dict(
            n=int(len(s10)), v2_success_S10_fail=int(np.sum((v2 == "성공") & (s10 != "성공"))),
            v2_fail_S10_success=int(np.sum((v2 != "성공") & (s10 == "성공"))),
            both_success=int(np.sum((v2 == "성공") & (s10 == "성공"))))
        res["pass_check"][track] = dict(
            S10_collision=int((s10 == "충돌").sum()), v2_collision=int((v2 == "충돌").sum()),
            S10_success=int((s10 == "성공").sum()), v2_success=int((v2 == "성공").sum()),
            ok=bool((s10 == "충돌").sum() <= (v2 == "충돌").sum() and (s10 == "성공").sum() >= (v2 == "성공").sum()))
        res["mcnemar_S10_vs_9input"][track] = dict(
            success=mcnemar(s10 == "성공", n9 == "성공"), collision=mcnemar(n9 == "충돌", s10 == "충돌"))
        allS10.append(s10)
        all9.append(n9)
    a, b = np.concatenate(allS10), np.concatenate(all9)
    res["mcnemar_S10_vs_9input"]["combined"] = dict(success=mcnemar(a == "성공", b == "성공"),
                                                     collision=mcnemar(b == "충돌", a == "충돌"))
    passed = all(v["ok"] for v in res["pass_check"].values())
    partial = (res["mcnemar_S10_vs_9input"]["combined"]["success"]["p_value"] < 0.05)
    res["verdict_S10"] = "통과 — MPC 대체 가능(v2 대비 비열화 없음)" if passed else (
        "부분 개선 — 단독 제어기 불가" if partial else "실패")
    # S11 참고(판정 대상 아님)
    res["S11_reference_pass_check"] = {t: bool((oc[(t, "S11")][0] == "충돌").sum() <= (oc[(t, "v2mpc")][0] == "충돌").sum()
                                              and (oc[(t, "S11")][0] == "성공").sum() >= (oc[(t, "v2mpc")][0] == "성공").sum())
                                       for t in TRACKS}
    return res, oc


class _MPCCtrl:
    """v2 MPC를 같은 루프에서 돌리며 원시 δ·입력 기록(closed_loop.run_episode의 is_student=True 경로 사용 —
    set_context는 기록용일 뿐 제어에 영향 없음)."""

    def __init__(self):
        self.mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
        self.calls = []
        self._ctx = None

    def set_context(self, v, ey, y, fg, lc):
        self._ctx = (v, ey, y, fg, lc)

    def solve(self, y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0, obstacle_info=None):
        r = self.mpc.solve(y0=y0, psi0_rad=psi0_rad, v0=v0, target_y=target_y, state_name=state_name,
                           delta_prev_deg=delta_prev_deg, obstacle_info=obstacle_info)
        v, ey, y, fg, lc = self._ctx
        x11 = extend_features(build_feature_vector(v, ey, y, state_name, fg, lc), "S11",
                              psi0_rad * 180.0 / math.pi, delta_prev_deg)
        self.calls.append(dict(state=state_name, raw=r.delta_deg, x11=x11))
        return r


class _StuCtrl(StudentLateral):
    def __init__(self, pred):
        super().__init__(pred)
        self.calls = []

    def solve(self, y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0, obstacle_info=None):
        r = super().solve(y0, psi0_rad, v0, target_y, state_name, delta_prev_deg, obstacle_info)
        v, ey, y, fg, lc = self._ctx
        x11 = extend_features(build_feature_vector(v, ey, y, state_name, fg, lc), "S11",
                              psi0_rad * 180.0 / math.pi, delta_prev_deg)
        self.calls.append(dict(state=state_name, raw=r.delta_deg, x11=x11))
        return r


def replay_stats(name, oc, stats):
    own = {"v2mpc": [0, 1, 2, 3, 9], "9input": [0, 1, 2, 3], "S10": [0, 1, 2, 3, 9], "S11": [0, 1, 2, 3, 9, 10]}[name]
    common = [0, 1, 2, 3, 9]
    out = {}
    for track, tname in TRACKS.items():
        ctrl = _MPCCtrl() if name == "v2mpc" else _StuCtrl(Predictor(MODEL_DIRS[name] / "checkpoints/policy_i4_best.pt",
                                                                     MODEL_DIRS[name] / "normalization_stats.json"))
        rows = []
        outcomes = []
        for key, sc in scenarios_for(tname):
            ctrl.calls = []
            r = run_episode(sc, ctrl, is_student=True)
            outcomes.append(r["outcome"])
            prev, ci_ = 0.0, 0
            for row in r["traj"]:
                pp = postprocess.apply(row[5], prev)
                if row[7] == "mpc":
                    c = ctrl.calls[ci_]
                    ci_ += 1
                    rows.append((c["state"], c["raw"], pp.clip_active, pp.rate_limit_active, c["x11"]))
                prev = row[6]
            assert ci_ == len(ctrl.calls)
        saved = list(oc[(track, name)][0])
        assert outcomes == saved, f"{name}/{track}: 재생 outcome이 저장 결과와 다름 — 집계 중단"
        st = np.array([r[0] for r in rows])
        raw = np.array([r[1] for r in rows])
        clip = np.array([r[2] for r in rows])
        rate = np.array([r[3] for r in rows])
        X = np.stack([r[4] for r in rows])
        ood_own = np.zeros(len(rows), bool)
        ood_com = np.zeros(len(rows), bool)
        for s in MPC_STATES:
            m = st == s
            if m.any():
                mu, sd = stats[s]
                z = np.abs((X[m] - mu) / sd)
                ood_own[m] = (z[:, own] > 3).any(1)
                ood_com[m] = (z[:, common] > 3).any(1)
        tol = config.DELTA_MAX_DEG + 0.0065  # v2 MPC는 QP 허용오차(SETTINGS_DECISION §19, 0.00653°)까지 제약 만족

        def blk(m):
            return dict(n=int(m.sum()), raw_over_25=float((np.abs(raw[m]) > tol).mean()),
                        raw_max_abs=float(np.abs(raw[m]).max()), clip=float(clip[m].mean()), rate=float(rate[m].mean()),
                        ood_own=float(ood_own[m].mean()), ood_common=float(ood_com[m].mean()))
        out[track] = dict(replay_outcomes_match_saved=True, ALL=blk(np.ones(len(rows), bool)),
                          **{s: blk(st == s) for s in MPC_STATES if (st == s).any()})
    return out


def timing():
    off = json.load(open(ROOT / "thesis_v2/results/timing_v3/20260925_002745_DESKTOP-MDCKRJS_v2/timing_v2.json",
                         encoding="utf-8"))
    res = {}
    for m in ("S10", "S11"):
        t = json.load(open(V2 / m / "eval/timing/timing.json", encoding="utf-8"))
        e = json.load(open(V2 / m / "eval/timing/env.json", encoding="utf-8"))
        res[m] = dict(meets_official_condition=e["power"]["meets_official_condition"],
                      power_mode_user_confirmed=e["power"]["power_mode_user_confirmed"],
                      ac_status=e["power"]["ac_status"], onnxruntime=e["onnxruntime"], torch=e["torch"],
                      onnx_check=t["onnx_conversion_check"], scenarios={})
        for sc in ("paper", "left_obstacle", "S6_psi-15"):
            r = t[sc]
            o = off[sc]["mpc_solve_ms"]
            res[m]["scenarios"][sc] = dict(
                n_calls=r["n_mpc_calls"], n_calls_official=off[sc]["n_mpc_calls"],
                v2_p99=r["v2_mpc_solve_ms"]["p99"], v2_p99_official=o["p99"],
                v2_p99_rel_diff=(r["v2_mpc_solve_ms"]["p99"] - o["p99"]) / o["p99"],
                v2_mean=r["v2_mpc_solve_ms"]["mean"], v2_mean_official=o["mean"],
                iters_p50_p99=(r["v2_mpc_iterations"]["p50"], r["v2_mpc_iterations"]["p99"]),
                iters_official=(off[sc]["iterations"]["p50"], off[sc]["iterations"]["p99"]),
                **{f"{k}_{s}": r[k][s] for k in ("v2_mpc_solve_ms", "pytorch_e2e_ms", "onnx_e2e_ms",
                                                 "pytorch_infer_only_ms", "onnx_infer_only_ms")
                   for s in ("p50", "p99", "cv")})
    return res


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res, oc = judgement()
    print("verdict S10:", res["verdict_S10"], res["pass_check"], flush=True)
    ds = dict(np.load(V2 / "dataset/dataset.npz", allow_pickle=True))
    stats = train_state_stats(ds)
    res["by_state"] = {}
    for name in TAGS:
        res["by_state"][name] = replay_stats(name, oc, stats)
        print(name, {t: round(v["ALL"]["raw_over_25"] * 100, 3) for t, v in res["by_state"][name].items()}, flush=True)
    dev = json.load(open(V2 / "dev_compare/dev_compare.json", encoding="utf-8"))
    mae3 = json.load(open(V2 / "eval3/mae_models.json", encoding="utf-8"))
    res["generalization"] = {
        m: dict(dev_open_loop_mae=dev["open_loop"][k]["ALL"]["mae"],
                eval3_open_loop_mae=mae3["models"][m]["overall"]["delta_vs_v2"]["mae"],
                dev_paper=(dev["closed_loop"][k]["dev_paper"]["success"], dev["closed_loop"][k]["dev_paper"]["collision"]),
                dev_s3=(dev["closed_loop"][k]["dev_s3"]["success"], dev["closed_loop"][k]["dev_s3"]["collision"]),
                eval3_paper=res["counts"]["paper"][m if m != "9" else "9input"]["success"],
                eval3_s3=res["counts"]["S3"][m if m != "9" else "9input"]["success"])
        for m, k in (("9", "9"), ("S10", "S10"), ("S11", "S11"))}
    res["timing"] = timing()
    with open(OUT / "eval3_judgement.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    print("saved", OUT)


if __name__ == "__main__":
    main()
