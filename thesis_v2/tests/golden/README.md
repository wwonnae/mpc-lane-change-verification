# golden 기준 데이터

`paper`·`left_obstacle` 시나리오 seed 0~2의 재구현 결과(전이 목록, 결과 분류, 완료 step,
최종 상태, 조향각 시계열)를 저장합니다. 생성 환경은 `env.json` 참고.

## 생성 환경 (최초, 이 파일들을 만든 실행)

`env.json` 참고 — 2026-09-17, 노트북(hostname DESKTOP-MDCKRJS), Python 3.9.12,
numpy 2.0.2, scipy 1.13.1, osqp 1.1.1.

## v1.1 재확인 (2026-09-22, front_gap 버그 수정 + 관찰구간 FSM 상시 갱신)

`sensors.py`의 REQ-SEN-01 버그 수정([정합], `THESIS_REVISION_LOG.md` 2026-09-22)과
`runner.py`의 관찰구간 FSM 상시 갱신 정정 이후, SSAFY PC(hostname 3층PC104, Python
3.11.9, numpy 2.4.6, scipy 1.17.1, osqp 1.1.3)에서 `python -m thesis_v2.tests.check_golden`
재실행 결과 **6/6 PASS, 전 항목 max\|diff\|=0.000000 rad**(파일 내용 갱신 없음 — 값이
그대로 일치했으므로 이 표기만 추가). 이 결과는 예상된 것입니다: 두 변경 모두 `lateral.py`의
조향 계산 입력(ey, y, psi, v, state)에 front_gap을 넣지 않으므로 golden이 저장하는
조향각 시계열에는 애초에 영향이 없고, seed 0~2의 100-episode 비교(`paper`/`left_obstacle`
전체 100 seed)에서도 outcome·finish_step·transitions가 v1.0과 완전히 동일함을 별도
확인했습니다.

## 사용법

- 확인만: `python -m thesis_v2.tests.check_golden` (PASS/FAIL과 불일치 시 첫 차이 step 출력)
- pytest에 포함됨: `test_check_golden.py`가 자동으로 같이 돈다(`pytest thesis_v2/tests`)
- 갱신(baseline을 **의도적으로** 바꿨을 때만): `python -m thesis_v2.tests.golden.generate_golden`
  — 결과가 다르게 나왔다고 golden을 바꾸는 것은 금지(repro/docs/WORK_RULES.md 금지 목록: "baseline을
  결과에 맞춰 수정"과 같은 원칙). 코드를 먼저 의도적으로 바꾸고, 그 변경을 새 기준으로
  기록하고 싶을 때만 실행합니다.

## 판정 기준

전이 목록(`from->to@step`)·결과 분류(outcome)·완료 step은 **완전 일치**해야 합니다.
조향각 시계열(`delta_final`, rad로 저장)은 최대 차이 **1e-3 rad** 이내면 일치로 판정합니다
(OSQP 버전·BLAS 구현 차이에 따른 솔버 수치오차 허용 — SETTINGS_DECISION.md §18의
eps_abs=1e-4보다 넉넉한 여유를 둠).

## 실패 시

SSAFY PC에서 이 확인이 실패하면, 코드가 다른 게 아니라 **환경 차이**(numpy/scipy/osqp
버전, BLAS 구현 등)로 수치가 갈렸을 가능성이 있습니다. `check_golden.py` 출력의 "첫 차이
step"부터 원인을 좁혀가고, `SETTINGS_DECISION.md` §18에 이미 고정한 설정 외에 버전 간
기본값이 다른 OSQP 파라미터가 더 있는지부터 확인하십시오. baseline 코드를 결과에 맞춰
고치지 않습니다(repro/docs/WORK_RULES.md 금지 목록) — 원인을 보고합니다.
