"""baseline_mpc 생성 단계 변이의 등가 판단 보조 실험(equivalence.json의 실험 근거).

- mutate.py를 고치지 않고 그 함수(generate, mutated_text, make_copy, _clear_pycache, _env)만 호출한다.
- 원본과 각 변이를 저장소 밖 임시 사본에서 mpc_setup_probe.py로 실행한다. 생성 결과(A, l, u)와
  444회 solve 출력을 비트 단위로 비교한다.
- 이 실험은 코드 증명이 아니다. 입력 없는 생성자 결과(A, l, u)의 비교만 전수 확인이고, solve 출력 비교는 표본이다.

사용(저장소 루트): python docs/verification/mutation/mpc_setup_experiment.py --out docs/verification/mutation/raw/mpc_setup_experiment.json
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mutate as M  # noqa: E402

IDS = ["baseline_mpc:142", "baseline_mpc:147", "baseline_mpc:194", "baseline_mpc:196", "baseline_mpc:205"]

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args()

src = (M.ROOT / "thesis_v2/baseline/mpc.py").read_text(encoding="utf-8")
muts = {m.id: m for m in M.generate("baseline_mpc", src)}


def run(text):
    tmp = Path(tempfile.mkdtemp(prefix="mut_eqexp_"))
    try:
        M.make_copy(tmp)
        (tmp / "thesis_v2/baseline/mpc.py").write_text(text, encoding="utf-8")
        M._clear_pycache(tmp)
        r = subprocess.run([sys.executable, str(HERE / "mpc_setup_probe.py")], cwd=tmp, env=M._env(),
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit(r.stderr[-800:])
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


base = run(src)
res = dict(purpose="baseline_mpc 생성 단계 변이: 생성 결과·solve 출력 비트 비교", started=time.strftime("%Y-%m-%dT%H:%M:%S"),
           host=platform.node(), python=sys.version.split()[0],
           packages={p: version(p) for p in ("numpy", "scipy", "osqp")},
           n_solves=len(base["solves"]), solver_statuses=sorted(set(s[1] for s in base["solves"])),
           n_fallback=sum(1 for s in base["solves"] if s[2]), mutants=[])
for i in IDS:
    mu = muts[i]
    o = run(M.mutated_text(src, mu))
    res["mutants"].append(dict(id=i, line=mu.edits[0].start[0], operator=mu.operator,
                               A_same=o["A"] == base["A"], l_same=o["l"] == base["l"], u_same=o["u"] == base["u"],
                               solve_mismatches=sum(x != y for x, y in zip(o["solves"], base["solves"]))))
    print(res["mutants"][-1], flush=True)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("n_solves", res["n_solves"], "statuses", res["solver_statuses"], "fallback", res["n_fallback"])
