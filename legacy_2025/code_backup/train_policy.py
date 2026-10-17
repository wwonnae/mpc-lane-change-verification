"""
Student Policy Training for RC Car Lane Change
final.py에 완벽하게 맞춰진 버전

Features (9차원):
  [0] v_cmd        - 명령 속도
  [1] ey           - 라인 추적 에러
  [2] front_gap    - 전방 장애물 거리
  [3] left_clear   - 좌측 공간 여부
  [4-8] state_one_hot - 현재 상태 (KEEP_L2, EVADE_L, KEEP_L1, RETURN_TO_L2, SAFE_STOP)

Labels (2차원):
  [0] delta_deg    - 조향각 (degrees)
  [1] v_cmd        - 속도 명령 (m/s)

사용법:
  python train_policy.py --dataset shard_00000.npz --epochs 200
  python train_policy.py --dataset shard_00000.npz --epochs 200 --hidden_dims 256 256 128
  python train_policy.py --dataset shard_00000.npz --model policy_best.pth --eval_only
"""

import argparse
import json
import os
import time
from typing import Tuple, Dict, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt


# =============================
# Dataset
# =============================
class PolicyDataset(Dataset):
    """RC Car Policy Dataset"""
    def __init__(self, npz_path: str, normalize: bool = True):
        print(f"[DATA] Loading from {npz_path}...")
        
        try:
            data = np.load(npz_path, allow_pickle=True)
        except Exception as e:
            raise FileNotFoundError(f"Failed to load {npz_path}: {e}")
        
        self.X = data['features'].astype(np.float32)  # (N, 9)
        self.Y = data['labels'].astype(np.float32)    # (N, 2)
        self.meta = data.get('meta', None)
        
        print(f"[DATA] Loaded {len(self.X)} samples")
        print(f"[DATA] Features: {self.X.shape}, Labels: {self.Y.shape}")
        
        # Validate dimensions
        if self.X.shape[1] != 9:
            raise ValueError(
                f"Expected 9 input features, got {self.X.shape[1]}. "
                f"Features should be: [v_cmd, ey, front_gap, left_clear, state_one_hot[5]]"
            )
        if self.Y.shape[1] != 2:
            raise ValueError(f"Expected 2 output labels, got {self.Y.shape[1]}")
        
        # Normalization
        self.normalize = normalize
        if normalize:
            self.X_mean = self.X.mean(axis=0, keepdims=True)
            self.X_std = self.X.std(axis=0, keepdims=True) + 1e-8
            self.Y_mean = self.Y.mean(axis=0, keepdims=True)
            self.Y_std = self.Y.std(axis=0, keepdims=True) + 1e-8
            
            self.X = (self.X - self.X_mean) / self.X_std
            self.Y = (self.Y - self.Y_mean) / self.Y_std
            
            print(f"[DATA] Normalized (mean=0, std=1)")
            print(f"[DATA] X_mean: {self.X_mean.squeeze()}")
            print(f"[DATA] X_std:  {self.X_std.squeeze()}")
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.Y[idx]
    
    def get_normalization_stats(self) -> Dict:
        """정규화 통계 반환 (배포용)"""
        if self.normalize:
            return {
                'X_mean': self.X_mean.squeeze().tolist(),
                'X_std': self.X_std.squeeze().tolist(),
                'Y_mean': self.Y_mean.squeeze().tolist(),
                'Y_std': self.Y_std.squeeze().tolist()
            }
        return {}


# =============================
# Model
# =============================
class StudentPolicy(nn.Module):
    """
    경량 Student Policy Network
    
    Input: 9차원
    Hidden: 2-3층 (64-256 neurons)
    Output: 2차원 (delta, v)
    """
    def __init__(self, input_dim: int = 9, hidden_dims: list = [128, 128, 64], 
                 output_dim: int = 2, use_batchnorm: bool = True, dropout: float = 0.1):
        super().__init__()
        
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        layers = []
        prev_dim = input_dim
        
        for i, hidden_dim in enumerate(hidden_dims):
            layers.append(nn.Linear(prev_dim, hidden_dim))
            
            if use_batchnorm:
                layers.append(nn.BatchNorm1d(hidden_dim))
            
            layers.append(nn.ReLU())
            
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            
            prev_dim = hidden_dim
        
        # Output layer
        layers.append(nn.Linear(prev_dim, output_dim))
        
        self.network = nn.Sequential(*layers)
        
        # Weight initialization
        self._init_weights()
        
        num_params = sum(p.numel() for p in self.parameters())
        print(f"[MODEL] Student Policy created")
        print(f"[MODEL] Architecture: {input_dim} -> {' -> '.join(map(str, hidden_dims))} -> {output_dim}")
        print(f"[MODEL] Parameters: {num_params:,}")
        print(f"[MODEL] BatchNorm: {use_batchnorm}, Dropout: {dropout}")
    
    def _init_weights(self):
        """Kaiming initialization"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
    
    def forward(self, x):
        return self.network(x)


# =============================
# Loss Function
# =============================
class WeightedMSELoss(nn.Module):
    """Delta와 V에 다른 가중치"""
    def __init__(self, delta_weight: float = 2.0, v_weight: float = 1.0):
        super().__init__()
        self.delta_weight = delta_weight
        self.v_weight = v_weight
    
    def forward(self, pred, target):
        delta_loss = F.mse_loss(pred[:, 0], target[:, 0])
        v_loss = F.mse_loss(pred[:, 1], target[:, 1])
        
        total_loss = self.delta_weight * delta_loss + self.v_weight * v_loss
        
        return total_loss, delta_loss, v_loss


# =============================
# Early Stopping
# =============================
class EarlyStopping:
    """Early stopping with patience"""
    def __init__(self, patience: int = 15, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_score = None
        self.early_stop = False
    
    def __call__(self, val_loss: float) -> bool:
        if self.best_score is None:
            self.best_score = val_loss
            return False
        
        if val_loss < (self.best_score - self.min_delta):
            self.best_score = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                print(f"[EARLY STOP] No improvement for {self.patience} epochs")
                self.early_stop = True
                return True
        
        return False


# =============================
# Trainer
# =============================
class Trainer:
    """Training orchestrator"""
    def __init__(self, model, train_loader, val_loader, device, args):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.args = args
        
        # Loss
        self.criterion = WeightedMSELoss(
            delta_weight=args.delta_weight,
            v_weight=args.v_weight
        )
        
        # Optimizer
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=args.lr,
            weight_decay=args.weight_decay
        )
        
        # Scheduler
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=10
        )
        
        # Early stopping
        self.early_stopping = EarlyStopping(patience=args.patience)
        
        # History
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'delta_rmse': [],
            'v_rmse': [],
            'lr': []
        }
        
        self.best_val_loss = float('inf')
    
    def train_epoch(self, epoch):
        """Train for one epoch"""
        self.model.train()
        
        total_loss = 0
        delta_loss_sum = 0
        v_loss_sum = 0
        
        for batch_idx, (X, Y) in enumerate(self.train_loader):
            X, Y = X.to(self.device), Y.to(self.device)
            
            # Forward
            self.optimizer.zero_grad()
            pred = self.model(X)
            loss, delta_loss, v_loss = self.criterion(pred, Y)
            
            # Backward
            loss.backward()
            
            # Gradient clipping
            if self.args.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.args.grad_clip)
            
            self.optimizer.step()
            
            total_loss += loss.item()
            delta_loss_sum += delta_loss.item()
            v_loss_sum += v_loss.item()
        
        avg_loss = total_loss / len(self.train_loader)
        avg_delta_loss = delta_loss_sum / len(self.train_loader)
        avg_v_loss = v_loss_sum / len(self.train_loader)
        
        return avg_loss, avg_delta_loss, avg_v_loss
    
    def validate(self, epoch):
        """Validate"""
        self.model.eval()
        
        total_loss = 0
        delta_loss_sum = 0
        v_loss_sum = 0
        
        all_preds = []
        all_targets = []
        
        with torch.no_grad():
            for X, Y in self.val_loader:
                X, Y = X.to(self.device), Y.to(self.device)
                
                pred = self.model(X)
                loss, delta_loss, v_loss = self.criterion(pred, Y)
                
                total_loss += loss.item()
                delta_loss_sum += delta_loss.item()
                v_loss_sum += v_loss.item()
                
                all_preds.append(pred.cpu().numpy())
                all_targets.append(Y.cpu().numpy())
        
        avg_loss = total_loss / len(self.val_loader)
        avg_delta_loss = delta_loss_sum / len(self.val_loader)
        avg_v_loss = v_loss_sum / len(self.val_loader)
        
        # RMSE 계산
        all_preds = np.concatenate(all_preds, axis=0)
        all_targets = np.concatenate(all_targets, axis=0)
        
        delta_rmse = np.sqrt(np.mean((all_preds[:, 0] - all_targets[:, 0])**2))
        v_rmse = np.sqrt(np.mean((all_preds[:, 1] - all_targets[:, 1])**2))
        
        return avg_loss, avg_delta_loss, avg_v_loss, delta_rmse, v_rmse
    
    def train(self):
        """Full training loop"""
        print(f"\n{'='*70}")
        print(f"Training Start")
        print(f"{'='*70}")
        print(f"Device: {self.device}")
        print(f"Epochs: {self.args.epochs}")
        print(f"Batch size: {self.args.batch_size}")
        print(f"Learning rate: {self.args.lr}")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        for epoch in range(1, self.args.epochs + 1):
            epoch_start = time.time()
            
            # Train
            train_loss, train_delta, train_v = self.train_epoch(epoch)
            
            # Validate
            val_loss, val_delta, val_v, delta_rmse, v_rmse = self.validate(epoch)
            
            # Scheduler step
            self.scheduler.step(val_loss)
            current_lr = self.optimizer.param_groups[0]['lr']
            
            # History
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['delta_rmse'].append(delta_rmse)
            self.history['v_rmse'].append(v_rmse)
            self.history['lr'].append(current_lr)
            
            # Print
            epoch_time = time.time() - epoch_start
            print(f"Epoch {epoch:3d}/{self.args.epochs} | "
                  f"Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                  f"Delta RMSE: {delta_rmse:.4f} | V RMSE: {v_rmse:.6f} | "
                  f"LR: {current_lr:.2e} | Time: {epoch_time:.1f}s")
            
            # Save best
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.save_checkpoint(epoch, is_best=True)
                print(f"  → Best model saved (val_loss: {val_loss:.6f})")
            
            # Save periodic checkpoint
            if epoch % self.args.save_interval == 0:
                self.save_checkpoint(epoch, is_best=False)
            
            # Early stopping
            if self.early_stopping(val_loss):
                print(f"\nEarly stopping at epoch {epoch}")
                break
        
        total_time = time.time() - start_time
        print(f"\n{'='*70}")
        print(f"Training Completed!")
        print(f"Total time: {total_time/60:.1f} minutes")
        print(f"Best validation loss: {self.best_val_loss:.6f}")
        print(f"{'='*70}\n")
        
        return self.history
    
    def save_checkpoint(self, epoch, is_best=False):
        """Save checkpoint"""
        os.makedirs(self.args.save_dir, exist_ok=True)
        
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'best_val_loss': self.best_val_loss,
            'history': self.history,
            'args': vars(self.args)
        }
        
        if is_best:
            path = os.path.join(self.args.save_dir, 'policy_best.pth')
            torch.save(checkpoint, path)
        else:
            path = os.path.join(self.args.save_dir, f'checkpoint_epoch_{epoch}.pth')
            torch.save(checkpoint, path)


# =============================
# Evaluation
# =============================
def evaluate_model(model, test_loader, device, dataset):
    """Detailed evaluation"""
    print(f"\n{'='*70}")
    print(f"Model Evaluation")
    print(f"{'='*70}")
    
    model.eval()
    
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for X, Y in test_loader:
            X, Y = X.to(device), Y.to(device)
            pred = model(X)
            
            all_preds.append(pred.cpu().numpy())
            all_targets.append(Y.cpu().numpy())
    
    all_preds = np.concatenate(all_preds, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)
    
    # Denormalize
    if dataset.normalize:
        Y_mean = dataset.Y_mean.squeeze()
        Y_std = dataset.Y_std.squeeze()
        
        all_preds = all_preds * Y_std + Y_mean
        all_targets = all_targets * Y_std + Y_mean
    
    # Metrics
    delta_pred = all_preds[:, 0]
    delta_true = all_targets[:, 0]
    delta_error = delta_pred - delta_true
    
    v_pred = all_preds[:, 1]
    v_true = all_targets[:, 1]
    v_error = v_pred - v_true
    
    print(f"\nDelta (Steering Angle):")
    print(f"  RMSE:    {np.sqrt(np.mean(delta_error**2)):.3f}°")
    print(f"  MAE:     {np.mean(np.abs(delta_error)):.3f}°")
    print(f"  Max Err: {np.max(np.abs(delta_error)):.3f}°")
    print(f"  Std:     {np.std(delta_error):.3f}°")
    print(f"  Range:   [{delta_true.min():.1f}, {delta_true.max():.1f}]°")
    
    print(f"\nVelocity:")
    print(f"  RMSE:    {np.sqrt(np.mean(v_error**2)):.4f} m/s")
    print(f"  MAE:     {np.mean(np.abs(v_error)):.4f} m/s")
    print(f"  Max Err: {np.max(np.abs(v_error)):.4f} m/s")
    print(f"  Range:   [{v_true.min():.3f}, {v_true.max():.3f}] m/s")
    
    # Large errors
    large_delta_errors = np.abs(delta_error) > 5.0
    large_v_errors = np.abs(v_error) > 0.1
    
    print(f"\nLarge Errors:")
    print(f"  Delta > 5°:    {large_delta_errors.sum():6d} ({100*large_delta_errors.mean():.2f}%)")
    print(f"  V > 0.1 m/s:   {large_v_errors.sum():6d} ({100*large_v_errors.mean():.2f}%)")
    
    print(f"{'='*70}\n")


# =============================
# Plot
# =============================
def plot_training_curves(history, save_path='training_curves.png'):
    """Plot training curves"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    
    epochs = range(1, len(history['train_loss']) + 1)
    
    # Loss
    axes[0, 0].plot(epochs, history['train_loss'], label='Train')
    axes[0, 0].plot(epochs, history['val_loss'], label='Val')
    axes[0, 0].set_xlabel('Epoch')
    axes[0, 0].set_ylabel('Loss')
    axes[0, 0].set_title('Training & Validation Loss')
    axes[0, 0].legend()
    axes[0, 0].grid(True)
    
    # Delta RMSE
    axes[0, 1].plot(epochs, history['delta_rmse'], label='Delta RMSE', color='orange')
    axes[0, 1].set_xlabel('Epoch')
    axes[0, 1].set_ylabel('RMSE (normalized)')
    axes[0, 1].set_title('Delta RMSE')
    axes[0, 1].legend()
    axes[0, 1].grid(True)
    
    # V RMSE
    axes[1, 0].plot(epochs, history['v_rmse'], label='V RMSE', color='green')
    axes[1, 0].set_xlabel('Epoch')
    axes[1, 0].set_ylabel('RMSE (normalized)')
    axes[1, 0].set_title('Velocity RMSE')
    axes[1, 0].legend()
    axes[1, 0].grid(True)
    
    # Learning Rate
    axes[1, 1].plot(epochs, history['lr'], label='LR', color='red')
    axes[1, 1].set_xlabel('Epoch')
    axes[1, 1].set_ylabel('Learning Rate')
    axes[1, 1].set_title('Learning Rate Schedule')
    axes[1, 1].set_yscale('log')
    axes[1, 1].legend()
    axes[1, 1].grid(True)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"[PLOT] Saved to {save_path}")
    plt.close()


# =============================
# Main
# =============================
def main():
    parser = argparse.ArgumentParser(description='Train Student Policy for RC Car')
    
    # Data
    parser.add_argument('--dataset', type=str, required=True, help='Path to NPZ dataset')
    parser.add_argument('--test_split', type=float, default=0.1, help='Test split ratio')
    parser.add_argument('--val_split', type=float, default=0.1, help='Validation split ratio')
    
    # Model
    parser.add_argument('--hidden_dims', nargs='+', type=int, default=[128, 128, 64], 
                        help='Hidden layer dimensions')
    parser.add_argument('--use_batchnorm', action='store_true', help='Use batch normalization')
    parser.add_argument('--dropout', type=float, default=0.1, help='Dropout rate')
    
    # Training
    parser.add_argument('--epochs', type=int, default=200, help='Number of epochs')
    parser.add_argument('--batch_size', type=int, default=256, help='Batch size')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--weight_decay', type=float, default=1e-4, help='Weight decay')
    parser.add_argument('--delta_weight', type=float, default=2.0, help='Delta loss weight')
    parser.add_argument('--v_weight', type=float, default=1.0, help='V loss weight')
    parser.add_argument('--grad_clip', type=float, default=1.0, help='Gradient clipping')
    parser.add_argument('--patience', type=int, default=15, help='Early stopping patience')
    
    # Misc
    parser.add_argument('--save_dir', type=str, default='./models', help='Save directory')
    parser.add_argument('--save_interval', type=int, default=50, help='Checkpoint save interval')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--eval_only', action='store_true', help='Evaluation only mode')
    parser.add_argument('--model', type=str, default=None, help='Model path for evaluation')
    
    args = parser.parse_args()
    
    # Seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[DEVICE] Using {device}")
    
    # Load dataset
    full_dataset = PolicyDataset(args.dataset, normalize=True)
    
    # Split
    total_size = len(full_dataset)
    test_size = int(total_size * args.test_split)
    val_size = int(total_size * args.val_split)
    train_size = total_size - test_size - val_size
    
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(args.seed)
    )
    
    print(f"[SPLIT] Train: {train_size}, Val: {val_size}, Test: {test_size}")
    
    # DataLoaders
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)
    
    # Model
    model = StudentPolicy(
        input_dim=9,
        hidden_dims=args.hidden_dims,
        output_dim=2,
        use_batchnorm=args.use_batchnorm,
        dropout=args.dropout
    ).to(device)
    
    # Evaluation only
    if args.eval_only:
        if args.model is None:
            raise ValueError("--model required for --eval_only")
        
        print(f"[EVAL] Loading model from {args.model}")
        checkpoint = torch.load(args.model, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        
        evaluate_model(model, test_loader, device, full_dataset)
        return
    
    # Train
    trainer = Trainer(model, train_loader, val_loader, device, args)
    history = trainer.train()
    
    # Plot
    plot_training_curves(history, os.path.join(args.save_dir, 'training_curves.png'))
    
    # Save stats
    stats = full_dataset.get_normalization_stats()
    stats_path = os.path.join(args.save_dir, 'normalization_stats.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"[SAVE] Normalization stats saved to {stats_path}")
    
    # Final evaluation
    print(f"\n[EVAL] Loading best model for final evaluation...")
    best_model_path = os.path.join(args.save_dir, 'policy_best.pth')
    checkpoint = torch.load(best_model_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    evaluate_model(model, test_loader, device, full_dataset)
    
    print(f"\n✅ Training completed!")
    print(f"   Best model: {best_model_path}")
    print(f"   Stats: {stats_path}")
    print(f"   Plots: {os.path.join(args.save_dir, 'training_curves.png')}")


if __name__ == '__main__':
    main()