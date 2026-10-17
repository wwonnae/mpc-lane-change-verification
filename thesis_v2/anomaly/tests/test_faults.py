"""고장 주입기·라벨·시나리오 단위 테스트 (DESIGN.md §2)."""
import pytest

from thesis_v2.baseline import config as base_config
from thesis_v2.improved.sensors import FrontObstacleInfo

from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.faults import FaultSpec, FaultInjector, SensorFrame, sample_fault, FAULT_IDS
from thesis_v2.anomaly.scenarios import generate_anomaly_scenario, initial_front_gap, estimated_trigger_step
from thesis_v2.anomaly.runner import run_episode, vehicle_off_road
from thesis_v2.baseline.vehicle import VehicleState


def _frame(fg=2.0, k=0):
    info = FrontObstacleInfo(gap_near=fg, gap_far=fg + 0.2, y_lo=-0.075, y_hi=0.075)
    return SensorFrame(front_gap=fg, left_clear=True, right_clear=False, ir_pattern=(0, 1, 0),
                       ey_line=0.0, obstacle_info=info)


def test_label_window():
    s = FaultSpec("lidar_dropout", onset_step=5, duration_steps=3)
    assert [int(s.active(k)) for k in range(1, 10)] == [0, 0, 0, 0, 1, 1, 1, 0, 0]
    p = FaultSpec("lidar_freeze", onset_step=5, duration_steps=None)
    assert p.active(10_000) and not p.active(4)


def test_identity_without_spec():
    inj = FaultInjector(None)
    f = _frame()
    assert inj.apply_sensors(1, f) is f
    assert inj.apply_actuator(1, 3.0) == 3.0
    assert inj.label(1) == 0


def test_freeze_holds_last_good_value_including_obstacle_info():
    inj = FaultInjector(FaultSpec("lidar_freeze", onset_step=3, duration_steps=None))
    outs = [inj.apply_sensors(k, _frame(fg=2.0 - 0.1 * k)) for k in range(1, 7)]
    assert [round(o.front_gap, 3) for o in outs] == [1.9, 1.8, 1.8, 1.8, 1.8, 1.8]
    assert all(o.obstacle_info.gap_near == pytest.approx(1.8) for o in outs[1:])


def test_spike_and_dropout_keep_obstacle_info_consistent():
    up = FaultInjector(FaultSpec("lidar_spike", 1, 1, magnitude=base_config.LIDAR_MAX_RANGE))
    o = up.apply_sensors(1, _frame())
    assert o.front_gap == base_config.LIDAR_MAX_RANGE and o.obstacle_info is None
    down = FaultInjector(FaultSpec("lidar_spike", 1, 1, magnitude=0.3))
    o = down.apply_sensors(1, _frame())
    assert o.front_gap == 0.3 and o.obstacle_info.gap_near == 0.3
    assert o.obstacle_info.gap_far == pytest.approx(0.5)
    drop = FaultInjector(FaultSpec("lidar_dropout", 1, 5))
    o = drop.apply_sensors(1, _frame())
    assert o.front_gap == base_config.LIDAR_MAX_RANGE and o.obstacle_info is None


def test_ir_and_clear_faults():
    o = FaultInjector(FaultSpec("ir_stuck", 1, None, pattern=(1, 0, 0))).apply_sensors(1, _frame())
    assert o.ir_pattern == (1, 0, 0) and o.ey_line == -0.04
    o = FaultInjector(FaultSpec("ir_dropout", 1, None)).apply_sensors(1, _frame())
    assert o.ir_pattern == (0, 0, 0) and o.ey_line is None
    o = FaultInjector(FaultSpec("right_clear_stuck", 1, None, value=True)).apply_sensors(1, _frame())
    assert o.right_clear is True and o.left_clear is True and o.front_gap == 2.0


def test_steer_delay_and_stuck():
    inj = FaultInjector(FaultSpec("steer_delay", onset_step=3, duration_steps=None, magnitude=2))
    out = [inj.apply_actuator(k, float(k)) for k in range(1, 7)]
    assert out == [1.0, 2.0, 1.0, 2.0, 3.0, 4.0]
    inj = FaultInjector(FaultSpec("steer_stuck", onset_step=3, duration_steps=2))
    out = [inj.apply_actuator(k, float(k)) for k in range(1, 7)]
    assert out == [1.0, 2.0, 2.0, 2.0, 5.0, 6.0]


def test_scenario_range_and_determinism():
    for s in an_config.SEEDS_FAULT_DEV[:20]:
        sc = generate_anomaly_scenario(s)
        lo, hi = an_config.ANOMALY_FRONT_GAP_RANGE
        assert lo <= initial_front_gap(sc) <= hi
        assert generate_anomaly_scenario(s) == sc
        assert estimated_trigger_step(sc) > an_config.WARMUP_STEPS + 5
    left = generate_anomaly_scenario(3200, left_obstacle=True)
    assert len(left.obstacles) == 2 and left.name == "anomaly_far_leftobs"


@pytest.mark.parametrize("kind", sorted(FAULT_IDS))
def test_sample_fault_deterministic_and_after_warmup(kind):
    sc = generate_anomaly_scenario(3200)
    a, b = sample_fault(kind, sc), sample_fault(kind, sc)
    assert a == b
    assert a.onset_step >= an_config.WARMUP_STEPS


def test_runner_labels_match_spec():
    sc = generate_anomaly_scenario(3201)
    spec = FaultSpec("lidar_dropout", onset_step=20, duration_steps=5)
    res = run_episode(sc, fault=spec, max_steps=an_config.ANOMALY_MAX_STEPS)
    labels = [r["label"] for r in res.alog]
    assert labels[18:26] == [0, 1, 1, 1, 1, 1, 0, 0]
    assert all(r["front_gap"] == base_config.LIDAR_MAX_RANGE for r in res.alog[19:24])
    assert res.alog[18]["front_gap"] < base_config.LIDAR_MAX_RANGE


def test_off_road_definition():
    lo, hi = an_config.ROAD_Y_RANGE
    on = VehicleState(0.0, 0.0, 0.0, 0.5)
    edge = VehicleState(0.0, lo + 0.05, 0.0, 0.5)   # 중심은 도로 안, 우측 모서리(−B/2)만 밖
    assert not vehicle_off_road(on, "corner") and not vehicle_off_road(on, "center")
    assert vehicle_off_road(edge, "corner") and not vehicle_off_road(edge, "center")
    assert vehicle_off_road(VehicleState(0.0, lo - 0.01, 0.0, 0.5), "center")
    assert vehicle_off_road(VehicleState(0.0, hi + 0.01, 0.0, 0.5), "center")
