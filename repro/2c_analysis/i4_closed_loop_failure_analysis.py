"""
I4 폐루프 실패 원인 분석(분석 전용, 모델·데이터·하이퍼파라미터 변경 없음). RESULT_I4.md §5.

방법: 저장된 I4 모델로 폐루프(paper eval 200~299, S3 eval 격자 900)를 결정론적으로 재생한다
(closed_loop.run_episode 그대로, 원본 미수정). Student가 δ를 내는 매 호출에서 **같은 입력**
(y0, psi0, v0, target_y, state, delta_prev, obstacle_info)으로 v2 MPC를 그림자 호출해(조향에는
미사용) 비교값을 얻는다. 그림자 MPC 인스턴스는 트랙당 1개, Student 궤적 순서대로 호출된다
(warm-start 상태가 Student 궤적을 따라감 -- 비교용 참고값).

재생 결과(outcome)가 사용자 실행 결과 파일(closed_loop_*_student.json)과 에피소드 단위로
완전히 같은지 먼저 확인하고, 다르면 중단한다.

대표 에피소드 선정 규칙(결과 보고 고르지 않음, 실행 전 고정): paper 트랙에서 seed 오름차순으로
첫 번째 충돌 1건, 첫 번째·두 번째 타임아웃 2건.

사용(저장소 루트): python repro/2c_analysis/i4_closed_loop_failure_analysis.py
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline import config, postprocess
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode
from thesis_v2.improved.student_i4 import config as i4_config
from thesis_v2.improved.student_i4.closed_loop import StudentLateral, run_episode, scenarios_for
from thesis_v2.improved.student_i4.features import build_feature_vector, MPC_STATES
from thesis_v2.improved.student_i4.model import Predictor

RUN = ROOT / "thesis_v2/results/i4_student/20260925_075822_DESKTOP-MDCKRJS"
OUT = ROOT / "repro/2c_analysis/out/i4_closed_loop_failure"
_RAD2DEG = 180.0 / math.pi
CONT = ["v", "ey_line", "front_gap", "left_clear"]


class RecordingStudent(StudentLateral):
    def __init__(self, predictor, shadow):
        super().__init__(predictor)
        self.shadow = shadow
        self.calls = []

    def solve(self, y0, psi0_rad, v0, target_y, state_name, delta_prev_deg=0.0, obstacle_info=None):
        res = super().solve(y0, psi0_rad, v0, target_y, state_name, delta_prev_deg, obstacle_info)
        sh = self.shadow.solve(y0=y0, psi0_rad=psi0_rad, v0=v0, target_y=target_y,
                               state_name=state_name, delta_prev_deg=delta_prev_deg,
                               obstacle_info=obstacle_info)
        v, ey, y, fg, lc = self._ctx
        self.calls.append(dict(x=build_feature_vector(v, ey, y, state_name, fg, lc),
                               y0=y0, psi0_deg=psi0_rad * _RAD2DEG, state=state_name,
                               student=res.delta_deg, mpc=sh.delta_deg, delta_prev=delta_prev_deg))
        return res


def replay(track, pred):
    shadow = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    ctrl = RecordingStudent(pred, shadow)
    eps = []
    for key, sc in scenarios_for(track):
        ctrl.calls = []
        r = run_episode(sc, ctrl, is_student=True)
        calls = ctrl.calls
        steps = []
        prev_final = 0.0
        y_pre, psi_pre = sc.y0, math.radians(sc.psi0_deg)
        ci = 0
        for i, (t, x, y, psi, state, d_des, d_fin, mode) in enumerate(r["traj"]):
            pp = postprocess.apply(d_des, prev_final)
            row = dict(step=i + 1, t=t, state=state, mode=mode, y=y_pre, psi_deg=psi_pre * _RAD2DEG,
                       delta_desired=d_des, delta_final=d_fin, rate=pp.rate_limit_active,
                       clip=pp.clip_active)
            if mode == "mpc":
                c = calls[ci]
                ci += 1
                row.update(student=c["student"], mpc=c["mpc"], diff=c["student"] - c["mpc"], x=c["x"])
            steps.append(row)
            prev_final = d_fin
            y_pre, psi_pre = y, psi
        assert ci == len(calls)
        eps.append(dict(key=key, outcome=r["outcome"], transitions=r["transitions"],
                        state_duration=r["state_duration"], total_steps=r["total_steps"], steps=steps))
    return eps


def check_against_saved(track, eps):
    saved = json.load(open(RUN / f"eval/closed_loop/closed_loop_{track}_student.json", encoding="utf-8"))
    a = [(str(e["key"]), e["outcome"]) for e in eps]
    b = [(str(tuple(p["key"]) if isinstance(p["key"], list) else p["key"]), p["outcome"])
         for p in saved["per_episode"]]
    assert a == b, f"{track}: 재생 결과가 저장 결과와 다름"


def train_stats():
    d = np.load(RUN / "dataset/dataset.npz", allow_pickle=True)
    tr = d["split"] == "train"
    X, st = d["X"][tr], d["state"][tr]
    s = json.load(open(RUN / "normalization_stats.json", encoding="utf-8"))
    g = dict(mean=np.array(s["X_mean"][:4]), std=np.array(s["X_std_safe"][:4]),
             lo=X[:, :4].min(0), hi=X[:, :4].max(0))
    per_state = {}
    for k in MPC_STATES:
        m = st == k
        sd = X[m, :4].std(0)
        per_state[k] = dict(mean=X[m, :4].mean(0), std=np.where(sd == 0, 1.0, sd),
                            lo=X[m, :4].min(0), hi=X[m, :4].max(0))
    # 학습 데이터 자신의 |z|>3 비율(기준선)
    z_tr = np.abs((X[:, :4] - g["mean"]) / g["std"])
    base = dict(global_z3=float((z_tr > 3).any(1).mean()))
    zs = np.zeros(len(X), bool)
    for k in MPC_STATES:
        m = st == k
        zs[m] = (np.abs((X[m, :4] - per_state[k]["mean"]) / per_state[k]["std"]) > 3).any(1)
    base["state_cond_z3"] = float(zs.mean())
    return g, per_state, base


def shift_and_error(eps, g, per_state):
    rows = [r for e in eps for r in e["steps"] if r["mode"] == "mpc"]
    X = np.stack([r["x"][:4] for r in rows])
    st = np.array([r["state"] for r in rows])
    t = np.array([r["t"] for r in rows])
    ad = np.abs(np.array([r["diff"] for r in rows]))
    stu = np.array([r["student"] for r in rows])
    mpc = np.array([r["mpc"] for r in rows])
    zg = (np.abs((X - g["mean"]) / g["std"]) > 3).any(1)
    outside_range = ((X < g["lo"]) | (X > g["hi"])).any(1)
    zc = np.zeros(len(X), bool)
    outside_state_range = np.zeros(len(X), bool)
    for k in MPC_STATES:
        m = st == k
        if m.any():
            p = per_state[k]
            zc[m] = (np.abs((X[m] - p["mean"]) / p["std"]) > 3).any(1)
            outside_state_range[m] = ((X[m] < p["lo"]) | (X[m] > p["hi"])).any(1)
    out = dict(n_calls=int(len(rows)),
               global_z3=float(zg.mean()), state_cond_z3=float(zc.mean()),
               outside_train_range=float(outside_range.mean()),
               outside_state_train_range=float(outside_state_range.mean()),
               by_state={}, by_time={}, err_by_time={})
    for k in MPC_STATES:
        m = st == k
        if not m.any():
            continue
        out["by_state"][k] = dict(n=int(m.sum()), global_z3=float(zg[m].mean()),
                                  state_cond_z3=float(zc[m].mean()),
                                  outside_state_train_range=float(outside_state_range[m].mean()),
                                  mae_student_vs_mpc=float(ad[m].mean()),
                                  student_raw_over_25=float((np.abs(stu[m]) > config.DELTA_MAX_DEG + 1e-9).mean()),
                                  mpc_raw_over_25=float((np.abs(mpc[m]) > config.DELTA_MAX_DEG + 0.01).mean()))
    bins = [0, 2, 4, 6, 8, 10, 11.1]
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (t > lo) & (t <= hi)
        if m.any():
            key = f"{lo}-{hi}s"
            out["by_time"][key] = dict(n=int(m.sum()), global_z3=float(zg[m].mean()),
                                       state_cond_z3=float(zc[m].mean()))
            out["err_by_time"][key] = dict(n=int(m.sum()), mae=float(ad[m].mean()),
                                           p95=float(np.percentile(ad[m], 95)))
    # 에피소드 내 전반/후반 비교(생존 편향 없는 쌍 비교)
    firsts, seconds = [], []
    for e in eps:
        a = [abs(r["diff"]) for r in e["steps"] if r["mode"] == "mpc"]
        if len(a) >= 10:
            h = len(a) // 2
            firsts.append(np.mean(a[:h]))
            seconds.append(np.mean(a[h:]))
    firsts, seconds = np.array(firsts), np.array(seconds)
    out["within_episode_half"] = dict(n_episodes=int(len(firsts)), first_half_mae_mean=float(firsts.mean()),
                                      second_half_mae_mean=float(seconds.mean()),
                                      frac_episodes_second_gt_first=float((seconds > firsts).mean()))
    # 오차가 heading(학생 입력에 없음)과 얼마나 관련 있는지
    psi = np.array([r["psi_deg"] for r in rows])
    diff = np.array([r["diff"] for r in rows])
    out["corr_diff_vs_psi"] = {k: float(np.corrcoef(psi[st == k], diff[st == k])[0, 1])
                               for k in MPC_STATES if (st == k).sum() > 10}
    out["psi_abs_mean_by_state"] = {k: float(np.abs(psi[st == k]).mean())
                                    for k in MPC_STATES if (st == k).any()}
    return out


def intervention(eps):
    res = {}
    for k in MPC_STATES + ["SAFE_STOP"]:
        rs = [r for e in eps for r in e["steps"] if r["state"] == k]
        rm = [r for r in rs if r["mode"] == "mpc"]
        if not rs:
            continue
        res[k] = dict(n_steps=len(rs), n_student_calls=len(rm),
                      clip_rate_per_student_call=(sum(r["clip"] for r in rm) / len(rm)) if rm else None,
                      rate_limit_rate_per_student_call=(sum(r["rate"] for r in rm) / len(rm)) if rm else None,
                      student_raw_over_25=(sum(abs(r["student"]) > config.DELTA_MAX_DEG + 1e-9 for r in rm)
                                           / len(rm)) if rm else None,
                      clip_rate_per_step=sum(r["clip"] for r in rs) / len(rs),
                      rate_limit_rate_per_step=sum(r["rate"] for r in rs) / len(rs))
    rm = [r for e in eps for r in e["steps"] if r["mode"] == "mpc"]
    res["ALL_student_calls"] = dict(
        n=len(rm), clip_rate=sum(r["clip"] for r in rm) / len(rm),
        rate_limit_rate=sum(r["rate"] for r in rm) / len(rm),
        student_raw_over_25=sum(abs(r["student"]) > config.DELTA_MAX_DEG + 1e-9 for r in rm) / len(rm),
        student_raw_max_abs=max(abs(r["student"]) for r in rm),
        mpc_raw_max_abs=max(abs(r["mpc"]) for r in rm))
    return res


def timeout_patterns(eps):
    tos = [e for e in eps if e["outcome"] == "타임아웃"]
    final_state = Counter(e["steps"][-1]["state"] for e in tos)
    last_tr = Counter((e["transitions"][-1][1], e["transitions"][-1][2]) if e["transitions"] else ("-", "-")
                      for e in tos)
    seq = Counter(" > ".join(["KEEP_L2"] + [b for _, _, b in e["transitions"]]) for e in tos)
    # 마지막 상태에서의 FSM 조건 미충족 분석
    detail = defaultdict(list)
    for e in tos:
        fs = e["steps"][-1]["state"]
        tail = [r for r in e["steps"] if r["state"] == fs]
        ys = np.array([r["y"] for r in tail])
        ps = np.array([r["psi_deg"] for r in tail])
        if fs == "RETURN_TO_L2":
            ok_y = np.abs(ys) <= config.NEAR_L2
            ok_p = np.abs(ps) <= config.PSI_L2_LIMIT_DEG
            detail[fs].append(dict(steps_in_state=len(tail), frac_y_ok=float(ok_y.mean()),
                                   frac_psi_ok=float(ok_p.mean()), frac_both_ok=float((ok_y & ok_p).mean()),
                                   y_mean=float(ys.mean()), y_min=float(ys.min()), y_max=float(ys.max()),
                                   psi_abs_mean=float(np.abs(ps).mean()),
                                   n_sign_changes_y=int(np.sum(np.diff(np.sign(ys)) != 0))))
        elif fs == "EVADE_L":
            ok = np.abs(ys - config.W) <= config.NEAR_L1
            detail[fs].append(dict(steps_in_state=len(tail), frac_y_near_L1=float(ok.mean()),
                                   y_mean=float(ys.mean()), y_max=float(ys.max()),
                                   psi_abs_mean=float(np.abs(ps).mean())))
        else:
            detail[fs].append(dict(steps_in_state=len(tail), y_mean=float(ys.mean())))
    summ = {}
    for fs, lst in detail.items():
        summ[fs] = dict(n=len(lst), **{k: float(np.mean([d[k] for d in lst])) for k in lst[0]})
    return dict(n=len(tos), final_state=dict(final_state), last_transition={f"{a}->{b}": v
                                                                              for (a, b), v in last_tr.items()},
                state_sequence=dict(seq), final_state_detail_mean=summ)


def step_table(ep, path):
    lines = ["| step | state | y (m) | ψ (°) | Student δ (°) | 같은 입력 v2 MPC δ (°) | 차이 (°) | 최종 δ (°) | 개입 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in ep["steps"]:
        if r["mode"] == "mpc":
            s, m, d = f"{r['student']:.2f}", f"{r['mpc']:.2f}", f"{r['diff']:+.2f}"
        else:
            s = m = d = f"({r['mode']})"
        iv = ",".join(x for x, f in (("clip", r["clip"]), ("rate", r["rate"])) if f) or "-"
        lines.append(f"| {r['step']} | {r['state']} | {r['y']:.3f} | {r['psi_deg']:.1f} | {s} | {m} | {d} | "
                     f"{r['delta_final']:.2f} | {iv} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def plot(reps, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(len(reps), 2, figsize=(12, 3.4 * len(reps)))
    for ax_row, (label, ep, v2res) in zip(axes, reps):
        xs = [r["t"] for r in ep["steps"]]
        ax_row[0].plot([row["x"] for row in v2res.logger.rows], [row["y"] for row in v2res.logger.rows],
                       color="#1f6feb", label=f"v2 MPC ({v2res.outcome})")
        ax_row[0].plot(ep["_x"], [r["y_post"] for r in ep["steps"]], color="#d1242f",
                       label=f"Student ({ep['outcome']})")
        for ob in ep["_obs"]:
            ax_row[0].add_patch(plt.Rectangle((ob.x_near, ob.y_lo), ob.x_far - ob.x_near, ob.y_hi - ob.y_lo,
                                              color="0.6", alpha=0.6))
        ax_row[0].axhline(0, color="0.8", lw=0.8)
        ax_row[0].axhline(config.W, color="0.8", lw=0.8, ls="--")
        ax_row[0].set_title(f"{label}: 궤적 x-y")
        ax_row[0].set_xlabel("x (m)")
        ax_row[0].set_ylabel("y (m)")
        ax_row[0].legend(fontsize=8)
        st_d = [r["student"] if r["mode"] == "mpc" else np.nan for r in ep["steps"]]
        mp_d = [r["mpc"] if r["mode"] == "mpc" else np.nan for r in ep["steps"]]
        ax_row[1].plot(xs, mp_d, color="#1f6feb", label="v2 MPC δ (같은 입력)")
        ax_row[1].plot(xs, st_d, color="#d1242f", label="Student δ")
        ax_row[1].plot(xs, [r["delta_final"] for r in ep["steps"]], color="0.4", lw=0.8, ls=":",
                       label="차량 입력 δ(후처리 후)")
        ax_row[1].axhline(25, color="0.7", lw=0.8)
        ax_row[1].axhline(-25, color="0.7", lw=0.8)
        ax_row[1].set_title(f"{label}: Student 궤적 위에서의 δ 비교")
        ax_row[1].set_xlabel("t (s)")
        ax_row[1].set_ylabel("δ (°)")
        ax_row[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def observability():
    """학습 데이터에서 교사 δ가 Student 입력(9차원)만으로 얼마나 결정되는지: Student 입력을 격자로
    묶었을 때(ey 0.01m, front_gap 0.05m, left_clear, state) 칸 안 δ 분산이 전체 분산에서 차지하는
    비율(= 입력만으로 설명 불가능한 몫의 하한 추정). 칸 크기는 센서 분해능 수준으로 고정."""
    d = np.load(RUN / "dataset/dataset.npz", allow_pickle=True)
    X, dl, st = d["X"], d["Y"][:, 0].astype(float), d["state"]
    keys = np.stack([np.round(X[:, 1] / 0.01), np.round(X[:, 2] / 0.05), X[:, 3],
                     np.argmax(X[:, 4:], 1)], 1)
    out = {}
    for name, m in [("ALL", np.ones(len(dl), bool))] + [(k, st == k) for k in MPC_STATES]:
        _, inv = np.unique(keys[m], axis=0, return_inverse=True)
        inv = inv.ravel()
        dd = dl[m]
        cnt = np.bincount(inv)
        mean = np.bincount(inv, dd) / cnt
        within = float(((dd - mean[inv]) ** 2).mean())
        multi = cnt[inv] > 1
        out[name] = dict(n=int(m.sum()), var_total=float(dd.var()), var_within_bins=within,
                         unexplained_share=within / float(dd.var()),
                         within_bin_std_deg=float(np.sqrt(within)),
                         frac_samples_in_shared_bins=float(multi.mean()))
    return out


def v2_psi_by_state(track):
    """비교 기준: v2 MPC 자신의 폐루프 궤적에서 MPC 호출 스텝의 상태별 |psi| 평균(같은 eval 입력)."""
    mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    acc = defaultdict(list)
    for key, sc in scenarios_for(track):
        res = improved_run_episode(sc, mpc=mpc)
        psi_pre = sc.psi0_deg
        for row in res.logger.rows:
            if row["solver_status"] != "N/A":
                acc[row["state"]].append(abs(psi_pre))
            psi_pre = row["psi"] * _RAD2DEG
    return {k: float(np.mean(v)) for k, v in acc.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pred = Predictor(RUN / "checkpoints/policy_i4_best.pt", RUN / "normalization_stats.json")
    g, per_state, base = train_stats()
    result = dict(train_baseline_ood=base, observability=observability())
    print("observability", result["observability"], flush=True)
    all_eps = {}
    for track in ("paper", "s3"):
        eps = replay(track, pred)
        check_against_saved(track, eps)
        all_eps[track] = eps
        result[track] = dict(outcomes=dict(Counter(e["outcome"] for e in eps)),
                             shift_and_error=shift_and_error(eps, g, per_state),
                             intervention=intervention(eps),
                             timeouts=timeout_patterns(eps),
                             v2_own_trajectory_psi_abs_mean_by_state=v2_psi_by_state(track))
        print(track, result[track]["outcomes"], flush=True)

    # 대표 에피소드(고정 규칙)
    paper = all_eps["paper"]
    col = [e for e in paper if e["outcome"] == "충돌"][:1]
    tos = [e for e in paper if e["outcome"] == "타임아웃"][:2]
    reps = []
    v2 = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    for e in col + tos:
        sc = generate_scenario(e["key"])
        # 그림용: 후처리 후 y(post-step)와 x 복원
        r = run_episode(generate_scenario(e["key"]), StudentLateral(pred), is_student=True)
        e["_x"] = [row[1] for row in r["traj"]]
        for s, row in zip(e["steps"], r["traj"]):
            s["y_post"] = row[2]
        e["_obs"] = sc.obstacles
        v2res = improved_run_episode(generate_scenario(e["key"]), mpc=v2)
        label = f"seed {e['key']} ({e['outcome']})"
        reps.append((label, e, v2res))
        step_table(e, OUT / f"steps_paper_seed{e['key']}_{'collision' if e['outcome']=='충돌' else 'timeout'}.md")
        result.setdefault("representative", []).append(dict(
            seed=e["key"], outcome=e["outcome"], v2_outcome_same_seed=v2res.outcome,
            transitions=e["transitions"], total_steps=e["total_steps"]))
    plot(reps, OUT / "trajectories_student_vs_v2.png")

    with open(OUT / "analysis.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=lambda o: o.tolist()
                  if isinstance(o, np.ndarray) else str(o))
    print("saved", OUT)


if __name__ == "__main__":
    main()
