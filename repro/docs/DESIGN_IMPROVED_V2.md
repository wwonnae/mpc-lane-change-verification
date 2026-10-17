# 3단계 발전 버전 v2 설계 (I5, 계산시간 상한 보장) — 검토 반영판, 구현·dev 진행

**전제**: eval 1회차(I1+I1b+I2'+I3, 커밋 `4652e3264f7ff9096ef8d91851bf86fc274af6cb`)는
그대로 확정입니다. `RESULT_IMPROVED.md`는 다시 고치지 않고, v2는 **새 개선 항목(I5)**을
얹은 **2회차**로 별도 진행합니다. 이 설계 확정 후 구현·dev까지 진행하고, **eval은
별도 승인 전까지 실행하지 않습니다**(`repro/docs/WORK_RULES.md` "3단계 발전 원칙" — dev/eval 분리,
eval 1회, 사전 승인).

**목적**: 1회차 계산시간 분석(`RESULT_IMPROVED.md` §4, `repro/2c_analysis/
eval_timing_analysis.py`)에서 개선판 MPC solve의 최댓값이 40.5~44.9ms(20Hz 예산
50ms의 81~90%, 전부 `state=EVADE_L`·`solver_status="maximum iterations reached"`)로
관측됐습니다. 50ms 초과는 대표 샘플에서 0건이었지만 여유가 크지 않고, 대표 샘플이
전체(S3 961격자·S6 7종·S7a 9종 전부)를 다 보지 못했으므로, **설계로 계산시간
상한을 보장**해 실제 임베디드 20Hz 루프에서 안전 여유를 명시적으로 확보하는 것이
v2의 목적입니다.

**검토 반영(A. 설계 수정, 이번 판에서 확정)**:
1. I5의 주 메커니즘을 **wall-clock `time_limit`에서 반복 상한(`max_iter`)으로
   변경**(결정론 유지). `time_limit`은 정상 상황에서 걸리지 않는 넉넉한 안전망(45ms)
   으로만 남긴다 — 아래 §1 전면 재작성.
2. 시간 예산 후보를 **5/10/20/30ms** 4개로 확대(선택 규칙은 "안전성 비열화 없는
   가장 낮은 값" 유지) — §1-1.
3. 새 S3 eval 격자를 원래 간격(0.01) 유지 + 반 칸(0.005) 오프셋으로 정정, y0는
   [-0.15,0.15](개정 2 범위) 안에서 -0.145~0.145로 명시 — §4.
4. 로깅 보강 항목 확정(제어 로직 아님) — §1-3.

---

## 0. 사전 확인 (완료)

### 0-1. 환경 확인 (B, 지난번 미응답분 — 이번 판에서 확인)

```
$ python -c "import sys; print(sys.executable)"
C:\Users\SSAFY\AppData\Local\Programs\Python\Python311\python.exe
$ python -c "import osqp,numpy,scipy; print(osqp.__version__, numpy.__version__, scipy.__version__)"
osqp=1.1.3  numpy=2.3.3  scipy=1.16.2
$ python --version
Python 3.11.9
```

- 이번 세션에서 `python`/`python3` 등 별칭 없이 항상 위 `sys.executable`(3층PC104
  로컬 CPython 3.11.9, `Python311\site-packages`)로 실행했습니다. `Python311`
  site-packages의 osqp는 **조회만이 아니라 이번 세션의 모든 실행(벤치마크·이후
  dev ablation 포함)에 실제로 쓰인 인터프리터**입니다(가상환경을 별도로 만들지
  않고 이 인터프리터로 직접 실행 — `.venv` 없음, 이 호스트는 애초에 노트북과 달리
  `requirements-py39.txt` 환경을 쓰지 않습니다).
- **강건성 검증·eval 1회차 결과 폴더 `env.json`과의 일치 여부(확인됨, 파일 대조)**:
  `thesis_v2/results/eval_final/`에는 `env.json`이 저장돼 있지 않습니다(1회차
  `run_eval.py`가 `env.json` 기록 로직 자체를 갖고 있지 않음 — `env.json` 기록은
  `thesis_v2/baseline/envinfo.py` 경로로만 만들어지고 baseline CLI(`run.py`)에서만
  호출됨). 대신 **같은 호스트(3층PC104)에서 가장 가까운 시점(2026-09-22, 2단계
  종료 직전)의 baseline v1.1 실행 기록**(`thesis_v2/results/20260922_115241_
  3PC104_baseline_v1.1_P/env.json`)과 대조한 결과:

  | 필드 | env.json(3층PC104, 2026-09-22) | 이번 세션(방금 실측) |
  |---|---|---|
  | executable | `...\Python311\python.exe` | `...\Python311\python.exe` (**일치**) |
  | python | 3.11.9 | 3.11.9 (**일치**) |
  | numpy | 2.4.6 | 2.4.6 (**일치**) |
  | scipy | 1.17.1 | 1.17.1 (**일치**) |
  | osqp | 1.1.3 | 1.1.3 (**일치**) |

  **전부 일치(확인됨)**. eval 1회차(같은 세션 계열, 2단계 종료 이후 3단계
  진행 중 이 PC에서 연속 실행) 자체의 `env.json`은 없지만, 이 세션에서
  패키지를 새로 설치·갱신한 적이 없으므로 eval 1회차도 같은 환경이었다고
  봅니다.

### 0-2. OSQP `time_limit` 동작 확인 (1.1.3 — 현재 설치 버전, 안전망 용도로 유지)

`OSQP().setup(..., time_limit=...)`는 `**settings` 키워드로 전달되며, C 소스
(`osqp/codegen/codegen_src/inc/public/osqp_api_constants.h:36,164`)에 시간 상한
도달 시 별도 상태 `OSQP_TIME_LIMIT_REACHED`가 정의돼 있음을 확인했습니다. 독립
임시 QP(프로젝트와 무관, 50×50 랜덤 PD 행렬, `eps_abs=eps_rel=1e-12`로 정상
수렴을 막고 `time_limit=1e-7`)로 직접 실행해 **`res.info.status == "run time
limit reached"`(status_val=8)**, `iter=0`을 확인했습니다(스크래치 검증, 파일로
남기지 않음).

**결론**: `"maximum iterations reached"`(반복 상한)와 `"run time limit reached"`
(시간 상한)는 서로 다른 문자열로 명확히 구분되므로, 반복 상한을 주 메커니즘으로
쓰고 시간 상한은 안전망으로만 둬도 두 상태를 로깅에서 분리 집계할 수 있습니다.

> **[정정 2026-10-14, run #6 조사 — 원문은 위에 그대로 둠]**
> 이 실험은 "run time limit reached" 문자열이 따로 있다는 것까지만 확인한다. 실제로 시간으로 끊긴 solve는
> 근사 검사(eps×10)나 직전 반복의 정상 검사를 통과하면 **"solved inaccurate"나 "solved"로도 보고된다**
> (OSQP v1.0.0 `osqp_api.c:908-931, 958-965`). 실측 절단 31건 중 9건이 이렇게 보고됐다.
> 그래서 status 문자열만으로는 발동을 분리 집계할 수 없다. 발동 판정은 `improved/mpc.py`의
> `time_limit_fingerprint`(status+반복 수)로 바꿨다.
> 근거: [STATIC_ANALYSIS.md §3](../../docs/verification/ci/run6_cause/STATIC_ANALYSIS.md), [S5_IMPACT.md §2](../../docs/verification/ci/run6_cause/S5_IMPACT.md),
> [raw/S6_fingerprint_check](../../docs/verification/ci/run6_cause/raw/S6_fingerprint_check/README.md).

### 0-3. 조향 허용오차 초과 6건과 max_iter의 관련성 (1회차 저장 로그만 사용, 재실행 없음)

`thesis_v2/results/eval_final/{S4,S5,S6}.json`의 저장된 집계(`violation_breakdown`,
`max_iter_count`)를 재확인(재실행 아님)한 결과, 6건이 발생한 5개 시나리오 배치
전부에서 `max_iter_count>0`(11~35/100)이었습니다(상세 표는 이전 판 그대로,
`repro/2c_analysis/eval_independent_evidence.py`·`eval_timing_analysis.py` 출력
참고). 다만 저장 로그가 시나리오 단위 집계뿐이라 "그 위반 스텝의 solver_status"는
직접 확인 못 함 — **정황적 연관 가능성만 있고 인과관계는 확정 못 함**. 이번 v2의
로깅 보강(§1-3)으로 다음에는 스텝 단위로 직접 확인 가능해집니다.

---

## 1. I5 — 반복 상한 MPC (주 메커니즘, 결정론 유지)

### 1-0. 메커니즘 변경 근거

**변경 전(설계 초안)**: `time_limit`(wall-clock)을 주 상한으로 사용.
**변경 후(이번 확정)**: **`max_iter`(반복 횟수)를 주 상한**으로 사용하고,
`time_limit`은 정상 상황에서 걸리지 않는 넉넉한 값(45ms)으로 **최후 안전망**에만
둔다.

**이유**: `time_limit`은 그 순간의 PC 부하(다른 프로세스의 CPU 점유, OS 스케줄링)
에 따라 "몇 번째 반복에서 끊기는지"가 실행마다 달라질 수 있습니다. OSQP의 반복은
warm-start 상태·문제 데이터가 같으면 **반복 경로 자체는 결정론적**이지만, "시간이
다 돼서 N번째 반복에서 끊겼다"는 판단은 벽시계 기준이라 **같은 seed를 재실행해도
끊기는 반복 횟수(따라서 그 스텝의 조향 출력)가 달라질 수 있습니다**. 이는
`thesis_v2/tests/golden/`의 "같은 입력 → 완전히 같은 조향 시계열" 재현성 요건과
충돌합니다. `max_iter`는 반복 횟수 자체를 상한으로 걸므로 **같은 문제 데이터·같은
warm-start면 항상 같은 반복에서 멈추는 결정론적 컷오프**입니다. `time_limit`은
"이론상 max_iter보다 훨씬 먼저 걸릴 일이 없는 값"으로 걸어두는 순수 안전망(예:
호스트가 예상보다 훨씬 느린 경우의 최후 방어선)이며, 발동 시 별도로 기록해
정상 경로(반복 상한)와 구분합니다.

> **[정정 2026-10-14, run #6 조사 — 원문은 위에 그대로 둠]**
> "결정론적 컷오프"는 **반복 상한 경로에만** 맞다. time_limit은 계산이 느릴 때만이 아니라 실행 환경이 한 solve
> 안에서 45 ms 넘게 멈출 때(OS·VM 스케줄링, 백그라운드 작업으로 추정)도 발동한다. 발동하면 같은 입력의 결과가 달라진다.
> - GitHub windows 러너(부하 없음): time_limit 켬 16/500·11/1500 회차 불일치, 끔(1e10) 0/500·0/1500.
> - 불일치마다 첫 불일치 solve는 입력이 같았고 시간 절단 흔적이 있었다(run #6 실패 재현).
> - 대응(사용자 결정): 제품의 time_limit 안전망은 유지한다. 결정론 비교 테스트는 `thesis_v2/conftest.py`의
>   `i5_time_limit_off` fixture로 time_limit을 끄고 검증한다. 발동 판정은 지문 규칙으로 바꿨다.
> 근거: [run6_cause/README.md §1·§4](../../docs/verification/ci/run6_cause/README.md), [S4_RESULT.md](../../docs/verification/ci/run6_cause/S4_RESULT.md).

### 1-1. 반복 1회당 시간 측정 → 시간 예산별 반복 상한 계산

**측정**: `repro/2c_analysis/i5_iter_time_benchmark.py`(신규, 읽기 전용 — 1회차
`ImprovedMPC`(I1+I1b+I2'+I3 조합)를 그대로 인스턴스화하고 `mpc.prob.solve`만
monkeypatch로 감싸 매 호출의 `(res.info.iter, res.info.run_time)`을 기록,
`thesis_v2/improved/` 파일은 전혀 수정하지 않음). 표본: paper dev seed
100~199(평상시 100 에피소드) + S6 ψ0=±15° dev seed 1000~1099(1회차에서 max_iter가
가장 잦았던 어려운 케이스, 200 에피소드) + S7a width=0.20 dev seed 1000~1099
(마찬가지로 어려운 케이스, 100 에피소드) — 총 solve 호출 **45,789회**.

**결과**(`repro/2c_analysis/out/i5_iter_time_benchmark.json`, 3층PC104 참고값):

| 지표 | mean | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| 반복 횟수(iter) | 250.5 | 25 | 475 | 5750 | 20000 |
| solve 시간(ms) | 0.529 | 0.086 | 0.967 | 11.25 | 49.27 |
| **반복 1회당 시간(ms/iter)** | 0.00333 | 0.00341 | 0.00399 | **0.00514** | 0.05514 |

(상태 분포: `solved` 45,617 / `maximum iterations reached` 171 / `solved
inaccurate` 1 — 표본에 어려운 케이스를 의도적으로 포함시켰음에도 대부분은
"solved"이고, 반복 1회당 시간은 대체로 안정적(p95=0.00399ms)이지만 아주 드물게
느려짐(max=0.05514ms, 조건수가 특히 나쁜 반복 1회).)

**시간 예산 → 반복 상한 계산** (반복 상한 = ⌊예산(ms) / p99(0.00514ms/iter)⌋,
p99를 쓰는 이유: 평균이 아니라 "느린 반복이 섞여도 그 예산 안에서 끝난다"는
보수적 보장을 위해):

| 예산 | 반복 상한 후보 | 계산 |
|---|---|---|
| 5ms | **972** | ⌊5/0.005144⌋ |
| 10ms | **1944** | ⌊10/0.005144⌋ |
| 20ms | **3888** | ⌊20/0.005144⌋ |
| 30ms | **5832** | ⌊30/0.005144⌋ |

**선택 규칙**(유지): 위 4개 후보를 dev에서 ablation으로 비교해 **"안전성
비열화(원래 제약 위반·충돌률·S3 실패율)가 없는 가장 낮은 값"**을 채택합니다
(§2 판정 기준, §7 dev ablation 결과로 확정 — 아래 채택 결과는 §7-3 참고).

**참고(위험 신호)**: 실측 반복 횟수의 p99(5750)·max(20000, 즉 1회차의 `_MAX_ITER`
자체에 걸린 사례 존재)가 반복 상한 후보(972~5832) 전부보다 큽니다 — 즉 4개 후보
전부 "1회차라면 계속 반복했을 어려운 solve"를 실측 표본 안에서 조기 컷오프시킬
가능성이 있고, 이는 dev ablation에서 hard_ok 통과율·I3 발동률로 직접 관찰해야
합니다(§1-4).

### 1-1-보강. 공식 측정 호스트(DESKTOP-MDCKRJS) 실측 환산표 (2026-09-24 추가)

§0-1에서 이미 확인했듯 이 문서의 §1-1 벤치마크는 **3층PC104**(Python 3.11.9,
osqp 1.1.3)에서 수행됐으나, 실제 dev/eval을 실행하는 **공식 측정 호스트는
DESKTOP-MDCKRJS**(`env.json`의 `is_official_measurement_host: true`, `.venv`
Python 3.9.12, osqp 1.1.1)입니다. 같은 벤치마크 스크립트(`repro/2c_analysis/
i5_iter_time_benchmark.py`, 읽기 전용, 표본 동일: paper dev seed 100~199 + S6
ψ0=±15 dev seed 1000~1099 + S7a width=0.20 dev seed 1000~1099, solve 호출
45,789회)를 DESKTOP-MDCKRJS(AC 연결, 최고 성능 모드)에서 그대로 재실행해
`repro/2c_analysis/out/i5_iter_time_benchmark_DESKTOP-MDCKRJS.json`에 저장했고,
3층PC104 결과는 `..._3PC104.json`으로 보존했습니다.

**반복 횟수(iter) 분포는 두 호스트에서 완전히 동일**합니다(mean 250.52032147...,
p50 25, p95 475, p99 5750, max 20000 — 소수점까지 일치) — 반복 경로가 문제
데이터·warm-start에만 의존하고 호스트 성능과 무관하다는 §1-0의 결정론 주장을
실측으로 재확인합니다. 반면 **반복 1회당 시간(ms/iter)은 호스트마다 다릅니다**
(DESKTOP-MDCKRJS가 더 빠름):

| 항목 | 3층PC104(2026-09-22) | DESKTOP-MDCKRJS(공식 측정 호스트, 2026-09-24, AC+고성능모드) |
|---|---|---|
| 반복 1회당 시간 p99(ms/iter) | 0.005144 | 0.0043765 |
| 반복 1회당 시간 mean/p50/p95/max(ms/iter) | 0.00333/0.00341/0.00399/0.05514 | 0.00226/0.00227/0.00260/0.05362 |

**반복 상한 값(972/1944/3888/5832)은 결정론 유지를 위해 변경하지 않습니다.**
아래는 그 고정된 4개 후보가 **이 호스트에서 실제로 몇 ms에 해당하는지**를
역산한 라벨(호스트별 p99 ms/iter × 후보 반복 수)입니다 — 실험 파라미터가
아니라 참고용 재라벨입니다:

| 반복 상한(고정) | 3층PC104 기준 라벨(정의) | DESKTOP-MDCKRJS 실제 환산(p99 기준) |
|---|---|---|
| 972 | 5ms | **4.25ms**(=972×0.0043765ms) |
| 1944 | 10ms | **8.51ms** |
| 3888 | 20ms | **17.02ms** |
| 5832 | 30ms | **25.52ms** |

DESKTOP-MDCKRJS가 3층PC104보다 반복당 약 15% 빠르므로, 같은 반복 상한이 이
호스트에서는 더 적은 ms로 끝납니다 — 즉 20Hz 예산(50ms) 대비 안전 여유가
3층PC104 기준보다 이 호스트에서 더 큽니다. 다만 이 표는 p99 통계 기반 참고
환산일 뿐이고, 실제 판정은 §2 절차대로 dev ablation의 실측
`mpc_solve_ms_p99/max`(DESKTOP-MDCKRJS에서 직접 측정)로 합니다.

### 1-2. 시간 초과 시 처리 (기존 I3 하드체크 구조 재사용, 반복 상한·시간 상한 공통)

`thesis_v2/improved/mpc.py:379~394`(1회차, 동결)의 `"maximum iterations reached"`
분기를 그대로 재사용하되, `"run time limit reached"`(안전망 발동 시)도 **같은
분기**로 묶습니다(새 상태 문자열을 튜플에 추가하는 것 외 로직 변경 없음):

```
elif status in ("maximum iterations reached", "run time limit reached"):
    hard_ok = |delta0| <= DELTA_MAX_DEG + eps_abs
              (I1 on이면 |delta0 - delta_prev| <= rate + eps_abs 도 확인)
    hard_ok 만족 -> 그 근사해 사용 (solver_status 그대로 기록)
    hard_ok 불만족 -> I3(직전 성공 해 shift) 시도
                       I3도 불가(직전 해 없음) -> 비례 fallback(K_P_FALLBACK)
```

I5 활성 시 OSQP 설정은 `max_iter=<채택된 반복 상한>`, `time_limit=0.045`(45초
아님, 45ms=0.045초 — 안전망, 반복 상한이 정상적으로 훨씬 먼저 걸리므로 정상
상황에서 발동하지 않아야 함)로 변경합니다. I5 비활성(플래그 off) 시에는
`max_iter=20000`만 설정하고 `time_limit`은 아예 넘기지 않아(**1회차와 kwargs
완전히 동일**) OSQP 기본값(사실상 무제한, `1e10`초)이 적용됩니다 — 이 경로는
1회차와 바이트 단위로 동일합니다.

### 1-3. 로깅 보완 (제어 로직 아님, §0-3 공백 메우기)

`thesis_v2/improved/mpc.py`의 `MPCResult`에 필드 2개 추가: `iterations: int`
(`res.info.iter`), `time_limit_hit: bool`(`status=="run time limit reached"`).
`thesis_v2/improved/runner.py`의 `EpisodeResult`에 추가:
- `time_limit_count`, `time_limit_rejected_count`(기존 `max_iter_count`/
  `max_iter_rejected_count`와 동일한 방식으로 별도 집계)
- `notable_step_log: List[dict]` — **아래 조건 중 하나라도 해당하는 스텝만**
  기록(전체 스텝을 다 남기면 S3 961격자류에서 용량이 커지므로 "주목할 만한
  스텝"만 선별): `solver_status`가 `maximum iterations reached`/`run time
  limit reached`이거나, 조향각/조향변화율/차로/헤딩 중 하나라도 허용오차를
  넘겼을 때. 각 항목에 `step, state, solver_status, iterations, time_limit_hit,
  approx_rejected, fallback_used, warm_start_shift_used, angle_excess_deg,
  rate_excess_deg, lane_excess_m, heading_excess_deg`를 기록합니다.

### 1-4. 위험 요인

- **반복 상한이 1회차의 실제 필요 반복보다 낮아 hard_ok 통과율이 떨어질 가능성**
  (§1-1 참고 — 실측 p99/max 반복 횟수가 후보 4개보다 큼). dev ablation에서
  `max_iter_count`(정확히는 "반복 상한 도달 횟수"로 명칭 유지)·I3 발동률이
  1회차보다 늘어나는지 직접 확인.
- **호스트 성능 의존성**: 반복 상한 자체는 결정론적(호스트 무관, 반복 횟수는
  CPU 속도와 무관하게 같은 문제·같은 warm-start면 항상 동일)이지만, "시간
  예산 5/10/20/30ms → 반복 상한 972~5832"라는 **환산 비율(ms당 반복 수)은
  호스트 성능에 의존**합니다. 노트북이 이 호스트보다 느리면 같은 반복 상한이
  더 많은 ms를 소모할 수 있어(또는 반대), §6의 노트북 일괄측정에서 실측
  ms/iter를 다시 재보고 반복 상한이 여전히 그 예산 안에 드는지 확인 필요.
- **`time_limit`(45ms) 안전망 자체의 비결정성**: 정상 상황에서는 반복 상한이
  먼저 걸려 발동하지 않아야 하지만, 만약 발동한다면(호스트가 극단적으로
  느려짐 등) 그 스텝은 §1-0의 결정론이 깨집니다 — 이는 "안전망이 실제로
  필요했던 예외 상황"이므로 감수하되, `time_limit_hit=True`로 반드시 로깅해
  발생 여부·빈도를 dev/eval에서 관찰합니다(정상 dev/eval에서는 0건이어야
  기대대로인 것).

> **[정정 2026-10-14, run #6 조사 — 원문은 위에 그대로 둠]**
> - 발동 원인은 "호스트가 극단적으로 느려짐"에 그치지 않는다. 평소 0.1~3 ms인 solve가 한 번에 45~106 ms 멈춘
>   일시 정지로도 발동했다(windows 러너, 이 PC 부하 조건).
> - `time_limit_hit=True`(당시 정의: status=="run time limit reached")는 발동의 일부만 잡았다(31건 중 22건).
>   정의를 지문 규칙으로 바꿔 로깅 보장을 회복했다(기록 전용, 제어 출력 불변).
> 근거: [S5_IMPACT.md §2](../../docs/verification/ci/run6_cause/S5_IMPACT.md), [S4_RESULT.md](../../docs/verification/ci/run6_cause/S4_RESULT.md).

### 1-5. golden 결정론 확인 (완료 조건에 추가)

`thesis_v2/tests/golden/`의 기존 golden(seed 0~2, baseline·v1 조향 시계열
바이트 동일 비교)에 더해, **I5 on 상태로 같은 golden 시나리오를 3회 반복
실행해 조향 시계열이 3회 모두 완전히 동일한지**를 새 확인 항목으로
추가합니다(반복 상한 방식이므로 통과해야 정상 — §7 Stage 1 완료 조건).

> **[정정 2026-10-14, run #6 조사 — 원문은 위에 그대로 둠]**
> "통과해야 정상"은 time_limit 미발동이 전제다. time_limit이 켜진 상태에서는 이 테스트가 확률적으로 실패한다
> (CI run #6 windows, 러너 재현 3/500·5/1500).
> 지금은 `i5_time_limit_off` fixture로 time_limit을 끄고 **반복 상한 경로의 결정론**을 검증한다.
> 발동 경로는 `test_i5_time_limit_safety_net_reachable`·`test_i5_time_limit_hit_*`가 따로 검증한다.
> 근거: [run6_cause/README.md](../../docs/verification/ci/run6_cause/README.md).

### 1-6. osqp 1.0.4 / 1.1.x 호환성 확인 방법 (참고, 안전망 문자열 확인용)

두 버전 모두 Python 인터페이스는 `OSQP().setup(..., **settings)`로 동일하게
`time_limit`/`max_iter`를 받습니다. `max_iter`는 버전에 무관하게 반복 횟수
정수로 동작이 동일(주 메커니즘이라 위험 낮음). `time_limit`(안전망) 상태
문자열만 환경마다 확인 필요 — 이 문서 §0-2와 동일한 독립 스크래치 스크립트를
그 환경에서 1회 실행해 `"run time limit reached"` 문자열을 그대로 반환하는지
확인(노트북은 Python 3.9/`requirements-py39.txt`, osqp 버전을 실행 전
`pip show osqp`로 먼저 확인).

---

## 2. 판정 기준 (실행 전 확정)

1회차 판정 기준을 **전부 유지**하고 아래를 추가합니다:

| 지표 | 측정 방법 | 조건 |
|---|---|---|
| MPC solve 최대 시간 | `time.perf_counter()`, dev 전체 배치의 max | 참고(호스트별 상대값, 공식 판정은 노트북 일괄측정) — 반복 상한 채택 자체의 판정 기준은 아래 "원래 제약 위반"·"충돌률" 기준 |
| 반복 상한 도달률(`max_iter_count`, 명칭 유지) | 도달 스텝 수 / 전체 MPC 호출 수 | 참고 지표 |
| `time_limit_hit`(안전망 발동) 횟수 | 카운트 | **dev/eval에서 0건이 기대값**(발생 시 원인 규명 — 반복 상한 계산이 실제 호스트 성능과 어긋났다는 신호) |
| 반복 상한 도달 시 I3 발동률 | `max_iter_hit` 중 `hard_ok` 실패 비율 | 참고 지표 — 1회차 대비 크게 늘면(자릿수 단위 증가) 그 상한 후보는 다음 순위로 재검토 |
| 원래 제약 위반(차로·헤딩·조향각·조향변화율) | 1회차와 동일 방식 | **1회차 대비 비열화 금지**(추가 위반 발생 시 그 후보는 기각) |
| 충돌률·S3 실패율·paper 종합 | 1회차와 동일 | **1회차 개선판 대비 악화 없음**(최우선, 협상 대상 아님) |
| I2 장애물 여유 미달 | 1회차와 동일 | 정보성(동일 처리) |

> **[정정 2026-10-14, run #6 조사 — 원문은 위에 그대로 둠]**
> 위 표 `time_limit_hit` 행 정정:
> - (1) 발생은 "반복 상한 계산이 호스트 성능과 어긋났다는 신호"만이 아니다. 실행 환경의 일시 정지로도 생긴다.
> - (2) 측정 방법은 status 문자열이 아니라 지문 규칙(`time_limit_fingerprint`)이다.
> - 저장된 eval 2회차(v2)와 anomaly eval에는 모든 solve가 45 ms 미만이라 절단이 없었다. 그래서 기록된 0건은
>   새 정의에서도 0건이다(첫 solve 제외, [S5_IMPACT.md §1](../../docs/verification/ci/run6_cause/S5_IMPACT.md)).

**상한값 확정 절차**: 4개 후보(972/1944/3888/5832)를 dev 전체 트랙(§3)에서
ablation으로 실행 → 위 표의 "비열화 금지" 조건을 만족하는 후보 중 **가장 낮은
값**을 채택 → 그 값으로 (승인 후) eval 1회 실행.

---

## 3. dev 검증 범위 (1회차의 공백 재발 방지)

1회차는 paper·S3·S4만 dev 재검증하고 S5~S7은 재검증 없이 eval을 실행해, eval
에서야 위반이 드러났습니다(`RESULT_IMPROVED.md` §5-2). v2는 **dev 단계에서
7개 트랙 전부**를 실행합니다:

| 트랙 | dev seed/격자 |
|---|---|
| paper | seed 100~199 |
| S3 | front_gap0 0.525~1.975/0.05, y0 -0.145~0.145/0.01 (1회차 dev와 동일, eval 격자에서 반 칸 오프셋, 30×30=900 cell) |
| S4 | seed 1000~1099, 노이즈 3종 |
| S5 | seed 1000~1099, 지연 1·2 step |
| S6 | seed 1000~1099, ψ0 7종 |
| S7a | seed 1000~1099, 장애물 크기 9종 |
| S7b | seed 1000~1099, rear_gap 4종 |

(left_obstacle은 SAFE_STOP 경로만 쓰고 MPC를 호출하지 않아 I5와 무관 — 이번
ablation에서는 생략하고, §7 Stage 3에서 최종 확정 조합으로 1회만 재확인.)

5개 조합(1회차 최종 조합 v1 + 반복상한 4개 후보) × 7개 트랙을 dev에서 실행 후
§2 절차로 상한값을 확정합니다.

---

## 4. 새 eval 데이터 (2회차, 기존 eval과 물리적으로 분리)

| 트랙 | 새 eval seed/격자 |
|---|---|
| paper / left_obstacle | seed 200~299 |
| **S3(정정)** | **간격은 원래 0.01 그대로 유지**, 격자를 **반 칸(0.005) 오프셋**. `front_gap0`: 원래 `0.50~2.00/0.01` 간격 축(1회차 eval은 0.05 간격, 31×31=961격자였음 — 정정: 1회차 eval 격자 간격은 `np.arange(0.50,2.0001,0.05)`(31개)×`np.arange(-0.15,0.1501,0.01)`(31개)=961. 새 eval은 같은 간격(0.05/0.01) 구조를 유지하되 축 자체를 반 칸 옮김) → `front_gap0 = 0.525~1.975 step 0.05`(1회차 dev와 같은 축, 30개), `y0 = -0.145~0.145 step 0.01`(1회차 dev와 같은 축, 30개) — **범위는 y0∈[-0.15,0.15](개정 2, REQ-SIM-03) 안에 그대로 있고, 격자 칸 수는 900(30×30)으로 1회차 eval(961)과 다른 새 표본**. (주의: 이 축은 1회차 **dev**에서 이미 쓴 축과 동일 — 하지만 1회차 dev는 "v1 로직 자체"를 검증하는 데 썼고, 이번 v2 S3 eval은 "v1+I5" 조합을 새로 검증하는 것이므로 축이 같아도 **다른 목적의 새 실행**입니다. 완전히 새로운 좌표가 필요하다면 대안으로 0.5025~1.9975 step 0.05(front_gap0), -0.1475~0.1475 step 0.01(y0)처럼 1/4칸 오프셋도 가능 — 구현 시 최종 확정, 아래 "구현 시 확정" 표기) |
| S4~S7 | 각 조건에서 seed 200~299 |

**구현 시 확정 사항**: S3 새 eval 격자는 위 두 안(① 1회차 dev와 동일 축 재사용,
② 1/4칸 추가 오프셋으로 dev와도 다른 완전히 새로운 축) 중 하나를 Stage 4(eval,
별도 승인) 직전에 확정합니다 — 이 문서에서는 "간격 0.01 유지, y0 범위
[-0.15,0.15] 안, 반 칸 오프셋"이라는 **원칙**만 확정하고 절대 좌표는 eval
실행 직전 승인 요청 시 함께 제시합니다(결과를 보고 좌표를 고르는 것이 아니라
실행 전에 좌표 자체를 먼저 고정하기 위함).

**기존 eval(seed 0~99, 원래 961격자)은 "연속성 참고"로만 함께 실행·보고**하고
v2의 최종 판정 근거로는 쓰지 않습니다.

---

## 5. I4(Student 재학습) 연결 계획

`DESIGN_IMPROVED.md` §6의 I4 계획은 **v2가 최종 확정된 뒤** 그대로 이어집니다.
I4의 학습 데이터는 **v2 MPC(I1+I1b+I2'+I3+I5, v2 eval로 확정된 반복 상한
포함)**로 생성합니다.

논문 핵심 주장 3(신경망 임베디드 적용 여지)의 핵심 논거는 "MPC는 최악의 경우
계산 부담이 크지만(v1: 관측 최대 40.5~44.9ms, v2: 설계상 상한 이하로 보장),
Student는 일정한 추론 시간을 갖는다"입니다. v2로 MPC의 최악 시간에 **반복
횟수 기준의 명시적 상한**이 생기면(호스트 무관하게 반복 횟수 자체는 상한이
걸림), "Student 추론 시간이 MPC 최악 시간 대비 몇 %인가"라는 비교가 v1(상한
없음, 관측값에만 의존)보다 더 방어 가능한 주장이 됩니다. `RESULT_STUDENT.md`의
기존 M트랙 측정치는 v1 MPC 기준이므로, v2 확정 후 **M트랙을 v2 MPC 기준으로
재측정**하는 것을 I4 착수 전 선행 작업으로 `NEXT_SESSION.md`에 추가합니다
(계획만, 실행 없음).

---

## 6. 노트북 일괄 측정 대상 목록 갱신

`NEXT_SESSION.md` §4의 "버전 목록"을 아래로 갱신합니다(실행은 3단계 전체
완료 후, 사용자가 노트북에서 진행):

| 버전 | 상태 | 비고 |
|---|---|---|
| `thesis_v2/baseline`(v1.1, front_gap 버그 수정판) | 확정 | 2단계 종료 시점 커밋 기준 |
| `thesis_v2/improved` v1(I1+I1b+I2'+I3) | 확정(eval 완료) | 커밋 `4652e32` |
| `thesis_v2/improved` v2(v1+I5=972) | **확정(eval 완료, 공식 계산시간 측정 완료)** | eval 커밋 `16e108b`/`e588eed`, 계산시간 공식측정 `RESULT_IMPROVED.md` §12(2026-09-25) |
| Student(PyTorch) | 기존 측정(v1 MPC 데이터 기준) | v2 확정 후 재측정 필요(§5) |
| Student(ONNX) | 기존 측정(v1 MPC 데이터 기준) | v2 확정 후 재측정 필요(§5) |

시나리오·실행 순서·전원 조건 확인 절차는 `NEXT_SESSION.md` §4 기존 내용을
그대로 따르고, 버전이 5개로 늘었으므로 같은 세션에서 끊지 않고 연속 실행해야
하는 총 소요 시간을 실행 전에 다시 추정해 안내합니다(명령 예시만 제시, 실행은
사용자).

---

## 7. 구현 순서와 진행 상황

| Stage | 내용 | 완료 조건 | 상태 |
|---|---|---|---|
| 0 | `improved/config.py`에 `ENABLE_I5_ITER_CAP_MPC` 플래그 + `I5_MAX_ITER`/`I5_TIME_LIMIT_SEC` 파라미터 추가, 플래그 False 시 1회차와 OSQP `setup()` kwargs 완전 동일 | golden(seed 0~2) 6/6 PASS, pytest 전체 통과 | 이번 세션에서 진행 |
| 1 | I5 구현(§1-2 하드체크 분기 확장), §1-3 로깅 보완, §1-5 golden 결정론 확인 | 단위테스트 통과 + golden 반복 실행 결정론 확인 | 이번 세션에서 진행 |
| 2 | dev에서 반복 상한 4개 후보 × §3의 7개 트랙 전부 실행 | §2 판정표 전부 기록 | **완료**(2026-09-24, DESKTOP-MDCKRJS, 5조합×7트랙 17,500 에피소드-런, `thesis_v2/results/dev_ablation_i5/20260924_205916_DESKTOP-MDCKRJS_full/`) |
| 3 | §2 절차로 상한값 1개 채택(제안) | dev 수치 근거로 제안, eval 미실행 | **완료 — cap=972(5ms 후보) 채택**. §9 참고 |
| 4 | eval 1회 실행(§4 새 seed, S3 좌표 최종 확정) + 연속성 참고용 기존 eval 재실행 | **별도 승인 후에만** | **완료(승인됨)**(2026-09-24 실행, 2026-09-25 승인) — 커밋 `16e108b`(준비) 기준 실행, 결과 커밋 `e588eed`. baseline/v1/v2 3-way 전부 협상불가 기준 통과(충돌 27서브그룹 전부 v1=v2=0, S3 81/900→0, v1↔v2 역전 0건). 상세 판정·노름 검증·계산시간 성격 규명(§9, (다) 혼재 — v2 최댓값 비재현 확인, 주 지표 max→p99 정정)은 `RESULT_IMPROVED.md` §8~11 |
| 5 | (보류) I4 M트랙 v2 재측정, Student 재학습 | Stage 4 완료 후 | Stage 4 완료로 착수 가능 — 아직 미실행 |

각 Stage 종료 시 `pytest thesis_v2/tests -q` + golden 체크로 baseline·v1 무회귀
확인(2026-09-24 재확인: 155 passed, I5 golden 결정론 3회 반복 PASS 포함).

**dev ablation p99 집계의 한계(2026-09-24)**: `run_dev_i5_ablation.py`의 `_aggregate()`는
서브그룹(트랙 내 세부 조건)별 p99/max만 저장해, 트랙·조합 전체를 합친 "진짜" 전체 p99는
사후에 재계산할 수 없었다(퍼센타일은 단순 평균으로 합쳐지지 않음 — §9 판정표의 p99
열은 "서브그룹 p99 중 최댓값"이라는 보수적 프록시). **이후 실행부터는 원시 solve 시간
배열(`mpc_solve_ms_all`)도 함께 저장하도록 스크립트를 보강**했다(이번 dev ablation
재실행은 하지 않음 — 다음 실행부터 적용).

---

## 9. dev ablation 판정표·허용오차 정정·채택 결과 (2026-09-24, DESKTOP-MDCKRJS)

전체 판정표(조합별 충돌률·S3 실패·원래 제약 위반 세부·solve 시간·상한 도달률·I3
발동률)와 채택 근거는 대화 보고로 기록했고(이 문서에는 결론만 남김), 정정 근거는
`SETTINGS_DECISION.md` §19, 정정 반영은 `THESIS_REVISION_LOG.md`(2026-09-24 항목)·
`RESULT_IMPROVED.md` §2-3/§5-6에 있다.

- 협상 불가 기준(충돌률 0/2600, S3 실패 0/900)은 5개 조합(v1 + I5 4후보) 전부 통과.
- §19 정정(조향각/조향율 허용오차에 `eps_rel` 항 반영)을 적용하면 조향 관련 위반은
  5개 조합 전부 0건으로 재판정됨(정정 전 1~16건은 전부 eps_abs 경계 수준 수치오차).
- 남은 "원래 제약 위반" 비교 대상은 **lane(차로 위치제약)뿐**: v1 대비 cap=972만
  개선(count 45→34, max/누적도 감소), cap=1944/3888/5832는 전부 악화(count 최대
  +11, max 최대 2배).
- **채택**: `I5_MAX_ITER = 972`(§1-1 시간예산 5ms 후보) — "안전성 비열화 없는 가장
  낮은 값" 규칙상 비열화 없는 유일한 후보이자 최저 예산 후보로 동시에 결정됨. 이
  호스트(DESKTOP-MDCKRJS) 실측 기준 solve 최대시간 38.164ms(v1, I5 없음) →
  13.593ms(cap=972, **−64.4%**).
- `improved/config.py`의 `I5_MAX_ITER` 기본값 반영은 아직 하지 않음(이 문서에 결론만
  기록 — eval 준비 단계에서 반영 여부 별도 확인 후 진행).

---

## 8. 확정 사항 요약

- I5 주 메커니즘은 **반복 상한(`max_iter`)**, `time_limit`(45ms)은 안전망(정상
  상황에서 미발동 기대, 발동 시 로깅으로 관찰)
  - **[정정 2026-10-14, run #6 조사]** "정상 상황에서 미발동"은 부하 없는 CI 러너에서도 성립하지 않았고,
    발동하면 결정론이 깨진다. 발동 로깅은 지문 규칙으로 바꿨다. 결정론 테스트는 time_limit off fixture로 검증한다
    ([run6_cause/README.md](../../docs/verification/ci/run6_cause/README.md), 위 §1-0·§1-4 정정).
- 반복 1회당 시간(3층PC104, I1+I1b+I2'+I3 조합, 45,789회 solve 실측): p99
  0.00514ms/iter → 반복 상한 후보 **972/1944/3888/5832**(예산 5/10/20/30ms)
- 조향 허용오차 초과 6건은 이번 v2로 해소를 보장하지 않음 — §0-3에서 정황적
  연관 가능성만 확인, 실제 해소 여부는 dev/eval 실행 후 확인 대상
- dev는 7개 트랙 전부 포함(1회차 공백 재발 방지, left_obstacle은 MPC 미사용이라
  제외), eval은 새 seed 200~299대 + S3 반 칸 오프셋 격자로 1회만 실행(별도 승인),
  기존 eval은 연속성 참고로만 병기
