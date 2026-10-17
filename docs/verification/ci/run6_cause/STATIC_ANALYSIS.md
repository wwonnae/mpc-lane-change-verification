# run #6 비결정성 — 0단계 정적 분석

- 작성: 2026-10-14, 대상 커밋 4c0c503(main, 작업 트리 clean)
- 범위: 코드와 osqp 소스 읽기, 설정값 읽기용 실행 1회(설정 변경 없음). 부하·반복 실험 없음.
- 표기: **[확인-파일]** 파일:행 근거, **[확인-실행]** 이 PC에서 실행해 확인, **[추정]** 근거를 붙인 추론.

## 요약

1. **[확인-실행]** I5 on 조합(test_i5 golden, i4 TEACHER_FLAGS)에서 OSQP가 실제로 쓰는 설정은
   `time_limit=0.045`, `max_iter=1944/972`, `adaptive_rho=1`(ITERATIONS), `adaptive_rho_interval=50`, `check_termination=25`,
   `warm_starting=1`, `polishing=0`이다. baseline과 I5 off 조합은 `time_limit=1e10`(사실상 무제한)이다.
2. **[확인-파일]** adaptive rho 갱신 시점은 **반복 수 기준**이다(`iter % 50 == 0`). 시간 기준 모드(`adaptive_rho=2`)는 쓰지 않는다.
   이 설정에서 OSQP 안의 벽시계 의존 경로는 **`time_limit` 검사 하나뿐**이다.
3. **[확인-파일]** time_limit에 걸린 solve는 status가 **"run time limit reached"만이 아니라 "solved inaccurate", "solved"로도 보고될 수 있다.**
   코드(`improved/mpc.py:408`)와 time_limit_monitor는 "run time limit reached"만 발동으로 센다. 따라서 run #6의
   "발동 0회 → 시간 제한 원인 아님" 판정은 근거가 될 수 없다.
4. **[확인-파일]** iteration 기록만으로 time_limit 발동을 판별할 수 있다(지문 규칙, §3-3). 저장된 평가 로그도 이 규칙으로 다시 점검할 수 있다.
5. **[추정]** 정적 분석으로 남는 1순위 가설은 H1(time_limit 절단이 다른 status로 보고됨)이다. H2(시간 기준 adaptive rho)는 소스와 실행으로 배제했다.
   H3(입력 단계 비결정성)와 H4(실행 간 상태)는 코드에서 근거를 찾지 못했지만 정적으로 배제할 수 없다. 1–3단계 실험으로 확인한다.
6. **[확인-파일/실행]** 조건 B의 "자연값"은 현재 값 50과 같다. B1=B2=현재 설정이므로 B는 원래 설정과 같은 실험이 된다(§6 제안).

## 1. 근거 자료

| 자료 | 위치 | 비고 |
|---|---|---|
| osqp 1.1.1 sdist | PyPI `osqp-1.1.1.tar.gz`, sha256 `1719e6a8…7acf4` | Python 래퍼와 빌드 스크립트 |
| C OSQP 소스 | GitHub `osqp/osqp` tag `v1.0.0` tarball, sha256 `dd6a1c2e…8e48` | sdist `CMakeLists.txt:31-34`가 `FetchContent … GIT_TAG v1.0.0`로 가져오는 버전 |
| 설치본 | `.venv` osqp 1.1.1(`ext_builtin.cp39-win_amd64.pyd`), numpy 2.0.2, scipy 1.13.1, Python 3.9.13 | CI `requirements-py39.txt`와 같은 고정 조합 |

- **[추정]** 설치된 바이너리가 C v1.0.0으로 빌드됐다는 것은 sdist 빌드 스크립트에서 추론한 것이다. 바이너리에서 버전 문자열은 찾지 못했다.
  아래 기본값(interval 50, check_termination 25, time_limit 1e10)은 실행으로 C 쪽 설정을 직접 읽어 v1.0.0 소스 기본값과 일치함을 확인했다.
- 아래 C 소스 행 번호는 v1.0.0 tarball 기준이다(`src/osqp_api.c`, `src/auxil.c`, `include/public/osqp_api_constants.h`).

## 2. OSQP에 실제로 넘어가는 설정

### 2-1. 코드 경로 [확인-파일]

| 항목 | improved(I5 on) | improved(I5 off) | baseline |
|---|---|---|---|
| setup 위치 | `improved/mpc.py:141-157` | 같음 | `baseline/mpc.py:66-73` |
| max_iter | `i5_max_iter`(`mpc.py:152`) | `_MAX_ITER=20000`(`mpc.py:49,156`) | `OSQP_MAX_ITER=4000`(`baseline/config.py:65`) |
| time_limit | `I5_TIME_LIMIT_SEC=0.045`(`mpc.py:153`, `improved/config.py:37`) | 넘기지 않음 → 기본값 | 넘기지 않음 → 기본값 |
| eps_abs / eps_rel | 1e-4 / `_EPS_REL=1e-5`(`mpc.py:61`) | 같음 | 1e-4 / 1e-4 |
| warm_starting / polishing | True / False(`baseline/config.py:66-67`) | 같음 | 같음 |
| adaptive_rho 계열 | 넘기지 않음 → 기본값 | 같음 | 같음 |

Python 래퍼는 `osqp_set_default_settings` 후 넘긴 키만 덮어쓴다(sdist `src/osqp/interface.py:381-383`).

### 2-2. 실행으로 읽은 C 쪽 설정 [확인-실행]

인스턴스를 생성한 뒤 `prob._solver.get_settings()`(C `solver->settings`, sdist `src/bindings.cpp.in:163-164`)로 읽었다(스크래치 스크립트 `dump_settings.py`).

| 설정 | I5 test(FINAL_COMBO, 1944) | i4 TEACHER_FLAGS(972) | FINAL_COMBO I5 off | baseline |
|---|---|---|---|---|
| max_iter | 1944 | 972 | 20000 | 4000 |
| time_limit | **0.045** | **0.045** | 1e10 | 1e10 |
| adaptive_rho | 1 (ITERATIONS) | 1 | 1 | 1 |
| adaptive_rho_interval | 50 | 50 | 50 | 50 |
| adaptive_rho_fraction / tolerance | 0.4 / 5.0 | 같음 | 같음 | 같음 |
| check_termination | 25 | 25 | 25 | 25 |
| warm_starting / polishing | 1 / 0 | 같음 | 같음 | 같음 |
| eps_abs / eps_rel | 1e-4 / 1e-5 | 1e-4 / 1e-5 | 1e-4 / 1e-5 | 1e-4 / 1e-4 |
| rho / sigma / alpha / scaling | 0.1 / 1e-6 / 1.6 / 10 | 같음 | 같음 | 같음 |

### 2-3. 재시도, fallback, 실행 간에 남는 상태 [확인-파일]

- **재시도:** solve마다 OSQP를 1회 호출한다(`improved/mpc.py:405`). 재시도 루프는 없다.
- **status 분기**(`improved/mpc.py:426-488`):
  - "solved", "solved inaccurate"는 해를 그대로 쓴다(`:426-427`).
  - "maximum iterations reached", "run time limit reached"는 하드 제약을 다시 검사한다(`:428-446`). 통과하면 해를 쓰고, 실패하면 I3(직전 해 shift, `:466-477`)로, 그것도 안 되면 비례 fallback(`:479-488`)으로 간다.
- **인스턴스 안에 남는 상태:**
  - OSQP warm start(직전 해)
  - `_last_solution_deltas`(I3, `mpc.py:159`)
  - `_fail_count`
  - 이것들은 같은 인스턴스의 solve 사이에만 이어진다. 대상 테스트는 실행마다 새 인스턴스를 만든다(`test_improved_i5.py:119`, `test_i4_student.py:50-53,62-64`).
- **모듈 전역:** improved/baseline/student_i4에서 모듈 수준 가변 객체는 설정 상수(dict, list)뿐이다. 실행 중에 바꾸는 코드는 찾지 못했다.
- **RNG:** `np.random.default_rng(seed)`를 시나리오 생성 시 seed로 만든다(`baseline/world.py:61,85,99,116`). 전역 RNG는 쓰지 않는다.
- **시간 측정값:** `time.perf_counter`(`improved/mpc.py:346,453,464`, `baseline/runner.py:262-264`)는 로그(`compute_time_ms`, `t_mpc_solve_ms`)에만 쓰인다. 제어 분기에는 쓰이지 않는다(`improved/runner.py:187,321`).
- 결론: 우리 코드에는 벽시계나 실행 순서에 의존하는 제어 경로가 없다. **[확인-파일]** 범위는 위 grep 대상 파일이다.

## 3. time_limit에 걸렸을 때 OSQP가 반환하는 것

### 3-1. status 종류 [확인-파일]

`src/auxil.c:784-797` `OSQP_STATUS_MESSAGE`:

| 번호 | 문자열 |
|---|---|
| 1 | solved |
| 2 | solved inaccurate |
| 3 | primal infeasible |
| 4 | primal infeasible inaccurate |
| 5 | dual infeasible |
| 6 | dual infeasible inaccurate |
| 7 | maximum iterations reached |
| 8 | run time limit reached |
| 9 | problem non convex |
| 10 | interrupted |
| 11 | unsolved |

열거값 정의는 `osqp_api_constants.h:29-36`에 있다.

### 3-2. 반복 루프와 종료 경로 [확인-파일] (`src/osqp_api.c`)

1. **반복 안 검사 순서**(`for iter = 1..max_iter`, `:698`):
   - ADMM 갱신 (`:700-723`)
   - **time_limit 검사** (`:740-757`)
   - termination 검사 가능 여부 계산 (`:764`, `iter % 25 == 0`)
   - adaptive rho (`:776-845`)
   - termination 검사 (`:860-865`)
2. **time_limit 검사**(`:743-757`)는 `OSQP_ENABLE_PROFILING`이 켜진 빌드에서만 동작한다.
   - 첫 solve: `setup_time + 경과 시간`
   - 이후 solve: `update_time + 경과 시간`
   - 이 값이 `time_limit` 이상이면 status를 TIME_LIMIT_REACHED로 바꾸고 `break`한다.
   - `update_time`은 직전 solve 이후 `osqp_update_data_vec`/`update_data_mat`에 쓴 시간을 누적한 값이다(`:1200-1253`, `:1326-1405`). 우리 코드는 매 스텝 `prob.update(q, l, u, Ax, Ax_idx)`(`improved/mpc.py:404`)로 행렬까지 갱신하므로, 그 시간도 45 ms 예산에 들어간다.
   - **[추정]** 이 바이너리는 profiling 빌드다. 바이너리에서 "run time limit reached" 문자열이 2번 나오는데, 하나는 status 표이고 하나는 profiling 블록 안 verbose 출력이다. 그리고 `test_i5_time_limit_safety_net_reachable`이 이 status를 실제로 받는다(CI.md:56, 100행).
3. **루프를 빠져나온 뒤**(`:908-960`):
   - `:908-929`: 마지막 반복에서 termination 검사를 하지 않았으면(`!can_check_termination`), `update_info(iter-1)` 후 **정규 기준으로 `check_termination(solver, 0)`** 을 한다. time_limit으로 빠져나온 경우도 여기에 해당할 수 있다. 통과하면 status가 **"solved"** 로 덮어써진다.
   - `:952-956`: status가 UNSOLVED(max_iter 도달)이면 근사 검사를 하고, 실패하면 MAX_ITER_REACHED가 된다.
   - `:958-965`: status가 **TIME_LIMIT_REACHED이면 근사 검사(`check_termination(solver, 1)`)** 를 한다. 통과하면 **"solved inaccurate"**, 실패하면 "run time limit reached"가 된다.
   - 근사 검사는 eps_abs, eps_rel, eps_prim_inf, eps_dual_inf를 각각 10배로 늘려 판정한다(`src/auxil.c:842-847, 899-905`).
4. **결론:** time_limit으로 끊긴 solve의 보고 status는 "solved", "solved inaccurate", "run time limit reached" 중 하나다(infeasible inaccurate 계열은 이론상 가능하지만 I1b 슬랙이 있어 feasible이다).
   - `improved/mpc.py:408`은 `time_limit_hit = (status == "run time limit reached")`이다.
   - `docs/verification/ci/time_limit_monitor.py:46-53`은 이 필드만 읽는다.
   - 따라서 **앞의 두 경우는 발동으로 세지지 않고, 코드도 정상 해로 그대로 쓴다(`mpc.py:426`).**
   - `time_limit_monitor.py:8,95`의 "발동 0회인 실패는 time_limit 원인이 아님"은 성립하지 않는다.

### 3-3. iteration 기록으로 판별하는 지문 규칙 [확인-파일, 실측 검증은 1단계]

`info.iter`는 `update_info(iter)`가 기록한다(`src/auxil.c:723`). 종료 경로별 `info.iter`는 다음과 같다(check_termination=25, max_iter=M).

| 종료 경로 | status | info.iter |
|---|---|---|
| 정상 수렴(반복 중 검사 통과) | solved | 25의 배수, < M |
| max_iter 도달 | solved(정규 재검사 통과) / solved inaccurate / maximum iterations reached | = M |
| time_limit 절단(k번째 반복에서 break) | run time limit reached / solved inaccurate / solved | k−1 (< M) |

- 이 표에 맞는지는 1단계에서 실측으로 검증한다. 임시 사본에서 time_limit을 아주 작게 줘서 끊기는 경우를 강제로 만들어 비교한다.
- 위 표에서 나오는 판별 규칙은 다음과 같다.
  - 다음 중 하나면 **time_limit이 발동한 것**이다.
    - status == "run time limit reached"
    - status == "solved inaccurate" 이고 iter < M
    - status == "solved" 이고 iter % 25 ≠ 0 이고 iter ≠ M
  - 판정할 수 없는 경우가 하나 있다. 바로 앞 반복에서 정규 검사를 하고 실패한 직후 끊긴 경우(iter가 25의 배수)인데, 이때 status는 "solved"가 될 수 없고 "solved inaccurate"나 "run time limit reached"가 된다. 이 둘은 위 규칙으로 잡히므로 누락은 없다.
  - M=972(972 % 25 = 22), M=1944(1944 % 25 = 19)라서 "iter = M"과 "25의 배수"는 겹치지 않는다.

> **[정정 2026-10-14, S6 — 원문은 위에 그대로 둠]** 위 판별 규칙에는 빈틈이 하나 있다. **첫 반복(k=1)에서 끊긴 경우다.**
> - 이때 "수렴 검사 가능" 플래그는 초기값 0이다(`osqp_api.c:666`). 플래그 갱신(`:764-765`)이 시간 검사(`:741-757`)
>   뒤에 있기 때문이다.
> - 그래서 `:908-931`에서 `update_info(iter-1 = 0)` 후 정상 eps로 검사한다. 수렴했으면 **"solved", iter 0**이 된다.
> - 0은 25의 배수라 위 규칙("solved" & iter % 25 ≠ 0)이 놓친다. 위 원문의 "누락은 없다"는 k−1 ≥ 1인 경우에만 맞다.
> - 정상 종료는 iter 0으로 "solved"를 낼 수 없다. 첫 수렴 검사가 25번째 반복이고, max_iter ≥ 1이다.
>   그래서 규칙에 **"status == solved 이고 iter == 0"**을 더하면 과대 집계 없이 빈틈이 막힌다(안 B, 사용자 결정).
> - 실측·양성 대조에서 "solved, iter 0"은 0건이었다. 같은 k=1 경로의 "run time limit reached, iter 0"은 S3·S4에서 실제로 나왔다.
> - 이 추가로 기존 판정(S1–S4)은 바뀌지 않는다(raw/S6_fingerprint_check/README.md).
> - 제품 `improved/mpc.py time_limit_fingerprint`와 `osqp_probe.tl_fingerprint`는 이 안 B로 맞췄다.
> - "OSQP info.run_time ≥ time_limit"을 OR로 더하는 안(C)도 검토했다. 실측(45 ms)에서는 새로 잡히는 것이 0이었다.
>   양성 대조(0.2/0.5/1 ms, 32,040 solve)에서는 정상 종료 뒤 마무리 시간으로 제한을 넘긴 과대 집계만 12건 나와
>   넣지 않았다(사용자 결정).

## 4. 설계 주장과 실제 코드 (요청하신 대조)

| 설계·테스트의 주장 | 실제 코드·동작 |
|---|---|
| `test_improved_i5.py:114-116` docstring: "반복 상한은 시간이 아니라 반복 횟수 기준이므로 결정론적이어야 함 -- DESIGN_IMPROVED_V2.md §1-0/§1-5" | `improved/mpc.py:150-153`: I5 on이면 `max_iter`와 함께 **`time_limit=0.045`도 setup에 넘긴다.** C 쪽에서 0.045로 읽힌다(§2-2) |
| `DESIGN_IMPROVED_V2.md:100-102`(§1-0): `max_iter`가 주 상한, `time_limit`은 "정상 상황에서 걸리지 않는" 안전망 | 실제로 걸리는지는 벽시계에 달려 있다(`osqp_api.c:743-757`). 첫 solve는 setup 시간, 이후 solve는 행렬 update 시간도 예산에 포함된다 |
| `DESIGN_IMPROVED_V2.md:110-111`(§1-0): "같은 문제 데이터·같은 warm-start면 항상 같은 반복에서 멈추는 결정론적 컷오프" | **time_limit이 한 번도 발동하지 않는다는 조건에서만** 참이다. 설계 문서 스스로 §1-4(`:250-255`)에서 "발동하면 §1-0의 결정론이 깨진다"고 적어 두었다 |
| `DESIGN_IMPROVED_V2.md:253-255`(§1-4): 발동은 `time_limit_hit=True`로 반드시 로깅해 관찰 | `time_limit_hit`는 "run time limit reached"만 잡는다(`mpc.py:408`). 끊긴 solve가 "solved inaccurate"나 "solved"로 보고되면 **로깅에서 빠진다**(§3-2) |
| `DESIGN_IMPROVED_V2.md:75-81`(§0-2): `time_limit=1e-7`, `eps=1e-12` 실험으로 "run time limit reached"와 "maximum iterations reached"가 구분됨을 확인 | 그 실험은 근사 검사가 통과할 수 없는 조건(eps 1e-12, iter=0)이라 다른 status로 보고되는 경로를 볼 수 없었다. **[추정]** §0-2 결론의 범위는 "문자열이 서로 다르다"까지다 |
| `DESIGN_IMPROVED_V2.md:257-262`(§1-5): I5 on 3회 반복 golden은 "반복 상한 방식이므로 통과해야 정상" | 이 테스트가 결정론을 보장하는 건 time_limit이 발동하지 않을 때뿐이다. 실행 환경 부하에 따라 통과 여부가 달라질 수 있는 구조다 |
| `improved/mpc.py:15-18` 모듈 docstring, `:149-151` 주석: "둘 다 결정론 유지 목적" | time_limit 자체는 결정론적 메커니즘이 아니다 |

판정(정적, **[추정]**): 설계 주장은 "time_limit 미발동"이라는 전제 아래에서만 맞다. 그 전제는 현재 로깅으로 검증되지 않는다.
실제로 발동이 비결정성을 만드는지는 1–4단계 실험으로 확인한다.

## 5. 대상별 정리

| 대상 | time_limit | 비교 방식 | 정적 판정 |
|---|---|---|---|
| `test_i5_golden_determinism_three_runs` | 0.045 | delta_final 비트 단위 비교(`test_improved_i5.py:122`) | 위험 있음 (H1 경로) |
| `test_i4_recorder_does_not_change_episode` | 0.045 (TEACHER_FLAGS, `student_i4/config.py:15-17`) | delta_final 비트 단위(`test_i4_student.py:54-55`) | 위험 있음 |
| `test_i4_closed_loop_matches_improved_runner_with_mpc[100,101]` | 0.045 | y 궤적 비트 단위, 전이, 스텝 수(`:63-72`) | 위험 있음 |
| baseline golden (`check_golden`) | 없음(1e10) | 허용오차 1e-3 rad | 벽시계 경로 없음 → 정적으로 결정론적 |
| I5 off 조합(v1 동치·equivalence 테스트) | 없음(1e10) | — | 같음 |

**baseline이 비결정성을 보이지 않은 이유(정적):**
- **[확인-실행]** baseline은 time_limit이 1e10이다. 그 밖의 설정 차이(eps_rel, max_iter)는 벽시계와 무관하다. 그래서 OSQP 안에 시간에 의존하는 분기가 없다. 설정 차이만으로 설명된다.
- 덧붙여, golden 허용오차 1e-3 rad는 run #6 크기의 차이(약 3e-4도 ≈ 5e-6 rad)를 잡지 못한다. 그래서 baseline golden 통과는 baseline이 결정론적이라는 독립 증거가 되지 못한다. 2단계에서 baseline 에피소드를 비트 단위로 비교하는 대조군을 둔다.

**그 밖에 영향을 받을 수 있는 테스트 [확인-파일]** (I5 on, time_limit 0.045 사용):
- `test_improved_i5.py::test_i5_tiny_iter_cap_triggers_max_iter_status_and_hard_check`: CI.md:64에 부하 조건에서 "run time limit reached"로 실패한 기록이 있다.
- `thesis_v2/anomaly/tests/test_closed_loop.py`의 `test_p0_matches_observational_runner`(8개), `test_determinism`(`an_config.V2_MPC_FLAGS`, `anomaly/config.py:13-15`):
  - 비교 대상이 결과, 스텝 수, 전이 같은 이산값이라 덜 민감하다. 그래도 바뀔 수 있다.
  - 참고로 `test_determinism`(`:120-122`)과 `test_p0_matches_observational_runner`(`:32-34`)는 같은 MPC 인스턴스를 두 실행에 함께 넘긴다.
    두 번째 실행은 첫 실행의 OSQP warm start와 I3 상태를 이어받는다. 이 테스트들이 현재 통과하는 것은 비교 대상이 이산값이기 때문으로 보인다(**[추정]**).
  - 이번 작업의 대상은 아니지만 비결정성 후보 목록에는 넣는다(5단계 mutation 재점검 범위).

## 6. 가설 상태와 조건 B 제안

| 가설 | 정적 판정 | 실험에서 볼 것 |
|---|---|---|
| H1 time_limit 절단(어떤 status로든) | **남음(1순위)** — 유일한 벽시계 경로 | 처음 어긋난 solve가 §3-3 지문 규칙에 해당하는지 |
| H2 시간 기준 adaptive rho | **배제** — `adaptive_rho=1`, interval 50 고정(§2-2, `osqp_api.c:574-592, 835-841`) | 래퍼에 rho_updates를 기록해 확인만 함 |
| H3 OSQP 입력이 이미 다름(numpy/BLAS 등) | 근거 없음, 정적으로 배제 불가 | 처음 어긋난 solve에서 입력(q, l, u, Ax) 해시가 같은지 |
| H4 실행 간 상태 | 근거 없음(§2-3) | 묶음 안 순서와 불일치의 상관, 입력 해시 |
| H5 메모리 정렬 등에 따른 부동소수 비결정(입력은 같고 time_limit 지문도 없는데 출력이 다름) | 정적으로 배제 불가 | 부하 없음 조건에서도 나오는지, 지문 없이 나오는지 |

**조건 B 자연값:**
- **[확인-파일/실행]** 현재 모드는 ITERATIONS이고 interval은 Python 기본값 50이다(`osqp_api_constants.h:135`, `osqp_api.c:311`). C 쪽에서도 50으로 읽힌다. 자동 계산(interval=0)은 쓰이지 않는다.
- 만약 interval=0을 넘겼다면 자동 규칙은 `4 × check_termination = 100`이다(`osqp_api.c:582-587`, 상수 `:149`).
- 따라서 **B1(자연값)=50=B2=현재 설정**이다. B는 원래 설정과 kwargs만 다르고 C 쪽 설정은 같다. 원래 설정과 같은 실험이므로 정보가 없다.
- 노트북 Run F("interval=50 고정 + 강한 부하")도 사실상 원래 설정이었다. **[추정]** 따라서 Run F 결과는 "원래 설정, 강한 부하"의 참고 표본으로 읽어야 한다.
- 대안은 0단계 보고에 선택지로 올린다.
