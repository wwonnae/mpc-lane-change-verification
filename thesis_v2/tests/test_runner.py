import pytest

from thesis_v2.baseline import config
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.world import Obstacle, Scenario, generate_scenario, generate_left_obstacle_scenario


def test_collision_has_priority_over_safe_stop_same_step():
    """repro/docs/WORK_RULES.md: 충돌 판정은 차량 갱신 직후, 종료판정(SAFE_STOP 포함)보다 먼저 -> 동시 발생 시 '충돌' 우선."""
    obstacle_front = Obstacle(x_near=-0.05, x_far=-0.05 + config.L,
                               y_lo=-config.B / 2, y_hi=config.B / 2)
    obstacle_left = Obstacle(x_near=-0.05, x_far=-0.05 + config.L,
                              y_lo=config.W - config.B / 2, y_hi=config.W + config.B / 2)
    scenario = Scenario(obstacles=[obstacle_front, obstacle_left],
                         v0=0.4, y0=0.0, psi0_deg=0.0, seed=0, name="collision_priority_test")
    result = run_episode(scenario)
    assert result.outcome == "충돌"
    assert result.finish_step == 1


def test_seed_reproducibility():
    scenario_a = generate_scenario(seed=7)
    scenario_b = generate_scenario(seed=7)
    result_a = run_episode(scenario_a)
    result_b = run_episode(scenario_b)
    assert result_a.outcome == result_b.outcome
    assert result_a.finish_step == result_b.finish_step
    assert result_a.total_steps == result_b.total_steps
    trans_a = [(t.step, t.from_state, t.to_state) for t in result_a.transitions]
    trans_b = [(t.step, t.from_state, t.to_state) for t in result_b.transitions]
    assert trans_a == trans_b


def test_safe_stop_holds_last_steering_and_does_not_crash():
    """REQ-LAT-05(§16): SAFE_STOP 진입 스텝의 조향각은 그 직전 스텝의 delta_final과 같아야
    하고(hold_last), rate limit/clip이 추가로 개입하지 않아야 한다. MPC가 SAFE_STOP으로
    호출되면 POSITION_CONSTRAINTS에 키가 없어 KeyError가 나므로, 에피소드가 크래시 없이
    끝나는 것 자체가 MPC 미호출의 증거이기도 하다."""
    scenario = generate_left_obstacle_scenario(seed=0)
    result = run_episode(scenario)
    assert result.outcome == "SAFE_STOP"
    fs = result.finish_step
    rows = result.logger.rows
    assert rows[fs - 1]["state"] == "SAFE_STOP"
    assert rows[fs - 1]["delta_mpc_raw"] == pytest.approx(rows[fs - 2]["delta_final"])
    assert rows[fs - 1]["delta_final"] == pytest.approx(rows[fs - 2]["delta_final"])
    assert rows[fs - 1]["rate_limit_active"] is False
    assert rows[fs - 1]["clip_active"] is False


def test_metrics_counts_are_internally_consistent():
    """MEASURE_PLAN.md P트랙 §18: clip_count는 세분류(clip_numerical+clip_violation) 합과
    같아야 하고, 논문 시나리오(paper)에서는 QP 구현이 정합이므로 clip_violation이 0이어야
    한다(관측된 초과가 전부 eps_abs 이내 -- §16 clip 출처 분석과 동일 결론)."""
    scenario = generate_scenario(seed=0)
    result = run_episode(scenario)
    assert result.clip_count == result.clip_numerical_count + result.clip_violation_count
    assert result.clip_violation_count == 0
    assert result.delta_violation_count == 0
    assert result.psi_violation_count == 0
    assert result.y_violation_count == 0
