"""run #6 비결정성 조사용 OSQP 기록 래퍼(1단계). 제품 코드는 고치지 않는다.

`osqp.OSQP` 클래스의 setup/update/warm_start/solve를 감싸, 원래 함수를 같은 인자로 그대로 호출하고
반환값과 인자를 **읽기만** 한다. solve마다 다음을 기록한다.

- OSQP 인스턴스 번호(생성 순서), 그 인스턴스의 solve 순번
- status, status_val, iter, rho_updates, rho_estimate, prim_res, dual_res
- setup_time, update_time, solve_time, run_time(OSQP 자체 측정, 초), wall_ms(래퍼의 perf_counter, 원래 solve 호출 구간)
- 인스턴스의 C 쪽 설정(time_limit, max_iter, adaptive_rho, adaptive_rho_interval, check_termination)
- 입력 해시: 직전 solve 이후 update()/warm_start()로 넘어간 배열(q, l, u, Px, Px_idx, Ax, Ax_idx, x, y)의 sha256
  (첫 solve는 setup의 P, q, A, l, u). 출력 해시: res.x, res.y의 sha256.
- tl_fingerprint: STATIC_ANALYSIS.md §3-3 규칙으로 판별한 time_limit 발동 여부

해시 계산은 원래 update()/solve() 호출 **바깥**(파이썬 쪽)에서 한다. OSQP의 time_limit 판정에 쓰이는 C 타이머
(setup_time/update_time/solve 경과)는 C 함수 안에서만 재므로 이 계산 시간은 들어가지 않는다(osqp v1.0.0
src/osqp_api.c:743-751, 1200-1253, 1326-1405).

사용
- 라이브러리: `import osqp_probe; osqp_probe.install(); ...; recs = osqp_probe.take()`
- pytest 플러그인: `pytest -p osqp_probe ...` (환경변수 OSQP_PROBE_LOG에 JSONL로 테스트별 기록)
"""
import hashlib
import json
import os
import time

import numpy as np
import osqp
import scipy.sparse as sp

_OSQP = osqp.OSQP
_ORIG = {}
_RECORDS = []
_SERIAL = [0]

_SETTING_KEYS = ("time_limit", "max_iter", "adaptive_rho", "adaptive_rho_interval", "check_termination")
_INFO_KEYS = ("status", "status_val", "iter", "rho_updates", "rho_estimate", "prim_res", "dual_res",
              "setup_time", "update_time", "solve_time", "run_time")


def _h(v):
    if v is None:
        return None
    if sp.issparse(v):
        v = v.tocsc()
        return hashlib.sha256(np.ascontiguousarray(v.data).tobytes() + np.ascontiguousarray(v.indices).tobytes()
                              + np.ascontiguousarray(v.indptr).tobytes()).hexdigest()[:16]
    a = np.ascontiguousarray(np.asarray(v))
    return hashlib.sha256(str(a.dtype).encode() + a.tobytes()).hexdigest()[:16]


def tl_fingerprint(status, iters, max_iter, check_termination):
    """STATIC_ANALYSIS.md §3-3: time_limit으로 끊긴 solve인지 iteration 기록으로 판별."""
    if status == "run time limit reached":
        return True
    if status == "solved inaccurate" and iters < max_iter:
        return True
    if status == "solved" and check_termination and iters % check_termination != 0 and iters != max_iter:
        return True
    # 2026-10-14 추가(안 B, raw/S6_fingerprint_check/): 첫 반복에서 끊기고 update_info(0) 검사를 통과하면
    # "solved", iter 0이 된다(osqp_api.c:908-931). 정상 종료는 iter 0으로 "solved"를 낼 수 없다.
    # 이 추가 전 기록(S1~S4)에는 해당 사례가 0건이라 기존 판정은 바뀌지 않는다(S6 README).
    if status == "solved" and iters == 0 and iters != max_iter:
        return True
    return False


def _setup(self, *args, **kwargs):
    out = _ORIG["setup"](self, *args, **kwargs)
    _SERIAL[0] += 1
    self._probe_serial = _SERIAL[0]
    self._probe_nsolve = 0
    names = ("P", "q", "A", "l", "u")
    vals = dict(zip(names, args))
    vals.update({k: kwargs[k] for k in names if k in kwargs})
    self._probe_pending = {f"setup_{k}": _h(vals.get(k)) for k in names}
    s = self._solver.get_settings()
    self._probe_settings = {k: (int(getattr(s, k)) if k != "time_limit" else float(getattr(s, k)))
                            for k in _SETTING_KEYS}
    return out


def _update(self, **kwargs):
    pend = getattr(self, "_probe_pending", None)
    if pend is not None:
        for k in sorted(kwargs):
            pend[f"upd_{k}"] = _h(kwargs[k])
    return _ORIG["update"](self, **kwargs)


def _warm_start(self, x=None, y=None):
    pend = getattr(self, "_probe_pending", None)
    if pend is not None:
        pend["ws_x"] = _h(x)
        pend["ws_y"] = _h(y)
    return _ORIG["warm_start"](self, x=x, y=y)


def _solve(self, *args, **kwargs):
    t0 = time.perf_counter_ns()
    res = _ORIG["solve"](self, *args, **kwargs)
    t1 = time.perf_counter_ns()
    info = res.info
    rec = {k: getattr(info, k, None) for k in _INFO_KEYS}
    rec["iter"] = int(rec["iter"])
    st = getattr(self, "_probe_settings", {})
    rec.update(st)
    rec["inst"] = getattr(self, "_probe_serial", -1)
    rec["k"] = getattr(self, "_probe_nsolve", -1)
    rec["wall_ms"] = (t1 - t0) / 1e6
    pend = getattr(self, "_probe_pending", None) or {}
    rec["in_hash"] = hashlib.sha256(json.dumps(pend, sort_keys=True).encode()).hexdigest()[:16]
    rec["in_parts"] = dict(pend)
    rec["x_hash"] = _h(res.x)
    rec["y_hash"] = _h(res.y)
    rec["tl_fp"] = tl_fingerprint(rec["status"], rec["iter"], st.get("max_iter", -1), st.get("check_termination", 0))
    self._probe_nsolve = rec["k"] + 1
    self._probe_pending = {}
    _RECORDS.append(rec)
    return res


def install():
    if _ORIG:
        return
    for name, fn in (("setup", _setup), ("update", _update), ("warm_start", _warm_start), ("solve", _solve)):
        _ORIG[name] = getattr(_OSQP, name)
        setattr(_OSQP, name, fn)


def uninstall():
    for name, fn in _ORIG.items():
        setattr(_OSQP, name, fn)
    _ORIG.clear()


def installed():
    return bool(_ORIG)


def take():
    """지금까지의 기록을 돌려주고 비운다(인스턴스 번호도 1부터 다시 센다 — 새로 만들어지는 인스턴스부터 적용)."""
    out = list(_RECORDS)
    _RECORDS.clear()
    _SERIAL[0] = 0
    return out


# ---------------- pytest 플러그인 ----------------

def pytest_configure(config):
    install()


def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    path = os.environ.get("OSQP_PROBE_LOG", "osqp_probe_log.jsonl")
    recs = take()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"nodeid": report.nodeid, "outcome": report.outcome, "solves": recs}) + "\n")
