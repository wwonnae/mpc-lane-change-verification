"""
이상탐지 확장 보고서용 보충 재현(DESIGN.md §25) — **평가 seed(4000~4099, 5000~5099)는 쓰지 않는다**(assert).

저장된 평가 결과(episodes CSV)에는 FSM 경로·센서 값이 없으므로, 같은 계열의 사례를 평가가 아닌 seed에서 재현해 메커니즘을 확인한다.
제어·탐지 코드는 import만 하고 바꾸지 않는다. step별 값 기록은 이 프로세스 안에서 모듈 함수를 감싸는 방식으로만 한다
(`baseline.sensors.front_gap_noisy`·`left_clear_noisy`, `anomaly.closed_loop.fsm_step`·`vehicle_step` — 감싼 함수는 원래 함수를
그대로 호출하고 반환값을 바꾸지 않는다).

산출: docs/revision/data/anomaly/supplement.json
  leftobs_survey   정상 좌측 장애물(원거리, S4-low) P0 400회(seed 3000~3399): 결과·FSM 경로·회피 계기
  factor           노이즈·거리 분리: 원거리 노이즈 없음 / 근거리(기존 left_obstacle) 노이즈 없음 / 근거리 + S4-low, 각 400회
  seed3173         정상 좌측 장애물 충돌 재현(임계값 대역 seed 3173): 충돌 직전 step 값
  p2_lcs_dev       left_clear_stuck × P2_A, dev seed 3200~3299: 정지 위치·자세·간격
  p2_rcs_dev       right_clear_stuck × P0/P2_A, dev seed 3200~3209: FSM 경로
사용(저장소 루트, .venv): python docs/revision/scripts/anomaly_supplement.py   (약 1분)
"""
import json
import math
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from thesis_v2.anomaly import closed_loop as cl  # noqa: E402
from thesis_v2.anomaly import config as ac  # noqa: E402
from thesis_v2.anomaly.common import git_info  # noqa: E402
from thesis_v2.anomaly.scenarios import generate_anomaly_scenario  # noqa: E402
from thesis_v2.baseline import config as bc  # noqa: E402
from thesis_v2.baseline import sensors as bs  # noqa: E402
from thesis_v2.baseline.world import generate_left_obstacle_scenario  # noqa: E402
from thesis_v2.improved.mpc import ImprovedMPC  # noqa: E402

OUT = ROOT / "docs/revision/data/anomaly/supplement.json"
CL_EVAL = ROOT / "thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval"
EVAL_SEEDS = set(ac.SEEDS_OFFLINE_EVAL) | set(ac.SEEDS_CLOSED_LOOP)

# ---- step 기록용 감싸기(반환값 불변) ----
LOG, CUR, LAST = [], {}, {}
_fg, _lc = bs.front_gap_noisy, bs.left_clear_noisy
_fsm, _vs = cl.fsm_step, cl.vehicle_step


def _fg_w(state, obstacles, rng, sigma):
    v = _fg(state, obstacles, rng, sigma)
    CUR.update(fg=v, fg_clean=bs.front_gap(state, obstacles))
    return v


def _lc_w(state, obstacles, rng, p):
    v = _lc(state, obstacles, rng, p)
    CUR.update(lc=v, lc_clean=bs.left_clear(state, obstacles))
    return v


def _fsm_w(fsm, sens, y, psi_deg, t):
    new = _fsm(fsm, sens, y, psi_deg, t)
    CUR.update(before=fsm.state.value, after=new.state.value)
    LOG.append(dict(CUR))
    return new


def _vs_w(state, delta, v, dt):
    n = _vs(state, delta, v, dt)
    LAST.update(prev=state, veh=n, v_cmd=v)
    return n


bs.front_gap_noisy, bs.left_clear_noisy = _fg_w, _lc_w
cl.fsm_step, cl.vehicle_step = _fsm_w, _vs_w


def _check(seed):
    assert seed not in EVAL_SEEDS, f"평가 seed {seed} 사용 금지"


def _path(r):
    if not r.transitions:
        return "KEEP_L2"
    return "->".join([r.transitions[0].from_state] + [t.to_state for t in r.transitions])


def _episode(sc, seed, noisy):
    _check(seed)
    LOG.clear()
    prof = bs.NOISE_PROFILES[ac.NORMAL_NOISE_PROFILE]
    return cl.run_closed_loop_episode(
        sc, mpc=ImprovedMPC(**ac.V2_MPC_FLAGS), policy="P0",
        noise_profile=prof if noisy else None,
        noise_rng=np.random.default_rng((seed, ac.NOISE_STREAM_ID)) if noisy else None,
        max_steps=ac.ANOMALY_MAX_STEPS, terminate_on_departure=True)


def _evade_cause():
    """첫 KEEP_L2→EVADE_L step에서 회피 조건(front_gap<G_TRIG 그리고 left_clear)을 만든 원인."""
    for e in LOG:
        if e["before"] == "KEEP_L2" and e["after"] == "EVADE_L":
            if not e["lc_clean"]:
                return "lc_flip"           # 참값 left_clear=False인데 S4 오판정으로 True
            if e["fg_clean"] >= bc.G_TRIG:
                return "fg_noise"          # 참값 left_clear=True(윈도우 진입 전)인데 front_gap 측정 노이즈로 G_TRIG 아래
            return "other"
    return None


def leftobs_survey(seeds):
    outcomes, paths, collisions = Counter(), Counter(), []
    for s in seeds:
        r = _episode(generate_anomaly_scenario(s, left_obstacle=True), s, True)
        outcomes[r.outcome] += 1
        key = f"{r.outcome}|{_path(r)}|{_evade_cause() or '-'}"
        paths[key] += 1
        if r.outcome == "충돌":
            collisions.append(s)
    evaded = sum(v for k, v in paths.items() if "EVADE_L" in k.split("|")[1])
    return dict(seeds=[seeds[0], seeds[-1]], n=len(seeds), outcomes=dict(outcomes), paths=dict(paths),
                evaded=evaded, collision_seeds=collisions)


def factor(seeds):
    cases = {
        "far_noisefree": (lambda s: generate_anomaly_scenario(s, left_obstacle=True), False),
        "near_noisefree": (generate_left_obstacle_scenario, False),
        "near_s4low": (generate_left_obstacle_scenario, True),
    }
    out = {}
    for name, (gen, noisy) in cases.items():
        oc, ev = Counter(), 0
        for s in seeds:
            r = _episode(gen(s), s, noisy)
            oc[r.outcome] += 1
            ev += "EVADE_L" in _path(r)
        out[name] = dict(n=len(seeds), outcomes=dict(oc), evaded=ev)
    return out


def seed3173():
    s = 3173
    r = _episode(generate_anomaly_scenario(s, left_obstacle=True), s, True)
    trig = next(i for i, e in enumerate(LOG) if e["after"] == "EVADE_L")
    steps = []
    for i in range(trig - 1, len(LOG)):
        e = LOG[i]
        steps.append(dict(step=i + 1, before=e["before"], after=e["after"], fg=round(e["fg"], 3),
                          fg_clean=round(e["fg_clean"], 3), lc=int(e["lc"]), lc_clean=int(e["lc_clean"])))
    last_move = math.hypot(LAST["veh"].x - LAST["prev"].x, LAST["veh"].y - LAST["prev"].y)
    psi_last = [round(math.degrees(x), 1) for x in (LAST["prev"].psi, LAST["veh"].psi)]
    return dict(seed=s, outcome=r.outcome, total_steps=r.total_steps, transitions=[(t.step, t.from_state, t.to_state)
                for t in r.transitions], steps=steps, cooldown_s=bc.COOLDOWN, cooldown_steps=round(bc.COOLDOWN / bc.DT),
                last_step_v_cmd=LAST["v_cmd"], last_step_move_m=round(last_move, 4), last_step_psi_deg=psi_last)


def p2_lcs_dev(meta):
    det = cl.build_detector("P2_A", meta["h_by_detector"], meta["model_dirs"])
    oc, frm, ys, psis, gaps = Counter(), Counter(), [], [], []
    for s in ac.SEEDS_FAULT_DEV:
        _check(s)
        r = cl.run_closed_loop_from_seed("left_clear_stuck", s, "P2", det)
        oc[r.outcome] += 1
        if r.outcome != "SAFE_STOP":
            continue
        v = LAST["veh"]
        sc = generate_anomaly_scenario(s, left_obstacle=True)
        frm[[t.from_state for t in r.transitions if t.to_state == "SAFE_STOP"][0]] += 1
        ys.append(v.y)
        psis.append(math.degrees(v.psi))
        gaps.append(bs.front_gap(v, sc.obstacles))

    def mm(x, nd):
        return [round(min(x), nd), round(st.median(x), nd), round(max(x), nd)]
    return dict(seeds=[ac.SEEDS_FAULT_DEV[0], ac.SEEDS_FAULT_DEV[-1]], outcomes=dict(oc), safe_stop_from=dict(frm),
                y_min_med_max=mm(ys, 3), psi_deg_min_med_max=mm(psis, 1), clean_gap_after_min_med_max=mm(gaps, 3),
                y_ge_015=sum(y >= 0.15 for y in ys), n_safe_stop=len(ys))


def p2_rcs_dev(meta):
    det = cl.build_detector("P2_A", meta["h_by_detector"], meta["model_dirs"])
    seeds = list(ac.SEEDS_FAULT_DEV)[:10]
    res = {"P0": Counter(), "P2": Counter()}
    for s in seeds:
        _check(s)
        for pol, d in (("P0", None), ("P2", det)):
            r = cl.run_closed_loop_from_seed("right_clear_stuck", s, pol, d)
            res[pol][f"{r.outcome}|{_path(r)}|{r.total_steps if pol == 'P2' else ''}"] += 1
    return dict(seeds=[seeds[0], seeds[-1]], P0=dict(res["P0"]), P2=dict(res["P2"]))


def main():
    meta = json.loads((CL_EVAL / "meta.json").read_text(encoding="utf-8"))
    seeds = [s for s in range(3000, 3400)]
    for s in seeds:
        _check(s)
    out = dict(
        purpose="이상탐지 확장 보고서 보충 재현(DESIGN.md §25) — 평가 seed 미사용",
        git=git_info(), thresholds_from=str(CL_EVAL.relative_to(ROOT)).replace("\\", "/"),
        leftobs_survey=leftobs_survey(seeds), factor=factor(seeds), seed3173=seed3173(),
        p2_lcs_dev=p2_lcs_dev(meta), p2_rcs_dev=p2_rcs_dev(meta))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved:", OUT.relative_to(ROOT))
    print(json.dumps({k: out[k] for k in ("leftobs_survey", "factor")}, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
