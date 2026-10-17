#!/usr/bin/env python3
"""
Loop time 분석 스크립트
"""
import os
import glob
import pandas as pd
import numpy as np

# runs 디렉토리에서 가장 최근 CSV 찾기
log_files = glob.glob('./runs/*.csv')

if not log_files:
    print("❌ ./runs/ 디렉토리에 CSV 파일이 없습니다.")
    print("먼저 시뮬레이션을 실행하세요:")
    print("  python lane_change_mpc.py --hz 20 --comm dummy --test")
    exit(1)

latest = max(log_files, key=os.path.getctime)
print(f"📁 파일: {latest}\n")

# CSV 읽기
try:
    df = pd.read_csv(latest)
except Exception as e:
    print(f"❌ CSV 읽기 실패: {e}")
    exit(1)

# loop_ms 컬럼 확인
if 'loop_ms' not in df.columns:
    print(f"❌ 'loop_ms' 컬럼이 없습니다.")
    print(f"Available columns: {df.columns.tolist()}")
    exit(1)

# 분석
loop_times = df['loop_ms'].dropna()

if len(loop_times) == 0:
    print("❌ loop_ms 데이터가 없습니다.")
    exit(1)

target_ms = 1000.0 / 20.0  # 20Hz = 50ms

print("=" * 60)
print("📊 LOOP TIME 분석 결과")
print("=" * 60)
print(f"샘플 수:     {len(loop_times):,}")
print(f"평균:        {loop_times.mean():.2f} ms")
print(f"중앙값:      {loop_times.median():.2f} ms")
print(f"최소:        {loop_times.min():.2f} ms")
print(f"최대:        {loop_times.max():.2f} ms")
print(f"표준편차:    {loop_times.std():.2f} ms")
print(f"Target:      {target_ms:.2f} ms (20Hz)")
print()

# Percentile
print("📈 Percentile:")
for p in [50, 75, 90, 95, 99]:
    val = np.percentile(loop_times, p)
    print(f"  {p:2d}%: {val:6.2f} ms")
print()

# Target 대비 분석
within_target = (loop_times <= target_ms).sum()
pct = (within_target / len(loop_times)) * 100
print(f"✅ Target 이내: {within_target:,} / {len(loop_times):,} ({pct:.1f}%)")

if loop_times.max() > target_ms:
    exceeds = (loop_times > target_ms).sum()
    pct_exceeds = (exceeds / len(loop_times)) * 100
    print(f"⚠️  Target 초과: {exceeds:,} / {len(loop_times):,} ({pct_exceeds:.1f}%)")
    print(f"   최대 초과량: {loop_times.max() - target_ms:.2f} ms")

print("=" * 60)

# 상태별 분석 (state 컬럼이 있으면)
if 'state' in df.columns:
    print("\n📋 상태별 Loop Time:")
    print("-" * 60)
    state_stats = df.groupby('state')['loop_ms'].agg(['mean', 'max', 'count'])
    state_stats = state_stats.sort_values('mean', ascending=False)
    print(state_stats.to_string())
    print()

# MPC 사용 구간 분석 (EVADE_L, KEEP_L1, RETURN_TO_L2)
if 'state' in df.columns:
    mpc_heavy_states = ['EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']
    mpc_data = df[df['state'].isin(mpc_heavy_states)]['loop_ms'].dropna()
    
    if len(mpc_data) > 0:
        print("\n🔍 MPC 집중 사용 구간 (차선 변경 시):")
        print("-" * 60)
        print(f"평균: {mpc_data.mean():.2f} ms")
        print(f"최대: {mpc_data.max():.2f} ms")
        print(f"중앙값: {mpc_data.median():.2f} ms")
        
        mpc_exceeds = (mpc_data > target_ms).sum()
        mpc_pct = (mpc_exceeds / len(mpc_data)) * 100
        print(f"Target 초과: {mpc_exceeds} / {len(mpc_data)} ({mpc_pct:.1f}%)")
        print()

print("\n💡 해석:")
if loop_times.mean() < target_ms * 0.8:
    print("✅ 평균 loop time이 충분히 여유있습니다.")
elif loop_times.mean() < target_ms:
    print("✅ 평균적으로 실시간 제약을 만족합니다.")
else:
    print("⚠️  평균 loop time이 target을 초과합니다. 최적화 필요.")

if loop_times.max() > target_ms * 1.5:
    print("⚠️  일부 구간에서 심각한 지연이 발생합니다.")