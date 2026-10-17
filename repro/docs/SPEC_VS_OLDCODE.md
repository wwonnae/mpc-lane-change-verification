# SPEC.md vs 기존 코드(A, code_backup 12-04) 대조

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

원본은 전혀 수정하지 않았습니다. "A"는 1단계에서 확인된 "실험 당시 코드"
(`legacy_2025/final_hierarchical_backup_thesis_1204.py`, 97,747B, 2025-12-04 04:17 스냅샷과 `.pyc` 서명
일치, `THESIS_TIME_CODE.md` 7·8절) 및 `legacy_2025/code_backup/simulator.py`(P트랙형 환경)입니다. 목적은
baseline(`thesis_v2/baseline/`, 아직 미구현)이 기존 코드를 복사하지 않도록, 어디가 이미
맞고 어디가 다른지 미리 표로 남기는 것입니다. C트랙(`MEASURE_PLAN.md`)에서 실행 검증할
"예상된 차이"의 근거 자료이기도 합니다.

범례: **일치**(코드가 REQ와 같음) / **불일치**(다름, 근거·행 인용) / **코드에만 있음**(REQ에
없는 기능이 코드에 추가로 있음) / **구조만 있음**(코드에 로직은 있으나 특정 실행 경로에서
죽은 코드로 확인됨) / **미확인**(시간상 확인 못 함, 2단계-B에서 필요시 확인).

---

## REQ-VEH

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-VEH-01 (kinematic model) | 일치 | `final_hierarchical_backup.py:656-659`(Pose 클래스 `update()`): `x+=v·cos(ψ)·dt; y+=v·sin(ψ)·dt; ψ+=(v/L)·tan(δ)·dt` — 식(1)~(3)과 동일 |
| REQ-VEH-02 (Table1 파라미터) | 일치 | argparse 기본값: `--delta_max 25.0`, `--v_max 0.5`, `--delta_rate 200.0`, `L=0.20/B=0.15`(`VehicleParams` 기본값, 90-96행 부근) |
| REQ-VEH-03 (Δδ_max=10°/step 후처리) | 일치 | `978-979행`: `max_rate_per_step = DELTA_RATE_MAX_DEGPS*dt; self.rate=RateLimit(...)` — `RateLimit.step()`(635-644행)이 클리핑 수행 |
| REQ-VEH-04 (Euler 적분) | 일치 | 위 Pose.update()가 직접 오일러 스텝 |
| REQ-VEH-05 (속도 동역학 없음) | 일치 | `v_cmd`가 매 상태 분기에서 `v_ref` 또는 `0.0`으로 직접 대입(가속도 적분 없음), 아래 REQ-SPD 참고 |

## REQ-FSM

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-FSM-01 (5상태) | 일치 | `class State(Enum)` KEEP_L2/EVADE_L/KEEP_L1/RETURN_TO_L2/SAFE_STOP |
| REQ-FSM-02a (KEEP_L2→EVADE_L) | 일치 | `1819-1826행`: `front_gap<G_TRIG and left_clear → EVADE_L` |
| REQ-FSM-02b (모든상태→SAFE_STOP, 예외없음) | 일치 | `1807-1809행`: 상태 분기 밖에서 무조건 체크(EVADE_L 예외는 **루트에만** 있음, A엔 없음) |
| REQ-FSM-02c (EVADE_L→KEEP_L1, \|y−0.3\|≤0.08) | **구조만 있음**(실질 일치) | `1830-1839행`: `ey_line` 기반 분기(\|ey_line\|<0.04, PDF에 없음)와 `pose.y` 기반 분기(PDF와 일치) 두 개가 있음. `legacy_2025/run_simulation.py`가 주입하는 `line_ey`는 `LineTraceSensor`에 실제로 닿지 않는 죽은 대입이라(`STAGE1_FACTS.md` 항목5) `ey_line`은 **항상 `None`** → 항상 pose 분기만 실행 → **실질적으로 PDF와 일치**. 단, 코드 자체는 PDF에 없는 분기를 여분으로 갖고 있음 |
| REQ-FSM-02d (KEEP_L1→RETURN, t>0.6s) | 일치 | `1842-1844행` |
| REQ-FSM-02e (RETURN→KEEP_L2, \|y\|≤0.20 AND \|ψ\|≤20°) | **불일치** | `1852-1861행`: 임계값 0.08(NEAR_BAND_L1 재사용), 헤딩각(ψ) 조건 전체 부재(`grep "psi.*20"` 0건) |
| REQ-FSM-03/03a (쿨다운 전체 적용) | **불일치**(전면 미구현) | A는 `COOLDOWN` 상수만 정의(`BehaviorParams`)하고 어떤 조건문에도 쓰지 않음(`cooldown_ok` 문자열 A에 0건 — 루트에만 3곳 존재) |
| REQ-FSM-04 (SAFE_STOP 복귀, spec=없음) | **코드에만 있음** | `2005-2019행`: `recovery_gap=G_SAFE_MIN*3.0` 히스테리시스로 SAFE_STOP→KEEP_L1/L2/EVADE_L 복귀 로직 존재(PDF엔 없음, baseline은 채택 안 함) |

## REQ-MPC

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-MPC-01 (이산 y,ψ 모델) | 일치 | `908-909행`: `gain_y=v·dt`, `gain_psi=(v/L)·dt`로 동역학 등식 구성 |
| REQ-MPC-02/03a (rΔδ=차분 항, 비대각 필요) | **불일치** | `874-881행`: `P_diag`가 **대각행렬만** 구성 — `rdelta`는 u_0에, `rddelta`는 **u_1..u_{n-1} 각각의 크기(u_i²)에 개별** 적용됨. 논문 식(6)의 `(δ_i−δ_{i-1})²`(차분 항, 비대각 필요)과 다름 — **크기 벌점이지 차분 벌점이 아님** |
| REQ-MPC-03 (가중치 값 qy=100 등) | 일치 | 생성자 인자로 그대로 전달(`1615행` 부근 주석 "qpsi=25.0 Increased from 20.0"도 논문 값 25로 수렴한 이력을 보여줌) |
| REQ-MPC-04 (δ,ψ 제약) | 일치 | `889-893행`(δ), `871행`(`psi_limit=radians(80)`) |
| REQ-MPC-04 (y 3단계 위치제약) | **불일치** | `887-888행`: `lb/ub[y_i] = ∓self.y_limit`, `y_limit=self.rp.MAX_Y_DEVIATION` — **상태 무관 단일 상수**(기본 0.45), L2/L1/차선변경구간 3단계 없음 |
| REQ-MPC-04a (Δδ 제약=후처리) | 일치 | OSQPMPC의 `lb/ub`엔 δ_i−δ_{i-1} 제약이 전혀 없음(위 887-893행에 y,δ 크기만 있음) → REQ-VEH-03의 `RateLimit`(후처리)로만 처리, PDF의 "QP 밖 후처리" 구조와 일치 |
| REQ-MPC-05 (상태별 제약 매핑) | 해당없음 | 위 항목대로 A엔애초에 상태별 제약 자체가 없어 "매핑"이라는 개념이 성립 안 함 |
| REQ-MPC-06 (QP/OSQP/warm-start) | 부분 확인 | OSQP solver 사용은 확인(`import osqp`, `class OSQPMPC`). warm-start 명시적 재사용 여부는 **미확인**(시간상 생략) |
| REQ-MPC-07 (fallback Kp=1.0) | **불일치** | `959-961행`: `delta_fallback = clip(-self.qy·(y0−target_y)·RAD2DEG, ...)` — 게인이 `K_p=1.0`이 아니라 **`-qy`(=100)** |
| REQ-MPC-08 (MPC가 v 결정 안 함) | 일치 | `solve()` 반환값은 `(delta_deg, ok)`뿐, v는 항상 별도로 `v_ref` 대입 |

## REQ-SPD

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-SPD-01 (v_ref=0.5, 비-SAFE 상태 유지) | 일치 | `1866행`: `v_ref=self.vp.V_MAX`, 각 상태 분기에서 `v_cmd=v_ref` |
| REQ-SPD-02 (SAFE_STOP v=0) | 일치 | `2001행`: `v_cmd=0.0` |
| REQ-SPD-03 (즉시 0, 램프 없음) | 일치 | 위와 동일 라인, `A_MIN` 참조는 생성자 전달뿐 실사용 0건(`grep A_MIN` 결과 2건 모두 정의/전달) |
| REQ-SPD-04 (G_TRIG/G_SAFE_MIN 값) | 일치 | argparse 기본값 `--g_trig 1.2 --g_safe_min 0.20` |
| REQ-SPD-05 (front_gap이 속도를 직접 안 정함) | 일치 | `v_ref`는 `front_gap`과 무관한 상수 대입(1866행), front_gap은 FSM 상태 전이에만 관여 |

## REQ-SEN (구 코드에서는 `legacy_2025/code_backup/simulator.py`가 담당)

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-SEN-01 (front_gap 계산) | **불일치**(다른 설계) | `simulator.py:131-139`: `dx=obstacle_x−x`; **`0<dx<5.0 AND \|dy\|<0.4`일 때만** `front_gap=dx`, 아니면 **`None`**(추천안 §7처럼 "큰 값"이 아니라 `None`, 게다가 횡방향 `dy` 게이트가 있어 차량이 충분히 옆으로 비켜서면 front_gap 자체가 사라짐 — PDF·추천안엔 없는 조건) |
| REQ-SEN-02 (left_clear 계산) | **불일치**(다른 설계) | `simulator.py:141-145`: `y<W*0.5`이면 무조건 True, 아니면 `\|y−obstacle_y\|>0.15`. §추천안의 "항상 True"보다 조건부(다만 L1 쪽 별도 장애물은 여전히 없음) |
| REQ-SEN-03 (IR→ey_line 변환) | 미확인 | `simulator.py`의 `_get_ir_sensors()`(107행~) 내부 변환식은 이번엔 상세 확인 안 함(2단계-B에서 필요시) |

## REQ-LAT / REQ-CTRL

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-LAT-01 (라인추종 δ=−K_ey·ey_line, K_ey=1.5) | 구조만 있음 | `final_hierarchical_backup.py`의 `self.lat.compute(ey_line, psi, 'keep')` 호출부는 존재(1889행 부근)하나, `legacy_2025/run_simulation.py` 경로에서는 `ey_line`이 항상 `None`이라 죽은 경로(위 REQ-FSM-02c와 동일 사유) |
| REQ-LAT-02 (EVADE_L·RETURN_TO_L2는 항상 MPC) | 일치 | EVADE_L 제어 블록(1916-1941행), RETURN_TO_L2 블록(1974행 "HYBRID STRATEGY: Always use Teacher MPC for RETURN_TO_L2" 주석)에 `ey_line` 조건 없이 무조건 MPC 호출 |
| REQ-LAT-03 (라인 미감지 판정=타임아웃) | **코드에만 있음**(추천안과 다름) | `SignalValidator(timeout=0.2)`(625-633행) 기반 — PDF 근거 없는 기존 코드만의 메커니즘. §4 추천안(존재/부재만 판정)과 다름 |
| REQ-LAT-04 (KEEP_L1도 대칭적 라인추종/MPC) | 일치(구조) | `1943-1971행`: KEEP_L2와 동일하게 `ey_line is not None` 분기 존재(단, 위와 같은 이유로 `legacy_2025/run_simulation.py`에서는 죽은 코드) |
| REQ-CTRL-01 (계층 통합) | 일치 | 위 두 블록이 상태별로 분기하는 구조 자체가 계층 통합에 해당 |

## REQ-SIM (구 코드: `legacy_2025/code_backup/simulator.py`)

| REQ | 판정 | 근거(파일:행) |
|---|---|---|
| REQ-SIM-01 (도로 W=0.30, L2/L1 중심) | 일치 | `RoadParams(W=0.30)` 기본값, `lane_centers=[0.0, self.rp.W]`(simulator.py:108) |
| REQ-SIM-02 (장애물 위치 U(0.5,2.0)) | **불일치** | `simulator.py:52`: `obstacle_x = np.random.uniform(2.5, 4.0)`(1단계 `STAGE1_FACTS.md` 항목4에서 이미 확인) |
| REQ-SIM-03 (초기 v~U(0.3,0.5), y~N(0,0.05²)) | **부분 불일치** | `simulator.py` reset(): `state.v=np.random.uniform(0.3,0.5)`(일치), `state.y=np.random.uniform(-0.05,0.05)`(균등, Gaussian 아님 — 불일치) |
| REQ-SIM-04/05 (200step/10s, "완료" 종료) | **불일치** | `simulator.py:92-104`: 종료는 `step_count≥max_steps`(200 또는 400) **또는** `\|y\|>MAX_Y_DEVIATION` **또는** `dist_to_obs<0.1`(충돌) 셋 중 하나 — "FSM이 KEEP_L2로 안전복귀"라는 조건은 없음 |
| REQ-SIM-08 (충돌 판정) | **불일치**(더 단순) | `simulator.py:100-101`: `dist_to_obs=sqrt((x−ox)²+(y−oy)²)<0.1` — 유클리드 거리 기반 점-점 충돌, 차량 크기(L,B)나 헤딩 미반영. §8 재검토 추천안(사각형-점)보다 단순하지만 최소한 **횡방향(y)도 함께 고려**하므로 1차 기각안(front_gap≤0, 종방향만)보다는 낫습니다 — 사실 이 점이 §8 옵션 선택에 참고할 만한 선례임 |

## REQ-STU (M트랙 사전 확인, `MEASURE_PLAN.md` 참고)

| REQ | 판정 | 근거 |
|---|---|---|
| REQ-STU-01 (구조 9→256→256→128→2, BN+Dropout0.15) | 일치 | `legacy_2025/models/policy_best.pth` state_dict 레이어 shape 확인: (256,9)(256,256)(128,256)(2,128) + BatchNorm 3곳 — Table4와 정확히 일치 |
| REQ-STU-02 (입력 9차원 순서) | 일치 | `legacy_2025/models/normalization_stats.json`의 `feature_names`: `[v, ey_line, front_gap, left_clear, state_KEEP_L2, state_EVADE_L, state_KEEP_L1, state_RETURN_TO_L2, state_SAFE_STOP]` — REQ-STU-02 순서와 정확히 일치 |
| REQ-STU-03 (출력 δ,v) | 일치 | `label_names: [delta, v]` |

---

## 요약

- **완전 일치**: REQ-VEH 전부(5), REQ-FSM-01/02a/02b/02d(4), REQ-MPC-01/03/04(δ,ψ만)/04a/08(5),
  REQ-SPD 전부(5), REQ-LAT-02/04(구조)(2), REQ-CTRL-01(1), REQ-SIM-01(1), REQ-STU 전부(3) —
  총 26건.
- **불일치**: REQ-FSM-02e, REQ-FSM-03/03a, REQ-MPC-02/03a(rΔδ 차분→크기로 오구현),
  REQ-MPC-04(y 3단계 제약 없음), REQ-MPC-07(fallback 게인), REQ-SEN-01/02(다른 설계),
  REQ-SIM-02/03/04-05/08 — 총 12건.
- **코드에만 있음(spec 초과)**: REQ-FSM-04(SAFE_STOP 복귀), REQ-LAT-03(타임아웃 기반 판정).
- **구조만 있음(죽은 코드)**: REQ-FSM-02c, REQ-LAT-01.
- **가장 중요한 신규 발견(이번 라운드)**: (1) MPC 비용함수의 rΔδ가 실제로는 "차분 벌점"이
  아니라 "크기 벌점"으로 잘못 구현됨(대각행렬 한계), (2) MPC 위치 제약이 상태와 무관한 단일
  상수(±0.45)이고 논문의 3단계 제약(L2/L1/차선변경구간)이 전혀 없음, (3) fallback 게인이
  K_p=1.0이 아니라 -qy(=100). 이 세 가지는 C트랙에서 "명세 차이로 설명됨"으로 분류할 핵심
  항목입니다.
