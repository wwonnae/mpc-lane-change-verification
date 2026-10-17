# 5단계: 영향 분석 — 저장된 평가 결과 점검, 설계 주장 대조, mutation 조건

작성: 2026-10-14. 읽기만 했고 재실행은 하지 않았다. 저장된 결과 파일은 수정하지 않았다.
표기: **[확인-파일]**, **[확인-실행]**(이 run6_cause 실험), **[추정]**.

## 1. 저장된 평가 결과에 지문 규칙 적용

### 1-1. 판정 방법 — 저장 결과에는 solve별 status·iter가 없다

- 지문 규칙(STATIC_ANALYSIS §3-3)은 solve마다 status와 iter가 있어야 적용할 수 있다.
  - **[정정 2026-10-14, S6]** §3-3 규칙에는 k=1 절단이 "solved, iter 0"으로 보고되는 빈틈이 있었다. "solved & iter==0"을 더한 안 B로 고쳤다(STATIC_ANALYSIS §3-3 정정 블록, raw/S6_fingerprint_check/).
    - 이 문서의 결론은 바뀌지 않는다. 아래 판정은 지문이 아니라 "compute_ms < 45 ms면 절단 불가"라는 필요조건에 기대기 때문이다.
    - 이 문서와 README에 적은 절단 31건, 감시 누락 9건의 수치도 그대로다. S1~S4에 "solved, iter 0"은 0건이었다.
  저장된 평가 결과에는 이 정보가 대부분 없다.
  - **[확인-파일]** `notable_step_log`는 status가 "maximum iterations reached"/"run time limit reached"이거나 허용오차를 넘은 스텝만 남긴다(DESIGN_IMPROVED_V2 §1-3).
  - 따라서 "solved"/"solved inaccurate"로 보고된 절단은 남지 않는다.
- 그래서 **필요조건**으로 판정했다.
  - time_limit 절단은 그 solve의 OSQP `run_time`이 0.045 s 이상일 때만 일어난다(osqp_api.c:743-757).
  - 저장된 solve 시간 `compute_ms`는 이 run_time의 상한 역할을 한다.
- **compute_ms가 run_time의 상한인 이유 [확인-파일]:**
  - `improved/mpc.py:346`에서 `t_start`를 잰다.
  - 그 뒤 `:404`에서 `prob.update(...)`, `:405`에서 `prob.solve(...)`를 부른다.
  - `:453`/`:464`에서 `compute_ms`를 계산한다.
  - mpc.py 안의 `prob.update` 호출은 `:404` 하나뿐이다(grep).
  - OSQP의 run_time은 "직전 solve 이후의 update 시간 + solve 시간"이다. 둘 다 이 측정 구간 안에 들어가므로 **compute_ms ≥ run_time**이다.
  - 따라서 **compute_ms < 45 ms인 solve는 time_limit으로 끊겼을 수 없다.**
- **예외 — 인스턴스의 첫 solve [확인-파일]:**
  - 첫 solve의 run_time에는 setup 시간이 들어간다.
  - setup(`mpc.py:157`, 생성자)은 측정 구간 밖이다.
  - 그래서 첫 solve만은 compute_ms로 상한을 줄 수 없다.
  - **[추정]** 정상 setup 시간은 약 0.12 ms(래퍼 기록)다. 그 짧은 구간에 수십 ms의 정지가 겹쳐야 하므로 가능성은 매우 낮지만, 배제하지는 못한다.

### 1-2. 결과 [확인-파일]

| 저장 결과 | time_limit 0.045가 걸린 구성 | solve 수 (전수 기록 여부) | 최대 compute_ms | ≥45 ms | `time_limit_count`/hits |
|---|---|---|---|---|---|
| `results/eval_v2/20260924_214446_DESKTOP-MDCKRJS` (eval 2회차, 커밋 16e108b) — new_eval v2 | v2(I5=972) | 288,068 (전수, `mpc_solve_ms_all`) | **32.33** | **0** | 0 |
| 같은 파일 legacy_continuity v2 | v2 | 288,156 (전수) | **34.96** | **0** | 0 |
| 같은 파일 v1 (new / legacy) | 없음(time_limit 1e10) | 288,005 / 288,134 | 37.40 / 33.75 | 0 / 0 | 0 |
| `results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval/diag_timing.csv` | V2_MPC_FLAGS(I5 on, `anomaly/config.py:13-15`) | 6,600 에피소드(에피소드별 최대만) | **6.375** | **0** | 0 |
| `results/dev_ablation_i5/20260924_205916_DESKTOP-MDCKRJS_full` (dev, 참고) | +I5 4후보 | 에피소드별 최대 | 24.35 | 0 | 0 |

- **결론 [확인-파일 + 위 근거]:**
  - eval 2회차 v2와 anomaly closed-loop eval에서는 첫 solve를 뺀 모든 solve가 45 ms 미만이었다.
  - 그러므로 **time_limit 절단은 일어날 수 없었다.**
  - 이 두 평가의 v2 결과는 time_limit을 끈 조건(A)에서도 같았을 것이다. 근거는 S3다. 절단이 없는 회차에서 orig와 A의 서명은 비트 단위로 같았다(i5 `374d…`, i4 `5623…`/`697b…`/`5b83…`, base `534c…`, S3_RESULT.md).
- **점검하지 못한 것 (한계):**
  - eval_v2의 S3 격자(`s3_grid_new_v2.json`, `s3_grid_legacy_v2.json`)에는 solve 시간이 없다. 결과 격자만 있어 점검할 수 없다.
  - `results/i4_student_v2/20260925_092109_DESKTOP-MDCKRJS`에도 solve 시간이 없다. 여기에는 Teacher 데이터셋 생성(TEACHER_FLAGS, I5 on)과 eval3 폐루프 MPC가 들어 있다.
  - 이 두 가지를 확인하는 방법은 둘이다. 같은 조건으로 A(time_limit 끔) 사본에서 다시 만들어 저장 결과와 비트 단위로 비교하거나, 래퍼 기록과 함께 다시 실행하는 것이다. 어느 쪽이든 실행 결정은 사용자가 한다(repro/docs/WORK_RULES.md: eval 재실행 규칙).
- **참고:** 공식 측정 호스트(DESKTOP-MDCKRJS, 3층PC109)는 이번 실험의 이 PC나 windows 러너와 다르다. 저장 결과의 최대값(32~35 ms)은 45 ms까지 여유가 10 ms 남짓이다. 다른 호스트에서 다시 실행하면 이 결론이 그대로 옮겨지지 않는다(windows 러너에서는 부하 없이 45 ms 초과 정지가 에피소드 0.06~0.7%였다, S4 #1·#2).

## 2. 설계 주장 대조 (DESIGN_IMPROVED_V2)

STATIC_ANALYSIS §4(정적 대조)에 실험 결과를 더했다.

| 위치 | 설계의 주장 | 실험 결과 | 판정 |
|---|---|---|---|
| §1-0 (`:97-114`) | max_iter가 주 상한이므로 "같은 문제 데이터·같은 warm-start면 항상 같은 반복에서 멈추는 결정론적 컷오프"다. time_limit은 "정상 상황에서 걸리지 않는" 안전망이다 | windows 러너 부하 없음 orig에서 #1 16/500, #2 11/1500 회차가 불일치했고, 각각 18/18·11/11이 time_limit 절단을 동반했다. 이 PC 부하 없음에서는 0/1000이었고 부하 k=8에서 1/1000이었다. time_limit을 끄면 3개 환경 모두 0이었다 [확인-실행 S2·S3·S4] | max_iter 경로는 결정론적이다(A에서 확인). 하지만 **I5 on 구성 전체는 결정론적이지 않다.** "정상 상황에서 걸리지 않는다"는 부하 없는 CI 러너에서도 성립하지 않았다 |
| §1-4 (`:250-255`) | 발동하면 결정론이 깨지는 것은 "안전망이 실제로 필요했던 예외 상황"(호스트가 극단적으로 느려짐 등)이다. `time_limit_hit=True`로 반드시 로깅한다 | 절단된 solve는 평소 0.1~3 ms 걸리는 solve가 한 번에 45 ms 이상 멈춘 경우였다(최대 105.9 ms; A에서는 같은 정지가 362 ms까지). 정지 원인은 OS·VM 스케줄링과 백그라운드 작업으로 본다([추정], S4 §2). 절단 31건 중 9건은 "solved inaccurate"/"solved"로 보고돼 `time_limit_hit`(`mpc.py:408`)에 잡히지 않았다(S2 1건, S4 #1 6건, #2 2건) | 원인 서술이 틀렸고, 로깅 보장도 성립하지 않는다 |
| §1-5 (`:257-262`) | I5 on golden 3회 반복은 "반복 상한 방식이므로 통과해야 정상"이다 | 같은 대상(i5)이 windows 러너에서 #1 3/500, #2 5/1500 실패했다. 이 PC 부하 없음에서는 0/1000 | 통과는 환경에 따라 확률적이다 |
| §2 판정 기준 (`:284`) | time_limit_hit 0건이 기대값이다. 발생하면 "반복 상한 계산이 실제 호스트 성능과 어긋났다는 신호"다 | 위와 같다. 발생 원인은 호스트 성능이 아니라 일시 정지다. 또 0건 집계는 "solved"/"solved inaccurate" 절단을 놓친다 | 해석과 측정 방법 둘 다 정정이 필요하다 |
| §0-2 (`:69-81`) | `time_limit=1e-7` 실험으로 "run time limit reached" 문자열을 확인했다 | 그 실험 조건에서는 다른 status 경로가 나타날 수 없다(STATIC §4). 실측 절단 31건(S2 1, S3 1, S4 #1 18, #2 11)의 status는 run time limit reached 22, solved inaccurate 6, solved 3이었다 | 결론 범위를 "문자열 확인"으로 좁혀야 한다 |
| RESULT_IMPROVED §10 (`:395-398`) | v2 최대 34.955 ms는 "비재현적"인 참고치다 | 저장값 자체는 위 §1처럼 45 ms 미만이므로 해당 eval에는 절단이 없었다 | 서술은 유지할 수 있다. 다만 "time_limit 0건 → 결정론" 연결은 근거가 되지 못한다 |

- 정정 범위 [추정]: DESIGN_IMPROVED_V2 §1-0·§1-4·§1-5·§2(time_limit_hit 행)·§0-2, `improved/mpc.py:15-18`·`:149-151` 주석, `test_improved_i5.py:114-116` docstring, `docs/verification/CI.md`의 time_limit 감시 설명(발동 0 = 시간 제한 원인 아님 판정)이다.
  - 앞의 둘(설계 문서·mpc.py 주석)은 제품 코드·사용자 문서다. 이 작업 범위(run6_cause/)에서는 고치지 않는다.

## 3. mutation에 주는 영향

- **1차 결과(커밋 78e0936):**
  - kill 중 비결정성 후보 테스트에서 처음 실패한 16개는 orig·A 모두 10/10으로 다시 실패했다(S5_MUTANT_RESULT.md). 이 kill은 유지된다.
  - 생존 129개에 대한 논의도 S5_MUTANT_RESULT.md에 있다.
- **I5 on MPC를 쓰는 테스트 [확인-파일]:**
  - `anomaly/tests/test_closed_loop.py:16`, `anomaly/tests/test_detector_a.py:27,48-49,227`(V2_MPC_FLAGS)
  - `tests/test_i4_student.py`(TEACHER_FLAGS)
  - `tests/test_improved_i5.py`
  - 앞의 둘은 mutation 대상 모듈 closed_loop·detector_a의 L1 테스트다. 생존 변이 중 closed_loop 31개와 detector_a 51개가 이 테스트들로 판정됐다.
- **2차 실행 조건(제안, 결정은 사용자):** PREREGISTRATION.md:119는 "같은 범위·연산자·층·타임아웃 규칙"이라고만 정하고, 실행 환경 조건은 정하지 않았다. 이번 결과로 보면 다음 중 하나가 필요하다.
  - (a) 1차처럼 이 PC 부하 없음에서 실행한다. 비결정성 후보 테스트에서 처음 실패한 kill은 이번과 같은 방식으로 재확인한다(규칙을 실행 전에 사전 선언에 추가한다).
  - (b) 제품 대응(아래 README 선택지)을 먼저 확정한 뒤 그 커밋에서 실행한다.
  - (c) 테스트 실행 환경에서만 time_limit을 끈다. 이 경우 사전 선언 범위(테스트 대상 코드 구성)가 바뀌므로 사전 선언을 개정해야 한다.
  - [추정] 이 PC 부하 없음에서 45 ms 초과 정지는 0/12,000 에피소드였다(S2_noload). 그래서 (a)의 실질적인 위험은 작다. 하지만 1차 실행 때 PC CPU 사용률은 14%였고(run_before.json pc_load_before), VS Code·claude가 돌고 있었다.
