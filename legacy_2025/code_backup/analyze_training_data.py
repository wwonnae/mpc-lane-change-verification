#!/usr/bin/env python3
"""
Training Data Analysis Script
Analyze RETURN_TO_L2 samples and y_error distribution
"""

import numpy as np
import sys

def analyze_training_data(data_path):
    """Analyze training data distribution"""
    
    # Load data
    print(f"Loading data from: {data_path}")
    data = np.load(data_path)
    
    # Check available keys
    print(f"\nAvailable keys: {list(data.keys())}")
    
    # Load arrays
    X = data['features']  # Features
    Y = data['labels']  # Targets (delta, v)
    
    print(f"\nData shape:")
    print(f"  X: {X.shape}")
    print(f"  Y: {Y.shape}")
    print(f"  Total samples: {len(X)}")
    
    # Feature indices (from dataset generation)
    # X: [delta_prev, delta_dot, v, y, y_dot, line_ey, ttc, gap, left_clear]
    idx_v = 2
    idx_y = 3
    idx_y_dot = 4
    idx_line_ey = 5
    idx_gap = 7
    
    # Y: [delta, v]
    idx_delta = 0
    idx_v_cmd = 1
    
    print("\n" + "="*60)
    print("OVERALL DISTRIBUTION")
    print("="*60)
    
    # Y distribution
    y_values = X[:, idx_y]
    print(f"\nLateral Position (y):")
    print(f"  Min:    {y_values.min():.3f} m")
    print(f"  Max:    {y_values.max():.3f} m")
    print(f"  Mean:   {y_values.mean():.3f} m")
    print(f"  Median: {np.median(y_values):.3f} m")
    print(f"  Std:    {y_values.std():.3f} m")
    
    # Delta distribution
    delta_values = Y[:, idx_delta]
    print(f"\nSteering Angle (delta):")
    print(f"  Min:    {delta_values.min():.2f} deg")
    print(f"  Max:    {delta_values.max():.2f} deg")
    print(f"  Mean:   {delta_values.mean():.2f} deg")
    print(f"  Median: {np.median(delta_values):.2f} deg")
    print(f"  Std:    {delta_values.std():.2f} deg")
    
    print("\n" + "="*60)
    print("Y_ERROR DISTRIBUTION ANALYSIS")
    print("="*60)
    
    # Analyze different y_error ranges
    ranges = [
        (0.0, 0.1, "Small error (0.0-0.1m)"),
        (0.1, 0.3, "Medium error (0.1-0.3m)"),
        (0.3, 0.5, "Large error (0.3-0.5m)"),
        (0.5, 1.0, "Very large error (0.5-1.0m)"),
    ]
    
    for low, high, label in ranges:
        # Find samples in this range (absolute y value)
        mask = (np.abs(y_values) >= low) & (np.abs(y_values) < high)
        count = mask.sum()
        percentage = 100 * count / len(X)
        
        if count > 0:
            delta_range = delta_values[mask]
            print(f"\n{label}:")
            print(f"  Count:      {count:6d} samples ({percentage:5.2f}%)")
            print(f"  Delta mean: {delta_range.mean():+7.2f} deg")
            print(f"  Delta std:  {delta_range.std():7.2f} deg")
            print(f"  Delta min:  {delta_range.min():+7.2f} deg")
            print(f"  Delta max:  {delta_range.max():+7.2f} deg")
        else:
            print(f"\n{label}:")
            print(f"  Count:      {count:6d} samples ({percentage:5.2f}%)")
    
    print("\n" + "="*60)
    print("CRITICAL: LARGE ERROR ANALYSIS (y > 0.3m)")
    print("="*60)
    
    # Focus on large errors (the problematic range in RETURN_TO_L2)
    large_error_mask = np.abs(y_values) > 0.3
    large_error_count = large_error_mask.sum()
    large_error_pct = 100 * large_error_count / len(X)
    
    print(f"\nSamples with |y| > 0.3m:")
    print(f"  Count:      {large_error_count:6d} samples ({large_error_pct:5.2f}%)")
    
    if large_error_count > 0:
        large_y = y_values[large_error_mask]
        large_delta = delta_values[large_error_mask]
        
        print(f"\nY distribution (large errors):")
        print(f"  Min:    {large_y.min():.3f} m")
        print(f"  Max:    {large_y.max():.3f} m")
        print(f"  Mean:   {large_y.mean():.3f} m")
        print(f"  Median: {np.median(large_y):.3f} m")
        
        print(f"\nDelta distribution (large errors):")
        print(f"  Min:    {large_delta.min():.2f} deg")
        print(f"  Max:    {large_delta.max():.2f} deg")
        print(f"  Mean:   {large_delta.mean():.2f} deg")
        print(f"  Median: {np.median(large_delta):.2f} deg")
        print(f"  Std:    {large_delta.std():.2f} deg")
        
        # Check if Student's observed output (-0.24deg) is in this range
        observed_student_delta = -0.24
        delta_min = large_delta.min()
        delta_max = large_delta.max()
        
        print(f"\n⚠️  Student NN observed output: {observed_student_delta:.2f} deg")
        print(f"   Training data range: [{delta_min:.2f}, {delta_max:.2f}] deg")
        
        if delta_min <= observed_student_delta <= delta_max:
            print(f"   ✅ Within training range (but may need more aggressive values)")
        else:
            print(f"   ❌ OUTSIDE training range! Student learned insufficient correction.")
    else:
        print("\n⚠️  WARNING: No samples with |y| > 0.3m found!")
        print("   This explains why Student NN cannot handle large deviations!")
    
    # Percentile analysis
    print("\n" + "="*60)
    print("PERCENTILE ANALYSIS")
    print("="*60)
    
    percentiles = [50, 75, 90, 95, 99, 99.9]
    print(f"\n|Y| Percentiles:")
    for p in percentiles:
        val = np.percentile(np.abs(y_values), p)
        print(f"  {p:5.1f}%: {val:.3f} m")
    
    print(f"\n|Delta| Percentiles:")
    for p in percentiles:
        val = np.percentile(np.abs(delta_values), p)
        print(f"  {p:5.1f}%: {val:.2f} deg")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    if large_error_pct < 5.0:
        print("\n⚠️  INSUFFICIENT LARGE ERROR SAMPLES!")
        print(f"   Only {large_error_pct:.2f}% of samples have |y| > 0.3m")
        print("\n   Recommendations:")
        print("   1. Generate more RETURN_TO_L2 scenarios")
        print("   2. Include samples with y=[0.3, 0.5, 0.7, 1.0]m")
        print("   3. Ensure Teacher MPC provides aggressive corrections")
        print("   4. Target: >10% samples with |y| > 0.3m")
    else:
        print("\n✅ Sufficient large error samples")
        print(f"   {large_error_pct:.2f}% of samples have |y| > 0.3m")
    
    if large_error_count > 0 and large_delta.std() < 5.0:
        print("\n⚠️  LOW VARIANCE IN LARGE ERROR CORRECTIONS!")
        print(f"   Delta std = {large_delta.std():.2f} deg (should be >5 deg)")
        print("   Student may not learn diverse recovery strategies")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    else:
        data_path = "/mnt/user-data/uploads/shard_00000.npz"
    
    try:
        analyze_training_data(data_path)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
