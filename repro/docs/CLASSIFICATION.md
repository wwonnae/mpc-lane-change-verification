# 코드 재분류 (1단계, 프롬프트 3번)

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

원본은 전혀 수정·삭제·이동하지 않았습니다. 전부 읽기만 했습니다.

## 분류 기준 (A~E, 이번 조사로 확정된 사실 반영)

- **A. 논문 데이터 생성 파이프라인 (확인됨)** — `legacy_2025/run_simulation.py` + `legacy_2025/final_hierarchical_backup_thesis_1204.py`(당시 이름 `final_hierarchical_backup.py`)
  code_backup 12-04 계열(97,747B, cooldown_ok/EVADE_L 예외 없음). `THESIS_TIME_CODE.md` 1·7·8절.
- **B. 논문 제출 이후 수정본** — 같은 컨트롤러 파일이지만 12-04 스냅샷 이후 손댄 버전.
- **C. 사후(2026, 논문 이후) 물리 검증/디버그** — `legacy_2025/verify/` 및 이를 위해 만든 루트 스크립트.
- **D. 논문 그림·표 생성 스크립트** — `results/*/metrics.npz`를 읽어 그림/표를 만드는 분석 코드
  (논문에 채택된 것과 안 된 것 모두 포함, 컬럼에 구분 표시).
- **E. 그 외** — 폐기된 실험 분기, 학습 스크립트, 데이터 생성 실험, 벤치마크 유틸 등 A~D에
  안 들어가는 것.

## (a) 전체 .py 분류표

루트와 `legacy_2025/code_backup/`의 내용이 바이트 단위로 같은 파일(줄바꿈만 다름, 이전 조사에서 `diff -q`/
`diff --strip-trailing-cr`로 확인됨)은 한 행에 "루트=code_backup 동일"로 묶었습니다.

| 파일 | 위치 | 분류 | 근거 | 확인/추정 |
|---|---|---|---|---|
| `legacy_2025/run_simulation.py` | 루트=code_backup 동일 | **A** | `np.savez` 스키마가 `results/*/metrics.npz`와 정확히 일치, 소스 바이트 Dec-3 스냅샷과 동일 | 확인됨 |
| `legacy_2025/final_hierarchical_backup_thesis_1204.py`(구 `code_backup/final_hierarchical_backup.py`) | **루트**(97,747B, 2025-12-04 04:17) | **A** | FSM 전이 간격 실측(쿨다운 미적용) + `.pyc` 소스 서명 일치 | 확인됨 |
| `legacy_2025/final_hierarchical_backup_modified_2026.py`(구 루트 `final_hierarchical_backup.py`) | **루트**(100,254B) | **B** | code_backup 12-04본 대비 diff: SAFE_STOP의 EVADE_L 예외, cooldown_ok 3곳 추가 | 확인됨 |
| `legacy_2025/backup/test_teacher_mpc.py` | 루트 전용 | **C** | docstring "Teacher MPC 검증 스크립트", 하드코딩 경로 `C:\Users\user\...`(현재 PC와 다른 계정), obstacle U(1.2,2.0) — 논문 서술과 무관한 별도 시나리오 | 확인됨 |
| `verify_fix.py` | code_backup 전용 | **C**에 가까운 **E** | "final_hierarchical_backup.py가 올바르게 수정됐는지 확인" — B(루트 수정) 작업의 자체 점검 도구로 추정 | 추정 |
| `legacy_2025/backup/recompute_table12_y.py` | `legacy_2025/backup/`(code_backup 사본과 동일) | **E**(고아) | 존재하지 않는 `runs/metrics.npz` 하드코딩 경로, 실행 불가 | 확인됨 |
| `legacy_2025/analysis.py` | 루트=code_backup 동일 | **D (논문 채택)** | `results/{mode}/metrics.npz` 로드(14행) → `trajectory_comparison.png` 저장(238행) = 논문 **그림1** | 확인됨 |
| `legacy_2025/analyze_mpc.py` | code_backup 전용 | **D (논문 채택)** | 서브플롯 제목이 논문 **그림2·그림3**과 완전 일치(9개+4개), `results/*/metrics.npz` 로드 | 확인됨 |
| `legacy_2025/backup/justify_mpc.py` | `legacy_2025/backup/`(code_backup 사본과 동일) | **D (논문 미채택)** | 서브플롯 제목이 논문 그림1~3 어디에도 없음, 1.091/0.206ms 하드코딩(351행) | 확인됨 |
| `legacy_2025/backup/constraint_analysis.py` | `legacy_2025/backup/`(code_backup 사본과 동일) | **D (논문 미채택)** | `/mnt/user-data/uploads` 하드코딩(37행) — RC카 개발 PC와 무관한 AI 툴 업로드 경로 패턴. 논문은 Table 12로 텍스트만 제시, 이 스크립트 그림은 없음 | 확인됨 |
| `analyze_dataset.py` | code_backup 전용 | **D (논문 미채택)** | 서브플롯 제목(TTC Distribution 등)이 논문에 없음 | 확인됨 |
| `legacy_2025/backup/compare_mpc_student.py` | `legacy_2025/backup/`(code_backup 사본과 동일) | **D (논문 미채택)** | Inference Time/Acceleration·Steering Error 서브플롯, 논문 그림1~3과 불일치 | 확인됨 |
| `analyze_training_data.py` | code_backup 전용 | **D (논문 미채택)** | docstring "Analyze RETURN_TO_L2 samples" — 개발 중 디버그용 | 추정 |
| `analyze_loop_time.py` | code_backup 전용 | **D (논문 미채택)** | docstring "Loop time 분석" | 추정 |
| `check_return_data.py` | code_backup 전용 | **E** | "Check RETURN_TO_L2 data quality" — 1회성 점검 스크립트 | 추정 |
| `check_times.py` | code_backup 전용 | **D (논문 미채택)** | `legacy_2025/results/teacher\|student/metrics.npz`의 `compute_time` 상태별 평균 출력 — 3절 재계산과 유사한 목적, 논문 그림/표로 채택 안 됨 | 확인됨 |
| `legacy_2025/backup/sensitivity_analysis.py` | `legacy_2025/backup/`(code_backup 사본과 동일) | **E** | "파라미터 민감도 분석", 별도 `legacy_2025/sensitivity_analysis/exp_01~04` 산출물과 대응, 논문 본문에 언급 없음 | 추정 |
| `legacy_2025/backup/benchmark_control_loop.py` | `legacy_2025/backup/`(code_backup 사본과 동일) | **E** | `final_hierarchical_backup.py`(import 시점의 루트 파일 = B, 현재 이름 `legacy_2025/final_hierarchical_backup_modified_2026.py`) 직접 벤치마크. 논문 Table 8 수치와 무관(하드코딩으로 이미 확인) | 확인됨(하드코딩과 무관함은 확인, 이 스크립트 자체 실행 여부는 미확인) |
| `final.py` | code_backup 전용 | **E**(구버전 제어기) | `run_teacher.py`/`run_student.py`/`run_hierarchical.py`가 import, "ORIGINAL parameters"(G_TRIG=1.0 등)로 논문 최종판과 다름 | 확인됨 |
| `final_original.py` | code_backup 전용 | **E** | 어디서도 import 안 됨(grep 결과 0건) | 확인됨 |
| `final_hierarchical.py` | code_backup 전용 | **E** | 어디서도 import 안 됨 | 확인됨 |
| `lane_change_mpc.py` | code_backup 전용 | **E** | `test_with_timing.py`만 import, 논문 데이터와 무관 | 확인됨 |
| `lane_change_mpc_final.py` | code_backup 전용 | **E** | `generate_synthetic_data.py` docstring이 언급하나 실제 import처는 미확인 | 추정 |
| `lane_change_mpc_final_complete.py` | code_backup 전용 | **E** | `collect_evade_dataset.py`가 서브프로세스로 호출(`--test` 고정 시나리오, 무작위 아님) | 확인됨 |
| `lane_change_no_ttc.py`, `lane_change_optimized_final.py`, `lane_change_proportional.py` | code_backup 전용 | **E** | 어디서도 import/호출되지 않음 | 확인됨 |
| `simulator.py` | code_backup 전용 | **E** | `run_teacher/student/hierarchical.py`가 import, obstacle U(2.5,4.0) — 논문 서술과 다름. `legacy_2025/backup/test_teacher_mpc.py`(C)도 이 파일을 재사용 | 확인됨 |
| `simulator_original.py` | code_backup 전용 | **E** | 어디서도 import 안 됨, obstacle U(1.5,2.5) | 확인됨 |
| `run_teacher.py` | code_backup 전용 | **E** | 자칭 "ORIGINAL parameters", G_TRIG=1.0/G_SAFE_MIN=0.15로 고정 파라미터표와 다름 | 확인됨 |
| `run_student.py`, `run_hierarchical.py` | code_backup 전용 | **E** | `final.py`+`simulator.py` 기반, A 파이프라인과 무관 | 확인됨(import 관계), 실행목적은 추정 |
| `run_experiments.py` | code_backup 전용 | **E** | `--random_env`가 죽은 플래그, `legacy_2025/results/teacher/ep_000~008`(front_gap 항상 NA)를 만든 실행 | 확인됨 |
| `collect_evade_dataset.py` | code_backup 전용 | **E** | `lane_change_mpc_final_complete.py --test` 100회 반복, 고정 시나리오 | 확인됨 |
| `generate_synthetic_data.py` | code_backup 전용 | **E** | docstring: `lane_change_mpc_final.py`에 합성 front_gap 프로파일 주입 | 추정(docstring만 확인) |
| `generate_return_data.py` | code_backup 전용 | **E** | docstring: RETURN_TO_L2 데이터 보강용 | 추정 |
| `test_synthetic_pipeline.py` | code_backup 전용 | **E** | 합성 데이터 파이프라인 통합 테스트 | 추정 |
| `test_with_timing.py` | code_backup 전용 | **E** | `lane_change_mpc.py` import, loop time 측정용 테스트 래퍼 | 확인됨(import), 목적은 추정 |
| `train_policy.py` | code_backup 전용 | **E** | docstring "final.py에 맞춰진 버전" — E(`final.py`) 계열용 학습 스크립트, `legacy_2025/models/policy_best.pth`와의 대응은 미확인 | 추정 |
| `train_policy_full.py` | code_backup 전용 | **E** | "논문용 완전 자동화 학습+평가"라고 자칭하나, 대응 데이터셋(정확한 npz)이 저장소에 없어 실행 여부 미확인 | 추정 |
| `train_student_v2.py` | code_backup 전용 | **E** | "original 60k + RETURN_TO_L2 6k" 결합 데이터셋 사용 — 해당 npz 없음 | 추정 |
| `student_only.py` | code_backup 전용 | **E** | "MPC 제거, 순수 추론 모드" — 배포용 경량화 버전으로 추정, 논문 데이터 생성과 무관 | 추정 |

## (b) 논문 표·그림·수치 → 생성 스크립트 → 출력 파일 매핑 (재현 불가 사유 포함)

| 논문 항목 | 생성 스크립트(확인/추정) | 출력 파일 | 재현 상태 |
|---|---|---|---|
| 그림 1 (Trajectory) | `legacy_2025/analysis.py`(확인) | `legacy_2025/figures/trajectory_comparison.png` | **근사 재현 가능** — `results/*/metrics.npz` 존재, 다만 원본 실행이 아닐 수 있음(teacher는 05-07 재실행분) |
| 그림 2 (MPC 성능 종합) | `legacy_2025/analyze_mpc.py`(확인) | `legacy_2025/figures/mpc_performance_analysis.png` | 근사 재현 가능(위와 동일 사유) |
| 그림 3 (Teacher-Student 비교) | `legacy_2025/analyze_mpc.py`(확인) | `legacy_2025/figures/teacher_student_comparison.png` | 근사 재현 가능 |
| Table 6,7,9,10,11,14 (FSM 상태·오차·속도·샘플분포) | `legacy_2025/run_simulation.py`+A컨트롤러(확인) → 수작업 또는 별도 스크립트로 표 작성(미발견) | `results/*/metrics.npz` | **근사 재현**(3절, 0.3~2%p 오차). 표를 직접 만든 스크립트 자체는 저장소에 없음 — 사람이 npz를 보고 수기로 정리했을 가능성 |
| Table 8, 16, 17, 18 (계산/추론 시간) | `legacy_2025/analysis.py:70-77`, `legacy_2025/backup/justify_mpc.py:351`, `legacy_2025/code_backup/run_hierarchical.py:390` — **일부만 상수**(정정 2026-09-26: 표 8·16 평균·표준편차·최대 6개와 본문 3.23 ms = 7개. 나머지는 출처 미발견) | 없음(코드 상수 또는 출처 미발견) | **재현 불가** — 근거 로그 없음, 재계산 값과 4배 이상 차이 나는 항목도 있음 |
| Table 12 (제약 만족률) | 미발견 | 없음 | **판정불가** — 판정 로직(경계 완화 기준 등)이 코드 어디에도 없어 2단계에서 기준 정의 필요 |
| Table 13 (조향각 변화율) | 추정: `legacy_2025/analyze_mpc.py`류가 `delta` 배열 diff로 계산 가능 | 없음(전용 스크립트 미발견) | 근사 재현 가능(2단계에서 직접 계산 필요) |
| Table 15 (Student 학습 손실 MSE/MAE) | `train_policy*.py`류(추정) | `legacy_2025/models/training_curves.png` 등 | **재현 불가** — 대응 학습 데이터셋 npz가 저장소에 없음 |
| 19,129 샘플 / 191.3 평균 | 미발견(수작업 집계로 추정) | - | **근사 재현**(18,989~18,950 vs 19,129) |

## (c) 폴더 배치와 분류가 충돌하는 사례

1. **`legacy_2025/code_backup/`라는 이름과 달리, 이 폴더 안의 `legacy_2025/analyze_mpc.py`가 논문 그림2·3을 만든 "활성"
   스크립트입니다.** 반면 정작 루트에 있는 `final_hierarchical_backup.py`는 "백업"이라는
   파일명과 반대로 논문 제출 이후에도 계속 수정되는 활성 개발 파일(B)입니다 — **이름과 실제
   역할이 정반대**입니다.
2. **`final_hierarchical_backup.py`라는 파일명 자체가 이미 두 위치(루트/`code_backup`)에서 서로
   다른 내용(A vs B)을 가리켜, 파일명만으로는 어느 버전인지 구분이 안 됩니다.**
3. `simulator.py`(현재 버전, E)와 `simulator_original.py`(더 이른 버전, E)의 이름이 실제 최신/구버전
   관계와 어긋납니다 — "original"이 붙은 쪽이 시간상 더 이르고(2025-12-01 22:19),
   "original"이 안 붙은 `simulator.py`가 더 나중 버전인데, 논문 서술(0.5~2.0m)에는 **둘 다** 안
   맞습니다. `final_original.py`/`final.py`도 같은 패턴(이르든 늦든 어느 쪽도 A가 아님).
4. `legacy_2025/results/teacher/`, `legacy_2025/results/student/` 폴더는 이름상 "실험 결과"로 보이지만, 내부에는 **논문과
   무관한 실행(E, front_gap NA)** 과 **논문에 가까운 실행(A, `metrics.npz`)** 이 같은 폴더에
   섞여 있어 폴더명만으로는 신뢰 가능한 데이터를 구분할 수 없습니다(`THESIS_TIME_CODE.md` 1절).
5. `legacy_2025/dataset/shard_00000.npz`(5,186B)와 루트/`code_backup`의 `shard_00000.npz`(373,826B)는 **같은
   파일명, 다른 내용**입니다 — 폴더 위치가 다르면 이름이 같아도 다른 데이터입니다.
6. `verify_fix.py`는 `legacy_2025/code_backup/`(E 폴더)에 있지만 실제로는 **B(루트 수정)** 작업을 점검하는
   스크립트로 추정되어, 폴더 배치(code_backup=과거 스냅샷)와 목적(현재/미래 수정 점검)이 어긋납니다.
