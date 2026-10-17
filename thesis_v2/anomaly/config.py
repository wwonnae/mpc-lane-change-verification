"""
이상탐지 확장 설정 (DESIGN.md §6·§10 결정 D1~D6, 2026-10-01 승인).

baseline/improved의 고정 파라미터·결정표 값은 여기서 다시 정의하지 않는다(단일 출처) —
`thesis_v2.baseline.config`를 재사용한다. 여기서는 이상탐지 확장에만 쓰는 값만 둔다.
"""
from thesis_v2.baseline import config as base_config
from thesis_v2.improved import config as improved_config

base_config.assert_fixed_params()

# ===== D1: 기준 제어기 = improved v2 (run_eval_v2.COMBO_V2와 같은 플래그) =====
V2_MPC_FLAGS = dict(enable_i1=True, enable_i1b=True, enable_i2=True, enable_i3=True,
                    i2_variant="narrow", enable_i5=True,
                    i5_max_iter=improved_config.I5_MAX_ITER)
assert V2_MPC_FLAGS["i5_max_iter"] == 972

# ===== D2: 정상 변동 = 기존 S4 노이즈 프로파일(baseline/sensors.py NOISE_PROFILES) =====
NORMAL_NOISE_PROFILE = "low"

# ===== D3: 이상탐지 전용 시나리오 =====
# 장애물 초기 전단거리. 논문 시나리오 U(0.5,2.0)는 절반가량이 첫 스텝부터 EVADE(G_TRIG=1.2)라
# 고장 주입 전 정상 구간·탐지 윈도우 워밍업이 없음(DESIGN.md §0-4).
ANOMALY_FRONT_GAP_RANGE = (2.0, 3.0)
# 에피소드 상한(접근 구간이 길어진 만큼). baseline config.MAX_STEPS(200)는 건드리지 않고
# anomaly runner 인자로만 쓴다. 관찰 구간(OBSERVE_STEPS=20)은 baseline 값 그대로.
ANOMALY_MAX_STEPS = 300

# ===== D5: 이탈 정의 =====
ROAD_Y_RANGE = (-0.15, 0.45)  # L2 우측 경계 ~ L1 좌측 경계 (W=0.30, 차로 중심 0/0.30)
# "corner": 차체 네 모서리 중 하나라도 도로 밖(10/01 승인안).
# "center": 차체 기하 중심(후륜축에서 L/2 앞)이 도로 밖 — 1단계 dev에서 고장 없는 정상 주행
#   (IR 이산 라인추종의 좌우 흔들림, |psi|≈10°)도 모서리가 최대 4.2 cm 도로 밖으로 나가
#   "corner" 정의로는 정상 주행이 이탈로 분류됨을 확인(seed 3200~3299). D5 개정 — 2026-10-01 승인.
DEPARTURE_MODE = "center"

# ===== D6: 오경보 목표 (2·3단계 임계값 결정용, 정상 에피소드 단위) =====
TARGET_EPISODE_FAR = 0.02

# ===== seed 대역 (DESIGN.md §6) =====
SEEDS_NORMAL_TRAIN = list(range(3000, 3200))   # 정상 학습·임계값(T)
SEEDS_FAULT_DEV = list(range(3200, 3300))      # 고장 설계 dev(D) — 임계값 결정 금지
SEEDS_OFFLINE_EVAL = list(range(4000, 4100))   # 오프라인 평가(E), 확정 코드에 1회
SEEDS_CLOSED_LOOP = list(range(5000, 5100))    # 폐루프 평가(C), 1회
# 탐지기 B 학습용 정상 seed(DESIGN.md §13-4, 2026-10-01 승인) — 임계값은 모든 탐지기가 SEEDS_NORMAL_TRAIN으로 정한다
SEEDS_B_TRAIN = list(range(3300, 3380))        # B 학습
SEEDS_B_VAL = list(range(3380, 3400))          # B2(AE) 조기 종료 검증

# 기존 사용 대역(0~1099: P·dev·I4 확장·S4~S7 dev, 2000~2099: E3)과 겹치지 않음을 고정
_EXISTING = set(range(0, 1100)) | set(range(2000, 2100))
_BANDS = [SEEDS_NORMAL_TRAIN, SEEDS_FAULT_DEV, SEEDS_OFFLINE_EVAL, SEEDS_CLOSED_LOOP,
          SEEDS_B_TRAIN, SEEDS_B_VAL]
for _i, _a in enumerate(_BANDS):
    assert not (set(_a) & _EXISTING), "기존 seed 대역과 겹침"
    for _b in _BANDS[_i + 1:]:
        assert not (set(_a) & set(_b)), "이상탐지 seed 대역끼리 겹침"

# ===== 고장 주입 공통 =====
# 고장 onset 최소 step(탐지 윈도우 W=10 step + 여유 5 step). 그 전은 항상 정상.
WARMUP_STEPS = 15

# 정상 변동(S4 노이즈) 난수 스트림: default_rng((seed, NOISE_STREAM_ID)) — world·고장 스트림과 분리
NOISE_STREAM_ID = 7001

# ===== 탐지기 전용 자이로(DESIGN.md §13-2, 2026-10-01 승인) =====
# g_k = (psi_k - psi_{k-1})/dt + n_k, n_k ~ N(0, SIGMA_GYRO^2). 제어기 입력이 아니다(탐지기만 받음).
# 근거: InvenSense PS-MPU-6000A-00 Rev 3.2 §6.1(p.12) Total RMS Noise 0.05 deg/s-rms(DLPFCFG=2, 100 Hz)의
# 20배 — 시뮬레이션에 없는 서보·슬립·진동·잔여 바이어스를 대신하는 [가정].
SIGMA_GYRO_DEG = 1.0
SIGMA_GYRO_SENSITIVITY_DEG = (0.05, 1.0, 5.0)  # 확장: 민감도(보고용, σ 선택에 쓰지 않음)
GYRO_STREAM_ID = 7002

# ===== 임계값 공통 절차(DESIGN.md §4, §13-4) =====
THRESHOLD_QUANTILE = 1.0 - TARGET_EPISODE_FAR  # 0.98, np.quantile(method="higher"), 경보는 score > h

# ===== 정상 데이터 범위 (DESIGN.md §17, iteration 2, 2026-10-02 승인) =====
# 임계값(SEEDS_NORMAL_TRAIN)·B 학습/검증(SEEDS_B_TRAIN/VAL) 정상 주행에 쓰는 시나리오. "far"=원거리, "leftobs"=좌측 장애물.
# iteration 1 결과 파일에는 이 필드가 없으며 ("far",)로 간주한다(--check 호환).
# iteration 3(DESIGN.md §18, 2026-10-02): A에 ir_miss 채널 추가, A 임계값만 재계산. B는 iteration 2 그대로(건드리지 않음).
ITERATION = 3
NORMAL_SCENARIOS = ("far", "leftobs")
NORMAL_SCENARIOS_IT1 = ("far",)
