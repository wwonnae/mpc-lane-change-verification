from thesis_v2.baseline import config


def test_fixed_params_match_claude_md():
    assert config.N == 15
    assert config.DT == 0.05
    assert config.QY == 100.0
    assert config.QPSI == 25.0
    assert config.RDELTA == 2.0
    assert config.RDDELTA == 5.0
    assert config.DELTA_MAX_DEG == 25.0
    assert config.DELTA_RATE_MAX_DEGPS == 200.0
    assert config.G_TRIG == 1.2
    assert config.G_SAFE_MIN == 0.20
    assert config.COOLDOWN == 0.3
    assert config.W == 0.30
    assert config.L == 0.20
    assert config.B == 0.15
