"""
교차 환경(SSAFY PC/노트북) 재현성 확인. thesis_v2/tests/golden/의 기준 데이터와 현재 환경의
재실행 결과를 비교한다. SETTINGS_DECISION.md §18(OSQP 설정 고정)이 실제로 두 환경에서
같은 결과를 내는지 검증하는 목적.

일치 판정: 전이 목록·결과 분류·완료 step 완전 일치 + 조향각 시계열(delta_final, rad) 최대
차이 <= 1e-3 rad. 불일치 시 첫 차이 발생 step과 값을 보고한다.

사용: python -m thesis_v2.tests.check_golden
"""
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.world import generate_scenario, generate_left_obstacle_scenario

_DEG2RAD = math.pi / 180.0
TOLERANCE_RAD = 1e-3

SCENARIOS = {
    "paper": generate_scenario,
    "left_obstacle": generate_left_obstacle_scenario,
}
SEEDS = [0, 1, 2]

GOLDEN_DIR = Path(__file__).parent / "golden"


class GoldenMismatch(Exception):
    pass


def _load_golden(scenario_name: str, seed: int) -> Dict[str, Any]:
    path = GOLDEN_DIR / f"{scenario_name}_seed{seed}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _current_delta_series_rad(result) -> List[float]:
    return [row["delta_final"] * _DEG2RAD for row in result.logger.rows]


def compare_one(scenario_name: str, seed: int) -> Dict[str, Any]:
    """golden 대비 현재 환경 재실행 결과를 비교. {"ok": bool, "detail": str} 반환."""
    golden = _load_golden(scenario_name, seed)
    gen = SCENARIOS[scenario_name]
    result = run_episode(gen(seed))

    if result.outcome != golden["outcome"]:
        return {"ok": False, "detail": f"outcome 불일치: golden={golden['outcome']} "
                                        f"current={result.outcome}"}
    if result.finish_step != golden["finish_step"]:
        return {"ok": False, "detail": f"finish_step 불일치: golden={golden['finish_step']} "
                                        f"current={result.finish_step}"}
    current_trans = [f"{tr.from_state}->{tr.to_state}@{tr.step}" for tr in result.transitions]
    if current_trans != golden["transitions"]:
        return {"ok": False, "detail": f"transitions 불일치: golden={golden['transitions']} "
                                        f"current={current_trans}"}

    current_deltas = _current_delta_series_rad(result)
    golden_deltas = golden["delta_final_rad"]
    if len(current_deltas) != len(golden_deltas):
        return {"ok": False, "detail": f"조향각 시계열 길이 불일치: golden={len(golden_deltas)} "
                                        f"current={len(current_deltas)}"}
    first_diff_step: Optional[int] = None
    max_diff = 0.0
    for i, (g, c) in enumerate(zip(golden_deltas, current_deltas)):
        diff = abs(g - c)
        if diff > max_diff:
            max_diff = diff
        if diff > TOLERANCE_RAD and first_diff_step is None:
            first_diff_step = i + 1
    if first_diff_step is not None:
        return {"ok": False, "detail": (
            f"조향각 시계열 불일치: 최대 차이={max_diff:.6f} rad(허용 {TOLERANCE_RAD} rad), "
            f"첫 차이 step={first_diff_step}, golden={golden_deltas[first_diff_step - 1]:.6f} "
            f"current={current_deltas[first_diff_step - 1]:.6f}")}

    return {"ok": True, "detail": f"일치 (max|diff|={max_diff:.6f} rad)"}


def check_all() -> (bool, List[Dict[str, Any]]):
    all_ok = True
    reports = []
    for scenario_name in SCENARIOS:
        for seed in SEEDS:
            res = compare_one(scenario_name, seed)
            res["scenario"] = scenario_name
            res["seed"] = seed
            reports.append(res)
            if not res["ok"]:
                all_ok = False
    return all_ok, reports


def main():
    ok, reports = check_all()
    for r in reports:
        status = "PASS" if r["ok"] else "FAIL"
        print(f"[{status}] {r['scenario']} seed={r['seed']}: {r['detail']}")
    print()
    print("전체 결과:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
