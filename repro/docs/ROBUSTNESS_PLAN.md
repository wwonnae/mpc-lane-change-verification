# 강건성 검증 시나리오 확장 설계 (S3~S7, `[발전]`)

**단계**: 설계만 — 코드 수정·실행 없음. 사용자 승인 후 구현·실행합니다. baseline 제어
로직(`FSM`·`MPC`·속도 제어)은 이 작업으로 수정하지 않습니다.

**근거 문서**: `SPEC.md`(REQ-SIM-01~09, REQ-SEN-01~04, REQ-FSM-02b, REQ-MPC-04/05),
`SETTINGS_DECISION.md`(§7 front_gap, §8 충돌판정, §9 IR→ey_line, §12 기준점, 개정1/2),
`MEASURE_PLAN.md`(공통 원칙·P트랙 지표·Wilson CI), `RESULT_BASELINE.md` §4(seed=85 원인
분석에서 쓴 v=V_MAX 고정 관례).

---

## 1. 위치 결정

- **논문 정합 결과**(그대로 유지, 이 작업으로 건드리지 않음): `paper`(REQ-SIM 시나리오),
  `left_obstacle`(추가 검증, REQ-FSM-02b/SAFE_STOP 확인용). 두 시나리오의 P트랙 결과는
  `RESULT_BASELINE.md`에 이미 보고되어 있고, 이후 값을 갱신하지 않습니다.
- **신규 S3~S7**: `[발전] 강건성 검증`으로 완전히 분리합니다. 성공률·충돌률 등을 논문
  정합 결과와 **합산하지 않습니다** — 별도 시나리오 이름(`robustness_s3_grid` 등)과 별도
  결과 폴더(`thesis_v2/results/<타임스탬프>_<호스트>_baseline_R<번호>/`, R3~R7)로 관리하고,
  보고서에도 "강건성 검증(참고)" 절로 분리해 기술합니다.

---

## 2. 시나리오 정의

공통: 별도 언급 없는 한 seed는 `paper` P트랙과 동일한 0~99(100개)를 재사용합니다(같은
난수열 위에서 "옵션만 추가된 조건"을 비교하는 것이 목적이므로 새 seed를 만들지 않습니다).

### S3 — 경계 지도 (장애물 거리 × 초기 y0)

| 항목 | 값 |
|---|---|
| 파라미터 1 | 장애물 전단거리 `front_gap0` ∈ [0.5, 2.0]m (REQ-SIM-02 범위) |
| 파라미터 2 | 초기 `y0` ∈ [-0.15, 0.15]m (REQ-SIM-03 절단 Gaussian 지지 범위) |
| 고정값 | `v0 = V_MAX = 0.5`m/s(최소 반응시간 worst case — `RESULT_BASELINE.md` §4 seed=85
  원인분석에서 쓴 것과 같은 관례), `psi0 = 0`°(REQ-SIM-03 공백 기본값) |
| 격자 | `front_gap0` step 0.05m → 31점(0.50~2.00), `y0` step 0.01m → 31점(-0.15~0.15).
  총 **961 cell** |
| 샘플링 | **결정론적**(난수 없음) — 각 cell을 정확히 1회 실행 |
| seed/식별자 | 무작위 표본이 아니므로 "seed" 대신 cell index(`front_gap0`,`y0` 값 자체)로
  식별, 결과 로그·폴더명에 두 값을 그대로 기록 |

**가설(1줄)**: front_gap0·y0 조합에 따라 회피 성공/실패 경계가 어디에 형성되는지, 실패
영역이 존재한다면 전체 격자 대비 비율이 얼마인지 확인한다.

### S4 — 센서 노이즈

| 항목 | 값 |
|---|---|
| 대상 | `front_gap`(연속), `ey_line`(연속, 검출된 경우만), `left_clear`/`right_clear`(이산,
  오판정 확률) — **센서 모델 계층에만 주입**, FSM·MPC·속도제어 코드는 그대로 |
| 레벨(3단계, 세트로 묶음) | Low: gap σ=0.01m, ey σ=0.005m, flip p=0.01 / Medium: gap
  σ=0.03m, ey σ=0.01m, flip p=0.03 / High: gap σ=0.05m, ey σ=0.02m, flip p=0.05 |
| 시나리오 | `paper` 기반, seed 0~99(P트랙과 동일) |
| 노이즈 rng | world 생성용 rng와 **별도 스트림**(예: `default_rng((seed, profile_id))`)으로
  분리해 장애물·초기조건 샘플링과 섞이지 않게 함 |

**가설(1줄)**: 센서 노이즈 수준이 올라갈수록 충돌률·제약위반률이 증가하는지, 어느
수준부터 완료율이 유의미하게(신뢰구간 기준) 떨어지는지 확인한다.

### S5 — 제어 지연

| 항목 | 값 |
|---|---|
| 지연 | 1스텝(50ms), 2스텝(100ms) — 사용자 지정값 |
| 시나리오 | `paper`, seed 0~99 |
| 대상 | postprocess 이후 최종 조향 명령이 차량 모델에 반영되는 시점만 지연(액추에이터
  지연). 센서·FSM·MPC 계산 자체는 지연 없이 매 스텝 정상 수행 |

**가설(1줄)**: 제어 명령 지연이 늘어날수록 G_SAFE_MIN 안전마진이 실효적으로 줄어들어
충돌률이 증가하는지 확인한다.

**⚠ 구현 위치 이슈(§4에서 상술, 사용자 확인 필요)**: 이 시나리오는 `world.py`/`sensors.py`
범주에 들어가지 않습니다(시나리오·센서 속성이 아니라 제어 루프 타이밍 속성). `runner.py`에
옵션을 추가해야 합니다.

### S6 — 초기 헤딩 오차

| 항목 | 값 |
|---|---|
| 파라미터 | `psi0` ∈ {-15, -10, -5, 0, 5, 10, 15}°(step 5°, 7점) |
| 시나리오 | `paper` 생성 로직 그대로 + `psi0_deg`만 교체, seed 0~99 |

**가설(1줄)**: 초기 헤딩 오차가 커질수록 KEEP_L2 위치제약(REQ-MPC-05, \|y\|≤0.15) 안에서
조향 포화나 QP infeasible(fallback 발동)이 늘어나는지 확인한다.

**해석 주석(실행 결과, 2026-09-22, 정정)**: ψ0=-15° 그리드에서 seed=6(y0=-0.12766,
v0=0.3687) 1건, 16 step에 걸쳐 \|y\|≤0.15 위반이 관측됨. **최초 판정("초기조건 구조적
불가피")은 infeasible이 시작된 step 3 시점 상태만 보고 계산한 것이었고, step 0(진짜
초기조건)부터 다시 계산하면 결론이 바뀝니다 → 정정: (b) 제어기 설계 한계.**

step 0(y0=-0.12766, ψ0=-15°)부터 실제 제약(\|δ\|≤25°, rate limit 10°/step, δ_prev=0
시작, REQ-SPD-01 실제 v 스케줄)으로 이론상 최선(가능한 한 빨리 +25°로 램프업) 궤적을
시뮬레이션하면 최소 y=-0.14973m로 **위반 없음** — 즉 진짜 초기조건에서는 제약을 지키는
경로가 존재했습니다. 그런데 실제로는 step 1·2에서 MPC 자신이 이미 δ=+25°(포화)를
원했고 `solved`(ok=True)였지만(→ 이 시점 QP는 아직 feasible), `solve()`가
`delta_prev`/rate limit을 전혀 몰라 "다음 step에 즉시 25° 적용 가능"이라고 낙관적으로
재계획하는 사이 실제(rate-limited) 궤적이 그 계획보다 계속 뒤처져 step 3에서 QP
자신도 infeasible로 판정하게 됐고, 이후 fallback(K_p=1.0)이 이론상 최선(+25° 포화)보다
훨씬 약한(+7.9~9.5°) 교정만 내놓아 실제로는 -0.166m까지 밀렸습니다. 상세 근거:
`THESIS_REVISION_LOG.md` 2026-09-22(정정) REQ-MPC-04/REQ-SIM-03/REQ-MPC-07 항목,
`repro/2c_analysis/s6_psi15_step0_reverify.py`. **baseline `paper`(ψ0=0 고정)에는
영향 없음** — S6 성공률·충돌률 통계에는 그대로 반영하되(있는 그대로 보고 원칙) 이
해석을 별도로 명시한다. 개선 후보는 `IMPROVEMENT_BACKLOG.md` 후보8 참고.

### S7 — 장애물 크기·배치

**S7a(크기 변화)**:

| 항목 | 값 |
|---|---|
| 길이 스윕(폭 B=0.15 고정) | `L_obs` ∈ {0.10, 0.15, 0.20(baseline), 0.30, 0.40}m |
| 폭 스윕(길이 L=0.20 고정) | `B_obs` ∈ {0.075, 0.10, 0.15(baseline), 0.20, 0.30}m |
| 고유 설정 수 | 두 스윕이 baseline(0.20,0.15)을 공유 → **9개 고유 설정** |
| 시나리오 | `paper` 생성 로직 그대로 + 장애물 크기만 교체, seed 0~99 |

**S7b(전후 배치)**:

| 항목 | 값 |
|---|---|
| 전방 장애물 | `front_gap0 = 1.0`m 고정(REQ-SIM-02 범위 중앙값 근사) |
| 후방 장애물 | 같은 L2 차로(y_center=0), `rear_gap` ∈ {0.1, 0.3, 0.5, 1.0}m(차량 후단
  기준 뒤쪽 거리), 크기는 baseline과 동일(L×B) |
| 시나리오 | seed 0~99, 4개 `rear_gap` 값 |

**가설(1줄, S7a)**: 장애물이 커질수록(특히 폭 증가) 유효 안전마진이 줄어 충돌률이
증가하는지 확인한다.

**가설(1줄, S7b)**: 차량 후방에 있는 장애물이 front_gap 계산에 영향을 주지 않는지 확인한다
— **추정(근거: 코드 검토, `thesis_v2/baseline/sensors.py:30`)**: 현재 `front_gap()`은
`gap = max(0.0, obs.x_near - fx)`로 전후 방향을 구분하지 않으므로, 통로와 측면이 겹치는
후방 장애물이 있으면 front_gap이 실제로는 통과했는데도 0으로 계산될 가능성이 있습니다.
이는 실행 전 코드 판독만으로 세운 가설이며, S7b 실행 결과로 확인/반증합니다(확인되면
`THESIS_REVISION_LOG.md`/`IMPROVEMENT_BACKLOG.md`에 발견 사항으로만 추가하고, baseline은
이 단계에서 고치지 않습니다).

---

## 3. 판정 기준 (실행 전 확정, 이후 변경 금지)

공통 지표(모든 S3~S7, cell/조합별로 개별 집계 + Wilson 95% CI, 형식은
`MEASURE_PLAN.md`의 `k/n (95% CI a~b%)` 그대로 사용):

| 지표 | 정의 | 비고 |
|---|---|---|
| 충돌률 | outcome=="충돌" 비율 | REQ-SIM-08 판정 그대로 재사용(`collision.py` 수정 없음) |
| 완료율 | outcome=="성공" 비율 | `runner.py` 기존 분류 그대로 |
| 제약 만족률 | δ/ψ/y 각각 `metrics.py`의 허용오차(eps_abs) 기준 | P트랙과 동일 기준(§18) |
| 정지거리 | outcome=="SAFE_STOP"인 에피소드의 종료 시점 `front_gap` 값(평균·최소) | SAFE_STOP이
  발생한 조합에서만 의미 있음. 발생 0건이면 "해당없음(SAFE_STOP 미발생)"으로 표기 |

시나리오별 추가 지표/판정:

- **S3**: 위 4개 지표 외에 **격자 히트맵**(cell별 outcome)과 **실패 영역 비율**
  (`실패 cell 수 / 961`, 실패 = outcome != "성공")을 추가로 보고. 균일 격자를 면적의
  근사로 사용함을 명시(정확한 기하학적 면적이 아님).
- **S4~S7**: 위 4개 지표를 조건(노이즈 레벨/지연 스텝/헤딩/크기/배치)별로 표로 나열.

**합격선**: 모든 S3~S7에 대해 **"정보로 보고"**로 명시합니다 — SPEC.md·SETTINGS_DECISION.md
어디에도 이 강건성 조건들에 대한 최소 기준이 없으므로, 임의 합격선을 만들지 않고 지표와
신뢰구간만 보고합니다.

**전수 보고 원칙**: 모든 격자·모든 조건을 보고합니다(유리한 구간만 선택 금지) — S3의 961
cell 전부, S4~S7의 모든 레벨/조합 전부를 결과 문서에 포함합니다.

---

## 4. 구현 방식

### `world.py` 추가(기존 함수 로직 변경 없음)

- `generate_scenario(seed, psi0_deg: float = 0.0)` — **기존 시그니처에 기본값 있는 키워드
  인자만 추가**. 기존 호출부(`run.py`의 `SCENARIOS["paper"](seed)`, 테스트 코드)는 전부
  위치 인자 `seed` 하나만 넘기므로 동작이 바뀌지 않습니다(S6에서 `psi0_deg` 지정 시에만
  다른 결과). 내부 로직 한 줄도 수정하지 않습니다.
- `generate_grid_scenario(front_gap0, y0, v0=config.V_MAX, psi0_deg=0.0) -> Scenario`
  (신규 함수, name="robustness_s3_grid") — S3용 결정론적 생성.
- `generate_scenario_custom_obstacle(seed, obstacle_length=config.OBSTACLE_LENGTH,
  obstacle_width=config.OBSTACLE_WIDTH) -> Scenario` (신규 함수,
  name="robustness_s7a_size") — 기존 `generate_scenario`의 난수 샘플링 순서를 그대로
  따르되 장애물 크기만 인자로 받음.
- `generate_front_rear_scenario(seed, front_gap0, rear_gap) -> Scenario` (신규 함수,
  name="robustness_s7b_frontrear") — 전방 장애물 1개 + 후방 장애물 1개.

### `sensors.py` 추가(기존 함수 로직 변경 없음)

- `front_gap_noisy(state, obstacles, rng, sigma) -> float` — 기존 `front_gap()` 호출 결과에
  `N(0, sigma)`를 더하고 `[0, LIDAR_MAX_RANGE]`로 clip.
- `ey_line_noisy(pattern_or_value, rng, sigma) -> Optional[float]` — 검출된 경우(`None`이
  아닐 때)만 노이즈 추가.
- `left_clear_noisy(state, obstacles, rng, flip_p) -> bool` /
  `right_clear_noisy(...)` — 기존 함수 호출 후 확률 `flip_p`로 결과를 반전.
- 기존 `front_gap`/`left_clear`/`right_clear`/`ey_line`은 **한 글자도 수정하지 않음** —
  새 함수가 기존 함수를 호출해 감싸는 구조.

### `runner.py`(S5 전용, 예외 — 사용자 확인 필요)

S5(제어 지연)는 시나리오 속성도 센서 속성도 아닌 **제어 루프 타이밍** 속성이라
`world.py`/`sensors.py`에 넣을 자리가 없습니다. `run_episode(scenario, mpc=None,
control_delay_steps: int = 0)`로 옵션을 추가하는 것을 제안합니다:

- `control_delay_steps=0`(기본값)이면 지연 큐를 쓰지 않는 분기로 처리해 현재 코드와
  **완전히 동일한 경로**를 실행합니다(차량 모델에 방금 계산한 `pp.delta_final_deg`를
  그대로 전달).
- `control_delay_steps>=1`일 때만 FIFO 큐에서 N스텝 전 값을 꺼내 차량 모델에 전달하고,
  큐가 아직 안 찼으면 `delta_prev` 초기값(0.0)과 같은 원칙으로 0.0을 사용합니다.

이 위치는 "S3~S7은 `world.py`/`sensors.py`에 옵션 추가"라는 원 지침의 예외이므로, 이
설계를 승인할 때 함께 확인 부탁드립니다. 대안으로 `runner.py`를 건드리지 않고
`thesis_v2/tests/compare/`처럼 별도 실행 스크립트에서 `run_episode`를 감싸는 방법도
있으나, 그러려면 `run_episode` 내부의 `vehicle_step` 호출 지점에 접근해야 해서 결국
`run_episode` 자체를 수정하는 것과 동일한 결과입니다 — 별도 함수로 완전히 새로 복제하는
방법은 로직 이중관리 위험이 있어 권장하지 않습니다.

### 회귀 확인(바이트 단위 동일성 보장)

1. 옵션 추가 커밋에서 **기존 함수 내부는 수정하지 않고 새 함수/기본값 인자만 추가**하는
   구조를 유지합니다(위 설계가 이미 그렇게 되어 있음).
2. `python -m pytest thesis_v2/tests -q` 전체 통과를 먼저 확인합니다(기존 테스트 전부,
   회귀 없음 확인).
3. `thesis_v2/tests/golden/`의 `paper_seed{0,1,2}.json`·`left_obstacle_seed{0,1,2}.json`을
   옵션 추가 후 코드로 **재생성 없이 그대로 비교**합니다(`check_golden.py` 또는 동등 절차) —
   전이 목록·결과 분류·완료 step·조향각 시계열이 기존 값과 완전히 일치해야 통과입니다.
4. 3이 실패하면 옵션 추가 코드를 되돌리고 원인(기존 함수를 실수로 건드렸는지)을 규명한
   뒤 다시 시도합니다 — golden 불일치 상태로 S3~S7 실행을 진행하지 않습니다.

---

## 5. 실행 규모·예상 시간 (참고, 실행은 사용자)

| 시나리오 | 조합 수 | 조합당 반복 | 총 실행(episode) 수 |
|---|---|---|---|
| S3 | 961 cell | 1(결정론적) | 961 |
| S4 | 3 프로파일 | 100 seed | 300 |
| S5 | 2 지연 레벨 | 100 seed | 200 |
| S6 | 7 헤딩 | 100 seed | 700 |
| S7a | 9 고유 설정 | 100 seed | 900 |
| S7b | 4 rear_gap | 100 seed | 400 |
| **합계** | | | **3,461** |

**예상 시간**: 정확한 episode당 실행 시간은 아직 실측하지 않았습니다. 참고로 실측된
MPC solve 평균시간은 0.11ms(`RESULT_BASELINE.md` §5b)로 매우 작아, episode당 총 소요는
파이썬 루프 오버헤드가 지배적일 것으로 보입니다. 대략 episode당 20~200ms로 가정하면
전체 3,461회는 **약 70초~12분** 범위입니다. 2단계-B 관례와 동일하게, 승인 후 **먼저
10~20개 소규모 실행으로 실제 episode당 시간을 재고 정확한 예상 시간을 다시 안내한 뒤**
전체 실행 여부를 확인받겠습니다.

결과 폴더: `thesis_v2/results/<타임스탬프>_<호스트>_baseline_R3/` ~ `_R7/`
(S7은 `_R7/` 아래 `s7a_*`/`s7b_*` 파일 접두사로 구분).
