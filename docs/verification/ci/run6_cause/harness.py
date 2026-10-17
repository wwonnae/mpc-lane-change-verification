"""run #6 비결정성 반복 실험 러너(1~4단계). 제품 코드·기존 테스트는 고치지 않고, 임시 사본(--root)의 테스트 함수를
그대로 호출한다. PLAN.md의 사전 선언을 따른다.

명령
  python harness.py run   --spec <spec.json>       # 실험 실행(중단·재개 가능, 10회 묶음 단위)
  python harness.py batch ...                      # (내부) 한 묶음을 별도 프로세스에서 실행
  python harness.py env   --out <env.json>         # PC 정보만 기록

spec.json
  {"exp": "S2_load", "out_dir": "...", "batch_size": 10, "block": 5, "settle_s": 12,
   "arms": [{"name": "L1", "root": "<사본>", "targets": ["i5","i4","base"], "probe": true, "load_k": 4, "trials": 300}, ...]}
  - 묶음 순서: arms 순서대로 block개 묶음씩 번갈아(교차 실행 — 시간에 따른 부하·온도 변화가 한 arm에 몰리지 않게).
    부하가 바뀔 때마다 settle_s초 기다린다(첫 묶음 전에도).
  - 끝난 묶음은 out_dir/batches/<arm>_<r>.json.gz 가 있으면 건너뛴다(재개).
  - out_dir/STOP 파일을 만들면 진행 중인 묶음을 끝내고 멈춘다(event "pause").
  - 시작·재개·중단·끝 시각, 묶음 시작·끝, 부하 변경은 out_dir/events.jsonl에 남는다.

대상(1회차 = 아래 대상을 각각 1번씩)
  i5     : test_improved_i5.test_i5_golden_determinism_three_runs (I5 on, max_iter 1944, 3 에피소드)
  i4     : test_i4_student의 동일성 테스트 3개 — recorder(seed 100), closed_loop(seed 100), closed_loop(seed 101)
  base   : baseline run_episode(generate_scenario(0)) 3회, 시간 열 제외 전체 행 비트 비교(대조군)
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMING_FIELDS = ("t_mpc_solve_ms", "t_step_ms")
IS_WIN = os.name == "nt"

# 부하 프로세스: 순수 파이썬 바쁜 루프 1개 = 코어 1개. venv 런처를 거치지 않도록 기본 인터프리터로 띄워
# Popen PID가 실제 부하 프로세스 PID가 되게 하고, harness가 사라지면(강제 종료 포함) 스스로 끝난다.
SPIN_CODE = r"""
import ctypes, os, sys
pp = int(sys.argv[1])
def alive():
    if os.name == "nt":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pp)
        if not h:
            return False
        c = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(c))
        k.CloseHandle(h)
        return c.value == 259
    try:
        os.kill(pp, 0)
        return True
    except OSError:
        return False
n = 0
while True:
    n += 1
    if n % 5000000 == 0 and not alive():
        break
"""
BASE_PY = getattr(sys, "_base_executable", None) or sys.executable


def _alive(pid):
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        c = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(c))
        k.CloseHandle(h)
        return c.value == 259
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _hash(obj):
    return hashlib.sha256(repr(obj).encode()).hexdigest()[:16]


# =====================================================================================
# 묶음(batch) 실행 — 별도 프로세스
# =====================================================================================

class _Capture:
    """테스트 모듈이 부르는 run_episode를 감싸 반환값만 모은다(인자·반환값 그대로)."""

    def __init__(self):
        self.eps = []

    def wrap(self, fn, kind):
        def w(*a, **k):
            r = fn(*a, **k)
            self.eps.append((kind, r))
            return r
        return w


def _episode_view(kind, r):
    """에피소드 결과에서 비교용 시계열을 뽑는다."""
    if kind == "cl":  # student_i4/closed_loop.run_episode: traj=(t,x,y,psi,state,delta_desired,delta_final,mode)
        delta = [row[6] for row in r["traj"]]
        full = [tuple(row) for row in r["traj"]]
        solve_rows = None  # cl은 solver_status를 기록하지 않는다 — solve↔step 대응은 ref(imp) 쪽으로 한다
        outcome = (r["outcome"], r["total_steps"])
    else:  # improved/baseline EpisodeResult
        rows = r.logger.rows
        delta = [row["delta_final"] for row in rows]
        full = [tuple((k, v) for k, v in row.items() if k not in TIMING_FIELDS) for row in rows]
        solve_rows = [i for i, row in enumerate(rows) if row.get("solver_status") != "N/A"]
        outcome = (r.outcome, r.total_steps)
    return dict(kind=kind, delta=delta, full=full, solve_rows=solve_rows, outcome=outcome)


def _solve_summary(solves):
    st = {}
    for s in solves:
        st[s["status"]] = st.get(s["status"], 0) + 1
    return dict(n=len(solves), status=st,
                n_tl_fp=sum(1 for s in solves if s["tl_fp"]),
                n_tl_status=sum(1 for s in solves if s["status"] == "run time limit reached"),
                max_wall_ms=max((s["wall_ms"] for s in solves), default=None),
                max_run_time_ms=max(((s["run_time"] or 0) * 1e3 for s in solves), default=None),
                sum_iter=sum(s["iter"] for s in solves),
                rho_updates_total=sum(s["rho_updates"] or 0 for s in solves))


def _first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else n


def _compare(va, vb, sa, sb):
    """에피소드 a/b 비교: 조향 첫 불일치 행, 최대 차이, solve 수준 첫 불일치와 그 solve의 입력 동일 여부."""
    i = _first_diff(va["delta"], vb["delta"])
    out = dict(delta_equal=(i is None), first_delta_row=i, len_a=len(va["delta"]), len_b=len(vb["delta"]),
               full_equal=(va["full"] == vb["full"]), outcome_equal=(va["outcome"] == vb["outcome"]))
    if i is not None:
        n = min(len(va["delta"]), len(vb["delta"]))
        out["max_abs_delta_diff_deg"] = max(abs(x - y) for x, y in zip(va["delta"][:n], vb["delta"][:n]))
        out["delta_at_first"] = [va["delta"][i] if i < len(va["delta"]) else None,
                                 vb["delta"][i] if i < len(vb["delta"]) else None]
    if sa is not None and sb is not None and (sa or sb):
        xa = [s["x_hash"] for s in sa]
        xb = [s["x_hash"] for s in sb]
        k = _first_diff(xa, xb)
        out["first_solve_diff"] = k
        if k is not None and k < len(sa) and k < len(sb):
            pa, pb = sa[k]["in_parts"], sb[k]["in_parts"]
            out["first_solve_in_equal"] = (sa[k]["in_hash"] == sb[k]["in_hash"])
            out["first_solve_in_parts_diff"] = sorted(key for key in set(pa) | set(pb) if pa.get(key) != pb.get(key))
            out["first_solve_tl_fp"] = [sa[k]["tl_fp"], sb[k]["tl_fp"]]
            rows = va["solve_rows"] if va["solve_rows"] is not None else vb["solve_rows"]
            out["first_solve_row"] = rows[k] if rows is not None and k < len(rows) else None
            lo, hi = max(0, k - 3), k + 4
            strip = lambda s: {kk: vv for kk, vv in s.items() if kk != "in_parts"}  # noqa: E731
            out["window_a"] = [strip(s) for s in sa[lo:hi]]
            out["window_b"] = [strip(s) for s in sb[lo:hi]]
    return out


def _group(solves):
    g = {}
    for s in solves:
        g.setdefault(s["inst"], []).append(s)
    return [g[k] for k in sorted(g)]


def _run_case(fn, cap, probe, n_eps, pairs, keep_full):
    """테스트 함수 1개 실행. pairs: 비교할 에피소드 쌍 [(a,b), ...]."""
    cap.eps.clear()
    if probe:
        probe.take()
    t0 = time.perf_counter()
    err = None
    try:
        fn()
        passed = True
    except AssertionError as e:
        passed = False
        err = ("AssertionError: " + str(e))[:300]
    except Exception:  # 테스트 오류(실패 아님)도 남긴다
        passed = False
        err = traceback.format_exc()[-1500:]
    dt = time.perf_counter() - t0
    solves = probe.take() if probe else []
    views = [_episode_view(k, r) for k, r in cap.eps]
    by_inst = _group(solves) if probe else []
    inst_ok = (not probe) or len(by_inst) == len(views)
    eps_out = []
    for j, v in enumerate(views):
        s = by_inst[j] if probe and inst_ok else None
        e = dict(kind=v["kind"], n_rows=len(v["delta"]), delta_hash=_hash(v["delta"]), full_hash=_hash(v["full"]),
                 outcome=v["outcome"])
        if s is not None:
            e["solves"] = _solve_summary(s)
            e["tl_fp_solves"] = [{kk: vv for kk, vv in x.items() if kk != "in_parts"} for x in s if x["tl_fp"]]
        eps_out.append(e)
    cmps = []
    for a, b in pairs:
        if a < len(views) and b < len(views):
            sa = by_inst[a] if probe and inst_ok else None
            sb = by_inst[b] if probe and inst_ok else None
            c = _compare(views[a], views[b], sa, sb)
            c["pair"] = [a, b]
            cmps.append(c)
    mismatch = (not passed) or any(not c["delta_equal"] for c in cmps)
    out = dict(passed=passed, err=err, secs=round(dt, 4), n_eps=len(views), expected_eps=n_eps,
               inst_ok=inst_ok, n_inst=len(by_inst), mismatch=mismatch, eps=eps_out, cmp=cmps)
    if probe and (mismatch or keep_full):
        out["solves_full"] = solves
    return out


def batch_main(args):
    pidfile = os.environ.get("RUN6_BATCH_PIDFILE")
    if pidfile:  # venv 런처가 아닌 실제 인터프리터 PID를 sysmon에 알린다
        Path(pidfile).write_text(str(os.getpid()) + "\n")
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    import thesis_v2
    assert Path(thesis_v2.__file__).resolve().is_relative_to(root), thesis_v2.__file__
    probe = None
    if args.probe:
        import osqp_probe
        osqp_probe.install()
        probe = osqp_probe
    targets = args.targets.split(",")
    cap = _Capture()
    cases = []
    if "i5" in targets:
        import thesis_v2.tests.test_improved_i5 as m5
        m5.improved_run_episode = cap.wrap(m5.improved_run_episode, "imp")
        cases.append(("i5", m5.test_i5_golden_determinism_three_runs, 3, [(0, 1), (0, 2), (1, 2)]))
    if "i4" in targets:
        import thesis_v2.tests.test_i4_student as m4
        m4.improved_run_episode = cap.wrap(m4.improved_run_episode, "imp")
        m4.cl_run_episode = cap.wrap(m4.cl_run_episode, "cl")
        cases.append(("i4_rec", m4.test_i4_recorder_does_not_change_episode, 2, [(0, 1)]))
        cases.append(("i4_cl100", lambda: m4.test_i4_closed_loop_matches_improved_runner_with_mpc(100), 2, [(0, 1)]))
        cases.append(("i4_cl101", lambda: m4.test_i4_closed_loop_matches_improved_runner_with_mpc(101), 2, [(0, 1)]))
    if "base" in targets:
        from thesis_v2.baseline import runner as brun
        from thesis_v2.baseline.world import generate_scenario
        run_b = cap.wrap(brun.run_episode, "base")

        def base_case():
            r = [run_b(generate_scenario(0)) for _ in range(3)]
            v = [_episode_view("base", x) for x in r]
            assert v[0]["full"] == v[1]["full"] == v[2]["full"]
        cases.append(("base", base_case, 3, [(0, 1), (0, 2), (1, 2)]))
    trials = []
    keep_full_first = args.keep_full_first
    for t in range(args.trials):
        tr = dict(trial=t, t_start=now_iso(), pid=os.getpid())
        for name, fn, n_eps, pairs in cases:
            tr[name] = _run_case(fn, cap, probe, n_eps, pairs, keep_full=(t < keep_full_first))
        tr["t_end"] = now_iso()
        trials.append(tr)
        if args.parent_pid and not _alive(args.parent_pid):
            # harness가 사라졌다 = 부하·기록 조건이 이 묶음 도중에 바뀌었다. 결과를 남기지 않는다(재개 시 다시 실행).
            print(f"[batch {args.batch_id}] harness(PID {args.parent_pid}) 없음 — 묶음 폐기", flush=True)
            sys.exit(3)
        if args.progress:
            print(f"[batch {args.batch_id}] trial {t} " + " ".join(
                f"{n}={'ok' if tr[n]['passed'] and not tr[n]['mismatch'] else 'MISMATCH'}" for n, *_ in cases),
                flush=True)
    import numpy, scipy, osqp
    meta = dict(batch_id=args.batch_id, arm=args.arm, root=str(root), probe=bool(args.probe), targets=targets,
                pid=os.getpid(), python=sys.version, numpy=numpy.__version__, scipy=scipy.__version__,
                osqp=osqp.__version__, condition=_read_json(root / "_run6_condition.json"),
                copy=_read_json(root / "_run6_copy.json"), load_k=args.load_k)
    out = Path(args.out)
    tmp = out.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(dict(meta=meta, trials=trials), f)
    os.replace(tmp, out)


def _read_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


# =====================================================================================
# 환경 기록
# =====================================================================================

def _cmd(c):
    try:
        return subprocess.run(c, capture_output=True, text=True, timeout=60, shell=isinstance(c, str)).stdout.strip()
    except Exception as e:
        return f"(실패: {e})"


def env_info():
    import numpy, scipy, osqp
    d = dict(time=now_iso(), hostname=platform.node(), platform=platform.platform(), machine=platform.machine(),
             processor=platform.processor(), cpu_count=os.cpu_count(), python=sys.version, executable=sys.executable,
             numpy=numpy.__version__, scipy=scipy.__version__, osqp=osqp.__version__,
             env={k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                                  "PYTHONHASHSEED", "GITHUB_ACTIONS", "RUNNER_OS", "ImageOS",
                                                  "ImageVersion", "RUNNER_NAME")})
    try:
        import torch
        d["torch"] = torch.__version__
        d["torch_threads"] = torch.get_num_threads()
    except Exception as e:
        d["torch"] = f"(없음: {e})"
    if IS_WIN:
        d["cpu"] = _cmd(["powershell", "-NoProfile", "-Command",
                         "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,"
                         "MaxClockSpeed | ConvertTo-Json -Compress"])
        d["os"] = _cmd(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber | "
                        "ConvertTo-Json -Compress"])
        d["power_scheme"] = _cmd(["powercfg", "/getactivescheme"])
    else:
        d["cpu"] = _cmd("lscpu")
        d["os"] = _cmd("cat /etc/os-release")
        d["nproc"] = _cmd("nproc")
    try:
        d["loadavg"] = os.getloadavg()
    except Exception:
        pass
    return d


# =====================================================================================
# 실험 실행(오케스트레이터)
# =====================================================================================

class _Exp:
    def __init__(self, spec):
        self.spec = spec
        self.dir = Path(spec["out_dir"]).resolve()
        (self.dir / "batches").mkdir(parents=True, exist_ok=True)
        self.events = self.dir / "events.jsonl"
        self.pid_exp = self.dir / "pids_exp.txt"
        self.pid_load = self.dir / "pids_load.txt"
        self.pid_batch = self.dir / "pids_batch.txt"
        self.sysmon_log = self.dir / "sysmon.jsonl"
        self.load = []
        self.load_k = 0
        self.load_started = False
        self.sysmon = None
        self.cur_batch_pid = None

    def ev(self, event, **kw):
        rec = dict(time=now_iso(), event=event, **kw)
        with open(self.events, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[harness] {rec['time']} {event} " + " ".join(f"{k}={v}" for k, v in kw.items()), flush=True)

    def write_pids(self):
        ids = [os.getpid()] + ([self.cur_batch_pid] if self.cur_batch_pid else [])
        if self.sysmon:
            ids.append(self.sysmon.pid)
        self.pid_exp.write_text("\n".join(str(i) for i in ids) + "\n")
        self.pid_load.write_text("\n".join(str(p.pid) for p in self.load) + "\n")

    def set_load(self, k):
        if k == self.load_k and len(self.load) == k and self.load_started:
            return
        self.load_started = True
        self.stop_load()
        for _ in range(k):
            self.load.append(subprocess.Popen([BASE_PY, "-c", SPIN_CODE, str(os.getpid())]))
        self.load_k = k
        self.write_pids()
        settle = float(self.spec.get("settle_s", 12))
        self.ev("load_set", k=k, pids=[p.pid for p in self.load],
                method="기본 인터프리터 순수 파이썬 바쁜 루프 x k(SPIN_CODE), 우선순위 Normal", exe=BASE_PY,
                settle_s=settle)
        # 부하 변경 뒤 대기: 부하 프로세스 기동 + 10초 CPU 표본 구간이 이전 부하 조건과 겹치지 않게
        time.sleep(settle)

    def stop_load(self):
        for p in self.load:
            p.kill()
        for p in self.load:
            try:
                p.wait(10)
            except Exception:
                pass
        if self.load:
            self.ev("load_stop", k=self.load_k)
        self.load = []
        self.load_k = 0
        self.write_pids()

    def sysmon_once(self, tag):
        if not IS_WIN:
            try:
                self.ev("loadavg", tag=tag, loadavg=os.getloadavg())
            except Exception:
                pass
            return
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "sysmon.ps1"),
                        "-Out", str(self.sysmon_log), "-ExpPidFile", f"{self.pid_exp};{self.pid_batch}",
                        "-LoadPidFile", str(self.pid_load), "-Once", "-OnceGap", "3", "-Tag", tag], check=False)

    def sysmon_start(self):
        if not IS_WIN:
            return
        self.sysmon = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "sysmon.ps1"),
             "-Out", str(self.sysmon_log), "-ExpPidFile", f"{self.pid_exp};{self.pid_batch}",
             "-LoadPidFile", str(self.pid_load), "-Interval", "10", "-ParentPid", str(os.getpid())])
        self.write_pids()

    def sysmon_stop(self):
        if self.sysmon:
            self.sysmon.kill()
            self.sysmon = None

    def schedule(self):
        """arms를 block개 묶음씩 번갈아 실행한다(block=1이면 묶음마다 교차). 순서는 spec만으로 정해진다."""
        bs = int(self.spec.get("batch_size", 10))
        block = int(self.spec.get("block", 1))
        arms = self.spec["arms"]
        nb = {a["name"]: (a["trials"] + bs - 1) // bs for a in arms}
        out = []
        r0 = 0
        while r0 < max(nb.values()):
            for a in arms:
                for r in range(r0, min(r0 + block, nb[a["name"]])):
                    out.append((a, r, min(bs, a["trials"] - r * bs)))
            r0 += block
        return out


def _last_seen(exp):
    """비정상 종료 시각 추정: 마지막 이벤트·마지막 sysmon 표본 중 늦은 것."""
    cands = []
    for p in (exp.events, exp.sysmon_log):
        if p.exists():
            lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
            if lines:
                d = json.loads(lines[-1])
                cands.append(d.get("time") or d.get("t_end"))
    return max(cands) if cands else None


def run_main(args):
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    exp = _Exp(spec)
    prev = []
    if exp.events.exists():
        prev = [json.loads(x) for x in exp.events.read_text(encoding="utf-8").splitlines() if x.strip()]
    stop_file = exp.dir / "STOP"
    if stop_file.exists():
        stop_file.unlink()
    if not prev:
        (exp.dir / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        (exp.dir / "env.json").write_text(json.dumps(env_info(), ensure_ascii=False, indent=1), encoding="utf-8")
        exp.ev("start", exp=spec["exp"])
    else:
        last = prev[-1]["event"]
        if last in ("end",):
            print("[harness] 이미 끝난 실험이다.")
            return
        if last in ("pause", "interrupt", "error"):
            exp.ev("resume", previous=last, previous_time=prev[-1]["time"])
        else:
            exp.ev("resume_after_unclean_stop", last_seen=_last_seen(exp),
                   note="이전 실행이 이벤트 없이 끝남(강제 종료 등). last_seen = 마지막 기록 시각 = 중단 시각 추정치")
    exp.write_pids()
    exp.sysmon_start()
    exp.sysmon_once("session_start")
    batches = exp.schedule()
    n_done0 = sum(1 for a, r, n in batches if (exp.dir / "batches" / f"{a['name']}_{r:03d}.json.gz").exists())
    exp.ev("schedule", total_batches=len(batches), already_done=n_done0)
    status = "end"
    try:
        for a, r, n in batches:
            out = exp.dir / "batches" / f"{a['name']}_{r:03d}.json.gz"
            if out.exists():
                continue
            if stop_file.exists():
                stop_file.unlink()
                status = "pause"
                break
            exp.set_load(int(a.get("load_k", 0)))
            cmd = [sys.executable, str(HERE / "harness.py"), "batch", "--root", str(Path(a["root"]).resolve()), "--targets",
                   ",".join(a["targets"]), "--trials", str(n), "--out", str(out), "--arm", a["name"],
                   "--batch-id", f"{a['name']}_{r:03d}", "--load-k", str(a.get("load_k", 0)),
                   "--keep-full-first", str(a.get("keep_full_first", 0) if r == 0 else 0),
                   "--parent-pid", str(os.getpid())]
            if a.get("probe", True):
                cmd.append("--probe")
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)  # 원본 저장소가 import 경로에 끼지 않게
            env["PYTHONIOENCODING"] = "utf-8"
            env["RUN6_BATCH_PIDFILE"] = str(exp.pid_batch)
            exp.ev("batch_start", batch=f"{a['name']}_{r:03d}", trials=n, load_k=exp.load_k)
            p = subprocess.Popen(cmd, env=env, cwd=str(exp.dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            exp.cur_batch_pid = p.pid
            exp.write_pids()
            log = p.communicate()[0]
            exp.pid_batch.write_text("")
            exp.cur_batch_pid = None
            exp.write_pids()
            if p.returncode != 0 or not out.exists():
                (exp.dir / f"batch_error_{a['name']}_{r:03d}.log").write_text(log, encoding="utf-8")
                exp.ev("error", batch=f"{a['name']}_{r:03d}", returncode=p.returncode, tail=log[-500:])
                status = "error"
                break
            mism = _batch_mismatch_count(out)
            exp.ev("batch_end", batch=f"{a['name']}_{r:03d}", mismatches=mism)
    except KeyboardInterrupt:
        status = "interrupt"
    finally:
        exp.stop_load()
        exp.sysmon_once("session_end")
        exp.sysmon_stop()
        exp.ev(status)


def _batch_mismatch_count(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        d = json.load(f)
    cnt = {}
    for t in d["trials"]:
        for k, v in t.items():
            if isinstance(v, dict) and "mismatch" in v:
                cnt[k] = cnt.get(k, 0) + int(v["mismatch"])
    return cnt


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--spec", required=True)
    b = sub.add_parser("batch")
    b.add_argument("--root", required=True)
    b.add_argument("--targets", default="i5,i4,base")
    b.add_argument("--trials", type=int, default=10)
    b.add_argument("--out", required=True)
    b.add_argument("--arm", default="")
    b.add_argument("--batch-id", default="")
    b.add_argument("--load-k", type=int, default=0)
    b.add_argument("--probe", action="store_true")
    b.add_argument("--keep-full-first", type=int, default=0)
    b.add_argument("--progress", action="store_true")
    b.add_argument("--parent-pid", type=int, default=0)
    e = sub.add_parser("env")
    e.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "run":
        run_main(args)
    elif args.cmd == "batch":
        batch_main(args)
    else:
        Path(args.out).write_text(json.dumps(env_info(), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
