"""
S3 히트맵에 사전 계산 물리 한계(bang-bang 최대노력 회피의 최소 feasible front_gap0)를
경계선으로 겹쳐 그린다. `avoidance_feasibility_recheck.py`(2단계-C 재검토, seed=85 재분류
근거)의 `min_feasible_front_gap`을 그대로 재사용한다(중복 구현 금지, baseline 미수정).

산출물: repro/2c_analysis/out/s3_with_physical_limit.png,
        repro/2c_analysis/out/s3_physical_limit_comparison.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from thesis_v2.baseline import config
from avoidance_feasibility_recheck import min_feasible_front_gap  # 재사용, 재구현 아님

ROBUST_DIR = (Path(__file__).resolve().parents[2] / "thesis_v2" / "results" /
              "20260922_115241_3PC104_baseline_v1.1_ROBUSTNESS" / "R3_s3_grid")
OUT_DIR = Path(__file__).resolve().parent / "out"


def main():
    grid = json.load(open(ROBUST_DIR / "s3_grid.json", encoding="utf-8"))
    front_gaps = np.array(grid["front_gap0_values"])
    y0s = np.array(grid["y0_values"])
    outcome_grid = grid["outcome_grid"]  # [i][j], i=front_gap idx, j=y0 idx
    v_fixed = grid["v0_fixed"]

    # 물리 한계: y0별 최소 feasible front_gap0 (bang-bang, v=V_MAX, psi0=0 -- S3와 동일 조건)
    physical_limit = {}
    for y0 in y0s:
        physical_limit[float(y0)] = min_feasible_front_gap(float(y0), v=v_fixed, psi0_deg=0.0)

    # 관측된 "제어기 실패 경계": 각 y0 열에서 충돌이 발생한 가장 큰 front_gap0(없으면 None)
    controller_boundary = {}
    for j, y0 in enumerate(y0s):
        collided_fgs = [front_gaps[i] for i in range(len(front_gaps))
                        if outcome_grid[i][j] == "충돌"]
        controller_boundary[float(y0)] = max(collided_fgs) if collided_fgs else None

    comparison = []
    for y0 in y0s:
        y0f = float(y0)
        phys = physical_limit[y0f]
        ctrl = controller_boundary[y0f]
        comparison.append({
            "y0": y0f,
            "physical_min_feasible_front_gap0": phys,
            "controller_observed_failure_upto": ctrl,
            "controller_margin_over_physical": (ctrl - phys) if ctrl is not None else None,
        })

    with open(OUT_DIR / "s3_physical_limit_comparison.json", "w", encoding="utf-8") as f:
        json.dump({"v_fixed": v_fixed, "comparison": comparison}, f, ensure_ascii=False, indent=2)

    # 그림: 기존 히트맵 재사용 + 물리 한계선 겹쳐 그리기
    _EN = {"성공": "success", "충돌": "collision"}
    outcome_labels = sorted(set(v for row in outcome_grid for v in row))
    label_to_idx = {lab: k for k, lab in enumerate(outcome_labels)}
    numeric = np.array([[label_to_idx[outcome_grid[i][j]] for j in range(len(y0s))]
                         for i in range(len(front_gaps))])

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(numeric.T, origin="lower", aspect="auto",
                    extent=[front_gaps[0], front_gaps[-1], y0s[0], y0s[-1]], cmap="tab10")
    phys_curve = [physical_limit[float(y0)] for y0 in y0s]
    ax.plot(phys_curve, y0s, color="black", linewidth=2.5, linestyle="--",
            label="physical limit (bang-bang min feasible front_gap0)")
    ax.set_xlabel("front_gap0 (m)")
    ax.set_ylabel("y0 (m)")
    ax.set_title("S3 boundary map vs physical limit (v=V_MAX, psi0=0)")
    ax.legend(loc="upper right")
    cbar = fig.colorbar(im, ticks=list(label_to_idx.values()))
    cbar.ax.set_yticklabels([_EN.get(lab, lab) for lab in outcome_labels])
    fig.tight_layout()
    fig.savefig(OUT_DIR / "s3_with_physical_limit.png", dpi=120)
    plt.close(fig)

    for c in comparison:
        print(c)


if __name__ == "__main__":
    main()
