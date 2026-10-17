# 실험 당시 코드 추정 — 상세 조사 (1단계 보완)

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

원본(루트, `legacy_2025/code_backup/`, `legacy_2025/results/`, `legacy_2025/models/` 등)은 전혀 수정·삭제·이동하지 않았습니다.
전부 읽기만 했습니다. 새로 만든 계산 스크립트/결과는 `repro/stage1_analysis/`에 있습니다(2단계 하네스는 별도 `repro/harness/`, `repro/results/`를 씁니다).
"확인됨"=이번 세션에서 직접 실행/열람, "추정"=정황 근거. 근거는 파일:행 또는 PDF 페이지.

---

## 1. `legacy_2025/results/` 재조사

### 1-1. 전체 파일 목록

`legacy_2025/results/teacher/`, `legacy_2025/results/student/` 전체 파일 (확인됨: 직접 열람 + `os.walk` 스크립트):

| 파일 | 크기(byte) | 파일명 내 시각 | 행 수(데이터, 헤더제외) | 상태 종류 | front_gap NA 비율 |
|---|---|---|---|---|---|
| `legacy_2025/results/teacher/metrics.npz` | 2,129,228 | (npz, 파일명에 시각 없음) | 18,989(샘플) / 100(에피소드) | KEEP_L2,EVADE_L,KEEP_L1,RETURN_TO_L2 | 0% |
| `legacy_2025/results/teacher/run_1764695779.csv` | 90,636 | 2025-12-03 02:16:19 | 1,073 | KEEP_L2 | 100% |
| `legacy_2025/results/teacher/run_1764695887.csv` | 326,387 | 2025-12-03 02:18:07 | 3,790 | KEEP_L2 | 100% |
| `legacy_2025/results/teacher/run_1764696519.csv` | 1,944,048 | 2025-12-03 02:28:39 | 22,251 | KEEP_L2 | 100% |
| `legacy_2025/results/teacher/run_1764698319.csv` | 523,961 | 2025-12-03 02:58:39 | 6,061 | KEEP_L2 | 100% |
| `legacy_2025/results/teacher/run_1764699492.csv` | 107 | 2025-12-03 03:18:12 | 0 (헤더만) | - | - |
| `legacy_2025/results/teacher/run_1764699864.csv` | 107 | 2025-12-03 03:24:24 | 0 | - | - |
| `legacy_2025/results/teacher/run_1764699919.csv` | 107 | 2025-12-03 03:25:19 | 0 | - | - |
| `legacy_2025/results/teacher/run_1764700348.csv` | 107 | 2025-12-03 03:32:28 | 0 | - | - |
| `legacy_2025/results/teacher/run_1764733354.csv` | 107 | 2025-12-03 12:42:34 | 0 | - | - |
| `legacy_2025/results/teacher/run_1764733587.csv` | 107 | 2025-12-03 12:46:27 | 0 | - | - |
| `legacy_2025/results/teacher/run_1764738086.csv` | 107 | 2025-12-03 14:01:26 | 0 | - | - |
| `legacy_2025/results/teacher/run_1778131088.csv` | 107 | **2026-05-07 14:18:08** | 0 | - | - |
| `legacy_2025/results/teacher/ep_000~007/run_*.csv` | 14,072–14,488 | 2025-12-03 02:49:55–02:51:05 (10초 간격) | 164–173 | KEEP_L2 | 100% |
| `legacy_2025/results/teacher/ep_008/run_1764697875.csv` | 4,861 | 2025-12-03 02:51:15 | 57 | KEEP_L2 | 100% |
| `legacy_2025/results/teacher/ep_008/metrics.npz` | 6,909 | - | 56(샘플) / 1(에피소드) | KEEP_L2만 | 0%(값 자체는 있으나 회피 없음) |
| `legacy_2025/results/student/metrics.npz` | 2,124,860 | - | 18,950(샘플) / 100(에피소드) | KEEP_L2,EVADE_L,KEEP_L1,RETURN_TO_L2 | 0% |
| `legacy_2025/results/student/run_1764698663.csv` | 515,492 | 2025-12-03 03:04:23 | 6,033 | KEEP_L2 | 100% |
| `legacy_2025/results/student/run_1764699511/866/935.csv` 등 4개 | 107 | 2025-12-03 03:18–14:01 | 0 | - | - |

**요약**: `legacy_2025/results/teacher/`, `legacy_2025/results/student/` 안의 **loose csv·ep_* csv는 전부 front_gap이 NA이고
state가 KEEP_L2뿐**입니다(빈 파일 제외). 반면 **최상위 `metrics.npz` 2개만 4개 상태가 모두
존재하고 front_gap이 실수값**입니다. 즉 이 디렉터리 안에는 **서로 다른 두 종류의 실행 결과가
섞여 있습니다.**

### 1-2. metrics.npz 상세 (재확인 완료, `repro/stage1_analysis/recompute_tables_from_results.py` 실행 결과 `repro/stage1_analysis/recompute_tables.json`)

| 항목 | teacher/metrics.npz | student/metrics.npz | 논문(Table 9,10) |
|---|---|---|---|
| 키 | y,psi,delta,v,state,front_gap,loop_time,**compute_time**,episode,success | 동일 | - |
| 총 샘플 | 18,989 | 18,950 | 19,129 |
| 에피소드 수 | 100 | 100 | 100 |
| 에피소드당 샘플 평균 | 189.89 | 189.5 | 191.3 |
| 에피소드당 최소/최대 | 180 / 200 | 180 / 200 | 142 / 267 |
| EVADE_L 샘플/비율 | 400 / 2.11% | 400 / 2.11% | 402 / 2.1% |
| KEEP_L1 샘플/비율 | 1,256 / 6.61% | 1,260 / 6.65% | 1,263 / 6.6% |
| KEEP_L2 샘플/비율 | 10,515 / 55.37% | 10,510 / 55.46% | 10,770 / 56.3% |
| RETURN_TO_L2 샘플/비율 | 6,818 / 35.91% | 6,780 / 35.78% | 6,694 / 35.0% |
| SAFE_STOP | 0 | 0 | 0 |
| `success` 배열 | shape=(0,) (비어있음) | shape=(0,) | - |

**모든 항목이 논문 수치와 0.3–2%포인트 이내로 근접하지만 정확히 일치하지는 않습니다.** 에피소드당
최소/최대 샘플(180/200 vs 논문 142/267)은 차이가 더 큽니다. → **같은 파이프라인·같은 코드의 다른
실행(시드 미고정)일 가능성이 높지만, 이 파일이 논문에 실린 표를 만든 "바로 그 실행"이라고
단정할 근거는 없습니다.**

### 1-3. legacy_2025/verify/REPORT.md와의 모순 해결

`legacy_2025/verify/REPORT.md:90`(이전 세션 기록, 전제로 쓰지 않고 재확인 대상)은 "저장소의 모든 npz
후보(60,000 / 150,000 / 213 / 100행)에서 19,129와 일치하는 파일 없음"이라고 적혀 있어, 마치
`legacy_2025/results/teacher/metrics.npz`를 못 찾았거나 존재하지 않았던 것처럼 보입니다. 그런데
`legacy_2025/verify/closed_loop/REPORT_B.md:79`와 `legacy_2025/verify/task3_numeric_verification.py`의 실행 로그에는
"`legacy_2025/results/teacher/metrics.npz`의 실제 compute_time 평균 1.883ms"라는 구체적 수치가 나오는데,
이번 세션에서 제가 **같은 파일을 직접 다시 계산해도 평균 1.8830ms로 사실상 동일**했습니다
(확인됨: `repro/stage1_analysis/recompute_tables.json`의 `teacher.compute_time_all.mean`). 즉:

- **모순이 아닙니다.** `legacy_2025/results/teacher/metrics.npz`는 예전에도 지금과 같은(EVADE_L·KEEP_L1·
  RETURN_TO_L2가 있는) 내용이었고, 이전 세션도 이 파일을 찾아서 compute_time을 계산했습니다.
  "19,129와 일치하는 파일 없음"이라는 문장은 **총 샘플 수(18,989 vs 19,129, 140개 차이)**가
  정확히 일치하지 않는다는 뜻이었지, metrics.npz에 상태 다양성이 없었다는 뜻이 아닙니다.
- 사용자가 기억하는 "이전 기록에서는 EVADE_L→KEEP_L1 전이가 있었다"는 진술과 이번 결과는
  **양립합니다.** 다만 그 전이가 있는 것은 `results/**/ep_*/run_*.csv`나 loose csv가 아니라
  **최상위 `metrics.npz` 2개뿐**입니다. csv 쪽(front_gap=NA, KEEP_L2뿐)은 처음부터 별개의,
  장애물이 감지되지 않는 실행이었습니다(3절 참고).

---

## 2. 논문 수치 역검색 (저장소 전체 + 두 zip)

`19129, 19129, 191.3, 10770, 6694, 1263, 0.2143, 56.3, 35.0, 3.71, 5.64` 등 논문 고유 수치로
`.py .json .md .ipynb .log .yaml .ps1` 전수 검색(확인됨: `repro/stage1_analysis/`에 준하는 1회성
검색 스크립트 실행, 저장소 전체 + `code_backup.zip` + `folder_backup.zip` 내부 텍스트 포함).
아주 흔한 숫자(41, 2.1, 402 단독 등)는 오탐이 많아 제외했습니다.

| 수치 | 발견 위치 | 맥락 |
|---|---|---|
| 1.091 / 0.206 | `legacy_2025/analysis.py:70,75`, `legacy_2025/backup/justify_mpc.py:351,392,667` (루트+code_backup 동일) | **하드코딩 상수** ("실제 측정값"이라는 주석은 있으나 이 파일 안에 측정 코드 없음) |
| 19,129 | `legacy_2025/verify/REPORT.md`, `legacy_2025/verify/task3_numeric_verification.py`, `legacy_2025/verify/closed_loop/REPORT_C.md` | **전부 "확인 안 됨"이라고 이전 세션이 이미 결론 낸 기록**. 실제 코드/데이터 파일에서 "19129"라는 문자열 자체는 어디에도 없음(제 재검색도 동일 결과) |
| 3.71 / 5.64 | `legacy_2025/verify/task3_numeric_verification.py`, `legacy_2025/verify/REPORT.md`, `legacy_2025/verify/closed_loop/REPORT_B.md` | 전부 "논문 claim"으로만 인용됨, 이를 만들어낸 원본 계산 코드는 없음. `REPORT_B.md`는 자체 하네스(harness_B)로 재현 시도했으나 **다른 값(outlier 포함 34.789ms 등)**이 나왔다고 기록 |
| 1263 / 6694 / 19129 (숫자 형태) | `legacy_2025/verify/closed_loop/episodes_A.json`, `timing_records_B.json` | **우연히 일치**: `obstacle_x` 값이나 `call_index`가 이 숫자를 우연히 포함하는 것 (예: `"obstacle_x": 1.3127898...` → "1263"과 무관, 자리수 우연 포함). 논문 수치의 출처 아님 |
| 그 외(56.3, 35.0, 0.458, 0.648, 402, 10770 등) | 저장소의 `.py/.json/.md` 어디에도 하드코딩/출력 문자열로 없음 | 즉 이 수치들은 **하드코딩이 아니라 실제 계산 결과일 가능성이 높다는 뜻**이기도 합니다 — 1절에서 `results/*/metrics.npz`를 직접 재계산해서 근접치를 확인했습니다 |

**[정정 2026-09-26]** 아래 "계산시간류(… 3.71/5.64ms) 하드코딩"과 3절·7절·8절의 같은 표현은 일부 값에만 맞는다. 저장소 전체 검색 결과(2026-09-26), 제출본 계산시간 수치 가운데 코드에 상수로 있는 것은 7개뿐이다: 표 8 평균·표준편차·최대 1.091 / 0.152 / 5.747 ms와 표 16 평균·표준편차·최대 0.206 / 0.055 / 1.557 ms(`legacy_2025/analysis.py:70-77`, 1.091·0.206은 `legacy_2025/backup/justify_mpc.py:351`에도), 본문 전체 평균 3.23 ms(`legacy_2025/code_backup/run_hierarchical.py:390-391`, MPC 기준 시간 상수로 사용). 나머지(표 8·16의 중앙값·최소·95/99 백분위, 본문 3.71·5.64 ms·11.3%, 표 18 배수)는 상수도 측정 코드도 찾지 못한 "출처 미발견"이다(표 16 최솟값 0.152는 표 8 표준편차 상수와 숫자만 같음).

**해석**: 계산시간류(1.091/0.206/3.71/5.64ms)는 이전 세션이 이미 "하드코딩, 재현 안 됨"으로
결론 낸 것을 제가 다시 검색해도 그대로였습니다(재확인 완료, 결론 유지). 반면 FSM 상태
분포/오차류(56.3%, 0.458, 0.648 등)는 하드코딩 문자열이 저장소에 없다는 것 자체가 "실제 실행
결과를 손으로 옮겨 적었을 가능성"을 지지하며, 3절의 재계산 결과가 이를 뒷받침합니다.

---

## 3. `metrics.npz`로 논문 표 재계산

전체 수치는 `repro/stage1_analysis/recompute_tables.json`에 있습니다(스크립트: `repro/stage1_analysis/
recompute_tables_from_results.py`, 읽기 전용, 새 시뮬레이션 실행 없음).

| 논문 수치 (페이지) | teacher/metrics.npz 재계산 | student/metrics.npz 재계산 | 판정 | 비고 |
|---|---|---|---|---|
| Table 9 총 샘플 19,129 (p.15) | 18,989 | 18,950 | 근사 (0.7–0.9% 차이) | |
| Table 9 에피소드당 평균 191.3 (p.15) | 189.89 | 189.5 | 근사 | |
| Table 10 EVADE_L 402/2.1% (p.15-16) | 400/2.11% | 400/2.11% | 근사 | |
| Table 10 KEEP_L1 1,263/6.6% (p.16) | 1,256/6.61% | 1,260/6.65% | 근사 | |
| Table 10 KEEP_L2 10,770/56.3% (p.15) | 10,515/55.37% | 10,510/55.46% | 근사 (0.9%p 차이) | |
| Table 10 RETURN_TO_L2 6,694/35.0% (p.16) | 6,818/35.91% | 6,780/35.78% | 근사 (0.9%p 차이) | |
| Table 7 평균속도 0.458±0.048, 최소0.301, 최대0.500 (p.14) | **0.500±0.000 (변동 없음)** | **0.4586±0.0478, 최소0.339, 최대0.500** | **불일치(teacher) / 근사(student)** | 아래 4-3 참고 — Teacher npz의 v는 상수 0.5 |
| Table 7 최소 front_gap 0.648m (p.14) | 0.6500 | 0.6500 | 근사(2mm 차이) | legacy_2025/run_simulation.py 산식 그대로: `2.0-9*0.15=0.65` |
| Table 12 횡방향 위치 위반 0.2143%/41스텝 (p.16) | 미재계산(제약 판정 로직 별도 필요) | 미재계산 | 판정불가 | 2단계에서 판정 기준 정하고 계산 필요 |
| Table 8 계산시간 평균1.091/최대5.747ms (p.15) | 평균1.883 / 최대52.50ms | 평균0.858 / 최대38.31ms | **불일치** | 이전 세션 결론과 일치(재확인됨) |
| 본문 "전체평균3.23/차선변경3.71/EVADE_L최대5.64ms" (p.15) | 차선변경(EVADE_L∪KEEP_L1∪RETURN_TO_L2) 평균1.912, EVADE_L최대31.97 | 차선변경평균1.350, 최대38.31(RETURN_TO_L2) | **불일치** | |
| Table 11 조향각 평균-2.73/std6.79/최소-12.44/최대24.99 (p.16) | 평균0.039/std6.79/최소-24.97/최대24.24 | 평균-2.60/std6.94/최소-12.59/최대24.998 | **student가 더 근접**, teacher 불일치(평균·최소) | |

**핵심 불일치 3가지**:
1. **teacher/metrics.npz의 속도(v)가 전부 정확히 0.5로 고정**(표준편차 0)입니다. 그런데 논문
   Table 7·11(둘 다 "Teacher 정책 성능" 절에 있음)이 보고하는 0.458±0.048/최소0.301/최대0.500은
   **teacher가 아니라 student/metrics.npz 값과 훨씬 가깝습니다** (student 재계산: 0.4586±0.0478/
   0.339/0.500). 논문 자체의 **그림3 "Velocity Comparison" 히스토그램도 Teacher를 0.50m/s의
   뾰족한 단일 스파이크로 그리고 있어**(p.19, 이미지로 확인), teacher v가 상수라는 이번 재계산과
   정합적입니다. → **Table 7·11의 속도 통계가 실제로는 student 쪽 파일(또는 그와 유사한 실행)에서
   나왔거나, teacher 쪽 "v" 필드가 목표속도(명령값)만 기록하고 실제 속도를 따로 기록하지
   않았을 가능성이 있습니다.** → **논문 라벨 불일치, 원인 판정불가로 기록합니다** (사실 근거는
   위 표의 수치 비교와 그림3 히스토그램뿐이며, 더 이상 원인을 추정하지 않습니다).
2. **조향각 평균값**: 논문은 -2.73°(우측 편향)인데 teacher 재계산은 +0.039°(거의 대칭)이고
   student 재계산이 -2.60°로 논문에 더 가깝습니다. 표 11도 "Teacher" 표로 되어 있는데 student
   쪽이 더 잘 맞는 동일한 패턴입니다.
3. **계산시간류는 전부 불일치** — 이미 이전 세션이 결론 낸 "재현 불가, 하드코딩 추정"과
   이번 재계산도 일치합니다(재확인 완료).

---

## 4. 장애물 0.5–2.0m 추적

모든 시뮬레이터/주입 생성기의 거리 관련 난수·프로파일 (전부 확인됨, 파일 열람+grep):

| 파일 | 메커니즘 | 범위/수식 | 논문 "0.5–2.0m"과 관계 |
|---|---|---|---|
| `legacy_2025/code_backup/simulator_original.py:52` | 물리 장애물 x좌표 균등분포 | U(1.5, 2.5)m | 다름 |
| `legacy_2025/code_backup/simulator.py:52` | 물리 장애물 x좌표 균등분포 | U(2.5, 4.0)m | 다름 |
| `legacy_2025/run_simulation.py:37`(루트=code_backup 동일), `RandomScenarioGenerator.generate_episode()` | **주입 front_gap**을 10 step에 걸쳐 선형 감소 | `gap = max(0.5, 2.0 - k*0.15)`, k=0..9 → 2.00,1.85,...,0.65m (바닥 0.5는 산식상 존재하나 10 step 안에서는 도달 안 함, 실측 최소값은 0.65) | **가장 유력한 실제 출처** — 아래 설명 |
| `legacy_2025/run_simulation.py:27,49,62,72` | 다른 국면(정상 주행/복귀)의 주입 front_gap | U(5.0,10.0)m, U(3.0,8.0)m | 장애물 회피 트리거와 무관한 구간 |
| `legacy_2025/code_backup/run_teacher.py:53`(자칭 "ORIGINAL parameters") | 물리 장애물 x좌표 | print만: "1.5-2.5m (original)" | `simulator_original.py`와 동일 range를 가리킴 |
| `legacy_2025/backup/test_teacher_mpc.py:101`(루트, 논문 이후 검증 스크립트로 이미 분류됨) | 물리 장애물 x좌표 | U(1.2, 2.0)m (177행 print은 "2.5,4.0"이라고 표시 — 파일 내부 모순) | 다름, 애초에 논문 이후 스크립트 |

**논문 서술이 물리 장애물 위치가 아니라 주입 front_gap 범위일 가능성 — 확인됨(강한 근거)**:

1. 논문 Table 7의 "최소 front_gap 0.648m"(p.14)은 `legacy_2025/run_simulation.py`의 감소식
   `2.0 - 9×0.15 = 0.65m`(10 step 반복문의 마지막 값)과 **2mm 차이**로 사실상 일치합니다
   (확인됨: teacher/student metrics.npz 재계산 결과 둘 다 정확히 0.6500m, 3절 참고).
   물리 장애물 x좌표 방식(simulator.py류)에서는 최소 front_gap이 초기 obstacle_x와 차량
   진행 속도·정지 시점에 좌우되는 연속값이라 이렇게 딱 떨어지는 계단식 최소값이 나오지 않습니다.
2. `legacy_2025/run_simulation.py`의 스크립트는 "장애물의 물리적 위치"라는 변수 자체가 없고, front_gap이라는
   **센서값(거리)** 을 직접 만들어 주입합니다. 논문이 "장애물의 위치는 0.5m–2.0m 균등분포"라고
   쓴 것은, 실제로는 이 **주입 front_gap의 시작–바닥 범위(2.0m→0.5m)** 를 "장애물 위치 범위"로
   잘못 서술했을 가능성이 높습니다.
3. 다만 완전히 들어맞지는 않습니다: 논문은 "초기 속도(0.3–0.5m/s) 무작위 설정"이라고도 쓰는데,
   `RandomScenarioGenerator`는 `v: random.uniform(0.4, 0.6)`을 씁니다(확인됨: `legacy_2025/run_simulation.py:27`
   등) — **0.3–0.5가 아니라 0.4–0.6입니다.** 이 부분은 논문 서술과 코드가 또 다르게 어긋납니다.

**결론**: "물리 장애물 위치설"은 반박됩니다(코드에 그런 변수가 없음). "front_gap 주입 범위설"은
front_gap 최소값 일치로 뒷받침되지만, 초기 속도 범위 불일치가 있어 **완전한 확인은 아니고 유력한
가설**입니다.

---

## 5. 그림 대조

| 논문 그림 | 페이지 | 서브플롯 제목(이미지 확인) | 저장소 파일(추정 매칭) | 생성 스크립트(확인됨: `savefig` 경로 일치) |
|---|---|---|---|---|
| 그림 1. Teacher 정책의 차선변경 궤적 예시 | 14 | "Trajectory Comparison (Sample Episode)" | `legacy_2025/figures/trajectory_comparison.png` | `legacy_2025/analysis.py:238` → `savefig(...,'trajectory_comparison.png')`, `results/{mode}/metrics.npz` 로드(`legacy_2025/analysis.py:14`) |
| 그림 2. MPC 성능 종합 분석 | 18 | State/Steering Angle/Velocity/Front Gap/Lateral Position Distribution, Avg Steering by State, Steering·Velocity Constraint Violations, Heading Angle Distribution (9개, 제목까지 완전 일치) | `legacy_2025/figures/mpc_performance_analysis.png` | `legacy_2025/analyze_mpc.py:233` → `savefig(...,'mpc_performance_analysis.png')` |
| 그림 3. Teacher와 Student 제어 비교 | 19 | Steering Angle/Velocity/Lateral Position Comparison, State-wise RMSE Comparison (4개, 제목 완전 일치) | `legacy_2025/figures/teacher_student_comparison.png` | `legacy_2025/analyze_mpc.py:317` |
| (논문에 없음) | - | Controller Selection, Dataset Size Comparison, Steering/Velocity Rate Distribution, Cumulative Control Effort, Teacher Tracking Error, Student Preserves..., Computation Time Comparison(5.3x) | `mpc_justification.png`(루트/`code_backup`/`legacy_2025/figures/`) | `legacy_2025/backup/justify_mpc.py:447` — **논문 본문 그림 목록(그림1–3)에 없음. 논문 외 용도(발표자료 등)로 추정** |
| (논문에 없음) | - | State/Velocity/Lane Error/Front Gap/TTC/Left Lane/Steering/Target Velocity Distribution | `legacy_2025/analysis/dataset_analysis.png` | `legacy_2025/code_backup/analyze_dataset.py` |
| (논문에 없음, Table 12로 텍스트만 제시) | - | 제약 위반 시각화 | `legacy_2025/constraint_analysis/constraint_analysis.png` | `legacy_2025/backup/constraint_analysis.py:317` |
| (논문에 없음) | - | 학습 손실 곡선 | `legacy_2025/models/training_curves.png`, `legacy_2025/models/training_history.png` | `legacy_2025/analysis.py:207` (`training_curves.png`), 별도 학습 스크립트가 `training_history.png` 생성 추정 |

**요약**: 논문에 실제로 번호가 매겨져 실린 그림은 3개(그림1–3)뿐이고, 전부 `legacy_2025/analysis.py` +
`legacy_2025/analyze_mpc.py` 두 스크립트가 `results/{teacher,student}/metrics.npz`를 읽어 생성합니다. 이는
3절의 결론(두 metrics.npz가 논문 수치의 가장 유력한 데이터 소스)과 다시 한번 정합적입니다.
`legacy_2025/backup/justify_mpc.py`, `analyze_dataset.py`, `legacy_2025/backup/constraint_analysis.py`의 출력은 논문 본문에는 없습니다.

---

## 6. 결론 (누락분 보완)

### zip 파일 정체

- **`code_backup.zip`**: `legacy_2025/code_backup/` 폴더의 스냅샷입니다. 내부 mtime 범위 2025-10-14–
  2025-12-04 04:34(확인됨: `unzip -l`), `legacy_2025/final_hierarchical_backup_thesis_1204.py` 항목이
  2025-12-04 04:17로 **논문 제출일(2025.12.04)과 같은 날**입니다. 예외적으로 `runcode.json`
  1개만 2026-05-07 15:21인데 내용이 IDE 확장 기본 템플릿이라 다른 파일 수정 시점의 증거로
  쓸 수 없습니다(확인됨).
- **`folder_backup.zip`**: 964개 항목, 17MB. 내부 mtime 2025-10-04–2026-05-07까지 넓게 분포
  (확인됨: `unzip -l`). `test_sim/` 등 `code_backup.zip`에 없는 폴더도 포함되어 있어, **더 넓은
  범위(여러 시점에 걸친) 개발 폴더 전체 백업**으로 추정됩니다. 상세 파일별 대조는 이번에도
  하지 않았습니다(필요하면 요청 바랍니다 — 964개 전수 조사는 시간이 걸립니다).

### 실험 당시 코드 추정

| 파일 | 판정 | 근거 |
|---|---|---|
| `legacy_2025/run_simulation.py`(루트=code_backup 동일) | **확인됨** — `legacy_2025/results/teacher\|student/metrics.npz`를 만든 코드 | 저장 스키마(`y,psi,delta,v,state,front_gap,loop_time,compute_time,episode,success`)가 `legacy_2025/run_simulation.py:262-273`의 `np.savez` 호출과 정확히 일치 |
| `final_hierarchical_backup.py` (FSM+MPC 본체, `legacy_2025/run_simulation.py`가 `import *`) | **확인됨(7절에서 확정)** — cooldown_ok/EVADE_L 예외가 **없는** code_backup 12-04 버전과 동일 | 7절: FSM 전이 간격 실측 + `.pyc` 헤더의 소스 mtime/size 대조 |
| `legacy_2025/analysis.py`, `legacy_2025/analyze_mpc.py` | **확인됨** — 논문 그림1–3을 생성한 스크립트 | 5절, savefig 경로 완전 일치 |
| 루트 `legacy_2025/final_hierarchical_backup_modified_2026.py`(현재본, cooldown_ok+EVADE_L 예외 포함) | **확인됨: 논문 제출 이후 수정본** | code_backup 스냅샷(12-04, 제출일과 동일) 대비 diff (STAGE1_FACTS.md 3절) |
| `run_experiments.py` + `--random_env` 경로 | **확인됨: 논문 데이터와 무관** | front_gap 항상 NA, KEEP_L2 고정 (1절) |
| `run_teacher.py`("ORIGINAL parameters") | **확인됨: 논문 최종판과 다른 파라미터(G_TRIG=1.0 등)** — 더 이른 시점의 실험 스크립트로 추정 | `legacy_2025/code_backup/run_teacher.py:25` |
| `collect_evade_dataset.py` + `lane_change_mpc_final_complete.py --test` | **확인됨: 논문 데이터와 무관**(고정 시나리오 6개, 무작위 아님) | `legacy_2025/code_backup/collect_evade_dataset.py:37-44` |

### 논문 결과표의 데이터 출처 추정

**센서 주입**입니다 (물리 시뮬레이션 아님) — 확인됨(3·4절). `legacy_2025/run_simulation.py`의
`RandomScenarioGenerator`는 kinematic bicycle model로 차량을 물리적으로 움직이며 장애물과의
거리를 계산하는 것이 아니라, FSM 상태별 구간(정상주행 30step→회피트리거 10step→KEEP_L1
40–60step→복귀 40step→정상주행)을 미리 스크립트로 짜 놓고 `front_gap`/`y`/`v` 값을 매 스텝
직접 주입합니다(확인됨: `legacy_2025/run_simulation.py:19-77`, `app.pose.y = sensor_data['y']` 등 대입문).
FSM+MPC 자체는 진짜로 동작하지만(그래서 δ, 제약만족률 같은 "제어기 출력" 지표는 신뢰할 만함),
"장애물이 무작위 위치에 있고 차량이 물리적으로 접근한다"는 논문의 실험 설계 서술과는 다른
메커니즘입니다.

### PDF와 코드가 다른 항목 수, 가장 큰 차이 3개

**정정(2026-09-17, `PDF_VS_CODE.md` 3차 재검증 후 최종)**: FSM 전이 조건을 코드 3단계 추적
(`legacy_2025/run_simulation.py`의 `ey_line` 주입이 `LineTraceSensor`에 실제로 닿지 않는 죽은 대입임을
확인, `PDF_VS_CODE.md` EVADE_L→KEEP_L1 행 참고)까지 마친 결과: **EVADE_L→KEEP_L1은 A=PDF
일치로 확정**(중간에 불일치로 오판했던 것을 재정정), **RETURN_TO_L2→KEEP_L2만 A·B·C 전부 PDF와
다름**(임계값 0.08 vs 0.20, 헤딩각 조건 누락)으로 확정되었습니다. 전 항목 표와 최종 개수는
`PDF_VS_CODE.md`("요약" 절)를 기준 문서로 삼습니다. 이 문단은 발견 경위 기록으로 남깁니다.

이번 라운드에서 확인한 "PDF 서술과 코드가 다른 항목"은 최소 **6건**입니다: (1) SAFE_STOP의
EVADE_L 예외(루트만, **논문 제출 이후 수정 — 규칙 1에 따라 판정 기준은 PDF Table 2로 확정**,
아래 참고), (2) cooldown_ok가 실제 데이터 생성 당시 코드에는 **없었음**(7절에서 확정), (3) 장애물
위치 서술 vs 실제 front_gap 주입 메커니즘, (4) 초기 속도 범위 0.3–0.5 vs 코드 0.4–0.6
(`legacy_2025/run_simulation.py`), (5) Table 7·11의 Teacher 속도/조향각 평균이 실제로는 teacher보다 student
npz에 더 가까움(원인 판정불가), (6) 계산시간류(1.091/0.206/3.23/3.71/5.64ms)가 하드코딩이고
재계산 값(1.88/0.86/1.91/1.35ms 등)과 다름. **(7)–(8) 추가 확인됨**: EVADE_L→KEEP_L1은 A조차
PDF에 없는 `\|ey_line\|<0.04` 분기가 실제로 작동하고, RETURN_TO_L2→KEEP_L2는 A·B·C 전부 임계값
(0.08 vs PDF의 0.20)과 헤딩각 조건 누락에서 PDF와 다릅니다(`PDF_VS_CODE.md` 참고).

> **SAFE_STOP 판정 기준 결정(사용자 확정, 2025-09-17)**: 설정값 선택 규칙 1번("제출 PDF에 명시된
> 값·조건·동작이 있으면 그것을 채택한다")을 적용합니다. **PDF Table 2(모든 상태 → SAFE_STOP,
> 예외 없음) + (3)번 쿨다운 서술을 판정 기준으로 확정**합니다. 즉 2단계 구현에서는 루트의
> EVADE_L 예외를 제거하고 쿨다운은 Table 2의 모든 전이에 일관 적용하는 방향입니다. **구현은
> 2단계에서 진행**하며, 이번 1단계에서는 결정 사실만 기록합니다.

**가장 큰 차이 3개**:
1. **계산시간 전부**(논문 1.091ms 평균 vs 재계산 1.88ms, 4배 이상 차이 나는 항목도 있음) —
   근거 없는 하드코딩으로 이미 이전 세션이 결론, 이번 세션도 재확인.
2. **Teacher 속도/조향각 통계가 실제로는 teacher metrics.npz(상수 0.5, 대칭적 조향각)와 안
   맞고 student metrics.npz와 더 가깝다**는 점 — 논문 자체 그림3(Velocity Comparison)이 이
   불일치를 시각적으로도 보여줌.
3. **"장애물 위치 0.5–2.0m 균등분포"라는 실험 설계 서술 자체가 실제 코드 메커니즘(스크립트형
   front_gap 주입)과 근본적으로 다름** — 물리적 무작위 장애물 배치가 아니라 결정론적 구간
   스케줄에 각 구간 길이만 무작위인 구조.

---

## 7. 실험 당시 FSM 버전 판정 (A)

읽기 전용 스크립트: `repro/stage1_analysis/analyze_fsm_transitions.py` → `repro/stage1_analysis/fsm_transition_analysis.json`.
`legacy_2025/results/teacher/metrics.npz`, `legacy_2025/results/student/metrics.npz`의 `episode`/`state`를 이용해 에피소드별
상태 전이 시점 간격(스텝 차이 × dt=0.05)을 계산했습니다.

| 전이 종류 | 최소 간격(s) | 평균 간격(s) | 0.3s 미만 건수(전체 100건 중) |
|---|---|---|---|
| KEEP_L2 → EVADE_L (teacher) | 1.80 | 2.31 | 0 |
| **EVADE_L → KEEP_L1 (teacher)** | **0.20** | 0.20 | **100 / 100** |
| KEEP_L1 → RETURN_TO_L2 (teacher) | 0.60 | 0.63 | 0 |
| RETURN_TO_L2 → KEEP_L2 (teacher) | 2.90 | 3.41 | 0 |
| KEEP_L2 → EVADE_L (student) | 1.80 | 2.33 | 0 |
| **EVADE_L → KEEP_L1 (student)** | **0.20** | 0.20 | **100 / 100** |
| KEEP_L1 → RETURN_TO_L2 (student) | 0.60 | 0.63 | 0 |
| RETURN_TO_L2 → KEEP_L2 (student) | 2.85 | 3.39 | 0 |

**EVADE_L→KEEP_L1 전이가 두 파일 모두, 100개 에피소드 전부에서 예외 없이 정확히 0.2초**(=쿨다운
0.3초보다 짧음)만에 일어납니다. 루트 코드(cooldown_ok 버전)라면 `arrived_l1` 조건이 참이어도
`cooldown_ok`(상태 진입 후 0.3초 경과)가 거짓이면 전이가 지연되어 최소 간격이 0.3s 이상이어야
합니다. 0.2s가 100/100건에서 나타난다는 것은 **쿨다운 게이트가 아예 걸려 있지 않은 버전**이었다는
뜻입니다. → 8절의 `.pyc` 헤더 증거와 합쳐 **확인됨**으로 판정합니다.

**SAFE_STOP / EVADE_L 예외 검증 — 판정불가**: `state=='SAFE_STOP'`인 샘플은 teacher·student 둘 다
0개이고, `EVADE_L` 상태에서 `front_gap<0.20`인 샘플도 0개입니다(npz에 `left_clear` 키 자체가
없어 그 조건은 아예 확인 불가). `legacy_2025/run_simulation.py`의 스크립트형 시나리오는 EVADE_L 구간의
front_gap 바닥이 0.65m(4절)라서 SAFE_STOP 트리거 조건(front_gap<0.20)에 애초에 도달하지
않습니다. **따라서 "EVADE_L이 SAFE_STOP에서 예외 처리되는지"는 이 데이터만으로는 검증할 방법이
없습니다 — 판정불가.**

**결론**: cooldown_ok 미적용 = **확인됨**. EVADE_L의 SAFE_STOP 예외 여부 = **판정불가**(이 데이터로는
테스트된 적이 없는 경로).

---

## 8. `metrics.npz` 원본 여부 (B)

두 zip 안에서 `metrics.npz`, `legacy_2025/run_simulation.py`, `final_hierarchical_backup.py`를 찾아 현재
파일과 SHA-256으로 대조했습니다(확인됨, 파일 자체는 원본 zip을 읽기만 함 — 추출본은
`repro/stage1_analysis/scratch_dec3_extract/`, `repro/stage1_analysis/_pyc_check/`에만 저장).

| 파일 | zip 내 위치/날짜 | 현재 파일과 비교 |
|---|---|---|
| `legacy_2025/results/student/metrics.npz` | `folder_backup.zip`, **2025-12-03 14:02:08**, 2,124,860B | **SHA-256 완전 일치** → 현재 파일 = Dec-3 원본, 한 번도 덮어써지지 않음 |
| `legacy_2025/results/teacher/ep_008/metrics.npz` | `folder_backup.zip`, 2025-12-03 02:51:18, 6,909B | **SHA-256 완전 일치** → Dec-3 원본 그대로 |
| `legacy_2025/results/teacher/metrics.npz` | `folder_backup.zip`, **2026-05-07 14:18:50**, 2,129,228B | **SHA-256 완전 일치** → 현재 파일 = **2026-05-07 재실행분**. Dec-3 원본은 이 zip에도, `code_backup.zip`에도 없음 — **원본은 소실된 것으로 판단** |
| `legacy_2025/run_simulation.py` | `code_backup.zip`, 2025-12-03 13:57:58, 10,414B | 줄바꿈(LF↔CRLF) 차이만 있고 **내용 100% 동일**(`diff --strip-trailing-cr` 결과 없음) → Dec-3 이후 **한 글자도 수정된 적 없음** |
| `final_hierarchical_backup.py` | `code_backup.zip`, 2025-12-04 04:17:58, 97,747B | 루트 현재본(100,254B, cooldown_ok 포함)과 다름 — 이미 STAGE1_FACTS.md 3절에서 확인 |
| `__pycache__/final_hierarchical_backup.cpython-39.pyc` | `folder_backup.zip`, **2026-05-07 14:15:36** | **디코딩 결과: 소스 mtime=2025-12-04 04:17:59, 소스 크기=97,747B** — 즉 2026-05-07 14:15에 컴파일된 이 캐시가 가리키는 소스는 **Dec-4 04:17 버전(97,747B)과 정확히 일치**, 현재 루트의 100,254B 버전이 아님 |

**타임라인 재구성(확인됨)**:
1. 2025-12-04 04:17:59 — `final_hierarchical_backup.py`가 97,747B로 저장됨(코드백업 스냅샷과 동일, cooldown_ok 없음). 논문 제출일(2025.12.04)과 같은 날.
2. 2025-12-03(전날 기록이지만 파일 자체는 이 버전 계열) — `legacy_2025/run_simulation.py` + 이 컨트롤러로 `legacy_2025/results/student/metrics.npz`, `legacy_2025/results/teacher/ep_008/metrics.npz` 생성. (teacher의 최상위 metrics.npz도 이때 원래 있었을 것으로 추정되나 원본은 소실)
3. **2026-05-07 14:15:36–14:18:50** — 누군가 **같은(97,747B, cooldown 없는) `final_hierarchical_backup.py`와 한 글자도 안 바뀐 `legacy_2025/run_simulation.py`**로 teacher 쪽만 다시 실행 → `legacy_2025/results/teacher/metrics.npz`, `run_1778131088.csv` 갱신. **이때 기존 Dec-3 teacher metrics.npz가 덮어써져 소실됨.**
4. 2026-05-07 이후 ~ 오늘(2026-09-17) 사이 — 루트 `legacy_2025/final_hierarchical_backup_modified_2026.py`가 100,254B로 수정되어 cooldown_ok·EVADE_L 예외가 추가됨(정확한 날짜는 특정 불가 — 이 구간의 스냅샷이 없음).

**"Teacher npz가 2026-05-07 이후 실행으로 덮어써졌다"는 이전 세션 기록 — 확인됨**(정확히는
"이후"가 아니라 "2026-05-07 그 실행 자체"). 원본(Dec-3) teacher metrics.npz는 두 zip 어디에도
없어 **복구 불가**로 판정합니다.

---

## 9. 추가 확인 — seed 고정 여부 / `.pyc` 바이트코드 대조 강화

### 9-1. seed 고정 여부

`np.random.seed(`, `random.seed(` 두 패턴 모두로 `legacy_2025/run_simulation.py`(루트=code_backup 동일)와
`legacy_2025/final_hierarchical_backup_modified_2026.py`(루트·code_backup 둘 다) 전체를 grep했습니다 — **매치 0건**
(확인됨). `legacy_2025/backup/test_teacher_mpc.py`도 동일하게 0건입니다. 즉 A(`legacy_2025/run_simulation.py`)도, C
(`legacy_2025/backup/test_teacher_mpc.py`)도 **seed를 고정하지 않습니다.**

**판단**: `legacy_2025/run_simulation.py`의 `RandomScenarioGenerator`는 에피소드마다 `evade_duration =
random.randint(40, 60)`(20 step 폭), `obstacle_start = random.randint(30, 50)`(20 step 폭) 등
여러 난수를 씁니다. 100 에피소드에 걸쳐 이 정도 폭의 난수가 누적되면 총 샘플 수가 수백 개
단위로 흔들리는 것은 자연스럽습니다 — **18,989 vs 19,129(140개, 0.7% 차이)는 "같은 코드의
다른 실행(시드 없음)"으로 설명 가능한 범위**라고 판단합니다(단정은 아니고, 재실행해서 분포
폭을 실측하기 전까지는 판단 수준의 결론입니다).

### 9-2. `.pyc` 바이트코드 대조 강화

기존(1차 조사)에는 `.pyc` 헤더의 소스 mtime/size만 대조했습니다. 이번에는 **같은 Python
버전으로 직접 컴파일해서 코드 객체 바이트를 비교**했습니다.

- `.pyc`를 만든 Python 버전: **CPython 3.9**(매직넘버 `0x0a0d0d61`, 파일명 `cpython-39`). 이
  세션에서는 `py -3.9`(Python **3.9.13**, Windows py launcher로 확인)를 사용해 재컴파일했습니다.
  원본이 정확히 3.9.13인지, 다른 3.9.x 패치 버전인지는 알 수 없습니다(매직넘버는 minor 버전까지만
  구분).
- `legacy_2025/final_hierarchical_backup_thesis_1204.py`를 `py -3.9 -m py_compile`로 컴파일(최적화 없음,
  `folder_backup.zip`의 `.pyc`와 동일하게 flags=0)하되, 원본 `.pyc`에서 발견한 소스 경로
  `C:\Users\user\MPC_LINETRACING\final_hierarchical_backup.py`를 `dfile`로 지정해 co_filename을
  맞췄습니다(추출 파일: `repro/stage1_analysis/_pyc_check/`).
- 결과: **파일 크기 완전 일치(61,788바이트 = 61,788바이트)**. 코드 객체 바이트를 처음부터
  끝까지 비교한 결과 **61,772바이트 중 단 한 곳**(offset 7011)만 다릅니다 — `daemon`이라는
  문자열 하나의 marshal 인터닝 플래그 비트(`Z` vs `\xda`, "이미 나온 문자열을 재사용하는지"
  표시 비트) 차이이고, 명령어·상수·문자열 내용 자체는 100% 동일합니다.

**판정**: 소스 코드가 100% 동일하지 않다면 이렇게 거의 완전히 같은 바이트열이 나올 수 없습니다
(문자열 하나 다르면 상수 테이블 크기·이후 오프셋이 전부 밀립니다 — 실제로는 안 밀렸습니다).
그러나 요청하신 이분법(확인됨 / 크기·mtime 정황) 중 어느 쪽에도 100% 맞지는 않아 **중간 등급으로
격상**합니다: **"확인됨(바이트 수준 정합, 완전한 비트 일치는 아님)"**. 남은 1비트 차이는 원본과
이 세션의 Python 3.9 패치 버전이 다를 가능성으로 추정합니다(패치 버전 간 marshal 인터닝
알고리즘 미세 차이) — 소스 코드 차이가 원인일 가능성은 사실상 배제합니다.

---

## 10. 최종 결론

- **zip 파일 정체**: `code_backup.zip`=2025-10-14–12-04 개발 스냅샷(`legacy_2025/code_backup/`와 거의 동일,
  49개 파일). `folder_backup.zip`=2025-10-04–2026-05-07까지 걸친 훨씬 넓은 범위의 개발 폴더
  전체 백업(964개 항목, `legacy_2025/results/`·`__pycache__`·`test_sim/` 등 포함) — 이번 조사로 최소
  2026-05-07 재실행 이후 시점까지 담고 있음이 확인됨.
- **논문 결과 데이터 출처**: `legacy_2025/run_simulation.py`(스크립트형 센서 주입) + 당시 `final_hierarchical_backup.py`
  (97,747B, cooldown 없음, EVADE_L 예외 없음) — **확인됨** (스키마 일치 1절, FSM 전이 간격 7절,
  `.pyc` 소스 서명 8절). 다만 총 샘플수 등 정확한 수치까지 재현되지는 않음(근사, 3절) — **확인 수준:
  "메커니즘·코드 버전은 확인됨, 수치 단위 완전 재현은 안 됨."**
- **실험 당시 FSM 버전 판정**: cooldown_ok/EVADE_L 예외가 **없는** 버전 — **확인됨**(7·8절 이중 근거).
- **`metrics.npz` 원본 여부**: student·ep_008은 Dec-3 원본 그대로(SHA-256 일치), **teacher 최상위
  파일은 2026-05-07 재실행분으로 원본이 아니며, Dec-3 원본은 두 zip 어디에도 없어 복구 불가** —
  **확인됨**.
- **PDF와 코드가 다른 항목 수**: `PDF_VS_CODE.md`(22개 항목 전수 대조, 2026-09-17 3차
  재검증 최종판) 기준 **A=PDF 불일치 6건 + 해석 갈림 1건**(FSM 전이 조건은 RETURN_TO_L2→
  KEEP_L2 1건만 해당 — EVADE_L→KEEP_L1은 재검증 끝에 "일치"로 확정됨). 상세·근거는
  `PDF_VS_CODE.md`를 기준 문서로 참고하십시오. **가장 큰 차이 3개**:
  (1) 계산시간류 전부(1.091ms vs 재계산 1.88ms 등, 하드코딩), (2) Table 7·11 "Teacher" 속도·조향각
  통계가 실제 teacher 데이터(속도 상수 0.5)보다 student 데이터와 훨씬 가까움(원인 판정불가),
  (3) "장애물 위치 0.5–2.0m 균등분포"라는 서술이 실제로는 결정론적 스크립트 구간에 각 구간
  길이만 무작위인 front_gap 주입 메커니즘을 가리키는 것으로 추정됨(초기속도 범위는 여전히 불일치).
- **한 줄 요약**: 논문 VI장의 수치는 **물리 폐루프(장애물을 실제로 감지·회피하는 kinematic
  시뮬레이션) 검증이 아니라, FSM 상태 구간을 미리 스크립트로 짜 놓고 센서값(front_gap/y/v)을
  직접 주입한 뒤 그 위에서 실제 FSM+MPC 컨트롤러를 돌린 결과입니다.**

---

## 다음 단계 전 확정 필요 사항 (2단계-A용, 지금 결정하지 않음)

**해결된 항목(2025-09-17 사용자 답변으로 종결, 재질문 안 함)**:
- Table 7·11 "Teacher" 속도/조향각 라벨링 불일치 → **논문 라벨 불일치, 원인 판정불가로 기록**
  (근거는 9절 "논문 결과 데이터 출처"와 3절 표에 정리됨. teacher/student 어느 쪽을 "정답"으로
  볼지 더 이상 판단하지 않음).
- SAFE_STOP의 EVADE_L 예외 + cooldown_ok → **설정값 선택 규칙 1 적용, PDF Table 2(모든 상태
  예외 없음)+쿨다운 서술을 판정 기준으로 확정**. 구현은 2단계에서.
- `folder_backup.zip` 964개 전수조사 → 하지 않음. 표적 조사(8절)로 필요한 사실은 확인됨.

**남은 항목**:
- `legacy_2025/run_simulation.py`의 초기속도 범위(0.4–0.6)를 논문 서술(0.3–0.5)에 맞출지, "실험 당시
  코드"(이제 확인됨, 7·8절)의 값을 그대로 채택할지 — 2단계-A 설정값 결정표에서 다룰 사항.
