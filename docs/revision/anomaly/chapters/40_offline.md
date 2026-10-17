# IV. 오프라인 평가

## 1. 방법

평가 데이터 AE에서 정상 2종(원거리·좌측 장애물) 각 100회와 고장 {{a:n_kinds}}종 각 {{a:off_n_kind}}회를 **관찰 전용**으로 한 번 실행하였다
(탐지기는 제어에 개입하지 않음). 같은 관측 로그에 네 탐지기를 모두 적용했으므로 탐지기 간 비교는 같은 데이터 위에서 이루어진다.

- **탐지**: 경보가 [onset, onset + 지속 + {{a:p_grace}}] 안에 한 번 이상 나면 탐지이다(영구 고장은 에피소드 끝까지). onset 이전 경보는 오경보로 센다.
  무해 고장의 탐지도 탐지로 센다(유해·무해 분리는 그 위에 얹는 별도 표).
- **지연**: 첫 경보 step − onset step의 중앙값(p90). 스텝 단위 F1은 point-adjust를 쓰지 않았다.
- **부트스트랩**: AUC·지연 신뢰구간은 에피소드 재추출 {{a:p_boot}}(반복 / seed).

## 2. 고장 종류별 탐지

**표 4-1. 고장 종류별 탐지(각 100회 중, 괄호는 Wilson 95% CI).** [데이터: AE | 호스트: H3 | 버전: A iteration 3 · B1/B2 iteration 2 · 하이브리드 iteration 3 · improved v2 | 커밋: K4]

| 구분 | 고장 | A | B1 | B2 | 하이브리드 |
|---|---|---|---|---|---|
| 유해 | lidar_freeze | {{a:off_A_lidar_freeze}} ({{a:off_A_lidar_freeze_ci}}) | {{a:off_B1_lidar_freeze}} ({{a:off_B1_lidar_freeze_ci}}) | {{a:off_B2_lidar_freeze}} ({{a:off_B2_lidar_freeze_ci}}) | {{a:off_HYBRID_lidar_freeze}} ({{a:off_HYBRID_lidar_freeze_ci}}) |
| 유해 | lidar_dropout | {{a:off_A_lidar_dropout}} ({{a:off_A_lidar_dropout_ci}}) | {{a:off_B1_lidar_dropout}} ({{a:off_B1_lidar_dropout_ci}}) | {{a:off_B2_lidar_dropout}} ({{a:off_B2_lidar_dropout_ci}}) | {{a:off_HYBRID_lidar_dropout}} ({{a:off_HYBRID_lidar_dropout_ci}}) |
| 유해 | ir_stuck | {{a:off_A_ir_stuck}} ({{a:off_A_ir_stuck_ci}}) | {{a:off_B1_ir_stuck}} ({{a:off_B1_ir_stuck_ci}}) | {{a:off_B2_ir_stuck}} ({{a:off_B2_ir_stuck_ci}}) | {{a:off_HYBRID_ir_stuck}} ({{a:off_HYBRID_ir_stuck_ci}}) |
| 유해 | steer_delay | {{a:off_A_steer_delay}} ({{a:off_A_steer_delay_ci}}) | {{a:off_B1_steer_delay}} ({{a:off_B1_steer_delay_ci}}) | {{a:off_B2_steer_delay}} ({{a:off_B2_steer_delay_ci}}) | {{a:off_HYBRID_steer_delay}} ({{a:off_HYBRID_steer_delay_ci}}) |
| 유해 | steer_stuck | {{a:off_A_steer_stuck}} ({{a:off_A_steer_stuck_ci}}) | {{a:off_B1_steer_stuck}} ({{a:off_B1_steer_stuck_ci}}) | {{a:off_B2_steer_stuck}} ({{a:off_B2_steer_stuck_ci}}) | {{a:off_HYBRID_steer_stuck}} ({{a:off_HYBRID_steer_stuck_ci}}) |
| 유해 | left_clear_stuck | {{a:off_A_left_clear_stuck}} ({{a:off_A_left_clear_stuck_ci}}) | {{a:off_B1_left_clear_stuck}} ({{a:off_B1_left_clear_stuck_ci}}) | {{a:off_B2_left_clear_stuck}} ({{a:off_B2_left_clear_stuck_ci}}) | {{a:off_HYBRID_left_clear_stuck}} ({{a:off_HYBRID_left_clear_stuck_ci}}) |
| 무해 | lidar_spike | {{a:off_A_lidar_spike}} ({{a:off_A_lidar_spike_ci}}) | {{a:off_B1_lidar_spike}} ({{a:off_B1_lidar_spike_ci}}) | {{a:off_B2_lidar_spike}} ({{a:off_B2_lidar_spike_ci}}) | {{a:off_HYBRID_lidar_spike}} ({{a:off_HYBRID_lidar_spike_ci}}) |
| 무해 | ir_dropout | {{a:off_A_ir_dropout}} ({{a:off_A_ir_dropout_ci}}) | {{a:off_B1_ir_dropout}} ({{a:off_B1_ir_dropout_ci}}) | {{a:off_B2_ir_dropout}} ({{a:off_B2_ir_dropout_ci}}) | {{a:off_HYBRID_ir_dropout}} ({{a:off_HYBRID_ir_dropout_ci}}) |
| 무해 | right_clear_stuck | {{a:off_A_right_clear_stuck}} ({{a:off_A_right_clear_stuck_ci}}) | {{a:off_B1_right_clear_stuck}} ({{a:off_B1_right_clear_stuck_ci}}) | {{a:off_B2_right_clear_stuck}} ({{a:off_B2_right_clear_stuck_ci}}) | {{a:off_HYBRID_right_clear_stuck}} ({{a:off_HYBRID_right_clear_stuck_ci}}) |
| 정상 | 원거리 경보 | {{a:off_A_normal_far}} ({{a:off_A_normal_far_ci}}) | {{a:off_B1_normal_far}} ({{a:off_B1_normal_far_ci}}) | {{a:off_B2_normal_far}} ({{a:off_B2_normal_far_ci}}) | {{a:off_HYBRID_normal_far}} ({{a:off_HYBRID_normal_far_ci}}) |
| 정상 | 좌측 장애물 경보 | {{a:off_A_normal_left}} ({{a:off_A_normal_left_ci}}) | {{a:off_B1_normal_left}} ({{a:off_B1_normal_left_ci}}) | {{a:off_B2_normal_left}} ({{a:off_B2_normal_left_ci}}) | {{a:off_HYBRID_normal_left}} ({{a:off_HYBRID_normal_left_ci}}) |

**표 4-2. 묶음별 탐지와 에피소드 단위 ROC.** [데이터: AE | 호스트: H3 | 버전: 표 4-1과 같음 | 커밋: K4]

| 탐지기 | 유해 6종 탐지 (CI) | 무해 3종 탐지 (CI) | 에피소드 ROC AUC (부트스트랩 95%) | 스텝 PR AP |
|---|---|---|---|---|
| A | {{a:off_A_harmful}} ({{a:off_A_harmful_ci}}) | {{a:off_A_harmless}} ({{a:off_A_harmless_ci}}) | {{a:off_A_auc}} ({{a:off_A_auc_ci}}) | {{a:off_A_ap}} |
| B1 | {{a:off_B1_harmful}} ({{a:off_B1_harmful_ci}}) | {{a:off_B1_harmless}} ({{a:off_B1_harmless_ci}}) | {{a:off_B1_auc}} ({{a:off_B1_auc_ci}}) | {{a:off_B1_ap}} |
| B2 | {{a:off_B2_harmful}} ({{a:off_B2_harmful_ci}}) | {{a:off_B2_harmless}} ({{a:off_B2_harmless_ci}}) | {{a:off_B2_auc}} ({{a:off_B2_auc_ci}}) | {{a:off_B2_ap}} |
| 하이브리드 | {{a:off_HYBRID_harmful}} ({{a:off_HYBRID_harmful_ci}}) | {{a:off_HYBRID_harmless}} ({{a:off_HYBRID_harmless_ci}}) | {{a:off_HYBRID_auc}} ({{a:off_HYBRID_auc_ci}}) | {{a:off_HYBRID_ap}} |

**관찰.**

- **A**는 유해 6종을 모두 100회 중 100회 탐지하였다. 무해 고장 중 lidar_spike는 100회 중 {{a:off_A_lidar_spike}}회였다. 아래로 튄 spike는
  {{a:off_A_spike_down}}, 위로 튄 spike는 {{a:off_A_spike_up}}을 잡았다. 위로 튄 1~2 step 무반사는 이산 채널 불일치 2회 이하라 h를 넘지 못한다.
- **B1**은 정상 데이터로만 학습한 상태에서 유해 고장을 거의 놓쳤다({{a:off_B1_harmful}}). 임계값이 좌측 장애물 정상 주행의 높은 점수로 정해졌기 때문으로
  보인다(VI장 2절).
- **B2**는 유해 고장 {{a:off_B2_harmful}}을 탐지했지만 lidar_freeze는 100회 중 {{a:off_B2_lidar_freeze}}회에 그쳤다. 대신 무해 대조군 ir_dropout을
  100회 중 {{a:off_B2_ir_dropout}}회 탐지하였다. 폐루프에서 이 탐지는 불필요 정지가 된다.
- **하이브리드**의 사전 예상은 lidar_freeze에서 빗나갔다. 하이브리드는 100회 중 {{a:off_HYBRID_lidar_freeze}}회로 B1({{a:off_B1_lidar_freeze}}회)과 같았다.
  A는 같은 fg 잔차를 CUSUM으로 여러 step 누적해 잡지만, 하이브리드는 원시 잔차의 10-step 윈도우 통계만 받는다. 그래서 "작지만 일정하게 치우친"
  신호가 {{a:p_n_feat_hy}}개 특징 중 일부로 묻힌 것으로 추정한다(구조는 사전 선언대로 바꾸지 않았다). 유해 고장 전체로는 하이브리드 {{a:off_HYBRID_harmful}}이
  B1 {{a:off_B1_harmful}}보다 많고 두 신뢰구간은 겹치지 않는다.
- **정상 오경보**는 네 탐지기 모두 원거리·좌측 장애물 각 100회 중 0~6회 범위이고 신뢰구간이 서로 겹친다. 정상 오경보에서는 탐지기 간 차이를 확인하지 못했다.

## 3. 탐지기 A의 지연·분리·선행 시간

**표 4-3. 탐지기 A 상세(각 100회).** [데이터: AE | 호스트: H3 | 버전: A iteration 3 | 커밋: K4]

| 고장 | 지연 중앙값 (p90) step | 분리 정확도(센서 단위) | 스텝 F1 | 관찰 실행 사고 수 | 사고 전 선행 step 중앙값 (최소) |
|---|---|---|---|---|---|
| lidar_freeze | {{a:off_A_lidar_freeze_delay}} | {{a:off_A_lidar_freeze_sep}} | {{a:off_A_lidar_freeze_f1}} | {{a:off_P0_lidar_freeze_fail}} | {{a:off_A_lidar_freeze_lead}} |
| lidar_dropout | {{a:off_A_lidar_dropout_delay}} | {{a:off_A_lidar_dropout_sep}} | {{a:off_A_lidar_dropout_f1}} | {{a:off_P0_lidar_dropout_fail}} | {{a:off_A_lidar_dropout_lead}} |
| ir_stuck | {{a:off_A_ir_stuck_delay}} | {{a:off_A_ir_stuck_sep}} | {{a:off_A_ir_stuck_f1}} | {{a:off_P0_ir_stuck_fail}} | {{a:off_A_ir_stuck_lead}} |
| steer_delay | {{a:off_A_steer_delay_delay}} | {{a:off_A_steer_delay_sep}} | {{a:off_A_steer_delay_f1}} | {{a:off_P0_steer_delay_fail}} | {{a:off_A_steer_delay_lead}} |
| steer_stuck | {{a:off_A_steer_stuck_delay}} | {{a:off_A_steer_stuck_sep}} | {{a:off_A_steer_stuck_f1}} | {{a:off_P0_steer_stuck_fail}} | {{a:off_A_steer_stuck_lead}} |
| left_clear_stuck | {{a:off_A_left_clear_stuck_delay}} | {{a:off_A_left_clear_stuck_sep}} | {{a:off_A_left_clear_stuck_f1}} | {{a:off_P0_left_clear_stuck_fail}} | {{a:off_A_left_clear_stuck_lead}} |
| lidar_spike | {{a:off_A_lidar_spike_delay}} | {{a:off_A_lidar_spike_sep}} | {{a:off_A_lidar_spike_f1}} | {{a:off_P0_lidar_spike_fail}} | {{a:off_A_lidar_spike_lead}} |
| ir_dropout | {{a:off_A_ir_dropout_delay}} | {{a:off_A_ir_dropout_sep}} | {{a:off_A_ir_dropout_f1}} | {{a:off_P0_ir_dropout_fail}} | {{a:off_A_ir_dropout_lead}} |
| right_clear_stuck | {{a:off_A_right_clear_stuck_delay}} | {{a:off_A_right_clear_stuck_sep}} | {{a:off_A_right_clear_stuck_f1}} | {{a:off_P0_right_clear_stuck_fail}} | {{a:off_A_right_clear_stuck_lead}} |

- 관찰 실행에서 충돌·이탈한 고장 에피소드 {{a:off_A_abf_total}}(사고 전 경보 / 사고 수)에서 A는 모두 사고보다 먼저 경보를 냈다. 폐루프에서 정지로 막을
  수 있는지는 V장에서 확인하였다.
- left_clear_stuck은 지연이 가장 길다. 좌측 장애물은 회피가 시작된 뒤에야 전방 스캔에 잡히므로 lc 채널은 회피 시작 후에야 불일치를 볼 수 있다
  (사전 예상과 같음). 사고 전 선행 시간도 가장 짧다.
- 분리 정확도는 첫 경보 채널이 고장 센서와 같은 비율이다(기대 채널 표는 평가 전 동결). 스텝 F1이 낮은 고장(steer_stuck, left_clear_stuck,
  lidar_dropout)은 고장 구간 일부에서만 잔차가 크거나 탐지가 늦은 경우이다.

## 4. 자이로 σ 가정에 대한 민감도(A)

**표 4-4. σ 일치·불일치 민감도(정상 200회, 고장 900회).** [데이터: AE | 호스트: H3 | 버전: A iteration 3 | 커밋: K4]

| 조건 | 실제 주입 σ | 탐지기 가정 σ | 정상 오경보 (CI) | 고장 탐지 | 지연 중앙값 (p90) |
|---|---|---|---|---|---|
| 기준 | 1 | 1 | {{a:off_base_normal}} ({{a:off_base_normal_ci}}) | {{a:off_A_fault_total}} | {{a:off_base_delay}} |
| 일치 | 0.05 | 0.05 | {{a:off_sg005_normal}} ({{a:off_sg005_normal_ci}}) | {{a:off_sg005_fault}} | {{a:off_sg005_delay}} |
| 일치 | 5 | 5 | {{a:off_sg5_normal}} ({{a:off_sg5_normal_ci}}) | {{a:off_sg5_fault}} | {{a:off_sg5_delay}} |
| 불일치 | 0.5 | 1 | {{a:off_mm05_normal}} ({{a:off_mm05_normal_ci}}) | {{a:off_mm05_fault}} | {{a:off_mm05_delay}} |
| 불일치 | 2 | 1 | {{a:off_mm2_normal}} ({{a:off_mm2_normal_ci}}) | {{a:off_mm2_fault}} | {{a:off_mm2_delay}} |
| 불일치 | 5 | 1 | {{a:off_mm5_normal}} ({{a:off_mm5_normal_ci}}) | {{a:off_mm5_fault}} | {{a:off_mm5_delay}} |

- **σ 일치**(주입과 가정을 함께 바꾸고 σ마다 h를 다시 정함)에서는 결과가 기준과 같았다. ψ 잔차가 가정 σ로 정규화되므로 맞게 동작하는 것이다.
- **σ 불일치**(가정 σ와 h는 고정, 실제 노이즈만 바꿈)에서는 실제 자이로가 가정보다 조용하면(0.5) 영향이 없었다. 반대로 시끄러우면 정상 오경보가
  급증하였다. 2배에서 정상 200회 중 {{a:off_mm2_normal}}회, 5배에서 {{a:off_mm5_normal}}회였다. σ = 5에서 고장 "탐지" {{a:off_mm5_fault}}회는 지연이
  0 step이며, 고장이 아니라 노이즈만으로 첫 step부터 경보가 난 것이므로 탐지로 읽으면 안 된다. σ = 2에서 고장 탐지가 기준보다 많고
  ({{a:off_mm2_fault}}회) 지연 p90이 짧아진 것({{a:off_mm2_delay}})도 노이즈 경보가 섞인 값이므로 탐지 성능이 나아졌다고 읽으면 안 된다.
