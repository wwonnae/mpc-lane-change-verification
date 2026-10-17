"""
I4(Student 재학습, 3단계 [발전]) 설정. 근거: repro/docs/DESIGN_I4.md (개정 1, 2026-09-25).

원본 legacy_2025/models/(policy_best.pth, normalization_stats.json)는 읽지도 쓰지도 않는다 -- 새 모델·
통계는 thesis_v2/results/i4_student/ 아래에만 저장한다(DESIGN_I4 §0, §1-6).
"""
import numpy as np

from thesis_v2.baseline import config as base_config
from thesis_v2.improved import config as improved_config

base_config.assert_fixed_params()

# ===== 교사: v2 MPC (DESIGN_IMPROVED_V2.md §9, DESIGN_I4 §1-1) =====
TEACHER_FLAGS = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                     i2_variant="narrow", enable_i5=True,
                     i5_max_iter=improved_config.I5_MAX_ITER)
assert TEACHER_FLAGS["i5_max_iter"] == 972

# ===== 데이터 (DESIGN_I4 §1-1, §1-4 개정 1) =====
DEV_PAPER_SEEDS = list(range(100, 200))
# S3 dev 격자: run_dev_i5_ablation.py의 DEV_S3_FRONT_GAPS/Y0S와 같은 값(반 칸 오프셋, 30x30)
DEV_S3_FRONT_GAPS = np.round(np.arange(0.525, 1.9751, 0.05), 4)
DEV_S3_Y0S = np.round(np.arange(-0.145, 0.1451, 0.01), 4)
assert len(DEV_S3_FRONT_GAPS) == 30 and len(DEV_S3_Y0S) == 30
# 표본 부족 시 확대 대역: 200개 단위, 300번대부터 순서 고정(eval 200~299 제외).
# 1000~1099는 S4~S7 dev 대역이라 겹치지 않도록 999에서 끝낸다.
EXPANSION_BLOCKS = [list(range(s, s + 200)) for s in (300, 500, 700)]
MIN_MAX_RATIO_THRESHOLD = 1.0 / 3.0

# ===== eval (DESIGN_I4 §3) =====
EVAL_PAPER_SEEDS = list(range(200, 300))
# S3 eval 격자(eval 2회차 신규 1/4칸 오프셋, run_eval_v2.py의 EVAL2_S3_*와 같은 값)
EVAL_S3_FRONT_GAPS = np.round(np.arange(0.5025, 1.9975 + 0.0001, 0.05), 4)
EVAL_S3_Y0S = np.round(np.arange(-0.1475, 0.1475 + 0.0001, 0.01), 4)
assert len(EVAL_S3_FRONT_GAPS) == 30 and len(EVAL_S3_Y0S) == 30

# eval3 (DESIGN_I4 §6-4, Student v2 최종 확인 전용, 1회만): 미사용 대역 2000~2099 + 3/4칸 오프셋 S3
EVAL3_PAPER_SEEDS = list(range(2000, 2100))
EVAL3_S3_FRONT_GAPS = np.round(np.arange(0.5375, 1.9875 + 0.0001, 0.05), 4)
EVAL3_S3_Y0S = np.round(np.arange(-0.1425, 0.1475 + 0.0001, 0.01), 4)
assert len(EVAL3_S3_FRONT_GAPS) == 30 and len(EVAL3_S3_Y0S) == 30
_legacy_fg = np.round(np.arange(0.50, 2.0001, 0.05), 4)
_legacy_y = np.round(np.arange(-0.15, 0.1501, 0.01), 4)
for _fg, _y in ((DEV_S3_FRONT_GAPS, DEV_S3_Y0S), (EVAL_S3_FRONT_GAPS, EVAL_S3_Y0S), (_legacy_fg, _legacy_y)):
    assert not (set(EVAL3_S3_FRONT_GAPS) & set(_fg)) and not (set(EVAL3_S3_Y0S) & set(_y))

_dev_all = set(DEV_PAPER_SEEDS) | {s for b in EXPANSION_BLOCKS for s in b}
assert not (_dev_all & set(EVAL_PAPER_SEEDS)), "dev/eval seed 겹침"
assert not (_dev_all & set(EVAL3_PAPER_SEEDS)) and not (set(EVAL_PAPER_SEEDS) & set(EVAL3_PAPER_SEEDS))
assert not (set(DEV_S3_FRONT_GAPS) & set(EVAL_S3_FRONT_GAPS))
assert not (set(DEV_S3_Y0S) & set(EVAL_S3_Y0S))

# ===== split (DESIGN_I4 §1-5 개정 1: 계층 분할, 고정 seed 1개, 재추첨 없음) =====
SPLIT_SEED = 20260925
VAL_FRACTION = 0.15

# ===== 학습 (DESIGN_I4 §2-1, Table 5 기준) =====
LEARNING_RATE = 1e-3       # Table 5 [정합]
BATCH_SIZE = 256           # Table 5 [정합]
EPOCHS = 50                # Table 5 [정합], 50 전부 실행·조기 종료 없음([해석], 개정 1)
DROPOUT = 0.15             # REQ-STU-01 [정합]
HIDDEN_DIMS = (256, 256, 128)  # REQ-STU-01 [정합]
GRAD_CLIP_NORM = 1.0       # [공백] DESIGN_I4 §2-1
LR_PLATEAU_FACTOR = 0.5    # [공백] DESIGN_I4 §2-1
LR_PLATEAU_PATIENCE = 5    # [공백] DESIGN_I4 §2-1
DEFAULT_TRAIN_SEED = 7     # CLI 인자 기본값(실행 명령에 명시)

# ===== 계산시간 (DESIGN_I4 §3-3, official_timing_benchmark_v3.py와 같은 조건) =====
TIMING_SEEDS = list(range(0, 100))
TIMING_WARMUP = 50
