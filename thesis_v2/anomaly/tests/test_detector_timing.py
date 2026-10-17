"""탐지기 계산 시간 측정 루프 — 측정용 루프가 관찰 전용 러너와 같은 에피소드를 만드는지(시간 값 제외) 확인한다."""
import pytest

from thesis_v2.anomaly.benchmark_detector_timing import run_normal_episode, stats, BUDGET_MS
from thesis_v2.anomaly.common import run_anomaly_episode
from thesis_v2.anomaly.detector_a import DetectorA

_H_A = 9.210921221467048  # §18 메인 h


@pytest.mark.parametrize("seed", [3000, 3001])
@pytest.mark.parametrize("scenario", ["far", "leftobs"])
def test_timed_loop_matches_observational_runner(seed, scenario):
    ref = run_anomaly_episode(seed, None, left_obstacle=(scenario == "leftobs"), detector=DetectorA(threshold=_H_A),
                              record_alog=False)
    got = run_normal_episode(scenario, seed, DetectorA(threshold=_H_A))
    assert got["outcome"] == ref.outcome
    assert got["total_steps"] == ref.total_steps
    assert got["first_alarm_step"] == ref.first_alarm_step
    assert [(t.step, t.from_state, t.to_state) for t in got["transitions"]] == \
           [(t.step, t.from_state, t.to_state) for t in ref.transitions]
    assert len(got["control_ms"]) == len(got["detector_ms"]) == got["total_steps"]


def test_stats_budget_ratio():
    s = stats([1.0, 2.0, 3.0, 100.0])
    assert s["max"] == 100.0 and s["n_over_budget"] == 1
    assert s["max_pct_of_budget"] == pytest.approx(100.0 / BUDGET_MS * 100.0)
