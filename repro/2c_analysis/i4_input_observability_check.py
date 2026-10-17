"""
REQ-STU-02 입력(9차원) 관측성 검증 — Student v2 [개정] 근거 계산(분석 전용, 모델 학습 없음).

(a) 해석적 확인: 논문 MPC(baseline OSQPMPC, REQ-MPC-01~06)는 초기상태 x0=[y0, ψ0]의 함수다.
    Student 9차원 입력을 고정한 채 ψ0만 바꿔 δ가 달라지는지 직접 계산한다. 같은 방식으로 δ_prev
    의존성을 baseline MPC(solve 인자에 δ_prev 없음, REQ-MPC-02 비용에 δ_prev 항 없음)와 v2 MPC(I1
    rate 제약 |δ0−δ_prev|≤10°/step)에서 각각 확인한다.
(b) 데이터 확인: dev 범위(paper seed 100~199 + S3 dev 격자 900, I4 Round 0과 같은 범위)에서 교사별
    (baseline MPC, v2 MPC) MPC 호출 스텝을 모아, 입력 격자(ey 0.01m, front_gap 0.05m, left_clear,
    상태) 안의 δ 분산이 전체에서 차지하는 비율을 계산하고, ψ(1°)·δ_prev(1°) 칸을 추가했을 때 얼마나
    줄어드는지 본다. 칸을 잘게 나누는 것만으로 분산이 줄어드는 효과를 분리하기 위해, 같은 상태 안에서
    ψ(또는 δ_prev)를 무작위로 섞은 **위약(placebo) 변수**를 같은 칸 크기로 추가한 대조값도 함께 낸다.

사용(저장소 루트): python repro/2c_analysis/i4_input_observability_check.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.runner import run_episode as base_run_episode
from thesis_v2.baseline.world import generate_scenario, generate_grid_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode
from thesis_v2.improved.student_i4 import config as i4_config
from thesis_v2.improved.student_i4.features import build_feature_vector, MPC_STATES

OUT = ROOT / "repro/2c_analysis/out/i4_input_observability"
_RAD2DEG = 180.0 / math.pi
PLACEBO_SEED = 12345


def analytic_demo():
    out = {"psi_dependence": [], "delta_prev_dependence": []}
    # Student 입력 고정: v=0.5, y0=0.10(RETURN_TO_L2, ey fallback=0.10), front_gap=LIDAR 최대, left_clear=True
    for psi_deg in (-30.0, -15.0, 0.0, 15.0, 30.0):
        b = OSQPMPC().solve(y0=0.10, psi0_rad=math.radians(psi_deg), v0=0.5, target_y=0.0,
                            state_name="RETURN_TO_L2")
        v2 = ImprovedMPC(**i4_config.TEACHER_FLAGS).solve(
            y0=0.10, psi0_rad=math.radians(psi_deg), v0=0.5, target_y=0.0,
            state_name="RETURN_TO_L2", delta_prev_deg=0.0)
        out["psi_dependence"].append(dict(psi0_deg=psi_deg, baseline_delta_deg=b.delta_deg,
                                          v2_delta_deg=v2.delta_deg))
    for dp in (-20.0, -10.0, 0.0, 10.0, 20.0):
        v2 = ImprovedMPC(**i4_config.TEACHER_FLAGS).solve(
            y0=0.10, psi0_rad=math.radians(-15.0), v0=0.5, target_y=0.0,
            state_name="RETURN_TO_L2", delta_prev_deg=dp)
        out["delta_prev_dependence"].append(dict(delta_prev_deg=dp, v2_delta_deg=v2.delta_deg,
                                                 baseline_note="baseline solve()에 δ_prev 인자 없음"))
    return out


class _Rec:
    def __init__(self, mpc, has_prev):
        self.calls = []
        orig = mpc.solve

        def wrapped(y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0, obstacle_info=None):
            if has_prev:
                r = orig(y0=y0, psi0_rad=psi0_rad, v0=v0, target_y=target_y, state_name=state_name,
                         delta_prev_deg=delta_prev_deg, obstacle_info=obstacle_info)
            else:
                r = orig(y0=y0, psi0_rad=psi0_rad, v0=v0, target_y=target_y, state_name=state_name)
            self.calls.append((y0, psi0_rad * _RAD2DEG, v0, state_name, r.delta_deg))
            return r
        mpc.solve = wrapped


def collect(teacher):
    scen = [generate_scenario(s) for s in i4_config.DEV_PAPER_SEEDS] + \
           [generate_grid_scenario(float(fg), float(y0)) for fg in i4_config.DEV_S3_FRONT_GAPS
            for y0 in i4_config.DEV_S3_Y0S]
    rows = []
    if teacher == "baseline":
        mpc = OSQPMPC()
        rec = _Rec(mpc, has_prev=False)
        run = lambda sc: base_run_episode(sc, mpc=mpc)
    else:
        mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
        rec = _Rec(mpc, has_prev=True)
        run = lambda sc: improved_run_episode(sc, mpc=mpc)
    for sc in scen:
        rec.calls = []
        res = run(sc)
        mrows = [r for r in res.logger.rows if r["solver_status"] != "N/A"]
        assert len(mrows) == len(rec.calls)
        prev_final = 0.0
        finals = {}
        # δ_prev = 직전 스텝의 최종 조향(후처리 후) — runner와 같은 정의
        k = 0
        for r in res.logger.rows:
            if r["solver_status"] != "N/A":
                y0, psi, v0, st, d = rec.calls[k]
                k += 1
                x = build_feature_vector(v0, r["ey_line"], y0, st, r["front_gap"], r["left_clear"])
                rows.append((x, psi, prev_final, st, d))
            prev_final = r["delta_final"]
    X = np.stack([r[0] for r in rows])
    return dict(X=X, psi=np.array([r[1] for r in rows]), dprev=np.array([r[2] for r in rows]),
                state=np.array([r[3] for r in rows]), delta=np.array([r[4] for r in rows]))


def unexplained_share(keys, y):
    _, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.ravel()
    cnt = np.bincount(inv)
    mean = np.bincount(inv, y) / cnt
    within = float(((y - mean[inv]) ** 2).mean())
    return dict(unexplained_share=within / float(y.var()), within_std_deg=math.sqrt(within),
                n_bins=int(len(cnt)), frac_samples_in_shared_bins=float((cnt[inv] > 1).mean()))


def placebo(v, state, rng):
    p = v.copy()
    for s in np.unique(state):
        m = np.nonzero(state == s)[0]
        p[m] = v[rng.permutation(m)]
    return p


def binning_table(d):
    rng = np.random.default_rng(PLACEBO_SEED)
    X = d["X"]
    base = np.stack([np.round(X[:, 1] / 0.01), np.round(X[:, 2] / 0.05), X[:, 3],
                     np.argmax(X[:, 4:], 1)], 1)
    psi_b = np.round(d["psi"] / 1.0)[:, None]
    dp_b = np.round(d["dprev"] / 1.0)[:, None]
    psi_pl = np.round(placebo(d["psi"], d["state"], rng) / 1.0)[:, None]
    dp_pl = np.round(placebo(d["dprev"], d["state"], rng) / 1.0)[:, None]
    variants = {
        "9dim(REQ-STU-02)": base,
        "9dim+psi": np.hstack([base, psi_b]),
        "9dim+psi_PLACEBO": np.hstack([base, psi_pl]),
        "9dim+psi+delta_prev": np.hstack([base, psi_b, dp_b]),
        "9dim+psi+delta_prev_PLACEBO": np.hstack([base, psi_b, dp_pl]),
    }
    out = {}
    for name, keys in variants.items():
        out[name] = {"ALL": unexplained_share(keys, d["delta"])}
        for s in MPC_STATES:
            m = d["state"] == s
            out[name][s] = unexplained_share(keys[m], d["delta"][m])
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"analytic": analytic_demo()}
    for teacher in ("baseline", "v2"):
        d = collect(teacher)
        result[teacher] = dict(n=int(len(d["delta"])), binning=binning_table(d))
        print(teacher, {k: round(v["ALL"]["unexplained_share"], 4) for k, v in result[teacher]["binning"].items()},
              flush=True)
    print(json.dumps(result["analytic"], indent=1))
    with open(OUT / "observability.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
