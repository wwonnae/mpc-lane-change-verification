<!-- 자동 생성: make_mcdc_tables.py -->

- 기존 테스트만(test_fsm.py): step 호출 22회, 재진술 불일치 0건, unique-cause 쌍 확인 조건 **11/14**
- 추가 후(test_fsm.py + test_fsm_mcdc.py): step 호출 28회, 재진술 불일치 0건, unique-cause 쌍 확인 조건 **14/14**

## 결정·조건별 확인 결과

벡터는 조건 순서대로 T/F. 참 사례 → 전이, 거짓 사례 → 유지. '도달 가능 형태' = 두 사례 모두 `last_change_t == state_enter_t`(D3에서만 의미 있음).

| 결정 | 조건 | 기존 테스트 | 추가 후 | 대표 쌍: 참 사례(벡터→출력) | 대표 쌍: 거짓 사례(벡터→출력) | 도달 가능 형태 쌍 |
|---|---|---|---|---|---|---|
| D0 `fsm.py:51` ANY→SAFE_STOP | `cooldown_ok` | 충족 | 충족 | `test_any_state_to_safe_stop_positive` (TTT→SAFE_STOP) | `test_cooldown_blocks_safe_stop` (FTT→KEEP_L2) | 해당 없음(state_enter_t 미사용) |
| D0 `fsm.py:51` ANY→SAFE_STOP | `front_gap < G_SAFE_MIN` | 충족 | 충족 | `test_any_state_to_safe_stop_positive` (TTT→SAFE_STOP) | `test_keep_l2_to_evade_l_negative_not_left_clear` (TFT→KEEP_L2) | 해당 없음(state_enter_t 미사용) |
| D0 `fsm.py:51` ANY→SAFE_STOP | `not left_clear` | 충족 | 충족 | `test_any_state_to_safe_stop_positive` (TTT→SAFE_STOP) | `test_safe_stop_condition_negative_left_clear_true` (TTF→EVADE_L) | 해당 없음(state_enter_t 미사용) |
| D1 `fsm.py:55` KEEP_L2→EVADE_L | `cooldown_ok` | 충족 | 충족 | `test_keep_l2_to_evade_l_positive` (TTT→EVADE_L) | `test_cooldown_blocks_keep_l2_to_evade` (FTT→KEEP_L2) | 해당 없음(state_enter_t 미사용) |
| D1 `fsm.py:55` KEEP_L2→EVADE_L | `front_gap < G_TRIG` | **미충족** | 충족 | `test_mcdc_d1_front_gap_lt_g_trig` (TTT→EVADE_L) | `test_mcdc_d1_front_gap_lt_g_trig` (TFT→KEEP_L2) | 해당 없음(state_enter_t 미사용) |
| D1 `fsm.py:55` KEEP_L2→EVADE_L | `left_clear` | 충족 | 충족 | `test_keep_l2_to_evade_l_positive` (TTT→EVADE_L) | `test_keep_l2_to_evade_l_negative_not_left_clear` (TTF→KEEP_L2) | 해당 없음(state_enter_t 미사용) |
| D2 `fsm.py:59` EVADE_L→KEEP_L1 | `cooldown_ok` | 충족 | 충족 | `test_evade_l_to_keep_l1_positive` (TT→KEEP_L1) | `test_cooldown_blocks_evade_to_keep_l1` (FT→EVADE_L) | 해당 없음(state_enter_t 미사용) |
| D2 `fsm.py:59` EVADE_L→KEEP_L1 | `|y - W| <= NEAR_L1` | 충족 | 충족 | `test_evade_l_to_keep_l1_positive` (TT→KEEP_L1) | `test_evade_l_to_keep_l1_negative_far_from_l1` (TF→EVADE_L) | 해당 없음(state_enter_t 미사용) |
| D3 `fsm.py:64` KEEP_L1→RETURN_TO_L2 | `cooldown_ok` | 충족 | 충족 | `test_keep_l1_to_return_positive` (TTT→RETURN_TO_L2) | `test_cooldown_blocks_keep_l1_to_return` (FTT→KEEP_L1) | **없음** |
| D3 `fsm.py:64` KEEP_L1→RETURN_TO_L2 | `t - state_enter_t > T_KEEP_L1_MIN` | **미충족** | 충족 | `test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form` (TTT→RETURN_TO_L2) | `test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form` (TFT→KEEP_L1) | 있음 |
| D3 `fsm.py:64` KEEP_L1→RETURN_TO_L2 | `right_clear` | 충족 | 충족 | `test_keep_l1_to_return_positive` (TTT→RETURN_TO_L2) | `test_keep_l1_to_return_negative_right_not_clear` (TTF→KEEP_L1) | **없음** |
| D4 `fsm.py:68` RETURN_TO_L2→KEEP_L2 | `cooldown_ok` | 충족 | 충족 | `test_return_to_keep_l2_positive` (TTT→KEEP_L2) | `test_cooldown_blocks_return_to_keep_l2` (FTT→RETURN_TO_L2) | 해당 없음(state_enter_t 미사용) |
| D4 `fsm.py:68` RETURN_TO_L2→KEEP_L2 | `|y| <= NEAR_L2` | **미충족** | 충족 | `test_mcdc_d4_abs_y_le_near_l2` (TTT→KEEP_L2) | `test_mcdc_d4_abs_y_le_near_l2` (TFT→RETURN_TO_L2) | 해당 없음(state_enter_t 미사용) |
| D4 `fsm.py:68` RETURN_TO_L2→KEEP_L2 | `|psi_deg| <= PSI_L2_LIMIT_DEG` | 충족 | 충족 | `test_return_to_keep_l2_positive` (TTT→KEEP_L2) | `test_return_to_keep_l2_negative_psi_too_large` (TTF→RETURN_TO_L2) | 해당 없음(state_enter_t 미사용) |

## 결정별 관측 벡터(추가 후, 실제로 평가된 호출만)

- D0 (REQ-FSM-02b, 03a): 평가 28회, 벡터 {FFF, FTT, TFF, TFT, TTF, TTT}
- D1 (REQ-FSM-02a, 03a): 평가 8회, 벡터 {FTF, FTT, TFT, TTF, TTT}
- D2 (REQ-FSM-02c, 03a): 평가 3회, 벡터 {FT, TF, TT}
- D3 (REQ-FSM-02d, 03a): 평가 5회, 벡터 {FTT, TFT, TTF, TTT}
- D4 (REQ-FSM-02e, 03a): 평가 5회, 벡터 {FTT, TFT, TTF, TTT}
