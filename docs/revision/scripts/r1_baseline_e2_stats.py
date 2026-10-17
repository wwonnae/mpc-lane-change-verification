"""
R1 — baseline v1.1 on E2(paper seed 200~299) 결정론적 재생 통계(DESIGN_REVISION §3-1, D3·D9). 분석 전용.

재생 방식은 eval 2회차(`thesis_v2/improved/run_eval_v2.py:run_paper`)와 같게: OSQPMPC 인스턴스 1개를 seed 200~299에 순서대로 재사용.
**검증**: eval 2회차 결과 파일에는 paper 에피소드별 outcome이 없고 집계만 있으므로, 저장된 집계 전부(성공·충돌·SAFE_STOP 수,
δ/ψ/y 허용오차 내 비율, solver 실패·fallback 수)가 재생 결과와 **정확히 일치**할 때만 통계를 저장한다. 하나라도 다르면 중단.

지표 정의(제출본 정의가 불명확한 항목은 CSV·본문에 정의를 명시):
- 차량 속도 = 각 스텝 운동에 쓰인 속도(갱신 전 v, 첫 스텝은 초기 v0). REQ-VEH-05로 이후 스텝은 v_cmd가 즉시 대입됨.
- 조향각 = 차량에 들어간 최종 조향(후처리 후 δ_final). MPC 원출력은 raw로 별도.
- |y| = L2 중심(y=0)으로부터의 거리(제출본 표 6 값이 이 정의에 가까움 — THESIS_REVISION_LOG 2026-09-25 표 6·14 항목),
  목표 추종 오차 = |y − 목표선(상태별)|(제출본 표 14, legacy_2025/backup/justify_mpc.py compute_tracking_error와 같은 정의). y·ψ는 갱신 후 값(로그).
- 변화율 = 에피소드 안에서만 차분(에피소드 경계 차분 제외).
- 제약 만족: 조향 |δ_raw| ≤ 25° + 허용오차(SETTINGS_DECISION §19 정정값 baseline 0.013731°, 저장 집계 대조용으로 기존 상수도 병기),
  속도 0 ≤ v ≤ V_MAX, y는 상태별 REQ-MPC-05 구간(metrics.y_within_tolerance, SAFE_STOP 제외), ψ ≤ 80°(+허용오차).

사용(저장소 루트): python docs/revision/scripts/r1_baseline_e2_stats.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline import config, metrics
from thesis_v2.baseline.fsm import FSMState, target_line_y
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.world import generate_scenario

EV2 = ROOT / "thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/all_eval_v2_summary.json"
OUT = ROOT / "docs/revision/data/r1_baseline_e2_stats.json"
SEEDS = list(range(200, 300))
STATES = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2", "SAFE_STOP"]
TOL_DELTA_S19_BASELINE = 0.013731  # SETTINGS_DECISION §19 baseline 정정값(deg)


def stats(a):
    a = np.asarray(a, float)
    if a.size == 0:
        return None
    return dict(n=int(a.size), mean=float(a.mean()), std=float(a.std()), min=float(a.min()), max=float(a.max()),
                rms=float(np.sqrt((a ** 2).mean())))


def main():
    mpc = OSQPMPC()
    results = [(s, generate_scenario(s)) for s in SEEDS]
    eps = []
    for s, sc in results:
        r = run_episode(sc, mpc=mpc)
        eps.append((s, sc, r))

    # ---- 저장 집계와 대조 ----
    stored = json.load(open(EV2, encoding="utf-8"))["new_eval"]["paper"]["baseline"]
    rs = [r for _, _, r in eps]
    dchk = sum(r.delta_checked_count for r in rs)
    ychk = sum(r.y_checked_count for r in rs)
    replay = {
        "n_episodes": len(rs),
        "n_success": sum(r.outcome == "성공" for r in rs),
        "n_collision": sum(r.outcome == "충돌" for r in rs),
        "safe_stop_count": sum(r.outcome == "SAFE_STOP" for r in rs),
        "delta_within_tolerance_rate": 1 - sum(r.delta_violation_count for r in rs) / dchk,
        "psi_within_tolerance_rate": 1 - sum(r.psi_violation_count for r in rs) / dchk,
        "y_within_tolerance_rate": 1 - sum(r.y_violation_count for r in rs) / ychk,
        "solver_fail_count": sum(r.solver_fail_count for r in rs),
        "fallback_count": sum(r.fallback_count for r in rs),
    }
    mism = {k: (stored[k], v) for k, v in replay.items() if stored[k] != v}
    if mism:
        print("MISMATCH — 통계를 저장하지 않고 중단:", mism)
        sys.exit(1)
    print("저장 집계와 완전 일치:", replay)

    # ---- 통계 ----
    per_state = {s: dict(y_abs=[], track=[], psi_abs=[], delta=[]) for s in STATES}
    all_v, all_delta, all_delta_raw, fg = [], [], [], []
    d_rate, v_rate = [], []
    n_steps = 0
    constraint = dict(delta_checked=0, delta_viol_s19=0, delta_viol_stored_const=0, v_checked=0, v_viol=0,
                      y_checked=0, y_viol=0, psi_checked=0, psi_viol=0)
    durations = []
    fg_success = []
    fg_at_evade = []
    for s, sc, r in eps:
        rows = r.logger.rows
        durations.append(len(rows) * config.DT)
        ev = [row["front_gap"] for row in rows if row["state"] == "EVADE_L"]
        if ev:
            fg_at_evade.append(ev[0])
        if r.outcome == "성공":
            fg_success.append(min(row["front_gap"] for row in rows))
        v_pre = [sc.v0] + [row["v"] for row in rows[:-1]]  # 각 스텝 운동에 쓰인 속도
        prev_d = None
        for row, v in zip(rows, v_pre):
            n_steps += 1
            st = row["state"]
            y, psi_deg = row["y"], math.degrees(row["psi"])
            per_state[st]["y_abs"].append(abs(y))
            per_state[st]["track"].append(abs(y - target_line_y(FSMState(st))))
            per_state[st]["psi_abs"].append(abs(psi_deg))
            per_state[st]["delta"].append(row["delta_final"])
            all_v.append(v)
            all_delta.append(row["delta_final"])
            if row["solver_status"] != "N/A":
                all_delta_raw.append(row["delta_mpc_raw"])
            fg.append(row["front_gap"])
            if prev_d is not None:
                d_rate.append(abs(row["delta_final"] - prev_d))
            prev_d = row["delta_final"]
            constraint["delta_checked"] += 1
            ex = abs(row["delta_mpc_raw"]) - config.DELTA_MAX_DEG
            constraint["delta_viol_s19"] += ex > TOL_DELTA_S19_BASELINE
            constraint["delta_viol_stored_const"] += not metrics.delta_within_tolerance(row["delta_mpc_raw"])
            constraint["v_checked"] += 1
            constraint["v_viol"] += not (0.0 <= v <= config.V_MAX + 1e-12)
            yok = metrics.y_within_tolerance(y, FSMState(st))
            if yok is not None:
                constraint["y_checked"] += 1
                constraint["y_viol"] += not yok
            constraint["psi_checked"] += 1
            constraint["psi_viol"] += not metrics.psi_within_tolerance(psi_deg)
        v_rate += list(np.abs(np.diff(v_pre)))
    dwell = {s: len(per_state[s]["y_abs"]) for s in STATES}
    out = dict(
        verification=dict(stored=stored, replay=replay, match=True),
        definitions=__doc__,
        n_episodes=len(eps), n_steps=n_steps,
        outcomes=dict(success=replay["n_success"], collision=replay["n_collision"], safe_stop=replay["safe_stop_count"]),
        table6={s: dict(dwell_steps=dwell[s], dwell_pct=100 * dwell[s] / n_steps,
                        y_abs=stats(per_state[s]["y_abs"]), track_err=stats(per_state[s]["track"]),
                        psi_abs_deg=stats(per_state[s]["psi_abs"]), delta_deg=stats(per_state[s]["delta"]))
                for s in STATES},
        speed=stats(all_v), steering_final=stats(all_delta), steering_mpc_raw=stats(all_delta_raw),
        front_gap_min_all=float(min(fg)), front_gap_min_success_episodes=float(min(fg_success)),
        front_gap_at_evade_entry=stats(fg_at_evade),
        front_gap_note=("front_gap은 차량 전단이 횡방향으로 겹치는 장애물 옆을 지나는 동안 0(REQ-SEN-01 정의: gap=max(0, x_near−x_front))이라 "
                        "성공 에피소드도 최솟값 0 — 충돌이 아님. 의미 있는 지표로 EVADE_L 진입 스텝의 front_gap을 따로 둠"), steering_rate=stats(d_rate), speed_rate=stats(v_rate),
        constraints=dict(**constraint,
                         delta_ok_pct_s19=100 * (1 - constraint["delta_viol_s19"] / constraint["delta_checked"]),
                         delta_ok_pct_stored_const=100 * (1 - constraint["delta_viol_stored_const"] / constraint["delta_checked"]),
                         v_ok_pct=100 * (1 - constraint["v_viol"] / constraint["v_checked"]),
                         y_ok_pct=100 * (1 - constraint["y_viol"] / constraint["y_checked"]),
                         psi_ok_pct=100 * (1 - constraint["psi_viol"] / constraint["psi_checked"])),
        episode_duration_s=stats(durations),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved", OUT)


if __name__ == "__main__":
    main()
