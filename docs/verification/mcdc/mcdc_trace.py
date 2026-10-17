"""FSM 전이 결정의 MC/DC 쌍을 테스트 실행에서 실측하는 pytest 플러그인 (docs/verification/MCDC_FSM.md).

Python 커버리지 도구(coverage.py)는 MC/DC를 측정하지 않는다. 이 플러그인은 `thesis_v2.baseline.fsm.step`을
감싸 매 호출의 입력에서 각 결정(D0~D4)의 조건 값을 계산해 기록하고, 세션 끝에 조건별 unique-cause 쌍을 찾는다.
제어 로직은 바꾸지 않는다 — 감싼 함수는 원래 `step`을 그대로 호출해 그 반환값을 돌려준다.

조건 재진술(아래 `_conditions`)은 SPEC REQ-FSM-02a~02e·03a를 config 상수로 다시 적은 것이다(fsm.py를 import해
쓰지 않음). 재진술이 코드와 어긋나면 "예측 다음 상태 ≠ 실제 다음 상태"로 드러나며, 그 경우 세션을 실패시킨다.

쌍 판정(unique-cause, 입력 값 기준):
  같은 결정 D의 두 호출에서 (1) 대상 조건 값이 다르고 (2) D의 나머지 조건 값이 **모두 같고**(단락 평가로 실제
  평가되지 않은 조건도 입력에서 계산한 값이 같아야 함) (3) D의 결정 결과가 다르고 (4) D가 두 호출 모두에서 실제로
  평가되었고 (5) 두 호출의 입력 FSM 상태가 같고 (6) 실제 다음 상태(관측 가능한 출력)도 다르면 그 조건의 독립
  영향이 확인된 것으로 센다. (5)는 D0처럼 모든 상태에 걸친 결정에서 출력 차이가 입력 상태 차이 때문이 아님을 보장한다.

사용(저장소 루트, PowerShell):
  $env:PYTHONPATH="docs/verification/mcdc"; $env:MCDC_OUT="<출력.json>"
  python -m pytest thesis_v2/tests/test_fsm.py -p mcdc_trace -q
"""
import json
import os
from itertools import combinations

from thesis_v2.baseline import config
from thesis_v2.baseline import fsm as _fsm_mod

S = _fsm_mod.FSMState

# 결정 정의: (ID, 소스 행, 적용 상태(None=모든 상태), 전이 대상, REQ, 조건 이름들)
DECISIONS = [
    ("D0", "fsm.py:51", None, S.SAFE_STOP, "REQ-FSM-02b, 03a",
     ["cooldown_ok", "front_gap < G_SAFE_MIN", "not left_clear"]),
    ("D1", "fsm.py:55", S.KEEP_L2, S.EVADE_L, "REQ-FSM-02a, 03a",
     ["cooldown_ok", "front_gap < G_TRIG", "left_clear"]),
    ("D2", "fsm.py:59", S.EVADE_L, S.KEEP_L1, "REQ-FSM-02c, 03a",
     ["cooldown_ok", "|y - W| <= NEAR_L1"]),
    ("D3", "fsm.py:64", S.KEEP_L1, S.RETURN_TO_L2, "REQ-FSM-02d, 03a",
     ["cooldown_ok", "t - state_enter_t > T_KEEP_L1_MIN", "right_clear"]),
    ("D4", "fsm.py:68", S.RETURN_TO_L2, S.KEEP_L2, "REQ-FSM-02e, 03a",
     ["cooldown_ok", "|y| <= NEAR_L2", "|psi_deg| <= PSI_L2_LIMIT_DEG"]),
]


def _conditions(f, sr, y, psi_deg, t):
    cd = (t - f.last_change_t) >= config.COOLDOWN
    return {
        "D0": [cd, sr.front_gap < config.G_SAFE_MIN, not sr.left_clear],
        "D1": [cd, sr.front_gap < config.G_TRIG, sr.left_clear],
        "D2": [cd, abs(y - config.W) <= config.NEAR_L1],
        "D3": [cd, (t - f.state_enter_t) > config.T_KEEP_L1_MIN, sr.right_clear],
        "D4": [cd, abs(y) <= config.NEAR_L2, abs(psi_deg) <= config.PSI_L2_LIMIT_DEG],
    }


RECORDS = []
MISMATCHES = []
_orig_step = _fsm_mod.step


def _traced_step(f, sensors, y, psi_deg, t):
    out = _orig_step(f, sensors, y, psi_deg, t)
    conds = _conditions(f, sensors, y, psi_deg, t)
    d0 = all(conds["D0"])
    evaluated = {"D0": True}
    predicted = S.SAFE_STOP if d0 else f.state
    for did, _, src, dst, _, _ in DECISIONS[1:]:
        evaluated[did] = (not d0) and f.state == src
        if evaluated[did] and all(conds[did]):
            predicted = dst
    nodeid = os.environ.get("PYTEST_CURRENT_TEST", "?").rsplit(" (", 1)[0]
    # step()은 전이 때 last_change_t와 state_enter_t를 같은 t로 둔다(fsm.py:74). 두 값이 다른 FSM 객체는 테스트가
    # 직접 만든 것이고(initial_fsm 제외) step()으로는 도달할 수 없다 — D3(두 시각을 모두 쓰는 유일한 결정)에서만 의미가 있다.
    rec = dict(test=nodeid, state=f.state.value, out=out.state.value, conds=conds, evaluated=evaluated,
               reachable_form=(f.last_change_t == f.state_enter_t))
    if predicted != out.state:
        MISMATCHES.append(dict(rec, predicted=predicted.value))
    RECORDS.append(rec)
    return out


_fsm_mod.step = _traced_step  # 테스트 모듈이 `from ...fsm import step` 하기 전에 바꿔 둔다(-p 플러그인은 수집 전 로드)


def analyze():
    result = []
    for did, line, src, dst, req, names in DECISIONS:
        recs = [r for r in RECORDS if r["evaluated"][did]]
        vectors = sorted({tuple(r["conds"][did]) for r in recs})
        per_cond = []
        for i, name in enumerate(names):
            pairs = []
            for a, b in combinations(recs, 2):
                ca, cb = a["conds"][did], b["conds"][did]
                if ca[i] == cb[i] or a["state"] != b["state"]:
                    continue
                if any(ca[j] != cb[j] for j in range(len(names)) if j != i):
                    continue
                if all(ca) == all(cb) or a["out"] == b["out"]:
                    continue
                t_rec, f_rec = (a, b) if all(ca) else (b, a)
                pairs.append(dict(true_case=dict(test=t_rec["test"], vector=t_rec["conds"][did], out=t_rec["out"]),
                                  false_case=dict(test=f_rec["test"], vector=f_rec["conds"][did], out=f_rec["out"]),
                                  both_reachable_form=t_rec["reachable_form"] and f_rec["reachable_form"]))
            # 같은 테스트 쌍 조합 중복 제거
            uniq = {}
            for p in pairs:
                uniq.setdefault((p["true_case"]["test"], p["false_case"]["test"]), p)
            per_cond.append(dict(condition=name, unique_cause_pair_found=bool(uniq),
                                 pair_found_reachable_form=any(p["both_reachable_form"] for p in uniq.values()),
                                 pairs=list(uniq.values())))
        result.append(dict(decision=did, line=line, from_state=src.value if src else "ANY", to_state=dst.value,
                           req=req, n_calls_evaluated=len(recs),
                           observed_vectors=[list(v) for v in vectors], conditions=per_cond))
    return result


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("MCDC_OUT")
    report = dict(n_step_calls=len(RECORDS), restatement_mismatches=MISMATCHES, decisions=analyze())
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    n_cond = sum(len(d["conditions"]) for d in report["decisions"])
    n_ok = sum(c["unique_cause_pair_found"] for d in report["decisions"] for c in d["conditions"])
    print(f"\n[mcdc_trace] step 호출 {len(RECORDS)}회, 재진술 불일치 {len(MISMATCHES)}건, "
          f"unique-cause 쌍 확인 조건 {n_ok}/{n_cond}")
    for d in report["decisions"]:
        for c in d["conditions"]:
            if not c["unique_cause_pair_found"]:
                print(f"[mcdc_trace]   미충족: {d['decision']} ({d['line']}) 조건 '{c['condition']}'")
            elif d["decision"] == "D3" and not c["pair_found_reachable_form"]:
                print(f"[mcdc_trace]   D3 조건 '{c['condition']}': 쌍은 도달 불가 형태(last_change_t≠state_enter_t) FSM으로만 확인")
    if MISMATCHES:
        session.exitstatus = 1
