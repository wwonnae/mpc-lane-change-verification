# 1단계: 사실 확정 (최종판, 2026-09-17)

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

원본 파일(루트, `legacy_2025/code_backup/`, `legacy_2025/results/`, `legacy_2025/models/` 등)은 전혀 수정·삭제·이동하지 않았습니다.
새로 만든 자료(PDF 페이지 이미지, 분석 스크립트, 이 문서들)는 전부 `repro/` 아래에만 있습니다.
"확인됨"은 이번 세션에서 직접 실행/열람한 결과이고, "추정"은 정황 근거만 있는 것입니다.
근거에는 파일 경로:행번호 또는 PDF 페이지 번호를 붙였습니다.

이 문서는 1단계의 최종 결론만 담습니다. 여러 후보를 좁혀나간 조사 과정은 결론과 뒤섞이지
않도록 맨 아래 "부록: 조사 경위"로 내렸습니다. 상세 표·코드 인용은 다음 문서를 참고하십시오.

## 1단계 산출물 체크리스트

| 산출물 | 경로 | 상태 |
|---|---|---|
| 논문 페이지별 핵심 수치/서술(전 페이지 표 이미지 대조 완료) | `repro/docs/THESIS_PAGES.md` | 완료 |
| 실험 당시 코드 추정 상세 조사(10절) | `repro/docs/THESIS_TIME_CODE.md` | 완료 |
| 코드 재분류(A–E, 그림/표 매핑, 폴더 충돌) | `repro/docs/CLASSIFICATION.md` | 완료 |
| PDF vs 코드 전 항목 대조(22개 항목, FSM 조건 코드 인용 재검증 완료) | `repro/docs/PDF_VS_CODE.md` | 완료 |
| 사실 확정 최종 요약(본 문서) | `repro/docs/STAGE1_FACTS.md` | 완료 |
| 1단계 분석 스크립트·중간 산출물 | `repro/stage1_analysis/` | 완료(이동 완료) |

---

## 핵심 요약 (최종 확정 사실)

1. **논문 데이터 출처 = `legacy_2025/run_simulation.py` + code_backup 12-04 계열 FSM.** `legacy_2025/results/teacher/
   metrics.npz`·`legacy_2025/results/student/metrics.npz`의 저장 스키마가 `legacy_2025/run_simulation.py`의 `np.savez`
   호출과 정확히 일치하고, 컨트롤러는 `.pyc` 바이트코드 대조(코드 객체 61,772바이트 중 1바이트
   차이, `THESIS_TIME_CODE.md` 9-2절)로 code_backup 12-04본(cooldown_ok·EVADE_L 예외 없음)임이
   확인됐습니다. FSM 전이 간격 실측(EVADE_L→KEEP_L1이 100/100 에피소드 전부 정확히 0.2초)도
   같은 결론을 뒷받침합니다. 단, 총 샘플 수(18,989/18,950 vs 논문 19,129)는 근사치일 뿐 정확히
   재현되지는 않습니다 — seed 미고정(`legacy_2025/run_simulation.py`, `final_hierarchical_backup.py` 전체에
   `.seed(` 0건, 확인됨)이 원인으로 설명 가능합니다.
2. **`legacy_2025/results/student/metrics.npz`는 원본이 확인됐고, `legacy_2025/results/teacher/metrics.npz`는
   2026-05-07 재실행분이며 원본은 두 zip 어디에도 없어 복구 불가입니다.**
   `folder_backup.zip` 안의 사본과 SHA-256을 대조한 결과: student·`ep_008` 사본(2025-12-03
   타임스탬프)은 현재 파일과 바이트 단위로 완전히 같습니다. teacher 최상위 `metrics.npz` 사본은
   `folder_backup.zip` 안에서도 **2026-05-07 14:18:50** 타임스탬프로만 존재하고 현재 파일과
   일치합니다 — 즉 이 파일은 처음부터 재실행분이고, Dec-3 당시의 teacher 원본은 어디에도
   남아있지 않습니다(`THESIS_TIME_CODE.md` 8절).
3. **논문 VI장 결과는 물리 폐루프 검증이 아닙니다.** `legacy_2025/run_simulation.py`는 kinematic 모델이
   장애물과의 거리를 실시간으로 계산하는 방식이 아니라, FSM 상태 구간(정상주행→회피트리거→
   KEEP_L1→복귀→정상주행)을 미리 스크립트로 짜 놓고 `front_gap`/`y`/`line_ey`/`v`를 매 스텝
   직접 주입한 뒤, 그 위에서 실제 FSM+MPC 컨트롤러를 돌린 결과입니다(확인됨,
   `legacy_2025/run_simulation.py:19-77` `RandomScenarioGenerator`). 다만 주입된 `line_ey`는 컨트롤러의
   `LineTraceSensor`에 실제로 전달되지 않는 죽은 값이라(`ey_line`이 항상 `None`, 아래 5번 참고)
   위치(y)는 "정상주행/KEEP_L1/RETURN_TO_L2 구간=주입값 그대로" + "EVADE_L 트리거·마지막
   정상주행 구간=진짜 MPC 물리 업데이트"가 섞인 값입니다.
4. **고정 파라미터 12개(N, dt, qy, qψ, rδ, rΔδ, δ범위, 조향속도, G_TRIG, G_SAFE_MIN, COOLDOWN
   상수값, W, L/B)는 코드와 논문이 전부 일치**합니다(`PDF_VS_CODE.md` 1–14행).
5. **FSM 전이 조건은 부분적으로만 일치합니다.** KEEP_L2→EVADE_L, KEEP_L1→RETURN_TO_L2,
   "모든상태→SAFE_STOP"(A만), **EVADE_L→KEEP_L1**은 A가 논문과 일치합니다 — 확인 결과
   `legacy_2025/run_simulation.py`가 주입하는 `line_ey`는 `LineTraceSensor`가 실제로 읽는 값(`sig_ey.v`)에
   전달되지 않는 죽은 대입이라 `ey_line`은 이 파이프라인에서 **항상 `None`**이고, 그 결과
   IR 분기는 절대 실행되지 않으며 논문과 같은 `|y-0.30|<0.08` 분기만 실행됩니다(`PDF_VS_CODE.md`
   EVADE_L→KEEP_L1 행, 코드 3단계 추적 근거 포함). 유일한 예외는 **RETURN_TO_L2→KEEP_L2**로,
   같은 이유(ELSE 분기만 실행)로 코드가 `|y|<0.08`(NEAR_BAND_L1 재사용)을 쓰는데 논문은 `|y|≤0.20
   AND |ψ|≤20°`를 요구합니다 — 임계값도 다르고 헤딩각 조건 자체가 코드 어디에도 없습니다.
6. Table 7·11의 "Teacher" 속도(0.458±0.048)·조향각(-2.73°) 통계는 `legacy_2025/results/teacher/metrics.npz`
   (속도 상수 0.5)보다 `legacy_2025/results/student/metrics.npz`에 훨씬 더 가깝습니다 — **논문 라벨 불일치로
   기록하며, 원인은 판정불가입니다** (아래 "결정 사항" ① 참고).
7. `legacy_2025/analysis.py`/`legacy_2025/backup/justify_mpc.py`의 1.091ms/0.206ms 등 계산시간류 수치는 하드코딩이며, 저장된
   `metrics.npz`로 직접 재계산한 값(teacher 평균 1.883ms, student 평균 0.858ms 등)과 다릅니다
   — 근거 로그 없음, 재현 불가로 확정합니다. **[정정 2026-09-26]** "계산시간류 수치는 하드코딩"은 일부 값에만 맞는다. 저장소 전체 검색 결과(2026-09-26), 제출본 계산시간 수치 가운데 코드에 상수로 있는 것은 7개뿐이다: 표 8 평균·표준편차·최대 1.091 / 0.152 / 5.747 ms와 표 16 평균·표준편차·최대 0.206 / 0.055 / 1.557 ms(`legacy_2025/analysis.py:70-77`, 1.091·0.206은 `legacy_2025/backup/justify_mpc.py:351`에도), 본문 전체 평균 3.23 ms(`legacy_2025/code_backup/run_hierarchical.py:390-391`, MPC 기준 시간 상수로 사용). 나머지(표 8·16의 중앙값·최소·95/99 백분위, 본문 3.71·5.64 ms·11.3%, 표 18 배수)는 상수도 측정 코드도 찾지 못한 "출처 미발견"이다(표 16 최솟값 0.152는 표 8 표준편차 상수와 숫자만 같음).

---

## 결정 사항 (더 이상 확인 요청하지 않음)

① **Table 7·11 라벨 불일치**: 원인 판정불가로 기록합니다. 사실 근거만 남깁니다 — teacher
   npz는 속도가 정확히 0.5로 고정(표준편차 0, 코드상 `v_cmd=v_ref=V_MAX` 규칙 기반 제어이므로
   이 자체는 논문 IV.3 서술과 오히려 일치), student npz는 0.4586±0.0478로 논문 Table 7의
   0.458±0.048과 훨씬 가까움. 논문 그림3(Velocity Comparison, p.19)도 Teacher를 0.50m/s
   스파이크로 그려 이 사실과 정합적입니다. **더 이상 원인을 추정하지 않습니다.**

② **SAFE_STOP 판정 기준**: 최종 확정.

   **PDF p.10 원문(이미지 재확인, 앞뒤 문장 포함)**: "G_TRIG = 1.2m는 회피 기동 시작 거리이다.
   차량이 이 거리 내로 장애물에 접근하면, FSM은 좌측 차선의 상태를 확인하고 회피 기동을
   시작한다. **G_SAFE_MIN = 0.20m는 비상 정지 거리이다. 회피 기동 중 장애물과의 거리가 이 값
   이하로 감소하면, 즉시 SAFE_STOP 상태로 전이하여 차량을 정지한다.**"

   **판단: 비모순.** Table 2("모든 상태 → SAFE_STOP", 예외 없음)와 p.10("회피 기동 중"에도
   SAFE_STOP이 발동한다는 서술)은 서로 배치되지 않습니다. p.10은 "회피 기동 중"이라는 가장
   위험한 상황을 예로 들어 Table 2의 일반 규칙을 구체적으로 보여주는 문장이지, "회피 기동 중"에만
   한정한다거나 다른 상태를 배제한다는 말이 없습니다. 오히려 p.10은 EVADE_L 중에도 SAFE_STOP이
   적용돼야 한다는 것을 Table 2보다 더 명시적으로 확인해줍니다. **따라서 설정값 선택 규칙 2
   (PDF 내부 모순 시 실험 당시 코드 채택)가 아니라 규칙 1(PDF에 명시된 값을 채택)이 적용됩니다.**

   - **EVADE_L 예외 여부**: 규칙 1 적용 → **PDF대로 예외 없음을 채택**(Table 2 + p.10 둘 다
     예외 없음을 지지). 우연히도 실험 당시 코드(A, code_backup 12-04)도 예외가 없어 PDF와
     일치합니다 — 규칙 1과 규칙 2가 같은 결론으로 수렴하는 경우입니다.
   - **쿨다운 적용 여부**: PDF (3)번 서술("상태 전이 쿨다운은... 쿨다운 시간(0.3초) 내에는
     추가 전이가 차단된다")이 명확히 존재하고, Table 2나 p.10 어디와도 모순되지 않습니다
     (Table 2는 트리거 조건만 요약한 표이고, 쿨다운은 그 위에 얹히는 별도 안전장치로 읽는 것이
     자연스럽습니다). **따라서 이것도 규칙 1이 적용되어 PDF대로 쿨다운을 구현하는 쪽을
     채택합니다.** 이 경우는 실험 당시 코드(A)가 쿨다운을 구현하지 않았던 것과 결론이
     갈립니다 — 규칙 1이 "실험 당시 코드"보다 우선하기 때문입니다(규칙 2는 PDF가 없거나
     모순될 때만 적용되는데, 쿨다운 서술은 PDF에 명확히 존재하므로 규칙 2의 적용 조건 자체가
     성립하지 않습니다).

   **결론**: EVADE_L 예외 없음 + 쿨다운 적용, 둘 다 규칙 1(PDF 채택)로 확정. **구현은
   2단계에서 진행**하며 여기서는 결정 사실만 기록합니다.

③ **`folder_backup.zip`(964개 항목) 전수조사**: 하지 않습니다. `metrics.npz`, `legacy_2025/run_simulation.py`,
   `final_hierarchical_backup.py`, 관련 `.pyc`에 대한 표적 조사로 필요한 사실(원본 여부, 코드
   버전)을 확인했고, 이것으로 조사를 종료합니다.

---

## 남은 미결 사항

- `legacy_2025/run_simulation.py`의 초기속도(0.4–0.6) 주입값은 teacher 모드에서 실제로 안 쓰이는 것으로
  확인됐지만(핵심요약 6·`PDF_VS_CODE.md`), student 모드나 다른 경로에서 실제로 쓰이는지는
  이번 세션에서 끝까지 추적하지 않았습니다 — 2단계에서 필요하면 확인합니다.
- Table 12(제약 만족률) 재계산은 판정 기준(경계 완화 여부 등)이 코드에 없어 2단계-A에서
  기준을 정의해야 합니다.

---

## 부록: 조사 경위 (결론 도출 과정, 참고용 — 위 "핵심 요약"이 최종 결론입니다)

논문 Table 6–18 수치의 출처를 찾기 위해 저장소의 후보 스크립트를 하나씩 배제해 나간 과정입니다.
최종 결론(핵심 요약 1번)과 다른 것처럼 보이는 문장이 있다면, 이 부록은 "그 결론에 도달하기까지
배제한 후보들"이고 본문의 핵심 요약이 우선한다는 점에 유의하십시오.

**배제한 후보 1 — `run_experiments.py --random_env`**: `--random_env`는 죽은 플래그이고
`--comm dummy`에서 `front_gap`이 채워지지 않아, `legacy_2025/results/teacher/ep_000~008`(front_gap 전부
NA, state는 KEEP_L2뿐)를 만들었을 뿐 논문 데이터와 무관합니다.

**배제한 후보 2 — `run_teacher.py` + `simulator.py`/`final.py`**: 스스로 "ORIGINAL parameters"
(G_TRIG=1.0 등, 고정 파라미터표와 다름)라고 표시하고 있어 논문 최종판 이전의 실험 스크립트로
추정됩니다.

**배제한 후보 3 — `collect_evade_dataset.py` + `lane_change_mpc_final_complete.py --test`**:
고정 시나리오 6개를 도는 방식이라 논문의 "무작위 시나리오 반복" 서술과 메커니즘이 다릅니다.
출력 파일명도 "10k" 규모라 19,129와 다릅니다.

**최종 채택 — `legacy_2025/run_simulation.py` + `legacy_2025/final_hierarchical_backup_thesis_1204.py`(12-04본, 구 code_backup)**:
저장 스키마 완전 일치, FSM 전이 간격의 쿨다운-부재 패턴, `.pyc` 바이트코드 서명까지 세 갈래
증거가 모두 이 조합을 가리켰습니다. `legacy_2025/results/teacher/`, `legacy_2025/results/student/`에 남아있는 loose
csv·ep_* csv(front_gap 항상 NA)는 이것과는 **별개의, 논문과 무관한 실행**입니다 — 같은 폴더
안에 서로 다른 두 실행이 섞여 있었던 것이 처음의 "모순"처럼 보였던 원인입니다.

`legacy_2025/verify/REPORT.md`(이전 세션 기록)의 "19,129와 일치하는 파일 없음"이라는 문장도 모순이
아닙니다 — 총 샘플 개수가 정확히 일치하지 않는다는 뜻이었지, `metrics.npz`에 상태 다양성이
없었다는 뜻이 아니었습니다. 이전 세션이 계산한 compute_time(1.883ms)도 이번 세션 재계산과
일치했습니다.
