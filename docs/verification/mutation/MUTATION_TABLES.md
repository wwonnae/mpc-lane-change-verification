# Mutation 표 (자동 생성)

> `make_mutation_tables.py`가 원자료에서 만든다. 손으로 고치지 않는다. CI는 `--check`로 바이트 비교한다.
> 점수 규칙은 PREREGISTRATION.md §5: 원점수 = 잡힘 / (전체 − 무효), 등가 제외 점수 = 잡힘 / (전체 − 무효 − 등가(판단)).
> 잡힘 = killed + killed_exception + timeout. 등가(판단)는 1차 생존 변이 분류(equivalence.json, 확정)를 두 실행 모두에 쓴다.

## 1. 실행 조건

| 실행 | 커밋 | git dirty | 시각 | Python | CPU % 전/후 | 깨끗한 사본 L1 s (모듈별) | L2 s | L3 s | 타임아웃 s (L1 fsm/detector_a/closed_loop/baseline_mpc) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1차(보강 전) | 78e0936 | false | 2026-10-13T11:32:48 ~ 2026-10-13T12:20:11 | 3.9.13 | 14 / 6 | fsm 0.41, detector_a 2.06, closed_loop 1.65, baseline_mpc 0.69 | 15.25 | 0.5 | L1 10.0/10.3/10.0/10.0, L2 76.25, L3 10.0 |
| 2차(보강 후) | 6971d64 | true | 2026-10-14T16:04:57 ~ 2026-10-14T16:51:09 | 3.9.13 | 6 / 1 | fsm 0.78, detector_a 3.38, closed_loop 1.53, baseline_mpc 0.77 | 22.66 | 0.53 | L1 10.0/16.9/10.0/10.0, L2 113.3, L3 10.0 |

## 2. 점수(모듈별)

| 실행 | 모듈 | 전체 | 무효 | 잡힘 | killed | killed_exception | timeout | 원점수 | 등가(판단) | 등가 제외 점수 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1차(보강 전) | fsm | 52 | 0 | 45 | 37 | 8 | 0 | 86.5% | 3 | 91.8% (45/49) |
| 1차(보강 전) | detector_a | 197 | 0 | 146 | 93 | 53 | 0 | 74.1% | 18 | 81.6% (146/179) |
| 1차(보강 전) | closed_loop | 63 | 0 | 32 | 22 | 10 | 0 | 50.8% | 4 | 54.2% (32/59) |
| 1차(보강 전) | baseline_mpc | 288 | 0 | 248 | 99 | 149 | 0 | 86.1% | 8 | 88.6% (248/280) |
| 1차(보강 전) | 합계 | 600 | 0 | 471 | 251 | 220 | 0 | 78.5% | 33 | 83.1% (471/567) |
| 2차(보강 후) | fsm | 52 | 0 | 49 | 41 | 8 | 0 | 94.2% | 3 | 100.0% (49/49) |
| 2차(보강 후) | detector_a | 197 | 0 | 168 | 113 | 55 | 0 | 85.3% | 18 | 93.9% (168/179) |
| 2차(보강 후) | closed_loop | 63 | 0 | 57 | 41 | 16 | 0 | 90.5% | 4 | 96.6% (57/59) |
| 2차(보강 후) | baseline_mpc | 288 | 0 | 257 | 108 | 149 | 0 | 89.2% | 8 | 91.8% (257/280) |
| 2차(보강 후) | 합계 | 600 | 0 | 531 | 303 | 228 | 0 | 88.5% | 33 | 93.7% (531/567) |

## 3. 처음 잡힌 층

| 실행 | 모듈 | L1 | L2 | L3 |
|---|---:|---:|---:|---:|
| 1차(보강 전) | fsm | 41 | 4 | 0 |
| 1차(보강 전) | detector_a | 146 | 0 | 0 |
| 1차(보강 전) | closed_loop | 32 | 0 | 0 |
| 1차(보강 전) | baseline_mpc | 201 | 45 | 2 |
| 2차(보강 후) | fsm | 41 | 8 | 0 |
| 2차(보강 후) | detector_a | 146 | 22 | 0 |
| 2차(보강 후) | closed_loop | 32 | 25 | 0 |
| 2차(보강 후) | baseline_mpc | 201 | 56 | 0 |

## 4. 1차 → 2차 변화

- 두 실행의 변이 정의(ID·행·원본·치환) 동일: 예 (600개)
- survived → killed: 52
- survived → killed_exception: 8
- 1차에서 잡혔는데 2차에서 잡히지 않은 변이: 0
- 보강 대상(equivalence.json `reinforce`) 60개 중 2차에서 잡힘: 60
- 2차에서 새로 잡힌 변이: 60 (그중 보강 대상 60)
- 두 실행 모두 잡혔고 처음 잡힌 층이 바뀐 변이 L3 → L2: 2 (baseline_mpc:219, baseline_mpc:220)

## 5. 생존 변이 분류 (equivalence.json 기준)

| 실행 | 모듈 | 생존 | 등가(판단) | 경계 동치 미검증(저위험) | 도달 불가 입력에서만 차이 | 보류(외부 라이브러리) | 테스트 공백 | MPC 측정: 허용오차 내, max\|diff\|=0 | MPC 측정: 허용오차 내, max\|diff\|>0 | 분류 없음 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1차(보강 전) | fsm | 7 | 3 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| 1차(보강 전) | detector_a | 51 | 18 | 9 | 2 | 0 | 22 | 0 | 0 | 0 |
| 1차(보강 전) | closed_loop | 31 | 4 | 0 | 2 | 0 | 25 | 0 | 0 | 0 |
| 1차(보강 전) | baseline_mpc | 40 | 8 | 0 | 0 | 2 | 1 | 25 | 4 | 0 |
| 2차(보강 후) | fsm | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2차(보강 후) | detector_a | 29 | 18 | 9 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2차(보강 후) | closed_loop | 6 | 4 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2차(보강 후) | baseline_mpc | 31 | 8 | 0 | 0 | 2 | 1 | 20 | 0 | 0 |

- 2차 생존 변이 목록:
  - `fsm:002` L35 const: 등가(판단)
  - `fsm:030` L59 rel: 등가(판단)
  - `fsm:049` L70 rel: 등가(판단)
  - `detector_a:004` L87 rel: 경계 동치 미검증(저위험)
  - `detector_a:007` L87 rel: 경계 동치 미검증(저위험)
  - `detector_a:009` L91 rel: 경계 동치 미검증(저위험)
  - `detector_a:044` L124 rel: 경계 동치 미검증(저위험)
  - `detector_a:046` L125 rel: 경계 동치 미검증(저위험)
  - `detector_a:065` L141 rel: 경계 동치 미검증(저위험)
  - `detector_a:069` L141 rel: 경계 동치 미검증(저위험)
  - `detector_a:072` L143 operand_drop: 등가(판단)
  - `detector_a:073` L143 rel: 등가(판단)
  - `detector_a:074` L143 arith: 등가(판단)
  - `detector_a:075` L143 operand_drop: 등가(판단)
  - `detector_a:076` L143 bool: 등가(판단)
  - `detector_a:077` L143 rel: 등가(판단)
  - `detector_a:078` L143 arith: 등가(판단)
  - `detector_a:079` L144 assign_del: 등가(판단)
  - `detector_a:080` L145 return_none: 등가(판단)
  - `detector_a:092` L155 rel: 경계 동치 미검증(저위험)
  - `detector_a:097` L155 rel: 경계 동치 미검증(저위험)
  - `detector_a:100` L157 rel: 등가(판단)
  - `detector_a:101` L157 arith: 등가(판단)
  - `detector_a:102` L158 assign_del: 등가(판단)
  - `detector_a:103` L159 return_none: 등가(판단)
  - `detector_a:128` L174 const: 등가(판단)
  - `detector_a:129` L174 const: 등가(판단)
  - `detector_a:130` L174 const: 등가(판단)
  - `detector_a:140` L180 operand_drop: 도달 불가 입력에서만 차이
  - `detector_a:143` L180 operand_drop: 도달 불가 입력에서만 차이
  - `detector_a:190` L207 rel: 등가(판단)
  - `detector_a:191` L207 const: 등가(판단)
  - `closed_loop:001` L170 assign_del: 등가(판단)
  - `closed_loop:011` L178 operand_drop: 등가(판단)
  - `closed_loop:029` L198 const: 등가(판단)
  - `closed_loop:034` L203 assign_del: 등가(판단)
  - `closed_loop:055` L355 operand_drop: 도달 불가 입력에서만 차이
  - `closed_loop:058` L355 operand_drop: 도달 불가 입력에서만 차이
  - `baseline_mpc:038` L75 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:084` L117 assign_del: 등가(판단)
  - `baseline_mpc:086` L118 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:087` L119 arith: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:088` L119 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:103` L129 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:104` L130 arith: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:105` L130 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:115` L135 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:116` L136 arith: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:117` L136 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:142` L159 assign_del: 등가(판단)
  - `baseline_mpc:144` L164 assign_del: 등가(판단)
  - `baseline_mpc:145` L165 assign_del: 등가(판단)
  - `baseline_mpc:147` L167 assign_del: 등가(판단)
  - `baseline_mpc:155` L178 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:175` L186 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:194` L196 assign_del: 보류(외부 라이브러리)
  - `baseline_mpc:195` L196 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:196` L197 assign_del: 보류(외부 라이브러리)
  - `baseline_mpc:197` L197 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:199` L198 arith: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:200` L198 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:205` L200 assign_del: 등가(판단)
  - `baseline_mpc:209` L208 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:212` L213 assign_del: 등가(판단)
  - `baseline_mpc:213` L213 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:275` L258 assign_del: 등가(판단)
  - `baseline_mpc:276` L258 arith: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:277` L258 const: MPC 측정: 허용오차 내, max|diff|=0
  - `baseline_mpc:283` L261 assign_del: 테스트 공백

## 6. 커버리지 대조 (깨끗한 사본에서 L2+L3 범위로 실행된 줄)

| 실행 | 모듈 | 생존 | 실행된 줄에서 생존 | 실행되지 않은 줄에서 생존 | 실행되지 않은 줄의 생존 변이 |
|---|---:|---:|---:|---:|---:|
| 1차(보강 전) | fsm | 7 | 7 | 0 | — |
| 1차(보강 전) | detector_a | 51 | 47 | 4 | detector_a:102, detector_a:114, detector_a:115, detector_a:116 |
| 1차(보강 전) | closed_loop | 31 | 18 | 13 | closed_loop:035, closed_loop:039, closed_loop:052, closed_loop:053, closed_loop:054, closed_loop:055, closed_loop:056, closed_loop:057, closed_loop:058, closed_loop:059, closed_loop:060, closed_loop:061, closed_loop:062 |
| 1차(보강 전) | baseline_mpc | 40 | 40 | 0 | — |
| 2차(보강 후) | fsm | 3 | 3 | 0 | — |
| 2차(보강 후) | detector_a | 29 | 29 | 0 | — |
| 2차(보강 후) | closed_loop | 6 | 6 | 0 | — |
| 2차(보강 후) | baseline_mpc | 31 | 31 | 0 | — |

## 7. time_limit kill 재확인 (RESULTS.md 사전 선언 변경 5)

- 대상 실행: `docs/verification/mutation/raw/run_after.json` (커밋 6971d64), 반복 5회, 시각 2026-10-14T16:51:09+09:00 ~ 2026-10-14T17:15:08+09:00
- kill 531개 중 대상(첫 실패 테스트가 time_limit 켠 I5 MPC 사용) 127개, 재확인 127개
- 판정: kill 유지 127
- 대상의 첫 실패 테스트 모듈: `thesis_v2.anomaly.tests.test_closed_loop` 19, `thesis_v2.anomaly.tests.test_detector_a` 95, `thesis_v2.anomaly.tests.test_mutation_gaps_closed_loop` 13
- timeout 등 first_failure 없음으로 제외: 0
- 재검토: 없음

## 원자료

- `raw/run_before.json` sha256 앞 16자리 `0c3749e1976d1bdc`
- `raw/run_after.json` sha256 앞 16자리 `97210c34866c9643`
- `equivalence.json` sha256 앞 16자리 `643b16cc6acf3a91`
- `raw/run_after_tl_recheck.json` sha256 앞 16자리 `4efec7f06394818b`
