"""
2단계-C 재검토: seed=85의 실제(MPC) 헤딩·조향 시계열과, 회피 가능함이 확인된 최대노력
(bang-bang) 궤적의 헤딩·조향 시계열을 나란히 비교한다. "MPC 비용함수가 장애물을 인지하지
않고 목표 차선만 추종하며, 헤딩 가중치(qpsi)로 궤적이 완만해진다"는 재분류 근거의 시각적
증거. baseline 코드는 수정하지 않음(읽기 전용, vehicle.step/collision만 재사용).

사용(저장소 루트에서): .venv\\Scripts\\python.exe repro\\2c_analysis\\seed85_heading_steering_compare.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from thesis_v2.baseline.world import generate_scenario  # noqa: E402
import avoidance_feasibility_recheck as afr  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[2] / "thesis_v2" / "results"
OUT_DIR = Path(__file__).resolve().parent / "out"
BATTERY_FOLDER = "20260917_221415_DESKTOP-MDCKRJS_baseline_P"
SEED = 85


def load_actual():
    npz = np.load(RESULTS_DIR / BATTERY_FOLDER / f"paper_seed{SEED}_steps.npz", allow_pickle=True)
    return npz


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    actual = load_actual()
    n_actual = len(actual["t"])

    sc = generate_scenario(SEED)
    fg0 = sc.obstacles[0].x_near - 0.20
    collided, hit_bound, trace = afr.bang_bang_collision(fg0, sc.y0, sc.v0, sc.psi0_deg)
    assert not collided, "bang-bang 궤적이 이 front_gap0에서 충돌하면 안 됨(이미 검증됨)"

    plot_window = n_actual + 15  # 실제 에피소드 길이 근방까지만 플롯(그 이후는 관심 밖)
    trace_plot = trace[:plot_window]
    bb_steps = [t[0] for t in trace_plot]
    bb_psi = [t[3] for t in trace_plot]      # deg
    bb_delta = [t[4] for t in trace_plot]    # deg

    actual_steps = list(range(1, n_actual + 1))
    actual_psi = [np.degrees(float(p)) for p in actual["psi"]]
    actual_delta = [float(d) for d in actual["delta_final"]]

    n_compare = n_actual  # 실제 충돌까지 24 step만 비교(그 이후 실제 데이터가 없음)

    lines = [
        f"# seed={SEED}: 실제(MPC) vs 최대노력(bang-bang) 헤딩·조향 비교 (step 1~{n_compare})",
        "",
        "| step | 실제 psi(deg) | bang-bang psi(deg) | 실제 delta_final(deg) | bang-bang delta(deg) |",
        "|---|---|---|---|---|",
    ]
    for i in range(n_compare):
        lines.append(f"| {i+1} | {actual_psi[i]:.2f} | {bb_psi[i]:.2f} | "
                      f"{actual_delta[i]:.2f} | {bb_delta[i]:.2f} |")
    table_path = OUT_DIR / "seed85_heading_steering_compare.md"
    table_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {table_path}")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    ax1.plot(actual_steps, actual_psi, "-o", ms=3, color="tab:red", label="actual (MPC) psi")
    ax1.plot(bb_steps, bb_psi, "--", color="tab:blue", label="bang-bang psi (feasible avoidance)")
    ax1.axvline(n_actual, color="gray", ls=":", lw=1, label="collision step")
    ax1.set_ylabel("psi (deg)")
    ax1.legend(fontsize=8)
    ax1.set_title(f"seed={SEED}: actual MPC trajectory vs max-effort (bang-bang) feasible trajectory")

    ax2.plot(actual_steps, actual_delta, "-o", ms=3, color="tab:red", label="actual (MPC) delta_final")
    ax2.plot(bb_steps, bb_delta, "--", color="tab:blue", label="bang-bang delta (always target +25deg)")
    ax2.axvline(n_actual, color="gray", ls=":", lw=1)
    ax2.axhline(25.0, color="black", lw=0.5, alpha=0.3)
    ax2.set_xlabel("step")
    ax2.set_ylabel("delta (deg)")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig_path = OUT_DIR / "seed85_heading_steering_compare.png"
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    print(f"wrote {fig_path}")

    print(f"\n요약: step11(실제 psi 피크 17.4deg) 이후 실제 MPC는 조향을 되돌리기 시작해(음의 delta)")
    print(f"목표(y=0.30)로 향한 헤딩을 줄이는 반면, bang-bang은 계속 +25deg를 유지해 훨씬 빠르게")
    print(f"y가 증가한다 -- MPC가 회피에 필요한 여유(margin={fg0 - afr.min_feasible_front_gap(sc.y0, sc.v0, sc.psi0_deg):.4f}m)를")
    print(f"쓰지 않고 목표 차선 추종(REQ-MPC-02 비용함수, qy/qpsi 가중치) 위주로 완만하게 도는 것이 원인.")


if __name__ == "__main__":
    main()
