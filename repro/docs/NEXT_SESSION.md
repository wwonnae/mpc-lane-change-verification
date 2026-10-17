# 다음 세션 작업 목록

> **공개 저장소 안내**: 이 문서는 원본 파일이 저장소 루트와 `code_backup/` 등에 있던 시점의 기록이다. 공개 저장소에서는 제출 당시 원본 파일과 폴더를 모두 `legacy_2025/` 아래로 옮겼으므로, 이 문서의 "루트"와 원본 경로는 `legacy_2025/` 기준으로 읽는다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 재구현 직전의 첫 점검 기록 `verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다.

> **경로 안내(5단계 재정리, 2026-09-25)**: 이 문서는 재정리 이전 경로로 작성되었습니다. 이동·개명: `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본) → 루트 `final_hierarchical_backup_thesis_1204.py`, 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본) → `final_hierarchical_backup_modified_2026.py`, `code_backup/analyze_mpc.py` → 루트, 루트 미사용 7개(test_teacher_mpc.py, justify_mpc.py, constraint_analysis.py, compare_mpc_student.py, sensitivity_analysis.py, benchmark_control_loop.py, recompute_table12_y.py) → `backup/`. 경로 표기는 새 위치로 갱신했고, 남아 있는 `final_hierarchical_backup.py`는 당시 모듈·파일 이름(zip 항목, import 대상 등)을 가리키는 역사적 표기입니다(A/B 구분은 문맥). 파일 내용은 바뀌지 않아 행 번호는 그대로 유효합니다. 계획·기록: `repro/docs/REORG_PLAN.md`.

> **4단계 초안 완료(2026-09-25)** — `docs/revision/재구현검증보고서_2026.md`(장별 원고 `docs/revision/chapters/`, 조립·검사 `docs/revision/scripts/build_report.py --check`). 남은 일: `docs/revision/OPEN_ITEMS.md` 8건 결정 반영 → 5단계(README·원본 코드 재정리).
>
> **3단계 종료(2026-09-25)** — 요약: `STAGE3_SUMMARY.md`. 다음은 **4단계(논문 개정판)**, 이어서 5단계(아래 §5).
>
> 종료 처리된 대기 항목(2026-09-25):
> - ~~계산시간 공식 재측정 미완~~ → **종료**. Student v2 계산시간 측정(S10·S11 각각, `--power-mode-confirmed`,
>   `meets_official_condition=true`)에서 v2 MPC를 같은 조건으로 재측정했고, timing_v3 공식값과 호출 수·반복 분포가 동일하며
>   p99가 paper/S6 1–3% 이내로 일치(`RESULT_I4.md` §9-5). I4 9입력 계산시간(§4)은 참고치로 그대로 둠.
> - ~~Student v2 설계 승인 대기~~ → 승인·실행·eval3 판정 완료(S10 "통과", `RESULT_I4.md` §9).

**순서 갱신(2026-09-22)**: 노트북 `_OFFICIAL` 계산시간 공식 판정을 맨 마지막으로 연기했습니다.
이유: 3단계 개선판까지 나온 뒤 baseline·개선판을 **같은 세션·같은 전원 조건에서 연달아**
측정해야 버전 간 계산시간 비교가 공정하기 때문입니다(`MEASURE_PLAN.md` 공통 원칙
"공식 계산시간 측정 시점[2026-09-22 변경]" 참고). 새 순서: (1) 검증 시나리오 확장
(2) C트랙 전체 비교 (3) 3단계 발전 (4) 노트북 계산시간 일괄 측정·판정 (5) 4·5단계.

SSAFY PC에서의 마지막 실행(2026-09-18, ONNX 재측정 + MAE 조건 보완)을 끝으로, 이 PC에서
할 수 있는 측정은 종료했습니다. 아래는 repro/docs/WORK_RULES.md 작업 단계 기준 남은 일과 각 작업의 첫
명령/할 일입니다. 노트북에서 이어서 진행하십시오.

---

## 1. 검증 시나리오 확장 (S3–S7, `[발전]` 강건성 검증)

**현재 상태**: 설계 문서 `repro/docs/ROBUSTNESS_PLAN.md` 작성 완료(2026-09-22), 채팅으로
요약 보고 후 사용자 승인 대기 중. **코드 수정·실행 전 승인 필요**(baseline 제어 로직은
수정하지 않고, `thesis_v2/baseline/world.py`·`sensors.py`에 옵션만 추가 — S5 제어 지연은
`runner.py`에 옵션 추가가 필요해 위치를 사용자와 재확인해야 함, `ROBUSTNESS_PLAN.md` §4
참고).

**할 일(첫 단계)**: `ROBUSTNESS_PLAN.md`를 다시 읽고 승인/수정 사항 확정 → world.py/
sensors.py(및 필요 시 runner.py)에 옵션 추가 → 기존 두 시나리오(paper, left_obstacle)
golden 테스트가 바이트 단위로 그대로 통과하는지 먼저 확인 → S3(격자, 실행 없이 코드
검증만 소규모로) → 사용자 승인 후 전체 격자/시나리오 실행.

결과는 `thesis_v2/results/<타임스탬프>_<호스트>_baseline_R<번호>/`(R3–R7)에 저장합니다.

---

## 2. C트랙 전체 비교 (기존 OSQPMPC vs baseline MPC, 전체 격자)

**현재 상태**: `DESIGN_BASELINE.md` §6에서 1080개 조합 격자를 설계했으나, 2단계-B에서는
10조합 소규모 확인만 실행했습니다(같은 문서 231행·262행: "전체 1080격자는 별도 승인 후").
전체 격자 실행이 아직 없습니다.

**할 일(첫 단계)**: `DESIGN_BASELINE.md` §6과 `MEASURE_PLAN.md` C트랙 절을 다시 읽고,
1080격자 전체 실행 명령과 예상 시간을 안내 → 사용자 실행 → 결과를 판정 라벨("명세 차이로
설명됨" / "설명 안 됨(버그 후보)")로 분류해 보고.

---

## 3. 3단계: 발전 버전 구현·비교 (`thesis_v2/improved/`)

**현재 상태**: `IMPROVEMENT_BACKLOG.md`에 후보 5개 기록됨(SAFE_STOP 복귀, 좌측 장애물
시나리오, IR 센서 물리 모사, **MPC 장애물 인지**[정정판, 충돌 seed=85 원인], **Student
ONNX Runtime 교체**[신규]).

**할 일(첫 단계)**: `IMPROVEMENT_BACKLOG.md`를 다시 읽고 어느 후보를 구현할지 사용자와
확정 — repro/docs/WORK_RULES.md에 따르면 baseline 결과를 보고 baseline 자체를 고치는 것은 금지이므로,
반드시 `thesis_v2/improved/`에 **새 패키지**로 만들어야 합니다. 후보4(MPC 장애물 인지)가
충돌률 1/100 문제와 직결되어 우선순위가 높아 보이지만, 결정은 사용자 승인 필요.

```bash
mkdir thesis_v2/improved
# thesis_v2/baseline/를 참고해 독립 패키지로 구성 (기존 파일 import 금지 원칙은
# thesis_v2 전체에 적용 — improved/도 baseline/ 외부 코드를 가져다 쓰지 않음.
# baseline/ 자체를 import해서 필요한 부분만 오버라이드하는 것은 repro/docs/WORK_RULES.md에 명시적
# 금지가 없으나, 독립 비교가 목적이므로 시작 전 사용자와 구조를 먼저 정할 것)
```

같은 seed·같은 측정 기준(`MEASURE_PLAN.md`)으로 baseline과 비교해야 합니다(새 기준
만들지 말 것). 검증 시나리오(S3–S7)로 baseline에서 드러난 약점(예: 충돌 seed=85 계열)이
있다면 개선판에서 같은 시나리오로 다시 측정해 비교합니다.

---

## 4. 노트북에서 계산시간 일괄 측정·판정 (구 "1." 항목, 순서 변경 + 조건 갱신)

**현재 상태**: `RESULT_BASELINE.md` §7–§8 — AC 전원은 확인됐지만 "Windows 전원 모드=
최고 성능"은 미확인이라 baseline만의 계산시간이 "보류" 판정으로 남아 있습니다. **이제
이 값을 단독으로 "합격/불합격"으로 승격하지 않고, 3단계 개선판이 완성된 뒤 아래 일괄
측정으로 함께 판정합니다**(`MEASURE_PLAN.md` 공통 원칙 "공식 계산시간 측정 시점[2026-09-22
변경]" 참고).

**일괄 측정 스크립트 계획(계획만, 구현은 3단계 끝나고)**:

- **버전 목록**: `thesis_v2/baseline`, `thesis_v2/improved`의 3단계에서 확정된 후보 각각
  (여러 개면 버전마다 별도 실행 — 후보를 나중에 골라내지 않고 3단계에서 실제로 완성한
  버전 전부를 포함).
- **시나리오**: `paper`, `left_obstacle`(논문 정합 시나리오, 기존 2단계-C와 동일 조건).
  강건성 시나리오(S3–S7, `ROBUSTNESS_PLAN.md`)는 계산시간이 아니라 강건성 지표가 목적이라
  기본적으로 제외하되, 특정 시나리오(예: S5 제어 지연)가 계산시간 자체에 영향을 줄 만하면
  포함 여부를 실행 전에 사용자와 확정.
- **실행 순서**: 매 버전에 대해 동일한 순서로 (1) `env.json` 전원 상태 확인 (2)
  `--power-mode-confirmed` 플래그로 `paper` 100 에피소드 (3) 같은 조건으로
  `left_obstacle` 100 에피소드. 버전 간 실행 순서(예: baseline → improved)는 세션마다
  고정하고, 순서 효과(발열 누적 등)를 배제하려면 가능하면 두 번째 반복은 순서를 뒤집어
  재실행하는 것도 고려 사항으로 기록(실행 여부는 사용자 결정).
- **전원 조건 확인 절차**: 노트북 충전기 연결 → Windows 설정 > 시스템 > 전원 > "전원 모드"가
  "최고 성능"인지 육안 확인 → 모든 버전·시나리오 실행을 **끊지 않고 같은 세션 안에서** 연속
  진행(중간에 절전/재부팅 없이) → 각 실행의 `env.json`에서 `power.meets_official_condition`이
  `true`인지 사후 확인.

실행 명령 예시(3단계 완료 후, 버전별로 동일 패턴 반복):

```bash
.venv/Scripts/python.exe -m thesis_v2.baseline.run --scenario paper --seed-start 0 --n-episodes 100 --power-mode-confirmed --out "thesis_v2/results/$(date +%Y%m%d_%H%M%S)_$(hostname)_baseline_P_OFFICIAL"
.venv/Scripts/python.exe -m thesis_v2.baseline.run --scenario left_obstacle --seed-start 0 --n-episodes 100 --power-mode-confirmed --out "thesis_v2/results/$(date +%Y%m%d_%H%M%S)_$(hostname)_baseline_P_leftobs_OFFICIAL"
# improved/ 버전도 같은 --scenario/--seed-start/--n-episodes/--power-mode-confirmed 규칙으로 동일 세션에서 이어서 실행
```

결과 폴더의 `env.json`·`summary.json`을 근거로 `RESULT_BASELINE.md`(및 개선판 결과 문서)의
계산시간 "보류" 판정을 "합격/불합격"으로 갱신하십시오.

---

## 5. 4·5단계: 논문 개정판 작성 + README + 원본 코드 재정리 실행

### 5-1. 4단계: 논문 개정판 작성

**현재 상태**: `THESIS_REVISION_LOG.md`에 발견 사항 누적 기록됨(SAFE_STOP 복귀 조건,
front_gap 계산식, 충돌 판정 기준, IR→ey_line 변환식, KEEP_L1/라인미감지 명세 누락,
REQ-MPC-02 옛 코드 비용함수 스케일링 버그 등).

**할 일(첫 단계)**: `THESIS_REVISION_LOG.md` 전체를 읽고 항목별로 "개정판 제안"을
반영할 새 문서 구조를 사용자와 합의. **제출본 PDF(`docs/졸업논문.pdf`)는 절대 수정하지
않고, 새 파일(예: `repro/docs/THESIS_V2.md` 또는 별도 문서)로 작성**(repro/docs/WORK_RULES.md 원칙).
`RESULT_BASELINE.md`·`RESULT_STUDENT.md`의 새로 측정한 수치만 인용하고, 제출본 수치는
"원본 서술"로만 참고 표기.

특히 확인이 필요한 항목(우선순위 높음):
- 논문 Table 8/15/16이 실제로 어떤 Teacher MPC 구현(옛 코드의 매콜재구성 방식, P/q
  스케일링 버그 포함 여부)으로 측정됐는지 — 원본 측정 스크립트를 찾지 못함
  (`RESULT_STUDENT.md` §6-4, §6-5)
- Table 15(MAE 1.20°)의 정확한 산출 방식·데이터셋 확인 필요

### 5-2. 5단계: README + 원본 코드 재정리 실행

**현재 상태**: 미착수. 이 단계에 **원본 코드 재정리 실행**(사용자 요청, 계획서 작성
완료)도 포함됩니다.

**할 일(README)**: 프로젝트 `README.md`를 실제 재구현 결과 기준으로 갱신(현재 `README.md`는
1단계 이전 상태로 추정 — 먼저 `cat README.md`로 현재 내용 확인).




**할 일(원본 코드 재정리 실행)**: `repro/docs/REORG_PLAN.md`를 그대로 실행 —
파일명 충돌 해결안(§4-1, `final_hierarchical_backup.py` 둘 다 개명:
`final_hierarchical_backup_thesis_1204.py`=A/`final_hierarchical_backup_modified_2026.py`=B)과
참조 파일 목록(§4-2)이 이미 확정돼 있으므로, §7 실행 순서대로 진행:
1. `git mv`로 루트 미사용 7개 파일을 새 `backup/`로, `analyze_mpc.py`를
   루트로, `final_hierarchical_backup.py` 두 벌을 각각 개명하며 이동
2. `thesis_v2/tests/compare/old_mpc_wrapper.py`의 `OLD_CODE_PATH` 등 §4-2(가) 코드
   참조 수정
3. `python -m pytest thesis_v2/tests -q`로 재확인, M트랙 스크립트도 재실행
4. §4-2(나)의 `repro/docs/*.md` 문서들을 새 파일명·위치 기준으로 갱신
5. `CLASSIFICATION.md`·`REORG_PLAN.md`에 "실행 완료" 갱신

---

## 참고: 이번 세션(2026-09-22)에서 새로 생긴 산출물

- `repro/docs/ROBUSTNESS_PLAN.md`(S3–S7 강건성 검증 설계, 실행 없음, 승인 대기)
- `repro/docs/MEASURE_PLAN.md`에 "공식 계산시간 측정 시점[2026-09-22 변경]" 추가(baseline·
  개선판을 노트북 1회 세션에서 연속 측정하는 것만 공식으로 인정)
- 본 문서(`NEXT_SESSION.md`) 순서 갱신(계산시간 공식 판정을 3단계 이후로 연기, C트랙
  전체 비교 항목 신설)
- baseline 제어 로직(`thesis_v2/baseline/`)은 이번 세션에서 전혀 수정하지 않았습니다.

## 참고: 2026-09-18(SSAFY PC 마지막 실행)에서 생긴 산출물

- `thesis_v2/tests/compare/{old_mpc_wrapper,student_model,run_m_track,run_onnx_benchmark,run_mae_recorded}.py`
- `thesis_v2/results/20260918_090132_3층PC108_m_track/`,
  `thesis_v2/results/20260918_143759_3층PC108_onnx_benchmark/`(ONNX 모델 파일 포함),
  `thesis_v2/results/mae_recorded_result.json`
- `repro/docs/RESULT_STUDENT.md`(§1–§8, ONNX 재측정·MAE 조건 보완 포함)
- `repro/docs/RESULT_BASELINE.md` §9(교차 환경 재현성, SSAFY PC golden 확인)
- `repro/docs/THESIS_REVISION_LOG.md`, `repro/docs/IMPROVEMENT_BACKLOG.md`에 신규 항목
  추가(REQ-MPC-02 옛 코드 버그, ONNX Runtime 교체 후보)
