# 측정 기준 (2단계-A, 실행 전 확정)

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

트랙별로 무엇을, 어떻게, 어떤 허용오차로 판정할지 실행 전에 고정합니다. 실행 후에는 이 기준을
바꾸지 않습니다(금지 목록). 결과는 `thesis_v2/results/<타임스탬프>_<호스트>_<버전>_<트랙>/`에
저장합니다(호스트명 포함 — SSAFY PC와 노트북 두 대를 오가며 실행하므로 어느 환경에서 나온
결과인지 폴더명만으로 구분하기 위함, `env.json`에도 동일 정보가 기록됨).

---

## 공통 원칙

- 모든 트랙은 `thesis_v2/baseline/config.py`의 고정 파라미터(N,dt,qy,qψ,rδ,rΔδ,δ±25°,200deg/s,
  G_TRIG,G_SAFE_MIN,COOLDOWN,W,L,B)를 그대로 사용합니다. 시작 시 assert로 검증합니다.
- seed는 트랙별로 하나 고정하고 결과 폴더명/메타데이터에 기록합니다. seed를 여러 개 시도해
  좋은 것을 고르지 않습니다.
- 절대수치(계산시간 등)는 하드웨어 종속이므로, "절대값"과 "주장 수준"(예: 20Hz 예산 내인지)을
  분리해서 기록합니다.
- 논문 수치와의 비교는 **참고용 각주로만** 답니다. baseline 결과가 논문 수치와 다르다고 해서
  baseline을 고치지 않습니다.
- **관찰구간 FSM 갱신 정의 정정[2026-09-22, baseline v1.1]**: 이전 버전은 완료 판정 후
  진단용 관찰구간(`OBSERVE_STEPS=20`) 동안 FSM을 갱신하지 않았습니다. 이 동결이
  REQ-SEN-01 front_gap 버그(장애물을 완전히 지나쳐도 방향 구분 없이 0.0을 반환)를
  우연히 가려, 100 에피소드 결과(성공 99/충돌 1)에 영향이 없는 것처럼 보이게 했습니다
  (`THESIS_REVISION_LOG.md` 2026-09-22 REQ-SEN-01). **정정 이유**: 관찰구간의 목적은
  "완료 후에도 실제로 안정 상태인지" 확인이므로, FSM이 멈춰 있으면 그 확인 자체가
  무의미합니다 — 실제 연속 주행을 재현하려면 관찰구간에도 FSM이 계속 갱신되어야
  합니다. **이것은 더 엄격한 방향의 정정이며, 결과를 보고 기준을 완화한 것이
  아닙니다**(repro/docs/WORK_RULES.md 금지 목록과 무관 — 오히려 이전 정의가 결함을 가릴 수 있었던
  느슨한 쪽이었고, 이번 정정으로 더 많은 실패 유형("관찰 중 상태 이탈")을 검출할 수
  있게 됐습니다). 제어기(FSM·MPC·속도 제어) 로직 자체는 바꾸지 않았고, 측정 하네스가
  "언제까지를 유효한 주행으로 볼지"의 정의만 바꿨습니다(`thesis_v2/baseline/runner.py`
  모듈 docstring 참고).
- **성공률·충돌률 등 이항 비율은 항상 Wilson 95% 신뢰구간과 함께 보고합니다**(2026-09-17
  추가, 100 에피소드처럼 표본이 작을 때 "99%" 같은 단독 % 표기는 표본오차를 숨겨 과신을
  유발할 수 있음). 형식: `k/n (95% CI a~b%)`(예: `99/100 (95% CI 94.6~99.8%)`), 단독 `%`
  표기 금지. 구현: `thesis_v2/baseline/summary.py:wilson_ci`.
- **공식 측정 환경 [환경 결정 변경, 2026-09-17]**: 노트북(Core Ultra 9 185H, `.venv` Python
  3.9.12, numpy 2.0.2, scipy 1.13.1, osqp 1.1.1, Windows 11 Pro, hostname
  `DESKTOP-MDCKRJS`). 이전(2단계-A)에는 SSAFY PC(Python 3.12.9)를 공식으로 지정했으나,
  **사용자가 현재 노트북만 사용 가능하고, 이 노트북이 논문 작성 당시 실제 사용 장비였다는
  점을 근거로 노트북으로 변경**합니다. SSAFY PC 값은 참고용으로만 남깁니다
  (`thesis_v2/requirements-py312.txt`).
- **계산시간 측정 조건(공식 측정 시 필수)**: 전원 어댑터 연결(AC) 상태 + Windows 전원 관리
  모드를 "최고 성능"으로 설정한 상태에서만 공식 계산시간 수치로 인정합니다(배터리 구동이나
  절전/균형 모드에서는 CPU 클럭이 스로틀링되어 계산시간이 부풀려질 수 있음). `env.json`에
  전원 상태(AC/배터리, `GetSystemPowerStatus` API)와 활성 전원 계획 이름(`powercfg
  /getactivescheme`, 조회 실패 시 `"unknown"`)을 기록해 사후에 조건 충족 여부를 확인할 수
  있게 합니다. 조건이 확인되지 않은 실행(배터리 구동이거나 전원 계획을 확인할 수 없는 경우)의
  계산시간은 "참고"로만 보고합니다.
  - **Windows 11 "전원 모드" 슬라이더(최고 절전/균형/최고 성능)는 `powercfg
    /getactivescheme`이 보여주는 "전원 계획"과 다른 값**입니다(overlay 레이어). `env.json`에
    `power.power_mode_overlay` 필드로
    `HKLM\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\ActiveOverlayAcPowerScheme`
    레지스트리 값을 읽어 기록을 시도합니다(`thesis_v2/baseline/envinfo.py`). **이 노트북은
    해당 레지스트리 값이 존재하지 않아 자동 감지가 불가능함을 확인했습니다**(2026-09-17,
    `power_mode_overlay="감지 불가"`로 기록됨 — OEM 전원관리 소프트웨어가 대신 제어하거나
    슬라이더를 아직 조작한 적이 없는 기기에서 발생 가능). **사용자 수동 확인 체크 항목 +
    코드 지원(2026-09-17 추가)**: 공식 계산시간 측정 실행 전, Windows 설정 > 시스템 >
    전원 > "전원 모드"가 실제로 "최고 성능"으로 되어 있는지 직접 확인한 뒤,
    `python -m thesis_v2.baseline.run ... --power-mode-confirmed`로 실행하십시오 — 이
    플래그가 `env.json`에 `power.power_mode_user_confirmed=true`와 확인 시각을 기록하고,
    최종 공식 조건 판정(`power.meets_official_condition`)에 반영됩니다:
    `ac_status=="AC" AND (power_mode_overlay가 최고 성능 GUID를 가리키거나 OR
    power_mode_user_confirmed==true)`. 이 노트북처럼 overlay 자동 감지가 안 되는 기기는
    `--power-mode-confirmed` 플래그가 공식 조건을 성립시키는 유일한 경로입니다. 플래그
    없이 실행한 결과는 자동으로 "참고"로만 표시됩니다(`summary.json`의
    `*.measurement_status`).
- **공식 계산시간 측정 시점[2026-09-22 변경]**: 공식 계산시간은 baseline과 3단계 개선판이
  모두 나온 뒤, **모든 버전을 노트북 1회 세션에서 연속 측정한다**. 이유: baseline만 먼저
  측정하고 개선판을 나중에 별도 세션에서 측정하면, 두 측정 사이의 전원·발열·백그라운드
  프로세스 등 세션 조건 차이가 버전 간 계산시간 비교에 섞여 공정한 비교가 안 됨. **그 전의
  모든 계산시간 수치(2단계-C까지 baseline만으로 측정한 값 포함)는 참고값(호스트 명기)이다**
  — "공식" 판정으로 승격하지 않는다. 일괄 측정 절차는 `NEXT_SESSION.md` §4에 계획만
  기록해두고, 구현·실행은 3단계 완료 후 진행한다.
- 교차 환경(노트북 ↔ SSAFY PC) 재현성: 각 실행은 결과 폴더에 `env.json`(호스트명, Python·
  numpy·scipy·osqp 버전, CPU, OS, OSQP 설정값, 전원 상태)을 남깁니다. 두 환경이 같은
  코드에서 같은 결과를 내는지는 `thesis_v2/tests/check_golden.py`(전이 목록·결과 분류·완료
  step 완전 일치 + 조향각 시계열 최대 차이 ≤1e-3 rad)로 확인합니다 — 실패하면 baseline을
  고치지 않고 원인(환경 차이 vs 코드 문제)을 먼저 규명합니다. **양방향 확인 완료**: 노트북
  (golden 생성 환경, osqp 1.1.1)에서 2026-09-17 6/6 PASS, **SSAFY PC(osqp 1.1.3, Python
  3.12.9)에서 2026-09-18 6/6 PASS(최대 차이 0.000000 rad)** — 상세는
  `RESULT_BASELINE.md` §9. 설치는 환경별 고정 파일(`thesis_v2/requirements-py39.txt`=노트북/
  공식, `thesis_v2/requirements-py312.txt`=SSAFY PC/참고)을 사용합니다. SSAFY PC의 `.venv`는
  `--system-site-packages`로 생성해 이미 설치된 torch(2.11.0+cu128, M트랙용)를 재사용합니다.
- **M트랙 측정 환경 원칙(2026-09-18 추가)**: MPC solve 시간과 Student 추론 시간의 비교는
  "torch가 설치된 동일 호스트에서, 같은 실행 안에서 쌍으로" 측정합니다(다른 호스트에서 각각
  잰 값을 나중에 나누지 않음 — 호스트별 CPU 성능 차이가 배수에 섞이는 것을 방지). P트랙의
  "공식 측정 환경=노트북" 원칙과는 별개입니다(노트북에 torch를 설치하지 않았으므로 M트랙은
  SSAFY PC에서 수행). 결과 폴더의 `env.json`에 호스트 정보(CPU, OS, torch 버전, torch 스레드
  수)를 명시합니다. **절대 계산시간(ms)은 참고치이며, 판정 대상은 MPC 대비 Student의 배수
  (중앙값 기준)입니다** — 절대값을 P트랙 공식 수치(노트북)와 직접 비교하지 않습니다.

---

## P트랙 — 물리 폐루프 (주 트랙)

**목적**: `thesis_v2/baseline`의 FSM+MPC+속도규칙이 kinematic 시뮬레이터에서 명세대로
동작하는지 확인.

**시나리오**: `REQ-SIM-01~09`(`SPEC.md`), seed 고정, 100 에피소드(논문과 같은 수 — 단
"논문 수치 재현"이 아니라 "표본 크기를 맞춘 것"임을 결과에 명시).

**측정 항목과 판정 기준(실행 전 확정)**:

| 항목 | 측정 방법 | 허용 기준 |
|---|---|---|
| 제약 만족(허용오차 내) / 위반 | 매 스텝 δ_raw(후처리 전), ψ, y(상태별 REQ-MPC-05 구간)를 각각 REQ-MPC-04 범위와 비교. **허용오차 = OSQP `eps_abs`**(SETTINGS_DECISION.md §18, rad/m 단위 그대로 — δ·ψ는 deg 환산 시 ≈0.0057°, y는 0.0001m): `\|δ_raw\|≤25°+eps_abs`이면 "제약 만족(허용오차 내)", 그 이상 벗어나면 "제약 위반". ψ·y도 같은 원칙(구현: `thesis_v2/baseline/metrics.py`) | 제약 만족(허용오차 내)이 100%여야 함 — eps_abs를 넘는 "제약 위반"이 하나라도 있으면 QP 구현 버그로 취급(§16 clip 출처 분석과 같은 판정 기준). y는 SAFE_STOP 스텝 제외(REQ-LAT-05, 위치제약 미정의) |
| clip 분리 기록 | 후처리 clip이 걸린 스텝을 `after_rate_deg`(rate limit 후, clip 전 값) 기준으로 세분류: `clip_numerical`(±25°를 eps_abs 이내로 초과, 솔버 수치오차) / `clip_violation`(eps_abs를 넘게 초과, 버그 후보) | `clip_violation`은 0건이 기대값. 0이 아니면 제약 만족률 항목과 함께 원인 분석(멈추고 보고) |
| 조향 포화 비율 | 상태별로 `\|δ_final\|≥25°−0.01°`인 스텝 수 / 그 상태의 총 스텝 수 | 기준 없음(기술 통계 — EVADE_L·RETURN_TO_L2처럼 급격한 조향이 필요한 상태에서 포화가 잦은 것은 "결과"이지 "버그"가 아님. 단 KEEP_L2·KEEP_L1에서 포화가 잦으면 원인 분석) |
| 충돌률 | REQ-SIM-08(§8) 기준 회전 사각형 SAT, FSM 판정보다 먼저 매 스텝 체크 | 0건이 기대값(논문 주장과 별개로, 명세대로면 G_SAFE_MIN=0.20 마진이 있어 발생하면 안 됨). 발생 시 "결과"로 그대로 보고 |
| SAFE_STOP 발생 횟수 | 상태 로그 | 논문 시나리오(`paper`)는 REQ-SIM-07에 따라 left_clear가 항상 True이므로 0건이 기대값. 좌측 장애물 시나리오(`left_obstacle`, 추가 검증용)는 발생이 기대값(REQ-FSM-02b 검증 목적) — 시나리오별로 기대치가 다름을 결과에 명시 |
| FSM 상태별 체류 비율·오차(y, ψ, δ) | 논문 Table 6 형식으로 재현하되 **"측정값"으로만 표기, 논문 수치와 나란히 놓지 않음** | 기준 없음(기술 통계, 참고용) |
| MPC 계산시간 | `time.perf_counter()`로 solve() 앞뒤 측정 | **공식 측정 환경은 노트북으로 지정**(위 공통 원칙 참고), **AC 전원 + Windows 최고 성능 모드 조건에서 측정한 값만 공식**으로 인정(`env.json`의 전원 상태로 확인). 조건 미충족이거나 다른 환경(예: SSAFY PC)에서 측정한 값은 "참고(환경명)"로만 보고(`summary.json`의 `mpc_solve_time_ms.measurement_status` 필드로 자동 표기). 주장 수준: 평균이 50ms(20Hz 예산)의 몇 %인지만 판정 |
| 종방향 제어 정합성 | v_cmd가 REQ-SPD-01/02를 벗어나는 스텝이 있는지(MPC가 속도를 건드리는지) | 0건이어야 함(핵심 주장 2번의 직접 검증) |

**seed**: 사용자 실행 시 하나의 정수로 고정(예: 42). 결과 폴더명에 포함.

---

## C트랙 — 비교 테스트 (기존 OSQPMPC vs baseline MPC)

**목적**: 같은 입력에서 기존 코드(`legacy_2025/final_hierarchical_backup_thesis_1204.py`, 2025-12-04
04:17본, 1단계에서 확인된 "실험 당시 코드")와 `thesis_v2/baseline`의 MPC가 얼마나 다른지,
차이가 **명세 차이로 설명되는지** 확인.

**금지**: `thesis_v2/baseline`는 기존 코드를 import하지 않습니다. 비교 코드만
`thesis_v2/tests/compare/`에서 기존 코드를 import합니다(예외로 허용된 유일한 위치).

**입력 설계**: 격자 또는 무작위(seed 고정) 샘플로 (y, ψ, v, target_y, FSM상태) 조합을 여러 개
만들어 두 MPC의 `solve()`에 동일하게 넣습니다.

**측정 항목과 판정 기준**:

| 항목 | 측정 방법 | 기대·판정 |
|---|---|---|
| δ 출력 차이 (같은 상태, 같은 위치 제약이 적용되는 조건) | \|δ_old − δ_new\| | qy,qψ,rδ,rΔδ,N이 전부 같으므로 **같은 위치제약 구간 안에서는 거의 0에 가까워야 함**(솔버 수치오차 수준, 예: 1e-3 deg 이내). 다르면 명세 불일치로 보고 원인 규명 |
| 위치 제약 구간이 다른 상태(RETURN_TO_L2 등, REQ-MPC-05로 baseline이 새로 상태별 매핑 적용) | 같은 (y,ψ,v)인데 상태만 바꿔 비교 | **다를 것으로 예상**(예상된 차이) — "명세 차이로 설명 가능"으로 분류 |
| FSM 전이 조건 차이 | 같은 (front_gap,left_clear,y,ψ,t) 조합을 기존 FSM·baseline FSM 양쪽에 넣고 다음 상태 비교 | RETURN_TO_L2→KEEP_L2(임계값 0.08 vs 0.20+헤딩), SAFE_STOP의 EVADE_L 예외 유무, 쿨다운 적용 범위 3곳에서 **다를 것으로 예상**(1단계 `PDF_VS_CODE.md`에 근거 있음) — "명세 차이로 설명 가능"으로 분류. 그 외 조건에서 다르면 버그로 취급 |
| MPC 비용함수 구조(rΔδ) | 같은 (y,ψ,v,target) 반복 입력에 대해 δ 시퀀스 궤적(N step) 비교 | 기존 코드는 rΔδ를 u_i² 크기 벌점으로 오구현(대각행렬, `SPEC_VS_OLDCODE.md`)해 baseline(진짜 차분 벌점, 비대각)과 **조향 궤적의 부드러움(2차 변화율)이 다를 것으로 예상** — "명세 차이로 설명 가능" |
| MPC 위치 제약(y bound) | EVADE_L·RETURN_TO_L2 등 상태를 바꿔가며 동일 (y,ψ,v)를 넣고 y 궤적이 제약에 걸리는 지점 비교 | 기존 코드는 상태 무관 단일 `±MAX_Y_DEVIATION`(기본 0.45), baseline은 상태별 3단계 제약 → **KEEP_L2/KEEP_L1에서 baseline이 더 타이트하게 제약될 것으로 예상** — "명세 차이로 설명 가능" |
| MPC 실패 시 fallback 게인 | OSQP를 강제로 실패시키는 입력(예: 극단적 초기값)에서 fallback δ 비교 | 기존 코드 게인 -qy(=100) vs baseline K_p=1.0 — **fallback δ 크기가 100배 수준으로 다를 것으로 예상** — "명세 차이로 설명 가능"(단, 둘 다 ±25° saturate되면 차이가 안 보일 수 있어 saturate 안 되는 입력으로 설계해야 함) |
| 계산시간 비교 | 같은 PC, 같은 입력 100회 반복 | 참고용(솔버 구현이 사실상 같은 OSQP 호출이므로 유의미한 차이 기대 안 함) |

**판정 라벨**: 각 차이는 "명세 차이로 설명됨" / "설명 안 됨(버그 후보)" 둘 중 하나로 표시합니다.

---

## M트랙 — 신경망(Student) 적용 여지

**목적**: 기존 `legacy_2025/models/policy_best.pth`(재학습 없음)를 그대로 로드해, MPC 대비 추론 속도와
(입력 정의가 맞을 때만) 조향 오차를 측정합니다.

**전제 조건 사전 확인 — 실행 완료(2026-09-17), 결과: 통과**

| 확인 항목 | 결과 |
|---|---|
| 학습 파이프라인 판정 | `legacy_2025/models/policy_best.pth`는 `torch.save`로 만든 딕셔너리 체크포인트(`epoch`, `model_state_dict`, `optimizer_state_dict`, `scheduler_state_dict`, `best_val_loss`, `history`, `args` 키 포함). `args`에 `{'data':'dataset_combined_v2_fixed','epochs':100,'batch_size':256,'lr':0.001,'val_split':0.15,'output':'models_v2_fixed','device':'cpu'}` 기록됨. **주의**: `epochs=100`, 실제 저장된 `epoch=77` — 논문 Table5의 "Epochs 50"과 다름(별도 학습 실행으로 추정, M트랙 사용 자체엔 지장 없음) |
| 체크포인트 키·shape | `model_state_dict`의 Linear 레이어 shape: `network.0`=(256,9), `network.4`=(256,256), `network.8`=(128,256), `network.12`=(2,128). BatchNorm(`network.1/5/9`)에 `running_mean/var` 포함 — **Table4 구조(9→256→256→128→2, BN 3곳)와 정확히 일치** |
| torch 버전·로드 가능 여부 | 이 PC torch **2.11.0+cu128**. `torch.load(..., weights_only=False)`로 정상 로드됨(체크포인트에 `args` 등 비-텐서 객체가 있어 `weights_only=True` 기본값으로는 실패할 수 있음 — thesis_v2에서 로드 시 `weights_only=False` 명시 필요) |
| 입력 9차원 일치 여부 | `legacy_2025/models/normalization_stats.json`의 `feature_names` = `[v, ey_line, front_gap, left_clear, state_KEEP_L2, state_EVADE_L, state_KEEP_L1, state_RETURN_TO_L2, state_SAFE_STOP]`, `label_names`=`[delta, v]` — **REQ-STU-02/03 정의와 정확히 일치**(순서 포함, state one-hot 순서도 논문 p.11 서술과 동일) |

**결론: 조향 오차 측정을 "무효" 처리할 필요가 없습니다** — 입력 정의가 정확히 일치하므로
M트랙에서 추론시간과 조향 오차를 모두 측정합니다.

**추가 확인(단위·인코딩, model.eval(), 비교 기준 우선순위)**:

| 확인 항목 | 결과/결정 |
|---|---|
| 단위 일치 | `normalization_stats.json`의 `X_mean[2]`(front_gap)≈7.18, `X_std[2]`≈4.00 — front_gap이 **미터 단위 원값**으로 정규화된 것으로 보임(0~10m LiDAR 유효범위와 스케일이 맞음). `X_mean[0]`(v)≈0.606, `X_std[0]`≈0.212 — v도 m/s 원값 스케일. baseline의 REQ-SEN-01 front_gap(§7, 미터)·REQ-SPD(v, m/s)과 **단위가 일치**하므로 별도 변환 불필요 |
| 인코딩(one-hot 순서) | `feature_names`의 `state_*` 5개가 `[KEEP_L2,EVADE_L,KEEP_L1,RETURN_TO_L2,SAFE_STOP]` 순서(REQ-STU-02, 논문 p.11 순서와 일치) — baseline의 state one-hot 생성 시 반드시 이 순서 그대로 사용 |
| `model.eval()` | 체크포인트에 BatchNorm(`running_mean/var`)이 있으므로, 추론 시 반드시 `model.eval()` 호출 필요(안 하면 배치 통계로 정규화되어 배치크기=1 추론 시 결과가 불안정/틀림). thesis_v2 M트랙 코드 작성 시 필수 항목으로 표시(지금은 코드 없음, 요구사항으로만 기록) |
| 조향 오차 비교 기준 우선순위 | Student는 **원 논문 Teacher 데이터(옛 MPC, code_backup 12-04)로 학습됨** — baseline(수정된 MPC)과 직접 비교하면 baseline 쪽의 [개정]·구조 차이(REQ-MPC-02/03a, 04, 07 등, `SPEC_VS_OLDCODE.md`)가 섞여 "Student 예측 오차"인지 "MPC 자체가 달라져서 생긴 차이"인지 구분이 안 됨. **1순위 비교 대상은 옛 MPC(C트랙에서 이미 준비)로 고정**하고, baseline MPC와의 비교는 참고용 2순위로만 보고 |

**주의사항(신규)**: `normalization_stats.json`의 속도 평균(X_mean[0]≈0.606m/s)이 논문의 속도
범위(0.0~0.5m/s, Table1)를 **초과**합니다(`THESIS_REVISION_LOG.md` 참고). baseline P트랙은
v_ref=0.5를 넘지 않으므로, M트랙에서 baseline 궤적을 Student에 입력하면 Student 입장에서는
일부 특징(v 등)이 **학습 시 관측한 분포보다 낮은 쪽**에 위치하게 됩니다 — 조향 오차 결과를
"Student가 부정확하다"로 바로 해석하지 말고, 입력이 학습 분포 안에 있는지 먼저 확인하고
보고합니다.

**결론(갱신)**: 위 확인으로 M트랙 실행 준비가 완료됐습니다. 코드는 2단계-D에서 작성합니다.

**측정 항목과 판정 기준**:

| 항목 | 측정 방법 | 기준 |
|---|---|---|
| 추론시간 vs MPC solve시간 | 같은 PC, 같은 입력 N회, `time.perf_counter()` | 참고용 배수 보고(예: "N배 빠름"), 절대 임계치 없음 |
| 조향 오차(δ) | Student(features) vs baseline MPC(y,ψ,v,target) 같은 상태에서 비교, **입력 특징 정의가 REQ-STU-02와 일치할 때만 수행** | 정의가 안 맞으면 "측정 무효"로 보고하고 종료 |

---

## R0 트랙 — 원본 재현

보류. 필요해지면(예: 논문 개정판에 "재현 성공률" 수치가 필요해질 때) 별도로 기준을 만듭니다.

---

## 실행 규모와 예상 시간 (참고, 실행은 사용자)

- P트랙 100 에피소드(최대 200 step): 순수 계산이라 에피소드당 수백 ms~수 초 예상(MPC 솔버
  호출 횟수에 좌우). 총 실행시간은 2단계-B에서 baseline 구현 후 1회 소규모 실행(5~10 에피소드)
  으로 먼저 실측해 안내하겠습니다.
- C트랙: 격자 크기에 따라 다름, 통상 수천 회 solve() 호출 — 수 초~수십 초 예상.
- M트랙: 6,000회 추론(논문과 표본 수만 맞춤) — 수 초 예상.

무거운 실행(100 에피소드 본 실행)은 2단계-B 코드 완성 후 정확한 명령과 예상 시간을
다시 안내하고, 실행은 사용자가 진행합니다.

---

## 3단계 I5(v2) 계산시간 주 지표를 max에서 p99로 변경 (2026-09-25, 지표 정의 변경)

**변경**: I5(반복 상한 v2, cap=972) 이후의 MPC solve 계산시간 판정에서, **최댓값(max)
대신 p99를 주 지표로 씁니다.** 위 P트랙 표의 "평균" 기준(baseline)과 `RESULT_IMPROVED.md`
§4/7이 지금까지 강조해온 "최댓값"(v1/v2 비교, 20Hz 예산 대비 %) 서술은 이 문서
작성 시점부터 **p99 기준으로 재해석**합니다(과거 기록된 max 수치 자체는 지우지 않고
"참고, 재현 안 됨"으로 병기).

**변경 시점**: 2026-09-25, eval 2회차(신규 seed 200~299) 승인 이후 — `RESULT_IMPROVED.md`
§9(최악 계산시간 성격 규명)의 진단 결과를 보고 결정했습니다. 결과를 보고 **판정 기준
자체(비열화 없음 등)를 바꾼 것이 아니라**, "어떤 통계량을 20Hz 예산 대비 %로 보고할지"
라는 지표 정의만 바꾼 것임을 명시합니다.

**근거(`repro/2c_analysis/eval_v2_timing_diagnosis.py`, 진단 재실행)**:
- v1: solve 시간(`compute_time_ms`, wall-clock)과 반복 횟수의 상관계수 **r=0.996**
  (n=69,561). 최댓값은 전부 `_MAX_ITER`(20000) 도달 사례 — **(가) 연산량 지배**,
  재실행해도 값 자체는 비슷한 크기(같은 조합·seed 재실행 시 37.4~45.2ms 사이,
  20000 반복이라는 성격은 항상 재현됨).
- v2: 상관계수 **r=0.941**로 여전히 강하지만(972 상한 도달 사례가 시간 분포 대부분을
  차지), **원래 eval 2회차에서 커밋된 최댓값(32.329ms, S7b/rear_gap_0.5m)이 같은
  조합·같은 seed·같은 warm-start 조건의 진단 재실행에서 전혀 재현되지 않았습니다**
  (재실행 관측 최댓값 6.018ms, 그마저 반복 25회의 저반복 solve — 972 상한 도달
  solve의 시간(1.4~4.4ms)보다 오히려 낮은 반복인데 더 오래 걸림). 반면 **p99는
  두 실행에서 거의 일치**합니다(커밋된 값 1.385~1.396ms vs 진단 재실행 1.402~
  1.408ms, 차이 <2%).
- **정확한 주장**: v1의 최댓값(42ms대)은 반복 20,000회 도달이라는, 재실행해도
  항상 재현되는 진짜 연산 폭주입니다. **I5(v2, cap=972)는 이 재현 가능한 연산
  폭주를 제거합니다** — 상한(972) 도달 solve 자체는 평균 1.46ms·최대 4.40ms로
  안정적입니다. eval 2회차에서 커밋된 v2의 최댓값(32ms대)은 반복 25회의 저반복
  solve에서 나왔고 연산량과 무관하며, 동일 조건 재실행으로 재현되지 않는 **OS
  지터**입니다(정확한 발생 원인을 이 세션에서 특정하지는 못함). v1도 지터가
  전혀 없다는 뜻은 아니지만, 20000반복 자체가 20~45ms로 이미 커서 지터의 상대적
  영향이 작아 구분이 잘 안 됐을 뿐입니다.
- **판정: (다) 혼재** — v1은 연산량이 압도적으로 지배하지만, v2(972, 채택된 최종
  조합)는 최댓값이 재현되지 않아 신뢰할 수 있는 지표가 아닙니다. p99는 두 조합
  전부에서 재현성이 확인돼 주 지표로 채택합니다.

**적용 범위**: `RESULT_IMPROVED.md`(§4 계산시간 트레이드오프, §9 v2 특성)의 "최댓값"
서술을 p99 기준으로 재작성하고, 최댓값은 "관측치(재현 보장 안 됨)"로 병기합니다.
baseline·v1(I5 없음) 판정 자체(P트랙 "평균" 기준)는 이 변경과 무관 — I5(v2) 도입
이후의 계산시간 비교에만 적용됩니다.

## 3단계(발전판) 판정 기준 해석 보완 (2026-09-23, dev 결과 확인 후 명확화)

`DESIGN_IMPROVED.md` §5의 "전체 위반 크기(최대·누적)가 baseline 이하" 조건은 dev
ablation(Stage 4) 결과를 본 뒤, 다음과 같이 **명확히** 합니다 — **이것은 판정 기준을
완화하는 것이 아니라, 처음부터 무엇을 "원래 제약"으로 볼지 명시하지 않았던 것을
분명히 하는 것**입니다(baseline이 이미 갖고 있던 REQ-MPC-04 등 원래 제약에 대한 판정
엄격도는 그대로 유지):

- **"위반 크기가 baseline 이하" 조건은 baseline에 이미 존재하는 원래 제약에만
  적용됩니다**: 차로 위치제약(REQ-MPC-04, 상태별 원래 범위 — I2가 올린 하한이 아니라
  `POSITION_CONSTRAINTS`의 원래 값), 헤딩(REQ-MPC-04, ±80°), 조향각·조향 변화율
  (REQ-VEH-02/03, ±25°·10°/step). baseline은 이 네 가지에 대해 위반이 0이므로, 개선판도
  이 네 가지에 대한 위반은 **0이어야 통과**입니다(baseline이 0이 아닌 경우가 생기면
  그때는 "baseline 이하"가 실질적 기준이 됨)
- **I2(장애물 인지)가 추가한 여유(margin) 기준은 별도 지표 "장애물 여유 미달"(최대·
  누적)로 보고**합니다 — 이건 REQ-MPC-04에 없는, baseline에는 아예 존재하지 않는
  **새 기준**이므로 "baseline 이하"라는 비교 자체가 성립하지 않습니다. 장애물 여유
  미달은 실패가 아니라 "I2가 원하는 것보다 덜 여유롭게 지나간 정도"를 보여주는
  정보성 지표로 다룹니다
- **발견 경위**: I1+I1b+I2 dev 실행에서 원래 차로 위치제약(REQ-MPC-04) 위반이
  baseline(0건)과 달리 nonzero(최대 0.134m, 100 에피소드 누적 18.18m, KEEP_L1/
  RETURN_TO_L2 상태)로 나와, "이 위반이 I2 자신이 만든 여유 기준 미달인지 원래
  REQ-MPC-04 위반인지" 분해가 필요해졌습니다. 분해 결과 이 위반은 **I2가 활성인 바로
  그 스텝(장애물 옆)에서 난 게 아니라, I2의 공격적 회피가 끝난 뒤 KEEP_L1/
  RETURN_TO_L2 구간에서 나는 원래 제약 위반**임을 확인했습니다(`i2_y_deficit`
  지표는 0건 — I2 자신의 여유 기준은 항상 만족함). 즉 이 사례는 "I2 여유 미달"이
  아니라 **원래 제약 위반이 baseline보다 큰 진짜 회귀**였고, 원인은 I2'(§DESIGN_IMPROVED
  I2 재도출)의 헤딩 하한 추가로 해소됨을 dev로 확인했습니다(I2': 원래 제약 위반 0,
  I2 여유 미달도 0)
- **판정 절차**: 개선판 dev/eval 보고 시 항상 (1) 원래 제약 4종 위반(0 또는
  baseline 이하 여부로 합격/불합격 판정) (2) I2 장애물 여유 미달(정보성, 판정 대상
  아님) 두 층으로 분리해 보고합니다
