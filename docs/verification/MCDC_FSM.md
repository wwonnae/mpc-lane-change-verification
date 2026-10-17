# MC/DC — `thesis_v2/baseline/fsm.py` 전이 조건

작업 2026-10-13, 3층PC109, Python 3.9.13. 제어 로직(`fsm.py`)은 바꾸지 않았다. 추가한 것은 테스트 3개(`thesis_v2/tests/test_fsm_mcdc.py`)와
측정 도구(`mcdc/`)뿐이다.

> **Python 커버리지 도구는 MC/DC를 자동 측정하지 않는다.** coverage.py는 구문·분기(행 간 이동)만 기록한다. 그래서 MC/DC는 **수동으로 설계**했고,
> 테스트 실행 중 조건 값을 기록하는 자체 플러그인(`mcdc/mcdc_trace.py`)으로 **검증**했다. 이 플러그인은 도구 적격성 확인을 거치지 않은 자체 제작 도구다.

## 핵심 (확인됨, 실행)

| | step 호출 | 재진술 불일치 | unique-cause 쌍이 확인된 조건 |
|---|---|---|---|
| 기존 `test_fsm.py`만 | 22 | 0 | **11/14** — 미충족 D1 `front_gap<G_TRIG`, D3 `elapsed>T_KEEP_L1_MIN`, D4 `\|y\|≤NEAR_L2` |
| + `test_fsm_mcdc.py`(3개 추가) | 28 | 0 | **14/14** |

- 조건별 쌍과 사용한 테스트: `mcdc/MCDC_TABLES.md`(자동 생성). 원자료: `mcdc/mcdc_before_existing_tests.json`, `mcdc/mcdc_after_added_tests.json`.
- 계획 단계의 추정 하나가 틀렸다. 사전 분석에서는 D0 `front_gap<G_SAFE_MIN` 쌍도 빠졌다고 봤다. 실측해 보니 기존 `test_any_state_to_safe_stop_positive`(TTT→SAFE_STOP)와
  `test_keep_l2_to_evade_l_negative_not_left_clear`(fg=1.1, left_clear=False → TFT→KEEP_L2)가 이미 쌍을 이루고 있었다. 그래서 테스트는 4개가 아니라 3개만 추가했다.
- **관찰(확인됨, 코드)**: D3의 `cooldown_ok`는 `step()`으로 도달할 수 있는 상태에서는 결과에 독립적으로 영향을 줄 수 없다(아래 "결합 조건").
  기존 쌍은 테스트가 직접 만든 FSM 객체에서만 성립한다. 코드는 바꾸지 않았다. 이 조건은 REQ-FSM-03a("5개 전이 전부 적용")가 명시적으로 요구한다.

## 1. 대상 결정 (복합 조건 전부)

`step()`의 전이 결정 5개, 조건 14개다. 상태 분기(`elif fsm.state == ...`)는 단일 조건이라 대상이 아니다. `target_line_y()`(40행)의
`state in (KEEP_L2, RETURN_TO_L2)`는 전이 조건이 아니므로 이번 범위에서 뺐다.

| 결정 | 행 | 전이 | 조건(순서 = 평가 순서) | REQ |
|---|---|---|---|---|
| D0 | `fsm.py:51` | 모든 상태 → SAFE_STOP | `cooldown_ok` ∧ `front_gap < G_SAFE_MIN` ∧ `not left_clear` | REQ-FSM-02b, 03a |
| D1 | `fsm.py:55` | KEEP_L2 → EVADE_L | `cooldown_ok` ∧ `front_gap < G_TRIG` ∧ `left_clear` | REQ-FSM-02a, 03a |
| D2 | `fsm.py:59` | EVADE_L → KEEP_L1 | `cooldown_ok` ∧ `\|y − W\| ≤ NEAR_L1` | REQ-FSM-02c, 03a |
| D3 | `fsm.py:64` | KEEP_L1 → RETURN_TO_L2 | `cooldown_ok` ∧ `t − state_enter_t > T_KEEP_L1_MIN` ∧ `right_clear` | REQ-FSM-02d, 03a |
| D4 | `fsm.py:68` | RETURN_TO_L2 → KEEP_L2 | `cooldown_ok` ∧ `\|y\| ≤ NEAR_L2` ∧ `\|ψ\| ≤ PSI_L2_LIMIT_DEG` | REQ-FSM-02e, 03a |

`cooldown_ok = (t − last_change_t) ≥ COOLDOWN`는 47행에서 한 번 계산해 다섯 결정이 함께 쓴다. D1–D4는 D0이 거짓일 때만 평가된다(`elif` 사슬).

## 2. MC/DC 방식 — unique-cause (단락 평가 반영)

Python의 `and`는 단락 평가다. 앞 조건이 거짓이면 뒤 조건은 평가되지 않는다. 이번 설계는 **unique-cause MC/DC**로 정했고, 단락 평가는 다음처럼 다룬다.

- 쌍의 두 사례에서 **대상 조건만 값이 다르고, 나머지 조건은 모두 같은 값**이어야 한다. 단락 평가로 실제로는 평가되지 않은 조건도
  "don't care"로 두지 않는다. 입력으로부터 계산한 값이 두 사례에서 같아야 한다(입력 값 기준의 엄격한 unique-cause).
- 결정 결과가 뒤집혀야 하고, **관측 가능한 출력**(다음 FSM 상태)도 달라야 한다. 두 사례의 입력 FSM 상태도 같아야 한다.
  D0처럼 모든 상태에 걸치는 결정에서, 출력이 다른 이유가 입력 상태 차이가 아님을 보장하기 위해서다.
- 해당 결정이 두 사례 모두에서 실제로 평가되어야 한다(D1–D4는 D0이 거짓인 사례만).
- **masking MC/DC로 처리한 쌍은 없다.** 14개 조건 모두 위 조건의 unique-cause 쌍이 존재한다. 결정 하나 안의 조건들은 서로 다른 입력
  (시각, front_gap, 센서 bool, y, ψ)에 의존하므로, 결정 안에서 독립적으로 바꿀 수 있다. 예외는 아래 D3의 시각 결합이다.

## 3. 결합 조건 — D3 `cooldown_ok` (확인됨, 코드)

- 운영 코드에서 `FSM` 객체를 만드는 곳은 `fsm.py:35`(`initial_fsm`, KEEP_L2)와 `fsm.py:74`(전이 시 `last_change_t = state_enter_t = t`) 두 곳뿐이다
  (`thesis_v2/baseline`·`improved`·`anomaly`에서 grep으로 확인, `FSM`은 frozen dataclass).
- 따라서 KEEP_L1에서는 항상 `last_change_t == state_enter_t`이다. 그러면 `t − state_enter_t > 0.6`이 참일 때 `t − last_change_t ≥ 0.3`도 반드시 참이 된다.
  D3은 도달 가능한 상태에서 `elapsed > T_KEEP_L1_MIN ∧ right_clear`와 같다. `cooldown_ok`가 결과를 뒤집는 사례(F,T,T)는 도달할 수 없다.
- unique-cause로도 masking으로도 이 조건의 독립 영향은 **도달 가능한 입력으로 보일 수 없다**(강한 결합). MC/DC 표의 D3 `cooldown_ok` 쌍
  (`test_keep_l1_to_return_positive` vs `test_cooldown_blocks_keep_l1_to_return`)은 테스트가 `last_change_t ≠ state_enter_t`인 객체를 직접 만들어 성립시킨 것이다.
  코드의 논리식 자체가 맞는지는 이 쌍으로 확인되지만, 운영 중 이 조건이 결과를 바꾸는 경우는 없다.
- 기존 D3 `right_clear` 쌍도 같은 형태(직접 만든 객체)였다. 이 조건은 시각과 무관하므로 도달 가능한 형태의 쌍도 만들 수 있다. 그러나 이번 지시는 "빠진 쌍만 추가"이고 쌍 자체는
  이미 있으므로 추가하지 않았다. 새 D3 테스트(`elapsed` 쌍)는 도달 가능한 형태(`last_change_t == state_enter_t`)로 만들었다.
- 처리: 코드는 바꾸지 않는다(baseline 동결, REQ-FSM-03a가 다섯 전이 모두에 쿨다운을 요구). 이 결합은 검증 관찰로만 기록한다.

## 4. 추가한 테스트 (`thesis_v2/tests/test_fsm_mcdc.py`)

각 테스트는 쌍의 두 사례를 함께 실행하고 다음을 **테스트 안에서** 검사한다.
(1) SPEC을 config 상수로 다시 적은 조건 벡터에서 대상 조건 하나만 다르다(`_assert_unique_cause`).
(2) `step()` 출력이 전이/유지로 뒤집힌다.

| 테스트 | REQ | 참 사례 → 출력 | 거짓 사례 → 출력 | 비고 |
|---|---|---|---|---|
| `test_mcdc_d1_front_gap_lt_g_trig` | REQ-FSM-02a | fg = G_TRIG − 0.01 → EVADE_L | fg = G_TRIG(경계, 엄격 부등호) → KEEP_L2 | left_clear=True, 쿨다운 만료 |
| `test_mcdc_d3_elapsed_gt_t_keep_l1_min_reachable_form` | REQ-FSM-02d | 경과 0.7 s → RETURN_TO_L2 | 경과 0.5 s → KEEP_L1 | 도달 가능한 형태. 경계 부동소수 오차를 피하려고 ±0.1 s |
| `test_mcdc_d4_abs_y_le_near_l2` | REQ-FSM-02e([개정] 0.08) | y = 0.07 → KEEP_L2 | y = 0.09 → RETURN_TO_L2 | ψ=0 |

추적표 `thesis_v2/tests/TRACEABILITY.md`의 REQ-FSM-02a·02d·02e 행에 추가했다.

## 5. 검증 도구 (`mcdc/mcdc_trace.py`)

- pytest 플러그인이다. `fsm.step`을 감싸 원래 함수를 그대로 호출하고, 입력에서 D0–D4의 조건 값, 평가 여부(단락·`elif` 반영), 입력·출력 상태를 기록한다.
- 조건 재진술이 코드와 어긋나는지 점검한다. 재진술로 예측한 다음 상태와 실제 다음 상태를 매 호출 비교하고, 하나라도 다르면 세션을 실패시킨다. 이번 측정에서 불일치는 0건이었다.
- 재현(저장소 루트, PowerShell):
  ```powershell
  $env:PYTHONPATH="docs/verification/mcdc"
  $env:MCDC_OUT="docs/verification/mcdc/mcdc_before_existing_tests.json"; .\.venv\Scripts\python -m pytest thesis_v2/tests/test_fsm.py -p mcdc_trace -q -s
  $env:MCDC_OUT="docs/verification/mcdc/mcdc_after_added_tests.json"; .\.venv\Scripts\python -m pytest thesis_v2/tests/test_fsm.py thesis_v2/tests/test_fsm_mcdc.py -p mcdc_trace -q -s
  .\.venv\Scripts\python docs/verification/mcdc/make_mcdc_tables.py docs/verification/mcdc/mcdc_before_existing_tests.json docs/verification/mcdc/mcdc_after_added_tests.json docs/verification/mcdc/MCDC_TABLES.md
  ```
- 측정 범위는 FSM 단위 테스트(`test_fsm.py`, `test_fsm_mcdc.py`)뿐이다. 폐루프 테스트도 `step()`을 수천 번 호출하지만, 설계된 쌍이 아니므로 MC/DC 근거로 쓰지 않았다.

## 6. ISO 26262-6과의 개념 대응 (준수 주장 아님)

MC/DC는 ISO 26262-6의 단위 수준 구조적 커버리지 지표 중 가장 엄격한 것이다(일반적으로 알려진 내용이며, 표준 원문과 대조하지 않았다).
이 문서는 그 **개념**을 FSM의 복합 조건에 적용한 기록이다. 표준이 요구하는 절차(ASIL 할당, 도구 적격성 확인, 독립성 등)는 수행하지 않았으므로 준수를 주장하지 않는다.
