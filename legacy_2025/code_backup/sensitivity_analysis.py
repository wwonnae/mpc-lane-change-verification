"""
파라미터 민감도 분석
다양한 하이퍼파라미터 조합으로 학습하여 성능 비교
"""

import argparse
import os
import json
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import sys
from pathlib import Path


def run_experiment(dataset_path, hidden_dim, dropout, epochs, batch_size, lr, save_dir, exp_name):
    """단일 실험 실행"""
    print(f"\n{'='*60}")
    print(f"Running experiment: {exp_name}")
    print(f"  hidden_dim={hidden_dim}, dropout={dropout}, lr={lr}")
    print(f"{'='*60}")
    
    exp_dir = os.path.join(save_dir, exp_name)
    
    cmd = [
        sys.executable, 'train_policy.py',
        '--dataset', dataset_path,
        '--hidden_dims', str(hidden_dim), str(hidden_dim), str(hidden_dim//2),
        '--dropout', str(dropout),
        '--epochs', str(epochs),
        '--batch_size', str(batch_size),
        '--lr', str(lr),
        '--save_dir', exp_dir,
        '--patience', '20'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        
        # 결과 파일 읽기
        history_path = os.path.join(exp_dir, 'training_history.json')
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                history = json.load(f)
            
            best_val_loss = min(history['val_loss'])
            final_train_loss = history['train_loss'][-1]
            
            return {
                'exp_name': exp_name,
                'hidden_dim': hidden_dim,
                'dropout': dropout,
                'lr': lr,
                'best_val_loss': best_val_loss,
                'final_train_loss': final_train_loss,
                'history': history
            }
        else:
            print(f"[WARN] History file not found: {history_path}")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Experiment failed: {e}")
        return None


def sensitivity_analysis(dataset_path, save_dir='./sensitivity_analysis', quick_mode=False):
    """파라미터 민감도 분석 실행"""
    os.makedirs(save_dir, exist_ok=True)
    
    if quick_mode:
        print("[INFO] Quick mode: using reduced epochs and experiments")
        epochs = 30
        experiments = [
            # hidden_dim, dropout, lr
            (64, 0.1, 1e-3),
            (128, 0.1, 1e-3),
            (128, 0.2, 1e-3),
            (128, 0.0, 1e-3),
        ]
    else:
        epochs = 80
        experiments = [
            # Baseline
            (128, 0.1, 1e-3),
            
            # Hidden dim sensitivity
            (64, 0.1, 1e-3),
            (256, 0.1, 1e-3),
            
            # Dropout sensitivity
            (128, 0.0, 1e-3),
            (128, 0.2, 1e-3),
            (128, 0.3, 1e-3),
            
            # Learning rate sensitivity
            (128, 0.1, 5e-4),
            (128, 0.1, 2e-3),
        ]
    
    results = []
    
    for i, (hidden_dim, dropout, lr) in enumerate(experiments):
        exp_name = f"exp_{i+1:02d}_h{hidden_dim}_d{dropout:.1f}_lr{lr:.0e}"
        
        result = run_experiment(
            dataset_path=dataset_path,
            hidden_dim=hidden_dim,
            dropout=dropout,
            epochs=epochs,
            batch_size=256,
            lr=lr,
            save_dir=save_dir,
            exp_name=exp_name
        )
        
        if result is not None:
            results.append(result)
    
    # 결과 저장
    results_path = os.path.join(save_dir, 'sensitivity_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n[SAVE] Results saved to: {results_path}")
    
    return results


def plot_sensitivity_results(results, save_dir):
    """민감도 분석 결과 시각화"""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # ========== 1. Hidden Dim 영향 ==========
    ax = axes[0, 0]
    hidden_dims = sorted(set(r['hidden_dim'] for r in results))
    
    # Hidden dim별로 그룹화
    hd_results = {}
    for hd in hidden_dims:
        hd_data = [r for r in results if r['hidden_dim'] == hd]
        if hd_data:
            hd_results[hd] = {
                'val_loss': np.mean([r['best_val_loss'] for r in hd_data]),
                'val_loss_std': np.std([r['best_val_loss'] for r in hd_data]),
                'train_loss': np.mean([r['final_train_loss'] for r in hd_data])
            }
    
    if hd_results:
        x = list(hd_results.keys())
        val_losses = [hd_results[k]['val_loss'] for k in x]
        val_stds = [hd_results[k]['val_loss_std'] for k in x]
        
        ax.errorbar(x, val_losses, yerr=val_stds, marker='o', capsize=5, 
                   linewidth=2, markersize=8, label='Val Loss')
        ax.set_xlabel('Hidden Layer Size', fontweight='bold')
        ax.set_ylabel('Validation Loss', fontweight='bold')
        ax.set_title('Effect of Hidden Layer Size', fontweight='bold', fontsize=12)
        ax.grid(alpha=0.3)
        ax.legend()
    
    # ========== 2. Dropout 영향 ==========
    ax = axes[0, 1]
    dropouts = sorted(set(r['dropout'] for r in results))
    
    # Dropout별로 그룹화 (hidden_dim=128만)
    do_results = {}
    for do in dropouts:
        do_data = [r for r in results if r['dropout'] == do and r['hidden_dim'] == 128]
        if do_data:
            do_results[do] = {
                'val_loss': np.mean([r['best_val_loss'] for r in do_data]),
                'val_loss_std': np.std([r['best_val_loss'] for r in do_data]),
                'train_loss': np.mean([r['final_train_loss'] for r in do_data])
            }
    
    if do_results:
        x = list(do_results.keys())
        val_losses = [do_results[k]['val_loss'] for k in x]
        train_losses = [do_results[k]['train_loss'] for k in x]
        val_stds = [do_results[k]['val_loss_std'] for k in x]
        
        ax.errorbar(x, val_losses, yerr=val_stds, marker='o', capsize=5,
                   linewidth=2, markersize=8, label='Val Loss')
        ax.plot(x, train_losses, marker='s', linewidth=2, markersize=8, 
               label='Train Loss', linestyle='--')
        ax.set_xlabel('Dropout Rate', fontweight='bold')
        ax.set_ylabel('Loss', fontweight='bold')
        ax.set_title('Effect of Dropout (Hidden=128)', fontweight='bold', fontsize=12)
        ax.grid(alpha=0.3)
        ax.legend()
    
    # ========== 3. Learning Rate 영향 ==========
    ax = axes[1, 0]
    lrs = sorted(set(r['lr'] for r in results))
    
    lr_results = {}
    for lr in lrs:
        lr_data = [r for r in results if r['lr'] == lr and r['hidden_dim'] == 128 and r['dropout'] == 0.1]
        if lr_data:
            lr_results[lr] = {
                'val_loss': np.mean([r['best_val_loss'] for r in lr_data]),
                'val_loss_std': np.std([r['best_val_loss'] for r in lr_data])
            }
    
    if lr_results:
        x_labels = [f"{lr:.0e}" for lr in lr_results.keys()]
        val_losses = [lr_results[k]['val_loss'] for k in lr_results.keys()]
        val_stds = [lr_results[k]['val_loss_std'] for k in lr_results.keys()]
        
        x_pos = range(len(x_labels))
        ax.bar(x_pos, val_losses, yerr=val_stds, capsize=5, alpha=0.7, 
              color='steelblue', edgecolor='black')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels)
        ax.set_xlabel('Learning Rate', fontweight='bold')
        ax.set_ylabel('Validation Loss', fontweight='bold')
        ax.set_title('Effect of Learning Rate', fontweight='bold', fontsize=12)
        ax.grid(axis='y', alpha=0.3)
    
    # ========== 4. 전체 비교 ==========
    ax = axes[1, 1]
    exp_names = [r['exp_name'].split('_')[1] for r in results]
    val_losses = [r['best_val_loss'] for r in results]
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(results)))
    bars = ax.bar(range(len(results)), val_losses, color=colors, edgecolor='black', alpha=0.8)
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(exp_names, rotation=45, ha='right')
    ax.set_xlabel('Experiment ID', fontweight='bold')
    ax.set_ylabel('Best Validation Loss', fontweight='bold')
    ax.set_title('All Experiments Comparison', fontweight='bold', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    
    # 최적값 표시
    best_idx = np.argmin(val_losses)
    ax.bar(best_idx, val_losses[best_idx], color='red', edgecolor='black', linewidth=2, alpha=0.8)
    ax.text(best_idx, val_losses[best_idx] + max(val_losses)*0.02, '★ BEST',
           ha='center', fontweight='bold', color='red')
    
    plt.tight_layout()
    
    output_path = os.path.join(save_dir, 'sensitivity_analysis.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"[SAVE] Sensitivity plot saved to: {output_path}")
    plt.close()
    
    # 결과 요약 출력
    print("\n" + "="*60)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("="*60)
    
    best_result = results[best_idx]
    print(f"\n★ Best Configuration:")
    print(f"   Hidden Dim: {best_result['hidden_dim']}")
    print(f"   Dropout: {best_result['dropout']}")
    print(f"   Learning Rate: {best_result['lr']}")
    print(f"   Val Loss: {best_result['best_val_loss']:.6f}")
    
    print(f"\n📊 Parameter Effects:")
    if hd_results:
        best_hd = min(hd_results.keys(), key=lambda k: hd_results[k]['val_loss'])
        print(f"   Best Hidden Dim: {best_hd} (loss={hd_results[best_hd]['val_loss']:.6f})")
    
    if do_results:
        best_do = min(do_results.keys(), key=lambda k: do_results[k]['val_loss'])
        print(f"   Best Dropout: {best_do} (loss={do_results[best_do]['val_loss']:.6f})")
    
    if lr_results:
        best_lr = min(lr_results.keys(), key=lambda k: lr_results[k]['val_loss'])
        print(f"   Best Learning Rate: {best_lr:.0e} (loss={lr_results[best_lr]['val_loss']:.6f})")
    
    print("="*60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hyperparameter sensitivity analysis')
    parser.add_argument('--dataset', type=str, required=True, help='Path to dataset')
    parser.add_argument('--save_dir', type=str, default='./sensitivity_analysis', 
                       help='Output directory')
    parser.add_argument('--quick', action='store_true', help='Quick mode (fewer experiments)')
    
    args = parser.parse_args()
    
    print("="*60)
    print("  Hyperparameter Sensitivity Analysis")
    print("="*60)
    
    # 분석 실행
    results = sensitivity_analysis(args.dataset, args.save_dir, quick_mode=args.quick)
    
    if results:
        # 시각화
        plot_sensitivity_results(results, args.save_dir)
        print("\n✅ Sensitivity analysis complete!")
    else:
        print("\n❌ No valid results obtained")
