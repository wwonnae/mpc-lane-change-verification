# ASPICE SWE.1–SWE.6 관점 매핑

> **이 문서는 ASPICE 준수 주장이나 ASPICE 평가(assessment)가 아니다.** 이미 있는 산출물(명세, 결정표, 코드, 테스트, 평가 결과)을
> **ASPICE SWE 프로세스 관점에서 역으로 분류·매핑**한 것이다. 프로세스를 ASPICE에 맞춰 수행한 기록이 아니며, 능력 수준(capability level)도 평가하지 않았다.

## 기준 버전과 프로세스 이름

기준은 **Automotive SPICE 4.0**이다. 프로세스 ID와 이름은 아래 UL Solutions 공개 페이지에서 확인했다.
SWE.5·SWE.6 페이지에는 "Automotive SPICE® v4.0"이 명시되어 있다. SWE.1–SWE.4 페이지에는 버전 표기가 없다.
VDA QMC가 발행한 PAM 4.0 원문은 직접 열람하지 못했으므로, 이름은 이 2차 출처 기준이다(2026-10-13 확인).

| ID | 프로세스 이름 (ASPICE 4.0) | 출처 |
|---|---|---|
| SWE.1 | Software Requirements Analysis | [UL — Process SWE.1](https://www.ul.com/sis/resources/process-swe-1) |
| SWE.2 | Software Architectural Design | [UL — Process SWE.2](https://www.ul.com/sis/resources/process-swe-2) |
| SWE.3 | Software Detailed Design and Unit Construction | [UL — Process SWE.3](https://www.ul.com/sis/resources/process-swe-3) |
| SWE.4 | Software Unit Verification | [UL — Process SWE.4](https://www.ul.com/sis/resources/process-swe-4) |
| SWE.5 | Software Component Verification and Integration Verification | [UL — Process SWE.5](https://www.ul.com/sis/resources/process-swe-5) (v4.0 명시) |
| SWE.6 | Software Verification | [UL — Process SWE.6](https://ul.com/sis/resources/process-swe-6) (v4.0 명시) |

## 매핑표

"근거"는 저장소 파일·행이다. "갭"은 ASPICE 관점에서 빠졌거나 약한 부분이다. 확인하지 못한 내용은 **추정**으로 표시했다.
추적 수치는 `TRACE_MATRIX.md`(자동 생성)에서 왔다.

| 프로세스 | 대응 산출물 | 근거 | 갭 |
|---|---|---|---|
| **SWE.1** Software Requirements Analysis | 제출본 논문을 명세로 삼은 요구사항 57개(REQ ID, [정합]/[해석]/[공백]/[개정] 태그). 모호·공백 항목의 결정표. 실현 불가 값의 사전 계산 | `repro/docs/SPEC.md:18-126`(표), `repro/docs/SETTINGS_DECISION.md:12-658`(§1–§20), `repro/docs/FEASIBILITY_CHECK.md`, 작업 규칙 `repro/docs/WORK_RULES.md:39-41`(1단계 사실 확정 → 2단계-A 명세 → 2단계-B 구현) | ① **요구사항이 코드보다 나중에 쓰였다**: 원본 코드(2025-12, 제출 당시)를 보고 논문에서 역으로 뽑은 명세다. 재구현 코드와는 같은 커밋에 처음 들어갔다(`SPEC.md`·`baseline/fsm.py` 모두 27d8973, 2026-09-17). 그래서 "명세가 먼저"였다는 것은 repro/docs/WORK_RULES.md의 절차 규칙으로만 뒷받침되고, git으로는 입증할 수 없다. ② REQ마다 검증 방법·합격 기준을 적는 열이 없다(`SPEC.md:20` 열 = ID·내용·근거·태그). ③ 정의 문제: REQ-SIM-07은 코드(`baseline/summary.py:40`)와 `MEASURE_PLAN.md:102,113`, `ROBUSTNESS_PLAN.md:6`에서 인용되지만 정의 행이 없다. git 전체 이력에서 `SPEC.md`에 정의된 적도 없다(`git log -S "REQ-SIM-07" -- repro/docs/SPEC.md` 결과 없음, 처음 인용된 커밋 27d8973). REQ-FSM-03b는 SPEC 표 밖, `SETTINGS_DECISION.md:329`(§13)에만 정의되어 있다. ④ 이상탐지 확장에는 REQ ID가 없다(DESIGN의 사전 선언만 있음). ⑤ 요구사항에 대한 독립 리뷰 기록이 없다 |
| **SWE.2** Software Architectural Design | baseline 모듈 구조·스텝 실행 순서·기록 스키마. 개선판 설계(I1–I5, ablation 플래그). Student 재학습 설계. 이상탐지 삽입 구조. 이번에 역으로 그린 UML 3종 | `repro/docs/DESIGN_BASELINE.md:8`(§1 모듈 구조), `:32`(§2 스텝 실행 순서), `:94`(§3 기록 스키마), `repro/docs/DESIGN_IMPROVED.md:19`(§1 개선 항목), `:188`(§3 Ablation), `repro/docs/DESIGN_IMPROVED_V2.md`, `repro/docs/DESIGN_I4.md`, `thesis_v2/anomaly/DESIGN.md:81`(§3 삽입 구조), `docs/verification/aspice/UML.md`(`check_uml.py`로 코드와 대조) | ① UML은 코드에서 **역으로** 그렸다(설계 산출물이 아님). ② 컴포넌트 간 인터페이스 명세(입출력 타입·단위·범위)가 별도 문서로 없다. 함수 시그니처와 docstring이 그 역할을 한다(**추정** — 별도 인터페이스 문서를 찾지 못함). ③ 이상탐지 DESIGN과 코드도 같은 커밋에 처음 들어갔다(2b49000, 2026-10-01) |
| **SWE.3** Software Detailed Design and Unit Construction | `thesis_v2/baseline`(동결)·`improved`·`improved/student_i4`·`anomaly` 패키지. 코드 주석의 REQ ID·태그. 고정 파라미터 단일 정의와 시작 시 assert | `thesis_v2/baseline/fsm.py:45-75`(REQ 주석 예), `thesis_v2/baseline/config.py:16-27`(정의), `:86-88`(assert), 코드 → REQ 역추적 `TRACE_MATRIX.md` "역방향: 코드(함수) → REQ" | ① 상세 설계 문서가 따로 없고 코드 주석이 그 역할을 한다. ② 코딩 규칙·정적 분석 실행 기록이 없다(**추정** — 저장소 루트에서 lint·정적 분석 설정 파일을 찾지 못함). ③ 코드 연결이 없는 REQ가 5개 있다(`TRACE_MATRIX.md` 요약) |
| **SWE.4** Software Unit Verification | REQ ID별 단위 테스트(`thesis_v2/tests` 185 + `anomaly/tests` 155 = 340 수집 항목, 그중 45개는 mutation 보강 — `docs/verification/mutation/RESULTS.md`). 구문·분기 커버리지. FSM 전이 조건 MC/DC(unique-cause, 11/14 → 14/14). REQ ↔ 테스트 추적표 | `thesis_v2/tests/TRACEABILITY.md`, `docs/verification/COVERAGE.md`(라이브러리 모듈 구문 91.6%·분기 83.0%), `docs/verification/MCDC_FSM.md`, `docs/verification/mcdc/MCDC_TABLES.md`, 자동 추적 `TRACE_MATRIX.md` | ① 커버리지 목표치를 **사전에 정하지 않았다**(`COVERAGE.md` 끝 절). ② MC/DC는 `fsm.py`만 했다. ③ 도구(coverage.py, 자체 MC/DC 플러그인) 적격성 확인이 없다. ④ 추적 고아(자동 집계): **테스트 없는 REQ 15개**, **REQ 없는 테스트 함수 166개**(이상탐지 94 · improved 33 · 인프라·도구 34 · 기타 5) — 억지로 연결하지 않았다. ⑤ 테스트 리뷰 기록이 없다 |
| **SWE.5** Software Component Verification and Integration Verification | 폐루프 SIL 회귀: golden(baseline v1.1, paper·left_obstacle × seed 0–2 = 6개 시나리오, 전이·결과·완료 step 완전 일치, 조향각 1e-3 rad). 통합 루프 동치 테스트(improved ↔ baseline, anomaly 런너 ↔ improved v2). CI(ubuntu-24.04·windows) | `thesis_v2/tests/check_golden.py:21`(허용오차), `thesis_v2/tests/golden/README.md:32-35`(판정 기준), `thesis_v2/anomaly/tests/test_golden_equivalence.py`, `thesis_v2/tests/test_improved_equivalence.py`, `.github/workflows/ci.yml`, `docs/verification/CI.md` "첫 GitHub 실행 결과"(run #1: 두 OS 모두 295 passed, golden 6/6, 차이 0 rad) | ① 통합은 한 Python 프로세스 안 함수 호출 수준이다. 실제 ECU·RTOS·통신 인터페이스 통합은 없다(시뮬레이션 한정, README 상태 표). ② golden 시나리오가 6개뿐이라 회귀 감지 범위가 그만큼으로 제한된다. ③ 인터페이스 단위의 통합 테스트 명세 문서가 없다 |
| **SWE.6** Software Verification | ① 제어기 평가: 실행 전 고정 기준(`MEASURE_PLAN.md`)으로 E2(seed 200–299 + 1/4칸 격자 900)·E3(seed 2000–2099 + 3/4칸 격자 900)를 확정 코드에 각 1회 실행. ② 이상탐지 오프라인 평가(seed 4000–4099). ③ 이상탐지 폐루프 평가 1,100회(11 run × 100 seed, seed 5000–5099). ②·③ 모두 동결 태그에서 1회 실행하고 `--check`로 재현 확인 | `repro/docs/MEASURE_PLAN.md:1`("실행 전 확정"), `repro/docs/RESULT_IMPROVED.md:262`(§8 eval 2회차 판정), `thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/`, `repro/2c_analysis/out/i4_eval3_judgement/eval3_judgement.json`, `thesis_v2/anomaly/DESIGN.md:198`(§13 사전 선언), `:560`(§19 사전 선언 수정), `:885`(§24 폐루프 사전 선언), `:1334`(§27)·`:1360`(§28) 재현 확인, `docs/revision/확장_센서시계열이상탐지_2026.md:323`(11 run × 100 seed = 1,100회), 결과 폴더는 `TRACE_MATRIX.md` "이상탐지 확장" 표 | ① **이상탐지 평가는 SW 요구사항 대비 검증이 아니라 "DESIGN §13(·§19·§24) 사전 선언 대비 평가"다.** 이상탐지에는 REQ ID가 없다. ② 제어기 평가도 REQ ID 단위의 합격 판정이 아니라 `MEASURE_PLAN.md` 지표 단위의 판정이다. 추적 매트릭스의 "평가 문서" 열은 REQ ID를 인용한 행일 뿐 검증 연결이 아니다. ③ 시뮬레이션(운동학 모델, 이상화된 센서) 한정이며 실차·HIL은 없다(README 상태 표). ④ 독립 시험 조직이 없다 |

## 공통 갭

- **독립 리뷰가 없다.** 요구사항·설계·코드·테스트를 같은 사람(과 Claude 세션)이 작성하고 확인했다. 이상탐지 보고서의 "독립 감사"(`thesis_v2/anomaly/DESIGN.md:1292`, §26)는
  서브에이전트 1회 검토이며, 독립된 사람의 리뷰가 아니다.
- **프로세스 산출물을 사후에 매핑했다.** 이 문서, `TRACE_MATRIX.md`, `UML.md`는 2026-10-13에 기존 산출물로부터 역으로 만들었다.
- **변경·형상 관리**는 git 커밋과 동결 태그(`anomaly-eval-freeze`, `anomaly-cl-freeze`)로만 한다. 변경 요청·승인 기록은 대화 기록과 DESIGN 문서의 절로 남아 있다(**추정** — 별도 변경 관리 도구 없음).
- 표준 내용(프로세스 목적, 기대 결과)은 원문과 대조하지 않았다. 이 문서는 프로세스 이름 수준의 대응만 다룬다.
