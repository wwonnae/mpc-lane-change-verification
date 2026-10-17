"""커밋 2(run #6 대응) 소규모 동적 비교 — 선택지 5가 제어 출력을 바꾸지 않는지 확인한다.

같은 PC·같은 조건에서 두 코드 사본을 차례로 실행해, 바뀐 기록 필드(time_limit_hit, time_limit_count,
time_limit_rejected_count, notable_step_log, mpc_time_limit_hits)와 계산 시간 필드를 뺀 모든 출력을 비교한다.
- old: 커밋 1(30a3a22)의 thesis_v2 (git archive, 저장소 밖 임시 폴더)
- new: 작업 트리(커밋 2 후보)의 thesis_v2 복사본(저장소 밖 임시 폴더)

대상(제품 설정 그대로, time_limit 0.045 — fixture를 쓰지 않는다):
 1. eval 2회차 방식 v2 paper seed 200~209: MPC 인스턴스 하나를 seed 순서대로 공유(run_eval_v2.run_paper와 같음)
 2. I5 on(COMBO_V2) paper seed 0~2: 에피소드마다 새 인스턴스
 3. anomaly 폐루프 P0(V2_MPC_FLAGS, 탐지기 A h=9.2109…): seed 3200, 3201, 3207
비교가 다르면, 그 실행의 기록 필드에 절단(time_limit_hit)이 있었는지 함께 본다(절단이 있으면 결과 차이는 정상 —
time_limit 비결정성 자체이며 코드 변경 탓이 아님).

사용(저장소 루트): python docs/verification/ci/run6_cause/commit2_compare.py --out docs/verification/ci/run6_cause/raw/C2_compare
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OLD_COMMIT = "30a3a22"
EXCLUDE_ROW = lambda k: k.startswith("t_") and k.endswith("_ms")  # noqa: E731  계산 시간 열
CHANGED_EP_FIELDS = {"time_limit_count", "time_limit_rejected_count", "notable_step_log", "mpc_solve_times_ms",
                     "mpc_time_limit_hits", "mpc_max_solve_ms", "logger"}

CHILD = r'''
import json, sys, dataclasses, hashlib
sys.path.insert(0, ".")
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved import config as improved_config
from thesis_v2.improved.runner import run_episode as improved_run_episode
from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.closed_loop import run_closed_loop_episode
from thesis_v2.anomaly.detector_a import DetectorA
from thesis_v2.anomaly.scenarios import generate_anomaly_scenario

assert improved_config.I5_TIME_LIMIT_SEC == 0.045
COMBO_V1 = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True, i2_variant="narrow")
COMBO_V2 = dict(COMBO_V1, enable_i5=True, i5_max_iter=improved_config.I5_MAX_ITER)
CHANGED = set(json.loads(sys.argv[1]))
out = []

hits = {"n": 0}
_orig = ImprovedMPC.solve
def _solve(self, *a, **k):
    r = _orig(self, *a, **k)
    if getattr(r, "time_limit_hit", False):
        hits["n"] += 1
    return r
ImprovedMPC.solve = _solve

def norm(v):
    if dataclasses.is_dataclass(v):
        return {k: norm(x) for k, x in dataclasses.asdict(v).items()}
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, float):
        return repr(v)
    return v

def rec(kind, seed, res, rows):
    h0 = hits["n"]
    fields = {}
    for f in dataclasses.fields(res):
        if f.name in CHANGED:
            continue
        fields[f.name] = norm(getattr(res, f.name))
    rows = [{k: repr(v) if isinstance(v, float) else v for k, v in r.items() if not (k.startswith("t_") and k.endswith("_ms"))}
            for r in rows]
    out.append(dict(kind=kind, seed=seed, fields=fields, rows=rows,
                    changed=dict(time_limit_count=getattr(res, "time_limit_count", None),
                                 notable_n=len(getattr(res, "notable_step_log", []) or []),
                                 mpc_time_limit_hits=getattr(res, "mpc_time_limit_hits", None))))

mpc = ImprovedMPC(**COMBO_V2)
for s in range(200, 210):
    h = hits["n"]
    r = improved_run_episode(generate_scenario(s), mpc=mpc)
    rec("eval2_paper_v2_shared", s, r, r.logger.rows); out[-1]["tl_hits_in_episode"] = hits["n"] - h
for s in (0, 1, 2):
    h = hits["n"]
    r = improved_run_episode(generate_scenario(s), mpc=ImprovedMPC(**COMBO_V2))
    rec("paper_v2_fresh", s, r, r.logger.rows); out[-1]["tl_hits_in_episode"] = hits["n"] - h
H_A = 9.210921221467048
for s in (3200, 3201, 3207):
    h = hits["n"]
    sc = generate_anomaly_scenario(s)
    r = run_closed_loop_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), detector=DetectorA(threshold=H_A),
                                policy="P0", max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)
    rec("anomaly_P0", s, r, []); out[-1]["tl_hits_in_episode"] = hits["n"] - h
json.dump(out, sys.stdout, ensure_ascii=False)
'''


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def make_old(dst):
    dst.mkdir(parents=True)
    arc = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", OLD_COMMIT, "thesis_v2",
                          ":(exclude)thesis_v2/results"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=arc, check=True)


def make_new(dst):
    dst.mkdir(parents=True)
    shutil.copytree(REPO / "thesis_v2", dst / "thesis_v2",
                    ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc"))


def run(copy):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    r = subprocess.run([sys.executable, "-c", CHILD, json.dumps(sorted(CHANGED_EP_FIELDS))], cwd=copy, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=3600)
    if r.returncode != 0:
        raise SystemExit(r.stderr[-3000:])
    return json.loads(r.stdout)


def h(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=str(Path(os.environ.get("TEMP", "/tmp")) / "run6_cause" / "commit2_compare"))
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    make_old(work / "old")
    make_new(work / "new")
    res = dict(started=now(), old_commit=OLD_COMMIT,
               new_head=subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                       text=True).stdout.strip(),
               new_dirty_files=subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True,
                                              text=True).stdout.splitlines(),
               excluded_fields=sorted(CHANGED_EP_FIELDS) + ["행의 t_*_ms 열"])
    old, new = run(work / "old"), run(work / "new")
    cmp = []
    for o, n in zip(old, new):
        assert (o["kind"], o["seed"]) == (n["kind"], n["seed"])
        same_f, same_r = o["fields"] == n["fields"], o["rows"] == n["rows"]
        diff_f = sorted(k for k in set(o["fields"]) | set(n["fields"]) if o["fields"].get(k) != n["fields"].get(k))
        cmp.append(dict(kind=o["kind"], seed=o["seed"], fields_equal=same_f, rows_equal=same_r, n_rows=len(o["rows"]),
                        fields_hash=[h(o["fields"]), h(n["fields"])], rows_hash=[h(o["rows"]), h(n["rows"])],
                        diff_fields=diff_f, tl_hits_old=o["tl_hits_in_episode"], tl_hits_new=n["tl_hits_in_episode"],
                        changed_old=o["changed"], changed_new=n["changed"]))
    res["comparisons"] = cmp
    res["all_equal"] = all(c["fields_equal"] and c["rows_equal"] for c in cmp)
    res["finished"] = now()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    with gzip.open(out / "outputs_old_new.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(dict(old=old, new=new), fh, ensure_ascii=False)
    for c in cmp:
        print(f"{c['kind']:24s} seed={c['seed']:<5d} fields={'same' if c['fields_equal'] else 'DIFF'} "
              f"rows={'same' if c['rows_equal'] else 'DIFF'} n_rows={c['n_rows']} tl_hits old/new={c['tl_hits_old']}/{c['tl_hits_new']}"
              + (f" diff={c['diff_fields']}" if c["diff_fields"] else ""))
    print("ALL EQUAL" if res["all_equal"] else "DIFFERENCES FOUND")


if __name__ == "__main__":
    main()
