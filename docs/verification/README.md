# 검증 산출물 (1단계: 커버리지 · MC/DC · CI)

기존 재구현(`thesis_v2/`)의 테스트를 현업 검증 산출물 형태로 정리한 것이다. **제어·탐지 로직과 평가 결과는 바꾸지 않았다.**
추가한 것은 다음뿐이다.
- 테스트 3개(MC/DC 보강)
- 측정 도구(커버리지 설정, MC/DC 기록 플러그인, time_limit 기록 플러그인)
- CI 워크플로
- 문서

작업 2026-10-13, PC 3층PC109, 기준 커밋 fc90e7f.

| 문서 | 내용 | 상태 |
|---|---|---|
| [COVERAGE.md](COVERAGE.md) | 구문·분기 커버리지(모듈별), 미커버 분기 분류. 표 원본: [coverage/COVERAGE_TABLES.md](coverage/COVERAGE_TABLES.md) | 확인됨(실행). 미커버 분기 분류는 추정 |
| [MCDC_FSM.md](MCDC_FSM.md) | `baseline/fsm.py` 전이 결정 5개·조건 14개의 unique-cause MC/DC. 표: [mcdc/MCDC_TABLES.md](mcdc/MCDC_TABLES.md) | 확인됨(실행): 기존 11/14 → 보강 후 14/14 |
| [aspice/README.md](aspice/README.md) | 2단계: ASPICE 4.0 SWE.1~6 관점 매핑(준수·평가 아님), 양방향 추적 매트릭스(자동 생성, `--check`), Mermaid UML 3종(코드 대조) | 확인됨(실행): `--check`·`check_uml.py` 일치. REQ 59개 중 테스트 없는 REQ 15개(2026-10-13 mutation 보강으로 REQ-EVAL-03에 테스트가 생겨 16 → 15), REQ 없는 테스트 함수 166개(mutation 보강 20개 포함) |
| [safety/README.md](safety/README.md) | 3단계: FMEA(주입 고장 9종 + 비주입 2, O·RPN 미적용)와 FTTI·FDTI·FRTI 근사 — 저장된 평가 결과만 분석, 표준 준수·안전 인증 아님 | 확인됨(실행): `make_safety_tables.py --check` 일치, summary.json 교차 대조 통과 |
| [mutation/README.md](mutation/README.md) | 4단계: 직접 만든 AST 변이기로 mutation testing(fsm·detector_a·closed_loop 경보/정책·baseline MPC, 변이 600개), LLM 보조 테스트 보강 | B단계 완료(확인됨, 실행·파일): 1차 600개 중 471 잡힘(원점수 78.5%, 등가 제외 83.1%), 노트북 재확인 129/129 일치, 생존 분류 확정, LLM 보조 테스트 45개 수락, 2차 실행 531 잡힘(원점수 88.5%, 등가 제외 93.7%, 보강 대상 60개 모두 잡음). 결과: [mutation/RESULTS.md](mutation/RESULTS.md) |
| [CI.md](CI.md) | GitHub Actions(ubuntu·windows × Python 3.9), time_limit 기록, golden 실패 판정 절차, 첫 실행 결과 | 확인됨(GitHub run #1, 커밋 b3d2ead): ubuntu·windows 모두 295 passed, golden 6/6. run #2(커밋 45c944e, 이미지 고정, 두 job 성공 — 사용자 전달): 두 job 모두 run #1과 같은 이미지(windows `windows-2025-vs2026` 20260925.250.1, ubuntu `ubuntu-24.04` 20261004.327.1) |

## 숫자 요약 (확인됨, 실행 — Windows, Python 3.9.13)

- 테스트 **295 passed**, 0 skipped(기존 292 + MC/DC 3). golden **6/6 PASS**(조향각 최대 차이 0 rad).
  - 이후 mutation 보강(closed_loop 17·detector_a 14·fsm 4·MPC 10 = 45개, 2026-10-13)으로 **340 passed**(노트북 DESKTOP-MDCKRJS, `.venv` Python 3.9.12, 확인됨·실행). 위 커버리지·CI 수치는 295개 시점의 측정이다.
  - 현재: run #6 대응(2026-10-14, 결정론 테스트 time_limit off fixture·지문 규칙 테스트 19개 추가)으로 **359 passed**(이 PC 3층PC109, `.venv` Python 3.9.13, 확인됨·실행, `docs/verification/ci/run6_cause/COMMIT2_VERIFY.md`).
- 커버리지(라이브러리 모듈 33개): 구문 **91.6%**, 분기 **83.0%**. `fsm.py`·`baseline/mpc.py`는 구문·분기 모두 100%.
- MC/DC(`fsm.py`): `fsm.py`는 이미 분기 100%였지만 MC/DC 쌍은 11/14였다. 테스트 3개를 추가해 14/14가 됐다.
  D3의 `cooldown_ok`는 도달 가능한 상태에서 다른 조건과 결합되어 있어(관찰), 독립 영향을 보일 수 없다.
- improved MPC의 time_limit: 기본 설정에서 발동 0회 / solve 13,106회.

## 현업 검증 개념과의 대응 (개념 대응만 — 표준 준수 주장 아님)

| 개념 | 이 저장소에서 대응하는 것 | 하지 않은 것 |
|---|---|---|
| ISO 26262-6 단위 검증 — 구조적 커버리지(구문·분기·MC/DC) | `COVERAGE.md`, `MCDC_FSM.md` | ASIL 할당, 커버리지 목표치 사전 설정, 도구 적격성 확인(coverage.py, 자체 MC/DC 플러그인) |
| ISO 26262-6 / ASPICE SWE.4 — 요구사항 기반 단위 테스트, 양방향 추적성 | REQ ID별 테스트 + `thesis_v2/tests/TRACEABILITY.md` | 독립 검증자에 의한 리뷰, 프로세스 평가 |
| ASPICE SWE.5·SWE.6 성격의 회귀 시험 / SIL 회귀 | golden 폐루프 비교(`check_golden`, 시나리오 6개, 1e-3 rad) | HIL, 실차 |
| 지속적 통합 | `.github/workflows/ci.yml` | 브랜치 보호 규칙 등 저장소 설정 |

"ISO 26262", "ASPICE"는 개념 설명을 위한 대응일 뿐이다. 이 저장소는 어떤 표준의 준수나 평가도 주장하지 않는다.
표준 내용 설명은 일반적으로 알려진 수준이며, 표준 원문과 대조하지 않았다.

## 파일

```
.github/workflows/ci.yml                    CI 워크플로
docs/verification/
  README.md  COVERAGE.md  MCDC_FSM.md  CI.md
  coverage/.coveragerc                      커버리지 설정(branch=True, 대상·제외)
  coverage/make_coverage_tables.py          coverage.json → COVERAGE_TABLES.md
  coverage/COVERAGE_TABLES.md               자동 생성 표
  mcdc/mcdc_trace.py                        MC/DC 기록 pytest 플러그인
  mcdc/make_mcdc_tables.py                  JSON → MCDC_TABLES.md
  mcdc/mcdc_before_existing_tests.json      측정 원자료(기존 테스트만)
  mcdc/mcdc_after_added_tests.json          측정 원자료(보강 후)
  mcdc/MCDC_TABLES.md                       자동 생성 표
  ci/time_limit_monitor.py                  time_limit 발동 기록 pytest 플러그인
  aspice/README.md  SWE_MAPPING.md  UML.md  2단계 문서
  aspice/make_trace_matrix.py               추적 매트릭스 생성기(--check)
  aspice/TRACE_MATRIX.md, trace_matrix.json 자동 생성 매트릭스
  aspice/check_uml.py                       UML ↔ 코드 대조
  safety/README.md  FMEA.md  FTTI.md          3단계 문서
  safety/make_safety_tables.py              FMEA·FTTI 수치 생성기(--check)
  safety/SAFETY_TABLES.md, safety_numbers.json  자동 생성 수치표
thesis_v2/tests/test_fsm_mcdc.py            MC/DC 보강 테스트 3개
thesis_v2/tests/TRACEABILITY.md             REQ-FSM-02a·02d·02e 행에 테스트 이름 추가
```

환경 재구성(이 PC): `py -3.9 -m venv .venv` → `PYTHONUTF8=1`로 `pip install -r thesis_v2/requirements-py39.txt -r thesis_v2/anomaly/requirements-anomaly.txt`
→ `pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu` → `pip install coverage==7.10.7`(coverage 7.10.x가 Python 3.9를 지원하는 마지막 계열이다.
7.11.0은 Python 3.9용 배포가 없음을 pip로 확인).
