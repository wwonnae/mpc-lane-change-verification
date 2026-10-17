"""1차 생존 변이만 다른 PC에서 다시 실행해 1차 결과와 같은지 확인한다(2차 실행 전 재현성 점검).

**이 파일은 mutate.py를 고치지 않는다. mutate.py를 모듈로 불러와 그 함수만 호출한다.**
(실행 뒤 이 docstring만 고쳤다. 실행한 판의 sha256은 raw/run_before_recheck_laptop.json의 driver_sha256 — RESULTS.md 참조.)

- mutate.py의 함수(generate, validate, mutated_text, make_copy, run_pytest, run_golden, pc_load, git_state)를
  수정 없이 그대로 쓴다. 층(L1→L2→L3), -x, 바이트코드 캐시 차단, 타임아웃 규칙(max(10 s, 깨끗한 사본 × 5))은 같다.
- 대상: raw/run_before.json에서 status == "survived"인 변이 ID. 재생성한 변이의 줄·연산자·원본·치환이 1차 기록과
  같은지 먼저 확인하고, 다르면 실행하지 않고 중단한다.
- 커버리지 수집은 하지 않는다(재현성 점검 범위 밖).

사용(저장소 루트): python docs/verification/mutation/recheck_survivors.py --before <run_before.json> --out <out.json>
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=".")
ap.add_argument("--before", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

repo = Path(a.repo).resolve()
mp = repo / "docs/verification/mutation/mutate.py"
spec = importlib.util.spec_from_file_location("mutate", mp)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
assert M.ROOT == repo, (M.ROOT, repo)

before = json.loads(Path(a.before).read_text(encoding="utf-8"))
surv = [r for r in before["mutants"] if r["status"] == "survived"]
by_id = {r["id"]: r for r in surv}
modules = [m for m in M.TARGETS if any(r["module"] == m for r in surv)]

raw = dict(purpose="1차 생존 변이 재실행(2차 실행 전, 새 테스트 넣기 전 테스트로)", tool_version=M.TOOL_VERSION,
           driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           mutate_py_sha256=hashlib.sha256(mp.read_bytes()).hexdigest(),
           before_file=Path(a.before).name, before_git=before["git"], before_started=before["started"],
           started=time.strftime("%Y-%m-%dT%H:%M:%S"), git=M.git_state(), python=sys.version.split()[0],
           packages={}, pc_load_before=M.pc_load(), n_targets=len(surv), mutants=[])
for pkg in ("numpy", "scipy", "osqp", "pytest"):
    try:
        from importlib.metadata import version
        raw["packages"][pkg] = version(pkg)
    except Exception as ex:
        raw["packages"][pkg] = repr(ex)

# 변이 동일성 확인(실행 전)
gen = {}
for m in modules:
    text = (repo / M.TARGETS[m]["path"]).read_text(encoding="utf-8")
    for mu in M.generate(m, text):
        gen[mu.id] = (mu, text)
for i, r in by_id.items():
    mu, _ = gen[i]
    got = dict(line=mu.line, operator=mu.operator, original=mu.original, replacement=mu.replacement)
    exp = {k: r[k] for k in got}
    if got != exp:
        raise SystemExit(f"변이 불일치 {i}: 재생성 {got} / 1차 {exp}")

tmp = Path(tempfile.mkdtemp(prefix="mut_recheck_"))
try:
    M.make_copy(tmp)
    M._clear_pycache(tmp)
    base = {m: M.run_pytest(tmp, M.TARGETS[m]["l1"], timeout=600) for m in modules}
    l2 = M.run_pytest(tmp, M.L2_CMD, timeout=1200)
    l3 = M.run_golden(tmp, timeout=600)
    for m in modules:
        if base[m]["status"] != "pass" or l2["status"] != "pass" or l3["status"] != "pass":
            raise SystemExit(f"깨끗한 사본이 통과하지 않음: {m} {base[m]} L2={l2} L3={l3}")
    timeouts = {m: dict(l1=max(10.0, 5 * base[m]["seconds"]), l2=max(10.0, 5 * l2["seconds"]),
                        l3=max(10.0, 5 * l3["seconds"])) for m in modules}
    raw["clean_run"] = dict(per_module_l1=base, l2=l2, l3=l3)
    raw["timeouts"] = timeouts

    for m in modules:
        cfg = M.TARGETS[m]
        target = tmp / cfg["path"]
        original = (repo / cfg["path"]).read_text(encoding="utf-8")
        assert target.read_text(encoding="utf-8") == original
        for i in [r["id"] for r in surv if r["module"] == m]:
            mu, _ = gen[i]
            rec = dict(id=mu.id, module=m, path=mu.path, line=mu.line, operator=mu.operator,
                       original=mu.original, replacement=mu.replacement, description=mu.description)
            bad = M.validate(original, mu)
            if bad:
                rec.update(status="invalid", invalid_reason=bad); raw["mutants"].append(rec); continue
            target.write_text(M.mutated_text(original, mu), encoding="utf-8")
            M._clear_pycache(tmp)
            layers, status, first = {}, "survived", None
            r1 = M.run_pytest(tmp, cfg["l1"], timeouts[m]["l1"]); layers["L1"] = r1
            if r1["status"] != "pass":
                status, first = r1["status"], "L1"
            else:
                r2 = M.run_pytest(tmp, M.L2_CMD, timeouts[m]["l2"]); layers["L2"] = r2
                if r2["status"] != "pass":
                    status, first = r2["status"], "L2"
                elif cfg["l3"]:
                    r3 = M.run_golden(tmp, timeouts[m]["l3"]); layers["L3"] = r3
                    if r3["status"] != "pass":
                        status, first = r3["status"], "L3"
                else:
                    layers["L3"] = dict(status="not_applicable")
            b = by_id[i]
            bd = b["layers"].get("L3", {}).get("max_diff_rad")
            nd = layers.get("L3", {}).get("max_diff_rad")
            rec.update(status=status, first_layer=first, layers=layers,
                       before_status=b["status"], same_status=(status == b["status"]),
                       before_l3_max_diff_rad=bd, same_l3_max_diff=(bd == nd))
            raw["mutants"].append(rec)
            target.write_text(original, encoding="utf-8")
            print(f"[{mu.id}] {mu.operator:12s} L{mu.line:<4d} {status:16s} {first or ''}"
                  f"{'' if rec['same_status'] else '  *** 1차와 다름'}", flush=True)
        assert target.read_text(encoding="utf-8") == original
    raw["pc_load_after"] = M.pc_load()
    raw["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    raw["git_after"] = M.git_state()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

ms = raw["mutants"]
raw["summary"] = dict(n=len(ms), same_status=sum(r.get("same_status", False) for r in ms),
                      different=[r["id"] for r in ms if not r.get("same_status", False)],
                      l3_max_diff_different=[r["id"] for r in ms if "L3" in r.get("layers", {})
                                             and r["layers"]["L3"].get("status") != "not_applicable"
                                             and not r["same_l3_max_diff"]])
out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(raw, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print("SUMMARY", json.dumps(raw["summary"], ensure_ascii=False))
