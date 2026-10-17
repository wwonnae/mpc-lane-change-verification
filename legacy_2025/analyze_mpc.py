"""
MPC 성능 분석 및 시각화
"""
import numpy as np
import matplotlib.pyplot as plt
import os

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

def load_data(result_dir):
    """데이터 로드"""
    data = np.load(os.path.join(result_dir, 'metrics.npz'), allow_pickle=True)
    return data

def analyze_mpc_performance(teacher_data):
    """MPC 예측 정확도 분석"""
    
    # 조향각 통계
    delta_mean = np.mean(teacher_data['delta'])
    delta_std = np.std(teacher_data['delta'])
    delta_min = np.min(teacher_data['delta'])
    delta_max = np.max(teacher_data['delta'])
    
    # 속도 통계
    v_mean = np.mean(teacher_data['v'])
    v_std = np.std(teacher_data['v'])
    v_min = np.min(teacher_data['v'])
    v_max = np.max(teacher_data['v'])
    
    # 제약 조건 위반 분석
    delta_violations = np.sum(np.abs(teacher_data['delta']) > 25.0)
    delta_violation_rate = (delta_violations / len(teacher_data['delta'])) * 100
    
    v_violations = np.sum((teacher_data['v'] < 0.0) | (teacher_data['v'] > 1.5))
    v_violation_rate = (v_violations / len(teacher_data['v'])) * 100
    
    return {
        'delta_mean': delta_mean,
        'delta_std': delta_std,
        'delta_min': delta_min,
        'delta_max': delta_max,
        'delta_violation_rate': delta_violation_rate,
        'v_mean': v_mean,
        'v_std': v_std,
        'v_min': v_min,
        'v_max': v_max,
        'v_violation_rate': v_violation_rate
    }

def print_mpc_tables(teacher_stats):
    """MPC 성능 표 출력"""
    
    print("\n" + "="*80)
    print("표 10. MPC 제어 성능 통계")
    print("="*80)
    print(f"{'지표':<25} {'조향각 (deg)':<25} {'속도 (m/s)':<25}")
    print("-"*80)
    print(f"{'평균':<25} {teacher_stats['delta_mean']:<25.2f} {teacher_stats['v_mean']:<25.3f}")
    print(f"{'표준편차':<25} {teacher_stats['delta_std']:<25.2f} {teacher_stats['v_std']:<25.3f}")
    print(f"{'최소값':<25} {teacher_stats['delta_min']:<25.2f} {teacher_stats['v_min']:<25.3f}")
    print(f"{'최대값':<25} {teacher_stats['delta_max']:<25.2f} {teacher_stats['v_max']:<25.3f}")
    
    print("\n" + "="*80)
    print("표 11. MPC 제약 조건 만족률")
    print("="*80)
    print(f"{'제약 조건':<40} {'위반율':<20} {'만족률':<20}")
    print("-"*80)
    print(f"{'조향각 (±25°)':<40} {teacher_stats['delta_violation_rate']:<20.2f}% "
          f"{100 - teacher_stats['delta_violation_rate']:<20.2f}%")
    print(f"{'속도 (0~1.5 m/s)':<40} {teacher_stats['v_violation_rate']:<20.2f}% "
          f"{100 - teacher_stats['v_violation_rate']:<20.2f}%")

def plot_mpc_analysis(teacher_data, output_dir):
    """MPC 성능 분석 그래프"""
    
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. 상태 분포
    ax1 = fig.add_subplot(gs[0, 0])
    states, counts = np.unique(teacher_data['state'], return_counts=True)
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#95a5a6']
    bars = ax1.bar(range(len(states)), counts, color=colors[:len(states)], edgecolor='black')
    ax1.set_xticks(range(len(states)))
    ax1.set_xticklabels(states, rotation=45, ha='right')
    ax1.set_ylabel('Sample Count', fontsize=11)
    ax1.set_title('State Distribution', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # 막대 위에 개수와 퍼센트 표시
    total = len(teacher_data['state'])
    for i, (bar, count) in enumerate(zip(bars, counts)):
        height = bar.get_height()
        percentage = (count / total) * 100
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{count}\n({percentage:.1f}%)',
                ha='center', va='bottom', fontsize=9)
    
    # 2. 조향각 분포
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.hist(teacher_data['delta'], bins=50, color='purple', alpha=0.7, edgecolor='black')
    ax2.axvline(-25, color='red', linestyle='--', linewidth=2, label='Constraint: ±25°')
    ax2.axvline(25, color='red', linestyle='--', linewidth=2)
    ax2.axvline(0, color='orange', linestyle='--', linewidth=1, label='Straight', alpha=0.5)
    ax2.set_xlabel('Steering Angle (deg)', fontsize=11)
    ax2.set_ylabel('Frequency', fontsize=11)
    ax2.set_title('Steering Angle Distribution', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # 3. 속도 분포
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.hist(teacher_data['v'], bins=50, color='darkblue', alpha=0.7, edgecolor='black')
    ax3.axvline(1.5, color='red', linestyle='--', linewidth=2, label='Max: 1.5 m/s')
    ax3.axvline(teacher_data['v'].mean(), color='orange', linestyle='--', linewidth=2,
                label=f'Mean: {teacher_data["v"].mean():.2f} m/s')
    ax3.set_xlabel('Velocity (m/s)', fontsize=11)
    ax3.set_ylabel('Frequency', fontsize=11)
    ax3.set_title('Velocity Distribution', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # 4. Front Gap 분포
    ax4 = fig.add_subplot(gs[1, 0])
    valid_gaps = teacher_data['front_gap'][teacher_data['front_gap'] < 10.0]
    ax4.hist(valid_gaps, bins=40, color='teal', alpha=0.7, edgecolor='black')
    if len(valid_gaps) > 0:
        ax4.axvline(valid_gaps.mean(), color='red', linestyle='--', linewidth=2,
                    label=f'Mean: {valid_gaps.mean():.2f}m')
    ax4.set_xlabel('Front Gap (m)', fontsize=11)
    ax4.set_ylabel('Frequency', fontsize=11)
    ax4.set_title('Front Gap Distribution', fontsize=13, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    # 5. 횡방향 오차 분포
    ax5 = fig.add_subplot(gs[1, 1])
    # 상태별 색상 구분
    for state in ['KEEP_L2', 'EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']:
        mask = teacher_data['state'] == state
        if mask.sum() > 0:
            ax5.hist(teacher_data['y'][mask], bins=30, alpha=0.5, 
                    label=state, edgecolor='black')
    ax5.axvline(0, color='black', linestyle='--', linewidth=1, label='L2 Center', alpha=0.5)
    ax5.axvline(0.3, color='green', linestyle='--', linewidth=1, label='L1 Center', alpha=0.5)
    ax5.set_xlabel('Lateral Position (m)', fontsize=11)
    ax5.set_ylabel('Frequency', fontsize=11)
    ax5.set_title('Lateral Position Distribution', fontsize=13, fontweight='bold')
    ax5.legend(fontsize=8, loc='upper right')
    ax5.grid(True, alpha=0.3)
    
    # 6. 상태별 평균 조향각
    ax6 = fig.add_subplot(gs[1, 2])
    state_order = ['KEEP_L2', 'EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']
    state_means = []
    state_stds = []
    state_colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']
    
    for state in state_order:
        mask = teacher_data['state'] == state
        if mask.sum() > 0:
            state_means.append(np.mean(teacher_data['delta'][mask]))
            state_stds.append(np.std(teacher_data['delta'][mask]))
        else:
            state_means.append(0)
            state_stds.append(0)
    
    bars = ax6.bar(range(len(state_order)), state_means, yerr=state_stds,
                   color=state_colors, alpha=0.7, edgecolor='black', capsize=5)
    ax6.axhline(0, color='black', linestyle='-', linewidth=0.5)
    ax6.set_xticks(range(len(state_order)))
    ax6.set_xticklabels(state_order, rotation=45, ha='right')
    ax6.set_ylabel('Mean Steering Angle (deg)', fontsize=11)
    ax6.set_title('Avg Steering by State', fontsize=13, fontweight='bold')
    ax6.grid(True, alpha=0.3, axis='y')
    
    # 7. 조향각 제약 위반 분석
    ax7 = fig.add_subplot(gs[2, 0])
    delta_over = np.sum(teacher_data['delta'] > 25)
    delta_under = np.sum(teacher_data['delta'] < -25)
    delta_valid = len(teacher_data['delta']) - delta_over - delta_under
    
    categories = ['Over\n(>25°)', 'Under\n(<-25°)', 'Valid']
    values = [delta_over, delta_under, delta_valid]
    colors_constraint = ['#e74c3c', '#e74c3c', '#2ecc71']
    bars = ax7.bar(categories, values, color=colors_constraint, alpha=0.7, edgecolor='black')
    
    for i, (bar, val) in enumerate(zip(bars, values)):
        percentage = (val / len(teacher_data['delta'])) * 100
        ax7.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val}\n({percentage:.2f}%)',
                ha='center', va='bottom', fontsize=10)
    
    ax7.set_ylabel('Sample Count', fontsize=11)
    ax7.set_title('Steering Angle Constraint Violations', fontsize=13, fontweight='bold')
    ax7.grid(True, alpha=0.3, axis='y')
    
    # 8. 속도 제약 위반 분석
    ax8 = fig.add_subplot(gs[2, 1])
    v_over = np.sum(teacher_data['v'] > 1.5)
    v_under = np.sum(teacher_data['v'] < 0.0)
    v_valid = len(teacher_data['v']) - v_over - v_under
    
    categories_v = ['Over\n(>1.5)', 'Under\n(<0)', 'Valid']
    values_v = [v_over, v_under, v_valid]
    bars = ax8.bar(categories_v, values_v, color=colors_constraint, alpha=0.7, edgecolor='black')
    
    for i, (bar, val) in enumerate(zip(bars, values_v)):
        percentage = (val / len(teacher_data['v'])) * 100
        ax8.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val}\n({percentage:.2f}%)',
                ha='center', va='bottom', fontsize=10)
    
    ax8.set_ylabel('Sample Count', fontsize=11)
    ax8.set_title('Velocity Constraint Violations', fontsize=13, fontweight='bold')
    ax8.grid(True, alpha=0.3, axis='y')
    
    # 9. 헤딩각 분포
    ax9 = fig.add_subplot(gs[2, 2])
    psi_deg = teacher_data['psi'] * 180 / np.pi
    ax9.hist(psi_deg, bins=50, color='indigo', alpha=0.7, edgecolor='black')
    ax9.axvline(0, color='orange', linestyle='--', linewidth=2, label='Straight')
    ax9.set_xlabel('Heading Angle (deg)', fontsize=11)
    ax9.set_ylabel('Frequency', fontsize=11)
    ax9.set_title('Heading Angle Distribution', fontsize=13, fontweight='bold')
    ax9.legend(fontsize=9)
    ax9.grid(True, alpha=0.3)
    
    plt.suptitle('MPC Performance Analysis', fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig(os.path.join(output_dir, 'mpc_performance_analysis.png'), 
                dpi=300, bbox_inches='tight')
    print(f"[PLOT] Saved mpc_performance_analysis.png")
    plt.close()

def plot_teacher_student_comparison(teacher_data, student_data, output_dir):
    """Teacher vs Student 상세 비교 그래프"""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. 조향각 비교
    ax1 = axes[0, 0]
    ax1.hist(teacher_data['delta'], bins=50, alpha=0.5, label='Teacher', 
             color='blue', edgecolor='black')
    ax1.hist(student_data['delta'], bins=50, alpha=0.5, label='Student', 
             color='red', edgecolor='black')
    ax1.axvline(teacher_data['delta'].mean(), color='blue', linestyle='--', linewidth=2)
    ax1.axvline(student_data['delta'].mean(), color='red', linestyle='--', linewidth=2)
    ax1.set_xlabel('Steering Angle (deg)', fontsize=12)
    ax1.set_ylabel('Frequency', fontsize=12)
    ax1.set_title('Steering Angle Comparison', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    # 2. 속도 비교
    ax2 = axes[0, 1]
    ax2.hist(teacher_data['v'], bins=50, alpha=0.5, label='Teacher', 
             color='blue', edgecolor='black')
    ax2.hist(student_data['v'], bins=50, alpha=0.5, label='Student', 
             color='red', edgecolor='black')
    ax2.axvline(teacher_data['v'].mean(), color='blue', linestyle='--', linewidth=2)
    ax2.axvline(student_data['v'].mean(), color='red', linestyle='--', linewidth=2)
    ax2.set_xlabel('Velocity (m/s)', fontsize=12)
    ax2.set_ylabel('Frequency', fontsize=12)
    ax2.set_title('Velocity Comparison', fontsize=14, fontweight='bold')
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3)
    
    # 3. 횡방향 위치 비교
    ax3 = axes[1, 0]
    ax3.hist(teacher_data['y'], bins=50, alpha=0.5, label='Teacher', 
             color='blue', edgecolor='black')
    ax3.hist(student_data['y'], bins=50, alpha=0.5, label='Student', 
             color='red', edgecolor='black')
    ax3.axvline(0, color='black', linestyle='--', linewidth=1, label='L2 Center')
    ax3.axvline(0.3, color='green', linestyle='--', linewidth=1, label='L1 Center')
    ax3.set_xlabel('Lateral Position (m)', fontsize=12)
    ax3.set_ylabel('Frequency', fontsize=12)
    ax3.set_title('Lateral Position Comparison', fontsize=14, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    # 4. 상태별 RMSE 비교
    ax4 = axes[1, 1]
    states = ['KEEP_L2', 'EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']
    teacher_rmse = []
    student_rmse = []
    
    for state in states:
        t_mask = teacher_data['state'] == state
        s_mask = student_data['state'] == state
        if t_mask.sum() > 0:
            teacher_rmse.append(np.sqrt(np.mean(teacher_data['y'][t_mask]**2)))
        else:
            teacher_rmse.append(0)
        if s_mask.sum() > 0:
            student_rmse.append(np.sqrt(np.mean(student_data['y'][s_mask]**2)))
        else:
            student_rmse.append(0)
    
    x = np.arange(len(states))
    width = 0.35
    ax4.bar(x - width/2, teacher_rmse, width, label='Teacher', 
            color='blue', alpha=0.7, edgecolor='black')
    ax4.bar(x + width/2, student_rmse, width, label='Student', 
            color='red', alpha=0.7, edgecolor='black')
    ax4.set_xticks(x)
    ax4.set_xticklabels(states, rotation=45, ha='right')
    ax4.set_ylabel('Lateral Error RMSE (m)', fontsize=12)
    ax4.set_title('State-wise RMSE Comparison', fontsize=14, fontweight='bold')
    ax4.legend(fontsize=11)
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'teacher_student_comparison.png'), 
                dpi=300, bbox_inches='tight')
    print(f"[PLOT] Saved teacher_student_comparison.png")
    plt.close()

def main():
    """메인 실행"""
    
    teacher_dir = './results/teacher'
    student_dir = './results/student'
    output_dir = './figures'
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("MPC 성능 분석")
    print("="*80)
    
    # 데이터 로드
    print("\n[INFO] Loading data...")
    teacher_data = load_data(teacher_dir)
    student_data = load_data(student_dir)
    
    # MPC 성능 분석
    teacher_stats = analyze_mpc_performance(teacher_data)
    
    # 표 출력
    print_mpc_tables(teacher_stats)
    
    # 그래프 생성
    print("\n[INFO] Generating plots...")
    plot_mpc_analysis(teacher_data, output_dir)
    plot_teacher_student_comparison(teacher_data, student_data, output_dir)
    
    print("\n" + "="*80)
    print("MPC 분석 완료!")
    print(f"결과 저장 위치: {output_dir}/")
    print("  - mpc_performance_analysis.png")
    print("  - teacher_student_comparison.png")
    print("="*80)

if __name__ == '__main__':
    main()
