# 부록. 조건 코드와 재현 방법

모든 표 캡션 끝에는 `[데이터 | 호스트 | 버전 | 커밋]` 조건 태그가 붙는다(기존 보고서 부록 B와 같은 규칙). 데이터 코드는 표 1-1에 있다. 수치는
모두 `docs/revision/ANOMALY_NUMBERS.csv`의 한 행에서 가져왔고, 각 행에 근거 파일과 조건 코드가 있다.

**표 부-1. 호스트 코드.** [데이터: 정의 표 | 호스트: 해당 없음 | 버전: 해당 없음 | 커밋: K6]

| 코드 | 기기 | 비고 |
|---|---|---|
| H1 | 노트북 `DESKTOP-MDCKRJS` | iteration 1·2 학습·임계값·dev, 탐지기 계산 시간 공식 측정(III장 5절). 기존 보고서의 H1과 같은 기기 |
| H3 | 교육장 PC `3층PC108` | iteration 3·하이브리드·동결 전 수정·오프라인 평가·폐루프 dev |
| H4 | 교육장 PC `3층PC109` | 폐루프 dev 전체 재확인·폐루프 평가·IF PC 간 동일성·보충 재현·평가 결과 `--check` 재계산 |

- 소프트웨어(H3·H4): {{a:env_py}}, {{a:env_ml}}. H1은 Python 패치 버전만 다르다.
- 결과 분류·점수는 결정적으로 설계하였다(난수 스트림 고정). 다른 호스트에서 같은 입력의 결과가 같다는 것은 IF 동일성, 폐루프 dev 전체 재계산(H3 → H4),
  오프라인 평가 결과 재계산(H3 → H4, {{a:offchk_same}}개 파일 일치)으로 확인하였다(VI장 5절, "실행 중 같은 PC에서 다른 작업 없음" 조건). 폐루프 평가
  결과는 같은 호스트에서 재계산해 {{a:clchk_same}}개 파일이 일치하였다(H4 → H4). 노트북에서 1회 나온 불일치(VI장 4절)의 원인은 미확정이다.
  탐지기 계산 시간은 H1 공식 조건(AC 전원 + 최고 성능)에서 측정하였다(III장 5절). 노트북 `x86` 기준이며 임베디드 보드는 측정하지 않았다.

**표 부-2. 커밋 코드(`main` 브랜치).** [데이터: 정의 표 | 호스트: 해당 없음 | 버전: 해당 없음 | 커밋: 표 자체]

| 코드 | 커밋 | 내용 |
|---|---|---|
| K1 | `2b49000` | 고장 주입기·원거리 시나리오·v2 동치 runner(golden) |
| K2 | `048b7a5` | 탐지기 A·B1·B2, iteration 1·2 |
| K3 | `0a81b8b` | 탐지기 A iteration 3(ir_miss) |
| K4 | `63e7b6e` | 동결 전 수정(σ 버그, σ 불일치, 하이브리드, 오프라인 평가 스크립트). 태그 `anomaly-eval-freeze` — 오프라인 평가의 코드 기준 |
| K5 | `c29a738` | 폐루프 dev 전체 재확인. 태그 `anomaly-cl-freeze` — 폐루프 평가의 코드 기준(평가 결과 `env.json`의 커밋 `{{a:cl_commit}}`) |
| K6 | 이 보고서 커밋 | 보충 재현(`anomaly_supplement.py`)·수치표·보고서. 제어·탐지 코드는 K5와 같음. `supplement.json`은 커밋 `52eb68b` + 미커밋 보고서 스크립트 상태에서 생성되었다(파일의 git 필드 dirty=true) — 제어·탐지 코드는 그 상태에서도 K5와 같다 |
| K7 | `{{a:tm_commit}}` | 탐지기 계산 시간 측정 스크립트(`benchmark_detector_timing.py`)와 테스트 — 계산 시간 측정의 코드 기준. 제어·탐지 코드는 K5와 같음(`git diff`로 확인) |

## 재현 방법

저장소 루트, `.venv`(`Python 3.9`, `thesis_v2/requirements-py39.txt` + `thesis_v2/anomaly/requirements-anomaly.txt` + torch CPU).

```powershell
.\.venv\Scripts\python -m pytest thesis_v2/tests thesis_v2/anomaly/tests -q          # 테스트
.\.venv\Scripts\python -m thesis_v2.tests.check_golden                               # 제어 동치(golden)
# 결정성 재확인(평가 결과 폴더는 다시 쓰지 않음, 같은 PC에서 다른 작업 없이)
.\.venv\Scripts\python -m thesis_v2.anomaly.eval_offline --check <오프라인 평가 결과 폴더>
.\.venv\Scripts\python -m thesis_v2.anomaly.closed_loop --check <폐루프 결과 폴더>
# 탐지기 계산 시간(H1 노트북, AC 전원 + 최고 성능, 다른 작업 없이, 약 15분)
.\.venv\Scripts\python -m thesis_v2.anomaly.benchmark_detector_timing --power-mode-confirmed --cooldown-before-sec 60
# 보고서
.\.venv\Scripts\python docs\revision\scripts\anomaly_supplement.py                  # 보충 재현(평가 seed 미사용, 약 1분)
.\.venv\Scripts\python docs\revision\scripts\make_anomaly_numbers.py                # ANOMALY_NUMBERS.csv
.\.venv\Scripts\python docs\revision\scripts\build_anomaly_report.py --check        # 조립 + 대조
```

- 평가 결과 폴더: 오프라인 `thesis_v2/results/anomaly/20261002_145638_3층PC108_it3_eval_offline_eval/`, 폐루프
  `thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval/`(실행 로그 `20261012_3층PC109_run_logs/`).
- 평가 실행(`--seeds eval`)은 동결 태그가 HEAD를 가리키고 작업 트리가 깨끗할 때만 허용된다(코드 가드). 평가를 다시 실행하는 것은 사전 선언 위반이다.
  결정성 확인은 `--check`로 한다.
- 설계·사전 선언·전체 기록: `thesis_v2/anomaly/DESIGN.md`(§13 사전 선언, §19 보완, §24 폐루프, §25 보충 확인).
