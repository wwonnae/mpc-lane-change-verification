# S6: time_limit 지문 규칙 검토 (2026-10-14)

- 재현: 저장소 루트에서 `python docs/verification/ci/run6_cause/raw/S6_fingerprint_check/check_fingerprint.py` → `result.json`.
- 양성 대조 원자료는 `pc_rt/`에 있다.
  - 저장소 밖 임시 사본(커밋 4c0c503)에서 `I5_TIME_LIMIT_SEC`만 0.2/0.5/1 ms로 바꿨다(`pc_rt/copies_condition/`).
  - harness.py로 i5+i4 대상을 10회차씩 돌리며 전 solve를 기록했다.
  - 이 PC, 부하 없음, 2026-10-14 15:12.
- result.json의 `episodes_time_limit_045` 키는 실측(45 ms) 자료에만 의미가 있다. 양성 대조 항목에서는 무시한다.

## 결과 [확인-실행]

| 자료 | time_limit | solve | 지문 안 A (커밋 2 전) | 안 B (A + "solved" & iter==0) | run_time ≥ limit | run_time 조건만 참 (B 대비 새로 잡힘 = 과대 집계) | B 참인데 run_time < limit |
|---|---|---|---|---|---|---|---|
| 실측 S1~S4 (전수 기록) | 45 ms | 18,987 (time_limit 있는 것) | 31 | 31 | 31 | **0** | 0 |
| 실측 S1~S4 (에피소드 최대값, orig·i5/i4) | 45 ms | 81,450 에피소드 | — | — | run_time ≥ 45 ms인데 지문 없는 에피소드 **0** | — | — |
| 양성 대조 | 0.2 ms | 10,680 | 422 | 422 | 433 | **11** | 0 |
| 양성 대조 | 0.5 ms | 10,680 | 327 | 327 | 327 | **0** | 0 |
| 양성 대조 | 1 ms | 10,680 | 330 | 330 | 331 | **1** | 0 |

- **run_time 조건만 참인 12건:** 모두 반복 수가 25의 배수(25, 50, 375)인 "solved"였고, run_time이 제한을 0.2~1.1% 넘었다.
  - OSQP 소스상 정상 종료다. 시간 검사(`osqp_api.c:741-757`)를 통과한 뒤 수렴 검사·마무리(`:860-865`, `:975`) 시간이 더해져 제한을 넘은 경우다.
  - 그래서 과대 집계로 분류했다.
- **안 B가 A에 더한 조건("solved" & iter==0):** 실측과 양성 대조 모두에서 0건이었다. 커밋 2 이전 기록(S1~S4)의 판정은 바뀌지 않는다.
- **도구 일치:** 제품 함수 `improved.mpc.time_limit_fingerprint`와 조사 도구 `osqp_probe.tl_fingerprint`(둘 다 안 B)는 모든 기록 solve에서 판정이 같았다(불일치 0).
- **사용자 결정(2026-10-14):** 안 B를 채택했고, run_time 조건(안 C)은 넣지 않았다.
