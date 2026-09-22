"""
LSTM 疲劳二分类验证脚本
- 标签: ses-1 = NS (正常睡眠) = 0, ses-2 = SD (睡眠剥夺) = 1
- 按受试者划分 train/val/test，避免数据泄露
- 输入: [Batch, 16, 5, 14, 14] -> 展平为 [Batch, 16, 980] 送入 LSTM
"""

import os
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score
from tqdm import tqdm

# ================= 配置 =================
# 项目根目录（baseline 的上一级），特征与结果在 feature_extracting/feature_data
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_DIR = os.path.join(_ROOT, 'feature_extracting', 'feature_data')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
SEED = 42
# 按受试者划分比例（保证同一人只出现在一个集合）
TRAIN_RATIO = 0.7
VAL_RATIO = 0.15
TEST_RATIO = 0.15
# 训练参数
BATCH_SIZE = 64
EPOCHS = 50
LR = 1e-3
# LSTM
INPUT_SIZE = 5 * 14 * 14  # 980
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2


def set_seed(seed):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ================= 数据加载与划分 =================
def load_ns_sd_features(feature_dir):
    """
    加载 NS 和 SD 特征及元数据。
    标签: NS (ses-1) = 0, SD (ses-2) = 1。
    返回: X (np.ndarray), y (np.ndarray), subjects (np.ndarray，每个样本的 subject）
    """
    # NS
    X_ns = np.load(os.path.join(feature_dir, 'eeg_features_vit_NS.npy')).astype(np.float32)
    meta_ns = pd.read_csv(os.path.join(feature_dir, 'eeg_features_vit_NS_metadata.csv'))
    n_ns = len(X_ns)
    # SD
    X_sd = np.load(os.path.join(feature_dir, 'eeg_features_vit_SD.npy')).astype(np.float32)
    meta_sd = pd.read_csv(os.path.join(feature_dir, 'eeg_features_vit_SD_metadata.csv'))
    n_sd = len(X_sd)

    X = np.concatenate([X_ns, X_sd], axis=0)
    y = np.concatenate([np.zeros(n_ns, dtype=np.int64), np.ones(n_sd, dtype=np.int64)], axis=0)
    subjects = np.concatenate([meta_ns['subject'].values, meta_sd['subject'].values], axis=0)

    return X, y, subjects


def split_by_subject(subjects, y, train_ratio, val_ratio, test_ratio, seed):
    """
    按受试者划分：每个 subject 只出现在 train / val / test 之一。
    """
    unique_subjects = np.unique(subjects)
    n_sub = len(unique_subjects)
    np.random.seed(seed)
    np.random.shuffle(unique_subjects)

    n_train = int(n_sub * train_ratio)
    n_val = int(n_sub * val_ratio)
    n_test = n_sub - n_train - n_val
    if n_test < 0:
        n_test = 0
        n_val = n_sub - n_train

    train_subs = set(unique_subjects[:n_train])
    val_subs = set(unique_subjects[n_train:n_train + n_val])
    test_subs = set(unique_subjects[n_train + n_val:])

    train_idx = np.array([i for i in range(len(subjects)) if subjects[i] in train_subs])
    val_idx = np.array([i for i in range(len(subjects)) if subjects[i] in val_subs])
    test_idx = np.array([i for i in range(len(subjects)) if subjects[i] in test_subs])

    return train_idx, val_idx, test_idx


def normalize_by_train(X_train, X_val, X_test):
    """用训练集均值/标准差对 train/val/test 做 Z-score（val/test 用 train 的统计量）。"""
    mean = X_train.mean()
    std = X_train.std()
    if std < 1e-8:
        std = 1.0
    X_train = (X_train - mean) / std
    X_val = (X_val - mean) / std
    X_test = (X_test - mean) / std
    return X_train, X_val, X_test, mean, std


# ================= Dataset =================
class FatigueDataset(Dataset):
    """特征 [N, 16, 5, 14, 14]，标签 0/1。"""

    def __init__(self, X, y):
        self.X = torch.from_numpy(X)
        self.y = torch.from_numpy(y).float().unsqueeze(1)  # [N, 1] for BCE

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


# ================= Model =================
class FatigueLSTM(nn.Module):
    """
    输入 x: [Batch, 16, 5, 14, 14]
    展平为 [Batch, 16, 980] 送入 LSTM，取最后时间步接全连接二分类。
    """

    def __init__(self, input_size=980, hidden_size=64, num_layers=2, dropout=0.2):
        super(FatigueLSTM, self).__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        # x: [B, 16, 5, 14, 14]
        B = x.size(0)
        x = x.view(B, 16, -1)  # [B, 16, 980]
        out, _ = self.lstm(x)
        last_step = out[:, -1, :]  # [B, hidden_size]
        return self.fc(last_step)  # [B, 1]


# ================= 训练与评估 =================
def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    for X_b, y_b in loader:
        X_b, y_b = X_b.to(device), y_b.to(device)
        optimizer.zero_grad()
        pred = model(X_b)
        loss = criterion(pred, y_b)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def evaluate(model, loader, device):
    model.eval()
    preds, labels = [], []
    with torch.no_grad():
        for X_b, y_b in loader:
            X_b = X_b.to(device)
            out = model(X_b)
            preds.append((out.cpu().numpy() >= 0.5).astype(np.int64).ravel())
            labels.append(y_b.numpy().ravel().astype(np.int64))
    preds = np.concatenate(preds)
    labels = np.concatenate(labels)
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, zero_division=0)
    return acc, f1


def main():
    set_seed(SEED)
    print("=" * 60)
    print("LSTM 疲劳二分类验证（NS=0, SD=1）")
    print("=" * 60)
    print(f"设备: {DEVICE}")

    # 1. 加载数据
    print("\n1. 加载 NS/SD 特征...")
    X, y, subjects = load_ns_sd_features(FEATURE_DIR)
    print(f"   总样本: {len(X)}, 形状: {X.shape}")
    print(f"   NS(0): {(y == 0).sum()}, SD(1): {(y == 1).sum()}")
    print(f"   受试者数: {len(np.unique(subjects))}")

    # 2. 按受试者划分
    print("\n2. 按受试者划分 train/val/test...")
    train_idx, val_idx, test_idx = split_by_subject(
        subjects, y, TRAIN_RATIO, VAL_RATIO, TEST_RATIO, SEED
    )
    # 安全检查：确保三个集合的受试者互不重叠，避免 data leakage
    train_subs = set(subjects[train_idx])
    val_subs = set(subjects[val_idx])
    test_subs = set(subjects[test_idx])
    assert train_subs.isdisjoint(val_subs)
    assert train_subs.isdisjoint(test_subs)
    assert val_subs.isdisjoint(test_subs)
    X_train, X_val, X_test = X[train_idx], X[val_idx], X[test_idx]
    y_train, y_val, y_test = y[train_idx], y[val_idx], y[test_idx]
    print(f"   Train: {len(train_idx)} 样本, Val: {len(val_idx)} 样本, Test: {len(test_idx)} 样本")

    # 3. 归一化（用 train 的 mean/std）
    X_train, X_val, X_test, norm_mean, norm_std = normalize_by_train(X_train, X_val, X_test)
    print(f"   归一化: mean={norm_mean:.4f}, std={norm_std:.4f}")

    # 4. DataLoader
    train_ds = FatigueDataset(X_train, y_train)
    val_ds = FatigueDataset(X_val, y_val)
    test_ds = FatigueDataset(X_test, y_test)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    # 5. 模型与优化
    model = FatigueLSTM(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT
    ).to(DEVICE)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    # 6. 训练
    print("\n3. 训练...")
    best_val_f1 = 0.0
    best_epoch = 0
    for epoch in range(EPOCHS):
        loss = train_epoch(model, train_loader, criterion, optimizer, DEVICE)
        val_acc, val_f1 = evaluate(model, val_loader, DEVICE)
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = epoch
            torch.save(model.state_dict(), os.path.join(FEATURE_DIR, 'lstm_fatigue_best.pt'))
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"   Epoch {epoch+1}/{EPOCHS}  loss={loss:.4f}  val_acc={val_acc:.4f}  val_f1={val_f1:.4f}")

    # 7. 加载最佳模型并在测试集上评估
    print("\n4. 测试集评估（最佳模型）...")
    model.load_state_dict(torch.load(os.path.join(FEATURE_DIR, 'lstm_fatigue_best.pt'), map_location=DEVICE))
    test_acc, test_f1 = evaluate(model, test_loader, DEVICE)
    print(f"   Test Accuracy: {test_acc:.4f}")
    print(f"   Test F1-Score: {test_f1:.4f}")

    # 保存本次运行配置与结果（便于复现）
    result = {
        'seed': SEED,
        'train_ratio': TRAIN_RATIO,
        'val_ratio': VAL_RATIO,
        'test_ratio': TEST_RATIO,
        'n_train': len(train_idx),
        'n_val': len(val_idx),
        'n_test': len(test_idx),
        'best_epoch': best_epoch + 1,
        'test_accuracy': float(test_acc),
        'test_f1': float(test_f1),
    }
    with open(os.path.join(FEATURE_DIR, 'lstm_fatigue_result.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存到: {FEATURE_DIR}/lstm_fatigue_result.json")
    print("=" * 60)


if __name__ == '__main__':
    main()
