# I4 — Student(신경망) 재학습 설계 (3단계, [발전])

> **2026-09-25 사용자 결정 반영(개정 1)** — §4의 결정 필요 항목 4개와 추가 지적 1건이
> 확정되어 본문을 고쳤습니다. 요약: (1) 역빈도 가중 삭제 → dev seed 200개 단위 확대로
> 대응(§1-4), (2) MAE는 v2 MPC 주 기준 + baseline v1.1 MPC 참고, 옛 MPC(12-04) 제외
> (§3-1), (3) 폐루프 평가 실행 — 1차 paper eval seed 200~299, 문제없으면 2차 S3 eval
> 격자, 실행은 사용자(§3-2), (4) epoch=50 전부·검증 손실 최저 체크포인트·조기 종료
> 없음(§2-1), (5) split seed 재추첨 규칙 삭제 → 에피소드 단위 계층 분할(§1-5),
> (6) v1 left_obstacle 현상은 "QP 발산"이 아니라 "반복 상한(20,000) 도달, 하드 제약
> 통과, fallback 0건"으로 표기(THESIS_REVISION_LOG), (7) 평가는 δ 중심, v_target
> 오차는 참고 지표(§1-3, §3-1). 이 개정 이후 데이터 생성·학습·MAE·계산시간을 실행하고
> 폐루프 실행 전에 멈춥니다.

> **2026-09-25 폐루프 실행 결과**: 1차(paper)·2차(S3) 모두 사용자 실행 완료, **폐루프 검증 실패**
> (paper 성공 7/충돌 23/타임아웃 70, S3 60/290/550; v2는 전부 성공). 결과·원인 분석·한계는
> `RESULT_I4.md` §5~7. 결과를 보고 모델·데이터·하이퍼파라미터를 바꾸지 않았음.

**전제**: 이 문서는 **설계만** 다룹니다. 코드 작성·데이터 생성·학습 실행은 이 문서
승인 후 별도 단계에서 진행합니다(repro/docs/WORK_RULES.md "코드 주석에 REQ ID와 태그를 남기고,
테스트는 REQ ID별로 만든다"의 사전 설계 단계). `IMPROVEMENT_BACKLOG.md` 후보6(2단계-D
직후 기록)을 계승하되, 교사를 baseline MPC가 아니라 **v2(I5=972, 3단계 최종 채택
조합, `DESIGN_IMPROVED_V2.md` §9)**로 갱신합니다.

**핵심 주장 3([보조]) 범위**: repro/docs/WORK_RULES.md "신경망은 임베디드 적용 여지 확인 수준.
재학습하지 않고 `legacy_2025/models/`를 수정 없이 사용한다"는 **baseline 트랙**(2단계-D M트랙)의
원칙이고, 이 I4는 **3단계 발전판** 항목입니다 — 원본 `legacy_2025/models/policy_best.pth`는
그대로 두고, **별도의 새 Student**를 v2 MPC 데이터로 학습해 "재학습하면 임베디드
적용 여지가 어떻게 바뀌는가"를 추가로 확인합니다.

**기준 문서**: `repro/docs/SPEC.md`(REQ-STU-01~04), `repro/docs/THESIS_PAGES.md`(Table
4=신경망 구조, Table 5=학습 설정: Adam·lr=1e-3·batch=256·epoch=50·85/15 split),
`repro/docs/RESULT_STUDENT.md`(2단계-D M트랙 방법론·측정 결과, 이 설계가 재사용하는
매핑표·벤치마크 방식의 출처), `repro/docs/IMPROVEMENT_BACKLOG.md` 후보6,
`repro/docs/MEASURE_PLAN.md`(2026-09-25 정정: 계산시간 주 지표 p99).

---

## 0. 전체 파일 배치 (제안)

```
thesis_v2/improved/student_i4/        # 학습·평가 코드(신규 패키지, 기존 improved/ control 로직과 분리)
  config.py                           # I4 전용 설정(하이퍼파라미터, 경로) — Table 5 값 명시
  dataset_gen.py                      # v2 MPC로 (feature, label) 생성
  model.py                            # StudentPolicy 정의(REQ-STU-01 그대로, 재구현 아님 — 구조 정의만 새로 작성)
  train.py                            # 학습 루프
  evaluate.py                         # MAE·폐루프·계산시간·변동성 평가
thesis_v2/results/i4_student/<timestamp>_<host>/
  legacy_2025/dataset/                            # 생성된 학습·검증 데이터셋(옛 데이터셋과 분리 보관)
  checkpoints/policy_i4_best.pt       # 새 모델(원본 legacy_2025/models/policy_best.pth와 별도 경로, 수정 없음)
  train_log.json                      # epoch별 train/val loss, lr, 시각
  eval/                               # MAE·폐루프·계산시간·변동성 결과 JSON
```

`legacy_2025/models/`(원본, `policy_best.pth`·`normalization_stats.json` 등)는 **읽기 전용
참고**(정규화 통계의 feature 순서·구조만 REQ-STU-02/04 대조용으로 참고하고, 파일
자체는 절대 열어서 덮어쓰지 않음)로만 쓰고 절대 수정·삭제하지 않습니다.

---

## 1. 데이터 생성

### 1-1. 생성 소스와 범위

| 항목 | 값 | 근거 |
|---|---|---|
| 교사(teacher) | **v2 MPC**(`ImprovedMPC(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True, i2_variant="narrow", enable_i5=True, i5_max_iter=972)`) | 3단계 최종 채택 조합(`DESIGN_IMPROVED_V2.md` §9) |
| 시나리오 1 | paper 시나리오, **dev seed 100~199**(100 episodes) | `run_dev_i5_ablation.py`의 `DEV_PAPER_SEEDS`와 동일 축(3단계 dev 원칙 재사용) |
| 시나리오 2 | S3 dev 격자(`front_gap0` 0.525~1.975/0.05 × `y0` -0.145~0.145/0.01, 30×30=900 cell) | `run_dev_i5_ablation.py`의 `DEV_S3_FRONT_GAPS/Y0S`와 동일(반 칸 오프셋, eval 격자·기존 eval과 안 겹침) |
| eval seed(0~99, 200~299) | **사용 안 함** | 학습 데이터에 eval 데이터를 섞으면 §3 MAE 평가가 "본 적 있는 분포"가 돼 평가가 무의미해짐 — dev/eval 분리 원칙(repro/docs/WORK_RULES.md 3단계 발전 원칙) 그대로 적용 |

**표본 규모 추정**(실행 전 계산, `RESULT_STUDENT.md` §1 M트랙 표본 밀도 기준
스텝당 MPC 호출 비율로 추정 — 실제 값은 생성 후 §1-4에서 실측치로 교체):
paper 100 episode ≈ 15,000~20,000 스텝(§8-5 공식 측정의 paper n_mpc_calls≈11,510/100ep
참고) + S3 900 episode(격자, 각 episode 최대 `MAX_STEPS+OBSERVE_STEPS`=220 스텝이나
실패/조기종료 episode는 더 짧음) ≈ 수만~10만 스텝 규모. MPC가 실제로 호출되는
스텝만 표본으로 쓰므로(라인 추종 모드 제외, `RESULT_STUDENT.md` §2와 동일 원칙)
최종 표본 수는 이보다 작습니다. **논문 원 데이터셋(추정 19,129개, 재현 불가로 이미
기록됨) 대비 같은 자릿수 이상**이 될 것으로 예상하며, 실측치는 생성 직후 이 절에
채워 넣습니다(결과를 보고 범위를 사후에 넓히지 않음 — 위 표가 최종 범위).

### 1-2. 입력 9차원 (REQ-STU-02 그대로, [정합])

`v, ey_line, front_gap, left_clear, state_one_hot(KEEP_L2, EVADE_L, KEEP_L1,
RETURN_TO_L2, SAFE_STOP)`. 매핑은 `RESULT_STUDENT.md` §2 매핑표를 그대로 재사용합니다
(`ey_line` NaN인 라인 미검출 스텝은 `y - target_line_y(state)`로 대체 — 이미
2단계-D에서 코드 근거로 확인된 규칙, 새로 정하는 게 아님). **차이점**: 2단계-D는
baseline 로그(`steps.npz`)에서 매핑했지만, I4는 v2(`thesis_v2/improved/`) 로그에서
매핑합니다 — `improved/runner.py`의 `logger.rows`에 이미 `y, psi, v, front_gap,
left_clear, ir_pattern, ey_line, state`가 있어 baseline과 동일한 필드로 매핑
가능(추가 로깅 불필요, 제어 로직 미수정).

### 1-3. 출력 (REQ-STU-03, Table 4 구조 유지, [정합])

라벨은 **v2 MPC의 `delta_deg`(후처리 전 raw 출력, `MPCResult.delta_deg`)**와
**v_target**입니다. `v_target`은 REQ-STU-03이 "v_target(m/s)"로 정의하지만 repro/docs/WORK_RULES.md
핵심 주장 2("MPC는 속도를 결정하지 않는다")에 따라 MPC 자체는 속도를 내지 않으므로,
이 라벨은 **종방향 규칙 기반 제어기의 출력**(`longitudinal.compute_v_cmd(state)`,
REQ-SPD-01/02)을 그대로 씁니다 — 논문 구조(Table 4, 출력 2차원 [δ, v_target])와
학습 대상(Student가 "제어기 전체(횡+종방향)"를 모방)을 그대로 유지하되, 각 라벨의
**출처**(δ=v2 MPC, v_target=규칙기반)는 명시적으로 분리해 기록합니다(라벨 조립
시점에 두 값을 하나의 시점(같은 스텝)에서 페어링).

**(개정 1) v_target은 참고 지표**: v_target은 상태만으로 결정되는 값입니다
(`compute_v_cmd`: SAFE_STOP이면 0, 아니면 V_MAX). MPC가 호출되는 스텝에는 SAFE_STOP이
없으므로(REQ-LAT-05) 학습 표본의 v_target은 사실상 상수(V_MAX)입니다. 따라서
평가·판정은 **δ 중심**으로 하고, v_target 오차는 참고 지표로만 표기합니다. 표준편차가
0이면 정규화 분모는 1로 둡니다(0 나눗셈 방지 — 2단계-D `student_model.py`의 X_std=0
처리와 같은 방식).

**(개정 1) 입력 캡처 시점**: 2단계-D는 로그(`steps`)의 `y`/`v`(차량 갱신 **후** 값)로
feature를 만들었지만, I4는 v2 MPC `solve()`에 실제로 들어간 **갱신 전** `y0`/`v0`와 같은
스텝 로그의 센서값(`ey_line`/`front_gap`/`left_clear`, 갱신 전 센서 판독)을 페어링합니다
(`improved/runner.py`는 수정하지 않고 MPC 인스턴스의 `solve`만 감싸 기록). Student가
폐루프에서 받는 입력과 시점이 정확히 같아집니다.

### 1-4. 상태별 표본 분포와 RETURN_TO_L2 부족 문제

**위험**: S3 격자는 `psi0=0` 고정이고 장애물 회피 궤적이 상대적으로 규칙적이라,
`RETURN_TO_L2`(EVADE_L→KEEP_L1 이후, KEEP_L2로 복귀하는 전이 구간)가 **다른 상태보다
episode당 지속 스텝 수가 짧고**, 특히 S3 격자 중 실패(충돌/SAFE_STOP/타임아웃)
episode는 아예 이 상태에 도달하지 못합니다 — 2단계-D M트랙(paper+left_obstacle
200 episode)의 실측 분포(EVADE_L 5,229 / **RETURN_TO_L2 5,344** / KEEP_L2 975 /
KEEP_L1 468)에서는 RETURN_TO_L2가 오히려 컸지만, 그건 `left_obstacle`(SAFE_STOP
비중 높음, RETURN_TO_L2 자체가 적음)과 섞인 수치이고, **paper 단독 + S3(대량,
psi0=0) 조합에서는 실제 분포가 달라질 수 있어 사전에 낙관할 수 없습니다.**

**대응 (개정 1, 사용자 결정 2026-09-25 — 역빈도 가중은 삭제)**:
1. dev seed 100~199 + S3 dev 격자(900)로 먼저 생성하고, **MPC가 호출된 스텝의 상태별
   개수**를 실측해 §1-4-표에 기록합니다. 특정 상태를 미리 "부족한 상태"로 지목하지
   않습니다(2단계-D 데이터에서는 RETURN_TO_L2가 아니라 KEEP_L1이 가장 적었음:
   468 vs RETURN_TO_L2 5,344).
2. 판정: **(가장 적은 상태의 스텝 수) < (가장 많은 상태의 스텝 수) / 3** 이면 paper
   dev seed를 **200개 단위로 늘려 재생성**합니다. eval seed 200~299는 제외하고
   **300번대부터** 씁니다(1차 확대 300~499, 2차 500~699, …). S3 dev 격자는 그대로
   둡니다(격자는 고정 설계라 확대 대상이 아님).
   - 판정 대상 상태: MPC가 호출될 수 있는 4개 상태(KEEP_L2, EVADE_L, KEEP_L1,
     RETURN_TO_L2). SAFE_STOP은 REQ-LAT-05에 따라 MPC를 호출하지 않아(hold_last)
     교사 라벨이 구조적으로 0건이므로 판정에서 제외합니다(선택이 아니라 정의상 0).
   - **[공백] 멈춤 조건(이번에 추가, 사용자 확인 필요)**: seed 확대는 모든 상태를
     거의 같은 비율로 늘리므로, 부족이 구조적(예: 라인이 감지되면 MPC 대신
     라인추종을 쓰는 상태)이면 확대를 반복해도 비율이 좋아지지 않습니다. 그래서
     **확대 후 (최소/최대) 비율이 확대 전보다 개선되지 않으면 더 늘리지 않고 멈추고
     보고**합니다. 확대 결과를 보고 seed 대역을 고르지 않도록 대역은 위 순서로 고정합니다.
3. **가중·오버샘플링은 쓰지 않습니다.** 손실은 모든 스텝에 같은 가중(MSE)입니다.
4. §3(평가)의 상태별 MAE는 항상 모든 상태를 따로 보고합니다.

#### §1-4-표. 상태별 표본 수 (MPC 호출 스텝, 실측 — 생성 후 기록)

원자료: `thesis_v2/results/i4_student/20260925_075822_DESKTOP-MDCKRJS/dataset/dataset_summary.json` (2026-09-25, DESKTOP-MDCKRJS, 57.6초).
MPC 호출 스텝만, 모든 dev 에피소드 outcome=성공(paper 500/500, S3 900/900).

| 라운드 | paper dev seed | KEEP_L2 | EVADE_L | KEEP_L1 | RETURN_TO_L2 | 최소/최대 | 판정 |
|---|---|---|---|---|---|---|---|
| 0 | 100~199 (100) + S3 900 | 8,176 | 46,001 | **4,453** | 56,446 | 0.0789 | < 1/3 → 확대 |
| 1 | + 300~499 (300) | 9,318 | 55,426 | **5,351** | 67,615 | 0.0791 | < 1/3 → 확대 |
| 2 | + 500~699 (500) | 10,383 | 64,617 | **6,226** | 78,821 | 0.0790 | 비율 개선 없음 → **멈춤** |

- 가장 적은 상태는 **KEEP_L1**(데이터에서 계산, 2단계-D와 같은 상태).
- **부족은 구조적입니다(확인됨, 실행)**: 에피소드당 MPC 호출 스텝이 paper/S3 모두
  KEEP_L1 ≈4.4~4.5, KEEP_L2 ≈5.5~8.5, EVADE_L ≈46, RETURN_TO_L2 ≈56으로 일정합니다.
  KEEP_L1·KEEP_L2는 라인이 감지되면 MPC 대신 라인추종(REQ-LAT-01)을 쓰므로 MPC 라벨은
  라인 미검출 구간(ey fallback 100%)에서만 생깁니다. seed를 늘리면 모든 상태가 같은 비율로
  늘어 **최소/최대 비율은 약 0.079에서 움직이지 않고**, 1/3 기준은 seed 확대로 도달할 수
  없습니다.
- 계층 분할 확인(라운드 2 데이터): train/val 상태 비율 KEEP_L2 6.5%/6.3%, EVADE_L
  40.4%/40.4%, KEEP_L1 3.9%/3.9%, RETURN_TO_L2 49.2%/49.4%.
- **학습 데이터 결정(2026-09-25 사용자): Round 0 채택 — 115,076 샘플**(paper dev 100 + S3 dev
  900). 근거: 설계가 사전 고정한 범위이고, seed 확대는 불균형 해소를 조건으로 한 조치였는데
  그 조건이 성립하지 않음(0.0789→0.0791→0.0790, 구조적). Round 2 데이터(160,047 샘플)는
  삭제하지 않고 `dataset_round2_UNUSED/`로 **미사용 보존**. 학습용 `legacy_2025/dataset/`은
  `--expansion-rounds 0`으로 같은 코드·같은 seed로 재생성(상태별 수는 라운드 0과 동일).
  - (정정) 이전 보고의 "114,576"은 합산 오기, 정확한 값은 115,076(= 8,176+46,001+4,453+56,446).
  - Round 0 계층 분할: train 97,824 / val 17,252. 상태 비율 train/val = KEEP_L2 7.13%/6.95%,
    EVADE_L 39.99%/39.91%, KEEP_L1 3.87%/3.90%, RETURN_TO_L2 49.02%/49.25%.
- **멈춤 조건은 Claude Code가 추가한 [공백] 항목**입니다(사용자 규칙에는 중단 조건이 없었음):
  "확대 후 최소/최대 비율이 개선되지 않으면 더 늘리지 않고 멈추고 보고".
- **학습 분포 = 실제 사용 분포(확인됨, 코드+실행)**: Student는 폐루프에서 **MPC 호출
  스텝만** 대체합니다. `closed_loop.py`는 `improved/lateral.py`의 `compute_lateral`을 그대로
  호출하고 MPC 인자 자리에만 Student를 넘깁니다 — SAFE_STOP은 `lateral.py:27-28`(hold_last),
  라인 감지 KEEP_L2/KEEP_L1은 `lateral.py:35`(line_follow)에서 먼저 반환되어 Student가 호출되지
  않고, `lateral.py:37`의 `mpc.solve` 자리에서만 Student δ가 쓰입니다. 실행 확인(dev seed
  100~102): Student 호출 수 = mpc 모드 스텝 수(158/158, 153/153, 190/190), line_follow 스텝
  (KEEP_L2 23·29, KEEP_L1 19·18·10)은 Student 미호출. 따라서 KEEP_L1 비중이 낮은 것은
  데이터 결함이 아니라 **Student가 실제로 쓰일 분포를 정확히 반영**한 것입니다.

### 1-5. 학습/검증 분리 기준 (개정 1: 재추첨 규칙 삭제 → 계층 분할)

**에피소드 단위 split**(스텝 단위 아님 — 같은 에피소드의 연속된 스텝은 서로
강하게 상관돼 있어, 스텝 단위로 무작위 분리하면 train/val이 사실상 겹쳐 val
loss가 과낙관됨, `IMPROVEMENT_BACKLOG.md` 후보6에서 이미 지적한 위험).

- 비율: **85/15**(Table 5, [정합]).
- 소스별 독립 분리: paper dev와 S3 dev를 따로 나눈 뒤 합칩니다.
- **계층 분할(stratified) 방법** — 에피소드 단위로 나누되 상태별 스텝 비율이
  학습/검증에서 유지되도록 합니다:
  1. 각 에피소드의 상태 구성 벡터(4개 상태별 스텝 비율)를 계산합니다.
  2. 그 소스 안에서 전체 스텝이 가장 적은 상태(데이터에서 계산 — 미리 지목하지
     않음)의 비율 기준으로, 동률은 다음으로 적은 상태 비율, …, 마지막으로 에피소드
     id 순으로 정렬합니다.
  3. 정렬된 목록을 n_val = round(0.15 × n_episode)개의 연속 블록으로 나누고, 각
     블록에서 1개 에피소드를 고정 split seed의 난수로 골라 검증 세트에 넣습니다
     (정렬 후 계통 추출 — 구성이 비슷한 에피소드끼리 묶인 블록마다 1개씩 뽑으므로
     상태 비율이 양쪽에 고르게 퍼짐).
- **split seed는 고정 1개(`SPLIT_SEED = 20260925`), 재추첨 없음.** 분할 결과의
  상태별 비율(train/val)은 그대로 기록만 하고, 결과를 보고 다시 나누지 않습니다.
- **변경 이유**: 개정 전 설계는 "검증 세트에 상태별 최소 20건이 될 때까지 split seed를
  1씩 올려 재시도"였습니다. 규칙을 미리 정해 두었더라도, 분할 결과를 보고 seed를
  바꾸는 절차는 **결과를 보고 고르는 것으로 보일 수 있어**(repro/docs/WORK_RULES.md 금지 "seed 골라내기"와
  같은 모양) 삭제했습니다. 계층 분할은 한 번의 고정 seed로 비율 유지를 구조적으로
  보장하므로 재추첨이 필요 없습니다.

### 1-6. 옛 데이터셋과의 분리

원본 학습에 쓰인 데이터셋(`dataset_combined_v2_fixed`, 체크포인트 `args`에서 확인,
저장소에 원본 파일 없음)과 **절대 병합하지 않습니다.** 새 데이터셋은
`thesis_v2/results/i4_student/<timestamp>/dataset/`에만 저장하고, 기존
`legacy_2025/models/normalization_stats.json`도 **다시 계산**(새 데이터셋의 평균·표준편차로,
REQ-STU-04 방식은 유지하되 값은 새로 산출 — 옛 통계를 재사용하면 새 데이터 분포와
안 맞음)합니다.

---

## 2. 학습

### 2-1. 하이퍼파라미터 — Table 5 기준, 편차 명시

| 항목 | Table 5(PDF) | 이번 사용값 | 편차 여부·근거 |
|---|---|---|---|
| Optimizer | Adam | Adam | 동일 |
| Learning rate | 1e-3 | 1e-3 | 동일 |
| Batch size | 256 | 256 | 동일 |
| Epoch | 50 | **50 전부 실행**, 검증 손실 최저 epoch의 체크포인트 채택, **조기 종료 없음**(개정 1 확정) | **[해석]**: Table 5는 "epoch=50"만 명시하고 조기종료 여부는 없음(공백). 기존 `legacy_2025/models/policy_best.pth`도 체크포인트에 `best_val_loss`/`best_epoch` 추적 흔적이 있어(§0, `train_policy` 계열 스크립트 구조) best-checkpoint 채택이 이 프로젝트의 기존 관행과 일치. **epoch 예산 자체(50)는 Table 5 그대로 유지**하고 "50번 다 돌되 그중 val loss가 가장 낮은 시점의 가중치를 저장"으로 해석 — PDF 값을 넘기지 않으므로 [개정]이 아니라 [해석]
| Train/val split | 85/15 | 85/15 | 동일(§1-5) |
| Loss | (PDF에 명시 없음) | MSE(`nn.MSELoss`), 정규화된 [δ, v_target] 2출력 평균, **가중 없음**(개정 1: 역빈도 가중 삭제) | **[공백]** — Table 5에 loss 함수 명시 없음. 기존 체크포인트가 회귀(δ, v_target 2차원 연속값) 문제이므로 MSE가 표준적 최소 가정 |
| Gradient clipping | (명시 없음) | `clip_grad_norm_(max_norm=1.0)` | **[공백]**, 안 쓰면 BatchNorm+작은 학습률 조합에서 손실 발산 위험이 있는 표준 안전장치 — 판정 결과에 개입하는 파라미터가 아니라 학습 안정화 장치이므로 실험 튜닝으로 보지 않음 |
| LR scheduler | (명시 없음) | `ReduceLROnPlateau(factor=0.5, patience=5)` | **[공백]**, 위와 같은 이유 |
| Dropout | 0.15(REQ-STU-01) | 0.15 | 동일 |
| 정규화 통계 | (legacy_2025/models/normalization_stats.json) | **학습 split만으로** 새로 계산(검증 split은 통계에 포함하지 않음), std=0인 차원은 분모 1 | [공백] — 검증 데이터 정보가 학습 전처리에 새지 않게 하는 표준 절차 |

### 2-2. 재현성

- 학습 seed(모델 초기화·DataLoader shuffle): 고정 정수 1개(예: `--seed 7`), 실행
  커맨드에 명시 인자로 남김(하드코딩 금지, CLI 인자).
- `torch.manual_seed`, `numpy.random.seed`, `random.seed` 모두 같은 값으로 고정.
- 학습 로그: epoch별 `train_loss/val_loss/lr/rmse_delta/rmse_v`를 JSON으로
  저장(`train_log.json`) — 그래프는 4단계 논문 개정판에서 필요 시 그림.
- 체크포인트: `torch.save`로 `{epoch, model_state_dict, optimizer_state_dict,
  scheduler_state_dict, best_val_loss, history, args}` 저장(기존 `legacy_2025/models/
  policy_best.pth` 구조와 동일 키 — 새 로더가 기존 M트랙 로더 코드 패턴을
  최대한 재사용 가능하도록).
- **GPU/CPU**: 이 PC(DESKTOP-MDCKRJS)에 CUDA 가능 여부를 학습 실행 직전에
  확인하고(`torch.cuda.is_available()`), `env.json` 스타일로 device 정보를
  같이 기록(계산시간 평가와 무관 — 학습 자체의 재현 기록용).

---

## 3. 평가 (실행 전 기준 확정)

### 3-1. MAE

- **비교 기준 (개정 1 확정)**: **주 기준 = v2 MPC 출력**(I4의 교사), **참고 = baseline
  v1.1 MPC 출력**. 옛 MPC(code_backup 12-04) 대비는 **하지 않습니다**(2단계-D §4-1에서
  옛 MPC 자체의 비용함수 스케일링 버그가 확인돼 기준으로 부적절).
  - baseline 참고값은 **같은 입력**에서 구합니다: v2가 주행한 궤적의 각 MPC 호출
    스텝마다, 같은 `(y0, psi0, v0, target_y, state)`로 baseline `OSQPMPC.solve()`를
    그림자(shadow) 호출합니다(차량 조향에는 쓰지 않음, 인스턴스 1개를 궤적 순서대로
    재사용 — warm-start 조건이 실제 사용과 같게). 이렇게 하면 "같은 입력에서 Student가
    v2와 baseline 중 어느 쪽에 가까운가"를 직접 비교할 수 있습니다. 같은 표에 v2와
    baseline 사이 차이(|δ_v2 − δ_base|)도 함께 적어, Student 오차를 해석할 척도로 씁니다.
- **δ 중심**: 판정·주 보고는 δ(deg) MAE입니다. v_target MAE는 참고 지표로만 표기합니다
  (§1-3 개정 1 — MPC 호출 스텝의 v_target은 상수).
- **데이터**: **eval seed 200~299**(paper 시나리오, eval 2회차와 동일 신규 축 —
  학습 데이터(dev 100~199 + S3 dev 격자)와 전혀 겹치지 않음, [정의상 held-out]).
  이 측정 전용으로 v2 MPC를 다시 실행해 (feature, v2 δ) 페어를 만듭니다(이미
  eval 2회차에서 v2를 실행했지만 그 결과는 판정 완료·동결이라 재사용하지 않고
  같은 seed로 **다시** 계산 — v2는 결정론적이라 같은 seed 재실행은 같은 수열을
  내므로 "새 조건"이 아님, `RESULT_IMPROVED.md` §10의 baseline/v1 연속성 재확인과
  같은 논리).
  - 이 재실행은 **판정 데이터가 아니라 진단/평가용 재실행**입니다 — eval 2회차
    자체의 승인된 결론(충돌률·S3 등)을 다시 만들거나 바꾸지 않습니다.
- **지표**: 상태별 MAE(delta, deg) + 전체 MAE, `RESULT_STUDENT.md` §4와 같은
  형식(MPC 호출 상태 4종 개별 + 전체 + OOD 비율(|z|>3, 연속형 4개 feature 기준, 새
  학습 split 통계 기준) + n). 추가로 오차 분포(p95, max)도 적습니다.
- **판정 기준**: 절대 임계치 없음(MEASURE_PLAN.md M트랙 원칙 유지) — 수치를 그대로
  보고하고, 논문 Table 15(1.20°, 어느 교사 기준인지 불명 — 이미 §4-1에서 확인 불가로
  기록됨)와는 직접 비교하지 않습니다.

### 3-2. 폐루프(closed-loop) 평가 — 포함 여부·판정 기준

논문은 Student를 **개루프(교사 출력 모방 오차)로만** 평가했고, "Student가 실제로
차량을 조향하는 폐루프 검증"은 하지 않은 것으로 확인됩니다(THESIS_PAGES.md에 해당
서술 없음 — PDF 자체의 한계). **이걸 하면 논문 범위를 넘어서는 새 성과**이므로,
**(개정 1) 실행합니다 — 단계적으로, 실행은 사용자가 합니다.**

**설계**:
- **방법**: `thesis_v2/improved/runner.py`의 `run_episode` 루프에서 `ImprovedMPC.
  solve()` 호출부를 **Student 추론으로 대체**한 별도 runner
  (`student_i4/closed_loop_runner.py`, 원본 `runner.py`는 미수정 — 같은 복제 패턴,
  `eval_timing_analysis.py`/`eval_v2_timing_diagnosis.py` 선례와 동일 방식)로
  에피소드를 끝까지 시뮬레이션. 종방향 제어는 그대로 규칙 기반(REQ-SPD, 핵심 주장
  2 유지 — Student 출력 v_target은 폐루프에서 쓰지 않음, δ만 대체). FSM·충돌판정·
  안전 로직은 전부 그대로.
- **시나리오 (개정 1: 2단계로 나눠 실행)**:
  - **1차**: paper eval seed 200~299(100회). v2 MPC 결과는 eval 2회차 원자료
    (`thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/`)와 페어 비교.
  - **2차**: 1차에 "문제없음"일 때만 S3 eval 격자(eval 2회차 신규 1/4칸 오프셋
    900격자, `run_eval_v2.py`의 `EVAL2_S3_FRONT_GAPS/Y0S`).
  - **"문제없음"의 정의(실행 전 확정, [공백] — 2026-09-25 사용자 승인)**: 실행 측면의
    문제만 봅니다 — (a) 예외·NaN 없이 100 에피소드 모두 결과(outcome)가 기록됨,
    (b) Student δ 출력에 NaN/inf 없음, (c) 결과 파일 저장 완료. 충돌률 등 성능
    수치는 2차 진행 여부를 가르지 않습니다(성능은 "정보로 보고" 원칙, 아래 판정
    기준). 결과를 보고 2차 격자·seed를 바꾸지 않습니다.
- **판정 기준(실행 전 확정)**:
  - 충돌률: v2 MPC 대비 **악화 없음**이 이상적이나, Student는 근사 모델이라
    다소 악화 가능 — "협상 대상"이 아니라 "정보로 보고"(baseline↔v2 판정과
    달리, Student는애초에 [보조] 핵심 주장 3 범위라 강한 판정 기준을 걸지 않음,
    MEASURE_PLAN.md M트랙 원칙 "절대 임계치 없음"을 폐루프에도 동일 적용).
  - S3 실패율: v2 MPC 대비 배수로 보고(예: "v2 0%→Student X%").
  - **하드 제약(δ 범위 등) 위반**: Student 출력은 QP가 아니라 하드 제약을
    보장하지 않으므로, 후처리(`postprocess.apply`, rate limit+clip)는 그대로
    거치되 clip 발생률을 별도 지표로 보고(제어 로직 변경 없음 — 후처리가
    이미 clip으로 범위를 강제하므로 안전 위반은 없음, 다만 "얼마나 자주
    clip에 의존하는지"가 Student 품질 지표).
- 실행 규모: paper 100 + S3 900 = 1,000 episode 폐루프 시뮬레이션 — **100 episode
  기준을 넘는 벤치마크이므로 repro/docs/WORK_RULES.md 보고 규칙대로 명령과 예상 시간만 제시하고
  실행은 사용자**가 합니다(설계 승인 시 이어서 준비).

### 3-3. 계산시간 (PyTorch·ONNX vs v2 MPC, 같은 조건)

- **방법론**: `official_timing_benchmark_v3.py`(방금 공식 측정에 쓴 스크립트)와
  **동일 조건**(같은 호스트 DESKTOP-MDCKRJS, AC+최고성능, `--power-mode-confirmed`,
  같은 3개 시나리오 paper/left_obstacle/S6_psi-15)으로 v2 MPC 대비 PyTorch·ONNX
  Student 추론 시간을 측정합니다. ONNX 변환은 `RESULT_STUDENT.md` §6 방식
  재사용(`torch.onnx.export(..., opset_version=17, dynamo=False)`, 변환 후 출력
  차이 검증 단계 포함).
- **주 지표**: **p99**(`MEASURE_PLAN.md` 2026-09-25 정정 반영 — max는 참고).
- **지표**: mean/p50/p95/**p99**/max, 추론만 vs 정규화 포함, 스레드 1 고정(§6-3
  선례, 임베디드 단일 코어 가정).
- **배수 보고**: v2 MPC p99 대비 Student(PyTorch/ONNX) p99의 배수(절대 임계치
  없음, MEASURE_PLAN.md M트랙 원칙 유지). **v2는 972 반복 상한으로 p99가 이미
  1.4ms대까지 낮아져 있어(§12), 1회차 M트랙 때(baseline MPC p99≈0.22ms) 보다
  Student에게 더 유리한(격차가 좁혀진) 비교 조건**이라는 점을 결과 해석에 명시.

**(개정 1) 구체 절차**: 한 프로세스에서 (1) `official_timing_benchmark_v3.py`의
`timed_improved_episode`와 같은 루프로 v2 MPC를 3개 시나리오 × seed 0~99로 주행하며
MPC solve 시간과 **그 호출의 Student 입력(9차원)**을 함께 모으고, (2) 주행이 끝난 뒤
같은 입력 목록 전체(호출 순서 그대로, 표본 선별 없음)에 대해 PyTorch → ONNX 순으로
1건씩(batch=1) 추론 시간을 잽니다(warmup 50회 제외). MPC와 Student의 입력 집합이
정확히 같습니다. v2 MPC 시간은 이 실행에서 다시 재고, 공식 측정(`timing_v3/..._v2`)과
나란히 적어 조건 차이를 확인합니다. 스레드는 torch·onnxruntime 모두 1(§6-3 선례).
`env.json`은 `collect_env_info`로 기록하고, 사용자가 전원 모드를 확인한 경우에만
`--power-mode-confirmed`를 붙입니다(붙이지 않은 결과는 참고치).

### 3-4. 변동성(variability) 비교 — MPC vs Student

**주장**: "MPC는 입력 난이도에 따라 반복 횟수·계산시간이 변하지만, Student는
일정하다." 이번 공식 측정(§12)에서 이미 이 비대칭성의 절반(MPC 쪽)은 수치로
확인됨 — v2 MPC 반복 횟수 mean이 시나리오별 59.4(paper)~142.6(left_obstacle)으로
2.4배 차이, p95는 225~972로 4.3배 차이. Student 쪽은 이번에 새로 측정합니다.

- **지표**: 각 버전(v2 MPC, Student-PyTorch, Student-ONNX)의 solve/추론 시간에
  대해 **변동계수(CV = std/mean)**를 시나리오별로 계산 후 비교. 반복 횟수는
  Student에는 개념이 없으므로 MPC만 보고(§12-3처럼).
- **예상(가설, 실행 전 명시 — 결과로 이 가설 자체를 사후 수정하지 않음)**: MPC의
  CV는 시나리오 난이도에 따라 크게 변하고(쉬운 시나리오는 CV 작음, 어려운 시나리오는
  반복 상한 근처까지 벌어져 CV 커짐), Student의 CV는 시나리오와 무관하게 일정한
  낮은 값을 유지할 것으로 예상합니다. 실측이 가설과 다르면(예: Student도 시나리오별
  CV 차이가 크면) 있는 그대로 보고합니다.

---

## 4. 사용자 결정 (2026-09-25 확정, 개정 1)

1. 표본 부족 대응: 역빈도 가중 삭제, dev seed 200개 단위 확대(300번대부터) — §1-4
2. MAE: v2 MPC 주 기준 + baseline v1.1 MPC 참고, 옛 MPC 제외 — §3-1
3. 폐루프: 실행, 1차 paper eval 200~299 → 문제없으면 2차 S3 eval 격자, 실행은 사용자 — §3-2
4. epoch: 50 전부, 검증 손실 최저 체크포인트, 조기 종료 없음 — §2-1
5. split: 재추첨 규칙 삭제 → 에피소드 단위 계층 분할, split seed 고정 1개 — §1-5
6. v1 left_obstacle 현상 표기: "반복 상한 20,000회 도달, 하드 제약 통과, fallback 0건"
   ("QP 발산" 표현 쓰지 않음) — THESIS_REVISION_LOG
7. 평가는 δ 중심, v_target 오차는 참고 지표 — §1-3, §3-1

**이번 개정에서 새로 생긴 확인 필요 항목([공백], 결과 보고 때 함께 확인 요청)**:
- §1-4 학습 데이터 범위 → **Round 0 확정**(2026-09-25)
- §1-4 seed 확대 멈춤 조건 → Claude Code 추가 [공백]으로 명시, Round 0 채택으로 종결
- §3-2 1차→2차 진행 조건 → **승인**(실행 오류 없음·NaN 없음·결과 저장 완료만, 성능 수치 제외)

---

## 6. Student v2 — 입력 10/11차원 ablation (2026-09-25 설계, **승인됨** — §6-7 추가 결정 반영)

근거: `SETTINGS_DECISION.md` §20(ψ [개정], δ_prev [발전 파생]). 기존 9차원 Student(I4) 결과·모델·데이터는
**보존**(삭제·덮어쓰기 금지) — Student v2는 새 결과 폴더(`thesis_v2/results/i4_student_v2/<ts>_<host>/`)와 새
코드 경로(기존 `student_i4/`에 입력 차원 옵션 추가, 기본값은 9차원 그대로 → 기존 테스트·재현 불변)로 진행.

### 6-1. 입력 정의 (11차원, 순서 고정)

| # | 이름 | 출처(시점: 해당 스텝 FSM·제어 계산 시점, 차량 갱신 전) | 근거·태그 | 정규화 |
|---|---|---|---|---|
| 0~8 | v, ey_line, front_gap, left_clear, state_one_hot(5) | 기존과 동일(§1-2, ey fallback 규칙 포함) | REQ-STU-02 [정합] | 학습 split z-score, std=0이면 분모 1 (기존과 동일) |
| 9 | ψ (deg) | 차량 헤딩(자기 상태, FSM REQ-FSM-02e가 쓰는 값과 같은 출처) = MPC `psi0_rad`×180/π | §20 **[개정]** | 학습 split z-score |
| 10 | δ_prev (deg) | 제어기 직전 스텝 최종 조향(후처리 후) = MPC `delta_prev_deg`와 같은 값, 첫 스텝 0 | §20 [발전] 파생(교사 v2의 I1) | 학습 split z-score |

- 기존 9개 순서를 바꾸지 않고 뒤에 붙임(기존 코드·해석과 대조 쉬움).
- 폐루프에서도 같은 값을 같은 시점에 넣음(캡처 시점 = 사용 시점, §1-3 개정 1 원칙 유지).

### 6-2. 네트워크·학습 — 입력 차원만 변경

- 구조: 논문 Table 4 그대로(첫 층만 11→256, 나머지 256→256→128→2, BatchNorm+ReLU+Dropout 0.15).
- 하이퍼파라미터: Table 5 + §2-1 [해석]/[공백] 전부 동일(Adam 1e-3, batch 256, 50 epoch 전부·검증 손실 최저
  체크포인트·조기 종료 없음, MSE 가중 없음, grad clip 1.0, ReduceLROnPlateau(0.5, 5), 학습 seed 7).
- 교사: v2 MPC(I4와 동일, cap=972).

### 6-3. 학습 데이터

- 범위: I4 Round 0과 같은 dev 범위(paper seed 100~199 + S3 dev 격자 900), **ψ·δ_prev를 포함해 재생성**.
  v2 MPC·시나리오가 결정론적이므로 스텝·라벨·상태 분포는 Round 0과 같아야 함 → 생성 직후 **기존 Round 0의
  δ 라벨·상태·에피소드 키와 완전 일치 확인**(불일치 시 멈추고 보고). 기존 데이터셋은 그대로 보존.
- 분할: §1-5 계층 분할, SPLIT_SEED=20260925 그대로(상태 구성이 같으므로 train/val 에피소드도 I4와 같음 →
  9차원 vs 11차원을 같은 분할에서 비교).
- 가중·오버샘플링 없음(§1-4 개정 1 그대로).

### 6-4. 평가 데이터 — 새 eval 대역 (seed 200~299는 최종 평가에 쓰지 않음)

**사용된 seed 대역 확인(코드·문서 전수 검색, 2026-09-25)**: 0~99(baseline·1회차 eval, 계산시간 측정),
100~199(dev), 200~299(eval 2회차 + I4 폐루프·실패 분석 — **이미 본 데이터**), 300~699(I4 Round 1·2 생성,
미사용 보존), 700~899(I4 config의 확대 예약 대역, 미생성), 1000~1099(S4~S7 dev). **2000 이상은 미사용.**

| 용도 | 정의 | 비고 |
|---|---|---|
| **eval3 paper** | **seed 2000~2099**(100) | 미사용 대역, 기존 대역과 거리 둠 |
| **eval3 S3** | front_gap0 **0.5375~1.9875**/0.05 × y0 **−0.1425~0.1475**/0.01 (30×30=900) — **3/4칸 오프셋** | 기존 격자 오프셋(front_gap 0/0.025/0.0025, y0 0/0.005/0.0025)과 전부 다름 → 겹침 없음(코드에서 assert). 범위 0.5~2.0, ±0.15 안 |
| 연속성 참고 | paper 200~299, eval 2회차 S3 격자 | "이미 본 데이터" — 판정에 쓰지 않고 참고로만 |

- eval3에서 **세 제어기 모두**(v2 MPC, 9차원 Student(I4 모델 그대로), Student v2)를 같은 seed·격자로 실행
  (v2 MPC·9차원 Student는 동결 모델 재실행, 수정 없음).
- eval3는 확정된 Student v2에 **1회만** 실행(repro/docs/WORK_RULES.md 3단계 원칙). 실패해도 모델·데이터·기준을 바꾸지 않고
  원인 분석만.

### 6-5. 판정 기준 (실행 전 확정)

| 항목 | 방법 | 판정 |
|---|---|---|
| **폐루프 충돌·완료(주 판정)** | eval3 paper 100 + S3 900, 에피소드 페어 비교(`run_eval_v2._paired`와 같은 방식) + Wilson 95% CI | **(a) v2 MPC 대비 비열화 없음**(3단계 기존 규칙 "비열화 금지" 재사용): 충돌 수 ≤ v2, 성공 수 ≥ v2 (paper·S3 각각) → **"통과 — MPC 대체 가능"**. **(b)** (a) 불충족이지만 9차원 Student 대비 성공 증가·충돌 감소가 페어 McNemar 정확검정(양측) p<0.05 → **"부분 개선 — 단독 제어기 불가"**. **(c)** 둘 다 아님 → **"실패"** |
| 폐루프 진행 조건(1차→2차) | §3-2와 동일 | 실행 오류·NaN 없음, 결과 저장 완료. 성능 수치는 조건 아님 |
| 개루프 MAE(상태별) | eval3 paper, v2 MPC 궤적의 MPC 호출 스텝 전부, 같은 입력으로 v2(주)·baseline(참고) 그림자 호출. **9차원 Student도 같은 입력으로 함께** 평가 | 절대 임계치 없음(M트랙 원칙). δ 중심, v_target 참고. 9차원 대비 변화 보고 |
| 원출력 ±25° 초과율·clip·rate 개입률(상태별) | 폐루프 Student 호출 스텝 기준(RESULT_I4 §6-3과 같은 정의) | 정보 보고(v2 MPC는 QP로 0%). 9차원 대비 변화 보고 |
| 분포 이동(상태 조건부 \|z\|>3) | RESULT_I4 §6-1과 같은 정의 | 정보 보고 |
| 계산시간 p99·CV | `benchmark_timing.py`와 같은 조건(3 시나리오 × seed 0~99), v2 MPC vs PyTorch vs ONNX, 9차원 vs 11차원 | 참고(절대 임계치 없음). `--power-mode-confirmed` 없으면 참고치로 표기 |

### 6-6. 실행 순서 (승인 후)

데이터 생성(+Round 0 일치 확인) → 학습 → 개루프 MAE → 폐루프 1차(eval3 paper) → 2차(eval3 S3) → 계산시간.
100 에피소드 넘는 실행은 repro/docs/WORK_RULES.md 규칙대로 명령·예상 시간을 제시하고 사용자가 실행(I4와 같은 방식).
실패 시 다음 후보: IMPROVEMENT_BACKLOG 후보 9(DAgger), 10(출력 제한 내장).

### 6-7. 추가 결정 (2026-09-25 사용자 승인) — ablation과 dev 선택

- **δ_prev 분류 = [발전]** 승인(§20). 사용자의 앞선 "[개정]" 지시는 정정됨(THESIS_REVISION_LOG).
- **두 버전 학습**(네트워크·하이퍼파라미터·데이터·split 동일, 입력 차원만 다름):
  - **S10** = 9입력 + ψ (10차원, [개정]만 — 논문 명세 결함 수정의 순수 효과)
  - **S11** = S10 + δ_prev (11차원, [개정]+[발전])
  - 참고: 기존 9입력(I4 모델 그대로, 재학습 없음)
- **dev 비교(선택은 dev에서만)**:
  - 개루프: 학습 데이터의 **val split**(dev 안의 held-out 에피소드, 세 모델 공통 — 같은 split) 상태별 δ MAE
    vs v2 MPC 라벨.
  - 폐루프: **dev paper seed 100~199 + dev S3 격자 900**(학습 시나리오와 같은 dev 범위, eval 데이터 아님).
  - 보조 지표: 원출력 ±25° 초과율, 분포 이탈률(상태 조건부 |z|>3, 학습 split 통계 기준 — (i) 각 모델 자신의
    연속 입력 기준, (ii) 공통 기준 = 연속 4개 + ψ), clip·rate 개입률.
- **선택 규칙(실행 전 확정)** — S10과 S11 중 하나. dev 폐루프 1,000 에피소드(paper 100 + S3 900)를 합쳐
  에피소드 페어 비교:
  1. S11이 S10보다 **성공이 유의하게 많고**(성공 여부 페어 McNemar 정확검정 양측 p<0.05) **충돌이 많지 않으면**
     (충돌 수 S11 ≤ S10) → **S11**
  2. 또는 S11이 **충돌이 유의하게 적고**(충돌 여부 페어 McNemar p<0.05) **성공이 적지 않으면**(성공 수 S11 ≥ S10)
     → **S11**
  3. 그 밖의 모든 경우(동등·유의하지 않은 차이·지표 간 상충) → **입력이 적은 S10**
  - 개루프 MAE·보조 지표는 선택에 쓰지 않고 보고만 함. 9입력은 선택 후보가 아님(명세 결함 버전, 참고 비교).
- **eval3**(paper 2000~2099, 3/4칸 S3): 선택 후 **1회만**. 실행 대상: v2 MPC / 기존 9입력 / 선택 버전(판정) /
  미선택 버전(참고 기록만, 판정에 쓰지 않음). 판정 기준은 §6-5 그대로.
- 결과가 나빠도 모델·데이터·기준을 바꾸지 않고 원인 분석만.
- **선택 결과(2026-09-25, 규칙 적용)**: dev 폐루프 S10·S11 모두 1000/1000 성공·충돌 0 → 동등 → **S10**
  (`RESULT_I4.md` §8). eval3 판정 대상 = S10, S11은 참고 기록.
- **eval3 최종 판정(2026-09-25, 기준 커밋 ab5b021)**: S10 paper 100/100·S3 900/900·충돌 0, v2 MPC와 페어 불일치 0 →
  **(a) 통과 — MPC 대체 가능**. 9입력 대비 McNemar p≈6×10⁻²⁸¹(성공, 합산). `RESULT_I4.md` §9~11.
