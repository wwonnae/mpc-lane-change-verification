#!/usr/bin/env python3
"""
Simple training script for Student Policy
Train on combined dataset (original 60k + RETURN_TO_L2 6k)
"""

import argparse
import json
import os
import time
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

print("[INFO] Imports successful")

# =============================
# Model Architecture (same as final_hierarchical.py)
# =============================
class StudentPolicy(nn.Module):
    """Lightweight MLP for imitation learning"""
    def __init__(self, input_dim=9, hidden_dims=[256, 256, 128], 
                 output_dim=2, use_batchnorm=True, dropout=0.15):
        super(StudentPolicy, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            if use_batchnorm:
                layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, output_dim))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)

# =============================
# Dataset
# =============================
class PolicyDataset(Dataset):
    def __init__(self, features, labels):
        self.X = torch.from_numpy(features).float()
        self.Y = torch.from_numpy(labels).float()
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.Y[idx]

# =============================
# Training
# =============================
def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    
    for X_batch, Y_batch in loader:
        X_batch = X_batch.to(device)
        Y_batch = Y_batch.to(device)
        
        optimizer.zero_grad()
        Y_pred = model(X_batch)
        loss = criterion(Y_pred, Y_batch)
        loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        
        optimizer.step()
        total_loss += loss.item()
    
    return total_loss / len(loader)

def validate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for X_batch, Y_batch in loader:
            X_batch = X_batch.to(device)
            Y_batch = Y_batch.to(device)
            
            Y_pred = model(X_batch)
            loss = criterion(Y_pred, Y_batch)
            total_loss += loss.item()
            
            all_preds.append(Y_pred.cpu().numpy())
            all_targets.append(Y_batch.cpu().numpy())
    
    avg_loss = total_loss / len(loader)
    
    # Compute RMSE per output
    all_preds = np.concatenate(all_preds, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)
    
    rmse_delta = np.sqrt(np.mean((all_preds[:, 0] - all_targets[:, 0])**2))
    rmse_v = np.sqrt(np.mean((all_preds[:, 1] - all_targets[:, 1])**2))
    
    return avg_loss, rmse_delta, rmse_v

def main():
    parser = argparse.ArgumentParser(description='Train Student Policy')
    parser.add_argument('--data', type=str, required=True, help='Dataset directory')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch_size', type=int, default=256, help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-3, help='Learning rate')
    parser.add_argument('--val_split', type=float, default=0.15, help='Validation split')
    parser.add_argument('--output', type=str, default='models_v2', help='Output directory')
    parser.add_argument('--device', type=str, default='cpu', choices=['cpu', 'cuda'])
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"TRAINING STUDENT POLICY (v2)")
    print(f"{'='*60}")
    
    # Load data
    data_file = os.path.join(args.data, 'shard_00000.npz')
    print(f"\nLoading data from: {data_file}")
    
    data = np.load(data_file)
    features = data['features']
    labels = data['labels']
    
    print(f"  Features shape: {features.shape}")
    print(f"  Labels shape: {labels.shape}")
    print(f"  Total samples: {len(features)}")
    
    # Compute normalization stats
    print(f"\nComputing normalization statistics...")
    X_mean = features.mean(axis=0)
    X_std = features.std(axis=0)
    Y_mean = labels.mean(axis=0)
    Y_std = labels.std(axis=0)
    
    print(f"  X mean: {X_mean}")
    print(f"  X std: {X_std}")
    print(f"  Y mean: {Y_mean}")
    print(f"  Y std: {Y_std}")
    
    # Normalize
    features_norm = (features - X_mean) / (X_std + 1e-9)
    labels_norm = (labels - Y_mean) / (Y_std + 1e-9)
    
    # Train/val split
    n_samples = len(features)
    n_val = int(n_samples * args.val_split)
    n_train = n_samples - n_val
    
    indices = np.random.permutation(n_samples)
    train_idx = indices[:n_train]
    val_idx = indices[n_train:]
    
    print(f"\nDataset split:")
    print(f"  Training:   {n_train} samples ({100*(1-args.val_split):.1f}%)")
    print(f"  Validation: {n_val} samples ({100*args.val_split:.1f}%)")
    
    # Create datasets
    train_dataset = PolicyDataset(features_norm[train_idx], labels_norm[train_idx])
    val_dataset = PolicyDataset(features_norm[val_idx], labels_norm[val_idx])
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    
    # Model
    device = torch.device(args.device)
    model = StudentPolicy(
        input_dim=9,
        hidden_dims=[256, 256, 128],
        output_dim=2,
        use_batchnorm=True,
        dropout=0.15
    ).to(device)
    
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel architecture:")
    print(f"  Input dim: 9")
    print(f"  Hidden dims: [256, 256, 128]")
    print(f"  Output dim: 2")
    print(f"  Total parameters: {total_params:,}")
    
    # Optimizer & Loss
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )
    criterion = nn.MSELoss()
    
    # Training loop
    print(f"\n{'='*60}")
    print(f"TRAINING")
    print(f"{'='*60}")
    
    best_val_loss = float('inf')
    best_epoch = 0
    patience = 15
    patience_counter = 0
    
    history = {
        'train_loss': [],
        'val_loss': [],
        'val_rmse_delta': [],
        'val_rmse_v': []
    }
    
    start_time = time.time()
    
    for epoch in range(args.epochs):
        # Train
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        
        # Validate
        val_loss, rmse_delta, rmse_v = validate(model, val_loader, criterion, device)
        
        # Scheduler
        scheduler.step(val_loss)
        
        # History
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_rmse_delta'].append(rmse_delta)
        history['val_rmse_v'].append(rmse_v)
        
        # Print progress
        print(f"Epoch {epoch+1:3d}/{args.epochs}: "
              f"Train Loss={train_loss:.6f}, "
              f"Val Loss={val_loss:.6f}, "
              f"RMSE(Δ)={rmse_delta:.3f}°, "
              f"RMSE(v)={rmse_v:.4f}")
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch + 1
            patience_counter = 0
            
            # Save checkpoint
            os.makedirs(args.output, exist_ok=True)
            checkpoint = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'best_val_loss': best_val_loss,
                'history': history,
                'args': vars(args)
            }
            torch.save(checkpoint, os.path.join(args.output, 'policy_best.pth'))
        else:
            patience_counter += 1
        
        # Early stopping
        if patience_counter >= patience:
            print(f"\nEarly stopping at epoch {epoch+1}")
            print(f"Best validation loss: {best_val_loss:.6f} at epoch {best_epoch}")
            break
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"Best epoch: {best_epoch}")
    print(f"Best val loss: {best_val_loss:.6f}")
    print(f"Final RMSE(Δ): {history['val_rmse_delta'][best_epoch-1]:.3f}°")
    print(f"Final RMSE(v): {history['val_rmse_v'][best_epoch-1]:.4f} m/s")
    
    # Save normalization stats
    stats_file = os.path.join(args.output, 'normalization_stats.json')
    stats = {
        'X_mean': X_mean.tolist(),
        'X_std': X_std.tolist(),
        'Y_mean': Y_mean.tolist(),
        'Y_std': Y_std.tolist(),
        'feature_names': ['v', 'ey_line', 'front_gap', 'left_clear', 
                         'state_KEEP_L2', 'state_EVADE_L', 'state_KEEP_L1', 
                         'state_RETURN_TO_L2', 'state_SAFE_STOP'],
        'label_names': ['delta', 'v']
    }
    
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"SAVED FILES")
    print(f"{'='*60}")
    print(f"Model:  {os.path.join(args.output, 'policy_best.pth')}")
    print(f"Stats:  {stats_file}")
    
    print(f"\nNext steps:")
    print(f"  1. Copy models to deployment location:")
    print(f"     cp {args.output}/policy_best.pth models/")
    print(f"     cp {args.output}/normalization_stats.json models/")
    print(f"  2. Test with final_hierarchical.py:")
    print(f"     python final_hierarchical.py --test")

if __name__ == "__main__":
    main()
