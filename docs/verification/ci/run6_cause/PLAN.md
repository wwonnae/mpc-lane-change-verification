# run #6 원인 확정 실험 — 사전 선언

- 작성: 2026-10-14, 실험 실행 전(1단계 도구 점검과 소규모 동작 확인만 한 상태)
- 원칙: 아래 N, 조건, 판정 규칙은 결과를 보기 전에 고정한다. 바꾸게 되면 사유와 시각을 이 문서 끝 "변경 기록"에 추가하고 이전 내용은 지우지 않는다.
- 근거: 정적 분석 `STATIC_ANALYSIS.md`(0단계)

## 1. 도구 (이 폴더)

| 파일 | 역할 |
|---|---|
| `osqp_probe.py` | OSQP 기록 래퍼. `osqp.OSQP`의 setup/update/warm_start/solve를 감싸 원래 함수를 그대로 부르고 읽기만 한다. pytest 플러그인으로도 쓸 수 있다(`-p osqp_probe`) |
| `harness.py` | 반복 실행. 임시 사본(--root)의 테스트 함수를 그대로 호출한다. 10회 묶음 단위로 중단·재개하고, 부하 생성과 CPU 기록기 실행을 관리한다 |
| `sysmon.ps1` | CPU 기록(Windows 성능 카운터 원시값, 10초 구간 평균, PID 기준) |
| `apply_condition.py` | 임시 사본 생성(`git archive`, thesis_v2만, results 제외)과 조건 적용. 저장소 경로 안에서는 적용을 거부한다 |
| `analyze.py` | 집계(§4 정의) |

## 2. 1회차와 대상

1회차는 아래를 각각 1번씩 실행한 것이다. 소요 시간은 부하 없이 약 0.76초다(2026-10-14 소규모 확인).

| 이름 | 내용 | 불일치 정의 |
|---|---|---|
| i5 | `test_improved_i5.test_i5_golden_determinism_three_runs` 호출(I5 on, max_iter 1944, time_limit 0.045, paper seed 0, 3 에피소드) | 테스트 실패, 또는 3개 에피소드 중 어느 쌍이라도 delta_final 시계열이 다름 |
| i4_rec | `test_i4_recorder_does_not_change_episode` (TEACHER_FLAGS, max_iter 972, seed 100) | 테스트 실패, 또는 ref/got delta_final이 다름 |
| i4_cl100, i4_cl101 | `test_i4_closed_loop_matches_improved_runner_with_mpc(100/101)` | 테스트 실패, 또는 ref(improved runner) delta_final과 got(closed_loop traj[6])이 다름 |
| base (대조군) | baseline `run_episode(generate_scenario(0))` 3회 | 시간 열(t_mpc_solve_ms, t_step_ms)을 뺀 전체 로그 행이 3회 중 하나라도 다름 |

- 테스트 함수는 사본의 원래 코드를 그대로 쓴다. 테스트가 부르는 `run_episode`만 반환값을 모으는 래퍼로 감싼다(인자와 반환값은 그대로 넘김).
- 회차 사이 기준: 같은 arm 안에서 최빈 서명(에피소드별 delta·전체 행 해시)과 다른 회차 수도 센다. 한 회차 안의 3회가 서로 같아도 다른 회차와 다른 경우를 잡기 위해서다.

## 3. 실험과 회차 수

**N:**
- 조건(arm)당 **1000회차**다. 불일치가 0회이면 단측 95% 상한은 1−0.05^(1/1000) ≈ **0.30%** 이다. 같은 값을 Clopper-Pearson 양측 구간으로도 보고한다.
- 계획 승인 때 예시로 든 300회(상한 1.0%)보다 늘렸다. 실측 회차 시간이 예상보다 짧기 때문이다(0.76초).
- 중간에 멈추는 규칙은 두지 않는다. 결과를 보고 N을 바꾸지 않는다.

| 실험 | 조건(arm) | 부하 | 회차 | 비고 |
|---|---|---|---|---|
| S1_identity | probe_off, probe_on (원래 설정 사본) | 없음 | 각 50 | 래퍼 무영향 확인. 묶음마다 교차 |
| S2_noload | orig | 없음 | 1000 | 사용자 확인 후 시작 |
| S2_load | L8, L16, L32 (orig) | k = 8 / 16 / 32 | 각 1000 | 5묶음씩 번갈아 실행 |
| S3 | orig, A (§6-1 결정: B·C 없음) | §3-2 규칙으로 정한 k | 각 1000 | 5묶음씩 번갈아 실행 |

### 3-1. 부하 생성 (고정)

- **방식:** 기본 인터프리터(`Python39\python.exe`)로 순수 파이썬 바쁜 루프 프로세스 k개를 띄운다. 프로세스 1개가 코어 1개를 100% 쓰고, 우선순위는 Normal(테스트와 같음)이다. harness가 사라지면 스스로 끝난다.
- **강도:** 이 PC의 논리 코어 8개 기준으로 다음 세 단계다.
  - k=8: 1배. 모든 코어가 바쁘다.
  - k=16: 2배 초과 할당
  - k=32: 4배 초과 할당
  - k<8은 빈 코어가 남아 테스트 스레드가 밀려날 일이 거의 없으므로 단계에서 뺐다. 계획 승인 때 예시로 든 "4/8/16"을 이렇게 바꾼다.
- **대기:** 부하를 바꿀 때마다 12초 기다린 뒤 다음 묶음을 시작한다. 10초 CPU 표본 구간이 이전 부하 조건과 겹치지 않게 하기 위해서다.

### 3-2. S3 부하 수준 (사전 규칙)

- S2_load에서 orig 불일치율이 가장 높은 k를 쓴다. 같으면 큰 k를 쓴다.
- 세 단계 모두 0회이면 k=32를 쓰고, 그 사실을 한계로 기록한다.

### 3-3. 부하 없음 조건

- 사용자가 PC를 쓰지 않는 시간에만 실행한다. 시작 전에 사용자 확인을 받는다.
- **회차별 위반 판정:** 그 회차의 실행 구간과 겹치는 sysmon 10초 표본을 겹친 길이로 가중 평균한다. 이 값의 `other_pct`(실험·부하 프로세스를 뺀 나머지 프로세스의 CPU 합, 기계 전체 대비 %)가 **10%를 넘으면 "조건 위반"** 으로 표시한다.
- 전체 사용률 원값(`total_pct`)과 잔차(`residual_pct` = total − 실험 − 부하)도 함께 기록한다.
- 위반 회차를 빼지 않은 결과와 뺀 결과를 둘 다 보고한다.

### 3-4. 기록 (원자료)

각 실험 폴더(`raw/<실험>/`)에 다음을 남긴다.
- `env.json`: PC 정보. CPU 모델, 코어 수, OS, Python, numpy, scipy, osqp, torch 버전, 전원 계획, 스레드 관련 환경변수
- `events.jsonl`: 시작, 재개, 중단, 끝, 묶음, 부하 변경 시각
- `sysmon.jsonl`: 10초마다 CPU 사용률과 상위 5개 프로세스. 세션 시작·끝 스냅샷 포함
- `batches/*.json.gz`: 회차별 결과
  - 불일치 여부, 처음 어긋난 행과 solve 번호, 최대 차이
  - 첫 불일치 solve의 입력이 같았는지와 다른 입력 항목
  - 첫 불일치 solve ±3의 status, iter, run_time, wall_ms, 지문
  - 지문이 나온 solve 전부
  - 불일치 회차는 모든 solve의 전체 기록
- **중단·재개:** `out_dir/STOP` 파일을 만들면 진행 중인 묶음을 끝내고 멈춘다. 강제 종료되면 진행 중이던 묶음은 저장하지 않는다(harness 생존을 회차마다 확인). 재개하면 끝난 묶음을 건너뛰고, 중단 시각 추정치(`last_seen`)와 재개 시각을 남긴다.

## 4. 판정 규칙

**지문(time_limit 발동, STATIC_ANALYSIS.md §3-3):** 다음 중 하나면 지문으로 본다.
- status가 "run time limit reached"
- status가 "solved inaccurate"이고 iter < max_iter
- status가 "solved"이고 iter % 25 ≠ 0이고 iter ≠ max_iter

1단계 양성 대조(§5)로 이 규칙을 검증했다.

| 질문 | 판정 |
|---|---|
| Q1. 불일치가 time_limit 발동과 항상 함께 나오는가 | 불일치 회차의 각 불일치 쌍마다 처음 어긋난 solve에서 (a) 입력 해시가 같은지, (b) 양쪽 중 하나라도 지문이 있는지 센다. **(a)와 (b)가 모든 쌍에서 참이면 "항상 함께"** 로 판정한다. 하나라도 거짓이면 그 사례를 따로 보고한다 |
| Q2. 래퍼 무영향 | S1에서 probe_off 50회와 probe_on 50회의 회차 서명(에피소드별 delta·전체 행 해시)이 **모두 하나의 값으로 같으면** 통과 |
| Q3. 부하와 불일치의 관계 | S2의 k별 불일치율과 Clopper-Pearson 95% 구간을 보고한다. 단조 경향은 서술로만 다루고 검정은 하지 않는다 |
| Q4. 조건 효과(3단계) | 같은 k에서 orig 대비 각 조건의 불일치 수를 Fisher 정확검정(양측)으로 비교한다. "그 조건에서 불일치가 사라졌다"는 **조건 arm 불일치 0회이면서 orig와의 p < 0.05** 일 때만 쓴다. orig 불일치가 0회이면 "판별 불가"로 적는다 |
| Q5. 대조군 base | base에서 불일치가 1회라도 나오면 정적 분석 §5(baseline에는 벽시계 경로 없음)와 모순이다. 따로 조사한다 |

**가설 판정:**
- **H1(time_limit 절단)을 원인으로 확정하는 조건:** Q1이 "항상 함께"이고, 3단계에서 A의 불일치가 사라짐(Q4)
- **H3/H4:** 첫 불일치 solve의 입력 해시가 다름
- **H5:** 입력이 같고 지문도 없는데 출력이 다름

이 경우들은 사례로 보고한다.

**monitor 누락 규모:** 지문이 있는 solve 가운데 status가 "run time limit reached"가 아닌 것의 수를 보고한다.

## 5. 1단계 확인 결과 (도구 점검, 측정 아님)

- **양성 대조(조건 T, time_limit 0.5 ms, 사본, 5회차 i5+i4):**
  - solve 5,340회 중 지문이 있는 158회는 전부 run_time ≥ time_limit이었다.
  - 지문이 없는 5,182회는 전부 run_time < time_limit이고 iter가 25의 배수였다.
  - 끊긴 solve의 보고 status는 "run time limit reached" 95회, **"solved inaccurate" 63회**였다. "solved inaccurate"는 `time_limit_hit`과 monitor에 세지지 않는 경로다.
  - "solved" + 25의 배수가 아닌 iter 경로는 이 표본에서 나오지 않았다.
  - 모든 회차에서 불일치가 났다. 첫 불일치 solve는 입력이 같고 양쪽 모두 지문이 있었다.
- **래퍼 무영향(부하 통제 없이 3회 + 3회):** 서명이 같았다. 정식 확인은 S1에서 한다.
- **도구 수정 이력(측정 전):**
  - venv 런처 PID 대신 실제 인터프리터 PID를 기록하도록 고쳤다.
  - sysmon을 PID 기준으로 바꾸고 other를 직접 합산하도록 고쳤다.
  - harness가 죽으면 부하 프로세스와 진행 중인 묶음이 함께 멈추도록 고쳤다.
  - 부하 변경 뒤 대기 시간을 넣었다.

## 6. 사용자 결정 (2026-10-14, 실행 전)

1. **조건 B: (1)안.** 3단계는 orig와 A(time_limit 끔) 두 조건만 비교한다. B와 C는 넣지 않는다.
   - 근거 [확인-실행, 2026-10-14]: B 사본(`apply_condition.py --cond B --interval 50`)에서 I5 test 조합과 TEACHER_FLAGS의 C 쪽 설정을 읽었다(사본 폴더에서 import해 사본 코드임을 확인). `adaptive_rho=1`, `adaptive_rho_interval=50`, `time_limit=0.045`, `max_iter=1944/972`로 **orig와 같았다.**
     자연값(자동 규칙)은 쓰이지 않고 기본값 50이 그대로 쓰이므로 B1(자연값)=B2(50)=orig다.
   - [추정] 노트북 Run F("adaptive_rho_interval=50 고정 + 강한 부하")도 같은 이유로 사실상 원래 설정이었다. Run F 결과는 "원래 설정, 강한 부하" 참고 표본으로 읽는다.
   - rho 갱신이 시간과 무관하다는 점은 래퍼가 기록한 rho 갱신 수로 확인한다. 같은 arm 안에서 에피소드 위치별 rho_updates 총수가 회차마다 하나의 값인지 본다(`analyze.py` "rho 갱신 총수"). 다만 불일치(지문)가 난 회차는 그 이후 경로가 달라지므로 따로 본다.
2. **N과 부하:** N=1000(조건당)과 부하 k=8/16/32를 승인받았다.
3. **부하 없음 조건의 VS Code·claude:** Claude Code가 VS Code 터미널 안에서 돌기 때문에 VS Code는 닫을 수 없다.
   - 위반 기준(other > 10%)은 그대로 둔다.
   - sysmon이 이름 패턴 `^(Code|claude|node)(#\d+)?$`에 맞는 프로세스 사용량을 `ide_pct`로 따로 기록하고, other에 기여한 상위 8개 프로세스(`top_other`)를 원자료에 남긴다.
   - 집계는 위반 회차를 "VS Code·claude 기여로만 위반"과 "그것을 빼도 위반"으로 나눠 표시한다.
4. **진행 순서:** S1과 S2 부하 없음은 사용자가 "시작"이라고 한 뒤 실행한다. 끝나면 결과를 먼저 보고한다. 부하 실험(S2 8/16/32, S3)은 사용자가 시작 시점을 정한다.

## 변경 기록

- 2026-10-14: §6 사용자 결정 기록. sysmon에 ide_pct·top_other 추가, analyze.py에 위반 원인 분류와 rho 갱신 분포 추가(측정 전).
- 2026-10-14 12:12: S2_load가 끝났다. 결과는 `S2_RESULT.md`에 있다. §3-2 규칙을 적용해 **S3 k=8**로 정했다(orig 불일치 L8 1/1000, L16 0, L32 0). 사용자 지시("멈추지 말고 계속")에 따라 바로 시작했다. 근거가 1건뿐이라는 한계도 함께 기록한다.
- 2026-10-14 12:20: analyze.py에 **보조** CPU 재분류 `other_adj_pct`를 추가했다. trial pid와 load_set pid를 top_other에서 빼는 방식이다. 이유는 sysmon이 표본 도중 끝난 batch 프로세스와 부하 전환 순간의 부하 프로세스를 other로 분류하는 결함을 S2_load 원자료에서 확인했기 때문이다. 위반 판정 원값(other_pct, 10%)은 바꾸지 않았고 둘 다 보고한다. 결과(불일치 판정)와는 무관한 집계 보조값이다.
- 2026-10-14 13:05: S3 끝(S3_RESULT.md). harness.py run_main이 batch에 넘기는 --root를 절대경로로 바꿨다(CI root '.' 대응, 실행 중에는 고치지 않음). 사본 cwd에서 root '.'로 2회차 확인 실행을 해 통과했다(스크래치 출력).
- 2026-10-14: S4(GitHub 러너, flaky-probe #1, 97d1ed6) 원자료를 raw/S4_runner/에 정리하고 S4_RESULT.md를 작성했다. 기존 CI 결과는 사용자 확인 대기다.
- 2026-10-14 14:21: 5단계 변이 재확인 완료(S5_MUTANT_RESULT.md). 16/16 kill 유지.
- 2026-10-14: S4_RESULT §3에 기존 CI 결과(두 OS 성공)를 기록했다. 5단계 영향 분석(S5_IMPACT.md), S5_MUTANT_RESULT 생존 129개 검토, README.md 초안을 작성했다(커밋 전, #2 결과 대기).
- 2026-10-14: 사용자 대응 결정(선택지 2+5+0, 1·3·4 불채택)을 README §4에 기록했다. 제품·테스트 변경은 커밋 1 이후 계획 승인 뒤에 한다.
- 2026-10-14: S4 #2(repeats 1500) 원자료를 raw/S4_runner/run2/에 정리했고(#1은 run1/로 이동), S4_RESULT §5, README, S5_IMPACT 수치를 갱신했다.
- 2026-10-14 15:10~15:12: S6 양성 대조 실행 중 경로 사고가 있었다. 스펙에 경로를 `/c/Users/...`(Git Bash 형식)로 적어 Windows Python이 `C:\c\Users\...`에 출력 폴더를 만들었다. 13:05 harness 상대경로 smoke 테스트 때도 같은 원인으로 이 폴더가 생겼다. 내용이 이 두 실행의 출력 16개 파일뿐인 것을 확인하고 `C:\c`를 지웠다. 저장소와 다른 파일에는 영향이 없다. 이후 스펙은 `C:/Users/...` 형식만 쓴다.
- 2026-10-14: S6 지문 규칙 검토(raw/S6_fingerprint_check/). 사용자 결정으로 안 B를 채택했다. osqp_probe.tl_fingerprint를 안 B로 맞췄고, 기존 판정 변화는 0건이었다. STATIC_ANALYSIS §3-3·S5_IMPACT·README에 정정 블록을 붙였다.
- 2026-10-14: 커밋 2(대응 변경 2+5+0) 준비. 재확인 기록은 COMMIT2_VERIFY.md에 있다.
- 2026-10-15: 야간 실행(3187e40) 결과를 반영했다(README §6 1~4 완료, COMMIT2_VERIFY §8). mutation 4단계를 마무리했다(RESULTS.md, MUTATION_TABLES, CI 단계).
