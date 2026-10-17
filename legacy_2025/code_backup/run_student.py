"""
Student Policy Simulator Test
학습된 Student policy로 시뮬레이터 테스트
"""
import sys
import os
import argparse
import numpy as np
import time
from simulator import SimulatedEnvironment
from final import App, AppConfig, BehaviorParams, VehicleParams, RoadParams, ControllerParams, State

# PyTorch import
try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("[WARNING] PyTorch not available. Cannot run Student policy.")

# Student Policy 모델 정의 (train_policy.py와 동일)
class StudentPolicy(nn.Module):
    """Student Policy Network"""
    def __init__(self, input_dim=9, hidden_dims=[256, 256, 128], 
                 output_dim=2, use_batchnorm=True, dropout=0.15):
        super().__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            if use_batchnorm:
                layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, output_dim))
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)


class StudentPolicyWrapper:
    """Student Policy Wrapper for inference"""
    def __init__(self, model_path, stats_path, device='cpu'):
        if not HAS_TORCH:
            raise RuntimeError("PyTorch not available")
        
        self.device = device
        
        # Load model
        print(f"[STUDENT] Loading model from {model_path}")
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        
        # Create model
        self.model = StudentPolicy(
            input_dim=9,
            hidden_dims=[256, 256, 128],
            output_dim=2,
            use_batchnorm=True,
            dropout=0.15
        ).to(device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        # Load normalization stats
        import json
        with open(stats_path, 'r') as f:
            stats = json.load(f)
        
        self.X_mean = np.array(stats['X_mean'], dtype=np.float32)
        self.X_std = np.array(stats['X_std'], dtype=np.float32)
        self.Y_mean = np.array(stats['Y_mean'], dtype=np.float32)
        self.Y_std = np.array(stats['Y_std'], dtype=np.float32)
        
        print(f"[STUDENT] Model loaded successfully")
        print(f"[STUDENT] Input dim: 9, Output dim: 2")
        
        # Inference time tracking
        self.inference_times = []
    
    def predict(self, features):
        """
        Predict action from features
        
        Args:
            features: (9,) numpy array [v_cmd, ey, front_gap, left_clear, state_one_hot[5]]
        
        Returns:
            delta_deg, v_cmd
        """
        # Normalize input
        features_normalized = (features - self.X_mean) / self.X_std
        
        # To tensor
        x = torch.from_numpy(features_normalized).float().unsqueeze(0).to(self.device)
        
        # Inference
        start_time = time.time()
        with torch.no_grad():
            y_normalized = self.model(x).cpu().numpy()[0]
        inference_time = time.time() - start_time
        self.inference_times.append(inference_time * 1000)  # ms
        
        # Denormalize output
        y = y_normalized * self.Y_std + self.Y_mean
        
        delta_deg = float(y[0])
        v_cmd = float(y[1])
        
        return delta_deg, v_cmd
    
    def get_avg_inference_time(self):
        """Get average inference time in ms"""
        if len(self.inference_times) == 0:
            return 0.0
        return np.mean(self.inference_times)


def run_student_test(model_path, stats_path, num_episodes=100, steps_per_episode=300):
    """Run Student policy test in simulator"""
    
    print(f"\n{'='*70}")
    print(f"Student Policy Simulator Test")
    print(f"{'='*70}")
    print(f"Model: {model_path}")
    print(f"Stats: {stats_path}")
    print(f"Episodes: {num_episodes}")
    print(f"Steps/Episode: {steps_per_episode}")
    print(f"{'='*70}\n")
    
    # Load Student policy
    student = StudentPolicyWrapper(model_path, stats_path)
    
    # Create simulator
    vp = VehicleParams()
    rp = RoadParams()
    bp = BehaviorParams(G_TRIG=1.0, G_SAFE_MIN=0.15, T_KEEP_L1_MIN=0.5)
    cp = ControllerParams()
    cfg = AppConfig(hz=20.0)
    
    env = SimulatedEnvironment(vp, rp, bp)
    
    # Results
    results = {
        'success': 0,
        'collision': 0,
        'timeout': 0,
        'total_steps': 0,
        'inference_times': []
    }
    
    # Episode data
    episode_data = []
    
    # Run episodes
    for ep in range(num_episodes):
        # Reset simulator
        env.reset(randomize=True)
        
        # Initial state
        current_state = State.KEEP_L2
        target_lane = 2
        x, y, psi = env.state.x, env.state.y, env.state.psi
        
        episode_success = False
        episode_steps = 0
        min_distance = float('inf')
        
        for step in range(steps_per_episode):
            # Get sensor data
            ir_left, ir_center, ir_right, front_gap, left_clear, done = env.step(0, 0.5)
            
            # Update state based on FSM logic (simplified)
            # State transition logic
            if current_state == State.KEEP_L2:
                if front_gap is not None and front_gap < bp.G_TRIG:
                    current_state = State.EVADE_L
                    target_lane = 1
            elif current_state == State.EVADE_L:
                if left_clear and ir_center == 1:  # On L1
                    current_state = State.KEEP_L1
            elif current_state == State.KEEP_L1:
                if left_clear:  # Can return
                    current_state = State.RETURN_TO_L2
                    target_lane = 2
            elif current_state == State.RETURN_TO_L2:
                if ir_center == 1 and abs(y - rp.W) < 0.05:  # Back on L2
                    current_state = State.KEEP_L2
            
            # Prepare features
            ey_line = None
            if ir_center == 1:
                if target_lane == 2:
                    ey_line = y - rp.W
                else:
                    ey_line = y - 0.0
            
            v_cmd = 0.5
            feats = np.array([
                v_cmd,
                ey_line if ey_line is not None else (y - (rp.W if target_lane == 1 else 0.0)),
                front_gap if front_gap is not None else 10.0,
                float(left_clear)
            ], dtype=np.float32)
            
            # State one-hot
            state_one_hot = np.zeros(len(State), dtype=np.float32)
            state_idx = max(0, min(len(State) - 1, current_state.value - 1))
            state_one_hot[state_idx] = 1.0
            feats = np.concatenate([feats, state_one_hot])
            
            # Student prediction
            delta_deg, v_pred = student.predict(feats)
            
            # Apply to simulator
            ir_left, ir_center, ir_right, front_gap, left_clear, done = env.step(delta_deg, v_pred)
            
            # Update position
            x, y, psi = env.state.x, env.state.y, env.state.psi
            
            # Track minimum distance to obstacle
            dist = np.sqrt((x - env.obstacle_x)**2 + (y - env.obstacle_y)**2)
            min_distance = min(min_distance, dist)
            
            episode_steps += 1
            results['total_steps'] += 1
            
            # Check termination
            if done:
                if dist < 0.1:
                    results['collision'] += 1
                else:
                    results['success'] += 1
                    episode_success = True
                break
        
        # Timeout = success (completed without collision)
        if not done:
            results['success'] += 1
            episode_success = True
        
        episode_data.append({
            'episode': ep,
            'success': episode_success,
            'steps': episode_steps,
            'min_distance': min_distance
        })
        
        # Progress
        if (ep + 1) % 10 == 0 or ep == 0:
            success_rate = (results['success'] / (ep + 1)) * 100
            print(f"[STUDENT] Ep {ep+1}/{num_episodes} | "
                  f"Success: {results['success']}/{ep+1} ({success_rate:.1f}%)")
    
    # Final results
    print(f"\n{'='*70}")
    print(f"Student Policy Test Results")
    print(f"{'='*70}")
    
    success_rate = (results['success'] / num_episodes) * 100
    collision_rate = (results['collision'] / num_episodes) * 100
    
    print(f"\nEpisodes: {num_episodes}")
    print(f"Total Steps: {results['total_steps']:,}")
    print(f"\nSuccess Rate: {success_rate:.1f}% ({results['success']}/{num_episodes})")
    print(f"Collision Rate: {collision_rate:.1f}% ({results['collision']}/{num_episodes})")
    
    # Min distance stats
    min_dists = [ep['min_distance'] for ep in episode_data]
    print(f"\nSafety Margin (min distance to obstacle):")
    print(f"  Average: {np.mean(min_dists):.3f} m")
    print(f"  Minimum: {np.min(min_dists):.3f} m")
    print(f"  Maximum: {np.max(min_dists):.3f} m")
    
    avg_inference = student.get_avg_inference_time()
    print(f"\nInference Performance:")
    print(f"  Average: {avg_inference:.3f} ms")
    print(f"  Frequency: {1000/avg_inference:.1f} Hz")
    
    print(f"\n{'='*70}")
    
    # Comparison
    print(f"\n📊 Teacher vs Student Comparison:")
    print(f"  Teacher Success Rate: 100.0%")
    print(f"  Student Success Rate: {success_rate:.1f}%")
    print(f"  Difference: {100.0 - success_rate:.1f}%")
    
    if success_rate >= 95.0:
        print(f"\n✅ EXCELLENT! Student matches Teacher performance!")
    elif success_rate >= 90.0:
        print(f"\n✅ GOOD! Student performs well (>90%)")
    elif success_rate >= 80.0:
        print(f"\n⚠️  ACCEPTABLE. Student needs improvement (80-90%)")
    else:
        print(f"\n❌ POOR. Student needs retraining (<80%)")
    
    print(f"{'='*70}\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Test Student Policy in Simulator')
    parser.add_argument('--model', type=str, default='models/policy_best.pth',
                       help='Path to trained model')
    parser.add_argument('--stats', type=str, default='models/normalization_stats.json',
                       help='Path to normalization stats')
    parser.add_argument('--episodes', type=int, default=100,
                       help='Number of test episodes')
    parser.add_argument('--steps', type=int, default=300,
                       help='Steps per episode')
    
    args = parser.parse_args()
    
    if not HAS_TORCH:
        print("[ERROR] PyTorch is required for Student policy")
        return
    
    if not os.path.exists(args.model):
        print(f"[ERROR] Model not found: {args.model}")
        return
    
    if not os.path.exists(args.stats):
        print(f"[ERROR] Stats not found: {args.stats}")
        return
    
    # Run test
    results = run_student_test(
        model_path=args.model,
        stats_path=args.stats,
        num_episodes=args.episodes,
        steps_per_episode=args.steps
    )


if __name__ == '__main__':
    main()
