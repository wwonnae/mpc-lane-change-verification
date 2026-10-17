#!/usr/bin/env python3
"""
Lane Change Dataset Collection Script
Runs Teacher (MPC) mode to collect expert demonstrations for lane-changing scenarios
"""

import subprocess
import sys
import os
import time

print("=" * 70)
print("Lane Change Dataset Collection")
print("=" * 70)
print()

# Configuration
DATASET_DIR = "./evade_dataset"
NUM_RUNS = 100  # 100번 반복 실행
PYTHON = sys.executable

# Create dataset directory
os.makedirs(DATASET_DIR, exist_ok=True)

print(f"Dataset directory: {DATASET_DIR}")
print(f"Number of runs: {NUM_RUNS}")
print(f"Python: {PYTHON}")
print()

# Run data collection
print("[1/3] Collecting data from Teacher (MPC) demonstrations...")
print("-" * 70)

for run_idx in range(NUM_RUNS):
    print(f"\n[Run {run_idx + 1}/{NUM_RUNS}]")
    
    cmd = [
        PYTHON,
        "lane_change_mpc_final_complete.py",
        "--test",  # Test mode (runs scenarios)
        "--run_mode", "teacher",  # Teacher mode (MPC)
        "--export_dataset", "1",  # Enable data collection
        "--dataset_dir", DATASET_DIR,  # Output directory
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        # Check if successful
        if "Passed: 6" in result.stdout:
            print(f"  ✓ Run {run_idx + 1} completed successfully")
        else:
            print(f"  ✗ Run {run_idx + 1} had failures")
            # Don't print stdout to reduce clutter
        
    except subprocess.TimeoutExpired:
        print(f"  ✗ Run {run_idx + 1} timed out")
    except Exception as e:
        print(f"  ✗ Run {run_idx + 1} failed: {e}")
    
    # Small delay between runs
    time.sleep(0.1)

print()
print("=" * 70)
print("[2/3] Merging shards into single dataset...")
print("-" * 70)

# Merge all shards
cmd_merge = [
    PYTHON,
    "lane_change_mpc_final_complete.py",
    "--merge_shards", "1",
    "--dataset_dir", DATASET_DIR,
    "--merged_out", "dataset_evade_10k.npz"
]

try:
    result = subprocess.run(cmd_merge, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 0:
        print("✓ Dataset merged successfully")
    else:
        print("✗ Merge failed")
        print(result.stderr)
except Exception as e:
    print(f"✗ Merge failed: {e}")

print()
print("=" * 70)
print("[3/3] Dataset collection complete!")
print("=" * 70)

# Check if dataset was created
if os.path.exists("dataset_evade_10k.npz"):
    import numpy as np
    data = np.load("dataset_evade_10k.npz")
    print(f"\n✓ Dataset created: dataset_evade_10k.npz")
    print(f"  Features shape: {data['features'].shape}")
    print(f"  Labels shape:   {data['labels'].shape}")
    print(f"  Total samples:  {data['features'].shape[0]}")
else:
    print("\n✗ Dataset file not found!")

print()
print("Next steps:")
print("  1. Train Student model:")
print("     python train.py --data dataset_evade_10k.npz --out evade_models")
print("  2. Test Student model:")
print("     python lane_change_mpc_final_complete.py --test --run_mode student --policy_onnx evade_models/ultra2/policy.onnx")
print()
