"""
Teacher MPC 검증 스크립트
- simulator.py: kinematic bicycle model 물리 시뮬레이션
- final_hierarchical_backup.py: 논문 파라미터 MPC + FSM
"""
import sys
import os
import math
import numpy as np

sys.path.insert(0, r"C:\Users\user\MPC_LINETRACING")

from simulator import SimulatedEnvironment
from final_hierarchical_backup import (
    OSQPMPC, VehicleParams, RoadParams, BehaviorParams,
    State
)

_RAD2DEG = 180.0 / math.pi
_DEG2RAD = math.pi / 180.0

# ============================
# 논문 파라미터 (final_hierarchical_backup 기준)
# ============================
vp = VehicleParams(
    L=0.20, B=0.15, V_MAX=0.5,
    DELTA_MAX_DEG=25.0, DELTA_RATE_MAX_DEGPS=200.0,
    A_MAX=2.0, A_MIN=-3.0, WHEEL_RATE_MAX=3.0
)
rp = RoadParams(W=0.30, MAX_Y_DEVIATION=0.45)
bp = BehaviorParams(
    G_TRIG=1.2,
    G_SAFE_MIN=0.20,
    T_KEEP_L1_MIN=0.6,
    COOLDOWN=0.3,
    NEAR_BAND_L1=0.08
)

# MPC (논문 표 3 파라미터)
mpc = OSQPMPC(vp, rp, N=15, dt=0.05,
              qy=100.0, qpsi=25.0, rdelta=2.0, rddelta=5.0)

# ============================
# 단순 FSM
# ============================
class SimpleFSM:
    def __init__(self, bp, rp, dt=0.05):
        self.bp = bp
        self.rp = rp
        self.dt = dt
        self.state = State.KEEP_L2
        self.last_state_change_step = 0
        self.step = 0

    def update(self, y, psi_deg, front_gap, left_clear):
        self.step += 1
        cooldown_ok = (self.step - self.last_state_change_step) * self.dt >= self.bp.COOLDOWN

        # 긴급 정지 — EVADE_L 중에는 발동 안 함 (final_hierarchical_backup.py와 동일 로직)
        if (front_gap is not None and front_gap < self.bp.G_SAFE_MIN
                and not left_clear
                and self.state != State.EVADE_L):
            self._set(State.SAFE_STOP)
            return

        if self.state == State.KEEP_L2:
            if front_gap is not None and front_gap < self.bp.G_TRIG and left_clear and cooldown_ok:
                self._set(State.EVADE_L)

        elif self.state == State.EVADE_L:
            if abs(y - self.rp.W) < self.bp.NEAR_BAND_L1 and cooldown_ok:
                self._set(State.KEEP_L1)

        elif self.state == State.KEEP_L1:
            elapsed = (self.step - self.last_state_change_step) * self.dt
            if elapsed > self.bp.T_KEEP_L1_MIN:
                self._set(State.RETURN_TO_L2)

        elif self.state == State.RETURN_TO_L2:
            if abs(y) < self.bp.NEAR_BAND_L1 and cooldown_ok:
                self._set(State.KEEP_L2)

    def _set(self, new_state):
        if new_state != self.state:
            self.state = new_state
            self.last_state_change_step = self.step

    def target_y(self):
        if self.state in (State.EVADE_L, State.KEEP_L1):
            return self.rp.W  # 0.30m (L1)
        return 0.0  # L2

# ============================
# 에피소드 실행
# ============================
def run_episode(env, fsm, max_steps=200, verbose=False):
    env.reset(randomize=True)
    fsm.__init__(bp, rp, dt=0.05)

    # 논문 파라미터 적용
    env.obstacle_x = float(np.random.uniform(1.2, 2.0))   # G_TRIG 기반: 1.2~2.0m 균등분포
    env.state.y = float(np.random.normal(0.0, 0.05))      # 논문: Gaussian(0, 0.05)
    env.state.v = float(np.random.uniform(0.3, 0.5))      # 논문: 0.3~0.5m/s

    x, y, psi, v = env.get_state()
    delta_prev = 0.0
    rate_limit = vp.DELTA_RATE_MAX_DEGPS * 0.05  # deg/step

    state_log = []       # 상태전이 기록
    prev_state = fsm.state
    evade_triggered = False
    returned_to_l2 = False

    for step in range(max_steps):
        ir_l, ir_c, ir_r, front_gap, left_clear, done = env.step(delta_prev, v)
        x, y, psi, v = env.get_state()
        psi_deg = psi * _RAD2DEG

        fsm.update(y, psi_deg, front_gap, left_clear)
        state = fsm.state

        # 상태전이 기록
        if state != prev_state:
            state_log.append((step, prev_state.name, state.name))
            if verbose:
                gap_str = f"{front_gap:.2f}" if front_gap is not None else "None"
                print(f"  [{step:3d}] {prev_state.name} -> {state.name}  y={y:.3f} gap={gap_str}")
            if state == State.EVADE_L:
                evade_triggered = True
            if state == State.KEEP_L2 and evade_triggered:
                returned_to_l2 = True
            prev_state = state

        if state == State.SAFE_STOP:
            return False, step, "SAFE_STOP", state_log, evade_triggered

        target = fsm.target_y()
        delta_deg, ok = mpc.solve(y, psi, v if v > 0.05 else 0.3, target)

        # rate limiting
        delta_deg = float(np.clip(delta_deg,
                                  delta_prev - rate_limit,
                                  delta_prev + rate_limit))
        delta_deg = float(np.clip(delta_deg, -vp.DELTA_MAX_DEG, vp.DELTA_MAX_DEG))
        delta_prev = delta_deg

        if done:
            dist = math.sqrt((x - env.obstacle_x)**2 + (y - env.obstacle_y)**2)
            if dist < 0.1:
                return False, step, "COLLISION", state_log, evade_triggered
            return True, step, "DONE", state_log, evade_triggered

    return True, max_steps, "TIMEOUT_OK", state_log, evade_triggered


# ============================
# 메인
# ============================
def main():
    NUM_EPISODES = 100
    MAX_STEPS = 400

    env = SimulatedEnvironment(vp, rp, bp, dt=0.05)
    env.max_steps = MAX_STEPS

    results = {"success": 0, "collision": 0, "safe_stop": 0}
    step_counts = []
    evade_counts = 0
    full_return_counts = 0   # L2 완전 복귀 완료한 에피소드 수
    state_change_counts = []

    print("=" * 60)
    print("Teacher MPC 검증 (kinematic bicycle model 시뮬레이션)")
    print(f"G_TRIG={bp.G_TRIG}, G_SAFE_MIN={bp.G_SAFE_MIN}, "
          f"T_KEEP_L1_MIN={bp.T_KEEP_L1_MIN}")
    print(f"qy=100, qpsi=25, rdelta=2, rddelta=5, N=15")
    print(f"obstacle_x: uniform(2.5, 4.0)m")
    print("=" * 60)

    # 첫 5개 에피소드는 상세 출력
    VERBOSE_EP = 5

    for ep in range(NUM_EPISODES):
        fsm = SimpleFSM(bp, rp)
        verbose = (ep < VERBOSE_EP)
        if verbose:
            print(f"\n[Episode {ep+1}] obstacle=({env.obstacle_x:.2f}, {env.obstacle_y:.2f})")

        success, steps, reason, state_log, evade_triggered = run_episode(
            env, fsm, MAX_STEPS, verbose=verbose
        )

        step_counts.append(steps)
        state_change_counts.append(len(state_log))
        if evade_triggered:
            evade_counts += 1
        # 전이 로그에서 RETURN_TO_L2 이후 KEEP_L2 복귀 확인
        states_seq = [t[2] for t in state_log]
        if 'KEEP_L2' in states_seq:
            idx = states_seq.index('KEEP_L2')
            if idx > 0 and state_log[idx-1][2] == 'RETURN_TO_L2' or \
               any(t[1] == 'RETURN_TO_L2' and t[2] == 'KEEP_L2' for t in state_log):
                full_return_counts += 1

        if success:
            results["success"] += 1
        elif reason == "COLLISION":
            results["collision"] += 1
        else:
            results["safe_stop"] += 1

        if verbose:
            print(f"  결과: {reason}, 스텝: {steps}, 전이: {state_log}")

        if (ep + 1) % 10 == 0:
            sr = results["success"] / (ep + 1) * 100
            print(f"Ep {ep+1:3d}/{NUM_EPISODES} | "
                  f"Success: {results['success']}/{ep+1} ({sr:.1f}%) | "
                  f"차선변경: {evade_counts}/{ep+1} | "
                  f"L2복귀완료: {full_return_counts}/{ep+1}")

    print("\n" + "=" * 60)
    print("결과")
    print("=" * 60)
    sr = results["success"] / NUM_EPISODES * 100
    print(f"성공률(충돌없음):  {sr:.1f}% ({results['success']}/{NUM_EPISODES})")
    print(f"충돌:              {results['collision']}회")
    print(f"비상정지:          {results['safe_stop']}회")
    print(f"평균 스텝:         {np.mean(step_counts):.1f}")
    print(f"차선변경 발생:     {evade_counts}/{NUM_EPISODES} 에피소드")
    print(f"L2 완전 복귀 완료: {full_return_counts}/{NUM_EPISODES} 에피소드")
    print(f"평균 상태전이 수:  {np.mean(state_change_counts):.1f}회/에피소드")
    print("=" * 60)

if __name__ == "__main__":
    main()