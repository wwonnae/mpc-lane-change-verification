"""
제출본(docs/졸업논문.pdf, 2025.12) 수치 → 개정판 수치 교체표 생성(DESIGN_REVISION.md §3, 집필 기준표).
제출본 값은 repro/docs/pdf_pages/page_NN.png 이미지 판독(THESIS_PAGES.md와 대조). 개정판 값은 저장된 결과 파일에서만 옮기며,
아직 산출되지 않은 값은 "산출대기(Rn)"로 두고 집필 전에 해당 스크립트로 채운다(값을 추정해 넣지 않는다).

열: no | 쪽 | 위치 | 항목 | 제출본_값 | 개정판_값 | 근거_파일 | 조건_코드 | 처리(유지/교체/삭제) | 분류 | 상태 | 비고
분류: 설정유지 / 개정 / 재측정 / 재현불가_대체 / 라벨불일치_대체 / 정의변경_대체 / 내부불일치_정정 / 미적용
상태: 확정 / 산출대기(R1: baseline v1.1 E2 재생 통계, R2: 공식 계산시간 보충 측정, R3: eval3 v2·S10 재생 통계)
조건 코드(부록 B): E1/E2/E3 데이터, D dev, T0 계산시간 seed 0~99(paper), H1 공식 호스트, '-' 설정값

사용(저장소 루트): python docs/revision/scripts/make_revision_numbers.py
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/revision/REVISION_NUMBERS.csv"

CFG = "thesis_v2/baseline/config.py"
SD = "repro/docs/SETTINGS_DECISION.md"
TV3 = "thesis_v2/results/timing_v3/20260925_002628_DESKTOP-MDCKRJS_baseline/timing_baseline.json"
EV2 = "thesis_v2/results/eval_v2/20260924_214446_DESKTOP-MDCKRJS/all_eval_v2_summary.json"
V2 = "thesis_v2/results/i4_student_v2/20260925_092109_DESKTOP-MDCKRJS"
DS = f"{V2}/dataset/dataset_summary.json"
TS10 = f"{V2}/S10/eval/timing/timing.json"
MAE3 = f"{V2}/eval3/mae_models.json"
J3 = "repro/2c_analysis/out/i4_eval3_judgement/eval3_judgement.json"
R1 = "산출대기(R1)"
R2 = "산출대기(R2)"
R3 = "산출대기(R3)"

rows = []


def add(page, loc, item, old, new, src, cond, act, cat, status="확정", note=""):
    rows.append([len(rows) + 1, page, loc, item, old, new, src, cond, act, cat, status, note])


def keep(page, loc, item, val, src=CFG, note=""):
    add(page, loc, item, val, val, src, "-", "유지", "설정유지", "확정", note)


# ---------------- III. 시스템 설계 ----------------
keep(6, "III.1", "제어 주기", "20Hz / 0.05s")
keep(6, "III.2(1)", "차선 폭", "0.30 m")
keep(6, "III.2(1)", "L2 중심", "y=0 m")
keep(6, "III.2(1)", "L1 중심", "y=0.30 m")
keep(6, "III.2(1)", "RC카 차폭(서술)", "0.15 m")
keep(6, "III.2(1)", "장애물 위치 범위", "U(0.5, 2.0) m", note="기준점=차량 전단으로 명시(SETTINGS_DECISION §12, 로그 REQ-SIM-02a)")
keep(6, "III.2(1)", "초기 속도 범위", "U(0.3, 0.5) m/s")
keep(6, "표1", "축간거리 L", "0.20 m")
keep(6, "표1", "차폭 B", "0.15 m")
keep(7, "표1", "최대 조향각", "±25 deg")
keep(7, "표1", "속도 범위", "0.0~0.5 m/s")
keep(7, "표1", "최대 조향각 변화율", "200 deg/s")
keep(7, "III.2(3)", "IR 센서 수·간격", "3개, 0.04 m", note="패턴→ey_line 변환표는 [공백] 결정(SETTINGS_DECISION §9)")
keep(7, "III.3", "쿨다운", "0.3 s")
keep(7, "III.3", "예측 구간", "0.75 s (15 step at 20Hz)")
add(7, "III.3", "Student 입력 차원", "9", "10 (+ψ)", SD + " §20", "-", "교체", "개정", note="[개정] 3건 중 1")
keep(7, "III.3", "Student 출력 차원", "2 (δ, v_target)")
# ---------------- IV. 의사결정 및 경로 계획 ----------------
keep(8, "IV.1(1)", "G_TRIG", "1.2 m")
keep(8, "IV.1(1)", "EVADE_L 목표 y", "0.30 m")
keep(8, "IV.1(1)/표2", "EVADE_L→KEEP_L1", "|y−0.30| ≤ 0.08 m")
keep(8, "IV.1(1)/표2", "T_KEEP_L1_MIN", "0.6 s", note="right_clear 조건 추가 [해석](SETTINGS_DECISION §14)")
add(8, "IV.1(1)/표2", "RETURN_TO_L2→KEEP_L2 |y| 임계값", "0.20 m", "0.08 m", SD + " 개정1, repro/docs/FEASIBILITY_CHECK.md", "-",
    "교체", "개정", note="[개정] 3건 중 1: 한 스텝 최대 이동 0.0086~0.0125m < 필요 0.05m")
keep(8, "IV.1(1)/표2", "RETURN_TO_L2→KEEP_L2 |ψ|", "≤ 20°")
keep(8, "표2", "KEEP_L2→EVADE_L", "front_gap < 1.2 m AND left_clear")
keep(8, "표2", "모든 상태→SAFE_STOP", "front_gap < 0.20 m AND left_clear=False", note="SAFE_STOP 종단 상태 명시(§1)")
keep(8, "IV.1(3)", "Δδ_max", "200 deg/s × 0.05 s = 10 deg/step")
keep(9, "IV.2(1)", "Δt", "0.05 s")
keep(9, "표3", "q_y", "100.0")
keep(9, "표3", "q_ψ", "25.0")
keep(9, "표3", "r_δ", "2.0")
keep(9, "표3", "r_Δδ", "5.0", note="차분 항은 비대각 Hessian으로 구현(REQ-MPC-03a)")
keep(9, "표3", "N", "15 (0.75 s)")
keep(9, "IV.2(3)", "조향각 제약", "−25° ≤ δ ≤ 25°")
keep(9, "IV.2(3)", "L2 위치 제약", "−0.15 ≤ y ≤ 0.15")
keep(9, "IV.2(3)", "L1 위치 제약", "0.15 ≤ y ≤ 0.45")
keep(9, "IV.2(3)", "차선 변경 구간 위치 제약", "−0.15 ≤ y ≤ 0.45")
keep(10, "IV.2(3)", "헤딩각 제약", "−80° ≤ ψ ≤ 80°")
keep(10, "IV.2(4)", "fallback K_p", "1.0", note="단위 rad/m [해석](SETTINGS_DECISION §11)")
keep(10, "IV.3(1)", "v_ref", "0.5 m/s")
keep(10, "IV.3(1)", "SAFE_STOP 속도", "0")
keep(10, "IV.3(2)", "G_SAFE_MIN", "0.20 m")
keep(10, "IV.4", "K_ey", "1.5", note="단위 rad/m 명시 [해석](SETTINGS_DECISION §17)")
# ---------------- V. 모방학습 ----------------
keep(11, "V.1(1)", "장애물 위치(데이터 생성)", "0.5~2.0 m")
keep(11, "V.1(1)", "초기 속도(데이터 생성)", "0.3~0.5 m/s")
add(11, "V.1(1)", "초기 횡방향 위치 분포", "±0.05m Gaussian", "TruncatedNormal(0, 0.05², [−0.15, 0.15])", SD + " 개정2", "-",
    "교체", "개정", note="[개정] 3건 중 1: 절단 없으면 0.27% 확률로 시작부터 제약 충족 불가")
keep(11, "V.1(1)", "에피소드 최대 길이", "10 s (200 step)", note="+관찰 20 step(OBSERVE_STEPS) [공백]")
add(11, "V.1(3)", "입력 특징 차원", "9", "10 (+ψ)", SD + " §20", "-", "교체", "개정", note="[개정] 3건 중 1(중복 표기 위치)")
add(11, "V.1(3)", "수집 에피소드 수", "100", "1,000 (dev paper 100 + S3 dev 900)", DS, "D", "교체", "재현불가_대체",
    note="19,129 계열 근거 로그 없음(로그 2026-09-17)")
add(11, "V.1(3)", "에피소드당 평균 step", "191", "115.1 (MPC 호출 스텝 기준)", DS, "D", "교체", "정의변경_대체",
    note="제출본은 전체 step, 개정판은 MPC 호출 스텝만 표본")
add(11, "V.1(3)", "총 샘플 수", "19,129", "115,076", DS, "D", "교체", "재현불가_대체")
keep(12, "표4", "은닉층 크기", "256-256-128")
keep(12, "표4", "Dropout", "0.15 (×3)")
add(12, "표4", "FC1 입력", "9", "10", SD + " §20", "-", "교체", "개정", note="[개정] 3건 중 1(중복 표기 위치)")
add(12, "V.2(1)", "총 파라미터 수", "약 135,000", "102,786 (9입력) / 103,042 (10입력, S10)", "thesis_v2/improved/student_i4/model.py(직접 계산)",
    "-", "교체", "내부불일치_정정", note="표 4 구조로 계산한 학습 파라미터 수와 불일치")
keep(12, "V.3(1)", "손실 함수", "MSE (정규화 공간, δ·v_target)")
keep(13, "표5", "Optimizer", "Adam")
keep(13, "표5", "Learning Rate", "1e-3")
keep(13, "표5", "Batch Size", "256")
keep(13, "표5", "Epochs", "50", note="50 전부 실행·검증손실 최저 체크포인트 [해석](DESIGN_I4 §2-1)")
keep(13, "표5", "Train/Val Split", "85/15", note="에피소드 단위 계층 분할")
add(13, "V.3(3)", "입력 노이즈 증강", "N(0, 0.01²)", "미적용", "repro/docs/DESIGN_I4.md", "-", "삭제", "미적용",
    note="I4/S10 학습에 적용하지 않음 — 개정판에 미적용 사실과 이유 명시 필요(사용자 결정 대기)")
add(13, "V.3(3)", "상태별 데이터 밸런싱(복제·제거)", "적용", "미적용", "repro/docs/DESIGN_I4.md §1-4", "-", "삭제", "미적용",
    note="사용자 결정으로 오버샘플링·가중 삭제(2026-09-25)")
# ---------------- VI.1 ----------------
add(13, "VI.1", "평가 시나리오 수", "100", "100 (E2 paper seed 200~299)", EV2, "E2", "교체", "재측정")
# ---------------- VI.2 표 6 ----------------
for st, vals in [("KEEP_L2", ("0.035 ± 0.028", "27.3 ± 22.1", "−0.82 ± 3.45", "56.3")),
                 ("EVADE_L", ("0.110 ± 0.065", "29.5 ± 18.4", "5.23 ± 7.12", "2.1")),
                 ("KEEP_L1", ("0.289 ± 0.041", "35.4 ± 14.2", "−1.45 ± 4.89", "6.6")),
                 ("RETURN_TO_L2", ("0.255 ± 0.096", "15.8 ± 12.7", "−8.91 ± 6.34", "35.0"))]:
    for name, v in zip(("횡방향 오차 m", "헤딩 절댓값 deg", "조향각 deg", "체류 비율 %"), vals):
        add(13, "표6", f"{st} {name}", v, R1, "repro/revision 스크립트 R1(baseline v1.1 E2 재생)", "E2", "교체", "재측정", R1)
for item, v in [("KEEP_L2 체류 비율", "56.3%"), ("KEEP_L2 횡방향 오차", "0.035 m"), ("EVADE_L 체류 비율", "2.1%"),
                ("RETURN_TO_L2 체류 비율", "35.0%")]:
    add(14, "VI.2(1) 본문", item, v, R1, "R1", "E2", "교체", "재측정", R1)
# ---------------- 표 7 ----------------
for item, v in [("평균 속도", "0.458 ± 0.048 m/s"), ("최소 속도", "0.301 m/s"), ("최대 속도", "0.500 m/s"),
                ("최소 front_gap", "0.648 m")]:
    add(14, "표7", item, v, R1, "R1", "E2", "교체", "라벨불일치_대체", R1,
        "제출본 값은 교사 규칙(상수 0.5)과 불일치, Student 결과와 근접(로그 Table 7·11)" if "속도" in item else
        "주입 front_gap 감소식 마지막 값과 일치 추정(로그 '장애물 위치')")
add(14, "표7", "충돌 횟수", "0", "5/100 (95% CI 2.2~11.2%)", EV2, "E2", "교체", "재측정",
    note="제출본 코드에 기하 충돌 판정 없음 — 개정판은 회전 사각형 판정")
add(14, "표7", "회피 성공률", "100.0%", "95/100 (95% CI 88.8~97.8%)", EV2, "E2", "교체", "재측정")
for item, v in [("평균 속도(본문)", "0.458 m/s"), ("최소 front_gap(본문)", "0.648 m")]:
    add(14, "VI.2(1) 본문", item, v, R1, "R1", "E2", "교체", "라벨불일치_대체", R1)
add(14, "그림1 본문", "조향각 MAE(누적 오차 서술)", "1.20°", "0.512° (S10, eval3 개루프)", MAE3, "E3", "교체", "재측정",
    note="교사·입력·데이터가 달라 직접 비교 불가")
# ---------------- 표 8 + 본문 ----------------
for item, v, nv, stt in [("평균", "1.091", "0.098", "확정"), ("중앙값", "1.035", "0.091", "확정"), ("표준편차", "0.152", R2, R2),
                         ("최소", "0.823", R2, R2), ("최대", "5.747", "1.414", "확정"), ("95 백분위", "1.312", "0.124", "확정"),
                         ("99 백분위", "1.524", "0.233 (주 지표)", "확정")]:
    add(15, "표8", f"MPC 계산시간 {item} (ms)", v, nv, TV3, "T0-H1", "교체", "재현불가_대체", stt,
        ("제출본 값은 legacy_2025/analysis.py 상수" if item in ("평균", "표준편차", "최대") else "제출본 값의 출처 미발견(상수·측정 코드 없음)")
        + "(로그 '계산시간류 수치 하드코딩' 2026-09-26 정정); baseline v1.1 paper, n=11,670")
add(15, "표8", "벤치마크 횟수", "3,000회", "11,670회(seed 0~99 전 MPC 호출)", TV3, "T0-H1", "교체", "정의변경_대체")
add(15, "VI.2(2) 본문", "측정 환경", "Intel Core i7, 16GB RAM", "DESKTOP-MDCKRJS, AC+최고 성능 확인", TV3.replace("timing_baseline.json", "env.json"),
    "H1", "교체", "재측정")
add(15, "VI.2(2) 본문", "전체 제어 주기 평균", "3.23 ms", "0.092 ms (p99 0.264)", TV3, "T0-H1", "교체", "재현불가_대체")
add(15, "VI.2(2) 본문", "차선 변경 구간 평균", "3.71 ms", R2, "R2(상태별 스텝 시간)", "T0-H1", "교체", "재현불가_대체", R2)
add(15, "VI.2(2) 본문", "EVADE_L 최대", "5.64 ms", R2, "R2", "T0-H1", "교체", "재현불가_대체", R2)
add(15, "VI.2(2) 본문", "20Hz 예산 대비", "11.3%", "p99 기준 0.53%(제어 1스텝 전체)", TV3, "T0-H1", "교체", "재현불가_대체")
# ---------------- VI.3 표 9·10 ----------------
add(15, "VI.3(1) 본문", "에피소드/샘플", "100 / 19,129", "1,000 / 115,076", DS, "D", "교체", "재현불가_대체")
for item, v, nv in [("총 에피소드", "100", "1,000"), ("총 샘플", "19,129", "115,076"), ("에피소드당 평균 샘플", "191.3", "115.1"),
                    ("에피소드당 최소 샘플", "142", "91"), ("에피소드당 최대 샘플", "267", "150"), ("평균 주행 시간", "9.6 s", R1)]:
    add(15, "표9", item, v, nv, DS if nv != R1 else "R1", "D" if nv != R1 else "E2", "교체",
        "재현불가_대체", "확정" if nv != R1 else R1, "개정판 샘플=MPC 호출 스텝(정의 다름)")
for st, n, p, nn, pp in [("KEEP_L2", "10,770", "56.3", "8,176", "7.1"), ("EVADE_L", "402", "2.1", "46,001", "40.0"),
                         ("KEEP_L1", "1,263", "6.6", "4,453", "3.9"), ("RETURN_TO_L2", "6,694", "35.0", "56,446", "49.1"),
                         ("SAFE_STOP", "0", "0.0", "0", "0.0")]:
    add(15 if st in ("KEEP_L2", "EVADE_L", "KEEP_L1") else 16, "표10", f"{st} 샘플 수", n, nn, DS, "D", "교체", "정의변경_대체",
        note="개정판은 MPC 호출 스텝(학습 표본) — 폐루프 체류는 표6에서 별도")
    add(15 if st in ("KEEP_L2", "EVADE_L", "KEEP_L1") else 16, "표10", f"{st} 비율 %", p, pp, DS, "D", "교체", "정의변경_대체")
for item, v in [("KEEP_L2 비율(본문)", "56.3%"), ("EVADE_L 비율(본문)", "2.1%")]:
    add(16, "VI.3(1) 본문", item, v, "7.1% / 40.0%(MPC 호출 스텝)", DS, "D", "교체", "정의변경_대체")
# ---------------- 표 11 ----------------
for var, vals in [("조향각 deg", ("−2.73", "6.79", "−12.44", "24.99")), ("속도 m/s", ("0.458", "0.048", "0.301", "0.500"))]:
    for stat, v in zip(("평균", "표준편차", "최소", "최대"), vals):
        add(16, "표11", f"{var} {stat}", v, R1, "R1", "E2", "교체", "라벨불일치_대체", R1)
for item, v in [("조향각 평균(본문)", "−2.73°"), ("조향각 최소·최대(본문)", "−12.44° / 24.99°")]:
    add(16, "VI.3(2) 본문", item, v, R1, "R1", "E2", "교체", "라벨불일치_대체", R1)
# ---------------- 표 12 ----------------
add(16, "표12", "조향각 위반율/만족률", "0.00 / 100.00", R1, "R1(허용오차 §19 정정 기준)", "E2", "교체", "재측정", R1)
add(16, "표12", "속도 범위", "0~1.5 m/s", "0~0.5 m/s", CFG, "-", "교체", "내부불일치_정정", note="표1(0.0~0.5)과 불일치")
add(16, "표12", "속도 위반율/만족률", "0.00 / 100.00", R1, "R1", "E2", "교체", "재측정", R1)
add(16, "표12", "횡방향 위치 위반율", "0.2143%", R1, "R1", "E2", "교체", "재측정", R1, "[개정] 2건 적용 후 0 기대(E1 baseline 위반 0)")
add(16, "표12", "횡방향 위치 만족률", "99.7857%", R1, "R1", "E2", "교체", "재측정", R1)
add(16, "표12", "헤딩각 위반율/만족률", "0.00 / 100.00", R1, "R1", "E2", "교체", "재측정", R1)
for item, v in [("위반 스텝 수(본문)", "41 / 19,129"), ("위반율(본문)", "0.2143% (0.21%)"), ("만족률(본문)", "99.7857%")]:
    add(16, "VI.3(3) 본문", item, v, R1, "R1", "E2", "교체", "재측정", R1)
# ---------------- 표 13 ----------------
for var, vals in [("조향각 변화율 deg/step", ("1.483", "1.827", "0.000", "10.000")),
                  ("속도 변화율 m/s/step", ("0.001", "0.002", "0.000", "0.015"))]:
    for stat, v in zip(("평균", "표준편차", "최소", "최대"), vals):
        add(17, "표13", f"{var} {stat}", v, R1, "R1", "E2", "교체", "재측정", R1)
add(17, "표13", "충돌 횟수", "0", "5 (E2, baseline v1.1)", EV2, "E2", "교체", "재측정")
add(17, "VI.3(4) 본문", "조향각 변화율 평균·최대", "1.483 / 10.000 deg/step", R1, "R1", "E2", "교체", "재측정", R1)
# ---------------- 표 14 ----------------
for st, tgt, mean, rms in [("KEEP_L2", "0.00", "0.029", "0.037"), ("EVADE_L", "0.30", "0.104", "0.128"),
                           ("KEEP_L1", "0.30", "0.026", "0.032"), ("RETURN_TO_L2", "0.00", "0.245", "0.263")]:
    keep(17, "표14", f"{st} 목표 y", tgt)
    add(17, "표14", f"{st} 평균 오차 m", mean, R1, "R1", "E2", "교체", "재측정", R1)
    add(17, "표14", f"{st} RMS 오차 m", rms, R1, "R1", "E2", "교체", "재측정", R1)
add(17, "VI.3(4) 본문", "KEEP_L2/KEEP_L1 평균 오차", "0.029 / 0.026 m", R1, "R1", "E2", "교체", "재측정", R1)
# ---------------- 그림 2 본문 ----------------
for item, v in [("조향각 평균·표준편차", "−2.73° / 6.79°"), ("속도 분포 중심", "0.46 m/s"), ("최소 front_gap", "0.65 m"),
                ("KEEP_L2 비율", "56.3%")]:
    add(18, "그림2 본문", item, v, R1, "R1", "E2", "교체", "라벨불일치_대체" if "속도" in item or "조향" in item else "재측정", R1)
# ---------------- VI.4 ----------------
add(18, "VI.4(1)", "학습/검증 샘플", "16,360 / 2,769", "97,824 / 17,252 (에피소드 단위 계층 분할)", DS, "D", "교체", "재현불가_대체")
for ds_name, mse, mae_d, mae_v, nmse, nmae in [("Training", "0.082", "1.15", "0.014", "0.0244 (epoch 48)", "—"),
                                               ("Validation", "0.095", "1.24", "0.016", "0.01597", "0.570"),
                                               ("Test(전체)", "0.091", "1.20", "0.015", "—", "0.512 (eval3)")]:
    src = f"{V2}/S10/train_log.json" if ds_name != "Test(전체)" else MAE3
    cond = "D" if ds_name != "Test(전체)" else "E3"
    add(18, "표15", f"{ds_name} MSE(정규화)", mse, nmse, src, cond, "교체" if nmse != "—" else "삭제", "재측정")
    add(18, "표15", f"{ds_name} MAE 조향 deg", mae_d, nmae, src, cond, "교체" if nmae != "—" else "삭제", "재측정",
        note="직접 비교 불가(교사·입력·데이터 다름)")
    add(18, "표15", f"{ds_name} MAE 속도 m/s", mae_v, "≈0 (MPC 호출 스텝의 v_target은 상수, 참고 지표)", src, cond, "교체", "정의변경_대체")
for item, v, nv in [("Train/Val 손실(본문)", "0.082 / 0.095", "0.0244 / 0.01597"), ("조향 MAE(본문)", "1.20° (1.2° 이내)", "0.512°")]:
    add(18, "VI.4(1) 본문", item, v, nv, MAE3 if "MAE" in item else f"{V2}/S10/train_log.json", "E3" if "MAE" in item else "D",
        "교체", "재측정")
# ---------------- 표 16 ----------------
for item, v, nv in [("평균", "0.206", "0.103"), ("중앙값", "0.189", "0.099"), ("표준편차", "0.055", "0.025"),
                    ("최소", "0.152", R2), ("최대", "1.557", "0.988"), ("95 백분위", "0.287", "0.116"),
                    ("99 백분위", "0.354", "0.206 (주 지표)")]:
    add(19, "표16", f"Student 추론 {item} ms (PyTorch e2e)", v, nv, TS10, "T0-H1", "교체", "재현불가_대체",
        R2 if nv == R2 else "확정", "S10, paper, n=11,518; ONNX는 표18")
for item, v, nv in [("평균 대비 배수", "5.30배 빠름", "2.1배(v2 MPC 0.220/PyTorch 0.103)"),
                    ("표준편차 대비", "2.76배 낮음", "8.8배 낮음(0.220/0.025)"), ("최대 대비", "3.69배 낮음", "5.9배 낮음(5.81/0.99)")]:
    add(19, "표16", item, v, nv, TS10, "T0-H1", "교체", "재현불가_대체", note="비교 대상 = v2 MPC(교사)")
add(19, "표16", "벤치마크 횟수", "6,000회", "11,518회(paper 전 MPC 호출 입력)", TS10, "T0-H1", "교체", "정의변경_대체")
for item, v in [("Student 평균(본문)", "0.206 ms"), ("Teacher 평균(본문)", "1.091 ms"), ("배수(본문)", "5.30배"),
                ("표준편차(본문)", "0.055 / 0.152 ms, 2.76배")]:
    add(19, "VI.4(2) 본문", item, v, "표16·18 개정값 참조", TS10, "T0-H1", "교체", "재현불가_대체")
# ---------------- 표 17 ----------------
for item, t, s, r in [("조향각 변화율 deg/step", "1.483", "1.484", "−0.1%"), ("속도 변화율 m/s/step", "0.004", "0.004", "0.0%"),
                      ("조향각 Jerk deg/step²", "0.935", "0.905", "+3.2%")]:
    add(19, "표17", f"{item} Teacher", t, R3, "R3(eval3 v2 MPC 재생)", "E3", "교체", "재측정", R3, "사용자 결정 D5: 재측정")
    add(19, "표17", f"{item} Student", s, R3, "R3(eval3 S10 재생)", "E3", "교체", "재측정", R3)
    add(19, "표17", f"{item} 개선율", r, R3, "R3", "E3", "교체", "재측정", R3)
add(19, "VI.4(3) 본문", "조향 변화율·Jerk 차이", "1.483 / 1.484, 3.2%", R3, "R3", "E3", "교체", "재측정", R3)
add(19, "표13·표17", "속도 변화율(표13 0.001 vs 표17 0.004)", "0.001 / 0.004", "R1·R3 재측정으로 해소", "R1, R3", "E2/E3", "교체",
    "내부불일치_정정", R1, "같은 '학습 데이터 기반' 지표가 표13·표17에서 다름")
# ---------------- 그림 3 본문 (p.20) ----------------
add(20, "그림3 본문", "속도 분포 중심", "0.46 m/s", R3, "R3", "E3", "교체", "라벨불일치_대체", R3)
# ---------------- 표 18 ----------------
t18 = [("평균", "1.091", "0.206", "5.30배", "0.220", "0.103 / 0.022"), ("중앙값", "1.035", "0.189", "5.48배", "0.160", "0.099 / 0.022"),
       ("표준편차", "0.152", "0.055", "2.76배", "0.220", "0.025 / 0.003"), ("최소", "0.823", "0.152", "5.41배", R2, R2),
       ("최대", "5.747", "1.557", "3.69배", "5.809", "0.988 / 0.199"), ("95 백분위", "1.312", "0.287", "4.57배", "0.489", "0.116 / 0.023"),
       ("99 백분위", "1.524", "0.354", "4.31배", "1.397", "0.206 / 0.027")]
for stat, t, s, r, nt, ns in t18:
    stt = R2 if R2 in (nt, ns) else "확정"
    add(20, "표18", f"Teacher {stat} ms", t, nt, TS10, "T0-H1", "교체", "재현불가_대체", stt, "Teacher=v2 MPC(교사)")
    add(20, "표18", f"Student {stat} ms", s, ns, TS10, "T0-H1", "교체", "재현불가_대체", stt, "PyTorch e2e / ONNX e2e")
    add(20, "표18", f"속도 향상 {stat}", r, "개정값으로 재계산(p99: PyTorch 6.8배, ONNX 52배)" if stat == "99 백분위" else "개정값으로 재계산",
        TS10, "T0-H1", "교체", "재현불가_대체", stt)
add(20, "VI.4(4) 본문", "평균 배수", "5.30배", "2.1배(PyTorch) / 9.8배(ONNX), p99 6.8배 / 52배", TS10, "T0-H1", "교체", "재현불가_대체")
# ---------------- VI.4(5) 예상 성능 ----------------
for item, v, nv, src, cond in [("조향 MAE", "1.2°", "0.512°(eval3 개루프) + 폐루프 100/100·900/900", J3, "E3"),
                               ("속도 MAE", "0.015 m/s", "≈0(참고)", MAE3, "E3"), ("조향 변화율 차이", "+0.1%", R3, "R3", "E3"),
                               ("추론 배수", "5.3배", "p99 6.8배(PyTorch)/52배(ONNX)", TS10, "T0-H1")]:
    add(20, "VI.4(5)", item, v, nv, src, cond, "교체", "재측정" if "배수" not in item else "재현불가_대체",
        R3 if nv == R3 else "확정", "제출본은 '예상'으로 서술 — 개정판은 폐루프 실측으로 대체")
# ---------------- VI.5 논의 ----------------
for item, v, nv, src, cond, cat in [
        ("샘플 수", "19,129", "115,076", DS, "D", "재현불가_대체"),
        ("조향·속도·헤딩 제약 만족", "100%", R1, "R1", "E2", "재측정"),
        ("횡방향 위치 만족률", "99.79%", R1, "R1", "E2", "재측정"),
        ("MPC 평균 계산시간", "1.091 ms", "0.098 ms(baseline) / 0.220 ms(v2, p99 1.397)", TV3, "T0-H1", "재현불가_대체"),
        ("조향 MAE", "1.2°", "0.512°", MAE3, "E3", "재측정"),
        ("Teacher 조향 표준편차", "6.79°", R1, "R1", "E2", "라벨불일치_대체"),
        ("MAE/표준편차 비", "18%", R1, "R1", "E2", "재측정"),
        ("추론 속도 배수", "5.3배", "p99 6.8배/52배", TS10, "T0-H1", "재현불가_대체"),
        ("표준편차 배수", "2.8배", "8.8배(PyTorch)", TS10, "T0-H1", "재현불가_대체")]:
    add(20 if item in ("샘플 수", "조향·속도·헤딩 제약 만족", "횡방향 위치 만족률", "MPC 평균 계산시간") else 21, "VI.5", item, v, nv,
        src, cond, "교체", cat, R1 if nv == R1 else "확정")
# ---------------- VII 결론 ----------------
for item, v, nv, src, cond, cat in [
        ("에피소드 수", "100", "100 (E2) / 1,000 (E3 paper+S3)", EV2, "E2", "재측정"),
        ("회피 성공률", "100%", "baseline 95/100, v2 100/100 (E2); S10 100/100·900/900 (E3)", EV2 + ", " + J3, "E2/E3", "재측정"),
        ("충돌", "0회", "baseline 5, v2 0 (E2); S10 0 (E3)", EV2 + ", " + J3, "E2/E3", "재측정"),
        ("평균 횡방향 오차", "0.035 m", R1, "R1", "E2", "재측정"),
        ("조향·속도·헤딩 제약 만족", "100%", R1, "R1", "E2", "재측정"),
        ("횡방향 위치 만족률", "99.79%", R1, "R1", "E2", "재측정"),
        ("조향 MAE", "1.2°", "0.512°", MAE3, "E3", "재측정"),
        ("속도 MAE", "0.015 m/s", "≈0(참고)", MAE3, "E3", "정의변경_대체"),
        ("Student 추론 평균", "0.206 ms", "0.103 ms(PyTorch) / 0.022 ms(ONNX)", TS10, "T0-H1", "재현불가_대체"),
        ("Teacher 평균", "1.091 ms", "0.220 ms(v2 MPC)", TS10, "T0-H1", "재현불가_대체"),
        ("추론 배수", "5.3배", "p99 6.8배/52배", TS10, "T0-H1", "재현불가_대체"),
        ("표준편차 배수", "2.8배", "8.8배(PyTorch)", TS10, "T0-H1", "재현불가_대체")]:
    add(21, "VII", item, v, nv, src, cond, "교체", cat, R1 if nv == R1 else "확정")


# =====================================================================================
# S2: R1·R3 결과로 산출대기 행 채우기 + 서술 위치 + 전사 검증 열 (DESIGN_REVISION §3-1, §3-4)
# 값은 저장된 JSON에서 직접 포맷(수동 전사 없음). R2 행은 R2 실행 후 같은 방식으로 채움.
# =====================================================================================
import json as _json

R1J = ROOT / "docs/revision/data/r1_baseline_e2_stats.json"
R2J = ROOT / "docs/revision/data/r2_timing_supplement/r2_timing.json"
R3J = ROOT / "docs/revision/data/r3_eval3_stats.json"
R1F = "docs/revision/data/r1_baseline_e2_stats.json"
R2F = "docs/revision/data/r2_timing_supplement/r2_timing.json"
R3F = "docs/revision/data/r3_eval3_stats.json"


def _f(x, n=3):
    return f"{x:.{n}f}".replace("-", "−")


def _pm(s, n=3):
    return f"{_f(s['mean'], n)} ± {_f(s['std'], n)}"


def build_fill():
    fill = {}
    if R1J.exists():
        r1 = _json.load(open(R1J, encoding="utf-8"))
        t6 = r1["table6"]
        for st in ("KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2"):
            fill[("표6", f"{st} 횡방향 오차 m")] = (_pm(t6[st]["y_abs"]), R1F, "|y|(L2 중심 기준 거리) — 제출본 표6 정의 추정")
            fill[("표6", f"{st} 헤딩 절댓값 deg")] = (_pm(t6[st]["psi_abs_deg"], 1), R1F, "")
            fill[("표6", f"{st} 조향각 deg")] = (_pm(t6[st]["delta_deg"], 2), R1F, "차량 입력 δ(후처리 후)")
            fill[("표6", f"{st} 체류 비율 %")] = (_f(t6[st]["dwell_pct"], 1), R1F, "전 스텝(관찰 구간 포함) 대비")
            fill[("표14", f"{st} 평균 오차 m")] = (_f(t6[st]["track_err"]["mean"]), R1F, "|y − 목표선|")
            fill[("표14", f"{st} RMS 오차 m")] = (_f(t6[st]["track_err"]["rms"]), R1F, "|y − 목표선|")
        fill[("VI.2(1) 본문", "KEEP_L2 체류 비율")] = (_f(t6["KEEP_L2"]["dwell_pct"], 1) + "%", R1F, "")
        fill[("VI.2(1) 본문", "KEEP_L2 횡방향 오차")] = (_f(t6["KEEP_L2"]["y_abs"]["mean"]) + " m", R1F, "|y|")
        fill[("VI.2(1) 본문", "EVADE_L 체류 비율")] = (_f(t6["EVADE_L"]["dwell_pct"], 1) + "%", R1F, "")
        fill[("VI.2(1) 본문", "RETURN_TO_L2 체류 비율")] = (_f(t6["RETURN_TO_L2"]["dwell_pct"], 1) + "%", R1F, "")
        sp, sd = r1["speed"], r1["steering_final"]
        ev = r1["front_gap_at_evade_entry"]
        fg_txt = (f"{_f(r1['front_gap_min_all'])} m(최솟값 — 차량 전단이 장애물 옆을 지날 때 0, 충돌 아님) / "
                  f"EVADE_L 진입 시 {_f(ev['mean'])} ± {_f(ev['std'])} m(최소 {_f(ev['min'])})")
        fill[("표7", "평균 속도")] = (_pm(sp) + " m/s", R1F, "각 스텝 운동에 쓰인 속도(첫 스텝 v0 포함)")
        fill[("표7", "최소 속도")] = (_f(sp["min"]) + " m/s", R1F, "초기 v0 최솟값")
        fill[("표7", "최대 속도")] = (_f(sp["max"]) + " m/s", R1F, "")
        fill[("표7", "최소 front_gap")] = (fg_txt, R1F, r1["front_gap_note"])
        fill[("VI.2(1) 본문", "평균 속도(본문)")] = (_f(sp["mean"]) + " m/s", R1F, "")
        fill[("VI.2(1) 본문", "최소 front_gap(본문)")] = (fg_txt, R1F, "")
        fill[("표9", "평균 주행 시간")] = (_f(r1["episode_duration_s"]["mean"], 2) + " s", R1F,
                                     "E2 baseline 에피소드 평균 길이(표9의 나머지 행은 학습 데이터셋 D)")
        for stat, key in (("평균", "mean"), ("표준편차", "std"), ("최소", "min"), ("최대", "max")):
            fill[("표11", f"조향각 deg {stat}")] = (_f(sd[key], 2), R1F, "차량 입력 δ(후처리 후)")
            fill[("표11", f"속도 m/s {stat}")] = (_f(sp[key]), R1F, "")
        fill[("VI.3(2) 본문", "조향각 평균(본문)")] = (_f(sd["mean"], 2) + "°", R1F, "")
        fill[("VI.3(2) 본문", "조향각 최소·최대(본문)")] = (f"{_f(sd['min'], 2)}° / {_f(sd['max'], 2)}°", R1F, "±25° clip 경계")
        c = r1["constraints"]
        fill[("표12", "조향각 위반율/만족률")] = (
            f"{_f(100 - c['delta_ok_pct_s19'], 2)} / {_f(c['delta_ok_pct_s19'], 2)} (허용오차 §19 정정값; 정정 전 상수 기준 "
            f"{c['delta_viol_stored_const']}/{c['delta_checked']} 스텝 초과)", R1F, "MPC 원출력 δ_raw")
        fill[("표12", "속도 위반율/만족률")] = (f"{_f(100 - c['v_ok_pct'], 2)} / {_f(c['v_ok_pct'], 2)}", R1F, "0 ≤ v ≤ 0.5")
        fill[("표12", "횡방향 위치 위반율")] = (_f(100 - c["y_ok_pct"], 4) + "%", R1F, f"{c['y_viol']}/{c['y_checked']} 스텝")
        fill[("표12", "횡방향 위치 만족률")] = (_f(c["y_ok_pct"], 4) + "%", R1F, "")
        fill[("표12", "헤딩각 위반율/만족률")] = (f"{_f(100 - c['psi_ok_pct'], 2)} / {_f(c['psi_ok_pct'], 2)}", R1F, "")
        fill[("VI.3(3) 본문", "위반 스텝 수(본문)")] = (f"{c['y_viol']} / {c['y_checked']:,}", R1F, "")
        fill[("VI.3(3) 본문", "위반율(본문)")] = (_f(100 - c["y_ok_pct"], 4) + "%", R1F, "")
        fill[("VI.3(3) 본문", "만족률(본문)")] = (_f(c["y_ok_pct"], 4) + "%", R1F, "")
        dr, vr = r1["steering_rate"], r1["speed_rate"]
        for stat, key in (("평균", "mean"), ("표준편차", "std"), ("최소", "min"), ("최대", "max")):
            fill[("표13", f"조향각 변화율 deg/step {stat}")] = (_f(dr[key]), R1F, "|Δδ_final|, 에피소드 내 차분")
            fill[("표13", f"속도 변화율 m/s/step {stat}")] = (_f(vr[key], 4), R1F, "|Δv|, 에피소드 내 차분")
        fill[("VI.3(4) 본문", "조향각 변화율 평균·최대")] = (f"{_f(dr['mean'])} / {_f(dr['max'])} deg/step", R1F, "")
        fill[("VI.3(4) 본문", "KEEP_L2/KEEP_L1 평균 오차")] = (
            f"{_f(t6['KEEP_L2']['track_err']['mean'])} / {_f(t6['KEEP_L1']['track_err']['mean'])} m", R1F, "")
        fill[("그림2 본문", "조향각 평균·표준편차")] = (f"{_f(sd['mean'], 2)}° / {_f(sd['std'], 2)}°", R1F, "")
        fill[("그림2 본문", "속도 분포 중심")] = (_f(sp["mean"]) + " m/s", R1F, "")
        fill[("그림2 본문", "최소 front_gap")] = (fg_txt, R1F, "")
        fill[("그림2 본문", "KEEP_L2 비율")] = (_f(t6["KEEP_L2"]["dwell_pct"], 1) + "%", R1F, "")
        fill[("VI.5", "조향·속도·헤딩 제약 만족")] = (
            f"조향 {_f(c['delta_ok_pct_s19'], 2)}% · 속도 {_f(c['v_ok_pct'], 2)}% · 헤딩 {_f(c['psi_ok_pct'], 2)}%", R1F, "")
        fill[("VI.5", "횡방향 위치 만족률")] = (_f(c["y_ok_pct"], 2) + "%", R1F, "")
        fill[("VII", "평균 횡방향 오차")] = (_f(t6["KEEP_L2"]["y_abs"]["mean"]) + " m (KEEP_L2 |y|)", R1F,
                                     "제출본 0.035는 표6 KEEP_L2 값 — 전체 평균이 아님(확인필요 참고)")
        fill[("VII", "조향·속도·헤딩 제약 만족")] = fill[("VI.5", "조향·속도·헤딩 제약 만족")]
        fill[("VII", "횡방향 위치 만족률")] = fill[("VI.5", "횡방향 위치 만족률")]
    if R3J.exists():
        r3 = _json.load(open(R3J, encoding="utf-8"))
        t17 = r3["table17_paper"]
        for label, key, n in (("조향각 변화율 deg/step", "steering_rate", 3), ("속도 변화율 m/s/step", "speed_rate", 4),
                              ("조향각 Jerk deg/step²", "steering_jerk", 3)):
            note = ("|Δ²δ_final|(라벨대로 조향각). 제출본 스크립트는 |Δ²v|(속도) — v2 "
                    f"{_f(t17['speed_jerk']['teacher'], 4)}, S10 {_f(t17['speed_jerk']['student'], 4)}") if key == "steering_jerk" else ""
            fill[("표17", f"{label} Teacher")] = (_f(t17[key]["teacher"], n), R3F, "Teacher = v2 MPC, E3 paper 폐루프. " + note)
            fill[("표17", f"{label} Student")] = (_f(t17[key]["student"], n), R3F, "Student = S10, E3 paper 폐루프")
            fill[("표17", f"{label} 개선율")] = (f"{t17[key]['improvement_pct']:+.1f}%".replace("-", "−"), R3F,
                                              "(Teacher−Student)/Teacher, 제출본 부호 규약")
        fill[("VI.4(3) 본문", "조향 변화율·Jerk 차이")] = (
            f"{_f(t17['steering_rate']['teacher'])} / {_f(t17['steering_rate']['student'])}, jerk "
            f"{t17['steering_jerk']['improvement_pct']:+.1f}%".replace("-", "−"), R3F, "S10 jerk가 v2보다 큼(불리한 방향 그대로 보고)")
        fill[("그림3 본문", "속도 분포 중심")] = (_f(r3["by_controller"]["S10"]["paper"]["speed"]["mean"]) + " m/s", R3F, "")
        fill[("VI.4(5)", "조향 변화율 차이")] = (f"{t17['steering_rate']['improvement_pct']:+.1f}%".replace("-", "−"), R3F, "")
        v5 = r3["vi5_mae_over_teacher_std"]
        fill[("VI.5", "Teacher 조향 표준편차")] = (_f(v5["teacher_delta_std"], 2) + "°", R3F, v5["note"])
        fill[("VI.5", "MAE/표준편차 비")] = (_f(v5["ratio_pct"], 1) + "%", R3F, "S10 MAE 0.512° / v2 δ 표준편차")
        if R1J.exists():
            fill[("표13·표17", "속도 변화율(표13 0.001 vs 표17 0.004)")] = (
                f"표13 {_f(r1['speed_rate']['mean'], 4)}(E2 baseline) / 표17 {_f(t17['speed_rate']['teacher'], 4)}(E3 v2)",
                f"{R1F}, {R3F}", "같은 정의(|Δv|)로 재측정 — 개정판에서는 두 표가 같은 정의를 씀")
    if R2J.exists():
        r2 = _json.load(open(R2J, encoding="utf-8"))
        cond_note = "공식 조건" if r2.get("meets_official_condition") else "참고치(공식 조건 미충족)"
        b = r2["baseline_v11"]
        fill[("표8", "MPC 계산시간 표준편차 (ms)")] = (_f(b["mpc_solve_ms"]["std"]), R2F, f"baseline v1.1, R2 {cond_note}")
        fill[("표8", "MPC 계산시간 최소 (ms)")] = (_f(b["mpc_solve_ms"]["min"]), R2F, f"baseline v1.1, R2 {cond_note}")
        lc = b["step_lane_change_states_ms"]
        fill[("VI.2(2) 본문", "차선 변경 구간 평균")] = (_f(lc["mean"]) + " ms", R2F, "EVADE_L·KEEP_L1·RETURN_TO_L2 제어 1스텝 전체")
        fill[("VI.2(2) 본문", "EVADE_L 최대")] = (_f(b["step_by_state_ms"]["EVADE_L"]["max"]) + " ms", R2F, "제어 1스텝 전체")
        pt, ox, v2 = r2["s10_pytorch_e2e_ms"], r2["s10_onnx_e2e_ms"], r2["v2_mpc_solve_ms"]
        fill[("표16", "Student 추론 최소 ms (PyTorch e2e)")] = (_f(pt["min"]), R2F, cond_note)
        fill[("표18", "Teacher 최소 ms")] = (_f(v2["min"]), R2F, "v2 MPC, " + cond_note)
        fill[("표18", "Student 최소 ms")] = (f"{_f(pt['min'])} / {_f(ox['min'])}", R2F, "PyTorch / ONNX, " + cond_note)
        fill[("표18", "속도 향상 최소")] = (f"{v2['min'] / pt['min']:.1f}배 / {v2['min'] / ox['min']:.1f}배", R2F, "")
    return fill


# ---- R2 단일 실행으로 계산시간 표 통일(S2 마무리) ----
# 표 8·16·18과 본문 계산시간 수치는 한 표 안에서 서로 다른 실행(timing_v3 / S10 timing / R2)이 섞이지 않도록 **R2 한 번의 실행**
# (공식 조건, seed 0~99 paper)에서 모두 가져온다. timing_v3·S10 timing 값은 교차 확인용 — 평균은 실행 간 3% 이내로 안정, 1ms 미만
# 양의 p99는 실행 간 최대 31% 변동(DESIGN_REVISION §3-5, RESULT_I4 §12) → 본문은 p99 배수를 실행 범위로 병기.
def build_r2_override():
    ov = {}
    if not R2J.exists():
        return ov
    r2 = _json.load(open(R2J, encoding="utf-8"))
    env = _json.load(open(R2J.parent / "env.json", encoding="utf-8"))
    b, v2, pt, ox = r2["baseline_v11"]["mpc_solve_ms"], r2["v2_mpc_solve_ms"], r2["s10_pytorch_e2e_ms"], r2["s10_onnx_e2e_ms"]
    step = r2["baseline_v11"]["step_total_ms"]
    note = "R2 단일 실행(공식 조건 meets_official_condition=%s, seed 0~99 paper)" % r2["meets_official_condition"]
    names = [("평균", "mean"), ("중앙값", "p50"), ("표준편차", "std"), ("최소", "min"), ("최대", "max"),
             ("95 백분위", "p95"), ("99 백분위", "p99")]
    for kr, k in names:
        ov[("표8", f"MPC 계산시간 {kr} (ms)")] = (_f(b[k]) + (" (주 지표)" if k == "p99" else ""), R2F, "baseline v1.1, " + note)
        ov[("표16", f"Student 추론 {kr} ms (PyTorch e2e)")] = (_f(pt[k]) + (" (주 지표)" if k == "p99" else ""), R2F, "S10, " + note)
        ov[("표18", f"Teacher {kr} ms")] = (_f(v2[k]), R2F, "Teacher = v2 MPC, " + note)
        ov[("표18", f"Student {kr} ms")] = (f"{_f(pt[k])} / {_f(ox[k])}", R2F, "S10 PyTorch e2e / ONNX e2e, " + note)
        ov[("표18", f"속도 향상 {kr}")] = (f"{v2[k] / pt[k]:.1f}배 / {v2[k] / ox[k]:.1f}배", R2F, "v2 MPC ÷ Student(PyTorch / ONNX)")
    ov[("표8", "벤치마크 횟수")] = (f"{b['n']:,}회(seed 0~99 전 MPC 호출)", R2F, note)
    ov[("표16", "벤치마크 횟수")] = (f"{pt['n']:,}회(paper 전 MPC 호출 입력)", R2F, note)
    ov[("표16", "평균 대비 배수")] = (f"{v2['mean'] / pt['mean']:.1f}배(v2 MPC {_f(v2['mean'])} / PyTorch {_f(pt['mean'])})", R2F, note)
    ov[("표16", "표준편차 대비")] = (f"{v2['std'] / pt['std']:.1f}배 낮음({_f(v2['std'])} / {_f(pt['std'])})", R2F, note)
    ov[("표16", "최대 대비")] = (f"{v2['max'] / pt['max']:.1f}배 낮음({_f(v2['max'])} / {_f(pt['max'])})", R2F, note)
    ov[("VI.2(2) 본문", "측정 환경")] = (f"{env['hostname']}, AC, 최고 성능 사용자 확인(meets_official_condition={env['power']['meets_official_condition']})",
                                     "docs/revision/data/r2_timing_supplement/env.json", "")
    ov[("VI.2(2) 본문", "전체 제어 주기 평균")] = (f"{_f(step['mean'])} ms (p99 {_f(step['p99'])})", R2F, "baseline v1.1 제어 1스텝 전체")
    ov[("VI.2(2) 본문", "20Hz 예산 대비")] = (f"p99 기준 {100 * step['p99'] / 50:.2f}%(제어 1스텝 전체)", R2F, "")
    p99pt, p99ox, mpt, mox = v2["p99"] / pt["p99"], v2["p99"] / ox["p99"], v2["mean"] / pt["mean"], v2["mean"] / ox["mean"]
    ratio = f"p99 {p99pt:.1f}배(PyTorch) / {p99ox:.1f}배(ONNX)"
    for loc, item in (("VI.4(2) 본문", "Student 평균(본문)"), ("VI.4(2) 본문", "Teacher 평균(본문)"), ("VI.4(2) 본문", "배수(본문)"),
                      ("VI.4(2) 본문", "표준편차(본문)")):
        ov[(loc, item)] = ("표16·18 개정값 참조", R2F, note)
    ov[("VI.4(4) 본문", "평균 배수")] = (f"평균 {mpt:.1f}배 / {mox:.1f}배, {ratio}", R2F, note)
    ov[("VI.4(5)", "추론 배수")] = (ratio, R2F, note)
    ov[("VI.5", "MPC 평균 계산시간")] = (f"{_f(b['mean'])} ms(baseline) / {_f(v2['mean'])} ms(v2, p99 {_f(v2['p99'])})", R2F, note)
    ov[("VI.5", "추론 속도 배수")] = (ratio, R2F, note)
    ov[("VI.5", "표준편차 배수")] = (f"{v2['std'] / pt['std']:.1f}배(PyTorch)", R2F, note)
    ov[("VII", "Student 추론 평균")] = (f"{_f(pt['mean'])} ms(PyTorch) / {_f(ox['mean'])} ms(ONNX)", R2F, note)
    ov[("VII", "Teacher 평균")] = (f"{_f(v2['mean'])} ms(v2 MPC)", R2F, note)
    ov[("VII", "추론 배수")] = (ratio, R2F, note)
    ov[("VII", "표준편차 배수")] = (f"{v2['std'] / pt['std']:.1f}배(PyTorch)", R2F, note)
    return ov


# ---- 속도 배수 행을 실행 범위로(사용자 결정 2026-09-25, OPEN #3) ----
# 같은 공식 조건에서 1ms 미만 양의 p99가 실행 간 −21~−31% 변동하므로(RESULT_I4 §12-1), 배수는 단일 실행 값이 아니라
# 두 공식 실행(S10 timing 실행, R2)의 범위로 쓴다. 이전 단일값(R2)은 비고와 CSV_CHANGELOG.md에 남긴다.
S10RUN = ROOT / "thesis_v2/results/i4_student_v2/20260925_092109_DESKTOP-MDCKRJS/S10/eval/timing/timing.json"
RANGE_NOTE = "변경 이력: 이전 단일값 «{old}»(R2 한 실행) → 두 공식 실행(S10 timing 실행·R2) 범위. 근거: 같은 조건에서 1ms 미만 p99 실행 간 변동 −21~−31%"
CHANGES = []


def _rng(vals, unit="배"):
    a, b = f"{min(vals):.1f}", f"{max(vals):.1f}"
    return f"{a}{unit}" if a == b else f"{a}~{b}{unit}"


def apply_ratio_ranges(ov):
    if not (R2J.exists() and S10RUN.exists()):
        return ov
    r2 = _json.load(open(R2J, encoding="utf-8"))
    s1 = _json.load(open(S10RUN, encoding="utf-8"))["paper"]
    runs = [(s1["v2_mpc_solve_ms"], s1["pytorch_e2e_ms"], s1["onnx_e2e_ms"]),
            (r2["v2_mpc_solve_ms"], r2["s10_pytorch_e2e_ms"], r2["s10_onnx_e2e_ms"])]

    def rr(k, j):  # j=1 PyTorch, 2 ONNX
        vals = [run[0][k] / run[j][k] for run in runs if k in run[0] and k in run[j]]
        return _rng(vals), len(vals)

    def setv(key, new, extra=""):
        old = ov[key][0]
        ov[key] = (new, f"{R2F}, {S10RUN.relative_to(ROOT).as_posix()}",
                   RANGE_NOTE.format(old=old) + (f" {extra}" if extra else ""))
        CHANGES.append((key, old, new))

    names = [("평균", "mean"), ("중앙값", "p50"), ("표준편차", "std"), ("최소", "min"), ("최대", "max"),
             ("95 백분위", "p95"), ("99 백분위", "p99")]
    for kr, k in names:
        (a, na), (b, nb) = rr(k, 1), rr(k, 2)
        extra = "S10 timing 실행에는 최솟값이 기록되지 않아 R2 한 실행 값만 있음(범위 아님)" if na == 1 else ""
        setv(("표18", f"속도 향상 {kr}"), f"{a} / {b}", extra)
    setv(("표16", "평균 대비 배수"), rr("mean", 1)[0] + "(v2 MPC ÷ PyTorch)")
    setv(("표16", "표준편차 대비"), rr("std", 1)[0] + " 낮음(PyTorch)")
    setv(("표16", "최대 대비"), rr("max", 1)[0] + " 낮음(PyTorch)")
    p99 = f"p99 {rr('p99', 1)[0]}(PyTorch) / {rr('p99', 2)[0]}(ONNX)"
    setv(("VI.4(4) 본문", "평균 배수"), f"평균 {rr('mean', 1)[0]} / {rr('mean', 2)[0]}, {p99}")
    for key in (("VI.4(5)", "추론 배수"), ("VI.5", "추론 속도 배수"), ("VII", "추론 배수")):
        setv(key, p99)
    for key in (("VI.5", "표준편차 배수"), ("VII", "표준편차 배수")):
        setv(key, rr("std", 1)[0] + "(PyTorch)")
    return ov


def write_changelog():
    lines = ["# REVISION_NUMBERS.csv 변경 이력", "",
             "## 2026-09-25 속도 배수 행 → 실행 범위(사용자 결정, OPEN #3)", "",
             "근거: 같은 공식 조건(DESKTOP-MDCKRJS, AC, 최고 성능)에서 1 ms 미만 양의 p99가 실행 간 −21~−31% 변동(RESULT_I4 §12-1).",
             "두 공식 실행(S10 timing 실행, R2)의 배수를 범위로 적고, 이전 단일값(R2 한 실행)을 아래와 각 행 비고에 남김.", "",
             "| 위치 | 항목 | 이전 값(R2 단일) | 새 값(범위) |", "|---|---|---|---|"]
    for (loc, item), old, new in CHANGES:
        lines.append(f"| {loc} | {item} | {old} | {new} |")
    (ROOT / "docs/revision/CSV_CHANGELOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


CHECK_POLICY = " → 처리: 개정판은 새 측정값(개정판_값)으로 교체, 제출본 값의 정의·출처 불명확은 부록 A에 기록"


# 서술 위치(DESIGN_REVISION §2, D4: 9입력=VI.4, S10 값=VI.7)
def place(loc, item, cat):
    if cat in ("내부불일치_정정", "미적용"):
        return {"V.2(1)": "V.2 각주 + 부록 A", "표12": "VI.3 각주 + 부록 A", "표13·표17": "VI.3·VI.7 각주 + 부록 A",
                "V.3(3)": "V.3 본문(미적용 명시) + VII 한계 + 부록 A"}.get(loc, "부록 A")
    if loc.startswith("III") or loc == "표1":
        return "III"
    if loc.startswith("IV.1") or loc == "표2":
        return "IV.1"
    if loc.startswith("IV") or loc == "표3":
        return "IV.2~IV.4"
    if loc.startswith("V.") or loc in ("표4", "표5"):
        return "V"
    if loc == "VI.1":
        return "VI.1"
    if loc in ("표6", "표7", "표8", "VI.2(1) 본문", "VI.2(2) 본문", "그림1 본문"):
        return "VI.2" if loc != "그림1 본문" else "VI.7(그림 F7 설명)"
    if loc in ("표9", "표10", "표11", "표12", "표13", "표14", "그림2 본문") or loc.startswith("VI.3"):
        return "VI.3"
    if loc in ("표15", "표16", "표17", "표18", "그림3 본문") or loc.startswith("VI.4"):
        return "VI.7(S10 개정값) / VI.4(제출본 대비 서술)"
    if loc == "VI.5":
        return "VI.8 논의"
    if loc == "VII":
        return "VII"
    return "부록 A"


# 전사 검증(DESIGN_REVISION §3-4). 판독 오류는 0건 — 아래는 출처·정의가 불확실해 "확인필요"로 둔 행(내용 확인 대상).
CHECK_NEEDED = {}
for _st in ("KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2"):
    CHECK_NEEDED[("표6", f"{_st} 횡방향 오차 m")] = "정의 불명(|y| 추정) — 값이 저장된 Student 데이터 |y|에 근접, 표14와 정의 불일치"
    CHECK_NEEDED[("표6", f"{_st} 헤딩 절댓값 deg")] = "저장된 Teacher 데이터(0.8~14.6°)와 불일치, Student 데이터(14~36°)에 근접"
    CHECK_NEEDED[("표14", f"{_st} 평균 오차 m")] = "저장 데이터 어느 쪽과도 정확히 일치 안 함(EVADE_L 0.104는 목표 오차로 불가능한 크기)"
    CHECK_NEEDED[("표14", f"{_st} RMS 오차 m")] = CHECK_NEEDED[("표14", f"{_st} 평균 오차 m")]
CHECK_NEEDED[("VII", "평균 횡방향 오차")] = "전체 평균처럼 서술되나 표6 KEEP_L2 값(0.035)"
for _w in ("Teacher", "Student", "개선율"):
    CHECK_NEEDED[("표17", f"조향각 Jerk deg/step² {_w}")] = "라벨은 조향각 jerk, 제출본 스크립트(legacy_2025/backup/justify_mpc.py:31)는 속도 2차 차분"
CHECK_NEEDED[("표13", "속도 변화율 m/s/step 평균")] = "표17과 같은 정의(legacy_2025/backup/justify_mpc.py:27)인데 값 다름(0.001 vs 0.004), 저장 데이터로 둘 다 재현 불가"
CHECK_NEEDED[("표17", "속도 변화율 m/s/step Teacher")] = CHECK_NEEDED[("표13", "속도 변화율 m/s/step 평균")]
CHECK_NEEDED[("표17", "속도 변화율 m/s/step Student")] = CHECK_NEEDED[("표13", "속도 변화율 m/s/step 평균")]
CHECK_NEEDED[("표13·표17", "속도 변화율(표13 0.001 vs 표17 0.004)")] = CHECK_NEEDED[("표13", "속도 변화율 m/s/step 평균")]
PAGE_FIX = {("표16", "벤치마크 횟수"): "18", ("표13·표17", "속도 변화율(표13 0.001 vs 표17 0.004)"): "17·19"}


# 비고 추가(사용자 결정 2026-09-25, OPEN #7·#8)
NOTE_ADD = {
    ("표9", "에피소드당 최대 샘플"): "제출본 내부 불일치: 제출본 표 9 최대 267은 최대 에피소드 길이 200 step(제출본 V장 1절)을 넘음 — 샘플 정의 불명(부록 A.3)",
    ("표9", "평균 주행 시간"): "이 행만 E2 baseline 데이터, 표 9의 나머지 행은 학습 데이터 D",
}


def finalize():
    fill = build_fill()
    ov = apply_ratio_ranges(build_r2_override())
    for r in rows:
        key = (r[2], r[3])
        if key in PAGE_FIX:
            r[1] = PAGE_FIX[key]
        if key in fill and r[10].startswith("산출대기"):
            val, src, note = fill[key]
            r[5], r[6], r[10] = val, src, "확정"
            if note:
                r[11] = (r[11] + " / " if r[11] else "") + note
        if key in ov:
            val, src, note = ov[key]
            r[5], r[6], r[10] = val, src, "확정"
            r[11] = note
        if key in NOTE_ADD:
            r[11] = (r[11] + " / " if r[11] else "") + NOTE_ADD[key]
        r.append(place(r[2], r[3], r[9]))
        if key in CHECK_NEEDED:
            r.append("확인필요: " + CHECK_NEEDED[key] + CHECK_POLICY)
        elif key in PAGE_FIX:
            r.append("일치(쪽 번호 정정)")
        else:
            r.append("일치")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    finalize()
    write_changelog()
    n_base = len(rows)
    import new_numbers  # 신설 절용 새 수치(기존 256행 뒤에 추가, 기존 행 불변)
    rows.extend(new_numbers.build())
    print("기존 행", n_base, "/ 신규 행", len(rows) - n_base)
    header = ["no", "쪽", "위치", "항목", "제출본_값", "개정판_값", "근거_파일", "조건_코드", "처리", "분류", "상태", "비고",
              "개정판_서술위치", "전사검증"]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("rows", len(rows))
    for col, idx in (("처리", 8), ("분류", 9), ("상태", 10)):
        print(col, dict(Counter(r[idx] for r in rows)))
    print("전사검증", dict(Counter(r[13].split(":")[0] for r in rows)))


if __name__ == "__main__":
    main()
