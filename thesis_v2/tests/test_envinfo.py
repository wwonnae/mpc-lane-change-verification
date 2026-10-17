from thesis_v2.baseline.envinfo import (
    BEST_PERFORMANCE_OVERLAY_GUID,
    _overlay_is_best_performance,
    collect_env_info,
)


def test_collect_env_info_does_not_crash_and_has_power_fields():
    info = collect_env_info()
    assert isinstance(info["hostname"], str)
    assert isinstance(info["is_official_measurement_host"], bool)
    power = info["power"]
    assert power["ac_status"] in ("AC", "battery", "unknown")
    assert isinstance(power["power_plan"], str)
    assert isinstance(power["power_mode_overlay"], str)
    assert len(power["power_mode_overlay"]) > 0
    assert power["power_mode_user_confirmed"] is False
    assert power["power_mode_user_confirmed_at"] is None


def test_power_mode_confirmed_flag_recorded_with_timestamp():
    info = collect_env_info(power_mode_confirmed=True)
    power = info["power"]
    assert power["power_mode_user_confirmed"] is True
    assert isinstance(power["power_mode_user_confirmed_at"], str)
    assert len(power["power_mode_user_confirmed_at"]) > 0


def test_overlay_guid_matcher():
    assert _overlay_is_best_performance(f"Max Performance Overlay ({BEST_PERFORMANCE_OVERLAY_GUID})")
    assert not _overlay_is_best_performance("Better Battery-life Overlay (961cc777-...)")
    assert not _overlay_is_best_performance("감지 불가(...)")


def test_meets_official_condition_with_user_confirmation_equals_ac_status():
    """power_mode_confirmed=True면 OR 항이 항상 참이 되므로, 공식 조건은 AC 여부만으로
    결정되어야 한다."""
    info = collect_env_info(power_mode_confirmed=True)
    power = info["power"]
    assert power["meets_official_condition"] == (power["ac_status"] == "AC")


def test_meets_official_condition_without_confirmation_requires_overlay():
    """power_mode_confirmed=False면 overlay 자동 감지로만 충족 가능하다."""
    info = collect_env_info(power_mode_confirmed=False)
    power = info["power"]
    expected = (power["ac_status"] == "AC") and power["power_mode_overlay_confirms_best_performance"]
    assert power["meets_official_condition"] == expected
