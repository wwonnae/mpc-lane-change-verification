"""
I4(Student 재학습, 3단계 [발전]) 테스트. DESIGN_I4.md(개정 1).
REQ-STU-01(구조), REQ-STU-02(입력 9차원·fallback), REQ-STU-03(출력 2차원·v_target 출처),
I4 캡처 무간섭, I4 계층 분할, I4 폐루프 루프 동등성(MPC로 돌리면 improved.runner와 같아야 함).
"""
import math

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from thesis_v2.baseline import config
from thesis_v2.baseline.world import generate_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode
from thesis_v2.improved.student_i4 import config as i4_config
from thesis_v2.improved.student_i4.closed_loop import run_episode as cl_run_episode
from thesis_v2.improved.student_i4.dataset_gen import stratified_episode_split
from thesis_v2.improved.student_i4.features import (
    FEATURE_NAMES, SolveRecorder, build_feature_vector, pair_calls_with_log, v_target_label,
)
from thesis_v2.improved.student_i4.model import StudentPolicy, compute_norm_stats


def test_req_stu_01_structure():
    m = StudentPolicy().eval()
    shapes = [tuple(p.shape) for n, p in m.named_parameters() if n.endswith("weight") and p.dim() == 2]
    assert shapes == [(256, 9), (256, 256), (128, 256), (2, 128)]
    assert m(torch.zeros(1, 9)).shape == (1, 2)


def test_req_stu_02_feature_order_and_fallback():
    assert FEATURE_NAMES[:4] == ["v", "ey_line", "front_gap", "left_clear"]
    x = build_feature_vector(0.5, None, 0.12, "EVADE_L", 1.3, True)
    # EVADE_L 목표선 y=W → ey fallback = y - W
    assert x[1] == pytest.approx(0.12 - config.W)
    assert list(x[4:]) == [0, 1, 0, 0, 0]
    x2 = build_feature_vector(0.5, 0.02, 0.12, "RETURN_TO_L2", 1.3, False)
    assert x2[1] == pytest.approx(0.02) and x2[3] == 0.0 and list(x2[4:]) == [0, 0, 0, 1, 0]


def test_req_stu_03_v_target_is_rule_based():
    assert v_target_label("EVADE_L") == config.V_MAX
    assert v_target_label("SAFE_STOP") == 0.0


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
def test_i4_recorder_does_not_change_episode():
    sc = generate_scenario(100)
    ref = improved_run_episode(sc, mpc=ImprovedMPC(**i4_config.TEACHER_FLAGS))
    mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    rec = SolveRecorder(mpc)
    got = improved_run_episode(generate_scenario(100), mpc=mpc)
    assert got.outcome == ref.outcome and got.total_steps == ref.total_steps
    assert [r["delta_final"] for r in got.logger.rows] == [r["delta_final"] for r in ref.logger.rows]
    samples = pair_calls_with_log(rec.pop(), got.logger.rows)
    assert len(samples) == sum(1 for r in got.logger.rows if r["solver_status"] != "N/A")


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
@pytest.mark.parametrize("seed", [100, 101])
def test_i4_closed_loop_matches_improved_runner_with_mpc(seed):
    ref = improved_run_episode(generate_scenario(seed), mpc=ImprovedMPC(**i4_config.TEACHER_FLAGS))
    got = cl_run_episode(generate_scenario(seed), ImprovedMPC(**i4_config.TEACHER_FLAGS),
                         is_student=False)
    assert got["outcome"] == ref.outcome
    assert got["finish_step"] == ref.finish_step
    assert got["total_steps"] == ref.total_steps
    assert [(s, a, b) for s, a, b in got["transitions"]] == \
        [(t.step, t.from_state, t.to_state) for t in ref.transitions]
    ys_ref = [r["y"] for r in ref.logger.rows]
    ys_got = [row[2] for row in got["traj"]]
    assert ys_got == ys_ref  # 같은 결정론적 루프 → 비트 단위 동일


def _fake_eps(n, rng):
    eps = []
    for k in range(n):
        m = int(rng.integers(0, 10))
        states = ["EVADE_L"] * 40 + ["RETURN_TO_L2"] * 50 + ["KEEP_L1"] * m + ["KEEP_L2"] * 5
        eps.append(dict(key=k, samples=[dict(state=s) for s in states]))
    return eps


def test_i4_stratified_split_fixed_seed_deterministic():
    eps = _fake_eps(100, np.random.default_rng(0))
    v1, _ = stratified_episode_split(eps, i4_config.SPLIT_SEED, 0.15)
    v2, _ = stratified_episode_split(eps, i4_config.SPLIT_SEED, 0.15)
    assert v1 == v2 and len(v1) == 15


def test_i4_norm_stats_zero_std_safe():
    X = np.ones((10, 9), np.float32)
    Y = np.ones((10, 2), np.float32)
    st = compute_norm_stats(X, Y)
    assert all(s == 1.0 for s in st["X_std_safe"]) and all(s == 1.0 for s in st["Y_std_safe"])


# ===== Student v2 (DESIGN_I4 §6, SETTINGS_DECISION §20: ψ [개정], δ_prev [발전]) =====
from thesis_v2.improved.student_i4.features import INPUT_VARIANTS, extend_features


def test_req_stu_02r_variant_order_and_dims():
    assert INPUT_VARIANTS["9"] == FEATURE_NAMES
    assert INPUT_VARIANTS["S10"] == FEATURE_NAMES + ["psi_deg"]
    assert INPUT_VARIANTS["S11"] == FEATURE_NAMES + ["psi_deg", "delta_prev_deg"]
    x9 = build_feature_vector(0.5, None, 0.1, "RETURN_TO_L2", 1.0, True)
    assert extend_features(x9, "9", 3.0, 4.0).shape == (9,)
    x10 = extend_features(x9, "S10", 3.0, 4.0)
    x11 = extend_features(x9, "S11", 3.0, 4.0)
    assert list(x10[9:]) == [3.0] and list(x11[9:]) == [3.0, 4.0]
    assert list(x11[:9]) == list(x9)
    X = extend_features(np.stack([x9, x9]), "S11", np.array([1.0, 2.0]), np.array([5.0, 6.0]))
    assert X.shape == (2, 11) and list(X[:, 10]) == [5.0, 6.0]
    assert StudentPolicy(input_dim=11).eval()(torch.zeros(1, 11)).shape == (1, 2)


def test_req_stu_02r_captured_delta_prev_is_previous_final():
    mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    rec = SolveRecorder(mpc)
    res = improved_run_episode(generate_scenario(100), mpc=mpc)
    samples = pair_calls_with_log(rec.pop(), res.logger.rows)
    finals = [0.0] + [r["delta_final"] for r in res.logger.rows]
    mpc_idx = [i for i, r in enumerate(res.logger.rows) if r["solver_status"] != "N/A"]
    for smp, i in zip(samples, mpc_idx):
        assert smp["delta_prev_deg"] == finals[i]
        assert math.isfinite(smp["psi_deg"])
