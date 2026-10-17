# 추적표 (REQ ID -> 코드 위치 -> 테스트)

`DESIGN_BASELINE.md` §5에서 예고된 추적표. baseline(`thesis_v2/baseline/`)에 실제로 구현된
REQ만 채웁니다. REQ-EVAL-*(측정 지표 정의)는 코드가 아니라 2단계-C/D의 측정 산출물이라 이
표의 대상이 아닙니다(해당 시점에 `MEASURE_PLAN.md` 기준으로 별도 확인).

| REQ ID | 코드 위치 | 테스트 |
|---|---|---|
| REQ-VEH-01 | `vehicle.py:step` | (직접 단위테스트 없음 — REQ-MPC-07b 부호규약 테스트로 간접 확인) |
| REQ-VEH-02 | `config.py` (고정 파라미터) | `test_config.py::test_fixed_params_match_claude_md` |
| REQ-VEH-03 | `postprocess.py:apply`(rate limit) | `test_postprocess.py::test_rate_limit_boundary_exact_not_active`, `test_rate_limit_boundary_just_over_active` |
| REQ-VEH-04 | `vehicle.py:step`(Euler) | (직접 단위테스트 없음 — 구현이 Euler 형태임은 코드 리뷰로 확인) |
| REQ-VEH-05 | `vehicle.py:step`(v=v_cmd 즉시 대입), `longitudinal.py` | `test_longitudinal.py::test_v_cmd_per_state[SAFE_STOP]` |
| REQ-FSM-01 | `fsm.py:FSMState`, `initial_fsm` | `test_fsm.py::test_initial_fsm_cooldown_pre_expired` |
| REQ-FSM-02a | `fsm.py:step`(KEEP_L2→EVADE_L) | `test_keep_l2_to_evade_l_positive`, `test_keep_l2_to_evade_l_negative_not_left_clear`, MC/DC: `test_fsm_mcdc.py::test_mcdc_d1_front_gap_lt_g_trig` |
| REQ-FSM-02b | `fsm.py:step`(모든 상태→SAFE_STOP) | `test_any_state_to_safe_stop_positive`, `test_safe_stop_condition_negative_left_clear_true`, `test_safe_stop_from_every_state`(5개 파라미터) |
| REQ-FSM-02c | `fsm.py:step`(EVADE_L→KEEP_L1) | `test_evade_l_to_keep_l1_positive`, `test_evade_l_to_keep_l1_negative_far_from_l1` |
| REQ-FSM-02d | `fsm.py:step`(KEEP_L1→RETURN_TO_L2), `sensors.py:right_clear` | `test_keep_l1_to_return_positive`, `test_keep_l1_to_return_negative_right_not_clear`, MC/DC: `test_fsm_mcdc.py::test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form` |
| REQ-FSM-02e | `fsm.py:step`(RETURN_TO_L2→KEEP_L2, [개정] NEAR_L2=0.08) | `test_return_to_keep_l2_positive`, `test_return_to_keep_l2_negative_psi_too_large`, MC/DC: `test_fsm_mcdc.py::test_mcdc_d4_abs_y_le_near_l2` |
| REQ-FSM-03 / 03a | `fsm.py:step`(cooldown_ok, 5개 전이 전부 적용) | `test_cooldown_blocks_keep_l2_to_evade`, `test_cooldown_blocks_evade_to_keep_l1`, `test_cooldown_blocks_keep_l1_to_return`, `test_cooldown_blocks_return_to_keep_l2`, `test_cooldown_blocks_safe_stop` |
| REQ-FSM-03b | `fsm.py:initial_fsm`(§13) | `test_initial_fsm_cooldown_pre_expired` |
| REQ-FSM-04 | `fsm.py:step`(SAFE_STOP 분기 `pass`, §1) | `test_safe_stop_is_terminal_no_recovery` |
| REQ-MPC-01 | `mpc.py:_build_A_template`(동역학 등식행) | `test_mpc.py::test_sign_convention_steers_toward_positive_target`, `..._negative_target`(간접) |
| REQ-MPC-02 | `mpc.py:_build_P`, `solve`(q 갱신) | `test_hessian_has_offdiagonal_rddelta_terms`(간접) |
| REQ-MPC-03 | `config.py`(N,QY,QPSI,RDELTA,RDDELTA) | `test_config.py::test_fixed_params_match_claude_md` |
| REQ-MPC-03a | `mpc.py:_build_P`(rΔδ 비대각) | `test_hessian_has_offdiagonal_rddelta_terms` |
| REQ-MPC-04 | `mpc.py:_build_A_template`(psi/delta bound 행, 고정) | `test_heading_and_steering_bound_constants` |
| REQ-MPC-04a | `postprocess.py:apply`(rate limit은 QP 밖, §15) | `test_postprocess.py::test_order_is_rate_limit_then_clip` |
| REQ-MPC-05 | `config.py:POSITION_CONSTRAINTS`, `mpc.py:solve`(l,u 갱신) | `test_position_constraints_per_state`(4개 상태 파라미터) |
| REQ-MPC-06 | `mpc.py:OSQPMPC.__init__`(sparsity 고정, warm_start) | (구조적 확인만, 별도 단위테스트 없음 — B-1 확정사항 1절) |
| REQ-MPC-07 / 07a | `mpc.py:solve`(fallback, K_P_FALLBACK rad/m) | `test_fallback_unit_is_rad_per_meter` |
| REQ-MPC-07b | `mpc.py:solve`, `vehicle.py:step`(부호 규약) | `test_sign_convention_steers_toward_positive_target`, `..._negative_target` |
| REQ-MPC-08 | `mpc.py`(z에 v 없음, 비용함수에 속도항 없음) | (구조적 확인 — MPCResult에 속도 필드 없음, 코드 리뷰로 확인) |
| REQ-SEN-01 | `sensors.py:front_gap` | `test_sensors.py::test_front_gap_obstacle_in_corridor`, `..._outside_corridor_ignored`, `..._picks_nearest_of_multiple` |
| REQ-SEN-02 | `sensors.py:left_clear` | `test_left_clear_blocked_by_obstacle_in_l1`, `test_left_clear_unaffected_by_obstacle_in_l2_only` |
| REQ-SEN-03 | `sensors.py:ir_pattern`, `ey_line` | `test_ir_pattern_to_ey_line`(6패턴 파라미터) |
| REQ-SEN-04 | `sensors.py:right_clear` | `test_right_clear_blocked_by_obstacle_in_l2`, `test_right_clear_unaffected_by_obstacle_in_l1_only` |
| REQ-LAT-01 | `lateral.py:compute_lateral`(line_follow, K_EY rad/m §17) | `test_lateral.py::test_keep_state_line_follow_when_detected` |
| REQ-LAT-02 | `lateral.py:compute_lateral`(EVADE_L/RETURN_TO_L2 항상 MPC) | `test_evade_return_always_mpc_when_detected`, `..._when_not_detected` |
| REQ-LAT-03 | `lateral.py:compute_lateral`(ey is None → mpc) | `test_keep_state_mpc_when_not_detected` |
| REQ-LAT-04 | `lateral.py:compute_lateral`(KEEP_L1 대칭 처리) | `test_keep_state_line_follow_when_detected[KEEP_L1]`, `test_keep_state_mpc_when_not_detected[KEEP_L1]` |
| REQ-LAT-05 | `lateral.py:compute_lateral`(SAFE_STOP hold_last, §16, 신규) | `test_safe_stop_holds_last_delta_regardless_of_ey`, `test_safe_stop_does_not_call_mpc`, `test_runner.py::test_safe_stop_holds_last_steering_and_does_not_crash` |
| REQ-CTRL-01 | `runner.py:run_episode`(횡+종 통합) | `test_runner.py`(전체) |
| REQ-SPD-01 / 02 | `longitudinal.py:compute_v_cmd` | `test_longitudinal.py::test_v_cmd_per_state`(5개 파라미터) |
| REQ-SPD-03 | `longitudinal.py:compute_v_cmd`(SAFE_STOP 즉시 0) | `test_v_cmd_per_state[SAFE_STOP]` |
| REQ-SPD-04 | `config.py:G_TRIG, G_SAFE_MIN` | `test_config.py::test_fixed_params_match_claude_md` |
| REQ-SPD-05 | `longitudinal.py:compute_v_cmd`(front_gap 미사용, FSM state만 입력) | (시그니처 확인 — front_gap 인자 없음) |
| REQ-SIM-01 | `config.py:W`, `world.py`(도로 암묵적 정의) | `test_config.py`(W 고정값) |
| REQ-SIM-02 / 02a | `world.py:generate_scenario`(전단 기준, §12) | (분포 단위테스트 없음 — seed 재현성 테스트로 간접 확인) |
| REQ-SIM-03 | `world.py:_sample_truncated_y0`([개정] 절단) | (분포 단위테스트 없음, seed 재현성으로 간접) |
| REQ-SIM-04 | `runner.py:run_episode`(MAX_STEPS=200 타임아웃) | (P트랙 실행에서 확인 — 소규모 실행 로그) |
| REQ-SIM-05 | `runner.py:run_episode`(완료 트리거, observing 서브루프) | `test_runner.py::test_seed_reproducibility`(간접) |
| REQ-SIM-08 | `collision.py:check_collision` | `test_collision.py`(4개: 無겹침/완전겹침/부분겹침/회전겹침) |
| 스텝순서(충돌 우선) | `runner.py:run_episode`(7번 충돌판정이 8번 종료판정보다 먼저) | `test_runner.py::test_collision_has_priority_over_safe_stop_same_step` |
| 로거 스키마(§3) | `logger.py:StepLogger` | `test_logger.py::test_logger_schema_has_all_fields`, `test_logger_save_npz_roundtrip` |
| 후처리 순서(§15) | `postprocess.py:apply` | `test_postprocess.py::test_order_is_rate_limit_then_clip`, clip 경계 2개 |
| OSQP 솔버 설정(§18) | `config.py:OSQP_*`, `mpc.py:__init__`/`solve`(setup/solve 인자) | `test_mpc.py`(기존 9개 전부, 설정 변경 후 동작 불변 확인) |
| 제약 만족/위반, clip 세분류, 조향 포화(MEASURE_PLAN.md §18 원칙) | `metrics.py` | `test_metrics.py`(11개), `test_runner.py::test_metrics_counts_are_internally_consistent` |
| summary.json 집계 | `summary.py:build_summary` | (스모크 테스트로 확인 — `run.py` 실행 결과 수동 확인, 전용 단위테스트 없음) |
| env.json 기록 | `envinfo.py:collect_env_info` | (스모크 테스트로 확인 — 전용 단위테스트 없음) |
| 교차 환경 재현성(golden) | `tests/golden/`, `tests/check_golden.py` | `test_check_golden.py`(6개: 시나리오2×seed3) |

## 비고

- REQ-STU-*(M트랙, 신경망)는 2단계-D 대상이라 이 표에 아직 없습니다.
- REQ-EVAL-*(성능/안전성/효율성/성공률 지표)는 `summary.json` 생성 코드(2단계-C 이후)가
  아직 없어 이 표의 대상이 아닙니다.
- "(직접 단위테스트 없음)"으로 표시된 항목은 버그가 아니라 `DESIGN_BASELINE.md` §5의 원래
  테스트 계획(68개)에 포함되지 않았던 항목입니다 — 더 필요하다고 판단되면 사용자 확인 후
  추가합니다(임의 추가 금지 원칙).

## I4 (Student 재학습, 3단계 [발전], DESIGN_I4.md 개정 1)

| 요구/결정 | 구현 | 테스트 |
|---|---|---|
| REQ-STU-01 구조(9→256→256→128→2) | `improved/student_i4/model.py:StudentPolicy` | `test_i4_student.py::test_req_stu_01_structure` |
| REQ-STU-02 입력 9차원·ey fallback | `improved/student_i4/features.py:build_feature_vector` | `test_i4_student.py::test_req_stu_02_feature_order_and_fallback` |
| REQ-STU-03 v_target=규칙 기반 | `features.py:v_target_label` | `test_i4_student.py::test_req_stu_03_v_target_is_rule_based` |
| 입력 캡처가 주행을 바꾸지 않음(§1-3) | `features.py:SolveRecorder` | `test_i4_student.py::test_i4_recorder_does_not_change_episode` |
| 계층 분할·고정 seed(§1-5) | `dataset_gen.py:stratified_episode_split` | `test_i4_student.py::test_i4_stratified_split_fixed_seed_deterministic` |
| std=0 정규화 가드(§1-3) | `model.py:compute_norm_stats` | `test_i4_student.py::test_i4_norm_stats_zero_std_safe` |
| 폐루프 루프 = improved.runner(§3-2) | `closed_loop.py:run_episode` | `test_i4_student.py::test_i4_closed_loop_matches_improved_runner_with_mpc`(2) |
