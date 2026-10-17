"""CI run #6 비결정 실패(test_i5_golden_determinism_three_runs) 재현 실험. 제품 코드·테스트는 수정하지 않는다.

- 시행 1회 = 새 프로세스에서 그 테스트 본문(I5 on, paper seed 0, 에피소드 3회)을 실행하고, 조향 시계열과
  매 solve의 반복 수·상태·시간을 기록한다. 3회 시계열이 모두 같으면 일치.
- 조건: 부하 없음 / CPU 부하(논리 코어 수만큼 바쁜 루프 프로세스).
- 변형: 저장소 밖 임시 사본(thesis_v2만 복사)의 improved/mpc.py에서 OSQP setup 인자만 바꾼다.
    none                : 변경 없음(원본과 같음)
    rho_interval_50     : adaptive_rho_interval=50 명시(osqp 1.1.1 기본값과 같음 — 사용자 요청 변형)
    adaptive_rho_off    : adaptive_rho=0(rho 적응 끔)
    no_time_limit       : time_limit 키 제거(I5 안전망 끔, OSQP 기본 1e10 s)
- 출력: JSON(조건·변형별 불일치 시행 수, 첫 불일치 위치, 불일치 시행의 해당 solve 반복 수·시간).

사용(저장소 루트): python docs/verification/ci/i5_determinism_experiment.py --trials 30 --out <json>
"""
import argparse
import json
import multiprocessing as mp
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PROBE = r'''
import json, os, sys
sys.path.insert(0, os.getcwd())
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved import mpc as impr
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode
FINAL_COMBO = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True, i2_variant="narrow")
rec = []
orig = impr.ImprovedMPC.solve
def solve(self, *a, **k):
    r = orig(self, *a, **k)
    rec[-1].append([r.iterations, r.solver_status, round(r.compute_time_ms, 3), r.time_limit_hit])
    return r
impr.ImprovedMPC.solve = solve
out = []
for _ in range(3):
    rec.append([])
    m = ImprovedMPC(**FINAL_COMBO, enable_i5=True, i5_max_iter=1944)
    res = run_episode(generate_scenario(0), mpc=m)
    out.append([row["delta_final"] for row in res.logger.rows])
print(json.dumps(dict(series=out, solves=rec, settings=dict(
    adaptive_rho=int(m.prob.settings.adaptive_rho), adaptive_rho_interval=int(m.prob.settings.adaptive_rho_interval),
    time_limit=float(m.prob.settings.time_limit), max_iter=int(m.prob.settings.max_iter)))))
'''

VARIANTS = {
    "none": None,
    "rho_interval_50": 'setup_kwargs["adaptive_rho_interval"] = 50',
    "adaptive_rho_off": 'setup_kwargs["adaptive_rho"] = 0',
    "no_time_limit": 'setup_kwargs.pop("time_limit", None)',
}
ANCHOR = "        self.prob.setup(**setup_kwargs)\n"


def _burn(stop):
    """CPU 부하용 바쁜 루프. stop 확인(프로세스 간 잠금)은 100만 반복마다 한 번만 한다 — 매 반복 확인하면 잠금 대기 때문에
    부하가 약해진다(2026-10-13 첫 실행 'cpu' 조건에서 CPU LoadPercentage 36% 확인 → 'cpu_strong'으로 다시 실행)."""
    x = 0
    while True:
        for _ in range(1_000_000):
            x = (x * 1103515245 + 12345) & 0xFFFFFFFF
        if stop.is_set():
            return


def pc_state():
    """CPU LoadPercentage(평균)와 전원 상태(Win32_Battery BatteryStatus: 2 = AC 연결)를 기록한다. Windows 외에서는 빈 값."""
    if os.name != "nt":
        return {}
    ps = ("$c=(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average;"
          "$b=(Get-CimInstance Win32_Battery | Select-Object -First 1 -ExpandProperty BatteryStatus);"
          "[pscustomobject]@{cpu_load_percent=$c;battery_status=$b} | ConvertTo-Json")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout)
    except Exception as ex:
        return dict(error=repr(ex))


def make_copy(variant):
    tmp = Path(tempfile.mkdtemp(prefix="i5det_"))
    shutil.copytree(ROOT / "thesis_v2", tmp / "thesis_v2", ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc"))
    code = VARIANTS[variant]
    if code:
        f = tmp / "thesis_v2/improved/mpc.py"
        s = f.read_text(encoding="utf-8")
        assert s.count(ANCHOR) == 1
        f.write_text(s.replace(ANCHOR, f"        {code}  # 실험 변형\n" + ANCHOR), encoding="utf-8")
    (tmp / "_probe.py").write_text(PROBE, encoding="utf-8")
    return tmp


def trial(tmp):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    r = subprocess.run([sys.executable, "_probe.py"], cwd=tmp, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(r.stderr[-1500:])
    return json.loads(r.stdout)


def compare(d):
    s = d["series"]
    if s[0] == s[1] == s[2]:
        return None
    for a, b in ((0, 1), (0, 2), (1, 2)):
        if s[a] != s[b]:
            idx = next((i for i, (x, y) in enumerate(zip(s[a], s[b])) if x != y), min(len(s[a]), len(s[b])))
            sa, sb = d["solves"][a], d["solves"][b]
            out = dict(pair=[a, b], index=idx, values=[s[a][idx] if idx < len(s[a]) else None, s[b][idx] if idx < len(s[b]) else None],
                        solve_at_index=[sa[idx] if idx < len(sa) else None, sb[idx] if idx < len(sb) else None],
                        first_solve_diff=next((i for i, (x, y) in enumerate(zip(sa, sb)) if x[:2] != y[:2]), None),
                        n_solves=[len(sa), len(sb)])
            # 첫 반복수·상태 차이 solve 앞뒤 기록(2026-10-13 추가: 첫 재현에서 값이 남지 않아 다시 실행)
            fd = out["first_solve_diff"]
            if fd is not None:
                out["solves_around_first_diff"] = dict(a=sa[max(0, fd - 2):fd + 3], b=sb[max(0, fd - 2):fd + 3], start=max(0, fd - 2))
            return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--variants", nargs="*", default=list(VARIANTS))
    ap.add_argument("--loads", nargs="*", default=["idle", "cpu"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = dict(purpose="CI run #6 test_i5_golden_determinism_three_runs 비결정 재현", started=time.strftime("%Y-%m-%dT%H:%M:%S"),
               host=platform.node(), platform=platform.platform(), python=sys.version.split()[0], cpu_count=os.cpu_count(),
               git=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
               dirty=bool(subprocess.run(["git", "status", "--porcelain", "thesis_v2"], cwd=ROOT, capture_output=True, text=True).stdout.strip()),
               trials=a.trials, results=[])
    for variant in a.variants:
        tmp = make_copy(variant)
        try:
            for load in a.loads:
                stop, procs = mp.Event(), []
                if load in ("cpu", "cpu_strong"):
                    procs = [mp.Process(target=_burn, args=(stop,), daemon=True) for _ in range(os.cpu_count() or 1)]
                    for p in procs:
                        p.start()
                    time.sleep(3.0)
                state_start = pc_state()
                mism, tl_hits, settings, max_iter_hits, t0 = [], 0, None, 0, time.perf_counter()
                try:
                    for k in range(a.trials):
                        d = trial(tmp)
                        settings = d["settings"]
                        tl_hits += sum(x[3] for run in d["solves"] for x in run)
                        max_iter_hits += sum(x[1] == "maximum iterations reached" for run in d["solves"] for x in run)
                        c = compare(d)
                        if c:
                            c["trial"] = k
                            mism.append(c)
                        print(f"{variant:17s} {load:4s} trial {k:2d} {'MISMATCH ' + str(c['index']) if c else 'same'}", flush=True)
                    state_end = pc_state()
                finally:
                    stop.set()
                    for p in procs:
                        p.join(timeout=5)
                out["results"].append(dict(variant=variant, load=load, pc_state_start=state_start, pc_state_end=state_end,
                                           n_trials=a.trials, n_mismatch=len(mism),
                                           time_limit_hits=tl_hits, max_iter_status_count=max_iter_hits,
                                           osqp_settings=settings, seconds=round(time.perf_counter() - t0, 1), mismatches=mism))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in out["results"]:
        print("SUMMARY", r["variant"], r["load"], f"{r['n_mismatch']}/{r['n_trials']}", "tl_hits", r["time_limit_hits"], "maxiter", r["max_iter_status_count"], r["osqp_settings"])


if __name__ == "__main__":
    main()
