# MPC 기반 자율주행 차선변경 제어기 — 졸업논문의 명세 기반 재구현과 검증

[![tests-and-golden](https://github.com/wwonnae/mpc-lane-change-verification/actions/workflows/ci.yml/badge.svg)](https://github.com/wwonnae/mpc-lane-change-verification/actions/workflows/ci.yml)

2025년 12월 제출한 졸업논문(`docs/졸업논문.pdf`)을 **요구사항 명세로 삼아 제어기를 처음부터 다시 구현하고**, 실행 전에 고정한 기준으로
측정·개선한 뒤, 그 결과로 기술보고서를 새로 쓴 저장소입니다. 제출본 PDF와 당시 코드는 `legacy_2025/`에 그대로 보존하고, 새 코드·새 수치만 따로 둡니다.

- **제어 구조**: FSM(차로 유지·회피·복귀·비상 정지) + 횡방향 **MPC(OSQP, 2-상태 y/ψ)** + **규칙 기반 종방향 속도 제어**(MPC에 속도를 넣지 않음)
- **검증 방식**: Python 제어기를 운동학 차량 모델·센서 모델과 폐루프로 돌리는 SIL 방식 시뮬레이션. 실제 RC카·실차 검증은 없음
- **보조 주제**: MPC를 모방한 소형 신경망(Student)의 임베디드 적용 여지 — 폐루프로 직접 검증

## 5분 안에 보기

**1. 무엇을 했나**
- 제출 논문을 요구사항 57개(REQ ID)로 명세화하고, 모호·공백 항목은 결정표로, 논문대로는 성립하지 않는 값 3건은 [개정]으로 기록한 뒤 새로 구현했습니다.
- 개발용·평가용 seed를 분리하고, 평가는 확정된 코드에 한 번만 실행했습니다. 판정 기준은 실행 전에 고정했습니다(`repro/docs/MEASURE_PLAN.md`).
- 같은 코드에 현업 검증 산출물 형태의 검증을 덧붙였습니다: 양방향 추적 매트릭스, 커버리지, MC/DC, FMEA·FTTI 근사, mutation testing, CI 비결정성 원인 규명.

**2. 핵심 결과** (근거는 아래 상태 표)

| 항목 | 결과 |
|---|---|
| 제출본 설계(baseline v1.1), 평가 seed 100회 | 회피 성공 95/100, 충돌 5/100 — 원인은 장애물 정보가 없는 비용함수(분석 사례 기준) |
| 개선판 v2, 평가 조건 전체 | 충돌 96/2700 → 0/2700, 경계 격자 실패 81/900 → 0/900, 역전 0 |
| 제출본 입력 정의(헤딩 없음)의 신경망 | 폐루프 성공 9/100 → 헤딩 추가(S10) 후 100/100 (같은 평가 데이터) |
| 교차 환경 재현성 | 기준 시나리오 6개, 다른 PC·Python 3.12에서 조향각 차이 0 rad |
| 테스트 | 359개 통과(재구현 204 + 이상탐지 155), golden 폐루프 회귀 6/6 |
| mutation testing | 변이 600개, 원점수 78.5% → 88.5%(등가 제외 83.1% → 93.7%) |

**3. 검증 산출물 지도** (`docs/verification/`)

| 산출물 | 문서 |
|---|---|
| 전체 안내 | [docs/verification/README.md](docs/verification/README.md) |
| 요구사항 ↔ 설계 ↔ 코드 ↔ 테스트 추적 매트릭스(자동 생성, `--check`), ASPICE SWE.1–6 관점 매핑, UML ↔ 코드 대조 | [docs/verification/aspice/](docs/verification/aspice/README.md) |
| 구문·분기 커버리지, FSM 전이 조건 MC/DC(11/14 → 14/14) | [COVERAGE.md](docs/verification/COVERAGE.md), [MCDC_FSM.md](docs/verification/MCDC_FSM.md) |
| FMEA·FTTI/FDTI/FRTI 근사(저장된 평가 결과 분석, 표준 준수·인증 아님) | [docs/verification/safety/](docs/verification/safety/README.md) |
| mutation testing(직접 만든 AST 변이기, 사전 선언 후 실행) | [docs/verification/mutation/RESULTS.md](docs/verification/mutation/RESULTS.md) |
| CI(GitHub Actions, ubuntu·windows), 비결정성 원인 규명(OSQP time_limit 절단) | [CI.md](docs/verification/CI.md), [ci/run6_cause/](docs/verification/ci/run6_cause/README.md) |

**4. 이 저장소에 대하여**
- 개발 이력이 담긴 원 저장소(비공개)를 정리해 올린 공개 스냅샷입니다. 문서·결과 파일에 적힌 커밋 해시, git tag, GitHub Actions 실행 번호(run #1–#6)는 원 저장소 기준이라 여기서는 열리지 않습니다.
- 공개하면서 제출 당시 원본 코드·데이터를 모두 `legacy_2025/`로 옮기고, 문서와 비교 스크립트의 경로를 새 위치로 고쳤습니다. 원본 파일 내용은 바꾸지 않았으므로 `파일:행` 인용은 그대로 유효합니다. 실행 기록(json 등 원자료) 안의 경로 문자열은 당시 값 그대로입니다. 재구현 직전에 만든 첫 점검 기록(`verify/`)은 공개본에서 뺐고, 같은 사실은 `repro/docs/STAGE1_FACTS.md`에 정리돼 있습니다.
- 작업 전 과정에 적용한 규칙은 `repro/docs/WORK_RULES.md`에 있습니다. 재구현·검증 작업에는 Claude Code를 활용했고, 판정 기준·사전 선언·결과 수락은 사람이 결정했습니다.
- **읽는 순서**: 위 요약 → 기술보고서 → 아래 상태 표 → 필요한 근거 문서

## 문서 지도

| 무엇 | 어디 |
|---|---|
| **기술보고서(최종 결과물)** | `docs/revision/재구현검증보고서_2026.md`, 인쇄용 `docs/revision/재구현검증보고서_2026.html` |
| 보고서의 모든 수치와 근거 파일(제출본 값 대조 포함) | `docs/revision/REVISION_NUMBERS.csv`, 값 변경 이력 `docs/revision/CSV_CHANGELOG.md` |
| 요구사항 명세(REQ ID 57개) | `repro/docs/SPEC.md` |
| 모호·공백 항목의 결정표, [개정] 근거 | `repro/docs/SETTINGS_DECISION.md`, `repro/docs/FEASIBILITY_CHECK.md` |
| 실행 전에 고정한 측정·판정 기준, seed 정책 | `repro/docs/MEASURE_PLAN.md` |
| 결과 기록(단계별) | `repro/docs/RESULT_BASELINE.md`, `RESULT_ROBUSTNESS.md`, `RESULT_IMPROVED.md`, `RESULT_STUDENT.md`, `RESULT_I4.md`, 요약 `STAGE3_SUMMARY.md` |
| 제출본에서 확인된 오류·정정 기록 | `repro/docs/THESIS_REVISION_LOG.md` |
| 당시 코드·데이터의 사실 조사(1단계) | `repro/docs/STAGE1_FACTS.md`, `CLASSIFICATION.md`, `THESIS_TIME_CODE.md`, `PDF_VS_CODE.md`, `SPEC_VS_OLDCODE.md` |
| 원본 코드 재정리 기록 | `repro/docs/REORG_PLAN.md` |
| REQ ID ↔ 테스트 추적표 | `thesis_v2/tests/TRACEABILITY.md` |
| **확장: 센서 시계열 이상탐지 보고서**(제출본·기존 보고서에 없는 내용) | `docs/revision/확장_센서시계열이상탐지_2026.md`, 수치표 `docs/revision/ANOMALY_NUMBERS.csv`, 설계·사전 선언·전체 기록 `thesis_v2/anomaly/DESIGN.md` |

## 저장소 구성 — 원본 코드와 재구현 코드

| 구분 | 위치 | 설명 |
|---|---|---|
| **재구현(새 코드)** | `thesis_v2/baseline/` | 논문 서술 + 결정표 그대로의 정합 구현(baseline v1.1). 개선 단계 동안 동결 |
| | `thesis_v2/improved/` | 개선판 v1(I1+I1b+I2'+I3)·v2(v1 + I5 반복 상한 972), Student 폐루프 검증(`student_i4/`). 각 개선은 config 플래그로 on/off |
| | `thesis_v2/tests/` | REQ ID별 단위 테스트(204개), golden 기준 데이터, `compare/`(옛 코드와의 비교 — 옛 코드를 import하는 유일한 위치) |
| | `thesis_v2/results/` | 모든 새 측정 결과(`<타임스탬프>_<호스트>_<버전·트랙>/`, 환경 기록 `env.json` 포함) |
| 분석·보고서 | `repro/`, `docs/revision/` | 사실 조사·분석 스크립트와 문서, 보고서 원고·수치표·그림·조립 스크립트 |
| **원본(제출 당시, 수정하지 않음)** | `legacy_2025/final_hierarchical_backup_thesis_1204.py` | **A** — 2025-12-04 논문 데이터를 만든 당시 제어기(12-04 스냅샷). 비교(C 트랙) 전용 |
| | `legacy_2025/final_hierarchical_backup_modified_2026.py` | **B** — 제출 이후 수정본(SAFE_STOP 예외·쿨다운 추가). 논문 결과와 무관 |
| | `legacy_2025/run_simulation.py`, `legacy_2025/analysis.py`, `legacy_2025/analyze_mpc.py` | 논문 데이터 생성 파이프라인과 논문 그림 생성 스크립트 |
| | `legacy_2025/backup/`, `legacy_2025/code_backup/` | 논문에 쓰이지 않은 스크립트(7개)와 당시 작업 폴더 |
| | `legacy_2025/results/`, `legacy_2025/models/`, `legacy_2025/dataset/`, `docs/졸업논문.pdf` | 제출 당시 데이터·모델·제출본 |

재구현 코드는 원본을 복사하지 않고 명세(`SPEC.md`)만 근거로 새로 작성했습니다. 원본 파일은 2026-09-25에 이름·위치를 한 번 정리했고(내용 불변,
`repro/docs/REORG_PLAN.md`), 공개 저장소에서는 다시 `legacy_2025/` 아래로 모았습니다. 원본 스크립트 안의 옛 import 경로는 고치지 않았으므로
원본 파이프라인을 그대로 다시 돌리는 용도는 아닙니다. 원본 코드를 쓰는 비교 스크립트(`thesis_v2/tests/compare/`)는 새 경로를 가리킵니다.

## 재현 방법

**환경**(Windows, Python 3.9 기준 — 3.12용은 `thesis_v2/requirements-py312.txt`, 상세 `thesis_v2/README.md`):

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r thesis_v2\requirements-py39.txt
```

**테스트**(수 초):

```powershell
.\.venv\Scripts\python -m pytest thesis_v2/tests thesis_v2/anomaly/tests -q   # 359 passed
.\.venv\Scripts\python -m thesis_v2.tests.check_golden     # golden 단독: 6/6 PASS, 조향각 최대 차이 0
```

**트랙별 실행**(평가 데이터는 확정된 코드로 한 번씩만 실행한 기록이 이미 `thesis_v2/results/`에 있음 — 다시 돌리면 같은 결과가 나와야 함.
100 에피소드 이상은 수 분–수십 분):

| 트랙 | 명령 |
|---|---|
| P 물리 폐루프 — baseline | `python -m thesis_v2.baseline.run --scenario paper --seed-start 0 --n-episodes 100 --out <폴더>` (`--scenario left_obstacle`로 SAFE_STOP 검증) |
| P — baseline·v1·v2 비교(E2) | `python -m thesis_v2.improved.run_eval_v2 --out-root <폴더>` |
| C 옛 MPC vs baseline MPC | `python -m thesis_v2.tests.compare.run_c_track_grid` |
| M 신경망(원 모델, 개루프) | `python -m thesis_v2.tests.compare.run_m_track` |
| Student 폐루프(E3) | `python -m thesis_v2.improved.student_i4.closed_loop --run-dir <run> --track eval3_paper --model-dir <S10>` |
| 계산 시간(공식 조건) | `python -m thesis_v2.improved.student_i4.benchmark_timing --run-dir <run> --power-mode-confirmed` (AC 전원 + 최고 성능 모드에서만) |
| 탐지기 계산 시간(공식 조건) | `python -m thesis_v2.anomaly.benchmark_detector_timing --power-mode-confirmed --cooldown-before-sec 60` (같은 조건, 약 15분) |
| 보고서 재조립 | `python docs/revision/scripts/make_revision_numbers.py` → `python docs/revision/scripts/build_report.py --check` → `python docs/revision/scripts/make_html.py` |

## 상태 표 — 무엇을 믿어도 되는가

- **검증됨**: 이 저장소에서 새로 측정했고, 사전 고정 기준으로 판정했으며, 근거 파일로 다시 확인할 수 있음
- **조건부**: 측정은 맞지만 적용 범위에 조건이 붙음
- **재현불가**: 제출본에 있으나 저장소의 코드·데이터로 다시 만들 수 없음(새 측정값으로 대체함)
- **사용금지**: 근거로 쓰면 결론이 틀어짐

비율은 k/n과 Wilson 95% 신뢰구간, 계산 시간은 p99가 주 지표입니다. E2 = seed 200–299 + 1/4칸 격자 900, E3 = seed 2000–2099 + 3/4칸 격자
900(둘 다 개발에 쓰지 않은 평가 데이터, 각 1회 실행).

| 항목 | 상태 | 근거 파일 | 비고 |
|---|---|---|---|
| baseline v1.1: 논문 시나리오 FSM 흐름(KEEP_L2→EVADE_L→KEEP_L1→RETURN_TO_L2→KEEP_L2), E2 paper 성공 95/100(88.8–97.8%), 충돌 5/100 | 검증됨 | `thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/`, `repro/docs/RESULT_IMPROVED.md` §8 | 충돌은 기하학적 판정(회전 사각형)으로 셈. 제출본 코드에는 충돌 판정이 없었음 |
| 좌측 차로 장애물 → SAFE_STOP: 100/100(baseline·v1·v2 동일) — **노이즈 없는 조건**(`thesis_v2/improved/run_eval_v2.py:174-178`) | 검증됨 | 같은 폴더 | 제출본에 없던 검증 시나리오. S4 노이즈 조건은 아래 행 |
| 좌측 차로 장애물 + S4-low 센서 노이즈: v2가 400회 중 4회 충돌(기존 근거리 시나리오), 이상탐지 원거리 시나리오 400회 중 1회(seed 3000–3399 보충 재현) | 조건부 | `docs/revision/data/anomaly/supplement.json`, `thesis_v2/anomaly/DESIGN.md` §25-1 | 노이즈 오판정으로 회피 진입 → SAFE_STOP이 쿨다운 0.3 s에 막힘(재현 seed 3173에서 확인). 기존 E2·E3는 이 조합을 평가하지 않았음. 개선 후보는 `IMPROVEMENT_BACKLOG.md` 후보 13(미구현) |
| improved v2(최종 MPC): E2 paper 100/100, S3 격자 실패 0/900; E3 paper 100/100, S3 900/900 | 검증됨 | `repro/docs/RESULT_IMPROVED.md` §8, `repro/2c_analysis/out/i4_eval3_judgement/eval3_judgement.json` | baseline의 S3 실패 81/900 → 0/900. v1도 0/900이나 계산 시간 꼬리가 길어 v2 채택 |
| Student S10(입력 9 + 헤딩 ψ): E3 paper 100/100, S3 900/900, v2 MPC와 결과가 다른 에피소드 0/100·0/900 | 검증됨 | `eval3_judgement.json`, `repro/docs/RESULT_I4.md` §9 | 판정 = "조향 명령 대체 시 v2 MPC 대비 비열화 없음(시뮬레이션, eval3)" |
| 제출본 입력(9차원) 그대로의 Student는 폐루프 실패: E2 paper 성공 7/100, 충돌 23/100(E3에서도 9/100·24/100) | 검증됨 | `thesis_v2/results/i4_student/20260925_075822_DESKTOP-MDCKRJS/eval/closed_loop/`, `RESULT_I4.md` §5·§6 | 원인: 입력에 헤딩이 없어 교사 조향을 결정할 수 없음(계산으로 증명, `SETTINGS_DECISION.md` §20) |
| 제출본 명세 중 실현 불가능한 값 3건([개정]) | 검증됨 | `repro/docs/FEASIBILITY_CHECK.md`, `SETTINGS_DECISION.md`, 보고서 부록 A.1 | 복귀 임계값 0.20→0.08 m, 초기 위치 분포 절단, Student 입력 +ψ. 고정 파라미터는 건드리지 않음 |
| 교차 환경 재현성: 다른 PC·Python 3.12·osqp 1.1.3에서 golden 6/6, 조향각 최대 차이 0 rad | 검증됨 | `repro/docs/RESULT_BASELINE.md` §9 | 판정 기준은 1e-3 rad |
| 공식 계산 시간(노트북, AC + 최고 성능): baseline MPC p99 0.184 ms, v2 MPC p99 1.380–1.405 ms(4회), 제어 1스텝 p99 = 20 Hz 예산의 0.39% | 검증됨 | `docs/revision/data/r2_timing_supplement/r2_timing.json`, `thesis_v2/results/timing_v3/`, `RESULT_I4.md` §12 | 측정 조건은 `env.json`에 기록(`meets_official_condition=true`) |
| 보고서 수치의 재생 검증: 통계용 재실행이 저장된 평가 결과와 에피소드 단위로 일치한 경우만 사용, 본문 수치 ↔ CSV 자동 대조 | 검증됨 | `docs/revision/scripts/r1_*.py`, `r3_*.py`, `build_report.py --check` | 불일치 시 저장하지 않도록 구현 |
| 단위 테스트 204개(REQ ID별) + golden | 검증됨 | `thesis_v2/tests/`, `TRACEABILITY.md` | 공개 저장소 정리(원본 `legacy_2025/` 이동) 후에도 전부 통과 |
| 모든 결과는 시뮬레이션(운동학 모델, 이상화된 센서 변환) 한정 | 조건부 | 보고서 VII장 | 실제 RC카·실차 검증 없음 |
| 신경망은 제약을 구조적으로 보장하지 못함: S10 원출력 >25° 0.80%(paper)·1.23%(S3), 최대 26.02° | 조건부 | `eval3_judgement.json` | 차량 입력은 후처리 clip으로 범위 안. 제약 보장은 MPC에만 해당 |
| S10은 제출본 Student가 아님(입력에 ψ 추가) | 조건부 | `SETTINGS_DECISION.md` §20 | FSM·속도·후처리는 규칙 기반 그대로, Student 학습에는 교사 MPC가 필요 |
| 추론 속도 배수는 범위로만: v2 MPC ÷ S10 p99 = ONNX 47.8–51.7배, PyTorch 6.8–9.9배 | 조건부 | `CSV_CHANGELOG.md`, `RESULT_I4.md` §12 | 1 ms 미만 p99가 같은 조건 실행 사이에 −21%·−31% 변동 |
| 계산 시간은 노트북 x86 한 대의 공식 조건 값 | 조건부 | 보고서 부록 B | 임베디드 보드(라즈베리파이 등)는 측정하지 않음 |
| baseline(제출본 설계)의 강건성은 논문 시나리오 범위 한정: E2 S3 격자 실패 81/900 | 조건부 | `RESULT_IMPROVED.md` §8, `RESULT_ROBUSTNESS.md` | 범위 밖 조건은 개선판 v2 기준으로 판단 |
| 제출본 계산 시간(표 8·16·18, 본문) | 재현불가 | `legacy_2025/analysis.py:70-77`, `legacy_2025/backup/justify_mpc.py:351`, `legacy_2025/code_backup/run_hierarchical.py:390`, CSV 93–99·183–189·210–230행 | 측정 코드 없음. 상수로 확인된 7개(표 8·16의 평균·표준편차·최대 1.091/0.152/5.747, 0.206/0.055/1.557 ms, 본문 3.23 ms)와 출처 미발견(나머지)으로 나뉨. 공식 조건 새 측정값으로 대체 |
| 학습 샘플 19,129개 | 재현불가 | CSV 50·108행, 보고서 부록 A.3 | 생성 기록 없음. 새 데이터셋 115,076개(정의: MPC 호출 스텝) |
| Student 조향 MAE 1.20°(표 15) | 재현불가 | `repro/docs/RESULT_STUDENT.md` §4·§8, CSV 179행 | 원 테스트셋 없음, 원 모델 재측정은 크게 다름. 새 S10 개루프 MAE 0.512°는 교사·입력·데이터가 달라 직접 비교 불가 |
| 총 파라미터 수 약 135,000 | 재현불가 | CSV 54행 | 표 4 구조로 계산하면 102,786 |
| 표 9 에피소드당 최대 샘플 267 | 재현불가 | CSV 111행, `THESIS_REVISION_LOG.md` | 에피소드 최대 길이 200 step보다 큼(제출본 내부 불일치) |
| 교사 성능 표의 일부 통계(표 6·7·11·13·14·17) | 재현불가 | 보고서 부록 A.3, `THESIS_REVISION_LOG.md` | 라벨·정의 불일치(예: "Teacher" 표 값이 저장된 Student 데이터에 가까움) — 같은 정의로 재측정 |
| `legacy_2025/results/`(당시 `metrics.npz`)를 제어 성능 근거로 사용 | 사용금지 | `repro/docs/THESIS_TIME_CODE.md` §3·§4 | 스크립트로 front_gap을 주입해 만든 데이터 — 물리 시뮬레이션이 아님 |
| 제출본 수치를 새 결과처럼 인용 | 사용금지 | `repro/docs/WORK_RULES.md`, CSV "제출본_값" 열 | 제출본 값은 비교 열에만 둠 |
| `legacy_2025/final_hierarchical_backup_thesis_1204.py`의 MPC를 정답 MPC로 사용 | 사용금지 | 보고서 IV장 2절, `repro/docs/RESULT_STUDENT.md` §4-1 | 비용함수 선형항·Hessian 불일치로 목표선의 두 배 위치로 끌림. C 트랙 비교 전용 |
| 제출본 원 모델(`legacy_2025/models/`) 성능을 폐루프 근거로 사용 | 사용금지 | `RESULT_STUDENT.md` §8 | 개루프 비교만 했음. 같은 입력 정의의 재학습 모델은 폐루프 실패 |
| 평가 데이터(E2·E3)로 파라미터 조정·재실행 | 사용금지 | `repro/docs/WORK_RULES.md` 3단계 원칙, `MEASURE_PLAN.md` | 파라미터는 해석적으로 또는 개발 데이터(D)에서만 결정. 평가는 확정 코드에 1회 |
| 교육장 PC(H2·H3) 계산 시간을 공식 값으로 사용 | 사용금지 | 보고서 부록 B | 참고치. 공식 값은 노트북 공식 조건 측정만 |

### 확장: 센서 시계열 이상탐지 (2026-10, 시뮬레이션 주입 고장)

제출본·기존 보고서에 없는 확장이다. 기준 제어기는 improved v2(수정 없음)이다. 고장 9종(유해 6·무해 3)과 정상 2종을 다뤘고, 오프라인 평가는 seed 4000–4099,
폐루프 평가는 seed 5000–5099로 각각 동결 커밋에 1회 실행하였다. 상세와 수치 근거는 `docs/revision/확장_센서시계열이상탐지_2026.md`에 있다.

| 항목 | 상태 | 근거 파일 | 비고 |
|---|---|---|---|
| 탐지기를 붙여도 제어가 바뀌지 않음(관찰 전용 golden), 테스트 359개(기존 204 + 이상탐지 155 — 기존 204는 MC/DC 보강 3개, mutation 보강 14개, run #6 대응 19개 포함, `docs/verification/MCDC_FSM.md`, `docs/verification/ci/run6_cause/`; 이상탐지 155는 mutation 보강 31개 포함, `docs/verification/mutation/RESULTS.md`) 통과 | 검증됨 | `thesis_v2/anomaly/tests/`, `thesis_v2/tests/check_golden.py` | 다른 PC(3층PC109)에서도 golden 6/6, 조향각 차이 0 |
| 결과의 결정성·PC 간 재현: 폐루프 dev 6개 조합 전체 `--check` 일치(3층PC108 결과를 3층PC109에서 재계산), IF 재학습 점수 차이 0.0 | 조건부 | `thesis_v2/anomaly/DESIGN.md` §24-1·§24-2·§27·§28, `thesis_v2/results/anomaly/20261012_*_identity_check/` | 일치는 "실행 중 같은 PC에서 다른 작업 없음" 조건에서 확인. **오프라인 평가 결과**(3층PC108 생성)를 3층PC109에서 `--check` 재계산해 10개 파일 전부 일치(2026-10-12, 로그 `thesis_v2/results/anomaly/20261012_3층PC109_run_logs/offline_eval_check_20261012_153144.log`, §27, 다른 PC 간 재현). **폐루프 평가 결과**(3층PC109 생성)를 같은 3층PC109에서 `--check` 재계산해 7개 파일 전부 일치(2026-10-12, 로그 `thesis_v2/results/anomaly/20261012_3층PC109_run_logs/cl_eval_check_20261012_154729.log`, §28, 같은 PC 재실행). 폐루프의 PC 간 재현 근거는 dev 결과(3층PC108 생성 → 3층PC109 전체 일치·노트북 부분 확인 일치). 조건부 유지 이유: 노트북 dev `--check` 1회 불일치(§24-1) 원인 미확정, 일치 확인은 모두 조용한 환경 조건, 폐루프 평가 결과의 재현은 같은 PC 재실행뿐 |
| 오프라인 평가: 탐지기 A가 유해 고장 600/600 탐지, 정상 오경보 0/200. B1 7/600, B2 508/600, 하이브리드 164/600 | 조건부 | `thesis_v2/results/anomaly/20261002_145638_3층PC108_it3_eval_offline_eval/summary.json` | A는 참값 y·모델 오차 0인 시뮬레이션에 기댄 **상한**. 자이로 σ가 가정의 2배이면 정상 오경보 180/200 |
| 폐루프: A + 정지(P1_A·P2_A)가 P0 충돌 160건 중 159건을 막고 새 충돌 0, 대가로 완료 770 → 231(P1_A)·529(P2_A) | 조건부 | `thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval/`, 보고서 V장 | 정지가 즉시(REQ-VEH-05, 제동 거리 없음)라 안전 효과는 **낙관적**. 같은 seed 안 run 간 상관 있음(seed 5064 오경보 1건이 9개 run에 반복) |
| P2_A의 left_clear_stuck SAFE_STOP 99건(같은 seed P0는 이탈 85·충돌 14) | 조건부 | 보고서 V장 Q4, `thesis_v2/anomaly/DESIGN.md` §25-2 | 정지했으나 1차선 안에서 장애물 약 0.20 m 이내까지 접근 — dev 재현(seed 3200–3299, 100/100)에서 정지 후 간격 0.038–0.202 m, 평가 99건은 같은 경로로 **추정**(정지 위치 기록 없음). 즉시 정지 가정 때문에 충돌이 안 났을 수 있음. P2_A의 P1_A 대비 완료 +298 중 99건이 이 정지 |
| P2_A의 rc 대응으로 무해 고장 right_clear_stuck이 99/100 타임아웃(같은 seed P0는 99건 모두 성공) | 검증됨 | 보고서 V장 Q3, 폐루프 평가 episodes_P2_A.csv | 원인 "right_clear=False 덮어쓰기로 KEEP_L1→RETURN 복귀 불가"는 코드(`baseline/fsm.py:64`)와 dev 10건 경로에 근거한 **추정**(평가 에피소드의 FSM 경로는 기록 없음). 사전 정의상 불필요 정지에 들어가지 않으므로 무해 완료(134/300)로 읽어야 함 |
| v2 제어기의 정상 좌측 장애물 주행 충돌(평가 1/100 — seed 5011, 보충 재현 1/400 — seed 3173) | 조건부 | 보고서 V장 5절, `docs/revision/data/anomaly/supplement.json` | 원인(seed 3173 재현으로 확인): left_clear 노이즈 오판정 → 회피 → SAFE_STOP 쿨다운 0.3 s. **seed 5011은 같은 원인으로 추정**(평가 결과에 경로 기록 없음, 평가 seed 재실행 안 함) |
| B 계열(정상 데이터로만 학습)의 LiDAR 멈춤 탐지 | 조건부 | 보고서 IV장 | lidar_freeze를 B1·하이브리드 0/100, B2 20/100만 탐지. B 결과는 정상 데이터 구성에 민감(iteration 1·2) |
| σ 전달 버그 상태의 임계값·dev 결과(`..._112515_...sg0.05`, `..._112618_...sg5`, `..._114809_...eval_offline_dev`) | 사용금지 | `thesis_v2/anomaly/DESIGN.md` §22 | 버그 증거로만 보존. 수정 후 폴더만 사용 |
| 탐지기 계산 시간(노트북 공식 조건, 정상 seed 3000–3199 × 2시나리오 400회, 탐지기당 59,331 step): 제어 1스텝 + 탐지기 p99 = A 1.27 ms(2.54%)·B2 1.58 ms(3.16%)·B1 11.29 ms(22.6%)·하이브리드 10.79 ms(21.6%), 20 Hz 예산 50 ms 대비. **A·B2는 최악값까지 20 Hz 예산 이내**(최댓값 3.71·5.07 ms, 초과 0 step) | 검증됨 | `thesis_v2/results/anomaly/20261012_232824_DESKTOP-MDCKRJS_detector_timing/timing.json`, 로그 `thesis_v2/results/anomaly/20261012_DESKTOP-MDCKRJS_run_logs/` | `env.json`: 커밋 c560b8f, dirty false, `meets_official_condition=true`. 측정 루프의 에피소드 결과가 저장된 임계값 실행과 1600/1600 일치(제어 무변경). DESIGN §29 |
| B1·하이브리드: **p99는 예산 이내지만 최댓값이 예산 초과**(탐지기 단독 68.31·56.58 ms, 제어 포함 68.80·61.01 ms, 각 1 step) → **스텝마다 보장되지 않음** | 조건부 | 같은 파일 | p50(약 6 ms)이 B2의 30–31배. 원인은 IF 단일 샘플 호출 비용(**추정**, 호출 내부 미분해, 초과 1 step과 OS 요인 미분리). 코드 미수정, 대안은 `IMPROVEMENT_BACKLOG.md` 후보 14(미구현) |
| 탐지기 계산 시간은 노트북 x86 한 대의 공식 조건 값 | 조건부 | 보고서 III장 5절·VII장 9 | 임베디드 보드(라즈베리파이 등)는 측정하지 않았음. 정상 주행만 측정 |
| 이상탐지 평가 데이터(seed 4000–4099, 5000–5099)로 탐지기·임계값 조정·재실행 | 사용금지 | `thesis_v2/anomaly/DESIGN.md` §13 | 평가는 동결 태그(`anomaly-eval-freeze`, `anomaly-cl-freeze`)에서 1회. 결정성 확인은 `--check`로만 |

이상탐지 보고서는 독립 감사(서브에이전트 1회)를 거쳐 지적 사항을 반영하였다(`thesis_v2/anomaly/DESIGN.md` §26).

## 남은 작업

- 개선 후보(구현하지 않음): DAgger류 반복 학습, 신경망 출력 제한 내장, 신경망 우선·MPC 폴백 하이브리드 — `repro/docs/IMPROVEMENT_BACKLOG.md`.
