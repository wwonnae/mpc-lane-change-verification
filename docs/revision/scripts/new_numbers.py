"""
기술보고서 신설 절(VI.4~VI.7, 부록 등)에 필요한 **새 수치** 행(제출본에 대응 값이 없는 수치). 모두 저장된 결과 파일에서 직접 읽어 포맷하며
새 측정·재학습은 하지 않는다. make_revision_numbers.py가 기존 256행 뒤에 붙인다(기존 행 번호·값 불변).
행 키(no 열)는 "N:<이름>" — 본문은 {{n:<이름>}}으로 참조(build_report.py).
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline import config as bcfg  # noqa: E402
from thesis_v2.baseline.summary import wilson_ci  # noqa: E402
from thesis_v2.improved import config as icfg  # noqa: E402

RES = ROOT / "thesis_v2/results"
EV1 = RES / "eval_final/all_eval_summary.json"
EV2 = RES / "eval_v2/20260924_214446_DESKTOP-MDCKRJS/all_eval_v2_summary.json"
I4 = RES / "i4_student/20260925_075822_DESKTOP-MDCKRJS"
V2 = RES / "i4_student_v2/20260925_092109_DESKTOP-MDCKRJS"
FAIL = ROOT / "repro/2c_analysis/out/i4_closed_loop_failure/analysis.json"
OBS = ROOT / "repro/2c_analysis/out/i4_input_observability/observability.json"
J3 = ROOT / "repro/2c_analysis/out/i4_eval3_judgement/eval3_judgement.json"
R2 = ROOT / "docs/revision/data/r2_timing_supplement/r2_timing.json"
TV3 = RES / "timing_v3"


def rel(p):
    return str(Path(p).relative_to(ROOT)).replace("\\", "/")


def f(x, n=3):
    return f"{x:.{n}f}".replace("-", "−")


def ci(k, n):
    c = wilson_ci(k, n)
    return f"{k}/{n} (95% CI {c['lo'] * 100:.1f}~{c['hi'] * 100:.1f}%)"


def rng(lo, hi, unit="배"):
    a, b = f"{lo:.1f}", f"{hi:.1f}"
    return f"{a}{unit}(두 실행 모두)" if a == b else f"{a}~{b}{unit}"


def pexp(p):
    """p값 표기: 1e-4 미만은 지수 표기."""
    if p >= 1e-4:
        return f"{p:.4f}"
    e = int(math.floor(math.log10(p)))
    m = p / 10 ** e
    return f"{m:.1f}×10^{e}".replace("-", "−")


def build():
    rows = []

    def add(key, chap, item, val, src, cond, note=""):
        rows.append([f"N:{key}", "—", chap, item, "—", val, rel(src) if isinstance(src, Path) else src, cond, "신설", "신규",
                     "확정", note, chap, "해당 없음(신규 수치)"])

    # ---------------- 공통·III: 재구현 규모 ----------------
    spec = (ROOT / "repro/docs/SPEC.md").read_text(encoding="utf-8")
    n_req = len(set(re.findall(r"^\| (REQ-[A-Z]+-[0-9]+[a-z]?r?) \|", spec, flags=re.M)))
    add("n_req", "III.3", "요구사항 ID 수(SPEC.md 표 행)", str(n_req), ROOT / "repro/docs/SPEC.md", "-")
    try:
        out = subprocess.run([sys.executable, "-m", "pytest", "thesis_v2/tests", "--collect-only", "-q"], cwd=ROOT,
                             capture_output=True, text=True, timeout=300).stdout
        n_tests = int(re.search(r"(\d+) tests? collected", out).group(1))
    except Exception:
        n_tests = None
    add("n_tests", "III.3", "단위 테스트 수(pytest 수집)", str(n_tests), "thesis_v2/tests (pytest --collect-only)", "-")
    add("n_revision_items", "부록 A", "[개정] 건수", "3", ROOT / "repro/docs/SETTINGS_DECISION.md", "-",
        "RETURN 임계값, 초기 y 절단, Student ψ 입력(§20)")
    # ---------------- IV: [개정] 계산 근거 ----------------
    step_min = 0.5 * math.sin(math.radians(20)) * bcfg.DT
    add("rev1_need", "IV.1", "[개정]1 필요 이동량(0.20−0.15)", f"{0.20 - bcfg.POSITION_CONSTRAINTS['KEEP_L2'][1]:.2f} m",
        ROOT / "repro/docs/FEASIBILITY_CHECK.md", "-")
    add("rev1_step", "IV.1", "[개정]1 한 스텝 최대 이동량(v·sin20°·dt ~ 조향 여유 가산)", f"{step_min:.4f}~0.0125 m",
        ROOT / "repro/docs/THESIS_REVISION_LOG.md", "-", "v=0.5, dt=0.05")
    p_out = 2 * (1 - 0.5 * (1 + math.erf(3 / math.sqrt(2))))
    add("rev2_prob", "III.2", "[개정]2 절단 없는 N(0,0.05²)의 |y0|>0.15 확률", f"{100 * p_out:.2f}%", "해석 계산(3σ 양측)", "-")
    add("margin_i2p", "VI.6", "I2' 장애물 마진(B/2 + L·sin20°)", f(icfg.MARGIN_I2_PRIME) + " m", ROOT / "thesis_v2/improved/config.py", "-")
    add("rho_i1b", "VI.6", "I1b 소프트 제약 벌점 ρ", f"{icfg.SOFT_CONSTRAINT_PENALTY:,.0f}", ROOT / "thesis_v2/improved/config.py", "-")
    add("i5_cap", "VI.6", "I5 반복 상한", str(icfg.I5_MAX_ITER), ROOT / "thesis_v2/improved/config.py", "-", "시간 예산 5 ms / 반복당 p99 0.00514 ms")
    add("i5_budget", "VI.6", "I5 시간 예산 후보", "5 / 10 / 20 / 30 ms", ROOT / "repro/docs/DESIGN_IMPROVED_V2.md", "-")
    add("rate_step", "VI.6", "I1 조향 변화율 하드 제약", f"{bcfg.DELTA_RATE_MAX_PER_STEP_DEG:.0f}°/step", ROOT / "thesis_v2/baseline/config.py", "-")
    add("front_gap_evade_mean", "VI.2", "EVADE_L 진입 시 front_gap 평균±표준편차 / 최소",
        "", ROOT / "docs/revision/data/r1_baseline_e2_stats.json", "E2")
    r1 = json.load(open(ROOT / "docs/revision/data/r1_baseline_e2_stats.json", encoding="utf-8"))
    ev = r1["front_gap_at_evade_entry"]
    rows[-1][5] = f"{f(ev['mean'])} ± {f(ev['std'])} m / 최소 {f(ev['min'])} m"
    add("e2_n_steps", "VI.2", "E2 baseline 전체 스텝 수", f"{r1['n_steps']:,}", ROOT / "docs/revision/data/r1_baseline_e2_stats.json", "E2")
    # ---------------- VI.5·VI.6: E1·E2 폐루프 ----------------
    e1 = json.load(open(EV1, encoding="utf-8"))
    e2 = json.load(open(EV2, encoding="utf-8"))["new_eval"]
    add("e1_paper_base", "VI.6", "E1 paper baseline 충돌", e1["paper"]["baseline"]["collision_rate_formatted"], EV1, "E1")
    add("e1_paper_v1", "VI.6", "E1 paper v1 충돌", e1["paper"]["improved"]["collision_rate_formatted"], EV1, "E1")
    add("e1_s3_base", "VI.6", "E1 S3(961) baseline 실패", ci(e1["S3"]["n_fail_baseline"], e1["S3"]["n_total"]), EV1, "E1")
    add("e1_s3_v1", "VI.6", "E1 S3(961) v1 실패", ci(e1["S3"]["n_fail_improved"], e1["S3"]["n_total"]), EV1, "E1")
    add("e1_s6m15_base", "VI.5", "E1 S6 ψ0=−15° baseline 충돌", e1["S6"]["psi0_-15deg"]["baseline"]["collision_rate_formatted"], EV1, "E1")
    add("e1_s7w20_base", "VI.5", "E1 S7a 폭 0.20 m baseline 충돌", e1["S7a"]["width_0.200m"]["baseline"]["collision_rate_formatted"], EV1, "E1")
    groups = ("paper", "left_obstacle", "S4", "S5", "S6", "S7a", "S7b")
    for g in groups:
        for v in ("baseline", "v1", "v2"):
            if g in ("paper", "left_obstacle"):
                k, n = e2[g][v]["n_collision"], e2[g][v]["n_episodes"]
            else:
                k = sum(e2[g][s][v]["n_collision"] for s in e2[g])
                n = sum(e2[g][s][v]["n_episodes"] for s in e2[g])
            add(f"e2_{g}_{v}", "VI.5", f"E2 {g} {v} 충돌", ci(k, n), EV2, "E2")
    # 쌍대 정확검정(McNemar, 불일치 쌍의 이항검정) — 같은 seed로 실행한 버전 비교(검증 4의 8·9번 정정, 2026-09-26)
    from math import comb

    def mcn_p(a, b):
        n, k = a + b, min(a, b)
        return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
    pp = e2["paper"]["paired_baseline_vs_v2"]
    add("e2_paper_mcn", "VI.6", "E2 paper baseline vs v2 성공 쌍대 정확검정(baseline만 실패/v2만 실패, p)",
        f"{pp['a_fail_b_success']}/{pp['a_success_b_fail']}, p={pexp(mcn_p(pp['a_fail_b_success'], pp['a_success_b_fail']))}", EV2, "E2")
    tot = {}
    for v in ("baseline", "v1", "v2"):
        k = n = 0
        for g in groups:
            if g in ("paper", "left_obstacle"):
                k += e2[g][v]["n_collision"]; n += e2[g][v]["n_episodes"]
            else:
                k += sum(e2[g][s_][v]["n_collision"] for s_ in e2[g]); n += sum(e2[g][s_][v]["n_episodes"] for s_ in e2[g])
        tot[v] = (k, n)
    assert tot["v1"][0] == 0 and tot["v2"][0] == 0, "개선판 충돌이 0이 아님 — 합산 검정 식 재검토"
    add("e2_coll_pool_base", "VI.6", "E2 전 조건(paper·left_obstacle·S4~S7b) 합산 baseline 충돌", ci(*tot["baseline"]), EV2, "E2")
    add("e2_coll_pool_v2", "VI.6", "E2 전 조건 합산 v2 충돌", ci(*tot["v2"]), EV2, "E2")
    add("e2_coll_pool_p", "VI.6", "E2 전 조건 합산 충돌 쌍대 정확검정 p(baseline vs v2, 개선판 충돌 0이므로 불일치 쌍 = baseline 충돌 수)",
        f"p={pexp(mcn_p(tot['baseline'][0], 0))}", EV2, "E2")
    add("e1_paper_mcn", "VI.6", "E1 paper baseline vs v1 충돌 쌍대 정확검정 p(개선판 충돌 0)",
        f"p={pexp(mcn_p(e1['paper']['baseline']['n_collision'], e1['paper']['improved']['n_collision']))}", EV1, "E1")
    ss = [e2["left_obstacle"][f"safe_stop_rate_{v}"] for v in ("baseline", "v1", "v2")]
    assert len(set(ss)) == 1, "left_obstacle SAFE_STOP 비율이 버전마다 다름 — '공통' 표기 불가"
    add("e2_left_safestop", "VI.5", "E2 left_obstacle SAFE_STOP(세 버전 공통, 값 일치 확인)", ss[0], EV2, "E2")
    add("e2_paper_v2_success", "VI.6", "E2 paper v2 성공", e2["paper"]["v2"]["success_rate_formatted"], EV2, "E2")
    add("e2_paper_base_success", "VI.2", "E2 paper baseline 성공", e2["paper"]["baseline"]["success_rate_formatted"], EV2, "E2")
    for v in ("v1", "v2"):
        pv = e2["paper"][v]
        add(f"e2_{v}_constraints", "VI.6", f"E2 paper {v} MPC 호출 / 반복 상한 도달 / 폐기(fallback) / 엄밀 기준 조향 위반",
            f"{pv['n_mpc_calls']:,} / {pv['max_iter_count']} / {pv['fallback_count']} / {pv['steering_angle_violation_rigorous_count']}", EV2, "E2")
    s3 = e2["S3"]
    for v in ("baseline", "v1", "v2"):
        add(f"e2_s3_{v}", "VI.5", f"E2 S3(900) {v} 실패", ci(s3[f"n_fail_{v}"], s3["n_total"]), EV2, "E2")
    # 물리 한계 대비 baseline 실패 경계 여유(E2 격자, 저장 결과에서 계산)
    g = json.load(open(EV2.parent / "s3_grid_new_baseline.json", encoding="utf-8"))
    import numpy as np
    fg = np.round(np.arange(0.5025, 1.9975 + 1e-4, 0.05), 4)
    y0 = np.round(np.arange(-0.1475, 0.1475 + 1e-4, 0.01), 4)
    lim = s3["physical_limit_curve"]
    margins = []
    for j, yy in enumerate(y0):
        fails = [fg[i] for i in range(len(fg)) if g[i][j] != "성공"]
        if fails:
            margins.append(max(fails) - lim[str(float(yy))])
    add("e2_s3_margin", "VI.5", "E2 baseline 실패 경계 − 물리 한계(실패가 있는 y0 열 평균, 범위)",
        f"{f(np.mean(margins))} m ({f(min(margins))}~{f(max(margins))} m, {len(margins)}열)", EV2.parent / "s3_grid_new_baseline.json", "E2")
    # 계산시간(timing_v3, 공식)
    for tag in ("baseline", "v1", "v2"):
        t = json.load(open(next(TV3.glob(f"*_{tag}/timing_{tag}.json")), encoding="utf-8"))
        for sc in ("paper", "left_obstacle", "S6_psi-15"):
            m = t[sc]["mpc_solve_ms"]
            add(f"tv3_{tag}_{sc}", "VI.6", f"timing_v3 {tag} {sc} MPC solve p99 / max (ms)", f"{f(m['p99'])} / {f(m['max'])}",
                next(TV3.glob(f"*_{tag}/timing_{tag}.json")), "T0-H1")
            it = t[sc]["iterations"]
            add(f"tv3_{tag}_{sc}_iter", "VI.6", f"timing_v3 {tag} {sc} 반복 횟수 p50 / p99 / max",
                f"{it['p50']:.0f} / {it['p99']:.0f} / {it['max']:.0f}", next(TV3.glob(f"*_{tag}/timing_{tag}.json")), "T0-H1")
    # ---------------- VI.4: 9입력 Student(I4) ----------------
    tl = json.load(open(I4 / "train_log.json", encoding="utf-8"))
    ds = json.load(open(I4 / "dataset/dataset_summary.json", encoding="utf-8"))
    add("i4_samples", "V.1", "학습 샘플(dev, MPC 호출 스텝)", f"{ds['n_samples']:,}", I4 / "dataset/dataset_summary.json", "D")
    for st, n in ds["state_counts_total"].items():
        add(f"i4_n_{st}", "V.1", f"학습 샘플 {st}", f"{n:,}", I4 / "dataset/dataset_summary.json", "D")
    add("i4_train_val", "V.3", "학습/검증 샘플(에피소드 단위 계층 분할)",
        f"{ds['split']['total']['train']['n']:,} / {ds['split']['total']['val']['n']:,}", I4 / "dataset/dataset_summary.json", "D")
    add("i4_best", "VI.4", "9입력 선택 epoch / 검증 손실", f"{tl['best_epoch']} / {tl['best_val_loss']:.5f}", I4 / "train_log.json", "D")
    mae = json.load(open(I4 / "eval/mae.json", encoding="utf-8"))
    add("i4_mae_all", "VI.4", "9입력 개루프 δ MAE vs v2 (E2)", f(mae["overall"]["delta_vs_v2"]["mae"], 2) + "°", I4 / "eval/mae.json", "E2")
    for st, b in mae["by_state"].items():
        add(f"i4_mae_{st}", "VI.4", f"9입력 개루프 δ MAE vs v2 {st}", f(b["delta_vs_v2"]["mae"], 2) + "°", I4 / "eval/mae.json", "E2")
    for tr, fn in (("paper", "closed_loop_paper_student.json"), ("s3", "closed_loop_s3_student.json")):
        c = json.load(open(I4 / "eval/closed_loop" / fn, encoding="utf-8"))
        oc = c["outcomes"]
        n = c["n_episodes"]
        add(f"i4_cl_{tr}_succ", "VI.4", f"9입력 폐루프 {tr} 성공", ci(oc.get("성공", 0), n), I4 / "eval/closed_loop" / fn, "E2")
        add(f"i4_cl_{tr}_coll", "VI.4", f"9입력 폐루프 {tr} 충돌", ci(oc.get("충돌", 0), n), I4 / "eval/closed_loop" / fn, "E2")
        add(f"i4_cl_{tr}_to", "VI.4", f"9입력 폐루프 {tr} 타임아웃", f"{oc.get('타임아웃', 0)}/{n}", I4 / "eval/closed_loop" / fn, "E2")
    fa = json.load(open(FAIL, encoding="utf-8"))
    for tr in ("paper", "s3"):
        se = fa[tr]["shift_and_error"]
        add(f"fa_{tr}_ood_state", "VI.4", f"9입력 폐루프 {tr} 상태 조건부 |z|>3 비율", f"{100 * se['state_cond_z3']:.1f}%", FAIL, "E2")
        add(f"fa_{tr}_err02", "VI.4", f"9입력 폐루프 {tr} 처음 2초 |Student δ − v2 δ| MAE", f(se["err_by_time"]["0-2s"]["mae"], 1) + "°", FAIL, "E2")
        ret = fa[tr]["timeouts"]
        add(f"fa_{tr}_to_ret", "VI.4", f"9입력 {tr} 타임아웃 중 RETURN_TO_L2에서 멈춘 수", f"{ret['final_state'].get('RETURN_TO_L2', 0)}/{ret['n']}", FAIL, "E2")
        iv = fa[tr]["intervention"]["ALL_student_calls"]
        add(f"fa_{tr}_over25", "VI.4", f"9입력 {tr} 원출력 >25° 비율 / 최대", f"{100 * iv['student_raw_over_25']:.2f}% / {iv['student_raw_max_abs']:.1f}°", FAIL, "E2")
    add("fa_train_ood", "VI.4", "학습 데이터 자신의 상태 조건부 |z|>3 비율", f"{100 * fa['train_baseline_ood']['state_cond_z3']:.1f}%", FAIL, "D")
    cr = fa["paper"]["shift_and_error"]["corr_diff_vs_psi"]
    add("fa_corr_psi", "VI.4", "폐루프 오차(Student−v2)와 ψ 상관 r(EVADE_L·KEEP_L1·RETURN_TO_L2, paper)",
        f"{min(cr['EVADE_L'], cr['KEEP_L1'], cr['RETURN_TO_L2']):.2f}~{max(cr['EVADE_L'], cr['KEEP_L1'], cr['RETURN_TO_L2']):.2f}", FAIL, "E2")
    add("fa_corr_psi_keepl2", "VI.4", "폐루프 오차(Student−v2)와 ψ 상관 r, KEEP_L2(paper)", f"{cr['KEEP_L2']:.2f}", FAIL, "E2")
    ct = json.load(open(ROOT / "repro/2c_analysis/out/c_track_37_rdelta_diffstyle_retest.json", encoding="utf-8"))
    per = [r["diff_after_deg"] for r in ct["results"] if not r["vanished"]]
    assert ct["n_persisted"] == len(per)
    add("ctrack_resid", "IV.2", "C트랙 target_y=0 잔여 격자: rΔδ를 차분형으로 바꾼 뒤 잔존 / 전체, 잔차 범위",
        f"{ct['n_persisted']}/{ct['n_total']}건 잔존(잔차 {min(per):.1f}~{max(per):.1f}°)", ROOT / "repro/2c_analysis/out/c_track_37_rdelta_diffstyle_retest.json", "C트랙(1080 격자)")
    add("fa_psi_return", "VI.4", "RETURN_TO_L2 평균 |ψ| v2 자기 궤적 / 9입력 Student 궤적(paper)",
        f"{fa['paper']['v2_own_trajectory_psi_abs_mean_by_state']['RETURN_TO_L2']:.1f}° / {fa['paper']['shift_and_error']['psi_abs_mean_by_state']['RETURN_TO_L2']:.1f}°", FAIL, "E2")
    # ---------------- VI.7: 관측성·S10/S11·eval3 ----------------
    ob = json.load(open(OBS, encoding="utf-8"))
    for t in ("baseline", "v2"):
        b = ob[t]["binning"]
        add(f"obs_{t}_9", "VI.7", f"관측성({t} 교사) 9입력 격자 내 δ 분산 비율(칸 내 σ)",
            f"{100 * b['9dim(REQ-STU-02)']['ALL']['unexplained_share']:.1f}% ({b['9dim(REQ-STU-02)']['ALL']['within_std_deg']:.2f}°)", OBS, "D")
        add(f"obs_{t}_psi", "VI.7", f"관측성({t} 교사) +ψ", f"{100 * b['9dim+psi']['ALL']['unexplained_share']:.1f}%", OBS, "D")
        add(f"obs_{t}_psipl", "VI.7", f"관측성({t} 교사) +ψ 위약", f"{100 * b['9dim+psi_PLACEBO']['ALL']['unexplained_share']:.1f}%", OBS, "D")
        add(f"obs_{t}_psidp", "VI.7", f"관측성({t} 교사) +ψ+δ_prev", f"{100 * b['9dim+psi+delta_prev']['ALL']['unexplained_share']:.1f}%", OBS, "D")
    an = ob["analytic"]
    add("obs_psi_demo", "VI.7", "논문 MPC δ0: ψ0 −30/−15/0/+15/+30°(9입력 고정)",
        " / ".join(f"{x['baseline_delta_deg']:+.1f}°".replace("-", "−") for x in an["psi_dependence"]), OBS, "-")
    add("obs_dprev_demo", "VI.7", "v2 MPC δ0: δ_prev −20/−10/0/+10/+20°",
        " / ".join(f"{x['v2_delta_deg']:+.1f}°".replace("-", "−") for x in an["delta_prev_dependence"]), OBS, "-")
    for m in ("S10", "S11"):
        t = json.load(open(V2 / m / "train_log.json", encoding="utf-8"))
        add(f"{m}_best", "VI.7", f"{m} 선택 epoch / 검증 손실", f"{t['best_epoch']} / {t['best_val_loss']:.5f}", V2 / m / "train_log.json", "D")
    add("S11_dim", "VI.7", "S11 입력 차원", "11", V2 / "S11/normalization_stats.json", "-")
    add("S10_dim", "V.1", "S10 입력 차원", "10", V2 / "S10/normalization_stats.json", "-")
    from thesis_v2.improved.student_i4 import config as scfg
    SC = ROOT / "thesis_v2/improved/student_i4/config.py"
    add("grad_clip", "V.3", "기울기 노름 절단", f"{scfg.GRAD_CLIP_NORM}", SC, "-")
    add("plateau", "V.3", "ReduceLROnPlateau 계수 / patience(epoch)", f"{scfg.LR_PLATEAU_FACTOR} / {scfg.LR_PLATEAU_PATIENCE}", SC, "-")
    dc = json.load(open(V2 / "dev_compare/dev_compare.json", encoding="utf-8"))
    for m in ("9", "S10", "S11"):
        ol = dc["open_loop"][m]["ALL"]["mae"]
        add(f"dev_{m}_mae", "VI.7", f"dev 개루프 MAE {m}", f(ol, 2) + "°", V2 / "dev_compare/dev_compare.json", "D")
        for tr in ("dev_paper", "dev_s3"):
            c = dc["closed_loop"][m][tr]
            add(f"dev_{m}_{tr}", "VI.7", f"dev 폐루프 {m} {tr} 성공/충돌/타임아웃", f"{c['success']}/{c['collision']}/{c['timeout']}",
                V2 / "dev_compare/dev_compare.json", "D")
    add("dev_mcnemar_S10_9", "VI.7", "dev S10 vs 9입력 성공 불일치 쌍(S10만/9만)",
        f"{dc['selection']['reference_9input']['mcnemar_success_selected_vs_9']['only_a']}/{dc['selection']['reference_9input']['mcnemar_success_selected_vs_9']['only_b']}",
        V2 / "dev_compare/dev_compare.json", "D")
    j3 = json.load(open(J3, encoding="utf-8"))
    for tr in ("paper", "S3"):
        for m in ("v2mpc", "9input", "S10", "S11"):
            c = j3["counts"][tr][m]
            add(f"e3_{tr}_{m}_succ", "VI.7", f"E3 {tr} {m} 성공", c["success"], J3, "E3")
            add(f"e3_{tr}_{m}_coll", "VI.7", f"E3 {tr} {m} 충돌", c["collision"], J3, "E3")
            add(f"e3_{tr}_{m}_to", "VI.7", f"E3 {tr} {m} 타임아웃", str(c["timeout"]), J3, "E3")
        pp = j3["paired_S10_vs_v2"][tr]
        add(f"e3_{tr}_pair", "VI.7", f"E3 {tr} S10 vs v2 불일치 쌍", f"{pp['v2_success_S10_fail'] + pp['v2_fail_S10_success']}/{pp['n']}", J3, "E3")
    mc = j3["mcnemar_S10_vs_9input"]["combined"]
    add("e3_mcn_succ", "VI.7", "E3 합산 McNemar 성공(S10만/9입력만, p)", f"{mc['success']['only_a']}/{mc['success']['only_b']}, p={pexp(mc['success']['p_value'])}", J3, "E3")
    add("e3_mcn_coll", "VI.7", "E3 합산 McNemar 충돌(9입력만/S10만, p)", f"{mc['collision']['only_a']}/{mc['collision']['only_b']}, p={pexp(mc['collision']['p_value'])}", J3, "E3")
    # 판정 라벨(사용자 결정 2026-09-25, OPEN #1): 공개 문서에는 범위를 넣은 표현을 쓰고 사전 기준 이름(DESIGN_I4 §6-5)은 괄호로 병기
    assert j3["verdict_S10"].startswith("통과 — MPC 대체 가능"), j3["verdict_S10"]
    add("e3_verdict", "VI.7", "E3 S10 판정", "조향 명령 대체 시 v2 MPC 대비 비열화 없음(시뮬레이션, eval3) (사전 기준 이름: 「통과 — MPC 대체 가능」)",
        J3, "E3", "사전 기준 판정 원문: " + j3["verdict_S10"])
    mm = json.load(open(V2 / "eval3/mae_models.json", encoding="utf-8"))["models"]
    for m in ("9", "S10", "S11"):
        add(f"e3_mae_{m}", "VI.7", f"E3 개루프 δ MAE vs v2 {m}", f(mm[m]["overall"]["delta_vs_v2"]["mae"], 3) + "°", V2 / "eval3/mae_models.json", "E3")
        for st, b in mm[m]["by_state"].items():
            add(f"e3_mae_{m}_{st}", "VI.7", f"E3 개루프 δ MAE vs v2 {m} {st}", f(b["delta_vs_v2"]["mae"], 3) + "°", V2 / "eval3/mae_models.json", "E3")
    for m in ("v2mpc", "9input", "S10", "S11"):
        for tr in ("paper", "S3"):
            b = j3["by_state"][m][tr]["ALL"]
            add(f"e3_iv_{m}_{tr}", "VI.7", f"E3 {m} {tr} 원출력 >25° / 최대 / 분포 이탈",
                f"{100 * b['raw_over_25']:.2f}% / {b['raw_max_abs']:.2f}° / {100 * b['ood_own']:.2f}%", J3, "E3")
    # 배수 범위(실행 간 변동): S10 timing 실행 vs R2
    s10run = json.load(open(V2 / "S10/eval/timing/timing.json", encoding="utf-8"))["paper"]
    r2 = json.load(open(R2, encoding="utf-8"))
    rp = sorted([s10run["v2_mpc_solve_ms"]["p99"] / s10run["pytorch_e2e_ms"]["p99"], r2["v2_mpc_solve_ms"]["p99"] / r2["s10_pytorch_e2e_ms"]["p99"]])
    ro = sorted([s10run["v2_mpc_solve_ms"]["p99"] / s10run["onnx_e2e_ms"]["p99"], r2["v2_mpc_solve_ms"]["p99"] / r2["s10_onnx_e2e_ms"]["p99"]])
    add("ratio_p99_pt", "VI.7", "v2 MPC ÷ S10 PyTorch p99 배수(공식 조건 실행 범위)", rng(rp[0], rp[1]), f"{rel(V2 / 'S10/eval/timing/timing.json')}, {rel(R2)}", "T0-H1")
    mp = sorted([s10run["v2_mpc_solve_ms"]["mean"] / s10run["pytorch_e2e_ms"]["mean"], r2["v2_mpc_solve_ms"]["mean"] / r2["s10_pytorch_e2e_ms"]["mean"]])
    mo = sorted([s10run["v2_mpc_solve_ms"]["mean"] / s10run["onnx_e2e_ms"]["mean"], r2["v2_mpc_solve_ms"]["mean"] / r2["s10_onnx_e2e_ms"]["mean"]])
    add("ratio_mean_pt", "VI.7", "v2 MPC ÷ S10 PyTorch 평균 배수(실행 범위)", rng(mp[0], mp[1]), f"{rel(V2 / 'S10/eval/timing/timing.json')}, {rel(R2)}", "T0-H1")
    add("ratio_mean_ox", "VI.7", "v2 MPC ÷ S10 ONNX 평균 배수(실행 범위)", rng(mo[0], mo[1]), f"{rel(V2 / 'S10/eval/timing/timing.json')}, {rel(R2)}", "T0-H1")
    sp = sorted([s10run["v2_mpc_solve_ms"]["std"] / s10run["pytorch_e2e_ms"]["std"], r2["v2_mpc_solve_ms"]["std"] / r2["s10_pytorch_e2e_ms"]["std"]])
    add("ratio_std_pt", "VI.8", "v2 MPC ÷ S10 PyTorch 표준편차 배수(실행 범위)", rng(sp[0], sp[1]), f"{rel(V2 / 'S10/eval/timing/timing.json')}, {rel(R2)}", "T0-H1")
    add("ratio_p99_ox", "VI.7", "v2 MPC ÷ S10 ONNX p99 배수(공식 조건 실행 범위)", rng(ro[0], ro[1]), f"{rel(V2 / 'S10/eval/timing/timing.json')}, {rel(R2)}", "T0-H1")
    tv3b = json.load(open(next(TV3.glob("*_baseline/timing_baseline.json")), encoding="utf-8"))["paper"]["mpc_solve_ms"]["p99"]
    tv3v2 = json.load(open(next(TV3.glob("*_v2/timing_v2.json")), encoding="utf-8"))["paper"]["mpc_solve_ms"]["p99"]
    s11run = json.load(open(V2 / "S11/eval/timing/timing.json", encoding="utf-8"))["paper"]
    vb = 100 * (r2["baseline_v11"]["mpc_solve_ms"]["p99"] / tv3b - 1)
    vpt = 100 * (r2["s10_pytorch_e2e_ms"]["p99"] / s10run["pytorch_e2e_ms"]["p99"] - 1)
    add("p99_var", "VI.7", "1ms 미만 양의 p99 실행 간 변동(baseline MPC timing_v3→R2, S10 PyTorch S10 실행→R2)",
        f"{vb:+.0f}%, {vpt:+.0f}%".replace("-", "−"), f"{rel(R2)}, timing_v3, {rel(V2 / 'S10/eval/timing/timing.json')}", "T0-H1")
    v2s = [tv3v2, s10run["v2_mpc_solve_ms"]["p99"], s11run["v2_mpc_solve_ms"]["p99"], r2["v2_mpc_solve_ms"]["p99"]]
    add("v2_p99_range", "VI.6", "v2 MPC p99 실행 범위(공식 조건 4회: timing_v3, S10·S11 실행, R2)", f"{min(v2s):.3f}~{max(v2s):.3f} ms",
        f"timing_v3, {rel(V2 / 'S10/eval/timing/timing.json')}, {rel(V2 / 'S11/eval/timing/timing.json')}, {rel(R2)}", "T0-H1")
    # ---------------- 부록 B: 환경 ----------------
    env = json.load(open(R2.parent / "env.json", encoding="utf-8"))
    add("env_py", "부록 B", "Python / numpy / osqp", f"{env['python'].split()[0]} / {env['numpy']} / {env['osqp']}", R2.parent / "env.json", "H1")
    add("env_torch", "부록 B", "torch / onnxruntime", f"{env['torch']} / {env['onnxruntime']}", R2.parent / "env.json", "H1")
    # ---------------- 부록 B: 조건·호스트·커밋 코드 정의 ----------------
    MP = ROOT / "repro/docs/MEASURE_PLAN.md"
    add("cond_E1", "부록 B", "E1 정의", "paper·left_obstacle seed 0~99, S3 원 격자 961(front_gap0 0.50~2.00 × y0 −0.15~0.15, 간격 0.05·0.01), S4~S7 seed 0~99",
        EV1, "E1")
    add("cond_E2", "부록 B", "E2 정의", "paper·left_obstacle·S4~S7 seed 200~299, S3 1/4칸 오프셋 격자 900(front_gap0 0.5025~1.9975 × y0 −0.1475~0.1475)",
        EV2, "E2")
    add("cond_E3", "부록 B", "E3 정의", "paper seed 2000~2099, S3 3/4칸 오프셋 격자 900(front_gap0 0.5375~1.9875 × y0 −0.1425~0.1475)",
        ROOT / "thesis_v2/improved/student_i4/config.py", "E3")
    add("cond_D", "부록 B", "D 정의", "dev: paper seed 100~199, S3 반 칸 오프셋 격자 900(front_gap0 0.525~1.975 × y0 −0.145~0.145), S4~S7 seed 1000~1099",
        ROOT / "thesis_v2/improved/student_i4/config.py", "D")
    add("cond_T0", "부록 B", "T0 정의", "계산시간 측정: paper(·left_obstacle·S6 ψ0=−15°) seed 0~99, 제어기 인스턴스 재사용, 스레드 1, warmup 50 제외", MP, "T0")
    add("cond_E1_n", "부록 B", "E1 S3 격자 수", "961", EV1, "E1")
    return rows


if __name__ == "__main__":
    for r in build():
        print(r[0], "|", r[3], "|", r[5])
