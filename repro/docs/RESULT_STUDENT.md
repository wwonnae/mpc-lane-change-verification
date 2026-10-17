# 2단계-D: M트랙(신경망 적용 여지) 결과

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

`MEASURE_PLAN.md` M트랙 절의 판정 기준을 그대로 적용합니다. 판정 기준 자체는 이 문서
작성 중 바꾸지 않았습니다. 실행 코드: `thesis_v2/tests/compare/run_m_track.py`
(`old_mpc_wrapper.py`를 통해서만 `legacy_2025/final_hierarchical_backup_thesis_1204.py`를 import —
repro/docs/WORK_RULES.md 예외 허용 위치). 원자료: `thesis_v2/results/20260918_090132_3층PC108_m_track/`
(`env.json`/`sanity.json`/`timing.json`/`mae.json`).

**측정 환경(M트랙 전용, MEASURE_PLAN.md 2026-09-18 추가 원칙에 따름)**: SSAFY PC
(hostname `3층PC108`, Intel Core i7-9700, Windows 11, Python 3.12.9, torch 2.11.0+cu128,
torch 스레드 8) — P트랙 공식 환경(노트북)과 다른 호스트입니다. 절대 계산시간(ms)은
참고치이며, 판정 대상은 MPC 대비 Student의 배수(중앙값 기준)입니다.

---

## §1. (a) 사전 확인

| 확인 항목 | 결과 |
|---|---|
| `legacy_2025/models/policy_best.pth` 로드 | 성공, `model.eval()` 적용 확인(`sanity.json.eval_mode_applied=true`) |
| `normalization_stats.json` feature_names 순서 | REQ-STU-02와 정확히 일치(`[v, ey_line, front_gap, left_clear, state_KEEP_L2, state_EVADE_L, state_KEEP_L1, state_RETURN_TO_L2, state_SAFE_STOP]`), 로더에서 assert로 강제 확인 |
| Student 9차원 입력을 baseline 로그에서 구성 가능한가 | **가능** — 매핑표는 §2 |
| 입력 표본 수 | 12,016 스텝(paper+left_obstacle, seed 0~99, MPC가 실제로 호출된 스텝 전부 — 표본 선별 없음) |

**결론: 막힘 없음 — 조향 오차 측정을 "무효" 처리할 필요 없음**(MEASURE_PLAN.md M트랙 기준).

## §2. 매핑표 (Student 9차원 ← baseline `steps.npz` 필드)

| Student feature | baseline 로그 필드 | 비고 |
|---|---|---|
| `v` | `steps.v` (m/s) | 그대로 |
| `ey_line` | `steps.ey_line` (m) | **NaN(라인 미검출) 시 `y - target_line_y(state)`로 대체** — 임의 가정이 아니라 `legacy_2025/final_hierarchical_backup_thesis_1204.py:1874`의 `get_student_features()` fallback 공식을 그대로 재현한 것(확인됨, 코드 근거). 전체 12,016 스텝 중 **74.8%**가 이 fallback 경로(라인 미검출) |
| `front_gap` | `steps.front_gap` (m) | 그대로 |
| `left_clear` | `steps.left_clear` (bool→0/1) | 그대로 |
| `state_one_hot(5)` | `steps.state` (문자열) | 순서 `[KEEP_L2, EVADE_L, KEEP_L1, RETURN_TO_L2, SAFE_STOP]`(REQ-STU-02, normalization_stats.json과 일치) |

MPC가 실제로 호출된 스텝(라인 미검출 KEEP_L2/KEEP_L1 + 항상 MPC인 EVADE_L/RETURN_TO_L2)의
상태별 개수: EVADE_L 5,229 / RETURN_TO_L2 5,344 / KEEP_L2 975 / KEEP_L1 468.
SAFE_STOP은 MPC를 호출하지 않아(REQ-LAT-05, hold_last) 표본에서 제외됩니다.

---

## §3. (b) 계산시간 벤치마크

표본 수는 논문 서술(THESIS_PAGES.md: Table 8 Teacher 3,000회, Table 16 Student 6,000회)을
그대로 따랐습니다. warmup 50회 제외, 같은 입력 풀(12,016 스텝)에서 seed=42로 6,000개를
뽑고 그 앞 3,000개를 MPC 측정에 재사용(쌍 측정). MPC는 **baseline MPC**
(`thesis_v2.baseline.mpc.OSQPMPC`, 핵심 주장 1의 대상)를 기준으로 삼았습니다 — 옛 MPC가
아닌 이유: 임베디드 적용 여지 질문("이 baseline 시스템을 신경망으로 대체할 수 있는가")의
대상이 baseline이기 때문입니다.

| 측정 | mean(ms) | p50 | p95 | p99 | max | n |
|---|---|---|---|---|---|---|
| baseline MPC solve() | 0.1422 | 0.1383 | 0.1784 | 0.2166 | 0.3120 | 2,950 |
| Student 추론만(정규화 텐서 입력) | 0.2124 | 0.2038 | 0.2545 | 0.4310 | 0.6546 | 5,950 |
| Student 정규화 포함(feature 조립+정규화+추론+역정규화) | 0.2400 | 0.2293 | 0.2938 | 0.4860 | 0.6880 | 5,950 |

**배수(중앙값 기준, 판정 대상)**:
- MPC / Student(추론만) = 0.1383 / 0.2038 = **0.68배** — Student가 아니라 **MPC가 약
  1.47배 더 빠름**.
- MPC / Student(정규화 포함) = 0.1383 / 0.2293 = **0.60배** — **MPC가 약 1.66배 더 빠름**.

**판정(MEASURE_PLAN.md 기준: "참고용 배수 보고, 절대 임계치 없음")**: 배수 자체는
보고하되 절대 임계치 판정은 없음 — 이 환경에서는 **Student가 MPC보다 빠르지 않고 오히려
느립니다.**

**해석(추정, 근거 명시)**: baseline MPC는 2-state(y,ψ) QP로 변수 45개뿐인 매우 작은
문제라 OSQP(C 구현) 한 번 호출이 이미 0.14ms 수준으로 극히 빠릅니다(RESULT_BASELINE.md
§2와 일치). 반면 Student 추론은 PyTorch eager 모드로 4개 Linear+BatchNorm+ReLU 블록을
파이썬 레벨에서 순차 실행해 호출당 디스패치 오버헤드가 누적됩니다. **논문 Table 16이
Student를 5.30배 더 빠르다고 보고한 것과 방법론이 다를 가능성이 있습니다** — 옛 코드
저장소의 `legacy_2025/backup/compare_mpc_student.py`(2단계-D와 무관한 과거 스크립트, 참고용으로만 읽음)는
Student 추론에 **ONNX Runtime**(`onnxruntime.InferenceSession`)을 사용합니다(확인됨,
`legacy_2025/backup/compare_mpc_student.py:143`). ONNX Runtime은 그래프 최적화·오퍼레이터 퓨전으로 PyTorch
eager 대비 소형 MLP 단건 추론에서 훨씬 빠른 경우가 흔합니다. 이 M트랙은 MEASURE_PLAN.md가
지정한 방식(torch, `model.eval()`)대로 측정한 것이며, 논문 수치와는 **"다른 방법론
측정"으로만 각주 비교**하고 baseline·이 결과 자체를 바꾸지 않습니다.

---

## §4. (c) 조향 오차 (MAE)

입력 12,016 스텝 전부 사용(선별 없음). 학습 분포 밖(OOD) 비율은 연속형 4개 특징
(v, ey, front_gap, left_clear)의 |z-score|>3 기준.

| 비교 대상 | 전체 MAE(도) | 비고 |
|---|---|---|
| **1순위: 옛 MPC**(code_backup 12-04, `OSQPMPC`, 옛 파이프라인 가중치 그대로) | **21.95°** | §4-1 원인 분석 필수 참고 |
| 2순위(참고): baseline MPC | **9.70°** | 제어기 구조 차이가 섞임(SPEC_VS_OLDCODE.md) |

### 상태별 MAE

| 상태 | n | MAE vs 옛 MPC(도) | MAE vs baseline MPC(도) | 옛 MPC 풀이 성공률 | OOD 비율 |
|---|---|---|---|---|---|
| EVADE_L | 5,229 | 27.92 | 7.93 | 100% | 0.11% |
| KEEP_L1 | 468 | 26.23 | **0.18** | 100% | 0.0% |
| RETURN_TO_L2 | 5,344 | 18.44 | 13.14 | 100% | 0.0% |
| KEEP_L2 | 975 | 7.14 | 4.91 | 100% | 19.18% |

전체 OOD 비율(z-score 기준): **1.61%**.

### §4-1. 옛 MPC 대비 MAE가 큰 이유 — 확인된 원인: 옛 코드 자체의 비용함수 스케일링 버그

**확인됨(코드+수치 재현, 추정 아님)**: `legacy_2025/final_hierarchical_backup_thesis_1204.py`의
`OSQPMPC._build_P` 상당 부분(848~895행)은 Hessian 대각원소를 `qy`, `qpsi`, `rdelta`,
`rddelta` **원값 그대로**(2배 하지 않음) 사용하는데, `solve()`(906~964행)의 선형항은
`q[y_i] = -2.0*qy*target_y`로 **2배** 계수를 씁니다. 표준 QP 형태
`0.5*x'Px + q'x`에서 이는 `qy*(y-target)^2` 항의 그래디언트가 아니라
`qy*(y - 2*target)`이 되어, **y의 실제(무제약) 끌림점이 `target_y`가 아니라
`2*target_y`가 됩니다.**

- `target_y=0`인 상태(KEEP_L2, RETURN_TO_L2)에서는 `2*target_y=target_y=0`이라 버그가
  드러나지 않습니다.
- `target_y=W=0.30`인 상태(EVADE_L, KEEP_L1)에서는 끌림점이 `0.60`이 되어, y_limit(±0.45)
  박스에 막혀서야 멈춥니다. 재현: `y0=0.30`(정확히 목표 지점)에 대해 옛 MPC는 여전히
  `δ=+25°`(최대 조향, 목표에서 더 멀어지는 방향)를 반환하고, `y0=0.45`(박스 경계)에서야
  `δ=0°`가 됩니다(직접 재현, `repro/2c_analysis` 방법론과 동일하게 `solve()` 내부를
  단계별로 재구성해 확인 — 코드: 이 세션에서 임시 검증, 결과 파일 없음, 재현 스크립트는
  `thesis_v2/tests/compare/old_mpc_wrapper.py`의 `build_old_mpc`/`solve_old`로 누구나
  같은 입력을 넣어 재현 가능).
- 이 버그는 baseline MPC(`thesis_v2/baseline/mpc.py:_build_P`)에는 **없습니다** —
  baseline은 `2 * config.QY`로 이미 올바르게 2배 처리되어 있습니다(코드 확인). 즉 baseline은
  기존에 알려진 rΔδ 대각/차분 버그(SPEC_VS_OLDCODE.md)에 더해, **이번에 새로 발견된 이
  스케일링 버그도 우연히 함께 고쳐져 있었습니다**(baseline을 새로 작성하며 표준 QP 변환을
  따랐기 때문 — 의도적 수정이 아니라 REQ-MPC-02를 표준식대로 새로 구현한 결과).
- **해석**: KEEP_L1(target=0.30)에서 "옛 MPC 대비 MAE"가 26.2°로 크면서 "baseline MPC
  대비 MAE"는 0.18°로 거의 0인 것은, Student의 예측이 실제로는 **올바르게 구현된 MPC(=
  baseline)에 가깝고, 버그가 있는 옛 MPC와는 다르다**는 뜻입니다. 옛 MPC 쪽이
  "부정확한 기준"이라는 의미로 해석해야지, Student가 부정확하다는 뜻이 아닙니다.
- EVADE_L·RETURN_TO_L2는 두 기준(옛/baseline) 모두와 여전히 어느 정도 차이가 있어(7.9°,
  13.1°), 위 버그만으로 설명되지 않는 잔여 오차가 있습니다 — **추정**: (1) ey_line
  fallback 비율이 74.8%로 매우 높아 baseline이 만드는 입력 분포가 실제 Student 학습
  데이터 분포와 다를 수 있고(§2), (2) KEEP_L2에서 OOD 비율이 19.2%로 다른 상태보다
  훨씬 높아(front_gap 등이 학습 시 관측 범위 밖일 가능성) 분포 밖 입력에서 Student
  예측이 불안정할 수 있습니다. 이 분포 불일치 가설은 이번 측정에서 추가로 검증하지
  않았습니다(범위 밖).

**논문 Table 15(MAE 1.20°)와의 관계**: 이 결과는 논문이 사용한 원본 테스트셋이 아니라
baseline이 생성한 별도 데이터셋으로 측정한 **"다른 데이터셋 대체 측정"**입니다(직접
비교 금지, MEASURE_PLAN.md). 위 버그 분석에 비추어, 논문 Table 15의 1.20°가 어떤 기준
MPC(버그 포함/제외)로 측정됐는지도 이번 조사로는 확인하지 못했습니다 — 4단계(논문
개정판) 작업 시 확인이 필요합니다.

---

## §6. ONNX 재측정 (SSAFY PC 마지막 실행, 2026-09-18)

실행 코드: `thesis_v2/tests/compare/run_onnx_benchmark.py`. 원자료:
`thesis_v2/results/20260918_143759_3층PC108_onnx_benchmark/`
(`env.json`/`onnx_benchmark_result.json`, ONNX 모델 파일 `policy_student.onnx` 포함 —
`legacy_2025/models/`에는 아무 파일도 추가하지 않음, 가중치 원본 미수정).

### §6-1. 설치·변환

- `onnxruntime` 1.29.0(이미 전역 설치돼 있었음, `.venv --system-site-packages`로 그대로
  사용), `onnx` 1.22.0(이번에 `.venv`에 설치, `pip install onnx` 성공).
- 변환: `torch.onnx.export(..., opset_version=17, dynamo=False)`. torch 2.11의 기본
  경로(`dynamo=True`)는 `onnxscript` 미설치로 `ModuleNotFoundError` 발생(확인됨) —
  레거시 TorchScript 기반 exporter(`dynamo=False`)로 전환해 해결(경고 메시지 발생하지만
  변환은 정상 동작, torch 2.9+ 부터는 이 경로가 deprecated 예정이라는 안내). 입력
  shape `(1,9)`, `dynamic_axes`로 배치 축만 가변, 입력명 `input`/출력명 `output`.
  가중치는 `policy_best.pth`에서 그대로 읽어 export — 수정 없음.

### §6-2. 변환 검증 (같은 입력 1,000건, seed=7, baseline 궤적 입력 풀에서 샘플)

| 지표 | 값 |
|---|---|
| 정규화된 네트워크 출력 최대 절대 차이 | 5.96e-6 |
| 역정규화 후 δ(도) 최대 절대 차이 | 4.39e-5° |

**결론: PyTorch와 ONNX 출력이 fp32 수치오차 수준에서 사실상 동일**(변환 정상, 정확도
손실 없음).

### §6-3. 동일 조건 벤치마크 (스레드 1로 고정 — torch/onnxruntime intra/inter-op 모두 1,
`env.json`에 기록, 임베디드 단일 코어 가정 + 스레딩 오버헤드 배제 목적)

표본 수: baseline MPC/옛 MPC 3,000회, PyTorch/ONNX 6,000회(논문 Table 8/16 표본수),
같은 입력 풀에서 seed=42로 페어링, warmup 50회 제외.

| 측정 | mean(ms) | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| baseline MPC solve() | 0.1437 | 0.1398 | 0.1762 | 0.2151 | 0.2910 |
| **옛 MPC**(code_backup 12-04, 매 호출 P/A 재구성) | **1.0694** | **1.0435** | 1.2012 | 1.3263 | 10.8496 |
| PyTorch 추론만 | 0.1988 | 0.1945 | 0.2372 | 0.2905 | 0.6432 |
| PyTorch 정규화 포함 | 0.2251 | 0.2209 | 0.2573 | 0.3103 | 0.6415 |
| ONNX 추론만 | 0.0398 | 0.0391 | 0.0425 | 0.0659 | 0.3666 |
| ONNX 정규화 포함 | 0.0481 | 0.0467 | 0.0610 | 0.0824 | 0.1747 |

**배수(중앙값 기준)**:
- baseline MPC / PyTorch(정규화 포함) = **0.63배**(MPC가 1.58배 더 빠름, §3과 동일 경향)
- baseline MPC / ONNX(정규화 포함) = **2.99배** — ONNX로 바꾸면 Student가 MPC보다
  **빨라짐**(3배)
- PyTorch / ONNX(정규화 포함) = **4.73배**, (추론만) = **4.97배** — 런타임만 바꿔도
  거의 5배 차이

### §6-4. 옛 legacy_2025/backup/compare_mpc_student.py 측정 방식과의 차이

| 항목 | 옛 `legacy_2025/backup/compare_mpc_student.py`(code_backup, 참고용으로 읽기만 함) | 이번 측정(`run_onnx_benchmark.py`) |
|---|---|---|
| MPC 구현 | **실제 OSQP 미사용** — `self.solver=None`으로 방치하고 `solve()`는 P제어 휴리스틱 placeholder(주석: "In reality, you'd solve the full QP problem") | 실제 OSQP 2건(baseline 증분형, 옛 코드 매콜재구성형) 모두 측정 |
| Student 입력 차원 | 10차원(`np.random.randn(n,10)`), 현재 `normalization_stats.json`의 9차원과 **불일치** | 9차원(REQ-STU-02와 일치, assert로 확인) |
| Student 런타임 | ONNX Runtime 고정(PyTorch 비교 없음) | PyTorch eager + ONNX Runtime 둘 다 측정 |
| 반복 횟수 | `n_samples=1000` 하드코딩 | Teacher 3,000/Student 6,000(논문 표본수) |
| 전처리 포함 여부 | `predict()`가 정규화를 항상 포함(분리 측정 없음) | "추론만"/"정규화 포함" 분리 측정 |
| warmup 분리 | 없음(1,000회 전부 통계에 포함) | 있음(50회 제외) |
| 스레드 고정 | 기록 없음 | torch/ORT 모두 intra/inter-op=1 고정, `env.json` 기록 |
| 입력 출처 | `np.random.seed(42)`, 순수 난수(실제 궤적 아님) | 실제 baseline 실행 로그 12,016 스텝 풀에서 시드 고정 샘플 |

**결론(확인됨)**: `legacy_2025/backup/compare_mpc_student.py`는 MPC를 흉내만 낸 placeholder이고 입력 차원도
현재 모델과 안 맞아, **논문 Table 8/16을 만든 실제 스크립트가 아닌 것**으로 판단됩니다
(참고용 옛 스크립트일 뿐).

### §6-5. 논문 "5.30배"가 런타임 차이로 설명되는가

논문 수치(THESIS_PAGES.md): Table 8 Teacher(3,000회) 평균 **1.091ms**, Table 16
Student(6,000회) 평균 0.206ms, **"5.30배"**(=1.091/0.206=5.296).

이번 측정에서 **옛 MPC(매 호출 재구성) 평균 1.0694ms, 중앙값 1.0435ms**로, 논문 Table 8의
1.091ms와 **거의 일치**(오차 약 2%, 다른 세대 CPU에서 나온 값임을 감안하면 매우 근접) —
**논문의 "Teacher" 시간은 baseline의 증분형 MPC(0.14ms)가 아니라 옛 코드의 "매 호출마다
행렬 재구성" 방식(1.07ms)으로 측정된 것으로 강하게 추정됩니다**(확인된 코드 차이:
`legacy_2025/final_hierarchical_backup_thesis_1204.py:948~951`은 매 `solve()`마다
`osqp.OSQP().setup()`을 새로 호출, `thesis_v2/baseline/mpc.py`는 최초 1회만 `setup()`하고
이후 `update()`만 호출).

**"옛 MPC(1.0435ms) / PyTorch 추론만(0.1945ms) = 5.365배"** — 논문의 5.30배와 **1.2%
이내로 거의 정확히 일치**합니다. 같은 비율을 "정규화 포함" 기준으로 보면 4.72배, ONNX
기준으로 보면 22.3배(ONNX는 논문 수치를 오히려 크게 초과)로, **PyTorch(추론만) 기준일
때만** 논문 수치와 이렇게 가깝게 맞아떨어집니다.

**결론: 부분적으로 "설명됨"(정황 증거, 원본 측정 스크립트를 확보하지 못해 완전히
확정하지는 못함)** — 논문의 "Teacher 1.091ms / Student 0.206ms = 5.30배"는, (1) Teacher
쪽은 옛 코드의 비효율적인(매 호출 행렬 재구성) MPC 구현 시간이고, (2) Student 쪽은 ONNX가
아니라 **PyTorch eager, 정규화 전처리 제외("추론만")** 시간일 가능성이 높습니다 — 이
조합만 이번 하드웨어에서 논문 비율을 거의 그대로 재현했습니다(baseline MPC 기준이나 ONNX
기준으로는 재현되지 않음). 다만 원본 논문 측정 스크립트를 이번 조사에서 찾지 못해
("legacy_2025/backup/compare_mpc_student.py"는 아님, §6-4) **"확정"이 아니라 "강한 정황 증거"**로 보고합니다.

---

## §7. MAE 측정 조건 보완 (SSAFY PC 마지막 실행)

§4의 MAE는 baseline이 생성한 궤적(ey_line fallback 74.8%)을 입력으로 삼아 **Student
학습 분포와 얼마나 가까운지 알 수 없다**는 한계가 있었습니다. 이번에는
`legacy_2025/results/teacher/metrics.npz`(옛 코드 TEACHER 모드 실제 실행, 100 에피소드, 18,989
스텝)와 `legacy_2025/results/student/metrics.npz`(옛 코드 STUDENT/hierarchical 모드 실제 실행, 100
에피소드, 18,950 스텝)를 사용했습니다 — 둘 다 `self.metrics` 딕셔너리(y,psi,delta,v,
state,front_gap,episode)를 그대로 저장한 실제 실행 원자료로, `v=0.5` 고정(teacher) 등
`legacy_2025/dataset/`, root `shard_00000.npz`(TEACHER 모드 데이터)와 특징이 일치해 **학습 데이터와
같은 계열의 실제 실행**으로 판단됩니다(추정 — 정확히 같은 파일인지는 확인 못함).

**한계(확인됨, 완전히 동일한 입력 재현 아님)**: `self.metrics`에는 `ey_line`,
`left_clear`가 저장되어 있지 않습니다(`legacy_2025/final_hierarchical_backup_thesis_1204.py:1687`
딕셔너리 정의 확인). 그래서:
- `ey` = `y - target_line_y(state)`로 근사(§4-1과 같은 fallback 공식, 코드 근거 있음)
- `left_clear` = `True`로 고정 근사(근거: `normalization_stats.json`의 `X_mean[3]≈0.996`,
  root `shard_00000.npz`도 거의 항상 `True` — 이 파이프라인 자체가 `left_clear=False`를
  거의 만들지 않음)

이 두 근사 때문에 아래 수치도 "논문 Table 15와 완전히 동일한 조건"은 아닙니다 — 다만
§4(baseline 궤적)보다는 실제 학습 분포에 훨씬 가깝습니다(OOD 비율로 확인, 아래 표).

### 입력 집합별 MAE 비교표

| 입력 집합 | n | MAE(도) | OOD 비율(|z|>3) | 비교 대상 | Table 15와 비교 가능성 |
|---|---|---|---|---|---|
| §4: baseline 궤적(ey fallback 74.8%) | 12,016 | 21.95(vs 옛 MPC) / 9.70(vs baseline MPC) | 1.61% | 재구성한 옛 MPC/baseline MPC | 낮음(입력 분포가 baseline 고유 시나리오) |
| §7: `legacy_2025/results/teacher`(실제 옛 TEACHER 실행) | 18,989 | **10.43** | **0.00%** | **실제 기록된 옛 MPC delta** | **가장 근접**(ey/left_clear 근사 한계는 있음) |
| §7: `legacy_2025/results/student`(실제 옛 STUDENT 실행, 자기 일관성 점검) | 18,950 | 8.89(전체, RETURN_TO_L2 포함 시 왜곡됨 — 아래 참고) | 1.14% | Student 자신이 실제로 낸 delta | 참고용(비교 목적 아님, 파이프라인 검증용) |

### `legacy_2025/results/teacher` 상태별 MAE (n=18,989, 학습 분포에 가장 가까운 값)

| 상태 | n | MAE(도) | OOD 비율 |
|---|---|---|---|
| KEEP_L2 | 10,515 | 5.68 | 0% |
| EVADE_L | 400 | 23.79 | 0% |
| KEEP_L1 | 1,256 | 8.81 | 0% |
| RETURN_TO_L2 | 6,818 | 17.29 | 0% |

OOD 비율이 4개 상태 전부 **0%** — §4(baseline 궤적, KEEP_L2에서 19.2% OOD)와 달리 이
입력은 학습 분포 **안**에 있습니다. 그런데도 EVADE_L(23.79°)·RETURN_TO_L2(17.29°) MAE는
여전히 크므로, **§4-1의 "옛 MPC 버그"만으로는 설명되지 않는 Student 자체의 예측 오차가
이 두 상태에 실재**합니다(이 값은 실제 기록된 옛 MPC delta와 비교한 것이라 제가 재구성한
`old_mpc_wrapper`의 버그 영향을 받지 않습니다).

### `legacy_2025/results/student` 자기 일관성 점검 — 중요 발견: RETURN_TO_L2는 무효

**확인됨(코드 근거)**: `legacy_2025/final_hierarchical_backup_thesis_1204.py:1974~1988`의 주석
"HYBRID STRATEGY: Always use Teacher MPC for RETURN_TO_L2" — **STUDENT/hierarchical
모드에서도 RETURN_TO_L2는 항상 옛 Teacher MPC를 쓰고 Student를 쓰지 않습니다.** 따라서
`legacy_2025/results/student/metrics.npz`의 RETURN_TO_L2 구간에 기록된 `delta`는 애초에 Student의
출력이 아니라 MPC의 출력이라, "Student 자기 일관성"으로 비교하면 안 됩니다(MAE
21.52°로 크게 나온 것은 이 때문 — 버그가 아니라 애초에 비교 대상이 잘못됨).
RETURN_TO_L2를 제외한 나머지 상태에서 자기 일관성(같은 가중치의 모델이 근사된 입력으로
얼마나 자신을 재현하는지)은 다음과 같습니다.

| 상태 | n | MAE(도) | OOD 비율 |
|---|---|---|---|
| KEEP_L2 | 10,510 | 1.97 | 0% |
| EVADE_L | 400 | 1.72 | 54%(!) |
| KEEP_L1 | 1,260 | 0.91 | 0% |
| ~~RETURN_TO_L2~~ | ~~6,780~~ | ~~21.52~~ | ~~0%~~ | **무효(위 근거로 제외)** |

KEEP_L2/KEEP_L1/EVADE_L의 낮은 자기 일관성 MAE(0.9~2.0°)는 `ey`/`left_clear` 근사가
이 상태들에서는 큰 오차를 만들지 않는다는 뜻입니다. 다만 EVADE_L은 OOD 비율이
**54%**로 매우 높습니다 — Student 자신이 실제로 몰았던 회피 구간의 절반 이상이 학습 시
관측 범위(z-score 기준) 밖이라는 뜻으로, 자기 일관성 MAE가 낮게 나온 것과 별개로
주의가 필요한 신호입니다(범위 밖 추정 — 이번 조사에서 추가로 규명하지 않음).

**어느 값이 논문 Table 15(MAE 1.20°)와 비교 가능한가**: `legacy_2025/results/teacher` 기반 값
(**10.43°**, 상태별 표 위)이 가장 근접한 대체 측정입니다 — 그래도 ey/left_clear를
근사했다는 한계 때문에 "다른 데이터셋 대체 측정"이며 논문 수치와 나란히 놓고 비교하지
않습니다(MEASURE_PLAN.md 원칙 그대로 유지).

---

## §8. 종합 판정 (MEASURE_PLAN.md 기준 그대로)

| 항목 | 판정 기준 | 결과 | 판정 |
|---|---|---|---|
| 조향 오차 측정 유효성 | 입력 정의가 REQ-STU-02와 일치할 때만 유효 | 일치 확인(§1) | **유효** |
| 추론시간 vs MPC(PyTorch) | 참고용 배수, 절대 임계치 없음 | MPC가 1.47~1.66배 더 빠름(§3, §6) | **정보** |
| 추론시간 vs MPC(ONNX) | 참고용 배수, 절대 임계치 없음 | **ONNX가 MPC보다 2.99배 더 빠름**(§6-3) | **정보**(런타임을 바꾸면 결론이 뒤집힘) |
| 조향 오차(MAE, baseline 궤적) | 임계치 없음, 참고 수치 | 1순위 21.95°(옛 MPC 버그로 과대), 2순위 9.70° | **정보** |
| 조향 오차(MAE, 학습 분포에 가까운 입력) | 임계치 없음, 참고 수치 | `legacy_2025/results/teacher` 기준 **10.43°**(OOD 0%) | **정보**(Table 15와 가장 근접하지만 근사 한계 있음) |
| 논문 "5.30배" 재현성 | — | 옛 MPC(재구성형)/PyTorch(추론만) 비율이 5.365배로 거의 일치 | **부분 설명됨**(정황 증거, §6-5) |

**핵심 결론**: (1) baseline MPC 기준으로는 이 환경에서 Student(PyTorch)가 더 느리지만,
**런타임을 ONNX로 바꾸면 baseline MPC보다 3배 빠릅니다** — "계산시간 이점이 없다"는
이전 세션 결론은 **런타임에 의존적**이라는 것으로 정정합니다. (2) 조향 오차는 입력을
학습 분포에 가깝게 바꾸자(§7) 이전 21.95°에서 10.43°로 줄었지만, 여전히 논문의 1.20°와는
거리가 있고 OOD 비율은 0%였으므로 **분포 밖 입력 때문이 아니라 Student 자체의 예측
정밀도 한계**로 보입니다(EVADE_L·RETURN_TO_L2에서 특히). (3) 논문의 "5.30배"는 baseline
MPC나 ONNX가 아니라 **"옛 코드의 비효율적 MPC" vs "PyTorch 추론만"** 조합일 가능성이
높습니다(§6-5). baseline·논문 결과는 수정하지 않고 위 내용을 그대로 보고합니다.
