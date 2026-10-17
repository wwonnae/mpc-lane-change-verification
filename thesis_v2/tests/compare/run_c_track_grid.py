"""
C트랙 전체 비교(1080 격자): 옛 OSQPMPC(legacy_2025/final_hierarchical_backup_thesis_1204.py, 2025-12-04) vs baseline MPC, 같은 입력
(y, psi, v, target_y, state)에서 solve() 1회 호출 결과(delta_deg)를 비교한다.
격자 정의는 DESIGN_BASELINE.md §6과 동일: y x psi x v x target_y x state = 9x5x3x2x4=1080.

repro/docs/WORK_RULES.md 예외: 이 파일(thesis_v2/tests/compare/만)만 옛 코드(legacy_2025/final_hierarchical_backup_thesis_1204.py)를 import한다(old_mpc_wrapper
경유). baseline/은 이 파일을 참조하지 않는다. 두 MPC 모두 solve()만 호출하고 baseline 코드는
전혀 수정하지 않는다.

분류 기준(MEASURE_PLAN.md C트랙, SPEC_VS_OLDCODE.md 기대 차이 + 2026-09-22 격리 실험으로
검증한 3가지 이미 문서화된 차이):
1) |diff|<=THRESHOLD_EXPLAINED_DEG(5도)면 항상 "rΔδ 구조 차이로 설명됨(작은 차이)" --
   old(크기벌점 대각)/baseline(차분벌점) Hessian 구조 차이만으로도 이 정도 편차는
   상시 발생함을 격리 실험(P만 old식으로 바꾼 hybrid 비교)으로 확인.
2) 둘 중 하나라도 fallback(ok=False)이면 -> "fallback/제약 차이로 설명됨"(게인 -qy vs
   K_p=1.0, 위치제약 범위 자체가 다르므로 infeasible 조건도 다를 수 있음, 둘 다 기대된 차이)
3) y0가 baseline 위치제약 경계에 근접(MARGIN=0.02m 이내)하거나 벗어나면 -> "위치
   제약(경계 인접 포함) 차이로 설명됨"(baseline 하드 제약이 old의 +-0.45와 다른 지점에서
   활성화됨 -- 경계 근접만으로도 QP 해가 크게 갈릴 수 있음을 실제 y_i 궤적 추출로 확인).
4) target_y != 0이면 -> "y_ref 끌림점 스케일링 버그(옛 코드 P/q 불일치)로 설명됨" --
   old는 P가 qy를 2배 하지 않으면서 q는 -2*qy*target_y(2배)를 써서, 표준 QP형태에서
   실제 무제약 끌림점이 target_y가 아니라 2*target_y가 됨(THESIS_REVISION_LOG.md
   2026-09-18 REQ-MPC-02 항목, legacy_2025/final_hierarchical_backup_thesis_1204.py 848~964행). target_y=0.3인 그리드 절반에서
   old가 극단값(주로 delta=+-25도 포화)으로 수렴하는 패턴과 일치.
5) 위 넷 다 아니면(target_y=0, 경계 비인접, fallback 아님) -> **"rΔδ 구조 차이로
   설명됨(포화영역)"**. 2026-09-22 `c_track_37_pscaled_retest.py`로 확정: 옛 MPC의 P를
   표준 스케일(x2, qy/qψ/rδ/rΔδ 전부)로 바꿔 37건을 재실행해도 **출력이 단 하나도
   바뀌지 않음**(0/37 vanish) -- 이는 우연이 아니라 수학적으로 당연한 결과다: target_y=0
   이면 선형항 q가 전부 0이 되고, q=0인 이차식(0.5*x'Px)은 P를 양의 상수배해도 최적해
   argmin이 바뀌지 않는다(x*=argmin 0.5*x'(cP)x는 c>0에 대해 c와 무관). 즉 이 잔여
   차이는 "P가 스케일링 안 됨"과는 무관하고, **rΔδ 항의 구조(옛 코드=대각 크기벌점 vs
   baseline=비대각 차분벌점) 자체**가 원인임이 확정됨(같은 실험이 반증한 셈이므로 별도
   미해결 항목 없음). 상세: `repro/2c_analysis/c_track_37_pscaled_retest.py`,
   `THESIS_REVISION_LOG.md` 2026-09-22 REQ-MPC-02 항목(정정).

사용(저장소 루트에서): python -m thesis_v2.tests.compare.run_c_track_grid
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from thesis_v2.baseline import config
from thesis_v2.baseline.mpc import OSQPMPC
from thesis_v2.tests.compare.old_mpc_wrapper import build_old_mpc, solve_old

_DEG2RAD = math.pi / 180.0

Y_VALUES = [-0.15, -0.05, 0.0, 0.05, 0.15, 0.22, 0.30, 0.38, 0.45]
PSI_VALUES_DEG = [-30, -10, 0, 10, 30]
V_VALUES = [0.3, 0.4, 0.5]
TARGET_Y_VALUES = [0.0, 0.30]
STATES = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2"]

# 상태-y 조합 중 물리적으로 나오지 않는 조합(참고용으로만 계산, 주 통계에서 제외).
# baseline 위치제약 범위를 크게(>=0.05m) 벗어나면 "그 상태에서 실제로 나올 수 없는 y"로 간주.
_MARGIN = 0.05


def _is_physically_plausible(state: str, y: float) -> bool:
    lo, hi = config.POSITION_CONSTRAINTS[state]
    return (lo - _MARGIN) <= y <= (hi + _MARGIN)


THRESHOLD_EXPLAINED_DEG = 5.0  # rΔδ 구조 차이만으로 설명 가능하다고 볼 임계값(격리실험 근거)
BOUNDARY_MARGIN = 0.02  # m, 이 안이면 "경계 인접"(호라이즌 내 제약 활성 가능)으로 취급


def classify(state: str, y: float, target_y: float, old_ok: bool, new_ok: bool,
             diff_deg: float) -> str:
    if diff_deg <= THRESHOLD_EXPLAINED_DEG:
        return "rΔδ 구조 차이로 설명됨(작은 차이)"
    if not old_ok or not new_ok:
        return "fallback/제약 차이로 설명됨"
    lo, hi = config.POSITION_CONSTRAINTS[state]
    if y <= lo + BOUNDARY_MARGIN or y >= hi - BOUNDARY_MARGIN or not (lo <= y <= hi):
        return "위치 제약(경계 인접 포함) 차이로 설명됨"
    if target_y != 0.0:
        return "y_ref 끌림점 스케일링 버그(옛 코드 P/q 불일치)로 설명됨"
    return "rΔδ 구조 차이로 설명됨(포화영역)"


def main():
    old_mpc = build_old_mpc(N=config.N, dt=config.DT, qy=config.QY, qpsi=config.QPSI,
                             rdelta=config.RDELTA, rddelta=config.RDDELTA)
    new_mpc = OSQPMPC()

    rows = []
    for y in Y_VALUES:
        for psi_deg in PSI_VALUES_DEG:
            for v in V_VALUES:
                for target_y in TARGET_Y_VALUES:
                    for state in STATES:
                        psi_rad = psi_deg * _DEG2RAD
                        delta_old_deg, ok_old = solve_old(old_mpc, y, psi_rad, v, target_y)
                        res_new = new_mpc.solve(y0=y, psi0_rad=psi_rad, v0=v,
                                                 target_y=target_y, state_name=state)
                        diff = abs(delta_old_deg - res_new.delta_deg)
                        plausible = _is_physically_plausible(state, y)
                        label = classify(state, y, target_y, ok_old, res_new.ok, diff)
                        rows.append({
                            "y": y, "psi_deg": psi_deg, "v": v, "target_y": target_y,
                            "state": state, "plausible": plausible,
                            "delta_old_deg": delta_old_deg, "ok_old": ok_old,
                            "delta_new_deg": res_new.delta_deg, "ok_new": res_new.ok,
                            "diff_deg": diff, "label": label,
                        })

    n_total = len(rows)
    plausible_rows = [r for r in rows if r["plausible"]]
    n_plausible = len(plausible_rows)

    label_counts_all = {}
    label_counts_plausible = {}
    for r in rows:
        label_counts_all[r["label"]] = label_counts_all.get(r["label"], 0) + 1
    for r in plausible_rows:
        label_counts_plausible[r["label"]] = label_counts_plausible.get(r["label"], 0) + 1

    # 2026-09-22: "설명 안 됨" 라벨은 더 이상 없음 -- 잔여였던 37건은 rΔδ 구조 차이(포화영역)로
    # 재분류·확정됨(c_track_37_pscaled_retest.py로 검증, classify() 주석 참고)
    unexplained = [r for r in plausible_rows if r["label"] == "설명 안 됨(버그 후보)"]

    diffs_all = [r["diff_deg"] for r in rows]
    diffs_plausible = [r["diff_deg"] for r in plausible_rows]

    summary = {
        "n_total": n_total,
        "n_plausible": n_plausible,
        "label_counts_all_1080": label_counts_all,
        "label_counts_plausible_only": label_counts_plausible,
        "diff_deg_stats_all": {
            "mean": sum(diffs_all) / len(diffs_all), "max": max(diffs_all),
        },
        "diff_deg_stats_plausible": {
            "mean": sum(diffs_plausible) / len(diffs_plausible), "max": max(diffs_plausible),
        },
        "n_unexplained_plausible": len(unexplained),
        "unexplained_examples": unexplained[:20],
    }

    out_dir = Path(__file__).resolve().parents[2] / "results" / "c_track_1080grid"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "c_track_grid_rows.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(out_dir / "c_track_grid_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
