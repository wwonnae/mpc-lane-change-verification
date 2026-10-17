"""
이상탐지 확장 보고서(확장_센서시계열이상탐지_2026.md)의 수치표 docs/revision/ANOMALY_NUMBERS.csv 생성.

값은 **저장된 결과 파일에서만** 계산한다(상수로 적지 않는다). 설정값은 config 모듈에서 읽는다.
기존 REVISION_NUMBERS.csv·make_revision_numbers.py와는 독립이다(수정하지 않음).

열: key | 항목 | 값 | 근거_파일 | 조건_코드 | 비고
조건 코드(보고서 부록): 데이터 AN·AT·AD·AE·AC·AS, 호스트 H1·H3·H4, 커밋 K1~K6.
사용(저장소 루트, .venv): python docs/revision/scripts/make_anomaly_numbers.py
"""
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from thesis_v2.anomaly import config as ac  # noqa: E402
from thesis_v2.anomaly import detector_a as da  # noqa: E402
from thesis_v2.anomaly import features_b as fb  # noqa: E402
from thesis_v2.baseline import config as bc  # noqa: E402
from thesis_v2.baseline import sensors as bs  # noqa: E402
from thesis_v2.baseline.summary import wilson_ci  # noqa: E402

OUT = ROOT / "docs/revision/ANOMALY_NUMBERS.csv"
R = "thesis_v2/results/anomaly/"
OFF = R + "20261002_145638_3층PC108_it3_eval_offline_eval"
CLE = R + "20261012_142758_3층PC109_it3_closed_loop_eval"
CLD = R + "20261002_173407_3층PC108_it3_closed_loop_dev"
LOGS = R + "20261012_3층PC109_run_logs"
THR_A1 = R + "20261001_233358_DESKTOP-MDCKRJS_stage2_threshold_a"
THR_A2 = R + "20261002_001000_DESKTOP-MDCKRJS_it2_threshold_a"
THR_A3 = R + "20261002_104706_3층PC108_it3_threshold_a"
THR_B1 = R + "20261001_235004_DESKTOP-MDCKRJS_stage3_threshold_b"
THR_B2 = R + "20261002_001119_DESKTOP-MDCKRJS_it2_threshold_b"
THR_HY = R + "20261002_111959_3층PC108_it3_threshold_hybrid"
THR_SG005_BUG = R + "20261002_112515_3층PC108_it3_threshold_a_sg0.05"
THR_SG5_BUG = R + "20261002_112618_3층PC108_it3_threshold_a_sg5"
THR_SG005 = R + "20261002_121655_3층PC108_it3_threshold_a_sg0.05"
THR_SG5 = R + "20261002_121733_3층PC108_it3_threshold_a_sg5"
OFFDEV_BUG = R + "20261002_114809_3층PC108_it3_eval_offline_dev"
OFFDEV_FIX = R + "20261002_122803_3층PC108_it3_eval_offline_dev"
DEV_B1_IT1 = R + "20261001_235052_DESKTOP-MDCKRJS_stage3_dev_detect_b1"
DEV_B2_IT1 = R + "20261001_235151_DESKTOP-MDCKRJS_stage3_dev_detect_b2"
DEV_B1_IT2 = R + "20261002_001238_DESKTOP-MDCKRJS_it2_dev_detect_b1"
DEV_B2_IT2 = R + "20261002_001336_DESKTOP-MDCKRJS_it2_dev_detect_b2"
DEV_A_IT2 = R + "20261002_001154_DESKTOP-MDCKRJS_it2_dev_detect_a"
DEV_A_IT3 = R + "20261002_104836_3층PC108_it3_dev_detect_a"
TRAIN_B2 = R + "20261002_001009_DESKTOP-MDCKRJS_it2_train_b"
TRAIN_HY = R + "20261002_111909_3층PC108_it3_train_hybrid"
IDC_B = R + "20261012_113550_3층PC109_stage3_if_identity_check"
IDC_HY = R + "20261012_113600_3층PC109_hybrid_if_identity_check"
SUP = "docs/revision/data/anomaly/supplement.json"

KINDS_HARMFUL = ["lidar_freeze", "lidar_dropout", "ir_stuck", "steer_delay", "steer_stuck", "left_clear_stuck"]
KINDS_HARMLESS = ["lidar_spike", "ir_dropout", "right_clear_stuck"]
KINDS = KINDS_HARMFUL + KINDS_HARMLESS
NORMAL_RUNS = ["none", "none_leftobs"]
COMBOS = ["P0", "P1_A", "P1_B1", "P1_B2", "P1_HYBRID", "P2_A"]
DETS = ["A", "B1", "B2", "HYBRID"]

rows = []
seen = set()


def add(key, item, value, src, cond="-", note=""):
    assert key not in seen, key
    seen.add(key)
    rows.append([key, item, str(value), src, cond, note])


def jload(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def cload(p):
    with open(ROOT / p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(x, nd=1):
    return f"{x * 100:.{nd}f}"


def ci(k, n):
    w = wilson_ci(k, n)
    return f"{pct(w['lo'])}~{pct(w['hi'])}%"


def ci_from(lst):
    return f"{pct(lst[0])}~{pct(lst[1])}%"


def fnum(x, nd=3):
    return f"{x:.{nd}f}"


# ================= 설정값(config에서 읽음) =================
CFG_A, CFG_B, CFG_AN = "thesis_v2/anomaly/detector_a.py", "thesis_v2/anomaly/features_b.py", "thesis_v2/anomaly/config.py"
CFG_BASE = "thesis_v2/baseline/config.py"
add("p_gtrig", "회피 조건 front_gap 임계값 G_TRIG", f"{bc.G_TRIG} m", CFG_BASE)
add("p_gsafe", "SAFE_STOP 조건 front_gap 임계값 G_SAFE_MIN", f"{bc.G_SAFE_MIN:.2f} m", CFG_BASE)
add("p_cooldown", "FSM 쿨다운", f"{bc.COOLDOWN} s", CFG_BASE)
add("p_cooldown_steps", "쿨다운 step 수(COOLDOWN/DT)", round(bc.COOLDOWN / bc.DT), CFG_BASE)
add("p_dt", "제어 주기", f"{bc.DT} s", CFG_BASE)
add("p_vmax", "주행 속도 명령", f"{bc.V_MAX} m/s", CFG_BASE)
add("p_vdt", "한 step 이동량 상한(V_MAX·DT)", f"{bc.V_MAX * bc.DT:.3f} m", CFG_BASE)
add("p_fg_far", "이상탐지 시나리오 초기 전단거리", f"{ac.ANOMALY_FRONT_GAP_RANGE[0]}~{ac.ANOMALY_FRONT_GAP_RANGE[1]} m", CFG_AN)
add("p_fg_near", "기존 시나리오 초기 전단거리", f"{bc.OBSTACLE_FRONT_GAP_RANGE[0]}~{bc.OBSTACLE_FRONT_GAP_RANGE[1]} m", CFG_BASE)
add("p_maxsteps", "이상탐지 에피소드 상한", f"{ac.ANOMALY_MAX_STEPS} step", CFG_AN)
add("p_observe", "복귀 후 관찰 구간", f"{bc.OBSERVE_STEPS} step", CFG_BASE)
prof = bs.NOISE_PROFILES[ac.NORMAL_NOISE_PROFILE]
add("p_s4_fg", "S4-low front_gap 노이즈 σ", f"{prof.sigma_front_gap} m", "thesis_v2/baseline/sensors.py")
add("p_s4_ey", "S4-low ey 노이즈 σ", f"{prof.sigma_ey} m", "thesis_v2/baseline/sensors.py")
add("p_s4_flip", "S4-low left/right_clear 오판정 확률", prof.flip_p, "thesis_v2/baseline/sensors.py")
add("p_sigma_gyro", "탐지기 전용 자이로 노이즈 σ(가정)", f"{ac.SIGMA_GYRO_DEG} °/s", CFG_AN)
add("p_gyro_datasheet", "MPU-6000/6050 Total RMS Noise(데이터시트)", "0.05 °/s-rms", "thesis_v2/anomaly/DESIGN.md §13-2",
    note="PS-MPU-6000A-00 Rev 3.2 §6.1; 가정 σ는 이 값의 20배")
add("p_gyro_ratio", "가정 σ ÷ 데이터시트 Total RMS", "20배", "thesis_v2/anomaly/DESIGN.md §13-2")
add("p_kappa", "CUSUM 기준값 κ(z 단위)", da.CUSUM_KAPPA, CFG_A)
add("p_p0", "이산 채널 정상 불일치 확률 p0", da.BERN_P0, CFG_A)
add("p_p1", "이산 채널 고장 불일치 확률 p1", da.BERN_P1, CFG_A)
add("p_quantile", "임계값 분위수(정상 에피소드 최대 점수)", "98%", CFG_AN, note="method=higher, 경보 S>h, 목표 오경보 2%")
add("p_window", "B 윈도우 길이", f"{fb.W} step", CFG_B)
add("p_n_ch_b", "B step 특징 채널 수", len(fb.CHANNEL_NAMES), CFG_B)
add("p_n_feat_b1", "B1 윈도우 특징 수(채널×5통계)", len(fb.CHANNEL_NAMES) * 5, CFG_B)
add("p_n_ch_hy", "하이브리드 채널 수(B 15 + A 7)", len(fb.CHANNEL_NAMES) + len(da.CHANNELS), "thesis_v2/anomaly/hybrid.py")
add("p_n_feat_hy", "하이브리드 특징 수", (len(fb.CHANNEL_NAMES) + len(da.CHANNELS)) * 5, "thesis_v2/anomaly/hybrid.py")
add("p_if_trees", "IF 트리 수", 200, "thesis_v2/anomaly/detector_b.py", note="§13-4 고정")
add("p_ae_latent", "AE 잠재 차원", 8, "thesis_v2/anomaly/ae_model.py", note="§13-4 고정")
add("p_ae_epochs", "AE epoch 상한 / 조기 종료 인내", "100 / 10", "thesis_v2/anomaly/ae_model.py", note="§13-4 고정")
add("p_depart", "이탈 판정(차체 기하 중심의 도로 범위)", "−0.15~0.45 m", CFG_AN, note="D5 개정")
add("p_mismatch_true", "σ 불일치 실험의 실제 주입 σ", "0.5 / 2 / 5 °/s", "thesis_v2/anomaly/eval_offline.py")
add("p_sg_set", "σ 일치 민감도 σ", "0.05 / 1 / 5 °/s", "thesis_v2/anomaly/eval_offline.py")
add("p_boot", "부트스트랩 반복 / seed", "2000 / 0", OFF + "/meta.json")

# 고장 파라미터 범위(설정값 — faults.sample_fault, dev 3200~3229에서만 결정, DESIGN.md §12)
from thesis_v2.anomaly.dev_detect import GRACE_STEPS  # noqa: E402
FLT = "thesis_v2/anomaly/faults.py"
add("p_warmup", "고장 onset 하한(워밍업)", f"{ac.WARMUP_STEPS} step", CFG_AN)
add("p_grace", "탐지 유예(고장 종료 후)", f"{GRACE_STEPS} step", "thesis_v2/anomaly/dev_detect.py")
add("f_dropout_dur", "lidar_dropout 지속", "20~60 step", FLT)
add("f_spike_dur", "lidar_spike 지속", "1~3 step", FLT, note="위(최대거리)/아래(0.05~0.5 m) 반반")
add("f_spike_down", "lidar_spike 아래로 튐 값", "0.05~0.5 m", FLT)
add("f_delay", "steer_delay 지연", "4~8 step", FLT)
add("f_stuck_dur", "steer_stuck 지속", "10~30 step", FLT)
add("f_rc_onset", "right_clear_stuck onset", "t_trig~t_trig+10 step", FLT)
add("f_dev_band", "고장 범위 결정 dev seed", "3200~3229", FLT)
add("n_kinds", "고장 종류 수(유해 6 + 무해 3)", len(KINDS), "thesis_v2/anomaly/dev_detect.py")
add("n_runs", "실행 run 수(정상 2 + 고장 9)", len(NORMAL_RUNS) + len(KINDS), "thesis_v2/anomaly/dev_detect.py")
add("n_combos", "폐루프 조합 수", len(COMBOS), "thesis_v2/anomaly/closed_loop.py")
add("n_ch_a", "A 채널 수", len(da.CHANNELS), CFG_A)
add("p_bern_llr", "이산 채널 불일치 1회당 LLR", f"+{da.LLR_MISMATCH:.2f} nats", CFG_A)
add("p_no_return", "무반사 판정 front_gap", f"≥ {bc.LIDAR_MAX_RANGE - da.NO_RETURN_MARGIN:.2f} m", CFG_A)


# seed 대역
def band(x):
    return f"{x[0]}~{x[-1]}"
add("seed_thr", "정상 임계값 seed(AN)", band(ac.SEEDS_NORMAL_TRAIN), CFG_AN, note="config 이름은 SEEDS_NORMAL_TRAIN(정상 학습·임계값)")
add("seed_train", "B 학습·검증 seed(AT)", band(ac.SEEDS_B_TRAIN + ac.SEEDS_B_VAL), CFG_AN, note=f"학습 {band(ac.SEEDS_B_TRAIN)}, 검증 {band(ac.SEEDS_B_VAL)}")
add("seed_dev", "고장 dev seed(AD)", band(ac.SEEDS_FAULT_DEV), CFG_AN)
add("seed_off", "오프라인 평가 seed(AE)", band(ac.SEEDS_OFFLINE_EVAL), CFG_AN)
add("seed_cl", "폐루프 평가 seed(AC)", band(ac.SEEDS_CLOSED_LOOP), CFG_AN)
add("seed_sup", "보충 재현 seed(AS)", "3000~3399", "docs/revision/scripts/anomaly_supplement.py", note="평가 seed 제외 assert")

# ================= 탐지기 A 임계값·이력 =================
a1, a2, a3 = jload(THR_A1 + "/thresholds.json"), jload(THR_A2 + "/thresholds.json"), jload(THR_A3 + "/thresholds.json")
add("h_a_it1", "A 임계값 h(iteration 1, 원거리 정상 200회)", fnum(a1["h"], 4), THR_A1 + "/thresholds.json", "AN·H1·K2")
add("h_a", "A 임계값 h(iteration 2·3, 정상 400회)", fnum(a3["h"], 4), THR_A3 + "/thresholds.json", "AN·H3·K3",
    note=f"it2 {a2['h']} = it3 {a3['h']}")
add("h_a_over", "A 정상 400회 중 h 초과", f"{a3['train_episodes_over_h']}", THR_A3 + "/thresholds.json", "AN")
add("thr_n_normal", "임계값 정상 에피소드 수(원거리 200 + 좌측 장애물 200)", a3["n_episodes"], THR_A3 + "/thresholds.json", "AN")
add("thr_outcomes", "임계값 정상 400회 결과", ", ".join(f"{k} {v}" for k, v in a3["outcomes"].items()),
    THR_A3 + "/thresholds.json", "AN")
psi_argmax = a3["per_channel"]["psi"].get("argmax_count")
irm = a3["per_channel"]["ir_miss"]
add("thr_irmiss_max", "정상 400회에서 ir_miss 채널 최대 점수", irm["max"], THR_A3 + "/thresholds.json", "AN")
b1t, b2t, hyt = jload(THR_B1 + "/thresholds_b.json"), jload(THR_B2 + "/thresholds_b.json"), jload(THR_HY + "/thresholds_hybrid.json")
add("h_b1_it1", "B1 h(iteration 1)", fnum(b1t["detectors"]["B1"]["h"], 4), THR_B1 + "/thresholds_b.json", "AN·H1·K2")
add("h_b2_it1", "B2 h(iteration 1)", fnum(b1t["detectors"]["B2"]["h"], 4), THR_B1 + "/thresholds_b.json", "AN·H1·K2")
add("h_b1", "B1 h(iteration 2)", fnum(b2t["detectors"]["B1"]["h"], 4), THR_B2 + "/thresholds_b.json", "AN·H1·K2")
add("h_b2", "B2 h(iteration 2)", fnum(b2t["detectors"]["B2"]["h"], 4), THR_B2 + "/thresholds_b.json", "AN·H1·K2")
add("h_hy", "하이브리드 h", fnum(hyt["h"], 4), THR_HY + "/thresholds_hybrid.json", "AN·H3·K4")
tm = jload(TRAIN_B2 + "/meta.json")
nw = tm.get("n_windows", {})
add("train_windows", "B 학습 윈도우 수(iteration 2)", f"{nw.get('train'):,}", TRAIN_B2 + "/meta.json", "AT")
add("val_windows", "B2 검증 윈도우 수(iteration 2)", f"{nw.get('val'):,}", TRAIN_B2 + "/meta.json", "AT")
idb, idh = jload(IDC_B + "/result.json"), jload(IDC_HY + "/result.json")
add("ifid_n", "IF 동일성 고정 입력 윈도우 수", idb["n"], IDC_B + "/result.json", "AD")
add("ifid_b", "IF 동일성(B1, H4 재학습 vs H1) 점수 최대 차이", idb["max_abs_diff"], IDC_B + "/result.json", "AD·H4")
add("ifid_hy", "IF 동일성(하이브리드, H4 재학습 vs H3) 점수 최대 차이", idh["max_abs_diff"], IDC_HY + "/result.json", "AD·H4")

# σ 전달 버그
add("bug_h_sg005", "버그 상태 A h(σ=0.05)", fnum(jload(THR_SG005_BUG + "/thresholds.json")["h"], 2), THR_SG005_BUG + "/thresholds.json",
    "AN·H3", note="폐기")
add("bug_h_sg5", "버그 상태 A h(σ=5)", fnum(jload(THR_SG5_BUG + "/thresholds.json")["h"], 2), THR_SG5_BUG + "/thresholds.json",
    "AN·H3", note="폐기")
add("fix_h_sg005", "수정 후 A h(σ=0.05)", fnum(jload(THR_SG005 + "/thresholds.json")["h"], 4), THR_SG005 + "/thresholds.json", "AN·H3·K4")
add("fix_h_sg5", "수정 후 A h(σ=5)", fnum(jload(THR_SG5 + "/thresholds.json")["h"], 4), THR_SG5 + "/thresholds.json", "AN·H3·K4")
for tag, d in (("bug", OFFDEV_BUG), ("fix", OFFDEV_FIX)):
    s = jload(d + "/summary.json")["A_sigma_sensitivity"]
    for sg, sk in (("sg005", "sg0.05"), ("sg5", "sg5")):
        x = s[sk]
        add(f"{tag}_dev_{sg}_fault", f"{'버그 상태' if tag == 'bug' else '수정 후'} dev σ={sk[2:]} 고장 탐지(900회 중)",
            x["fault_detected"]["k"], d + "/summary.json", "AD·H3", note="폐기" if tag == "bug" else "")
        add(f"{tag}_dev_{sg}_normal", f"{'버그 상태' if tag == 'bug' else '수정 후'} dev σ={sk[2:]} 정상 오경보(200회 중)",
            x["normal_false_alarm"]["k"], d + "/summary.json", "AD·H3", note="폐기" if tag == "bug" else "")


# dev 이력(B 정상 데이터 범위 공백, iteration 3 ir_miss)
def dev_counts(path):
    rs = cload(path + "/episodes.csv")
    out = {}
    for run in sorted(set(r["run"] for r in rs)):
        rr = [r for r in rs if r["run"] == run]
        if run.startswith("none"):
            out[run] = sum(1 for r in rr if r["first_alarm"] not in ("", "None"))
        else:
            out[run] = sum(1 for r in rr if r["detected"] in ("True", "1", "true"))
    return out


for tag, path in (("b1_it1", DEV_B1_IT1), ("b2_it1", DEV_B2_IT1), ("b1_it2", DEV_B1_IT2), ("b2_it2", DEV_B2_IT2),
                  ("a_it2", DEV_A_IT2), ("a_it3", DEV_A_IT3)):
    c = dev_counts(path)
    for run in ("none", "none_leftobs", "lidar_freeze", "lidar_dropout", "steer_delay", "ir_dropout"):
        add(f"dev_{tag}_{run}", f"dev {tag} {run} {'경보' if run.startswith('none') else '탐지'}(100회 중)", c[run],
            path + "/episodes.csv", "AD")

# ================= 오프라인 평가 =================
S = jload(OFF + "/summary.json")
om = jload(OFF + "/meta.json")
add("off_n_kind", "오프라인 평가 고장 종류별 에피소드 수", S["A"]["per_kind"]["lidar_freeze"]["fault_started"], OFF + "/summary.json", "AE")
for d in DETS:
    x = S[d]
    for sc, key in (("far", "normal_far"), ("left", "normal_leftobs")):
        e = x[key]["episodes"]
        add(f"off_{d}_normal_{sc}", f"오프라인 {d} 정상 {sc} 경보", e["k"], OFF + "/summary.json", "AE·H3·K4")
        add(f"off_{d}_normal_{sc}_ci", f"오프라인 {d} 정상 {sc} 경보 CI", ci_from(e["ci95"]), OFF + "/summary.json", "AE·H3·K4")
    for g in ("harmful", "harmless"):
        e = x[f"{g}_detected"]
        add(f"off_{d}_{g}", f"오프라인 {d} {g} 탐지", f"{e['k']}/{e['n']}", OFF + "/summary.json", "AE·H3·K4")
        add(f"off_{d}_{g}_k", f"오프라인 {d} {g} 탐지 횟수", e["k"], OFF + "/summary.json", "AE·H3·K4")
        add(f"off_{d}_{g}_ci", f"오프라인 {d} {g} 탐지 CI", ci_from(e["ci95"]), OFF + "/summary.json", "AE·H3·K4")
    rp = x["roc_pr"]
    add(f"off_{d}_auc", f"오프라인 {d} 에피소드 ROC AUC", fnum(rp["episode_auc"]), OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{d}_auc_ci", f"오프라인 {d} ROC AUC 부트스트랩 95%", f"{fnum(rp['episode_auc_ci95'][0])}~{fnum(rp['episode_auc_ci95'][1])}",
        OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{d}_ap", f"오프라인 {d} 스텝 PR AP", fnum(rp["step_ap"]), OFF + "/summary.json", "AE·H3·K4")
    for k in KINDS:
        p = x["per_kind"][k]
        add(f"off_{d}_{k}", f"오프라인 {d} {k} 탐지(100회 중)", p["detected"], OFF + "/summary.json", "AE·H3·K4")
        add(f"off_{d}_{k}_ci", f"오프라인 {d} {k} 탐지 CI", ci_from(p["detected_ci95"]), OFF + "/summary.json", "AE·H3·K4")
        dl = "—" if p["delay_median"] is None else f"{p['delay_median']} ({p['delay_p90']})"
        add(f"off_{d}_{k}_delay", f"오프라인 {d} {k} 지연 중앙값(p90) step", dl, OFF + "/summary.json", "AE·H3·K4")
        if d == "A":
            sp = p["separation_accuracy"]
            add(f"off_A_{k}_sep", f"오프라인 A {k} 분리 정확도(센서 단위)", f"{sp['k']}/{sp['n']}", OFF + "/summary.json", "AE·H3·K4")
            f1 = p["step_prf1"]["f1"]
            add(f"off_A_{k}_f1", f"오프라인 A {k} 스텝 F1", "—" if f1 is None else fnum(f1, 2), OFF + "/summary.json", "AE·H3·K4")
            add(f"off_P0_{k}_fail", f"관찰 실행(탐지기 개입 없음) {k} 충돌·이탈(100회 중)", p["failures"], OFF + "/summary.json", "AE·H3·K4")
            lt = p["lead_time_steps"]
            add(f"off_A_{k}_lead", f"오프라인 A {k} 사고 전 선행 step 중앙값(최소)",
                "—" if lt["median"] is None else f"{lt['median']:.0f} ({lt['min']:.0f})", OFF + "/summary.json", "AE·H3·K4")
        if d != "A":
            p_ = x["per_kind"][k]
            add(f"off_{d}_{k}_abf", f"오프라인 {d} {k} 사고 전 경보(사고 에피소드 중)", f"{p_['alarm_before_failure']}/{p_['failures']}",
                OFF + "/summary.json", "AE·H3·K4")
a_fail = sum(S["A"]["per_kind"][k]["failures"] for k in KINDS)
a_abf = sum(S["A"]["per_kind"][k]["alarm_before_failure"] for k in KINDS)
add("off_A_abf_total", "오프라인 A 사고 에피소드 중 사고 전 경보", f"{a_abf}/{a_fail}", OFF + "/summary.json", "AE·H3·K4")
spk = S["A"]["delay_by_magnitude"]["lidar_spike"]
add("off_A_spike_down", "오프라인 A lidar_spike 아래로 튐 탐지", f"{spk['down']['detected']}/{spk['down']['n']}", OFF + "/summary.json", "AE·H3·K4")
add("off_A_spike_up", "오프라인 A lidar_spike 위로 튐 탐지", f"{spk['up']['detected']}/{spk['up']['n']}", OFF + "/summary.json", "AE·H3·K4")
for k_, nm in (("sg0.05", "sg005"), ("sg5", "sg5")):
    x = S["A_sigma_sensitivity"][k_]
    add(f"off_{nm}_normal", f"σ 일치 {k_} 정상 오경보(200회 중)", x["normal_false_alarm"]["k"], OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{nm}_fault", f"σ 일치 {k_} 고장 탐지(900회 중)", x["fault_detected"]["k"], OFF + "/summary.json", "AE·H3·K4")
for k_, nm in (("mismatch0.5", "mm05"), ("mismatch2", "mm2"), ("mismatch5", "mm5")):
    x = S["A_sigma_mismatch_sensitivity"][k_]
    add(f"off_{nm}_normal", f"σ 불일치 {k_} 정상 오경보(200회 중)", x["normal_false_alarm"]["k"], OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{nm}_normal_ci", f"σ 불일치 {k_} 정상 오경보 CI", ci_from(x["normal_false_alarm"]["ci95"]), OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{nm}_fault", f"σ 불일치 {k_} 고장 탐지(900회 중)", x["fault_detected"]["k"], OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{nm}_delay", f"σ 불일치 {k_} 지연 중앙값(p90)", f"{x['delay_median']} ({x['delay_p90']})", OFF + "/summary.json", "AE·H3·K4")
add("off_n_harmful", "오프라인 유해 고장 에피소드 수", S["A"]["harmful_detected"]["n"], OFF + "/summary.json", "AE")
for k_, nm in (("sg0.05", "sg005"), ("sg5", "sg5")):
    x = S["A_sigma_sensitivity"][k_]
    add(f"off_{nm}_normal_ci", f"σ 일치 {k_} 정상 오경보 CI", ci_from(x["normal_false_alarm"]["ci95"]), OFF + "/summary.json", "AE·H3·K4")
    add(f"off_{nm}_delay", f"σ 일치 {k_} 지연 중앙값(p90)", f"{x['delay_median']} ({x['delay_p90']})", OFF + "/summary.json", "AE·H3·K4")
# 기준(σ=1) 합산 지연·정상 오경보: episodes_A.csv를 eval_offline과 같은 함수(delay_stats)로 집계
from thesis_v2.anomaly.eval_offline import delay_stats  # noqa: E402
ea = cload(OFF + "/episodes_A.csv")
started = [dict(detected=r["detected"] in ("True", "1", "true"),
                delay_steps=None if r["delay_steps"] in ("", "None") else int(float(r["delay_steps"])))
           for r in ea if not r["run"].startswith("none") and r["onset"] not in ("", "None")
           and int(float(r["onset"])) <= int(r["total_steps"])]
med, p90 = delay_stats(started)
add("off_base_delay", "σ=1 기준 고장 지연 중앙값(p90), 9종 합산", f"{med} ({p90})", OFF + "/episodes_A.csv", "AE·H3·K4",
    note="eval_offline.delay_stats로 집계")
nfa = sum(1 for r in ea if r["run"].startswith("none") and r["first_alarm"] not in ("", "None"))
nn = sum(1 for r in ea if r["run"].startswith("none"))
add("off_base_normal", "σ=1 기준 정상 오경보(200회 중)", nfa, OFF + "/episodes_A.csv", "AE·H3·K4")
add("off_base_normal_ci", "σ=1 기준 정상 오경보 CI", ci(nfa, nn), OFF + "/episodes_A.csv", "AE·H3·K4")
a_all = S["A"]["harmful_detected"]["k"] + S["A"]["harmless_detected"]["k"]
add("off_A_fault_total", "오프라인 A 고장 탐지 합(900회 중, σ=1)", a_all, OFF + "/summary.json", "AE·H3·K4")

# ================= 폐루프 평가 =================
CL = {c: cload(f"{CLE}/episodes_{c}.csv") for c in COMBOS}
P0 = {(r["run"], r["seed"]): r for r in CL["P0"]}
COMPLETE = {"성공", "SAFE_STOP"}
FAIL = {"충돌", "이탈"}
src_cl = CLE + "/episodes_*.csv"
n_all = len(CL["P0"])
add("cl_n", "폐루프 조합당 에피소드 수(11 run × 100 seed)", f"{n_all:,}", src_cl, "AC")
for c in COMBOS:
    rs = CL[c]
    oc = Counter(r["outcome"] for r in rs)
    for o, k in (("충돌", "col"), ("이탈", "dep"), ("탐지 정지", "det"), ("SAFE_STOP", "ss"), ("성공", "succ"), ("타임아웃", "to")):
        add(f"cl_{c}_{k}", f"폐루프 {c} {o}", oc[o], src_cl, "AC·H4·K5")
    other = sum(v for o, v in oc.items() if o not in ("충돌", "이탈", "탐지 정지", "SAFE_STOP", "성공", "타임아웃"))
    add(f"cl_{c}_other", f"폐루프 {c} 기타(사전 6분류 밖)", other, src_cl, "AC·H4·K5")
    comp = oc["성공"] + oc["SAFE_STOP"]
    add(f"cl_{c}_comp", f"폐루프 {c} 완료(성공+SAFE_STOP)", comp, src_cl, "AC·H4·K5")
    add(f"cl_{c}_comp_ci", f"폐루프 {c} 완료 CI", ci(comp, n_all), src_cl, "AC·H4·K5")
    add(f"cl_{c}_col_ci", f"폐루프 {c} 충돌 CI", ci(oc["충돌"], n_all), src_cl, "AC·H4·K5")
    un = Counter(r["unnecessary_stop"] for r in rs if r["unnecessary_stop"])
    tot = sum(un.values())
    add(f"cl_{c}_unn", f"폐루프 {c} 불필요 정지", tot, src_cl, "AC·H4·K5")
    add(f"cl_{c}_unn_parts", f"폐루프 {c} 불필요 정지(정상/무해/고장 전)", f"{un['normal']}/{un['harmless']}/{un['before_onset']}", src_cl, "AC·H4·K5")
    add(f"cl_{c}_unn_ci", f"폐루프 {c} 불필요 정지 CI", ci(tot, n_all), src_cl, "AC·H4·K5")
    if c != "P0":
        m = Counter()
        for r in rs:
            p = P0[(r["run"], r["seed"])]
            m["colprev"] += p["outcome"] == "충돌" and r["outcome"] != "충돌"
            m["colnew"] += p["outcome"] != "충돌" and r["outcome"] == "충돌"
            m["failprev"] += p["outcome"] in FAIL and r["outcome"] not in FAIL
            m["failnew"] += p["outcome"] not in FAIL and r["outcome"] in FAIL
            m["complost"] += p["outcome"] in COMPLETE and r["outcome"] not in COMPLETE
            m["compgain"] += p["outcome"] not in COMPLETE and r["outcome"] in COMPLETE
        for k, v in m.items():
            add(f"cl_{c}_{k}", f"폐루프 {c} 같은 seed 쌍 {k}", v, src_cl, "AC·H4·K5")
        add(f"cl_{c}_compdelta", f"폐루프 {c} 완료 순변화(P0 대비)", f"{m['compgain'] - m['complost']:+d}".replace("-", "−"),
            src_cl, "AC·H4·K5")
    for g, ks in (("normal", NORMAL_RUNS), ("harmful", KINDS_HARMFUL), ("harmless", KINDS_HARMLESS)):
        gr = [r for r in rs if r["run"] in ks]
        n = len(gr)
        fail = sum(r["outcome"] in FAIL for r in gr)
        comp = sum(r["outcome"] in COMPLETE for r in gr)
        unn = sum(1 for r in gr if r["unnecessary_stop"])
        add(f"cl_{c}_{g}_fail", f"폐루프 {c} {g} 충돌+이탈", fail, src_cl, "AC·H4·K5")
        add(f"cl_{c}_{g}_fail_ci", f"폐루프 {c} {g} 충돌+이탈 CI", ci(fail, n), src_cl, "AC·H4·K5")
        add(f"cl_{c}_{g}_comp", f"폐루프 {c} {g} 완료", comp, src_cl, "AC·H4·K5")
        add(f"cl_{c}_{g}_comp_ci", f"폐루프 {c} {g} 완료 CI", ci(comp, n), src_cl, "AC·H4·K5")
        add(f"cl_{c}_{g}_unn", f"폐루프 {c} {g} 불필요 정지", unn, src_cl, "AC·H4·K5")
        add(f"cl_{c}_{g}_unn_ci", f"폐루프 {c} {g} 불필요 정지 CI", ci(unn, n), src_cl, "AC·H4·K5")
    for k in NORMAL_RUNS + KINDS:
        kr = [r for r in rs if r["run"] == k]
        o = Counter(r["outcome"] for r in kr)
        unn = sum(1 for r in kr if r["unnecessary_stop"])
        cell = f"{o['충돌']}·{o['이탈']}·{o['성공'] + o['SAFE_STOP']}·{unn}"
        add(f"cl_{c}_{k}_cell", f"폐루프 {c} {k} 충돌·이탈·완료·불필요", cell, src_cl, "AC·H4·K5")
# P2_A 대 P1_A 완료 차이의 종류별 분해(같은 run·seed)
P1A = {(r["run"], r["seed"]): r for r in CL["P1_A"]}
gain = Counter()
for r in CL["P2_A"]:
    q = P1A[(r["run"], r["seed"])]
    gain[r["run"]] += (r["outcome"] in COMPLETE) - (q["outcome"] in COMPLETE)
add("p2p1_gain", "P2_A − P1_A 완료 차이", sum(gain.values()), src_cl, "AC·H4·K5")
for k in NORMAL_RUNS + KINDS:
    add(f"p2p1_gain_{k}", f"P2_A − P1_A 완료 차이 {k}", gain[k], src_cl, "AC·H4·K5")
add("p2p1_gain_nonlcs", "P2_A − P1_A 완료 차이(left_clear_stuck 제외)", sum(gain.values()) - gain["left_clear_stuck"], src_cl, "AC·H4·K5")
for g, ks in (("normal", NORMAL_RUNS), ("harmful", KINDS_HARMFUL), ("harmless", KINDS_HARMLESS)):
    add(f"cl_n_{g}", f"폐루프 {g} 묶음 에피소드 수", sum(1 for r in CL["P0"] if r["run"] in ks), src_cl, "AC")
add("cl_P0_harmful_fail_pct", "P0 유해 고장 충돌+이탈 비율", f"{pct(sum(r['outcome'] in FAIL for r in CL['P0'] if r['run'] in KINDS_HARMFUL) / sum(r['run'] in KINDS_HARMFUL for r in CL['P0']))}%",
    src_cl, "AC")

# Q1 미정착
q1 = [(c, r) for c in COMBOS for r in CL[c] if r["outcome"] == "미정착"]
r1 = q1[0][1]
add("q1_run", "미정착 에피소드 run·seed", f"{r1['run']} seed {r1['seed']}", src_cl, "AC")
add("q1_seed", "미정착 seed", r1["seed"], src_cl, "AC")
add("q1_combos", "미정착이 나온 조합", " · ".join(sorted(set(c for c, _ in q1))), src_cl, "AC")
add("q1_onset", "미정착 에피소드 고장 onset step", r1["onset"], src_cl, "AC")
add("q1_finish_step", "미정착 에피소드 복귀 step", r1["finish_step"], src_cl, "AC")
add("q1_total", "미정착 에피소드 종료 step", r1["total_steps"], src_cl, "AC")
alarms = {c: next(r for r in CL[c] if r["run"] == r1["run"] and r["seed"] == r1["seed"])["first_alarm_step"] for c in COMBOS}
add("q1_alarm_A", "같은 에피소드 A 경보 step(P1_A·P2_A)", alarms["P1_A"], src_cl, "AC")
add("q1_alarm_B2", "같은 에피소드 B2 경보 step", alarms["P1_B2"], src_cl, "AC")
add("q1_alarm_HY", "같은 에피소드 하이브리드 경보 step", alarms["P1_HYBRID"], src_cl, "AC")
# Q2 정상 충돌
q2 = [r for r in CL["P0"] if r["run"] in NORMAL_RUNS and r["outcome"] == "충돌"]
add("q2_seed", "정상 주행 충돌 seed", q2[0]["seed"], src_cl, "AC")
add("q2_step", "정상 주행 충돌 step", q2[0]["total_steps"], src_cl, "AC")
add("q2_all", "정상 주행 충돌이 나온 조합 수", sum(any(r["run"] == q2[0]["run"] and r["seed"] == q2[0]["seed"] and r["outcome"] == "충돌"
                                              for r in CL[c]) for c in COMBOS), src_cl, "AC")
# Q3 타임아웃
to = [r for r in CL["P2_A"] if r["outcome"] == "타임아웃"]
add("q3_n", "P2_A 타임아웃", len(to), src_cl, "AC")
add("q3_kinds", "P2_A 타임아웃 고장 종류", ", ".join(f"{k} {v}" for k, v in Counter(r["run"] for r in to).items()), src_cl, "AC")
add("q3_action", "P2_A 타임아웃 대응", ", ".join(f"{k} {v}" for k, v in Counter(r["policy_action"] for r in to).items()), src_cl, "AC")
add("q3_p0", "같은 seed P0 결과", ", ".join(f"{k} {v}" for k, v in Counter(P0[(r["run"], r["seed"])]["outcome"] for r in to).items()), src_cl, "AC")
dl = sorted(int(r["first_alarm_step"]) - int(r["onset"]) for r in to)
add("q3_delay", "rc 경보 시점(onset 후 step, 최소~최대)", f"{dl[0]}~{dl[-1]}", src_cl, "AC")
# Q4 SAFE_STOP
lcs = [r for r in CL["P2_A"] if r["run"] == "left_clear_stuck" and r["outcome"] == "SAFE_STOP"]
add("q4_n", "P2_A left_clear_stuck SAFE_STOP", len(lcs), src_cl, "AC")
add("q4_p0", "같은 seed P0 결과", ", ".join(f"{k} {v}" for k, v in Counter(P0[(r["run"], r["seed"])]["outcome"] for r in lcs).items()), src_cl, "AC")
dl = sorted(int(r["first_alarm_step"]) - int(r["onset"]) for r in lcs)
add("q4_delay", "lc 경보 시점(onset 후 step, 최소~최대)", f"{dl[0]}~{dl[-1]}", src_cl, "AC")
# seed 5064(같은 seed 안 상관)
by_seed = Counter((r["seed"], r["first_alarm_step"]) for r in CL["P1_A"] if r["first_alarm_channel"] == "psi"
                  and (r["unnecessary_stop"] or r["run"] in NORMAL_RUNS))
(seed_c, step_c), _ = by_seed.most_common(1)[0]
same = [r for r in CL["P1_A"] if r["seed"] == seed_c and r["first_alarm_step"] == step_c and r["first_alarm_channel"] == "psi"]
add("corr_seed", "같은 오경보가 여러 run에 나타난 seed", seed_c, src_cl, "AC")
add("corr_step", "그 오경보 step", step_c, src_cl, "AC")
add("corr_runs", "같은 step psi 경보가 난 run 수(11개 중)", len(same), src_cl, "AC")
irs = next(r for r in CL["P2_A"] if r["seed"] == seed_c and r["run"] == "ir_stuck")
add("corr_irstuck_onset", "그 seed ir_stuck onset step", irs["onset"], src_cl, "AC")
add("corr_irstuck_p0", "그 seed ir_stuck의 P0 결과", P0[("ir_stuck", seed_c)]["outcome"], src_cl, "AC")
for c in ("P1_A", "P2_A"):
    u = sum(1 for r in CL[c] if r["seed"] == seed_c and r["unnecessary_stop"] and r["first_alarm_step"] == step_c
            and r["first_alarm_channel"] == "psi")
    add(f"corr_unn_{c}", f"{c} 불필요 정지 중 이 seed 몫", u, src_cl, "AC")
# 폐루프 실행 기록
env = jload(CLE + "/env.json")
add("cl_commit", "폐루프 평가 커밋(env.json)", env["git"]["commit"][:7], CLE + "/env.json", "AC·H4")
log = (ROOT / LOGS / "cl_eval_20261012_132540.log").read_text(encoding="utf-8")
tail = [l for l in log.splitlines() if l.startswith("exit=")][0]
add("cl_runtime", "폐루프 평가 실행 시간", "약 62분", LOGS + "/cl_eval_20261012_132540.log", "AC·H4", note=tail)
# 오프라인 평가 결과의 재현 확인(--check, 3층PC109, 2026-10-12) — 로그에서 읽음
OFF_LOG = LOGS + "/offline_eval_check_20261012_153144.log"
olog = (ROOT / OFF_LOG).read_text(encoding="utf-8").splitlines()
same = [l for l in olog if l.strip().endswith(": 일치") and l.strip().startswith(("episodes_", "summary"))]
diff_ = [l for l in olog if l.strip().endswith(": 불일치")]
otail = [l for l in olog if l.startswith("exit=")][0]
assert not diff_ and "전체 일치" in "\n".join(olog)
add("offchk_same", "오프라인 평가 --check 일치 파일 수", len(same), OFF_LOG, "AE·H4", note=otail)
add("offchk_exit", "오프라인 평가 --check 종료 코드", otail.split()[0].split("=")[1], OFF_LOG, "AE·H4")
h_, m_, s_ = otail.split("elapsed=")[1].strip().split(":")
tot = round(int(h_) * 3600 + int(m_) * 60 + float(s_))
add("offchk_time", "오프라인 평가 --check 실행 시간(반올림)", f"{tot // 60}분 {tot % 60}초", OFF_LOG, "AE·H4")
add("offchk_head", "오프라인 평가 --check 실행 코드(HEAD)", "d14ac34", OFF_LOG, "AE·H4",
    note="63e7b6e 이후 오프라인 계산 경로 코드 변경 없음(git diff: hybrid.py는 클래스 추가만, common.py는 write_env 기록 시점만)")
# 폐루프 평가 결과의 재현 확인(--check, 같은 3층PC109 재실행, 2026-10-12) — 로그·_check_diag_timing.csv에서 읽음
CL_LOG = LOGS + "/cl_eval_check_20261012_154729.log"
clog = (ROOT / CL_LOG).read_text(encoding="utf-8").splitlines()
csame = [l for l in clog if l.strip().endswith(": 일치") and l.strip().startswith(("episodes_", "summary"))]
assert not [l for l in clog if l.strip().endswith(": 불일치")] and "전체 일치" in "\n".join(clog)
ctail = [l for l in clog if l.startswith("exit=")][0]
add("clchk_same", "폐루프 평가 --check 일치 파일 수", len(csame), CL_LOG, "AC·H4", note=ctail)
add("clchk_exit", "폐루프 평가 --check 종료 코드", ctail.split()[0].split("=")[1], CL_LOG, "AC·H4")
h_, m_, s_ = ctail.split("elapsed=")[1].strip().split(":")
tot = round(int(h_) * 3600 + int(m_) * 60 + float(s_))
add("clchk_time", "폐루프 평가 --check 실행 시간(반올림)", f"{tot // 3600}시간 {tot % 3600 // 60}분 {tot % 60}초", CL_LOG, "AC·H4")
add("clchk_head", "폐루프 평가 --check 실행 코드(HEAD)", "c7bd3e1", CL_LOG, "AC·H4",
    note="c29a738 이후 thesis_v2 코드 변경 없음(git diff: DESIGN.md만)")
cdiag = cload(CLE + "/_check_diag_timing.csv")
add("clchk_tlhit", "폐루프 평가 --check MPC time_limit 발동 합계", sum(int(d["time_limit_hits"]) for d in cdiag),
    CLE + "/_check_diag_timing.csv", "AC·H4")
add("clchk_maxsolve", "폐루프 평가 --check MPC 최대 solve 시간(참고)", f"{max(float(d['max_solve_ms']) for d in cdiag):.3f} ms",
    CLE + "/_check_diag_timing.csv", "AC·H4")
diag = cload(CLE + "/diag_timing.csv")
add("cl_tlhit", "폐루프 평가 MPC time_limit 발동 합계", sum(int(d["time_limit_hits"]) for d in diag), CLE + "/diag_timing.csv", "AC·H4")
add("cl_maxsolve", "폐루프 평가 MPC 최대 solve 시간(참고)", f"{max(float(d['max_solve_ms']) for d in diag):.3f} ms", CLE + "/diag_timing.csv", "AC·H4")
# dev(참고)
dsum = jload(CLD + "/summary.json")
for c in ("P0", "P1_A", "P2_A"):
    add(f"cld_{c}_col", f"dev 폐루프 {c} 충돌(참고)", dsum[c]["collisions"], CLD + "/summary.json", "AD·H3")
    add(f"cld_{c}_comp", f"dev 폐루프 {c} 완료율(참고)", f"{dsum[c]['completion_rate']:.3f}", CLD + "/summary.json", "AD·H3")
for c in COMBOS:
    add(f"cl_{c}_comprate", f"폐루프 {c} 완료율", f"{sum(r['outcome'] in COMPLETE for r in CL[c]) / n_all:.3f}", src_cl, "AC·H4·K5")

# ================= 보충 재현(AS) =================
sup = jload(SUP)
ls = sup["leftobs_survey"]
add("sup_n", "보충 재현 정상 좌측 장애물 에피소드 수", ls["n"], SUP, "AS·H4·K6")
add("sup_evaded", "회피를 한 번이라도 거친 에피소드", ls["evaded"], SUP, "AS·H4·K6")
add("sup_evaded_pct", "회피 경유 비율", f"{pct(ls['evaded'] / ls['n'], 0)}%", SUP, "AS·H4·K6")
add("sup_col", "충돌", ls["outcomes"].get("충돌", 0), SUP, "AS·H4·K6")
add("sup_ss", "SAFE_STOP", ls["outcomes"].get("SAFE_STOP", 0), SUP, "AS·H4·K6")
add("sup_col_seed", "충돌 seed", ", ".join(str(s) for s in ls["collision_seeds"]), SUP, "AS·H4·K6")
pc = Counter()
for k, v in ls["paths"].items():
    out, path, cause = k.split("|")
    pc[(out, path, cause)] += v
def ps(out, path, cause=None):
    return sum(v for (o, p, c), v in pc.items() if o == out and p == path and (cause is None or c == cause))
add("sup_path_direct", "KEEP_L2→SAFE_STOP", ps("SAFE_STOP", "KEEP_L2->SAFE_STOP"), SUP, "AS·H4·K6")
add("sup_path_evade", "KEEP_L2→EVADE_L→SAFE_STOP", ps("SAFE_STOP", "KEEP_L2->EVADE_L->SAFE_STOP"), SUP, "AS·H4·K6")
add("sup_path_evade_flip", "위 중 left_clear 오판정 계기", ps("SAFE_STOP", "KEEP_L2->EVADE_L->SAFE_STOP", "lc_flip"), SUP, "AS·H4·K6")
add("sup_path_evade_fg", "위 중 front_gap 노이즈 계기", ps("SAFE_STOP", "KEEP_L2->EVADE_L->SAFE_STOP", "fg_noise"), SUP, "AS·H4·K6")
add("sup_path_l1", "KEEP_L2→EVADE_L→KEEP_L1→SAFE_STOP", ps("SAFE_STOP", "KEEP_L2->EVADE_L->KEEP_L1->SAFE_STOP"), SUP, "AS·H4·K6")
add("sup_path_l1_flip", "위 중 left_clear 오판정 계기", ps("SAFE_STOP", "KEEP_L2->EVADE_L->KEEP_L1->SAFE_STOP", "lc_flip"), SUP, "AS·H4·K6")
add("sup_path_l1_fg", "위 중 front_gap 노이즈 계기", ps("SAFE_STOP", "KEEP_L2->EVADE_L->KEEP_L1->SAFE_STOP", "fg_noise"), SUP, "AS·H4·K6")
f = sup["factor"]
for k, nm in (("far_noisefree", "원거리·노이즈 없음"), ("near_noisefree", "근거리·노이즈 없음"), ("near_s4low", "근거리·S4-low")):
    add(f"sup_{k}_ss", f"{nm} SAFE_STOP", f[k]["outcomes"].get("SAFE_STOP", 0), SUP, "AS·H4·K6")
    add(f"sup_{k}_col", f"{nm} 충돌", f[k]["outcomes"].get("충돌", 0), SUP, "AS·H4·K6")
    add(f"sup_{k}_ev", f"{nm} 회피 경유", f[k]["evaded"], SUP, "AS·H4·K6")
s3 = sup["seed3173"]
st_ = {x["step"]: x for x in s3["steps"]}
trig = s3["transitions"][0][0]
stop = s3["transitions"][1][0]
add("s3173_seed", "재현 seed", s3["seed"], SUP, "AS")
add("s3173_trig", "회피 시작 step", trig, SUP, "AS")
add("s3173_stop", "SAFE_STOP·충돌 step", stop, SUP, "AS")
add("s3173_prev_fg", "회피 직전 step front_gap 측정", st_[trig - 1]["fg"], SUP, "AS")
add("s3173_fg", "회피 step front_gap 측정(참값)", f"{st_[trig]['fg']} ({st_[trig]['fg_clean']})", SUP, "AS")
add("s3173_blocked", "SAFE_STOP 조건이 참인데 쿨다운으로 막힌 step", f"{trig + 1}~{stop - 1}", SUP, "AS")
add("s3173_fg_stop", "정지 판단 step front_gap 측정", st_[stop]["fg"], SUP, "AS")
add("s3173_move", "정지 판단 step 이동 거리", f"{s3['last_step_move_m']:.3f} m", SUP, "AS")
add("s3173_psi", "정지 step 헤딩 변화", f"{s3['last_step_psi_deg'][0]}°→{s3['last_step_psi_deg'][1]}°", SUP, "AS")
p2l = sup["p2_lcs_dev"]
add("dev_lcs_ss", "dev P2_A left_clear_stuck SAFE_STOP(100회 중)", p2l["outcomes"].get("SAFE_STOP", 0), SUP, "AD·H4·K6")
add("dev_lcs_from", "SAFE_STOP 직전 상태", ", ".join(f"{k} {v}" for k, v in p2l["safe_stop_from"].items()), SUP, "AD·H4·K6")
add("dev_lcs_y", "정지 시 y(최소~최대, 중앙값)", f"{p2l['y_min_med_max'][0]}~{p2l['y_min_med_max'][2]} m (중앙값 {p2l['y_min_med_max'][1]})", SUP, "AD·H4·K6")
add("dev_lcs_psi", "정지 시 헤딩(최소~최대)", f"{p2l['psi_deg_min_med_max'][0]}~{p2l['psi_deg_min_med_max'][2]}°", SUP, "AD·H4·K6")
add("dev_lcs_gap", "정지 후 참값 front_gap(최소~최대, 중앙값)",
    f"{p2l['clean_gap_after_min_med_max'][0]}~{p2l['clean_gap_after_min_med_max'][2]} m (중앙값 {p2l['clean_gap_after_min_med_max'][1]})", SUP, "AD·H4·K6")
add("dev_lcs_gap_min", "정지 후 참값 front_gap 최소", f"{p2l['clean_gap_after_min_med_max'][0]} m", SUP, "AD·H4·K6")
add("dev_lcs_y_l1", "정지 시 y ≥ 0.15 m", f"{p2l['y_ge_015']}/{p2l['n_safe_stop']}", SUP, "AD·H4·K6")
p2r = sup["p2_rcs_dev"]
add("dev_rcs_n", "dev right_clear_stuck 경로 확인 seed 수", sum(p2r["P2"].values()), SUP, "AD·H4·K6")
add("dev_rcs_p2", "P2 경로", "; ".join(f"{k.split('|')[1].replace('->', '→')} {v}" for k, v in p2r["P2"].items()), SUP, "AD·H4·K6")

# ================= 탐지기 계산 시간(공식 조건, H1 노트북, 데이터 AN, 2026-10-12) =================
# timing.json·env.json·step_times_ms.npz·실행 로그에서 읽는다(benchmark_detector_timing.py 출력).
TM = R + "20261012_232824_DESKTOP-MDCKRJS_detector_timing"
TM_LOG = R + "20261012_DESKTOP-MDCKRJS_run_logs/detector_timing_20261012_232716.log"
tmj, tme = jload(TM + "/timing.json"), jload(TM + "/env.json")
assert tmj["official_run"] and tmj["meets_official_condition"] and tme["is_official_measurement_host"]
assert tme["git"]["dirty"] is False


def ms(x):
    return f"{x:.3f} ms" if x < 1 else f"{x:.2f} ms"


def pb(x):
    return f"{x:.2f}%" if x < 10 else f"{x:.1f}%"


import numpy as np  # noqa: E402
tmz = np.load(ROOT / TM / "step_times_ms.npz")
add("tm_budget", "20 Hz 제어 주기 예산", f"{tmj['budget_ms']:.0f} ms", TM + "/timing.json", "AN·H1·K7")
add("tm_commit", "계산 시간 측정 커밋(env.json, dirty=false)", tme["git"]["commit"][:7], TM + "/env.json", "AN·H1·K7")
add("tm_cond", "측정 조건(env.json)", f"{tme['hostname']}, {tme['power']['ac_status']}, 전원 모드 최고 성능, meets_official_condition=true",
    TM + "/env.json", "AN·H1·K7", note=tme["cpu"])
add("tm_n_eps", "탐지기별 측정 에피소드 수(정상 원거리 + 좌측 장애물)", tmj["n_episodes_per_detector"], TM + "/timing.json", "AN·H1·K7")
n_steps = {d: tmj["detectors"][d]["n_steps"] for d in DETS}
assert len(set(n_steps.values())) == 1
add("tm_n_steps", "탐지기별 측정 step 수", f"{n_steps['A']:,}", TM + "/timing.json", "AN·H1·K7")
tlog = (ROOT / TM_LOG).read_text(encoding="utf-8").splitlines()
ttail = [l for l in tlog if l.startswith("exit=")][0]
h_, m_, s_ = ttail.split("elapsed=")[1].strip().split(":")
tot = round(int(h_) * 3600 + int(m_) * 60 + float(s_))
add("tm_runtime", "측정 실행 시간(대기 60 s 포함, 반올림)", f"{tot // 60}분 {tot % 60}초", TM_LOG, "AN·H1·K7", note=ttail)
for d in DETS:
    x = tmj["detectors"][d]
    for part, nm in (("detector_ms", "det"), ("combined_ms", "comb"), ("control_ms", "ctrl")):
        s = x[part]
        lbl = {"det": f"{d} 탐지기 단독", "comb": f"제어 1스텝 + {d}", "ctrl": f"제어 1스텝({d} 패스)"}[nm]
        for q in ("p50", "p99", "max"):
            add(f"tm_{d}_{nm}_{q}", f"{lbl} {q}", ms(s[q]), TM + "/timing.json", "AN·H1·K7")
            add(f"tm_{d}_{nm}_{q}_pct", f"{lbl} {q} ÷ 50 ms", pb(s[f"{q}_pct_of_budget"]), TM + "/timing.json", "AN·H1·K7")
        add(f"tm_{d}_{nm}_over", f"{lbl} 50 ms 초과 step 수", s["n_over_budget"], TM + "/timing.json", "AN·H1·K7")
    srt = np.sort(tmz[f"{d}_detector_ms"])[::-1]
    add(f"tm_{d}_det_2nd", f"{d} 탐지기 단독 두 번째로 큰 값", ms(float(srt[1])), TM + "/step_times_ms.npz", "AN·H1·K7")
add("tm_mpc_p99", "v2 MPC solve p99(4개 패스 범위)",
    f"{min(tmj['detectors'][d]['mpc_solve_ms']['p99'] for d in DETS):.2f}~{max(tmj['detectors'][d]['mpc_solve_ms']['p99'] for d in DETS):.2f} ms",
    TM + "/timing.json", "AN·H1·K7")
add("tm_ctrl_p99", "제어 1스텝 p99(4개 패스 범위)",
    f"{min(tmj['detectors'][d]['control_ms']['p99'] for d in DETS):.2f}~{max(tmj['detectors'][d]['control_ms']['p99'] for d in DETS):.2f} ms",
    TM + "/timing.json", "AN·H1·K7")
add("tm_ctrl_max", "제어 1스텝 최댓값(4개 패스 중 최대)", ms(max(tmj["detectors"][d]["control_ms"]["max"] for d in DETS)),
    TM + "/timing.json", "AN·H1·K7")
add("tm_b_over_ratio", "B1·하이브리드 탐지기 p50 ÷ B2 탐지기 p50(범위)",
    f"{min(tmj['detectors'][d]['detector_ms']['p50'] for d in ('B1', 'HYBRID')) / tmj['detectors']['B2']['detector_ms']['p50']:.0f}~"
    f"{max(tmj['detectors'][d]['detector_ms']['p50'] for d in ('B1', 'HYBRID')) / tmj['detectors']['B2']['detector_ms']['p50']:.0f}배",
    TM + "/timing.json", "AN·H1·K7")
# 측정 루프가 제어를 바꾸지 않았는지: 4개 패스의 에피소드 결과를 저장된 A 임계값 실행(같은 seed·조건, H3)과 대조
thr_ref = {(r["scenario"], r["seed"]): (r["outcome"], r["total_steps"]) for r in cload(THR_A3 + "/episodes.csv")}
tm_match = 0
for d in DETS:
    eps = cload(TM + f"/episodes_{d}.csv")
    assert len(eps) == tmj["n_episodes_per_detector"]
    tm_match += sum((r["outcome"], r["total_steps"]) == thr_ref[(r["scenario"], r["seed"])] for r in eps)
add("tm_match", "측정 에피소드 결과(outcome·total_steps) = A 임계값 실행 결과", f"{tm_match}/{len(DETS) * tmj['n_episodes_per_detector']}",
    TM + "/episodes_*.csv", "AN·H1·K7", note=THR_A3 + "/episodes.csv 대조")

# ================= 테스트·환경 =================
def collect(path):
    out = subprocess.run([sys.executable, "-m", "pytest", path, "--collect-only", "-q"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    line = [l for l in out.splitlines() if "collected" in l or "tests collected" in l][-1]
    return int(line.split()[0])
n1, n2 = collect("thesis_v2/tests"), collect("thesis_v2/anomaly/tests")
add("n_tests_base", "기존 단위 테스트 수(pytest 수집)", n1, "thesis_v2/tests", "-")
add("n_tests_anomaly", "이상탐지 테스트 수(pytest 수집)", n2, "thesis_v2/anomaly/tests", "-")
add("n_tests_total", "테스트 합계", n1 + n2, "pytest --collect-only", "-")
add("env_py", "실행 환경(H3·H4)", "Python 3.9.13 / numpy 2.0.2 / scipy 1.13.1 / osqp 1.1.1", CLE + "/env.json", "H4",
    note="H1 노트북은 Python 3.9.12, 나머지 같음")
add("env_ml", "학습 패키지", "scikit-learn 1.6.1 / pandas 2.2.3 / torch 2.8.0+cpu", CLE + "/env.json", "H4")

with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["key", "항목", "값", "근거_파일", "조건_코드", "비고"])
    w.writerows(rows)
print(f"saved: {OUT.relative_to(ROOT)} ({len(rows)} rows)")
