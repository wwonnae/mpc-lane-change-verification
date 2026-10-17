"""폐루프(5단계) 단위 테스트 — DESIGN.md §24. P0는 관찰 전용 러너와 완전히 같아야 한다(golden)."""
import pytest

from thesis_v2.anomaly import config as an_config
from thesis_v2.anomaly.closed_loop import run_closed_loop_episode
from thesis_v2.anomaly.detector_a import DetectorA
from thesis_v2.anomaly.faults import FaultSpec
from thesis_v2.anomaly.runner import run_episode as observational_run_episode
from thesis_v2.anomaly.scenarios import generate_anomaly_scenario, estimated_trigger_step
from thesis_v2.improved.mpc import ImprovedMPC

_H_A = 9.210921221467048  # §18 메인 h


def _mpc():
    return ImprovedMPC(**an_config.V2_MPC_FLAGS)


def _onset(sc):
    return max(an_config.WARMUP_STEPS, estimated_trigger_step(sc) - 8)


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
@pytest.mark.parametrize("seed,left", [(3200, False), (3201, False), (3200, True), (3201, True)])
@pytest.mark.parametrize("with_fault", [False, True])
def test_p0_matches_observational_runner(seed, left, with_fault):
    sc = generate_anomaly_scenario(seed, left_obstacle=left)
    fault = None
    if with_fault:
        on = _onset(sc)
        fault = FaultSpec("lidar_freeze" if not left else "left_clear_stuck", onset_step=on,
                          duration_steps=None, value=True if left else None)
    kwargs = dict(mpc=_mpc(), fault=fault, max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)
    ref = observational_run_episode(sc, detector=DetectorA(threshold=_H_A), **kwargs)
    got = run_closed_loop_episode(sc, detector=DetectorA(threshold=_H_A), policy="P0", **kwargs)
    assert got.outcome == ref.outcome
    assert got.total_steps == ref.total_steps
    assert got.first_alarm_step == ref.first_alarm_step
    assert [(t.step, t.from_state, t.to_state) for t in got.transitions] == \
           [(t.step, t.from_state, t.to_state) for t in ref.transitions]
    assert got.policy_action is None


def test_p2_requires_detector():
    sc = generate_anomaly_scenario(3200)
    with pytest.raises(ValueError):
        run_closed_loop_episode(sc, mpc=_mpc(), detector=None, policy="P2",
                                max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)


def test_p1_stops_immediately_on_first_alarm():
    """lidar_freeze는 A의 fg 채널로 100% 탐지된다(§14) — P1은 그 step에 즉시 정지해야 한다."""
    sc = generate_anomaly_scenario(3207)
    on = _onset(sc)
    fault = FaultSpec("lidar_freeze", onset_step=on, duration_steps=None)
    got = run_closed_loop_episode(sc, mpc=_mpc(), fault=fault, detector=DetectorA(threshold=_H_A),
                                  policy="P1", max_steps=an_config.ANOMALY_MAX_STEPS,
                                  terminate_on_departure=True)
    assert got.first_alarm_step is not None
    assert got.policy_action == "stop"
    assert got.outcome in ("탐지 정지", "충돌", "이탈")
    assert got.total_steps == got.first_alarm_step  # 경보 그 step에 바로 끝남
    assert got.finish_step == got.total_steps


def test_p2_ir_stuck_overrides_ey_without_stopping():
    """ir_stuck은 A의 ey 채널로 탐지된다(§14) — P2는 정지하지 않고 ey=None으로 덮어써 계속 달려야 한다."""
    sc = generate_anomaly_scenario(3205)
    on = _onset(sc)
    fault = FaultSpec("ir_stuck", onset_step=on, duration_steps=None, pattern=(1, 0, 0))
    got = run_closed_loop_episode(sc, mpc=_mpc(), fault=fault, detector=DetectorA(threshold=_H_A),
                                  policy="P2", max_steps=an_config.ANOMALY_MAX_STEPS,
                                  terminate_on_departure=True)
    assert got.first_alarm_channel == "ey"
    assert got.policy_action == "override_ey"
    assert got.total_steps > got.first_alarm_step  # 멈추지 않고 계속 진행
    assert got.outcome != "탐지 정지"


def test_p2_right_clear_stuck_overrides_rc_without_stopping():
    sc = generate_anomaly_scenario(3206)
    fault = FaultSpec("right_clear_stuck", onset_step=estimated_trigger_step(sc), duration_steps=None, value=True)
    got = run_closed_loop_episode(sc, mpc=_mpc(), fault=fault, detector=DetectorA(threshold=_H_A),
                                  policy="P2", max_steps=an_config.ANOMALY_MAX_STEPS,
                                  terminate_on_departure=True)
    assert got.first_alarm_channel == "rc"
    assert got.policy_action == "override_rc"
    assert got.total_steps > got.first_alarm_step
    assert got.outcome != "탐지 정지"


def test_p2_left_clear_stuck_overrides_lc_without_stopping():
    sc = generate_anomaly_scenario(3208, left_obstacle=True)
    fault = FaultSpec("left_clear_stuck", onset_step=an_config.WARMUP_STEPS, duration_steps=None, value=True)
    got = run_closed_loop_episode(sc, mpc=_mpc(), fault=fault, detector=DetectorA(threshold=_H_A),
                                  policy="P2", max_steps=an_config.ANOMALY_MAX_STEPS,
                                  terminate_on_departure=True)
    assert got.first_alarm_channel == "lc"
    assert got.policy_action == "override_lc"
    assert got.total_steps > got.first_alarm_step
    assert got.outcome != "탐지 정지"


def test_p2_steer_delay_stops_like_p1():
    """psi 채널(조향 고장)은 P2에서도 즉시 정지(fg·trk·psi는 P1과 같음, §24)."""
    sc = generate_anomaly_scenario(3205)
    on = _onset(sc)
    fault = FaultSpec("steer_delay", onset_step=on, duration_steps=None, magnitude=6.0)
    got = run_closed_loop_episode(sc, mpc=_mpc(), fault=fault, detector=DetectorA(threshold=_H_A),
                                  policy="P2", max_steps=an_config.ANOMALY_MAX_STEPS,
                                  terminate_on_departure=True)
    assert got.first_alarm_channel == "psi"
    assert got.policy_action == "stop"
    assert got.total_steps == got.first_alarm_step


@pytest.mark.usefixtures("i5_time_limit_off")  # 결정론 비교: time_limit off (thesis_v2/conftest.py)
def test_determinism():
    sc = generate_anomaly_scenario(3207)
    on = _onset(sc)
    fault = FaultSpec("lidar_freeze", onset_step=on, duration_steps=None)
    kwargs = dict(mpc=_mpc(), fault=fault, max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True)
    a = run_closed_loop_episode(sc, detector=DetectorA(threshold=_H_A), policy="P1", **kwargs)
    b = run_closed_loop_episode(sc, detector=DetectorA(threshold=_H_A), policy="P1", **kwargs)
    assert (a.outcome, a.total_steps, a.first_alarm_step) == (b.outcome, b.total_steps, b.first_alarm_step)


def test_freeze_ok_requires_clean_and_cl_tag():
    """§24 폐루프 동결 가드: clean + HEAD의 anomaly-cl-freeze 태그만 통과(오프라인 평가 태그는 불통과)."""
    from thesis_v2.anomaly import closed_loop as cl
    assert cl.EVAL_FREEZE_TAG == "anomaly-cl-freeze"
    assert not cl.freeze_ok({"dirty": True, "tag": cl.EVAL_FREEZE_TAG, "commit": "x"})[0]
    assert not cl.freeze_ok({"dirty": False, "tag": None, "commit": "x"})[0]
    assert not cl.freeze_ok({"dirty": False, "tag": "anomaly-eval-freeze", "commit": "x"})[0]
    assert cl.freeze_ok({"dirty": False, "tag": cl.EVAL_FREEZE_TAG, "commit": "x"})[0]


def test_timing_diag_recorded_but_not_in_episode_row():
    """§24-2: MPC 진단값(time_limit_hit·최대 solve ms)은 결과에 기록되지만 episodes CSV 행(HEADER)에는 없다."""
    from thesis_v2.anomaly import closed_loop as cl
    res = cl.run_closed_loop_from_seed("none", 3200, "P0", None)
    assert res.mpc_max_solve_ms > 0.0
    assert res.mpc_time_limit_hits >= 0
    row = cl.episode_row(res, "none", 3200)
    assert list(row) == cl.HEADER
    assert not any("time" in h or "solve" in h for h in cl.HEADER)
    d = cl.diag_row(res, "P0", "none", 3200)
    assert list(d) == cl.DIAG_HEADER


def test_summarize_timing_flags_hit_episodes():
    from thesis_v2.anomaly import closed_loop as cl
    diag = [dict(combo="P0", run="none", seed=1, time_limit_hits=0, max_solve_ms=3.0),
            dict(combo="P1_A", run="ir_stuck", seed=2, time_limit_hits=2, max_solve_ms=46.1)]
    t = cl.summarize_timing(diag)
    assert t["time_limit_hit_total"] == 2
    assert t["time_limit_hit_episodes"] == [dict(combo="P1_A", run="ir_stuck", seed=2, time_limit_hits=2)]
    assert t["max_solve_ms"] == 46.1


def test_diff_csv_text_reports_row_column_values():
    from thesis_v2.anomaly import closed_loop as cl
    saved = "run,seed,outcome,total_steps\nnone,1,성공,100\nnone,2,충돌,50\n"
    recomputed = "run,seed,outcome,total_steps\nnone,1,성공,100\nnone,2,충돌,51\n"
    lines = cl.diff_csv_text(saved, recomputed)
    assert lines == ["행 2 (run=none seed=2) 열 total_steps: 저장본 '50' vs 재계산 '51'"]
    assert cl.diff_csv_text(saved, saved) == []
    assert "행 수 다름" in cl.diff_csv_text(saved, saved + "none,3,성공,9\n")[0]


def _fake_results(tmp_path, monkeypatch, diag_hits=0):
    """compute를 가짜로 바꾸고, 그 가짜 결과로 저장본 폴더를 만든다(시뮬레이션 없이 _check 동작만 확인)."""
    import json as _json
    from thesis_v2.anomaly import closed_loop as cl
    from thesis_v2.anomaly.common import write_csv

    def row(run, seed, steps):
        return dict(run=run, seed=seed, outcome="성공", total_steps=steps, finish_step=steps, onset=None,
                    duration=None, first_alarm_step=None, first_alarm_channel=None, policy_action=None,
                    unnecessary_stop=None)
    rows = {name: [row("none", 1, 100), row("none", 2, 120)] for name in cl.COMBO_NAMES}
    diag = [dict(combo=n, run="none", seed=s, time_limit_hits=diag_hits, max_solve_ms=1.0)
            for n in cl.COMBO_NAMES for s in (1, 2)]
    calls = []

    def fake_compute(seeds, h, m, combos=None):
        names = cl.COMBO_NAMES if combos is None else combos
        calls.append(list(names))
        return ({k: [dict(r) for r in rows[k]] for k in names}, [dict(d) for d in diag if d["combo"] in names])
    monkeypatch.setattr(cl, "compute", fake_compute)
    rows["_calls"] = calls
    (tmp_path / "meta.json").write_text(_json.dumps(dict(seeds=[1, 2], h_by_detector={}, model_dirs={})),
                                        encoding="utf-8")
    for name in cl.COMBO_NAMES:
        write_csv(tmp_path / f"episodes_{name}.csv", cl.HEADER, rows[name])
    summary = cl.summarize({k: rows[k] for k in cl.COMBO_NAMES})
    (tmp_path / "summary.json").write_text(_json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def test_check_match_removes_tmp_and_ignores_diag(tmp_path, monkeypatch, capsys):
    """일치하면 임시 episodes 파일은 지우고 종료 코드 0. time_limit_hit가 있어도(진단) 비교에는 영향 없음."""
    from thesis_v2.anomaly import closed_loop as cl
    _fake_results(tmp_path, monkeypatch, diag_hits=3)
    with pytest.raises(SystemExit) as e:
        cl._check(tmp_path)
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "전체 일치" in out
    assert "time_limit_hit 총합 36" in out
    assert not list(tmp_path.glob("_check_episodes_*.csv"))
    assert not (tmp_path / "_check_summary.json").exists()
    assert (tmp_path / "_check_diag_timing.csv").exists()


def test_check_mismatch_keeps_tmp_and_prints_diff(tmp_path, monkeypatch, capsys):
    from thesis_v2.anomaly import closed_loop as cl
    from thesis_v2.anomaly.common import write_csv
    rows = _fake_results(tmp_path, monkeypatch)
    saved = [dict(r) for r in rows["P0"]]
    saved[1]["total_steps"] = 121
    write_csv(tmp_path / "episodes_P0.csv", cl.HEADER, saved)
    with pytest.raises(SystemExit) as e:
        cl._check(tmp_path)
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "episodes_P0.csv: 불일치" in out
    assert "행 2 (run=none seed=2) 열 total_steps: 저장본 '121' vs 재계산 '120'" in out
    assert (tmp_path / "_check_episodes_P0.csv").exists()
    assert [p.name for p in tmp_path.glob("_check_episodes_*.csv")] == ["_check_episodes_P0.csv"]
    assert "summary.json: 일치" in out


def test_parse_check_only():
    from thesis_v2.anomaly import closed_loop as cl
    assert cl.parse_check_only(None) is None
    assert cl.parse_check_only("P2_A, P0") == ["P0", "P2_A"]  # COMBO_NAMES 순서로 정렬
    for bad in ("P3", "P0,XX", "", ","):
        with pytest.raises(ValueError):
            cl.parse_check_only(bad)


def test_compute_runs_only_selected_combos(monkeypatch):
    from thesis_v2.anomaly import closed_loop as cl
    seen = []
    monkeypatch.setattr(cl, "build_detector", lambda name, h, m: name)
    monkeypatch.setattr(cl, "run_closed_loop_from_seed",
                        lambda run, s, policy, det: seen.append(det) or cl.ClosedLoopResult(
                            s, "x", "성공", 1, 1, [], None, None, None, None))
    rows, diag = cl.compute([1], {}, {}, combos=["P0", "P2_A"])
    assert list(rows) == ["P0", "P2_A"]
    assert set(seen) == {"P0", "P2_A"}
    assert {d["combo"] for d in diag} == {"P0", "P2_A"}
    rows_all, _ = cl.compute([1], {}, {})
    assert list(rows_all) == cl.COMBO_NAMES


def test_check_only_subset_compares_selected(tmp_path, monkeypatch, capsys):
    """부분 확인: 선택 조합만 재계산·비교 — 선택 안 한 조합의 저장본이 달라도 영향 없음."""
    from thesis_v2.anomaly import closed_loop as cl
    from thesis_v2.anomaly.common import write_csv
    rows = _fake_results(tmp_path, monkeypatch)
    broken = [dict(r) for r in rows["P1_A"]]
    broken[0]["total_steps"] = 999
    write_csv(tmp_path / "episodes_P1_A.csv", cl.HEADER, broken)
    with pytest.raises(SystemExit) as e:
        cl._check(tmp_path, combos=["P0", "P2_A"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert rows["_calls"] == [["P0", "P2_A"]]
    assert "episodes_P1_A.csv" not in out
    assert "summary.json[P0,P2_A]: 일치" in out
    assert "부분 확인 P0,P2_A" in out and "선택 조합 일치" in out
    assert "전체 일치" not in out
    assert not list(tmp_path.glob("_check_episodes_*.csv"))


def test_check_only_without_p0_uses_saved_p0_baseline(tmp_path, monkeypatch, capsys):
    from thesis_v2.anomaly import closed_loop as cl
    rows = _fake_results(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as e:
        cl._check(tmp_path, combos=["P2_A"])
    assert e.value.code == 0
    assert rows["_calls"] == [["P2_A"]]
    assert "저장본 episodes_P0.csv" in capsys.readouterr().out


def test_check_only_subset_mismatch(tmp_path, monkeypatch, capsys):
    from thesis_v2.anomaly import closed_loop as cl
    from thesis_v2.anomaly.common import write_csv
    rows = _fake_results(tmp_path, monkeypatch)
    saved = [dict(r) for r in rows["P2_A"]]
    saved[0]["outcome"] = "충돌"
    write_csv(tmp_path / "episodes_P2_A.csv", cl.HEADER, saved)
    with pytest.raises(SystemExit) as e:
        cl._check(tmp_path, combos=["P0", "P2_A"])
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "행 1 (run=none seed=1) 열 outcome: 저장본 '충돌' vs 재계산 '성공'" in out
    assert (tmp_path / "_check_episodes_P2_A.csv").exists()
    assert not (tmp_path / "_check_episodes_P0.csv").exists()


def test_main_check_only_argument_errors(monkeypatch):
    import sys as _sys
    from thesis_v2.anomaly import closed_loop as cl
    for argv in (["closed_loop.py", "--check-only", "P0"],
                 ["closed_loop.py", "--check", "x", "--check-only", "P9"]):
        monkeypatch.setattr(_sys, "argv", argv)
        with pytest.raises(SystemExit) as e:
            cl.main()
        assert e.value.code == 2


def test_main_refuses_eval_seeds_without_freeze(monkeypatch, capsys):
    """--seeds eval은 임계값 로딩·시뮬레이션 전에 거부되어야 한다(git_info를 가짜로 바꿔 저장소 상태와 무관하게 확인)."""
    import sys as _sys
    from thesis_v2.anomaly import closed_loop as cl
    monkeypatch.setattr(cl, "git_info", lambda: {"dirty": True, "tag": cl.EVAL_FREEZE_TAG, "commit": "x"})
    monkeypatch.setattr(_sys, "argv", ["closed_loop.py", "--seeds", "eval"])
    with pytest.raises(SystemExit) as e:
        cl.main()
    assert e.value.code != 0
    assert "거부" in capsys.readouterr().err

    monkeypatch.setattr(cl, "git_info", lambda: {"dirty": False, "tag": "anomaly-eval-freeze", "commit": "x"})
    with pytest.raises(SystemExit) as e:
        cl.main()
    assert e.value.code != 0

    monkeypatch.setattr(cl, "git_info", lambda: {"dirty": False, "tag": cl.EVAL_FREEZE_TAG, "commit": "x"})
    monkeypatch.setattr(_sys, "argv", ["closed_loop.py", "--seeds", "eval", "--a-thresholds", "nope"])
    with pytest.raises(FileNotFoundError):  # 가드 통과 후 임계값 로딩에서 실패 — 거부는 아니었다는 뜻
        cl.main()
