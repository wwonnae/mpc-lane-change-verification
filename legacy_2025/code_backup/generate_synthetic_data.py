"""
합성 데이터 생성 및 MPC Expert Demo 수집

작동 방식:
1. 다양한 front_gap 프로파일 생성 (500~1000개 시나리오)
2. 각 시나리오를 lane_change_mpc_final.py에 입력
3. MPC가 생성한 제어 명령(steering, velocity) 수집
4. train_policy.py 형식에 맞게 저장 (npz)

사용법:
    python generate_synthetic_data.py --num_scenarios 1000 --output_dir ./synthetic_data
"""

import argparse
import numpy as np
import os
import sys
import json
from typing import List, Tuple, Dict
from dataclasses import dataclass
import time


# =============================
# 합성 데이터 생성 파라미터
# =============================
@dataclass
class SyntheticConfig:
    """합성 데이터 생성 설정"""
    
    # 초기 장애물 거리 범위 (cm)
    initial_gap_min: float = 50.0
    initial_gap_max: float = 200.0
    
    # 감소 속도 (cm/step) - 20Hz 기준
    decay_rates: List[float] = None  # [빠름, 중간, 느림]
    
    # 노이즈 레벨 (cm)
    noise_std: float = 2.0
    
    # 시뮬레이션 길이 (steps)
    sim_length: int = 400  # 20초 @ 20Hz
    
    # 특수 시나리오 비율
    sudden_stop_ratio: float = 0.1  # 급정지
    fluctuation_ratio: float = 0.15  # 거리 증감 반복
    
    def __post_init__(self):
        if self.decay_rates is None:
            self.decay_rates = [3.0, 2.0, 1.0]  # 빠름/중간/느림


# =============================
# Front Gap 프로파일 생성기
# =============================
class FrontGapGenerator:
    """다양한 front_gap 시계열 프로파일 생성"""
    
    def __init__(self, config: SyntheticConfig, seed: int = 42):
        self.cfg = config
        self.rng = np.random.RandomState(seed)
    
    def generate_normal_profile(self) -> np.ndarray:
        """일반적인 감소 프로파일: 초기값 → 0으로 선형 감소"""
        initial_gap = self.rng.uniform(self.cfg.initial_gap_min, self.cfg.initial_gap_max)
        decay_rate = self.rng.choice(self.cfg.decay_rates)
        
        gap_profile = []
        current_gap = initial_gap
        
        for step in range(self.cfg.sim_length):
            # 노이즈 추가
            noise = self.rng.normal(0, self.cfg.noise_std)
            noisy_gap = max(0.0, current_gap + noise)
            gap_profile.append(noisy_gap)
            
            # 감소
            current_gap = max(0.0, current_gap - decay_rate)
            
            # 0에 도달하면 유지
            if current_gap <= 0:
                current_gap = 0.0
        
        return np.array(gap_profile)
    
    def generate_sudden_stop_profile(self) -> np.ndarray:
        """급정지 프로파일: 정상 주행 → 갑작스런 급감속"""
        initial_gap = self.rng.uniform(100.0, self.cfg.initial_gap_max)
        
        # 정상 주행 구간 (느린 감소)
        normal_steps = self.rng.randint(30, 60)  # 1.5~3초
        slow_decay = 0.5
        
        gap_profile = []
        current_gap = initial_gap
        
        for step in range(self.cfg.sim_length):
            noise = self.rng.normal(0, self.cfg.noise_std)
            noisy_gap = max(0.0, current_gap + noise)
            gap_profile.append(noisy_gap)
            
            if step < normal_steps:
                # 정상 주행: 느린 감소
                current_gap = max(0.0, current_gap - slow_decay)
            else:
                # 급정지: 빠른 감소
                current_gap = max(0.0, current_gap - 5.0)
            
            if current_gap <= 0:
                current_gap = 0.0
        
        return np.array(gap_profile)
    
    def generate_fluctuation_profile(self) -> np.ndarray:
        """거리 증감 반복 프로파일: 앞차 가속/감속 반복"""
        base_gap = self.rng.uniform(80.0, 150.0)
        fluctuation_amplitude = self.rng.uniform(10.0, 30.0)
        fluctuation_period = self.rng.randint(20, 40)  # 1~2초 주기
        
        gap_profile = []
        
        for step in range(self.cfg.sim_length):
            # 사인파 변동
            phase = (step % fluctuation_period) / fluctuation_period * 2 * np.pi
            fluctuation = fluctuation_amplitude * np.sin(phase)
            
            # 전체적으로는 감소 추세
            decay = step * 0.3
            
            current_gap = max(0.0, base_gap + fluctuation - decay)
            noise = self.rng.normal(0, self.cfg.noise_std)
            noisy_gap = max(0.0, current_gap + noise)
            
            gap_profile.append(noisy_gap)
        
        return np.array(gap_profile)
    
    def generate_scenario(self, scenario_type: str = 'normal') -> Dict:
        """단일 시나리오 생성"""
        if scenario_type == 'normal':
            gap_profile = self.generate_normal_profile()
        elif scenario_type == 'sudden_stop':
            gap_profile = self.generate_sudden_stop_profile()
        elif scenario_type == 'fluctuation':
            gap_profile = self.generate_fluctuation_profile()
        else:
            raise ValueError(f"Unknown scenario type: {scenario_type}")
        
        return {
            'type': scenario_type,
            'front_gap': gap_profile,
            'length': len(gap_profile)
        }
    
    def generate_batch(self, num_scenarios: int) -> List[Dict]:
        """여러 시나리오 일괄 생성"""
        scenarios = []
        
        num_normal = int(num_scenarios * (1.0 - self.cfg.sudden_stop_ratio - self.cfg.fluctuation_ratio))
        num_sudden = int(num_scenarios * self.cfg.sudden_stop_ratio)
        num_fluctuation = num_scenarios - num_normal - num_sudden
        
        print(f"[GEN] Generating {num_scenarios} scenarios:")
        print(f"  - Normal: {num_normal}")
        print(f"  - Sudden Stop: {num_sudden}")
        print(f"  - Fluctuation: {num_fluctuation}")
        
        # 일반 시나리오
        for i in range(num_normal):
            scenarios.append(self.generate_scenario('normal'))
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{num_normal} normal scenarios")
        
        # 급정지 시나리오
        for i in range(num_sudden):
            scenarios.append(self.generate_scenario('sudden_stop'))
        
        # 증감 반복 시나리오
        for i in range(num_fluctuation):
            scenarios.append(self.generate_scenario('fluctuation'))
        
        # 셔플
        self.rng.shuffle(scenarios)
        
        return scenarios


# =============================
# MPC Simulator Wrapper
# =============================
class MPCSimulator:
    """lane_change_mpc_final.py를 직접 import해서 사용"""
    
    def __init__(self):
        # Import MPC 코드
        try:
            import sys
            import os
            
            # 현재 디렉토리에서 lane_change_mpc_final.py import
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            from lane_change_mpc_final import (
                App, AppConfig, VehicleParams, RoadParams, 
                BehaviorParams, ControllerParams, RunMode
            )
            
            self.App = App
            self.AppConfig = AppConfig
            self.VehicleParams = VehicleParams
            self.RoadParams = RoadParams
            self.BehaviorParams = BehaviorParams
            self.ControllerParams = ControllerParams
            self.RunMode = RunMode
            
            print("[SIM] MPC Simulator initialized successfully")
            
        except Exception as e:
            print(f"[ERROR] Failed to import MPC code: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def run_scenario(self, front_gap_profile: np.ndarray) -> Dict:
        """
        단일 시나리오 실행
        
        Args:
            front_gap_profile: front_gap 시계열 (N,) 단위: cm
        
        Returns:
            {
                'features': np.ndarray (N, 10),
                'labels': np.ndarray (N, 2),
                'states': List[str],
                'front_gap': np.ndarray (N,)
            }
        """
        # MPC 설정
        cfg = self.AppConfig(
            hz=20.0,
            run_mode=self.RunMode.TEACHER,
            comm="dummy",
            log_dir="./temp_logs",
            export_dataset=0,
            debug_print=0,
            lidar_port=0  # LiDAR 비활성화
        )
        
        vp = self.VehicleParams()
        rp = self.RoadParams()
        bp = self.BehaviorParams()
        cp = self.ControllerParams()
        
        # App 인스턴스 생성
        app = self.App(cfg, vp, rp, bp, cp)
        
        # 시나리오 실행 (front_gap은 cm 단위로 전달)
        result = app.run_scenario(front_gap_profile)
        
        # 결과에 front_gap 추가
        result['front_gap'] = front_gap_profile
        
        return result


# =============================
# Dataset Builder
# =============================
class DatasetBuilder:
    """합성 데이터를 train_policy.py 형식으로 변환"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def build_from_scenarios(self, scenarios: List[Dict], simulator: MPCSimulator) -> str:
        """
        시나리오 배치를 실행하고 dataset_all.npz 생성
        
        Args:
            scenarios: 시나리오 리스트
            simulator: MPC 시뮬레이터
        
        Returns:
            저장된 파일 경로
        """
        all_features = []
        all_labels = []
        
        print(f"\n[BUILD] Running {len(scenarios)} scenarios through MPC...")
        print("Progress: ", end='', flush=True)
        
        for i, scenario in enumerate(scenarios):
            if (i + 1) % 10 == 0:
                print(f"{i + 1}...", end='', flush=True)
            elif (i + 1) % 100 == 0:
                print(f"\n  {i + 1}/{len(scenarios)} completed")
                print("Progress: ", end='', flush=True)
            
            # MPC 시뮬레이션 실행
            result = simulator.run_scenario(scenario['front_gap'])
            
            all_features.append(result['features'])
            all_labels.append(result['labels'])
        
        print(f"\nCompleted {len(scenarios)} scenarios!")
        
        # 배치 결합
        features = np.concatenate(all_features, axis=0)
        labels = np.concatenate(all_labels, axis=0)
        
        print(f"\n[BUILD] Total samples: {len(features)}")
        print(f"  Features shape: {features.shape}")
        print(f"  Labels shape: {labels.shape}")
        
        # 저장
        output_path = os.path.join(self.output_dir, 'dataset_all.npz')
        np.savez_compressed(
            output_path,
            features=features,
            labels=labels,
            meta=None  # meta 정보는 필요시 추가
        )
        
        print(f"\n[BUILD] Dataset saved to: {output_path}")
        
        # 통계 출력
        self._print_stats(features, labels)
        
        return output_path
    
    def _print_stats(self, features: np.ndarray, labels: np.ndarray):
        """데이터셋 통계 출력"""
        print("\n[STATS] Dataset Statistics:")
        print(f"  Features:")
        print(f"    - v_cmd:   mean={features[:, 0].mean():.3f}, std={features[:, 0].std():.3f}")
        print(f"    - ey:      mean={features[:, 1].mean():.3f}, std={features[:, 1].std():.3f}")
        print(f"    - fg:      mean={features[:, 2].mean():.3f}, std={features[:, 2].std():.3f}")
        print(f"    - ttc:     mean={features[:, 3].mean():.3f}, std={features[:, 3].std():.3f}")
        print(f"  Labels:")
        print(f"    - delta_deg: mean={labels[:, 0].mean():.3f}, std={labels[:, 0].std():.3f}")
        print(f"    - v_cmd:     mean={labels[:, 1].mean():.3f}, std={labels[:, 1].std():.3f}")


# =============================
# Main
# =============================
def main():
    parser = argparse.ArgumentParser(description='Generate synthetic data for MPC teacher')
    parser.add_argument('--num_scenarios', type=int, default=1000,
                       help='Number of scenarios to generate')
    parser.add_argument('--output_dir', type=str, default='./synthetic_data',
                       help='Output directory for dataset')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--visualize', action='store_true',
                       help='Visualize sample scenarios')
    
    # 데이터 생성 파라미터
    parser.add_argument('--initial_gap_min', type=float, default=50.0,
                       help='Minimum initial gap (cm)')
    parser.add_argument('--initial_gap_max', type=float, default=200.0,
                       help='Maximum initial gap (cm)')
    parser.add_argument('--noise_std', type=float, default=2.0,
                       help='Sensor noise std (cm)')
    parser.add_argument('--sim_length', type=int, default=400,
                       help='Simulation length (steps)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("  Synthetic Data Generator for MPC Teacher")
    print("=" * 70)
    print(f"  Number of scenarios: {args.num_scenarios}")
    print(f"  Output directory: {args.output_dir}")
    print(f"  Random seed: {args.seed}")
    print("=" * 70 + "\n")
    
    # 설정
    config = SyntheticConfig(
        initial_gap_min=args.initial_gap_min,
        initial_gap_max=args.initial_gap_max,
        noise_std=args.noise_std,
        sim_length=args.sim_length
    )
    
    # 데이터 생성기
    generator = FrontGapGenerator(config, seed=args.seed)
    
    # 시나리오 생성
    t0 = time.time()
    scenarios = generator.generate_batch(args.num_scenarios)
    t1 = time.time()
    
    print(f"\n[DONE] Generated {len(scenarios)} scenarios in {t1 - t0:.2f}s")
    
    # 샘플 시각화
    if args.visualize:
        visualize_scenarios(scenarios[:5])
    
    # MPC 시뮬레이터
    simulator = MPCSimulator()
    
    # 데이터셋 빌드
    builder = DatasetBuilder(args.output_dir)
    dataset_path = builder.build_from_scenarios(scenarios, simulator)
    
    print("\n" + "=" * 70)
    print("  ✅ All Done!")
    print("=" * 70)
    print(f"  Dataset: {dataset_path}")
    print(f"\n  Next steps:")
    print(f"    1. Train: python train_policy.py --dataset {dataset_path} --epochs 100")
    print(f"    2. Evaluate: python train_policy.py --dataset {dataset_path} --eval_only")
    print("=" * 70 + "\n")


def visualize_scenarios(scenarios: List[Dict]):
    """샘플 시나리오 시각화"""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] matplotlib not available, skipping visualization")
        return
    
    fig, axes = plt.subplots(len(scenarios), 1, figsize=(12, 3 * len(scenarios)))
    if len(scenarios) == 1:
        axes = [axes]
    
    for i, scenario in enumerate(scenarios):
        ax = axes[i]
        gap = scenario['front_gap']
        steps = np.arange(len(gap))
        
        ax.plot(steps / 20.0, gap, label=f"Type: {scenario['type']}")
        ax.axhline(y=80, color='r', linestyle='--', alpha=0.5, label='Trigger (80cm)')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Front Gap (cm)')
        ax.set_title(f"Scenario {i + 1}: {scenario['type']}")
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('sample_scenarios.png', dpi=150, bbox_inches='tight')
    print("[VIZ] Sample scenarios saved to sample_scenarios.png")
    plt.close()


if __name__ == '__main__':
    main()
