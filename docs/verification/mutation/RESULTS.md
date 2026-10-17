# Mutation testing 결과

이 문서는 B단계(1차 실행 → 생존 분류 → LLM 보조 테스트 보강 → 2차 실행)에서 작성한다.

**상태(2026-10-15): B단계 완료.**
- 1차 실행 완료: 3층PC109, 커밋 `78e0936`, 600개 중 잡힘 471·생존 129. 원자료 [raw/run_before.json](raw/run_before.json)
- 노트북 재확인 완료: 1차 생존 129개 재실행, 129개 모두 1차와 같음. 아래 절.
- 생존 변이 분류 확정(사용자 검토 반영): [equivalence.json](equivalence.json)(`status: confirmed`). 아래 "생존 변이 분류(확정)" 절.
- 테스트 보강 완료: closed_loop 17, detector_a 14, fsm 4, MPC 10 = 45개 수락(2026-10-13, 아래 "LLM 보조 테스트").
- **2차 실행 완료**(2026-10-14 16:04–16:51, 3층PC109, 커밋 `6971d64`): 잡힘 531·생존 69. 보강 대상 60개 모두 잡힘. 1차에서 잡혔는데 2차에서 생존한 변이 0개.
  원자료 [raw/run_after.json](raw/run_after.json). 아래 "2차 실행(보강 후)" 절.
- **time_limit kill 재확인 완료**(사전 선언 변경 5): 대상 127개, kill 유지 127, 재검토 0. 원자료 [raw/run_after_tl_recheck.json](raw/run_after_tl_recheck.json).
- 모든 표의 수치는 [make_mutation_tables.py](make_mutation_tables.py)가 원자료에서 만든 [MUTATION_TABLES.md](MUTATION_TABLES.md)에 있다(CI `--check`).

## 요약

| 모듈 | 원점수 1차 → 2차 | 등가 제외 점수 1차 → 2차 | 2차 생존(분류) |
|---|---|---|---|
| fsm | 86.5% → **94.2%** | 91.8% → **100.0%** (49/49) | 3 (등가 3) |
| detector_a | 74.1% → **85.3%** | 81.6% → **93.9%** (168/179) | 29 (등가 18, 경계 동치 미검증 9, 도달 불가 입력만 2) |
| closed_loop | 50.8% → **90.5%** | 54.2% → **96.6%** (57/59) | 6 (등가 4, 도달 불가 입력만 2) |
| baseline_mpc | 86.1% → **89.2%** | 88.6% → **91.8%** (257/280) | 31 (등가 8, 측정 max\|diff\|=0 20, 보류 2, 테스트 공백 1 — `:283`, 보강하지 않기로 함) |
| **합계** | 78.5% → **88.5%** | 83.1% → **93.7%** (531/567) | 69 |

- 1차 → 2차 변화는 보강 대상 60개(survived → killed 52, → killed_exception 8)뿐이다. 그 밖의 540개는 상태가 같다. 처음 잡힌 층이 바뀐 것은 2개(`baseline_mpc:219`·`:220`, L3 → L2, 새 MPC 보강 테스트가 golden보다 먼저 잡음)다.
- 새로 잡힌 60개는 모두 L2에서 처음 잡혔다. 보강 테스트는 `test_mutation_gaps_*.py`라는 새 파일에 있고, L1은 모듈의 기존 테스트 파일만 실행하기 때문이다(사전 선언 §2·§8).

## 1차 생존 변이 재실행 — 다른 PC에서 재현성 확인 (2차 실행 전, 2026-10-13)

**결론: 1차 생존 변이 129개를 노트북에서 다시 실행한 결과, 129개 모두 1차와 같은 `survived`였다. L3를 실행한 47개(fsm 7, baseline_mpc 40)의 `max|diff|` 값도 1차와 모두 같았다.** 원자료: [raw/run_before_recheck_laptop.json](raw/run_before_recheck_laptop.json)

| 항목 | 1차 실행(`raw/run_before.json`) | 재실행(`raw/run_before_recheck_laptop.json`) |
|---|---|---|
| PC | 3층PC109 | DESKTOP-MDCKRJS(노트북) |
| 커밋 | `78e0936`, 깨끗한 트리 | `0b14fa9`, 실행 전후 모두 깨끗한 트리. `78e0936`과 다른 점은 `raw/run_before.json` 추가뿐이다. 따라서 테스트·제품 코드·`mutate.py`는 1차와 같고, 새 테스트는 넣기 전이다 |
| Python / 패키지 | 3.9.13 / **기록 없음**(아래 한계) | `.venv` 3.9.12 / numpy 2.0.2, scipy 1.13.1, osqp 1.1.1, pytest 8.4.2(`thesis_v2/requirements-py39.txt` 고정 조합, 원자료 `packages`) |
| 시각 | 11:32–12:20(600개) | 16:22–16:55(129개) |
| 깨끗한 사본 L2 / L3 시간 | 15.25 s / 0.50 s | 17.44 s / 0.54 s |
| L2 타임아웃(규칙: max(10 s, 5×깨끗한 사본)) | 76.25 s | 87.2 s(노트북에서 같은 규칙으로 측정) |
| CPU LoadPercentage 실행 전 / 후 | 원자료 참조 | 18 / 5 |
| 대상 | 600개 | 1차 `survived` 129개(detector_a 51, baseline_mpc 40, closed_loop 31, fsm 7) |
| 결과 | `survived` 129 | `survived` 129. 1차와 다른 것 0개 |

- **방법**: [recheck_survivors.py](recheck_survivors.py)는 **`mutate.py`를 고치지 않고 그 함수만 호출한다**. 쓰는 함수는 `generate`, `validate`, `mutated_text`, `make_copy`, `run_pytest`, `run_golden`, `pc_load`, `git_state`다.
  - 1차와 같은 것: 층(L1→L2→L3), `-x`, 바이트코드 캐시 차단, 타임아웃 규칙
  - 1차와 다른 것:
    - 대상을 1차 생존 ID로 한정한다.
    - 커버리지는 수집하지 않는다. 재현성 확인 범위 밖이고, `.venv`에 coverage도 없다.
  - 실행 전에 129개를 재생성해, 줄·연산자·원본·치환이 1차 기록과 모두 같은지 확인했다.
  - 드라이버 sha256 `772b11dc…`, `mutate.py` sha256 `76b4bd17…`(전체 값은 원자료 `driver_sha256`, `mutate_py_sha256`).
  - 실행 뒤 드라이버의 **docstring만** 고쳤다("mutate.py를 고치지 않고 함수만 호출" 문구 추가). 그래서 저장소 판의 sha256은 `f8ac6fcb…`로 원자료 값과 다르다.
    - 확인: 실행 판과 저장소 판의 AST가 docstring을 빼면 같다(`ast.dump` 비교).
- **처음 잡힌 층**: 모두 없음. detector_a·closed_loop는 L1·L2 통과(L3 해당 없음). fsm·baseline_mpc는 L1·L2·L3 통과.
- **L3 `max|diff|`가 0이 아닌 생존 변이**(4개, 모두 `thesis_v2/baseline/mpc.py`): 아래 표의 "행"은 원본 파일의 행 번호이고, ID 뒤의 숫자는 변이 일련번호다. 둘은 다른 값이다. 198만 우연히 같다.

  | 변이 ID | 행 | 연산자 | 변이 전 | 변이 후 | 1차 `max\|diff\|` (rad) | 재실행 `max\|diff\|` (rad) |
  |---|---:|---|---|---|---:|---:|
  | `baseline_mpc:133` | 149 | const `1.0`→`0.0` | `vals.append(1.0)` | `vals.append(0.0)` | 8e-06 | 8e-06 |
  | `baseline_mpc:165` | 180 | arith `+`→`-` | `row_psi = row_y + 1` | `row_psi = row_y - 1` | 1.2e-05 | 1.2e-05 |
  | `baseline_mpc:198` | 198 | const `1`→`0` | `for i in range(1, self.N + 1):` | `for i in range(0, self.N + 1):` | 1.2e-05 | 1.2e-05 |
  | `baseline_mpc:246` | 234 | const `1`→`0` | `for i in range(1, N + 1):` | `for i in range(0, N + 1):` | 1.52e-04 | 1.52e-04 |

  - 149행의 전체 줄: `rows.append(r); cols.append(_idx_psi(i)); vals.append(1.0)`
  - 모두 허용오차 1e-3 rad 이하다. 분류(§5)는 아직 하지 않았다.
- **한계**:
  - 이 확인은 1차 **생존** 변이에만 해당한다. 1차에서 잡힌 471개는 다시 실행하지 않았다.
  - **1차 실행(3층PC109)의 패키지 버전은 기록되지 않았다.**
    - `raw/run_before.json`에는 Python 버전(3.9.13)만 있고 패키지 버전은 없다. `mutate.py`가 패키지 버전을 기록하지 않기 때문이다.
    - 그래서 두 실행의 패키지가 같았는지는 확인되지 않았다.
    - 추정: 3층PC109 `.venv`의 수치 패키지는 CI 고정 목록과 같았을 것이다.
      - 근거: 같은 날 1차 실행 전의 로컬 확인 기록, `docs/verification/CI.md:119`. 3층PC109 `.venv`가 Python 3.9.13, numpy 2.0.2, scipy 1.13.1, osqp 1.1.1, torch 2.8.0+cpu로 기록되어 있다. 이 버전들은 CI 고정 목록(`docs/verification/CI.md:14`, `thesis_v2/requirements-py39.txt`)과 같다.
      - 확인되지 않은 것: 그 `.venv`를 고정 목록 파일로 설치했는지, pytest 버전, 그 기록과 1차 실행(11:32) 사이에 환경이 바뀌지 않았는지.

## 사전 선언 변경 (PREREGISTRATION §10)

1. **범주 추가 — "경계 동치 미검증(저위험)"** (2026-10-13, 1차 실행 결과를 본 뒤의 변경, 사용자 지시)
   - 내용: 엄격/비엄격 부등호만 바뀐 생존 변이 중, 비교 대상이 연속값이라 정확히 같은 값이 사실상 나오지 않는 것은 등가로 분류하지 않고 이 범주로 분류한다. **분모에서 빼지 않는다**(등가 제외 점수에서도 분모에 남는다).
   - 이 범주에 넣지 않는 경계(→ 테스트 공백):
     - SPEC 요구사항으로 정해진 경계(예: REQ-FSM-02a–02e)
     - 정수 경계
     - clip이나 대입으로 정확한 값이 실제로 나오는 경계(예: front_gap = 0.0, v = 0.0)
   - 사유: 사전 선언 §5는 fsm·detector_a·closed_loop 생존 변이를 등가 또는 테스트 공백 둘로만 나눴다. 그런데 연속값 경계 변이는 어떤 입력으로도 차이가 없다고 증명할 수 없어 등가가 아니다. 그렇다고 제품 경로에서 그 입력이 사실상 생기지 않으니, 테스트 공백으로 세면 위험도가 과장된다.
   - 원래 규칙의 결과도 함께 보고한다(§10-2). 원래 규칙에서는 이 범주가 모두 테스트 공백이다.
2. **범주 추가 — "보류(외부 라이브러리 의존)"** (2026-10-13, 결과를 본 뒤의 변경, 사용자 결정) — `baseline_mpc:194`, `:196`(`mpc.py:196-197` setup 시점 l·u placeholder 대입 삭제)
   - 내용: 저장소 코드만으로 등가를 증명할 수 없다. 남는 차이가 OSQP 내부 상태(setup 때 제약 종류에 따른 rho 벡터·KKT 분해)뿐이기 때문이다. **분모에 남긴다.**
   - 근거로 기록하는 실험: [mpc_setup_experiment.py](mpc_setup_experiment.py), 결과 [raw/mpc_setup_experiment.json](raw/mpc_setup_experiment.json). 444회 solve(fallback 186회 포함)의 출력이 원본과 비트 단위로 같았다. 코드 증명이 아니다.
   - 사유: 사전 선언 §5는 baseline_mpc 대입 삭제 변이를 등가(판단) 또는 테스트 공백으로만 나눴다. 이 둘은 코드로 등가를 보일 수 없고, 잡는 테스트가 가능한지도 불확실하다.
   - 원래 규칙으로는 두 개 모두 테스트 공백이다.
3. **범주 추가 — "도달 불가 입력에서만 차이"** (2026-10-13, 결과를 본 뒤의 변경, 사용자 결정) — `detector_a:140`, `:143`, `closed_loop:055`, `:058`
   - 내용: 제품 코드가 만들지 않는 입력에서만 동작(예외)이 다른 변이. **분모에 남기고, 테스트는 추가하지 않는다.**
   - 테스트를 추가하지 않는 이유: 이 변이를 잡는 테스트는 점수만 올리고, 제품 동작의 결함을 막지 못하는 저가치 테스트다.
   - 각 항목이 도달 불가인 근거(코드 행)는 `equivalence.json`의 `reason`·`evidence`에 있다.
   - 원래 규칙으로는 네 개 모두 테스트 공백이다.
4. 위 1–3은 모두 분모에 남는다. 그래서 **원점수와 등가 제외 점수는 원래 규칙과 바뀐 규칙에서 같다**. 원래 규칙에서는 1–3의 15개(9 + 2 + 4)가 모두 테스트 공백으로 세어진다.
5. **2차 실행 환경 조건과 kill 재확인 규칙 추가** (2026-10-14, 1차 실행 결과를 본 뒤의 변경, 사용자 결정) — **결과: 대상 127개 모두 kill 유지, 재검토 0. 그래서 원래 규칙과 바뀐 규칙의 결과가 같다**(아래 "2차 실행" 절)
   - 배경: run #6 조사(`docs/verification/ci/run6_cause/`)에서 확인한 사실이다. improved v2 MPC의 OSQP `time_limit`(0.045 s)이 실행 환경의 일시 정지로 발동하면 같은 입력의 결과가 바뀔 수 있다. 사전 선언 §6(1차)과 PREREGISTRATION.md:119(2차)는 실행 환경 조건을 정하지 않았다.
   - 환경: 2차 실행은 이 항목을 추가한 커밋(run #6 대응 커밋 2) 이후 코드로 한다. 실행 중 같은 PC에서 다른 작업을 하지 않는다. 실행 전후 PC 부하를 기록한다(1차와 같은 `pc_load_before/after`, 야간 실행 스크립트 `overnight_run.sh`의 부하·전원 기록).
   - 테스트 변경: 커밋 2에서 결정론 비교 테스트 등 9개 함수(수집 항목 37개)에 `i5_time_limit_off` fixture를 적용했다(`thesis_v2/conftest.py`, 제품 설정은 그대로). 또 지문 규칙·fixture 보호 테스트 6개 함수(수집 항목 19개)를 추가했다. 2차 실행은 이 테스트 스위트를 쓴다. 범위·연산자·층은 바뀌지 않는다. 타임아웃은 기존 규칙대로 그 실행의 clean run에서 다시 정한다.
   - kill 재확인:
     - 대상: 처음 실패한 테스트가 time_limit이 켜진 I5 on MPC를 쓰는 테스트인 kill. 실행 시점에 그 테스트가 `I5_TIME_LIMIT_SEC` < 1인 상태에서 `enable_i5=True` 인스턴스를 만드는지로 판정한다(`recheck_tl_kills.py`).
     - 방법: 실행 뒤 orig·A(time_limit 1e10) 사본에서 그 테스트를 각 5회 다시 실행한다.
     - 판정: 둘 다 5/5 실패이고 변이 없는 대조가 5/5 통과하면 kill로 유지한다. 아니면 "재검토"로 따로 보고한다.
     - 생존 판정은 재확인하지 않는다(근거: `run6_cause/S5_MUTANT_RESULT.md` 검토).
   - 원래 규칙의 결과: 재확인으로 바뀐 판정이 있으면 원래 규칙의 결과도 함께 보고한다.

## 생존 변이 분류(확정)

[equivalence.json](equivalence.json)은 [build_equiv.py](build_equiv.py)로 만든다. 분류 판단은 스크립트 안의 표에 적혀 있다.

| 모듈 | 생존 | 등가(판단) | 경계 동치 미검증 | 도달 불가 입력만 | 보류(외부 라이브러리) | 테스트 공백 | MPC 측정 0 / >0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| fsm | 7 | 3 | 0 | 0 | 0 | 4 | – |
| detector_a | 51 | 18 | 9 | 2 | 0 | 22 | – |
| closed_loop | 31 | 4 | 0 | 2 | 0 | 25 | – |
| baseline_mpc | 40 | 8 | – | 0 | 2 | 1 | 25 / 4 |
| **합계** | **129** | **33** | **9** | **4** | **2** | **52** | **25 / 4** |

- 등가의 근거 종류(`evidence_type`): 코드 31, 실험 1(`baseline_mpc:147` — scipy 1.13.1, 입력 없는 생성자라 모든 경우), 수치(부동소수점) 근거 1(`fsm:030`).
- 보강 대상(`reinforce`) 60개 = 테스트 공백 52 − `baseline_mpc:283` + baseline_mpc 측정 분류 중 명백한 공백 11 − `:155`·`:209`. 60개 모두 보강 테스트로 잡힌다(아래 "LLM 보조 테스트").
  - 보강하지 않는 3개와 이유(`no_test_reason`): `:283`·`:209`는 명세에 없는 동작(발견 사항 4), `:155`는 출력으로 구분되지 않음(사전 선언대로 측정값 분류 유지).
- 3차 검토(2026-10-13): `fsm:030`을 테스트 공백에서 등가(수치·부동소수점 근거)로 바꿨다. 59행 비교에 들어오는 y는 모든 호출 경로에서 클리핑 없는 `vehicle.y`라 범위를 한정할 수 없지만, abs(y − W) == 0.08이 되는 double y는 전 범위(±inf·NaN 포함)에 없다. 근거는 `equivalence.json`의 `reason`.
- 2차 검토(2026-10-13): `closed_loop:011`을 테스트 공백에서 등가(코드)로 바꿨다. CSV 쓰기 전 메모리에서 first_alarm_channel을 집계·비교하는 곳이 없음을 확인했다. 근거: `common.py:92-101`, `closed_loop.py:182-193`, `:411-440`.
  - 명백한 공백 11개의 표 분류는 사전 선언대로 측정값이다: `:133`, `:155`, `:165`, `:198`, `:209`, `:246`, `:272`, `:273`, `:285`, `:286`, `:287`.

**점수(보강 전, 1차 실행)** — 잡힌 수 = killed + killed_exception(타임아웃 0)

| 모듈 | 전체 | 잡힘 | 원점수 | 등가 | 등가 제외 점수 |
|---|---:|---:|---:|---:|---:|
| fsm | 52 | 45 | 86.5% | 3 | 91.8% (45/49) |
| detector_a | 197 | 146 | 74.1% | 18 | 81.6% (146/179) |
| closed_loop | 63 | 32 | 50.8% | 4 | 54.2% (32/59) |
| baseline_mpc | 288 | 248 | 86.1% | 8 | 88.6% (248/280) |
| **합계** | **600** | **471** | **78.5%** | **33** | **83.1% (471/567)** |

## 2차 실행(보강 후)

**실행 조건**(확인됨, 원자료·로그): `docs/verification/mutation/overnight_run.sh` 1단계, 사용자가 별도 Git Bash 창에서 실행했다. 로그는 [raw/overnight/20261014_160442/](raw/overnight/20261014_160442/)에 있다.

| 항목 | 1차 | 2차 |
|---|---|---|
| 커밋 / git.dirty | `78e0936` / false | `6971d64` / **true**(아래 발견 사항 5 — 저장소 안 로그 폴더의 미추적 파일, 코드 변경 아님) |
| 시각 | 2026-10-13 11:32–12:20 | 2026-10-14 16:04–16:51 |
| CPU LoadPercentage 전 / 후 | 14 / 6 | 6 / 1 |
| 깨끗한 사본 L2 / L3 | 15.25 s / 0.50 s | 22.66 s / 0.53 s(테스트 340 → 359개, 보강 45 + run #6 대응 19) |
| L2 타임아웃 | 76.25 s | 113.3 s(같은 규칙 max(10 s, 5×깨끗한 사본)) |
| 변이 정의 | 600개 | 600개, ID·행·원본·치환이 1차와 모두 같음. 대상 4개 파일·`mutate.py`는 두 커밋 사이에 바뀌지 않았다(`git diff 78e0936 6971d64`) |
| 타임아웃·무효 | 0 / 0 | 0 / 0 |

**점수**: 위 "요약" 표, 상세는 MUTATION_TABLES.md §2.
**처음 잡힌 층**(MUTATION_TABLES.md §3): 2차 L1 420 / L2 111 / L3 0. 1차 L1 420 / L2 49 / L3 2.
**2차 생존 69개 분류**(MUTATION_TABLES.md §5): 모두 1차 분류(equivalence.json)에 있는 ID다. 새로 생존한 변이는 없다.
- 등가(판단) 33(1차와 같음)
- 경계 동치 미검증 9, 도달 불가 입력만 4, 보류 2(모두 1차와 같음)
- baseline_mpc 측정 max|diff|=0 20(1차 25에서 계산 시간 5개 `:272·273·285·286·287`이 보강으로 잡힘)
- 측정 max|diff|>0 0(1차 4개 `:133·165·198·246` 모두 보강으로 잡힘)
- 테스트 공백 1(`baseline_mpc:283`, fallback 클램프 — 발견 사항 4, 명세에 없는 동작이라 보강하지 않음)
- 2차 생존 변이의 L3 max|diff|는 1차와 모두 같았다.

**time_limit kill 재확인**(사전 선언 변경 5, `recheck_tl_kills.py`, 16:51–17:15):
- kill 531개 중, 처음 실패한 테스트가 time_limit이 켜진 I5 MPC를 만드는 것이 127개였다.
  - 첫 실패 테스트 모듈별: `test_detector_a` 95, `test_closed_loop` 19, `test_mutation_gaps_closed_loop` 13.
  - 판정은 실행 시점에 그 테스트를 변이 없는 사본에서 돌려 했다.
- 127개 모두 orig·A(time_limit 1e10)에서 5/5 실패했고, 변이 없는 대조는 5/5 통과했다 → **kill 유지 127, 재검토 0**.
- timeout으로 제외된 kill 0.
- 재확인 스크립트의 코드 범위 확인(`thesis_v2`, results 제외): 깨끗함, HEAD = 실행 커밋.

## 예측 대조 (PREREGISTRATION §7, 1차 실행 기준 — 예측은 보강 전 테스트에 대한 것)

| # | 예측 | 결과(1차) | 판정 |
|---|---|---|---|
| P1 | `fsm.py:64` D3 `cooldown_ok` 관련 변이 생존 | `fsm:035`(cooldown_ok 제거)·`:036`(and→or) 모두 L1에서 잡힘 | **틀림**(P1′이 맞음 — 테스트가 도달 불가 형태로 쿨다운을 막는다) |
| P1′ | 같은 행 cooldown_ok 피연산자 제거는 L1에서 잡힘 | `fsm:035` L1 killed | 맞음 |
| P2 | 경계 rel 6개(47·51·59·64·68×2) 생존, 테스트 공백 | 51·64·68×2의 4개는 생존·공백. 59(`fsm:030`)는 생존이나 등가(수치 근거)로 분류. 47(`fsm:009`)은 L1에서 잡힘 | **부분**(4/6) |
| P2′ | `fsm.py:55` `<`→`<=` L1에서 잡힘 | `fsm:022` L1 killed | 맞음 |
| P3 | `fsm.py:35` state_enter_t 상수 생존, 등가 | `fsm:002` 생존, 등가(판단) | 맞음 |
| P4 | `detector_a.py:207` `>`→`>=` 생존, 등가 | `detector_a:190` 생존, 등가(판단) | 맞음 |
| P5 | detector_a 연속값 경계 rel(87·124·125·141·143·155·157·214) 생존 | 12개 모두 생존(경계 동치 미검증 8, 등가 3, 214행 `:197`은 테스트 공백) | 맞음 |
| P6 | `detector_a.py:126-127` 추적 평균 갱신 대입 삭제 생존, 공백 | 126(`:048`) 생존·공백, 127(`:054`, `tr.n += 1`)은 L1에서 잡힘 | **부분**(1/2) |
| P7 | closed_loop 181-193 대부분 잡힘 | 12개 중 9개 잡힘, 생존 3(override 플래그 대입 삭제 `:018·021·024`) | 맞음 |
| P7′ | `closed_loop.py:355` `<`→`<=` 생존, 공백 | `closed_loop:061` 생존·공백(같은 행 `is not`→`is` 2개도 생존) | 맞음 |
| M1 | placeholder(118·129·135, 196-200) 생존, max\|diff\|=0 | placeholder 값 상수 5개(`:086·103·115·195·197`)와 l/u 대입 삭제 2개(`:194·196`, 보류)는 생존·0. 같은 범위(198-200행)의 루프·행 인덱스·대입 변이 8개 중 4개(`:201-204`)는 잡힘. 생존 4개 중 `:198`(range 시작 1→0)만 1.2e-05이고 `:199·200·205`는 0 | **대체로 맞음**(placeholder 값은 맞음, 같은 범위의 다른 변이는 일부 잡힘·1개 >0) |
| M2 | 계산 시간(206·253·262) 생존, 0 | 단위·부호 변이 5개(`:272·273·285·286·287`) 생존·0. 대입 삭제 3개(`:206·270·284`)는 예외로 L1, `:271`(253 `-`→`+`)은 L2에서 잡힘 | **부분**(5/9) |
| M3 | fallback(258-261) 대부분 생존 또는 일부 잡힘 | 생존 4(`:275-277`, `:283`), 잡힘 5(`:278-282`, test_fallback_unit) | 맞음(예측이 두 경우를 모두 허용) |
| M4 | `mpc.py:208` 0.05→0 생존, 0 | `baseline_mpc:209` 생존·0 | 맞음 |
| M5 | ψ·δ 행 계수(149·154) 생존, 0 또는 작음 | 149(`:133`) 생존·8e-06, 154(`:137`, δ 행)는 L2에서 잡힘 | **부분**(1/2) |
| M6 | Hessian·동역학 계수 대부분 L1 또는 L3에서 잡힘 | 19개 모두 잡힘(L1 8, L2 11, L3 0) | 맞음(잡힘은 맞음, 층은 L3가 아니라 L2) |

- 집계: 맞음 10, 대체로 맞음 1, 부분 4, 틀림 1(P1). 예측은 바꾸지 않았다(§10).

## 커버리지 대조 (PREREGISTRATION §5, MUTATION_TABLES.md §6)

깨끗한 사본에서 L2+L3 범위로 coverage를 돌려 실행된 줄을 기록했다.

- **1차:** 생존 129개 중 실행된 줄에서 생존 112, 실행되지 않은 줄에서 생존 17.
  - detector_a 4: `:102·114·115·116`
  - closed_loop 13: 11개(`:052-062`)는 불필요 정지 분류(`closed_loop.py:352-356`)이고, 2개(`:035·039`)는 정지 step의 충돌·이탈 결과 분류(`:205·207`)다. 둘 다 기존 테스트가 실행하지 않던 경로였다.
  - detector_a 4개는 `:102`(158행, 등가)와 `:114-116`(168행, 테스트 공백)이다.
- **2차:** 생존 69개가 모두 실행된 줄에 있다. 실행되지 않은 줄의 생존은 0이다. 보강 테스트가 그 줄들을 실행하게 됐다.
  - 이 69개는 테스트가 실행하는데도 잡히지 않은 것이다. 모두 등가·경계 동치 미검증·도달 불가 입력·보류·측정값 분류이거나, 보강하지 않기로 한 `:283`이다.
- 커버리지는 "실행됨"만 말한다. 1차 테스트 공백 52개 중 38개는 실행된 줄에 있었다. 테스트가 그 줄을 실행했지만 결과를 확인하지 않았다는 뜻이다.

## 발견 사항(1차 실행)

1. **`compute_time_ms` 오류를 어떤 테스트도 잡지 못했다.**
   - `compute_time_ms`는 핵심 주장 1의 측정값이다(`thesis_v2/baseline/runner.py:150`, `:206`에서 기록).
   - 변이 5개가 모두 L1·L2·L3를 통과했다: `baseline_mpc:272`·`:273`(정상 경로 `mpc.py:253`: ×1000 → ÷1000, ×0), `:285`·`:286`·`:287`(fallback 경로 `mpc.py:262`: − → +, ×1000 → ÷1000, ×0).
   - golden과 테스트는 조향각만 비교하고 계산 시간 값은 확인하지 않는다(사전 선언 M2 예측과 같음).
2. **ψ 제약 행이 제거돼도 golden 차이는 8e-06 rad였다.**
   - 변이: `baseline_mpc:133`, `mpc.py:149` ψ 제약 행 계수 1.0 → 0.0. 이 행으로는 ψ_i를 제약하지 못한다.
   - 1차와 재실행의 L3 `max|diff|`는 둘 다 8e-06 rad였다(허용오차 1e-3 이내). 1.2e-05는 다른 변이(`:165`, `:198`)의 값이다.
   - 원인(확인됨, 실행): golden 6개 시나리오에서 ψ 제약이 활성되지 않는다. [mpc_golden_psi_activity.py](mpc_golden_psi_activity.py)(결과 [raw/mpc_golden_psi_activity.json](raw/mpc_golden_psi_activity.json))로 측정했다.
     - 전체 351회 solve(모두 solved)에서 예측 |ψ| 최대는 0.2815 rad(16.1°)다. 제약 PSI_LIMIT_DEG = 80°의 20%다.
     - 같은 측정에서 δ는 제약 25°에 닿았다(최대/한계 = 1.0001, OSQP 허용오차 범위).
   - 8e-06의 차이는 제약 활성 때문이 아니다. 행이 바뀌어 OSQP 반복 경로가 달라진 데서 온 수치 차이로 추정한다(제약이 비활성이라 최적해는 같아야 한다).
   - 의미: golden은 ψ 제약(REQ-MPC-04)이 있든 없든 통과한다. ψ 제약을 확인하는 테스트가 없다(사전 선언 M5와 같음).
3. **정지 step은 액추에이터 고장을 거치지 않는다(낙관적 모델링).** closed_loop 테스트 보강 중 발견했다. 코드와 평가 결과는 수정하지 않았다.
   - 내용(확인됨, 코드): 즉시 정지 step은 `delta_to_vehicle = delta_prev`로 차량을 갱신하고 `injector.apply_actuator`를 부르지 않는다(`thesis_v2/anomaly/closed_loop.py:199-200`). 그래서 steer_stuck·steer_delay가 활성인 동안에도 명령한 δ_{k−1}로 갱신된다. 정지 step에서만 액추에이터 고장이 사라지는 셈이다.
     - 일반 step은 `apply_actuator`를 거친다(`:237`).
     - DESIGN.md §24는 "직전 조향(δ_{k−1}) 유지"까지만 정하고, 정지 step에 액추에이터 고장을 적용할지는 정하지 않았다.
   - 테스트: 이 동작을 고정하는 제안 테스트(`test_p1_stop_step_holds_previous_command`)는 사용자 결정으로 넣지 않았다(`llm_tests_log.json`). 그래서 `closed_loop:030`은 첫 step 정지 테스트(NameError)로만 잡힌다.
   - **영향 크기(확인됨, 저장 결과)**: 평가 결과 `thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval`에서 steer 고장이 활성인 상태로 정지 step이 실행된 에피소드를 셌다([count_stop_step_steer_faults.py](count_stop_step_steer_faults.py) → [raw/stop_step_steer_fault_count.json](raw/stop_step_steer_fault_count.json)). 평가는 다시 실행하지 않았다.

     | 조합 | 정지 에피소드 | 그중 steer 고장 활성(delay / stuck) | 정지 step 결과 |
     |---|---:|---:|---|
     | P1_A | 868 | 199 (100 / 99) | 탐지 정지 199 |
     | P1_B1 | 20 | 6 (2 / 4) | 탐지 정지 5, 이탈 1 |
     | P1_B2 | 691 | 187 (100 / 87) | 탐지 정지 187 |
     | P1_HYBRID | 191 | 115 (89 / 26) | 탐지 정지 115 |
     | P2_A | 471 | 199 (100 / 99) | 탐지 정지 199 |

   - **결과가 바뀔 수 있었는지(추정)**: 바뀐 결과는 0건으로 추정한다.
     - 근거 1: 정지 step의 위치 x·y는 조향과 무관하다(`vehicle.py:24-25`). 조향은 ψ에만 들어간다(`:26`).
     - 근거 2: 정지 step에 액추에이터 고장을 적용했다면, 그 step의 갱신은 같은 seed P0의 같은 step 갱신과 같았을 것이다.
       - steer_stuck은 명령과 무관하게 고착값을 낸다(`faults.py:148-152`).
       - steer_delay는 d = 4–8 step 전 명령을 낸다(`faults.py:144-147`, `:201-203`). 이 값은 이번 step 명령과 무관하다.
       - 경보 전까지 P1·P2 궤적은 P0와 같다(정책이 입력을 바꾸기 전). 이 전제는 다시 실행해 확인하지 않았다.
     - 따라서 그 정지 step이 충돌·이탈로 판정됐을 경우는 같은 seed P0가 같은 step에 충돌·이탈로 끝난 경우뿐이다.
       - 그런 에피소드는 P1_B1 seed 5048(steer_stuck, step 72, P0 이탈) 1건뿐이다. 이 에피소드는 기록된 결과도 이미 '이탈'이다.
       - 나머지 705건은 P0가 그 step 뒤에도 계속 주행했다. 액추에이터 고장을 적용했어도 '탐지 정지'였을 것이다.
     - 이 추정은 정지 step 한 번의 판정에 관한 것이다. 정지 뒤 차량이 계속 움직이는 효과(즉시 정지 가정, `safety/FTTI.md` §4)는 별개의 한계다.
   - 후속: `repro/docs/IMPROVEMENT_BACKLOG.md` 후보 15, `docs/verification/safety/FTTI.md` §4 한계에 연결.
4. **구현에는 있으나 명세에 없는 동작(파생 요구사항 누락) — baseline MPC 2건.** 보강 테스트를 만들다가 발견했다. 테스트로 고정하지 않았고, 코드와 SETTINGS_DECISION은 수정하지 않았다.
   - (a) **속도 하한** `v = max(0.05, min(V_MAX, |v0|))`(`thesis_v2/baseline/mpc.py:208`, 주석 "수치안정")
     - SPEC(REQ-MPC-01 모델은 v를 그대로 씀)과 SETTINGS_DECISION에 이 하한이 없다(grep "0.05"·"하한"·"수치안정", 확인됨·파일).
     - 영향(추정, 코드 근거): baseline에서 MPC가 불리는 속도는 0.3–0.5 m/s다. 초기 속도는 INITIAL_V_RANGE(0.3, 0.5)(`config.py:46`, `world.py:65`), 이후는 V_MAX(`longitudinal.py:12`)다. v=0인 SAFE_STOP에서는 MPC를 부르지 않는다(`lateral.py:38-41`). 따라서 이 하한은 기존 실행 결과에 영향을 주지 않았을 것이다.
     - 변이 `baseline_mpc:209`(0.05 → 0)는 v0 = 0에서 δ_0을 25° 바꾼다(스크래치 측정). 그래서 동작 차이는 분명하지만, 무엇이 맞는지 명세가 없다.
   - (b) **fallback 출력의 ±25° 클램프**(`mpc.py:261`)
     - REQ-MPC-07/07a와 SETTINGS_DECISION §11은 δ_fallback = −K_p·(y − y_ref)만 정한다.
     - 차량 조향 한계 δ_max = ±25°(REQ-VEH-02)는 있다. 하지만 그 적용 위치는 후처리(rate limit → ±25° clip, SETTINGS_DECISION §15, `postprocess.py:26-27`)로 정해져 있어, MPC fallback 단계의 클램프는 명세에 없다.
     - 영향(추정, 코드 근거): 최종 조향 명령은 후처리에서 어차피 ±25°로 잘리므로 차량 동작은 같다. 달라지는 것은 기록되는 MPC 원출력(fallback 값)뿐이다.
     - 변이 `baseline_mpc:283`(클램프 삭제)은 1차 실행에서 생존했다.
   - 후속: `repro/docs/IMPROVEMENT_BACKLOG.md` 후보 16.

5. **2차 원자료의 git.dirty = true는 저장소 안 로그 폴더 때문이다(2차 실행, 코드 변경 아님).**
   - 사실(확인됨, 로그):
     - `overnight_run.sh`는 시작하자마자 로그 폴더 `raw/overnight/20261014_160442/`를 저장소 안에 만든다.
     - 시작 전 확인은 이 폴더의 미추적 파일만 빼고 작업 트리가 깨끗함을 확인했다(16:04:44, 중단 사유 없음, HEAD = origin/main = `6971d64`).
     - `mutate.py`의 `git_state()`는 `git status --porcelain` 출력이 비어 있지 않으면 dirty로 기록한다. 그래서 미추적 로그 파일만으로도 true가 된다.
   - 영향: 없다고 판단한다. 변이 실행은 저장소의 `thesis_v2`(results 제외)를 임시 사본으로 복사해 쓰므로 로그 폴더와 무관하다. 커밋도 실행 전후 같다(`git_after` = `6971d64`).
   - 사용자 지시로 `--check`를 마지막 단계로 옮긴 목적(원자료가 dirty로 기록되지 않게)은 이 때문에 달성되지 않았다. 다음 실행부터 로그 폴더를 저장소 밖에 두거나 dirty 판정에서 빼려면 `overnight_run.sh`를 고쳐야 한다(수정하지 않음, 사용자 결정).
6. **선택지 5(run #6 대응)가 저장 평가 수준에서 출력 불변임을 확인(2차 실행과 같은 야간 실행 3단계).**
   - anomaly `closed_loop --check`(저장 eval `20261012_142758_3층PC109_it3_closed_loop_eval`, 17:15–18:18): 7개 파일 전체 일치.
   - 새 지문 판정으로 센 time_limit 발동은 0이었고, 최대 solve는 3.0 ms였다(`_check_diag_timing.csv`).
   - 상세는 `docs/verification/ci/run6_cause/COMMIT2_VERIFY.md`에 있다.

## LLM 보조 테스트

**아래 테스트는 LLM(Claude Code, claude-opus-5-5)이 제안했다.** 수락 기준과 절차는 PREREGISTRATION.md §8을 따른다. 기록: [llm_tests_log.json](llm_tests_log.json).

| 모듈 | 파일 | 제안 | 수락 | 거절 | 대상 공백 | ② 잡음 | ④ 검토 방식 |
|---|---|---:|---:|---:|---:|---:|---|
| closed_loop | `thesis_v2/anomaly/tests/test_mutation_gaps_closed_loop.py` | 18 | 17 | 1 | 25 | 25 | 사용자 일괄 검토(요약표 기준, 별도 Claude 채팅 세션의 검토 보조) |
| detector_a | `thesis_v2/anomaly/tests/test_mutation_gaps_detector_a.py` | 14 | 14 | 0 | 22 | 22 | 같음(조건부 수락, 아래) |
| fsm | `thesis_v2/tests/test_mutation_gaps_fsm.py` | 4 | 4 | 0 | 4 | 4 | 같음 |
| baseline_mpc | `thesis_v2/tests/test_mutation_gaps_mpc.py` | 10 | 10 | 0 | 9 | 9 | 같음 |
| **합계** | | **46** | **45** | **1** | **60** | **60** | |

- 테스트 수는 파라미터 변형을 포함한 수집 항목 기준이다. 대상은 `reinforce` 60개다(baseline_mpc는 테스트 공백이 아닌 측정 분류의 명백한 공백 9개).
- **④ 부분 충족 4개(detector_a)**: 추적 위치가 탐지기 출력(DetectorOutput)에 없어 `det.tracks`를 직접 확인한다. 기존 `test_detector_a.py:144-219`와 같은 방식이다. 대상 테스트:
  - `test_front_gap_without_obstacle_info_does_not_create_track`(029·032 — 두 변이는 예외로 잡힌다)
  - `test_no_return_measurement_does_not_create_track`(031)
  - `test_track_position_is_mean_of_accepted_measurements`(048·053)
  - `test_dead_reckoning_and_front_point_match_plant_while_heading_is_nonzero`(172·026)
- 합성 입력(순간이동, 정지 중 회전, 갑작스러운 장애물 출현, 주입한 측정 오차, 장애물 통과)을 쓰는 detector_a 테스트 6개는 그 사실을 docstring에 적었다(사용자 조건).
- MPC 테스트의 입력 성격:
  - ψ 제약 테스트는 정상 주행에서 제약이 걸리지 않아 스트레스 입력(ψ0 = 79°, target_y = 5.0)을 쓴다.
  - QP 독립 구현 비교는 저속(v0 = 0.05 m/s)에서 차이가 드러난다.
  - 계산 시간 테스트는 `mpc.py`의 시계 참조만 가짜로 바꾼다.

- ①(원본 통과)·②(대상 변이를 잡음)·③(docstring에 DESIGN 절): [check_gap_tests.py](check_gap_tests.py) → [raw/gap_tests_closed_loop_check.json](raw/gap_tests_closed_loop_check.json). 수락본 기준이다.
  - 첫 step 정지 테스트를 뺀 재확인([raw/gap_tests_closed_loop_check_without_first_step.json](raw/gap_tests_closed_loop_check_without_first_step.json)): 028·030·037은 그 테스트로만 잡힌다.
- 거절 1개: `test_p1_stop_step_holds_previous_command`. DESIGN §24에 없는 모델링을 고정하게 되어 거절했다. 대신 발견 사항 3과 백로그 후보 15로 기록했다.
- 사람이 고친 부분: 거절한 함수만 파일에서 삭제했다. 나머지는 제안 그대로다.

## 구성 대조 (PREREGISTRATION.md 기준, 모두 완료)

| # | 사전 선언한 항목 | 위치 |
|---|---|---|
| 1 | 실행 조건: 커밋, PC 부하, 깨끗한 사본의 층별 시간, 타임아웃 | "2차 실행" 절 표, MUTATION_TABLES.md §1 |
| 2 | 점수: 원점수, 등가 제외 점수. 보강 전·후, 모듈별 | "요약", MUTATION_TABLES.md §2 |
| 3 | 처음 잡힌 층 분포, 예외·타임아웃 | "2차 실행" 절, MUTATION_TABLES.md §2·§3 |
| 4 | 생존 변이 분류 | "생존 변이 분류(확정)", "2차 실행" 절, MUTATION_TABLES.md §5 |
| 5 | 예측 P1–P7′, M1–M6 | "예측 대조" |
| 6 | 커버리지 대조 | "커버리지 대조", MUTATION_TABLES.md §6 |
| 7 | LLM 보조 테스트 | "LLM 보조 테스트" |

- CI(PREREGISTRATION §9): `test_mutate.py`와 `make_mutation_tables.py --check`를 `.github/workflows/ci.yml`에 넣었다(2026-10-15). 전체 변이 실행은 CI에서 하지 않는다.
