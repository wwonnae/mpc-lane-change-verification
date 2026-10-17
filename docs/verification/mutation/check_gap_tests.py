"""LLM 보조 테스트 수락 기준 ①~③ 자동 확인(PREREGISTRATION.md §8-3).

① 원본에서 통과  ② 대상 변이를 잡음(저장소 밖 임시 사본에서 실행)  ③ 각 테스트 함수 docstring에 REQ ID 또는 DESIGN 절(§)
④(관찰 가능한 동작 확인)는 사용자가 검토한다 — 이 스크립트는 판단하지 않는다.

- mutate.py를 고치지 않고 그 함수(generate, mutated_text, make_copy, _clear_pycache, run_pytest)만 호출한다.
- 대상 변이는 equivalence.json에서 고른다(--module의 test_gap 전부, 또는 --ids).

사용(저장소 루트):
  python docs/verification/mutation/check_gap_tests.py --tests thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py \
      --module closed_loop --out docs/verification/mutation/raw/gap_tests_closed_loop_check.json
"""
import argparse
import ast
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mutate as M  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--tests", required=True)
ap.add_argument("--module", required=True)
ap.add_argument("--ids", nargs="*")
ap.add_argument("--out", required=True)
ap.add_argument("--deselect-k", help="pytest -k 식으로 일부 테스트를 빼고 ②만 다시 확인(층별 독립성 확인용)")
a = ap.parse_args()

eq = json.loads((HERE / "equivalence.json").read_text(encoding="utf-8"))
ids = a.ids or [x["id"] for x in eq["mutants"] if x["module"] == a.module and x["classification"] == "test_gap"]
test_src = (M.ROOT / a.tests).read_text(encoding="utf-8")

# ③ docstring
doc_check = {}
for node in ast.walk(ast.parse(test_src)):
    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
        ds = ast.get_docstring(node) or ""
        doc_check[node.name] = bool(re.search(r"REQ-[A-Z]+-\d+|§\s?\d+", ds))

cfg = M.TARGETS[a.module]
original = (M.ROOT / cfg["path"]).read_text(encoding="utf-8")
muts = {m.id: m for m in M.generate(a.module, original)}
res = dict(tests=a.tests, deselect_k=a.deselect_k, tests_sha256=hashlib.sha256(test_src.encode("utf-8")).hexdigest(), module=a.module,
           started=time.strftime("%Y-%m-%dT%H:%M:%S"), git=M.git_state(), python=sys.version.split()[0],
           criterion3_docstring=doc_check, mutants=[])
tmp = Path(tempfile.mkdtemp(prefix="mut_gapcheck_"))
try:
    M.make_copy(tmp)
    M._clear_pycache(tmp)
    res["criterion1_original"] = M.run_pytest(tmp, [a.tests], timeout=600)   # ①
    target = tmp / cfg["path"]
    for i in ids:
        mu = muts[i]
        target.write_text(M.mutated_text(original, mu), encoding="utf-8")
        M._clear_pycache(tmp)
        r = M.run_pytest(tmp, [a.tests] + (["-k", f"not ({a.deselect_k})"] if a.deselect_k else []), timeout=600)  # ②
        r.pop("tail", None)
        res["mutants"].append(dict(id=i, line=mu.edits[0].start[0], operator=mu.operator, killed=r["status"] != "pass", **r))
        print(i, r["status"], r.get("first_failure"), flush=True)
        target.write_text(original, encoding="utf-8")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
res["summary"] = dict(criterion1_pass=res["criterion1_original"]["status"] == "pass",
                      criterion3_all=all(doc_check.values()),
                      n_targets=len(ids), n_killed=sum(m["killed"] for m in res["mutants"]),
                      survived=[m["id"] for m in res["mutants"] if not m["killed"]])
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("SUMMARY", json.dumps(res["summary"], ensure_ascii=False))
