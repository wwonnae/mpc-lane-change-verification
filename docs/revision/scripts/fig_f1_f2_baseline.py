"""
그림 F1(baseline v1.1 대표 궤적)·F2(baseline 성능 종합). 데이터: baseline_e2_replay.py 캐시(E2, 저장 집계 일치 검증).
F1 대표 에피소드 선택 규칙(사전 고정): seed 200부터 오름차순으로 첫 번째 성공 1건 + 첫 번째 충돌 1건.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from fig_common import save, C_BASE, STATE_ORDER
from baseline_e2_replay import load, STATES

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from thesis_v2.baseline import config  # noqa: E402

ST_COLORS = {"KEEP_L2": "#d0d7de", "EVADE_L": "#ffd8b5", "KEEP_L1": "#c8e1ff", "RETURN_TO_L2": "#d8f3dc"}
SRC = "docs/revision/data/baseline_e2_steps.npz(재생, 저장 집계 일치 검증) · R1 통계"


def main():
    d = load()
    outc = list(d["outcomes"])
    seeds = [int(d[f"ep{i}_meta"][0]) for i in range(len(outc))]
    i_succ = next(i for i, o in enumerate(outc) if o == "성공")
    i_col = next(i for i, o in enumerate(outc) if o == "충돌")

    # ---------------- F1 ----------------
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5))
    for col, i in enumerate((i_succ, i_col)):
        a = d[f"ep{i}"]
        m = d[f"ep{i}_meta"]
        ax = axes[0, col]
        ax.plot(a[:, 1], a[:, 2], color=C_BASE, lw=1.8, label="baseline v1.1 차량 궤적(후륜 중심)")
        ax.add_patch(Rectangle((m[3], m[5]), m[4] - m[3], m[6] - m[5], color="0.35", alpha=0.7, label="장애물"))
        # 마지막 스텝의 차체 풋프린트(후륜 중심 기준 [0, L] x [-B/2, B/2], 헤딩만큼 회전) — 충돌은 차체 전단 기준
        xe, ye, pe = a[-1, 1], a[-1, 2], np.radians(a[-1, 3])
        corners = np.array([[0, -config.B / 2], [config.L, -config.B / 2], [config.L, config.B / 2], [0, config.B / 2], [0, -config.B / 2]])
        R = np.array([[np.cos(pe), -np.sin(pe)], [np.sin(pe), np.cos(pe)]])
        cw = corners @ R.T + [xe, ye]
        if outc[i] == "충돌":  # 충돌 패널만: 가로·세로 같은 축척으로 차체 모양 그대로(성공 패널은 x 범위가 길어 축척을 맞추지 않음)
            ax.plot(cw[:, 0], cw[:, 1], color="#cf222e", lw=1.2, label="충돌 스텝 차체(L×B, 회전 반영)")
            ax.set_aspect("equal", adjustable="box")
        ax.axhline(0.0, color="0.6", lw=0.8, ls="--", label="L2 중심(y=0)")
        ax.axhline(config.W, color="0.6", lw=0.8, ls=":", label="L1 중심(y=0.30)")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(f"({'a' if col == 0 else 'b'}) seed {seeds[i]} — {outc[i]}: 궤적 x–y")
        ax.legend(fontsize=7, loc="upper left")
        ax2 = axes[1, col]
        st = a[:, 7].astype(int)
        for k in range(len(a)):
            s = STATES[st[k]]
            if s in ST_COLORS:
                ax2.axvspan(a[k, 0] - 0.025, a[k, 0] + 0.025, color=ST_COLORS[s], lw=0)
        mpc = a[:, 9] > 0
        ax2.plot(a[:, 0], a[:, 5], color=C_BASE, lw=1.5, label="차량 입력 δ(후처리 후)")
        ax2.plot(a[mpc, 0], a[mpc, 6], ".", color="#0969da", ms=2.5, label="MPC 원출력 δ_raw")
        ax2.axhline(25, color="0.5", lw=0.8)
        ax2.axhline(-25, color="0.5", lw=0.8)
        ax2.set_xlabel("t (s)")
        ax2.set_ylabel("조향각 δ (°)")
        ax2.set_title(f"({'c' if col == 0 else 'd'}) seed {seeds[i]}: 조향각 (배경색 = FSM 상태)")
        from matplotlib.patches import Patch
        h, l_ = ax2.get_legend_handles_labels()
        h += [Patch(color=c) for c in ST_COLORS.values()]
        l_ += list(ST_COLORS)
        ax2.legend(h, l_, fontsize=7, loc="lower left", ncol=2)
    fig.suptitle("F1. baseline v1.1(제출본 설계의 정합 재구현) 대표 에피소드 — E2 paper", fontsize=12)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    save(fig, "F1_baseline_trajectories", "baseline v1.1 대표 에피소드 궤적·조향(성공 1, 충돌 1)", SRC, "E2 (paper seed 200~299)",
         f"seed 오름차순 첫 성공(seed {seeds[i_succ]}) + 첫 충돌(seed {seeds[i_col]})",
         "제출본 그림 1(Teacher 궤적 예시 부분)", "fig_f1_f2_baseline.py")

    # ---------------- F2 ----------------
    allr = np.concatenate([d[f"ep{i}"] for i in range(len(outc))])
    st = allr[:, 7].astype(int)
    names = [STATES[k] for k in st]
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    # (a) 체류 비율
    n = len(allr)
    dw = [100 * sum(1 for s in names if s == S) / n for S in STATE_ORDER]
    ax[0, 0].bar(STATE_ORDER, dw, color=C_BASE)
    for x, v in enumerate(dw):
        ax[0, 0].text(x, v + 0.5, f"{v:.1f}%", ha="center", fontsize=8)
    ax[0, 0].set_ylabel("체류 비율 (%)")
    ax[0, 0].set_title(f"(a) FSM 상태 체류 비율 (전 {n:,} 스텝)")
    ax[0, 0].tick_params(axis="x", labelsize=8)
    # (b) 조향 분포
    ax[0, 1].hist(allr[:, 5], bins=60, color=C_BASE)
    ax[0, 1].axvline(25, color="#cf222e", ls="--", lw=1, label="제약 ±25°")
    ax[0, 1].axvline(-25, color="#cf222e", ls="--", lw=1)
    ax[0, 1].set_xlabel("차량 입력 δ (°)")
    ax[0, 1].set_ylabel("스텝 수")
    ax[0, 1].set_title(f"(b) 조향각 분포 (평균 {allr[:, 5].mean():.2f}°, 표준편차 {allr[:, 5].std():.2f}°)")
    ax[0, 1].legend(fontsize=8)
    # (c) 횡방향 위치 분포(상태별)
    for S, c in zip(STATE_ORDER, ["#6e7781", "#fb8500", "#0969da", "#2da44e"]):
        msk = np.array([s == S for s in names])
        ax[0, 2].hist(allr[msk, 2], bins=np.linspace(-0.15, 0.45, 61), histtype="step", lw=1.5, color=c, label=S)
    ax[0, 2].axvline(0, color="0.3", ls="--", lw=0.8)
    ax[0, 2].axvline(config.W, color="0.3", ls=":", lw=0.8)
    ax[0, 2].set_xlabel("y (m)")
    ax[0, 2].set_ylabel("스텝 수")
    ax[0, 2].set_title("(c) 횡방향 위치 분포 (상태별)")
    ax[0, 2].legend(fontsize=7)
    # (d) 상태별 목표 추종 오차
    tgt = {"KEEP_L2": 0.0, "RETURN_TO_L2": 0.0, "EVADE_L": config.W, "KEEP_L1": config.W}
    me, rm = [], []
    for S in STATE_ORDER:
        msk = np.array([s == S for s in names])
        e = np.abs(allr[msk, 2] - tgt[S])
        me.append(e.mean())
        rm.append(np.sqrt((e ** 2).mean()))
    xx = np.arange(4)
    ax[1, 0].bar(xx - 0.2, me, 0.4, color=C_BASE, label="평균 |y − 목표선|")
    ax[1, 0].bar(xx + 0.2, rm, 0.4, color="#afb8c1", label="RMS")
    ax[1, 0].set_xticks(xx, STATE_ORDER, fontsize=8)
    ax[1, 0].set_ylabel("오차 (m)")
    ax[1, 0].set_title("(d) 상태별 목표 추종 오차")
    ax[1, 0].legend(fontsize=8)
    # (e) 헤딩
    ax[1, 1].boxplot([np.abs(allr[np.array([s == S for s in names]), 3]) for S in STATE_ORDER], tick_labels=STATE_ORDER,
                     showfliers=False)
    ax[1, 1].tick_params(axis="x", labelsize=8)
    ax[1, 1].set_ylabel("|ψ| (°)")
    ax[1, 1].set_title("(e) 상태별 헤딩 절댓값 (상자: 사분위, 수염: 1.5 IQR)")
    # (f) 제약 만족률
    import json
    from fig_common import DATA_DIR
    r1 = json.load(open(DATA_DIR / "r1_baseline_e2_stats.json", encoding="utf-8"))["constraints"]
    labs = ["조향 |δ_raw|≤25°", "속도 0~0.5 m/s", "위치 y(상태별)", "헤딩 |ψ|≤80°"]
    vals = [r1["delta_ok_pct_s19"], r1["v_ok_pct"], r1["y_ok_pct"], r1["psi_ok_pct"]]
    ax[1, 2].barh(labs, vals, color="#2da44e")
    for k, v in enumerate(vals):
        ax[1, 2].text(v - 1, k, f"{v:.2f}%", va="center", ha="right", color="white", fontsize=9)
    ax[1, 2].set_xlim(0, 100)
    ax[1, 2].set_xlabel("허용오차 내 만족률 (%)")
    ax[1, 2].set_title("(f) 제약 만족률 (허용오차: SETTINGS_DECISION §19)")
    fig.suptitle("F2. baseline v1.1 성능 종합 — E2 paper 100 에피소드 폐루프 (성공 95, 충돌 5)", fontsize=12)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    save(fig, "F2_baseline_summary", "baseline v1.1 성능 종합(체류·조향·위치·추종 오차·헤딩·제약 만족)", SRC,
         "E2 (paper seed 200~299, 전 스텝)", "선택 없음(전 에피소드·전 스텝)", "제출본 그림 2(MPC 성능 종합 분석)",
         "fig_f1_f2_baseline.py")


if __name__ == "__main__":
    main()
