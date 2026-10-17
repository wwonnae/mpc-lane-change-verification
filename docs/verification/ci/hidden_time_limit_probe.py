"""실험용 pytest 플러그인 — time_limit_monitor가 놓치는 "숨은" time_limit 정지를 테스트별로 센다. 제어 로직·테스트 결과는 바꾸지 않는다.

배경(확인됨, osqp 소스): OSQP 1.x는 time_limit으로 반복을 멈춘 뒤 근사 종료 판정(check_termination(..., 1))을 한 번 더 하고,
통과하면 상태를 "solved inaccurate"로 바꾼다(osqp/codegen/codegen_src/src/osqp_api.c:958-964). improved/mpc.py는
상태 문자열이 "run time limit reached"일 때만 time_limit_hit=True로 기록하므로(improved/mpc.py:408), 이 경우는 발동으로 잡히지 않는다.

판별: 정상 수렴은 "solved", 반복 상한 도달 후 근사 통과는 "solved inaccurate"이면서 반복 수 == max_iter다(osqp_api.c:950-955).
따라서 "solved inaccurate"이면서 반복 수 < max_iter인 solve는 time_limit 정지 뒤 근사 통과로 본다.
(check_termination 주기 25회마다만 종료 판정을 하므로 반복 수 < max_iter인 "solved inaccurate"는 다른 경로로 생기지 않는다 — 추정,
근거: 같은 파일 반복 루프의 종료 판정은 approximate=0으로만 호출됨.)

사용: time_limit_monitor와 함께 `-p hidden_time_limit_probe`, 출력 JSON 경로는 환경변수 HIDDEN_TL_LOG.
"""
import json
import os
from collections import defaultdict

from thesis_v2.improved import mpc as _impr_mpc

HIDDEN = defaultdict(int)   # nodeid -> "solved inaccurate" & iter < max_iter 수
EXPLICIT = defaultdict(int)  # nodeid -> "run time limit reached" 수
OUTCOMES = {}
_orig_solve = _impr_mpc.ImprovedMPC.solve


def _nodeid():
    return os.environ.get("PYTEST_CURRENT_TEST", "(수집/세션 단계)").rsplit(" (", 1)[0]


def _solve(self, *args, **kwargs):
    res = _orig_solve(self, *args, **kwargs)
    nid = _nodeid()
    max_iter = int(self.prob.settings.max_iter)
    if res.solver_status == "solved inaccurate" and res.iterations < max_iter:
        HIDDEN[nid] += 1
    if res.solver_status == "run time limit reached":
        EXPLICIT[nid] += 1
    return res


_impr_mpc.ImprovedMPC.solve = _solve


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        OUTCOMES[report.nodeid] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    failed = sorted(k for k, v in OUTCOMES.items() if v == "failed")
    log = dict(n_hidden=sum(HIDDEN.values()), n_explicit=sum(EXPLICIT.values()),
               tests_with_hidden={k: dict(hidden=v, outcome=OUTCOMES.get(k, "?")) for k, v in sorted(HIDDEN.items())},
               tests_with_explicit={k: dict(explicit=v, outcome=OUTCOMES.get(k, "?")) for k, v in sorted(EXPLICIT.items())},
               failed_tests=[dict(test=k, hidden=HIDDEN.get(k, 0), explicit=EXPLICIT.get(k, 0)) for k in failed])
    with open(os.environ.get("HIDDEN_TL_LOG", "hidden_tl.json"), "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
