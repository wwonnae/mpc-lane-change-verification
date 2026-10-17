# 논문 PDF vs 코드 — 전 항목 대조 (1단계, 프롬프트 4번)

> **경로 안내**: 이 문서는 원본 파일 재정리(2026-09-25) 이전 경로로 작성되었고, 공개 저장소에서는 제출 당시 원본을 모두 `legacy_2025/` 아래로 옮겼다. 경로 표기는 새 위치로 갱신했다. 옛 이름 `code_backup/final_hierarchical_backup.py`(A, 12-04 논문 데이터 생성본)는 `legacy_2025/final_hierarchical_backup_thesis_1204.py`, 옛 루트 `final_hierarchical_backup.py`(B, 제출 이후 수정본)는 `legacy_2025/final_hierarchical_backup_modified_2026.py`, 옛 `code_backup/analyze_mpc.py`는 `legacy_2025/analyze_mpc.py`이고, 논문에 쓰이지 않은 스크립트 7개는 `legacy_2025/backup/`에 있다. 본문에 남은 `final_hierarchical_backup.py`는 당시 모듈·파일 이름을 가리키는 역사적 표기다. 파일 내용은 바뀌지 않아 행 번호는 그대로 유효하다. 기록: `repro/docs/REORG_PLAN.md`. 재구현 직전에 만든 첫 점검 기록 `legacy_2025/verify/`(와 `verify.zip`)는 공개본에 포함하지 않았다. 같은 사실은 `repro/docs/STAGE1_FACTS.md`·`THESIS_TIME_CODE.md`에 정리돼 있다.

원본은 전혀 수정·삭제·이동하지 않았습니다. "A(실험 당시 코드)" = `legacy_2025/run_simulation.py` +
`legacy_2025/final_hierarchical_backup_thesis_1204.py`(2025-12-04 04:17, 97,747B, cooldown_ok/EVADE_L 예외
없음 — `THESIS_TIME_CODE.md` 7·8절에서 확인됨). "B(루트 현재 코드)" = 루트 `legacy_2025/final_hierarchical_backup_modified_2026.py`(100,254B, 논문 제출 이후 수정본). "C(legacy_2025/backup/test_teacher_mpc.py)" =
사후(2026, 논문 이후) 물리 검증 스크립트, B를 import.

트랙: **[재현]** = A/run_simulation.py 계열(논문 수치의 실제 출처로 추정), **[검증]** = C/verify
계열(2026년 사후 작성), **[본체]** = A·B·C가 공유하는 컨트롤러 상수(트랙 구분 의미 없음).

| 항목 | PDF 서술(페이지) | A(실험 당시 코드) | B(루트 현재 코드) | C(legacy_2025/backup/test_teacher_mpc.py) | 트랙 | 일치 여부 |
|---|---|---|---|---|---|---|
| N (예측horizon) | 15 (p.9 Table 3) | 15 | 15 | 15 (import) | 본체 | **일치** |
| dt | 0.05 (p.6,9) | 0.05 | 0.05 | 0.05(명시, 31행) | 본체 | **일치** |
| q_y | 100.0 (p.9) | 100 | 100 | 100(주석, 174행) | 본체 | **일치** |
| q_ψ | 25.0 (p.9) | 25 | 25 | 25(주석) | 본체 | **일치** |
| r_δ | 2.0 (p.9) | 2 | 2 | 2(주석) | 본체 | **일치** |
| r_Δδ | 5.0 (p.9) | 5 | 5 | 5(주석) | 본체 | **일치** |
| δ 제약 | ±25° (p.6,9) | ±25° | ±25° | ±25°(vp 생성자 27행) | 본체 | **일치** |
| 조향 속도 제약 | 200 deg/s (p.6,8) | 200 | 200 | 200(vp 생성자) | 본체 | **일치** |
| G_TRIG | 1.2m (p.8) | 1.2(`legacy_2025/run_simulation.py` args_dict) | 1.2(기본값) | 1.2(명시, 32행) | 본체 | **일치** |
| G_SAFE_MIN | 0.20m (p.8) | 0.20(args_dict) | 0.20(기본값) | 0.20(명시, 33행) | 본체 | **일치** |
| COOLDOWN 상수값 | 0.3초 (p.8) | 0.3(정의됨) | 0.3(정의됨) | 0.3(명시, 35행) | 본체 | **일치**(상수값만) |
| **COOLDOWN 실제 적용 여부** | "(3) 상태 전이 쿨다운은 연속적인 상태 전이를 방지" — 적용된다고 서술 | **미적용**(조건문에서 안 씀, `THESIS_TIME_CODE.md` 7절 실측+8절 `.pyc` 확인) | **적용됨**(EVADE_L진입·EVADE_L→KEEP_L1·RETURN→KEEP_L2 3곳에 `cooldown_ok` 게이트) | **적용됨**(SimpleFSM 3곳 모두 `cooldown_ok` 게이트, 57·67·71·80행) | [재현]=불일치, [검증]=일치 | **A만 불일치** |
| W(차선 폭) | 0.30m (p.6) | 0.30 | 0.30 | 0.30(rp 생성자) | 본체 | **일치** |
| 차량 L, B | 0.20m/0.15m (p.6) | 0.20/0.15 | 0.20/0.15 | 0.20/0.15 | 본체 | **일치** |
| KEEP_L2→EVADE_L 조건 | front_gap<1.2 AND left_clear=True (Table 2) | `legacy_2025/final_hierarchical_backup_thesis_1204.py:1820-1824`: `if front_gap is not None and front_gap < self.bp.G_TRIG:` → `if left_clear: self.set_state(State.EVADE_L)` | `final_hierarchical_backup.py:1822-1825`: 위와 동일하나 `if cooldown_ok and front_gap is not None and front_gap < self.bp.G_TRIG:` | `legacy_2025/backup/test_teacher_mpc.py:67`: `if front_gap is not None and front_gap < self.bp.G_TRIG and left_clear and cooldown_ok:` | 본체/[검증]확장 | **A=PDF 일치(쿨다운 없음), B·C는 `cooldown_ok` 추가로 조건 확장(더 늦게 전이)** |
| **모든 상태→SAFE_STOP 조건** | "모든 상태" 예외 없이 front_gap<0.20 AND left_clear=False (Table 2). **p.10 원문(이미지 재확인, 앞뒤 문장 포함)**: "G_SAFE_MIN = 0.20m는 비상 정지 거리이다. **회피 기동 중** 장애물과의 거리가 이 값 이하로 감소하면, 즉시 SAFE_STOP 상태로 전이하여 차량을 정지한다." (바로 앞 문장은 G_TRIG=1.2m 정의) | `legacy_2025/final_hierarchical_backup_thesis_1204.py:1807-1809`: `if (front_gap is not None and front_gap < self.bp.G_SAFE_MIN and not left_clear):` — 상태와 무관하게 매 사이클 최상단에서 체크(진짜 "모든 상태") | `final_hierarchical_backup.py:1807-1810`: 위 조건에 `and self.state.value != State.EVADE_L.value` **추가** | `legacy_2025/backup/test_teacher_mpc.py:59-62`: `if (front_gap is not None and front_gap < self.bp.G_SAFE_MIN and not left_clear and self.state != State.EVADE_L):` — 주석 "EVADE_L 중에는 발동 안 함(final_hierarchical_backup.py와 동일 로직)" | [재현]=일치, [검증]=불일치 | **B·C만 불일치(A는 PDF의 두 서술 모두와 정확히 일치). Table 2와 p.10 문장은 서로 비모순 — 판단 근거는 아래 "p.10 판단" 참고** |
| EVADE_L→KEEP_L1 조건 | \|y−0.30\|≤0.08m (Table 2). IR 분기에 대한 언급은 PDF에 없음 | **재검토 완료(코드 3단계 추적)**: `legacy_2025/final_hierarchical_backup_thesis_1204.py:1832-1839`엔 두 분기(`ey_line` 기반 \|ey_line\|<0.04 / `pose.y` 기반 \|y-0.30\|<0.08)가 있으나, **`ey_line`은 이 파이프라인에서 항상 `None`**임을 확인함. 근거: ①`legacy_2025/run_simulation.py:113`이 `app.lines.last_ey = ...`를 대입하지만 `LineTraceSensor`(`final_hierarchical_backup.py:661-674`) 클래스엔 `last_ey`라는 속성/용도가 없음(죽은 대입, `get_ey()`는 `self.sig_ey.v`만 읽음). ②`self.lines.update()`가 실제로 호출되는 곳은 `final_hierarchical_backup.py:1755,1773`뿐인데, 이 블록은 `if self._test_time is None:`(1753행, "실제 주행 모드") 안에 있고, `legacy_2025/run_simulation.py`는 매 스텝 `app._test_time = step_time`(52행 부근)을 설정하므로 **이 블록 자체가 실행되지 않음**(else 분기 "테스트 모드: inject_sensors()에서 이미 설정됨"으로 감, `legacy_2025/run_simulation.py`는 그 `inject_sensors()`도 호출 안 함). ③따라서 `self.sig_ey.ts`가 초기값 0.0에서 갱신된 적이 없어 `is_valid()`(625-633행)가 항상 False → `get_ey()`가 항상 `None` 반환(확인됨). **결론: A는 항상 ELSE(pose 기반) 분기 `\|y-0.30\|<0.08`만 실행 — PDF와 정확히 일치.** 100/100 에피소드가 정확히 4스텝(0.2s) 만에 전이하는 이유도 이제 완전히 결정론적으로 설명됨: KEEP_L1 스크립트 구간(`legacy_2025/run_simulation.py:47-53`)이 `y`를 U(0.25,0.35)로 직접 주입하는 순간, `\|주입값-0.30\|`은 항상 ≤0.05<0.08이라 그 스텝에서 즉시 조건이 참이 됨(추가 판정불가 사항 없음) | `final_hierarchical_backup.py:1832-1840`: A와 동일(ELSE 분기만 실행) + `cooldown_ok` 추가 | `legacy_2025/backup/test_teacher_mpc.py:70-72`: 분기 없이 `abs(y - self.rp.W) < self.bp.NEAR_BAND_L1 and cooldown_ok`만 사용(=A의 실사용 조건과 형태 동일) | 본체/확장 | **정정: A=PDF 완전 일치(쿨다운 없음). B·C는 동일 조건 + 쿨다운 추가만 다름** |
| KEEP_L1→RETURN_TO_L2 조건 | t>0.6s (Table 2) | `legacy_2025/final_hierarchical_backup_thesis_1204.py:1842-1844`: `elapsed = t0 - self.last_state_change; if elapsed > self.bp.T_KEEP_L1_MIN:` | `final_hierarchical_backup.py:1844-1846`: 동일(쿨다운 미추가 — 자체 조건이 이미 0.6s>0.3s) | `legacy_2025/backup/test_teacher_mpc.py:74-77`: `elapsed = (self.step - self.last_state_change_step)*self.dt; if elapsed > self.bp.T_KEEP_L1_MIN:` | 본체 | **일치**(A=B=C=PDF, 유일하게 3버전+PDF가 전부 완전히 같은 항목) |
| RETURN_TO_L2→KEEP_L2 조건 | \|y\|≤0.20m **AND** \|ψ\|≤20° (Table 2) | `legacy_2025/final_hierarchical_backup_thesis_1204.py:1852-1861`: `if ey_line is not None: ...(IF분기)... else: pose_err_l2 = self.pose.y; arrived_l2 = abs(pose_err_l2) < NEAR_BAND_L1`(**\|y\|<0.08**). 위 행에서 확인했듯 `ey_line`이 이 파이프라인에서 항상 `None`이므로 **IF분기는 절대 실행되지 않고 ELSE(\|y\|<0.08)만 실행됨**(확인됨, 근거 동일). PDF의 0.20이 아니라 0.08(NEAR_BAND_L1 재사용)이고, **헤딩각(ψ) 조건은 파일 전체에 존재하지 않음**(`grep "psi.*20\|heading_ok"` 0건, 확인됨) | `final_hierarchical_backup.py:1852-1864`: A와 동일(ELSE만 실행) + `cooldown_ok` | `legacy_2025/backup/test_teacher_mpc.py:79-81`: `abs(y) < self.bp.NEAR_BAND_L1 and cooldown_ok`(0.08 기준, 헤딩 조건 없음) | [재현]=불일치, [검증]=불일치 | **A·B·C 전부 불일치** — 임계값(0.08 vs 0.20)과 헤딩각 조건 누락이 세 버전 모두 동일(쿨다운 유무와는 별개 사안) |
| SAFE_STOP 속도 처리 | "목표 속도를 0으로 설정하며, 가능한 한 빠르게 감속한다" (p.8) | `final_hierarchical_backup.py:2001`(code_backup 기준 동일 위치): `v_cmd = 0.0` **즉시**, `A_MIN=-3.0`(93행) 정의되어 있으나 감속 램프 계산에 미사용(전체 파일 `grep A_MIN` 결과 정의·인자전달 2곳뿐, 확인됨) | 좌동(이 블록은 diff에 없음, A와 동일) | 해당 없음(`legacy_2025/backup/test_teacher_mpc.py`는 SAFE_STOP 감지 시 즉시 `return False, step, "SAFE_STOP", ...`로 종료, 속도값 자체를 다루지 않음) | 본체 | **부분 일치** — "0으로 설정"은 맞음. "가능한 한 빠르게"를 `A_MIN` 기반 램프로 해석하면 불일치(즉시 스텝점프이지 램프가 아님), "즉시 0"으로 해석하면 일치 — **해석에 따라 갈림, 코드 사실 자체는 확인됨** |
| 장애물 위치/거리 범위 | "장애물의 위치는 0.5m~2.0m 균등분포" (p.6,11) | **주입 front_gap**이 2.0→0.65m로 10 step 선형감소(물리 위치 변수 없음), `legacy_2025/run_simulation.py:37` | (B는 A와 동일 파일 재사용 대상이 아님 — 이 로직은 legacy_2025/run_simulation.py에 있음, 컨트롤러 자체엔 없음) | 물리 obstacle_x = U(**1.2, 2.0**)m(101행), 단 177행 print은 "U(2.5,4.0)"이라고 표시(자기모순) | [재현]=구조적 불일치, [검증]=범위도 다름 | **셋 다 불일치**(메커니즘 또는 수치가 다름) |
| 초기 속도 | "0.3m/s~0.5m/s 균등분포" (p.6,11) | **U(0.4, 0.6)** 주입(`legacy_2025/run_simulation.py:27` 등). **Teacher 모드에선 이 값이 v_cmd에 반영되지 않음(정정: 인용 라인 수정)** — `ey_line`이 항상 `None`이므로(위 EVADE_L→KEEP_L1 행 근거) KEEP_L2도 "라인추종" 분기(1889행 부근)가 아니라 **"No line sensor - Teacher MPC (fallback)"** 분기(`legacy_2025/final_hierarchical_backup_thesis_1204.py:1904-1913`)가 실행되고, 거기서 `v_cmd = v_ref`(1913행) = `self.vp.V_MAX`(=0.5)로 고정됨. EVADE_L도 동일 패턴(`v_cmd = v_ref`, 1937행). PDF p.10 "KEEP_L2·EVADE_L·KEEP_L1·RETURN_TO_L2 상태에서는 v_ref를 유지한다"는 서술과는 오히려 **일치**. 주입된 난수는 `app.speed.v_mps`에만 들어가고 v_cmd 계산 경로엔 안 쓰임(확인됨) — `legacy_2025/results/teacher/metrics.npz`의 `v`가 전부 정확히 0.5인 이유 | 해당 없음(컨트롤러엔 초기속도 생성 로직 없음, B는 A와 이 블록이 동일) | **U(0.3, 0.5)** 주입(102행, 주석 "논문: 0.3~0.5m/s"), `SimpleFSM`은 v를 별도로 안 씀(MPC가 직접 y,ψ,v로 delta 계산) | [재현]=주입값 자체는 불일치하나 실사용 안 함, [검증]=일치 | **주입값 기준으로는 A만 불일치·C 일치. 다만 A는 애초에 이 값을 안 씀 — "불일치"보다는 "무관"에 가까움** |
| 초기 횡방향 위치(y) 분포 | "±0.05m **Gaussian**" (p.11) | **균등분포 U(-0.05,0.05)** 주입(`legacy_2025/run_simulation.py:26`). **정정**: 이전 보고서는 "컨트롤러가 ey_line으로 pose.y를 블렌딩해 재가공한다"고 썼으나, `ey_line`이 항상 `None`이므로(위 근거) 그 블렌딩 코드(`final_hierarchical_backup.py:1884-1886`, `if ey_line is not None:` 블록)는 **실행되지 않는 죽은 코드**입니다. 실제로 y는 (a) `legacy_2025/run_simulation.py`가 매 스텝 직접 주입하는 구간(KEEP_L2 초기, KEEP_L1, RETURN_TO_L2)에서는 주입값 그대로, (b) 주입이 없는 구간(EVADE_L 트리거 10step, 마지막 "정상 주행" 구간)에서는 MPC가 계산한 `delta_deg`로 커널매틱 업데이트(`Pose.update`, 656-659행)되어 진짜로 움직입니다 — 순수 주입도, 순수 물리도 아닌 **구간별 혼합**입니다 | 해당 없음 | **정규분포 N(0, 0.05²)** 주입(103행, 주석 "논문: Gaussian(0, 0.05)"), `simulator.py`엔 블렌딩 로직 없음(단순 kinematic 업데이트만) | [재현]=분포 종류 불일치 + 구간별 혼합 메커니즘, [검증]=일치 | **A만 불일치**(균등 vs 가우시안), **C가 PDF와 정확히 일치** |
| 에피소드 수 | 100개 (p.11,13,15) | 100(`--num_episodes` 기본값) | - | 100(`NUM_EPISODES`, 161행) | 본체 | **일치** |
| 최대 step / 시간 | "최대 10초(200 step at 20Hz)" (p.11) | 200(`RandomScenarioGenerator(steps_per_episode=200)`) | - | **400**(`MAX_STEPS=400`, 161행 — 논문의 2배) | [재현]=일치, [검증]=불일치 | **C만 불일치**(명시적으로 2배) |
| 종료 조건 | "안전하게 회피·복귀 완료 또는 SAFE_STOP 도달 시 종료" (p.11) | **완료 조건으로 종료하지 않음** — `run_simulation_episode()`(`legacy_2025/run_simulation.py:80-125`)는 `if app._stop_flag: break`(SAFE_STOP 전용, 0회 발생)만 있고 "FSM이 KEEP_L2로 완전복귀하면 종료"하는 코드가 없음. 사전 생성된 180~200 step 타임라인을 끝까지 실행(길이 편차는 타임라인 생성 산식 `230−obstacle_start`로 전부 설명됨, 확인됨) | - | `legacy_2025/code_backup/simulator.py:92-104`(`SimulatedEnvironment.step()`): `done=True`는 **① `step_count>=max_steps`(=400, 재정정) ② `abs(y)>MAX_Y_DEVIATION` ③ `dist_to_obs<0.1`(충돌) 셋 중 하나**로 결정됨(x위치 기준이라는 이전 표현은 부정확했음, 정정). `legacy_2025/backup/test_teacher_mpc.py:150-156`에서 SAFE_STOP 체크(133행)가 `if done:` 충돌 체크보다 **먼저 return**하므로, 같은 스텝에서 SAFE_STOP과 충돌이 동시 성립해도 SAFE_STOP만 기록됨(재확인됨) | [재현]=불일치(완료-조기종료 없음), [검증]=step수/이탈/충돌 기준일 뿐 "FSM 완료"와 무관 | **A·C 둘 다 PDF의 "완료 시 종료" 서술과 정확히는 안 맞음**(정정: C의 종료 기준은 x위치가 아니라 step수·y이탈·충돌 3종) |
| 샘플 수 집계 방식 | "100 에피소드, 총 19,129 샘플" (p.11,15) | 매 스텝 `app.metrics`에 append → 에피소드 종료 후 전부 `np.savez`(2절), **seed 미고정**이라 실행마다 총합이 달라짐(3(a)절) | - | - | [재현] | **메커니즘은 일치**(스텝별 누적), **총량은 근사치**(18,989/18,950 vs 19,129, 3(a)절에서 난수 변동으로 설명 가능 판정) |

## 요약(일치/불일치 개수) — 3차 재검증(ey_line 항상 None 확인) 후 최종

전체 22개 대조 항목 기준(A 기준 판정):

- **A=PDF 완전 일치**: 16개 — N, dt, q_y, q_ψ, r_δ, r_Δδ, δ범위, 조향속도, G_TRIG, G_SAFE_MIN,
  COOLDOWN 상수값, W, L/B(12개 본체 상수) + **모든상태→SAFE_STOP** + **EVADE_L→KEEP_L1**(정정,
  아래 참고) + KEEP_L1→RETURN_TO_L2 + 에피소드 수.
- **A=PDF 불일치**: 6개 — **RETURN_TO_L2→KEEP_L2**(임계값 0.08≠0.20, 헤딩각 조건 자체가 없음),
  쿨다운 실제 적용 여부(A는 미적용), 장애물/front_gap 범위(메커니즘 자체가 다름), 초기 y 분포
  (균등≠가우시안), 종료 조건(완료-조기종료 없음), 샘플 수 총량(근사치, 정확히는 다름).
- **해석에 따라 갈림**: 1개 — SAFE_STOP 속도 처리("즉시 0"=일치, "A_MIN 램프"=불일치).
- **B·C 전용 차이**: 쿨다운 적용으로 EVADE_L 관련 3개 전이가 더 늦게 발생, SAFE_STOP에 EVADE_L
  예외 추가(B·C만 PDF와 불일치), 최대 step C만 400(PDF의 2배), 초기속도 값 자체는 C가 PDF와
  일치(단, A 자체가 그 값을 안 쓰므로 "불일치"라기보단 "무관").

**재검증 이력(중요 — 두 번 뒤집힘)**:
1. **1차 조사**: EVADE_L→KEEP_L1·RETURN_TO_L2→KEEP_L2 둘 다 "A=PDF 일치"로 보고.
2. **2차 재검증**(y 점프 0.0225→0.3189만 근거): `ey_line`이 항상 주입된다고 잘못 판단해 두
   전이 모두 "PDF에 없는 IR 분기가 작동"으로 뒤집음 — **이 판정은 틀렸습니다.**
3. **3차 재검증(이번, 코드 3단계 추적)**: `legacy_2025/run_simulation.py:113`의 `app.lines.last_ey=...`
   대입이 `LineTraceSensor` 클래스가 실제로 읽는 `sig_ey.v`와 무관한 죽은 대입이고,
   `self.lines.update()`가 호출되는 유일한 경로(`final_hierarchical_backup.py:1755,1773`)는
   `self._test_time is None`일 때만 실행되는데 `legacy_2025/run_simulation.py`는 항상 `_test_time`을
   설정하므로 그 경로 자체가 실행되지 않습니다. 결론: **`ey_line`은 이 파이프라인에서 항상
   `None`**이고, 두 전이 모두 `ey_line`-분기가 아니라 **pose.y-기반(ELSE) 분기만 실행**됩니다.
   → **EVADE_L→KEEP_L1은 "A=PDF 일치"로 원상복구**(단 메커니즘은 완전히 다시 설명: 확률적
   센서가 아니라 스크립트 주입값 자체가 항상 임계값을 만족하는 결정론적 구조),
   **RETURN_TO_L2→KEEP_L2는 "A·B·C 전부 불일치" 유지**(임계값·헤딩각 문제는 애초에
   `ey_line` 분기와 무관한, ELSE 분기 자체의 값 차이였음).

**흥미로운 역전 유지**: 초기 속도·초기 y 분포의 "주입값" 자체는 여전히 A보다 C가 PDF와 더
가깝습니다. 다만 이번 재검증으로 **A는 초기 속도 주입값을 애초에 v_cmd 계산에 쓰지 않는다**는
사실이 추가로 확인되어(위 표 참고), "불일치"보다는 "그 값 자체가 무관"이라는 표현이 더
정확합니다.
