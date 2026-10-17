# baseline 설계 (2단계-B-1)

코드는 아직 작성하지 않았습니다. 이 문서 승인 후 2단계-B-2에서 구현합니다. 기준 문서:
`SPEC.md`, `SETTINGS_DECISION.md`, `MEASURE_PLAN.md`, `FEASIBILITY_CHECK.md`, `repro/docs/WORK_RULES.md`.

---

## 1. 모듈 구조 (`thesis_v2/baseline/`)

| 파일 | 역할 | 담당 REQ | 주요 인터페이스 |
|---|---|---|---|
| `config.py` | 고정 파라미터 + 결정표 값 정의, 시작 시 assert | REQ-VEH-02, REQ-MPC-03, REQ-FSM-03, 전체 §값 | 모듈 상수만(함수 없음). `assert_fixed_params()`가 import 시 자동 실행 |
| `vehicle.py` | kinematic bicycle, Euler 적분, 후륜 중심 | REQ-VEH-01,04,05, REQ-MPC-07b(부호) | `class VehicleState(x:float m, y:float m, psi:float rad, v:float m/s)`. `step(state, delta_deg:float, v_cmd:float m/s, dt:float) -> VehicleState`. +y=좌측, +psi=좌회전, +delta_deg=좌회전 |
| `world.py` | 도로·장애물·시나리오 생성 | REQ-SIM-01,02,02a,03, §개정2 | `class Obstacle(x_near:float, x_far:float, y_range:Tuple[float,float])`. `class Scenario(front_gap0, obstacle, v0, y0, psi0=0.0)`. `generate_scenario(rng: np.random.Generator) -> Scenario`, `generate_left_obstacle_scenario(rng) -> Scenario`(추가 검증용, §9/left_clear 테스트) |
| `sensors.py` | LiDAR·IR 센서 모사 | REQ-SEN-01–04, §7,9,14 | `front_gap(state, obstacle) -> float`(m). `left_clear(state, obstacles) -> bool`. `right_clear(state, obstacles) -> bool`. `ir_pattern(state, active_line_y) -> Tuple[int,int,int]`. `ey_line(pattern) -> Optional[float]`(m, None=미검출) |
| `fsm.py` | 5상태, 전이표, 쿨다운 | REQ-FSM-01–04, §1,2,13,14 | `class FSMState(Enum)`. `class FSM(state, target_lane, last_change_t, entered_t)`. `step(fsm, sensors, t) -> FSM`(새 FSM 반환, 순수함수) |
| `mpc.py` | OSQP 2-state MPC + fallback | REQ-MPC-01–08, §2,11 | `class OSQPMPC` — `__init__(config)`(P,A 구조 1회 생성), `solve(y0, psi0, v0, target_y, state_name) -> MPCResult(delta_deg, solver_status:str, ok:bool, fallback_used:bool, compute_time_ms:float)` |
| `lateral.py` | 상태별 라인추종/MPC 선택 | REQ-LAT-01–04, §4,5 | `compute_lateral(fsm_state, ey_line, y, psi, v, mpc) -> LateralResult(delta_desired_deg, mode:str, mpc_result:Optional[MPCResult])` |
| `longitudinal.py` | 상태별 v_ref | REQ-SPD-01–05 | `compute_v_cmd(fsm_state) -> float`(m/s) |
| `postprocess.py` | rate limit + clip | REQ-VEH-03, REQ-MPC-04a | `apply_rate_limit(delta_desired, delta_prev, dt) -> float`(PDF 식 그대로: `clip(desired, prev-Δmax, prev+Δmax)`) |
| `collision.py` | 회전 사각형 SAT | REQ-SIM-08, §8 | `check_collision(vehicle_state, obstacle) -> bool` |
| `runner.py` | 에피소드 루프 | REQ-SIM-04,05, §6, repro/docs/WORK_RULES.md 스텝순서 | `run_episode(scenario, seed, config) -> EpisodeResult` |
| `logger.py` | 스텝별 기록 | 기록 스키마(§3) | `class StepLogger` — `log(step_data: dict)`, `save(path)` → `steps.npz` |
| `run.py` | CLI 진입점 | - | `python -m thesis_v2.baseline.run --track P --seeds 1,2,3 --out thesis_v2/results/...` |

**의존관계**: `runner.py`가 나머지 전부를 오케스트레이션. `sensors.py`/`fsm.py`/`mpc.py`/
`lateral.py`/`longitudinal.py`/`postprocess.py`/`collision.py`/`vehicle.py`는 서로를 몰라도
되게(순수 함수 위주) 설계 — 단위 테스트를 독립적으로 짜기 위함.

---

## 2. 스텝 실행 순서

**요청하신 순서 그대로 채택**: 센서 → FSM → 횡·종방향 제어 → 후처리 → 차량 갱신 → 충돌 판정 → 종료 판정.

```
# runner.py: run_episode() 내부, 매 스텝(step=1..max_steps)
# 상태: vehicle(x,y,psi,v), fsm(state,target_lane,last_change_t), delta_prev

1. 센서 계산 (REQ-SEN-01~04)                         # 이번 스텝 "관측" — vehicle의 이전 스텝 결과 위치 기준
   front_gap = sensors.front_gap(vehicle, obstacle)
   left_clear = sensors.left_clear(vehicle, [obstacle])
   right_clear = sensors.right_clear(vehicle, [obstacle])
   ir = sensors.ir_pattern(vehicle, active_line_y=fsm.target_line_y())
   ey = sensors.ey_line(ir)

2. FSM 갱신 (REQ-FSM-01~04)                          # 센서값만 입력(repro/docs/WORK_RULES.md 원칙)
   fsm_new = fsm.step(fsm, Sensors(front_gap,left_clear,right_clear), t=step*dt)
   # 내부에서: 모든 상태에 대해 SAFE_STOP 조건 우선 체크(REQ-FSM-02b) →
   #           그 다음 현재 상태별 전이 조건 체크(02a/02c/02d/02e) → 쿨다운(§13) 게이트

3. 횡방향 제어 (REQ-LAT-01~04)
   lat = lateral.compute_lateral(fsm_new.state, ey, vehicle.y, vehicle.psi, vehicle.v, mpc)
   delta_desired = lat.delta_desired_deg

4. 종방향 제어 (REQ-SPD-01~05)
   v_cmd = longitudinal.compute_v_cmd(fsm_new.state)

5. 후처리 (REQ-VEH-03, REQ-MPC-04a)
   delta_final = postprocess.apply_rate_limit(delta_desired, delta_prev, dt)
   delta_prev = delta_final

6. 차량 갱신 (REQ-VEH-01,04,05)
   vehicle_new = vehicle.step(vehicle, delta_final, v_cmd, dt)

7. 충돌 판정 (REQ-SIM-08)                            # 차량 갱신 직후, 이번 스텝의 "결과"에 대해
   collided_this_step = collision.check_collision(vehicle_new, obstacle)
   if collided_this_step: episode_outcome = "충돌"; break   # 최우선 종료 사유(§6)

8. 종료 판정 (REQ-SIM-04,05, §6)
   if fsm_new.state == SAFE_STOP: episode_outcome="SAFE_STOP"; break
   elif fsm_new.state==KEEP_L2 and visited_evade and not just_re_entered_before:
       완료 트리거 → 20 step 관찰 서브루프 실행 → "성공" or "미정착"; break
   elif step >= 200: episode_outcome="타임아웃"; break
   else: vehicle, fsm = vehicle_new, fsm_new; continue  # 다음 스텝으로

# 매 스텝 logger.log(...)로 §3 스키마 기록 (충돌/종료 여부와 무관하게 이번 스텝은 항상 기록)
```

**충돌 우선순위 보장**: 7번(충돌)이 8번(SAFE_STOP/완료/타임아웃) 판정보다 먼저 오므로, 같은
스텝에 "충돌"과 "FSM상 완료/SAFE_STOP"이 동시에 성립해도 **항상 충돌로 분류**됩니다(테스트
항목: "runner 순서" 참고).

**FSM-vs-충돌 시점 관계(repro/docs/WORK_RULES.md 59행)**: 위 순서상 한 반복(iteration) 안에서는 FSM(2번)이
차량 갱신(6번)·충돌 판정(7번)보다 먼저 실행됩니다 — 이건 "이번 스텝에 어떤 제어를 할지"
결정하는 것이라 물리 갱신보다 먼저일 수밖에 없습니다. repro/docs/WORK_RULES.md의 "충돌 판정이 FSM 갱신보다
먼저"는 **다음 반복과의 관계**를 말합니다: 스텝 k의 충돌 판정(7번)은 스텝 k+1의 FSM 갱신(2번)
**이전에** 이미 끝나 있습니다(반복문 구조상 자동 성립) — 즉 "충돌이 나면 다음 스텝의 FSM
판단을 하기 전에 먼저 멈춘다"는 뜻이며, 같은 스텝 안에서 FSM보다 먼저 충돌을 본다는 뜻이
아닙니다. 이 해석을 설계에 명시해 혼동을 막습니다.

---

## 3. 기록 스키마

### `steps.npz` (스텝별, 매 스텝 1행)

| 필드 | 타입 | 단위/비고 |
|---|---|---|
| t | float | s |
| x, y, psi, v | float | m, m, rad, m/s (psi는 저장은 rad, 로그 출력시 deg 병기) |
| delta_mpc_raw | float | deg, MPC/라인추종이 낸 1차 출력(후처리 전) |
| delta_after_rate | float | deg, rate limit 적용 후(= delta_final, 현 설계는 rate limit이 유일한 후처리라 동일값) |
| delta_final | float | deg, 차량에 실제 인가된 값 |
| v_cmd | float | m/s |
| state | str | FSM 상태명 |
| front_gap, left_clear, right_clear | float/bool | m, bool, bool |
| ir_pattern | str | "010" 등 3자리 |
| ey_line | float or None | m |
| solver_status | str | OSQP status 문자열, 라인추종 스텝은 "N/A" |
| fallback_used | bool | |
| t_mpc_solve_ms | float | §4 참고, MPC 미사용 스텝은 0.0 |
| t_step_ms | float | §4 참고 |

### `episodes.json` (에피소드 요약)

`seed, front_gap0, obstacle_xy, v0, y0, psi0, outcome(성공/충돌/SAFE_STOP/타임아웃/미정착/조기복귀),
finish_step, state_durations(dict), transitions(list of {step,t,from,to})`.

### `summary.json`

`MEASURE_PLAN.md`의 P/C/M 트랙 지표 전부(제약 만족률, 충돌률, SAFE_STOP 횟수, FSM 상태별
체류·오차, MPC 계산시간 통계, 종방향 정합성 등) — 트랙별로 섹션 구분.

### `env.json`

`{"os": platform.platform(), "python": sys.version, "numpy": ..., "scipy": ..., "osqp": ...,
"cpu": platform.processor(), "timestamp": ...}` — `MEASURE_PLAN.md`의 "절대값은 하드웨어
종속" 원칙 지원용.

---

## 4. 계산시간 측정 범위

- **`t_mpc_solve_ms`**: `OSQPMPC.solve()` 함수 진입–반환까지만(순수 QP 빌드+solve, 논문 Table 8과
  같은 정의로 맞춤 — REQ-EVAL-03). `time.perf_counter()`를 `mpc.py`의 `solve()` 내부 시작/끝에 배치.
- **`t_step_ms`**: `runner.py`의 스텝 루프 1–8번 전체(센서–종료판정)를 감싸는 시간. 20Hz
  예산(50ms) 대비 주장 검증용(REQ-EVAL-03 "주장 수준" 판정).
- 라인추종만 쓰는 스텝은 `t_mpc_solve_ms=0.0`(MPC 자체를 호출 안 함, REQ-LAT-01).

---

## 5. 테스트 계획 (`thesis_v2/tests/`)

| 테스트 | 대상 REQ | 개수 |
|---|---|---|
| config assert(고정파라미터 12개 값 일치) | REQ-VEH-02, REQ-MPC-03 등 | 1 |
| MPC Hessian 구조(rΔδ가 비대각에 있는지 대수적으로 확인, δ_i²가 아니라 (δ_i-δ_{i-1})² 항인지) | REQ-MPC-02,03a | 1 |
| MPC 상태별 위치제약 행(KEEP_L2/KEEP_L1/EVADE_L/RETURN_TO_L2 4가지 bound 벡터 확인) | REQ-MPC-04,05 | 4 |
| MPC 헤딩·조향 제약 상수 확인 | REQ-MPC-04 | 1 |
| 부호 규약(양의 δ→양의 ψ̇→양의 ẏ 한 스텝으로 확인) | REQ-MPC-07b | 1 |
| Fallback 단위(K_p rad/m 변환 확인, 알려진 입력→출력 수치 비교) | REQ-MPC-07,07a | 1 |
| FSM 전이 5개(각 조건 참/거짓 양쪽 케이스) | REQ-FSM-02a–02e | 10(전이당 참/거짓 2개) |
| 쿨다운(전이 직후 0.3s 내 재전이 차단, 5개 전이 전부 + 초기값이 첫 전이를 막지 않음) | REQ-FSM-03,03a,03b | 6 |
| SAFE_STOP(모든 상태에서 진입 가능 — EVADE_L 포함 5개 상태 전부) | REQ-FSM-02b | 5 |
| IR 변환표 6패턴(100/110/010/011/001/000 → 지정된 ey_line) | REQ-SEN-03 | 6 |
| front_gap 통로 겹침(통로 안/밖 장애물 2케이스 + 지나친 뒤 큰 값) | REQ-SEN-01 | 3 |
| left_clear/right_clear 윈도우(장애물 없음→True, 윈도우 안 장애물→False, 좌측차로 장애물 시나리오로 실제 False 확인) | REQ-SEN-02,04 | 4 |
| SAT 충돌(축정렬 겹침/비겹침, 회전 상태 겹침, 모서리만 스침) | REQ-SIM-08 | 4 |
| runner 순서(같은 스텝에 충돌+완료 동시성립 시 충돌 우선 기록) | 스텝순서 | 1 |
| seed 재현성(같은 seed 2회 실행 결과 동일) | MEASURE_PLAN §P트랙 | 1 |
| **합계** | | **49** |

**추적표**: `thesis_v2/tests/TRACEABILITY.md`에 `REQ ID | 코드 위치(파일:함수) | 테스트 이름`
표를 만들어 구현과 함께 채웁니다(지금은 빈 틀만 제안, 실제 채우기는 B-2).

---

## 6. C트랙 비교 설계 (`tests/compare/`)

**입력 집합**: (y, ψ, v, target_y, FSM상태) 조합을 격자로 생성 —
y∈{-0.15,-0.05,0,0.05,0.15,0.22,0.30,0.38,0.45}, ψ∈{-30,-10,0,10,30}deg, v∈{0.3,0.4,0.5},
target_y∈{0,0.30}, state∈{KEEP_L2,EVADE_L,KEEP_L1,RETURN_TO_L2} → 9×5×3×2×4=1080 조합(단
물리적으로 상태-y 조합이 안 맞는 것은 필터링, 예: KEEP_L2인데 y=0.45는 실제로 안 나오는
조합이라 참고용으로만 계산).

**SPEC_VS_OLDCODE.md 기대 차이 대응표**:

| 기대 차이(SPEC_VS_OLDCODE.md) | 비교 테스트 |
|---|---|
| rΔδ 크기벌점(구코드) vs 차분벌점(baseline) | 동일 (y,ψ,v,target) 반복입력에서 δ 시퀀스(N=15) 궤적 비교, 진동/부드러움 지표(2차 변화율) 비교 |
| 위치제약 단일상수(구코드 ±0.45) vs 상태별(baseline) | 같은 상태에서 y가 구코드 제약은 통과하지만 baseline 제약(더 좁음)은 위반하는 경계 케이스 탐색 |
| fallback 게인 −qy(구코드) vs K_p=1.0 rad/m(baseline) | OSQP를 강제 실패시키는 입력(예: 도달불가 제약 조합)에서 두 fallback δ 비교, 배율 확인 |
| FSM: EVADE_L SAFE_STOP 예외(구코드 루트) 유무 | 동일 (front_gap<0.20, left_clear=False, state=EVADE_L) 입력을 양쪽 FSM에 넣어 다음 상태 비교 |
| FSM: RETURN_TO_L2→KEEP_L2 임계값 0.08(baseline) vs 0.08(구코드, NEAR_BAND_L1 재사용 우연히 같음) | 값 자체는 같아 차이 없음 예상 — 대신 **헤딩 조건 유무**(baseline만 |ψ|≤20° 검사)로 차이 확인 |
| 쿨다운 미구현(구코드 code_backup) vs 구현(baseline) | 연속 전이 조건을 인위적으로 만들어(예: front_gap이 급변) 0.3s 내 재전이 여부 비교 |

각 비교는 "명세 차이로 설명됨" / "설명 안 됨(버그 후보)"로 라벨링해 `tests/compare/report.md`에
기록(코드는 B-2에서).

---

## 7. 의존성 (`requirements.txt` 초안)

당시(2단계-A 작성 시점) PC 확인값: Python 3.12.9, numpy 2.5.1, scipy 1.18.0, osqp 1.1.3,
Windows 11(SSAFY PC). **[환경 결정 변경, 2026-09-17] 공식 측정 환경은 이후 노트북(Core
Ultra 9 185H, `.venv` Python 3.9.12, numpy 2.0.2, scipy 1.13.1, osqp 1.1.1)으로 변경됨** —
근거·최신 상태는 `MEASURE_PLAN.md` 공통 원칙을 참고(SSAFY PC 값은 참고용 기록으로만 남김,
`thesis_v2/requirements-py312.txt`에 별도 보관).

```
numpy>=2.0,<3.0
scipy>=1.10,<2.0
osqp>=1.0,<2.0
torch  # M트랙(2단계-D)에서만 필요, baseline P/C트랙 자체는 불필요 — 별도 optional로 분리 검토
```

**주의**: 정확한 버전 고정(`==`)은 하지 않습니다 — 사용자 실행 PC의 기존 환경과 충돌 가능성을
줄이기 위해 범위만 지정하고, 실제 실행 시 `env.json`에 실사용 버전을 기록해 재현성을
확보합니다. 환경별 정확한 고정 버전은 `thesis_v2/requirements-py39.txt`(노트북, 공식)·
`thesis_v2/requirements-py312.txt`(SSAFY PC, 참고)에 각각 기록되어 있습니다.

---

## 8. 미결 지점 (구현 중 막힐 것으로 예상되는 부분)

1. **OSQP 워밍스타트 구조**: Hessian(P)과 제약행렬(A)의 sparsity 패턴을 상태 전체(4가지
   위치제약)에 대해 고정할지, 상태가 바뀔 때마다 새 `OSQP()` 인스턴스를 만들지 결정 필요.
   전자가 "warm-start"(REQ-MPC-06)에 더 부합하지만, `l,u` 갱신만으로 상태전환 시 제약을
   바꾸는 게 OSQP API상 자연스러운지 구현하면서 확인 필요 — 문제가 있으면 [원인→수정안→REQ]로
   보고하겠습니다.
2. **IR 센서의 "활성 라인" 결정 로직**: `ir_pattern()`이 L2 중심(y=0)과 L1 중심(y=0.30) 중
   어느 라인을 감지 대상으로 볼지 — 두 후보 모두 계산해 감지범위(약 ±0.08m) 안에 들어오는
   쪽을 채택하는 방식으로 설계했으나(1절), 차선 변경 중간 지점(y≈0.15)처럼 **두 라인 다
   감지범위 밖인 경우**가 실제로 자주 생길 수 있어(→ 000, 미검출 → REQ-LAT에서 MPC로 폴백)
   이게 의도된 동작인지(그렇다고 생각합니다만) 확인 후 진행하겠습니다.
3. **완료 후 20 step 관찰 중 에피소드 최대 길이 초과 가능성**: `runner.py`가 완료를 200 step
   근처(예: 195 step)에서 트리거하면 관찰 20 step이 200을 넘습니다. `MEASURE_PLAN.md`/§6엔
   이 경우를 어떻게 셀지 명시가 없어 — **관찰 20 step은 200 step 예산과 별개로 항상 수행**
   (타임아웃 판정과 무관한 사후 진단)으로 두겠습니다만, 확인 부탁드립니다.
4. **C트랙 격자 크기(1080 조합)의 실행 시간**: 소규모는 아니라 2단계-B에서는 코드만 만들고
   전체 실행은 안 합니다(6절 설계까지만, 실제 비교 실행은 별도 승인 후).

이 문서에 이견 없으면 2단계-B-2(구현)로 진행하겠습니다.

---

## B-1 승인 후 확정 사항 (미결 지점 답변 + 추가사항)

**1. OSQP**: 인스턴스 1개, P·A **희소 구조**(sparsity pattern)는 고정. 매 스텝
`prob.update(q=..., l=..., u=..., Ax=...)`로 갱신 — q,l,u뿐 아니라 **A의 v-의존 수치도
`Ax`로 함께 갱신**합니다(동역학 등식 행의 계수 `v·dt`, `(v/L)·dt`가 v_now에 따라 바뀌므로).
sparsity 자체(어느 자리가 0이 아닌지)는 절대 안 바뀝니다. 상태별 위치제약 차이는 y bound
행의 l,u 값으로만 표현. 구조 변경이 필요해지면 멈추고 보고합니다.

**2. 횡방향 제어 선택 확정**: KEEP_L2·KEEP_L1은 라인 감지 시 라인추종, 미감지 시 MPC.
EVADE_L·RETURN_TO_L2는 **IR 감지 여부와 무관하게 항상 MPC**(REQ-LAT-02, PDF p.10 "MPC가
최적 경로를 계획한다" — 원문 확인 완료, SPEC과 일치). MPC 사용은 폴백이 아니라 설계상
동작이므로 `fallback_used`는 **OSQP 자체가 실패했을 때만** True로 기록합니다.
**KEEP 상태에서 IR이 감지한 라인이 목표 차로 라인이 아닌 경우**: `sensors.ir_pattern()`은
두 후보 라인(L2 중심 0, L1 중심 W) 중 **감지범위 안에 들어온 쪽**만 패턴을 만들므로,
차선 경계 부근에서 "엉뚱한 라인"이 감지될 수는 있습니다(예: KEEP_L2인데 y가 커져 L1 중심에
더 가까워짐). 이 경우 **감지된 라인이 어느 쪽이든 그대로 라인추종에 사용**합니다(REQ-LAT-01
공식 자체가 "목표=0으로 수렴"이 아니라 "감지된 라인을 따라간다"는 순수 반응형 제어라서,
어떤 라인이 감지됐는지 판별할 필요가 없습니다 — 물리 IR 센서도 "지금 밑에 있는 선"만 알지
그게 L2인지 L1인지 모릅니다). 이 처리가 SPEC과 다르면 즉시 중단하고 보고합니다만, REQ-LAT-01
원문(p.10 식 8, δ=−K_ey·ey_line)이 라인 종류를 구분하지 않으므로 SPEC과 일치한다고 판단합니다.

**3. 종료**: timeout=200 step까지 완료 미달성. 완료 후 20 step 관찰은 200 step 예산과
무관하게 **항상 수행**하고 별도 필드(`observed_settle_violation`)로 episodes.json에 기록.

**4. C트랙**: B-2에서는 코드 + 10조합 소규모 확인만 실행. 전체 1080격자는 별도 승인 후.

**5. postprocess.py 순서 확정**: rate limit(REQ-VEH-03) → clip(±25°, REQ-VEH-02 Table1) 순.
PDF는 이 순서를 명시하지 않아 **[공백]으로 `SETTINGS_DECISION.md` §15에 기록**(아래).
스텝 기록에 `rate_limit_active`(bool, rate limit이 실제로 값을 깎았는지), `clip_active`(bool,
±25° clip이 실제로 발동했는지) 추가.

**6. 테스트 추가**(§5 표에 반영, 총 49→60개):

| 테스트 | 대상 REQ | 개수 |
|---|---|---|
| 후처리: rate limit 경계(딱 10°/step, 그 이상) | REQ-VEH-03 | 2 |
| 후처리: clip 경계(딱 25°, 그 이상) | REQ-VEH-02 | 2 |
| 후처리: 순서(rate limit 결과가 25° 넘으면 clip이 한 번 더 깎는 케이스) | §15 | 1 |
| 횡방향 선택: 상태(5)×IR감지여부(2) 조합 | REQ-LAT-01–04 | 10 − (SAFE_STOP은 제어 자체가 없어 제외 4상태×2=8) → **8** |
| 종방향: 상태별 v_cmd(5상태) | REQ-SPD-01,02 | 5 |
| 로거: steps.npz 스키마 필드 전부 존재 확인 | §3 | 1 |
| **추가 합계** | | **19** |
| **전체 합계(기존49+신규19)** | | **68** |

### §15(신규, SETTINGS_DECISION.md 반영) — 후처리 순서 [공백]

PDF는 "조향각 Rate Limiting"(p.8-9)과 "최대 조향각 ±25°"(Table1, p.6-7)을 각각 서술하지만
**둘을 적용하는 순서**는 명시하지 않습니다.

- **옵션 A(추천, 채택)**: rate limit 먼저(`clip(desired, prev-Δmax, prev+Δmax)`, REQ-VEH-03
  식 그대로) → 그 결과를 ±25°로 clip. 근거: REQ-VEH-03의 식 자체가 이미 "이전 스텝 기준
  변화량"만 다루므로 델타 자체의 최종 하드리밋(±25°)은 그 이후에 한 번 더 확인하는 게
  자연스럽습니다(REQ-MPC-04에서도 δ 자체 제약이 별도 항목으로 있음).
- 옵션 B: clip 먼저 → rate limit — 이 경우 δ_prev 자체가 항상 ±25° 안이므로 결과는 거의
  동일하나(둘 다 첫 스텝부터 δ_prev가 ±25° 안에서 시작), 옵션 A가 PDF의 서술 순서(Rate
  Limiting 문단이 먼저 나옴, p.8-9)와 더 가깝습니다.

**추천: 옵션 A.**
