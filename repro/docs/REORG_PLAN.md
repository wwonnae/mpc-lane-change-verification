# 원본 코드 재정리 계획 (5단계에서 실행 완료, 2026-09-25)

> **공개 저장소 안내**: 이 문서는 원본 파일이 저장소 루트와 `code_backup/` 등에 있던 시점의 기록이다. 공개 저장소에서는 제출 당시 원본 파일과 폴더를 모두 `legacy_2025/` 아래로 옮겼으므로, 이 문서의 "루트"와 원본 경로는 `legacy_2025/` 기준으로 읽는다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 재구현 직전의 첫 점검 기록 `verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다.

## 실행 기록 (2026-09-25, 5단계)

- 실행 전 상태 고정: git tag `pre-reorg-2026-09-25`(원격 푸시됨). 되돌리기: `git checkout pre-reorg-2026-09-25 -- .`
- `git mv` 10건(히스토리 보존): §2의 루트 미사용 7개 → `backup/`, `code_backup/analyze_mpc.py` → 루트,
  루트 `final_hierarchical_backup.py`(B) → `final_hierarchical_backup_modified_2026.py`,
  `code_backup/final_hierarchical_backup.py`(A) → 루트 `final_hierarchical_backup_thesis_1204.py`. 파일 내용은 바꾸지 않음.
- 코드 참조 수정: `thesis_v2/tests/compare/old_mpc_wrapper.py`의 `OLD_CODE_PATH` 외 compare/·repro/2c_analysis·docs/revision/scripts의
  경로·주석(§4-2(가)). `repro/stage1_analysis/scratch_dec3_extract/run_simulation_dec3.py`는 같은 폴더의 모듈을 찾는 역사적 추출본으로,
  이동 전에도 그 폴더에 대상 파일이 없어 이동과 무관 — 수정하지 않음.
- 검증: `pytest thesis_v2/tests` 168 passed(이동 전과 같음), `check_golden` PASS, 옛 MPC(OSQPMPC) 48개 고정 입력 출력이
  이동 전과 바이트 단위로 동일(같은 파일 SHA-256), compare/ 스크립트 4개 import 정상.
- 문서: §4-2(나)의 문서에 경로 안내를 추가하고 경로 표기를 새 위치로 갱신(역사적 파일명 표기는 유지).
- **깨진 채로 둔 원본 참조(§4-2(다), 내용 수정 금지)**: 루트 `run_simulation.py`와 `code_backup/run_simulation.py`의
  `from final_hierarchical_backup import *`, `verify/closed_loop/harness_*.py`, `code_backup/verify_fix.py`·`run_experiments.py`·
  `generate_return_data.py`, `backup/`로 옮긴 스크립트들. 원본 파이프라인을 다시 돌리려면 tag `pre-reorg-2026-09-25`를
  체크아웃하거나 임시 사본 이름을 `final_hierarchical_backup.py`로 맞춰야 한다.

아래는 실행 전에 작성한 계획 원문이다(경로는 계획 당시 기준).

사용자 요청: "논문에서 쓰인 코드랑 안 쓰인 코드 구분해서 안 쓰인 건 backup 폴더에 넣고
쓰인 코드랑 데이터들은 `MPC_LINETRACING` 폴더(루트)에 유지".

## 연기 결정 (2026-09-18)

**실제 파일 이동은 5단계(README·포트폴리오 정리)로 연기합니다.**

**이유**:
- 루트 파일을 이동하면 `thesis_v2/tests/compare/old_mpc_wrapper.py`의 하드코딩 경로가
  깨집니다(§4 참고).
- `repro/stage1_analysis/`, `repro/2c_analysis/`의 스크립트들도 루트/`code_backup`
  파일 경로나 그 파일들이 만든 산출물(`repro/2c_analysis/out/` 등)을 전제로 작성돼
  있어, 파일 위치가 바뀌면 재실행 시 경로를 다시 맞춰야 합니다(이번 점검 결과
  `repro/2c_analysis/*.py`는 `code_backup`/`final_hierarchical_backup`을 직접
  참조하지는 않고 `thesis_v2.baseline`만 import하는 것으로 확인됐지만, `repro/
  stage1_analysis/scratch_dec3_extract/run_simulation_dec3.py`는 참조가 있어 확인
  필요 — §5 참고).
- 1단계 문서(`CLASSIFICATION.md`, `STAGE1_FACTS.md`, `THESIS_TIME_CODE.md`,
  `PDF_VS_CODE.md`, `SPEC_VS_OLDCODE.md`, `SETTINGS_DECISION.md` 등)가 전부 "루트
  `final_hierarchical_backup.py`=B(제출 후 수정본), `code_backup/
  final_hierarchical_backup.py`=A(12-04 논문 데이터 생성본)"라는 **위치 기반** 구분을
  근거로 서술돼 있습니다. 파일을 옮기면 이 문서들의 "루트=B/code_backup=A" 서술이
  전부 실제 위치와 어긋나게 됩니다(문서 자체를 전부 고치거나, 최소한 "이 문서는 이동
  이전 시점 기준" 안내를 추가해야 함).

**그때까지 원본 폴더(루트 `.py`, `code_backup/`, `verify/`, `results/`, `models/`,
`docs/졸업논문.pdf`)는 "아카이브(동결)"로 취급합니다.** 읽기·참고·비교(import)는
계속하되, 새로 만드는 파일·수정 작업은 전부 `thesis_v2/`(와 `repro/`)에서만 진행합니다.
이 원칙은 `repro/docs/WORK_RULES.md`의 기존 "원본 수정·삭제·이동 금지"와 동일한 방향이며, 이번 결정은
그 금지를 "5단계까지 한시적으로 유지"로 재확인한 것입니다.

## 0. 규칙 충돌과 이전 세션 결정

`repro/docs/WORK_RULES.md`: "원본(루트 .py, `code_backup/`, `results/`, `models/`, `verify/`,
`docs/졸업논문.pdf`)은 수정·삭제·**이동 금지**." 이 요청은 이 규칙과 정면 충돌합니다.
1단계 산출물(`CLASSIFICATION.md`)도 "원본은 전혀 수정·삭제·이동하지 않았습니다"를 원칙으로
삼았습니다.

**이전 세션 결정(2026-09-18, 1차)**: 실제 파일 이동은 하지 않고 계획 문서만 작성.
**이번 세션 결정(2026-09-18, 2차)**: 파일명 충돌 해결안 확정(§4-1), 실행 시점은
**5단계(README·포트폴리오 정리)**로 명시 연기(맨 위 "연기 결정" 참고).

## 1. 분류 기준 (CLASSIFICATION.md와 동일)

- **사용(유지 대상)**: A(논문 데이터 생성 파이프라인), B(논문 제출 이후 활성 수정본),
  D-채택(논문 그림/표로 실제 쓰인 분석 스크립트)
- **미사용(backup 이동 대상)**: C(사후 물리 검증/디버그), D-미채택(그림/표 후보였으나
  논문에 안 실림), E(그 외 폐기 실험·유틸)

## 2. 루트 `.py` 10개 — 이동 계획

| 파일 | 분류 | 계획 | 근거(`CLASSIFICATION.md`) |
|---|---|---|---|
| `run_simulation.py` | A | **유지** | 논문 데이터 생성 파이프라인 본체 |
| `final_hierarchical_backup.py`(루트, 100,254B) | B | **유지, 5단계에 개명 예정**(§4-1) | 논문 제출 이후에도 계속 수정되는 활성 버전 — `code_backup/`의 동명 A버전과 이름 충돌해 `final_hierarchical_backup_modified_2026.py`로 개명 확정 |
| `analysis.py` | D-채택 | **유지** | 논문 그림1(`trajectory_comparison.png`) 생성 |
| `test_teacher_mpc.py` | C | **backup 이동** | 사후 디버그, 하드코딩 경로가 다른 계정(`C:\Users\user\...`), 논문과 무관한 시나리오 |
| `justify_mpc.py` | D-미채택 | **backup 이동** | 논문 그림1–3 어디에도 없는 서브플롯, 수치 하드코딩 |
| `constraint_analysis.py` | D-미채택 | **backup 이동** | AI 툴 업로드 경로 하드코딩(`/mnt/user-data/uploads`), 논문은 Table12를 텍스트로만 제시 |
| `compare_mpc_student.py` | D-미채택 | **backup 이동** | 논문 그림과 불일치. **이번 세션(2026-09-18) 재확인**: 실제 OSQP를 쓰지 않는 P제어 placeholder(`self.solver=None`), 10차원 입력(현재 9차원 모델과 불일치) — 논문 Table 8/16을 만든 스크립트가 아님(`RESULT_STUDENT.md` §6-4) |
| `sensitivity_analysis.py` | E | **backup 이동** | 논문 본문 언급 없음 |
| `benchmark_control_loop.py` | E | **backup 이동** | 논문 Table8 수치와 무관(하드코딩 확인됨) |
| `recompute_table12_y.py` | E(고아) | **backup 이동** | 존재하지 않는 `runs/metrics.npz` 경로, 실행 불가 |

**요약**: 루트 유지 3개(`run_simulation.py`, `final_hierarchical_backup.py`, `analysis.py`),
새 `backup/`로 이동 7개.

## 3. `code_backup/` → 루트로 꺼낼 파일 (사용됨이 확인된 것)

| 파일 | 분류 | 계획 | 근거 |
|---|---|---|---|
| `analyze_mpc.py` | D-채택 | **루트로 이동** | 서브플롯 제목이 논문 그림2·3과 완전 일치, 루트에 동명 파일 없음(충돌 없음) |
| `final_hierarchical_backup.py`(code_backup, 97,747B, 2025-12-04 04:17) | A | **루트로 이동+개명 확정**(`final_hierarchical_backup_thesis_1204.py`, §4-1), 5단계 실행 | 실제 논문 데이터를 생성한 정확한 스냅샷(FSM 쿨다운 미적용 실측 확인) |
| `run_simulation.py`(code_backup) | A | **이동 불필요** | 루트와 바이트 단위로 동일한 사본 — 루트본이 이미 유지 대상이므로 code_backup 쪽 사본은 "이미 code_backup 안에 있는 중복 백업"으로 그대로 둬도 무방(단, §5의 "code_backup 내부 분류표"에는 사용됨으로 표시) |
| `analysis.py`(code_backup) | D-채택 | **이동 불필요**(위와 동일 사유, 루트와 바이트 동일) |

## 4. 막힌 지점과 결정 사항

### 4-1. 파일명 충돌 — **결정 완료(2026-09-18): 둘 다 개명**

`code_backup/final_hierarchical_backup.py`(A, 논문 데이터를 실제로 만든 12-04 스냅샷,
97,747B)와 루트 `final_hierarchical_backup.py`(B, 논문 제출 이후 수정본, 100,254B,
SAFE_STOP의 EVADE_L 예외·cooldown_ok 3곳 추가)는 이름은 같지만 내용이 다릅니다(diff
확인됨). 둘 다 파일명을 바꿔 "어느 쪽이 원래 이름인가"를 다투지 않기로 확정합니다.

| 현재 위치·이름 | 새 이름(5단계 실행 시) | 새 위치 |
|---|---|---|
| `code_backup/final_hierarchical_backup.py`(A) | `final_hierarchical_backup_thesis_1204.py` | 루트 |
| 루트 `final_hierarchical_backup.py`(B) | `final_hierarchical_backup_modified_2026.py` | 루트(그대로, 이름만 변경) |

### 4-2. 이동·개명 시 함께 고쳐야 할 참조 파일 목록 (5단계 실행 시 점검 순서)

**(가) 코드 — 실제로 경로/import를 고쳐야 함**:
- `thesis_v2/tests/compare/old_mpc_wrapper.py` — `OLD_CODE_PATH = REPO_ROOT / "code_backup" /
  "final_hierarchical_backup.py"`를 `REPO_ROOT / "final_hierarchical_backup_thesis_1204.py"`로
  변경(파일이 루트로 옮겨지고 이름도 바뀌므로 둘 다 반영)
- `thesis_v2/tests/compare/run_m_track.py`, `run_onnx_benchmark.py` — `old_mpc_wrapper`를
  통해서만 간접 참조라 직접 수정은 불필요하지만, 이동 후 `pytest`/재실행으로 반드시
  재검증
- `repro/stage1_analysis/scratch_dec3_extract/run_simulation_dec3.py` — 참조 확인됨(§연기
  결정 참고), 실제 내용(경로 하드코딩인지 단순 텍스트 언급인지) 5단계 실행 시 재확인 필요

**(나) 문서 — "루트=B, code_backup=A" 서술을 갱신하거나 "이동 이전 시점 기준" 안내 추가**:
`repro/docs/CLASSIFICATION.md`, `STAGE1_FACTS.md`, `THESIS_TIME_CODE.md`,
`PDF_VS_CODE.md`, `SPEC_VS_OLDCODE.md`, `SETTINGS_DECISION.md`, `MEASURE_PLAN.md`,
`RESULT_STUDENT.md`, `THESIS_REVISION_LOG.md`, `IMPROVEMENT_BACKLOG.md`(이 파일들은
`repro/`에 있어 repro/docs/WORK_RULES.md 원본 보호 대상이 아니므로 편집 가능 — 단 이동 전에는 손대지
않음, 5단계에서 한 번에 갱신)

**(다) 원본(수정 불가) — 참조가 깨지지만 고칠 수 없음, 확인만**:
`verify/closed_loop/harness_A.py`, `verify/task2_data_provenance.py`,
`code_backup/verify_fix.py`, `code_backup/run_experiments.py`,
`code_backup/benchmark_control_loop.py`, `code_backup/generate_return_data.py`,
루트 `test_teacher_mpc.py`, `benchmark_control_loop.py`(이 스크립트는 루트 개명 대상인
`final_hierarchical_backup.py`를 직접 import해 벤치마크하므로, 5단계 이동 시 어느
파일을 찾는지 재확인 필요 — 단, `benchmark_control_loop.py` 자신도 backup 이동 대상(E)
이고 더 실행할 계획이 없어 우선순위는 낮음) 등 — 전부 repro/docs/WORK_RULES.md 보호 대상(원본)이라
이동 후에도 **내용을 고치지 않습니다**(이미 더 이상 실행되지 않는 역사적 스크립트로
취급 — E/C 분류, §5). 참조가 깨진 채로 두되, 아카이브 성격임을 문서에 명시.

## 5. `code_backup/` 내부 전체 분류 (40개 파일, `CLASSIFICATION.md` 표 기반 재정리)

물리적 이동은 계획하지 않습니다(폴더 자체가 이미 "backup" 성격) — 사용자 요청대로
사용/미사용만 분류합니다.

**사용됨(논문에 채택, 4개)**: `final_hierarchical_backup.py`(A), `analyze_mpc.py`(D-채택),
`run_simulation.py`(A, 루트와 동일 사본), `analysis.py`(D-채택, 루트와 동일 사본) —
§3 표와 일치.

**미사용(36개, E 또는 D-미채택 또는 C에 가까운 E)**:

| 파일 | 분류 |
|---|---|
| `analyze_dataset.py` | D-미채택 |
| `analyze_loop_time.py` | D-미채택 |
| `analyze_training_data.py` | D-미채택 |
| `benchmark_control_loop.py` | E |
| `check_return_data.py` | E |
| `check_times.py` | D-미채택 |
| `collect_evade_dataset.py` | E |
| `compare_mpc_student.py` | D-미채택 |
| `constraint_analysis.py` | D-미채택 |
| `final.py` | E(구버전 제어기) |
| `final_hierarchical.py` | E |
| `final_original.py` | E |
| `generate_return_data.py` | E |
| `generate_synthetic_data.py` | E |
| `justify_mpc.py` | D-미채택 |
| `lane_change_mpc.py` | E |
| `lane_change_mpc_final.py` | E |
| `lane_change_mpc_final_complete.py` | E |
| `lane_change_no_ttc.py` | E |
| `lane_change_optimized_final.py` | E |
| `lane_change_proportional.py` | E |
| `recompute_table12_y.py` | E(고아) |
| `run_experiments.py` | E |
| `run_hierarchical.py` | E |
| `run_student.py` | E |
| `run_teacher.py` | E |
| `sensitivity_analysis.py` | E |
| `simulator.py` | E |
| `simulator_original.py` | E |
| `student_only.py` | E |
| `test_synthetic_pipeline.py` | E |
| `test_with_timing.py` | E |
| `train_policy.py` | E |
| `train_policy_full.py` | E |
| `train_student_v2.py` | E |
| `verify_fix.py` | E(C에 가까움 — B 작업 점검용으로 추정) |

## 6. 데이터/기타 파일 (사용자 요청: "데이터들은 유지")

`results/`, `models/`, `dataset/`(및 `dataset/shard_00000.npz` — 루트 사본과 이름은 같지만
**내용이 다른 별개 파일**, `CLASSIFICATION.md` §(c)-5), `figures/`, `docs/졸업논문.pdf`는
전부 repro/docs/WORK_RULES.md 보호 대상이자 사용자가 "유지"를 요청한 데이터이므로 **이동 계획에서 제외**
(현재 위치 그대로).

## 7. 실행 시 순서 (5단계에서 진행, 지금 실행하지 않음)

1. `git mv`로 이동(히스토리 보존):
   - 새 `backup/` 폴더 생성 후 §2의 7개 파일(`test_teacher_mpc.py`, `justify_mpc.py`,
     `constraint_analysis.py`, `compare_mpc_student.py`, `sensitivity_analysis.py`,
     `benchmark_control_loop.py`, `recompute_table12_y.py`) 이동
   - `code_backup/analyze_mpc.py` → 루트로 이동
   - `code_backup/final_hierarchical_backup.py` → 루트 `final_hierarchical_backup_thesis_1204.py`로
     이동+개명(§4-1)
   - 루트 `final_hierarchical_backup.py` → `final_hierarchical_backup_modified_2026.py`로
     개명(같은 위치, 이름만)
2. §4-2(가)의 코드 참조 수정(`old_mpc_wrapper.py` 등)
3. `python -m pytest thesis_v2/tests -q`로 전체 재검증(118개 통과 확인),
   `python -m thesis_v2.tests.compare.run_m_track` 등 M트랙 스크립트도 재실행해 새 경로로
   문제없이 동작하는지 확인
4. §4-2(나)의 문서들을 새 파일명·위치 기준으로 갱신(또는 "이 문서는 2026-09-18 이동
   이전 시점 기준" 안내를 각 문서 상단에 추가)
5. §4-2(다)의 원본 스크립트들은 내용을 고치지 않고, 참조가 깨진 채로 "아카이브, 더 이상
   실행되지 않음" 상태로 남긴다는 점만 확인
6. `repro/docs/CLASSIFICATION.md`·이 문서에 "실행 완료(날짜)" 갱신
