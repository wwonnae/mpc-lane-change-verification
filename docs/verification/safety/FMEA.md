# FMEA — 주입 고장 9종 + 비주입 이상 2가지 (시뮬레이션)

> **ISO 26262·AIAG-VDA FMEA의 용어와 틀을 빌려 시뮬레이션 결과를 정리한 것이며, 표준 준수나 안전 인증이 아니다.**
> 대상은 시뮬레이션에서 주입한 고장 9종이다(`thesis_v2/anomaly/faults.py:30-40`). 여기에 평가 중 관찰된(또는 가설로 제기된) 비주입 이상 2가지를 더했다.
> 새 평가는 실행하지 않았다. 이 문서의 모든 수치는 `SAFETY_TABLES.md`(자동 생성, `make_safety_tables.py --check`로 재계산 대조)의 표에 있다.
> 본문에는 수치를 직접 쓰지 않는다.

## 1. 척도와 열 정의

**결과 심각도(시뮬레이션)** — 정의는 `SAFETY_TABLES.md` T1에 있다. 수준이 높을수록 나쁘다.
충돌 > 이탈 > 미완료(타임아웃·미정착·관찰 중 상태 이탈) > 정지(SAFE_STOP·탐지 정지) > 성공 순이다. 순서의 근거는 다음과 같다.
- **충돌**: 차체와 장애물의 회전 사각형이 겹친 것이다(REQ-SIM-08, `repro/docs/SPEC.md:107`). 물리적 접촉이라 피해 가능성이 가장 크다.
- **이탈**: 차체 기하 중심이 도로 밖으로 나간 것이다(DESIGN D5, `thesis_v2/anomaly/DESIGN.md:174`). 접촉은 없지만 차량이 제어 범위를 벗어났다.
- **미완료**: 회피·복귀 임무를 끝내지 못했으나 위험 사건은 없다. 가용성 손실이다.
- **정지**: 안전 상태로 들어갔지만 임무를 중단했다. 정지가 필요 없었다면 불필요 정지, 즉 가용성 손실이다.
  좌측 장애물 정상 시나리오(`none_leftobs`)의 SAFE_STOP은 기대 결과이므로 성공과 같은 수준으로 둔다(`repro/docs/MEASURE_PLAN.md:113`).
- ISO 26262의 S0–S3(사람의 부상 정도 기준)과는 다르다. 이 척도는 시뮬레이션 결과(outcome)의 순서일 뿐이다.

**발생도(O)**: **해당 없음**. 주입 빈도(run당 100회)와 고장 시작 시점은 실험 설계값이다. 실제 센서·액추에이터 고장률이 아니다.

**검출도(D)**: 탐지기 A(주 대상)와 B2·HYBRID·B1의 **오프라인 탐지율 k/100(Wilson 95% CI, T3)**과 **폐루프 결과(P1 즉시 정지 vs P0, T4)**로만 적는다.
AIAG-VDA의 1–10 D 등급으로는 환산하지 않는다. 그 등급표는 검출 방법의 성숙도와 검출 기회로 정의되어 있어, 시뮬레이션 탐지율을 그 등급에 대응시킬 근거가 없기 때문이다(표준 원문은 대조하지 않았다).

**RPN·Action Priority**: **계산하지 않는다.** RPN(S×O×D)은 O가 없어 만들 수 없다. AIAG-VDA FMEA는 곱 대신 S·O·D 조합표로 Action Priority(H/M/L)를 정하며 S를 우선한다는 점이 RPN과 다르다.
그러나 AP도 O를 입력으로 쓰므로 적용하지 않는다(표준 원문은 대조하지 않았다).

**영향의 기준**: P0(탐지기 없음) 폐루프 평가, run별 100회(seed 5000–5099)다. 같은 seed를 run끼리 공유하므로 run 간 결과는 서로 독립이 아니다.

## 2. FMEA 표

| # | 고장 모드 | 주입 위치·동작(코드) | 잠재 영향(정성) | 영향 (P0) | 결과 심각도 | O | 검출도 D | 권고 조치 / 연결 |
|---|---|---|---|---|---|---|---|---|
| 1 | `lidar_freeze` 전방 거리 고착 | `faults.py:116-120` front_gap·장애물 정보를 직전 정상값으로 고정 | 장애물 접근을 보지 못해 회피를 시작하지 않음 | T2 `lidar_freeze` 행 | T2 최댓값 열 | 해당 없음 | T3·T4·T8 `lidar_freeze` 행. A 주, B2·HYBRID·B1 참고(B1·HYBRID는 backlog 후보 14) | 현재 대응은 A 경보 시 즉시 정지(P1/P2). 즉시 정지 가정의 한계는 `FTTI.md` §4. B1·HYBRID 시간 → 후보 14 |
| 2 | `lidar_spike` 전방 거리 순간 튐 | `faults.py:121-123` front_gap을 주입값(magnitude)으로 대체. 지속 스텝 범위는 DESIGN §12 고장 범위 표(`thesis_v2/anomaly/DESIGN.md:184`) | 짧은 오측정. 회피 판단이 잠깐 흔들릴 수 있음 | T2 `lidar_spike` 행(무해 고장, `closed_loop.py:297`) | T2 최댓값 열 | 해당 없음 | T3·T4. 탐지가 곧 **불필요 정지**(T4 불필요 정지 열) | 기존 backlog 항목 없음. 무해 고장에서의 정지는 가용성 손실로 분리 |
| 3 | `lidar_dropout` 전방 거리 소실 | `faults.py:124-125` front_gap=최대 거리, 장애물 정보 없음(지속 구간) | 소실 동안 장애물이 없는 것으로 보고 회피가 늦어짐 | T2 `lidar_dropout` 행 | T2 최댓값 열 | 해당 없음 | T3·T4·T8 `lidar_dropout` 행 | 후보 14(B1·HYBRID 행) |
| 4 | `ir_stuck` 라인 센서 고착 | `faults.py:126-128` IR 패턴 고정 → ey_line 고정 | 잘못된 차선 오차로 라인추종이 틀어져 이탈 | T2 `ir_stuck` 행 | T2 최댓값 열 | 해당 없음 | T3·T4·T8 `ir_stuck` 행. P2_A는 ey를 버리고 MPC 경로로 감(정지 없음, T7) | 후보 14(B1·HYBRID 행) |
| 5 | `ir_dropout` 라인 소실 | `faults.py:129-130` IR 패턴 (0,0,0), ey 없음 | 라인 미감지 → MPC 경로(REQ-LAT-03)로 전환 | T2 `ir_dropout` 행(무해 고장) | T2 최댓값 열 | 해당 없음 | T3·T4. P1 탐지는 불필요 정지(T4) | 기존 backlog 항목 없음 |
| 6 | `right_clear_stuck` 우측 비어 있음 판정 고착 | `faults.py:131-132` right_clear 고정 | KEEP_L1 → RETURN 복귀 판단 오류 가능 | T2 `right_clear_stuck` 행(무해 고장) | T2 최댓값 열 | 해당 없음 | T3·T4. P2_A의 rc 덮어쓰기가 **타임아웃**을 만듦(T7·T10) — 위험 사건이 아니라 가용성 손실 | 기존 backlog 항목 없음. P2 rc 정책의 부작용으로 기록 |
| 7 | `left_clear_stuck` 좌측 비어 있음 판정 고착(좌측 장애물 시나리오) | `faults.py:133-134` left_clear 고정 | 막힌 좌측 차선을 비었다고 보고 회피 진입 → 충돌·이탈 | T2 `left_clear_stuck` 행 | T2 최댓값 열 | 해당 없음 | T3·T4·T8. P2_A는 lc를 막힘으로 덮어써 FSM SAFE_STOP으로 감(FRTI는 T7 — 쿨다운 경로를 거침) | **후보 13**(`repro/docs/IMPROVEMENT_BACKLOG.md:210`, 쿨다운이 SAFE_STOP을 늦춤)과 같은 FSM 경로 |
| 8 | `steer_delay` 조향 지연 | `faults.py:144-147` 최종 조향을 d 스텝 늦게 반영 | 진동·과회전 → 충돌·이탈 | T2 `steer_delay` 행 | T2 최댓값 열 | 해당 없음 | T3·T4·T8 `steer_delay` 행 | 후보 14(B1·HYBRID 행) |
| 9 | `steer_stuck` 조향 고착 | `faults.py:148-152` 직전 조향각으로 고정(지속 구간) | 원하는 조향을 못 해 이탈 | T2 `steer_stuck` 행 | T2 최댓값 열 | 해당 없음 | T3·T4·T8 `steer_stuck` 행 | 후보 14(B1·HYBRID 행) |
| 10 | **가설 고장 모드: MPC time_limit 발동**(비주입) | improved v2 MPC의 OSQP `time_limit`(`thesis_v2/improved/config.py:37`, `improved/mpc.py:153`). 벽시계 기준이라 CPU 부하에서 발동할 수 있음 | 발동하면 해가 달라져 결과가 바뀔 수 있음. 노트북 dev `--check` 불일치의 원인 **가설**(DESIGN §24-1, `thesis_v2/anomaly/DESIGN.md:968`, 가설은 982행, "재현되지 않아 확정하지 못했다") | **데이터 없음** — 가설 고장 모드(평가 발동 0/6,600)(T9, `diag_timing.csv`의 time_limit_hits. 이 숫자는 `make_safety_tables.py`가 재계산 값과 대조) | 데이터 없음(영향이 관찰되지 않음) | 해당 없음 | 탐지기 대상 아님. MPC 결과의 `time_limit_hit` 기록과 CI `time_limit_monitor`(`docs/verification/CI.md`)로 감시 | CI에서 발동 여부를 테스트별로 기록(이미 적용) |
| 11 | **비주입 이상: 정상 좌측 장애물 seed 5011 충돌** | 고장 없음(`none_leftobs`) | 원인은 **추정**: left_clear 노이즈 오판정 → 회피 진입 → SAFE_STOP이 쿨다운에 막힘. 같은 경로는 비평가 seed 3173 재현으로 확인했고, 5011 자체의 경로는 기록이 없다(DESIGN §25-1, `thesis_v2/anomaly/DESIGN.md:1220-1232`, `README.md:130`) | T2 `none_leftobs` 행, T9 | T2 최댓값 열 | 해당 없음 | 고장이 아니라 탐지 대상이 아님. 모든 조합에서 같은 결과(T9) | **후보 13**(`repro/docs/IMPROVEMENT_BACKLOG.md:210`) |

- "T2 최댓값 열"은 P0 100회에서 관찰된 가장 나쁜 결과 심각도다. 같은 표에 수준별 횟수 분포도 있다.
- 무해/유해 구분은 설계 단계의 정의를 따른다(`thesis_v2/anomaly/closed_loop.py:296-297`, DESIGN §19-2). 결과로 다시 분류하지 않았다.
- 검출도의 근거 표:
  - T3: 오프라인 seed 4000–4099. 고장 시작된 에피소드 중 탐지된 비율과, 정상 run의 오경보.
  - T4: 폐루프 seed 5000–5099. P1에서 위험 사건이 몇 번 났는지, 막았는지, 새로 생겼는지, 불필요 정지가 몇 번인지.
  - T8: FDTI + FRTI < FTTI 판정(만족 / 저하 운행으로 회피 / 미달 / 판정 제외 — 고장 전 오경보).

## 3. 출처 파일·열

- 폐루프: `thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval/episodes_{P0,P1_A,P1_B1,P1_B2,P1_HYBRID,P2_A}.csv`
  - 열: run, seed, outcome, total_steps, finish_step, onset, first_alarm_step, policy_action, unnecessary_stop
  - 같은 폴더의 `diag_timing.csv`(time_limit_hits, max_solve_ms), `meta.json`(seed 범위, 임계값)
- 오프라인: `thesis_v2/results/anomaly/20261002_145638_3층PC108_it3_eval_offline_eval/episodes_{A,B1,B2,HYBRID}.csv`
  - 열: run, onset, total_steps, detected, delay_steps, alarm_before_onset, alarm_before_failure, first_alarm
- 교차 대조: 두 폴더의 `summary.json`. 폐루프 run별 outcome 수와, 오프라인 detected/fault_started가 CSV 재계산과 같지 않으면 생성기가 중단한다.
