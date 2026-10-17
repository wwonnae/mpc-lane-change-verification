# 양방향 추적 매트릭스 (자동 생성)

<!-- make_trace_matrix.py가 생성. 손으로 고치지 않는다. 확인: python docs/verification/aspice/make_trace_matrix.py --check -->

연결 규칙과 입력 문서는 `make_trace_matrix.py` 머리말에 있다. 평가 문서 열은 **REQ ID를 인용한 행**이며, 그 행이 해당 REQ를
평가로 검증했다는 뜻은 아니다. 고아 항목은 억지로 연결하지 않고 그대로 센다.

## 요약

| 항목 | 값 |
|---|---|
| REQ 대상(SPEC 표 행 ∪ thesis_v2 코드·테스트 직접 인용) | 59 |
| — SETTINGS_DECISION 정의(SPEC 표 없음) | 1 |
| — SPEC 정의 | 57 |
| — 정의 없음 | 1 |
| 테스트가 1개 이상 연결된 REQ | 44 |
| **테스트 없는 REQ(고아)** | **15** |
| 코드 연결 없는 REQ | 5 |
| 테스트 함수(파라미터 변형 포함 수집 항목) | 241 (359) |
| REQ가 연결된 테스트 함수 | 69 |
| **REQ 없는 테스트 함수(고아)** | **172** |
| — 이상탐지(REQ 체계 밖) | 94 |
| — improved(SPEC에 REQ 없음) | 39 |
| — 인프라·도구(요구사항 수준 아님) | 34 |
| — 기타 | 5 |
| TRACEABILITY.md 비-REQ 행 | 12 |
| TRACEABILITY.md에서 해석하지 못한 표기 | 0 |

고아 테스트 범주 규칙(순서대로 첫 일치): ① `thesis_v2/anomaly/tests/` → 이상탐지 ② 테스트 파일이 `thesis_v2.improved`를 import → improved
③ 파일명 `test_<대상>.py`의 대상이 ['check_golden', 'envinfo', 'logger', 'metrics', 'run_cli', 'summary'] → 인프라·도구 ④ 나머지 → 기타.

## 정방향: REQ → 설계 → 코드 → 테스트 → 평가 문서

| REQ | 정의 | 설계 | 코드 | 테스트 | 평가 문서(인용 행) |
|---|---|---|---|---|---|
| REQ-CTRL-01 | SPEC 정의<br>`repro/docs/SPEC.md:92`<br>횡방향(REQ-LAT, 라인추종 또는 MPC) + 종방향(REQ-SPD, 규칙기반) 계층 통합 | **없음** | thesis_v2/baseline/runner.py:run_episode (추적표 43행) | thesis_v2/tests/test_runner.py::test_collision_has_priority_over_safe_stop_same_step (추적표·파일 단위)<br>thesis_v2/tests/test_runner.py::test_metrics_counts_are_internally_consistent (추적표·파일 단위)<br>thesis_v2/tests/test_runner.py::test_safe_stop_holds_last_steering_and_does_not_crash (추적표·파일 단위)<br>thesis_v2/tests/test_runner.py::test_seed_reproducibility (추적표·파일 단위) | **없음** |
| REQ-EVAL-01 | SPEC 정의<br>`repro/docs/SPEC.md:113`<br>제어 성능 지표: 횡방향 오차, 헤딩각 오차, 조향각 변화율, 목표 추종 오차 | **없음** | **없음** | **없음** | **없음** |
| REQ-EVAL-02 | SPEC 정의<br>`repro/docs/SPEC.md:114`<br>안전성 지표: 제약 만족률, 충돌 횟수, 최소 장애물 거리 | **없음** | **없음** | **없음** | **없음** |
| REQ-EVAL-03 | SPEC 정의<br>`repro/docs/SPEC.md:115`<br>계산 효율성 지표: 평균 계산시간, 최대 계산시간, 계산시간 표준편차(+ 백분위수는 Table 8에서만 등장) | DESIGN_BASELINE.md §4 (행 133, 본문 인용) | thesis_v2/baseline/summary.py:_step_time_stats (행 100, 주석·직접) | thesis_v2/tests/test_mutation_gaps_mpc.py::test_compute_time_ms_is_elapsed_perf_counter_in_milliseconds (테스트 내 인용) | **없음** |
| REQ-EVAL-04 | SPEC 정의<br>`repro/docs/SPEC.md:116`<br>회피 성공률: 정의 문장 자체는 없고 Table 7 "회피 성공률(%) — 설명: 전체 성공"으로만 등장 | SETTINGS_DECISION.md §10 (행 256, 절 제목)<br>SETTINGS_DECISION.md §6 (행 88, 본문 인용) | **없음** | **없음** | RESULT_BASELINE.md:45 |
| REQ-FSM-01 | SPEC 정의<br>`repro/docs/SPEC.md:32`<br>5개 상태: KEEP_L2, EVADE_L, KEEP_L1, RETURN_TO_L2, SAFE_STOP | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md 확정된 (행 597, 본문 인용) | thesis_v2/baseline/fsm.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/fsm.py:FSMState (추적표 14행) | thesis_v2/tests/test_fsm.py::test_initial_fsm_cooldown_pre_expired (추적표·함수 명시) | **없음** |
| REQ-FSM-02a | SPEC 정의<br>`repro/docs/SPEC.md:33`<br>KEEP_L2→EVADE_L: front_gap<1.2 AND left_clear=True | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §12 (행 289, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 16, 주석·직접)<br>thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (추적표 15행)<br>thesis_v2/baseline/fsm.py:step (행 46, 주석·직접)<br>thesis_v2/baseline/fsm.py:step (행 54, 주석·직접) | thesis_v2/tests/test_fsm.py::test_keep_l2_to_evade_l_negative_not_left_clear (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_keep_l2_to_evade_l_positive (추적표·함수 명시)<br>thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d1_front_gap_lt_g_trig (추적표·함수 명시)<br>thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d1_front_gap_lt_g_trig (테스트 내 인용) | **없음** |
| REQ-FSM-02b | SPEC 정의<br>`repro/docs/SPEC.md:34`<br>모든 상태→SAFE_STOP: front_gap<0.20 AND left_clear=False, 예외 없음 | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md left_clear (행 225, 본문 인용)<br>SETTINGS_DECISION.md §12 (행 289, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 17, 주석·직접)<br>thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (추적표 16행)<br>thesis_v2/baseline/fsm.py:step (행 46, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (행 50, 주석·직접)<br>thesis_v2/baseline/summary.py:<module> (행 41, 주석·직접)<br>thesis_v2/baseline/summary.py:build_summary (행 225, 주석·직접)<br>thesis_v2/baseline/world.py:generate_left_obstacle_scenario (행 115, 주석·직접) | thesis_v2/tests/test_fsm.py::test_any_state_to_safe_stop_positive (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_safe_stop_condition_negative_left_clear_true (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_safe_stop_from_every_state (추적표·함수 명시)<br>thesis_v2/tests/test_mutation_gaps_fsm.py::test_safe_stop_requires_front_gap_strictly_below_g_safe_min (테스트 내 인용) | MEASURE_PLAN.md:113<br>RESULT_BASELINE.md:59<br>ROBUSTNESS_PLAN.md:6,16 |
| REQ-FSM-02c | SPEC 정의<br>`repro/docs/SPEC.md:35`<br>EVADE_L→KEEP_L1: \ | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 25, 주석·직접)<br>thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (추적표 17행)<br>thesis_v2/baseline/fsm.py:step (행 46, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (행 58, 주석·직접) | thesis_v2/tests/test_fsm.py::test_evade_l_to_keep_l1_negative_far_from_l1 (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_evade_l_to_keep_l1_positive (추적표·함수 명시) | **없음** |
| REQ-FSM-02d | SPEC 정의<br>`repro/docs/SPEC.md:36`<br>KEEP_L1→RETURN_TO_L2: right_clear(REQ-SEN-04) AND t>0.6s | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §14 (행 349, 절 제목)<br>SETTINGS_DECISION.md §6 (행 88, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 24, 주석·직접)<br>thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:FSM (행 30, 주석·직접)<br>thesis_v2/baseline/fsm.py:step (추적표 18행)<br>thesis_v2/baseline/fsm.py:step (행 46, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (행 62, 주석·직접)<br>thesis_v2/baseline/sensors.py:right_clear (추적표 18행) | thesis_v2/tests/test_fsm.py::test_keep_l1_to_return_negative_right_not_clear (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_keep_l1_to_return_positive (추적표·함수 명시)<br>thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form (추적표·함수 명시)<br>thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_fsm.py::test_keep_l1_return_requires_elapsed_strictly_above_t_keep_l1_min (테스트 내 인용) | **없음** |
| REQ-FSM-02e | SPEC 정의<br>`repro/docs/SPEC.md:38`<br>RETURN_TO_L2→KEEP_L2: \ | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §2 (행 27, 본문 인용)<br>SETTINGS_DECISION.md §20 (행 658, 본문 인용)<br>SETTINGS_DECISION.md §6 (행 88, 본문 인용)<br>SETTINGS_DECISION.md 확정된 (행 597, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 26, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 27, 주석·직접)<br>thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (추적표 19행)<br>thesis_v2/baseline/fsm.py:step (행 46, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (행 67, 주석·직접)<br>thesis_v2/improved/config.py:<module> (행 59, 주석·직접) | thesis_v2/tests/test_fsm.py::test_return_to_keep_l2_negative_psi_too_large (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_return_to_keep_l2_positive (추적표·함수 명시)<br>thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d4_abs_y_le_near_l2 (추적표·함수 명시)<br>thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d4_abs_y_le_near_l2 (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_fsm.py::test_return_to_keep_l2_accepts_psi_exactly_limit (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_fsm.py::test_return_to_keep_l2_accepts_y_exactly_near_l2 (테스트 내 인용) | RESULT_I4.md:172 |
| REQ-FSM-03 | SPEC 정의<br>`repro/docs/SPEC.md:39`<br>상태 전이 쿨다운 0.3초: 상태 변경 후 0.3초 내 추가 전이 차단 | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §13 (행 329, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 18, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:FSM (행 29, 주석·직접)<br>thesis_v2/baseline/fsm.py:step (추적표 20행) | thesis_v2/tests/test_fsm.py::test_cooldown_blocks_evade_to_keep_l1 (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_keep_l1_to_return (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_keep_l2_to_evade (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_return_to_keep_l2 (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_safe_stop (추적표·함수 명시) | **없음** |
| REQ-FSM-03a | SPEC 정의<br>`repro/docs/SPEC.md:40`<br>쿨다운 적용 범위: PDF (3)번은 "상태가 변경된 후... 추가 전이가 차단된다"고 전이 종류를 한정하지 않음 → 5개 전… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용) | thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (추적표 20행)<br>thesis_v2/baseline/fsm.py:step (행 46, 주석·직접) | thesis_v2/tests/test_fsm.py::test_cooldown_blocks_evade_to_keep_l1 (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_keep_l1_to_return (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_keep_l2_to_evade (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_return_to_keep_l2 (추적표·함수 명시)<br>thesis_v2/tests/test_fsm.py::test_cooldown_blocks_safe_stop (추적표·함수 명시) | **없음** |
| REQ-FSM-03b | SETTINGS_DECISION 정의(SPEC 표 없음)<br>`repro/docs/SETTINGS_DECISION.md:329 (§13)` | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §13 (행 329, 절 제목) | thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:initial_fsm (추적표 21행)<br>thesis_v2/baseline/fsm.py:initial_fsm (행 34, 주석·직접) | thesis_v2/tests/test_fsm.py::test_initial_fsm_cooldown_pre_expired (추적표·함수 명시) | **없음** |
| REQ-FSM-04 | SPEC 정의<br>`repro/docs/SPEC.md:41`<br>SAFE_STOP 진입 시 회복 조건·재진입 로직 | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §1 (행 12, 절 제목) | thesis_v2/baseline/fsm.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/fsm.py:step (추적표 22행)<br>thesis_v2/baseline/fsm.py:step (행 71, 주석·직접) | thesis_v2/tests/test_fsm.py::test_safe_stop_is_terminal_no_recovery (추적표·함수 명시) | **없음** |
| REQ-LAT-01 | SPEC 정의<br>`repro/docs/SPEC.md:82`<br>라인추종: δ=−K_ey·ey_line, K_ey=1.5 — KEEP_L2에서 라인이 명확히 감지될 때 사용 | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §4 (행 133, 본문 인용)<br>SETTINGS_DECISION.md §11 (행 271, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용)<br>SETTINGS_DECISION.md §17 (행 432, 절 제목) | thesis_v2/baseline/config.py:<module> (행 29, 주석·직접)<br>thesis_v2/baseline/lateral.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/lateral.py:compute_lateral (추적표 38행)<br>thesis_v2/baseline/lateral.py:compute_lateral (행 47, 주석·직접)<br>thesis_v2/improved/lateral.py:<module> (행 2, 주석·직접) | thesis_v2/tests/test_lateral.py::test_keep_state_line_follow_when_detected (추적표·함수 명시) | **없음** |
| REQ-LAT-02 | SPEC 정의<br>`repro/docs/SPEC.md:83`<br>MPC 모드: 라인이 감지되지 않거나 차선 변경 중(EVADE_L, RETURN_TO_L2)에 사용 — EVADE_L·RETU… | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용) | thesis_v2/baseline/lateral.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/lateral.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/lateral.py:compute_lateral (추적표 39행)<br>thesis_v2/baseline/lateral.py:compute_lateral (행 53, 주석·직접)<br>thesis_v2/improved/lateral.py:<module> (행 2, 주석·범위(~))<br>thesis_v2/improved/student_i4/features.py:<module> (행 50, 주석·직접) | thesis_v2/tests/test_lateral.py::test_evade_return_always_mpc_when_detected (추적표·함수 명시)<br>thesis_v2/tests/test_lateral.py::test_evade_return_always_mpc_when_not_detected (추적표·함수 명시) | **없음** |
| REQ-LAT-03 | SPEC 정의<br>`repro/docs/SPEC.md:84`<br>"라인이 감지되지 않음"의 판정 기준(센서 유효성 타임아웃 등 구체값) | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용)<br>SETTINGS_DECISION.md §4 (행 60, 절 제목)<br>SETTINGS_DECISION.md §9 (행 191, 본문 인용) | thesis_v2/baseline/lateral.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/lateral.py:compute_lateral (추적표 40행)<br>thesis_v2/baseline/lateral.py:compute_lateral (행 53, 주석·연속(/))<br>thesis_v2/baseline/sensors.py:ey_line (행 94, 주석·직접)<br>thesis_v2/improved/lateral.py:<module> (행 2, 주석·범위(~))<br>thesis_v2/improved/student_i4/features.py:<module> (행 50, 주석·연속(/)) | thesis_v2/tests/test_lateral.py::test_keep_state_mpc_when_not_detected (추적표·함수 명시) | **없음** |
| REQ-LAT-04 | SPEC 정의<br>`repro/docs/SPEC.md:85`<br>KEEP_L1 상태에서의 횡방향 제어 모드 | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용)<br>SETTINGS_DECISION.md §5 (행 74, 절 제목) | thesis_v2/baseline/lateral.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/lateral.py:compute_lateral (추적표 41행)<br>thesis_v2/baseline/lateral.py:compute_lateral (행 53, 주석·연속(/))<br>thesis_v2/improved/lateral.py:<module> (행 2, 주석·범위(~)) | thesis_v2/tests/test_lateral.py::test_keep_state_line_follow_when_detected (추적표·함수 명시)<br>thesis_v2/tests/test_lateral.py::test_keep_state_mpc_when_not_detected (추적표·함수 명시) | **없음** |
| REQ-LAT-05 | SPEC 정의<br>`repro/docs/SPEC.md:86`<br>SAFE_STOP 상태의 횡방향 제어(조향) | SETTINGS_DECISION.md §16 (행 394, 절 제목) | thesis_v2/baseline/lateral.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/lateral.py:<module> (행 6, 주석·직접)<br>thesis_v2/baseline/lateral.py:compute_lateral (추적표 42행)<br>thesis_v2/baseline/lateral.py:compute_lateral (행 38, 주석·직접)<br>thesis_v2/baseline/metrics.py:y_within_tolerance (행 45, 주석·직접)<br>thesis_v2/baseline/runner.py:run_episode (행 146, 주석·직접)<br>thesis_v2/baseline/summary.py:build_summary (행 240, 주석·직접)<br>thesis_v2/improved/lateral.py:<module> (행 2, 주석·범위(~))<br>thesis_v2/improved/student_i4/features.py:<module> (행 50, 주석·직접) | thesis_v2/tests/test_lateral.py::test_safe_stop_does_not_call_mpc (추적표·함수 명시)<br>thesis_v2/tests/test_lateral.py::test_safe_stop_holds_last_delta_regardless_of_ey (추적표·함수 명시)<br>thesis_v2/tests/test_metrics.py::test_y_within_tolerance_safe_stop_is_not_applicable (테스트 내 인용)<br>thesis_v2/tests/test_runner.py::test_safe_stop_holds_last_steering_and_does_not_crash (추적표·함수 명시)<br>thesis_v2/tests/test_runner.py::test_safe_stop_holds_last_steering_and_does_not_crash (테스트 내 인용) | MEASURE_PLAN.md:109<br>RESULT_STUDENT.md:41 |
| REQ-MPC-01 | SPEC 정의<br>`repro/docs/SPEC.md:47`<br>이산 선형 모델(2-state, y·ψ): y_{k+1}=y_k+v·dt·ψ_k, ψ_{k+1}=ψ_k+(v/L)·dt·δ_k | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>SETTINGS_DECISION.md §11 (행 271, 본문 인용)<br>SETTINGS_DECISION.md §17 (행 432, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용)<br>SETTINGS_DECISION.md §20 (행 658, 본문 인용) | thesis_v2/baseline/mpc.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/mpc.py:_build_A_template (추적표 23행) | thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_negative_target (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_positive_target (추적표·함수 명시)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_delta0_matches_independent_spec_qp (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_heading_constraint_binds_when_optimum_would_exceed_limit (테스트 내 인용) | **없음** |
| REQ-MPC-02 | SPEC 정의<br>`repro/docs/SPEC.md:48`<br>비용함수: J=Σ_{i=1}^N[qy(y_i−y_ref)²+qψ·ψ_i²] + rδ·δ_0² + Σ_{i=1}^{N-1} rΔ… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §11 (행 271, 본문 인용)<br>SETTINGS_DECISION.md §17 (행 432, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용)<br>SETTINGS_DECISION.md §20 (행 658, 본문 인용) | thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:OSQPMPC._build_P (행 80, 주석·직접)<br>thesis_v2/baseline/mpc.py:_build_P (추적표 24행)<br>thesis_v2/improved/mpc.py:ImprovedMPC._build_P (행 207, 주석·직접) | thesis_v2/tests/test_mpc.py::test_hessian_has_offdiagonal_rddelta_terms (추적표·함수 명시)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_delta0_matches_independent_spec_qp (테스트 내 인용) | MEASURE_PLAN.md:174<br>RESULT_BASELINE.md:90,106<br>RESULT_STUDENT.md:127 |
| REQ-MPC-03 | SPEC 정의<br>`repro/docs/SPEC.md:49`<br>가중치: qy=100, qψ=25, rδ=2, rΔδ=5, N=15(0.75s) | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용) | thesis_v2/baseline/config.py (추적표 25행)<br>thesis_v2/baseline/config.py:<module> (행 10, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 11, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 12, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 13, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 8, 주석·직접)<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~)) | thesis_v2/tests/test_config.py::test_fixed_params_match_claude_md (추적표·함수 명시)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_delta0_matches_independent_spec_qp (테스트 내 인용) | **없음** |
| REQ-MPC-03a | SPEC 정의<br>`repro/docs/SPEC.md:50`<br>rδ는 첫 제어입력의 크기(δ_0²)에만 곱해지고, rΔδ는 연속 제어입력의 차분(δ_i−δ_{i-1})²에 곱해진다 — 식(… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용) | thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/mpc.py:OSQPMPC._build_P (행 80, 주석·연속(/))<br>thesis_v2/baseline/mpc.py:_build_P (추적표 26행)<br>thesis_v2/improved/mpc.py:ImprovedMPC._build_P (행 207, 주석·연속(/)) | thesis_v2/tests/test_mpc.py::test_hessian_has_offdiagonal_rddelta_terms (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_hessian_has_offdiagonal_rddelta_terms (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_delta0_matches_independent_spec_qp (테스트 내 인용) | MEASURE_PLAN.md:174 |
| REQ-MPC-04 | SPEC 정의<br>`repro/docs/SPEC.md:51`<br>제약: −25°≤δ_i≤25°; 헤딩 −80°≤ψ_i≤80°; 횡방향 위치 — L2주행 −0.15≤y≤0.15, L1주행 0.… | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md left_clear (행 225, 본문 인용)<br>SETTINGS_DECISION.md §14 (행 349, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용)<br>SETTINGS_DECISION.md §6 (행 88, 본문 인용)<br>SETTINGS_DECISION.md 확정된 (행 597, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 33, 주석·직접)<br>thesis_v2/baseline/metrics.py:delta_within_tolerance (행 34, 주석·직접)<br>thesis_v2/baseline/metrics.py:psi_within_tolerance (행 39, 주석·직접)<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/mpc.py:OSQPMPC._build_A_template (행 147, 주석·직접)<br>thesis_v2/baseline/mpc.py:OSQPMPC._build_A_template (행 152, 주석·직접)<br>thesis_v2/baseline/mpc.py:_build_A_template (추적표 27행)<br>thesis_v2/baseline/runner.py:run_episode (행 172, 주석·직접)<br>thesis_v2/improved/config.py:<module> (행 53, 주석·직접)<br>thesis_v2/improved/runner.py:run_episode (행 263, 주석·직접)<br>thesis_v2/improved/runner.py:run_episode (행 282, 주석·직접) | thesis_v2/tests/test_mpc.py::test_heading_and_steering_bound_constants (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_heading_and_steering_bound_constants (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_delta0_matches_independent_spec_qp (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_heading_constraint_binds_when_optimum_would_exceed_limit (테스트 내 인용) | MEASURE_PLAN.md:109,260,264,265,270,274,277<br>RESULT_BASELINE.md:28<br>RESULT_IMPROVED.md:53,416<br>RESULT_ROBUSTNESS.md:54<br>ROBUSTNESS_PLAN.md:6,102 |
| REQ-MPC-04a | SPEC 정의<br>`repro/docs/SPEC.md:52`<br>조향 변화율(Δδ) 제약의 위치는 QP가 아니라 후처리 클리핑이다 — p.9-10의 "(3) 제약조건" QP 목록엔 δ,ψ,y… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용) | thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/postprocess.py:apply (추적표 28행) | thesis_v2/tests/test_postprocess.py::test_order_is_rate_limit_then_clip (추적표·함수 명시) | **없음** |
| REQ-MPC-05 | SPEC 정의<br>`repro/docs/SPEC.md:53`<br>횡방향 위치 제약의 상태별 매핑: KEEP_L2→"L2주행" 제약, KEEP_L1→"L1주행" 제약, EVADE_L·RETUR… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용)<br>SETTINGS_DECISION.md §2 (행 27, 절 제목) | thesis_v2/baseline/config.py:<module> (행 36, 주석·직접)<br>thesis_v2/baseline/config.py:POSITION_CONSTRAINTS (추적표 29행)<br>thesis_v2/baseline/metrics.py:y_within_tolerance (행 44, 주석·직접)<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·연속(/))<br>thesis_v2/baseline/mpc.py:solve (추적표 29행) | thesis_v2/tests/test_mpc.py::test_position_constraints_per_state (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_position_constraints_per_state (테스트 내 인용) | MEASURE_PLAN.md:109,139<br>RESULT_BASELINE.md:28<br>RESULT_IMPROVED.md:416<br>ROBUSTNESS_PLAN.md:6,85 |
| REQ-MPC-06 | SPEC 정의<br>`repro/docs/SPEC.md:54`<br>QP 정식화: minimize (1/2)zᵀHz+fᵀz s.t. l≤A_ineq·z≤u, z=[y1,ψ1,δ0,...,yN,ψ… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §8 (행 215, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용)<br>SETTINGS_DECISION.md §20 (행 658, 본문 인용) | thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 7, 주석·직접)<br>thesis_v2/baseline/mpc.py:OSQPMPC.__init__ (추적표 30행) | **없음** | RESULT_BASELINE.md:65<br>RESULT_ROBUSTNESS.md:77 |
| REQ-MPC-07 | SPEC 정의<br>`repro/docs/SPEC.md:55`<br>Fallback: 최적화 실패 시 δ_fallback=−K_p·(y−y_ref), K_p=1.0 | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §11 (행 271, 본문 인용)<br>SETTINGS_DECISION.md §18 (행 455, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 28, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 70, 주석·직접)<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/mpc.py:OSQPMPC.solve (행 257, 주석·직접)<br>thesis_v2/baseline/mpc.py:solve (추적표 31행) | thesis_v2/tests/test_mpc.py::test_fallback_unit_is_rad_per_meter (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_fallback_unit_is_rad_per_meter (테스트 내 인용)<br>thesis_v2/tests/test_mutation_gaps_mpc.py::test_compute_time_ms_is_elapsed_perf_counter_in_milliseconds (테스트 내 인용) | RESULT_BASELINE.md:66<br>RESULT_ROBUSTNESS.md:54,77<br>ROBUSTNESS_PLAN.md:102 |
| REQ-MPC-07a | SPEC 정의<br>`repro/docs/SPEC.md:56`<br>식(7) 단위 확정: K_p=1.0은 rad/m(δ_fallback_rad=−K_p·(y−y_ref), 이후 deg로 변환) | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>SETTINGS_DECISION.md §11 (행 271, 절 제목)<br>SETTINGS_DECISION.md §17 (행 432, 본문 인용) | thesis_v2/baseline/lateral.py:compute_lateral (행 47, 주석·직접)<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 4, 주석·연속(/))<br>thesis_v2/baseline/mpc.py:OSQPMPC.solve (행 257, 주석·연속(/))<br>thesis_v2/baseline/mpc.py:solve (추적표 31행) | thesis_v2/tests/test_mpc.py::test_fallback_unit_is_rad_per_meter (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_fallback_unit_is_rad_per_meter (테스트 내 인용) | **없음** |
| REQ-MPC-07b | SPEC 정의<br>`repro/docs/SPEC.md:57`<br>부호 규약: +y = 좌측(L1 방향), +ψ = 좌회전(반시계, 헤딩 증가), +δ = 좌회전(전륜을 좌측으로) — eq(1… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §11 (행 271, 절 제목) | thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/mpc.py:<module> (행 4, 주석·연속(/))<br>thesis_v2/baseline/mpc.py:solve (추적표 32행)<br>thesis_v2/baseline/vehicle.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/vehicle.py:step (추적표 32행) | thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_negative_target (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_positive_target (추적표·함수 명시)<br>thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_positive_target (테스트 내 인용) | **없음** |
| REQ-MPC-08 | SPEC 정의<br>`repro/docs/SPEC.md:58`<br>MPC는 속도를 결정하지 않음(z벡터에 v 없음, 비용함수에 속도 항 없음) | DESIGN_BASELINE.md §1 (행 8, 본문 인용) | thesis_v2/baseline/mpc.py (추적표 33행)<br>thesis_v2/baseline/mpc.py:<module> (행 3, 주석·범위(~)) | **없음** | RESULT_BASELINE.md:91 |
| REQ-SEN-01 | SPEC 정의<br>`repro/docs/SPEC.md:74`<br>front_gap 계산: LiDAR가 "전방 장애물까지의 거리"를 측정 — 구체적 기하 공식(장애물 통과 후 처리 등) | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §12 (행 289, 본문 인용)<br>SETTINGS_DECISION.md §6 (행 88, 본문 인용)<br>SETTINGS_DECISION.md §7 (행 130, 절 제목) | thesis_v2/baseline/config.py:<module> (행 32, 주석·직접)<br>thesis_v2/baseline/runner.py:<module> (행 11, 주석·직접)<br>thesis_v2/baseline/runner.py:<module> (행 9, 주석·직접)<br>thesis_v2/baseline/sensors.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/sensors.py:<module> (행 9, 주석·직접)<br>thesis_v2/baseline/sensors.py:front_gap (추적표 34행)<br>thesis_v2/baseline/sensors.py:front_gap (행 32, 주석·직접)<br>thesis_v2/improved/sensors.py:front_obstacle_info (행 34, 주석·직접) | thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_corridor_is_vehicle_width_around_y (테스트 내 인용)<br>thesis_v2/tests/test_improved_sensors.py::test_front_obstacle_info_excludes_passed_obstacle (테스트 내 인용)<br>thesis_v2/tests/test_sensors.py::test_front_gap_obstacle_in_corridor (추적표·함수 명시)<br>thesis_v2/tests/test_sensors.py::test_front_gap_obstacle_outside_corridor_ignored (추적표·함수 명시)<br>thesis_v2/tests/test_sensors.py::test_front_gap_picks_nearest_of_multiple (추적표·함수 명시) | MEASURE_PLAN.md:24,26,171<br>RESULT_ROBUSTNESS.md:5<br>ROBUSTNESS_PLAN.md:6 |
| REQ-SEN-02 | SPEC 정의<br>`repro/docs/SPEC.md:75`<br>left_clear 계산: "좌측 차선의 장애물 유무" | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md left_clear (행 225, 본문 인용) | thesis_v2/anomaly/detector_a.py:<module> (행 65, 주석·직접)<br>thesis_v2/baseline/sensors.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/sensors.py:_window_clear (행 48, 주석·직접)<br>thesis_v2/baseline/sensors.py:left_clear (추적표 35행)<br>thesis_v2/baseline/sensors.py:left_clear (행 62, 주석·직접)<br>thesis_v2/baseline/world.py:generate_left_obstacle_scenario (행 115, 주석·직접) | thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_l1_obstacle_is_evaluated_in_l1_window_only (테스트 내 인용)<br>thesis_v2/tests/test_sensors.py::test_left_clear_blocked_by_obstacle_in_l1 (추적표·함수 명시)<br>thesis_v2/tests/test_sensors.py::test_left_clear_unaffected_by_obstacle_in_l2_only (추적표·함수 명시) | ROBUSTNESS_PLAN.md:6 |
| REQ-SEN-03 | SPEC 정의<br>`repro/docs/SPEC.md:76`<br>IR 3개(0.04m 간격, 이진패턴) → ey_line 변환 공식 | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §9 (행 191, 절 제목) | thesis_v2/baseline/config.py:<module> (행 30, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 31, 주석·직접)<br>thesis_v2/baseline/sensors.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/sensors.py:ey_line (행 94, 주석·직접)<br>thesis_v2/baseline/sensors.py:ir_pattern (추적표 36행)<br>thesis_v2/baseline/sensors.py:ir_pattern (행 72, 주석·직접) | thesis_v2/tests/test_sensors.py::test_ir_pattern_to_ey_line (추적표·함수 명시) | ROBUSTNESS_PLAN.md:6 |
| REQ-SEN-04 | SPEC 정의<br>`repro/docs/SPEC.md:37`<br>right_clear(신규, left_clear와 대칭): L2 범위[−0.15,0.15] AND x∈[차체 후단−G_SAFE… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §14 (행 349, 절 제목) | thesis_v2/anomaly/detector_a.py:<module> (행 64, 주석·직접)<br>thesis_v2/baseline/sensors.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/sensors.py:_window_clear (행 48, 주석·연속(/))<br>thesis_v2/baseline/sensors.py:right_clear (추적표 37행)<br>thesis_v2/baseline/sensors.py:right_clear (행 67, 주석·직접) | thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_l1_obstacle_is_evaluated_in_l1_window_only (테스트 내 인용)<br>thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_window_extends_g_safe_min_behind_rear_axle (테스트 내 인용)<br>thesis_v2/tests/test_sensors.py::test_right_clear_blocked_by_obstacle_in_l2 (추적표·함수 명시)<br>thesis_v2/tests/test_sensors.py::test_right_clear_unaffected_by_obstacle_in_l1_only (추적표·함수 명시) | ROBUSTNESS_PLAN.md:6 |
| REQ-SIM-01 | SPEC 정의<br>`repro/docs/SPEC.md:101`<br>도로: 2차선, 차선폭 W=0.30m, L2 중심 y=0, L1 중심 y=0.30 | DESIGN_BASELINE.md §1 (행 8, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 19, 주석·직접)<br>thesis_v2/baseline/config.py:W (추적표 48행)<br>thesis_v2/baseline/world.py (추적표 48행)<br>thesis_v2/baseline/world.py:<module> (행 3, 주석·직접) | thesis_v2/tests/test_config.py::test_fixed_params_match_claude_md (추적표·파일 단위) | MEASURE_PLAN.md:102<br>ROBUSTNESS_PLAN.md:6 |
| REQ-SIM-02 | SPEC 정의<br>`repro/docs/SPEC.md:102`<br>장애물: L2 차선에 정지 장애물 1개(크기 L×B, 차량과 동일 풋프린트로 가정), 위치 X_obs~U(0.5,2.0)m | SETTINGS_DECISION.md left_clear (행 225, 본문 인용)<br>SETTINGS_DECISION.md §12 (행 289, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 44, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 45, 주석·직접)<br>thesis_v2/baseline/world.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/world.py:generate_scenario (추적표 49행)<br>thesis_v2/baseline/world.py:generate_scenario (행 59, 주석·직접) | **없음** | MEASURE_PLAN.md:102<br>ROBUSTNESS_PLAN.md:6,34,122 |
| REQ-SIM-02a | SPEC 정의<br>`repro/docs/SPEC.md:103`<br>"장애물 위치"의 측정 기준점: 차량 후륜(kinematic model 원점) 기준인지, 차체 전단(LiDAR가 실제로 있을 … | SETTINGS_DECISION.md §12 (행 289, 절 제목) | thesis_v2/anomaly/scenarios.py:generate_anomaly_scenario (행 22, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 44, 주석·연속(/))<br>thesis_v2/baseline/world.py:<module> (행 3, 주석·연속(/))<br>thesis_v2/baseline/world.py:generate_front_rear_scenario (행 103, 주석·직접)<br>thesis_v2/baseline/world.py:generate_scenario (추적표 49행) | **없음** | MEASURE_PLAN.md:102<br>ROBUSTNESS_PLAN.md:6 |
| REQ-SIM-03 | SPEC 정의<br>`repro/docs/SPEC.md:104`<br>초기 조건: v0~U(0.3,0.5)m/s, y0~TruncatedNormal(0, 0.05², [−0.15,0.15])(원문… | SETTINGS_DECISION.md 확정된 (행 597, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 44, 주석·연속(/))<br>thesis_v2/baseline/config.py:<module> (행 46, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 47, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 48, 주석·직접)<br>thesis_v2/baseline/world.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/world.py:_sample_truncated_y0 (추적표 50행)<br>thesis_v2/baseline/world.py:_sample_truncated_y0 (행 49, 주석·직접)<br>thesis_v2/baseline/world.py:generate_scenario (행 60, 주석·직접) | **없음** | MEASURE_PLAN.md:102<br>RESULT_BASELINE.md:61<br>RESULT_IMPROVED.md:165<br>RESULT_ROBUSTNESS.md:54,78<br>ROBUSTNESS_PLAN.md:6,35,37,102 |
| REQ-SIM-04 | SPEC 정의<br>`repro/docs/SPEC.md:105`<br>에피소드: 최대 200 step(10s at 20Hz), "안전하게 회피 및 복귀를 완료" 또는 SAFE_STOP 도달 시 종… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §6 (행 88, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 52, 주석·직접)<br>thesis_v2/baseline/runner.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/runner.py:run_episode (추적표 51행) | **없음** | MEASURE_PLAN.md:102<br>ROBUSTNESS_PLAN.md:6 |
| REQ-SIM-05 | SPEC 정의<br>`repro/docs/SPEC.md:106`<br>"완료" 트리거 정의 | SETTINGS_DECISION.md §10 (행 256, 본문 인용)<br>SETTINGS_DECISION.md §6 (행 88, 절 제목) | thesis_v2/baseline/config.py:<module> (행 52, 주석·연속(/))<br>thesis_v2/baseline/runner.py:<module> (행 4, 주석·연속(/))<br>thesis_v2/baseline/runner.py:run_episode (추적표 52행) | thesis_v2/tests/test_runner.py::test_seed_reproducibility (추적표·함수 명시) | MEASURE_PLAN.md:102<br>ROBUSTNESS_PLAN.md:6 |
| REQ-SIM-07 | 정의 없음<br>`SPEC.md·SETTINGS_DECISION.md에 정의 행 없음` | **없음** | thesis_v2/baseline/summary.py:<module> (행 40, 주석·직접) | **없음** | MEASURE_PLAN.md:102,113<br>ROBUSTNESS_PLAN.md:6 |
| REQ-SIM-08 | SPEC 정의<br>`repro/docs/SPEC.md:107`<br>충돌(collision) 판정: 실거리 기반 기하 판정 — front_gap(종방향)만으로는 차선변경 중 옆면·모서리 접촉을 … | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용)<br>SETTINGS_DECISION.md §10 (행 256, 본문 인용)<br>SETTINGS_DECISION.md §8 (행 167, 절 제목) | thesis_v2/baseline/collision.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/collision.py:check_collision (추적표 53행)<br>thesis_v2/baseline/config.py:<module> (행 49, 주석·직접)<br>thesis_v2/baseline/world.py:<module> (행 4, 주석·직접) | thesis_v2/tests/test_collision.py::test_full_overlap_same_footprint (추적표·파일 단위)<br>thesis_v2/tests/test_collision.py::test_no_overlap_far_obstacle (추적표·파일 단위)<br>thesis_v2/tests/test_collision.py::test_partial_overlap (추적표·파일 단위)<br>thesis_v2/tests/test_collision.py::test_rotated_vehicle_corner_pokes_into_obstacle (추적표·파일 단위) | MEASURE_PLAN.md:102,112<br>ROBUSTNESS_PLAN.md:6,147 |
| REQ-SPD-01 | SPEC 정의<br>`repro/docs/SPEC.md:64`<br>v_ref=0.5m/s, KEEP_L2·EVADE_L·KEEP_L1·RETURN_TO_L2 상태에서 유지 | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 56, 주석·직접)<br>thesis_v2/baseline/longitudinal.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (추적표 44행)<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (행 12, 주석·직접)<br>thesis_v2/improved/student_i4/features.py:v_target_label (행 68, 주석·직접) | thesis_v2/tests/test_longitudinal.py::test_v_cmd_per_state (추적표·함수 명시) | MEASURE_PLAN.md:116<br>RESULT_BASELINE.md:29<br>RESULT_ROBUSTNESS.md:71<br>ROBUSTNESS_PLAN.md:94 |
| REQ-SPD-02 | SPEC 정의<br>`repro/docs/SPEC.md:65`<br>SAFE_STOP: v=0으로 설정 | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용) | thesis_v2/baseline/longitudinal.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (추적표 44행)<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (행 11, 주석·직접)<br>thesis_v2/improved/student_i4/features.py:v_target_label (행 68, 주석·연속(/)) | thesis_v2/tests/test_longitudinal.py::test_v_cmd_per_state (추적표·함수 명시) | MEASURE_PLAN.md:116<br>RESULT_BASELINE.md:29 |
| REQ-SPD-03 | SPEC 정의<br>`repro/docs/SPEC.md:66`<br>SAFE_STOP 감속 방식: "가능한 한 빠르게 감속" | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용)<br>SETTINGS_DECISION.md §3 (행 45, 절 제목) | thesis_v2/baseline/longitudinal.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (추적표 45행)<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (행 11, 주석·연속(/)) | thesis_v2/tests/test_longitudinal.py::test_v_cmd_per_state (추적표·함수 명시) | **없음** |
| REQ-SPD-04 | SPEC 정의<br>`repro/docs/SPEC.md:67`<br>G_TRIG=1.2m(회피 시작), G_SAFE_MIN=0.20m(비상정지) | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용) | thesis_v2/baseline/config.py:G_SAFE_MIN (추적표 46행)<br>thesis_v2/baseline/config.py:G_TRIG (추적표 46행)<br>thesis_v2/baseline/longitudinal.py:<module> (행 3, 주석·범위(~)) | thesis_v2/tests/test_config.py::test_fixed_params_match_claude_md (추적표·함수 명시) | **없음** |
| REQ-SPD-05 | SPEC 정의<br>`repro/docs/SPEC.md:68`<br>front_gap은 속도를 직접(연속적으로) 결정하지 않는다 — 속도는 FSM 상태에 의해서만 결정되고(REQ-SPD-01/0… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용) | thesis_v2/baseline/longitudinal.py:<module> (행 3, 주석·범위(~))<br>thesis_v2/baseline/longitudinal.py:compute_v_cmd (추적표 47행) | **없음** | **없음** |
| REQ-STU-01 | SPEC 정의<br>`repro/docs/SPEC.md:122`<br>신경망 구조: 입력9→FC1(256)→FC2(256)→FC3(128)→출력2, ReLU, BatchNorm+Dropout(0.… | **없음** | thesis_v2/improved/student_i4/config.py:<module> (행 62, 주석·직접)<br>thesis_v2/improved/student_i4/config.py:<module> (행 63, 주석·직접)<br>thesis_v2/improved/student_i4/model.py:<module> (행 2, 주석·직접)<br>thesis_v2/improved/student_i4/model.py:StudentPolicy (추적표 76행) | thesis_v2/tests/test_i4_student.py::test_req_stu_01_structure (추적표·함수 명시) | **없음** |
| REQ-STU-02 | SPEC 정의<br>`repro/docs/SPEC.md:123`<br>입력 특징(9차원): v, ey, front_gap, left_clear, state_one_hot(5) | SETTINGS_DECISION.md §20 (행 658, 절 제목) | thesis_v2/improved/student_i4/features.py:<module> (행 2, 주석·직접)<br>thesis_v2/improved/student_i4/features.py:<module> (행 25, 주석·직접)<br>thesis_v2/improved/student_i4/features.py:build_feature_vector (추적표 77행)<br>thesis_v2/improved/student_i4/features.py:build_feature_vector (행 56, 주석·직접)<br>thesis_v2/improved/student_i4/train.py:main (행 35, 주석·직접) | thesis_v2/tests/test_i4_student.py::test_req_stu_02_feature_order_and_fallback (추적표·함수 명시) | MEASURE_PLAN.md:162,172,190<br>RESULT_I4.md:136,201<br>RESULT_STUDENT.md:23,37,203,323<br>STAGE3_SUMMARY.md:33 |
| REQ-STU-02r | SPEC 정의<br>`repro/docs/SPEC.md:126`<br>(3단계 Student v2 전용) 입력 11차원 = REQ-STU-02의 9차원 + ψ(차량 헤딩) + δ_prev(직전 최… | **없음** | **없음** | **없음** | **없음** |
| REQ-STU-03 | SPEC 정의<br>`repro/docs/SPEC.md:124`<br>출력(2차원): δ(deg), v_target(m/s) | **없음** | thesis_v2/improved/student_i4/features.py:<module> (행 2, 주석·직접)<br>thesis_v2/improved/student_i4/features.py:v_target_label (추적표 78행)<br>thesis_v2/improved/student_i4/features.py:v_target_label (행 68, 주석·직접) | thesis_v2/tests/test_i4_student.py::test_req_stu_03_v_target_is_rule_based (추적표·함수 명시) | MEASURE_PLAN.md:162 |
| REQ-STU-04 | SPEC 정의<br>`repro/docs/SPEC.md:125`<br>정규화 통계 | **없음** | **없음** | **없음** | **없음** |
| REQ-VEH-01 | SPEC 정의<br>`repro/docs/SPEC.md:22`<br>Kinematic bicycle model(후륜 중심 기준): ẋ=v·cos(ψ), ẏ=v·sin(ψ), ψ̇=(v/L)·ta… | DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §16 (행 394, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 9, 주석·직접)<br>thesis_v2/baseline/vehicle.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/vehicle.py:step (추적표 9행)<br>thesis_v2/baseline/vehicle.py:step (행 21, 주석·직접) | **없음** | **없음** |
| REQ-VEH-02 | SPEC 정의<br>`repro/docs/SPEC.md:23`<br>차량 파라미터: L=0.20m(축간거리), B=0.15m(차폭), δ_max=±25°, 속도범위 0.0~0.5 m/s, δ_r… | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §5 (행 143, 본문 인용) | thesis_v2/baseline/config.py (추적표 10행)<br>thesis_v2/baseline/config.py:<module> (행 14, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 15, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 20, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 21, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 4, 주석·직접)<br>thesis_v2/baseline/config.py:<module> (행 56, 주석·직접) | thesis_v2/tests/test_config.py::test_fixed_params_match_claude_md (추적표·함수 명시) | MEASURE_PLAN.md:266 |
| REQ-VEH-03 | SPEC 정의<br>`repro/docs/SPEC.md:24`<br>조향각 rate limiting: Δδ_max = 200deg/s × dt(0.05s) = 10°/step, `δ_cmd=cl… | DESIGN_BASELINE.md B-1 (행 238, 본문 인용)<br>DESIGN_BASELINE.md §1 (행 8, 본문 인용)<br>DESIGN_BASELINE.md §2 (행 32, 본문 인용)<br>SETTINGS_DECISION.md §15 (행 386, 본문 인용) | thesis_v2/baseline/config.py:<module> (행 34, 주석·직접)<br>thesis_v2/baseline/postprocess.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/postprocess.py:apply (추적표 11행) | thesis_v2/tests/test_postprocess.py::test_rate_limit_boundary_exact_not_active (추적표·함수 명시)<br>thesis_v2/tests/test_postprocess.py::test_rate_limit_boundary_just_over_active (추적표·함수 명시) | MEASURE_PLAN.md:266 |
| REQ-VEH-04 | SPEC 정의<br>`repro/docs/SPEC.md:25`<br>시뮬레이션 적분법: Euler 적분 | **없음** | thesis_v2/baseline/vehicle.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/vehicle.py:step (추적표 12행)<br>thesis_v2/baseline/vehicle.py:step (행 22, 주석·직접) | **없음** | **없음** |
| REQ-VEH-05 | SPEC 정의<br>`repro/docs/SPEC.md:26`<br>속도(v)에 대한 별도 동역학(가속도/관성) 방정식 없음 — v는 매 스텝 직접 지정되는 입력으로 취급 | SETTINGS_DECISION.md §16 (행 394, 본문 인용)<br>SETTINGS_DECISION.md §3 (행 45, 본문 인용) | thesis_v2/anomaly/scenarios.py:estimated_trigger_step (행 39, 주석·직접)<br>thesis_v2/baseline/longitudinal.py (추적표 13행)<br>thesis_v2/baseline/vehicle.py:<module> (행 3, 주석·직접)<br>thesis_v2/baseline/vehicle.py:step (추적표 13행)<br>thesis_v2/baseline/vehicle.py:step (행 22, 주석·직접) | thesis_v2/tests/test_longitudinal.py::test_v_cmd_per_state (추적표·함수 명시) | **없음** |

## 고아: 테스트 없는 REQ

- REQ-EVAL-01 — SPEC 정의, 코드 연결 0건, 평가 문서 인용 0건
- REQ-EVAL-02 — SPEC 정의, 코드 연결 0건, 평가 문서 인용 0건
- REQ-EVAL-04 — SPEC 정의, 코드 연결 0건, 평가 문서 인용 1건
- REQ-MPC-06 — SPEC 정의, 코드 연결 3건, 평가 문서 인용 2건
- REQ-MPC-08 — SPEC 정의, 코드 연결 2건, 평가 문서 인용 1건
- REQ-SIM-02 — SPEC 정의, 코드 연결 5건, 평가 문서 인용 2건
- REQ-SIM-02a — SPEC 정의, 코드 연결 5건, 평가 문서 인용 2건
- REQ-SIM-03 — SPEC 정의, 코드 연결 8건, 평가 문서 인용 5건
- REQ-SIM-04 — SPEC 정의, 코드 연결 3건, 평가 문서 인용 2건
- REQ-SIM-07 — 정의 없음, 코드 연결 1건, 평가 문서 인용 2건
- REQ-SPD-05 — SPEC 정의, 코드 연결 2건, 평가 문서 인용 0건
- REQ-STU-02r — SPEC 정의, 코드 연결 0건, 평가 문서 인용 0건
- REQ-STU-04 — SPEC 정의, 코드 연결 0건, 평가 문서 인용 0건
- REQ-VEH-01 — SPEC 정의, 코드 연결 4건, 평가 문서 인용 0건
- REQ-VEH-04 — SPEC 정의, 코드 연결 3건, 평가 문서 인용 0건

## 역방향: 테스트 → REQ

| 테스트 함수 | 변형 수 | REQ | 추적표 비-REQ 행 | 고아 범주 |
|---|---:|---|---|---|
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_check_match_removes_tmp_and_ignores_diag` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_check_mismatch_keeps_tmp_and_prints_diff` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_check_only_subset_compares_selected` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_check_only_subset_mismatch` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_check_only_without_p0_uses_saved_p0_baseline` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_compute_runs_only_selected_combos` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_determinism` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_diff_csv_text_reports_row_column_values` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_freeze_ok_requires_clean_and_cl_tag` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_main_check_only_argument_errors` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_main_refuses_eval_seeds_without_freeze` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p0_matches_observational_runner` | 8 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p1_stops_immediately_on_first_alarm` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p2_ir_stuck_overrides_ey_without_stopping` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p2_left_clear_stuck_overrides_lc_without_stopping` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p2_requires_detector` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p2_right_clear_stuck_overrides_rc_without_stopping` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_p2_steer_delay_stops_like_p1` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_parse_check_only` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_summarize_timing_flags_hit_episodes` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_closed_loop.py::test_timing_diag_recorded_but_not_in_episode_row` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_channel_scores_cover_all_channels` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_detector_a_with_gyro_does_not_change_control` | 3 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_fault_raises_expected_channel` | 5 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_gyro_without_noise_is_finite_difference` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_ir_dropout_masks_ey_but_not_ir_miss` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_llr_constants` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_normal_noise_residuals_are_standardized` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_normal_residuals_are_zero_without_noise` | 2 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_right_clear_stuck_raises_rc` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_threshold_quantile_higher` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_tracker_error_bounded_by_gate_under_slow_drift` | 6 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_tracker_error_bounded_during_50_step_freeze_with_noise` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_tracker_keeps_obstacles_per_lane` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_a.py::test_tracker_not_contaminated_by_frozen_lidar` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_b.py::test_detector_b_does_not_change_control` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_b.py::test_features_reflect_dropout_flag` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_b.py::test_norm_zero_std_safe` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_b.py::test_online_equals_offline` | 2 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_b.py::test_step_features_shape_and_onehot` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_b.py::test_windows_and_stats` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_timing.py::test_stats_budget_ratio` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_detector_timing.py::test_timed_loop_matches_observational_runner` | 4 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_ap_no_positive_is_none` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_ap_perfect_ranking` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_auc_perfect_separation` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_auc_ties_are_half` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_bootstrap_episode_stat_deterministic` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_compute_and_summarize_small` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_expected_fine_spike_direction` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_freeze_ok_requires_clean_and_tagged` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_label_array_permanent_and_bounded` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_main_refuses_eval_seeds_without_freeze` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_run_record_decouples_inject_and_assumed_sigma` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_step_prf1_basic` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_eval_offline.py::test_wilson_matches_module` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_freeze_holds_last_good_value_including_obstacle_info` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_identity_without_spec` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_ir_and_clear_faults` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_label_window` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_off_road_definition` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_runner_labels_match_spec` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_sample_fault_deterministic_and_after_warmup` | 9 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_scenario_range_and_determinism` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_spike_and_dropout_keep_obstacle_info_consistent` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_faults.py::test_steer_delay_and_stuck` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_golden_equivalence.py::test_equivalent_to_improved_v2` | 18 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_golden_equivalence.py::test_equivalent_with_s4_low_noise` | 2 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_channel_names_are_b_then_a` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_detector_hybrid_does_not_change_control` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_detector_hybrid_online_equals_offline` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_hybrid_recorder_does_not_change_control` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_norm_round_trips_and_rejects_wrong_channels` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_score_episode_deterministic_and_masked_prefix_zero` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_hybrid.py::test_step_matrix_shape_and_a_columns_match_residuals` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_p1_stop_on_first_step_is_detection_stop` | 2 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_p1_stop_step_collision_is_classified_as_collision` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_p1_stop_step_departure_is_classified_as_departure` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_p1_stop_step_departure_without_termination_is_detection_stop` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_p2_override_feeds_controller_the_overridden_value` | 3 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_unnecessary_stop_harmful_fault_boundary` | 3 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_unnecessary_stop_harmless_fault` | 3 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_unnecessary_stop_normal_episode` | 2 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py::test_unnecessary_stop_requires_detection_stop_outcome` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_alarm_requires_score_strictly_above_threshold` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_corridor_ignores_tracks_beyond_lidar_range` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_corridor_is_vehicle_width_around_y` | 2 | REQ-SEN-01 | — |  |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_corridor_longitudinal_margin_near_obstacle_end` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_corridor_range_uses_distance_ahead_of_front` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_dead_reckoning_and_front_point_match_plant_while_heading_is_nonzero` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_fg_residual_valid_only_if_previous_gap_positive` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_front_gap_without_obstacle_info_does_not_create_track` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_l1_obstacle_is_evaluated_in_l1_window_only` | 1 | REQ-SEN-02, REQ-SEN-04 | — |  |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_no_return_measurement_does_not_create_track` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_psi_residual_masked_when_previous_speed_is_zero` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_track_position_is_mean_of_accepted_measurements` | 1 | — | — | 이상탐지(REQ 체계 밖) |
| `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py::test_window_extends_g_safe_min_behind_rear_axle` | 1 | REQ-SEN-04 | — |  |
| `thesis_v2/tests/test_check_golden.py::test_matches_golden` | 6 | — | (비-REQ 행) 교차 환경 재현성(golden) | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_collision.py::test_full_overlap_same_footprint` | 1 | REQ-SIM-08 | — |  |
| `thesis_v2/tests/test_collision.py::test_no_overlap_far_obstacle` | 1 | REQ-SIM-08 | — |  |
| `thesis_v2/tests/test_collision.py::test_partial_overlap` | 1 | REQ-SIM-08 | — |  |
| `thesis_v2/tests/test_collision.py::test_rotated_vehicle_corner_pokes_into_obstacle` | 1 | REQ-SIM-08 | — |  |
| `thesis_v2/tests/test_config.py::test_fixed_params_match_claude_md` | 1 | REQ-MPC-03, REQ-SIM-01, REQ-SPD-04, REQ-VEH-02 | — |  |
| `thesis_v2/tests/test_envinfo.py::test_collect_env_info_does_not_crash_and_has_power_fields` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_envinfo.py::test_meets_official_condition_with_user_confirmation_equals_ac_status` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_envinfo.py::test_meets_official_condition_without_confirmation_requires_overlay` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_envinfo.py::test_overlay_guid_matcher` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_envinfo.py::test_power_mode_confirmed_flag_recorded_with_timestamp` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_fsm.py::test_any_state_to_safe_stop_positive` | 1 | REQ-FSM-02b | — |  |
| `thesis_v2/tests/test_fsm.py::test_cooldown_blocks_evade_to_keep_l1` | 1 | REQ-FSM-03, REQ-FSM-03a | — |  |
| `thesis_v2/tests/test_fsm.py::test_cooldown_blocks_keep_l1_to_return` | 1 | REQ-FSM-03, REQ-FSM-03a | — |  |
| `thesis_v2/tests/test_fsm.py::test_cooldown_blocks_keep_l2_to_evade` | 1 | REQ-FSM-03, REQ-FSM-03a | — |  |
| `thesis_v2/tests/test_fsm.py::test_cooldown_blocks_return_to_keep_l2` | 1 | REQ-FSM-03, REQ-FSM-03a | — |  |
| `thesis_v2/tests/test_fsm.py::test_cooldown_blocks_safe_stop` | 1 | REQ-FSM-03, REQ-FSM-03a | — |  |
| `thesis_v2/tests/test_fsm.py::test_evade_l_to_keep_l1_negative_far_from_l1` | 1 | REQ-FSM-02c | — |  |
| `thesis_v2/tests/test_fsm.py::test_evade_l_to_keep_l1_positive` | 1 | REQ-FSM-02c | — |  |
| `thesis_v2/tests/test_fsm.py::test_initial_fsm_cooldown_pre_expired` | 1 | REQ-FSM-01, REQ-FSM-03b | — |  |
| `thesis_v2/tests/test_fsm.py::test_keep_l1_to_return_negative_right_not_clear` | 1 | REQ-FSM-02d | — |  |
| `thesis_v2/tests/test_fsm.py::test_keep_l1_to_return_positive` | 1 | REQ-FSM-02d | — |  |
| `thesis_v2/tests/test_fsm.py::test_keep_l2_to_evade_l_negative_not_left_clear` | 1 | REQ-FSM-02a | — |  |
| `thesis_v2/tests/test_fsm.py::test_keep_l2_to_evade_l_positive` | 1 | REQ-FSM-02a | — |  |
| `thesis_v2/tests/test_fsm.py::test_return_to_keep_l2_negative_psi_too_large` | 1 | REQ-FSM-02e | — |  |
| `thesis_v2/tests/test_fsm.py::test_return_to_keep_l2_positive` | 1 | REQ-FSM-02e | — |  |
| `thesis_v2/tests/test_fsm.py::test_safe_stop_condition_negative_left_clear_true` | 1 | REQ-FSM-02b | — |  |
| `thesis_v2/tests/test_fsm.py::test_safe_stop_from_every_state` | 5 | REQ-FSM-02b | — |  |
| `thesis_v2/tests/test_fsm.py::test_safe_stop_is_terminal_no_recovery` | 1 | REQ-FSM-04 | — |  |
| `thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d1_front_gap_lt_g_trig` | 1 | REQ-FSM-02a | — |  |
| `thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form` | 1 | REQ-FSM-02d | — |  |
| `thesis_v2/tests/test_fsm_mcdc.py::test_mcdc_d4_abs_y_le_near_l2` | 1 | REQ-FSM-02e | — |  |
| `thesis_v2/tests/test_i4_student.py::test_i4_closed_loop_matches_improved_runner_with_mpc` | 2 | — | (비-REQ 행) 폐루프 루프 = improved.runner(§3-2) | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_i4_student.py::test_i4_norm_stats_zero_std_safe` | 1 | — | (비-REQ 행) std=0 정규화 가드(§1-3) | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_i4_student.py::test_i4_recorder_does_not_change_episode` | 1 | — | (비-REQ 행) 입력 캡처가 주행을 바꾸지 않음(§1-3) | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_i4_student.py::test_i4_stratified_split_fixed_seed_deterministic` | 1 | — | (비-REQ 행) 계층 분할·고정 seed(§1-5) | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_i4_student.py::test_req_stu_01_structure` | 1 | REQ-STU-01 | — |  |
| `thesis_v2/tests/test_i4_student.py::test_req_stu_02_feature_order_and_fallback` | 1 | REQ-STU-02 | — |  |
| `thesis_v2/tests/test_i4_student.py::test_req_stu_02r_captured_delta_prev_is_previous_final` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_i4_student.py::test_req_stu_02r_variant_order_and_dims` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_i4_student.py::test_req_stu_03_v_target_is_rule_based` | 1 | REQ-STU-03 | — |  |
| `thesis_v2/tests/test_improved_equivalence.py::test_improved_runner_matches_golden_when_flags_off` | 6 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_equivalence.py::test_single_call_matches_baseline_when_flags_off` | 5 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_golden_determinism_three_runs` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_max_iter_default_is_972` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_off_setup_kwargs_identical_to_v1` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_on_requires_max_iter` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_on_uses_972_by_default` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_product_instance_keeps_time_limit_safety_net` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_time_limit_fingerprint_table` | 14 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_time_limit_fingerprint_without_check_termination` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_time_limit_hit_false_without_cut` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_time_limit_hit_set_for_any_reported_status` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_time_limit_off_fixture_reaches_osqp_settings` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_time_limit_safety_net_reachable` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_i5_tiny_iter_cap_triggers_max_iter_status_and_hard_check` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_i5.py::test_norm_logging_fields_present_and_consistent` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i1_off_allows_immediate_large_jump` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i1_on_clamps_relative_to_nonzero_delta_prev` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i1_on_clamps_to_rate_from_delta_prev` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i1b_off_reports_infeasible_on_known_hard_case` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i1b_on_solves_the_same_known_hard_case` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i1b_zero_violation_when_feasible` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i2_no_effect_when_obstacle_far_away` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i2_prime_narrow_variant_raises_psi_lower_bound_and_uses_smaller_margin` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i2_raises_lower_bound_within_obstacle_window` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i2_solve_pushes_higher_than_without_i2_when_obstacle_adjacent` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i3_off_never_sets_warm_start_shift_used` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i3_shifts_previous_successful_solution_on_failure` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_i3_uses_proportional_fallback_when_no_prior_solution` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_mpc.py::test_margin_i2_value` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_sensors.py::test_front_obstacle_info_excludes_passed_obstacle` | 1 | REQ-SEN-01 | — |  |
| `thesis_v2/tests/test_improved_sensors.py::test_front_obstacle_info_matches_front_gap_and_reports_bounds` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_sensors.py::test_front_obstacle_info_none_when_out_of_corridor` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_improved_sensors.py::test_front_obstacle_info_picks_nearest` | 1 | — | — | improved(SPEC에 REQ 없음) |
| `thesis_v2/tests/test_lateral.py::test_evade_return_always_mpc_when_detected` | 2 | REQ-LAT-02 | — |  |
| `thesis_v2/tests/test_lateral.py::test_evade_return_always_mpc_when_not_detected` | 2 | REQ-LAT-02 | — |  |
| `thesis_v2/tests/test_lateral.py::test_keep_state_line_follow_when_detected` | 2 | REQ-LAT-01, REQ-LAT-04 | — |  |
| `thesis_v2/tests/test_lateral.py::test_keep_state_mpc_when_not_detected` | 2 | REQ-LAT-03, REQ-LAT-04 | — |  |
| `thesis_v2/tests/test_lateral.py::test_safe_stop_does_not_call_mpc` | 1 | REQ-LAT-05 | — |  |
| `thesis_v2/tests/test_lateral.py::test_safe_stop_holds_last_delta_regardless_of_ey` | 3 | REQ-LAT-05 | — |  |
| `thesis_v2/tests/test_logger.py::test_logger_save_npz_roundtrip` | 1 | — | (비-REQ 행) 로거 스키마(§3) | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_logger.py::test_logger_schema_has_all_fields` | 1 | — | (비-REQ 행) 로거 스키마(§3) | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_longitudinal.py::test_v_cmd_per_state` | 5 | REQ-SPD-01, REQ-SPD-02, REQ-SPD-03, REQ-VEH-05 | — |  |
| `thesis_v2/tests/test_metrics.py::test_classify_clip_none_when_within_bound` | 1 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_classify_clip_numerical_within_eps` | 1 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_classify_clip_violation_beyond_eps` | 1 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_delta_within_tolerance_boundary` | 1 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_is_saturated_boundary` | 1 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_psi_within_tolerance_boundary` | 1 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_y_within_tolerance_per_state` | 4 | — | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_metrics.py::test_y_within_tolerance_safe_stop_is_not_applicable` | 1 | REQ-LAT-05 | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS |  |
| `thesis_v2/tests/test_mpc.py::test_fallback_unit_is_rad_per_meter` | 1 | REQ-MPC-07, REQ-MPC-07a | (비-REQ 행) OSQP 솔버 설정(§18) |  |
| `thesis_v2/tests/test_mpc.py::test_heading_and_steering_bound_constants` | 1 | REQ-MPC-04 | (비-REQ 행) OSQP 솔버 설정(§18) |  |
| `thesis_v2/tests/test_mpc.py::test_hessian_has_offdiagonal_rddelta_terms` | 1 | REQ-MPC-02, REQ-MPC-03a | (비-REQ 행) OSQP 솔버 설정(§18) |  |
| `thesis_v2/tests/test_mpc.py::test_position_constraints_per_state` | 4 | REQ-MPC-05 | (비-REQ 행) OSQP 솔버 설정(§18) |  |
| `thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_negative_target` | 1 | REQ-MPC-01, REQ-MPC-07b | (비-REQ 행) OSQP 솔버 설정(§18) |  |
| `thesis_v2/tests/test_mpc.py::test_sign_convention_steers_toward_positive_target` | 1 | REQ-MPC-01, REQ-MPC-07b | (비-REQ 행) OSQP 솔버 설정(§18) |  |
| `thesis_v2/tests/test_mutation_gaps_fsm.py::test_keep_l1_return_requires_elapsed_strictly_above_t_keep_l1_min` | 1 | REQ-FSM-02d | — |  |
| `thesis_v2/tests/test_mutation_gaps_fsm.py::test_return_to_keep_l2_accepts_psi_exactly_limit` | 1 | REQ-FSM-02e | — |  |
| `thesis_v2/tests/test_mutation_gaps_fsm.py::test_return_to_keep_l2_accepts_y_exactly_near_l2` | 1 | REQ-FSM-02e | — |  |
| `thesis_v2/tests/test_mutation_gaps_fsm.py::test_safe_stop_requires_front_gap_strictly_below_g_safe_min` | 1 | REQ-FSM-02b | — |  |
| `thesis_v2/tests/test_mutation_gaps_mpc.py::test_compute_time_ms_is_elapsed_perf_counter_in_milliseconds` | 2 | REQ-EVAL-03, REQ-MPC-07 | — |  |
| `thesis_v2/tests/test_mutation_gaps_mpc.py::test_delta0_matches_independent_spec_qp` | 7 | REQ-MPC-01, REQ-MPC-02, REQ-MPC-03, REQ-MPC-03a, REQ-MPC-04 | — |  |
| `thesis_v2/tests/test_mutation_gaps_mpc.py::test_heading_constraint_binds_when_optimum_would_exceed_limit` | 1 | REQ-MPC-01, REQ-MPC-04 | — |  |
| `thesis_v2/tests/test_postprocess.py::test_clip_boundary_exact_not_active` | 1 | — | — | 기타 |
| `thesis_v2/tests/test_postprocess.py::test_clip_boundary_just_over_active` | 1 | — | — | 기타 |
| `thesis_v2/tests/test_postprocess.py::test_order_is_rate_limit_then_clip` | 1 | REQ-MPC-04a | (비-REQ 행) 후처리 순서(§15) |  |
| `thesis_v2/tests/test_postprocess.py::test_rate_limit_boundary_exact_not_active` | 1 | REQ-VEH-03 | — |  |
| `thesis_v2/tests/test_postprocess.py::test_rate_limit_boundary_just_over_active` | 1 | REQ-VEH-03 | — |  |
| `thesis_v2/tests/test_run_cli.py::test_power_mode_confirmed_flag_reaches_env_json` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_run_cli.py::test_without_flag_defaults_to_not_confirmed` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_runner.py::test_collision_has_priority_over_safe_stop_same_step` | 1 | REQ-CTRL-01 | (비-REQ 행) 스텝순서(충돌 우선) |  |
| `thesis_v2/tests/test_runner.py::test_metrics_counts_are_internally_consistent` | 1 | REQ-CTRL-01 | (비-REQ 행) 제약 만족/위반, clip 세분류, 조향 포화(MEAS |  |
| `thesis_v2/tests/test_runner.py::test_safe_stop_holds_last_steering_and_does_not_crash` | 1 | REQ-CTRL-01, REQ-LAT-05 | — |  |
| `thesis_v2/tests/test_runner.py::test_seed_reproducibility` | 1 | REQ-CTRL-01, REQ-SIM-05 | — |  |
| `thesis_v2/tests/test_s7b_precheck_front_gap.py::test_front_gap_obstacle_directly_ahead_is_normal_positive_gap` | 1 | — | — | 기타 |
| `thesis_v2/tests/test_s7b_precheck_front_gap.py::test_front_gap_obstacle_fully_behind_rear_is_excluded` | 1 | — | — | 기타 |
| `thesis_v2/tests/test_s7b_precheck_front_gap.py::test_front_gap_obstacle_overlapping_vehicle_body_is_zero` | 1 | — | — | 기타 |
| `thesis_v2/tests/test_sensors.py::test_front_gap_obstacle_in_corridor` | 1 | REQ-SEN-01 | — |  |
| `thesis_v2/tests/test_sensors.py::test_front_gap_obstacle_outside_corridor_ignored` | 1 | REQ-SEN-01 | — |  |
| `thesis_v2/tests/test_sensors.py::test_front_gap_picks_nearest_of_multiple` | 1 | REQ-SEN-01 | — |  |
| `thesis_v2/tests/test_sensors.py::test_ir_pattern_to_ey_line` | 6 | REQ-SEN-03 | — |  |
| `thesis_v2/tests/test_sensors.py::test_left_clear_blocked_by_obstacle_in_l1` | 1 | REQ-SEN-02 | — |  |
| `thesis_v2/tests/test_sensors.py::test_left_clear_unaffected_by_obstacle_in_l2_only` | 1 | REQ-SEN-02 | — |  |
| `thesis_v2/tests/test_sensors.py::test_right_clear_blocked_by_obstacle_in_l2` | 1 | REQ-SEN-04 | — |  |
| `thesis_v2/tests/test_sensors.py::test_right_clear_unaffected_by_obstacle_in_l1_only` | 1 | REQ-SEN-04 | — |  |
| `thesis_v2/tests/test_summary.py::test_empty_results_do_not_crash` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_expected_outcome_left_obstacle_is_safe_stop` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_expected_outcome_paper_is_success` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_max_call_info_excluding_first_call_is_never_first` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_max_call_info_matches_actual_max` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_max_excluding_first_call_le_max` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_percentiles_present_and_ordered` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_solver_fail_and_fallback_totals_present` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_step_time_ms_has_budget_pct` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_step_time_ms_is_at_least_mpc_solve_time` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_step_time_ms_max_excluding_first_call_le_max` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_step_time_ms_present_and_ordered` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_summary_success_and_collision_ci_present_and_formatted` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_wilson_ci_bounds_contain_point_estimate` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_wilson_ci_known_reference_p50_n100` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_wilson_ci_none_for_zero_n` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |
| `thesis_v2/tests/test_summary.py::test_wilson_ci_zero_successes_lower_bound_is_zero` | 1 | — | — | 인프라·도구(요구사항 수준 아님) |

## 역방향: 코드(함수) → REQ

| 위치(파일:정의) | 인용 REQ | 정의 없는 REQ |
|---|---|---|
| `thesis_v2/anomaly/detector_a.py:<module>` | REQ-SEN-02, REQ-SEN-04 | — |
| `thesis_v2/anomaly/scenarios.py:estimated_trigger_step` | REQ-VEH-05 | — |
| `thesis_v2/anomaly/scenarios.py:generate_anomaly_scenario` | REQ-SIM-02a | — |
| `thesis_v2/baseline/collision.py:<module>` | REQ-SIM-08 | — |
| `thesis_v2/baseline/config.py:<module>` | REQ-FSM-02a, REQ-FSM-02b, REQ-FSM-02c, REQ-FSM-02d, REQ-FSM-02e, REQ-FSM-03, REQ-LAT-01, REQ-MPC-03, REQ-MPC-04, REQ-MPC-05, REQ-MPC-07, REQ-SEN-01, REQ-SEN-03, REQ-SIM-01, REQ-SIM-02, REQ-SIM-02a, REQ-SIM-03, REQ-SIM-04, REQ-SIM-05, REQ-SIM-08, REQ-SPD-01, REQ-VEH-01, REQ-VEH-02, REQ-VEH-03 | — |
| `thesis_v2/baseline/fsm.py:<module>` | REQ-FSM-01, REQ-FSM-02a, REQ-FSM-02b, REQ-FSM-02c, REQ-FSM-02d, REQ-FSM-02e, REQ-FSM-03, REQ-FSM-03a, REQ-FSM-03b, REQ-FSM-04 | — |
| `thesis_v2/baseline/fsm.py:FSM` | REQ-FSM-02d, REQ-FSM-03 | — |
| `thesis_v2/baseline/fsm.py:initial_fsm` | REQ-FSM-03b | — |
| `thesis_v2/baseline/fsm.py:step` | REQ-FSM-02a, REQ-FSM-02b, REQ-FSM-02c, REQ-FSM-02d, REQ-FSM-02e, REQ-FSM-03a, REQ-FSM-04 | — |
| `thesis_v2/baseline/lateral.py:<module>` | REQ-LAT-01, REQ-LAT-02, REQ-LAT-03, REQ-LAT-04, REQ-LAT-05 | — |
| `thesis_v2/baseline/lateral.py:compute_lateral` | REQ-LAT-01, REQ-LAT-02, REQ-LAT-03, REQ-LAT-04, REQ-LAT-05, REQ-MPC-07a | — |
| `thesis_v2/baseline/longitudinal.py:<module>` | REQ-SPD-01, REQ-SPD-02, REQ-SPD-03, REQ-SPD-04, REQ-SPD-05 | — |
| `thesis_v2/baseline/longitudinal.py:compute_v_cmd` | REQ-SPD-01, REQ-SPD-02, REQ-SPD-03 | — |
| `thesis_v2/baseline/metrics.py:delta_within_tolerance` | REQ-MPC-04 | — |
| `thesis_v2/baseline/metrics.py:psi_within_tolerance` | REQ-MPC-04 | — |
| `thesis_v2/baseline/metrics.py:y_within_tolerance` | REQ-LAT-05, REQ-MPC-05 | — |
| `thesis_v2/baseline/mpc.py:<module>` | REQ-MPC-01, REQ-MPC-02, REQ-MPC-03, REQ-MPC-03a, REQ-MPC-04, REQ-MPC-04a, REQ-MPC-05, REQ-MPC-06, REQ-MPC-07, REQ-MPC-07a, REQ-MPC-07b, REQ-MPC-08 | — |
| `thesis_v2/baseline/mpc.py:OSQPMPC._build_A_template` | REQ-MPC-04 | — |
| `thesis_v2/baseline/mpc.py:OSQPMPC._build_P` | REQ-MPC-02, REQ-MPC-03a | — |
| `thesis_v2/baseline/mpc.py:OSQPMPC.solve` | REQ-MPC-07, REQ-MPC-07a | — |
| `thesis_v2/baseline/postprocess.py:<module>` | REQ-VEH-03 | — |
| `thesis_v2/baseline/runner.py:<module>` | REQ-SEN-01, REQ-SIM-04, REQ-SIM-05 | — |
| `thesis_v2/baseline/runner.py:run_episode` | REQ-LAT-05, REQ-MPC-04 | — |
| `thesis_v2/baseline/sensors.py:<module>` | REQ-SEN-01, REQ-SEN-02, REQ-SEN-03, REQ-SEN-04 | — |
| `thesis_v2/baseline/sensors.py:_window_clear` | REQ-SEN-02, REQ-SEN-04 | — |
| `thesis_v2/baseline/sensors.py:ey_line` | REQ-LAT-03, REQ-SEN-03 | — |
| `thesis_v2/baseline/sensors.py:front_gap` | REQ-SEN-01 | — |
| `thesis_v2/baseline/sensors.py:ir_pattern` | REQ-SEN-03 | — |
| `thesis_v2/baseline/sensors.py:left_clear` | REQ-SEN-02 | — |
| `thesis_v2/baseline/sensors.py:right_clear` | REQ-SEN-04 | — |
| `thesis_v2/baseline/summary.py:<module>` | REQ-FSM-02b, REQ-SIM-07 | REQ-SIM-07 |
| `thesis_v2/baseline/summary.py:_step_time_stats` | REQ-EVAL-03 | — |
| `thesis_v2/baseline/summary.py:build_summary` | REQ-FSM-02b, REQ-LAT-05 | — |
| `thesis_v2/baseline/vehicle.py:<module>` | REQ-MPC-07b, REQ-VEH-01, REQ-VEH-04, REQ-VEH-05 | — |
| `thesis_v2/baseline/vehicle.py:step` | REQ-VEH-01, REQ-VEH-04, REQ-VEH-05 | — |
| `thesis_v2/baseline/world.py:<module>` | REQ-SIM-01, REQ-SIM-02, REQ-SIM-02a, REQ-SIM-03, REQ-SIM-08 | — |
| `thesis_v2/baseline/world.py:_sample_truncated_y0` | REQ-SIM-03 | — |
| `thesis_v2/baseline/world.py:generate_front_rear_scenario` | REQ-SIM-02a | — |
| `thesis_v2/baseline/world.py:generate_left_obstacle_scenario` | REQ-FSM-02b, REQ-SEN-02 | — |
| `thesis_v2/baseline/world.py:generate_scenario` | REQ-SIM-02, REQ-SIM-03 | — |
| `thesis_v2/improved/config.py:<module>` | REQ-FSM-02e, REQ-MPC-04 | — |
| `thesis_v2/improved/lateral.py:<module>` | REQ-LAT-01, REQ-LAT-02, REQ-LAT-03, REQ-LAT-04, REQ-LAT-05 | — |
| `thesis_v2/improved/mpc.py:ImprovedMPC._build_P` | REQ-MPC-02, REQ-MPC-03a | — |
| `thesis_v2/improved/runner.py:run_episode` | REQ-MPC-04 | — |
| `thesis_v2/improved/sensors.py:front_obstacle_info` | REQ-SEN-01 | — |
| `thesis_v2/improved/student_i4/config.py:<module>` | REQ-STU-01 | — |
| `thesis_v2/improved/student_i4/features.py:<module>` | REQ-LAT-02, REQ-LAT-03, REQ-LAT-05, REQ-STU-02, REQ-STU-03 | — |
| `thesis_v2/improved/student_i4/features.py:build_feature_vector` | REQ-STU-02 | — |
| `thesis_v2/improved/student_i4/features.py:v_target_label` | REQ-SPD-01, REQ-SPD-02, REQ-STU-03 | — |
| `thesis_v2/improved/student_i4/model.py:<module>` | REQ-STU-01 | — |
| `thesis_v2/improved/student_i4/train.py:main` | REQ-STU-02 | — |

## TRACEABILITY.md 비-REQ 행

- `thesis_v2/tests/TRACEABILITY.md:54` 스텝순서(충돌 우선) — 테스트 1개
- `thesis_v2/tests/TRACEABILITY.md:55` 로거 스키마(§3) — 테스트 2개
- `thesis_v2/tests/TRACEABILITY.md:56` 후처리 순서(§15) — 테스트 1개
- `thesis_v2/tests/TRACEABILITY.md:57` OSQP 솔버 설정(§18) — 테스트 6개
- `thesis_v2/tests/TRACEABILITY.md:58` 제약 만족/위반, clip 세분류, 조향 포화(MEASURE_PLAN.md §18 원칙) — 테스트 9개
- `thesis_v2/tests/TRACEABILITY.md:59` summary.json 집계 — 테스트 0개
- `thesis_v2/tests/TRACEABILITY.md:60` env.json 기록 — 테스트 0개
- `thesis_v2/tests/TRACEABILITY.md:61` 교차 환경 재현성(golden) — 테스트 1개
- `thesis_v2/tests/TRACEABILITY.md:79` 입력 캡처가 주행을 바꾸지 않음(§1-3) — 테스트 1개
- `thesis_v2/tests/TRACEABILITY.md:80` 계층 분할·고정 seed(§1-5) — 테스트 1개
- `thesis_v2/tests/TRACEABILITY.md:81` std=0 정규화 가드(§1-3) — 테스트 1개
- `thesis_v2/tests/TRACEABILITY.md:82` 폐루프 루프 = improved.runner(§3-2) — 테스트 1개

## TRACEABILITY.md에서 해석하지 못한 표기

- (없음)

## 이상탐지 확장: DESIGN 절 → 스크립트 → 결과 폴더 (REQ 체계 밖, 별도 표)

항목 목록은 사람이 고른 것이다(`ANOMALY_CHAIN`). 절 제목·경로 존재와, 스크립트 소스의 폴더 태그 문자열·폴더 이름 일치는 생성 때마다 자동 확인한다.

| 항목 | DESIGN.md 절 | 스크립트 | 결과 폴더 | 태그 확인 |
|---|---|---|---|---|
| 탐지기 A 임계값(iteration 3) | §13(행 198), §18(행 500) | `thesis_v2/anomaly/calibrate_a.py` | `thesis_v2/results/anomaly/20261002_104706_3층PC108_it3_threshold_a` | 예 |
| 탐지기 B1·B2 학습(iteration 2) | §15(행 378), §17(행 423) | `thesis_v2/anomaly/train_b.py` | `thesis_v2/results/anomaly/20261002_001009_DESKTOP-MDCKRJS_it2_train_b` | 예 |
| 하이브리드 학습(iteration 3) | §20(행 606) | `thesis_v2/anomaly/train_hybrid.py` | `thesis_v2/results/anomaly/20261002_111909_3층PC108_it3_train_hybrid` | 예 |
| 오프라인 평가(seed 4000~4099) | §13(행 198), §19(행 560), §21(행 688) | `thesis_v2/anomaly/eval_offline.py` | `thesis_v2/results/anomaly/20261002_145638_3층PC108_it3_eval_offline_eval` | 예 |
| 오프라인 평가 재현 확인(--check) | §27(행 1346) | `thesis_v2/anomaly/eval_offline.py` | `thesis_v2/results/anomaly/20261012_3층PC109_run_logs` | — (로그 폴더) |
| 폐루프 평가(seed 5000~5099, 6조합 = 11 run × 100 seed = 1,100회) | §24(행 885) | `thesis_v2/anomaly/closed_loop.py` | `thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval` | 예 |
| 폐루프 평가 재현 확인(--check) | §28(행 1372) | `thesis_v2/anomaly/closed_loop.py` | `thesis_v2/results/anomaly/20261012_3층PC109_run_logs` | — (로그 폴더) |
| 탐지기 계산 시간(공식 조건) | §29(행 1402) | `thesis_v2/anomaly/benchmark_detector_timing.py` | `thesis_v2/results/anomaly/20261012_232824_DESKTOP-MDCKRJS_detector_timing` | 예 |
