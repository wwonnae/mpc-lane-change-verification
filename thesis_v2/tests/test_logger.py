import numpy as np

from thesis_v2.baseline.logger import STEP_FIELDS, StepLogger


def _sample_row():
    return dict(
        t=0.05, x=0.1, y=0.0, psi=0.0, v=0.4,
        delta_mpc_raw=1.0, delta_after_rate=1.0, delta_final=1.0, v_cmd=0.4,
        state="KEEP_L2", front_gap=1.0, left_clear=True, right_clear=True,
        ir_pattern=(0, 1, 0), ey_line=0.0, solver_status="solved", fallback_used=False,
        t_mpc_solve_ms=0.5, t_step_ms=0.6, rate_limit_active=False, clip_active=False,
    )


def test_logger_schema_has_all_fields():
    logger = StepLogger()
    logger.log(**_sample_row())
    assert logger.has_all_fields()
    assert set(logger.rows[0].keys()) == set(STEP_FIELDS)


def test_logger_save_npz_roundtrip(tmp_path):
    logger = StepLogger()
    logger.log(**_sample_row())
    path = tmp_path / "steps.npz"
    logger.save_npz(path)
    data = np.load(path, allow_pickle=True)
    for f in STEP_FIELDS:
        assert f in data.files
