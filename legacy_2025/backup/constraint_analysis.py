"""
제약 위반률 분석
학습된 모델이 물리적 제약을 얼마나 잘 만족하는지 평가
"""

import argparse
import os
import numpy as np
import torch
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def load_model_and_data(model_path, dataset_path, device='cpu'):
    """모델과 데이터 로드"""
    # 데이터 로드
    print(f"[LOAD] Loading dataset from {dataset_path}")
    data = np.load(dataset_path, allow_pickle=True)
    features = data['features'].astype(np.float32)
    labels = data['labels'].astype(np.float32)
    meta = data.get('meta', None)
    
    # 정규화 (train_policy.py와 동일)
    X_mean = features.mean(axis=0)
    X_std = features.std(axis=0) + 1e-8
    Y_mean = labels.mean(axis=0)
    Y_std = labels.std(axis=0) + 1e-8
    
    features_norm = (features - X_mean) / X_std
    
    # 모델 로드
    print(f"[LOAD] Loading model from {model_path}")
    checkpoint = torch.load(model_path, map_location=device)
    
    # 모델 재구성 (train_policy.py의 LightweightMLP)
    import sys
    sys.path.insert(0, '/mnt/user-data/uploads')
    try:
        from train_policy import LightweightMLP
        
        # 체크포인트에서 설정 추출
        state_dict = checkpoint['model_state_dict']
        
        # 첫 레이어에서 input_dim 추출
        input_dim = list(state_dict.values())[0].shape[1]
        
        # 마지막 레이어에서 output_dim 추출  
        output_dim = list(state_dict.values())[-1].shape[0]
        
        # hidden_dims 추정 (간단하게 128, 128, 64 사용)
        model = LightweightMLP(
            input_dim=input_dim,
            hidden_dims=[128, 128, 64],
            output_dim=output_dim,
            use_batchnorm=True,
            dropout=0.1
        )
        
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return None, None, None, None, None, None
    
    return model, features, features_norm, labels, meta, (X_mean, X_std, Y_mean, Y_std)


def evaluate_constraints(model, features_norm, labels, stats, device='cpu'):
    """제약 위반률 평가"""
    Y_mean, Y_std = stats[2], stats[3]
    
    # 예측
    with torch.no_grad():
        X_tensor = torch.from_numpy(features_norm).to(device)
        Y_pred_norm = model(X_tensor).cpu().numpy()
    
    # 역정규화
    predictions = Y_pred_norm * Y_std + Y_mean
    
    # 제약 조건
    DELTA_MAX = 25.0  # deg
    DELTA_MIN = -25.0  # deg
    V_MAX = 1.5  # m/s
    V_MIN = 0.0  # m/s
    
    # 위반 검사
    delta_pred = predictions[:, 0]
    v_pred = predictions[:, 1]
    
    delta_over = (delta_pred > DELTA_MAX).sum()
    delta_under = (delta_pred < DELTA_MIN).sum()
    v_over = (v_pred > V_MAX).sum()
    v_under = (v_pred < V_MIN).sum()
    
    total = len(predictions)
    
    results = {
        'total_samples': total,
        'delta_violations': {
            'over': delta_over,
            'under': delta_under,
            'total': delta_over + delta_under,
            'rate': (delta_over + delta_under) / total * 100
        },
        'v_violations': {
            'over': v_over,
            'under': v_under,
            'total': v_over + v_under,
            'rate': (v_over + v_under) / total * 100
        },
        'any_violation': {
            'count': ((np.abs(delta_pred) > DELTA_MAX) | (v_pred > V_MAX) | (v_pred < V_MIN)).sum(),
            'rate': ((np.abs(delta_pred) > DELTA_MAX) | (v_pred > V_MAX) | (v_pred < V_MIN)).sum() / total * 100
        },
        'predictions': predictions,
        'targets': labels
    }
    
    # Teacher 위반률 (비교용)
    delta_target = labels[:, 0]
    v_target = labels[:, 1]
    
    teacher_delta_viol = ((np.abs(delta_target) > DELTA_MAX).sum() / total * 100)
    teacher_v_viol = (((v_target > V_MAX) | (v_target < V_MIN)).sum() / total * 100)
    
    results['teacher_violations'] = {
        'delta_rate': teacher_delta_viol,
        'v_rate': teacher_v_viol
    }
    
    return results


def plot_constraint_analysis(results, save_dir):
    """제약 위반률 분석 시각화"""
    os.makedirs(save_dir, exist_ok=True)
    
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    
    predictions = results['predictions']
    targets = results['targets']
    
    # ========== 1. 조향각 제약 위반 ==========
    ax = axes[0, 0]
    
    violation_types = ['Over\n(>25°)', 'Under\n(<-25°)', 'Valid']
    counts = [
        results['delta_violations']['over'],
        results['delta_violations']['under'],
        results['total_samples'] - results['delta_violations']['total']
    ]
    colors = ['#e74c3c', '#e74c3c', '#2ecc71']
    
    bars = ax.bar(violation_types, counts, color=colors, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('Sample Count', fontweight='bold')
    ax.set_title('Steering Angle Constraint Violations', fontweight='bold', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + results['total_samples']*0.01,
               f'{count}\n({count/results["total_samples"]*100:.2f}%)',
               ha='center', va='bottom', fontweight='bold')
    
    # ========== 2. 속도 제약 위반 ==========
    ax = axes[0, 1]
    
    violation_types = ['Over\n(>1.5)', 'Under\n(<0)', 'Valid']
    counts = [
        results['v_violations']['over'],
        results['v_violations']['under'],
        results['total_samples'] - results['v_violations']['total']
    ]
    
    bars = ax.bar(violation_types, counts, color=colors, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('Sample Count', fontweight='bold')
    ax.set_title('Velocity Constraint Violations', fontweight='bold', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + results['total_samples']*0.01,
               f'{count}\n({count/results["total_samples"]*100:.2f}%)',
               ha='center', va='bottom', fontweight='bold')
    
    # ========== 3. 전체 위반률 비교 (Student vs Teacher) ==========
    ax = axes[0, 2]
    
    categories = ['Steering', 'Velocity', 'Any']
    student_rates = [
        results['delta_violations']['rate'],
        results['v_violations']['rate'],
        results['any_violation']['rate']
    ]
    teacher_rates = [
        results['teacher_violations']['delta_rate'],
        results['teacher_violations']['v_rate'],
        results['teacher_violations']['delta_rate'] + results['teacher_violations']['v_rate']
    ]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, student_rates, width, label='Student', 
                  color='steelblue', edgecolor='black')
    bars2 = ax.bar(x + width/2, teacher_rates, width, label='Teacher',
                  color='orange', edgecolor='black')
    
    ax.set_ylabel('Violation Rate (%)', fontweight='bold')
    ax.set_title('Violation Rate Comparison', fontweight='bold', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # 값 표시
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{height:.2f}%', ha='center', va='bottom', fontsize=9)
    
    # ========== 4. 조향각 산점도 (위반 강조) ==========
    ax = axes[1, 0]
    
    delta_pred = predictions[:, 0]
    delta_target = targets[:, 0]
    
    # 정상 샘플
    valid_mask = (np.abs(delta_pred) <= 25.0)
    ax.scatter(delta_target[valid_mask], delta_pred[valid_mask], 
              alpha=0.3, s=1, c='steelblue', label='Valid')
    
    # 위반 샘플
    invalid_mask = ~valid_mask
    ax.scatter(delta_target[invalid_mask], delta_pred[invalid_mask],
              alpha=0.8, s=10, c='red', marker='x', label='Violation')
    
    # 제약 영역 표시
    ax.axhline(y=25, color='red', linestyle='--', linewidth=2, alpha=0.7)
    ax.axhline(y=-25, color='red', linestyle='--', linewidth=2, alpha=0.7)
    ax.fill_between([-30, 30], 25, 30, alpha=0.2, color='red')
    ax.fill_between([-30, 30], -30, -25, alpha=0.2, color='red')
    
    # 완벽한 예측선
    ax.plot([-30, 30], [-30, 30], 'k--', lw=1, alpha=0.5, label='Perfect')
    
    ax.set_xlabel('Target δ (deg)', fontweight='bold')
    ax.set_ylabel('Predicted δ (deg)', fontweight='bold')
    ax.set_title('Steering Angle Predictions', fontweight='bold', fontsize=12)
    ax.set_xlim(-30, 30)
    ax.set_ylim(-30, 30)
    ax.legend()
    ax.grid(alpha=0.3)
    ax.axis('equal')
    
    # ========== 5. 속도 산점도 (위반 강조) ==========
    ax = axes[1, 1]
    
    v_pred = predictions[:, 1]
    v_target = targets[:, 1]
    
    # 정상 샘플
    valid_mask = (v_pred >= 0) & (v_pred <= 1.5)
    ax.scatter(v_target[valid_mask], v_pred[valid_mask],
              alpha=0.3, s=1, c='steelblue', label='Valid')
    
    # 위반 샘플
    invalid_mask = ~valid_mask
    ax.scatter(v_target[invalid_mask], v_pred[invalid_mask],
              alpha=0.8, s=10, c='red', marker='x', label='Violation')
    
    # 제약 영역 표시
    ax.axhline(y=1.5, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Max')
    ax.axhline(y=0.0, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Min')
    ax.fill_between([0, 1.8], 1.5, 1.8, alpha=0.2, color='red')
    ax.fill_between([0, 1.8], -0.2, 0.0, alpha=0.2, color='red')
    
    # 완벽한 예측선
    ax.plot([0, 1.8], [0, 1.8], 'k--', lw=1, alpha=0.5, label='Perfect')
    
    ax.set_xlabel('Target v (m/s)', fontweight='bold')
    ax.set_ylabel('Predicted v (m/s)', fontweight='bold')
    ax.set_title('Velocity Predictions', fontweight='bold', fontsize=12)
    ax.set_xlim(-0.1, 1.7)
    ax.set_ylim(-0.2, 1.8)
    ax.legend()
    ax.grid(alpha=0.3)
    
    # ========== 6. 위반 정도 히스토그램 ==========
    ax = axes[1, 2]
    
    # 제약 초과 정도 계산
    delta_excess = np.maximum(0, np.abs(delta_pred) - 25.0)
    
    ax.hist(delta_excess[delta_excess > 0], bins=30, color='crimson', 
           edgecolor='black', alpha=0.7)
    ax.set_xlabel('Constraint Excess (deg)', fontweight='bold')
    ax.set_ylabel('Frequency', fontweight='bold')
    ax.set_title('Steering Violation Magnitude', fontweight='bold', fontsize=12)
    ax.grid(alpha=0.3)
    
    if len(delta_excess[delta_excess > 0]) > 0:
        mean_excess = delta_excess[delta_excess > 0].mean()
        max_excess = delta_excess[delta_excess > 0].max()
        ax.axvline(mean_excess, color='blue', linestyle='--', linewidth=2,
                  label=f'Mean: {mean_excess:.2f}°')
        ax.text(0.7, 0.9, f'Max: {max_excess:.2f}°', 
               transform=ax.transAxes, fontweight='bold')
        ax.legend()
    
    plt.tight_layout()
    
    output_path = os.path.join(save_dir, 'constraint_analysis.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[SAVE] Constraint analysis plot saved to: {output_path}")
    plt.close()


def print_constraint_summary(results):
    """제약 위반 요약 출력"""
    print("\n" + "="*60)
    print("CONSTRAINT VIOLATION ANALYSIS")
    print("="*60)
    
    print(f"\nTotal samples: {results['total_samples']}")
    
    print(f"\n📐 Steering Angle Constraints (±25°):")
    print(f"   Over-violations:  {results['delta_violations']['over']:6d} ({results['delta_violations']['over']/results['total_samples']*100:5.2f}%)")
    print(f"   Under-violations: {results['delta_violations']['under']:6d} ({results['delta_violations']['under']/results['total_samples']*100:5.2f}%)")
    print(f"   Total violations: {results['delta_violations']['total']:6d} ({results['delta_violations']['rate']:5.2f}%)")
    
    print(f"\n🚗 Velocity Constraints [0, 1.5] m/s:")
    print(f"   Over-violations:  {results['v_violations']['over']:6d} ({results['v_violations']['over']/results['total_samples']*100:5.2f}%)")
    print(f"   Under-violations: {results['v_violations']['under']:6d} ({results['v_violations']['under']/results['total_samples']*100:5.2f}%)")
    print(f"   Total violations: {results['v_violations']['total']:6d} ({results['v_violations']['rate']:5.2f}%)")
    
    print(f"\n⚠️  Any Constraint Violation:")
    print(f"   Total: {results['any_violation']['count']:6d} ({results['any_violation']['rate']:5.2f}%)")
    
    print(f"\n📊 Comparison with Teacher:")
    print(f"   Teacher δ violations: {results['teacher_violations']['delta_rate']:5.2f}%")
    print(f"   Teacher v violations: {results['teacher_violations']['v_rate']:5.2f}%")
    print(f"   Student δ violations: {results['delta_violations']['rate']:5.2f}%")
    print(f"   Student v violations: {results['v_violations']['rate']:5.2f}%")
    
    if results['any_violation']['rate'] < 5.0:
        print(f"\n✅ PASS: Violation rate < 5%")
    else:
        print(f"\n⚠️  WARNING: Violation rate >= 5%")
    
    print("="*60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Constraint violation analysis')
    parser.add_argument('--model', type=str, required=True, help='Path to trained model (.pth)')
    parser.add_argument('--dataset', type=str, required=True, help='Path to dataset (.npz)')
    parser.add_argument('--save_dir', type=str, default='./constraint_analysis',
                       help='Output directory')
    parser.add_argument('--device', type=str, default='cpu', choices=['cpu', 'cuda'])
    
    args = parser.parse_args()
    
    print("="*60)
    print("  Physical Constraint Violation Analysis")
    print("="*60)
    
    # 모델과 데이터 로드
    model, features, features_norm, labels, meta, stats = load_model_and_data(
        args.model, args.dataset, args.device
    )
    
    if model is None:
        print("[ERROR] Failed to load model")
        exit(1)
    
    # 제약 평가
    results = evaluate_constraints(model, features_norm, labels, stats, args.device)
    
    # 시각화
    plot_constraint_analysis(results, args.save_dir)
    
    # 요약 출력
    print_constraint_summary(results)
    
    print("\n✅ Analysis complete!")
