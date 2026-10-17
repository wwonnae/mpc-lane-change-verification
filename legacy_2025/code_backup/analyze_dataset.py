"""
데이터셋 분석 스크립트
상태별 분포, feature 통계, label 분포 시각화
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter
import os


def analyze_and_plot_dataset(npz_path, save_dir='./analysis'):
    """데이터셋 분석 및 시각화"""
    os.makedirs(save_dir, exist_ok=True)
    
    # 데이터 로드
    print(f"[LOAD] Loading dataset from {npz_path}")
    data = np.load(npz_path, allow_pickle=True)
    
    features = data['features']
    labels = data['labels']
    meta = data.get('meta', None)
    
    print(f"[INFO] Dataset shape: {features.shape}, {labels.shape}")
    
    # 상태 추출
    if meta is None:
        print("[WARN] No metadata found, skipping state analysis")
        states = None
    else:
        states = [m['state'] for m in meta]
        state_counts = Counter(states)
        print(f"[INFO] State distribution:")
        for state, count in state_counts.most_common():
            print(f"       {state:15s}: {count:6d} ({count/len(states)*100:5.2f}%)")
    
    # 그래프 생성
    fig = plt.figure(figsize=(16, 12))
    
    # ========== 1. 상태별 샘플 수 ==========
    if states is not None:
        ax1 = plt.subplot(3, 3, 1)
        state_names = list(state_counts.keys())
        state_values = [state_counts[s] for s in state_names]
        colors = ['#2ecc71', '#f39c12', '#3498db', '#9b59b6', '#e74c3c', '#95a5a6']
        
        bars = ax1.bar(range(len(state_names)), state_values, color=colors[:len(state_names)])
        ax1.set_xticks(range(len(state_names)))
        ax1.set_xticklabels(state_names, rotation=45, ha='right')
        ax1.set_ylabel('Sample Count')
        ax1.set_title('State Distribution', fontweight='bold')
        ax1.grid(axis='y', alpha=0.3)
        
        # 값 표시
        for i, (bar, val) in enumerate(zip(bars, state_values)):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                    f'{val}\n({val/len(states)*100:.1f}%)',
                    ha='center', va='bottom', fontsize=9)
    
    # ========== 2. 속도 분포 (상태별) ==========
    ax2 = plt.subplot(3, 3, 2)
    if states is not None:
        for state in state_counts.keys():
            mask = np.array([s == state for s in states])
            v_state = features[mask, 0]
            ax2.hist(v_state, bins=30, alpha=0.5, label=state)
        ax2.legend(fontsize=8)
    else:
        ax2.hist(features[:, 0], bins=50, color='steelblue', alpha=0.7)
    ax2.set_xlabel('Velocity (m/s)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Velocity Distribution', fontweight='bold')
    ax2.grid(alpha=0.3)
    
    # ========== 3. 차선 오차 분포 ==========
    ax3 = plt.subplot(3, 3, 3)
    if states is not None:
        for state in ['KEEP_L2', 'EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']:
            if state in state_counts:
                mask = np.array([s == state for s in states])
                ey_state = features[mask, 1]
                ax3.hist(ey_state, bins=30, alpha=0.5, label=state)
        ax3.legend(fontsize=8)
    else:
        ax3.hist(features[:, 1], bins=50, color='coral', alpha=0.7)
    ax3.set_xlabel('Lane Error ey (m)')
    ax3.set_ylabel('Frequency')
    ax3.set_title('Lane Error Distribution', fontweight='bold')
    ax3.grid(alpha=0.3)
    
    # ========== 4. 전방 거리 분포 ==========
    ax4 = plt.subplot(3, 3, 4)
    fg = features[:, 2]
    ax4.hist(fg, bins=50, color='teal', alpha=0.7, edgecolor='black')
    ax4.axvline(fg.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {fg.mean():.2f}m')
    ax4.set_xlabel('Front Gap (m)')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Front Gap Distribution', fontweight='bold')
    ax4.legend()
    ax4.grid(alpha=0.3)
    
    # ========== 5. TTC 분포 ==========
    ax5 = plt.subplot(3, 3, 5)
    ttc = features[:, 3]
    ttc_clipped = np.clip(ttc, 0, 10)  # 시각화용 clipping
    ax5.hist(ttc_clipped, bins=50, color='orange', alpha=0.7, edgecolor='black')
    ax5.axvline(2.0, color='red', linestyle='--', linewidth=2, label='TTC_TRIG=2.0s')
    ax5.set_xlabel('Time-to-Collision (s)')
    ax5.set_ylabel('Frequency')
    ax5.set_title('TTC Distribution (clipped at 10s)', fontweight='bold')
    ax5.legend()
    ax5.grid(alpha=0.3)
    
    # ========== 6. Left Clear 비율 ==========
    ax6 = plt.subplot(3, 3, 6)
    left_clear = features[:, 4]
    clear_count = (left_clear == 1).sum()
    blocked_count = (left_clear == 0).sum()
    ax6.bar(['Clear', 'Blocked'], [clear_count, blocked_count], color=['#2ecc71', '#e74c3c'])
    ax6.set_ylabel('Sample Count')
    ax6.set_title('Left Lane Status', fontweight='bold')
    ax6.grid(axis='y', alpha=0.3)
    for i, v in enumerate([clear_count, blocked_count]):
        ax6.text(i, v + 100, f'{v}\n({v/len(left_clear)*100:.1f}%)', ha='center', va='bottom')
    
    # ========== 7. 조향각 분포 ==========
    ax7 = plt.subplot(3, 3, 7)
    delta = labels[:, 0]
    ax7.hist(delta, bins=50, color='purple', alpha=0.7, edgecolor='black')
    ax7.axvline(25, color='red', linestyle='--', linewidth=2, label='Max: ±25°')
    ax7.axvline(-25, color='red', linestyle='--', linewidth=2)
    ax7.axvline(0, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Straight')
    ax7.set_xlabel('Steering Angle δ (deg)')
    ax7.set_ylabel('Frequency')
    ax7.set_title('Steering Angle Distribution', fontweight='bold')
    ax7.legend()
    ax7.grid(alpha=0.3)
    
    # ========== 8. 목표 속도 분포 ==========
    ax8 = plt.subplot(3, 3, 8)
    v_cmd = labels[:, 1]
    ax8.hist(v_cmd, bins=50, color='navy', alpha=0.7, edgecolor='black')
    ax8.axvline(1.5, color='red', linestyle='--', linewidth=2, label='Max: 1.5 m/s')
    ax8.axvline(v_cmd.mean(), color='orange', linestyle='--', linewidth=2, label=f'Mean: {v_cmd.mean():.2f}')
    ax8.set_xlabel('Target Velocity (m/s)')
    ax8.set_ylabel('Frequency')
    ax8.set_title('Target Velocity Distribution', fontweight='bold')
    ax8.legend()
    ax8.grid(alpha=0.3)
    
    # ========== 9. 상태별 평균 조향각 ==========
    ax9 = plt.subplot(3, 3, 9)
    if states is not None:
        state_delta_means = []
        state_delta_stds = []
        state_names_filtered = []
        for state in state_counts.keys():
            mask = np.array([s == state for s in states])
            delta_state = labels[mask, 0]
            state_delta_means.append(delta_state.mean())
            state_delta_stds.append(delta_state.std())
            state_names_filtered.append(state)
        
        x = range(len(state_names_filtered))
        ax9.bar(x, state_delta_means, yerr=state_delta_stds, capsize=5, 
               color=colors[:len(state_names_filtered)], alpha=0.7, edgecolor='black')
        ax9.set_xticks(x)
        ax9.set_xticklabels(state_names_filtered, rotation=45, ha='right')
        ax9.axhline(0, color='black', linestyle='-', linewidth=0.5)
        ax9.set_ylabel('Mean Steering Angle (deg)')
        ax9.set_title('Avg Steering by State', fontweight='bold')
        ax9.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    # 저장
    output_path = os.path.join(save_dir, 'dataset_analysis.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[SAVE] Analysis plot saved to: {output_path}")
    plt.close()
    
    # 통계 출력
    print("\n" + "="*60)
    print("DATASET STATISTICS")
    print("="*60)
    print(f"Total samples: {len(features)}")
    print(f"\nFeature statistics:")
    feature_names = ['v_now', 'ey', 'front_gap', 'ttc', 'left_clear']
    for i, name in enumerate(feature_names):
        print(f"  {name:15s}: mean={features[:, i].mean():7.3f}, std={features[:, i].std():7.3f}, "
              f"min={features[:, i].min():7.3f}, max={features[:, i].max():7.3f}")
    
    print(f"\nLabel statistics:")
    label_names = ['delta', 'v_cmd']
    for i, name in enumerate(label_names):
        print(f"  {name:15s}: mean={labels[:, i].mean():7.3f}, std={labels[:, i].std():7.3f}, "
              f"min={labels[:, i].min():7.3f}, max={labels[:, i].max():7.3f}")
    
    print("="*60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze dataset')
    parser.add_argument('--dataset', type=str, required=True, help='Path to .npz dataset')
    parser.add_argument('--save_dir', type=str, default='./analysis', help='Output directory')
    
    args = parser.parse_args()
    
    analyze_and_plot_dataset(args.dataset, args.save_dir)
    
    print("\n✅ Analysis complete!")
