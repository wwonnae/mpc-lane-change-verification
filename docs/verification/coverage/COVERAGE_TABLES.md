<!-- 자동 생성: make_coverage_tables.py, coverage 7.10.7, branch=True, 측정 시각 2026-10-13T09:05:56.607800 -->

## 패키지 × 분류 요약

| 패키지 | 분류 | 모듈 수 | 구문 (커버/전체) | 구문 % | 분기 (커버/전체) | 분기 % |
|---|---|---:|---:|---:|---:|---:|
| anomaly | 라이브러리 | 10 | 769/851 | 90.4% | 163/196 | 83.2% |
| anomaly | 실행 스크립트 | 11 | 859/1631 | 52.7% | 224/424 | 52.8% |
| baseline | 라이브러리 | 15 | 875/937 | 93.4% | 191/222 | 86.0% |
| baseline | 실행 스크립트 | 1 | 43/48 | 89.6% | 5/10 | 50.0% |
| improved | 라이브러리 | 8 | 720/793 | 90.8% | 162/204 | 79.4% |
| improved | 실행 스크립트 | 10 | 141/1461 | 9.7% | 33/328 | 10.1% |
| **라이브러리 합계** | | 33 | 2364/2581 | 91.6% | 516/622 | 83.0% |
| **실행 스크립트 합계** | | 22 | 1043/3140 | 33.2% | 262/762 | 34.4% |
| **전체** | | 55 | 3407/5721 | 59.6% | 778/1384 | 56.2% |

## 모듈별

| 모듈 | 분류 | 구문 (커버/전체) | 구문 % | 분기 (커버/전체) | 분기 % | 미커버 분기 수 |
|---|---|---:|---:|---:|---:|---:|
| `thesis_v2/anomaly/ae_model.py` | 라이브러리 | 24/63 | 38.1% | 0/10 | 0.0% | 10 |
| `thesis_v2/anomaly/common.py` | 라이브러리 | 51/75 | 68.0% | 7/12 | 58.3% | 5 |
| `thesis_v2/anomaly/config.py` | 라이브러리 | 32/32 | 100.0% | 4/4 | 100.0% | 0 |
| `thesis_v2/anomaly/detector_a.py` | 라이브러리 | 141/142 | 99.3% | 47/48 | 97.9% | 1 |
| `thesis_v2/anomaly/detector_b.py` | 라이브러리 | 63/64 | 98.4% | 6/8 | 75.0% | 2 |
| `thesis_v2/anomaly/faults.py` | 라이브러리 | 127/131 | 96.9% | 48/52 | 92.3% | 4 |
| `thesis_v2/anomaly/features_b.py` | 라이브러리 | 69/70 | 98.6% | 5/6 | 83.3% | 1 |
| `thesis_v2/anomaly/hybrid.py` | 라이브러리 | 78/78 | 100.0% | 5/6 | 83.3% | 1 |
| `thesis_v2/anomaly/runner.py` | 라이브러리 | 163/175 | 93.1% | 39/48 | 81.2% | 9 |
| `thesis_v2/anomaly/scenarios.py` | 라이브러리 | 21/21 | 100.0% | 2/2 | 100.0% | 0 |
| `thesis_v2/anomaly/benchmark_detector_timing.py` | 스크립트 | 133/207 | 64.3% | 27/50 | 54.0% | 23 |
| `thesis_v2/anomaly/calibrate_a.py` | 스크립트 | 0/64 | 0.0% | 0/10 | 0.0% | 10 |
| `thesis_v2/anomaly/calibrate_b.py` | 스크립트 | 0/68 | 0.0% | 0/12 | 0.0% | 12 |
| `thesis_v2/anomaly/calibrate_hybrid.py` | 스크립트 | 0/61 | 0.0% | 0/6 | 0.0% | 6 |
| `thesis_v2/anomaly/closed_loop.py` | 스크립트 | 375/441 | 85.0% | 108/144 | 75.0% | 36 |
| `thesis_v2/anomaly/dev_detect.py` | 스크립트 | 25/128 | 19.5% | 1/32 | 3.1% | 31 |
| `thesis_v2/anomaly/dev_detect_a.py` | 스크립트 | 0/6 | 0.0% | 0/4 | 0.0% | 4 |
| `thesis_v2/anomaly/eval_offline.py` | 스크립트 | 326/440 | 74.1% | 88/144 | 61.1% | 56 |
| `thesis_v2/anomaly/run_fault_dev.py` | 스크립트 | 0/63 | 0.0% | 0/6 | 0.0% | 6 |
| `thesis_v2/anomaly/train_b.py` | 스크립트 | 0/85 | 0.0% | 0/8 | 0.0% | 8 |
| `thesis_v2/anomaly/train_hybrid.py` | 스크립트 | 0/68 | 0.0% | 0/8 | 0.0% | 8 |
| `thesis_v2/baseline/collision.py` | 라이브러리 | 34/35 | 97.1% | 11/12 | 91.7% | 1 |
| `thesis_v2/baseline/config.py` | 라이브러리 | 58/58 | 100.0% | 0/0 | — | 0 |
| `thesis_v2/baseline/envinfo.py` | 라이브러리 | 52/67 | 77.6% | 4/10 | 40.0% | 6 |
| `thesis_v2/baseline/fsm.py` | 라이브러리 | 47/47 | 100.0% | 22/22 | 100.0% | 0 |
| `thesis_v2/baseline/lateral.py` | 라이브러리 | 22/22 | 100.0% | 4/4 | 100.0% | 0 |
| `thesis_v2/baseline/logger.py` | 라이브러리 | 35/36 | 97.2% | 11/12 | 91.7% | 1 |
| `thesis_v2/baseline/longitudinal.py` | 라이브러리 | 6/6 | 100.0% | 2/2 | 100.0% | 0 |
| `thesis_v2/baseline/metrics.py` | 라이브러리 | 26/26 | 100.0% | 6/6 | 100.0% | 0 |
| `thesis_v2/baseline/mpc.py` | 라이브러리 | 170/170 | 100.0% | 36/36 | 100.0% | 0 |
| `thesis_v2/baseline/postprocess.py` | 라이브러리 | 17/17 | 100.0% | 0/0 | — | 0 |
| `thesis_v2/baseline/runner.py` | 라이브러리 | 148/169 | 87.6% | 36/52 | 69.2% | 16 |
| `thesis_v2/baseline/sensors.py` | 라이브러리 | 77/77 | 100.0% | 20/22 | 90.9% | 2 |
| `thesis_v2/baseline/summary.py` | 라이브러리 | 116/120 | 96.7% | 37/40 | 92.5% | 3 |
| `thesis_v2/baseline/vehicle.py` | 라이브러리 | 21/21 | 100.0% | 0/0 | — | 0 |
| `thesis_v2/baseline/world.py` | 라이브러리 | 46/66 | 69.7% | 2/4 | 50.0% | 2 |
| `thesis_v2/baseline/run.py` | 스크립트 | 43/48 | 89.6% | 5/10 | 50.0% | 5 |
| `thesis_v2/improved/config.py` | 라이브러리 | 13/13 | 100.0% | 0/0 | — | 0 |
| `thesis_v2/improved/lateral.py` | 라이브러리 | 23/23 | 100.0% | 4/4 | 100.0% | 0 |
| `thesis_v2/improved/mpc.py` | 라이브러리 | 329/329 | 100.0% | 78/80 | 97.5% | 2 |
| `thesis_v2/improved/runner.py` | 라이브러리 | 201/249 | 80.7% | 54/90 | 60.0% | 36 |
| `thesis_v2/improved/sensors.py` | 라이브러리 | 28/28 | 100.0% | 7/8 | 87.5% | 1 |
| `thesis_v2/improved/run_dev_ablation.py` | 스크립트 | 0/136 | 0.0% | 0/32 | 0.0% | 32 |
| `thesis_v2/improved/run_dev_i5_ablation.py` | 스크립트 | 0/140 | 0.0% | 0/34 | 0.0% | 34 |
| `thesis_v2/improved/run_eval.py` | 스크립트 | 0/170 | 0.0% | 0/34 | 0.0% | 34 |
| `thesis_v2/improved/run_eval_v2.py` | 스크립트 | 0/249 | 0.0% | 0/54 | 0.0% | 54 |
| `thesis_v2/improved/student_i4/config.py` | 라이브러리 | 42/42 | 100.0% | 2/2 | 100.0% | 0 |
| `thesis_v2/improved/student_i4/features.py` | 라이브러리 | 53/56 | 94.6% | 15/18 | 83.3% | 3 |
| `thesis_v2/improved/student_i4/model.py` | 라이브러리 | 31/53 | 58.5% | 2/2 | 100.0% | 0 |
| `thesis_v2/improved/student_i4/benchmark_timing.py` | 스크립트 | 0/152 | 0.0% | 0/30 | 0.0% | 30 |
| `thesis_v2/improved/student_i4/closed_loop.py` | 스크립트 | 104/184 | 56.5% | 30/64 | 46.9% | 34 |
| `thesis_v2/improved/student_i4/dataset_gen.py` | 스크립트 | 37/130 | 28.5% | 3/34 | 8.8% | 31 |
| `thesis_v2/improved/student_i4/dev_compare.py` | 스크립트 | 0/139 | 0.0% | 0/24 | 0.0% | 24 |
| `thesis_v2/improved/student_i4/evaluate_mae.py` | 스크립트 | 0/70 | 0.0% | 0/10 | 0.0% | 10 |
| `thesis_v2/improved/student_i4/train.py` | 스크립트 | 0/91 | 0.0% | 0/12 | 0.0% | 12 |

## 미커버 분기 목록 — 라이브러리 모듈

`행A→행B`: 행A의 판단에서 행B로 가는 경로가 테스트 중 한 번도 실행되지 않음(`exit` = 함수 종료).

- `thesis_v2/anomaly/ae_model.py` (10): 51→52, 51→54, 65→66, 65→85, 69→70, 69→76, 78→79, 78→81, 83→65, 83→84
- `thesis_v2/anomaly/common.py` (5): 81→82, 81→86, 89→90, 89→91, 98→99
- `thesis_v2/anomaly/detector_a.py` (1): 157→158
- `thesis_v2/anomaly/detector_b.py` (2): 27→28, 73→75
- `thesis_v2/anomaly/faults.py` (4): 86→87, 133→135, 148→153, 205→208
- `thesis_v2/anomaly/features_b.py` (1): 55→56
- `thesis_v2/anomaly/hybrid.py` (1): 93→95
- `thesis_v2/anomaly/runner.py` (9): 95→98, 132→279, 185→186, 242→243, 244→245, 247→248, 250→253, 274→275, 279→280
- `thesis_v2/baseline/collision.py` (1): 38→39
- `thesis_v2/baseline/envinfo.py` (6): 31→32, 34→35, 34→36, 59→69, 69→72, 94→95
- `thesis_v2/baseline/logger.py` (1): 28→29
- `thesis_v2/baseline/runner.py` (16): 111→244, 117→124, 140→141, 151→152, 153→154, 166→168, 168→169, 168→170, 174→175, 189→190, 194→195, 213→214, 215→216, 218→221, 239→240, 244→245
- `thesis_v2/baseline/sensors.py` (2): 74→76, 87→79
- `thesis_v2/baseline/summary.py` (3): 193→194, 197→198, 200→201
- `thesis_v2/baseline/world.py` (2): 51→55, 53→51
- `thesis_v2/improved/mpc.py` (2): 379→384, 440→444
- `thesis_v2/improved/runner.py` (36): 88→89, 88→90, 94→exit, 94→95, 148→358, 175→176, 188→189, 190→191, 192→193, 196→197, 198→201, 202→203, 202→208, 209→210, 218→219, 222→229, 224→225, 226→227, 237→239, 239→240, 239→241, 244→245, 257→258, 263→264, 269→270, 279→280, 280→281, 280→283, 283→284, 283→290, 328→329, 330→331, 333→336, 338→339, 353→354, 358→359
- `thesis_v2/improved/sensors.py` (1): 47→41
- `thesis_v2/improved/student_i4/features.py` (3): 103→104, 107→108, 109→110

## 미커버 분기 수 — 실행 스크립트

행 단위 목록은 coverage.json에 있다(약 1.4 MB라 저장소에 넣지 않음 — COVERAGE.md의 재생성 명령으로 다시 만든다).

- `thesis_v2/anomaly/benchmark_detector_timing.py`: 23/50
- `thesis_v2/anomaly/calibrate_a.py`: 10/10
- `thesis_v2/anomaly/calibrate_b.py`: 12/12
- `thesis_v2/anomaly/calibrate_hybrid.py`: 6/6
- `thesis_v2/anomaly/closed_loop.py`: 36/144
- `thesis_v2/anomaly/dev_detect.py`: 31/32
- `thesis_v2/anomaly/dev_detect_a.py`: 4/4
- `thesis_v2/anomaly/eval_offline.py`: 56/144
- `thesis_v2/anomaly/run_fault_dev.py`: 6/6
- `thesis_v2/anomaly/train_b.py`: 8/8
- `thesis_v2/anomaly/train_hybrid.py`: 8/8
- `thesis_v2/baseline/run.py`: 5/10
- `thesis_v2/improved/run_dev_ablation.py`: 32/32
- `thesis_v2/improved/run_dev_i5_ablation.py`: 34/34
- `thesis_v2/improved/run_eval.py`: 34/34
- `thesis_v2/improved/run_eval_v2.py`: 54/54
- `thesis_v2/improved/student_i4/benchmark_timing.py`: 30/30
- `thesis_v2/improved/student_i4/closed_loop.py`: 34/64
- `thesis_v2/improved/student_i4/dataset_gen.py`: 31/34
- `thesis_v2/improved/student_i4/dev_compare.py`: 24/24
- `thesis_v2/improved/student_i4/evaluate_mae.py`: 10/10
- `thesis_v2/improved/student_i4/train.py`: 12/12
