"""5단계: mutation 1차 kill 중 비결정성 후보 테스트에서 처음 실패한 변이를 통제 조건에서 다시 실행한다.

- 대상 선정(사전 규칙, PLAN.md §7): docs/verification/mutation/raw/run_before.json에서 kill된 변이 중
  first_failure(처음 잡힌 층의 첫 실패 테스트)가 CANDIDATE_PATTERNS에 맞는 것 전부 + 사용자가 지목한 fsm:003/005/006.
- 변이 재현: mutation 1차 실행 커밋(run_before.json의 git.commit)을 git archive로 사본에 풀고, mutate.py의
  generate_from_text로 같은 id의 변이를 다시 만든다(원본 문자열·행이 기록과 같은지 확인). mutate.py는 import만 한다.
- 조건: orig(그대로)와 A(I5_TIME_LIMIT_SEC=1e10, apply_condition.py와 같은 치환). 각 조건에서 그 first_failure 테스트
  하나를 R회 pytest로 실행한다(-p no:cacheprovider, PYTHONDONTWRITEBYTECODE=1). 변이 없는 사본도 같은 방식으로 대조 실행.
- 판정: 변이가 orig·A 모두에서 R회 전부 실패하고 대조가 R회 전부 통과하면 "kill 유지(비결정성과 무관)".

사용: python mutant_recheck.py --out raw/S5_mutant_recheck/result.json [--repeats 5] [--work <사본 폴더>]
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MUT_DIR = REPO / "docs" / "verification" / "mutation"
CANDIDATE_PATTERNS = ("test_improved_i5::", "test_i4_student::test_i4_", "test_closed_loop::test_p0_matches_observational_runner",
                      "test_closed_loop::test_determinism")
USER_NAMED = ("fsm:003", "fsm:005", "fsm:006")
TL_LINE = "I5_TIME_LIMIT_SEC = 0.045"


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def nodeid_to_path(ff):
    mod, name = ff.split("::", 1)
    return mod.replace(".", "/") + ".py::" + name


def make_copy(dest, commit, cond):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    arc = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", commit, "thesis_v2",
                          ":(exclude)thesis_v2/results"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=arc, check=True)
    if cond == "A":
        cfg = dest / "thesis_v2/improved/config.py"
        t = cfg.read_text(encoding="utf-8")
        assert t.count(TL_LINE) == 1
        with open(cfg, "w", encoding="utf-8", newline="\n") as f:
            f.write(t.replace(TL_LINE, "I5_TIME_LIMIT_SEC = 1e10  # run6_cause 조건 A"))


def run_test(copy, nodepath):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONPATH", None)
    for d in copy.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    t = time.perf_counter()
    r = subprocess.run([sys.executable, "-m", "pytest", nodepath, "-x", "-q", "-p", "no:cacheprovider"], cwd=copy,
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    out = r.stdout
    kind = "pass" if r.returncode == 0 else ("assert" if "AssertionError" in out or "\nE       assert" in out
                                              else "exception")
    return dict(rc=r.returncode, kind=kind, secs=round(time.perf_counter() - t, 2), tail=out[-400:] if r.returncode else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--work", default=str(Path(os.environ.get("TEMP", "/tmp")) / "run6_cause" / "mutant_recheck"))
    ap.add_argument("--list", action="store_true", help="대상만 출력하고 실행하지 않음")
    args = ap.parse_args()
    sys.path.insert(0, str(MUT_DIR))
    import mutate  # 읽기 전용 사용(generate_from_text, mutated_text, TARGETS)

    rb = json.loads((MUT_DIR / "raw" / "run_before.json").read_text(encoding="utf-8"))
    commit = rb["git"]["commit"]
    chosen = []
    for m in rb["mutants"]:
        lay = m.get("first_layer")
        if not lay:
            continue
        ff = (m["layers"].get(lay) or {}).get("first_failure") or ""
        why = []
        if any(p in ff for p in CANDIDATE_PATTERNS):
            why.append("비결정성 후보 테스트에서 처음 실패")
        if m["id"] in USER_NAMED:
            why.append("사용자 지목")
        if why:
            chosen.append(dict(id=m["id"], module=m["module"], line=m["line"], original=m["original"],
                               replacement=m["replacement"], first_layer=lay, first_failure=ff,
                               recorded_status=m["layers"][lay]["status"], why=why))
    print(f"[mutant_recheck] 대상 {len(chosen)}개 (commit {commit[:7]})")
    for c in chosen:
        print(f"  {c['id']} L{c['line']} {c['original'][:30]!r}->{c['replacement'][:20]!r} | {c['first_layer']} "
              f"{c['first_failure'].split('::')[-1][:60]} | {c['recorded_status']} | {', '.join(c['why'])}")
    if args.list:
        return
    work = Path(args.work).resolve()
    try:
        work.relative_to(REPO)
        sys.exit("작업 폴더는 저장소 밖이어야 한다")
    except ValueError:
        pass
    res = dict(started=now_iso(), commit=commit, repeats=args.repeats, targets=chosen, runs=[])
    clean = {cond: work / f"clean_{cond}" for cond in ("orig", "A")}
    for cond, d in clean.items():
        make_copy(d, commit, cond)
    # 대조: 변이 없는 사본에서 대상 테스트들(중복 제거)
    for nodepath in sorted({nodeid_to_path(c["first_failure"]) for c in chosen}):
        for cond, d in clean.items():
            for i in range(args.repeats):
                r = run_test(d, nodepath)
                res["runs"].append(dict(mutant=None, cond=cond, test=nodepath, rep=i, **r))
                print(f"[clean {cond}] {nodepath.split('::')[-1][:50]} #{i}: {r['kind']}", flush=True)
    for c in chosen:
        cfg = mutate.TARGETS[c["module"]]
        for cond in ("orig", "A"):
            d = work / f"mut_{cond}"
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(clean[cond], d)
            src = (d / cfg["path"]).read_text(encoding="utf-8")
            ms = {m.id: m for m in mutate.generate_from_text(c["module"], cfg["path"], src, cfg["ranges"])}
            m = ms[c["id"]]
            assert m.line == c["line"] and m.original == c["original"] and m.replacement == c["replacement"], c["id"]
            with open(d / cfg["path"], "w", encoding="utf-8", newline="") as f:
                f.write(mutate.mutated_text(src, m))
            nodepath = nodeid_to_path(c["first_failure"])
            for i in range(args.repeats):
                r = run_test(d, nodepath)
                res["runs"].append(dict(mutant=c["id"], cond=cond, test=nodepath, rep=i, **r))
                print(f"[{c['id']} {cond}] #{i}: {r['kind']}", flush=True)
    # 판정
    verdict = {}
    for c in chosen:
        rs = [r for r in res["runs"] if r["mutant"] == c["id"]]
        ctrl = [r for r in res["runs"] if r["mutant"] is None and r["test"] == nodeid_to_path(c["first_failure"])]
        mut_fail_all = all(r["rc"] != 0 for r in rs)
        ctrl_pass_all = all(r["rc"] == 0 for r in ctrl)
        verdict[c["id"]] = dict(
            mutant_fail={cond: sum(1 for r in rs if r["cond"] == cond and r["rc"] != 0) for cond in ("orig", "A")},
            control_pass={cond: sum(1 for r in ctrl if r["cond"] == cond and r["rc"] == 0) for cond in ("orig", "A")},
            kinds=sorted({r["kind"] for r in rs}),
            verdict="kill 유지(비결정성과 무관)" if mut_fail_all and ctrl_pass_all else "재검토 필요")
    res["verdict"] = verdict
    res["finished"] = now_iso()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in verdict.items():
        print(k, v)


if __name__ == "__main__":
    main()
