"""
그림 F1·F2용 baseline v1.1 E2(paper seed 200~299) 스텝 데이터 캐시. R1과 같은 재생 방식·같은 검증(저장 집계 9개 정확히 일치할 때만 저장).
출력: docs/revision/data/baseline_e2_steps.npz (에피소드별 배열 + 메타)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline.mpc import OSQPMPC  # noqa: E402
from thesis_v2.baseline.runner import run_episode  # noqa: E402
from thesis_v2.baseline.world import generate_scenario  # noqa: E402

EV2 = ROOT / "thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/all_eval_v2_summary.json"
OUT = ROOT / "docs/revision/data/baseline_e2_steps.npz"
STATES = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2", "SAFE_STOP"]
COLS = ["t", "x", "y", "psi_deg", "v_pre", "delta_final", "delta_raw", "state_idx", "front_gap", "is_mpc"]


def load():
    if OUT.exists():
        return np.load(OUT, allow_pickle=True)
    mpc = OSQPMPC()
    eps = [(s, generate_scenario(s)) for s in range(200, 300)]
    res = [(s, sc, run_episode(sc, mpc=mpc)) for s, sc in eps]
    stored = json.load(open(EV2, encoding="utf-8"))["new_eval"]["paper"]["baseline"]
    rs = [r for _, _, r in res]
    dchk = sum(r.delta_checked_count for r in rs)
    chk = dict(n_success=sum(r.outcome == "성공" for r in rs), n_collision=sum(r.outcome == "충돌" for r in rs),
               safe_stop_count=sum(r.outcome == "SAFE_STOP" for r in rs),
               delta_within_tolerance_rate=1 - sum(r.delta_violation_count for r in rs) / dchk,
               solver_fail_count=sum(r.solver_fail_count for r in rs), fallback_count=sum(r.fallback_count for r in rs))
    bad = {k: (stored[k], v) for k, v in chk.items() if stored[k] != v}
    if bad:
        raise SystemExit(f"저장 집계와 불일치 — 중단: {bad}")
    arrs = {}
    for i, (s, sc, r) in enumerate(res):
        rows = r.logger.rows
        v_pre = [sc.v0] + [row["v"] for row in rows[:-1]]
        arrs[f"ep{i}"] = np.array([[row["t"], row["x"], row["y"], math.degrees(row["psi"]), v, row["delta_final"],
                                    row["delta_mpc_raw"], STATES.index(row["state"]), row["front_gap"],
                                    1.0 if row["solver_status"] != "N/A" else 0.0] for row, v in zip(rows, v_pre)], float)
        ob = sc.obstacles[0]
        arrs[f"ep{i}_meta"] = np.array([s, sc.v0, sc.y0, ob.x_near, ob.x_far, ob.y_lo, ob.y_hi], float)
    arrs["outcomes"] = np.array([r.outcome for _, _, r in res])
    arrs["columns"] = np.array(COLS)
    np.savez_compressed(OUT, **arrs)
    print("검증 통과·캐시 저장:", chk)
    return np.load(OUT, allow_pickle=True)


if __name__ == "__main__":
    load()
