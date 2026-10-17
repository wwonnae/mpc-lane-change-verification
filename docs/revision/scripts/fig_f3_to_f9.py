"""
그림 F3~F9(DESIGN_REVISION §8-4). 모든 입력은 저장된 결과·재생 검증을 통과한 데이터(R1·R3·R2·eval 2회차·관측성 분석)만 쓴다.
대표 에피소드 선택 규칙은 각 함수 docstring(사전 고정).
"""
import json
import shutil

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator


def plain_log_ticks(ax, ticks):
    """로그 축 눈금을 일반 소수로(한글 글꼴에 수학 기호 U+2212가 없어 10^-1 표기가 깨지는 문제 방지)."""
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))

from fig_common import ROOT, DATA_DIR, FIG_DIR, save, C_BASE, C_V1, C_V2, C_S10, C_ONNX, STATE_ORDER

EV2 = ROOT / "thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS"
TV3 = ROOT / "thesis_v2/results/timing_v3"


def f3():
    """F3: 9입력 Student(I4) 실패 궤적 vs 같은 seed v2 MPC — 기존 분석 그림 재사용.
    선택 규칙(I4 실패 분석 때 사전 고정): E2 paper seed 오름차순 첫 충돌 1 + 첫·둘째 타임아웃 2(seed 201, 202, 204)."""
    src = ROOT / "repro/2c_analysis/out/i4_closed_loop_failure/trajectories_student_vs_v2.png"
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, FIG_DIR / "F3_student9_failure.png")
    meta = json.load(open(FIG_DIR / "figures_meta.json", encoding="utf-8"))
    meta["F3_student9_failure"] = dict(
        title="논문 입력(9차원) 그대로 재학습한 Student의 폐루프 실패 사례 vs 같은 seed v2 MPC",
        source="repro/2c_analysis/out/i4_closed_loop_failure/ (i4_closed_loop_failure_analysis.py, 저장 결과와 outcome 일치 재생)",
        cond="E2 (paper seed 200~299)", selection="seed 오름차순 첫 충돌(201) + 첫·둘째 타임아웃(202, 204) — I4 분석 시 사전 고정",
        replaces="없음(신설, VI.4)", script="(재사용) repro/2c_analysis/i4_closed_loop_failure_analysis.py", file="figures/F3_student9_failure.png",
        note="그림 하단 조건 태그 없음(재사용 그림) — 캡션으로 표기")
    json.dump(meta, open(FIG_DIR / "figures_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("copied F3")


def f4():
    """F4: S3 경계 지도(front_gap0 × y0 격자 900)와 물리 한계선 — baseline v1.1 vs v2. 선택 없음(격자 전체)."""
    summ = json.load(open(EV2 / "all_eval_v2_summary.json", encoding="utf-8"))["new_eval"]["S3"]
    fg = np.round(np.arange(0.5025, 1.9975 + 1e-4, 0.05), 4)
    y0 = np.round(np.arange(-0.1475, 0.1475 + 1e-4, 0.01), 4)
    lim = summ["physical_limit_curve"]
    ly = np.array(sorted(float(k) for k in lim))
    lx = np.array([lim[f"{k}"] if f"{k}" in lim else lim[str(k)] for k in [str(v) for v in ly]])
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    for ax, (name, fname, c) in zip(axes, (("baseline v1.1", "s3_grid_new_baseline.json", C_BASE),
                                           ("improved v2", "s3_grid_new_v2.json", C_V2))):
        g = np.array(json.load(open(EV2 / fname, encoding="utf-8")))
        z = (g == "성공").astype(float).T  # [y0][fg]
        dx, dy = 0.05, 0.01
        ax.pcolormesh(np.r_[fg - dx / 2, fg[-1] + dx / 2], np.r_[y0 - dy / 2, y0[-1] + dy / 2], z,
                      cmap=plt.matplotlib.colors.ListedColormap(["#cf222e", "#d0d7de"]), vmin=0, vmax=1, shading="flat")
        ax.plot(lx, ly, "k--", lw=2)
        nf = int((g != "성공").sum())
        ax.set_title(f"{name}: 실패 {nf}/{g.size}")
        ax.set_xlabel("초기 front_gap0 (m, 차량 전단 기준)")
        ax.set_xlim(0.0, 2.05)
        ax.legend(handles=[Patch(color="#d0d7de", label="성공"), Patch(color="#cf222e", label="충돌"),
                           plt.Line2D([], [], color="k", ls="--", lw=2, label="물리 한계(최대 조향 회피의 최소 front_gap0)")],
                  fontsize=8, loc="upper right")
    axes[0].set_ylabel("초기 y0 (m)")
    fig.suptitle("F4. S3 경계 지도 — 격자 900(1/4칸 오프셋), v=0.5 m/s·ψ0=0 고정, 점선 왼쪽은 어떤 제어로도 충돌", fontsize=11)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    save(fig, "F4_s3_boundary", "S3 경계 지도와 물리 한계 — baseline v1.1 vs improved v2",
         "thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/s3_grid_new_{baseline,v2}.json, all_eval_v2_summary.json(physical_limit_curve)",
         "E2 (S3 격자 1/4칸 오프셋 900)", "선택 없음(격자 전체)", "없음(신설, VI.5) — 기존 분석 그림(구 격자·3층PC104)을 E2로 다시 그림",
         "fig_f3_to_f9.py")


def f5():
    """F5: 개선판 비교 요약(항목별 단독 ablation은 개발 데이터 — thesis_v2/results/dev_ablation) — E2 트랙별 충돌 수(baseline/v1/v2), S3 실패, MPC solve p99(공식 조건 timing_v3). 선택 없음."""
    d = json.load(open(EV2 / "all_eval_v2_summary.json", encoding="utf-8"))["new_eval"]
    groups, n = [], []
    vals = {v: [] for v in ("baseline", "v1", "v2")}
    for g in ("paper", "left_obstacle", "S4", "S5", "S6", "S7a", "S7b"):
        if g in ("paper", "left_obstacle"):
            for v in vals:
                vals[v].append(d[g][v]["n_collision"])
            n.append(d[g]["baseline"]["n_episodes"])
        else:
            for v in vals:
                vals[v].append(sum(d[g][k][v]["n_collision"] for k in d[g]))
            n.append(sum(d[g][k]["baseline"]["n_episodes"] for k in d[g]))
        groups.append(g)
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8), gridspec_kw=dict(width_ratios=[3, 1, 1.3]))
    x = np.arange(len(groups))
    for k, (v, c) in enumerate((("baseline", C_BASE), ("v1", C_V1), ("v2", C_V2))):
        ax[0].bar(x + (k - 1) * 0.27, vals[v], 0.27, color=c, label={"baseline": "baseline v1.1", "v1": "improved v1", "v2": "improved v2"}[v])
        for xi, val in zip(x, vals[v]):
            ax[0].text(xi + (k - 1) * 0.27, val + 0.4, str(val), ha="center", fontsize=7)
    ax[0].set_xticks(x, [f"{g}\n(n={m})" for g, m in zip(groups, n)], fontsize=8)
    ax[0].set_ylabel("충돌 에피소드 수")
    ax[0].set_title("(a) 트랙별 충돌 수 — E2")
    ax[0].legend(fontsize=8)
    s3 = d["S3"]
    sv = [s3["n_fail_baseline"], s3["n_fail_v1"], s3["n_fail_v2"]]
    ax[1].bar(["baseline\nv1.1", "improved\nv1", "improved\nv2"], sv, color=[C_BASE, C_V1, C_V2])
    for k, v in enumerate(sv):
        ax[1].text(k, v + 1, f"{v}/900", ha="center", fontsize=8)
    ax[1].set_ylabel("실패 격자 수")
    ax[1].set_title("(b) S3 격자 실패 — E2")
    p99 = []
    for tag in ("baseline", "v1", "v2"):
        f = next(TV3.glob(f"*_{tag}/timing_{tag}.json"))
        p99.append(json.load(open(f, encoding="utf-8"))["paper"]["mpc_solve_ms"]["p99"])
    ax[2].bar(["baseline\nv1.1", "improved\nv1", "improved\nv2"], p99, color=[C_BASE, C_V1, C_V2])
    for k, v in enumerate(p99):
        ax[2].text(k, v * 1.15, f"{v:.3f} ms", ha="center", fontsize=8)
    ax[2].set_yscale("log")
    ax[2].set_ylim(0.1, 20)
    plain_log_ticks(ax[2], [0.1, 0.2, 0.5, 1, 2, 5, 10, 20])
    ax[2].set_ylabel("MPC solve p99 (ms, 로그 축)")
    ax[2].set_title("(c) 계산시간 p99 — T0·H1(공식)")
    fig.suptitle("F5. 개선판 비교 요약 — baseline · v1(I1·I1b·I2'·I3) · v2(v1 + I5 반복 상한 972)", fontsize=11)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    save(fig, "F5_improvement_ablation", "개선판 비교 요약(baseline·v1·v2) — 충돌·S3 실패·계산시간 p99",
         "eval_v2/.../all_eval_v2_summary.json, timing_v3/*/timing_*.json", "E2 (a·b) / T0-H1 (c, paper seed 0~99)",
         "선택 없음(전 에피소드)", "없음(신설, VI.6)", "fig_f3_to_f9.py")


def f6():
    """F6: 입력 관측성 — 입력 격자 안에서 설명되지 않는 교사 δ 분산 비율(교사: 논문 MPC=baseline, v2). 선택 없음(dev 전체)."""
    o = json.load(open(ROOT / "repro/2c_analysis/out/i4_input_observability/observability.json", encoding="utf-8"))
    keys = ["9dim(REQ-STU-02)", "9dim+psi_PLACEBO", "9dim+psi", "9dim+psi+delta_prev_PLACEBO", "9dim+psi+delta_prev"]
    labels = ["9입력\n(논문 명세)", "9입력 + ψ 위약\n(섞은 ψ)", "9입력 + ψ\n(S10)", "S10 + δ_prev 위약", "9입력 + ψ + δ_prev\n(S11)"]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    x = np.arange(len(keys))
    for k, (t, c, name) in enumerate((("baseline", C_BASE, "교사 = 논문 MPC(baseline v1.1)"), ("v2", C_V2, "교사 = v2 MPC(I4 교사)"))):
        v = [100 * o[t]["binning"][kk]["ALL"]["unexplained_share"] for kk in keys]
        ax.bar(x + (k - 0.5) * 0.38, v, 0.38, color=c, label=name)
        for xi, val in zip(x, v):
            ax.text(xi + (k - 0.5) * 0.38, val + 0.6, f"{val:.1f}%", ha="center", fontsize=8)
    ax.set_xticks(x, labels, fontsize=9)
    ax.set_ylabel("입력 격자 안 δ 분산 / 전체 δ 분산 (%)")
    ax.set_title("F6. Student 입력으로 설명되지 않는 교사 조향 분산 — ψ를 넣어야 사라짐(위약 대조: 같은 칸 크기의 섞은 변수)", fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, "F6_input_observability", "입력 관측성 — 9입력 / +ψ / +ψ+δ_prev와 위약 대조",
         "repro/2c_analysis/out/i4_input_observability/observability.json", "D (dev paper seed 100~199 + S3 dev 격자 900)",
         "선택 없음(dev MPC 호출 스텝 전체)", "없음(신설, VI.7 — [개정] 근거)", "fig_f3_to_f9.py")


def _r3():
    return np.load(DATA_DIR / "r3_eval3_paper_steps.npz", allow_pickle=True)


def f7():
    """F7: v2 MPC vs S10 궤적·조향 — E3 paper. 선택 규칙(사전 고정): eval3 seed 2000, 2001, 2002(처음 세 seed)."""
    d = _r3()
    fig, axes = plt.subplots(3, 2, figsize=(13, 10))
    for row, i in enumerate((0, 1, 2)):
        m = d[f"v2mpc_ep{i}_meta"]
        for name, c, lab in (("v2mpc", C_V2, "v2 MPC(교사)"), ("S10", C_S10, "Student S10")):
            a = d[f"{name}_ep{i}"]
            axes[row, 0].plot(a[:, 1], a[:, 2], color=c, lw=1.6, label=lab)
            pol = a[:, 7] > 0
            axes[row, 1].plot(a[:, 0], a[:, 5], color=c, lw=1.3, label=f"{lab} — 차량 입력 δ")
            axes[row, 1].plot(a[pol, 0], a[pol, 4], ".", color=c, ms=2, alpha=0.6,
                              label=f"{lab} — 원출력(MPC/Student 호출 스텝)")
        axes[row, 0].add_patch(Rectangle((m[3], m[5]), m[4] - m[3], m[6] - m[5], color="0.35", alpha=0.7, label="장애물"))
        axes[row, 0].axhline(0, color="0.6", ls="--", lw=0.8)
        axes[row, 0].axhline(0.30, color="0.6", ls=":", lw=0.8)
        axes[row, 0].set_ylabel("y (m)")
        axes[row, 0].set_title(f"seed {int(m[0])}: 궤적 x–y (두 제어기 모두 성공)")
        axes[row, 1].axhline(25, color="0.5", lw=0.8)
        axes[row, 1].axhline(-25, color="0.5", lw=0.8)
        axes[row, 1].set_ylabel("조향각 δ (°)")
        axes[row, 1].set_title(f"seed {int(m[0])}: 조향각")
    axes[2, 0].set_xlabel("x (m)")
    axes[2, 1].set_xlabel("t (s)")
    axes[0, 0].legend(fontsize=8, loc="upper right")
    h, l_ = axes[0, 1].get_legend_handles_labels()
    fig.legend(h, l_, fontsize=8, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.012))
    fig.suptitle("F7. v2 MPC(교사) vs Student S10(입력 9 + ψ) — E3 paper 대표 에피소드", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    save(fig, "F7_v2_vs_s10_trajectories", "v2 MPC vs Student S10 궤적·조향(대표 3 에피소드)",
         "docs/revision/data/r3_eval3_paper_steps.npz(재생, eval3 저장 outcome과 일치 검증)", "E3 (paper seed 2000~2099)",
         "eval3 seed 2000·2001·2002(처음 세 seed, 사전 고정)", "제출본 그림 1(Teacher–Student 궤적 비교 부분)", "fig_f3_to_f9.py")


def f8():
    """F8: v2 MPC vs S10 제어 비교 — E3 paper 전 에피소드. 제출본 그림 3 대응(속도 패널은 두 제어기 모두 규칙 기반이라 제외)."""
    d = _r3()
    names = [k for k in d.files if k.startswith("v2mpc_ep") and not k.endswith("_meta")]
    get = lambda who: np.concatenate([d[k.replace("v2mpc", who)] for k in names])  # noqa: E731
    A, B = get("v2mpc"), get("S10")
    fig, ax = plt.subplots(2, 2, figsize=(13, 8))
    bins = np.linspace(-25.5, 25.5, 52)
    ax[0, 0].hist(A[:, 5], bins=bins, histtype="step", lw=1.6, color=C_V2, label="v2 MPC")
    ax[0, 0].hist(B[:, 5], bins=bins, histtype="step", lw=1.6, color=C_S10, label="S10")
    ax[0, 0].set_xlabel("차량 입력 δ (°)")
    ax[0, 0].set_ylabel("스텝 수")
    ax[0, 0].set_title("(a) 조향각 분포")
    ax[0, 0].legend(fontsize=8)
    yb = np.linspace(-0.15, 0.45, 61)
    ax[0, 1].hist(A[:, 2], bins=yb, histtype="step", lw=1.6, color=C_V2, label="v2 MPC")
    ax[0, 1].hist(B[:, 2], bins=yb, histtype="step", lw=1.6, color=C_S10, label="S10")
    ax[0, 1].axvline(0, color="0.4", ls="--", lw=0.8)
    ax[0, 1].axvline(0.30, color="0.4", ls=":", lw=0.8)
    ax[0, 1].set_xlabel("y (m)")
    ax[0, 1].set_ylabel("스텝 수")
    ax[0, 1].set_title("(b) 횡방향 위치 분포")
    ax[0, 1].legend(fontsize=8)
    tgt = {"KEEP_L2": 0.0, "RETURN_TO_L2": 0.0, "EVADE_L": 0.30, "KEEP_L1": 0.30}
    xx = np.arange(4)
    for k, (M, c, lab) in enumerate(((A, C_V2, "v2 MPC"), (B, C_S10, "S10"))):
        rms = []
        for si, S in enumerate(STATE_ORDER):
            e = M[M[:, 6] == si, 2] - tgt[S]
            rms.append(np.sqrt(np.mean(e ** 2)))
        ax[1, 0].bar(xx + (k - 0.5) * 0.38, rms, 0.38, color=c, label=lab)
    ax[1, 0].set_xticks(xx, STATE_ORDER, fontsize=8)
    ax[1, 0].set_ylabel("RMS |y − 목표선| (m)")
    ax[1, 0].set_title("(c) 상태별 목표 추종 오차(RMS)")
    ax[1, 0].legend(fontsize=8)
    r3 = json.load(open(DATA_DIR / "r3_eval3_stats.json", encoding="utf-8"))["table17_paper"]
    labs = ["조향각 변화율\n(deg/step)", "조향각 jerk\n(deg/step²)"]
    tv = [r3["steering_rate"]["teacher"], r3["steering_jerk"]["teacher"]]
    sv = [r3["steering_rate"]["student"], r3["steering_jerk"]["student"]]
    x2 = np.arange(2)
    ax[1, 1].bar(x2 - 0.19, tv, 0.38, color=C_V2, label="v2 MPC")
    ax[1, 1].bar(x2 + 0.19, sv, 0.38, color=C_S10, label="S10")
    for xi, t, s in zip(x2, tv, sv):
        ax[1, 1].text(xi - 0.19, t + 0.02, f"{t:.3f}", ha="center", fontsize=8)
        ax[1, 1].text(xi + 0.19, s + 0.02, f"{s:.3f}", ha="center", fontsize=8)
    ax[1, 1].set_xticks(x2, labs)
    ax[1, 1].set_ylabel("평균 |차분|")
    ax[1, 1].set_title("(d) 부드러움(표 17 재측정)")
    ax[1, 1].set_ylim(0, 1.1)
    ax[1, 1].legend(fontsize=8, loc="upper right")
    fig.suptitle("F8. v2 MPC vs Student S10 제어 비교 — E3 paper 100 에피소드 폐루프(둘 다 100/100 성공)", fontsize=12)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    save(fig, "F8_v2_vs_s10_control", "v2 MPC vs Student S10 제어 비교(조향 분포·위치 분포·추종 오차·부드러움)",
         "docs/revision/data/r3_eval3_paper_steps.npz, r3_eval3_stats.json", "E3 (paper seed 2000~2099, 전 스텝)",
         "선택 없음(전 에피소드·전 스텝)", "제출본 그림 3(Teacher와 Student 제어 비교, 학습 데이터 기반) — 폐루프 기반으로 대체",
         "fig_f3_to_f9.py")


def f9():
    """F9: 계산시간 분위수 — R2 단일 실행(공식 조건). 원시 배열 미저장이라 분위수 막대(p50·p95·p99·max)."""
    r2 = json.load(open(DATA_DIR / "r2_timing_supplement/r2_timing.json", encoding="utf-8"))
    items = [("baseline v1.1 MPC", r2["baseline_v11"]["mpc_solve_ms"], C_BASE), ("v2 MPC", r2["v2_mpc_solve_ms"], C_V2),
             ("S10 PyTorch e2e", r2["s10_pytorch_e2e_ms"], C_S10), ("S10 ONNX e2e", r2["s10_onnx_e2e_ms"], C_ONNX)]
    qs = ["p50", "p95", "p99", "max"]
    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(qs))
    w = 0.2
    for k, (lab, s, c) in enumerate(items):
        v = [s[q] for q in qs]
        ax.bar(x + (k - 1.5) * w, v, w, color=c, label=lab)
        for xi, val in zip(x, v):
            ax.text(xi + (k - 1.5) * w, val * 1.12, f"{val:.3f}", ha="center", fontsize=7, rotation=90)
    ax.set_yscale("log")
    ax.set_ylim(0.01, 80)
    plain_log_ticks(ax, [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50])
    ax.set_xticks(x, ["p50", "p95", "p99 (주 지표)", "max"])
    ax.set_ylabel("시간 (ms, 로그 축)")
    ax.axhline(50, color="#cf222e", ls="--", lw=1)
    ax.text(3.45, 38, "20Hz 예산 50 ms", color="#cf222e", fontsize=8, ha="right")
    ax.set_title("F9. 계산시간 분위수 — 같은 MPC 호출 입력(paper seed 0~99), 스레드 1, R2 단일 실행", fontsize=11)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "F9_timing_quantiles", "계산시간 분위수 — baseline MPC / v2 MPC / S10 PyTorch / S10 ONNX",
         "docs/revision/data/r2_timing_supplement/r2_timing.json", "T0-H1 (paper seed 0~99, 공식 조건 True)",
         "선택 없음(전 MPC 호출)", "제출본 표 16·18의 그림 대응(제출본에 해당 그림 없음 — 신설)", "fig_f3_to_f9.py")


if __name__ == "__main__":
    for fn in (f3, f4, f5, f6, f7, f8, f9):
        fn()
