import pytest

from thesis_v2.tests.check_golden import compare_one, SCENARIOS, SEEDS


@pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
@pytest.mark.parametrize("seed", SEEDS)
def test_matches_golden(scenario_name, seed):
    """교차 환경 재현성(SETTINGS_DECISION.md §18): 이 환경의 재실행 결과가 golden 기준과
    일치하는지. 노트북(golden 생성 환경)에서는 항상 통과해야 하고, SSAFY PC에서 실패하면
    두 환경 간 차이가 있다는 뜻이므로 원인을 보고해야 한다(baseline을 결과에 맞춰 고치지 않음)."""
    result = compare_one(scenario_name, seed)
    assert result["ok"], result["detail"]
