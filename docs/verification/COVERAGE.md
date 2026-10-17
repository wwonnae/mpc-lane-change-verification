# 구문·분기 커버리지 (thesis_v2 baseline / improved / anomaly)

측정 2026-10-13, PC 3층PC109, `.venv` Python 3.9.13, coverage 7.10.7(branch 모드), pytest 8.4.2, 기준 커밋 fc90e7f + 이번 작업 파일(작업 트리).
제어·탐지 코드는 바꾸지 않았다. 표의 모든 수치는 `coverage/COVERAGE_TABLES.md`(자동 생성)에서 왔다.

## 핵심

| 범위 | 구문 | 분기 |
|---|---|---|
| 라이브러리 모듈 합계(33개 — 제어기·시뮬레이터·탐지기 본체) | 2364/2581 = **91.6%** | 516/622 = **83.0%** |
| 실행 스크립트 합계(22개 — 평가·학습·벤치마크 CLI) | 1043/3140 = 33.2% | 262/762 = 34.4% |
| 전체(55개) | 3407/5721 = 59.6% | 778/1384 = 56.2% |
| `baseline/fsm.py` | 47/47 = 100% | 22/22 = 100% |
| `baseline/mpc.py` | 170/170 = 100% | 36/36 = 100% |
| `improved/mpc.py` | 329/329 = 100% | 78/80 = 97.5% |

- 테스트: `thesis_v2/tests` + `thesis_v2/anomaly/tests` = **295 passed**(기존 292 + 이번 MC/DC 보강 3), 0 skipped.
- `fsm.py`는 MC/DC 보강 **전에도** 구문·분기 100%였다. 그런데도 MC/DC 쌍 3개가 비어 있었다(`MCDC_FSM.md`).
  분기 100%라고 해서 복합 조건의 각 조건이 결과에 독립적으로 영향을 준다는 것까지 확인되지는 않는다.
- 실행 스크립트는 단위 테스트 대상이 아니다. 사용자가 직접 실행해 결과 폴더를 만들고, 그 결과는 `--check` 재계산과
  golden으로 따로 확인해 왔다(README 상태 표). 그래서 라이브러리와 분리해서 보고한다. 분류 기준은
  `if __name__ == "__main__"`이 있는지 여부다(`make_coverage_tables.py`).

## 측정 범위와 방법

- 대상(`coverage/.coveragerc`): `thesis_v2/` 전체. 제외: `thesis_v2/tests/*`, `thesis_v2/anomaly/tests/*`, `thesis_v2/results/*`.
  `tests/compare/`(옛 코드 비교)는 tests 아래라서 대상이 아니다. 루트의 원본 코드(제출 당시)도 대상이 아니다.
- 커버리지 수치는 `thesis_v2/` 안의 코드만 센다. 테스트가 임포트하는 외부 라이브러리(OSQP, torch 등)는 세지 않는다.
- 재생성(저장소 루트):
  ```powershell
  $env:COVERAGE_FILE="$env:TEMP\.coverage"
  .\.venv\Scripts\python -m coverage run --rcfile=docs/verification/coverage/.coveragerc -m pytest thesis_v2/tests thesis_v2/anomaly/tests -q
  .\.venv\Scripts\python -m coverage json --rcfile=docs/verification/coverage/.coveragerc -o $env:TEMP\coverage.json
  .\.venv\Scripts\python docs/verification/coverage/make_coverage_tables.py $env:TEMP\coverage.json docs/verification/coverage/COVERAGE_TABLES.md
  ```
  `coverage.json`(약 1.4 MB, 행 단위 기록)은 저장소에 넣지 않았다.

## 미커버 분기 — 라이브러리 모듈

전체 목록(`파일: 행A→행B`)은 `coverage/COVERAGE_TABLES.md`의 "미커버 분기 목록"에 있다(라이브러리 106개).
아래 분류는 해당 행의 코드를 읽고 내린 판단이다(**추정** — 각 분기를 일부러 실행해 확인하지는 않았다). 분류하지 못한 분기는 그대로 둔다.

| 분류 | 예(행) | 의미 |
|---|---|---|
| 정상 주행에서 일어나지 않는 이상·방어 경로 | `baseline/runner.py:151`(solver 실패), `:153`(fallback), `:166`·`:168`(clip 종류), `:174`·`:189`(허용오차 위반 기록), `:239`(MAX_STEPS 시간 초과), `improved/runner.py:188~202`(solver 실패·fallback·warm-start shift·time limit), `:209~226`(제약 위반량 기록), `baseline/collision.py:38`(퇴화 축), `baseline/world.py:51·53`(초기 위치 재추출 1000회 소진) | 테스트 시나리오(paper·left_obstacle seed 0~2 등)가 정상이라 이 분기에 도달하지 않는다. 기록·안전 경로라서 **단위 결함 주입 테스트 후보**다(이번 범위 밖, 추가하지 않음) |
| 환경 의존 | `baseline/envinfo.py:31~95`(Windows 전원 API 실패·성공 분기), `baseline/summary.py:193~200`(공식 측정 호스트 여부), `anomaly/common.py:81~98`(환경 기록) | 실행하는 PC의 상태에 따라 갈린다. 테스트 PC는 공식 호스트가 아니다 |
| 학습·오프라인 함수 | `anomaly/ae_model.py:51~84`(오토인코더 학습 루프) | 테스트는 학습 대신 작은 모델 state_dict를 쓴다(`test_eval_offline.py:91~114`) |
| 설정 변형(ablation 플래그) | `improved/mpc.py:379`(I2 `narrow` 변형), `:440`(I1 꺼짐) | 최종 조합(v2) 외의 플래그 조합 |

- `improved/runner.py:198`(`solver_status == "run time limit reached"`)은 전체 테스트 중 한 번도 실행되지 않았다(확인됨). 이 PC에서
  improved MPC solve 13,106회 동안 기본 설정의 time_limit 발동은 0회였다(`CI.md`, time_limit_monitor 로그). 테스트가 설정값을 1e-9로
  바꿔 일부러 발동시키는 1회(`test_improved_i5.py::test_i5_time_limit_safety_net_reachable`)는 MPC 단위에서 직접 호출하므로 runner 분기를 지나지 않는다.

## ISO 26262-6과의 개념 대응 (준수 주장 아님)

ISO 26262-6은 소프트웨어 단위 수준의 구조적 커버리지 지표로 구문(statement)·분기(branch)·MC/DC를 두고, ASIL에 따라 권장 정도를 다르게 둔다
(일반적으로 알려진 내용이다. 이 저장소에서 표준 원문의 표·권장 등급과 대조하지는 않았다). 이 문서는 같은 **개념**의 지표를 Python 코드에 적용해
측정한 기록일 뿐이다. 이 저장소는 안전 목표, ASIL 할당, 도구 적격성 확인(coverage.py), 커버리지 목표치 사전 설정 같은 표준 절차를 수행하지 않았으므로
ISO 26262 준수를 주장하지 않는다. 특히 이번 커버리지 목표치는 **사전에 정하지 않았다**. 따라서 위 %는 판정이 아니라 현황이다.
