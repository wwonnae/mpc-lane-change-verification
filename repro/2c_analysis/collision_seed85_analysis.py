"""
2단계-C 결과 분석 (2): 논문 시나리오(paper) 100 에피소드 중 유일한 충돌(seed=85) 원인 분석.
읽기 전용 -- 결과 폴더(steps.npz/episodes.json)와 baseline 코드는 수정하지 않는다.

산출물(repro/2c_analysis/out/):
- collision_seed85_pre_impact.md : 충돌 직전 스텝별 표
- collision_seed85_trajectory.png : 궤적 + 차체/장애물 사각형
- collision_seed85_vs_seed34_compare.md : 근접-장애물 성공 사례(seed34)와의 비교

사용(저장소 루트에서): .venv\\Scripts\\python.exe repro\\2c_analysis\\collision_seed85_analysis.py
"""
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config
from thesis_v2.baseline.world import generate_scenario

RESULTS_DIR = Path(__file__).resolve().parents[2] / "thesis_v2" / "results"
OUT_DIR = Path(__file__).resolve().parent / "out"
FOLDER = "20260917_221415_DESKTOP-MDCKRJS_baseline_P"  # 배터리 실행(최초 발견 폴더). AC 폴더도
# 같은 seed=85에서 동일하게 충돌함을 battery_vs_ac_compare.py에서 별도 확인.

COLLISION_SEED = 85
COMPARE_SEED = 34  # 더 가까운 장애물(fg0=0.506) + 더 빠른 속도(v0=0.474)인데도 성공한 사례


def _rect_corners(x, y, psi, length, width, rear_at_origin=True):
    if rear_at_origin:
        local = [(0, -width / 2), (length, -width / 2), (length, width / 2), (0, width / 2)]
    else:
        local = [(-length / 2, -width / 2), (length / 2, -width / 2),
                  (length / 2, width / 2), (-length / 2, width / 2)]
    ch, sh = math.cos(psi), math.sin(psi)
    return [(x + lx * ch - ly * sh, y + lx * sh + ly * ch) for lx, ly in local]


def load_steps(seed: int):
    npz = np.load(RESULTS_DIR / FOLDER / f"paper_seed{seed}_steps.npz", allow_pickle=True)
    return {k: npz[k] for k in npz.files}


def write_pre_impact_table(steps: dict, out_path: Path):
    n = len(steps["t"])
    lines = [
        f"# seed={COLLISION_SEED} 충돌 직전 스텝 표 (전체 {n} step, 30 step 미만이면 전부 표시)",
        "",
        "| step | state | x | y | psi(deg) | delta_raw | delta_final | front_gap | left_clear | right_clear | solver_status | fallback | saturated(|d|>=25-0.01) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    start = max(0, n - 30)
    for i in range(start, n):
        psi_deg = math.degrees(float(steps["psi"][i]))
        sat = abs(float(steps["delta_final"][i])) >= config.DELTA_MAX_DEG - 0.01
        lines.append(
            f"| {i+1} | {steps['state'][i]} | {float(steps['x'][i]):.4f} | {float(steps['y'][i]):.4f} | "
            f"{psi_deg:.2f} | {float(steps['delta_mpc_raw'][i]):.3f} | {float(steps['delta_final'][i]):.3f} | "
            f"{float(steps['front_gap'][i]):.4f} | {bool(steps['left_clear'][i])} | {bool(steps['right_clear'][i])} | "
            f"{steps['solver_status'][i]} | {bool(steps['fallback_used'][i])} | {sat} |"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


def plot_trajectory(steps: dict, scenario, out_path: Path):
    fig, ax = plt.subplots(figsize=(9, 4))
    xs = steps["x"].astype(float)
    ys = steps["y"].astype(float)
    ax.plot(xs, ys, "-o", ms=3, color="tab:blue", label="vehicle path (rear axle)")

    n = len(xs)
    # 차체 사각형: 시작/중간/충돌 시점만 표시(과밀 방지)
    highlight_idx = sorted(set([0, n // 2, n - 1]))
    for i in highlight_idx:
        corners = _rect_corners(float(steps["x"][i]), float(steps["y"][i]), float(steps["psi"][i]),
                                 config.L, config.B, rear_at_origin=True)
        corners.append(corners[0])
        cx, cy = zip(*corners)
        style = dict(color="red", lw=2) if i == n - 1 else dict(color="tab:blue", lw=1, alpha=0.5)
        ax.plot(cx, cy, **style)
        ax.annotate(f"step{i+1}", (float(steps["x"][i]), float(steps["y"][i])), fontsize=8)

    for obs in scenario.obstacles:
        ax.add_patch(plt.Rectangle((obs.x_near, obs.y_lo), obs.x_far - obs.x_near,
                                    obs.y_hi - obs.y_lo, color="black", alpha=0.3, label="obstacle"))

    ax.axhline(0.0, color="gray", ls="--", lw=0.5)
    ax.axhline(config.W, color="gray", ls="--", lw=0.5)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"paper seed={COLLISION_SEED}: collision at step {n} (red = vehicle footprint at impact)")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize=8, loc="upper left")
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def write_compare_table(out_path: Path):
    sc85 = generate_scenario(COLLISION_SEED)
    sc34 = generate_scenario(COMPARE_SEED)
    fg85 = sc85.obstacles[0].x_near - config.L
    fg34 = sc34.obstacles[0].x_near - config.L
    lines = [
        "# seed=85(충돌) vs seed=34(성공, 더 근접·더 빠름) 초기조건 비교",
        "",
        "| seed | 결과 | front_gap0(m) | v0(m/s) | y0(m) | 목표까지 순 이동거리(초기 y0 -> 차선변경 완료 필요폭 0.15) |",
        "|---|---|---|---|---|---|",
        f"| 85 | 충돌 | {fg85:.4f} | {sc85.v0:.4f} | {sc85.y0:.4f} | {0.15 - sc85.y0:.4f} |",
        f"| 34 | 성공 | {fg34:.4f} | {sc34.v0:.4f} | {sc34.y0:.4f} | {0.15 - sc34.y0:.4f} |",
        "",
        "**해석**: seed34은 장애물이 더 가깝고(fg0 0.506<0.566) 속도도 더 빠른데도(v0 0.474>0.394)",
        "성공했다. 차이는 초기 횡위치 y0 -- seed34는 y0=+0.129로 이미 차선변경 목표 방향에",
        "가까워 장애물(폭 [-0.075,0.075]) 옆을 비켜가는 데 필요한 순 이동거리가 약 0.02m뿐이지만,",
        "seed85는 y0=-0.046로 반대쪽에서 출발해 약 0.20m를 이동해야 한다. front_gap0/v0로",
        "정해지는 '충돌까지 남은 시간'과 y0로 정해지는 '회피에 필요한 시간'의 상대적 크기가",
        "결과를 가른다 -- FSM의 EVADE_L 트리거(front_gap<G_TRIG)는 이 둘의 상대적 크기를",
        "전혀 고려하지 않는 거리 단일 기준이라는 것이 이 충돌의 구조적 원인이다.",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    steps = load_steps(COLLISION_SEED)
    scenario = generate_scenario(COLLISION_SEED)
    write_pre_impact_table(steps, OUT_DIR / "collision_seed85_pre_impact.md")
    plot_trajectory(steps, scenario, OUT_DIR / "collision_seed85_trajectory.png")
    write_compare_table(OUT_DIR / "collision_seed85_vs_seed34_compare.md")


if __name__ == "__main__":
    main()
