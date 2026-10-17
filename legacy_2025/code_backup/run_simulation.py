"""
시뮬레이션 환경 기반 Teacher/Student 성능 평가
"""
import sys
import os
import time
import numpy as np
import random

# final_hierarchical_backup 모듈 import
sys.path.insert(0, os.path.dirname(__file__))
from final_hierarchical_backup import *

class RandomScenarioGenerator:
    """랜덤 시나리오 생성기"""
    
    def __init__(self, steps_per_episode=200):
        self.steps = steps_per_episode
    
    def generate_episode(self):
        """단일 에피소드 시나리오 생성"""
        timeline = []
        
        # 초기 상태: KEEP_L2 정상 주행
        for step in range(0, 30):
            timeline.append((step, {
                'roi': InfraROI(front_gap=random.uniform(5.0, 10.0), roi_left_clear=True),
                'v': random.uniform(0.4, 0.6),
                'y': random.uniform(-0.05, 0.05),
                'line_ey': random.uniform(-0.05, 0.05),
                'left_clear': True
            }))
        
        # 장애물 접근: EVADE_L 트리거
        obstacle_start = random.randint(30, 50)
        for step in range(obstacle_start, obstacle_start + 10):
            gap = max(0.5, 2.0 - (step - obstacle_start) * 0.15)  # 2.0m → 0.5m
            timeline.append((step, {
                'roi': InfraROI(front_gap=gap, roi_left_clear=True),
                'v': random.uniform(0.4, 0.6),
                'line_ey': random.uniform(-0.05, 0.05),
                'left_clear': True
            }))
        
        # 회피 중: KEEP_L1
        evade_duration = random.randint(40, 60)
        for step in range(obstacle_start + 10, obstacle_start + 10 + evade_duration):
            timeline.append((step, {
                'roi': InfraROI(front_gap=random.uniform(3.0, 8.0), roi_left_clear=True),
                'v': random.uniform(0.4, 0.6),
                'y': random.uniform(0.25, 0.35),  # L1 차선
                'line_ey': random.uniform(-0.05, 0.05),
                'left_clear': True
            }))
        
        # 복귀: RETURN_TO_L2
        return_start = obstacle_start + 10 + evade_duration
        for step in range(return_start, min(return_start + 40, self.steps)):
            y_progress = (step - return_start) / 40.0
            y_val = 0.30 * (1 - y_progress)  # 0.30m → 0.0m
            timeline.append((step, {
                'roi': InfraROI(front_gap=random.uniform(5.0, 10.0), roi_left_clear=True),
                'v': random.uniform(0.4, 0.6),
                'y': y_val,
                'line_ey': random.uniform(-0.05, 0.05),
                'left_clear': True
            }))
        
        # 나머지: 정상 주행
        for step in range(min(return_start + 40, self.steps), self.steps):
            timeline.append((step, {
                'roi': InfraROI(front_gap=random.uniform(5.0, 10.0), roi_left_clear=True),
                'v': random.uniform(0.4, 0.6),
                'y': random.uniform(-0.05, 0.05),
                'line_ey': random.uniform(-0.05, 0.05),
                'left_clear': True
            }))
        
        return timeline

def run_simulation_episode(app, timeline, episode_num):
    """단일 에피소드 시뮬레이션 실행"""
    
    # TestHarness 방식으로 실행
    sim = SensorSimulator()
    sim.add_timeline(timeline)
    
    # 앱 상태 리셋
    app._stop = False
    app._stop_flag = False
    app.state = State.KEEP_L2
    app.target_lane = 2
    app.pose.x = 0.0
    app.pose.y = 0.0
    app.pose.psi = 0.0
    app.delta_prev = 0.0
    app.delta_filtered = 0.0
    app.current_episode = episode_num
    
    base_time = time.time()
    
    for step in range(len(timeline)):
        step_time = base_time + (step * app.dt)
        app._test_time = step_time
        
        sensor_data = sim.get_values(step)
        
        # 센서 데이터 주입
        if sensor_data:
            if 'y' in sensor_data:
                app.pose.y = sensor_data['y']
            if 'line_ey' in sensor_data:
                app.lines.last_ey = sensor_data['line_ey']
            if 'v' in sensor_data:
                app.speed.v_mps = sensor_data['v']
            if 'roi' in sensor_data:
                app.infra = sensor_data['roi']
            if 'left_clear' in sensor_data:
                app.left_clear_override = sensor_data['left_clear']
        
        try:
            app.step_once()
        except Exception as e:
            print(f"[ERROR] Episode {episode_num}, Step {step}: {e}")
            break
        
        # SAFE_STOP으로 종료
        if app._stop_flag:
            break
    
    app._test_time = None
    
    # 성공 여부
    success = (app.state != State.SAFE_STOP)
    return success

def run_experiment(mode, num_episodes=100, model_path=None, stats_path=None):
    """전체 실험 실행"""
    
    print(f"\n{'='*80}")
    print(f"Starting {mode.upper()} simulation experiment: {num_episodes} episodes")
    print(f"{'='*80}\n")
    
    # App 초기화
    args_dict = {
        'hz': 20,
        'run_mode': mode,
        'comm': 'dummy',
        'hb_period': 5.0,
        'log_dir': f'./results/{mode}',
        'export_dataset': 0,
        'dataset_dir': './dataset',
        'merge_shards': 0,
        'merged_out': 'merged.npz',
        'tau_ms': 0,
        'tau_jitter_ms': 0,
        'policy_onnx': '',
        'policy_ts': '',
        'yaml': 'params.yaml',
        'debug': False,
        'lidar_port': 0,  # Dummy mode: no hardware
        'ir_spacing': 0.07,
        'L': 0.20,
        'B': 0.15,
        'v_max': 0.5,
        'delta_max': 25.0,
        'delta_rate': 200.0,
        'a_max': 2.0,
        'a_min': -3.0,
        'wheel_rate': 10.0,
        'lane_width': 0.30,
        'max_y_deviation': 3.0,
        'g_trig': 1.2,
        'g_safe_min': 0.20,
        't_keep_l1_min': 0.6,
        'k_ey_keep': 4.0,
        'k_ey_evade': 6.0,
        'k_ey_return': 3.0,
        'k_delta_rate': 0.05,
        'assume_straight_nominal': 1,
        'student_model': model_path if model_path else 'models/policy_best.pth',
        'student_stats': stats_path if stats_path else 'models/normalization_stats.json'
    }
    
    cfg = AppConfig(
        hz=args_dict['hz'],
        run_mode=RunMode[args_dict['run_mode'].upper()],
        assume_straight_nominal=args_dict['assume_straight_nominal'],
        comm=args_dict['comm'],
        hb_period=args_dict['hb_period'],
        log_dir=args_dict['log_dir'],
        export_dataset=args_dict['export_dataset'],
        dataset_dir=args_dict['dataset_dir'],
        merge_shards=args_dict['merge_shards'],
        merged_out=args_dict['merged_out'],
        tau_ms=args_dict['tau_ms'],
        tau_jitter_ms=args_dict['tau_jitter_ms'],
        policy_onnx=args_dict['policy_onnx'],
        policy_ts=args_dict['policy_ts'],
        yaml_path=args_dict['yaml'],
        debug_print=0,
        lidar_port=args_dict['lidar_port'],
        ir_sensor_spacing=args_dict['ir_spacing'],
        student_model_path=args_dict['student_model'],
        student_stats_path=args_dict['student_stats']
    )
    
    vp = VehicleParams(
        L=args_dict['L'], B=args_dict['B'], V_MAX=args_dict['v_max'],
        DELTA_MAX_DEG=args_dict['delta_max'],
        DELTA_RATE_MAX_DEGPS=args_dict['delta_rate'],
        A_MAX=args_dict['a_max'], A_MIN=args_dict['a_min'],
        WHEEL_RATE_MAX=args_dict['wheel_rate']
    )
    
    rp = RoadParams(
        W=args_dict['lane_width'],
        MAX_Y_DEVIATION=args_dict['max_y_deviation']
    )
    
    bp = BehaviorParams(
        G_TRIG=args_dict['g_trig'],
        G_SAFE_MIN=args_dict['g_safe_min'],
        T_KEEP_L1_MIN=args_dict['t_keep_l1_min']
    )
    
    cp = ControllerParams(
        k_ey_keep=args_dict['k_ey_keep'],
        k_ey_evade=args_dict['k_ey_evade'],
        k_ey_return=args_dict['k_ey_return'],
        k_delta_rate=args_dict['k_delta_rate']
    )
    
    app = App(cfg, vp, rp, bp, cp)
    
    # 시나리오 생성기
    scenario_gen = RandomScenarioGenerator(steps_per_episode=200)
    
    # 에피소드 실행
    for ep in range(num_episodes):
        print(f"[Episode {ep+1}/{num_episodes}] ", end='', flush=True)
        
        timeline = scenario_gen.generate_episode()
        success = run_simulation_episode(app, timeline, ep)
        
        status = "SUCCESS" if success else "FAILED"
        print(f"{status}")
        
        if (ep + 1) % 10 == 0:
            success_rate = np.mean(app.episode_success) * 100
            print(f"  Progress: {ep+1}/{num_episodes} | Success rate: {success_rate:.1f}%")
    
    # 최종 저장은 app에서 자동으로 됨 (수정된 코드 사용 시)
    print(f"\n{'='*80}")
    print(f"{mode.upper()} experiment complete!")
    print(f"Success rate: {np.mean(app.episode_success)*100:.1f}%")
    print(f"Data saved to: {cfg.log_dir}/metrics.npz")
    print(f"{'='*80}\n")
    
    # 수동으로 저장
    os.makedirs(cfg.log_dir, exist_ok=True)
    np.savez(
        os.path.join(cfg.log_dir, 'metrics.npz'),
        y=np.array(app.metrics['y']),
        psi=np.array(app.metrics['psi']),
        delta=np.array(app.metrics['delta']),
        v=np.array(app.metrics['v']),
        state=np.array(app.metrics['state']),
        front_gap=np.array(app.metrics['front_gap']),
        loop_time=np.array(app.metrics['loop_time']),
        compute_time=np.array(app.metrics['compute_time']),
        episode=np.array(app.metrics['episode']),
        success=np.array(app.episode_success)
    )
    print(f"[SAVED] {cfg.log_dir}/metrics.npz")

def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['teacher', 'student', 'both'], default='both')
    parser.add_argument('--num_episodes', type=int, default=100)
    parser.add_argument('--student_model', default='models/policy_best.pth')
    parser.add_argument('--student_stats', default='models/normalization_stats.json')
    args = parser.parse_args()
    
    if args.mode in ['teacher', 'both']:
        run_experiment('teacher', args.num_episodes)
    
    if args.mode in ['student', 'both']:
        run_experiment('student', args.num_episodes,
                      args.student_model, args.student_stats)
    
    print("\n" + "="*80)
    print("ALL EXPERIMENTS COMPLETE!")
    print("Run 'python analysis.py' to generate figures and tables")
    print("="*80)

if __name__ == '__main__':
    main()
