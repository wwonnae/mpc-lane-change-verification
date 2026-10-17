"""
논문용 완전 자동화 학습 + 평가 스크립트

자동으로 수집하는 데이터:
1. Training/Validation Loss Curves
2. Learning Rate Schedule
3. Test Set Performance (MAE, MSE, R²)
4. Per-State Accuracy
5. Prediction Distribution Analysis
6. Model Inference Time
7. Training Time

사용법:
python train_policy_full.py --dataset dataset_all.npz --output_dir ./results
"""

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split

# =============================
# Dataset
# =============================
class PolicyDataset(Dataset):
    def __init__(self, npz_path: str, normalize: bool = True):
        data = np.load(npz_path, allow_pickle=True)
        
        self.X = data['features'].astype(np.float32)  # (N, 10)
        self.Y = data['labels'].astype(np.float32)    # (N, 2)
        self.meta = data.get('meta', None)
        
        print(f"✓ Loaded {len(self.X)} samples from {npz_path}")
        print(f"  Input shape: {self.X.shape}, Output shape: {self.Y.shape}")
        
        if self.X.shape[1] != 10:
            raise ValueError(f"Expected 10 features, got {self.X.shape[1]}")
        
        # Normalization
        self.normalize = normalize
        if normalize:
            self.X_mean = self.X.mean(axis=0)
            self.X_std = self.X.std(axis=0) + 1e-8
            self.Y_mean = self.Y.mean(axis=0)
            self.Y_std = self.Y.std(axis=0) + 1e-8
            
            self.X_norm = (self.X - self.X_mean) / self.X_std
            self.Y_norm = (self.Y - self.Y_mean) / self.Y_std
            
            # Save stats for later use
            self.stats = {
                'X_mean': self.X_mean.tolist(),
                'X_std': self.X_std.tolist(),
                'Y_mean': self.Y_mean.tolist(),
                'Y_std': self.Y_std.tolist()
            }
        else:
            self.X_norm = self.X
            self.Y_norm = self.Y
            self.stats = None
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X_norm[idx], self.Y_norm[idx]
    
    def get_raw_item(self, idx):
        """Get unnormalized data"""
        return self.X[idx], self.Y[idx]
    
    def denormalize_output(self, y_norm):
        """Denormalize predictions"""
        if self.normalize:
            return y_norm * self.Y_std + self.Y_mean
        return y_norm


# =============================
# Model Architecture
# =============================
class PolicyNetwork(nn.Module):
    def __init__(self, input_dim=10, hidden_dims=[64, 64], output_dim=2, dropout=0.1):
        super().__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, output_dim))
        
        self.network = nn.Sequential(*layers)
        
        # Initialize weights
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)
    
    def forward(self, x):
        return self.network(x)


# =============================
# Training Loop
# =============================
class Trainer:
    def __init__(self, model, train_loader, val_loader, test_loader, 
                 device, output_dir, lr=1e-3, weight_decay=1e-5):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.device = device
        self.output_dir = output_dir
        
        self.optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=10
        )
        self.criterion = nn.MSELoss()
        
        # Metrics tracking
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'lr': [],
            'epoch_time': []
        }
        
        self.best_val_loss = float('inf')
        self.best_epoch = 0
        
        os.makedirs(output_dir, exist_ok=True)
    
    def train_epoch(self):
        self.model.train()
        total_loss = 0
        
        for X, Y in self.train_loader:
            X, Y = X.to(self.device), Y.to(self.device)
            
            self.optimizer.zero_grad()
            pred = self.model(X)
            loss = self.criterion(pred, Y)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            total_loss += loss.item()
        
        return total_loss / len(self.train_loader)
    
    def validate(self, loader):
        self.model.eval()
        total_loss = 0
        
        with torch.no_grad():
            for X, Y in loader:
                X, Y = X.to(self.device), Y.to(self.device)
                pred = self.model(X)
                loss = self.criterion(pred, Y)
                total_loss += loss.item()
        
        return total_loss / len(loader)
    
    def train(self, num_epochs, early_stopping_patience=20):
        print(f"\n{'='*60}")
        print(f"Starting Training for {num_epochs} epochs")
        print(f"{'='*60}\n")
        
        patience_counter = 0
        
        for epoch in range(1, num_epochs + 1):
            epoch_start = time.time()
            
            # Train
            train_loss = self.train_epoch()
            
            # Validate
            val_loss = self.validate(self.val_loader)
            
            # Update scheduler
            self.scheduler.step(val_loss)
            current_lr = self.optimizer.param_groups[0]['lr']
            
            # Track metrics
            epoch_time = time.time() - epoch_start
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['lr'].append(current_lr)
            self.history['epoch_time'].append(epoch_time)
            
            # Save best model
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.best_epoch = epoch
                patience_counter = 0
                
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'val_loss': val_loss,
                }, os.path.join(self.output_dir, 'best_model.pth'))
                
                print(f"✓ Epoch {epoch:3d} | Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                      f"LR: {current_lr:.6f} | Time: {epoch_time:.2f}s | ★ BEST")
            else:
                patience_counter += 1
                print(f"  Epoch {epoch:3d} | Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                      f"LR: {current_lr:.6f} | Time: {epoch_time:.2f}s")
            
            # Early stopping
            if patience_counter >= early_stopping_patience:
                print(f"\n⚠ Early stopping at epoch {epoch} (patience={early_stopping_patience})")
                break
        
        print(f"\n{'='*60}")
        print(f"Training Complete! Best Val Loss: {self.best_val_loss:.6f} at Epoch {self.best_epoch}")
        print(f"{'='*60}\n")
        
        # Load best model
        checkpoint = torch.load(os.path.join(self.output_dir, 'best_model.pth'))
        self.model.load_state_dict(checkpoint['model_state_dict'])
    
    def plot_training_curves(self):
        """Plot and save training curves"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Loss curves
        axes[0].plot(self.history['train_loss'], label='Train Loss', linewidth=2)
        axes[0].plot(self.history['val_loss'], label='Val Loss', linewidth=2)
        axes[0].axvline(self.best_epoch - 1, color='red', linestyle='--', 
                        label=f'Best (Epoch {self.best_epoch})')
        axes[0].set_xlabel('Epoch')
        axes[0].set_ylabel('MSE Loss')
        axes[0].set_title('Training & Validation Loss')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Learning rate
        axes[1].plot(self.history['lr'], linewidth=2, color='orange')
        axes[1].set_xlabel('Epoch')
        axes[1].set_ylabel('Learning Rate')
        axes[1].set_title('Learning Rate Schedule')
        axes[1].set_yscale('log')
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'training_curves.png'), dpi=150)
        print(f"✓ Saved training curves to {self.output_dir}/training_curves.png")
        plt.close()


# =============================
# Evaluation
# =============================
class Evaluator:
    def __init__(self, model, test_loader, dataset, device, output_dir):
        self.model = model
        self.test_loader = test_loader
        self.dataset = dataset
        self.device = device
        self.output_dir = output_dir
    
    def evaluate(self):
        """Comprehensive evaluation"""
        print(f"\n{'='*60}")
        print("Evaluating on Test Set")
        print(f"{'='*60}\n")
        
        self.model.eval()
        
        all_preds = []
        all_targets = []
        all_preds_raw = []
        all_targets_raw = []
        
        # Inference time measurement
        inference_times = []
        
        with torch.no_grad():
            for X, Y in self.test_loader:
                X, Y = X.to(self.device), Y.to(self.device)
                
                # Measure inference time
                start = time.time()
                pred = self.model(X)
                inference_times.append((time.time() - start) * 1000)  # ms
                
                all_preds.append(pred.cpu().numpy())
                all_targets.append(Y.cpu().numpy())
        
        # Concatenate all batches
        preds = np.concatenate(all_preds, axis=0)
        targets = np.concatenate(all_targets, axis=0)
        
        # Denormalize for physical metrics
        preds_raw = self.dataset.denormalize_output(preds)
        targets_raw = self.dataset.denormalize_output(targets)
        
        # Compute metrics
        metrics = self._compute_metrics(preds_raw, targets_raw)
        metrics['avg_inference_time_ms'] = np.mean(inference_times)
        metrics['std_inference_time_ms'] = np.std(inference_times)
        
        # Print results
        self._print_metrics(metrics)
        
        # Save metrics
        with open(os.path.join(self.output_dir, 'test_metrics.json'), 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"✓ Saved test metrics to {self.output_dir}/test_metrics.json")
        
        # Plot prediction analysis
        self._plot_predictions(preds_raw, targets_raw)
        
        return metrics
    
    def _compute_metrics(self, preds, targets):
        """Compute various metrics"""
        mae = np.abs(preds - targets).mean(axis=0)
        mse = ((preds - targets) ** 2).mean(axis=0)
        rmse = np.sqrt(mse)
        
        # R² score
        ss_res = ((targets - preds) ** 2).sum(axis=0)
        ss_tot = ((targets - targets.mean(axis=0)) ** 2).sum(axis=0)
        r2 = 1 - ss_res / (ss_tot + 1e-8)
        
        return {
            'mae_accel': float(mae[0]),
            'mae_steering': float(mae[1]),
            'rmse_accel': float(rmse[0]),
            'rmse_steering': float(rmse[1]),
            'r2_accel': float(r2[0]),
            'r2_steering': float(r2[1]),
            'overall_mae': float(mae.mean()),
            'overall_rmse': float(rmse.mean())
        }
    
    def _print_metrics(self, metrics):
        """Pretty print metrics"""
        print("Test Set Performance:")
        print(f"  Acceleration:")
        print(f"    MAE:  {metrics['mae_accel']:.4f} m/s²")
        print(f"    RMSE: {metrics['rmse_accel']:.4f} m/s²")
        print(f"    R²:   {metrics['r2_accel']:.4f}")
        print(f"  Steering:")
        print(f"    MAE:  {metrics['mae_steering']:.4f} rad")
        print(f"    RMSE: {metrics['rmse_steering']:.4f} rad")
        print(f"    R²:   {metrics['r2_steering']:.4f}")
        print(f"  Inference Time: {metrics['avg_inference_time_ms']:.3f} ± "
              f"{metrics['std_inference_time_ms']:.3f} ms")
        print()
    
    def _plot_predictions(self, preds, targets):
        """Plot prediction vs target scatter plots"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        labels = ['Acceleration (m/s²)', 'Steering (rad)']
        
        for i, ax in enumerate(axes):
            ax.scatter(targets[:, i], preds[:, i], alpha=0.3, s=10)
            
            # Diagonal line
            min_val = min(targets[:, i].min(), preds[:, i].min())
            max_val = max(targets[:, i].max(), preds[:, i].max())
            ax.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect')
            
            ax.set_xlabel(f'True {labels[i]}')
            ax.set_ylabel(f'Predicted {labels[i]}')
            ax.set_title(f'{labels[i]} Prediction')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'prediction_scatter.png'), dpi=150)
        print(f"✓ Saved prediction plots to {self.output_dir}/prediction_scatter.png")
        plt.close()


# =============================
# Main
# =============================
def main():
    parser = argparse.ArgumentParser(description='Full Training Pipeline for Paper')
    parser.add_argument('--dataset', type=str, required=True, help='Path to dataset NPZ file')
    parser.add_argument('--output_dir', type=str, default='./results', 
                        help='Output directory for results')
    parser.add_argument('--epochs', type=int, default=200, help='Max training epochs')
    parser.add_argument('--batch_size', type=int, default=64, help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-3, help='Learning rate')
    parser.add_argument('--hidden_dims', type=int, nargs='+', default=[64, 64], 
                        help='Hidden layer dimensions')
    parser.add_argument('--dropout', type=float, default=0.1, help='Dropout rate')
    parser.add_argument('--early_stopping', type=int, default=20, 
                        help='Early stopping patience')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    # Set seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}\n")
    
    # Load dataset
    print("Loading dataset...")
    full_dataset = PolicyDataset(args.dataset, normalize=True)
    
    # Split: 70% train, 15% val, 15% test
    n = len(full_dataset)
    n_train = int(0.7 * n)
    n_val = int(0.15 * n)
    n_test = n - n_train - n_val
    
    train_dataset, val_dataset, test_dataset = random_split(
        full_dataset, [n_train, n_val, n_test],
        generator=torch.Generator().manual_seed(args.seed)
    )
    
    print(f"✓ Split: Train={n_train}, Val={n_val}, Test={n_test}\n")
    
    # Data loaders
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)
    
    # Model
    model = PolicyNetwork(
        input_dim=10,
        hidden_dims=args.hidden_dims,
        output_dim=2,
        dropout=args.dropout
    )
    
    print(f"Model: {sum(p.numel() for p in model.parameters())} parameters\n")
    
    # Save configuration
    config = vars(args)
    config['n_train'] = n_train
    config['n_val'] = n_val
    config['n_test'] = n_test
    config['n_params'] = sum(p.numel() for p in model.parameters())
    
    os.makedirs(args.output_dir, exist_ok=True)
    with open(os.path.join(args.output_dir, 'config.json'), 'w') as f:
        json.dump(config, f, indent=2)
    
    # Save normalization stats
    if full_dataset.stats:
        with open(os.path.join(args.output_dir, 'dataset_stats.json'), 'w') as f:
            json.dump(full_dataset.stats, f, indent=2)
    
    # Training
    trainer = Trainer(
        model, train_loader, val_loader, test_loader,
        device, args.output_dir, lr=args.lr
    )
    
    train_start = time.time()
    trainer.train(args.epochs, early_stopping_patience=args.early_stopping)
    train_time = time.time() - train_start
    
    print(f"Total training time: {train_time:.2f}s ({train_time/60:.2f}min)\n")
    
    # Plot training curves
    trainer.plot_training_curves()
    
    # Evaluation
    evaluator = Evaluator(model, test_loader, full_dataset, device, args.output_dir)
    metrics = evaluator.evaluate()
    
    # Export to ONNX
    print("\nExporting to ONNX...")
    dummy_input = torch.randn(1, 10).to(device)
    onnx_path = os.path.join(args.output_dir, 'policy.onnx')
    torch.onnx.export(
        model, dummy_input, onnx_path,
        input_names=['input'], output_names=['output'],
        dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},
        opset_version=11
    )
    print(f"✓ Saved ONNX model to {onnx_path}")
    
    # Save summary
    summary = {
        'training_time_sec': train_time,
        'best_epoch': trainer.best_epoch,
        'best_val_loss': trainer.best_val_loss,
        'test_metrics': metrics,
        'config': config
    }
    
    with open(os.path.join(args.output_dir, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"All results saved to: {args.output_dir}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
