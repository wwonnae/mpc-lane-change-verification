# CI — 전체 단위 테스트 + golden(폐루프 SIL 회귀)

워크플로: `.github/workflows/ci.yml`. push·PR마다 `{ubuntu-24.04, windows-2025} × Python 3.9`로 실행한다(`fail-fast: false`).
러너 이미지는 run #1에서 확인한 이미지를 기준으로 고정했다(아래 "러너 이미지 고정"). run #1 자체는 `ubuntu-latest`·`windows-latest` 라벨로 실행되었다.

> **상태(2026-10-13)**: GitHub Actions run #1(커밋 b3d2ead, `-latest` 라벨)이 두 OS 모두 성공했다(아래 "첫 GitHub 실행 결과").
> 이미지를 고정한 워크플로(`ubuntu-24.04`·`windows-2025`)의 run #2(커밋 45c944e)는 두 job 모두 성공했다(사용자 전달). 아래 "run #2 — 이미지 고정 확인" 참고.
> 2단계에서 추가한 추적 매트릭스·UML 대조 단계는 45c944e 이후 변경이라 아직 GitHub에서 실행하지 않았다.
> **run #6(커밋 4c0c503)**: Windows attempt 1에서 `test_i5_golden_determinism_three_runs` 실패, attempt 2 통과 → 비결정(확인됨). 원인은 가설 단계다(아래 "run #6" 절, "다음 작업").
>
> **[정정·갱신 2026-10-15 — 위 원문은 그대로 둠]**
> - run #6 원인은 **확정됐다: OSQP `time_limit` 절단**(`ci/run6_cause/README.md` §1). 대응은 결정 2+5+0이다. 아래 "run #6" 절 첫머리의 정정 블록을 본다.
> - 추적 매트릭스·UML·안전 수치표 대조는 run #6 attempt 1에서 GitHub 러너로 실행됐고 두 OS 모두 일치했다(아래 run #6 "사실" 표, `ci/raw/run6_attempt1/*_check.txt`). 위 셋째 줄("아직 GitHub에서 실행하지 않았다")은 그 이전 시점의 서술이다.
> - 지금 ci.yml의 단계 전체는 아래 "실행 내용" 표에, GitHub 실행 기록은 "주요 실행 기록"에 정리했다.

## 실행 내용

| 단계 | 명령 | 비고 |
|---|---|---|
| 설치 | `pip install -r thesis_v2/requirements-py39.txt -r thesis_v2/anomaly/requirements-anomaly.txt` + `torch==2.8.0`(CPU 인덱스) | 노트북 고정 조합 그대로(numpy 2.0.2, scipy 1.13.1, osqp 1.1.1, pytest 8.4.2, scikit-learn 1.6.1, pandas 2.2.3). onnx·onnxruntime·coverage는 설치하지 않음 |
| 환경 기록 | `platform`, `pip freeze` → `ci-out/env.txt` | |
| 단위 테스트 | `pytest thesis_v2/tests thesis_v2/anomaly/tests -p time_limit_monitor` → `ci-out/junit.xml`, `ci-out/time_limit_log.json` | 수집된 테스트는 하나도 빼지 않는다 |
| golden | `python -m thesis_v2.tests.check_golden` → `ci-out/golden.txt` | 단위 테스트가 실패해도 실행한다(`if: always()`). golden 기준값은 읽기만 하고 `generate_golden`은 실행하지 않는다 |
| 추적 매트릭스 대조 | `python docs/verification/aspice/make_trace_matrix.py --check` → `ci-out/trace_check.txt` | 저장된 `TRACE_MATRIX.md`·`trace_matrix.json`이 그 OS에서 다시 생성한 결과와 바이트 단위로 같은지 본다(2단계 추가, `aspice/README.md`). 생성물은 `.gitattributes`로 LF 체크아웃 |
| UML 대조 | `python docs/verification/aspice/check_uml.py` → `ci-out/uml_check.txt` | 상태도·시퀀스도·컴포넌트도 ↔ 코드(2단계 추가) |
| 안전 수치표 대조 | `python docs/verification/safety/make_safety_tables.py --check` → `ci-out/safety_check.txt` | 저장된 평가 CSV(git 추적)로 FMEA·FTTI 수치표를 다시 계산해 바이트 비교(3단계 추가, 평가 재실행 아님) |
| mutation 도구 자체 테스트 | `python -m pytest docs/verification/mutation/test_mutate.py -q -p no:cacheprovider` → `ci-out/mutate_selftest.txt` | 변이 생성·적용·층 실행기 자체 테스트(PREREGISTRATION §6). 제품 테스트 수(359)에는 들어가지 않는다. 전체 변이 실행은 CI에서 하지 않는다(약 1시간, 타임아웃 판정이 러너 부하에 묶임 — PREREGISTRATION §9) |
| mutation 수치표 대조 | `python docs/verification/mutation/make_mutation_tables.py --check` → `ci-out/mutation_tables_check.txt` | 저장된 `raw/*.json`·`equivalence.json`으로 `MUTATION_TABLES.md`를 다시 만들어 바이트 비교(변이 재실행 아님). 생성물은 `.gitattributes`로 LF 체크아웃 |
| 로그 보관 | `ci-out/`를 OS별 artifact로 업로드 | 실패해도 업로드한다 |

**[갱신 2026-10-15]** 위 표를 `.github/workflows/ci.yml`의 현재 단계와 맞췄다(mutation 두 줄은 커밋 ac5f01b에서 ci.yml에 추가, 로그 보관 줄은 원래 아래 문단 뒤에 떨어져 있던 것을 표 안으로 옮김). 순서도 ci.yml과 같다.
- golden 이후 다섯 대조 단계(추적 매트릭스, UML, 안전 수치표, mutation 자체 테스트, mutation 수치표)는 모두 `if: always()`라 앞 단계가 실패해도 실행된다. 각 단계는 `tee`로 파이프하지만 `exit ${PIPESTATUS[0]}`로 원래 명령의 종료 코드를 돌려준다.
- 단위 테스트 단계의 환경: `PYTHONPATH=docs/verification/ci`(time_limit_monitor 위치), `TIME_LIMIT_LOG=ci-out/time_limit_log.json`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`. pytest 옵션은 `-q -rfEs -p time_limit_monitor -p no:cacheprovider --junitxml=ci-out/junit.xml`이다.
- **결정론 테스트 fixture(run #6 대응, 커밋 6971d64)**: 단위 테스트 단계의 명령은 바뀌지 않았다. 다만 두 실행을 비트 단위로 비교하는 테스트 등 9개 함수(수집 항목 37개)는 `thesis_v2/conftest.py`의 `i5_time_limit_off` fixture로 I5 time_limit을 1e10으로 끈 상태에서 실행된다(제품 설정 0.045는 그대로). time_limit 발동 경로는 `test_i5_time_limit_safety_net_reachable`이 계속 검증하고, fixture가 실제 OSQP 설정에 닿는지는 보호 테스트 2개가 확인한다(`ci/run6_cause/COMMIT2_VERIFY.md` §1, README §4 "커밋 2 세부 결정").
- 현재 수집 테스트 수는 **359**다(이 PC 3층PC109 확인, COMMIT2_VERIFY §5). GitHub 러너에서는 6971d64·ac5f01b·931f7bf가 두 OS 모두 성공했다(사용자 전달). 다만 러너에서의 테스트 수는 로그를 받지 않아 확인하지 않았다(아래 "주요 실행 기록").

**대조 단계가 실패했을 때(저장소 루트에서 실행, 실패 로그 끝 줄에도 같은 명령이 출력된다)**:

- 추적 매트릭스: `python docs/verification/aspice/make_trace_matrix.py && git diff -- docs/verification/aspice/TRACE_MATRIX.md docs/verification/aspice/trace_matrix.json`
  — 재생성한 뒤 차이가 의도한 변경(테스트 추가, REQ 인용 변경 등)인지 확인하고, 생성물을 함께 커밋한다.
- 안전 수치표: `python docs/verification/safety/make_safety_tables.py && git diff -- docs/verification/safety/SAFETY_TABLES.md docs/verification/safety/safety_numbers.json`
  — 입력 결과 CSV나 FMEA.md의 time_limit 표기가 바뀌었는지 먼저 확인한다(결과 폴더는 원래 바뀌면 안 된다).
- UML: 그림은 손으로 쓴 문서라 자동 재생성이 없다. 실패 목록대로 `docs/verification/aspice/UML.md`를 코드에 맞게 고친 뒤 `python docs/verification/aspice/check_uml.py`로 다시 확인한다.
- mutation 수치표(2026-10-15 추가): `python docs/verification/mutation/make_mutation_tables.py && git diff -- docs/verification/mutation/MUTATION_TABLES.md`
  — 원자료(`raw/*.json`)나 `equivalence.json`이 바뀌었는지 먼저 확인한다. 원자료는 실행 기록이라 원래 바뀌면 안 된다.
- mutation 도구 자체 테스트: 실패한 테스트를 로컬에서 `python -m pytest docs/verification/mutation/test_mutate.py -q`로 재현한다. 도구(`mutate.py`)는 사전 선언 도구이므로 고치면 RESULTS.md "사전 선언 변경"에 기록한다.

`PYTHONUTF8=1`: 요구사항 파일의 한글 주석과 한글 출력 때문에 둔다. Windows 기본 코드페이지로 읽으면 실패한다. 이 PC에서도 같은 문제가 있었다(DESIGN §24, 1042행 이후).

## 제외 판단

- **제외한 pytest 테스트: 0개.** 계산 시간의 **절대값**을 판정하는 테스트가 없다(grep 확인). 시간 관련 단언은 모두 환경과 무관한 형태다.
  - 자기 일관성: `test_summary.py:133`(step 시간 ≥ MPC 시간), `:36·39`(기록값끼리 일치)
  - 상수: `:146`(예산 50 ms)
  - 0보다 큼: `anomaly/tests/test_closed_loop.py:140`
  - 기록 길이: `test_detector_timing.py:22`
  - `test_closed_loop.py:156`의 46.1은 가짜 결과 파일에 넣은 값을 다시 읽는 것이다.
- `test_envinfo.py`는 Windows 전원 API(`powercfg`, 레지스트리, `GetSystemPowerStatus`)를 쓴다. 하지만 `envinfo.py`가 실패 시 `"unknown"`/`"감지 불가"`를 돌려주게 되어 있고,
  테스트는 형식과 논리 관계만 본다. run #1에서 Ubuntu 전체 295 passed·0 skipped(junit)로 이 테스트도 통과했다(확인됨).
- **CI에서 실행하지 않는 것**: 계산 시간 측정 스크립트(`improved/student_i4/benchmark_timing.py`, `anomaly/benchmark_detector_timing.py`, `tests/compare/run_onnx_benchmark.py`).
  이유는 두 가지다. 공식 계산 시간은 노트북(DESKTOP-MDCKRJS) + AC 전원 + 최고 성능 조건에서만 유효하다(README 상태 표, 보고서 부록 B). 그리고 공유 vCPU 러너의 시간은 그 조건이 아니다.
  이 파일들은 pytest 테스트가 아니라 스크립트라서 원래 수집되지 않는다. 나머지 평가 스크립트(100 에피소드 실행 등)도 repro/docs/WORK_RULES.md의 "실행은 사용자" 원칙에 따라 CI에 넣지 않았다.
- `tests/compare/`(옛 코드 import, C·M 트랙)는 `test_*.py`가 없어 수집되지 않는다.

## OSQP time_limit 기록 (`docs/verification/ci/time_limit_monitor.py`)

improved v2 MPC는 반복 상한(972)과 함께 OSQP `time_limit = 0.045 s`(벽시계)를 안전망으로 둔다(`improved/config.py:37`). 느린 러너에서는 이 안전망이 발동해 해가 달라질 수 있다.

- 플러그인은 `ImprovedMPC.solve`를 감싸 반환값의 `time_limit_hit`만 읽는다. **테스트 결과를 바꾸지 않는다.** 실패는 실패로 남고, 어느 테스트에서 몇 번 발동했는지를
  `ci-out/time_limit_log.json`, 콘솔, GitHub 주석에 남긴다. 실패한 테스트에서 발동했으면 `::error`, 통과한 테스트에서 발동했으면 `::warning`이다.
  발동이 0회인 실패에는 "시간 제한 원인 아님"이라고 표시한다.
- 테스트가 설정값을 일부러 바꿔 발동시키는 경우(`test_i5_time_limit_safety_net_reachable`, 1e-9 s)는 인스턴스 생성 시점의 설정값이 기본값과 다르다. 이런 발동은 "의도적"으로 따로 센다.
- baseline MPC(golden 대상)에는 time_limit이 없다(`baseline/mpc.py`에 없음, grep 확인). 따라서 golden은 이 요인의 영향을 받지 않는다.

**로컬 확인(확인됨, 실행, 2026-10-13, 3층PC109, Windows, `.venv` Python 3.9.13)** — CI와 같은 명령, 같은 환경변수(bash):
- 정상: **295 passed**, golden **6/6 PASS**(조향각 최대 차이 0.000000 rad), improved MPC solve 13,106회 중 기본 설정의 발동 **0회**, 의도적 발동 1회(위 테스트, 통과).
- 감시 동작 확인(스크래치 전용, 저장소 코드 무수정): 스크래치 플러그인으로 `I5_TIME_LIMIT_SEC = 1e-6`을 강제하고
  `test_golden_equivalence.py` + `test_improved_i5.py`를 실행했다.
  - 발동한 테스트 13개(solve 2,464회 중 발동 2,462회)를 모두 기록했고 `::warning`/`::error` 주석을 출력했다.
  - 이 조건에서 실패한 1개(`test_i5_tiny_iter_cap_triggers_max_iter_status_and_hard_check` — 기대한 상태 "maximum iterations reached" 대신 "run time limit reached")는
    **실패로 유지**됐다(exit 1).
  - golden 동치 테스트들은 발동 중에도 통과했다. 두 쪽이 같은 조건에서 함께 제한을 받았기 때문이다.

> **[정정 2026-10-15, run #6 조사 — 위 절의 원문은 그대로 둠]** 근거: `ci/run6_cause/README.md` §1-2, `STATIC_ANALYSIS.md` §3-3과 정정, `raw/S6_fingerprint_check/`, `S5_IMPACT.md` §2, `COMMIT2_VERIFY.md` §1·§5.
> - **감시가 세던 것(커밋 6971d64 이전).** `time_limit_hit`는 status가 `"run time limit reached"`일 때만 참이었다. 그런데 OSQP는 시간으로 끊긴 solve를 `"solved inaccurate"`나 `"solved"`로도 보고한다. 실측 절단 31건(3층PC109 2, GitHub windows 러너 flaky-probe #1 18·#2 11) 중 9건이 이 감시에 잡히지 않았다. 따라서 위 "발동이 0회인 실패에는 '시간 제한 원인 아님'이라고 표시한다"는 **그 시기 기록에서는 판정 근거가 되지 못한다.** run #1의 "발동 0회", 위 "로컬 확인"의 "발동 0회", run #6의 "발동 0회(시간 제한 원인 아님)"가 모두 이 옛 정의로 센 값이다.
> - **지금 세는 것(커밋 6971d64 이후).** `time_limit_hit`는 `improved/mpc.py`의 `time_limit_fingerprint`(지문 규칙 **안 B**)로 판정한다. 다음 중 하나면 절단이다.
>   - status `"run time limit reached"`
>   - `"solved inaccurate"`이고 iter < max_iter
>   - `"solved"`이고 iter가 check_termination의 배수가 아니며 max_iter도 아님
>   - `"solved"`이고 iter == 0(첫 반복 절단)
>
>   이 규칙은 OSQP C v1.0.0 소스의 종료 경로에서 도출했고, 실측 절단 31/31과 양성 대조에서 일치했다(S6). run_time 조건(안 C)은 넣지 않았다. 플러그인 코드는 바뀌지 않았고 이 새 판정을 그대로 읽는다(`time_limit_monitor.py` docstring 정정 블록).
> - **"발동 0회" 판정 문구의 범위.** 커밋 6971d64 이후 실행에서 "기본 설정 인스턴스의 발동 0회"는 "그 테스트의 기본 설정 인스턴스에서 지문 규칙상 절단이 없었다"는 뜻이다. 판정은 C OSQP v1.0.0 소스 분석에 기댄다. 설치된 osqp 1.1.1 바이너리가 v1.0.0으로 빌드됐다는 것은 sdist 빌드 스크립트에서 추론한 것이다(추정, STATIC_ANALYSIS §1). 그 전 커밋의 기록에는 이 해석을 적용하지 않는다. 플러그인이 출력하는 문구 "(시간 제한 원인 아님)"은 코드에 그대로 남아 있다(`time_limit_monitor.py:104`, 이번에 바꾸지 않음).
> - **결정론 테스트는 time_limit을 끄고 돈다.** 결정론 비교 테스트는 `i5_time_limit_off` fixture(1e10)로 실행된다. 그 인스턴스는 생성 시점 설정값이 기본값과 달라 위 "의도적" 분류에 들어간다. 1e10이라 실제 발동은 없다. 따라서 이 테스트들이 실패하면 time_limit 절단이 아닌 다른 원인을 찾는다.
> - **원인 서술 정정.** 절의 첫 문단 "느린 러너에서는 이 안전망이 발동"은 부정확하다. 절단은 평소 0.1–3 ms인 solve가 한 번에 45 ms 넘게 멈출 때 일어났다(VM 스케줄링·백그라운드 작업으로 추정, S4_RESULT §2). 부하 없는 windows 러너에서도 에피소드의 0.06–0.7%에서 45 ms 초과 정지가 있었다.
> - 커밋 6971d64 이후 로컬 전체 테스트(359 passed)에서는 기본 설정 발동 0회, 의도적 발동 4회였다(COMMIT2_VERIFY §5).

## golden 실패 시 판정 절차

golden 기준값(`thesis_v2/tests/golden/*.json`)은 노트북 Windows(Python 3.9.12, numpy 2.0.2, scipy 1.13.1, osqp 1.1.1)에서 만들어졌다(`golden/env.json`).
판정 기준은 전이·결과·완료 step은 완전 일치, 조향각은 최대 차이 1e-3 rad 이하다(`golden/README.md`). **기준값은 어떤 경우에도 CI 결과에 맞춰 바꾸지 않는다.**

| Windows job | Ubuntu job | 1차 해석 | 다음 확인 |
|---|---|---|---|
| PASS | PASS | 회귀 없음 | — |
| PASS | FAIL | OS·BLAS·컴파일러 차이로 인한 수치 차이 후보 | `golden.txt`의 첫 차이 step·값, `env.txt`의 패키지 버전 비교. 리눅스 참고 기록(아래)과 대조 |
| FAIL | FAIL | 코드 변경을 먼저 의심 | 로컬 Windows `.venv`에서 같은 커밋으로 `check_golden` 재현 |
| FAIL | PASS | Windows 러너 환경(버전 해석 등) 후보 | `env.txt` 비교 |

**리눅스 참고 기록(참고만, 공식 결과 폴더 없음 — 아래 CI 결과와 별개)**: 2026-10-01 연결 폴더 셸(Linux VM, Python 3.10.12, numpy 2.0.2·scipy 1.13.1·osqp 1.1.1, DESIGN §12 193행)에서
기존 테스트 158 passed + torch 없음 1 skip(DESIGN §12 172행). `check_golden` 6/6 PASS는 사용자 전달 기록이다(2026-10-13). DESIGN에는 테스트 수만 문구로 있고, golden 비교 테스트
`test_check_golden.py`는 그 기존 테스트에 포함된다. 당시 기존 테스트 수(README 기준 168)와 158+1의 차이 이유는 기록에 없다. 이 VM은 Python 3.10이므로 CI(3.9)와 조건이 같지 않다.

## 첫 GitHub 실행 결과 (run #1, 커밋 b3d2ead, 2026-10-13)

근거: 사용자가 내려받은 로그 zip(`logs_103842545043.zip`, 같은 파일 `logs_103842545043 (1).zip`은 SHA-256 동일한 중복)의 단계별 로그와
OS별 artifact(`ci-out-ubuntu-latest-py3.9.zip`, `ci-out-windows-latest-py3.9.zip`의 `env.txt`·`junit.xml`·`golden.txt`·`time_limit_log.json`).
값은 모두 이 파일에서 읽었다(확인됨, 파일). 두 job 모두 checkout 로그의 커밋이 `b3d2eadf575da9d000960119bce9f289e8ec0108`이다.
- **[추가 2026-10-15] 원본 위치:** 위 zip 3개는 [`ci/run1_original/`](ci/run1_original/)에 보관한다(sha256은 같은 폴더 `zip_sha256.txt`). 중복 `logs_103842545043 (1).zip`은 바이트 단위로 같아 저장소에서 지웠다.

| 항목 | Ubuntu job (`ubuntu-latest / py3.9`) | Windows job (`windows-latest / py3.9`) | 근거 |
|---|---|---|---|
| Runner Image 이름 / 버전 | `ubuntu-24.04` / 20261004.327.1 | `windows-2025-vs2026` / 20260925.250.1 | `1_Set up job.txt`의 "Runner Image" 그룹 |
| OS | Ubuntu 24.04.5 LTS | Microsoft Windows Server 2025 10.0.26100 Datacenter | 같은 로그 "Operating System" |
| Python | 3.9.25 (GCC 13.3.0) | 3.9.13 (MSC v.1929 64 bit) | `env.txt` 첫 줄, setup-python 다운로드 파일명 |
| torch | 2.8.0+cpu (`cp39-manylinux_2_28_x86_64` 휠) | 2.8.0+cpu (`cp39-win_amd64` 휠) | `4_Install` 로그, `env.txt` |
| numpy / scipy / osqp / pytest / scikit-learn / pandas | 2.0.2 / 1.13.1 / 1.1.1 / 8.4.2 / 1.6.1 / 2.2.3 | 같음 | `env.txt` |
| pytest 결과 줄 | `295 passed in 15.07s` | `295 passed in 21.64s` | `6_Unit tests` 로그 |
| junit | tests=295, failures=0, errors=0, skipped=0 | tests=295, failures=0, errors=0, skipped=0 | `junit.xml` `<testsuite>` |
| check_golden | 6/6 PASS, 6개 모두 max\|diff\|=0.000000 rad, "전체 결과: PASS" | 같음 | `7_Golden` 로그, `golden.txt` |
| time_limit_monitor | solve 13,106회, 기본 설정 발동 **0회**, 의도적 발동 1회(`test_i5_time_limit_safety_net_reachable`, passed), 실패 테스트 0 | 같음 | `6_Unit tests` 로그, `time_limit_log.json` |
| `##[error]` | 없음 | 없음 | 전체 로그 검색 |
| `##[warning]` | Node.js 20 지원 종료 안내 1건(actions/checkout@v4·setup-python@v5·upload-artifact@v4가 Node.js 24로 강제 실행) | 같음 | `17_Complete job.txt` |

- **실패가 초록으로 가려졌을 가능성(확인됨, ci.yml)**: `continue-on-error`는 워크플로 어디에도 없다. 단계는 `shell: bash`(`-e -o pipefail`, 로그의 `shell:` 줄로 확인)로 실행되어
  명령이 실패하면 그 단계가 실패한다. golden 단계는 `tee`로 파이프하지만 `exit ${PIPESTATUS[0]}`로 check_golden의 종료 코드를 그대로 돌려준다.
  `if: ${{ always() }}`(golden, 업로드)는 앞 단계가 실패해도 **실행**하게 할 뿐, job 결과를 성공으로 바꾸지 않는다. 그리고 위 수치(295 passed, failures 0, golden PASS)가
  성공을 직접 보여 준다.
- **리눅스 golden 자동 확인은 이번이 처음이다.** Ubuntu 24.04 + Python 3.9.25에서 golden 6/6 PASS, 조향각 최대 차이 0.000000 rad였다. 기준값을 만든 Windows 노트북과
  OS·컴파일러(GCC vs MSC)·Python 패치 버전이 달라도 표시 자릿수(1e-6 rad)에서 차이가 없었다. 이것은 CI 로그·artifact로 남는 첫 리눅스 golden 기록이다.
  위 "리눅스 참고 기록"(2026-10-01 VM, Python 3.10.12)은 사용자 전달 + DESIGN §12의 테스트 수 문구뿐이며 결과 파일이 없어 별개로 둔다.
- Windows job의 golden도 PASS(차이 0)이다. 따라서 "golden 실패 시 판정 절차" 표의 첫 행(회귀 없음)에 해당한다.

### Python 버전 (OS·환경별)

| 환경 | Python | 컴파일러 | 수치 패키지(numpy / scipy / osqp) | torch | 테스트 | golden | 근거 |
|---|---|---|---|---|---|---|---|
| CI Ubuntu (`ubuntu-24.04`, run #1) | **3.9.25** | GCC 13.3.0 | 2.0.2 / 1.13.1 / 1.1.1 | 2.8.0+cpu | 295 passed | 6/6, 차이 0 | artifact `env.txt`·`junit.xml`·`golden.txt` |
| CI Windows (`windows-2025-vs2026`, run #1) | **3.9.13** | MSC v.1929 | 2.0.2 / 1.13.1 / 1.1.1 | 2.8.0+cpu | 295 passed | 6/6, 차이 0 | 같음 |
| 로컬 3층PC109 (`.venv`, 2026-10-13) | **3.9.13** | (기록 안 함) | 2.0.2 / 1.13.1 / 1.1.1 | 2.8.0+cpu | 295 passed | 6/6, 차이 0 | 이 문서 "로컬 확인"(실행) |
| 참고: golden 생성 노트북(2026-09-17) | 3.9.12 | — | 2.0.2 / 1.13.1 / 1.1.1 | — | — | 기준값 생성 | `thesis_v2/tests/golden/env.json` |

`actions/setup-python`의 `python-version: "3.9"`는 이미지별로 제공되는 3.9 빌드를 받는다. 그래서 패치 버전이 OS마다 다르다(Ubuntu 3.9.25, Windows 3.9.13 — 다운로드 파일명
`python-3.9.25-linux-24.04-x64.tar.gz`, `python-3.9.13-win32-x64.zip`). 패치 버전 차이는 golden 결과에 나타나지 않았다.

## 러너 이미지 고정 (run #1 이후 변경)

- 변경: `runs-on`의 매트릭스 값을 `ubuntu-latest`·`windows-latest`에서 `ubuntu-24.04`·`windows-2025`로 바꿨다.
  - Ubuntu: run #1 Set up job 로그의 "Runner Image" 이름 `ubuntu-24.04`를 그대로 썼다(glibc·빌드 번호로 추정하지 않음).
  - Windows: run #1의 Runner Image는 `windows-2025-vs2026`이었다(`windows-latest _ py3.9/1_Set up job.txt`). 이 이름은 임시 라벨일 수 있어서 정식 라벨 `windows-2025`로 고정했다.
    run #2에서 정식 라벨 `windows-2025`는 run #1과 **같은 이미지**(`windows-2025-vs2026` / 20260925.250.1)로 배정되었다(아래 "run #2 — 이미지 고정 확인").
- 이유: `-latest` 라벨은 가리키는 이미지가 바뀐다. `ubuntu-latest`가 2026-10-19부터 Ubuntu 26으로 이전된다는 안내는 run #1 화면 Annotations notice(로그 zip에는 없음 —
  내려받은 로그 zip의 단계별·통합 로그와 artifact 전체를 검색해 해당 문구가 없음을 확인)로 표시되었다.
  새 이미지에서 `actions/setup-python`이 Python 3.9를 제공하는지는 지금 확인할 수 없다. golden·테스트 결과를 같은 조건에서 반복해 비교하려면(재현성) 이미지를 고정해야 한다.
- 참고(GitHub changelog): Visual Studio 2026 Windows 이미지는 `windows-2025-vs2026` 라벨로 먼저 제공되었고, `windows-latest`·`windows-2025`의 VS 2026 이전이 2026-06에
  예정되었다 — [Upcoming image migrations](https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations),
  [New runner images in public preview](https://github.blog/changelog/2026-06-11-new-runner-images-in-public-preview/). 이 안내와 run #1의 `windows-latest` → `windows-2025-vs2026` 배정은
  어긋나지 않는다. 정식 라벨의 실제 배정은 run #2 Runner Image로 확인했다(아래).
- 영향: artifact 이름이 `ci-out-ubuntu-24.04-py3.9`, `ci-out-windows-2025-py3.9`로 바뀐다(`ci-out-${{ matrix.os }}-…`). job 이름도 같은 값으로 표시된다.
- 고정 이미지에서도 이미지 **버전**(예: 20261004.327.1)은 GitHub이 계속 갱신한다. 그래서 실행마다 Set up job 로그의 버전과 `env.txt`를 함께 남긴다(artifact).

## run #2 — 이미지 고정 확인 (커밋 45c944e)

출처: run #2 화면 Set up job > Runner Image(사용자 전달). 두 job 모두 성공했다(사용자 전달). 이 실행의 로그 zip·artifact는 받지 않았으므로, 테스트 수·golden 값 등은 이 문서에 옮기지 않았다.

| job (라벨) | run #2 Runner Image | run #1 Runner Image | 판정 |
|---|---|---|---|
| windows (`windows-2025`) | `windows-2025-vs2026` / 20260925.250.1 | `windows-2025-vs2026` / 20260925.250.1 (`-latest` 라벨) | **같음** — 이름·버전 일치. 정식 라벨 `windows-2025`가 run #1과 같은 이미지로 배정되었다 |
| ubuntu (`ubuntu-24.04`) | `ubuntu-24.04` / 20261004.327.1 | `ubuntu-24.04` / 20261004.327.1 (`ubuntu-latest` 라벨) | **같음** — 이름·버전 일치. 고정 라벨 `ubuntu-24.04`가 run #1과 같은 이미지로 배정되었다 |

- 한계: 이 판정은 run #2 시점의 배정이다. 라벨이 가리키는 이미지와 그 버전은 GitHub가 바꿀 수 있다. 같은 라벨이 다음 실행에서도 같은 이미지라는 보장은 없다.

## 주요 실행 기록 (2026-10-15 정리)

저장소의 문서·원자료, 또는 사용자가 GitHub Actions 화면에서 확인해 전달한 결과가 있는 실행만 적는다. 근거가 없는 실행은 결과를 추측하지 않고 "기록 없음"으로 둔다. 이 PC에는 gh CLI가 없어 GitHub에서 직접 조회하지 않았다.
`tests-and-golden`(ci.yml, push·PR마다)과 `flaky-probe`(`.github/workflows/flaky_probe.yml`, 수동 실행)는 실행 번호가 따로 매겨진다.

| 실행 | 워크플로 | 커밋 | 결과 | 근거 |
|---|---|---|---|---|
| run #1 | tests-and-golden(`-latest` 라벨) | b3d2ead | 두 OS 성공. 295 passed, golden 6/6(차이 0) | 위 "첫 GitHub 실행 결과"(로그 zip·artifact, 확인됨·파일) |
| run #2 | tests-and-golden(이미지 고정) | 45c944e | 두 job 성공. Runner Image가 run #1과 같음 | 위 "run #2"(사용자 전달, 로그·artifact 받지 않음) |
| run #3–#5 | tests-and-golden | — | **기록 없음** | 저장소에 결과·커밋 대응 근거가 없다 |
| run #6 | tests-and-golden | 4c0c503 | attempt 1: ubuntu 340 passed, **windows 1 failed·339 passed**(`test_i5_golden_determinism_three_runs`). golden 6/6, 추적·UML·안전 수치표 일치(두 OS). attempt 2: windows 성공 | 아래 "run #6"(`ci/raw/run6_attempt1/`, attempt 2는 사용자 전달) |
| (번호 기록 없음) | tests-and-golden | 97d1ed6 | 두 OS(windows-2025, ubuntu-24.04) 성공 | `ci/run6_cause/S4_RESULT.md` §3(사용자 보고, 2026-10-14). run 번호는 기록되지 않았다 |
| flaky-probe #1 | flaky-probe, repeats 500, orig·A, 부하 없음 | 97d1ed6 | job 4개 워크플로 성공(테스트 결과로 실패 처리하지 않는 워크플로). 불일치 회차 windows orig **16/500**, windows A 0/500, ubuntu orig·A 모두 0 | `ci/run6_cause/S4_RESULT.md` §1, `ci/run6_cause/raw/S4_runner/run1/`(원본 zip은 `run1/original_zips/`) |
| flaky-probe #2 | flaky-probe, repeats 1500, orig·A, 부하 없음 | 사용자 보고 없음(조건 적용 해시가 #1과 같아 같은 코드로 추정) | 불일치 회차 windows orig **11/1500**, windows A 0/1500, ubuntu orig·A 모두 0 | `ci/run6_cause/S4_RESULT.md` §5, `ci/run6_cause/raw/S4_runner/run2/`(원본 zip은 `run2/original_zips/`) |
| (번호 기록 없음) | tests-and-golden | 6971d64(run #6 대응 커밋 2: 결정론 테스트 fixture, 지문 규칙 B) | ubuntu·windows 모두 성공 | 사용자 전달(GitHub Actions 화면 확인, 2026-10-15). 로그·artifact는 받지 않음 |
| (번호 기록 없음) | tests-and-golden | ac5f01b(mutation 단계 `test_mutate.py`, `make_mutation_tables.py --check` 추가) | 두 OS 모두 성공. **새 mutation 단계 2개가 GitHub 러너에서 처음 실행돼 통과** | 사용자 전달(GitHub Actions 화면 확인, 2026-10-15). 로그·artifact는 받지 않음 |
| (번호 기록 없음) | tests-and-golden | 931f7bf(노트북 기록 7bd9363 병합, 원본 zip 커밋 642200f·34c1ced 포함) | 두 OS 모두 성공 | 사용자 전달(GitHub Actions 화면 확인, 2026-10-15). 로그·artifact는 받지 않음 |
| 그 밖의 푸시 | tests-and-golden | 30a3a22, 3187e40 등 | **기록 없음** | 저장소에도 사용자 전달에도 결과 근거가 없다 |

- run #6 대응(결정론 테스트 fixture, 지문 규칙, 커밋 6971d64)과 mutation CI 단계 2개(커밋 ac5f01b)는 GitHub 러너에서 두 OS 모두 성공했다(사용자 전달). 다만 로그·artifact를 받지 않아 테스트 수(359)·time_limit 감시 집계 등 세부 값은 이 문서에 옮기지 않았다. 세부 값의 근거는 로컬 3층PC109 실행이다(COMMIT2_VERIFY §5).
- run #1 원본 로그 zip은 커밋 642200f로 저장소 루트 `ci_run1/`에 들어갔고, `ci/run1_original/`로 옮겼다(중복 1개 삭제, sha256 기록). 위 "첫 GitHub 실행 결과" 참고.

## run #6 — Windows job 비결정 실패 1회 (커밋 4c0c503)

출처: attempt 1의 로그 zip(SHA-256 `47d1aee7…854f`)과 artifact zip(`04135af1…d0c9`)은 사용자가 내려받은 것이다(`C:\Users\user\Desktop\ci_run6_attempt1\`). 필요한 파일은
[`ci/raw/run6_attempt1/`](ci/raw/run6_attempt1/)에 복사했다. attempt 2의 결과와 이미지는 사용자가 전달했다. attempt 2의 로그와 artifact는 받지 않았다.

> **[정정 2026-10-15 — 이 절의 원문(2026-10-13 노트북 작성)은 아래에 그대로 둠. 결론은 [`ci/run6_cause/README.md`](ci/run6_cause/README.md) §1이 대신한다]**
>
> - **원인(확정): OSQP `time_limit`(I5 on, 0.045 s) 절단.** 한 solve 안에서 실행 환경이 45 ms 넘게 멈추면 그 solve가 시간으로 끊긴다. 해가 달라지고, warm start를 거쳐 이후 조향 시계열이 갈라진다.
> - **근거:**
>   - GitHub windows 러너, 부하 없음: orig(time_limit 0.045) **16/500**(flaky-probe #1)·**11/1500**(#2) 회차 불일치 대 A(time_limit 1e10) **0/500·0/1500**. 회차 단위 Fisher p=2.7e-5·0.00096(보조). 사전 지정 단위(대상별)는 #1 i4_cl100 p=0.031이고, i5 단독은 #1 p=0.25, #2 p=0.062로 어느 실행에서도 0.05에 이르지 못했다(README §1, §3 한계).
>   - **불일치는 전부 첫 불일치 solve의 입력이 같았고 절단 흔적(지문)이 있었다**: 3층PC109 2/2, 러너 #1 18/18·#2 11/11(대상 단위). 흔적 없는 불일치는 전체 실험에서 0건이다.
>   - A에서는 45 ms 넘는 정지가 있었는데도(러너 #1 42·#2 11 에피소드, 최대 362 ms) 불일치가 0이었다. ubuntu 러너는 최대 solve가 5 ms 안팎이라 정지도 불일치도 없었다.
>   - run #6 attempt 1의 "발동 0회"는 옛 감시가 `"solved inaccurate"`/`"solved"`로 보고된 절단을 세지 못한 것과 맞는다(러너 #1의 i5 불일치 3건 중 2건이 그런 형태, S4_RESULT §1).
> - **대응: 결정 2 + 5 + 0**(사용자 결정 2026-10-14, README §4). 1(재시도)·3(제품 time_limit 제거)·4(값 증가)는 채택하지 않았다.
>   - 2: 결정론 테스트 fixture — `thesis_v2/conftest.py`의 `i5_time_limit_off`를 결정론 비교 테스트 등 9개 함수(수집 37개)에 명시 적용. 제품 설정 0.045는 유지(커밋 6971d64).
>   - 5: 지문 규칙 B — `time_limit_hit`를 `time_limit_fingerprint`로 판정. 출력 불변 로깅 변경이며, 저장 평가 `--check`로 확인했다(COMMIT2_VERIFY §2·§3·§8).
>   - 0: 문서 정정 — DESIGN_IMPROVED_V2, RESULT_IMPROVED §10, anomaly DESIGN, `time_limit_monitor.py` docstring(커밋 6971d64), 그리고 이 CI.md(이번).
> - **아래 노트북 실험(A–E, F 부분 실행)은 조건 통제 안 됨, 참고로만 둔다.** 같은 노트북에서 다른 작업을 함께 했고(커밋 7bd9363 메시지), 같은 "강한 부하"에서도 실패 빈도가 D1 15/30·D2 16/30·E 2/30으로 흔들렸다. 원인 판단은 run6_cause의 사전 선언 실험(3층PC109 S1–S3, GitHub 러너 S4)에 기댄다.
> - **노트북에서 세운 가설의 판정:**
>   - 가설 (1) time_limit — **맞음**(위 근거로 확정).
>   - 가설 (2) adaptive rho(시간 기준 rho 갱신이 실행마다 달라짐) — **틀림.** 설정은 반복 수 기준(`adaptive_rho=1`, interval 50)이고, 래퍼가 기록한 rho 갱신 수는 모든 조건에서 실행마다 같았다(README §1-3). 노트북 원문도 이미 "시간 기반 모드는 쓰이지 않는다"고 적었지만, 원인 후보에서 빼지 않고 F 재실행을 남겨 두었다. F는 다시 실행하지 않았다. interval 50 고정이 원래 설정과 같아서, 그 조건(조건 B)은 run6_cause에서도 두지 않았다(README §1 "사용자 결정 기록").
>   - 노트북의 숨은 발동 판별("`solved inaccurate` + iter < max_iter", 실험 E·`ci/hidden_time_limit_probe.py`)은 **불완전했다.** `"solved"`로 보고되는 절단을 빠뜨린다. 지금 규칙은 안 B다(위 "OSQP time_limit 기록" 정정 블록).
> - 아래 하위 절별 정정은 각 절 첫머리에 짧게 붙였다.

### 사실 (확인됨)

| 항목 | attempt 1 ubuntu | attempt 1 windows | attempt 2 windows | 근거 |
|---|---|---|---|---|
| 커밋 | `4c0c503797fd…` | 같음 | 같음(사용자 전달: 같은 run의 재실행) | checkout 로그 |
| Runner Image | `ubuntu-24.04` / 20261004.327.1 | `windows-2025-vs2026` / 20260925.250.1 | 같은 이름·버전(사용자 전달) | `windows_1_set_up_job.log:15-17` |
| 패키지 | numpy 2.0.2 / scipy 1.13.1 / osqp 1.1.1 / torch 2.8.0+cpu | 같음, Python 3.9.13 | — | `env.txt` |
| pytest | `340 passed in 14.48s` | **`1 failed, 339 passed in 35.87s`** | 성공(사용자 전달) | `ubuntu_6_unit_tests.log:26`, `windows_6_unit_tests.log:608` |
| 실패 테스트 | — | `test_improved_i5.py::test_i5_golden_determinism_three_runs` | — | `windows_6_unit_tests.log:325`, `junit.xml`(tests=340 failures=1) |
| time_limit_monitor | solve 14,038회, 발동 0 | solve 14,038회, 발동 0. 실패 테스트에 "발동 0회(시간 제한 원인 아님)"으로 표시됨 | — | `time_limit_log.json`, `windows_6_unit_tests.log:21-23` |
| golden / 추적 / UML / 안전 수치표 | 일치 | golden 6/6(차이 0), 나머지도 일치 | — | `golden.txt`, `*_check.txt` |

- 테스트 내용(`thesis_v2/tests/test_improved_i5.py:113-122`): `ImprovedMPC(FINAL_COMBO, enable_i5=True, i5_max_iter=1944)`로 paper seed 0을 3회 실행한다. 조향 시계열(`delta_final`)이 3회 **완전히 같아야**(`==`) 통과한다.
- 실패 내용: 두 시계열은 모두 길이 162다. 인덱스 38–145 사이 86개 step이 다르고, 최대 차이는 3.15e-4°다. 처음 다른 값은 인덱스 38의 `-2.174894544892109` vs `-2.175209512130098`이다.
- **같은 커밋·같은 이미지에서 attempt 1은 실패하고 attempt 2는 통과했다. 따라서 이 테스트는 이 환경에서 비결정적이다(확인됨).**
- golden(`check_golden`)은 baseline MPC만 쓰고, baseline에는 time_limit이 없다. 따라서 이 실패와 무관하다(위 "OSQP time_limit 기록"의 마지막 항목).

### OSQP 설정 (확인됨, 코드·실행)

| 항목 | baseline MPC | improved MPC (I5 on) | 근거 |
|---|---|---|---|
| eps_abs / polishing / warm_starting | 1e-4 / False / True | 같음 | `baseline/config.py`, `improved/mpc.py:142-147` |
| max_iter | 4000 | `i5_max_iter`(테스트 1944, 평가 972) | `improved/mpc.py:152`, `improved/config.py:34` |
| time_limit | 없음(OSQP 기본 1e10 s) | **0.045 s** | `improved/mpc.py:153`, `improved/config.py:37` |
| adaptive_rho 관련 | 지정 안 함 | 지정 안 함 | grep(`adaptive_rho` 0건) |
| adaptive_rho 실행값(osqp 1.1.1) | adaptive_rho=1, interval=50, fraction 0.4, tolerance 5.0, check_termination 25, rho 0.1 | 같음 | setup 전후 `prob.settings` 출력(실행) |

**adaptive_rho_interval이 0일 때 시간 기준인가 (확인됨, 소스)** — 아니다. 우리 설정에서 rho 적응 주기는 반복 수 기준이다.
- 근거 1: 설치된 osqp 1.1.1 휠에 들어 있는 codegen 소스 `.venv/lib/site-packages/osqp/codegen/codegen_src`(`version.h`는 "1.0.0". 컴파일된 내장 solver와 같은 소스인지는 확인하지 않았다)
  - `inc/public/osqp_api_constants.h:126-127`: 모드는 `OSQP_ADAPTIVE_RHO_UPDATE_ITERATIONS = 1`, `..._TIME = 2`다. `:133`: 기본값은 ITERATIONS다. `:135`: 기본 interval은 50이다.
  - `src/osqp_api.c:580-590`: ITERATIONS 모드에서 interval이 0이면 `4 × check_termination`(= 100)을 쓴다.
  - `src/osqp_api.c:783-791`: setup 시간의 일부로 정하는 시간 기반 주기는 **TIME 모드일 때만** 쓴다.
  - `src/osqp_api.c:835-837`: 적응 시점은 `iter % interval == 0`이다.
- 근거 2: GitHub `osqp/osqp` 태그 v1.0.0의 `include/public/osqp_api_constants.h`, `src/osqp_api.c`도 같은 내용이다(raw.githubusercontent.com에서 확인).
- 실행값 interval은 50이고 0이 아니다. 따라서 위 "0 → 4×check_termination" 분기도 타지 않는다.

**time_limit 동작과 기록의 빈틈 (확인됨, 소스)**
- `src/osqp_api.c:741-759`: 매 반복 `setup_time 또는 update_time + 경과 시간 ≥ time_limit`이면 TIME_LIMIT_REACHED로 바꾸고 반복을 멈춘다(벽시계 기준).
- `src/osqp_api.c:958-964`: 멈춘 뒤 **근사 종료 판정 `check_termination(solver, 1)`을 한 번 더 한다. 통과하면 상태가 `"solved inaccurate"`가 된다.** 실패할 때만 `"run time limit reached"`로 남는다.
- `improved/mpc.py:408`은 `status == "run time limit reached"`일 때만 `time_limit_hit=True`다. `time_limit_monitor`는 이 값만 읽는다.
  → **time_limit으로 멈췄지만 근사 판정을 통과한 solve는 발동으로 세지 않는다.** attempt 1의 "발동 0회(시간 제한 원인 아님)" 표시는 time_limit을 원인에서 배제하지 못한다.
  이 빈틈은 이번 조사에서 처음 확인했다. 위 "OSQP time_limit 기록"과 run #1의 "발동 0회" 기록도 같은 한계를 갖는다.
- 반복 루프 안의 종료 판정은 정확 판정 `check_termination(solver, 0)`(`:861`, `:930`)뿐이다. 근사 판정 `(…, 1)`은 반복 상한(`:950-955`) 또는 time_limit(`:958-964`)으로 끝난 뒤에만 한다.
  그러므로 "`solved inaccurate`이면서 반복 수 < max_iter"인 solve는 time_limit 정지로 판별할 수 있다(추정 — 위 호출 위치에서 도출했고, 다른 경로는 찾지 못했다).
  이 판별을 실험용 플러그인 [`ci/hidden_time_limit_probe.py`](ci/hidden_time_limit_probe.py)로 만들었다(아래 실험 E).

> **[정정 2026-10-15]** 이 판별(`solved inaccurate` + iter < max_iter)은 절단의 일부만 잡는다. `"solved"`로 보고되는 절단(iter가 check_termination의 배수가 아님, 또는 iter 0)이 빠진다. 지금 제품 판정은 지문 규칙 안 B다(`ci/run6_cause/STATIC_ANALYSIS.md` §3-3과 정정, 위 "OSQP time_limit 기록" 정정 블록).

### 재현 실험 (확인됨, 실행 — 노트북 DESKTOP-MDCKRJS, 논리 코어 22, `.venv` Python 3.9.12, 커밋 4c0c503, thesis_v2 dirty 아님)

> **[정정 2026-10-15] 조건 통제 안 됨, 참고.** 이 실험들은 노트북에서 다른 작업과 함께 돌았다. 같은 "강한 부하"에서도 실패 빈도가 크게 흔들렸다(아래 D1·D2·E). 수치는 원인 판단의 근거로 쓰지 않는다. 원인 판단은 `ci/run6_cause/`의 사전 선언 실험에 기댄다(이 절 첫머리 정정 블록). F는 다시 실행하지 않았다.

변형은 저장소 밖 임시 사본의 `improved/mpc.py`에서 setup 인자만 바꿨다. 저장소의 제품 코드와 테스트는 수정하지 않았다.
스크립트: [`ci/i5_determinism_experiment.py`](ci/i5_determinism_experiment.py)(테스트 본문을 새 프로세스에서 실행), [`ci/i5_determinism_suite_experiment.py`](ci/i5_determinism_suite_experiment.py)(CI와 같은 범위로 전체 suite 실행).
CPU 부하는 논리 코어 수(22)만큼 바쁜 루프 프로세스를 띄워 만들었다.

| # | 형태 | 부하 | 변형 | 실패 시행 / 30 | 비고 | 원자료(`ci/raw/`) |
|---|---|---|---|---|---|---|
| A | 테스트 본문만, 시행마다 새 프로세스 | 없음 / 약함(*) | none·rho_interval_50·adaptive_rho_off·no_time_limit | 모두 0 | | `i5_determinism_laptop.json` |
| B | 같음 | 강함(CPU 100%, AC) | none / rho_interval_50 / no_time_limit / adaptive_rho_off | 0 / 0 / 0 / **1** | adaptive_rho_off는 상한 도달 360회로 solve가 길다. 불일치 시행의 기록된 발동은 0 | `i5_determinism_laptop_cpu_strong.json` |
| C | **전체 suite**(CI와 같은 범위, 한 프로세스) | 없음 / 약함(*) | 원본 | 0 / 0 | | `i5_determinism_suite_laptop.json` |
| D1 | 전체 suite | 강함(100%, AC) | 원본 | 대상 테스트 1, **아무 테스트 실패 15** | | `i5_determinism_suite_laptop_cpu_strong.json` |
| D2 | 전체 suite + time_limit_monitor | 강함(100%, AC) | none | 대상 테스트 **4**, 아무 테스트 실패 **16** | 실패 25건 중 21건은 같은 테스트에서 발동이 기록됨 | `…_cpu_strong_monitor_none.json` |
| D3 | 같음 | 강함(100%, AC) | **no_time_limit** | **0, 0** | 발동 0 | `…_cpu_strong_monitor_no_time_limit.json` |
| E | 전체 suite + monitor + 숨은 발동 판별 | 없음 / 강함(100%, AC) | none | 없음 5회: 0, 정지 0 / 강함 30회: 대상 테스트 0, **아무 테스트 실패 2** | 강함: 환경 요인 정지 9회(기록되는 발동 7 + **숨은 발동 2**). 실패 2건 모두 그 테스트에서 정지가 있었다(기록 1건, **숨은 발동만 1건**). 의도적 발동 테스트(1e-9 s)는 제외 | `…_idle_hidden_probe.json`, `…_cpu_strong_hidden_probe.json` |
| F | 전체 suite + monitor | 강함(100%, AC) | rho_interval_50 | **부분 실행(사용자가 강제 종료, 30회 중 15회 완료)**: 대상 0, 아무 테스트 실패 0 | 기록된 발동 2회(시행 4·8). 숨은 발동 판별 없음. pc_state 기록 없음(JSON을 끝에서 쓰는 구조라 로그에서 옮김) | `…_monitor_rho_interval_50_PARTIAL.json`, `logs/i5suite5_rho50.log` |

(*) 첫 "약한" 부하는 바쁜 루프가 매 반복 공유 잠금을 확인하는 구조라, CPU LoadPercentage가 36%에 그쳤다. 루프를 고친 뒤 100%로 다시 측정했다(`cpu_strong`). JSON의 `pc_state`(CPU 부하, 전원 상태 2 = AC)는 고친 뒤 실행분에만 있다.

- 강한 부하의 전체 suite에서 실패한 테스트는 대상 테스트만이 아니다. 모두 **improved v2 MPC(time_limit 0.045 s)를 두 번 이상 돌려 결과가 같은지 보는 테스트**였다(D2 합계).
  - `test_detector_a_with_gyro_does_not_change_control[0,1,2]`(10)
  - `test_i5_golden_determinism_three_runs`(4)
  - `test_golden_equivalence::test_equivalent_to_improved_v2[…]`(5)
  - `test_i4_recorder_does_not_change_episode`(2)
  - `test_hybrid_recorder_does_not_change_control`(2)
  - `test_p0_matches_observational_runner[True-3201-True]`(1)
  - `test_i4_closed_loop_matches_improved_runner_with_mpc[100]`(1)
- D2 실패 25건 중 4건은 그 테스트에서 기록된 발동이 0이었다. E에서 이 경우를 직접 확인했다. 시행 2의 `test_golden_equivalence::test_equivalent_to_improved_v2[detector-paper-generate_scenario-0]` 실패는 time_limit_monitor 기준으로 발동 0이었다. 그러나 같은 테스트에 "`solved inaccurate`, 반복 수 < max_iter" solve가 1회 있었다(`…_cpu_strong_hidden_probe.json`).
  E의 두 번째 실패(`test_eval_offline.py::test_run_record_decouples_inject_and_assumed_sigma`, D2에는 없던 테스트)는 기록되는 발동이 1회였다.
- 같은 "강한 부하" 조건이라도 실패 빈도는 D1 15/30, D2 16/30, E 2/30으로 크게 달랐다. 부하 프로세스 수와 CPU 100%는 같았지만, 순간 부하(스케줄링, 열·전원 상태)는 통제하지 못했다. 빈도 숫자는 조건 간 대략적 비교로만 쓴다.
  정지가 있었던 테스트 7건 중 5건은 통과했다. 정지가 결과를 바꾸지 않았거나, 비교하는 두 실행이 같은 해를 냈을 수 있다(추정).
- 사용자가 요청한 "adaptive_rho_interval 고정" 변형(rho_interval_50)은 osqp 1.1.1의 실행값과 같은 값이다. B에서는 원본(none)도 0/30이라 차이를 판별할 수 없었다. 그래서 재현되는 전체 suite 형태(F)로 다시 측정하던 중, 15/30회에서 강제 종료됐다. 15회에서 실패는 0이었다. 다만 같은 조건의 원본도 E에서 2/30이었으므로, 15회로는 차이를 판별할 수 없다.

### 원인 (가설 — 확정하지 않음)

> **[정정 2026-10-15] 확정됨.** 가설 (1) time_limit이 원인이다. 가설 (2) adaptive rho는 **틀렸다**(반복 수 기준이고, rho 갱신 수가 모든 조건에서 실행마다 같았다). 아래 "확정하지 못한 것" 세 항목은 run6_cause에서 해소됐다: (2) 배제는 README §1-3, 러너의 실제 절단은 S4(러너 #1 18건·#2 11건, 불일치 전부 동반), 러너 조건은 부하 없는 GitHub 러너에서 직접 재현했다(S4). 근거는 이 절 첫머리 정정 블록과 `ci/run6_cause/README.md` §1.

원인 가설은 두 가지이며 아직 확정하지 않는다. (1) time_limit, (2) adaptive rho.
- (2)에 대해 확인된 것: rho 조정 주기는 osqp 소스상 **반복 수 기준**이다. 시간 기반 모드(ADAPTIVE_RHO_UPDATE_TIME)는 우리 설정에서 쓰이지 않는다(위 소스 근거).
- 따라서 (2)가 원인이려면 다른 경로가 있어야 한다. 아직 배제 실험(F)은 끝나지 않았다.

**가설 (1), 현재 근거가 더 많음: I5의 OSQP `time_limit = 0.045 s`(벽시계 안전망)가 CPU가 붐빌 때 일부 solve를 반복 상한보다 먼저 멈춘다. 그래서 그 solve의 해가 실행마다 달라진다.**
근거:
1. 같은 부하·같은 suite에서 time_limit만 끄면 실패가 16/30에서 0/30이 됐다(D2 vs D3, 확인됨).
2. 실패한 테스트는 모두 time_limit이 있는 improved v2 MPC를 반복 실행해 비교한다. baseline만 쓰는 golden 비교 테스트는 같은 실행들에서 통과했다(확인됨).
3. adaptive_rho는 반복 수 기준이다(소스). 그 자체로는 실행마다 달라질 이유가 없다. F(interval=50 명시)는 15회만 끝나 판별하지 못했다.
4. CI 기록의 "발동 0회"는 위 기록 빈틈 때문에 반증이 되지 않는다(소스). 실제로 노트북에서 "monitor 발동 0, 숨은 정지 1"인 실패가 재현됐다(E 시행 2, 확인됨). attempt 1이 같은 경우였는지는 기록이 없어 알 수 없다.
5. Windows 러너의 단위 테스트 시간은 35.87 s로, run #1(21.64 s)과 같은 run의 ubuntu(14.48 s)보다 길다(확인됨). 이번 실행에서 러너가 느렸을 수 있다. 러너의 CPU 부하 자체는 기록이 없다.

확정하지 못한 것:
- 가설 (2) 배제: F 재실행 필요.
- GitHub 러너에서 실제로 time_limit 정지가 있었는지는 attempt 1 기록만으로 알 수 없다(위 빈틈).
- 노트북의 인위적 강한 부하가 러너 조건과 같다는 근거도 없다.

### 영향

> **[정정 2026-10-15]** 저장 평가 영향은 `ci/run6_cause/S5_IMPACT.md` §1로 정리됐다: eval 2회차 v2와 anomaly closed-loop eval은 첫 solve를 뺀 모든 solve가 45 ms 미만이라 절단이 불가능했다. S3 격자와 i4_student_v2는 solve 시간 기록이 없어 점검하지 못했다. anomaly 저장 평가는 지문 판정 후 `--check`로도 전체 일치했다(COMMIT2_VERIFY §8). a의 2026-10-03 P0 불일치는 anomaly DESIGN.md에 "유력한 후보, 추정, 확정 아님"으로 보충했다(커밋 6971d64). mutation(b)은 kill 16개 재확인(S5_MUTANT_RESULT, 아래 fsm:003/005/006 포함 16/16 kill 유지)과 2차 실행 후 time_limit kill 재확인(127개 모두 유지, mutation RESULTS.md)으로 정리됐다.

**a. 2026-10-03 노트북 dev `--check` P0 불일치(`thesis_v2/anomaly/DESIGN.md` §24-1)와 원인이 같을 가능성 — 가설**
- MPC 설정은 같은 경로다(확인됨, 코드). 폐루프 평가의 `V2_MPC_FLAGS`(`thesis_v2/anomaly/config.py:13-15`)는 I1·I1b·I2·I3(narrow) + I5(max_iter 972, time_limit 0.045 s)다.
  이 테스트와 같은 `ImprovedMPC` setup 경로를 쓰고, 다른 것은 max_iter(테스트 1944)뿐이다. adaptive_rho 관련 설정은 둘 다 기본값이다.
- §24-1은 "부하에서 발동 0, 최대 42.2 ms"를 근거로 time_limit 가설을 확정하지 못했다. 그 "발동 0"도 같은 기록 빈틈을 갖는다.
  - 다만 §24-1 표의 최대 solve 시간 42.2 ms는 `compute_time_ms`다. 측정 구간(`improved/mpc.py:346` 시작 → `:453`/`:464`)은 OSQP update와 solve를 모두 포함한다.
  - 따라서 OSQP 내부 시간이 45 ms 이상인 solve는 그 계측에 없었다고 본다(추정). 즉 §24-1의 재현 실험(1,100 에피소드)에서는 숨은 발동도 없었다.
- 정리하면 "원인이 같다"는 가설은 이번 결과로 **더 그럴듯해졌지만 확정되지 않는다.** 2026-10-03 불일치 실행의 solve 기록이 남아 있지 않다(§24-1: 비교 직후 임시 파일을 삭제함).
- 저장된 평가에는 time_limit으로 끊긴 계산이 없었다고 본다(추정 — 측정값 자체는 확인됨, "없었다"는 결론은 아래 추론). OSQP 내부 시간은 `compute_time_ms`를 넘지 않으므로, 최대 solve 시간이 45 ms 미만인 평가에는 숨은 발동도 없다.
  - improved v2 eval(`results/eval_v2/20260924_214446_DESKTOP-MDCKRJS`): v2의 최대 `mpc_solve_ms_max`가 34.96 ms다.
  - 폐루프 평가(`results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval/diag_timing.csv`, 6,600 에피소드): 최대 `max_solve_ms`가 6.375 ms다.

**b. mutation 1차 실행(`mutation/raw/run_before.json`)**
- **L2에서 이 테스트(`test_i5_golden_determinism_three_runs`)가 처음 실패 테스트였던 변이는 0개다**(확인됨, 원자료).
  L2에서 잡힌 49개의 처음 실패 테스트는 `test_improved_equivalence` 45, `test_i4_student` 3, `test_summary` 1이다.
- 부하가 큰 상태에서는 `test_i4_student.py`의 동일성 테스트(`test_i4_recorder_does_not_change_episode`, `test_i4_closed_loop_matches_improved_runner_with_mpc`)도 실패했다(D2, 확인됨).
  1차 실행에서 L2 처음 실패가 `test_i4_student.py`인 변이는 3개이며, **부하 때문에 잘못 잡혔을 가능성을 재판정 대상으로 둔다**(아래 "다음 작업").

  | 변이 | 내용 | 상태 | 처음 실패 테스트 | 부하 민감 여부 |
  |---|---|---|---|---|
  | fsm:003 | `fsm.py:40` `in` → `not in` | `killed`(단언) | `test_req_stu_02_feature_order_and_fallback` | MPC를 쓰지 않는 특징 벡터 단위 테스트(`test_i4_student.py:33-40`). 부하 실험에서 실패한 적 없음 |
  | fsm:005 | `fsm.py:41` `0.0` → `None` | `killed_exception` | `test_i4_recorder_does_not_change_episode` | D2에서 실패한 적 있는 테스트. 다만 상태가 예외(수치 불일치 아님) |
  | fsm:006 | `fsm.py:42` `config.W` → `None` | `killed_exception` | `test_req_stu_02_feature_order_and_fallback` | fsm:003과 같은 테스트 |

  - 처음 실패 테스트와 상태를 보면 3개 모두 부하와 무관하게 잡혔을 가능성이 높다고 본다(추정). 그래도 확인은 재실행으로 한다.
- D2에서 부하에 민감했던 다른 테스트로 넓혀서 본 결과(확인됨, 원자료)
  - L2 `fsm:005`: `test_i4_recorder_does_not_change_episode`, `killed_exception`
  - L1 detector_a 51개: `test_detector_a_with_gyro_does_not_change_control[0]`, 모두 `killed_exception`
  - L1 closed_loop 13개: `test_p0_matches_observational_runner`, `killed` 9 + `killed_exception` 4
- 해석(추정)
  - `killed_exception`은 수치 불일치(AssertionError)가 아니라 변이가 일으킨 예외다. time_limit 비결정과는 무관하다고 본다.
  - 단언 실패 9개(closed_loop:002, 004–008, 013, 015, 027)는 모두 `first_alarm_step` 기록 로직(`closed_loop.py:171-197`)을 바꾼 변이다. 테스트가 `first_alarm_step` 일치를 직접 단언하므로 결정론적으로 잡혔을 것으로 본다(코드 읽기).
  - 1차 실행 당시 PC 부하는 시작 14%, 끝 6%였다(`run_before.json`의 `pc_load_before/after`). 위 A·C의 약한 부하(36%)에서도 실패는 0/30이었다.
- **2차 실행 위험**: L2에는 이 테스트와 위 동등성 테스트들이 들어 있다. 부하가 큰 상태에서 돌리면, 생존해야 할 변이가 비결정 실패 때문에 "잡힘"으로 잘못 기록될 수 있다.
  깨끗한 사본 사전 확인(PREREGISTRATION 50행)에서 이런 실패가 나면 실행 전체가 중단된다.

### 대응 선택지 (결정: 사용자 — 이 문서는 선택지와 영향만 기록한다)

> **[정정 2026-10-15] 결정됨.** 아래 ①②③ 표는 노트북 작성 당시의 비교다. 최종 결정은 `ci/run6_cause/README.md` §4의 선택지 번호로 **2 + 5 + 0**이다(아래 ②의 "time_limit을 끈 인스턴스로 비교"에 해당하는 fixture + 감시 정정 + 문서 정정). 아래 "선택지와 별개로 권하는 보완" 첫 항목(감시가 숨은 발동도 세기)은 선택지 5로 반영됐다. 다만 규칙은 여기 적힌 것보다 넓은 안 B다.

모든 선택지에서 공통으로, **저장된 평가 결과의 값은 바뀌지 않는다고 본다**(추정, 위 "영향 a").
improved v2 eval의 최대 solve는 34.96 ms이고 폐루프 평가의 최대 solve는 6.375 ms로, 모두 45 ms 미만이다. 따라서 그 평가들에서는 time_limit이 한 번도 작동할 수 없었다.
- 같은 이유로 DESIGN_IMPROVED_V2 §2의 사전 판정 "time_limit_hit 0건"은 숨은 발동까지 포함해도 성립했다고 본다(추정).
- 다만 그 판정을 낼 때 쓴 카운터 자체는 숨은 발동을 세지 않았다. 이 사실은 어느 선택지에서든 기록해야 한다.

| | ① 설정 수정(제품 변경) | ② 테스트 판정 변경 | ③ 한계로 기록 |
|---|---|---|---|
| 내용 | `improved/mpc.py`/`config.py`의 I5 `time_limit`을 없애거나 크게 올림(예: 1 s) | 비교 테스트가 time_limit 정지와 무관한 결정론만 보게 함. 예: 테스트 안에서 `time_limit`을 끈 인스턴스로 비교하거나, 정지(기록 + 숨은 발동)가 있었으면 그 시행을 판정에서 제외 | 코드·테스트는 그대로 두고 비결정성을 알려진 한계로 기록하고 운용으로 대응 |
| 실험 근거 | D3: time_limit을 없애면 강한 부하에서도 0/30. 크게 올리는 안은 측정하지 않음(확률만 줄 것으로 추정) | — | — |
| 기존 평가 결과 | 값은 같을 것(추정, 위 근거). 그러나 repro/docs/WORK_RULES.md "eval 후 코드 수정 = 새 반복" 규칙에 해당한다. 사유와 함께 새 반복으로 기록하고, 이전 eval 결과는 그대로 남긴다. 같은 값인지 확인하려면 재계산(`--check`류)이 필요하다. 그 재계산을 할지는 사용자 결정. `anomaly-cl-freeze` 태그는 이전 코드를 가리킨 채로 남는다 | 영향 없음(제품 코드 무변경) | 영향 없음 |
| I5 설계·사전 선언 | DESIGN_IMPROVED_V2 §1-0("time_limit은 안전망")·§1-4·§2(time_limit_hit 지표)가 바뀐다. 없애면 "호스트가 극단적으로 느릴 때의 최후 방어선"이 사라진다. `test_i5_time_limit_safety_net_reachable`도 수정 필요 | §1-5 완료 조건 "I5 on 3회 완전 동일"의 범위를 "time_limit 정지가 없을 때"로 좁힌다. §1-4는 이미 "발동하면 그 스텝은 결정론이 깨진다"고 적고 있어 그와는 맞는다. 다만 결정론 주장 자체는 약해진다(약화로 명시 기록) | §1-5 주장에 "CPU 부하로 time_limit이 작동하면 깨질 수 있음(관찰됨: CI run #6, 노트북 강한 부하)"을 단서로 추가 |
| 다른 테스트 | 같은 원인으로 실패한 동등성 테스트 7종(위 D2·E 목록)도 함께 해소될 것(D3, 추정) | 대상 테스트 하나만 바꾸면 나머지 7종은 여전히 비결정. 일관되게 바꾸려면 7종 모두 판정을 손봐야 한다 | 8종 모두 그대로. CI 실패 시 재실행 판단이 필요 |
| mutation 사전 선언(PREREGISTRATION) | `improved/mpc.py`는 변이 대상이 아니다. 하지만 L2 실행 코드가 1차와 달라진다. 2차 실행 전에 "1차와의 차이"로 RESULTS에 기록 | 기존 테스트의 판정이 바뀐다(2차 실행의 L2가 1차와 달라짐). 2차 실행 전에 변경 사유와 날짜를 RESULTS/PREREGISTRATION에 기록. 1차에서 이 8종이 단언 실패로 처음 잡은 변이는 closed_loop 9개뿐이다(위 b) | 2차 실행 **전에** 운용 규칙을 사전 선언으로 추가(아래). 결과를 보기 전 결정이므로 결과 기반 변경이 아니다 |
| CI | 실패 원인 제거 | 실패 원인 중 해당 테스트 판정만 제거 | 비결정 실패가 계속 날 수 있음. Windows 러너가 느린 실행에서 다시 나올 것으로 추정 |

**선택지와 별개로 권하는 보완(제품·테스트 아님, 사용자 결정)**
- `time_limit_monitor`가 "`solved inaccurate` + 반복 수 < max_iter"도 세게 하기(`ci/hidden_time_limit_probe.py`와 같은 판별). 지금 "발동 0회(시간 제한 원인 아님)" 문구는 틀릴 수 있다(E 시행 2에서 확인됨).
- `safety/FMEA.md` 10행과 `thesis_v2/anomaly/DESIGN.md` §24-1에 이 조사를 상호 참조. §24-1의 원인은 여전히 "미확정"으로 둔다.

**③을 고를 때 mutation 2차 실행 완화안(실행 전 사전 선언용 초안)**
1. 실행 조건: 노트북 AC·최고 성능 모드, 실행 중 같은 PC에서 다른 작업 없음(DESIGN §24-2와 같은 규칙). 실행 전후 부하는 이미 기록됨(PREREGISTRATION 52행).
2. 대상: L2 또는 L1에서 **단언 실패(`killed`)**로 처음 잡혔고, 그 처음 실패 테스트가 위 부하 민감 테스트 8종 중 하나인 변이.
   이런 변이는 같은 변이를 조용한 상태에서 다시 실행한다. 판정이 달라지면 둘 다 기록하고 "비결정 의심"으로 따로 센다.
3. 깨끗한 사본 사전 확인이 이 8종 중 하나로 실패하면 1회 재시도한다. 재시도도 실패하면 중단한다(PREREGISTRATION 50행의 중단 규칙은 그대로).

### 다음 작업 (2026-10-13 기준, 순서대로)

> **[정정 2026-10-15] 상태:**
> 1. F 재실행 — **하지 않음.** run6_cause에서 조건 B(interval 50 고정)가 원래 설정과 같음을 확인해 두지 않았다(README §1).
> 2. 원인 확정 — **완료**(time_limit 절단, 가설 (2)는 틀림).
> 3. 대응 선택지 결정 — **완료**(2 + 5 + 0, 2026-10-14).
> 4. L2 kill 3개 재판정 — **완료.** fsm:003/005/006 모두 orig·A 5/5 실패, kill 유지(`ci/run6_cause/S5_MUTANT_RESULT.md`).
> 5. 2차 mutation 실행 — **완료**(2026-10-14, 커밋 6971d64, mutation RESULTS.md "2차 실행").
> 6. 커밋 — 조사 기록은 7bd9363(노트북), run6_cause 조사·대응은 97d1ed6·30a3a22·6971d64·ac5f01b로 커밋됐다.

2026-10-13 저녁, 사용자가 노트북을 끄려고 실행 중인 python 프로세스를 강제 종료했다. 이때 중단된 실험은 F 하나다. A–E는 모두 끝났고 원자료 JSON이 `ci/raw/`에 저장되어 있다. 콘솔 로그는 `ci/raw/logs/`에 복사했다.

1. **F 재실행**(adaptive_rho_interval=50, 강한 부하, 전체 suite 30회, 약 35분):
   `python docs/verification/ci/i5_determinism_suite_experiment.py --trials 30 --loads cpu_strong --variant rho_interval_50 --hidden-probe --out docs/verification/ci/raw/i5_determinism_suite_laptop_cpu_strong_monitor_rho_interval_50.json`
   - 원본(none)도 같은 조건에서 2/30–16/30으로 흔들렸다. 그래서 같은 세션에서 none과 번갈아 돌리는 등 비교 설계를 실행 전에 정한다.
2. **원인 확정**: 가설 (1) time_limit, (2) adaptive rho. 확정 전까지 둘 다 "가설"로 둔다.
3. **대응 선택지 결정(사용자)**: 위 ①·②·③과 보완안.
4. **L2 kill 3개 재판정**: fsm:003, fsm:005, fsm:006. 조용한 노트북에서 해당 변이만 다시 실행하고, 결과를 `mutation/RESULTS.md`에 기록한다.
5. **2차 mutation 실행**: 3의 결정과 4의 결과를 반영한 사전 선언 추가 후 실행.
   `python docs/verification/mutation/mutate.py run --out docs/verification/mutation/raw/run_after.json`(약 50–60분)
6. **커밋**(사용자).

## 알려진 위험 (추정)

- 고정 이미지에서도 이미지 버전 갱신으로 시스템 라이브러리가 바뀔 수 있다. 수치 패키지는 버전을 고정했으므로 영향은 작을 것으로 추정하지만, golden FAIL이 나면 Set up job의 이미지 버전부터 비교한다.
- Node.js 20 지원 종료 경고(run #1)는 결과에 영향이 없었다. 하지만 `actions/*@v4·v5`를 Node.js 24 대응 버전으로 올려야 할 수 있다(이번 변경 범위 밖).
- 라벨 고정은 **이미지 이름**을 고정하지 않는다. `windows-2025` 라벨이 어떤 이미지(예: VS 2022 판/VS 2026 판)를 가리킬지, 이미지 버전을 언제 올릴지는 GitHub가 바꿀 수 있다.
  그래서 실행마다 Set up job의 Runner Image 이름·버전을 확인해 run #1·#2와 비교한다.
