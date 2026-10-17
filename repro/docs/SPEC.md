# 재구현 명세 (2단계-A)

원본(루트, `legacy_2025/code_backup/`, `legacy_2025/results/`, `legacy_2025/models/`, `legacy_2025/verify/`(공개본 제외), `docs/졸업논문.pdf`)은 수정·삭제·이동
하지 않았습니다. 이 문서는 논문 서술을 요구사항(REQ)으로 분해한 명세서입니다. 아직 코드는
작성하지 않았습니다.

표시 규칙: **[정합]** PDF에 명시 → 그대로 구현. **[해석]** PDF 서술은 있으나 모호 → 선택지 제시,
`SETTINGS_DECISION.md`에서 사용자 결정. **[공백]** 구현에 필요한데 PDF에 아예 없음 → 최소
가정 + 사용자 결정 + `THESIS_REVISION_LOG.md` 기록 대상. **[발전]** PDF에 없는 개선 →
baseline에 넣지 않고 `IMPROVEMENT_BACKLOG.md`에만 기록(이 문서엔 후보만 적어둠).

근거 페이지는 전부 1단계에서 이미지로 직접 확인한 것입니다(`repro/docs/THESIS_PAGES.md`,
`repro/docs/pdf_pages/page_NN.png`). 원문 인용은 pdftotext 결과(`docs/졸업논문.txt`, 한글 깨짐
없는 숫자·수식 부분)와 이미지 판독을 함께 사용했습니다.

---

## REQ-VEH: 차량 모델·파라미터

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-VEH-01 | Kinematic bicycle model(후륜 중심 기준): ẋ=v·cos(ψ), ẏ=v·sin(ψ), ψ̇=(v/L)·tan(δ) | p.7 식(1)~(3), "x, y는 차량 후륜 중심의 위치" | [정합] |
| REQ-VEH-02 | 차량 파라미터: L=0.20m(축간거리), B=0.15m(차폭), δ_max=±25°, 속도범위 0.0~0.5 m/s, δ_rate_max=200deg/s | p.6-7 Table 1 | [정합] |
| REQ-VEH-03 | 조향각 rate limiting: Δδ_max = 200deg/s × dt(0.05s) = 10°/step, `δ_cmd=clip(δ_desired, δ_prev−Δδ_max, δ_prev+Δδ_max)` | p.8-9, 명시적 수식 있음 | [정합] |
| REQ-VEH-04 | 시뮬레이션 적분법: Euler 적분 | p.7 "III.3": "Euler 적분법을 사용한다" | [정합] |
| REQ-VEH-05 | 속도(v)에 대한 별도 동역학(가속도/관성) 방정식 없음 — v는 매 스텝 직접 지정되는 입력으로 취급 | p.7 식(1)~(3)에 v의 시간미분식 없음(확인됨, 이미지) | [정합](이 자체가 "SAFE_STOP=즉시 v=0" 판단의 근거) |

## REQ-FSM: 유한상태기계

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-FSM-01 | 5개 상태: KEEP_L2, EVADE_L, KEEP_L1, RETURN_TO_L2, SAFE_STOP | p.6,8 | [정합] |
| REQ-FSM-02a | KEEP_L2→EVADE_L: front_gap<1.2 AND left_clear=True | p.8 Table 2 | [정합] |
| REQ-FSM-02b | **모든 상태**→SAFE_STOP: front_gap<0.20 AND left_clear=False, 예외 없음 | p.8 Table 2 + p.10 "회피 기동 중... 즉시 SAFE_STOP"(1단계에서 비모순 판정 완료, `STAGE1_FACTS.md` 결정②) | [정합] |
| REQ-FSM-02c | EVADE_L→KEEP_L1: \|y−0.30\|≤0.08m | p.8 Table 2 | [정합] |
| REQ-FSM-02d | KEEP_L1→RETURN_TO_L2: **right_clear(REQ-SEN-04) AND t>0.6s** | p.8 IV.1(1) KEEP_L1 문단 원문 "KEEP_L1(1차선 유지) 상태는 회피 차선에서 대기하며, **전방 장애물을 완전히 통과할 때까지** 1차선을 유지한다. 최소 유지 시간(T_KEEP_L1_MIN=0.6초)이 경과하면 RETURN_TO_L2 상태로 전이한다." Table 2(p.8)는 "t>0.6s"만 요약 | [해석] — "완전 통과"를 시뮬레이터 좌표 직접비교가 아니라 **센서(right_clear) 판정**으로 구현(repro/docs/WORK_RULES.md 원칙). `keep_l1_return_check_v2.py` 계산: 시간조건만이면 front_gap0=1.2/1.6/2.0m에서 RETURN 중 충돌, right_clear AND 시간이면 0.5~2.0m 전 구간(완료 79~140 step, +20 관찰 포함 99~160 step) 무충돌·200 step 이내 |
| REQ-SEN-04 | **right_clear**(신규, left_clear와 대칭): L2 범위[−0.15,0.15] AND x∈[차체 후단−G_SAFE_MIN, 차체 전단+G_TRIG] 윈도우에 장애물이 없으면 True | p.7 "LiDAR 센서는 2D 스캔을 수행하여 주변 장애물까지의 거리를 측정"(원문은 left_clear만 예시로 들었으나 2D 스캔이라는 서술 자체는 전방위적이라 반대쪽 차로 판정에도 동일하게 적용 가능) | [해석] — left_clear(REQ-SEN-02)와 대칭 정의, `SETTINGS_DECISION.md` §14 |
| REQ-FSM-02e | RETURN_TO_L2→KEEP_L2: **\|y\|≤0.08m**(원문 0.20m에서 [개정]) **AND** \|ψ\|≤20° | p.8 Table 2(원문 0.20m) | **[개정]** — 원문 0.20m은 REQ-MPC-04의 KEEP_L2 위치제약(\|y\|≤0.15m, 같은 p.9-10 표에 명시)과 구조적으로 충돌(증명: `FEASIBILITY_CHECK.md` 계산2, `SETTINGS_DECISION.md` §개정1). \|ψ\|≤20°는 충돌 없어 원문 유지 |
| REQ-FSM-03 | 상태 전이 쿨다운 0.3초: 상태 변경 후 0.3초 내 추가 전이 차단 | p.8 "(3) 안전 메커니즘" | [정합] — 모든 전이에 일관 적용(아래 REQ-FSM-03a) |
| REQ-FSM-03a | 쿨다운 적용 범위: PDF (3)번은 "상태가 변경된 후... 추가 전이가 차단된다"고 **전이 종류를 한정하지 않음** → 5개 전이(FSM-02a~02e) 전부에 동일하게 적용 | p.8 (3), 문장에 예외 문구 없음 | [정합](가장 문장에 가까운 해석 — 특정 3곳에만 적용한 구 코드가 아니라 "전부 적용"을 채택) |
| REQ-FSM-04 | SAFE_STOP 진입 시 회복 조건·재진입 로직 | **PDF에 없음** — Table 2/본문 어디에도 SAFE_STOP→다른 상태로의 복귀 조건이 서술되지 않음 | [공백] — `SETTINGS_DECISION.md` §1 |

## REQ-MPC: MPC 횡방향 제어

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-MPC-01 | 이산 선형 모델(2-state, y·ψ): y_{k+1}=y_k+v·dt·ψ_k, ψ_{k+1}=ψ_k+(v/L)·dt·δ_k | p.9 식(4)~(5) | [정합] |
| REQ-MPC-02 | 비용함수: J=Σ_{i=1}^N[qy(y_i−y_ref)²+qψ·ψ_i²] + rδ·δ_0² + Σ_{i=1}^{N-1} rΔδ(δ_i−δ_{i-1})² | p.9 식(6) | [정합] |
| REQ-MPC-03 | 가중치: qy=100, qψ=25, rδ=2, rΔδ=5, N=15(0.75s) | p.9 Table 3 | [정합, 고정 파라미터] |
| REQ-MPC-03a | rδ는 **첫 제어입력의 크기(δ_0²)에만** 곱해지고, rΔδ는 **연속 제어입력의 차분(δ_i−δ_{i-1})²에** 곱해진다 — 식(6)의 두 항은 서로 다른 대상(크기 vs 차분)을 벌점화하므로 Hessian에 rΔδ에 대응하는 **비대각(off-diagonal) 항**이 필요함(대각행렬만으로는 (a−b)² 항을 표현 불가) | p.9 식(6): `r_δ·δ_0² + Σ_{i=1}^{N-1} r_Δδ(δ_i−δ_{i-1})²` | [정합] |
| REQ-MPC-04 | 제약: −25°≤δ_i≤25°; 헤딩 −80°≤ψ_i≤80°; 횡방향 위치 — L2주행 −0.15≤y≤0.15, L1주행 0.15≤y≤0.45, 차선변경구간 −0.15≤y≤0.45 | p.9-10 | [정합] |
| REQ-MPC-04a | 조향 변화율(Δδ) 제약의 **위치는 QP가 아니라 후처리 클리핑**이다 — p.9-10의 "(3) 제약조건" QP 목록엔 δ,ψ,y만 있고 Δδ_max(10°/step)는 그 이전 절(p.8-9, "안전 메커니즘"·"조향각 Rate Limiting")에서 `δ_cmd=clip(δ_desired, δ_prev−Δδ_max, δ_prev+Δδ_max)`로 별도 서술됨 → QP 밖에서 MPC 출력(δ_desired)에 사후 적용 | p.8-9 수식, p.9-10 QP 제약 목록에 Δδ 부재(둘 다 이미지로 확인) | [정합] |
| REQ-MPC-05 | 횡방향 위치 제약의 상태별 매핑: KEEP_L2→"L2주행" 제약, KEEP_L1→"L1주행" 제약, EVADE_L·RETURN_TO_L2→"차선변경구간" 제약(가장 넓은 범위) | **PDF는 "3가지 제약이 있다"고만 하고 상태-제약 매핑 규칙을 명시하지 않음** | [해석] — `SETTINGS_DECISION.md` §2(다만 세 상태군과 제약 이름이 1:1로 대응해 사실상 유일한 해석) |
| REQ-MPC-06 | QP 정식화: minimize (1/2)zᵀHz+fᵀz s.t. l≤A_ineq·z≤u, z=[y1,ψ1,δ0,...,yN,ψN,δ_{N-1}]ᵀ, H=diag(qy,qψ,rδ,rΔδ 조합), OSQP solver, warm-start | p.10 | [정합] |
| REQ-MPC-07 | Fallback: 최적화 실패 시 δ_fallback=−K_p·(y−y_ref), K_p=1.0 | p.10 식(7) | [정합] |
| REQ-MPC-07a | 식(7) 단위 확정: K_p=1.0은 **rad/m**(δ_fallback_rad=−K_p·(y−y_ref), 이후 deg로 변환) | PDF 수식만 있고 단위 명시 없음 — 결정 근거는 `SETTINGS_DECISION.md` §11 | [해석](결정 완료) |
| REQ-MPC-07b | 부호 규약: **+y = 좌측(L1 방향), +ψ = 좌회전(반시계, 헤딩 증가), +δ = 좌회전(전륜을 좌측으로)** — eq(1)-(3)에서 δ>0→ψ̇>0(좌회전)→ẏ>0(좌측 이동)이 일관되게 성립 | p.7 식(1)~(3)의 부호 구조로부터 도출(PDF가 명시적 부호표는 안 주지만, 식 자체가 이 규약과만 일관됨) | [정합](식으로부터 유도, 다른 부호 규약은 식(1)-(3)과 모순) |
| REQ-MPC-08 | MPC는 속도를 결정하지 않음(z벡터에 v 없음, 비용함수에 속도 항 없음) | p.9 식(6), z 정의(p.10) — 핵심 주장 2번과 일치 | [정합] |

## REQ-SPD: 규칙 기반 종방향 속도 제어

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-SPD-01 | v_ref=0.5m/s, KEEP_L2·EVADE_L·KEEP_L1·RETURN_TO_L2 상태에서 유지 | p.10 "(1) 속도 결정 규칙" | [정합] |
| REQ-SPD-02 | SAFE_STOP: v=0으로 설정 | p.8,10 | [정합] |
| REQ-SPD-03 | SAFE_STOP 감속 방식: "가능한 한 빠르게 감속" | p.8 | [해석] — REQ-VEH-05(속도에 가속도 방정식 없음)에 따라 "즉시 0으로 스텝점프"가 가장 문장에 가까운 해석 → `SETTINGS_DECISION.md` §3 |
| REQ-SPD-04 | G_TRIG=1.2m(회피 시작), G_SAFE_MIN=0.20m(비상정지) | p.8,10, 고정 파라미터 | [정합] |
| REQ-SPD-05 | front_gap은 속도를 직접(연속적으로) 결정하지 않는다 — 속도는 FSM **상태**에 의해서만 결정되고(REQ-SPD-01/02), front_gap은 G_TRIG/G_SAFE_MIN 문턱을 통해 FSM 상태 전이(REQ-FSM-02a/02b)에만 관여한다 | p.10 "(1) 속도 결정 규칙" 전체 — front_gap을 속도식에 직접 대입하는 서술 없음 | [정합] |

## REQ-SEN: 센서 모델

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-SEN-01 | front_gap 계산: LiDAR가 "전방 장애물까지의 거리"를 측정 — 구체적 기하 공식(장애물 통과 후 처리 등) | p.7 "LiDAR 데이터로부터 전방 장애물까지의 거리(front_gap)... 추출"만 서술, 공식 없음 | [공백] — `SETTINGS_DECISION.md` §7 |
| REQ-SEN-02 | left_clear 계산: "좌측 차선의 장애물 유무" | p.7. 시나리오 서술(p.6,11)엔 L1(좌측 차선) 장애물이 전혀 등장하지 않음 | [정합] — 시나리오상 좌측 차선엔 장애물이 없으므로 left_clear=True 항상(→ SAFE_STOP은 이 baseline 시나리오에서 이론적으로만 존재, 실제 발생 안 함. 이는 논문 Table 10의 "SAFE_STOP 0건"과도 일치) |
| REQ-SEN-03 | IR 3개(0.04m 간격, 이진패턴) → ey_line 변환 공식 | p.7 "(3) 센서 모델" — "센서 패턴에 따라... 추정한다"만 서술, 변환식 없음 | [공백] — `SETTINGS_DECISION.md` §9 |

## REQ-LAT: 횡방향 제어 법칙(모드별)

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-LAT-01 | 라인추종: δ=−K_ey·ey_line, K_ey=1.5 — KEEP_L2에서 라인이 명확히 감지될 때 사용 | p.10 식(8) | [정합](식·값) / [해석](K_ey 단위 rad/m, 신규) → `SETTINGS_DECISION.md` §17 |
| REQ-LAT-02 | MPC 모드: 라인이 감지되지 않거나 차선 변경 중(EVADE_L, RETURN_TO_L2)에 사용 — EVADE_L·RETURN_TO_L2는 라인 감지 여부와 무관하게 **항상** MPC | p.10 "MPC 모드는 라인이 감지되지 않거나 차선 변경 중(EVADE_L, RETURN_TO_L2)에 사용된다" | [정합] |
| REQ-LAT-03 | "라인이 감지되지 않음"의 판정 기준(센서 유효성 타임아웃 등 구체값) | **PDF는 "감지되지 않는 경우"라고만 함, 구체적 유효성 판정 로직 없음** | [공백] — 최소 가정: 매 스텝 IR 센서 값이 존재하면 "감지됨", 존재하지 않으면(가려짐 등) "감지 안 됨" → `SETTINGS_DECISION.md` §4 |
| REQ-LAT-04 | KEEP_L1 상태에서의 횡방향 제어 모드 | **PDF p.10 문장은 "KEEP_L2에서 라인 감지 시 라인추종", "차선 변경 중(EVADE_L, RETURN_TO_L2)엔 MPC"라고만 하고 KEEP_L1을 명시하지 않음** | [공백] — KEEP_L1도 "차선 유지" 상태이므로 KEEP_L2와 대칭적으로 "라인 감지 시 라인추종(목표 y=0.30), 아니면 MPC"로 채움 → `SETTINGS_DECISION.md` §5 |
| REQ-LAT-05 | SAFE_STOP 상태의 횡방향 제어(조향) | **PDF의 "4. 통합 제어 구조"(p.10)는 KEEP_L2/KEEP_L1/EVADE_L/RETURN_TO_L2만 다루고 SAFE_STOP은 언급이 전혀 없음** | [공백] — 신규(2단계-B 구현 중 발견, `KeyError` 재현으로 확인) — MPC·라인추종 호출 없이 직전 최종 조향각 유지(수정안 a) → `SETTINGS_DECISION.md` §16 |

## REQ-CTRL: 계층 통합 (상위 구조)

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-CTRL-01 | 횡방향(REQ-LAT, 라인추종 또는 MPC) + 종방향(REQ-SPD, 규칙기반) 계층 통합 | p.10 "4. 통합 제어 구조" | [정합] |

## REQ-SIM: P트랙 물리 폐루프 시뮬레이터(시나리오·에피소드)

핵심 주장 범위(제어기)는 아니지만, P트랙 검증에 필요한 시뮬레이션 환경 요구사항입니다.
센서 계산식은 REQ-SEN을 참고하십시오.

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-SIM-01 | 도로: 2차선, 차선폭 W=0.30m, L2 중심 y=0, L1 중심 y=0.30 | p.6 | [정합, 고정 파라미터 W] |
| REQ-SIM-02 | 장애물: L2 차선에 정지 장애물 1개(크기 L×B, 차량과 동일 풋프린트로 가정), 위치 X_obs~U(0.5,2.0)m | p.6,11 "장애물의 위치는 0.5m에서 2.0m 사이의 균등 분포" | [정합] 분포 자체 / [공백] 장애물 크기(→§8, L×B로 채움) |
| REQ-SIM-02a | "장애물 위치"의 측정 기준점: 차량 후륜(kinematic model 원점) 기준인지, 차체 전단(LiDAR가 실제로 있을 위치) 기준인지 | **PDF는 (x,y)를 "차량 후륜 중심"으로 정의(p.7)하지만, "장애물 위치"·front_gap은 LiDAR(전방 센서) 측정값이라 전단 기준이 자연스러움 — PDF가 명시하지 않음** | [해석] — `SETTINGS_DECISION.md` §12. 두 해석의 실현가능성이 다름(계산 근거 있음) |
| REQ-SIM-03 | 초기 조건: v0~U(0.3,0.5)m/s, y0~**TruncatedNormal(0, 0.05², [−0.15,0.15])**(원문은 절단 없는 N(0,0.05²)), ψ0=0 명시 없음 | p.6,11 | [정합](v) / **[개정]**(y0 절단 — 원문 미절단 Gaussian은 KEEP_L2 자체 위치제약 \|y\|≤0.15(p.9-10)를 벗어난 값을 뽑을 수 있어 초기 스텝부터 QP infeasible 가능, 증명: `SETTINGS_DECISION.md` §개정2) / [공백](ψ0 — 최소가정 0) |
| REQ-SIM-04 | 에피소드: 최대 200 step(10s at 20Hz), "안전하게 회피 및 복귀를 완료" 또는 SAFE_STOP 도달 시 종료 | p.11 | [정합] 구조, [해석] "완료"의 정확한 트리거 |
| REQ-SIM-05 | "완료" 트리거 정의 | **PDF는 "완료"만 언급, 조작적 정의 없음** | [해석] — 가장 자연스러운 해석: EVADE_L에 진입했던 에피소드가 다시 KEEP_L2 상태가 되면 완료(REQ-FSM-02e 조건이 이미 \|y\|≤0.20,\|ψ\|≤20°를 요구하므로 "안전하게"를 내포) → `SETTINGS_DECISION.md` §6 |
| REQ-SIM-08 | 충돌(collision) 판정: 실거리 기반 기하 판정 — front_gap(종방향)만으로는 차선변경 중 옆면·모서리 접촉을 못 잡음(재검토로 확인) | **PDF에 충돌 판정 공식 전혀 없음**(안전거리 G_SAFE_MIN=0.20은 "정지 거리"이지 "충돌 거리"가 아님) | [공백] — `SETTINGS_DECISION.md` §8: 차량(L,B,ψ) vs 장애물(점, 0-크기) 사각형-점 포함 판정 추천 |

## REQ-EVAL: 평가 지표 정의

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-EVAL-01 | 제어 성능 지표: 횡방향 오차, 헤딩각 오차, 조향각 변화율, 목표 추종 오차 | p.13 "성능 평가 지표는 다음과 같다..." | [정합] 지표 목록 / [공백] 각 지표의 정확한 통계 공식(평균만인지 평균±표준편차인지는 Table 6/13/14에서 역으로 확인 가능 — 평균±표준편차, RMS 병기) |
| REQ-EVAL-02 | 안전성 지표: 제약 만족률, 충돌 횟수, 최소 장애물 거리 | p.13 | [정합] 지표 목록. 제약 만족률 계산식은 REQ-MPC-04 제약 대비 위반 스텝 비율(Table 12 방식 참고) |
| REQ-EVAL-03 | 계산 효율성 지표: 평균 계산시간, 최대 계산시간, 계산시간 표준편차(+ 백분위수는 Table 8에서만 등장) | p.13, p.15 Table 8 | [정합] |
| REQ-EVAL-04 | 회피 성공률: 정의 문장 자체는 없고 Table 7 "회피 성공률(%) — 설명: 전체 성공"으로만 등장 | p.14 Table 7 | [공백] — 최소 가정: (SAFE_STOP도 충돌도 없이 에피소드 종료)/(전체 에피소드) → `SETTINGS_DECISION.md`에 §10으로 추가 |

## REQ-STU: Student 정책 (M트랙, 재학습 없음)

| ID | 내용 | 근거 | 태그 |
|---|---|---|---|
| REQ-STU-01 | 신경망 구조: 입력9→FC1(256)→FC2(256)→FC3(128)→출력2, ReLU, BatchNorm+Dropout(0.15) | p.12 Table 4 | [정합, 구조 확인용] — **재구현하지 않음.** `legacy_2025/models/policy_best.pth`를 그대로 로드해 구조 일치만 검증 |
| REQ-STU-02 | 입력 특징(9차원): v, ey, front_gap, left_clear, state_one_hot(5) | p.11 | [정합] — M트랙 추론 입력 조립에 사용 |
| REQ-STU-03 | 출력(2차원): δ(deg), v_target(m/s) | p.11 | [정합] |
| REQ-STU-04 | 정규화 통계 | `legacy_2025/models/normalization_stats.json` 그대로 사용 | [정합](파일 그대로 사용, 수정 금지) |
| REQ-STU-02r | (3단계 Student v2 전용) 입력 11차원 = REQ-STU-02의 9차원 + ψ(차량 헤딩) + δ_prev(직전 최종 조향) | SETTINGS_DECISION.md §20 | ψ: **[개정]**(논문 MPC가 ψ0의 함수 — 9차원으로 모방 불가 계산 증명), δ_prev: [발전] 파생(교사 v2의 I1 종속). 2단계-D·기존 I4(9차원)는 REQ-STU-02 그대로 |

---

## [발전] 후보 (baseline엔 포함 안 함, `IMPROVEMENT_BACKLOG.md`에만 기록 예정)

이번 조사 중 눈에 띈 것만 나열합니다. 3단계 전까지는 논의만 하고 구현하지 않습니다.
- SAFE_STOP 회복 로직(REQ-FSM-04, [공백]으로 최소 가정만 baseline에 넣고, 더 정교한 이력/재시도
  로직은 발전 후보로 분리)
- RETURN_TO_L2→KEEP_L2에 실제 헤딩각 조건(REQ-FSM-02e)을 넣었을 때의 안정성 튜닝
  (baseline은 PDF 그대로 구현, 발전판에서 필요시 손볼 후보)

## 요약: 결정이 필요한 항목 ([해석]·[공백])

`SETTINGS_DECISION.md`에서 다룹니다: §1 SAFE_STOP 복귀 조건(REQ-FSM-04), §2 MPC 위치제약
상태매핑(REQ-MPC-05), §3 SAFE_STOP 감속 방식(REQ-SPD-03), §4 라인 미감지 판정 기준
(REQ-LAT-03), §5 KEEP_L1 횡방향 제어 모드(REQ-LAT-04), §6 에피소드 "완료" 트리거
(REQ-SIM-05), §7 front_gap 계산식(REQ-SEN-01), §8 충돌 판정 기준(REQ-SIM-08, 재검토),
§9 IR→ey_line 변환(REQ-SEN-03), §10 회피 성공률 정의(REQ-EVAL-04), §16 SAFE_STOP 횡방향
제어(REQ-LAT-05, 신규), §17 K_ey 단위(REQ-LAT-01, 신규), §18 OSQP 솔버 설정(REQ-MPC-06 관련,
신규, 교차 환경 재현성).

REQ-MPC-03a(rΔδ 차분 항)와 REQ-MPC-04a(Δδ 제약 위치)는 PDF 서술이 명확해 [정합]으로
분류했고 사용자 결정이 필요 없습니다 — 다만 `SPEC_VS_OLDCODE.md`에서 확인했듯 **기존 코드는
이 두 가지를 PDF와 다르게 구현**하고 있어 C트랙에서 "예상된 차이"로 다룹니다.
