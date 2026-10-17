"""CI용 pytest 플러그인 — improved v2 MPC의 OSQP time_limit(안전망) 발동을 테스트별로 기록한다.

배경: improved v2는 반복 상한(주 메커니즘)과 함께 OSQP `time_limit`(벽시계 시간, improved/config.py
I5_TIME_LIMIT_SEC)을 안전망으로 둔다. 벽시계 기준이라 느린 공유 CI 러너에서는 발동할 수 있고, 발동하면 해가
달라져 결과 비교 테스트가 실패할 수 있다. 이 플러그인은
- 테스트 결과(통과/실패)를 **바꾸지 않는다** — 실패는 실패로 남는다.
- 대신 어떤 테스트에서 time_limit이 몇 번 발동했는지를 로그·JSON에 남겨, 실패 원인이 "환경(계산 시간)"인지
  "코드"인지 구분할 근거를 준다(발동 0회인 실패는 time_limit 원인이 아님).
- 테스트가 time_limit 설정을 일부러 바꿔 만든 인스턴스의 발동(예: test_i5_time_limit_safety_net_reachable)은
  환경 요인이 아니므로 따로 센다(생성 시점 설정값이 플러그인 로드 시점 기본값과 다르면 "의도적").
- 제어 로직은 바꾸지 않는다 — `ImprovedMPC.solve`를 감싸 원래 함수를 그대로 호출하고 반환값의
  `time_limit_hit` 필드만 읽는다. baseline MPC(golden 대상)에는 time_limit이 없다.

정정(2026-10-14, run #6 조사 docs/verification/ci/run6_cause/ — 위 원문은 그대로 둠):
- 커밋 2 이전의 `time_limit_hit`는 status=="run time limit reached"만 참이었다. 시간으로 끊긴 solve가
  "solved"/"solved inaccurate"로 보고되면 0회로 집계됐다(실측 절단 31건 중 9건). 그래서 그 시기의
  "발동 0회 → time_limit 원인 아님" 판정(run #6 포함)은 근거가 되지 못한다.
- 지금 `time_limit_hit`는 improved/mpc.py `time_limit_fingerprint`(status+반복 수)로 판정한다. OSQP 소스상
  절단과 정확히 일치하므로(raw/S6_fingerprint_check) 이 플러그인 코드는 바꾸지 않고 새 판정을 그대로 따른다.
- 결정론 비교 테스트는 thesis_v2/conftest.py의 i5_time_limit_off fixture로 time_limit을 끈다. 그 인스턴스는
  생성 시점 설정값이 기본값과 달라 위 "의도적" 분류에 들어간다(1e10이라 실제 발동은 없다).

사용: PYTHONPATH에 이 폴더를 넣고 `pytest -p time_limit_monitor ...`. 출력 JSON 경로는 환경변수 TIME_LIMIT_LOG
(기본 time_limit_log.json). GitHub Actions에서는 `::warning`/`::error` 주석으로도 출력한다.
"""
import json
import os
from collections import defaultdict

from thesis_v2.improved import config as _impr_cfg
from thesis_v2.improved import mpc as _impr_mpc

HITS = defaultdict(int)       # nodeid -> 발동 횟수(기본 time_limit 설정 인스턴스 — 환경 요인 후보)
HITS_ALTERED = defaultdict(int)  # nodeid -> 발동 횟수(테스트가 time_limit 설정을 바꿔 만든 인스턴스 — 의도적)
CALLS = defaultdict(int)      # nodeid -> solve 호출 수
OUTCOMES = {}                 # nodeid -> passed/failed/skipped
DEFAULT_LIMIT = _impr_cfg.I5_TIME_LIMIT_SEC  # 플러그인 로드 시점(테스트 실행 전) 설정값
_orig_init = _impr_mpc.ImprovedMPC.__init__
_orig_solve = _impr_mpc.ImprovedMPC.solve


def _nodeid():
    return os.environ.get("PYTEST_CURRENT_TEST", "(수집/세션 단계)").rsplit(" (", 1)[0]


def _init(self, *args, **kwargs):
    _orig_init(self, *args, **kwargs)
    # time_limit은 생성 시 OSQP setup에 들어간다(improved/mpc.py). 생성 시점 설정값을 기억해 의도적 변경과 구분한다.
    self._tlm_limit_at_init = _impr_cfg.I5_TIME_LIMIT_SEC


def _solve(self, *args, **kwargs):
    res = _orig_solve(self, *args, **kwargs)
    nid = _nodeid()
    CALLS[nid] += 1
    if getattr(res, "time_limit_hit", False):
        if getattr(self, "_tlm_limit_at_init", DEFAULT_LIMIT) == DEFAULT_LIMIT:
            HITS[nid] += 1
        else:
            HITS_ALTERED[nid] += 1
    return res


_impr_mpc.ImprovedMPC.__init__ = _init
_impr_mpc.ImprovedMPC.solve = _solve


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        OUTCOMES[report.nodeid] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    hit_tests = {k: v for k, v in HITS.items() if v > 0}
    failed = sorted(k for k, v in OUTCOMES.items() if v == "failed")
    log = dict(
        time_limit_sec_config=DEFAULT_LIMIT,
        n_solve_calls=sum(CALLS.values()),
        n_time_limit_hits=sum(HITS.values()),
        n_time_limit_hits_altered_config=sum(HITS_ALTERED.values()),
        tests_with_altered_config_hits={k: dict(hits=v, outcome=OUTCOMES.get(k, "?"))
                                        for k, v in sorted(HITS_ALTERED.items())},
        tests_with_hits={k: dict(hits=v, solve_calls=CALLS[k], outcome=OUTCOMES.get(k, "?"))
                         for k, v in sorted(hit_tests.items())},
        failed_tests=[dict(test=k, time_limit_hits=HITS.get(k, 0)) for k in failed],
    )
    with open(os.environ.get("TIME_LIMIT_LOG", "time_limit_log.json"), "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)

    print(f"\n[time_limit_monitor] improved MPC solve {log['n_solve_calls']}회, time_limit 발동 "
          f"{log['n_time_limit_hits']}회(테스트 {len(hit_tests)}개), 실패 테스트 {len(failed)}개 "
          f"[별도: 테스트가 time_limit 설정을 바꿔 의도적으로 발동 {log['n_time_limit_hits_altered_config']}회]")
    for k, v in sorted(HITS_ALTERED.items()):
        print(f"[time_limit_monitor]   (의도적, 설정 변경) 발동 {v}회 — 결과: {OUTCOMES.get(k, '?')} — {k}")
    for k, v in sorted(hit_tests.items()):
        msg = f"time_limit 발동 {v}회 / solve {CALLS[k]}회 — 결과: {OUTCOMES.get(k, '?')} — {k}"
        print(f"[time_limit_monitor]   {msg}")
        if gha:
            level = "error" if OUTCOMES.get(k) == "failed" else "warning"
            print(f"::{level}::[time_limit] {msg} (실패는 그대로 유지, 환경 요인 가능성 기록)")
    for k in failed:
        if HITS.get(k, 0) == 0:
            print(f"[time_limit_monitor]   실패, time_limit 발동 0회(시간 제한 원인 아님) — {k}")

