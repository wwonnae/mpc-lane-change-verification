"""저장된 폐루프 평가 결과에서, steer 고장이 활성인 상태로 정지 step이 실행된 에피소드 수를 센다(읽기 전용, 재실행 없음).

배경(RESULTS.md 발견 사항): 정지 step은 apply_actuator를 거치지 않는다(thesis_v2/anomaly/closed_loop.py:199-200).
그래서 steer_stuck·steer_delay가 활성이어도 명령 δ_{k−1}로 차량을 갱신한다.

- 정지 step k = policy_action == "stop"인 에피소드의 first_alarm_step(= finish_step, closed_loop.py:197-211)
- 고장 활성 = run ∈ {steer_stuck, steer_delay} 이고 onset ≤ k, 그리고 duration이 비었거나 k < onset + duration
  (FaultSpec.active, thesis_v2/anomaly/faults.py:62-65)
- 참고 지표: 같은 (run, seed)의 P0가 같은 step k에 충돌·이탈로 끝났는지(정지 step 판정이 바뀔 수 있었는지의 추정 근거)

사용(저장소 루트): python docs/verification/mutation/count_stop_step_steer_faults.py --out docs/verification/mutation/raw/stop_step_steer_fault_count.json
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval"
STEER = ("steer_stuck", "steer_delay")

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args()


def load(name):
    with open(EVAL / f"episodes_{name}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


p0 = {(r["run"], r["seed"]): r for r in load("P0")}
out = dict(source=str(EVAL.relative_to(ROOT)).replace("\\", "/"), combos={})
for name in ("P1_A", "P1_B1", "P1_B2", "P1_HYBRID", "P2_A"):
    rows = load(name)
    stops = [r for r in rows if r["policy_action"] == "stop"]
    hit = []
    for r in stops:
        if r["run"] not in STEER:
            continue
        k, on = int(r["first_alarm_step"]), int(r["onset"])
        dur = int(r["duration"]) if r["duration"] else None
        if on <= k and (dur is None or k < on + dur):
            b = p0[(r["run"], r["seed"])]
            hit.append(dict(run=r["run"], seed=int(r["seed"]), stop_step=k, outcome=r["outcome"],
                            p0_outcome=b["outcome"], p0_finish_step=int(b["finish_step"]) if b["finish_step"] else None))
    out["combos"][name] = dict(
        n_episodes=len(rows), n_stop=len(stops),
        n_steer_runs=sum(r["run"] in STEER for r in rows),
        n_stop_with_steer_fault_active=len(hit),
        by_run=dict(Counter(h["run"] for h in hit)),
        stop_outcomes=dict(Counter(h["outcome"] for h in hit)),
        p0_ends_same_step_with_collision_or_departure=sum(
            h["p0_finish_step"] == h["stop_step"] and h["p0_outcome"] in ("충돌", "이탈") for h in hit),
        p0_outcomes=dict(Counter(h["p0_outcome"] for h in hit)),
        episodes=hit)
Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for k, v in out["combos"].items():
    print(k, {x: v[x] for x in v if x != "episodes"})
