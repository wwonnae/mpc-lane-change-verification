# V. 폐루프 평가

## 1. 정책과 방법

탐지 결과가 실제로 제어를 바꾸는 유일한 지점은 정책 층이다. 정책은 제어 모듈을 바꾸지 않고 제어기에 들어가는 값을 덮어쓴다.

- **P0**: 탐지기 없음. 모든 비교의 기준이다.
- **P1(즉시 정지)**: 첫 경보 step에 속도 명령 0·직전 조향 유지로 차량을 한 번 갱신하고 에피소드를 끝낸다("탐지 정지"). 그 step에 충돌·이탈이 나면 그쪽으로 분류한다.
- **P2(A만, 채널별 대응)**: 첫 경보 채널로 분기해 에피소드 끝까지 유지한다. fg·trk·ψ → P1과 같은 정지, ey·ir_miss → 제어기에 ey=None 전달
  (기존 MPC 경로), rc → right_clear=False(막힘으로 간주), lc → left_clear=False. 탐지기 자신은 덮어쓰기 전 값을 계속 본다.
- 조합 {{a:n_combos}}개: P0, P1 × {A, B1, B2, 하이브리드}, P2 × A. 각 조합은 정상 2종과 고장 {{a:n_kinds}}종(II장)을 seed {{a:seed_cl}}로 실행하였다
  ({{a:n_runs}} run × 100 seed = {{a:cl_n}}회).
- **결과 분류**(사전 선언 6종): 충돌 / 이탈 / 탐지 정지 / SAFE_STOP(FSM 자체 판단) / 성공 / 타임아웃. **완료** = 성공 + SAFE_STOP.
  **불필요 정지** = 정상 주행의 탐지 정지 + 무해 고장의 탐지 정지 + 유해 고장 onset 이전 탐지 정지.
- "충돌 감소"와 "완료 감소"를 항상 함께 적는다. P0 대비 비교는 같은 run·seed의 1:1 쌍으로 하였다.
- 실행은 동결 커밋(K5, 태그 `anomaly-cl-freeze`)에서 1회 하였다({{a:cl_runtime}}). dev 대역의 같은 실행을 다른 PC에서 다시 계산해 결과 파일 전체가
  일치함을 먼저 확인하였다(VI장 4절).

## 2. 전체 결과

**표 5-1. 조합별 결과({{a:cl_n}}회, [ ]는 Wilson 95% CI).** [데이터: AC | 호스트: H4 | 버전: improved v2 · A iteration 3 · B iteration 2 · 하이브리드 iteration 3 | 커밋: K5]

| 조합 | 충돌 | 이탈 | 탐지 정지 | SAFE_STOP | 성공 | 타임아웃 | 기타 | 충돌 [CI] | 완료 [CI] | 불필요 정지(정상/무해/고장 전) [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| P0 | {{a:cl_P0_col}} | {{a:cl_P0_dep}} | {{a:cl_P0_det}} | {{a:cl_P0_ss}} | {{a:cl_P0_succ}} | {{a:cl_P0_to}} | {{a:cl_P0_other}} | [{{a:cl_P0_col_ci}}] | {{a:cl_P0_comp}} [{{a:cl_P0_comp_ci}}] | {{a:cl_P0_unn}} |
| P1_A | {{a:cl_P1_A_col}} | {{a:cl_P1_A_dep}} | {{a:cl_P1_A_det}} | {{a:cl_P1_A_ss}} | {{a:cl_P1_A_succ}} | {{a:cl_P1_A_to}} | {{a:cl_P1_A_other}} | [{{a:cl_P1_A_col_ci}}] | {{a:cl_P1_A_comp}} [{{a:cl_P1_A_comp_ci}}] | {{a:cl_P1_A_unn}} ({{a:cl_P1_A_unn_parts}}) [{{a:cl_P1_A_unn_ci}}] |
| P1_B1 | {{a:cl_P1_B1_col}} | {{a:cl_P1_B1_dep}} | {{a:cl_P1_B1_det}} | {{a:cl_P1_B1_ss}} | {{a:cl_P1_B1_succ}} | {{a:cl_P1_B1_to}} | {{a:cl_P1_B1_other}} | [{{a:cl_P1_B1_col_ci}}] | {{a:cl_P1_B1_comp}} [{{a:cl_P1_B1_comp_ci}}] | {{a:cl_P1_B1_unn}} ({{a:cl_P1_B1_unn_parts}}) [{{a:cl_P1_B1_unn_ci}}] |
| P1_B2 | {{a:cl_P1_B2_col}} | {{a:cl_P1_B2_dep}} | {{a:cl_P1_B2_det}} | {{a:cl_P1_B2_ss}} | {{a:cl_P1_B2_succ}} | {{a:cl_P1_B2_to}} | {{a:cl_P1_B2_other}} | [{{a:cl_P1_B2_col_ci}}] | {{a:cl_P1_B2_comp}} [{{a:cl_P1_B2_comp_ci}}] | {{a:cl_P1_B2_unn}} ({{a:cl_P1_B2_unn_parts}}) [{{a:cl_P1_B2_unn_ci}}] |
| P1_HYBRID | {{a:cl_P1_HYBRID_col}} | {{a:cl_P1_HYBRID_dep}} | {{a:cl_P1_HYBRID_det}} | {{a:cl_P1_HYBRID_ss}} | {{a:cl_P1_HYBRID_succ}} | {{a:cl_P1_HYBRID_to}} | {{a:cl_P1_HYBRID_other}} | [{{a:cl_P1_HYBRID_col_ci}}] | {{a:cl_P1_HYBRID_comp}} [{{a:cl_P1_HYBRID_comp_ci}}] | {{a:cl_P1_HYBRID_unn}} ({{a:cl_P1_HYBRID_unn_parts}}) [{{a:cl_P1_HYBRID_unn_ci}}] |
| P2_A | {{a:cl_P2_A_col}} | {{a:cl_P2_A_dep}} | {{a:cl_P2_A_det}} | {{a:cl_P2_A_ss}} | {{a:cl_P2_A_succ}} | {{a:cl_P2_A_to}} | {{a:cl_P2_A_other}} | [{{a:cl_P2_A_col_ci}}] | {{a:cl_P2_A_comp}} [{{a:cl_P2_A_comp_ci}}] | {{a:cl_P2_A_unn}} ({{a:cl_P2_A_unn_parts}}) [{{a:cl_P2_A_unn_ci}}] |

**표 5-2. 같은 seed 쌍 비교(P0 대비, {{a:cl_n}}쌍 — "막음"은 즉시 정지 가정 기준이며 낙관적, VII장 3).** [데이터: AC | 호스트: H4 | 버전: 표 5-1과 같음 | 커밋: K5]

| 조합 | 충돌을 막음 / 새 충돌 | 실패(충돌+이탈)를 막음 / 새 실패 | 완료를 잃음 / 새로 완료 | 완료 순변화 |
|---|---|---|---|---|
| P1_A | {{a:cl_P1_A_colprev}} / {{a:cl_P1_A_colnew}} | {{a:cl_P1_A_failprev}} / {{a:cl_P1_A_failnew}} | {{a:cl_P1_A_complost}} / {{a:cl_P1_A_compgain}} | {{a:cl_P1_A_compdelta}} |
| P1_B1 | {{a:cl_P1_B1_colprev}} / {{a:cl_P1_B1_colnew}} | {{a:cl_P1_B1_failprev}} / {{a:cl_P1_B1_failnew}} | {{a:cl_P1_B1_complost}} / {{a:cl_P1_B1_compgain}} | {{a:cl_P1_B1_compdelta}} |
| P1_B2 | {{a:cl_P1_B2_colprev}} / {{a:cl_P1_B2_colnew}} | {{a:cl_P1_B2_failprev}} / {{a:cl_P1_B2_failnew}} | {{a:cl_P1_B2_complost}} / {{a:cl_P1_B2_compgain}} | {{a:cl_P1_B2_compdelta}} |
| P1_HYBRID | {{a:cl_P1_HYBRID_colprev}} / {{a:cl_P1_HYBRID_colnew}} | {{a:cl_P1_HYBRID_failprev}} / {{a:cl_P1_HYBRID_failnew}} | {{a:cl_P1_HYBRID_complost}} / {{a:cl_P1_HYBRID_compgain}} | {{a:cl_P1_HYBRID_compdelta}} |
| P2_A | {{a:cl_P2_A_colprev}} / {{a:cl_P2_A_colnew}} | {{a:cl_P2_A_failprev}} / {{a:cl_P2_A_failnew}} | {{a:cl_P2_A_complost}} / {{a:cl_P2_A_compgain}} | {{a:cl_P2_A_compdelta}} |

**표 5-3. 묶음별(정상 {{a:cl_n_normal}} · 유해 {{a:cl_n_harmful}} · 무해 {{a:cl_n_harmless}}회).** [데이터: AC | 호스트: H4 | 버전: 표 5-1과 같음 | 커밋: K5]

| 조합 | 정상: 충돌+이탈 / 완료 / 불필요 | 유해: 충돌+이탈 [CI] | 유해: 완료 [CI] | 무해: 완료 [CI] | 무해: 불필요 정지 [CI] |
|---|---|---|---|---|---|
| P0 | {{a:cl_P0_normal_fail}} / {{a:cl_P0_normal_comp}} / {{a:cl_P0_normal_unn}} | {{a:cl_P0_harmful_fail}} [{{a:cl_P0_harmful_fail_ci}}] | {{a:cl_P0_harmful_comp}} [{{a:cl_P0_harmful_comp_ci}}] | {{a:cl_P0_harmless_comp}} [{{a:cl_P0_harmless_comp_ci}}] | {{a:cl_P0_harmless_unn}} [{{a:cl_P0_harmless_unn_ci}}] |
| P1_A | {{a:cl_P1_A_normal_fail}} / {{a:cl_P1_A_normal_comp}} / {{a:cl_P1_A_normal_unn}} | {{a:cl_P1_A_harmful_fail}} [{{a:cl_P1_A_harmful_fail_ci}}] | {{a:cl_P1_A_harmful_comp}} [{{a:cl_P1_A_harmful_comp_ci}}] | {{a:cl_P1_A_harmless_comp}} [{{a:cl_P1_A_harmless_comp_ci}}] | {{a:cl_P1_A_harmless_unn}} [{{a:cl_P1_A_harmless_unn_ci}}] |
| P1_B1 | {{a:cl_P1_B1_normal_fail}} / {{a:cl_P1_B1_normal_comp}} / {{a:cl_P1_B1_normal_unn}} | {{a:cl_P1_B1_harmful_fail}} [{{a:cl_P1_B1_harmful_fail_ci}}] | {{a:cl_P1_B1_harmful_comp}} [{{a:cl_P1_B1_harmful_comp_ci}}] | {{a:cl_P1_B1_harmless_comp}} [{{a:cl_P1_B1_harmless_comp_ci}}] | {{a:cl_P1_B1_harmless_unn}} [{{a:cl_P1_B1_harmless_unn_ci}}] |
| P1_B2 | {{a:cl_P1_B2_normal_fail}} / {{a:cl_P1_B2_normal_comp}} / {{a:cl_P1_B2_normal_unn}} | {{a:cl_P1_B2_harmful_fail}} [{{a:cl_P1_B2_harmful_fail_ci}}] | {{a:cl_P1_B2_harmful_comp}} [{{a:cl_P1_B2_harmful_comp_ci}}] | {{a:cl_P1_B2_harmless_comp}} [{{a:cl_P1_B2_harmless_comp_ci}}] | {{a:cl_P1_B2_harmless_unn}} [{{a:cl_P1_B2_harmless_unn_ci}}] |
| P1_HYBRID | {{a:cl_P1_HYBRID_normal_fail}} / {{a:cl_P1_HYBRID_normal_comp}} / {{a:cl_P1_HYBRID_normal_unn}} | {{a:cl_P1_HYBRID_harmful_fail}} [{{a:cl_P1_HYBRID_harmful_fail_ci}}] | {{a:cl_P1_HYBRID_harmful_comp}} [{{a:cl_P1_HYBRID_harmful_comp_ci}}] | {{a:cl_P1_HYBRID_harmless_comp}} [{{a:cl_P1_HYBRID_harmless_comp_ci}}] | {{a:cl_P1_HYBRID_harmless_unn}} [{{a:cl_P1_HYBRID_harmless_unn_ci}}] |
| P2_A | {{a:cl_P2_A_normal_fail}} / {{a:cl_P2_A_normal_comp}} / {{a:cl_P2_A_normal_unn}} | {{a:cl_P2_A_harmful_fail}} [{{a:cl_P2_A_harmful_fail_ci}}] | {{a:cl_P2_A_harmful_comp}} [{{a:cl_P2_A_harmful_comp_ci}}] | {{a:cl_P2_A_harmless_comp}} [{{a:cl_P2_A_harmless_comp_ci}}] | {{a:cl_P2_A_harmless_unn}} [{{a:cl_P2_A_harmless_unn_ci}}] |

**관찰.**

- **A + 정지(P1_A·P2_A)**: 유해 고장의 충돌+이탈이 P0 {{a:cl_P0_harmful_fail}}회에서 {{a:cl_P1_A_harmful_fail}}회로 줄었다(신뢰구간 겹치지 않음).
  같은 seed 쌍에서 새로 생긴 충돌·이탈은 없었다. 이 감소는 정지 판단 후 한 step(≤ {{a:p_vdt}})만 이동하고 바로 v = 0이 되는 차량 모델
  (REQ-VEH-05)에 기댄 **낙관적 값**이다(VII장 3). 또 P1_A는 유해 고장 에피소드를 하나도 완료하지 못했다({{a:cl_P1_A_harmful_comp}}). 정지가 사고를
  막는 대신 임무를 포기한 것이다.
- **P2_A 대 P1_A**: 안전 결과(충돌·이탈)는 같고 완료는 P2_A {{a:cl_P2_A_comp}} [{{a:cl_P2_A_comp_ci}}], P1_A {{a:cl_P1_A_comp}} [{{a:cl_P1_A_comp_ci}}]이다.
  두 신뢰구간은 겹치지 않는다. 같은 run·seed로 나누면 차이 {{a:p2p1_gain}}회는 ir_dropout {{a:p2p1_gain_ir_dropout}}회, ir_stuck {{a:p2p1_gain_ir_stuck}}회,
  left_clear_stuck {{a:p2p1_gain_left_clear_stuck}}회이다. 앞의 둘은 ey·ir_miss 경보에서 멈추지 않고 MPC로 주행을 이어간 결과이다. left_clear_stuck
  {{a:p2p1_gain_left_clear_stuck}}회는 lc 경보로 회피를 막아 SAFE_STOP으로 끝난 것인데, L1 장애물 앞까지 접근한 정지라 즉시 정지 가정에 기댄다(Q4).
  이를 빼도 IR 채널 대응만으로 {{a:p2p1_gain_nonlcs}}회 차이가 난다. 다만 rc 대응은 무해 고장 right_clear_stuck을 모두 타임아웃으로
  만들었다(4절 Q3).
- **B1**은 충돌을 하나도 막지 못했다({{a:cl_P1_B1_colprev}}). **B2**는 충돌 {{a:cl_P1_B2_colprev}}건을 막았지만 완료 {{a:cl_P1_B2_complost}}건을 잃었고, 무해 고장에서
  불필요 정지가 {{a:cl_P1_B2_harmless_unn}}회였다. **하이브리드**는 같은 seed 쌍에서 충돌 {{a:cl_P1_HYBRID_colprev}}건을 막았다. 그러나 전체 충돌률 신뢰구간은
  P0와 겹친다(P0 [{{a:cl_P0_col_ci}}], 하이브리드 [{{a:cl_P1_HYBRID_col_ci}}]). lidar_freeze는 100회 모두 충돌로 남았다.

## 3. 고장 종류별

**표 5-4. 고장 종류별 결과(각 100회, 칸 = 충돌·이탈·완료·불필요 정지, 나머지는 탐지 정지).** [데이터: AC | 호스트: H4 | 버전: 표 5-1과 같음 | 커밋: K5]

| 구분 | run | P0 | P1_A | P1_B1 | P1_B2 | P1_HYBRID | P2_A |
|---|---|---|---|---|---|---|---|
| 정상 | none(원거리) | {{a:cl_P0_none_cell}} | {{a:cl_P1_A_none_cell}} | {{a:cl_P1_B1_none_cell}} | {{a:cl_P1_B2_none_cell}} | {{a:cl_P1_HYBRID_none_cell}} | {{a:cl_P2_A_none_cell}} |
| 정상 | none_leftobs(좌측 장애물) | {{a:cl_P0_none_leftobs_cell}} | {{a:cl_P1_A_none_leftobs_cell}} | {{a:cl_P1_B1_none_leftobs_cell}} | {{a:cl_P1_B2_none_leftobs_cell}} | {{a:cl_P1_HYBRID_none_leftobs_cell}} | {{a:cl_P2_A_none_leftobs_cell}} |
| 유해 | lidar_freeze | {{a:cl_P0_lidar_freeze_cell}} | {{a:cl_P1_A_lidar_freeze_cell}} | {{a:cl_P1_B1_lidar_freeze_cell}} | {{a:cl_P1_B2_lidar_freeze_cell}} | {{a:cl_P1_HYBRID_lidar_freeze_cell}} | {{a:cl_P2_A_lidar_freeze_cell}} |
| 유해 | lidar_dropout | {{a:cl_P0_lidar_dropout_cell}} | {{a:cl_P1_A_lidar_dropout_cell}} | {{a:cl_P1_B1_lidar_dropout_cell}} | {{a:cl_P1_B2_lidar_dropout_cell}} | {{a:cl_P1_HYBRID_lidar_dropout_cell}} | {{a:cl_P2_A_lidar_dropout_cell}} |
| 유해 | ir_stuck | {{a:cl_P0_ir_stuck_cell}} | {{a:cl_P1_A_ir_stuck_cell}} | {{a:cl_P1_B1_ir_stuck_cell}} | {{a:cl_P1_B2_ir_stuck_cell}} | {{a:cl_P1_HYBRID_ir_stuck_cell}} | {{a:cl_P2_A_ir_stuck_cell}} |
| 유해 | steer_delay | {{a:cl_P0_steer_delay_cell}} ᵃ | {{a:cl_P1_A_steer_delay_cell}} | {{a:cl_P1_B1_steer_delay_cell}} ᵃ | {{a:cl_P1_B2_steer_delay_cell}} | {{a:cl_P1_HYBRID_steer_delay_cell}} | {{a:cl_P2_A_steer_delay_cell}} |
| 유해 | steer_stuck | {{a:cl_P0_steer_stuck_cell}} | {{a:cl_P1_A_steer_stuck_cell}} | {{a:cl_P1_B1_steer_stuck_cell}} | {{a:cl_P1_B2_steer_stuck_cell}} | {{a:cl_P1_HYBRID_steer_stuck_cell}} | {{a:cl_P2_A_steer_stuck_cell}} |
| 유해 | left_clear_stuck | {{a:cl_P0_left_clear_stuck_cell}} | {{a:cl_P1_A_left_clear_stuck_cell}} | {{a:cl_P1_B1_left_clear_stuck_cell}} | {{a:cl_P1_B2_left_clear_stuck_cell}} | {{a:cl_P1_HYBRID_left_clear_stuck_cell}} | {{a:cl_P2_A_left_clear_stuck_cell}} ᶜ |
| 무해 | lidar_spike | {{a:cl_P0_lidar_spike_cell}} | {{a:cl_P1_A_lidar_spike_cell}} | {{a:cl_P1_B1_lidar_spike_cell}} | {{a:cl_P1_B2_lidar_spike_cell}} | {{a:cl_P1_HYBRID_lidar_spike_cell}} | {{a:cl_P2_A_lidar_spike_cell}} |
| 무해 | ir_dropout | {{a:cl_P0_ir_dropout_cell}} | {{a:cl_P1_A_ir_dropout_cell}} | {{a:cl_P1_B1_ir_dropout_cell}} | {{a:cl_P1_B2_ir_dropout_cell}} | {{a:cl_P1_HYBRID_ir_dropout_cell}} | {{a:cl_P2_A_ir_dropout_cell}} |
| 무해 | right_clear_stuck | {{a:cl_P0_right_clear_stuck_cell}} | {{a:cl_P1_A_right_clear_stuck_cell}} | {{a:cl_P1_B1_right_clear_stuck_cell}} | {{a:cl_P1_B2_right_clear_stuck_cell}} | {{a:cl_P1_HYBRID_right_clear_stuck_cell}} | {{a:cl_P2_A_right_clear_stuck_cell}} ᵇ |

ᵃ 기타(미정착) 1건 포함(Q1). ᵇ 나머지는 탐지 정지가 아니라 타임아웃이다(Q3). ᶜ 완료는 모두 SAFE_STOP이며, 1차선 안에서 장애물 약 0.20 m 이내까지 접근한 정지로 추정한다(dev 재현 근거, Q4).

## 4. 개별 확인

**Q1. 사전 6분류 밖 결과 1건 — 기타.** {{a:q1_run}}(onset {{a:q1_onset}}, 영구 고장)이 {{a:q1_combos}}에서 "미정착"으로 끝났다. B1은 이 에피소드에서 경보를 내지 않았다.
차는 step {{a:q1_finish_step}}에 복귀했지만, 복귀 후 관찰 구간({{a:p_observe}})에서 차로 중심 범위를 벗어나 step {{a:q1_total}}에 미정착으로 끝났다. 폐루프 루프가 기존 runner의 분류를 그대로
물려받아 생긴 결과이다(`closed_loop.py:253`). 폐루프 사전 선언(`DESIGN.md` §24)은 "기타는 두지 않는다 — 6종으로 전부 분류되지 않으면 버그로 본다"고
정했으므로 이는 **사전 선언 위반**이다. 원인은 새 코드의 오분류가 아니라 선언이 기존 분류를 빠뜨린 것이다. 재분류하지 않고 기타로 분리하였으며,
완료로도 실패로도 세지 않았다.
같은 에피소드에서 A는 step {{a:q1_alarm_A}}, B2는 step {{a:q1_alarm_B2}}, 하이브리드는 step {{a:q1_alarm_HY}}에 경보를 내고 정지하였다.

**Q2. P1_A·P2_A에 남은 충돌 1건.** 두 조합에서 같은 에피소드이다. 고장 없는 정상 좌측 장애물 주행 seed {{a:q2_seed}}이며 step {{a:q2_step}}에서 충돌하였다.
P0를 포함한 {{a:q2_all}}개 조합 모두에서 같은 step에 충돌했고, 어느 탐지기도 충돌 전에 경보를 내지 않았다. 고장이 아니라 제어기 자체의 실패이므로
탐지·정지로 막을 대상이 아니다. 원인은 5절에서 다룬다.

**Q3. P2_A 타임아웃 {{a:q3_n}}건.** 고장 종류별로는 {{a:q3_kinds}}건, 대응별로는 {{a:q3_action}}건이었다(모두 rc 경보). 같은 seed의 P0 결과는 {{a:q3_p0}}건이었다. rc 경보는 onset 후
{{a:q3_delay}} step에 났다. KEEP_L1→RETURN_TO_L2 전이에는 right_clear가 필요하다(`baseline/fsm.py:64`). rc 대응이 이 값을 끝까지 False로 덮어쓰므로,
복귀 전에 대응이 걸리면 성공이 원리적으로 불가능하다. dev seed {{a:dev_rcs_n}}개로 경로를 확인한 결과 P2의 FSM 경로는 {{a:dev_rcs_p2}}건으로, 모두 KEEP_L1에서 전이가 멈춘 채
에피소드 상한까지 머물렀다(평가 에피소드의 마지막 FSM 상태는 결과 파일에 없어, 평가 쪽은 코드와 dev 근거에 의한 추정이다). 이 고장은 P0에서 무해했는데,
"막힘으로 간주"라는 보수적 대응이 임무를 끝내지 못하게 만든 것이다. 사전 정의의 불필요 정지는 탐지 정지만 세므로 이 {{a:q3_n}}건은 표 5-1의 불필요
정지에 들어 있지 않다. P2_A의 무해 고장 비용은 무해 완료 {{a:cl_P2_A_harmless_comp}}회(P0 {{a:cl_P0_harmless_comp}}회)로 읽어야 한다.

**Q4. left_clear_stuck의 P2_A SAFE_STOP {{a:q4_n}}건 — 정지했으나 1차선 안에서 장애물 약 0.20 m 이내까지 접근(dev 재현 근거, 평가는 추정).**
같은 seed의 P0 결과는 {{a:q4_p0}}건이었다. P2_A에서는 lc 경보 후 left_clear=False로 덮어써 FSM의 SAFE_STOP 조건(front_gap < {{a:p_gsafe}} 그리고
left_clear=False)으로 멈췄고, 충돌·이탈은 없었다(CSV 확인). lc 경보는 onset 후 {{a:q4_delay}} step에 났으며, 회피가 시작된 뒤에야 난 것으로 본다
(사전 예상과 IV장 3절. 평가 에피소드의 FSM 경로는 기록되지 않음). 평가 에피소드의 정지 위치도 기록되지 않아, dev seed {{a:seed_dev}}로 같은 대응을
재현해 정지 위치를 확인하였다(100회 중 {{a:dev_lcs_ss}}회 SAFE_STOP). 아래는 dev 값이며 평가 {{a:q4_n}}건도 같은 경로로 **추정**한다.
- 직전 상태: {{a:dev_lcs_from}}.
- 정지 시 차량 중심 y: {{a:dev_lcs_y}}. {{a:dev_lcs_y_l1}}이 y ≥ 0.15 m로, 차가 이미 1차선(L1) 쪽으로 들어가 있었다.
- 헤딩: {{a:dev_lcs_psi}}.
- 정지 판단 step에 한 step 더 이동한 뒤의 참값 front_gap: {{a:dev_lcs_gap}}. 정지 판단은 측정 front_gap < {{a:p_gsafe}}에서 일어났고, 이동 후 참값
  간격의 최댓값은 0.20 m를 약간 넘는다(측정 노이즈) — 그래서 "약 0.20 m 이내"로 적었다.

정상 좌측 장애물 주행이 2차선에서 멈추는 것과 다른 정지이다. 차량 모델에서는 정지 판단 step에 한 번 v·dt(≤ {{a:p_vdt}}) 이동한 뒤 곧바로 v = 0이 된다.
그래서 **이 정지들이 충돌 없이 끝난 것은 즉시 정지 가정 때문일 수 있다**. 제동 거리가 있는 실제 차량이라면 남은 간격(dev 최소 {{a:dev_lcs_gap_min}})을 넘어
충돌했을 수 있다(VII장).

**같은 seed 안의 상관.** A 조합에서 seed {{a:corr_seed}}는 {{a:n_runs}}개 run 중 {{a:corr_runs}}개에서 **같은 step {{a:corr_step}}에 ψ 경보**가 났다.
seed마다 시나리오·센서 노이즈·자이로 노이즈가 run 사이에 공유되고(같은 seed 쌍 비교를 위한 설계), 고장 onset 전 궤적이 같기 때문이다. 이 하나의 오경보가
P1_A 불필요 정지 중 {{a:corr_unn_P1_A}}건, P2_A 중 {{a:corr_unn_P2_A}}건을 차지한다. 또 ir_stuck(onset {{a:corr_irstuck_onset}})에서는 같은 오경보가
onset과 같은 step에 나 "onset 이후 정지"로 분류되어 불필요 정지에 들어가지 않고 탐지로 집계되었다(같은 seed의 P0는 {{a:corr_irstuck_p0}}). P2_A
ir_stuck 완료에서 빠진 1건이 이것이다. 따라서 이 오경보의 실제 영향은 조합마다 {{a:corr_runs}}건이다. 따라서 {{a:cl_n}}회는 서로 독립이 아니다. {{a:cl_n}}회 기준 신뢰구간은 독립을
가정하므로 실제보다 좁게 나올 수 있다. seed가 서로 다른 고장 종류별 100회 단위가 더 적절한 단위이다.

## 5. 정상 좌측 장애물 주행의 충돌 — 제어기 자체의 실패

평가 결과 파일에는 FSM 경로·센서 값이 기록되지 않아, seed {{a:q2_seed}} 자체의 경로는 확인할 수 없다(평가 seed는 다시 실행하지 않았다). 대신 같은 계열의
사례를 평가가 아닌 seed에서 재현하였다. **사용 대역은 {{a:seed_sup}}**(임계값 AN {{a:seed_thr}} · 개발 AD {{a:seed_dev}} · 학습 AT {{a:seed_train}})이며 평가 seed는 쓰지 않았다
(스크립트에서 assert). 임계값 정상 데이터에 이미 기록된 좌측 장애물 정상 충돌(seed {{a:s3173_seed}})을 재현해 step별 값을 기록하였다(AS).
seed {{a:q2_seed}}의 원인은 이 재현과 같은 것으로 **추정**한다(확인 아님).

**표 5-5. 정상 좌측 장애물 충돌 재현(seed {{a:s3173_seed}}).** [데이터: AS | 호스트: H4 | 버전: improved v2 | 커밋: K6]

| step | FSM | 사건 |
|---|---|---|
| {{a:s3173_trig}} 직전 | KEEP_L2 | front_gap 측정 {{a:s3173_prev_fg}}, left_clear=False(정상). SAFE_STOP 조건 front_gap < {{a:p_gsafe}} 미충족 |
| {{a:s3173_trig}} | KEEP_L2→EVADE_L | front_gap 측정(참값) {{a:s3173_fg}} — 측정이 {{a:p_gsafe}} 바로 위라 SAFE_STOP이 아니었다. 이때 **left_clear가 S4 노이즈로 한 번 True로 뒤집혀**(참값 False) 회피 조건(front_gap < {{a:p_gtrig}} 그리고 left_clear)이 성립 |
| {{a:s3173_blocked}} | EVADE_L | SAFE_STOP 조건이 매 step 참이지만 **쿨다운 {{a:p_cooldown}}({{a:p_cooldown_steps}} step)**로 전이가 막혔다. 차는 {{a:p_vmax}}로 앞 장애물에 다가가며 왼쪽으로 회전 |
| {{a:s3173_stop}} | EVADE_L→SAFE_STOP | 쿨다운이 끝나 SAFE_STOP(front_gap 측정 {{a:s3173_fg_stop}}). 이 step의 위치 갱신은 직전 속도를 써서 {{a:s3173_move}} 이동·회전({{a:s3173_psi}}) → 차체 모서리가 앞 장애물과 겹쳐 충돌 |

**표 5-6. 정상 좌측 장애물 주행의 경로와 원인 분리(각 {{a:sup_n}}회, seed {{a:seed_sup}}).** [데이터: AS | 호스트: H4 | 버전: improved v2 | 커밋: K6]

| 조건 | SAFE_STOP | 충돌 | 회피(EVADE_L) 경유 |
|---|---|---|---|
| 원거리({{a:p_fg_far}}) + S4-low(이 확장의 정상 조건) | {{a:sup_ss}}(직행 {{a:sup_path_direct}}) | {{a:sup_col}} | {{a:sup_evaded}} ({{a:sup_evaded_pct}}) |
| 원거리 + 노이즈 없음 | {{a:sup_far_noisefree_ss}} | {{a:sup_far_noisefree_col}} | {{a:sup_far_noisefree_ev}} |
| 근거리({{a:p_fg_near}}, 기존 left_obstacle) + 노이즈 없음 | {{a:sup_near_noisefree_ss}} | {{a:sup_near_noisefree_col}} | {{a:sup_near_noisefree_ev}} |
| 근거리 + S4-low | {{a:sup_near_s4low_ss}} | {{a:sup_near_s4low_col}} | {{a:sup_near_s4low_ev}} |

- 원거리 + S4-low에서 회피를 거친 경로는 다음과 같다. KEEP_L2→EVADE_L→SAFE_STOP {{a:sup_path_evade}}회(계기: left_clear 오판정 {{a:sup_path_evade_flip}},
  참값 left_clear=True인데 front_gap 노이즈로 {{a:p_gtrig}} 아래 {{a:sup_path_evade_fg}}), KEEP_L1까지 들어갔다가 SAFE_STOP {{a:sup_path_l1}}회
  (오판정 {{a:sup_path_l1_flip}}, front_gap 노이즈 {{a:sup_path_l1_fg}}), 충돌 {{a:sup_col}}회(seed {{a:sup_col_seed}}).
- **기존 v2 평가의 left_obstacle 결과(SAFE_STOP 100/100, 기존 보고서 VI장 5절)와 다른 이유는 거리가 아니라 노이즈이다.** 기존 평가의 left_obstacle은
  노이즈 없이 실행하였고(`improved/run_eval_v2.py` `run_left_obstacle`), S4 노이즈는 paper 시나리오에만 걸었다. 노이즈가 없으면 front_gap이 {{a:p_gtrig}}
  아래로 내려가는 순간과 좌측 장애물이 left_clear 윈도우에 들어오는 순간이 같아 회피가 일어나지 않는다. 표 5-6에서 노이즈가 없으면 거리와 무관하게
  회피·충돌이 0이고, 기존 근거리 시나리오도 S4-low를 켜면 충돌이 생긴다.
- 정리하면, v2 제어기는 left_clear·front_gap 노이즈가 있는 좌측 장애물 상황에서 드물게 충돌한다(평가 100회 중 1회, 보충 재현 {{a:sup_n}}회 중
  {{a:sup_col}}회·{{a:sup_near_s4low_col}}회). 기존 평가는 이 조합을 다루지 않았다. SAFE_STOP 전이의 쿨다운 예외나 left_clear 다수결 같은 제어기 수정은
  이 확장의 범위 밖이라 하지 않았다.
