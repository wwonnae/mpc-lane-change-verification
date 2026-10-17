# Mutation testing + LLM 보조 테스트 보강 (검증 산출물 보강 4단계)

> 기존 테스트가 제어·탐지 코드의 작은 결함을 얼마나 잡는지 **변이(mutation)로 측정**한다. 생존한 변이 중 테스트 공백은 테스트를 보강한다.
> 실행 범위·연산자·층·타임아웃·예측은 **실행 전에** [PREREGISTRATION.md](PREREGISTRATION.md)에 고정했다.

상태(2026-10-15): **B단계 완료.**
- 점수: 원점수 78.5% → 88.5%, 등가 제외 점수 83.1% → 93.7%(600개, 보강 전 → 후).
- 보강 대상 60개는 모두 잡혔고, 1차에서 잡혔는데 2차에서 생존한 변이는 0개다.
- time_limit kill 재확인(사전 선언 변경 5)은 127개 모두 유지였다.
- 상세는 [RESULTS.md](RESULTS.md), 수치 표는 [MUTATION_TABLES.md](MUTATION_TABLES.md)에 있다.

## 도구 선택 — 직접 만든 AST 변이기

| 기준 | mutmut 3.3.1 | cosmic-ray 8.7.0 | `mutate.py`(직접 작성) |
|---|---|---|---|
| Windows | 네이티브 미지원. 공식 문서: fork 지원이 필요해 Windows에서는 WSL에서 실행 | PyPI 메타데이터 `Operating System :: OS Independent`(휠 METADATA 확인). 공식 문서에서 Windows 언급은 찾지 못함 | 표준 라이브러리만 사용 |
| Python 3.9 | 휠은 받을 수 있음(METADATA에 Requires-Python 없음) | `Requires-Python: >=3.9` | 3.9 `ast`(end_col_offset)·`tokenize` |
| 의존성 | libcst, textual 등 | aiohttp, sqlalchemy, gitpython 등 13개 | 없음 |
| 연산자 제어 | 내장 연산자 위주 | 연산자 플러그인 선택 | 8종을 코드에 고정(PREREGISTRATION §3) |
| 층별 판정(처음 잡힌 층) | 단일 테스트 명령 | 단일 테스트 명령 | L1 → L2 → L3를 직접 구현, golden 조향 차이도 기록 |

- 버전과 메타데이터는 2026-10-13에 `pip download --no-deps`로 임시 폴더에 받아 METADATA만 읽고 지웠다. 설치하지 않았다.
- 직접 만든 도구는 [test_mutate.py](test_mutate.py)(29개)로 신뢰성을 확인한다(PREREGISTRATION §6).
  - 개발 중 발견한 버그 2건은 고친 뒤 회귀 테스트로 남겼다.
    - AST 열 위치(UTF-8 바이트)를 문자 위치로 착각해, 한글이 있는 줄에서 편집 위치가 어긋남
    - 여러 줄 구간을 지울 때 줄 수가 바뀜
  - 바이트코드 캐시가 같은 길이의 변이를 가린다는 것은 스크래치 실험으로 확인했다(캐시를 허용하면 `1 + 2`→`1 - 2` 변이에도 테스트가 통과함). 그래서 실행기는 캐시를 끄고 돌린다.

## 파일

| 파일 | 내용 | 단계 |
|---|---|---|
| [PREREGISTRATION.md](PREREGISTRATION.md) | 범위 600개, 연산자 8종, 판정 층, 타임아웃, 점수 규칙, 예측(P1–P7′, M1–M6), LLM 보강 절차, CI 결정 | A |
| `mutate.py` | 변이 생성기 + 층별 실행기(저장소 밖 임시 사본에서만 변이) | A |
| `test_mutate.py` | 도구 자체 테스트 | A |
| [RESULTS.md](RESULTS.md) | 점수(보강 전·후), 예측 대조, 커버리지 대조, LLM 기록 요약 | B |
| `raw/run_before.json`, `raw/run_after.json` | 원자료 | B |
| `equivalence.json`, `llm_tests_log.json` | 등가 판단, LLM 제안 기록 | B |
| `make_mutation_tables.py`, [MUTATION_TABLES.md](MUTATION_TABLES.md) | 원자료 → 표, `--check`(CI) | B |
| `recheck_tl_kills.py`, `raw/run_after_tl_recheck.json` | 사전 선언 변경 5: time_limit 켠 I5 MPC 테스트에서 처음 잡힌 kill을 orig·A(time_limit 끔)로 재확인 | B |
| `overnight_run.sh`, `raw/overnight/` | 2차 실행·kill 재확인·anomaly `--check`를 차례로 실행하고 결과 파일만 커밋하는 스크립트(2026-10-14), 실행 로그 | B |
| `recheck_survivors.py`, `raw/run_before_recheck_laptop.json` | 1차 생존 변이만 다른 PC에서 재실행(재현성 확인) | B |
| `build_equiv.py` | 생존 변이 분류 표 → `equivalence.json` | B |
| `mpc_setup_experiment.py`, `mpc_setup_probe.py`, `raw/mpc_setup_experiment.json` | baseline_mpc 생성 단계 변이의 등가·보류 판단용 실험 | B |
| `mpc_golden_psi_activity.py`, `raw/mpc_golden_psi_activity.json` | golden 시나리오에서 ψ 제약 활성 여부 측정 | B |
| `check_gap_tests.py`, `raw/gap_tests_*_check*.json` | LLM 보조 테스트 수락 기준 ①–③ 자동 확인 | B |
| `count_stop_step_steer_faults.py`, `raw/stop_step_steer_fault_count.json` | 저장된 폐루프 평가에서 steer 고장 활성 중 정지 step 수(RESULTS 발견 사항 3, 읽기 전용) | B |

- 위 보조 스크립트들은 `mutate.py`를 고치지 않고 그 함수만 호출한다.

## 실행

```
python -m pytest docs/verification/mutation/test_mutate.py -q       # 도구 자체 테스트(약 10초)
python docs/verification/mutation/mutate.py list                      # 변이 목록·수(실행 안 함)
python docs/verification/mutation/mutate.py run --out docs/verification/mutation/raw/run_before.json
python docs/verification/mutation/make_mutation_tables.py [--check]  # 원자료 → MUTATION_TABLES.md / 저장본 대조
```

- `test_mutate.py`는 기본 테스트 수집 경로(`thesis_v2/tests`, `thesis_v2/anomaly/tests`) 밖에 있다. 그래서 제품 테스트 수와 추적 매트릭스에는 들어가지 않는다.
- 전체 변이 실행은 CI에서 돌리지 않는다. 이유는 PREREGISTRATION §9에 있다. CI는 `test_mutate.py`와 `make_mutation_tables.py --check`만 실행한다(`.github/workflows/ci.yml`).

## 출처
- mutmut 문서(Windows는 WSL): https://mutmut.readthedocs.io, https://github.com/boxed/mutmut
- Cosmic Ray 문서: https://cosmic-ray.readthedocs.io/
