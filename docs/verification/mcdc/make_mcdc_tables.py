"""mcdc_trace.py 출력 JSON(추가 전·후) -> MC/DC 결정·조건·쌍 표(markdown). 값은 전부 JSON에서 읽는다.

사용(저장소 루트):
  python docs/verification/mcdc/make_mcdc_tables.py docs/verification/mcdc/mcdc_before_existing_tests.json \
      docs/verification/mcdc/mcdc_after_added_tests.json docs/verification/mcdc/MCDC_TABLES.md
"""
import json
import sys
from pathlib import Path


def _tf(v):
    return "".join("T" if x else "F" for x in v)


def _short(nodeid):
    return nodeid.split("::", 1)[1] if "::" in nodeid else nodeid


def _pick(pairs):
    """대표 쌍: 도달 가능 형태 우선, 그다음 추가 테스트(test_fsm_mcdc)보다 기존 테스트 우선."""
    return sorted(pairs, key=lambda p: (not p["both_reachable_form"],
                                        "test_fsm_mcdc" in p["true_case"]["test"] + p["false_case"]["test"]))[0]


def main(before_json, after_json, out_md):
    before = json.loads(Path(before_json).read_text(encoding="utf-8"))
    after = json.loads(Path(after_json).read_text(encoding="utf-8"))
    bmap = {(d["decision"], c["condition"]): c for d in before["decisions"] for c in d["conditions"]}

    out = ["<!-- 자동 생성: make_mcdc_tables.py -->\n"]
    for label, rep in (("기존 테스트만(test_fsm.py)", before), ("추가 후(test_fsm.py + test_fsm_mcdc.py)", after)):
        n = sum(len(d["conditions"]) for d in rep["decisions"])
        ok = sum(c["unique_cause_pair_found"] for d in rep["decisions"] for c in d["conditions"])
        out.append(f"- {label}: step 호출 {rep['n_step_calls']}회, 재진술 불일치 {len(rep['restatement_mismatches'])}건, "
                   f"unique-cause 쌍 확인 조건 **{ok}/{n}**")
    out.append("\n## 결정·조건별 확인 결과\n")
    out.append("벡터는 조건 순서대로 T/F. 참 사례 → 전이, 거짓 사례 → 유지. '도달 가능 형태' = 두 사례 모두 "
               "`last_change_t == state_enter_t`(D3에서만 의미 있음).\n")
    out.append("| 결정 | 조건 | 기존 테스트 | 추가 후 | 대표 쌍: 참 사례(벡터→출력) | 대표 쌍: 거짓 사례(벡터→출력) | 도달 가능 형태 쌍 |")
    out.append("|---|---|---|---|---|---|---|")
    for d in after["decisions"]:
        for c in d["conditions"]:
            b = bmap[(d["decision"], c["condition"])]
            pre = "충족" if b["unique_cause_pair_found"] else "**미충족**"
            post = "충족" if c["unique_cause_pair_found"] else "**미충족**"
            if c["pairs"]:
                p = _pick(c["pairs"])
                tc = f"`{_short(p['true_case']['test'])}` ({_tf(p['true_case']['vector'])}→{p['true_case']['out']})"
                fc = f"`{_short(p['false_case']['test'])}` ({_tf(p['false_case']['vector'])}→{p['false_case']['out']})"
            else:
                tc = fc = "—"
            if d["decision"] != "D3":
                reach = "해당 없음(state_enter_t 미사용)"
            else:
                reach = "있음" if c["pair_found_reachable_form"] else "**없음**"
            out.append(f"| {d['decision']} `{d['line']}` {d['from_state']}→{d['to_state']} | `{c['condition']}` | "
                       f"{pre} | {post} | {tc} | {fc} | {reach} |")
    out.append("\n## 결정별 관측 벡터(추가 후, 실제로 평가된 호출만)\n")
    for d in after["decisions"]:
        vecs = ", ".join(_tf(v) for v in d["observed_vectors"])
        out.append(f"- {d['decision']} ({d['req']}): 평가 {d['n_calls_evaluated']}회, 벡터 {{{vecs}}}")
    Path(out_md).write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:4])
