# 커밋 2(run #6 대응: 선택지 2 + 5 + 0) 재확인 기록

- 작성: 2026-10-14. 이 PC(3층PC109), `.venv` Python 3.9.13, osqp 1.1.1. 부하 없음(사용자 작업 중이었으나 실험 부하 없음).
- 대상: 커밋 1(30a3a22) 위의 작업 트리(커밋 2 후보). 결정 내용은 README §4 "커밋 2 세부 결정"에 있다.
- 최종 수치는 모든 수정이 끝난 뒤 다시 실행한 결과다(§5의 시각).

## 1. 바뀐 것 (요약)

| 구분 | 파일 | 내용 |
|---|---|---|
| 선택지 2 | `thesis_v2/conftest.py`(신규) | `i5_time_limit_off` fixture(I5_TIME_LIMIT_SEC → 1e10, 명시 적용) |
| | 테스트 5개 파일 | 9개 함수(수집 항목 37개)에 `@pytest.mark.usefixtures("i5_time_limit_off")`. `test_i5_golden_determinism_three_runs` docstring 정정 |
| | `test_improved_i5.py` | 보호 테스트 2개(fixture → OSQP settings 1e10, 제품 인스턴스 0.045·972) |
| 선택지 5 | `thesis_v2/improved/mpc.py` | `time_limit_fingerprint`(안 B) 추가. setup 직후 `prob.settings`의 max_iter·check_termination 저장. I5 on의 `time_limit_hit`를 지문 판정으로 바꿈. 모듈 docstring·주석 정정 |
| | `thesis_v2/improved/runner.py` | `time_limit_count` 집계를 `time_limit_hit` 기준으로(max_iter 분기와 분리). 주목 스텝 조건에 `time_limit_hit` 추가. 필드 주석 |
| | `thesis_v2/improved/config.py` | 주석만 |
| | `test_improved_i5.py` | 지문 규칙 표 테스트(14경우), check_termination=0, 1e-9에서 status와 무관하게 hit, 1e10에서 hit 아님(4개 함수) |
| 선택지 0 | `repro/docs/DESIGN_IMPROVED_V2.md` | §0-2·§1-0·§1-4·§1-5·§2·§8 정정 블록(원문 유지) |
| | `repro/docs/RESULT_IMPROVED.md` | §10 정정·보충 블록 |
| | `thesis_v2/anomaly/DESIGN.md` | 2026-10-03 P0 불일치: "유력한 후보, 추정, 확정 아님" 보충 블록 |
| | `docs/verification/ci/time_limit_monitor.py` | docstring 정정(코드 변경 없음) |
| 생성물 | `docs/verification/aspice/TRACE_MATRIX.md`, `trace_matrix.json` | 테스트 추가·문서 행 이동에 따른 재생성(CI.md 절차) |
| 조사 기록 | `run6_cause/` | S6 지문 검토(raw/S6_fingerprint_check), osqp_probe 안 B, STATIC §3-3·S5_IMPACT·README 정정, 이 문서, `commit2_compare.py`·raw/C2_compare, PLAN 변경 기록 |
| mutation | `docs/verification/mutation/RESULTS.md` | 사전 선언 변경 5번 |
| | `recheck_tl_kills.py`(신규), `overnight_run.sh`(신규) | 5번 규칙 kill 재확인 도구, 야간 실행 스크립트 |
| 저장소 설정 | `.gitattributes` | `overnight_run.sh`를 LF로 체크아웃(Git Bash 실행용) |

- **CI.md는 바꾸지 않았다**(사용자 결정: 노트북 미커밋 수정과 충돌 회피, README §6 다음 작업).
- **ci.yml도 바꾸지 않았다.**

## 2. 제어 출력이 바뀌지 않는다는 근거 [확인-파일]

- `time_limit_hit`는 `MPCResult`에 담기기만 한다. 제어 분기(해 채택, I3 하드체크, fallback)는 `status`로 갈린다(`improved/mpc.py`의 `if status in ("solved", "solved inaccurate")` / `elif status in ("maximum iterations reached", "run time limit reached")`). 이 분기는 바뀌지 않았다.
- `time_limit_hit`를 읽는 곳은 다음뿐이다(grep). 모두 기록·진단이다.
  - `improved/runner.py`: `time_limit_count` 집계, notable_step_log 조건·필드
  - `anomaly/closed_loop.py:88`: 진단 집계
  - `docs/verification/ci/time_limit_monitor.py`
- 설정 읽기(`self.prob.settings`)는 setup 이후 값을 읽기만 한다.

## 3. 소규모 동적 비교 [확인-실행] (`commit2_compare.py` → `raw/C2_compare/`)

- old = 커밋 1(30a3a22) git archive, new = 작업 트리 복사본. 둘 다 저장소 밖 임시 폴더, 제품 설정(time_limit 0.045) 그대로.
- 비교에서 뺀 것: 바뀐 기록 필드(`time_limit_hit`, `time_limit_count`, `time_limit_rejected_count`, `notable_step_log`, `mpc_time_limit_hits`)와 계산 시간(`mpc_solve_times_ms`, `mpc_max_solve_ms`, 행의 `t_*_ms`). 나머지 EpisodeResult/ClosedLoopResult 전 필드와 스텝 로그 전 행을 비교했다.

| 대상 | 에피소드 | 결과 |
|---|---|---|
| eval 2회차 방식 v2 paper seed 200~209(인스턴스 공유, `run_eval_v2.run_paper`와 같음) | 10 | 전부 동일 |
| I5 on(COMBO_V2) paper seed 0~2(에피소드마다 새 인스턴스) | 3 | 전부 동일 |
| anomaly 폐루프 P0(V2_MPC_FLAGS, 탐지기 A) seed 3200·3201·3207 | 3 | 전부 동일 |

- 두 실행 모두 절단(time_limit_hit)은 0회였다.
- 저장 평가 수준의 확인(anomaly `closed_loop --check`, 약 95분)은 야간 실행 3단계(마지막)에서 한다(`docs/verification/mutation/overnight_run.sh`).

## 4. 평가 동결과의 관계

- 사용자 결정: 선택지 5는 **출력 불변 로깅 변경**이다(새 eval 반복 아님).
- 근거는 위 §2(정적)와 §3(동적)이고, 야간 `--check`로 보강한다.
- 저장된 eval 결과의 `time_limit_count`·`time_limit_hits` 0건은 새 정의에서도 0건이다. 근거는 모든 solve가 45 ms 미만이라 절단이 불가능했다는 점이다(첫 solve 제외, S5_IMPACT §1). 저장 결과 파일은 고치지 않았다.

## 5. 재확인 결과 [확인-실행]

(아래 표는 모든 수정 후 최종 실행 값. 시각은 각 행에 적는다.)

| 항목 | 명령 | 결과 |
|---|---|---|
| 전체 테스트 | `PYTHONPATH=docs/verification/ci python -m pytest thesis_v2/tests thesis_v2/anomaly/tests -q -rfEs -p time_limit_monitor -p no:cacheprovider` | **359 passed**(15.45 s, 15:32). 커밋 1 기준 340 + 새 테스트 19. time_limit_monitor: improved solve 14,044회, 기본 설정 발동 0회, 의도적(설정 변경) 발동 4회 |
| golden | `python -m thesis_v2.tests.check_golden` | **PASS 6/6** |
| 추적 매트릭스 | `python docs/verification/aspice/make_trace_matrix.py --check` | **일치**. 처음 실행은 불일치였다(새 테스트 6개, 문서 행 이동으로 인용 행 번호 변경). CI.md 절차대로 재생성하고 diff를 확인한 뒤 일치했다 |
| UML 대조 | `python docs/verification/aspice/check_uml.py` | **일치** |
| 안전 수치표 | `python docs/verification/safety/make_safety_tables.py --check` | **일치** |
| 소규모 동적 비교 | `python docs/verification/ci/run6_cause/commit2_compare.py --out docs/verification/ci/run6_cause/raw/C2_compare` | **16/16 에피소드 동일**(ALL EQUAL, 15:32 재실행) |
| S6 지문 검토 | `python docs/verification/ci/run6_cause/raw/S6_fingerprint_check/check_fingerprint.py` | 실측 31/31 일치, 안 B 추가분 0, 제품·도구 불일치 0 |

## 6. 야간 실행 스크립트 dry-run [확인-실행] (1차 2026-10-14 15:28~15:32, 커밋·푸시 없음, 출력은 저장소 밖)

> 이 절의 표는 **순서 변경 전** 1차 dry-run(--check → mutation → 재확인)이다. 사용자 지시로 순서를 바꿨다.
> 바뀐 순서는 mutation → 재확인 → --check이고, 이유는 --check가 git 추적 파일 `_check_diag_timing.csv`를 덮어써 mutation 원자료의 git.dirty가 참이 되는 것을 피하기 위해서다.
> 바꾼 뒤의 2차 dry-run 결과는 §7에 있다.

`bash docs/verification/mutation/overnight_run.sh --dry-run`. 시작 전 확인은 커밋 전이라 실패했고(작업 트리 변경, HEAD = origin/main은 일치), dry-run이라 계속 진행했다.

| 단계 | dry-run 내용 | 종료 코드 | 시간 |
|---|---|---|---|
| 1 closed_loop --check | 저장 평가 폴더를 저장소 밖으로 복사, `--check-only P0` | 0 (episodes_P0.csv·summary[P0] 일치, time_limit_hit 0, 최대 solve 9.0 ms) | 49 s |
| 2 mutation | fsm 변이 3개(clean run 포함) | 0 (killed_exception 1, survived 1, killed 1) | 66 s |
| 3a kill 재확인 | 위 결과(kill 2개) | 0 (대상 0: 첫 실패 테스트가 time_limit 켠 I5 MPC를 쓰지 않음) | 4 s |
| 3b kill 재확인 | 1차 결과 run_before.json, 대상 1개·1회 | 0 (kill 469개 중 대상 114개 판정, detector_a:001 orig·A 실패·대조 통과 → kill 유지) | 47 s |

- PC 상태 기록(before/after)도 남았다. 부하 14~19%, 전원 "균형 조정", AC 절전·최대 절전 "안 함"(0).
  다만 **Windows Update 재부팅 대기 키가 둘 다 True**였고, 활성 시간은 08~19시였다(야간 자동 재시작 가능성, 보고서 참조).
- 저장소 작업 트리는 dry-run 전후로 같았다(저장 평가 폴더를 복사해 썼음).
- 3b의 대상 114개는 1차 결과에 지금 테스트 스위트를 적용한 값이다. 정식 실행에서는 run_after.json 기준으로 다시 판정한다. 재확인 시간은 대상 수 × 10회 실행에 비례한다.

## 7. 순서 변경 후 dry-run [확인-실행] (2차, 2026-10-14 15:48~15:51, 커밋·푸시 없음, 출력은 저장소 밖)

| 단계 | dry-run 내용 | 종료 코드 | 결과 |
|---|---|---|---|
| 1 mutation | fsm 변이 3개(clean run 포함) | 0 | killed_exception / survived / killed (66 s) |
| 2a kill 재확인 | 위 결과(kill 2개) | 0 | 대상 0 (4 s) |
| 2b kill 재확인 | run_before.json, 대상 1개·1회 | 0 | detector_a:001 kill 유지 (47 s) |
| 3 closed_loop --check | 저장 평가 폴더 사본, `--check-only P0` | 0 | episodes_P0.csv·summary[P0] 일치, time_limit_hit 0 (49 s) |

- dry-run 전후로 저장소의 `thesis_v2/results`에는 변경이 없었다.
- `_check_diag_timing.csv`(저장 평가 폴더)는 **git 추적 파일이다**(`git ls-files`로 확인). 정식 실행에서 --check가 이 파일을 덮어쓰면 야간 커밋 대상에 그대로 들어간다(스크립트의 허용 경로 `<평가 폴더>/_check_*`).
  불일치일 때 생기는 `_check_episodes_*.csv`·`_check_summary.json`은 추적되지 않지만 무시 대상도 아니라서, 같은 규칙으로 커밋된다.
- 같은 시각에 테스트 수 문구(루트 README, docs/verification/README, aspice/README)를 340에서 359로 맞춘 뒤 세 대조를 다시 실행했다. 추적 매트릭스·UML·안전 수치표 모두 일치했다(15:48).

## 8. 저장 평가 수준 확인 — anomaly `closed_loop --check` [확인-실행] (야간 실행 3단계, 2026-10-14 17:15–18:18, 결과 커밋 3187e40)

- 명령: `python -m thesis_v2.anomaly.closed_loop --check thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval`(커밋 6971d64, 3층PC109)
- 결과: `episodes_P0·P1_A·P1_B1·P1_B2·P1_HYBRID·P2_A.csv`, `summary.json` **전체 일치**, 종료 코드 0. 로그: `docs/verification/mutation/raw/overnight/20261014_160442/3_closed_loop_check.out`
- 진단(새 지문 판정): time_limit 발동 **0**(6,600 에피소드), 최대 solve 3.019 ms. `_check_diag_timing.csv`는 덮어써져 커밋됐다(이전 값은 git 이력 `741478e`).
- 소요 62분 54초. 같은 PC에서 같은 폴더를 확인한 2026-10-12 `--check`(60분 23초, anomaly DESIGN §28)와 비슷하다.
  95분 근처의 기록은 2026-10-03 노트북에서 다른 폴더(dev)를 확인한 것이다(94분 47초, DESIGN §24-1).
- 결론: 선택지 5(time_limit_hit 지문 판정)는 저장된 anomaly 폐루프 평가 결과를 바꾸지 않는다. 앞의 §2(정적)와 §3(동적 16 에피소드)에 이어 저장 평가 수준에서도 확인했다.
