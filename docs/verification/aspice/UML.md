# UML — FSM 상태도 · 제어 1스텝 시퀀스도 · 컴포넌트도

기존 코드에서 **역으로** 그린 그림이다(설계 단계에서 먼저 그린 것이 아니다). GitHub Mermaid로 렌더링된다.
세 그림 모두 `check_uml.py`가 코드와 대조한다. 대조 항목은 각 절 끝에 적었다. 그림을 고치거나 코드가 바뀌면
`python docs/verification/aspice/check_uml.py`를 다시 돌린다. 불일치가 있으면 exit 1이다.

## 1. FSM 상태도 (`thesis_v2/baseline/fsm.py`)

<!-- uml:state -->
```mermaid
stateDiagram-v2
    [*] --> KEEP_L2 : 초기화 initial_fsm, 쿨다운 만료 상태로 시작(REQ-FSM-03b) [fsm.py:35]
    KEEP_L2 --> EVADE_L : D1 cooldown_ok ∧ front_gap < G_TRIG ∧ left_clear [fsm.py:55]
    EVADE_L --> KEEP_L1 : D2 cooldown_ok ∧ abs(y − W) ≤ NEAR_L1 [fsm.py:59]
    KEEP_L1 --> RETURN_TO_L2 : D3 cooldown_ok ∧ elapsed > T_KEEP_L1_MIN ∧ right_clear [fsm.py:64]
    RETURN_TO_L2 --> KEEP_L2 : D4 cooldown_ok ∧ abs(y) ≤ NEAR_L2 ∧ abs(psi_deg) ≤ PSI_L2_LIMIT_DEG [fsm.py:68]
    KEEP_L2 --> SAFE_STOP : D0 [fsm.py:51]
    EVADE_L --> SAFE_STOP : D0 [fsm.py:51]
    KEEP_L1 --> SAFE_STOP : D0 [fsm.py:51]
    RETURN_TO_L2 --> SAFE_STOP : D0 [fsm.py:51]
    note right of SAFE_STOP
        D0 (모든 상태에서 먼저 검사): cooldown_ok ∧ front_gap < G_SAFE_MIN ∧ not left_clear
        종단 상태: 복귀 없음 (fsm.py:70-71, REQ-FSM-04)
    end note
    note left of KEEP_L1
        D3 elapsed = t − state_enter_t (fsm.py:63)
        D3 관찰: 전이 때 last_change_t = state_enter_t (fsm.py:74) 이므로
        도달 가능한 상태에서 elapsed > 0.6 이면 cooldown_ok(≥ 0.3)도 참.
        cooldown_ok는 D3 결과를 바꾸지 못함 (MCDC_FSM.md §3, 코드 무수정)
    end note
    note left of KEEP_L2
        cooldown_ok = (t − last_change_t) ≥ COOLDOWN (fsm.py:47), 다섯 결정 공통 (REQ-FSM-03a)
        전이가 일어나면 last_change_t = state_enter_t = t (fsm.py:73-74)
    end note
```

- 가드는 `fsm.py`의 조건식을 그대로 옮겼다. 상수는 `thesis_v2/baseline/config.py`의 값이다. G_TRIG=1.2, G_SAFE_MIN=0.20, COOLDOWN=0.3, W=0.30, NEAR_L1=0.08,
  NEAR_L2=0.08([개정]), T_KEEP_L1_MIN=0.6, PSI_L2_LIMIT_DEG=20.0이다(`config.py:16-27`).
- D0은 `if`, D1–D4는 `elif fsm.state == …` 사슬 안에 있다(`fsm.py:51-71`). 그래서 D0이 참이면 D1–D4는 평가되지 않는다. D0이 SAFE_STOP 자신에서 참이면 상태는
  그대로라서 전이로 기록되지 않는다(`fsm.py:73`). 그림에는 SAFE_STOP이 아닌 4개 상태에서 나가는 화살표로 그렸다.
- D0–D4 이름은 `docs/verification/MCDC_FSM.md`와 같다.
- **자동 대조**(`check_uml.py`):
  - 상태 집합이 `FSMState`와 같은지
  - 전이 집합(출발, 도착, 행)이 `fsm.py`를 AST로 읽은 결과와 같은지. 규칙: 상태 조건 없는 첫 `if`는 SAFE_STOP이 아닌 모든 상태에서의 전이로 펼치고, 초기 전이는 `initial_fsm`의 반환 행으로 본다.
  - 각 결정의 가드에 나오는 `config.*` 상수, `sensors.*` 필드, 지역 변수가 그 결정 ID(D0–D4)가 적힌 그림 행에 모두 있는지

## 2. 제어 1스텝 시퀀스도 (이상탐지 폐루프, `thesis_v2/anomaly/closed_loop.py`)

폐루프 평가(1,100회)에 쓰인 루프 `run_closed_loop_episode`(`closed_loop.py:94-289`)의 1스텝이다. 정책 P0이면 `anomaly/runner.py:run_episode`와 결과가 같다
(`closed_loop.py:16`). 그 런너는 이상탐지 확장이 없는 improved v2 루프와 golden 동치다(`anomaly/runner.py:10-11`).

<!-- uml:sequence -->
```mermaid
sequenceDiagram
    autonumber
    participant L as 루프 closed_loop.py
    participant S as 센서 baseline/improved sensors
    participant F as 고장 주입 FaultInjector
    participant D as 탐지기 (A/B1/B2/HYBRID)
    participant M as FSM baseline/fsm.py
    participant C as 횡방향 improved/lateral.py
    participant Q as v2 MPC ImprovedMPC
    participant P as 차량·충돌 baseline/vehicle, collision
    L->>S: base_sensors.front_gap() · anomaly/closed_loop.py:138 (left_clear·right_clear·ir_pattern·ey_line 139-142, 노이즈 시 144-152)
    L->>S: improved_sensors.front_obstacle_info() · anomaly/closed_loop.py:153
    L->>F: injector.apply_sensors() · anomaly/closed_loop.py:157
    F-->>L: 주입 후 frame (고장 없으면 항등)
    L->>D: detector.update() · anomaly/closed_loop.py:172
    D-->>L: score, alarm, channel (탐지기는 주입된 원래 값만 본다)
    alt 첫 경보 + 정책 P1 또는 P2의 fg·trk·psi 채널 → 즉시 정지
        L->>P: vehicle_step() · anomaly/closed_loop.py:200 (v_cmd=0, 직전 조향 유지)
        L->>P: collision.check_collision() · anomaly/closed_loop.py:201
        Note over L: 에피소드 종료 ("탐지 정지" 또는 충돌·이탈)
    else 계속 (P0, 또는 P2의 ey·rc·lc 채널은 그 값을 제어 입력에서 덮어씀 214-216)
        L->>M: fsm_step() · anomaly/closed_loop.py:219
        M-->>L: 새 FSM 상태
        L->>C: compute_lateral() · anomaly/closed_loop.py:229
        C->>Q: mpc.solve() · improved/lateral.py:37
        Q-->>C: 조향 원출력, solver 상태
        C-->>L: delta_desired
        L->>L: longitudinal.compute_v_cmd() · anomaly/closed_loop.py:232
        L->>L: postprocess.apply() · anomaly/closed_loop.py:233
        L->>F: injector.apply_actuator() · anomaly/closed_loop.py:237
        L->>P: vehicle_step() · anomaly/closed_loop.py:238
        L->>P: collision.check_collision() · anomaly/closed_loop.py:239
        Note over L,P: 충돌 판정은 차량 갱신 직후, 다음 스텝 FSM 갱신보다 먼저 (repro/docs/WORK_RULES.md baseline 원칙)
    end
```

- 횡방향은 상태와 라인 감지 여부에 따라 라인추종 또는 MPC를 쓴다(REQ-LAT-01–05, `improved/lateral.py`). 그림의 `mpc.solve()`는 MPC 경로다. 라인추종 경로는 생략했다.
- 이탈 판정(`vehicle_off_road`, 240행)과 종료 판정(243-279행)은 시뮬레이션 쪽이라 생략했다.
- **자동 대조**(`check_uml.py`):
  - `호출() · 파일:행` 표기마다 그 행에 호출 이름이 실제로 있는지
  - `anomaly/closed_loop.py`의 행 번호가 그림 순서대로 증가하는지(실행 순서)
  - 조건 분기의 정확성(어떤 정책에서 어느 쪽으로 가는지)은 대조하지 않는다.

## 3. 컴포넌트도 (패키지 단위 import 그래프)

<!-- uml:component -->
```mermaid
flowchart LR
    baseline["baseline<br/>FSM · MPC(OSQP) · 센서 · 차량 · 충돌 · 런너<br/>(3단계 동안 동결)"]
    improved["improved<br/>v1/v2 MPC · 센서 확장 · 런너 · 평가"]
    student_i4["student_i4<br/>Student 신경망 재학습 · 폐루프 · 벤치마크"]
    anomaly["anomaly<br/>고장 주입 · 탐지기 A/B1/B2/HYBRID · 오프라인/폐루프 평가"]
    numpy[(numpy)]
    scipy[(scipy)]
    osqp[(osqp)]
    torch[(torch)]
    sklearn[(scikit-learn)]
    onnxruntime[(onnxruntime)]
    improved --> baseline
    student_i4 --> baseline
    student_i4 --> improved
    anomaly --> baseline
    anomaly --> improved
    baseline -.-> numpy
    baseline -.-> scipy
    baseline -.-> osqp
    improved -.-> numpy
    improved -.-> scipy
    improved -.-> osqp
    student_i4 -.-> numpy
    student_i4 -.-> scipy
    student_i4 -.-> torch
    student_i4 -.-> onnxruntime
    anomaly -.-> numpy
    anomaly -.-> torch
    anomaly -.-> sklearn
```

- 실선 `A --> B`: 패키지 A의 모듈이 B를 import한다(`thesis_v2/<패키지>/`, tests 제외). `student_i4`는 `improved/student_i4/`를 따로 묶은 것이다.
  점선은 외부 라이브러리 import다(numpy, scipy, osqp, torch, sklearn, pandas, onnx, onnxruntime, matplotlib, joblib 중 실제로 import되는 것).
- baseline은 다른 내부 패키지를 import하지 않는다. 이것은 repro/docs/WORK_RULES.md의 "baseline 동결, 개선은 improved에서만"과 맞는다.
- **자동 대조**(`check_uml.py`): 그림의 실선 집합이 AST로 구한 패키지 import 그래프와 같은지, 점선 집합이 외부 라이브러리 import 집합과 같은지.
  그림에 없는 import가 생기거나 그림에만 있는 화살표가 있으면 실패한다.
