# 재구현 작업 규칙

재구현 전 과정에 적용한 규칙이다. 다른 문서가 "작업 규칙"이라고 인용하는 기준이 이 문서다.

## 목적과 흐름
제출 논문(`docs/졸업논문.pdf`, 2025.12)을 요구사항 명세로 삼아 제어기를 새로 구현·검증하고, 개선한 뒤, 논문 개정판을 만든다.
1. baseline: 논문 서술 + 확정된 결정표대로 구현한다.
2. 측정: 실행 전에 고정한 기준(`MEASURE_PLAN.md`)으로 측정한다.
3. 발전: `thesis_v2/improved/`에서 개선하고, 같은 기준·같은 seed로 비교한다.
4. 논문 개정판: 새 문서로 작성한다. 제출본 PDF는 수정하지 않는다.

- 기존 코드는 참고·비교용이다. 복사해 붙이지 않고, 로직은 SPEC 근거로 새로 작성한다.
- 제출본 논문 수치를 새 코드 결과로 표기하지 않는다. 새로 측정한 수치만 보고한다.

## 핵심 주장과 범위
1. [최우선] MPC(OSQP, 2-state)로 제약을 만족하는 조향각을 계산한다.
2. [최우선] 종방향은 규칙 기반 속도 제어다. MPC에 속도를 넣지 않는다.
3. [보조] 신경망은 임베디드 적용 여지 확인 수준이다.

## 기준 문서 (구현의 유일한 근거)
- `repro/docs/SPEC.md`: 요구사항 (REQ ID)
- `repro/docs/SETTINGS_DECISION.md`: [해석]/[공백]/[개정] 확정 결정
- `repro/docs/MEASURE_PLAN.md`: 측정 항목·판정 기준·seed 정책
- `repro/docs/FEASIBILITY_CHECK.md`: 사전 계산 근거
- 누적 기록: `repro/docs/THESIS_REVISION_LOG.md`, `repro/docs/IMPROVEMENT_BACKLOG.md`
- SPEC·결정표에 없는 동작이 구현에 필요하면 임의로 정하지 않고, 결정을 먼저 기록한 뒤 구현한다.

## 파일·폴더
- 제출 당시 원본(`legacy_2025/`, `docs/졸업논문.pdf`)은 내용을 수정하지 않는다.
- 재구현 코드: `thesis_v2/` (독립 패키지, 원본 파일 import 금지)
  - `thesis_v2/baseline/`: 정합 구현
  - `thesis_v2/improved/`: 개선 버전
  - `thesis_v2/tests/`: REQ ID별 테스트. `tests/compare/`만 원본 코드 import 허용
  - `thesis_v2/results/<타임스탬프>_<호스트>_<버전·트랙>/`: 모든 새 측정 결과

## 명세 태그
- [정합] PDF 명시 → 그대로 구현
- [해석] PDF 모호 → 결정표대로 구현
- [공백] PDF에 없음 → 결정표의 최소 가정대로 구현
- [개정] PDF 값이 실행 전 계산으로 실현 불가 증명 → 결정표의 수정 값으로 구현. 고정 파라미터는 대상 아님
- [발전] PDF에 없는 개선 → baseline에 넣지 않고 `IMPROVEMENT_BACKLOG.md`에만 기록
- 코드 주석에 REQ ID와 태그를 남기고, 테스트는 REQ ID별로 만든다(추적표 유지).

## baseline 원칙
- 논문 시나리오에서 KEEP_L2→EVADE_L→KEEP_L1→RETURN_TO_L2→KEEP_L2 흐름이 동작해야 한다.
- 실행 결과를 보고 baseline을 수정하지 않는다(개선은 improved/에서).
- 제어기(FSM·MPC·속도 제어)는 센서 모델 출력(front_gap, left_clear, right_clear, ey_line, 차량 상태)만 입력으로 받는다. 시뮬레이터 내부 좌표 직접 참조 금지.
- 충돌 판정은 매 스텝 차량 상태 갱신 직후, FSM 갱신보다 먼저 한다(회전 사각형 겹침).
- MPC 원출력, 후처리 후 출력, solver 상태, fallback 사용 여부를 매 스텝 기록한다.

## 개선 단계 원칙
- 개발용(dev)·평가용(eval) 데이터를 분리한다. 파라미터·margin은 해석적으로 정하거나(가능한 경우 우선) dev에서만 결정한다. eval 데이터로는 어떤 파라미터도 정하지 않는다.
- eval은 확정된 코드에 1회만 실행한다. eval 실행 후 결과를 보고 그 코드를 다시 고치지 않는다(고치면 새 반복으로 사유와 함께 기록하고 이전 eval 결과도 남긴다).
- 각 개선 항목은 config 플래그로 독립 on/off 가능해야 한다(ablation 필수).
- `thesis_v2/baseline/`는 개선 단계 동안 동결한다.

## 고정 파라미터 (변경 금지)
N=15, dt=0.05, qy=100, qpsi=25, rdelta=2, rddelta=5, δ±25°, 200deg/s,
G_TRIG=1.2, G_SAFE_MIN=0.20, COOLDOWN=0.3, W=0.30, L=0.20, B=0.15
- `thesis_v2/baseline/config.py` 한 곳에서만 정의하고, 시작 시 이 값과 일치하는지 assert한다.

## 검증 트랙 (섞지 않는다)
- P 물리 폐루프(주 트랙): 논문 시나리오 + 추가 검증 시나리오(좌측 차로 장애물 → SAFE_STOP)를 분리 실행
- C 비교: 같은 입력에서 원본 MPC(`legacy_2025/final_hierarchical_backup_thesis_1204.py`) vs baseline MPC
- M 신경망: MPC solve vs Student 추론 시간, 조향 오차

## 금지
- 결과를 보고 판정 기준·설정 변경, seed 골라내기, 에피소드 선별
- 결과 상수 하드코딩
- baseline을 결과에 맞춰 수정
- 발전 버전에만 유리한 측정 기준

## 기록 규칙
- "확인됨(실행/파일/PDF 페이지)"과 "추정(근거)"을 구분하고, 근거에 경로:행 또는 PDF 페이지·REQ ID를 붙인다.
