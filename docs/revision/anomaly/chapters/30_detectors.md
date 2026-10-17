# III. 탐지기

네 탐지기는 같은 관측(제어기가 받는 센서 출력 + 차량 자기 상태 + 직전 조향 명령 + 탐지기 전용 자이로)만 받는다. 임계값은 모두 같은
절차로 정하였다. 정상 데이터 AN의 에피소드별 최대 점수를 모으고 그 {{a:p_quantile}} 분위수를 h로 두며, 점수가 h를 넘으면 경보이다.
고장 데이터로 임계값을 정하지 않았다.

## 1. 탐지기 A — 모델 잔차 + CUSUM

차량 운동학 모델과 센서 기하로 "이번 step에 보여야 할 값"을 예측하고, 측정과의 차이(잔차)를 채널별로 누적한다. 채널은 {{a:n_ch_a}}개이다.

- **fg**: 정지 장애물 가정에서 자차 이동량만큼 줄어야 할 front_gap과 측정의 차이.
- **trk**: 지난 측정과 자차 이동량으로 추적한 장애물이 통로에 남아 있어야 하는데 무반사가 나오면 불일치.
- **rc·lc**: 추적 장애물로 예측한 right_clear·left_clear와 측정의 불일치.
- **ey**: 참값 y로 예상한 IR 값과 측정 ey의 차이(둘 다 검출일 때).
- **ir_miss**: 참값 y로는 검출이어야 하는데 측정이 미검출이면 불일치(iteration 3에서 추가, VI장).
- **ψ**: 직전 조향 명령으로 예측한 요레이트와 자이로 관측의 차이.

연속 채널은 해석적 노이즈 σ로 z-정규화한 뒤 양측 CUSUM(κ = {{a:p_kappa}})으로, 이산 채널은 베르누이 로그우도비 CUSUM(정상 불일치 확률
p0 = {{a:p_p0}}, 고장 p1 = {{a:p_p1}}, 불일치 1회당 {{a:p_bern_llr}})으로 누적한다. 점수는 채널 최댓값이고, 첫 경보 시점의 최대 채널이 "경보 채널"이다.
이 채널이 고장 센서를 가리키므로 폐루프의 채널별 대응(P2)에 쓴다. A는 정상 데이터로 학습하지 않으며, 정상 데이터는 h를 정하는 데만 썼다.

## 2. 탐지기 B1·B2 — 정상 데이터로만 학습

- **입력**: step마다 {{a:p_n_ch_b}}채널(front_gap·무반사 플래그·Δfront_gap, ey·미검출 플래그, left/right_clear, 직전 조향 명령, 자이로, 속도,
  FSM 상태 one-hot)을 정규화하고, 길이 {{a:p_window}} 윈도우를 1 step씩 이동한다.
- **B1 Isolation Forest**: 윈도우의 채널별 평균·표준편차·최소·최대·끝−처음({{a:p_n_feat_b1}}특징), 트리 {{a:p_if_trees}}개. 점수 = −score_samples.
- **B2 1D 합성곱 오토인코더**: 윈도우 전체를 잠재 {{a:p_ae_latent}}차원으로 압축·복원한 재구성 오차. epoch 상한·조기 종료 인내 {{a:p_ae_epochs}}.
- 학습은 AT 대역(원거리 + 좌측 장애물 정상 주행)에서만 하였다(학습 윈도우 {{a:train_windows}}개). B는 고장 센서를 가리키지 못하므로 폐루프에서는
  전역 정지(P1)만 쓴다.
- **PC 간 동일성**: 다른 PC(H4)에서 같은 데이터로 IF를 다시 학습해 고정 입력({{a:ifid_n}}윈도우) 점수를 비교하였다. 최대 차이는 B1 {{a:ifid_b}},
  하이브리드 {{a:ifid_hy}}였다.

## 3. 하이브리드 — A의 잔차를 B1 특징으로

B1의 {{a:p_n_ch_b}}채널에 A의 원시 잔차 {{a:n_ch_a}}채널(CUSUM 점수가 아니라 step별 잔차)을 더해 {{a:p_n_ch_hy}}채널 × 5통계 = {{a:p_n_feat_hy}}특징으로
Isolation Forest를 학습하였다. 하이퍼파라미터·학습 데이터·임계값 절차는 B1과 같다. 학습 전에 "A의 fg 잔차를 받으므로 lidar_freeze 탐지가 B1보다
뚜렷이 오를 것"이라고 예상하였다(IV장에서 대조).

## 4. 임계값

**표 3-1. 탐지기별 임계값.** [데이터: AN | 호스트: H1 · H3 | 버전: A iteration 3 · B iteration 2 · 하이브리드 iteration 3 | 커밋: K2 · K3 · K4]

| 탐지기 | h | 정상 데이터 | 비고 |
|---|---|---|---|
| A | {{a:h_a}} | 원거리 + 좌측 장애물 {{a:thr_n_normal}}회 | 정상 중 h 초과 {{a:h_a_over}}회. iteration 1(원거리 200회만)은 {{a:h_a_it1}} |
| B1 | {{a:h_b1}} | 같음 | iteration 1은 {{a:h_b1_it1}} |
| B2 | {{a:h_b2}} | 같음 | iteration 1은 {{a:h_b2_it1}} |
| 하이브리드 | {{a:h_hy}} | 같음 | — |

- 임계값 정상 데이터 {{a:thr_n_normal}}회의 결과는 {{a:thr_outcomes}}이었다. 이 충돌 1건은 고장이 없는 좌측 장애물 정상 주행에서 나왔다(V장 5절과 같은 계열).
- 정상 데이터에서 ir_miss 채널의 최대 점수는 {{a:thr_irmiss_max}}였다. 참값 y를 쓰는 한 정상 주행의 IR 미검출 불일치는 해석적으로 0이기 때문이다(VII장).

## 5. 계산 시간(공식 조건)

노트북 H1({{a:tm_cond}})에서 정상 주행 {{a:tm_n_eps}}회(데이터 AN, 원거리 + 좌측 장애물, 고장 없음)를 탐지기마다 따로 실행해 step별 시간을 쟀다
(탐지기당 {{a:tm_n_steps}} step, 커밋 K7). "제어 1스텝"은 센서(S4 노이즈 포함)부터 FSM, 횡방향(v2 MPC), 종방향, 후처리, 차량 갱신, 충돌 판정까지이다.
탐지기 시간은 `update()` 1회이다. "합"은 같은 step의 두 시간을 더한 값이다. 예산은 20 Hz 제어 주기 {{a:tm_budget}}이다. 측정 루프는 제어를 바꾸지 않았다.
4개 패스의 에피소드 결과(결과 분류·step 수)가 저장된 임계값 실행과 {{a:tm_match}} 일치하였다.

**표 3-2. 탐지기 계산 시간(step당, 괄호는 {{a:tm_budget}} 대비).** [데이터: AN | 호스트: H1 | 버전: A iteration 3 · B iteration 2 · 하이브리드 iteration 3 · improved v2 | 커밋: K7]

| 탐지기 | 탐지기 단독 p50 | p99 | 최댓값 | 예산 초과 step | 제어 1스텝 + 탐지기 p99 | 최댓값 | 예산 초과 step |
|---|---|---|---|---|---|---|---|
| A | {{a:tm_A_det_p50}} | {{a:tm_A_det_p99}} ({{a:tm_A_det_p99_pct}}) | {{a:tm_A_det_max}} ({{a:tm_A_det_max_pct}}) | {{a:tm_A_det_over}} | {{a:tm_A_comb_p99}} ({{a:tm_A_comb_p99_pct}}) | {{a:tm_A_comb_max}} ({{a:tm_A_comb_max_pct}}) | {{a:tm_A_comb_over}} |
| B1 | {{a:tm_B1_det_p50}} | {{a:tm_B1_det_p99}} ({{a:tm_B1_det_p99_pct}}) | {{a:tm_B1_det_max}} ({{a:tm_B1_det_max_pct}}) | {{a:tm_B1_det_over}} | {{a:tm_B1_comb_p99}} ({{a:tm_B1_comb_p99_pct}}) | {{a:tm_B1_comb_max}} ({{a:tm_B1_comb_max_pct}}) | {{a:tm_B1_comb_over}} |
| B2 | {{a:tm_B2_det_p50}} | {{a:tm_B2_det_p99}} ({{a:tm_B2_det_p99_pct}}) | {{a:tm_B2_det_max}} ({{a:tm_B2_det_max_pct}}) | {{a:tm_B2_det_over}} | {{a:tm_B2_comb_p99}} ({{a:tm_B2_comb_p99_pct}}) | {{a:tm_B2_comb_max}} ({{a:tm_B2_comb_max_pct}}) | {{a:tm_B2_comb_over}} |
| 하이브리드 | {{a:tm_HYBRID_det_p50}} | {{a:tm_HYBRID_det_p99}} ({{a:tm_HYBRID_det_p99_pct}}) | {{a:tm_HYBRID_det_max}} ({{a:tm_HYBRID_det_max_pct}}) | {{a:tm_HYBRID_det_over}} | {{a:tm_HYBRID_comb_p99}} ({{a:tm_HYBRID_comb_p99_pct}}) | {{a:tm_HYBRID_comb_max}} ({{a:tm_HYBRID_comb_max_pct}}) | {{a:tm_HYBRID_comb_over}} |

- **A·B2는 최악값까지 20 Hz 예산 이내였다.** 측정한 모든 step에서 제어 1스텝 + 탐지기가 예산 안에 끝났다.
- **B1·하이브리드는 p99는 예산 이내지만 최댓값이 예산을 넘었다. 따라서 스텝마다 예산 안에 끝난다고 보장되지 않는다.** 예산을 넘은 step은
  B1 {{a:tm_B1_det_over}}개, 하이브리드 {{a:tm_HYBRID_det_over}}개였고, 두 번째로 큰 값은 B1 {{a:tm_B1_det_2nd}}, 하이브리드 {{a:tm_HYBRID_det_2nd}}였다.
- 원인은 **Isolation Forest 단일 샘플 호출 비용(추정)**으로 본다. B1·하이브리드의 p50은 B2의 {{a:tm_b_over_ratio}}이고, 둘 다 step마다 윈도우 1개로
  IF(트리 {{a:p_if_trees}}개)를 호출한다. 호출 내부 시간은 나누어 재지 않았다. 예산을 넘은 1 step이 이 비용에서 왔는지, OS 스케줄링 같은 다른 요인에서
  왔는지도 분리하지 않았다. 코드는 바꾸지 않았으며 대안(트리 수 축소, ONNX 변환 등)은 `repro/docs/IMPROVEMENT_BACKLOG.md`에 후보로만 기록하였다.
- 하이브리드의 시간에는 내부 DetectorA 계산이 들어 있다.
- 참고로 제어 1스텝 p99는 {{a:tm_ctrl_p99}}, v2 MPC solve p99는 {{a:tm_mpc_p99}}였다(4개 패스 범위). 시나리오와 노이즈 조건이 달라 기존 개정 보고서의
  계산 시간 값과 직접 비교하지 않는다.
- **이 값은 노트북 `x86` 한 대의 공식 조건 값이며, 임베디드 보드에서는 측정하지 않았다**(VII장 9).
