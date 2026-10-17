"""
C트랙 37건(설명 안 됨) 확정 실험 (읽기 전용, 분석 전용). baseline은 전혀 건드리지 않고,
**옛 MPC 인스턴스의 P만** 표준 QP 스케일(전부 x2 -- qy,qpsi,rdelta,rddelta 동시 2배,
`legacy_2025/final_hierarchical_backup_thesis_1204.py:855-881`(구 legacy_2025/code_backup/final_hierarchical_backup.py)의 self.P를 그대로 2배)로 바꾼 변형을
이 스크립트 안에서만 만들어 37건을 재실행한다. old 코드 파일 자체는 수정하지 않는다
(런타임에 인스턴스 속성만 교체, `old_mpc.P = old_mpc.P * 2`).

판정: 이 변형(P만 2배, rΔδ 크기벌점 구조와 위치제약 ±0.45는 원래 old 그대로 유지)의
출력이 baseline과 얼마나 가까워지는지로 "P 스케일링 버그가 잔여 원인인지"를 확인한다.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from thesis_v2.baseline import config
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.tests.compare.old_mpc_wrapper import build_old_mpc, solve_old

_DEG2RAD = math.pi / 180.0

ROWS_PATH = (Path(__file__).resolve().parents[2] / "thesis_v2" / "results" /
             "c_track_1080grid" / "c_track_grid_rows.json")
OUT_PATH = Path(__file__).resolve().parent / "out" / "c_track_37_pscaled_retest.json"


def main():
    rows = json.load(open(ROWS_PATH, encoding="utf-8"))
    unexplained = [r for r in rows if r["label"] == "설명 안 됨(버그 후보)" and r["plausible"]]
    print(f"재실행 대상: {len(unexplained)}건")

    old_mpc = build_old_mpc(N=config.N, dt=config.DT, qy=config.QY, qpsi=config.QPSI,
                             rdelta=config.RDELTA, rddelta=config.RDDELTA)
    old_mpc.P = old_mpc.P * 2  # <-- 유일한 변경: P 표준 스케일(x2), rΔδ 구조·위치제약은 그대로

    new_mpc = OSQPMPC()

    results = []
    n_vanished = 0
    n_persisted = 0
    for r in unexplained:
        y, psi_deg, v, target_y, state = r["y"], r["psi_deg"], r["v"], r["target_y"], r["state"]
        psi_rad = psi_deg * _DEG2RAD
        delta_pscaled, ok_pscaled = solve_old(old_mpc, y, psi_rad, v, target_y)
        res_new = new_mpc.solve(y0=y, psi0_rad=psi_rad, v0=v, target_y=target_y, state_name=state)
        diff_before = r["diff_deg"]
        diff_after = abs(delta_pscaled - res_new.delta_deg)
        vanished = diff_after <= 5.0  # 같은 "작은 차이" 기준 재사용(rΔδ 구조 차이 수준)
        if vanished:
            n_vanished += 1
        else:
            n_persisted += 1
        results.append({
            "y": y, "psi_deg": psi_deg, "v": v, "target_y": target_y, "state": state,
            "delta_old_original": r["delta_old_deg"], "delta_new": r["delta_new_deg"],
            "diff_before_deg": diff_before,
            "delta_old_pscaled": delta_pscaled, "ok_pscaled": ok_pscaled,
            "diff_after_deg": diff_after, "vanished": vanished,
        })

    print(f"차이 소멸(<=5deg): {n_vanished}건")
    print(f"잔존(>5deg): {n_persisted}건")
    print()
    for r in results:
        if not r["vanished"]:
            print(f"y={r['y']} psi={r['psi_deg']} v={r['v']} target={r['target_y']} "
                  f"state={r['state']} | old(원본)={r['delta_old_original']:.3f} "
                  f"old(P x2)={r['delta_old_pscaled']:.3f} new={r['delta_new']:.3f} "
                  f"diff_before={r['diff_before_deg']:.3f} diff_after={r['diff_after_deg']:.3f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"n_total": len(unexplained), "n_vanished": n_vanished,
                    "n_persisted": n_persisted, "results": results}, f,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
