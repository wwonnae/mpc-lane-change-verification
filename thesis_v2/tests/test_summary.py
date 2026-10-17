import pytest

from thesis_v2.baseline.summary import build_summary, wilson_ci
from thesis_v2.baseline.runner import run_episode
from thesis_v2.baseline.world import generate_scenario, generate_left_obstacle_scenario
from thesis_v2.baseline.mpc import OSQPMPC

_DUMMY_ENV = {"hostname": "TEST-HOST", "is_official_measurement_host": False,
              "power": {"ac_status": "unknown", "power_plan": "unknown"}}


@pytest.fixture(scope="module")
def paper_results():
    mpc = OSQPMPC()
    return [run_episode(generate_scenario(seed), mpc=mpc) for seed in range(5)]


def test_solver_fail_and_fallback_totals_present(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    assert summary["solver_fail_total"] == sum(r.solver_fail_count for r in paper_results)
    assert summary["fallback_total"] == sum(r.fallback_count for r in paper_results)


def test_percentiles_present_and_ordered(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    p = summary["mpc_solve_time_ms"]
    assert p["p50"] is not None
    assert p["p50"] <= p["p95"] <= p["p99"]
    assert p["max"] >= p["p99"]


def test_max_call_info_matches_actual_max(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    info = summary["mpc_solve_time_ms"]["max_call_info"]
    assert info is not None
    assert info["t_mpc_solve_ms"] == pytest.approx(summary["mpc_solve_time_ms"]["max"])
    seed_result = next(r for r in paper_results if r.seed == info["seed"])
    row = seed_result.logger.rows[info["step"] - 1]
    assert row["t_mpc_solve_ms"] == pytest.approx(info["t_mpc_solve_ms"])
    assert row["state"] == info["state"]


def test_expected_outcome_paper_is_success():
    summary = build_summary([], "paper", _DUMMY_ENV)
    assert summary["expected_outcome"] == "성공"


def test_expected_outcome_left_obstacle_is_safe_stop():
    mpc = OSQPMPC()
    results = [run_episode(generate_left_obstacle_scenario(seed), mpc=mpc) for seed in range(3)]
    summary = build_summary(results, "left_obstacle", _DUMMY_ENV)
    assert summary["expected_outcome"] == "SAFE_STOP"
    assert summary["expected_outcome_achievement_rate"] == pytest.approx(
        summary["outcome_counts"].get("SAFE_STOP", 0) / len(results)
    )


def test_empty_results_do_not_crash():
    summary = build_summary([], "paper", _DUMMY_ENV)
    assert summary["n_episodes"] == 0
    assert summary["success_rate"] is None
    assert summary["mpc_solve_time_ms"]["max_call_info"] is None
    assert summary["success_rate_ci95"] is None


# ---------- Wilson 95% 신뢰구간 ----------

def test_wilson_ci_none_for_zero_n():
    assert wilson_ci(0, 0) is None


def test_wilson_ci_bounds_contain_point_estimate():
    ci = wilson_ci(99, 100)
    assert 0.0 <= ci["lo"] <= ci["point"] <= ci["hi"] <= 1.0
    assert ci["point"] == pytest.approx(0.99)


def test_wilson_ci_known_reference_p50_n100():
    """표준 참고값: n=100, k=50 -> Wilson 95% CI ~= [0.404, 0.596] (널리 알려진 예시)."""
    ci = wilson_ci(50, 100)
    assert ci["lo"] == pytest.approx(0.404, abs=0.005)
    assert ci["hi"] == pytest.approx(0.596, abs=0.005)


def test_wilson_ci_zero_successes_lower_bound_is_zero():
    ci = wilson_ci(0, 10)
    assert ci["lo"] == pytest.approx(0.0)
    assert ci["hi"] > 0.0


def test_summary_success_and_collision_ci_present_and_formatted(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    assert summary["success_rate_ci95"] is not None
    assert summary["collision_rate_ci95"] is not None
    assert summary["success_rate_formatted"].startswith(
        f"{summary['outcome_counts'].get('성공', 0)}/{len(paper_results)} (95% CI ")
    assert "~" in summary["success_rate_formatted"]


# ---------- 첫 호출 제외 최대 계산시간 ----------

def test_max_excluding_first_call_le_max(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    m = summary["mpc_solve_time_ms"]
    if m["max_excluding_first_call"] is not None:
        assert m["max_excluding_first_call"] <= m["max"]


def test_max_call_info_excluding_first_call_is_never_first():
    mpc = OSQPMPC()
    results = [run_episode(generate_scenario(seed), mpc=mpc) for seed in [0, 1, 2, 85]]
    summary = build_summary(results, "paper", _DUMMY_ENV)
    info = summary["mpc_solve_time_ms"]["max_call_info_excluding_first_call"]
    if info is not None:
        assert info["is_first_mpc_call_of_episode"] is False


# ---------- t_step_ms(스텝 전체 소요시간) 통계 ----------

def test_step_time_ms_present_and_ordered(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    s = summary["step_time_ms"]
    assert s["p50"] <= s["p95"] <= s["p99"]
    assert s["max"] >= s["p99"]
    assert s["n_steps"] == sum(len(r.logger.rows) for r in paper_results)


def test_step_time_ms_is_at_least_mpc_solve_time(paper_results):
    """t_step_ms는 t_mpc_solve_ms를 포함한 스텝 전체 시간이므로 항상 그 이상이어야 한다."""
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    for r in paper_results:
        for row in r.logger.rows:
            assert row["t_step_ms"] >= (row.get("t_mpc_solve_ms") or 0.0)


def test_step_time_ms_max_excluding_first_call_le_max(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    s = summary["step_time_ms"]
    if s["max_excluding_first_call"] is not None:
        assert s["max_excluding_first_call"] <= s["max"]


def test_step_time_ms_has_budget_pct(paper_results):
    summary = build_summary(paper_results, "paper", _DUMMY_ENV)
    s = summary["step_time_ms"]
    assert s["budget_ms_20hz"] == pytest.approx(50.0)
    assert s["mean_pct_of_budget"] == pytest.approx(s["mean"] / 50.0 * 100.0)
