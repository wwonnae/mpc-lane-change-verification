"""closed_loop 테스트 보강 — mutation testing 1차 생존 변이 중 테스트 공백(docs/verification/mutation/equivalence.json).

이 파일의 테스트는 LLM(Claude Code)이 제안했다. 수락 기준과 검토 기록은 docs/verification/mutation/RESULTS.md,
llm_tests_log.json에 있다(PREREGISTRATION.md §8).

탐지기는 _ScriptedDetector(정해진 step부터 정해진 채널로 경보)를 쓴다. 정책 동작만 확인하려는 것이고, 탐지 성능과는 무관하다.
DESIGN.md §24: 탐지기는 Detector 프로토콜(reset/update)만 맞으면 된다.
"""
import dataclasses

import pytest

from thesis_v2.anomaly import closed_loop as cl
from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.faults import FaultSpec
from thesis_v2.anomaly.runner import DetectorOutput
from thesis_v2.anomaly.scenarios import generate_anomaly_scenario, estimated_trigger_step
from thesis_v2.improved.mpc import ImprovedMPC


class _ScriptedDetector:
    def __init__(self, alarm_step: int, channel: str):
        self.alarm_step, self.channel = alarm_step, channel

    def reset(self) -> None:
        pass

    def update(self, obs) -> DetectorOutput:
        alarm = obs.step >= self.alarm_step
        return DetectorOutput(score=1.0 if alarm else 0.0, alarm=alarm, channel=self.channel)


def _run(sc, policy="P0", detector=None, fault=None, terminate_on_departure=True):
    return cl.run_closed_loop_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), fault=fault, detector=detector,
                                      policy=policy, max_steps=an_config.ANOMALY_MAX_STEPS,
                                      terminate_on_departure=terminate_on_departure)


def _observable(res):
    return (res.outcome, res.total_steps, res.finish_step, [(t.step, t.from_state, t.to_state) for t in res.transitions])


def _onset(sc):
    return max(an_config.WARMUP_STEPS, estimated_trigger_step(sc) - 8)


# ---------------- P1 즉시 정지 step ----------------

@pytest.mark.parametrize("terminate_on_departure", [True, False])
def test_p1_stop_on_first_step_is_detection_stop(terminate_on_departure):
    """DESIGN.md §24 P1: 첫 경보 step에 v_cmd=0·직전 조향 유지로 한 번 갱신하고 종료한다. 그 step에 충돌·이탈이
    없으면 결과는 '탐지 정지'다. 경보가 첫 step(k=1)이어도 같다."""
    sc = generate_anomaly_scenario(3200)
    res = _run(sc, "P1", _ScriptedDetector(1, "fg"), terminate_on_departure=terminate_on_departure)
    assert res.outcome == "탐지 정지"
    assert res.policy_action == "stop"
    assert res.first_alarm_step == res.finish_step == res.total_steps == 1


def test_p1_stop_step_collision_is_classified_as_collision():
    """DESIGN.md §24 P1: 정지 step의 한 번 갱신으로 충돌이 생기면 결과는 '탐지 정지'가 아니라 '충돌'이다
    (물리적으로 이미 일어난 일이 우선). 충돌 판정은 갱신 후 상태로 한다(repro/docs/WORK_RULES.md baseline 원칙: 상태 갱신 직후 충돌 판정)."""
    sc = generate_anomaly_scenario(3200)
    fault = lambda: FaultSpec("lidar_dropout", onset_step=_onset(sc), duration_steps=None)
    p0 = _run(sc, fault=fault())
    assert p0.outcome == "충돌" and p0.finish_step >= 2     # 전제: P0는 이 step에 충돌한다
    res = _run(sc, "P1", _ScriptedDetector(p0.finish_step, "fg"), fault=fault())
    assert res.outcome == "충돌"
    assert res.finish_step == res.first_alarm_step == p0.finish_step


def _edge_scenario():
    """도로 좌측 경계(ROAD_Y_RANGE 상한 0.45) 가까이에서 바깥쪽(ψ0 = 30°)으로 출발하는 시나리오.
    이탈 여부가 조향보다 위치에 좌우되도록 만든 것이다(seed 3200의 장애물·속도는 그대로)."""
    return dataclasses.replace(generate_anomaly_scenario(3200), y0=0.38, psi0_deg=30.0)


def test_p1_stop_step_departure_is_classified_as_departure():
    """DESIGN.md §24 P1: 정지 step의 한 번 갱신으로 이탈이 생기면(terminate_on_departure=True) 결과는 '이탈'이다."""
    sc = _edge_scenario()
    p0 = _run(sc)
    assert p0.outcome == "이탈" and p0.finish_step >= 2     # 전제: P0는 이 step에 처음 이탈한다
    res = _run(sc, "P1", _ScriptedDetector(p0.finish_step, "fg"))
    assert res.outcome == "이탈"
    assert res.finish_step == p0.finish_step


def test_p1_stop_step_departure_without_termination_is_detection_stop():
    """DESIGN.md §24 P1 + run_closed_loop_episode(terminate_on_departure=False): 이탈 종료를 끈 실행에서는 정지 step에
    도로를 벗어나도 '이탈'로 분류하지 않는다(결과는 '탐지 정지')."""
    sc = _edge_scenario()
    p0 = _run(sc)
    assert p0.outcome == "이탈" and p0.finish_step >= 2
    res = _run(sc, "P1", _ScriptedDetector(p0.finish_step, "fg"), terminate_on_departure=False)
    assert res.outcome == "탐지 정지"
    assert res.finish_step == p0.finish_step


# ---------------- P2 덮어쓰기 ----------------

@pytest.mark.parametrize("channel,fault_kind,value", [
    ("ey", "ir_dropout", None),            # ey → None
    ("rc", "right_clear_stuck", False),    # right_clear → False
    ("lc", "left_clear_stuck", False),     # left_clear → False
])
def test_p2_override_feeds_controller_the_overridden_value(channel, fault_kind, value):
    """DESIGN.md §24 P2: 첫 경보 채널이 ey/rc/lc이면 그 step부터 에피소드 끝까지 FSM·횡방향에 들어가는 값을
    ey=None / right_clear=False / left_clear=False로 덮어쓴다(정지 없음). 따라서 결과는, 정책 없이(P0) 같은 step부터
    그 값이 센서에 주입된 실행과 같아야 한다."""
    sc = generate_anomaly_scenario(3200)
    k = 10
    p2 = _run(sc, "P2", _ScriptedDetector(k, channel))
    ref = _run(sc, fault=FaultSpec(fault_kind, onset_step=k, duration_steps=None, value=value))
    assert p2.policy_action == f"override_{channel}"
    assert _observable(p2) == _observable(ref)
    assert _observable(p2) != _observable(_run(sc))  # 전제: 덮어쓰기가 결과를 바꾸는 시나리오


# ---------------- episode_row 불필요 정지 분류 ----------------

def _result(outcome, onset=None, first_alarm_step=None):
    fault = None if onset is None else dict(kind="x", onset_step=onset, duration_steps=None)
    return cl.ClosedLoopResult(seed=0, scenario_name="t", outcome=outcome, finish_step=None, total_steps=100,
                               transitions=[], fault=fault, first_alarm_step=first_alarm_step,
                               first_alarm_channel="fg" if first_alarm_step else None,
                               policy_action="stop" if outcome == "탐지 정지" else None)


@pytest.mark.parametrize("run", ["none", "none_leftobs"])
def test_unnecessary_stop_normal_episode(run):
    """DESIGN.md §24 불필요 정지 1: run ∈ {none, none_leftobs}이고 결과가 '탐지 정지'이면 'normal'. 다른 결과는 None."""
    assert cl.episode_row(_result("탐지 정지", first_alarm_step=30), run, 0)["unnecessary_stop"] == "normal"
    assert cl.episode_row(_result("성공"), run, 0)["unnecessary_stop"] is None


@pytest.mark.parametrize("run", sorted(cl.HARMLESS_KINDS))
def test_unnecessary_stop_harmless_fault(run):
    """DESIGN.md §24 불필요 정지 2(§19-2 HARMLESS_KINDS): 무해 고장 run의 '탐지 정지'는 경보 시점과 무관하게 'harmless'."""
    assert cl.episode_row(_result("탐지 정지", onset=50, first_alarm_step=60), run, 0)["unnecessary_stop"] == "harmless"


@pytest.mark.parametrize("first_alarm_step,expected", [
    (49, "before_onset"),   # onset 전
    (50, None),             # onset 그 step — 'first_alarm_step < onset_step'이 아님
    (51, None),             # onset 후 — 의도한 정상 동작
])
def test_unnecessary_stop_harmful_fault_boundary(first_alarm_step, expected):
    """DESIGN.md §24 불필요 정지 3: 유해 고장에서 first_alarm_step < onset_step이고 '탐지 정지'이면 'before_onset'.
    onset 이후(같은 step 포함) 정지는 불필요가 아니다(None)."""
    run = sorted(cl.HARMFUL_KINDS)[0]
    row = cl.episode_row(_result("탐지 정지", onset=50, first_alarm_step=first_alarm_step), run, 0)
    assert row["unnecessary_stop"] == expected


def test_unnecessary_stop_requires_detection_stop_outcome():
    """DESIGN.md §24 불필요 정지: 세 경우 모두 결과가 '탐지 정지'일 때만 해당한다. 유해 고장 onset 전 경보라도
    결과가 '충돌'이면 None."""
    run = sorted(cl.HARMFUL_KINDS)[0]
    assert cl.episode_row(_result("충돌", onset=50, first_alarm_step=40), run, 0)["unnecessary_stop"] is None
