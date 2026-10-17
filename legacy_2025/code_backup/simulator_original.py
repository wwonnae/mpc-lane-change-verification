"""
Simulation Environment for Teacher Data Generation
완전 동작 검증 버전 with Debug
"""
import numpy as np
import math
import time
import csv
import os
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum, auto

_RAD2DEG = 180.0 / math.pi
_DEG2RAD = math.pi / 180.0

class State(Enum):
    KEEP_L2 = auto()
    EVADE_L = auto()
    KEEP_L1 = auto()
    RETURN_TO_L2 = auto()
    SAFE_STOP = auto()

@dataclass
class SimState:
    x: float = 0.0
    y: float = 0.0
    psi: float = 0.0
    v: float = 0.0

class SimulatedEnvironment:
    def __init__(self, vp, rp, bp, dt=0.05, ir_spacing=0.04):
        self.vp = vp
        self.rp = rp
        self.bp = bp
        self.dt = dt
        self.ir_spacing = ir_spacing
        
        self.state = SimState()
        self.obstacle_x = 0.0
        self.obstacle_y = 0.0
        self.step_count = 0
        self.max_steps = 200
        
    def reset(self, randomize=True):
        if randomize:
            self.state.x = 0.0
            self.state.y = np.random.uniform(-0.05, 0.05)
            self.state.psi = np.random.uniform(-5, 5) * _DEG2RAD
            self.state.v = np.random.uniform(0.3, 0.5)
            # 장애물을 가까이 배치
            self.obstacle_x = np.random.uniform(1.5, 2.5)
            self.obstacle_y = np.random.uniform(-0.05, 0.05)
        else:
            self.state.x = 0.0
            self.state.y = 0.0
            self.state.psi = 0.0
            self.state.v = 0.4
            self.obstacle_x = 2.0
            self.obstacle_y = 0.0
        
        self.step_count = 0
        print(f"[SIM_ENV] Reset: obstacle at x={self.obstacle_x:.2f}, y={self.obstacle_y:.2f}")
        return (self.state.x, self.state.y, self.state.psi, self.state.v)
    
    def step(self, delta_deg: float, v_cmd: float) -> Tuple[int, int, int, Optional[float], bool, bool]:
        # 차량 상태 업데이트
        delta_rad = np.clip(delta_deg * _DEG2RAD, -self.vp._delta_max_rad, self.vp._delta_max_rad)
        self.state.v = np.clip(v_cmd, self.vp.V_MIN, self.vp.V_MAX)
        
        if abs(delta_rad) < 1e-6:
            self.state.x += self.state.v * math.cos(self.state.psi) * self.dt
            self.state.y += self.state.v * math.sin(self.state.psi) * self.dt
        else:
            R = self.vp.L / math.tan(delta_rad)
            omega = self.state.v / R
            dpsi = omega * self.dt
            self.state.psi += dpsi
            dx_body = self.state.v * self.dt
            c = math.cos(self.state.psi)
            s = math.sin(self.state.psi)
            self.state.x += dx_body * c
            self.state.y += dx_body * s
        
        self.state.psi = math.atan2(math.sin(self.state.psi), math.cos(self.state.psi))
        
        # 센서 시뮬레이션
        ir_left, ir_center, ir_right = self._get_ir_sensors()
        front_gap, left_clear = self._get_lidar_data()
        
        # 종료 조건
        self.step_count += 1
        done = False
        
        if self.step_count >= self.max_steps:
            done = True
        if abs(self.state.y) > self.rp.MAX_Y_DEVIATION:
            done = True
        
        dist_to_obs = math.sqrt((self.state.x - self.obstacle_x)**2 + (self.state.y - self.obstacle_y)**2)
        if dist_to_obs < 0.1:
            done = True
            print(f"[SIM_ENV] COLLISION at step {self.step_count}")
        
        return ir_left, ir_center, ir_right, front_gap, left_clear, done
    
    def _get_ir_sensors(self) -> Tuple[int, int, int]:
        lane_centers = [0.0, self.rp.W]
        distances = [abs(self.state.y - lc) for lc in lane_centers]
        nearest_lane_y = lane_centers[np.argmin(distances)]
        deviation = self.state.y - nearest_lane_y
        
        if abs(deviation) < self.ir_spacing * 0.3:
            return 0, 1, 0
        elif deviation > self.ir_spacing * 0.6:
            if deviation > self.ir_spacing * 0.9:
                return 1, 0, 0
            else:
                return 1, 1, 0
        elif deviation < -self.ir_spacing * 0.6:
            if deviation < -self.ir_spacing * 0.9:
                return 0, 0, 1
            else:
                return 0, 1, 1
        else:
            if deviation > 0:
                return 1, 1, 0
            else:
                return 0, 1, 1
    
    def _get_lidar_data(self) -> Tuple[Optional[float], bool]:
        dx = self.obstacle_x - self.state.x
        dy = self.obstacle_y - self.state.y
        
        # 전방 장애물 감지 (x 방향 거리 & y 방향 오차 체크)
        if dx > 0 and dx < 5.0 and abs(dy) < 0.25:
            front_gap = dx
        else:
            front_gap = None
        
        # 좌측 공간 (L1 방향)
        if self.state.y < self.rp.W * 0.5:
            left_clear = True
        else:
            left_clear = (abs(self.state.y - self.obstacle_y) > 0.15)
        
        return front_gap, left_clear
    
    def get_state(self) -> Tuple[float, float, float, float]:
        return self.state.x, self.state.y, self.state.psi, self.state.v


class MockComm:
    def __init__(self, sim_env, ir_spacing):
        self.sim = sim_env
        self.ir_spacing = ir_spacing
        self.ir_values = (0, 1, 0)
        self.lidar_front_gap = None
        self.lidar_left_clear = True
        
    def get_line_position(self):
        ir_left, ir_center, ir_right = self.ir_values
        
        if ir_center == 1:
            if ir_left == 1 and ir_right == 0:
                return self.ir_spacing * 0.5
            elif ir_left == 0 and ir_right == 1:
                return -self.ir_spacing * 0.5
            else:
                return 0.0
        elif ir_left == 1 and ir_center == 0 and ir_right == 0:
            return self.ir_spacing
        elif ir_right == 1 and ir_center == 0 and ir_left == 0:
            return -self.ir_spacing
        else:
            return None
    
    def get_lidar_data(self, car_x_W=None, car_y_W=None, car_yaw_W=None):
        from final import InfraROI
        return InfraROI(
            front_gap=self.lidar_front_gap,
            roi_left_clear=self.lidar_left_clear,
            timestamp=time.time()
        )
    
    def send_command(self, v_cmd, delta_deg):
        pass
    
    def send(self, v_cmd, delta_deg):
        return True
    
    def close(self):
        pass


def run_simulation_episodes(app, num_episodes=1000, steps_per_episode=200, 
                            dataset_dir="./dataset", randomize=True):
    """시뮬레이션 기반 teacher 데이터 생성"""
    
    # 시뮬레이션 환경
    sim = SimulatedEnvironment(
        vp=app.vp,
        rp=app.rp,
        bp=app.bp,
        dt=app.dt,
        ir_spacing=app.cfg.ir_sensor_spacing
    )
    sim.max_steps = steps_per_episode
    
    # Mock Comm
    original_comm = app.comm
    mock_comm = MockComm(sim, app.cfg.ir_sensor_spacing)
    app.comm = mock_comm
    
    # 로그
    os.makedirs(dataset_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(dataset_dir, f"sim_teacher_{timestamp}.csv")
    
    fp = open(log_path, 'w', newline='')
    writer = csv.writer(fp)
    writer.writerow([
        "episode", "step", "t", "x", "y", "psi_deg", "v",
        "ir_left", "ir_center", "ir_right", 
        "front_gap", "left_clear", "state",
        "delta_deg", "v_cmd"
    ])
    
    print(f"[SIM] Starting {num_episodes} episodes")
    print(f"[SIM] Randomize: {randomize}")
    print(f"[SIM] Log: {log_path}")
    
    total_steps = 0
    success_count = 0
    
    for ep in range(num_episodes):
        # 리셋
        x, y, psi, v = sim.reset(randomize=randomize)
        
        app.pose.x = x
        app.pose.y = y
        app.pose.psi = psi
        app.speed._v = v
        app.v_cmd_prev = v
        app.delta_prev = 0.0
        
        app.set_state(State.KEEP_L2)
        app.lines.sig_ey.v = None
        app.lines.sig_ey.ts = 0.0
        
        episode_success = False
        state_changes = 0
        
        for step in range(steps_per_episode):
            t = step * app.dt
            
            # 시뮬레이션 스텝
            delta_deg = app.delta_prev
            v_cmd = app.v_cmd_prev
            ir_left, ir_center, ir_right, front_gap, left_clear, done = sim.step(delta_deg, v_cmd)
            
            # Mock comm 업데이트
            mock_comm.ir_values = (ir_left, ir_center, ir_right)
            mock_comm.lidar_front_gap = front_gap
            mock_comm.lidar_left_clear = left_clear
            
            # Pose 동기화
            app.pose.x, app.pose.y, app.pose.psi, _ = sim.get_state()
            app.speed._v = sim.state.v
            
            # 디버그 출력 (첫 에피소드만)
            if ep == 0 and step % 50 == 0:
                gap_str = f"{front_gap:.2f}" if front_gap is not None else "None"
                print(f"[DEBUG] Step {step}: x={sim.state.x:.2f}, y={sim.state.y:.2f}, "
                      f"front_gap={gap_str}, "
                      f"left_clear={left_clear}, state={app.state.name}")
            
            # step_once 호출
            old_state = app.state
            app._test_time = None
            app.step_once()
            
            if old_state.value != app.state.value:
                state_changes += 1
                if ep == 0:
                    print(f"[DEBUG] State change at step {step}: {old_state.name} -> {app.state.name}")
            
            # 제어 출력
            delta_deg_out = app.delta_prev
            v_cmd_out = app.v_cmd_prev
            
            # 로깅
            writer.writerow([
                ep, step, f"{t:.3f}",
                f"{sim.state.x:.3f}", f"{sim.state.y:.3f}", 
                f"{sim.state.psi * _RAD2DEG:.1f}", f"{sim.state.v:.2f}",
                ir_left, ir_center, ir_right,
                f"{front_gap:.2f}" if front_gap is not None else "NA",
                int(left_clear),
                app.state.name,
                f"{delta_deg_out:.1f}", f"{v_cmd_out:.2f}"
            ])
            
            # 종료
            if done or app.state == State.SAFE_STOP:
                if sim.state.x > sim.obstacle_x + 0.5 and app.state != State.SAFE_STOP:
                    episode_success = True
                    if ep == 0:
                        print(f"[DEBUG] SUCCESS: Passed obstacle")
                break
            
            total_steps += 1
        
        if episode_success:
            success_count += 1
        
        print(f"[SIM] Ep {ep+1}/{num_episodes} | "
              f"States: {state_changes} changes | "
              f"Success: {success_count}/{ep+1} ({100*success_count/(ep+1):.1f}%)")
    
    fp.close()
    
    if app.shard is not None:
        app.shard.flush()
    
    app.comm = original_comm
    
    print(f"\n[SIM] Completed {num_episodes} episodes")
    print(f"[SIM] Total steps: {total_steps}")
    print(f"[SIM] Success rate: {100*success_count/num_episodes:.1f}%")
    print(f"[SIM] Log: {log_path}")
