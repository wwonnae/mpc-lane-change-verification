# II. 고장 모델과 실험 조건

## 1. 제어기가 받는 신호

제어기 입력 중 센서 측정값은 LiDAR 계열(front_gap, left_clear, right_clear, v2 MPC가 쓰는 전방 장애물 정보)과 IR 패턴에서 변환한
ey_line뿐이다. 차량 자기 상태 y·ψ는 추정기를 거치지 않은 시뮬레이터 참값이고, 속도 v는 직전 step의 속도 명령 그 자체이다
(REQ-VEH-05, 속도 동역학 없음). 따라서 "속도 센서 드리프트"는 대응하는 센서가 없어 고장 목록에서 제외하였다.

고장은 "센서 함수 출력 → [고장 주입] → [탐지기] → 제어기" 위치에 넣었다. 조향 고장만 후처리 이후 최종 조향이 차량에 들어가는 위치에
넣었다. LiDAR 고장은 front_gap과 v2 MPC의 장애물 정보에 같은 값으로 들어간다.

## 2. 고장 9종

고장 크기·지속시간·onset 범위는 dev seed {{a:f_dev_band}}에서 탐지기 없이 실행해 "영향이 나타나는 범위 + 무해 범위"를 포함하도록
정하였고, 평가에서는 바꾸지 않았다. 유해·무해 구분도 같은 dev 실행(탐지기 없음)에서 충돌·이탈이 생겼는지로 정하였다.

**표 2-1. 고장 목록.** [데이터: 정의 표(범위 결정은 AD 일부, 마지막 열은 AE) | 호스트: 해당 없음(마지막 열은 H3) | 버전: improved v2 · 고장 주입기 | 커밋: K1 · K4]

| 고장 | 주입 방식 | 범위 | 구분 | 관찰 실행 충돌·이탈(100회 중, AE) |
|---|---|---|---|---|
| lidar_freeze | front_gap·장애물 정보를 onset 값으로 고정 | 회피 전 onset, 영구 | 유해 | {{a:off_P0_lidar_freeze_fail}} |
| lidar_dropout | 최대 거리(무반사) 연속 반환 | 회피 시점을 덮도록, 지속 {{a:f_dropout_dur}} | 유해 | {{a:off_P0_lidar_dropout_fail}} |
| ir_stuck | IR 패턴을 한쪽 끝 패턴으로 고정 | 회피 전 onset, 영구 | 유해 | {{a:off_P0_ir_stuck_fail}} |
| steer_delay | 최종 조향의 차량 반영 지연 | {{a:f_delay}}, 영구 | 유해 | {{a:off_P0_steer_delay_fail}} |
| steer_stuck | 조향을 onset 직전 값으로 고정 | 회피 직후, 지속 {{a:f_stuck_dur}} | 유해 | {{a:off_P0_steer_stuck_fail}} |
| left_clear_stuck | left_clear를 True(비어 있음)로 고정 | 좌측 장애물 시나리오, 영구 | 유해 | {{a:off_P0_left_clear_stuck_fail}} |
| lidar_spike | front_gap이 위(최대 거리)·아래({{a:f_spike_down}})로 튐 | {{a:f_spike_dur}}, 위·아래 반반 | 무해 | {{a:off_P0_lidar_spike_fail}} |
| ir_dropout | IR 미검출(ey=None) | 회피 전 onset, 영구 | 무해 | {{a:off_P0_ir_dropout_fail}} |
| right_clear_stuck | right_clear를 True(비어 있음)로 고정 | onset {{a:f_rc_onset}}, 영구 | 무해 | {{a:off_P0_right_clear_stuck_fail}} |

- 마지막 열은 오프라인 평가의 관찰 실행(탐지기가 제어에 개입하지 않음)에서 센 값이다. 무해 고장 3종은 이 실행에서도 충돌·이탈이 없었다.
- ir_dropout은 미검출이면 MPC 경로로 넘어가는 설계 때문에 무해하고, right_clear_stuck(True 고착)은 dev에서 무해함을 확인하였고(탐지기 없이
  성공), 그 원인은 v2 MPC의 장애물 제약이 장애물 옆 복귀를 막기 때문으로 **추정**한다. 이 둘과 lidar_spike는 "탐지해서 멈추면 손해"인 대조군 역할을 한다.
- 고장 onset은 에피소드 시작 후 {{a:p_warmup}} 이후이다(탐지 윈도우 워밍업).

## 3. 정상 조건과 시나리오

- **원거리 시나리오**: 기존 시나리오는 장애물 초기 전단거리가 {{a:p_fg_near}}라 절반가량이 첫 step부터 회피에 들어가, 고장 전 정상 구간이
  없다. 이상탐지 실험은 초기 전단거리를 {{a:p_fg_far}}로 늘리고 에피소드 상한을 {{a:p_maxsteps}}로 두었다(기존 baseline 설정은 그대로).
- **좌측 장애물 시나리오**: 같은 종방향 구간 L1에도 장애물이 있어 정상이면 SAFE_STOP으로 끝난다. left_clear_stuck과 정상 비교용이다.
- **정상 변동**: 시뮬레이션 플랜트와 예측 모델이 같아 노이즈가 없으면 잔차가 정확히 0이 된다. 그래서 정상 조건에 기존 S4-low 센서 노이즈
  (front_gap σ {{a:p_s4_fg}}, ey σ {{a:p_s4_ey}}, left/right_clear 오판정 확률 {{a:p_s4_flip}})를 깔았다.
- **탐지기 전용 자이로**: 조향 고장을 보기 위해 요레이트 관측 g = Δψ/dt + n, n ~ N(0, σ²)을 탐지기에만 주었다(제어기 입력은 그대로).
  σ = {{a:p_sigma_gyro}}는 가정이다. MEMS 자이로 데이터시트의 Total RMS Noise({{a:p_gyro_datasheet}})의 {{a:p_gyro_ratio}}로, 시뮬레이션에 없는
  오차(서보·슬립·진동·보정 잔여)를 대신한다. 정상 주행의 ψ 변동은 전부 이 가정에서 나온다(VII장).
- **이탈 판정**: 차체 기하 중심이 도로 범위({{a:p_depart}}) 밖이면 이탈이다. 모서리 기준은 고장 없는 IR 라인추종의 흔들림도 이탈로 세어 바꿨다.
