"""
Golden(회귀) 테스트 — DESIGN.md §3.

(a) 고장·탐지기 없음, (b) 관찰 전용 탐지기만 부착 — 두 경우 모두 anomaly runner가
improved/runner.py(v2 플래그)와 **스텝 로그·결과가 완전히 같아야**(허용오차 0) 한다.
(b)는 "탐지기가 제어를 바꾸지 않는다"는 증거, (c) 비활성 고장(onset이 에피소드 이후)도 같아야 한다.
비교에서 계산 시간 필드(t_mpc_solve_ms)만 제외한다(실행마다 달라지는 측정값).
"""
import numpy as np
import pytest

from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.world import generate_scenario, generate_left_obstacle_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.faults import FaultSpec
from thesis_v2.anomaly.runner import run_episode as anomaly_run_episode, DetectorOutput

_IGNORE = {"t_mpc_solve_ms"}
_S4_LOW_PROFILE_ID = 0  # run_eval_v2._S4_PROFILE_IDS 관례와 무관한 이 테스트 전용 고정값


class _RecordingDetector:
    """관찰만 하는 더미 탐지기(관측값을 받아 기록하고 항상 경보를 낸다 — 정책이 없으므로
    경보가 나도 제어가 바뀌면 안 된다)."""

    def __init__(self):
        self.n = 0

    def reset(self):
        self.n = 0

    def update(self, obs):
        self.n += 1
        return DetectorOutput(score=float(obs.frame.front_gap), alarm=True, channel="dummy")


def _rows(logger):
    return [{k: v for k, v in r.items() if k not in _IGNORE} for r in logger.rows]


def _assert_same(ref, got):
    assert got.outcome == ref.outcome
    assert got.finish_step == ref.finish_step
    assert got.total_steps == ref.total_steps
    assert [(t.step, t.from_state, t.to_state) for t in got.transitions] == \
           [(t.step, t.from_state, t.to_state) for t in ref.transitions]
    ref_rows, got_rows = _rows(ref.logger), _rows(got.logger)
    assert len(got_rows) == len(ref_rows)
    for i, (a, b) in enumerate(zip(ref_rows, got_rows)):
        assert a == b, f"step {i + 1} 불일치: {[(k, a[k], b[k]) for k in a if a[k] != b[k]]}"


CASES = [("paper", generate_scenario, s) for s in (0, 1, 2)] + \
        [("left_obstacle", generate_left_obstacle_scenario, s) for s in (0, 1, 2)]


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
@pytest.mark.parametrize("name,gen,seed", CASES)
@pytest.mark.parametrize("mode", ["none", "detector", "inactive_fault"])
def test_equivalent_to_improved_v2(name, gen, seed, mode):
    sc = gen(seed)
    ref = improved_run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS))
    kwargs = {}
    if mode == "detector":
        kwargs["detector"] = _RecordingDetector()
    elif mode == "inactive_fault":
        kwargs["fault"] = FaultSpec("lidar_freeze", onset_step=10_000, duration_steps=None)
    got = anomaly_run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), **kwargs)
    _assert_same(ref, got)
    if mode == "detector":
        assert got.first_alarm_step == 1  # 경보는 났지만 제어는 그대로였다
    assert all(r["label"] == 0 for r in got.alog)


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
@pytest.mark.parametrize("seed", [0, 1])
def test_equivalent_with_s4_low_noise(seed):
    sc = generate_scenario(seed)
    profile = base_sensors.NOISE_PROFILES[an_config.NORMAL_NOISE_PROFILE]
    ref = improved_run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), noise_profile=profile,
                               noise_rng=np.random.default_rng((seed, _S4_LOW_PROFILE_ID)))
    got = anomaly_run_episode(sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), noise_profile=profile,
                              noise_rng=np.random.default_rng((seed, _S4_LOW_PROFILE_ID)),
                              detector=_RecordingDetector())
    _assert_same(ref, got)
