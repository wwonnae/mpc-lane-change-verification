"""1차 생존 변이 129개의 분류(equivalence.json)를 만든다. 분류 판단은 이 파일의 표(D, OBV, NOEFF)에 사람이 적은 것이고,
스크립트는 변이 전후 코드·L3 측정값을 원자료에서 채워 넣기만 한다.

- mutate.py를 고치지 않고 그 함수(generate, mutated_text)만 호출한다.
- 기준: RESULTS.md "사전 선언 변경", 아래 criteria. 근거 종류(evidence_type)는 등가 항목마다 "코드" 또는 "실험(...)".

사용(저장소 루트): python docs/verification/mutation/build_equiv.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mutate as M  # noqa: E402

repo = M.ROOT
EQ, GAP, BND, TOL0, TOLP, HOLD, UNR = ("equivalent_judgement", "test_gap", "boundary_unverified_low_risk",
                                       "within_tolerance_measured_zero", "within_tolerance_measured_nonzero",
                                       "pending_external_library", "differs_only_on_unreachable_input")
CODE = "코드"
D = {}


def d(i, cls, reason, evidence, **kw):
    if cls == EQ:
        kw.setdefault("evidence_type", CODE)
    D[i] = dict(classification=cls, reason=reason, evidence=evidence, **kw)


NO_TEST = "테스트를 추가하지 않는다: 제품 코드가 만들지 않는 입력에서만 생기는 차이라, 이 변이를 잡는 테스트는 점수만 올리고 제품 동작의 결함을 막지 못하는 저가치 테스트다(사용자 결정 2026-10-13)."
# ---------------- fsm ----------------
d("fsm:002", EQ, "state_enter_t는 KEEP_L1 분기(63행)에서만 읽힌다. initial_fsm()의 상태는 KEEP_L2이고, 상태가 바뀌는 유일한 경로(74행)가 state_enter_t=t로 다시 만든다. 따라서 초기값 0.0/1.0은 step()이 읽기 전에 항상 덮어써진다. 저장소 전체에서 state_enter_t를 읽는 곳은 63행뿐이고 FSM을 직접 만드는 곳도 35·74행뿐이다(grep). 기록 여부: thesis_v2 제품 코드(테스트 제외)에서 FSM 객체는 `.state`와 fsm_step() 인자로만 쓰인다. logger·summary·결과 CSV에 FSM 객체나 state_enter_t를 넘기는 곳이 없다(grep `state_enter`, `\\bfsm\\b`, asdict/vars/repr — 2026-10-13 확인). CSV의 float repr(anomaly/common.py:95-101)은 개별 값에만 쓰인다.",
  ["thesis_v2/baseline/fsm.py:35", "thesis_v2/baseline/fsm.py:61-63", "thesis_v2/baseline/fsm.py:73-74"])
for i, ln, why in [("fsm:014", "51", "front_gap == G_SAFE_MIN(0.20)이고 not left_clear일 때 원본은 SAFE_STOP 아님, 변이는 SAFE_STOP"),
                   ("fsm:038", "64", "t − state_enter_t == T_KEEP_L1_MIN(0.6)일 때 원본은 전이 없음, 변이는 RETURN_TO_L2"),
                   ("fsm:045", "68", "|y| == NEAR_L2(0.08)일 때 원본은 KEEP_L2 전이, 변이는 전이 없음"),
                   ("fsm:047", "68", "|psi_deg| == PSI_L2_LIMIT_DEG(20.0)일 때 원본은 KEEP_L2 전이, 변이는 전이 없음")]:
    d(i, GAP, why + ". 경계 부등호는 SPEC REQ-FSM-02a~02e에 정해진 요구사항이고, step()에 경계값을 직접 넣을 수 있다(test_mcdc_d1이 G_TRIG 경계를 이렇게 확인함). 기존 테스트는 경계에서 떨어진 값만 쓴다(사전 선언 P2).",
      ["thesis_v2/baseline/fsm.py:" + ln])
d("fsm:030", EQ, "변이(59행 <= → <)는 abs(y − W) == NEAR_L1(0.08)일 때만 다르다. 그런데 그 값이 나오는 IEEE-754 double y가 없다. "
  "(1) y의 출처: fsm.step을 부르는 곳은 모두 vehicle.y를 넘긴다(baseline/runner.py:134, improved/runner.py:170, anomaly/runner.py:180, "
  "anomaly/closed_loop.py:219, anomaly/benchmark_detector_timing.py:138, improved/student_i4/closed_loop.py:94, improved/student_i4/benchmark_timing.py:69). "
  "vehicle.y는 vehicle.py:25(y + v·sinψ·dt)로 갱신되고 클리핑이 없으며, 초기값은 절단 정규분포(world.py:48-55) 또는 시나리오 값이다. 따라서 범위를 코드로 한정할 수 없고, "
  "아래 논증은 모든 double(±inf, NaN 포함)에 대해 한다. "
  "(2) y ∈ [0.15, 0.6]: Sterbenz 보조정리(y/2 ≤ W ≤ 2y)로 y − W는 오차 없이 계산된다. 따라서 결과가 0.08(double)과 같으려면 y = W ± 0.08이 실수로 정확히 성립해야 하는데, "
  "W(=0.3의 double) ± NEAR_L1(=0.08의 double)은 double로 표현되지 않는다(분수 계산 확인: float(W+NEAR_L1)=0.38, float(W−NEAR_L1)=0.21999999999999997, 둘 다 정확값과 다름). "
  "(3) y < 0.15이면 실제 |y − W| > 0.15, y > 0.6이면 > 0.3이다. 반올림은 단조라 계산값도 0.15·0.3 이상이고 0.08이 될 수 없다. "
  "(4) ±inf·NaN은 원본과 변이 모두 비교가 거짓이다. "
  "보조 확인: 0.38·0.22 근처 double 각 129개를 훑어 abs(y − W) == NEAR_L1인 값이 없음을 확인했다(2026-10-13). 입력 형은 Python float 또는 numpy.float64로 모두 binary64다.",
  ["thesis_v2/baseline/fsm.py:59", "thesis_v2/baseline/vehicle.py:25", "thesis_v2/baseline/world.py:48-55", "thesis_v2/baseline/config.py:19", "thesis_v2/baseline/config.py:25"],
  evidence_type="수치(부동소수점) 근거")
d("fsm:049", EQ, "70행의 if 본문은 pass이고 뒤에 else가 없다. 조건이 참이든 거짓이든 실행되는 문장이 없다. 조건식 fsm.state == FSMState.SAFE_STOP은 Enum 비교라 부작용이 없다. 이후 73-75행은 조건 결과와 무관하다.",
  ["thesis_v2/baseline/fsm.py:70-71", "thesis_v2/baseline/fsm.py:73-75"])

# ---------------- detector_a ----------------
WIN_CALLERS = ["thesis_v2/anomaly/detector_a.py:187", "thesis_v2/anomaly/detector_a.py:189"]
for i in ["detector_a:072", "detector_a:073", "detector_a:074", "detector_a:075", "detector_a:076",
          "detector_a:077", "detector_a:078", "detector_a:079", "detector_a:080"]:
    d(i, EQ, "143-145행은 any_ambiguous(→ 반환값 None 또는 False)만 바꾼다. True를 반환하는 141-142행과 루프 제어에는 영향이 없다. _window_state의 호출자는 187·189행 두 곳뿐이고 둘 다 `is True`로만 비교하므로 None과 False를 구분하지 않는다(grep: 다른 호출자 없음). 143행 식은 부작용 없는 비교·산술이다.",
      ["thesis_v2/anomaly/detector_a.py:137-145"] + WIN_CALLERS)
for i in ["detector_a:100", "detector_a:101", "detector_a:102", "detector_a:103"]:
    d(i, EQ, "157-159행은 any_ambiguous(→ 반환값 None 또는 False)만 바꾼다. True를 반환하는 155-156행과 루프 제어에는 영향이 없다. _corridor_state의 호출자는 184행 한 곳이고, 결과 corr는 185행 `corr is True`에서만 쓰인다(grep: 다른 호출자·다른 사용 없음).",
      ["thesis_v2/anomaly/detector_a.py:152-159", "thesis_v2/anomaly/detector_a.py:184-186"])
for i, f in [("detector_a:128", "x"), ("detector_a:129", "psi"), ("detector_a:130", "v")]:
    d(i, EQ, f"바뀌는 것은 VehicleState의 {f} 인자뿐이다. ir_pattern()은 state.y만 읽고(sensors.py 79행 rel = line_y − state.y가 state를 읽는 유일한 곳), ey_line()은 패턴만 받는다. VehicleState는 필드만 있는 dataclass라 생성에 부작용이 없다. 따라서 ey_exp는 obs.y만의 함수로 같다.",
      ["thesis_v2/anomaly/detector_a.py:174", "thesis_v2/baseline/sensors.py:71-91", "thesis_v2/baseline/sensors.py:93-97", "thesis_v2/baseline/vehicle.py:13-17"])
for i, why in [("detector_a:190", "m > 0.5 → m >= 0.5"), ("detector_a:191", "m > 0.5 → m > 0.0")]:
    d(i, EQ, f"{why}. m은 res[c](c ∈ s_bin 키 = trk·rc·lc·ir_miss, 108행)이고, res는 _residuals()가 만든다(198행). 이 네 채널에 대입되는 값은 1.0 또는 0.0뿐이다(178·186·188·190행). None이면 206행에서 건너뛴다. m ∈ {{0.0, 1.0}}에서 두 조건의 참거짓이 같다.",
      ["thesis_v2/anomaly/detector_a.py:204-207", "thesis_v2/anomaly/detector_a.py:108", "thesis_v2/anomaly/detector_a.py:178",
       "thesis_v2/anomaly/detector_a.py:186", "thesis_v2/anomaly/detector_a.py:188", "thesis_v2/anomaly/detector_a.py:190"])
BND_NOTE = "엄격/비엄격 부등호만 바뀐다. 차이는 비교 양쪽이 정확히 같은 값일 때만 생긴다."
for i in ("detector_a:004", "detector_a:007"):
    d(i, BND, BND_NOTE + " 레인 윈도우(±0.15, 0.15–0.45)와 시나리오 장애물 y 경계([−0.075, 0.075], [0.225, 0.375])는 맞닿지 않는다. 통로 경계는 연속값 차량 y ± B/2라 정확히 같아지기 어렵다.",
      ["thesis_v2/anomaly/detector_a.py:87", "thesis_v2/anomaly/detector_a.py:64-65", "thesis_v2/baseline/world.py:43-44", "thesis_v2/anomaly/scenarios.py:23-25"])
d("detector_a:009", BND, BND_NOTE + " front_gap(노이즈 있는 연속값, 무반사는 clip으로 정확히 10.0)이 정확히 LIDAR_MAX_RANGE − NO_RETURN_MARGIN(9.95)일 때만 다르다. NO_RETURN_MARGIN은 SPEC 요구사항이 아니라 DESIGN §13-3의 구현 상수다.",
  ["thesis_v2/anomaly/detector_a.py:91", "thesis_v2/anomaly/detector_a.py:53-54", "thesis_v2/baseline/sensors.py:110"])
d("detector_a:044", BND, BND_NOTE + " 추적 y 중심 차이가 정확히 TRACK_Y_ASSOC(0.15)일 때만 다르다. 모든 시나리오의 장애물 중심은 0과 W(0.30)뿐이라 차이는 0 또는 0.30이다.",
  ["thesis_v2/anomaly/detector_a.py:124", "thesis_v2/anomaly/scenarios.py:23-25", "thesis_v2/baseline/world.py:64-120"])
for i, ln, what in [("detector_a:046", "125", "|측정 근거리 − 추적 평균|(노이즈 있는 연속값)이 정확히 4σ_fg"),
                    ("detector_a:065", "141", "x_far(측정 평균)가 정확히 lo + BOUNDARY_MARGIN"),
                    ("detector_a:069", "141", "x_near(측정 평균)가 정확히 hi − BOUNDARY_MARGIN"),
                    ("detector_a:092", "155", "x_far가 정확히 fx + BOUNDARY_MARGIN"),
                    ("detector_a:097", "155", "x_near − fx가 정확히 9.95")]:
    d(i, BND, BND_NOTE + f" {what}일 때만 다르다. 비교 대상은 노이즈 있는 측정과 dead-reckoning에서 나온 연속값이다.",
      [f"thesis_v2/anomaly/detector_a.py:{ln}"])
gaps = {
    "detector_a:005": ("87", "a_lo > b_hi 조건이 빠져, 레인 위쪽에 있는 장애물(예: L1 장애물 [0.225, 0.375] vs L2 윈도우 상한 0.15)도 겹침으로 본다. L1 장애물이 있을 때 rc 채널이 잘못 계산된다.", None),
    "detector_a:026": ("112", "전단 x가 L·cosψ 대신 L/cosψ가 된다. ψ ≠ 0이면 값이 다르다(ψ=0.1 rad에서 약 2 mm). 추적 x와 윈도우 판정이 바뀐다.", None),
    "detector_a:029": ("117", "info is None이고 front_gap이 무반사가 아니면 info.gap_far에서 AttributeError. lidar_spike 고장은 장애물이 없을 때 front_gap만 바꾸고 obstacle_info는 None으로 둔다(faults.py:86-87, 121-123). 따라서 제품 경로에서도 생긴다.", None),
    "detector_a:031": ("117", "obstacle_info가 있는데 front_gap이 무반사(≥ 9.95)이면, 원본은 갱신하지 않고 변이는 x_near ≈ fx + 10인 측정으로 추적을 갱신·생성한다.", None),
    "detector_a:032": ("117", "or→and. info None + 정상 front_gap이면 AttributeError(lidar_spike로 도달 가능). info 있음 + 무반사이면 잘못 갱신한다.", None),
    "detector_a:048": ("126", "추적 평균 갱신이 사라져, 첫 측정값이 계속 유지된다(사전 선언 P6).", None),
    "detector_a:053": ("126", "/(n+1) → /n. n=1부터 평균 대신 최신 측정으로 대체된다.", None),
    "detector_a:060": ("135", "윈도우 하한이 rx − 0.2 대신 rx + 0.2. 차량 옆·뒤 0.4 m 구간의 장애물을 윈도우 밖으로 본다.", None),
    "detector_a:083": ("150", "통로 하한이 y − B/2 대신 y + B/2. 통로가 상단 경계 한 점이 된다.", None),
    "detector_a:087": ("150", "통로 상한이 y + B/2 대신 y + 2B.", None),
    "detector_a:093": ("155", "확실 판정 하한이 fx + 0.05 대신 fx − 0.05. 0.1 m 구간의 추적이 True로 바뀐다(정확히 같은 값 문제가 아님).", None),
    "detector_a:094": ("155", "라이다 범위 조건이 빠져, 9.95 m 너머의 추적도 통로에 '확실히' 있다고 본다. 이때 무반사이면 trk 불일치로 센다.", None),
    "detector_a:096": ("155", "x_near − fx → x_near + fx. fx(주행 거리)가 커지면 범위 판정이 달라진다.", None),
    "detector_a:098": ("155", "범위 상한이 9.95 → 10.05. 그 사이 0.1 m 구간의 추적 판정이 다르다.", None),
    "detector_a:114": ("168", "직전 front_gap이 정확히 0.0이면 원본은 fg 잔차를 마스크하고, 변이는 계산한다. 0.0은 clip(sensors.py:110)과 max(0.0, …)(sensors.py:42)로 실제로 나오는 값이다. 그래서 '사실상 안 나오는 경계'가 아니다.", None),
    "detector_a:115": ("168", "마스크 조건이 직전 front_gap > 0 → > 1.0. 1 m 이내에서 fg 잔차가 사라진다.", None),
    "detector_a:116": ("167-168", "직전 front_gap > 0 조건이 빠진다(114와 같은 입력에서 차이).", None),
    "detector_a:145": ("180", "v_{k−1} = 0이면 원본은 psi 채널을 마스크하고, 변이는 계산한다. 정지 명령(v_cmd = 0.0)으로 v = 0.0이 정확히 나온다(vehicle.py:27).", None),
    "detector_a:146": ("180", "p.v > 0 → p.v >= 0. v = 0.0은 정지 명령에서 정확히 나오는 값이라(vehicle.py:27) '사실상 안 나오는 경계'가 아니다. 145와 같은 입력에서 다르다.", None),
    "detector_a:166": ("190", "left_clear=False일 때 lc 잔차가 0.0 → 1.0. 정상 일치를 불일치로 센다.", None),
    "detector_a:172": ("197", "dead-reckoning이 v·cosψ 대신 v/cosψ. ψ ≠ 0이면 x̂가 달라진다.", None),
    "detector_a:197": ("214", "alarm이 score > h에서 score ≥ h로 바뀐다. DESIGN §13의 정의는 'score > h'(엄격)다. score가 정확히 h일 때 다르다. CUSUM 점수는 0.0이 흔하므로(max(0, …)) h = 0이면 쉽게 도달한다.", None),
}
for i, (ln, why, note) in gaps.items():
    d(i, GAP, why, [f"thesis_v2/anomaly/detector_a.py:{ln}"])
d("detector_a:140", UNR, "prev가 None인데 yaw_rate_meas가 있으면 p.v에서 AttributeError. 제품 경로에서는 prev가 None인 첫 step의 yaw_rate_meas가 항상 None이다(closed_loop.py:162-167, anomaly/runner.py:162-167, DetectorObs 계약 runner.py:46-47).",
  ["thesis_v2/anomaly/detector_a.py:180", "thesis_v2/anomaly/closed_loop.py:162-167", "thesis_v2/anomaly/runner.py:46-47", "thesis_v2/anomaly/runner.py:162-167"], no_test_reason=NO_TEST)
d("detector_a:143", UNR, "prev가 있는데 yaw_rate_meas가 None이면 None − pred_rate에서 TypeError. 제품 경로에서는 prev가 있으면(두 번째 step부터) yaw_rate_meas를 항상 계산한다(closed_loop.py:162-167).",
  ["thesis_v2/anomaly/detector_a.py:180", "thesis_v2/anomaly/closed_loop.py:162-167"], no_test_reason=NO_TEST)

# ---------------- closed_loop ----------------
d("closed_loop:001", EQ, "det_out은 172행(detector가 있을 때 대입)과, 같은 if 블록 안에서 그 뒤에 오는 176·178행에서만 읽힌다(grep: 다른 사용 없음). detector가 None이면 블록 전체를 건너뛰어 det_out을 읽지 않는다. 그래서 170행 초기화를 지워도 NameError나 값 차이가 없다.",
  ["thesis_v2/anomaly/closed_loop.py:170-178"])
d("closed_loop:011", EQ, "차이는 탐지기 B·하이브리드처럼 channel=\"\"을 반환할 때(detector_b.py:96, hybrid.py:120) first_alarm_channel이 None 대신 \"\"이 되는 것뿐이다. 이 값을 쓰는 곳은 세 곳이다. (1) P2 분기 182-193행: None과 \"\" 모두 세 OVERRIDE 집합에 없어 같은 else(정지)로 간다. (2) episode_row 360행 → CSV 쓰기: fmt()가 None을 빈 칸으로 쓰고(common.py:94-95) \"\"은 str(\"\")로 같은 빈 칸이 된다(common.py:100). (3) CSV 쓰기 전 메모리에서 집계하는 summarize()(411-440행)는 first_alarm_channel을 읽지 않는다. 결과 수치 스크립트(docs/revision/scripts/make_anomaly_numbers.py:416-428의 == 'psi' 비교)는 저장된 CSV를 읽는다(같은 파일 81·312행). 저장소에서 이 필드를 메모리에서 Counter·groupby·== 비교하는 곳은 없다(grep, 2026-10-13, 사용자 요청 확인).",
  ["thesis_v2/anomaly/common.py:92-101", "thesis_v2/anomaly/closed_loop.py:182-193", "thesis_v2/anomaly/closed_loop.py:178",
   "thesis_v2/anomaly/closed_loop.py:360", "thesis_v2/anomaly/closed_loop.py:411-440", "docs/revision/scripts/make_anomaly_numbers.py:81", "docs/revision/scripts/make_anomaly_numbers.py:312"])
d("closed_loop:029", EQ, "정지 분기의 v_cmd는 200행에서 vehicle_step(vehicle.py:20)에 넘겨진다. 위치·방향 갱신은 이전 속도 state.v를 쓴다(vehicle.py:24 x = state.x + state.v·cosψ·dt, 25 y = … state.v·sinψ·dt, 26 ψ = … (state.v/L)·tanδ·dt). v_cmd는 27행에서 반환 상태의 v 필드에만 대입된다. 그 뒤 check_collision과 vehicle_off_road는 x·y·ψ만 쓴다(collision.py:15-20·48-53, runner.py:87-97). 211행 break 뒤에는 vehicle을 읽지 않는다(281-289행). 그래서 v 값 0.0/1.0은 결과에 나타나지 않는다.",
  ["thesis_v2/anomaly/closed_loop.py:197-211", "thesis_v2/baseline/vehicle.py:20-27", "thesis_v2/baseline/collision.py:15-20",
   "thesis_v2/baseline/collision.py:48-53", "thesis_v2/anomaly/runner.py:87-97", "thesis_v2/anomaly/closed_loop.py:281-289"])
d("closed_loop:034", EQ, "같은 스텝의 충돌·이탈 판정은 vehicle_new를 읽는다(201행 check_collision(vehicle_new, …), 202행 vehicle_off_road(vehicle_new)). 둘 다 203행 대입보다 먼저 실행되어 vehicle을 읽지 않는다. 203행 다음은 204-210행(collided·off_road·terminate_on_departure만 읽음)과 211행 break다. 루프 뒤 281-289행은 vehicle을 읽지 않는다. 그래서 vehicle = vehicle_new 대입은 관찰되지 않는다.",
  ["thesis_v2/anomaly/closed_loop.py:203-211", "thesis_v2/anomaly/closed_loop.py:281-289"])
cl = {
    "closed_loop:018": ("184", "P2 ey·ir_miss 경보 뒤 ey 덮어쓰기가 적용되지 않는다(policy_action 문자열만 남음).", None),
    "closed_loop:021": ("187", "P2 rc 경보 뒤 right_clear 덮어쓰기가 적용되지 않는다.", None),
    "closed_loop:024": ("190", "P2 lc 경보 뒤 left_clear 덮어쓰기가 적용되지 않는다.", None),
    "closed_loop:028": ("198", "v_cmd 대입이 없어지면 이전 step의 v_cmd가 쓰이지만, 이 값은 결과에 나타나지 않는다(029와 같은 이유). 차이는 첫 step(step_idx=1)에 정지할 때만 생긴다. 이때 v_cmd가 정의되지 않아 NameError가 난다. threshold는 실행 입력이라 첫 step 경보는 제품 경로에서도 가능하다(사용자 결정: 테스트 공백, 보강).", None),
    "closed_loop:030": ("199", "delta_to_vehicle가 이전 step 값(apply_actuator 결과)으로 남는다. steer_stuck·steer_delay 고장 중에는 delta_prev와 달라 ψ와 충돌 판정이 바뀐다. 첫 step 정지에서는 NameError.", None),
    "closed_loop:031": ("200", "vehicle_new가 이전 step 값(= 현재 vehicle)으로 남는다. 정지 step의 한 칸 이동이 빠진 채로 충돌·이탈을 판정한다.", None),
    "closed_loop:032": ("201", "collided가 이전 step 값(정지 직전이면 보통 False)으로 남는다. 정지 step의 충돌이 '탐지 정지'로 기록된다.", None),
    "closed_loop:033": ("202", "off_road가 이전 step 값으로 남는다. terminate_on_departure=True이고 정지 step에서 처음 이탈하면 '이탈' 대신 '탐지 정지'로 기록된다.", None),
    "closed_loop:035": ("205", "충돌인데 outcome이 None으로 남아 281-282행에서 '타임아웃'이 된다.", None),
    "closed_loop:036": ("206", "terminate_on_departure=False여도 이탈이면 '이탈'로 기록된다.", None),
    "closed_loop:037": ("206", "terminate_on_departure=True이면 이탈이 아니어도 '이탈'로 기록된다.", None),
    "closed_loop:038": ("206", "and → or. 위 두 경우 모두 다르다.", None),
    "closed_loop:039": ("207", "이탈인데 outcome이 None으로 남아 '타임아웃'이 된다.", None),
    "closed_loop:048": ("348", "is_normal이 정의되지 않아 outcome='탐지 정지'일 때 351행에서 NameError.", None),
    "closed_loop:049": ("348", "정상 run과 고장 run의 판정이 뒤바뀐다.", None),
    "closed_loop:051": ("350", "탐지 정지가 아닌 결과에 unnecessary_stop이 붙고, 탐지 정지에는 붙지 않는다.", None),
    "closed_loop:052": ("352", "정상 run의 탐지 정지에서 'normal'이 None으로 남는다.", None),
    "closed_loop:053": ("353", "무해·유해 고장 판정이 뒤바뀐다.", None),
    "closed_loop:054": ("354", "무해 고장의 탐지 정지에서 'harmless'가 None으로 남는다.", None),
    "closed_loop:056": ("355", "is not → is. 유해 고장(onset 있음)의 onset 전 정지가 'before_onset'으로 분류되지 않는다.", None),
    "closed_loop:057": ("355", "and → or. 유해 고장 정지는 onset 이후여도 'before_onset'이 된다.", None),
    "closed_loop:059": ("355", "is not None → is None. 경보가 있는 탐지 정지에서 'before_onset'이 붙지 않는다.", None),
    "closed_loop:060": ("355", "onset 비교가 빠져, onset 이후 정지도 'before_onset'이 된다.", None),
    "closed_loop:061": ("355", "first_alarm_step == onset(정수)일 때 다르다. 정수라 정확히 같은 값이 실제로 나온다(사전 선언 P7').", None),
    "closed_loop:062": ("356", "'before_onset'이 None으로 남는다.", None),
}
for i, (ln, why, note) in cl.items():
    d(i, GAP, why, [f"thesis_v2/anomaly/closed_loop.py:{ln}"])
d("closed_loop:055", UNR, "onset이 None인 비정상 run에서 first_alarm_step < None → TypeError. 제품 경로(run_closed_loop_from_seed 310-313행)에서 onset이 None인 run은 'none'으로 시작하는 run뿐이다. 실제로 쓰는 이름은 'none'과 'none_leftobs' 두 개이고, 둘 다 351행 is_normal 분기에서 먼저 처리된다.",
  ["thesis_v2/anomaly/closed_loop.py:355", "thesis_v2/anomaly/closed_loop.py:310-313", "thesis_v2/anomaly/closed_loop.py:348-351"], no_test_reason=NO_TEST)
d("closed_loop:058", UNR, "first_alarm_step이 None이면 None < onset → TypeError. 제품 경로에서 outcome='탐지 정지'는 policy_action='stop'일 때만 생긴다(197-209행). policy_action='stop'은 경보가 처음 났을 때만 정해지고, 같은 블록에서 first_alarm_step도 대입된다(176-193행). 따라서 350행을 지나면 first_alarm_step이 항상 있다.",
  ["thesis_v2/anomaly/closed_loop.py:355", "thesis_v2/anomaly/closed_loop.py:176-193", "thesis_v2/anomaly/closed_loop.py:197-209"], no_test_reason=NO_TEST)

# ---------------- baseline_mpc ----------------
d("baseline_mpc:084", EQ, "지역 변수 c_idx는 대입(117행) 뒤 어디서도 읽히지 않는다(grep: mpc.py 117행뿐). len(rows)는 부작용이 없다.", ["thesis_v2/baseline/mpc.py:117"])
d("baseline_mpc:142", EQ, "159행에서 만든 self.A는 160-166행에서 읽히지 않고 167행에서 덮어써진다. 생성 호출은 같은 데이터로 163행 coo_matrix도 만들므로, 159행만 예외를 내는 입력이 없다. 생성자 __init__은 입력이 없다.",
  ["thesis_v2/baseline/mpc.py:159-167"])
d("baseline_mpc:144", EQ, "self._A_coo_rows는 저장소 어디서도 읽히지 않는다(grep: 164행 대입뿐. improved/mpc.py는 자기 클래스의 같은 이름 속성이라 무관하다. baseline OSQPMPC를 상속하거나 리플렉션으로 읽는 코드도 없다).",
  ["thesis_v2/baseline/mpc.py:164"])
d("baseline_mpc:145", EQ, "self._A_coo_cols는 저장소 어디서도 읽히지 않는다(144와 같은 grep 근거).", ["thesis_v2/baseline/mpc.py:165"])
d("baseline_mpc:147", EQ, "167행이 없으면 self.A는 159행의 sp.csc_matrix((vals,(rows,cols)))로 남는다. 생성자는 입력이 없어 이 행렬은 상수다. 원본(166행 coo.tocsc())과 변이의 self.A를 직접 비교하니 indptr·indices·data가 비트 단위로 같았다. 입력 공간이 한 점이므로 이 비교가 전수 확인이다. 이후 OSQP setup(67-74행)과 Ax_idx(_rc_to_dataidx, 166행 csc 기준)가 같은 행렬을 쓴다.",
  ["thesis_v2/baseline/mpc.py:159", "thesis_v2/baseline/mpc.py:163-173", "thesis_v2/baseline/mpc.py:66-74"],
  evidence_type="실험(scipy 1.13.1, 입력 없는 생성자라 모든 경우)", experiment_file="raw/mpc_setup_experiment.json",
  condition="scipy 1.13.1(.venv)에서 비교. 다른 scipy 버전에서는 다시 확인해야 한다.")
d("baseline_mpc:205", EQ, "y 위치제약 행(_row_ybound0 … +N−1)은 175-176행에서 이미 −inf/+inf로 초기화된다. 177-197행이 쓰는 행(동역학 2…2N−1, ψ·δ 제약, 0·1행)과 겹치지 않으므로, 200행 대입은 같은 값을 다시 쓰는 것이다. 보조 실험에서도 생성된 l·u가 원본과 비트 단위로 같았다(raw/mpc_setup_experiment.json).",
  ["thesis_v2/baseline/mpc.py:175-200", "thesis_v2/baseline/mpc.py:109-157"])
d("baseline_mpc:212", EQ, "지역 변수 vi는 대입(213행) 뒤 읽히지 않는다(grep: 213행뿐).", ["thesis_v2/baseline/mpc.py:213"])
d("baseline_mpc:275", EQ, "self._fail_count는 75행(초기화)과 258행(증가)에서만 쓰이고, 저장소 어디서도 읽히지 않는다(grep. improved/mpc.py는 별개 클래스). 정수 덧셈은 부작용이 없다.",
  ["thesis_v2/baseline/mpc.py:75", "thesis_v2/baseline/mpc.py:258"])
for i, ln in [("baseline_mpc:194", "196"), ("baseline_mpc:196", "197")]:
    d(i, HOLD, f"{ln}행 대입이 없으면 setup 시점의 l·u가 그 행에서 0 대신 −inf/+inf다. 매 solve는 231·232행에서 l·u 전체를 새로 넘기므로(243행), 남는 차이는 OSQP 내부 상태(setup 때 제약 종류에 따른 rho 벡터, KKT 분해)뿐이다. update 뒤 이 상태가 원본과 같아지는지는 OSQP 구현(저장소 밖)에 달려 있어, 저장소 코드만으로는 증명할 수 없다.",
      [f"thesis_v2/baseline/mpc.py:{ln}", "thesis_v2/baseline/mpc.py:66-74", "thesis_v2/baseline/mpc.py:228-246"],
      experiment="mpc_setup_experiment.py(결과 raw/mpc_setup_experiment.json): 같은 OSQPMPC 인스턴스로 연속 432회(y0·ψ0·v0·target·상태 격자, 웜스타트 경로 포함)와 새 인스턴스 첫 호출 12회, 합계 444회(fallback 186회 포함)의 delta_deg·solver_status·fallback_used가 원본과 비트 단위로 모두 같았다. 코드 증명이 아니라 실험 근거다.",
      decision="보류(외부 라이브러리 의존). 분모에 남긴다(사용자 결정 2026-10-13).")
d("baseline_mpc:283", GAP, "fallback 조향의 ±25° 클램프가 사라진다. solver 실패(실험에서 'primal infeasible' 확인) 중 |y0 − target| > 0.436 m이면 25°를 넘는 값이 나온다. 기존 fallback 테스트는 이 범위를 쓰지 않는다(추정, 사전 선언 M3).",
  ["thesis_v2/baseline/mpc.py:257-264"])
OBV = {
    "baseline_mpc:133": "ψ 제약 행의 계수가 0이 되어 ψ 상·하한 제약이 사라진다(사전 선언 M5). ψ 제약이 활성되는 입력에서 해가 다르다.",
    "baseline_mpc:155": "동역학 l=u=0 초기화 루프가 i=0,1까지 돌며 음수 행 번호(−2, −1 → 마지막 두 δ 제약 행)와 0·1행을 0으로 만든다. δ_{N−2}, δ_{N−1}이 0으로 고정된다.",
    "baseline_mpc:165": "row_psi가 row_y − 1이 되어 각 ψ 동역학 행 대신 이전 행에 l=u=0을 쓴다. 마지막 ψ 동역학 행이 −inf/+inf로 남는다.",
    "baseline_mpc:198": "198행 루프가 i=0까지 돌아 마지막 동역학 행(row_ybound0 − 1)을 −inf/+inf로 만든다. 그 행의 동역학 제약이 사라진다.",
    "baseline_mpc:246": "234행 루프가 i=0까지 돌아 마지막 동역학 행에 위치 상·하한을 넣는다(0=0 등식 대신). 동역학이 바뀐다.",
    "baseline_mpc:209": "v 하한 0.05가 0이 된다. v0 = 0이면 A의 v 의존 계수가 모두 0이 되어 해가 달라진다(사전 선언 M4: golden에서는 v ≥ 0.3).",
    "baseline_mpc:272": "compute_time_ms가 ms 대신 s/1000 단위가 된다. compute_time_ms는 runner.py:150·206에서 기록되는 출력이다(핵심 주장 1 측정값).",
    "baseline_mpc:273": "compute_time_ms가 항상 0.0이 된다(runner.py:150·206에서 기록됨).",
    "baseline_mpc:285": "fallback 경로 compute_time_ms가 (perf_counter + t_start)·1000으로 매우 큰 값이 된다.",
    "baseline_mpc:286": "fallback 경로 compute_time_ms 단위 오류.",
    "baseline_mpc:287": "fallback 경로 compute_time_ms가 항상 0.0.",
}
NOEFF = {
    "baseline_mpc:038": "_fail_count는 읽히지 않는다(75·258행뿐).",
    "baseline_mpc:276": "_fail_count는 읽히지 않는다.",
    "baseline_mpc:277": "_fail_count는 읽히지 않는다.",
    "baseline_mpc:213": "지역 변수 vi는 읽히지 않는다.",
    "baseline_mpc:087": "_v_entries는 저장소 어디서도 읽히지 않는다(grep: 107·119·130·136행 append뿐).",
    "baseline_mpc:088": "_v_entries는 읽히지 않는다.", "baseline_mpc:104": "_v_entries는 읽히지 않는다.",
    "baseline_mpc:105": "_v_entries는 읽히지 않는다.", "baseline_mpc:116": "_v_entries는 읽히지 않는다.",
    "baseline_mpc:117": "_v_entries는 읽히지 않는다.",
    "baseline_mpc:086": "placeholder 값이다. 매 solve에서 Ax(215-217행)로 덮어써진다(사전 선언 M1). 다만 setup 시점 A 값이 달라 OSQP 내부 스케일링이 달라질 수 있다.",
    "baseline_mpc:103": "placeholder 값이다. 매 solve에서 Ax(222-223행)로 덮어써진다(사전 선언 M1). 다만 setup 시점 스케일링이 달라질 수 있다.",
    "baseline_mpc:115": "placeholder 값이다. 매 solve에서 Ax(224-225행)로 덮어써진다(사전 선언 M1). 다만 setup 시점 스케일링이 달라질 수 있다.",
    "baseline_mpc:175": "ψ 제약 루프가 i=0까지 돌아 마지막 y 위치제약 행에 ψ 범위를 쓴다. 이 행은 매 solve 234-236행에서 덮어써진다.",
    "baseline_mpc:195": "0행 placeholder가 1.0이다. 매 solve 231행에서 덮어써진다(194와 같은 OSQP setup 문제).",
    "baseline_mpc:197": "1행 placeholder가 1.0이다. 매 solve 232행에서 덮어써진다.",
    "baseline_mpc:199": "198행 루프 끝이 N−1이 된다. 빠진 행은 이미 −inf/+inf다(205와 같은 이유).",
    "baseline_mpc:200": "198행 루프 끝이 N이 된다. 빠진 행은 이미 −inf/+inf다.",
}

before = {m["id"]: m for m in json.loads((repo / "docs/verification/mutation/raw/run_before.json").read_text(encoding="utf-8"))["mutants"]}
recheck = {m["id"]: m for m in json.loads((repo / "docs/verification/mutation/raw/run_before_recheck_laptop.json").read_text(encoding="utf-8"))["mutants"]}
surv = [m for m in before.values() if m["status"] == "survived"]
texts, gens, items = {}, {}, []
for r in surv:
    p, mod = r["path"], r["module"]
    if p not in texts:
        texts[p] = (repo / p).read_text(encoding="utf-8")
        gens[mod] = {x.id: x for x in M.generate(mod, texts[p])}
    mu = gens[mod][r["id"]]
    ln = mu.edits[0].start[0]
    old = texts[p].splitlines()[ln - 1].strip()
    new = M.mutated_text(texts[p], mu).splitlines()[ln - 1].strip()
    diff = r["layers"].get("L3", {}).get("max_diff_rad")
    it = dict(id=r["id"], module=mod, path=p, source_line=ln, operator=r["operator"], before=old, after=new,
              l3_max_diff_rad_run_before=diff,
              l3_max_diff_rad_recheck=recheck[r["id"]]["layers"].get("L3", {}).get("max_diff_rad"))
    if mod == "baseline_mpc" and r["operator"] in ("const", "arith"):
        assert r["id"] not in D, r["id"]
        it["classification"] = TOLP if diff and diff > 0 else TOL0
        it["reason"] = f"사전 선언 §5: baseline_mpc const·arith는 L3 측정값으로만 분류(max|diff| = {diff} rad ≤ 1e-3)."
        if r["id"] in OBV:
            it["obvious_test_gap"] = OBV[r["id"]]
            it["reinforce"] = True  # 표 분류는 사전 선언대로, 보강 대상에는 포함(사용자 결정 2026-10-13)
        if r["id"] in NOEFF:
            it["code_note"] = NOEFF[r["id"]]
    else:
        it.update(D.pop(r["id"]))
        if it["classification"] == GAP:
            it["reinforce"] = True
    items.append(it)
assert not D, list(D)
# 보강 대상에서 뺀 항목(사용자 결정 2026-10-13, 3차 검토). 분류는 그대로 두고 이유만 남긴다.
NO_REINFORCE = {
    "baseline_mpc:283": "테스트하지 않음: fallback 출력의 ±25° 클램프는 SPEC·SETTINGS_DECISION에 MPC 단계 요구사항으로 없다. 차량 조향 한계 δ_max=±25°(REQ-VEH-02)는 있으나, 적용 위치는 후처리(rate limit → ±25° clip, SETTINGS_DECISION §15, postprocess.py:26-27)로 정해져 있다. 명세에 없는 동작을 고정하지 않도록 RESULTS.md 발견 사항 4, IMPROVEMENT_BACKLOG 후보 16으로 기록.",
    "baseline_mpc:209": "테스트하지 않음: 속도 하한 max(0.05, …)(mpc.py:208)는 구현에는 있으나 명세에 없는 동작(파생 요구사항 누락). RESULTS.md 발견 사항 4, IMPROVEMENT_BACKLOG 후보 16으로 기록. SETTINGS_DECISION은 수정하지 않음.",
    "baseline_mpc:155": "테스트하지 않음: 관찰 가능한 출력(delta_deg)으로 구분되지 않음(격자 624개 입력에서 δ_0 차이 0). 사전 선언대로 측정값 분류 유지.",
}
for it in items:
    if it["id"] in NO_REINFORCE:
        it["reinforce"] = False
        it["no_test_reason"] = NO_REINFORCE[it["id"]]
order = {m: i for i, m in enumerate(M.TARGETS)}
items.sort(key=lambda x: (order[x["module"]], x["id"]))
doc = dict(
    status="confirmed",
    drafted="2026-10-13",
    confirmed="2026-10-13 (사용자 검토 반영: 보류·도달 불가 범주, closed_loop:028 공백, MPC 명백한 공백 11건 보강 포함). 2026-10-13 2차 검토: closed_loop:011 테스트 공백 → 등가(코드). 3차 검토: fsm:030 테스트 공백 → 등가(수치·부동소수점 근거)",
    source_runs=["raw/run_before.json", "raw/run_before_recheck_laptop.json"],
    criteria={
        EQ: "등가(판단): 어떤 입력으로도 관찰 가능한 동작에 차이가 없음을 코드 근거로 보일 수 있을 때만. 관찰 가능한 동작 = 공개 함수의 반환값과 그 뒤 상태 중 제품 코드가 읽거나 결과에 기록하는 것, 그리고 예외. 사적 메서드는 호출자가 결과를 쓰는 방식까지 포함해 판단.",
        BND: "경계 동치 미검증(저위험): 엄격/비엄격 부등호만 바뀌고, 비교 대상이 연속값이라 정확히 같은 값이 사실상 나오지 않는 경우. SPEC 요구사항으로 정해진 경계, 정수 경계, clip·대입으로 정확한 값이 실제로 나오는 경계는 제외(테스트 공백). 분모에서 빼지 않는다. 사전 선언에 없던 범주 — RESULTS.md '사전 선언 변경' 1.",
        UNR: "도달 불가 입력에서만 차이: 제품 코드가 만들지 않는 입력에서만 동작(예외)이 다르다. 분모에서 빼지 않고 테스트도 추가하지 않는다(no_test_reason). 사전 선언에 없던 범주 — RESULTS.md '사전 선언 변경' 3.",
        GAP: "테스트 공백: 위에 해당하지 않는 생존 변이. reinforce=true(보강 대상).",
        TOL0: "baseline_mpc const·arith, L3 max|diff| = 0(사전 선언 §5 측정 분류).",
        TOLP: "baseline_mpc const·arith, 0 < L3 max|diff| ≤ 1e-3(사전 선언 §5 측정 분류).",
        HOLD: "보류(외부 라이브러리 의존): 저장소 코드만으로 등가를 증명할 수 없고(OSQP 내부 상태), 실험상 차이도 없음. 분모에 남긴다. 사전 선언에 없던 범주 — RESULTS.md '사전 선언 변경' 2.",
        "evidence_type": "등가 항목의 근거 종류. '코드' = 저장소 코드 행으로 보임. '실험(...)' = 측정으로 보임(조건 명시). '수치(부동소수점) 근거' = IEEE-754 double 산술로 같은 값이 나올 수 없음을 보임.",
        "reinforce": "보강 대상. 테스트 공백 전부 + baseline_mpc const·arith 중 obvious_test_gap(표 분류는 사전 선언대로 측정값).",
    },
    mutants=items)
out = repo / "docs/verification/mutation/equivalence.json"
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
c = Counter((x["module"], x["classification"]) for x in items)
for m in M.TARGETS:
    print(m, {k[1]: v for k, v in c.items() if k[0] == m})
print("total", len(items))
print("reinforce", sum(1 for x in items if x.get("reinforce")))
print("evidence_type", Counter(x.get("evidence_type") for x in items if x["classification"] == EQ))
print("obvious", [x["id"] for x in items if "obvious_test_gap" in x])
