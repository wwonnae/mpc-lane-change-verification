"""
개선판(3단계) 설정. DESIGN_IMPROVED.md 참고.

baseline/config.py의 고정 파라미터(N,dt,qy,qpsi,rdelta,rddelta,delta±25,200deg/s,
G_TRIG,G_SAFE_MIN,COOLDOWN,W,L,B 등)는 여기서 다시 정의하지 않는다(단일 출처 유지) --
필요한 곳에서 `from thesis_v2.baseline import config as base_config`로 재사용한다.
여기서는 3단계 ablation 플래그와, DESIGN_IMPROVED.md에서 실험 튜닝이 아니라
해석적으로 도출한 새 파라미터 2개만 정의한다.
"""
import math

from thesis_v2.baseline import config as base_config

base_config.assert_fixed_params()  # 고정 파라미터가 baseline과 여전히 일치하는지 재확인

# ===== ablation 플래그 (기본값 전부 False = baseline과 동일 경로, DESIGN_IMPROVED.md §3) =====
ENABLE_I1_RATE_AWARE_MPC = False
ENABLE_I1B_SOFT_CONSTRAINTS = False
ENABLE_I2_OBSTACLE_AWARE_MPC = False
ENABLE_I3_WARM_START_FALLBACK = False

# ===== I5(v2, DESIGN_IMPROVED_V2.md): 반복 상한(주 메커니즘) + time_limit(안전망) =====
# 기본 False면 mpc.py의 OSQP setup() kwargs가 1회차(I5 없음)와 완전히 동일하다.
ENABLE_I5_ITER_CAP_MPC = False
# 반복 상한 후보(DESIGN_IMPROVED_V2.md §1-1, 3층PC104 실측 반복시간 p99=0.00514ms/iter
# 기준 시간예산 5/10/20/30ms -> 972/1944/3888/5832). ablation에서 ImprovedMPC(...,
# i5_max_iter=<후보>)로 명시적으로 넘겨 비교하며, 여기 기본값은 dev 결과로 채택된 값을
# 채워 넣는 용도(실험 튜닝이 아니라 §1-1 계산 + dev 비열화 확인 결과).
# 2026-09-24 확정(DESIGN_IMPROVED_V2.md §9): dev ablation(5조합×7트랙, DESKTOP-MDCKRJS)
# 결과 972가 v1(I5 없음) 대비 비열화 없는 유일한 후보(lane 위반 45->34, 최대/누적도 감소)
# 이자 최저 예산 후보 -- "안전성 비열화 없는 가장 낮은 값" 규칙으로 채택.
# 주의: 이 값은 ENABLE_I5_ITER_CAP_MPC=True일 때만 쓰인다 -- 플래그 자체는 여전히
# 기본 False라 v1 조합(I5 없음)은 이 값과 무관하게 1회차와 바이트 단위로 동일하다.
I5_MAX_ITER = 972
# time_limit 안전망(초 단위). 반복 상한이 정상적으로 훨씬 먼저 걸리므로 정상 상황에서는
# 발동하지 않아야 한다(발동 시 time_limit_hit=True로 별도 로깅, DESIGN_IMPROVED_V2.md §1-4).
# 2026-10-14 정정(run #6 조사, docs/verification/ci/run6_cause/): 계산이 느려서가 아니라 실행 환경의
# 일시 정지(45 ms 이상)로도 발동하며, 발동하면 같은 입력의 결과가 달라진다. time_limit_hit는
# mpc.time_limit_fingerprint(status+반복 수)로 판정한다. 결정론 비교 테스트는 thesis_v2/conftest.py의
# i5_time_limit_off fixture로 이 값을 끄고 검증한다(제품 값은 그대로).
I5_TIME_LIMIT_SEC = 0.045

# ===== I1b: 위치제약 소프트화(y,psi) ell-1 벌점 가중치 =====
# 해석적 도출(DESIGN_IMPROVED.md I1b, exact penalty 조건): 원 하드 문제 KKT 승수 상한을
# y: 2*qy*0.75*N=2250, psi: 2*qpsi*80deg(rad)*N=1047 로 보수적으로 추정하고, 최댓값(2250)에
# 안전계수 ~4.4배를 적용해 확정(dev 튜닝 대상 아님).
SOFT_CONSTRAINT_PENALTY = 10000.0

# ===== I2: 장애물 인지 y 하한 마진 =====
# 해석적 도출(DESIGN_IMPROVED.md I2): 회전한 차체(후륜 기준 [0,L]x[-B/2,B/2])의 우측
# (-y) 최저 모서리 오프셋은 psi>=0이면 -B/2*cos(psi)(후륜우측), psi<0이면
# L*sin(psi)-B/2*cos(psi)(전륜우측)이다. QP 결정변수인 psi_i의 부호를 solve() 시점에
# 알 수 없으므로(선형성 유지 위해 psi_i에 의존하지 않는 고정값 필요), REQ-MPC-04의
# 하드 상한 PSI_LIMIT_DEG(80도)를 가정한 최악값을 쓴다(그보다 작은 값은 실제로 QP가
# 80도에 가까운 psi를 낼 때 마진 부족 -- 실험적으로 작은 값을 고르는 것은 금지 사항).
MARGIN_I2 = base_config.B / 2 + base_config.L * math.sin(math.radians(base_config.PSI_LIMIT_DEG))

# ===== I2' (narrow 변형): I2 활성 구간에 psi>=-20도 하한을 함께 추가할 때의 마진 =====
# 근거: REQ-FSM-02e(논문 RETURN_TO_L2->KEEP_L2 복귀 완료 조건 |psi|<=20도)를 재사용해
# "I2가 활성인 동안은 헤딩이 -20도보다 더 나빠지지 않는다"를 QP 자신의 제약으로 강제하면,
# 차체 최저 모서리 오프셋의 최악값도 80도가 아니라 20도 기준으로 줄어든다(해석적 도출,
# 실험 튜닝 아님). psi 하한 자체는 I1b가 켜져 있으면 소프트(슬랙), 꺼져 있으면 하드.
MARGIN_I2_PRIME = base_config.B / 2 + base_config.L * math.sin(math.radians(20.0))
