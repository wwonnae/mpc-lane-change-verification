# run #6 비결정성 원인 확정 — 정리 (초안)

- 상태: **초안(2026-10-14). 대응 결정 기록됨(§4).** flaky-probe 보강 실행 #2(repeats=1500) 결과까지 반영했다. 사용자가 커밋 1로 커밋한다.
- 대상: CI run #6(커밋 4c0c503)의 windows attempt 1에서 `test_improved_i5.py::test_i5_golden_determinism_three_runs`가 실패했다(1·2회차가 index 38부터 약 3e-4° 차이, time_limit 감시 발동 0회). attempt 2와 ubuntu는 통과했다.
- 원칙: 제품 코드·기존 테스트·평가 결과·CI.md·ci.yml은 수정하지 않았다. 설정을 바꾸는 실험은 저장소 밖 임시 사본에서만, CI에서는 작업 공간 사본에만 적용했다. 사전 선언은 `PLAN.md`(변경 기록 포함)에 있다.
- 표기: **[확인]**은 실행 또는 파일로 확인한 것이고, 근거 문서를 붙였다. **[추정]**은 근거를 붙인 추론이다.

## 1. 결론

1. **[확인] 원인은 OSQP `time_limit`(I5 on에서 0.045 s)에 걸려 solve가 끊기는 것이다.**
   한 solve가 45 ms 넘게 멈추면 그 solve가 시간으로 끊긴다. 그러면 해(x·y)가 달라지고, warm start를 거쳐 이후 조향 시계열이 갈라진다.
   - 불일치 회차의 첫 불일치 solve는 **입력이 같았고 시간 제한 흔적이 있었다.** 이 PC 2/2, GitHub windows 러너 #1 18/18·#2 11/11(대상 단위)이다(S2·S3·S4).
   - 시간 제한 흔적 없는 불일치는 전체 실험에서 0건이었다.
   - time_limit을 끈 조건(A)에서는 45 ms 넘는 정지가 있었는데도(windows 러너 #1 42·#2 11 에피소드, 최대 362 ms) 불일치가 0이었다.
   - windows 러너, 부하 없음: #1 orig **16/500** 회차 대 A **0/500**(회차 단위 Fisher p=2.7e-5, 보조), #2 orig **11/1500** 대 A **0/1500**(p=0.00096).
   - 사전 지정 단위인 대상별로는 #1 i4_cl100 p=0.031이다. **i5 단독은 #1 3:0(p=0.25), 보강 #2 5:0(p=0.062)로 어느 실행에서도 0.05에 이르지 못했다.** #1+#2 사후 합산은 8:0, p=0.0078이다(보조).
   - #2에서 불일치율과 45 ms 초과 정지가 #1보다 낮았다. job마다 러너 CPU 모델이 달랐다(S4_RESULT §5).
2. **[확인] 기존 감시는 이 절단의 일부만 센다.**
   - 절단은 "run time limit reached" 말고도 "solved inaccurate", "solved"로 보고된다(STATIC_ANALYSIS §3).
   - 실측 절단 31건(이 PC 2, 러너 #1 18, #2 11) 중 9건이 기존 감시에 잡히지 않았다(`improved/mpc.py:408`의 `time_limit_hit`과 CI time_limit_monitor).
   - run #6의 "발동 0회 → 시간 제한 원인 아님" 판정은 근거가 되지 못한다.
3. **[확인] 다른 가설은 배제했다.**
   - 시간 기준 adaptive rho(H2): 설정이 반복 수 기준(`adaptive_rho=1`, interval 50)이다. 래퍼가 기록한 rho 갱신 수는 모든 조건에서 실행마다 같았다.
   - 래퍼 영향: S1에서 래퍼를 켜고 끈 결과의 서명이 같았다.
   - baseline 대조군: time_limit 없음, 모든 조건에서 0 불일치.
   - 입력 단계 비결정성: 첫 불일치 solve 입력이 언제나 같았다.
4. **[확인] 환경 차이.**
   - windows 러너(2 vCPU)는 부하 없이도 45 ms 넘는 정지가 에피소드의 0.06~0.7%였다(#1 0.33·0.7%, #2 0.07·0.06%).
   - 이 PC(8코어)는 부하 없이 0%, 바쁜 루프 8개 부하에서 약 0.008~0.025%였다.
   - ubuntu 러너는 최대 solve가 5 ms라 정지도 불일치도 없었다(S4 §2).
   - [추정] 정지의 원인은 VM 스케줄링과 러너 백그라운드 작업(CompatTelRunner, Defender)이다.
5. **[확인] 저장된 평가 결과에는 영향이 없다.**
   - eval 2회차 v2(전체 solve 576,224회, 최대 34.96 ms)와 anomaly closed-loop eval(6,600 에피소드, 최대 6.375 ms) 모두 solve 시간이 45 ms 미만이었다.
   - 측정 구간이 OSQP run_time을 포함하므로(`improved/mpc.py:346,404-405,453`), 첫 solve를 빼면 절단은 일어날 수 없었다(S5_IMPACT §1).
   - eval_v2의 S3 격자와 i4_student_v2(데이터셋·eval3)에는 solve 시간 기록이 없어 점검하지 못했다.
6. **[확인] mutation.**
   - 1차 kill 중 비결정성 후보 테스트에서 처음 실패한 16개는 orig·A 모두에서 10/10으로 다시 실패했고, 실패 종류도 기록과 같았다(S5_MUTANT_RESULT).
   - 생존 129개 [추정]: fsm·baseline_mpc 47개는 구조적으로 영향이 없다. closed_loop·detector_a 82개는 영향 가능성이 무시할 만큼 작다(같은 문서의 검토).

### 사용자 결정 기록 (실험 전, PLAN.md §6)

- **조건 B는 두지 않았다.** B 사본(`adaptive_rho_interval` 자연값/50)의 C 쪽 설정을 읽어 보니 `adaptive_rho=1`, `interval=50`, `time_limit=0.045`, `max_iter=1944/972`로 **orig와 같았다**[확인-실행]. 그래서 3단계는 orig와 A만 비교했다.
- **[추정]** 노트북 Run F("interval 50 고정 + 강한 부하")도 같은 이유로 사실상 원래 설정이었다. Run F는 "원래 설정, 강한 부하"의 참고 표본으로 읽는다.
- rho 갱신이 시간과 무관하다는 점은 래퍼의 rho 갱신 수로 확인했다(결론 3).

## 2. 실험 요약

| 단계 | 내용 | 결과 | 문서 |
|---|---|---|---|
| 0 | 정적 분석(osqp 1.1.1 → C OSQP v1.0.0 소스, 실제 설정 읽기) | 벽시계 경로는 time_limit 하나뿐이다. 절단 status가 3종일 수 있음. 지문 규칙 정의 | STATIC_ANALYSIS.md |
| 1 | 기록 래퍼, 양성 대조(time_limit 0.5 ms) | 지문 158건 모두 run_time ≥ limit, 비지문 5182건 모두 미만 | PLAN.md §5 |
| S1 | 래퍼 무영향(이 PC, 50+50) | 서명 같음 | raw/S1_identity |
| S2 | 이 PC, 부하 없음 / 8 / 16 / 32 (각 1000) | 0 / 1 / 0 / 0 불일치, 흔적 동반 1/1 | S2_RESULT.md |
| S3 | 이 PC, k=8, orig 대 A (각 1000) | 1 대 0 (p=1), 흔적 동반 1/1 | S3_RESULT.md |
| S4 #1 | GitHub 러너, 부하 없음, orig·A × ubuntu·windows (각 500) | windows orig 16, 나머지 0. 흔적 동반 18/18 | S4_RESULT.md |
| S6 | 지문 규칙 검토(실측 + 양성 대조 0.2/0.5/1 ms) | 안 B(+ solved & iter 0) 채택. run_time 조건은 과대 집계만 더함(실측 0, 양성 대조 12/32,040) | raw/S6_fingerprint_check/README.md |
| S4 #2 | 같은 조건 repeats 1500 | windows orig 11(i5 5), 나머지 0. 흔적 동반 11/11. i5 단독 p=0.062 | S4_RESULT.md §5 |
| 5 | 저장 평가 점검, 설계 주장 대조, 변이 재확인 | 영향 없음 / 정정 필요 / kill 16개 유지 | S5_IMPACT.md, S5_MUTANT_RESULT.md |

## 3. 한계

- 러너 실험은 2회(#1, #2) 실행했고, 각 job은 VM 1대씩이다. #2에서는 job마다 CPU 모델이 달랐다. 정지 빈도가 VM에 따라 크게 달라서(에피소드 0.06~0.7%) 러너 불일치율은 하나의 값으로 말할 수 없다.
- i5 대상만 놓고 보면 orig 대 A의 사전 지정 비교가 어느 실행에서도 p<0.05에 이르지 못했다. i5에 대한 원인 판단은 다른 대상과 같은 기전 증거(같은 입력 + 절단, A에서 0)에 기댄다.
- harness는 대상 테스트만 반복한다. 실제 CI(pytest 전체, 같은 프로세스 안의 다른 테스트)와 동시에 도는 작업이 다르므로, 러너의 불일치율을 CI 1회 실행의 실패 확률로 그대로 옮길 수 없다.
- 이 PC의 orig 대 A 비교(S3)는 1 대 0이라 통계적 구분력이 없다. 원인 판단은 회차 단위의 기전 증거(같은 입력 + 절단)와 러너 결과에 기댄다.
- CPU 기록(sysmon)은 표본 도중 끝난 batch·부하 전환 프로세스를 "other"로 분류하는 결함이 있었다. 보조 재분류로 보완했고, 위반 판정 원값은 그대로 보고했다(S2_RESULT).
- 저장 결과 점검은 필요조건(최대 시간 < 45 ms)에 기댄다. 인스턴스 첫 solve(setup 시간 포함)는 이 방법으로 배제되지 않는다. S3 격자와 I4 v2 결과는 점검하지 못했다.
- 이 PC에는 KB5127648 재부팅 대기 상태가 있었다(재부팅하지 않음).
- **[정정 2026-10-14, S6]** 지문 규칙(STATIC_ANALYSIS §3-3)에는 첫 반복 절단이 "solved, iter 0"으로 보고되는 빈틈이 있었다. 커밋 2 계획에서는 한계를 "25의 배수 반복에서 끊겨 solved로 보고되는 경우"라고 말했는데, 이것은 틀렸다.
  - 소스상 그런 경우는 iter 0 하나뿐이다(`osqp_api.c:666, 741-765, 908-931`).
  - "solved & iter==0"을 더한 안 B로 막았고, 기존 판정은 바뀌지 않는다(해당 0건, raw/S6_fingerprint_check/).

## 4. 대응 선택지와 영향

### 사용자 결정 (2026-10-14)

**선택지 2 + 5 + 0 조합을 채택한다. 1·3·4는 채택하지 않는다.**

- **채택 이유(사용자):** 결정론 검증과 실시간 마감 보장은 별개 요구사항이므로 분리한다.
  - 제품의 time_limit(안전망)은 유지한다.
  - 감시를 바로잡는다(5).
  - 결정론 테스트는 time_limit 없이 검증한다(2).
  - time_limit 발동 경로는 `test_i5_time_limit_safety_net_reachable`이 계속 검증한다.
  - 문서를 정정한다(0).
- **불채택 이유(사용자):**
  - 1: 실패를 숨긴다.
  - 3: 테스트 편의를 위해 제품 안전망을 제거하는 셈이다.
  - 4: 문제를 줄일 뿐 제거하지 못하고, 마감 근거도 약해진다.
- **진행 순서:**
  - 커밋 1: 조사 기록(이 폴더와 flaky_probe.yml). 보강 실행 #2 결과까지 반영했다.
  - 커밋 2: 대응 변경. 커밋 1 이후 변경 계획을 사용자에게 보이고 승인을 받은 뒤 진행한다.

### 커밋 2 세부 결정 (2026-10-14, 계획 승인 시)

- **선택지 2 범위:** `thesis_v2/conftest.py`의 `i5_time_limit_off` fixture(I5_TIME_LIMIT_SEC=1e10, 명시 적용)를 다음 테스트에 붙인다.
  - 결정론 비교: `test_i5_golden_determinism_three_runs`, `test_i4_recorder_does_not_change_episode`, `test_i4_closed_loop_matches_improved_runner_with_mpc[100,101]`, anomaly `test_p0_matches_observational_runner`(8), `test_determinism`, `test_detector_a_with_gyro_does_not_change_control[0,1,2]`, `test_golden_equivalence` 매개변수 전부.
  - 그리고 `test_i5_tiny_iter_cap_triggers_max_iter_status_and_hard_check`(max_iter 동작 검사, time_limit 무관).
  - fixture가 실제 OSQP 설정에 닿는지와 제품 인스턴스가 0.045를 유지하는지를 보호 테스트 2개로 확인한다.
- **선택지 5 범위:** `improved/mpc.py`에 `time_limit_fingerprint`를 두고 I5 on의 `time_limit_hit`를 이것으로 판정한다. `improved/runner.py`의 `time_limit_count` 집계와 주목 스텝 조건도 이 판정을 따른다.
  - 지문 규칙은 **안 B**(기존 + "solved & iter==0")이고, run_time 조건(안 C)은 넣지 않는다(S6 수치 근거).
- **선택지 0 범위:** DESIGN_IMPROVED_V2 §0-2·§1-0·§1-4·§1-5·§2·§8, `test_improved_i5` docstring, `time_limit_monitor.py` docstring, anomaly DESIGN.md(2026-10-03 P0 불일치: "유력한 후보, 추정, 확정 아님"), RESULT_IMPROVED §10에 정정 블록을 단다(원문 유지).
  - **CI.md는 이번에 하지 않는다**(노트북 미커밋 수정과 충돌 회피). 다음 작업으로 남긴다.
- **평가 동결:** 선택지 5는 "출력 불변 로깅 변경"으로 기록한다(새 eval 반복 아님). 확인 결과는 `COMMIT2_VERIFY.md`에 있다.
- **mutation 2차 조건:** S5_IMPACT §3 (a)를 커밋 2 이후 상태에 적용한다. mutation RESULTS.md "사전 선언 변경" 5번 문구는 계획 초안대로 쓴다.

### 선택지별 영향 (결정 전 비교표)

각 선택지는 조합할 수 있다.

| # | 선택지 | 제품 코드 변경 | 저장된 평가 재실행 필요 여부(근거) | mutation 사전 선언·결과에 주는 영향 | CI 안정성 효과 | 설계 문서 정정 범위 |
|---|---|---|---|---|---|---|
| 0 | 그대로 두고 문서만 정정 | 없음 | 불필요. 저장 eval v2·anomaly eval은 모든 solve가 45 ms 미만이라 절단이 없었다(S5_IMPACT §1). S3 격자·I4 v2는 미점검 | 1차 결과 유지(kill 16개 재확인). 2차 실행은 이 PC 부하 없음에서 하고, 비결정성 후보 테스트의 kill을 재확인하는 규칙을 실행 전에 추가 | **변화 없음.** windows 러너에서 I5 on 테스트가 확률적으로 실패한다(대상별 #1 0.6~1.2%/회, #2 0.07~0.33%/회, S4) | §1-0·§1-4·§1-5·§2 time_limit_hit 행·§0-2, mpc.py 주석(:15-18, :149-151), test docstring(:114-116), CI.md 감시 판정 문구를 "time_limit 미발동일 때만 결정론적"으로 정정 |
| 1 | CI에서 실패 테스트 재시도(rerun) | 없음(ci.yml·테스트 설정 변경) | 불필요(위와 같음) | 사전 선언의 층·타임아웃 규칙과 별개다. 단, mutation이 같은 재시도를 쓰면 kill 판정 규칙이 바뀌므로 사전 선언 개정이 필요하다 | 실패 표시는 줄지만 비결정성은 남는다. 진짜 결정론 회귀도 재시도로 가려질 수 있다 | 0과 같고, CI.md에 재시도 규칙을 추가 |
| 2 | 테스트에서만 time_limit 끄기(fixture/conftest로 I5_TIME_LIMIT_SEC 큰 값) | 없음(테스트 코드 변경) | 불필요(위와 같음) | 테스트 스위트가 바뀌므로 2차 실행 전 사전 선언에 기록이 필요하다. I5 on 테스트가 제품 구성(0.045)과 다른 구성을 검사하게 된다 | **결정론 확보.** A 조건은 세 환경 모두 0 불일치였다(러너 #2 1500×2 포함, 이 PC 1000, 러너 500×2). 단, 제품 설정의 time_limit 경로는 CI에서 검증되지 않는다 | 0과 같고, "테스트는 time_limit off로 결정론을 검사한다"는 범위 서술을 추가 |
| 3 | 제품에서 time_limit 제거(I5는 max_iter만) | **있음**(`improved/config.py`/`mpc.py`) | **원칙상 불필요하다는 근거가 있음.** 저장 eval v2·anomaly eval에는 절단이 없었고, 절단이 없을 때 orig와 A의 출력은 비트 단위로 같았다(S3 서명 동일). 단, repro/docs/WORK_RULES.md 규칙상 eval 이후 코드를 고치면 새 반복으로 기록해야 하고, 재확인 실행 여부는 사용자가 정한다. S3 격자·I4 v2는 미점검 | 1차는 커밋 78e0936에 묶여 유지된다. improved는 변이 대상이 아니므로 범위는 그대로다. 2차는 새 커밋에서 실행하고 I5 on 테스트가 결정론적이 된다 | **결정론 확보**(2와 같은 근거). 제품과 테스트 구성이 일치한다 | §1-0 주장이 참이 된다. §1-2·§1-4·§1-6(안전망 서술)·§2(time_limit_hit 행) 삭제 또는 개정. 안전망 제거 사유를 기록. mpc.py 주석·docstring 개정 |
| 4 | time_limit 값을 크게(예: 0.5~1 s) | **있음**(config 값) | 3과 같음(저장 결과는 45 ms 기준으로도 절단이 없었다) | 3과 같음. 다만 비결정성이 남으므로 2차 실행 조건은 0과 같음 | 빈도는 줄지만 0은 아니다. A에서 관측된 최대 정지가 238 ms였다. 얼마나 줄지는 측정하지 않았다 | 0과 같고, 값 변경 근거 추가 |
| 5 | 감시 정정: 절단을 지문 규칙으로 집계(`time_limit_hit`, time_limit_monitor) | **있음**(로깅만, 제어 출력 불변) | 불필요. 로깅 필드뿐이고, 저장 결과의 기존 0건은 §1 근거로 "실제 0"이다 | 결과 영향 없음. 2차 실행 중 절단 여부를 기록할 수 있게 된다 | 그대로지만, 실패가 나면 원인(절단)을 바로 판별할 수 있다 | §1-3·§1-4·§2(측정 방법)와 CI.md 감시 설명을 지문 규칙으로 개정 |

- 공통: 기존 기록(CI.md의 run #6 판정 "시간 제한 원인 아님")은 지우지 않는다. 어떤 선택지든 정정 기록을 추가하는 방식이 repro/docs/WORK_RULES.md 원칙에 맞다. 어디에 적을지는 사용자가 정한다.
- 이 표의 "CI 안정성 효과"는 harness 대상 테스트의 러너 결과에 근거한다. ci.yml의 전체 실행에 대해서는 측정하지 않았다.

## 5. 파일

| 파일 | 내용 |
|---|---|
| PLAN.md | 사전 선언, 사용자 결정(§6), 변경 기록 |
| STATIC_ANALYSIS.md | 0단계 정적 분석 |
| S2_RESULT.md, S3_RESULT.md, S4_RESULT.md | 실험별 결과 |
| S5_IMPACT.md, S5_MUTANT_RESULT.md | 영향 분석, 변이 재확인 |
| osqp_probe.py, harness.py, sysmon.ps1, apply_condition.py, analyze.py, mutant_recheck.py | 도구 |
| specs/ | 실험 스펙과 실행 로그 |
| raw/ | 원자료(S1_identity, S2_noload, S2_load, S3, S4_runner, S5_mutant_recheck, S6_fingerprint_check) |
| COMMIT2_VERIFY.md | 커밋 2(대응 변경) 재확인 결과: 전체 테스트, golden, CI 대조 3종, 소규모 동적 비교 |
| ../../../../.github/workflows/flaky_probe.yml | 러너 재현용 수동 워크플로 |

## 6. 다음 작업

1. ~~야간 실행 결과 확인~~ — **완료(2026-10-15)**. 실행은 2026-10-14 16:04–18:18, 결과 커밋 `3187e40`, 세 단계 모두 종료 코드 0.
   - mutation 2차: 원점수 78.5% → 88.5%, 등가 제외 83.1% → 93.7%. 보강 대상 60개 모두 잡힘, 잡혔다가 생존으로 바뀐 변이 0(mutation RESULTS.md).
   - kill 재확인: 대상 127개, kill 유지 127, 재검토 0.
   - anomaly `--check`(저장 eval): 7개 파일 전체 일치. 새 지문 판정 time_limit 발동 0, 최대 solve 3.0 ms. 선택지 5의 출력 불변을 저장 평가 수준에서 확인했다(COMMIT2_VERIFY.md §8).
   - `run_after.json`의 git.dirty는 true였다. 원인은 저장소 안 로그 폴더의 미추적 파일이고, 코드 변경은 아니다(mutation RESULTS.md 발견 사항 5).
2. ~~mutation RESULTS.md 마무리~~ — **완료**: 2차 결과, 예측 대조, 커버리지 대조, 사전 선언 변경 5 결과.
3. ~~make_mutation_tables~~ — **완료**: `docs/verification/mutation/make_mutation_tables.py` → `MUTATION_TABLES.md`(`--check`).
4. ~~CI 단계 추가~~ — **완료**: `.github/workflows/ci.yml`에 `test_mutate.py`, `make_mutation_tables.py --check` 단계를 넣었다.
5. ~~**CI.md 정정**~~ — **완료(2026-10-15)**. 노트북 기록(커밋 7bd9363)을 합친 뒤 별도 커밋으로 했다. CI.md에 정정 블록을 원문 유지로 달았다: run #6 절 첫머리(원인·근거·대응 2+5+0, 노트북 실험 A~E·F는 "조건 통제 안 됨, 참고", 가설 (2) adaptive rho는 틀림)와 하위 절별 정정, "OSQP time_limit 기록" 절(지문 규칙 안 B 기준). "실행 내용" 표를 ci.yml 현재 단계와 맞췄고(mutation 두 단계, 결정론 테스트 fixture), "주요 실행 기록"을 추가했다. flaky-probe #1·#2 원본 zip은 `raw/S4_runner/run1|run2/original_zips/`로 옮겼다(해시 일치, S4_RESULT).
   - 아래는 원래 계획(기록용):
   - 노트북의 미커밋 CI.md 수정을 합친 뒤 별도 커밋으로 한다.
   - 대상: time_limit 감시 설명, run #6 판정("발동 0회 → 시간 제한 원인 아님")에 정정 블록을 단다(원문 유지). 근거는 이 README §1과 S5_IMPACT §2다.
   - 같이 할 것: CI.md "실행 내용" 표에 새 CI 단계 2개(mutation 도구 자체 테스트, `make_mutation_tables.py --check`)를 추가한다(ci.yml에는 2026-10-15 반영).
6. **`overnight_run.sh` 로그 위치: 수정하지 않음(사용자 결정, 이유: 실행 완료 후 수정은 결과에 영향 없음).** 로그 폴더가 저장소 안에 있어 mutation 원자료의 git.dirty가 true로 기록된다(mutation RESULTS.md 발견 사항 5).
   - 고치는 방법은 두 가지다: 로그를 저장소 밖에 두고 끝에 복사하거나, `mutate.py`의 dirty 판정에서 그 폴더를 빼는 것이다.
   - 둘째는 사전 선언 도구(`mutate.py`)를 바꾸는 것이다.
