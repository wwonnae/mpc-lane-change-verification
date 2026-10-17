#!/usr/bin/env python3
"""Check RETURN_TO_L2 data quality"""
import numpy as np
import sys

if len(sys.argv) < 2:
    print("Usage: python check_return_data.py <npz_file>")
    sys.exit(1)

data = np.load(sys.argv[1])
features = data['features']
labels = data['labels']

print("="*60)
print("RETURN_TO_L2 데이터 품질 체크")
print("="*60)

print(f"\n총 샘플: {len(features)}")

# 처음 50개 샘플 확인 (연속된 trajectory)
print("\n처음 50 steps (연속된 trajectory):")
print("  step   v    ey_line   delta")
for i in range(min(50, len(features))):
    v = features[i, 0]
    ey = features[i, 1]
    delta = labels[i, 0]
    print(f"  {i:3d}: {v:.2f}  {ey:+.3f}  {delta:+7.2f}°")

# ey 구간별 delta 통계 (양방향)
print("\ney 구간별 delta 평균 (양방향):")
bins_pos = [(0.05, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 1.1)]
bins_neg = [(-1.1, -0.5), (-0.5, -0.3), (-0.3, -0.2), (-0.2, -0.1), (-0.1, -0.05)]

print("  [음수 ey: 왼쪽, delta는 양수여야 함]")
for low, high in bins_neg:
    mask = (features[:, 1] >= low) & (features[:, 1] < high)
    if mask.sum() > 0:
        deltas = labels[mask, 0]
        print(f"  ey [{low:+.2f}, {high:+.2f}): delta={deltas.mean():+6.2f}±{deltas.std():.2f}° ({mask.sum()} samples)")

print("  [양수 ey: 오른쪽, delta는 음수여야 함]")
for low, high in bins_pos:
    mask = (features[:, 1] >= low) & (features[:, 1] < high)
    if mask.sum() > 0:
        deltas = labels[mask, 0]
        print(f"  ey [{low:+.2f}, {high:+.2f}): delta={deltas.mean():+6.2f}±{deltas.std():.2f}° ({mask.sum()} samples)")

# Delta 분포 확인
print("\nDelta 분포:")
delta_ranges = [(-25, -20), (-20, -15), (-15, -10), (-10, -5), (-5, 0), 
                (0, 5), (5, 10), (10, 15)]
for low, high in delta_ranges:
    mask = (labels[:, 0] >= low) & (labels[:, 0] < high)
    count = mask.sum()
    pct = count / len(labels) * 100
    if count > 0:
        print(f"  [{low:+3d}, {high:+3d}): {count:5d} samples ({pct:5.1f}%)")

# Chattering 체크 (연속된 방향 전환)
print("\nChattering 체크:")
delta_signs = np.sign(labels[:, 0])
sign_changes = np.sum(delta_signs[1:] != delta_signs[:-1])
total_steps = len(delta_signs) - 1
chattering_rate = sign_changes / total_steps * 100
print(f"  방향 전환: {sign_changes}/{total_steps} steps ({chattering_rate:.1f}%)")
if chattering_rate > 50:
    print(f"  ⚠️ WARNING: 높은 chattering rate!")
elif chattering_rate > 30:
    print(f"  ⚠️ CAUTION: 중간 chattering rate")
else:
    print(f"  ✅ OK: 낮은 chattering rate")

print("\n" + "="*60)
