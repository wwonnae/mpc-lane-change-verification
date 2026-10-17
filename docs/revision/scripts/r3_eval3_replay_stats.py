"""
R3 — eval3 v2 MPC·Student S10 결정론적 재생 통계(DESIGN_REVISION §3-1, D5·D9). 분석 전용, 모델·기준 변경 없음.

재생 방식은 사용자 eval3 실행과 같음: `thesis_v2/improved/student_i4/closed_loop.py`의 run_episode, 트랙마다 제어기 인스턴스 1개를
격자/seed 순서대로 재사용(--policy mpc = ImprovedMPC(v2), S10 = StudentLateral). **검증**: paper·S3 두 트랙 모두 에피소드별 outcome이
저장 결과(`eval/closed_loop/closed_loop_eval3_*_{mpc_v2mpc,student_S10}.json`)와 완전히 같을 때만 저장. 하나라도 다르면 중단.

표 17 지표(제출본 legacy_2025/backup/justify_mpc.py compute_smoothness_metrics와 같은 차분 정의, 단 에피소드 경계 차분 제외):
- 조향각 변화율 = |Δδ_final| (deg/step), 속도 변화율 = |Δv| (m/s/step, v = 각 스텝 운동에 쓰인 속도: 첫 스텝 v0, 이후 v_cmd),
- 조향각 jerk = |Δ²δ_final| (deg/step²) — 제출본 표 17 라벨("조향각 Jerk")대로. 제출본 스크립트는 실제로는 속도의 2차 차분(|Δ²v|)을
  계산했으므로 그 값도 `speed_jerk`로 병기(THESIS_REVISION_LOG 2026-09-25 표 13·17 항목).
- 개선율 = (Teacher − Student) / Teacher × 100(제출본 부호 규약: Student가 작으면 +).
- 대상 트랙: eval3 paper(100). S3(900)은 참고로 병기.
추가: 그림 F7·F8용 paper 스텝 데이터(npz), MAE/교사 조향 표준편차 비(VI.5, 교사 = eval3 paper MPC 호출 스텝의 v2 δ).

사용(저장소 루트): python docs/revision/scripts/r3_eval3_replay_stats.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline import config, longitudinal
from thesis_v2.baseline.fsm import FSMState, target_line_y
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.student_i4 import config as i4_config
from thesis_v2.improved.student_i4.closed_loop import StudentLateral, run_episode, scenarios_for
from thesis_v2.improved.student_i4.model import Predictor

V2 = ROOT / "thesis_v2/results/i4_student_v2/20260925_092109_DESKTOP-MDCKRJS"
CL = V2 / "eval/closed_loop"
OUT = ROOT / "docs/revision/data/r3_eval3_stats.json"
NPZ = ROOT / "docs/revision/data/r3_eval3_paper_steps.npz"
CTRL = {"v2mpc": "mpc_v2mpc", "S10": "student_S10"}
TRACKS = {"paper": "eval3_paper", "S3": "eval3_s3"}


def make_ctrl(name):
    if name == "v2mpc":
        return ImprovedMPC(**i4_config.TEACHER_FLAGS), False
    pred = Predictor(V2 / "S10/checkpoints/policy_i4_best.pt", V2 / "S10/normalization_stats.json")
    return StudentLateral(pred), True


def m(a):
    a = np.asarray(a, float)
    return dict(n=int(a.size), mean=float(a.mean()), std=float(a.std()), max=float(a.max())) if a.size else None


def smooth(eps):
    dr, vr, dj, vj, ya, tr, dl, v_all = [], [], [], [], {}, {}, [], []
    for sc, r in eps:
        d = np.array([row[6] for row in r["traj"]])
        st = [row[4] for row in r["traj"]]
        v = np.array([sc.v0] + [longitudinal.compute_v_cmd(FSMState(s)) for s in st[:-1]], float)
        dr += list(np.abs(np.diff(d)))
        vr += list(np.abs(np.diff(v)))
        dj += list(np.abs(np.diff(d, 2)))
        vj += list(np.abs(np.diff(v, 2)))
        dl += list(d)
        v_all += list(v)
        for row in r["traj"]:
            s = row[4]
            ya.setdefault(s, []).append(abs(row[2]))
            tr.setdefault(s, []).append(abs(row[2] - target_line_y(FSMState(s))))
    return dict(steering_rate=m(dr), speed_rate=m(vr), steering_jerk=m(dj), speed_jerk=m(vj), steering=m(dl), speed=m(v_all),
                y_abs_by_state={s: m(v) for s, v in ya.items()},
                track_err_rms_by_state={s: float(np.sqrt(np.mean(np.square(v)))) for s, v in tr.items()})


def main():
    res = {"verification": {}, "by_controller": {}}
    steps = {}
    for name, tag in CTRL.items():
        res["by_controller"][name] = {}
        for track, tname in TRACKS.items():
            ctrl, is_student = make_ctrl(name)
            eps = []
            for key, sc in scenarios_for(tname):
                eps.append((sc, run_episode(sc, ctrl, is_student=is_student)))
            saved = json.load(open(CL / f"closed_loop_{tname}_{tag}.json", encoding="utf-8"))
            got = [r["outcome"] for _, r in eps]
            want = [e["outcome"] for e in saved["per_episode"]]
            ok = got == want
            res["verification"][f"{name}/{track}"] = dict(match=ok, n=len(got))
            if not ok:
                print(f"MISMATCH {name}/{track} — 통계를 저장하지 않고 중단")
                sys.exit(1)
            res["by_controller"][name][track] = smooth(eps)
            if track == "paper":
                for i, (sc, r) in enumerate(eps):
                    steps[f"{name}_ep{i}"] = np.array([[row[0], row[1], row[2], row[3], row[5], row[6],
                                                        ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2", "SAFE_STOP"].index(row[4]),
                                                        1.0 if row[7] == "mpc" else 0.0] for row in r["traj"]], float)
                    steps[f"{name}_ep{i}_meta"] = np.array([sc.seed, sc.v0, sc.y0, sc.obstacles[0].x_near, sc.obstacles[0].x_far,
                                                             sc.obstacles[0].y_lo, sc.obstacles[0].y_hi], float)
            print(f"{name}/{track}: outcome 일치 {len(got)}", flush=True)
    t = res["by_controller"]["v2mpc"]["paper"]
    s = res["by_controller"]["S10"]["paper"]

    def imp(a, b):
        return 100.0 * (a - b) / a if a else None
    res["table17_paper"] = {
        k: dict(teacher=t[k]["mean"], student=s[k]["mean"], improvement_pct=imp(t[k]["mean"], s[k]["mean"]))
        for k in ("steering_rate", "speed_rate", "steering_jerk", "speed_jerk")}
    mae = json.load(open(V2 / "eval3/mae_models.json", encoding="utf-8"))["models"]["S10"]["overall"]["delta_vs_v2"]["mae"]
    smp = np.load(V2 / "eval3/mae_models_samples.npz", allow_pickle=True)
    teacher_std = float(np.std(smp["delta_v2"]))
    res["vi5_mae_over_teacher_std"] = dict(s10_mae=mae, teacher_delta_std=teacher_std, ratio_pct=100 * mae / teacher_std,
                                           note="교사 = eval3 paper MPC 호출 스텝(11,349)의 v2 MPC δ")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    np.savez_compressed(NPZ, columns=np.array(["t", "x", "y", "psi", "delta_desired", "delta_final", "state_idx", "is_policy"]),
                        **steps)
    print(json.dumps(res["table17_paper"], indent=1), res["vi5_mae_over_teacher_std"])


if __name__ == "__main__":
    main()
