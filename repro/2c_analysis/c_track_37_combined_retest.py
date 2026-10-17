"""
C트랙 37건 직접 증거 보강(2): rΔδ 차분형(위 스크립트) 단독으로는 7/37만 소멸했다 --
잔존 30건은 원래부터 알려진 **위치제약 차이**(old=+-0.45 고정 vs baseline=상태별)가 함께
작용하기 때문일 가능성이 높다. 이 스크립트는 옛 MPC에 (1) rΔδ 차분형 P **AND** (2) 그
state에 맞는 baseline 위치제약(lb/ub)까지 동시에 적용한 변형으로 37건을 재실행해, 두
요인을 합치면 정말 전부 사라지는지 확정한다. 읽기 전용, 분석 전용, baseline/old 코드
파일은 수정하지 않음(런타임 인스턴스 속성만 교체).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.tests.compare.old_mpc_wrapper import build_old_mpc, solve_old
from c_track_37_rdelta_diffstyle_retest import build_diffstyle_P

_DEG2RAD = math.pi / 180.0

ROWS_PATH = (Path(__file__).resolve().parents[2] / "thesis_v2" / "results" /
             "c_track_1080grid" / "c_track_grid_rows.json")
OUT_PATH = Path(__file__).resolve().parent / "out" / "c_track_37_combined_retest.json"


def set_old_y_bounds(old_mpc, lo: float, hi: float):
    for i in range(old_mpc.N):
        idx = old_mpc._idx_y(i)
        old_mpc.lb[idx] = lo
        old_mpc.ub[idx] = hi


def main():
    rows = json.load(open(ROWS_PATH, encoding="utf-8"))
    unexplained = [r for r in rows if r["label"] == "rΔδ 구조 차이로 설명됨(포화영역)"
                   and r["plausible"]]
    print(f"재실행 대상: {len(unexplained)}건")

    old_mpc = build_old_mpc(N=config.N, dt=config.DT, qy=config.QY, qpsi=config.QPSI,
                             rdelta=config.RDELTA, rddelta=config.RDDELTA)
    old_mpc.P = build_diffstyle_P(old_mpc, config.QY, config.QPSI, config.RDELTA, config.RDDELTA)

    new_mpc = OSQPMPC()

    n_vanished = 0
    n_persisted = 0
    results = []
    for r in unexplained:
        y, psi_deg, v, target_y, state = r["y"], r["psi_deg"], r["v"], r["target_y"], r["state"]
        lo, hi = config.POSITION_CONSTRAINTS[state]
        set_old_y_bounds(old_mpc, lo, hi)
        psi_rad = psi_deg * _DEG2RAD
        delta_combined, ok_combined = solve_old(old_mpc, y, psi_rad, v, target_y)
        res_new = new_mpc.solve(y0=y, psi0_rad=psi_rad, v0=v, target_y=target_y, state_name=state)
        diff_after = abs(delta_combined - res_new.delta_deg)
        vanished = diff_after <= 1.0
        if vanished:
            n_vanished += 1
        else:
            n_persisted += 1
        results.append({
            "y": y, "psi_deg": psi_deg, "v": v, "target_y": target_y, "state": state,
            "delta_old_original": r["delta_old_deg"], "delta_new": r["delta_new_deg"],
            "diff_before_deg": r["diff_deg"],
            "delta_old_combined": delta_combined, "ok_combined": ok_combined,
            "diff_after_deg": diff_after, "vanished": vanished,
        })

    print(f"차이 소멸(<=1deg): {n_vanished}건")
    print(f"잔존(>1deg): {n_persisted}건")
    print()
    for r in results:
        status = "소멸" if r["vanished"] else "잔존"
        print(f"[{status}] y={r['y']} psi={r['psi_deg']} v={r['v']} state={r['state']} | "
              f"old(원본)={r['delta_old_original']:.3f} old(combined)={r['delta_old_combined']:.3f} "
              f"new={r['delta_new']:.3f} diff_before={r['diff_before_deg']:.3f} "
              f"diff_after={r['diff_after_deg']:.4f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"n_total": len(unexplained), "n_vanished": n_vanished,
                    "n_persisted": n_persisted, "results": results}, f,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
