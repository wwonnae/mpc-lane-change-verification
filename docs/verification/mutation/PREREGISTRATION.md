# Mutation testing 사전 선언 (실행 전 고정)

작성 2026-10-13, 3층PC109. 이 문서는 **1차 실행 전에** 커밋한다. 실행 후 변경 규칙은 §10에 있다.
도구: `mutate.py`(직접 작성, TOOL_VERSION 1). 자체 테스트: `test_mutate.py`(29개 통과).

## 1. 목적

기존 테스트(`thesis_v2/tests`, `thesis_v2/anomaly/tests`, golden)가 제어·탐지 코드의 작은 결함(변이)을 얼마나 잡는지 측정한다. 생존한 변이는 등가 변이와 테스트 공백으로 나누고, 테스트 공백은 테스트를 보강해 다시 측정한다.
제품 코드와 기존 테스트는 수정하지 않는다. 변이는 저장소 밖 임시 사본에서만 만든다.

## 2. 범위 (생성 변이 600개, `python docs/verification/mutation/mutate.py list`)

| 모듈 | 파일·행 | 변이 수 | L1 테스트 | L3(golden) |
|---|---|---:|---|---|
| fsm | `thesis_v2/baseline/fsm.py:33-75`(initial_fsm, target_line_y, step) | 52 | `test_fsm.py`, `test_fsm_mcdc.py` | 적용 |
| detector_a | `thesis_v2/anomaly/detector_a.py:86-215`(추적기, 잔차, CUSUM, 경보 판정) | 197 | `anomaly/tests/test_detector_a.py` | 해당 없음 |
| closed_loop | `thesis_v2/anomaly/closed_loop.py:169-216`(경보 → 정책 결정), `:344-362`(`episode_row`, 불필요 정지 분류) | 63 | `anomaly/tests/test_closed_loop.py` | 해당 없음 |
| baseline_mpc | `thesis_v2/baseline/mpc.py:1-264`(전체) | 288 | `test_mpc.py` | 적용 |

- **제외**: `thesis_v2/improved/mpc.py`. golden 기준값은 baseline v1.1 경로만 실행한다(`thesis_v2/tests/golden/README.md`). 그래서 improved MPC는 L3 판정을 할 수 없다.
- detector_a·closed_loop는 baseline 경로가 아니므로 L3가 "해당 없음"이다. 두 모듈은 L1·L2로만 판정한다.

## 3. 변이 연산자 (8종, 원본 문자열의 해당 구간만 바꿈)

| ID | 변이 | 포함 이유 |
|---|---|---|
| rel | `<`↔`<=`, `>`↔`>=`, `==`↔`!=`, `is`↔`is not`, `in`↔`not in` | 가드·임계 판정은 경계에서 틀리기 쉽다. SPEC은 엄격/비엄격 부등호를 구분한다(예: REQ-FSM-02a `front_gap<1.2`) |
| bool | 하나의 `and`/`or` 연쇄 전체를 반대 연산자로 | 복합 가드 전체의 의미 변경 |
| operand_drop | 연쇄에서 피연산자 하나 제거 | MC/DC와 같은 관점. 각 조건이 실제로 필요한지 확인 |
| not_rm | `not x` → `x` | 부정 조건(D0 `not left_clear`, `not _lat_overlap` 등) |
| const | 정수·실수 상수: 0이 아니면 0, 0이면 1 | 임계값·초기값·하한 |
| arith | `+`↔`-`, `*`↔`/`(`+=` 등 포함) | CUSUM 누적, 잔차, 예측식, QP 계수 |
| return_none | 값을 반환하는 `return` → `return None` | 판정 결과 전달 누락 |
| assign_del | 대입문 → `pass` | 상태 갱신 누락(새 FSM 상태, 추적 평균, 정책 플래그 등) |

## 4. 판정 층과 결과 분류

- **L1**: 위 표의 모듈 단위 테스트.
- **L2**: 전체 pytest(`thesis_v2/tests`, `thesis_v2/anomaly/tests`)에서 **golden 테스트 `test_check_golden.py`를 뺀 것**. L3와 겹치지 않게 하려는 것이다.
- **L3**: `python -m thesis_v2.tests.check_golden`. 출력의 시나리오별 `max|diff|`(rad)를 원자료에 기록한다.
- 층은 L1 → L2 → L3 순서로 실행하고, **처음 잡힌 층**을 기록한다. 각 pytest는 `-x`(첫 실패에서 중단)로 돌린다.
- **분류**:
  - `killed`: 단언 실패
  - `killed_exception`: 단언이 아닌 예외. 수집·import 오류 포함
  - `timeout`
  - `survived`
  - `invalid`: 생성 단계의 구문 오류 등. 현재 0개
  - 타임아웃과 예외는 따로 센다.
- **타임아웃**: 층마다 max(10 s, 깨끗한 사본에서 측정한 시간 × 5). 측정값과 타임아웃 값은 원자료에 기록한다.
- 실행 전에 깨끗한 사본이 L1·L2·L3를 모두 통과해야 한다. 아니면 중단한다.
- 바이트코드 캐시를 막는다(`PYTHONDONTWRITEBYTECODE=1`, 매 변이 전 `__pycache__` 삭제). 캐시를 허용하면 같은 길이의 변이가 이전 코드로 실행되어 생존으로 잘못 기록되는 것을 스크래치 실험으로 확인했다.
- 실행 전후의 PC 부하(CPU LoadPercentage, CPU 시간 상위 프로세스)와 git 커밋·dirty 여부를 원자료에 남긴다.

## 5. 생존 변이 처리와 점수

**분류 규칙(모듈별)**:

- **fsm, detector_a, closed_loop**: 연산자 종류와 상관없이 생존 변이마다 다음 둘 중 하나로 분류한다.
  - 등가: 근거를 적고 "판단"으로 표시해 `equivalence.json`에 남긴다.
  - 테스트 공백: 보강 대상이다.
- **baseline_mpc**: 사람의 등가 판단은 **분기·논리·return·대입 삭제** 변이(rel, bool, operand_drop, not_rm, return_none, assign_del)에만 한다. 이 경우 등가(판단, 근거) 아니면 테스트 공백으로 분류한다.
  - **상수·산술(const, arith) 생존 변이**는 등가로 판단하지 않는다. L3의 조향각 최대 차이(`max|diff|`, rad, 원자료에 자동 기록)로만 분류한다.
    - "허용오차 내 생존(측정값)": `max|diff|` ≤ 1e-3 rad. 0인 경우와 0보다 큰 경우를 나눠 센다.
    - "허용오차 밖·golden 통과(조사)": `max|diff|` > 1e-3인데 L3가 통과한 경우. 원리상 생기면 안 되므로 원인을 조사해 따로 분류한다.
  - baseline_mpc 생존 변이 중 테스트 공백이 분명한 것은 다른 모듈과 같이 보강한다.

**점수**(보강 전·후 모두):
- 원점수 = 잡힌 수 / (전체 − 무효). 잡힌 수 = killed + killed_exception + timeout. 타임아웃과 예외는 따로도 센다.
- 등가 제외 점수 = 잡힌 수 / (전체 − 무효 − 등가(판단) 수).
- baseline_mpc의 "허용오차 내 생존(측정값)"은 등가로 빼지 않는다. 대신 그 수를 따로 보인다.

**커버리지 대조**: 깨끗한 사본에서 coverage로 실행된 줄을 기록한다. 실행된 줄에서 생존한 변이를 목록으로 만든다.

## 6. 도구 신뢰성 (자체 테스트 `test_mutate.py`)

- **연산자 단위**: 고정 코드 조각에서 연산자마다 기대한 소스가 나오는지 확인한다(16개).
- **적용 확인**: 대상 4개 모듈의 모든 변이가 다음을 만족하는지 확인한다.
  - 파싱되고, 줄 수가 같다.
  - 바뀐 줄이 편집 구간 안에만 있다.
  - 원본 토큰이 기록된 `original`과 같다.
- **지점 수 대조**: 연산자별 변이 수가 따로 작성한 AST 계산과 같은지 확인한다.
- **비ASCII 회귀**: AST `col_offset`은 UTF-8 바이트 단위다. 그래서 한글이 앞에 있는 줄에서도 정확한 위치를 바꾸는지 확인한다(§11 버그 1의 회귀 테스트).
- **바이트코드 캐시**: 같은 길이의 변이가 잡히는지 확인한다.
- **기준 변이**: 깨끗한 사본은 L1을 통과하고, `fsm.py:55` `<`→`<=`는 `test_mcdc_d1`이 잡는지 확인한다. 실행 후 원본 파일 해시가 그대로인지도 확인한다.

## 7. 예측 (실행 후 `RESULTS.md`에서 맞음/틀림 대조)

| # | 대상 | 예측 | 근거 |
|---|---|---|---|
| P1 | `fsm.py:64` D3의 `cooldown_ok` 관련 변이 | 생존(도달 가능한 상태에서 등가) | `docs/verification/MCDC_FSM.md` §3 |
| P1' | `fsm.py:64` D3 `cooldown_ok` 피연산자 제거 | **L1에서 잡힘**(P1과 반대) | `test_fsm.py:105-110`이 도달 불가 형태(last_change_t ≠ state_enter_t)로 쿨다운을 막는다 |
| P2 | `fsm.py:47` `>=`→`>`, `:51` `<`→`<=`, `:59` `<=`→`<`, `:64` `>`→`>=`, `:68` `<=`→`<`(y, ψ 두 개) | 생존, **테스트 공백** | 기존 테스트가 경계에서 ±0.01 s 또는 ±0.01 m 이상 떨어진 값만 쓴다 |
| P2' | `fsm.py:55` `<`→`<=` | L1에서 잡힘 | `test_mcdc_d1`이 `front_gap = G_TRIG`를 쓴다 |
| P3 | `fsm.py:35` `initial_fsm`의 `state_enter_t=0.0` 상수(0.0 → 1.0) | 생존, **등가(판단)** — fsm은 연산자와 상관없이 판단하므로 §5 규칙과 맞음 | `state_enter_t`는 D3(KEEP_L1)에서만 읽는다(`fsm.py:63`). 초기 상태 KEEP_L2에서는 읽지 않고, KEEP_L1로 가려면 전이가 두 번 필요하며 전이마다 `state_enter_t = t`로 다시 설정된다(`fsm.py:74`) |
| P4 | `detector_a.py:207` `m > 0.5`→`>=` | 생존, 등가(판단) | m은 0.0 또는 1.0 |
| P5 | detector_a의 연속값 경계 비교(`_lat_overlap` 87행, BOUNDARY_MARGIN 141·143·155·157행, 추적 게이트 124·125행, 경보 `score > threshold` 214행)의 rel 변이 | 생존 | 노이즈가 있는 연속값이라 정확히 같은 값이 나오기 어렵다. 214행은 §13 "score > h" 정의라 경계 테스트 공백일 수도 있다 |
| P6 | `detector_a.py:126-127` 추적 평균 갱신 대입 삭제 | 생존, 테스트 공백 | 추적 평균을 직접 확인하는 테스트가 없다(추정) |
| P7 | closed_loop P2 채널 분기(181-193행)의 변이 | 대부분 잡힘 | `test_closed_loop.py:65-114`가 ey·rc·lc·stop 분기를 각각 검사 |
| P7' | `closed_loop.py:355` `first_alarm_step < onset` → `<=` | 생존, 테스트 공백 | 경보 = onset 경계를 쓰는 테스트가 없다(추정) |
| M1 | `mpc.py:118·129·135`의 placeholder `vals.append(0.0)`과 `:196-200`의 l/u placeholder | 생존, `max|diff|`=0 | 매 solve에서 Ax·l·u로 덮어쓴다(`mpc.py:215-236`, `:243-244`) |
| M2 | `mpc.py:206·253·262`(계산 시간) const·arith·대입 삭제 | 생존, `max|diff|`=0 | golden과 테스트는 조향만 비교하고 계산 시간은 비교하지 않는다 |
| M3 | `mpc.py:258-261` fallback 분기 | 대부분 생존(L3 차이 0) 또는 `test_fallback_unit_is_rad_per_meter`에서 일부 잡힘 | golden 시나리오는 solver 실패가 없어 fallback이 실행되지 않는다(추정) |
| M4 | `mpc.py:208` `max(0.05, …)`의 0.05 → 0 | 생존, `max|diff|`=0 | golden·테스트에서 v ≥ 0.3이라 하한이 쓰이지 않는다(REQ-SIM-03 v0 범위) |
| M5 | `mpc.py:149·154`(ψ·δ 제약 행 계수 1.0) | 생존, `max|diff|` 0 또는 작음 | 시나리오에서 ψ·δ 상·하한 제약이 활성되지 않으면 영향이 없다(추정) |
| M6 | Hessian·동역학 계수(84·85·94·96·217·223·225·230·241행)의 const·arith | 대부분 L1(`test_mpc.py`) 또는 L3에서 잡힘 | 해와 조향이 직접 바뀐다 |

## 8. LLM 보조 테스트 보강 절차

1. 1차 실행 뒤 생존 변이를 분류한다(등가 / 테스트 공백).
2. Claude Code(이 세션)가 테스트 공백 변이마다 테스트를 제안한다. 새 파일로만 추가한다.
   - `thesis_v2/tests/test_mutation_gaps_*.py`
   - `thesis_v2/anomaly/tests/test_mutation_gaps_*.py`
3. 수락 기준 ①–③은 자동으로 확인한다.
   - ① 원본에서 통과
   - ② 대상 변이를 잡음(임시 사본에서 실행)
   - ③ docstring에 REQ ID 또는 DESIGN 절이 있음
4. 수락 기준 ④(내부 변수가 아니라 관찰 가능한 동작을 확인)는 **사용자가 검토**한다. 생존 변이별로 대상 변이, 확인하는 관찰 가능한 동작, ④ 판단 근거를 한 줄씩 정리한 요약표를 드리고, 실제 검토 방식을 기록에 사실대로 남긴다.
5. 제안·수락·거절·거절 사유·사람이 고친 부분을 `llm_tests_log.json`에 남긴다. 이 테스트들이 LLM 제안에서 나왔다는 사실을 `RESULTS.md`에 명시한다.
6. 수락된 테스트를 넣은 뒤 2차 실행(같은 범위·연산자·층·타임아웃 규칙)을 한다.
   - 테스트 수가 바뀌면 다음을 함께 처리한다: README 테스트 수 갱신, 추적 매트릭스 재생성, 세 `--check`(trace·uml·safety) 통과.

## 9. CI

- **전체 변이 실행은 CI에서 돌리지 않는다.** 1회에 약 1시간 안팎(추정)이 걸리고, 타임아웃 판정이 러너 부하에 따라 달라질 수 있어 결과가 실행 환경에 묶이기 때문이다.
- CI에서는 다음만 확인한다.
  - 저장된 원자료(`raw/*.json`)와 생성 표가 일치하는지: `make_mutation_tables.py --check`(B단계에서 추가)
  - 도구 자체 테스트 `test_mutate.py`

## 10. 실행 후 사전 선언을 바꿔야 할 때

- 이 문서는 1차 실행 전에 커밋한 뒤 **고치지 않는다**. 커밋 해시가 사전 선언의 기준이다.
- 실행 후 범위·연산자·층·타임아웃·분류 규칙·점수 규칙을 바꿔야 하면 다음 절차를 따른다.
  1. `RESULTS.md`에 "사전 선언 변경" 절을 두고 변경 내용, 사유, 결과를 본 뒤의 변경인지 여부를 적는다.
  2. 바뀐 규칙의 결과와 원래 규칙의 결과를 **둘 다** 보고한다.
  3. 원래 규칙으로 실행한 원자료는 지우지 않는다.
- 도구 버그가 실행 후 발견되면 다음과 같이 처리한다.
  1. 버그와 수정을 기록한다.
  2. 영향받은 실행을 다시 한다. 이전 원자료는 별도 파일로 남긴다.
  3. 버그가 결과에 준 영향을 비교해 보고한다.
- 예측(§7)은 실행 후에도 바꾸지 않는다. 맞음/틀림만 대조한다.

## 11. 사전 선언 전 도구 수정 기록 (실행 전, 2026-10-13)

도구를 처음 작성한 직후 `mutate.py list`로 변이를 생성해 보니 600개 중 **9개가 무효**였다. 원인은 다음 두 버그였고, 둘 다 고친 뒤 무효가 0이 되었다. 변이 실행은 이 수정 뒤에만 한다.

1. **바이트 열과 문자 열 혼동**
   - 증상: AST의 `col_offset`·`end_col_offset`은 UTF-8 **바이트** 단위인데, 이를 문자 위치로 썼다. 그래서 한글이 있는 줄에서 편집 위치가 어긋났다.
   - 무효 3개: `closed_loop.py:205·207·209`의 `outcome = "충돌"` 등 대입 삭제. 바꾼 결과가 파싱되지 않았다.
   - 같은 원인으로 위치가 어긋났지만 우연히 파싱되는 변이가 있었다면 **엉뚱한 곳이 조용히 변이**됐을 수 있다.
   - 수정: AST 위치를 문자 위치로 바꾸는 `Source.cpos`를 추가했다.
   - 회귀 테스트: `test_non_ascii_line_offsets`, 그리고 모든 대상 변이에 대해 원본 토큰이 기록된 `original`과 같은지 확인하는 테스트.
2. **여러 줄 구간에서 줄 수 변경**
   - 증상: 줄 연속(`\`)이 있는 피연산자 제거(`detector_a.py:167-168`)와 여러 줄 return 값 교체(`detector_a.py:214`, `closed_loop.py:358`, `mpc.py:254·263`)에서 지운 구간의 줄바꿈이 사라졌다.
   - 무효 6개.
   - 수정: 지운 줄바꿈 수만큼 줄 연속으로 채워 이후 줄 번호를 유지한다(`Source.apply`).
   - 회귀 테스트: 모든 대상 변이에서 줄 수가 같은지 확인한다.

**바이트코드 캐시 대조 실험(스크래치, 저장소 밖)**:
- 방법: 임시 폴더에 `modx.py`(`return 1 + 2`)와 그 테스트를 두고, 캐시를 허용한 채 pytest를 한 번 실행했다(rc 0). 이어서 같은 길이의 변이 `1 - 2`로 바꾸고, 수정 시각을 원래 값으로 되돌려 "같은 초 안의 쓰기"를 재현한 뒤 다시 실행했다.
- 결과: **rc 0**. 이전 바이트코드가 쓰여 변이가 가려졌다.
- 그래서 실행기는 `PYTHONDONTWRITEBYTECODE=1`로 돌리고 변이마다 `__pycache__`를 지운다(§4).
- 회귀 테스트: `test_same_length_mutation_is_not_masked_by_bytecode_cache`.

