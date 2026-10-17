# 2단계-C: baseline 결과 판정

`MEASURE_PLAN.md`(2단계-A 확정, 2026-09-17 §"환경 결정 변경" 반영판)의 판정 기준을 그대로
적용합니다. 기준 자체는 이 문서 작성 중 바꾸지 않았습니다. 원본 데이터는
`thesis_v2/results/`의 4개 폴더(아래 §0), 분석 스크립트·산출물은 `repro/2c_analysis/`
(코드는 읽기 전용 분석 — baseline 로직·결과 폴더 어느 쪽도 수정하지 않았습니다).

---

## §0. 실행 정보

| 폴더 | 시나리오 | seed 범위 | 비고 |
|---|---|---|---|
| `20260917_221415_DESKTOP-MDCKRJS_baseline_P` | paper | 0–99 | 배터리 구동 |
| `20260917_221418_DESKTOP-MDCKRJS_baseline_P_leftobs` | left_obstacle | 0–99 | 배터리 구동 |
| `20260917_221615_DESKTOP-MDCKRJS_baseline_P_AC` | paper | 0–99 | "AC" 지정 실행(§5 참고 — 실측상 조건 미충족) |
| `20260917_221618_DESKTOP-MDCKRJS_baseline_P_leftobs_AC` | left_obstacle | 0–99 | "AC" 지정 실행(§5 참고) |

공통 환경: hostname `DESKTOP-MDCKRJS`(공식 측정 호스트, MEASURE_PLAN.md 공통 원칙),
Python 3.9.12, numpy 2.0.2, scipy 1.13.1, osqp 1.1.1.

---

## §1. 핵심 주장 검증 (repro/docs/WORK_RULES.md 핵심 주장 1·2)

| 핵심 주장 | 검증 방법 | 결과 | 판정 |
|---|---|---|---|
| 1. MPC(OSQP)가 제약을 만족하는 조향각을 계산한다 | δ/ψ/y를 REQ-MPC-04/05 범위 대비 eps_abs 허용오차 내로 검사(전 스텝) | paper: 15,433/15,433 스텝 전부 허용오차 내(위반 0). left_obstacle: 4,661(δ,ψ)/4,561(y, SAFE_STOP 제외) 스텝 전부 허용오차 내(위반 0). clip 187건(paper)·0건(left_obstacle) 전부 `clip_numerical`(위반 아님), `clip_violation` 0건. QP 실패(solver_fail) 0건, fallback 0건(4개 폴더 합산 400 에피소드 전체) | **합격** |
| 2. 종방향은 규칙기반, MPC가 속도를 건드리지 않는다 | 매 스텝 v_cmd가 REQ-SPD-01/02 값(V_MAX 또는 0.0) 중 하나인지 | 4개 폴더 전체(총 40,188 스텝)에서 위반 0건 | **합격** |

*2026-09-24 재확인*: `metrics.py`의 `TOL_DELTA_DEG` 정의 오류(§19, `SETTINGS_DECISION.md`)를
I5 dev ablation 판정 중 발견해 baseline에도 소급 재검토했습니다. baseline은 원래
δ/ψ/y 위반 0건(위 표)이라 정정된 허용오차(0.013731°, eps_abs만 반영 시 0.005730°)를
적용해도 판정에 변화가 없습니다(0→0).

---

## §2. P트랙 판정표 — `paper` 시나리오 (100 에피소드, 배터리+AC 두 실행 모두 동일 결과)

| 항목 | 기준(MEASURE_PLAN.md) | 실측 | 판정 |
|---|---|---|---|
| 제약 만족(허용오차 내)/위반 | 100% 만족, 위반=버그 취급 | δ 100%(15433/15433), ψ 100%, y 100% | **합격** |
| clip 분리(`clip_numerical`/`clip_violation`) | `clip_violation` 0건 기대 | clip 187건 전부 `clip_numerical`, `clip_violation` 0건 | **합격** |
| 조향 포화 비율 | 기준 없음(기술통계), KEEP 상태에서 잦으면 원인분석 | KEEP_L2 0%, KEEP_L1 0%, EVADE_L 2.49%, RETURN_TO_L2 7.24% | **정보**(이상 없음) |
| 성공률 | REQ-EVAL-04(§10) | **99/100 (95% CI 94.6–99.8%)** | **정보**(충돌률과 상보, 판정은 충돌률 행 참고) |
| 충돌률 | 0건이 기대값, 발생하면 안 됨(발생 시 결과로 보고) | **1/100 (95% CI 0.2–5.4%) 충돌(seed=85)** | **불합격**(§4 원인분석 정정판: 구현 버그 아님 — 회피 궤적 자체는 존재했음이 확인됨, MPC 비용함수가 장애물을 인지 못 해 그 여유를 못 쓴 **제어기 설계 한계**, `THESIS_REVISION_LOG.md`/`IMPROVEMENT_BACKLOG.md` 후보4 기록) |
| SAFE_STOP 발생 횟수 | 0건 기대(시나리오상 left_clear 항상 True) | 0/100 (95% CI 0.0–3.7%) | **합격** |
| FSM 상태별 체류·오차 | 기준 없음(참고) | KEEP_L2 3079, EVADE_L 5229, KEEP_L1 1781, RETURN_TO_L2 5344 step (배터리 실행 기준) | **정보** |
| MPC 계산시간 | 공식(AC+최고성능)에서 평균이 50ms의 몇 %인지 | AC 조건 확인된 최선의 참고값(§5b, 2026-09-17 22:42 충전기 연결 재실행): mean=0.1124ms(예산의 0.22%), p99=0.3031ms, max=10.595ms(이상치, §6). 배터리: mean=0.1356ms, p99=0.4218ms, max=15.686ms | **보류**(§5b: AC는 확인, "최고 성능" 모드는 미확인 — `power_mode_overlay` 기록 포함 재실행 필요. 참고값 자체는 예산 대비 매우 여유) |
| 종방향 제어 정합성 | v_cmd가 REQ-SPD를 벗어나면 안 됨 | 위반 0건 | **합격** |

## §3. P트랙 판정표 — `left_obstacle` 시나리오 (추가 검증, 100 에피소드)

| 항목 | 기준 | 실측 | 판정 |
|---|---|---|---|
| 제약 만족(허용오차 내)/위반 | 100% 만족 | δ/ψ 100%(4661/4661), y 100%(4561/4561, SAFE_STOP 제외) | **합격** |
| clip 분리 | `clip_violation` 0건 기대 | clip 0건 | **합격** |
| 충돌률 | 0건 기대 | 0/100 (95% CI 0.0–3.7%) | **합격** |
| SAFE_STOP 발생(기대 결과) | REQ-FSM-02b 검증 목적상 **발생이 기대값** | 100/100 (95% CI 96.3–100.0%) | **합격** |

**조건부 표기(2026-09-22 추가)**: 위 §2·§3의 "제약 만족 100%"는 **REQ-SIM-03이 정의한
실현 가능한 초기조건 분포(v0–U(0.3,0.5), y0–TruncatedNormal(0,0.05²,[-0.15,0.15]),
ψ0=0 고정)에서 100%**라는 뜻입니다. `ROBUSTNESS_PLAN.md` S6([발전] 강건성 검증, ψ0을
흔든 그리드)에서는 ψ0=-15° 근방 + y0가 truncation 경계에 가까운 조합 1건(seed=6)에서
제약 위반이 관측됐고, 원인은 baseline 버그가 아니라 **REQ-MPC-06(MPC가 이전 조향값을
모름)·REQ-MPC-07(fallback이 약함)의 제어기 설계 한계**로 판정됐습니다(baseline
`paper`/`left_obstacle`은 ψ0=0 고정이라 영향 없음 — `THESIS_REVISION_LOG.md` 2026-09-22
정정 항목, `RESULT_ROBUSTNESS.md` §2 참고). "100% 만족"을 무조건적 보장으로 읽지 말고
이 범위 조건과 함께 인용하십시오.
| MPC 계산시간 | 위와 동일(보류 사유 동일) | AC 조건 확인된 참고값(§5b): mean=0.1303ms, p99=0.3553ms, max=0.5871ms(첫 호출, warm-up — 첫호출 제외 max=0.3584ms). 배터리: mean=0.1326ms, p99=0.3125ms, max=0.4793ms | **보류**(§5b: AC는 확인, "최고 성능" 모드는 미확인) |
| 종방향 제어 정합성 | 동일 | 위반 0건 | **합격** |

---

## §4. 충돌(seed=85) 원인 분석 요약 — **정정판**(최초 분류 "논문 로직상 불가피"는 오판정,
아래로 정정)

- **분류(정정): 제어기 설계 한계 — MPC 비용함수가 장애물을 인지하지 않고 목표 차선만
  추종하며, 헤딩 가중치(qψ)로 궤적이 완만해짐. 구현 버그 아님.**
- **재검증(사용자 수기 검산 + 독립 재계산 일치)**: δ≤25°·10°/step·회전 사각형·차선경계
  0.45·초기 ψ=0 조건으로 "최대노력(bang-bang, 항상 δ=+25°)" 정책의 최소 필요
  front_gap0을 계산(`repro/2c_analysis/avoidance_feasibility_recheck.py`, baseline의
  `vehicle.step`/`collision.check_collision`을 그대로 재사용). seed=85 실제 초기조건
  (y0=−0.0464, v0=0.3944, ψ0=0)에서 **최소 feasible front_gap0=0.2675m, 실제
  front_gap0=0.5665m → 여유 0.2990m**. 즉 **회피 궤적이 존재함** — "물리적으로
  불가피한 충돌"이 아닙니다. 초기 y0 스윕(0.0/−0.046/−0.10/−0.15, v=V_MAX=0.5
  worst-case)에서도 사용자 수기값(0.26/0.30/0.33/0.36m)과 본 재계산값
  (0.2362/0.2739/0.3069/0.3307m)이 같은 경향·같은 결론으로 일치(세부 수치 차이
  ≈10%는 방법론 디테일 차이로 추정, 결론에 무관 — `FEASIBILITY_CHECK.md` 계산3).
- **근본 원인(정정)**: REQ-MPC-02 비용함수(J=Σqy(y−y_ref)²+qψψ²+rδδ₀²+rΔδΔδ²)는
  장애물의 존재·위치를 전혀 입력받지 않습니다(REQ-MPC-08과 일관 — z에 장애물 관련 변수
  없음). 그 결과 MPC는 "얼마나 급하게 피해야 하는지"와 무관하게 매 스텝 같은 비용
  최적화만 수행하며, 실제 관측(`seed85_heading_steering_compare.png`)에서 헤딩이
  step11 부근 17.4°에서 정체·감소하기 시작해(qψ 벌점 때문) 가용 여유(0.299m)를 다
  쓰지 않고 완만하게 돕니다. FSM의 EVADE_L 트리거 자체(front_gap<G_TRIG)는 이미
  이론상 최선의 시점(첫 스텝)에 반응했으므로 트리거 조건은 원인이 아닙니다(최초 분류의
  오류 — 트리거 지연이 아니라 MPC의 **회피 후 거동**이 원인).
- 근거(변경 없음): MPC는 매 스텝 solved(OSQP 실패·fallback 없음), δ/ψ/y 전부 허용오차
  내 — 제어기가 "제약을 만족하는 조향각을 계산한다"는 핵심 주장 1 자체는 훼손되지
  않음(제약 자체가 장애물을 몰라서 생긴 문제). seed=34(더 근접·더 빠른데 성공, y0가
  회피 방향에 이미 가까움)는 y0이 결정적 변수임을 보여주는 보조 증거로 유지.
- 산출물: `repro/2c_analysis/out/collision_seed85_pre_impact.md`(24 step 전체 표),
  `collision_seed85_trajectory.png`(궤적+사각형), `collision_seed85_vs_seed34_compare.md`
  (비교표), `avoidance_feasibility_recheck.json`(재계산 원자료),
  `seed85_heading_steering_compare.md/png`(실제 vs 회피가능 헤딩·조향 비교). 기록:
  `THESIS_REVISION_LOG.md`(2026-09-17, REQ-MPC-02 항목, 정정판),
  `IMPROVEMENT_BACKLOG.md` 후보4(정정판).

---

## §5. 배터리 vs AC 비교

- **제어 결과(전이 목록·결과 분류·완료 step)**: paper 100/100, left_obstacle 100/100
  **완전히 동일**(차이 0건) — 결정론적 재현성 확인(`repro/2c_analysis/battery_vs_ac_compare.py`).
- **중요 발견 — "AC" 폴더가 실제로는 공식 조건을 충족하지 못함**: `env.json` 실측값을
  확인한 결과, "AC"로 이름 붙인 두 폴더도 `power.ac_status="battery"`,
  `power.power_plan="균형 조정"`(Balanced)로 기록되어 있습니다 — **AC 전원도 최고 성능
  모드도 실제로는 적용되지 않은 상태**였습니다(배터리 실행 폴더와 전원 조건이 동일). 이
  노트북에서 `.NET SystemInformation.PowerStatus`로 별도 교차 확인한 결과 현재 시점엔
  실제로 AC가 연결되어 있어(`PowerLineStatus=Online`) 계측 코드(`envinfo.py`) 자체의
  버그는 아닌 것으로 확인했습니다 — 즉 **실행 당시 실제로 배터리 상태였거나 전원 계획을
  변경하지 않은 채 실행된 것으로 판단됩니다.** 계산시간을 "공식" 수치로 확정하려면
  전원 연결 + Windows 전원 모드를 "고성능"류로 실제 전환한 뒤 재실행이 필요합니다(§2/§3
  "보류" 판정의 근거).
- **계산시간 비교표(참고용 — 위 사유로 양쪽 다 비공식)**:

| 시나리오 | 실행 | mean(ms) | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| paper | 배터리 | 0.1356 | 0.1082 | 0.2357 | 0.4218 | 15.6864 |
| paper | "AC" | 0.1416 | 0.1075 | 0.2738 | 0.4956 | 22.9345 |
| left_obstacle | 배터리 | 0.1326 | 0.1108 | 0.2515 | 0.3125 | 0.4793 |
| left_obstacle | "AC" | 0.1358 | 0.1113 | 0.2683 | 0.4465 | 0.5209 |

  "AC" 실행이 모든 지표에서 오히려 배터리 실행보다 소폭 느립니다 — 두 실행의 실제 전원
  조건이 같았다는 위 발견과 일치하며(성능 모드가 정말 바뀌었다면 반대 경향이 기대됨),
  차이는 정상적인 시스템 잡음 범위로 판단됩니다.

---

## §5b. 충전기 연결 후 재실행 비교 (2026-09-17 22:42–22:43, 가장 최근 실행)

사용자가 충전기를 연결한 뒤 재실행한 결과 폴더 2개
(`20260917_224259_DESKTOP-MDCKRJS_baseline_P_AC`,
`20260917_224302_DESKTOP-MDCKRJS_baseline_P_leftobs_AC`)를
`repro/2c_analysis/battery_vs_new_ac_compare.py`로 배터리 실행과 비교했습니다.

- **env.json 실측**: 이번엔 `ac_status="AC"`로 **실제로 AC 연결이 확인됨**(§5의 이전
  "AC" 폴더와 달리 정상). 다만 `power_plan="균형 조정"`(고전 전원 계획, overlay 아님)은
  그대로이고, **`power_mode_overlay` 필드는 이 실행 시점엔 기능이 없어 기록되지
  않았습니다**(항목3에서 막 추가함) — 즉 **"Windows 전원 모드=최고 성능" 조건은 이
  실행에서 확인할 방법이 없습니다**(기록 자체가 없음, "미충족"이 아니라 "미확인").
- **제어 결과 동일성**: paper 100/100, left_obstacle 100/100 **완전히 동일**(배터리
  대비 차이 0건) — 재확인.
- **계산시간 비교표**:

| 시나리오 | 실행 | mean(ms) | p50 | p95 | p99 | max | max(첫호출 제외) |
|---|---|---|---|---|---|---|---|
| paper | 배터리 | 0.1356 | 0.1082 | 0.2357 | 0.4218 | 15.6864 | 15.6864 |
| paper | 새 AC(충전기 연결) | 0.1124 | 0.0977 | 0.1902 | 0.3031 | 10.5950 | 10.5950 |
| left_obstacle | 배터리 | 0.1326 | 0.1108 | 0.2515 | 0.3125 | 0.4793 | 0.4793 |
| left_obstacle | 새 AC(충전기 연결) | 0.1303 | 0.1055 | 0.2520 | 0.3553 | 0.5871 | 0.3584(**max는 그 episode의 첫 MPC 호출**) |

  paper 시나리오는 이번엔 AC 쪽이 전 지표에서 **일관되게 더 빠릅니다**(mean −17%, p99
  −28%, max −32%) — §5의 "가짜 AC"(실제 배터리)와 달리 방향이 물리적으로 타당합니다
  (AC 연결 자체의 효과로 보임). left_obstacle은 표본이 작아(에피소드당 MPC 호출 3–4회
  수준) 차이가 통계적으로 유의한지 판단하기 어렵습니다.
- **판정(MEASURE_PLAN.md §"계산시간 측정 조건" 기준 그대로 적용)**: AC 조건은 이번에
  **충족**이 확인됐지만, "Windows 전원 모드=최고 성능" 조건은 **미확인**(기록 없음,
  §3에서 추가한 `power_mode_overlay` 필드가 이 실행에는 없음)이므로, 두 조건을 **모두**
  요구하는 공식 기준을 완전히 만족했다고 확정할 수 없습니다. **§2/§3의 계산시간 판정은
  "보류"를 유지**합니다 — 단, 이 새 AC 데이터를 "AC 조건은 확인된 최선의 참고값"으로
  §2/§3에 반영합니다. 완전한 공식 판정을 원하면 `power_mode_overlay` 필드가 포함된
  현재 코드로 한 번 더 재실행하고, 실행 전 Windows 설정에서 "전원 모드"를 육안으로
  "최고 성능"으로 확인하십시오(MEASURE_PLAN.md 수동 확인 체크 항목).

---

## §6. 계산시간 이상치(참고)

paper 시나리오에서 max 계산시간이 p99 대비 30–50배 큰 이상치(15.69ms, 22.93ms, 배터리·
구AC 실행 기준)가 각각 1건씩 관측되었습니다(`repro/2c_analysis/out/missing_metrics_report.json`).
둘 다 EVADE_L 상태, 해당 에피소드의 **첫 MPC 호출이 아님**(warm-start 문제가 아님을 시사),
p50/p95/p99는 모두 정상 범위(<0.5ms)라 OS 스케줄링 잡음(다른 프로세스 간섭 등) 가능성이
높습니다 — OSQP 알고리즘 자체의 특이 동작으로 보이지 않습니다. **충전기 연결 재실행(§5b)
에서도 paper에 유사한 이상치(10.60ms, 역시 첫 호출 아님)가 재현**되어, 일회성이 아니라
이 환경(노트북)에서 간헐적으로 나타나는 OS 스케줄링 잡음일 가능성이 더 높아졌습니다.
left_obstacle은 새 AC 실행에서 max(0.5871ms)가 **그 episode의 첫 호출**로 확인되어(§5b),
그 경우는 warm-up 효과로 분류합니다 — summary.json의 `max_excluding_first_call`
(0.3584ms)이 이런 경우를 자동으로 분리해 보여줍니다.

---

## §7. 종합

- 핵심 주장 1·2: **합격**.
- 제약 만족·clip·SAFE_STOP·종방향 정합성: **전부 합격**(두 시나리오 공통).
- **충돌률만 불합격**(paper 1/100, 95% CI 0.2–5.4%) — 원인은 구현 버그가 아니라 **MPC 비용함수가 장애물을
  인지하지 않는 제어기 설계 한계**로 확인됨(정정판, §4). 회피에 필요한 거리보다 실제
  여유가 더 컸음(margin 0.299m)에도 MPC가 그 여유를 쓰지 않고 목표 차선 추종 위주로
  완만하게 돌았음. baseline 코드는 결과에 맞춰 수정하지 않았습니다(repro/docs/WORK_RULES.md 금지 목록).
- 계산시간 공식 판정은 **여전히 보류** — 지금까지의 실행 4개(§5, §5b) 전부 정식 공식
  조건을 만족하지 못했습니다. **도구는 이제 준비됨**: `run.py --power-mode-confirmed`
  플래그(2026-09-17 추가)가 육안 확인 시각을 `env.json`에 남기고
  `power.meets_official_condition`을 자동 판정합니다(`ac_status=="AC" AND
  (power_mode_overlay 최고 성능 GUID 감지 OR power_mode_user_confirmed==true)`). §8의
  공식 재실행 명령으로 실행하면, `power.meets_official_condition==true`인 결과 폴더의
  `mpc_solve_time_ms`/`step_time_ms`를 곧바로 "합격/불합격"으로 승격할 수 있습니다(이
  문서는 아직 그 실행을 반영하지 않은 상태입니다).

## §8. 공식 재실행 명령 (준비 완료, 실행 대기)

```bash
.venv/Scripts/python.exe -m thesis_v2.baseline.run --scenario paper --seed-start 0 --n-episodes 100 --power-mode-confirmed --out "thesis_v2/results/$(date +%Y%m%d_%H%M%S)_$(hostname)_baseline_P_OFFICIAL"
.venv/Scripts/python.exe -m thesis_v2.baseline.run --scenario left_obstacle --seed-start 0 --n-episodes 100 --power-mode-confirmed --out "thesis_v2/results/$(date +%Y%m%d_%H%M%S)_$(hostname)_baseline_P_leftobs_OFFICIAL"
```

실행 전 Windows 설정 > 시스템 > 전원 > "전원 모드"를 "최고 성능"으로 직접 바꾸고
충전기를 연결한 상태여야 `meets_official_condition=true`가 기록됩니다(둘 중 하나라도
빠지면 `--power-mode-confirmed`를 줘도 `ac_status`가 "battery"거나 마찬가지로 참고용
처리됨 -- 플래그는 "전원 모드"만 대신 확인해줄 뿐 AC 연결 자체는 여전히 자동 감지값을
따릅니다). 결과 폴더의 `env.json`에서 `power.meets_official_condition`을 확인해
`RESULT_BASELINE.md`의 계산시간 판정을 갱신하십시오.

---

## §9. 교차 환경 재현성 — SSAFY PC 확인 (2026-09-18, 미뤄뒀던 항목)

**실행**: `python -m thesis_v2.tests.check_golden` (SSAFY PC, `.venv`, `--system-site-packages`
로 생성).

| 항목 | golden 생성 환경(노트북) | 확인 환경(SSAFY PC, 이번 실행) |
|---|---|---|
| hostname | `DESKTOP-MDCKRJS` | `3층PC108` |
| Python | 3.9.12 | 3.12.9 |
| numpy | 2.0.2 | 2.5.1 |
| scipy | 1.13.1 | 1.18.0 |
| osqp | **1.1.1**(venv) | **1.1.3** |
| OS | Windows-10-10.0.26200-SP0 | Windows-11-10.0.26200-SP0 |
| CPU | Intel Core Ultra 9 185H | Intel Core i7-9700 |

참고(확인됨, `SETTINGS_DECISION.md` §18): 노트북에서는 venv(`osqp==1.1.1`) 외에 base 환경
(`osqp==1.0.4`)에서도 OSQP 설정 API(`polishing`/`warm_starting`/`raise_error` 이름·기본값)를
별도로 실측 확인한 바 있습니다. 다만 그 확인은 API 동작 확인이었고, `check_golden.py` 자체를
osqp 1.0.4로 재실행한 기록은 없습니다(추정 아님 — `repro/docs` 어디에도 그 실행 로그가 없음을
확인함) — 따라서 아래 결과는 "노트북 osqp 1.1.1 golden vs SSAFY PC osqp 1.1.3"의 비교입니다.

**결과**: 6/6 시나리오·seed 조합 전부 **PASS**(전이 목록·결과 분류·완료 step 완전 일치,
조향각 시계열 최대 차이 = **0.000000 rad**, 6개 조합 전부 동일 — `paper` seed 0–2,
`left_obstacle` seed 0–2).

```
[PASS] paper seed=0: 일치 (max|diff|=0.000000 rad)
[PASS] paper seed=1: 일치 (max|diff|=0.000000 rad)
[PASS] paper seed=2: 일치 (max|diff|=0.000000 rad)
[PASS] left_obstacle seed=0: 일치 (max|diff|=0.000000 rad)
[PASS] left_obstacle seed=1: 일치 (max|diff|=0.000000 rad)
[PASS] left_obstacle seed=2: 일치 (max|diff|=0.000000 rad)
전체 결과: PASS
```

**해석**: osqp 1.1.1→1.1.3, numpy 2.0.2→2.5.1, scipy 1.13.1→1.18.0, Python 3.9→3.12,
Windows 10→11, 다른 CPU(다른 마이크로아키텍처) 조합에서도 완전 결정론적으로 동일한 조향각
시계열이 나왔습니다. 판정 기준(`MEASURE_PLAN.md`)은 "차이 ≤1e-3 rad"였으나 실측 차이는
정확히 0이었으므로, 부동소수점 연산 순서 차이(BLAS 구현 차이 등)로 인한 수치 흔들림조차
관측되지 않았습니다 — QP 자체가 결정론적(warm-start 없이 매 스텝 새로 setup, 동일 KKT 조건)
이고 OSQP의 ADMM 반복이 두 버전에서 같은 수렴 경로를 탔다는 뜻으로 해석됩니다. 실패 사례가
없어 "실패 시 원인 분석" 절차는 적용되지 않았습니다.

**결론**: `MEASURE_PLAN.md` §"교차 환경(노트북 ↔ SSAFY PC) 재현성"의 "SSAFY PC 쪽 golden
교차 확인은 미확인(추후)" 상태를 **확인 완료**로 갱신합니다(양방향 모두 PASS).
