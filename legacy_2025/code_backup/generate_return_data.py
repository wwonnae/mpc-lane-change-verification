#!/usr/bin/env python3
"""
Generate RETURN_TO_L2 Training Data
Focus on y=[0.3, 1.0]m range with Teacher MPC demonstrations
"""

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, List

import numpy as np

# Add output path to import final.py modules
sys.path.insert(0, '/mnt/user-data/outputs')

# Import necessary classes from final.py
try:
    from final import (
        VehicleParams, RoadParams, BehaviorParams, ControllerParams,
        State, OSQPMPC, LateralController
    )
    print("[OK] Imported modules from final.py")
except Exception as e:
    print(f"[ERR] Failed to import from final.py: {e}")
    sys.exit(1)

# Define Pose class (simple version for data generation)
@dataclass
class Pose:
    """Simple pose representation"""
    x: float = 0.0
    y: float = 0.0
    psi: float = 0.0  # heading (radians)

# Constants
_RAD2DEG = 180.0 / math.pi
_DEG2RAD = math.pi / 180.0

@dataclass
class ScenarioConfig:
    """Configuration for RETURN_TO_L2 scenario"""
    y_start: float = 1.0        # Start at L1 (1.0m)
    y_end: float = 0.0          # End at L2 (0.0m)
    v_nominal: float = 0.5      # Nominal velocity (REDUCED for stability)
    psi_initial: float = 0.0    # Initial heading (deg)
    duration_max: float = 10.0  # Max scenario duration (s)
    dt: float = 0.05            # Time step (50ms)

class DataGenerator:
    """Generate RETURN_TO_L2 training data using Teacher MPC"""
    
    def __init__(self, vp: VehicleParams, rp: RoadParams, bp: BehaviorParams, cp: ControllerParams):
        self.vp = vp
        self.rp = rp
        self.bp = bp
        self.cp = cp
        self.dt = 0.05  # 50ms
        
        # Initialize MPC (Teacher) - MATCH DEPLOYMENT CODE EXACTLY
        # These parameters are proven to work in final_hierarchical_backup.py
        # Line 1613-1617: self.mpc used for RETURN_TO_L2 (Line 1955)
        self.mpc = OSQPMPC(
            vp=vp, rp=rp,
            N=15, dt=self.dt,
            qy=100.0,    # Match deployment: good position tracking
            qpsi=25.0,   # Match deployment: good heading control
            rdelta=2.0,  # Match deployment: reduce steering oscillations
            rddelta=5.0  # Match deployment: prevent abrupt changes
        )
        
        # State
        self.pose = Pose()
        self.delta_prev = 0.0
        self.v_cmd_prev = vp.V_MAX
        
        print(f"[DATAGEN] Initialized with dt={self.dt}s, MPC horizon={self.mpc.N}")
        print(f"[DATAGEN] MPC params (from deployment): qy=100, qpsi=25, rdelta=2, rddelta=5")
    
    def reset(self, y_start: float, psi_deg: float = 0.0):
        """Reset to initial state"""
        self.pose.x = 0.0
        self.pose.y = y_start
        self.pose.psi = psi_deg * _DEG2RAD
        self.delta_prev = 0.0
        self.v_cmd_prev = self.vp.V_MAX
    
    def bicycle_step(self, delta_rad: float, v: float):
        """Bicycle model dynamics"""
        L = self.vp.L
        dt = self.dt
        
        # Kinematic bicycle model
        psi_dot = v * math.tan(delta_rad) / L
        
        x_dot = v * math.cos(self.pose.psi)
        y_dot = v * math.sin(self.pose.psi)
        
        self.pose.x += x_dot * dt
        self.pose.y += y_dot * dt
        self.pose.psi += psi_dot * dt
        
        # Normalize psi to [-pi, pi]
        while self.pose.psi > math.pi:
            self.pose.psi -= 2 * math.pi
        while self.pose.psi < -math.pi:
            self.pose.psi += 2 * math.pi
    
    def generate_scenario(self, config: ScenarioConfig) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate one RETURN_TO_L2 scenario
        
        Returns:
            features: (N, 9) array
            labels: (N, 2) array
        """
        self.reset(config.y_start, config.psi_initial)
        
        features_list = []
        labels_list = []
        
        target_y = config.y_end
        v_ref = config.v_nominal
        max_steps = int(config.duration_max / self.dt)
        
        for step in range(max_steps):
            # Current state
            y = self.pose.y
            psi = self.pose.psi
            v_now = self.v_cmd_prev
            
            # Check if reached target (within 5cm)
            if abs(y - target_y) < 0.05:
                break
            
            # Compute MPC control (Teacher)
            delta_deg, ok = self.mpc.solve(y, psi, v_now, target_y)
            if not ok:
                print(f"[WARN] MPC failed at step {step}, y={y:.3f}")
                break
            
            # Saturate delta to physical limits
            DELTA_MAX = 25.0  # degrees
            delta_deg = np.clip(delta_deg, -DELTA_MAX, DELTA_MAX)
            
            # Extract features (match ACTUAL deployment code)
            # [v, ey_line, front_gap, left_clear, state_one_hot(5)]
            ey_line = y - target_y  # Error from target line (center of L2)
            front_gap = 10.0  # No obstacle
            left_clear = 1.0  # Always clear in RETURN_TO_L2
            
            # State one-hot: RETURN_TO_L2 is state index 3
            # States: KEEP_L2(0), EVADE_L(1), KEEP_L1(2), RETURN_TO_L2(3), SAFE_STOP(4)
            state_one_hot = np.zeros(5, dtype=np.float32)
            state_one_hot[3] = 1.0  # RETURN_TO_L2
            
            features = np.array([
                v_now,
                ey_line,
                front_gap,
                left_clear,
                state_one_hot[0],
                state_one_hot[1],
                state_one_hot[2],
                state_one_hot[3],
                state_one_hot[4]
            ], dtype=np.float32)
            
            # Labels (Teacher's action)
            labels = np.array([delta_deg, v_ref], dtype=np.float32)
            
            features_list.append(features)
            labels_list.append(labels)
            
            # Apply control
            delta_rad = delta_deg * _DEG2RAD
            self.bicycle_step(delta_rad, v_ref)
            
            # Update history
            self.delta_prev = delta_deg
            self.v_cmd_prev = v_ref
        
        if len(features_list) == 0:
            return None, None
        
        features_arr = np.array(features_list, dtype=np.float32)
        labels_arr = np.array(labels_list, dtype=np.float32)
        
        return features_arr, labels_arr
    
    def generate_dataset(self, num_scenarios: int, output_dir: str):
        """Generate multiple RETURN_TO_L2 scenarios"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        all_features = []
        all_labels = []
        
        print(f"\n{'='*60}")
        print(f"GENERATING RETURN_TO_L2 TRAINING DATA")
        print(f"{'='*60}")
        print(f"Target scenarios: {num_scenarios}")
        print(f"Output directory: {output_dir}")
        
        # Scenario variations - BIDIRECTIONAL
        # Include both left (y<0) and right (y>0) initial positions
        y_starts = np.concatenate([
            np.linspace(-1.0, -0.3, 8),  # Left side: L1 → L2
            np.linspace(0.3, 1.0, 8)      # Right side: past L2 → L2
        ])
        psi_initials = [-5, -2, 0, 2, 5]      # Initial heading variations (reduced range for stability)
        v_nominal = 0.5  # FIXED velocity for stable data generation
        
        scenarios_generated = 0
        total_samples = 0
        
        for i in range(num_scenarios):
            # Random scenario parameters
            y_start = np.random.choice(y_starts)
            psi_initial = np.random.choice(psi_initials)
            # v_nominal is now fixed at 0.5 m/s
            
            config = ScenarioConfig(
                y_start=y_start,
                y_end=0.0,
                v_nominal=v_nominal,
                psi_initial=psi_initial,
                duration_max=10.0,
                dt=self.dt
            )
            
            # Generate scenario
            features, labels = self.generate_scenario(config)
            
            if features is None:
                continue
            
            all_features.append(features)
            all_labels.append(labels)
            scenarios_generated += 1
            total_samples += len(features)
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{num_scenarios} scenarios, "
                      f"{scenarios_generated} successful, "
                      f"{total_samples} samples")
        
        # Concatenate all data
        print(f"\nConcatenating data...")
        features_all = np.concatenate(all_features, axis=0)
        labels_all = np.concatenate(all_labels, axis=0)
        
        print(f"\nDataset statistics:")
        print(f"  Scenarios generated: {scenarios_generated}")
        print(f"  Total samples: {len(features_all)}")
        print(f"  Features shape: {features_all.shape}")
        print(f"  Labels shape: {labels_all.shape}")
        
        # ey_line distribution (y error from L2 center)
        ey_values = features_all[:, 1]  # ey_line is 2nd feature (index 1)
        print(f"\ney_line distribution:")
        print(f"  Min:    {ey_values.min():.3f} m")
        print(f"  Max:    {ey_values.max():.3f} m")
        print(f"  Mean:   {ey_values.mean():.3f} m")
        print(f"  Median: {np.median(ey_values):.3f} m")
        
        # Delta distribution
        delta_values = labels_all[:, 0]
        print(f"\nDelta distribution:")
        print(f"  Min:    {delta_values.min():.2f} deg")
        print(f"  Max:    {delta_values.max():.2f} deg")
        print(f"  Mean:   {delta_values.mean():.2f} deg")
        print(f"  Median: {np.median(delta_values):.2f} deg")
        print(f"  Std:    {delta_values.std():.2f} deg")
        
        # Count samples in critical ranges
        print(f"\ney_line range distribution:")
        ranges = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0)]
        for low, high in ranges:
            mask = (ey_values >= low) & (ey_values < high)
            count = mask.sum()
            if len(ey_values) > 0:
                pct = 100 * count / len(ey_values)
                print(f"  [{low:.1f}, {high:.1f})m: {count:6d} samples ({pct:5.2f}%)")
        
        # Save dataset
        output_file = os.path.join(output_dir, "shard_00000.npz")
        print(f"\nSaving to: {output_file}")
        
        meta = {
            'scenario_type': 'RETURN_TO_L2',
            'num_scenarios': scenarios_generated,
            'total_samples': len(features_all),
            'dt': self.dt,
            'ey_range': [float(ey_values.min()), float(ey_values.max())],
            'feature_names': ['v', 'ey_line', 'front_gap', 'left_clear',
                            'state_KEEP_L2', 'state_EVADE_L', 'state_KEEP_L1', 
                            'state_RETURN_TO_L2', 'state_SAFE_STOP'],
            'label_names': ['delta', 'v']
        }
        
        np.savez_compressed(
            output_file,
            features=features_all,
            labels=labels_all,
            meta=json.dumps(meta)
        )
        
        print(f"\n{'='*60}")
        print(f"SUCCESS! Generated {total_samples} RETURN_TO_L2 samples")
        print(f"{'='*60}")
        
        return output_file

def main():
    parser = argparse.ArgumentParser(description='Generate RETURN_TO_L2 training data')
    parser.add_argument('--output', type=str, default='dataset_return',
                       help='Output directory')
    parser.add_argument('--num-scenarios', type=int, default=100,
                       help='Number of scenarios to generate')
    args = parser.parse_args()
    
    # Initialize parameters (same as final.py)
    vp = VehicleParams()
    rp = RoadParams()
    bp = BehaviorParams()
    cp = ControllerParams()
    
    # Create generator
    generator = DataGenerator(vp, rp, bp, cp)
    
    # Generate dataset
    output_file = generator.generate_dataset(
        num_scenarios=args.num_scenarios,
        output_dir=args.output
    )
    
    print(f"\nOutput: {output_file}")
    print(f"\nNext steps:")
    print(f"  1. Combine with existing data:")
    print(f"     - Original: /mnt/user-data/uploads/shard_00000.npz (60k samples)")
    print(f"     - New: {output_file} (~10k samples)")
    print(f"  2. Retrain Student NN:")
    print(f"     python train_policy.py --data dataset_teacher_500/,{args.output}/")
    print(f"  3. Test improved Student NN:")
    print(f"     python final_hierarchical.py --test")

if __name__ == "__main__":
    main()
