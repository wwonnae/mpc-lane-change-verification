"""
C트랙 37건(rΔδ 구조 차이로 설명, 소거법 결론) 직접 증거 보강 (읽기 전용, 분석 전용).
`c_track_37_pscaled_retest.py`(P 표준 스케일 x2 -> 0/37 변화, 스케일링 가설 반증)에 이어,
이번엔 **옛 MPC의 rΔδ 항 자체를 차분형(baseline과 같은 구조)으로 바꾼 변형**을 만들어
37건을 재실행한다. old 코드 파일은 수정하지 않고, 런타임에 인스턴스 속성(`old_mpc.P`)만
교체한다(P의 y/psi 블록 스케일링은 옛 코드 그대로 raw qy/qpsi 유지 -- 이번 실험은 오직
"rΔδ가 차분형이면 차이가 사라지는가"만 격리해서 본다).

이 스크립트가 "옛 MPC 코드 자체를 변경"하는 게 아니라 "분석 스크립트 안에서 옛 MPC
인스턴스의 P만 교체"하는 것임에 유의(repro/docs/WORK_RULES.md: thesis_v2/tests/compare/만 옛 코드 import
허용, 이 분석은 그 wrapper를 그대로 재사용).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import scipy.sparse as sp

from thesis_v2.baseline import config
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.tests.compare.old_mpc_wrapper import build_old_mpc, solve_old

_DEG2RAD = math.pi / 180.0

ROWS_PATH = (Path(__file__).resolve().parents[2] / "thesis_v2" / "results" /
             "c_track_1080grid" / "c_track_grid_rows.json")
OUT_PATH = Path(__file__).resolve().parent / "out" / "c_track_37_rdelta_diffstyle_retest.json"


def build_diffstyle_P(old_mpc, qy: float, qpsi: float, rdelta: float, rddelta: float):
    """옛 MPC의 변수 인덱싱(_idx_y/_idx_psi/_idx_u, n_ctrl=N-1)을 그대로 쓰되, u 블록만
    baseline과 같은 차분벌점 구조(비대각)로 재구성. y/psi 블록은 옛 코드 그대로(raw qy,qpsi,
    스케일링 손대지 않음 -- rΔδ 구조 효과만 격리)."""
    N = old_mpc.N
    n_ctrl = old_mpc.n_ctrl  # N-1
    n_vars = old_mpc.n_vars
    rows, cols, vals = [], [], []
    for i in range(N):
        rows.append(old_mpc._idx_y(i)); cols.append(old_mpc._idx_y(i)); vals.append(qy)
        rows.append(old_mpc._idx_psi(i)); cols.append(old_mpc._idx_psi(i)); vals.append(qpsi)

    diag = np.zeros(n_ctrl)
    diag[0] += rdelta
    for i in range(1, n_ctrl):
        diag[i] += rddelta
        diag[i - 1] += rddelta
    for k in range(n_ctrl):
        rows.append(old_mpc._idx_u(k)); cols.append(old_mpc._idx_u(k)); vals.append(2 * diag[k])
    for i in range(1, n_ctrl):
        c = -2 * rddelta
        rows.append(old_mpc._idx_u(i)); cols.append(old_mpc._idx_u(i - 1)); vals.append(c)
        rows.append(old_mpc._idx_u(i - 1)); cols.append(old_mpc._idx_u(i)); vals.append(c)

    # 위 y/psi 대각 항은 옛 코드 관례(diag 값 자체가 2배 아님, self.P=sp.diags(P_diag)와
    # 동일하게 raw 값 사용)와 맞추기 위해 u 블록만 표준 형태(2*계수)로 짓고 y/psi는 raw 유지.
    return sp.coo_matrix((vals, (rows, cols)), shape=(n_vars, n_vars)).tocsc()


def main():
    rows = json.load(open(ROWS_PATH, encoding="utf-8"))
    unexplained = [r for r in rows if r["label"] == "rΔδ 구조 차이로 설명됨(포화영역)"
                   and r["plausible"]]
    print(f"재실행 대상: {len(unexplained)}건")

    old_mpc = build_old_mpc(N=config.N, dt=config.DT, qy=config.QY, qpsi=config.QPSI,
                             rdelta=config.RDELTA, rddelta=config.RDDELTA)
    old_mpc.P = build_diffstyle_P(old_mpc, config.QY, config.QPSI, config.RDELTA, config.RDDELTA)

    new_mpc = OSQPMPC()

    results = []
    n_vanished = 0
    n_persisted = 0
    for r in unexplained:
        y, psi_deg, v, target_y, state = r["y"], r["psi_deg"], r["v"], r["target_y"], r["state"]
        psi_rad = psi_deg * _DEG2RAD
        delta_diffstyle, ok_diffstyle = solve_old(old_mpc, y, psi_rad, v, target_y)
        res_new = new_mpc.solve(y0=y, psi0_rad=psi_rad, v0=v, target_y=target_y, state_name=state)
        diff_before = r["diff_deg"]
        diff_after = abs(delta_diffstyle - res_new.delta_deg)
        vanished = diff_after <= 1.0  # 엄격한 기준(수치오차 수준)
        if vanished:
            n_vanished += 1
        else:
            n_persisted += 1
        results.append({
            "y": y, "psi_deg": psi_deg, "v": v, "target_y": target_y, "state": state,
            "delta_old_original": r["delta_old_deg"], "delta_new": r["delta_new_deg"],
            "diff_before_deg": diff_before,
            "delta_old_diffstyle": delta_diffstyle, "ok_diffstyle": ok_diffstyle,
            "diff_after_deg": diff_after, "vanished": vanished,
        })

    print(f"차이 소멸(<=1deg): {n_vanished}건")
    print(f"잔존(>1deg): {n_persisted}건")
    print()
    for r in results:
        status = "소멸" if r["vanished"] else "잔존"
        print(f"[{status}] y={r['y']} psi={r['psi_deg']} v={r['v']} target={r['target_y']} "
              f"state={r['state']} | old(원본)={r['delta_old_original']:.3f} "
              f"old(rΔδ차분형)={r['delta_old_diffstyle']:.3f} new={r['delta_new']:.3f} "
              f"diff_before={r['diff_before_deg']:.3f} diff_after={r['diff_after_deg']:.4f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"n_total": len(unexplained), "n_vanished": n_vanished,
                    "n_persisted": n_persisted, "results": results}, f,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
