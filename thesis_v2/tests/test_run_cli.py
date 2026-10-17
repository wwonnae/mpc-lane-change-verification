import json
import sys

from thesis_v2.baseline.run import main


def test_power_mode_confirmed_flag_reaches_env_json(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    argv = [
        "run.py", "--scenario", "paper", "--seeds", "0",
        "--out", str(out_dir), "--power-mode-confirmed",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    main()

    env = json.loads((out_dir / "env.json").read_text(encoding="utf-8"))
    assert env["power"]["power_mode_user_confirmed"] is True
    assert env["power"]["power_mode_user_confirmed_at"] is not None


def test_without_flag_defaults_to_not_confirmed(tmp_path, monkeypatch):
    out_dir = tmp_path / "out2"
    argv = ["run.py", "--scenario", "paper", "--seeds", "0", "--out", str(out_dir)]
    monkeypatch.setattr(sys, "argv", argv)
    main()

    env = json.loads((out_dir / "env.json").read_text(encoding="utf-8"))
    assert env["power"]["power_mode_user_confirmed"] is False
