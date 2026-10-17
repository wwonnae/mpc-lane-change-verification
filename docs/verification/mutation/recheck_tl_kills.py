"""사전 선언 변경 5번(RESULTS.md) — time_limit이 켜진 I5 on MPC를 쓰는 테스트에서 처음 잡힌 kill을 재확인한다.

- 입력: mutate.py run 결과(JSON, 예: raw/run_after.json).
- 사본: 실행한 커밋의 thesis_v2를 저장소 밖 작업 폴더에 복사한다.
  - 정식 실행은 결과 JSON의 git.commit이 지금 HEAD와 같고 작업 트리가 깨끗해야 한다.
  - dry-run은 --allow-dirty로 작업 트리를 그대로 쓴다.
- 대상 판정(실행 시점): kill(killed/killed_exception)의 first_failure 테스트를 변이 없는 사본에서 한 번 실행한다.
  - 그 테스트 호출 중에 `improved_config.I5_TIME_LIMIT_SEC < 1`인 상태로 `ImprovedMPC(enable_i5=True)`가 만들어지면 대상이다.
  - 판정은 이 스크립트가 만드는 임시 pytest 플러그인으로 한다. i5_time_limit_off fixture가 붙은 테스트는 1e10이라 제외된다.
  - timeout kill은 first_failure가 없어 대상에서 빼고, 그 사실을 결과에 남긴다.
- 조건: orig(그대로)와 A(사본의 improved/config.py에서 I5_TIME_LIMIT_SEC = 1e10). 각 조건에서 그 테스트를 R회 실행한다.
  - 변이 없는 사본에서도 같은 방식으로 대조 실행한다.
- 판정: 변이가 orig·A 모두 R/R 실패이고 대조가 R/R 통과하면 "kill 유지". 아니면 "재검토".
- 제품 코드·테스트는 바꾸지 않는다(사본만 바꾼다). mutate.py는 import만 한다.

사용(저장소 루트):
  python docs/verification/mutation/recheck_tl_kills.py --run docs/verification/mutation/raw/run_after.json \\
      --out docs/verification/mutation/raw/run_after_tl_recheck.json [--repeats 5] [--max-targets N] [--allow-dirty]
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TL_LINE = "I5_TIME_LIMIT_SEC = 0.045"
PLUGIN = r'''
import json, os
_used = {"tl_on_i5": False, "n_i5": 0}

def pytest_runtest_call(item):
    from thesis_v2.improved import mpc as _m, config as _c
    orig = _m.ImprovedMPC.__init__
    def _init(self, *a, **k):
        orig(self, *a, **k)
        if getattr(self, "enable_i5", False):
            _used["n_i5"] += 1
            if _c.I5_TIME_LIMIT_SEC < 1:
                _used["tl_on_i5"] = True
    _m.ImprovedMPC.__init__ = _init
    item._tlprobe_orig = orig

def pytest_runtest_teardown(item):
    from thesis_v2.improved import mpc as _m
    if hasattr(item, "_tlprobe_orig"):
        _m.ImprovedMPC.__init__ = item._tlprobe_orig

def pytest_sessionfinish(session):
    with open(os.environ["TLPROBE_OUT"], "w", encoding="utf-8") as f:
        json.dump(_used, f)
'''


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()


def nodeid_to_path(ff):
    mod, name = ff.split("::", 1)
    return mod.replace(".", "/") + ".py::" + name


def make_copy(dest, cond):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(REPO / "thesis_v2", dest / "thesis_v2", ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc"))
    if cond == "A":
        cfg = dest / "thesis_v2/improved/config.py"
        t = cfg.read_bytes().decode("utf-8")
        assert t.count(TL_LINE) == 1, "config.py의 I5_TIME_LIMIT_SEC 행을 찾지 못함"
        cfg.write_bytes(t.replace(TL_LINE, "I5_TIME_LIMIT_SEC = 1e10  # recheck_tl_kills 조건 A").encode("utf-8"))


def _env(extra=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    env.update(extra or {})
    return env


def run_test(copy, nodepath, plugin_dir=None, probe_out=None):
    for d in copy.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    cmd = [sys.executable, "-m", "pytest", nodepath, "-x", "-q", "-p", "no:cacheprovider"]
    extra = {}
    if plugin_dir:
        cmd += ["-p", "tlprobe_plugin"]
        extra = {"PYTHONPATH": str(plugin_dir), "TLPROBE_OUT": str(probe_out)}
    t = time.perf_counter()
    r = subprocess.run(cmd, cwd=copy, env=_env(extra), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    out = r.stdout
    kind = "pass" if r.returncode == 0 else ("assert" if ("AssertionError" in out or "\nE       assert" in out)
                                             else "exception")
    return dict(rc=r.returncode, kind=kind, secs=round(time.perf_counter() - t, 2), tail=out[-400:] if r.returncode else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--max-targets", type=int, default=None, help="dry-run용: 대상 중 앞 N개만 재확인")
    ap.add_argument("--allow-dirty", action="store_true", help="dry-run용: 커밋·작업 트리 일치 확인 생략")
    ap.add_argument("--work", default=str(Path(tempfile.gettempdir()) / "recheck_tl_kills"))
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    import mutate  # 읽기 전용(generate_from_text, mutated_text, TARGETS)

    run = json.loads(Path(a.run).read_text(encoding="utf-8"))
    # 사본은 thesis_v2(results 제외)만 쓰므로 그 범위의 변경만 본다. 야간 실행에서는 앞 단계(closed_loop --check)가
    # 저장 결과 폴더의 _check_* 파일을 쓰기 때문에 저장소 전체 dirty와 run.git.dirty는 참일 수 있다(기록만 한다).
    head = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "--", "thesis_v2", ":(exclude)thesis_v2/results"))
    if not a.allow_dirty and (run["git"]["commit"] != head or dirty):
        sys.exit(f"커밋·코드 불일치: run={run['git']} HEAD={head} code_dirty={dirty} (dry-run이면 --allow-dirty)")
    work = Path(a.work).resolve()
    try:
        work.relative_to(REPO)
        sys.exit("작업 폴더는 저장소 밖이어야 한다")
    except ValueError:
        pass
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    plugin_dir = work / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "tlprobe_plugin.py").write_text(PLUGIN, encoding="utf-8")
    res = dict(started=now(), run=str(a.run), run_git=run["git"], head=head, dirty=dirty, repeats=a.repeats,
               rule="RESULTS.md 사전 선언 변경 5", candidates=[], skipped_timeouts=[], runs=[], verdict={})
    clean = {c: work / f"clean_{c}" for c in ("orig", "A")}
    for c, d in clean.items():
        make_copy(d, c)

    kills = []
    for m in run["mutants"]:
        lay = m.get("first_layer")
        if not lay or m.get("status") not in ("killed", "killed_exception", "timeout"):
            continue
        ff = (m["layers"].get(lay) or {}).get("first_failure")
        if m["status"] == "timeout" or not ff or "::" not in ff:
            res["skipped_timeouts"].append(dict(id=m["id"], status=m["status"], first_layer=lay, first_failure=ff))
            continue
        kills.append((m, ff))
    # 대상 판정: first_failure 테스트별로 변이 없는 orig 사본에서 1회 실행
    usage = {}
    for ff in sorted({ff for _, ff in kills}):
        po = work / "probe.json"
        if po.exists():
            po.unlink()
        r = run_test(clean["orig"], nodeid_to_path(ff), plugin_dir, po)
        u = json.loads(po.read_text(encoding="utf-8")) if po.exists() else {"tl_on_i5": None, "n_i5": None}
        usage[ff] = dict(u, clean_rc=r["rc"])
        print(f"[usage] tl_on_i5={u['tl_on_i5']} n_i5={u['n_i5']} rc={r['rc']} {ff}", flush=True)
    res["test_usage"] = usage
    targets = [(m, ff) for m, ff in kills if usage.get(ff, {}).get("tl_on_i5")]
    res["n_kills"] = len(kills)
    res["n_targets_all"] = len(targets)
    if a.max_targets is not None:
        targets = targets[:a.max_targets]
    for m, ff in targets:
        res["candidates"].append(dict(id=m["id"], module=m["module"], line=m["line"], status=m["status"],
                                      first_layer=m["first_layer"], first_failure=ff))
    print(f"[recheck_tl_kills] kill {len(kills)}개 중 대상 {res['n_targets_all']}개(재확인 {len(targets)}개)", flush=True)

    for nodepath in sorted({nodeid_to_path(ff) for _, ff in targets}):
        for c, d in clean.items():
            for i in range(a.repeats):
                r = run_test(d, nodepath)
                res["runs"].append(dict(mutant=None, cond=c, test=nodepath, rep=i, **r))
                print(f"[clean {c}] #{i} {r['kind']} {nodepath.split('::')[-1][:60]}", flush=True)
    for m, ff in targets:
        cfg = mutate.TARGETS[m["module"]]
        for c in ("orig", "A"):
            d = work / f"mut_{c}"
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(clean[c], d)
            src = (d / cfg["path"]).read_text(encoding="utf-8")
            ms = {x.id: x for x in mutate.generate_from_text(m["module"], cfg["path"], src, cfg["ranges"])}
            mu = ms[m["id"]]
            assert mu.line == m["line"] and mu.original == m["original"] and mu.replacement == m["replacement"], m["id"]
            with open(d / cfg["path"], "w", encoding="utf-8", newline="") as f:
                f.write(mutate.mutated_text(src, mu))
            for i in range(a.repeats):
                r = run_test(d, nodeid_to_path(ff))
                res["runs"].append(dict(mutant=m["id"], cond=c, test=nodeid_to_path(ff), rep=i, **r))
                print(f"[{m['id']} {c}] #{i} {r['kind']}", flush=True)
    for m, ff in targets:
        rs = [r for r in res["runs"] if r["mutant"] == m["id"]]
        ctrl = [r for r in res["runs"] if r["mutant"] is None and r["test"] == nodeid_to_path(ff)]
        ok = all(r["rc"] != 0 for r in rs) and all(r["rc"] == 0 for r in ctrl) and len(rs) == 2 * a.repeats
        res["verdict"][m["id"]] = dict(
            mutant_fail={c: sum(1 for r in rs if r["cond"] == c and r["rc"] != 0) for c in ("orig", "A")},
            control_pass={c: sum(1 for r in ctrl if r["cond"] == c and r["rc"] == 0) for c in ("orig", "A")},
            kinds=sorted({r["kind"] for r in rs}), verdict="kill 유지" if ok else "재검토")
    res["finished"] = now()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    n_keep = sum(1 for v in res["verdict"].values() if v["verdict"] == "kill 유지")
    print(f"[recheck_tl_kills] 재확인 {len(res['verdict'])}개: kill 유지 {n_keep}, 재검토 {len(res['verdict']) - n_keep}")
    sys.exit(0 if n_keep == len(res["verdict"]) else 3)


if __name__ == "__main__":
    main()
