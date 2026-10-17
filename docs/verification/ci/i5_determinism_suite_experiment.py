"""CI와 같은 방식(전체 pytest 한 프로세스)으로 test_i5_golden_determinism_three_runs의 실패 빈도를 센다. 제품 코드·테스트 수정 없음.

i5_determinism_experiment.py는 테스트 본문만 새 프로세스에서 돌린다. CI 실패는 전체 수집 실행 중(같은 프로세스에서 앞선 테스트들 뒤)에
났으므로, 이 스크립트는 CI 명령과 같은 범위(thesis_v2/tests + thesis_v2/anomaly/tests)를 그대로 반복한다.

사용(저장소 루트): python docs/verification/ci/i5_determinism_suite_experiment.py --trials 30 --out <json>
"""
import argparse
import json
import multiprocessing as mp
import os
import platform
import re
import shutil
import subprocess
import tempfile
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = "test_improved_i5.py::test_i5_golden_determinism_three_runs"


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


def make_copy(variant, hidden_probe=False):
    """저장소 밖 임시 사본(thesis_v2 + time_limit_monitor 플러그인). variant는 i5_determinism_experiment.VARIANTS의 키."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from i5_determinism_experiment import VARIANTS, ANCHOR
    tmp = Path(tempfile.mkdtemp(prefix="i5suite_"))
    shutil.copytree(ROOT / "thesis_v2", tmp / "thesis_v2", ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc"))
    (tmp / "_plugin").mkdir()
    shutil.copy2(Path(__file__).resolve().parent / "time_limit_monitor.py", tmp / "_plugin" / "time_limit_monitor.py")
    if hidden_probe:  # 2026-10-13 추가: "solved inaccurate"로 바뀐 time_limit 정지도 센다(hidden_time_limit_probe.py)
        shutil.copy2(Path(__file__).resolve().parent / "hidden_time_limit_probe.py", tmp / "_plugin" / "hidden_time_limit_probe.py")
    code = VARIANTS[variant]
    if code:
        f = tmp / "thesis_v2/improved/mpc.py"
        s = f.read_text(encoding="utf-8")
        assert s.count(ANCHOR) == 1
        f.write_text(s.replace(ANCHOR, f"        {code}  # 실험 변형\n" + ANCHOR), encoding="utf-8")
    return tmp


def run_suite(copy=None):
    """copy가 없으면 저장소에서 직접(플러그인 없이), 있으면 임시 사본에서 time_limit_monitor 플러그인과 함께 실행한다."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    args = [sys.executable, "-m", "pytest", "thesis_v2/tests", "thesis_v2/anomaly/tests", "-q", "-rf", "-p", "no:cacheprovider"]
    cwd = ROOT
    if copy is not None:
        cwd = copy
        env["PYTHONPATH"] = str(copy / "_plugin")
        env["TIME_LIMIT_LOG"] = str(copy / "_tl.json")
        args += ["-p", "time_limit_monitor"]
        if (copy / "_plugin" / "hidden_time_limit_probe.py").exists():
            env["HIDDEN_TL_LOG"] = str(copy / "_hidden.json")
            args += ["-p", "hidden_time_limit_probe"]
    r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    failed = re.findall(r"^FAILED (\S+)", r.stdout, flags=re.M)
    diff = re.findall(r"At index (\d+) diff: (\S+) != (\S+)", r.stdout)
    res = dict(returncode=r.returncode, tail=tail, failed=failed, target_failed=any(TARGET in f for f in failed), diff=diff[:1])
    if copy is not None:
        tl = json.loads((copy / "_tl.json").read_text(encoding="utf-8"))
        res["time_limit"] = dict(n_solve_calls=tl["n_solve_calls"], n_hits=tl["n_time_limit_hits"],
                                 tests_with_hits=tl["tests_with_hits"], failed_tests=tl["failed_tests"])
        if (copy / "_hidden.json").exists():
            res["hidden_time_limit"] = json.loads((copy / "_hidden.json").read_text(encoding="utf-8"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--loads", nargs="*", default=["idle", "cpu"])
    ap.add_argument("--variant", default=None, help="지정하면 임시 사본 + time_limit_monitor로 실행(none/no_time_limit 등)")
    ap.add_argument("--hidden-probe", action="store_true", help="--variant와 함께: hidden_time_limit_probe 플러그인도 켠다")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = dict(purpose="CI run #6 비결정 실패 — 전체 suite 반복", started=time.strftime("%Y-%m-%dT%H:%M:%S"), host=platform.node(),
               platform=platform.platform(), python=sys.version.split()[0], cpu_count=os.cpu_count(),
               git=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
               dirty=bool(subprocess.run(["git", "status", "--porcelain", "thesis_v2"], cwd=ROOT, capture_output=True, text=True).stdout.strip()),
               variant=a.variant, hidden_probe=a.hidden_probe, results=[])
    copy = make_copy(a.variant, a.hidden_probe) if a.variant else None
    for load in a.loads:
        stop, procs = mp.Event(), []
        if load in ("cpu", "cpu_strong"):
            procs = [mp.Process(target=_burn, args=(stop,), daemon=True) for _ in range(os.cpu_count() or 1)]
            for p in procs:
                p.start()
            time.sleep(3.0)
        state_start = pc_state()
        runs, t0 = [], time.perf_counter()
        try:
            for k in range(a.trials):
                r = run_suite(copy)
                runs.append(r)
                tl = r.get("time_limit", {})
                print(f"{load:4s} trial {k:2d} {r['tail']} target_failed={r['target_failed']} {r['diff']} tl_hits={tl.get('n_hits')} hidden={r.get('hidden_time_limit', {}).get('n_hidden')}", flush=True)
            state_end = pc_state()
        finally:
            stop.set()
            for p in procs:
                p.join(timeout=5)
        out["results"].append(dict(load=load, pc_state_start=state_start, pc_state_end=state_end, n_trials=a.trials, n_target_failed=sum(r["target_failed"] for r in runs),
                                   n_any_failed=sum(r["returncode"] != 0 for r in runs), seconds=round(time.perf_counter() - t0, 1), runs=runs))
    if copy is not None:
        shutil.rmtree(copy, ignore_errors=True)
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in out["results"]:
        print("SUMMARY", r["load"], f"target_failed {r['n_target_failed']}/{r['n_trials']}", f"any_failed {r['n_any_failed']}", f"{r['seconds']} s")


if __name__ == "__main__":
    main()
