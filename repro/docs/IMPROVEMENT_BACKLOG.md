# 개선 아이디어 백로그 (누적 기록)

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

목적: baseline 구현·검증 중 떠오르는 개선 아이디어([발전] 항목)를 여기에만 기록합니다.
baseline(`thesis_v2/baseline/`)에는 절대 넣지 않고, 3단계(`thesis_v2/improved/`)에서
선택적으로 구현·비교합니다.

형식: `## 후보 N — 제목` / **동기** / **baseline과의 차이** / **예상 트레이드오프**

---

## 후보 1 — SAFE_STOP 회복 로직 정교화

- **동기**: `SPEC.md` REQ-FSM-04([공백]), baseline은 "복귀 없음(종단 상태)"로 최소 가정
- **baseline과의 차이**: front_gap 회복 시 재출발 가능하게 하는 이력 기반 복귀 로직 추가
- **예상 트레이드오프**: 안전성(불필요한 조기 종료 감소) vs 복잡도·새 파라미터(회복 임계값)
  필요

## 후보 2 — 좌측 차선 장애물 시나리오 추가

- **동기**: `SPEC.md` REQ-SIM-07 — baseline 시나리오는 논문처럼 좌측 차선에 장애물이 전혀
  없어 SAFE_STOP이 실제로는 발생하지 않음(이론상으로만 존재)
- **baseline과의 차이**: 좌측 차선에도 가끔 장애물을 배치해 left_clear=False 케이스와
  SAFE_STOP 진입·(후보1과 결합 시)회복을 실제로 검증
- **예상 트레이드오프**: SAFE_STOP 경로를 실제로 검증할 수 있게 되지만, 논문이 서술한
  시나리오 자체를 벗어나므로 "발전판 전용" 결과로만 보고해야 함

## 후보 3 — IR 센서 이산 패턴 물리 모사

- **동기**: `SPEC.md` REQ-SIM-09 — baseline은 이상적 참값(ey_line=y−target_center)을 사용
- **baseline과의 차이**: 0.04m 간격 3개 이산 센서의 이진 패턴을 실제로 모사하고 보간/추정
  알고리즘을 추가
- **예상 트레이드오프**: 더 사실적인 센서 노이즈·양자화 오차 재현 가능 vs 구현 복잡도 증가,
  추가 파라미터(패턴→값 매핑 규칙) 필요

## 후보 4 — MPC 비용함수에 장애물 근접도(회피 긴급도) 반영 [정정판]

- **정정 안내**: 최초 기록("EVADE_L 트리거에 시간 여유(TTC) 반영")은 원인을 FSM의
  EVADE_L 트리거 시점으로 잘못 짚었습니다. 사용자 수기 검산 + 독립 재계산
  (`repro/2c_analysis/avoidance_feasibility_recheck.py`) 결과 seed=85는 FSM이 이론상
  최선(첫 스텝)에 반응했고 회피 궤적도 존재했음(여유 0.299m)이 확인되어, 개선 대상을
  **FSM 트리거**가 아니라 **MPC 비용함수**로 정정합니다
- **동기**: 2단계-C 결과 분석 — paper 100 에피소드 중 seed=85가 충돌(24 step만에,
  front_gap0=0.5665m, v0=0.394m/s, y0=−0.0464m). 정정된 원인은 REQ-MPC-02 비용함수
  (J=Σqy(y−y_ref)²+qψψ²+...)가 **장애물의 존재·거리를 전혀 입력받지 않아**, 회피가
  급한 상황에서도 평소와 똑같이 "부드러운" 궤적(헤딩 벌점 qψ=25로 인해 헤딩이 일정 수준
  이상 커지면 조향을 되돌림)을 그린다는 것. 실측(`repro/2c_analysis/out/
  seed85_heading_steering_compare.png`)에서 실제 MPC 헤딩이 step11 부근 17.4°에서
  정체·감소하는 반면, 같은 초기조건에서 "항상 δ=+25°"인 최대노력 정책은 계속 헤딩을
  키워 회피에 성공함(여유 0.299m 확인) — MPC가 가용 여유를 쓰지 않은 것이 직접 원인
- **baseline과의 차이**: MPC 비용함수 또는 제약에 장애물 근접도를 반영하는 안.
  예: (a) front_gap(센서값)이 작을수록 qψ를 낮춰(또는 rΔδ를 낮춰) 더 공격적인 회피를
  허용하는 가변 가중치, (b) y_ref 자체를 장애물 통과 시점까지 동적으로 당기는 안,
  (c) 장애물 통과 시점(front_gap 기반 예측 x)까지는 y가 안전역(예: |y|≥0.15)에 있어야
  한다는 제약을 QP에 추가(진짜 "장애물 인지" MPC로 확장)
- **예상 트레이드오프**: 충돌률 감소(핵심 안전 지표 개선) vs 논문의 고정 비용함수 가중치
  (qy=100,qψ=25,rδ=2,rΔδ=5)·QP 정식화(REQ-MPC-02/06)를 벗어나는 새 로직·새 파라미터
  필요(baseline은 고정 파라미터·QP 정식화를 바꾸지 않으므로 3단계에서만 검토), 장애물
  인지 항 추가 시 QP가 비볼록화되거나 계산시간이 늘 위험(REQ-EVAL-03 계산 효율성과
  트레이드오프)
- **2026-09-22 추가 근거(S3 강건성 격자, `RESULT_ROBUSTNESS.md` §1)**: seed=85 한 건이
  아니라 **전체 961격자에서 체계적으로 확인됨** — 물리적 최선(bang-bang) 회피가 가능한
  최소 front_gap0(y0별 0.24~0.33m, `avoidance_feasibility_recheck.py` 재사용)과 실제
  baseline MPC가 성공하기 시작하는 관측 경계(y0별 0.5~0.9m) 사이에 **평균 0.42m(범위
  0.26~0.57m)의 여유가 그냥 버려지고 있음**(y0∈[-0.15,0.01] 17개 열 평균). 3단계에서
  이 격자를 그대로 재사용해 개선 전후 경계를 정량 비교할 수 있음(같은 기준, 결과 보고
  전 확정)

## 후보 5 — Student 추론 런타임을 ONNX Runtime으로 교체

- **동기**: 2단계-D M트랙(SSAFY PC, `RESULT_STUDENT.md` §6)에서 같은 가중치를 PyTorch
  eager로 추론하면 baseline MPC(0.14ms)보다 느리지만(0.22ms, 정규화 포함), **ONNX
  Runtime으로 바꾸면 0.047ms로 baseline MPC보다 약 3배 빨라짐**을 확인(변환 검증: PyTorch
  대비 출력 최대 차이 4.39e-5°, 정확도 손실 없음)
- **baseline과의 차이**: baseline 자체(제어 로직)는 변경 없음 — "신경망 임베디드 적용
  여지"(핵심 주장 3, [보조])를 논할 때 추론 런타임만 PyTorch에서 ONNX Runtime으로
  바꾸는 안. 재학습 없음, `legacy_2025/models/policy_best.pth` 그대로 사용(export만 함)
- **예상 트레이드오프**: 계산시간 이점(임베디드 적용 여지 강화) vs 배포 파이프라인에
  ONNX 변환·검증 단계 추가 필요, `torch.onnx.export`의 `dynamo=True`(신규 기본 경로)가
  `onnxscript` 의존성을 요구해(이번 세션 SSAFY PC에서 `ModuleNotFoundError` 확인)
  `dynamo=False`(레거시, PyTorch 2.9+ deprecated 예정) 경로를 써야 했다는 점도 함께
  기록(장기적으로 `onnxscript` 설치나 다른 경로 필요)

## 후보 6 — baseline MPC 데이터로 Student 재학습

- **동기**: 현재 `legacy_2025/models/policy_best.pth`는 옛 Teacher MPC(`legacy_2025/code_backup/
  final_hierarchical_backup.py`, 2025-12-04)가 생성한 데이터를 모방하도록 학습됐습니다.
  그런데 이 옛 MPC의 `OSQPMPC`는 REQ-MPC-02 비용함수 구현에 확인된 스케일링 버그가
  있습니다(Hessian `P`는 `qy/qψ/rδ/rΔδ` 원값, 선형항 `q`는 2배 계수 — 표준 QP 형태에서
  `y_ref≠0`인 상태의 실제 끌림점이 `2*y_ref`가 됨, `THESIS_REVISION_LOG.md` 2026-09-18
  REQ-MPC-02 항목). baseline MPC(`thesis_v2/baseline/mpc.py`)는 이 버그가 없이 REQ-MPC-02를
  정확히 구현합니다. 그 결과 2단계-D M트랙 MAE 측정(`RESULT_STUDENT.md` §4, §7)에서 "Student
  vs 옛 MPC" MAE(EVADE_L 27.9°/23.8°, KEEP_L1 26.2° 등)와 "Student vs baseline MPC"
  MAE(KEEP_L1 0.18° 등)가 크게 엇갈려, **현재 Student가 버그 있는 교사를 모방한 것인지
  baseline(올바른 교사)에 가까운지가 뒤섞여 있어 공정한 비교가 아닙니다**
- **baseline과의 차이**: baseline 자체(제어 로직)는 변경 없음 — baseline `runner`가 남기는
  실행 로그(`thesis_v2/results/*/*_steps.npz`, `steps` 필드: y,psi,v,ey_line,front_gap,
  left_clear,state,delta_mpc_raw)로 (feature, baseline MPC 출력) 데이터셋을 새로 생성해
  Student를 재학습하는 안. REQ-STU-02(입력 9차원)·REQ-STU-04(정규화 통계 방식)는 유지하되
  값은 baseline 데이터로 새로 계산
- **측정 계획**: 재학습된 모델을 PyTorch·ONNX 양쪽으로 벤치마크(`run_onnx_benchmark.py`
  패턴 재사용), 조향 오차 MAE는 **baseline MPC 출력을 기준**으로 계산(옛 MPC 대비 1순위
  비교는 더 이상 의미 없음 — 애초에 옛 MPC를 학습 대상으로 삼지 않으므로). 데이터셋은
  학습/검증 분리(예: 에피소드 단위 split, 같은 에피소드의 step이 train/val에 섞이지
  않도록) 필요
- **예상 트레이드오프**: 공정한(버그 없는 기준으로 학습된) Student MAE·속도 비교 확보 vs
  재학습 파이프라인 구축 필요(현재 저장소에 Student 학습 스크립트는 `legacy_2025/code_backup/
  train_student_v2.py`뿐이고 thesis_v2에는 없음 — repro/docs/WORK_RULES.md "재학습하지 않는다"는
  baseline 원칙과 별개로 3단계 발전판에서만 수행). repro/docs/WORK_RULES.md 핵심 주장 3([보조])
  범위이므로 우선순위는 3단계 내에서도 낮게 둘 것

## 후보 7 — left_clear/right_clear 경계 접촉 판정을 차량 풋프린트 기준으로 정교화

- **동기**: `ROBUSTNESS_PLAN.md` S7a(장애물 폭 0.30m) 실행 결과, `sensors.py:_window_clear`
  가 경계 접촉(장애물 y_hi가 정확히 차로 경계 0.15에 닿음)을 "막힘"으로 판정해 100/100
  에피소드가 SAFE_STOP으로 끝남(충돌 0건). 실제로는 L1 차로 중심(y≈0.30)까지 도달하면
  차량 풋프린트([y-B/2,y+B/2])가 장애물과 전혀 겹치지 않아 **물리적으로 통과 가능한
  여유가 있었음**(`SETTINGS_DECISION.md` left_clear 절 "경계 접촉 판정 원칙" 참고) — 즉
  현재 정의는 "차로 절반 전체"를 기준으로 보수적으로 판정하지, 차량이 실제로 지나갈
  좁은 통로가 있는지는 보지 않음
- **baseline과의 차이**: `_window_clear`의 y 범위 인자를 차로 전체(L1: [0.15,0.45])가
  아니라, 목표 차로 중심(target_line_y) 기준 **차량 풋프린트 폭(B) 통로**([target_y-B/2,
  target_y+B/2])로 좁혀 판정하는 안. 또는 장애물과 차로 경계 사이 실제 여유(margin)를
  계산해 차량 폭(B)보다 크면 통과 가능으로 판정
- **예상 트레이드오프**: 불필요한 SAFE_STOP 감소(가용 차로 여유를 실제로 활용) vs
  "코 앞이 아니라 목표 지점 기준"으로 판정이 바뀌면 정말 좁은 통로에서 차량이 옆면을
  스칠 위험을 놓칠 수 있어 REQ-SIM-08 충돌판정과의 정합성 재검토 필요 — 현재(보수적)
  정의는 "안전 우선" 설계이므로 3단계에서 바꿀지는 충돌률·완료율 트레이드오프를 실제
  측정한 뒤 판단. **동작은 이 세션에서 바꾸지 않았음**(baseline `sensors.py` 미수정)

## 후보 8 — MPC의 rate limit/이전 조향각 인지 + fallback 공격성 강화

- **동기**: `ROBUSTNESS_PLAN.md` S6(ψ0=-15°, seed=6) 재검증 결과(`THESIS_REVISION_LOG.md`
  2026-09-22 정정 항목) — REQ-SIM-03 초기조건 자체는 실현 가능했는데(step 0부터 이론상
  최선 궤적으로 재계산하면 위반 없음), 실제로는 (1) `mpc.py:solve()`가 `delta_prev`나
  rate limit(REQ-VEH-03, 10°/step)을 전혀 입력받지 않아 매 step "즉시 원하는 각도(최대
  25°)를 낼 수 있다"고 낙관적으로 재계획하고, (2) QP가 infeasible로 전환된 뒤
  REQ-MPC-07 fallback(K_p=1.0, y-오차에만 비례)이 이론상 최선(+25° 포화)에 한참 못
  미치는 약한 교정만 내놓는 두 가지가 겹쳐 실제로는 제약을 위반함
- **baseline과의 차이**: (a) `solve()`에 실제 `delta_prev`를 인자로 받아, delta_0에
  대해서만이라도 `|delta_0 - delta_prev| <= rate_limit`을 QP의 하드 제약으로 추가(수평선
  나머지는 그대로 두어 계산량 영향 최소화). (b) fallback을 "y-오차 비례"가 아니라
  "가능한 최대 조향(부호는 오차 방향)"으로 바꾸거나, 최근 QP 해가 포화 상태였는지를
  참고해 fallback도 그 방향으로 포화시키는 안
- **예상 트레이드오프**: 강건성 향상(S6류 극단 초기조건에서 위반 감소) vs QP에 제약을
  추가하면 계산시간 증가·다른 상태에서의 거동 변화 위험(REQ-MPC-06 정식화 자체를 바꾸는
  것이라 3단계에서만 검토). fallback을 더 공격적으로 바꾸면 평상시(정상 상태) 오작동
  시 과도한 조향을 낼 위험도 함께 검토 필요

---

> 이하 후보 9~12는 I4 폐루프 실패 분석(`RESULT_I4.md` §5~7, 2026-09-25)에서 나온 **제안만**입니다
> (구현하지 않음). 수치 근거는 `repro/2c_analysis/out/i4_closed_loop_failure/analysis.json`.

## 후보 9 — 실패 궤적을 포함한 데이터 보강 (DAgger류)

- **동기**: Student 폐루프에서 입력 분포가 학습 분포를 크게 벗어남(상태 조건부 |z|>3이 학습 1.0% →
  폐루프 30.0% / 32.4%, RETURN_TO_L2는 47% / 50%, 6~8s 구간 68% / 74%). Student가 스스로 만든 상태
  (큰 헤딩, 과진입·과복귀)는 교사 데이터에 없음. 논문 VII 향후 연구 넷째 항목("DAgger 같은 반복적 학습
  기법")과 같은 방향
- **방법(제안)**: Student(또는 Student/MPC 혼합)로 dev 시나리오를 주행하며 방문한 상태마다 v2 MPC를
  그림자 호출해 라벨을 붙이고 데이터에 합쳐 재학습을 반복. dev seed만 사용(eval 금지)
- **예상 효과**: 분포 이동 축소 → RETURN_TO_L2 진동·과복귀 감소 기대. **단, 후보 12의 관측성 문제(ψ·δ_prev
  미입력)는 데이터를 늘려도 남으므로**(학습 데이터 자체에서 교사 δ 분산 33%가 입력으로 설명 불가) 단독
  효과는 제한적일 것으로 추정
- **트레이드오프**: 반복마다 데이터 생성·학습 비용, 반복 횟수·혼합 비율이 새 설계 파라미터가 됨(dev에서만 결정)

## 후보 10 — 출력 제약을 모델에 내장

- **동기**: Student 원출력이 ±25°를 넘은 비율 1.60% / 3.80%(KEEP_L1 11.9% / 27.9%), 최대 44.5° / 50.4°.
  개루프에서도 최대 26.24°. 현재는 후처리 clip에만 의존
- **방법(제안)**: 출력층에 25°·tanh 같은 유계 활성화로 |δ|≤25°를 구조적으로 보장. 필요하면 δ_prev를
  입력으로 받아 |δ−δ_prev|≤10°/step도 출력 단계에서 보장(후보 12와 연계)
- **예상 효과**: 원출력 범위 위반 0%(구조적 보장), clip 의존 제거. **폐루프 성공률 자체는 크게 바뀌지 않을
  것으로 추정** — clip은 이미 차량 입력을 범위 안으로 맞추고 있고, 실패의 주원인은 범위 위반이 아니라
  헤딩 미관측에 의한 조향 부족·과다(§6-1)
- **트레이드오프**: 경계 근처 포화 영역에서 기울기 소실로 학습이 느려질 수 있음. 위치·헤딩 같은 상태
  제약(REQ-MPC-04)은 출력 제한만으로는 보장되지 않음 — 여전히 MPC와 같은 "제약 만족 보장"은 아님

## 후보 11 — 하이브리드: 신경망 우선 + MPC 폴백

- **동기**: MPC는 폐루프 100% 성공(0 충돌)이지만 p99 계산시간이 Student보다 4~24배 큼(`RESULT_I4.md` §4).
  Student는 빠르지만 단독 주행 실패
- **방법(제안)**: 매 스텝 Student 출력을 먼저 계산하고, 안전 판정(예: 예측 궤적이 위치·헤딩 제약을
  위반하거나 Student 입력이 학습 분포 밖이거나, 상태가 RETURN_TO_L2/KEEP_L1처럼 실패가 집중된 경우)이
  걸리면 v2 MPC로 넘김. 판정 규칙은 해석적으로 정하거나 dev에서만 결정
- **예상 효과**: 안전성은 MPC 수준에 가깝게, 평균 계산량은 폴백 비율만큼 감소. **최악 계산시간(p99)은
  MPC 폴백 시간으로 결정되므로 줄지 않음** — 이점은 평균 계산량·전력이지 최악 보장 아님
- **트레이드오프**: 판정기 자체가 새 설계 요소(오탐=불필요한 폴백, 미탐=위험). 이번 분석에서 오차가 초기
  2초부터 7.9°로 커서 폴백 비율이 높을 가능성(추정)

## 후보 12 — Student 입력에 헤딩 ψ·직전 조향 δ_prev 추가 (분석에서 도출, 사용자 제시 목록 외)

> **2026-09-25 분류 변경**: 사용자 결정으로 [발전] → **[개정]** 처리. 계산 확인 결과 ψ는 논문 MPC 자체의
> 입력이라 **[개정]**(`SETTINGS_DECISION.md` §20), δ_prev는 교사 v2(I1)에서만 필요해 **[발전] 파생**으로
> 나눠 기록(사용자 확인 대기). 구현은 `DESIGN_I4.md` §6(Student v2, 11차원). 아래 원 기록은 그대로 둠.

- **동기**: 이번 분석의 주원인. v2 MPC δ는 ψ·δ_prev에 의존하지만 REQ-STU-02 입력에 없음. 학습 데이터에서
  Student 입력 격자 내 교사 δ 분산이 전체의 33.4%(칸 내 표준편차 4.8°), 폐루프 오차와 ψ 상관 r=0.54~0.65,
  RETURN_TO_L2 평균 |ψ| v2 9.6° vs Student 28.6°
- **방법(제안)**: 입력을 9→11차원(ψ, δ_prev 추가)으로 확장. **논문 REQ-STU-02·Table 4 구조와 달라지므로
  [발전] 항목으로만** 다루고, 원 입력 정의 결과(I4)와 나란히 비교
- **예상 효과**: 관측 불가능 성분 제거로 개루프·폐루프 오차 모두 감소 기대(가장 직접적인 원인 대응).
  후보 9·10과 결합 가능
- **트레이드오프**: 논문 구조와의 정합성 상실(개정판에서 "논문 입력 정의의 한계"로 서술 필요). ψ는 실제
  RC카에서 IMU 등 추가 센서 필요 — 센서 모델에 ψ 측정이 들어가야 repro/docs/WORK_RULES.md "센서 모델 출력만 입력" 원칙과
  맞음(현재 FSM은 자기 상태 y·ψ를 이미 입력으로 씀)

## 후보 13 — 노이즈로 회피에 들어간 뒤 SAFE_STOP이 쿨다운에 막혀 정지가 늦어짐 (이상탐지 확장에서 발견, 2026-10-12, 고치지 않음)

- **동기**: 좌측 장애물 시나리오 + S4-low 센서 노이즈에서 고장 없는 v2 주행이 드물게 충돌한다(이상탐지 폐루프 평가 seed 5011 —
  같은 원인으로 **추정**; 보충 재현 seed 3000~3399에서 원거리 400회 중 1회(seed 3173, 원인 **확인**), 기존 근거리 left_obstacle
  400회 중 4회). 재현 경로: front_gap 측정이 G_SAFE_MIN(0.20 m) 바로 위인 step에 left_clear가 노이즈로 한 번 True로 뒤집혀
  KEEP_L2→EVADE_L → 다음 step부터 SAFE_STOP 조건(front_gap<0.20 그리고 left_clear=False)이 참이지만 쿨다운 0.3 s(6 step,
  REQ-FSM-03)가 전이를 막음 → 그동안 v=0.5 m/s로 접근 → SAFE_STOP step에도 직전 속도로 한 step 이동해 충돌.
  근거: `thesis_v2/anomaly/DESIGN.md` §25-1, `docs/revision/data/anomaly/supplement.json`. 기존 E2·E3 left_obstacle은 노이즈 없이
  실행해(`thesis_v2/improved/run_eval_v2.py:174-178`) 이 조건을 다루지 않았다.
- **baseline과의 차이(후보, 미구현)**: (a) SAFE_STOP 전이에 쿨다운 예외(모든 상태→SAFE_STOP은 쿨다운 무시), (b) left_clear 다수결·
  연속 k step 확인 후 회피 허가, (c) 회피 진입 직후 front_gap이 G_SAFE_MIN 아래면 즉시 정지. 모두 FSM 명세(REQ-FSM-02b·03) 변경이라
  [발전]으로만 다룬다.
- **예상 트레이드오프**: (a)는 정지 지연을 없애지만 노이즈 한 번에 SAFE_STOP이 앞당겨질 수 있음(불필요 정지 증가 가능), (b)는 오판정
  회피를 줄이지만 정상 회피 시작이 k step 늦어짐(원거리 성공률·S3 경계에 영향), (c)는 조건이 추가되어 FSM 검증 범위가 늘어남.
  평가는 노이즈 있는 left_obstacle·paper 트랙을 새 seed 대역에서 같은 기준으로 비교해야 함.

## 후보 14 — B1·하이브리드(Isolation Forest) 탐지기의 step당 최악 시간이 20 Hz 예산을 넘음 (이상탐지 확장 계산 시간 측정에서 발견, 2026-10-12, 고치지 않음)

- **동기**: 노트북 공식 조건(AC 전원 + 최고 성능, 정상 seed 3000~3199 × 2시나리오, 탐지기당 59,331 step) 측정에서 B1·하이브리드의
  step당 시간은 p99가 예산 이내(제어 포함 11.29·10.79 ms)였지만 최댓값이 50 ms를 넘은 step이 각 1개 있었다(68.80·61.01 ms). p50(약 6 ms)이
  B2(AE, 0.20 ms)의 30~31배다. 원인은 IF(트리 200개, `score_samples`)를 step마다 윈도우 1개로 부르는 **단일 샘플 호출 비용으로 추정**한다
  (호출 내부 시간은 나누어 재지 않았고, 예산 초과 1 step과 OS 스케줄링 요인도 분리하지 않음). A·B2는 최악값까지 예산 이내였다.
  근거: `thesis_v2/results/anomaly/20261012_232824_DESKTOP-MDCKRJS_detector_timing/timing.json`, `thesis_v2/anomaly/DESIGN.md` §29.
- **대안(후보, 미구현)**: (a) 트리 수 축소(200 → 예: 50·100) — §13-4 고정 하이퍼파라미터 변경이므로 재학습·임계값 재결정 필요,
  (b) ONNX 변환(skl2onnx) 또는 트리 일괄 평가 구현으로 Python 호출 오버헤드 제거 — 새 패키지 필요(설치 전 확인), 점수 동일성 검증 필요,
  (c) 호출 내부 분해 측정(특징 계산·`score_samples`·sklearn 입력 검증)으로 원인부터 확정, (d) 시간 상한 감시(예산 초과 시 해당 step 판정 생략·
  이전 점수 유지) — 탐지 지연과 맞바꿈.
- **예상 트레이드오프**: (a)는 점수 분산이 커져 오경보·탐지율이 바뀔 수 있음(평가를 새 seed 대역에서 다시 해야 함), (b)는 의존성 추가와
  수치 차이 가능성(golden 비교 필요), (d)는 결정성(같은 입력 → 같은 결과)을 실행 PC 부하에 묶음. 어느 것이든 임베디드 보드 측정과 함께
  판단해야 한다(현재 노트북 x86만 측정).

## 후보 15 — 폐루프 즉시 정지 step이 액추에이터 고장을 거치지 않음 (mutation testing 보강에서 발견, 2026-10-13, 고치지 않음)

- **동기**: 이상탐지 폐루프의 즉시 정지 step(P1, P2의 fg·trk·psi)은 `delta_to_vehicle = delta_prev`로 차량을 갱신하고
  `injector.apply_actuator`를 부르지 않는다(`thesis_v2/anomaly/closed_loop.py:199-200`). 그래서 steer_stuck·steer_delay가 활성이어도
  명령한 δ_{k−1}로 갱신된다. 정지 step에서만 액추에이터 고장이 사라지는 **낙관적 모델링**이다. DESIGN.md §24는 "직전 조향(δ_{k−1}) 유지"까지만 정했다.
  저장된 평가에서 이런 정지 step은 P1_A 199, P1_B1 6, P1_B2 187, P1_HYBRID 115, P2_A 199건이다. 기록된 결과가 바뀐 경우는 0건으로
  **추정**한다(근거: `docs/verification/mutation/RESULTS.md` 발견 사항 3, `docs/verification/mutation/raw/stop_step_steer_fault_count.json`).
- **baseline과의 차이(후보, 미구현)**: 정지 step의 조향도 `injector.apply_actuator(step_idx, delta_prev)`를 거치게 한다(물리적으로
  고장 난 액추에이터는 정지 명령에도 고장 상태 그대로). 폐루프 결과 정의(DESIGN.md §24)를 바꾸는 것이므로 사전 선언 뒤 새 평가가 필요하다.
- **예상 트레이드오프**: 위 추정대로면 현재 평가 결과는 바뀌지 않는다. 정지 step 한 번의 판정만 보수적으로 바뀐다. 다만 정지 뒤 제동 거리를
  모델링하게 되면(`docs/verification/safety/FTTI.md` §4 즉시 정지 가정) 고장 액추에이터가 정지 중 궤적에 주는 영향이 커지므로 함께 다뤄야 한다.

## 후보 16 — baseline MPC의 명세에 없는 동작 2건을 명세에 올리거나 정리 (mutation testing 보강에서 발견, 2026-10-13, 고치지 않음)

- **동기**: 구현에는 있으나 SPEC·SETTINGS_DECISION에 없는 동작(파생 요구사항 누락)이 2건 있다. 각 동작을 바꾸는 변이가 기존 테스트에서
  생존했고, 무엇이 맞는지 명세가 없어 테스트로 고정하지 않았다(`docs/verification/mutation/RESULTS.md` 발견 사항 4).
  (a) 속도 하한 `max(0.05, …)`(`thesis_v2/baseline/mpc.py:208`, "수치안정") — baseline 실행에서 MPC 호출 속도는 0.3~0.5 m/s라 영향 없음(추정).
  (b) fallback 출력 ±25° 클램프(`mpc.py:261`) — 차량 한계 ±25°(REQ-VEH-02)의 적용 위치는 후처리(SETTINGS_DECISION §15)라 MPC 단계 클램프는 중복.
  최종 명령은 같고 MPC 원출력 기록만 달라진다(추정).
- **baseline과의 차이(후보, 미구현)**: (a) 하한의 필요성(OSQP 수치 문제 여부)을 확인해 결정표에 [공백] 항목으로 올리거나, v0 < 하한 입력을 호출부에서
  막는 전제조건으로 바꾼다. (b) fallback 단계 클램프를 결정표에 명시하거나 없애고 후처리 클립에만 맡긴다(MPC 원출력 기록의 의미를 정해야 함).
  baseline 동결 원칙상 baseline 코드는 바꾸지 않고, 결정표 변경과 improved 쪽 반영 여부를 함께 판단한다.
- **예상 트레이드오프**: 명세에 올리면 테스트로 고정할 수 있지만 결정표 개정 절차가 필요하다. 없애면 (a)는 v0 → 0에서 A의 v 의존 계수가 0이 되어
  해가 바뀌고(측정: δ_0 25° 차이), (b)는 MPC 원출력 기록에 ±25° 밖 값이 나타날 수 있다.
