"""
EEGNetv4 疲劳二分类 Baseline（基于 raw EEG）

- 输入：直接使用预处理后的 EEG epoch 波形，形状 [N, C, T]
- 标签：ses-1 = NS (正常睡眠) = 0, ses-2 = SD (睡眠剥夺) = 1
- 划分：按受试者做一次性 Train / Val / Test（cross-subject），
        每个 subject 只出现在一个集合中。

说明：
- 数据来源和通道顺序与 `extract_features_for_vit.py` 保持一致：
  - `DATA_PATH` 指向预处理后的 .set 文件目录；
  - `eeg_structure_summary.csv` 提供 file_name / subject / status 等信息；
  - `channel_grid_mapping.csv` 提供统一的通道顺序。
"""

import os
import json
from typing import Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score
from braindecode.models import EEGNetv4
import mne


# ================= 配置 =================

# 项目根目录（baseline 的上一级），EEG 数据在根目录，映射/信息表与特征在 feature_extracting
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(_ROOT, 'EEG数据', 'EEG数据', '预处理后的数据')
MAPPING_CSV = os.path.join(_ROOT, 'feature_extracting', 'channel_grid_mapping.csv')
INFO_CSV = os.path.join(_ROOT, 'feature_extracting', 'eeg_structure_summary.csv')
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

# 统一的 raw EEG 窗口长度（Samples），例如 4 秒 * 500 Hz = 2000
RAW_TARGET_SAMPLES = 2000


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ================= 数据加载 =================

def load_raw_ns_sd_epochs(
    data_path: str,
    info_csv: str,
    mapping_csv: str
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    从 EEG .set 文件中加载 NS / SD 的 raw epoch 数据。

    返回:
        X: (N, C, T) float32
        y: (N,) int64, 0=NS(ses-1), 1=SD(ses-2)
        subjects: (N,) object/str，每个样本对应的 subject
    """
    print("\n[数据加载] 读取通道映射和文件信息 ...")
    mapping_df = pd.read_csv(mapping_csv)
    channel_names = mapping_df['channel_name'].tolist()

    info_df = pd.read_csv(info_csv)
    # 只保留 status == 'ok' 的文件
    info_df = info_df[info_df['status'] == 'ok'].reset_index(drop=True)

    # 只使用 ses-1 (NS) 和 ses-2 (SD)
    mask_ns = info_df['file_name'].str.contains('ses-1')
    mask_sd = info_df['file_name'].str.contains('ses-2')
    info_df = info_df[mask_ns | mask_sd].reset_index(drop=True)

    X_list = []
    y_list = []
    subjects_list = []

    n_files = len(info_df)
    print(f"  ✓ 有效文件数: {n_files}")

    for idx, row in info_df.iterrows():
        file_name = row['file_name']
        subject = row['subject']

        if 'ses-1' in file_name:
            label = 0  # NS
        elif 'ses-2' in file_name:
            label = 1  # SD
        else:
            # 理论上不会进入这里，因为上面已经筛过
            continue

        file_path = os.path.join(data_path, file_name)
        print(f"  [{idx+1}/{n_files}] 读取 {file_name} (subject={subject}, label={label})")

        try:
            epochs = mne.read_epochs_eeglab(file_path, verbose='ERROR')

            # 确保通道顺序与 mapping 一致
            epoch_ch_names = epochs.ch_names
            if epoch_ch_names != channel_names:
                epochs = epochs.reorder_channels(channel_names)

            data = epochs.get_data().astype(np.float32)  # (n_epochs, C, T_i)
            n_epochs, n_chans, n_times = data.shape

            # 统一时间长度到 RAW_TARGET_SAMPLES=2000
            if n_times > RAW_TARGET_SAMPLES:
                # 直接截取前 RAW_TARGET_SAMPLES 个采样点
                data = data[:, :, :RAW_TARGET_SAMPLES]
                n_times = RAW_TARGET_SAMPLES
            elif n_times < RAW_TARGET_SAMPLES:
                # 样本长度不足 2000，当前先跳过这些文件，避免后续拼接失败
                print(
                    f"    ⚠ 跳过 {file_name}：epoch 长度 {n_times} < RAW_TARGET_SAMPLES={RAW_TARGET_SAMPLES}"
                )
                continue

            X_list.append(data)
            y_list.append(np.full(n_epochs, label, dtype=np.int64))
            subjects_list.append(np.full(n_epochs, subject, dtype=object))

        except Exception as e:
            print(f"    ⚠ 读取 {file_name} 时出错，跳过此文件: {e}")
            continue

    if not X_list:
        raise RuntimeError("未能从任何文件中成功读取 epoch 数据，请检查路径和文件状态。")

    X = np.concatenate(X_list, axis=0)          # (N, C, T)
    y = np.concatenate(y_list, axis=0)          # (N,)
    subjects = np.concatenate(subjects_list, axis=0)  # (N,)

    print(f"\n[数据加载完成] 总样本数: {X.shape[0]}, 形状: {X.shape}")
    print(f"  NS(0): {(y == 0).sum()}, SD(1): {(y == 1).sum()}")
    print(f"  受试者数: {len(np.unique(subjects))}")

    return X, y, subjects


def split_by_subject(subjects: np.ndarray,
                     y: np.ndarray,
                     train_ratio: float,
                     val_ratio: float,
                     test_ratio: float,
                     seed: int):
    """
    按受试者划分：每个 subject 只出现在 train / val / test 之一。
    """
    unique_subjects = np.unique(subjects)
    n_sub = len(unique_subjects)
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_subjects)

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


def normalize_by_train(X_train: np.ndarray,
                       X_val: np.ndarray,
                       X_test: np.ndarray):
    """
    用训练集均值/标准差对 train/val/test 做 Z-score（val/test 用 train 的统计量）。
    """
    mean = X_train.mean()
    std = X_train.std()
    if std < 1e-8:
        std = 1.0
    X_train = (X_train - mean) / std
    X_val = (X_val - mean) / std
    X_test = (X_test - mean) / std
    return X_train, X_val, X_test, mean, std


# ================= Dataset =================

class RawEEGDataset(Dataset):
    """raw EEG 数据集: X 形状 [N, C, T]，y 为 0/1。"""

    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.from_numpy(X)
        self.y = torch.from_numpy(y).long()  # CrossEntropyLoss 期望 Long 类型标签

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


# ================= 训练与评估 =================

def train_epoch(model: nn.Module,
                loader: DataLoader,
                criterion: nn.Module,
                optimizer: torch.optim.Optimizer,
                device: torch.device) -> float:
    model.train()
    total_loss = 0.0
    for X_b, y_b in loader:
        X_b, y_b = X_b.to(device), y_b.to(device)
        optimizer.zero_grad()
        out = model(X_b)              # 期望形状 [B, n_classes]
        loss = criterion(out, y_b)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def evaluate(model: nn.Module,
             loader: DataLoader,
             device: torch.device):
    model.eval()
    preds, labels = [], []
    with torch.no_grad():
        for X_b, y_b in loader:
            X_b = X_b.to(device)
            out = model(X_b)          # [B, n_classes]
            pred = out.argmax(dim=1).cpu().numpy()
            preds.append(pred)
            labels.append(y_b.numpy().astype(np.int64))
    preds = np.concatenate(preds)
    labels = np.concatenate(labels)
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, zero_division=0)
    return acc, f1


# ================= 主函数 =================

def main():
    set_seed(SEED)
    print("=" * 60)
    print("EEGNetv4 疲劳二分类 Baseline（raw EEG, NS=0, SD=1）")
    print("=" * 60)
    print(f"设备: {DEVICE}")

    # 1. 加载 raw EEG 数据
    X, y, subjects = load_raw_ns_sd_epochs(DATA_PATH, INFO_CSV, MAPPING_CSV)
    n_trials, n_chans, n_times = X.shape
    print(f"\n数据概览: trials={n_trials}, chans={n_chans}, samples={n_times}")

    # 2. 按受试者划分 train / val / test
    print("\n[划分数据] 按受试者划分 train/val/test ...")
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
    print(f"  Train: {len(train_idx)} 样本, Val: {len(val_idx)} 样本, Test: {len(test_idx)} 样本")

    # 3. 归一化（用 train 的 mean/std）
    print("\n[归一化] 使用 train 统计量对 train/val/test 做 z-score ...")
    X_train, X_val, X_test, norm_mean, norm_std = normalize_by_train(X_train, X_val, X_test)
    print(f"  归一化: mean={norm_mean:.4f}, std={norm_std:.4f}")

    # 4. DataLoader
    train_ds = RawEEGDataset(X_train, y_train)
    val_ds = RawEEGDataset(X_val, y_val)
    test_ds = RawEEGDataset(X_test, y_test)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    # 5. 构建 EEGNetv4 模型
    print("\n[模型] 构建 EEGNetv4 ...")
    model = EEGNetv4(
        n_chans=n_chans,          # 通道数
        n_outputs=2,              # 二分类：NS / SD
        n_times=n_times,          # 时间点数（前面统一成 2000）
        final_conv_length='auto'
    ).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    # 6. 训练
    print("\n[训练] 开始训练 EEGNetv4 ...")
    best_val_f1 = 0.0
    best_epoch = 0
    best_state = None

    for epoch in range(EPOCHS):
        loss = train_epoch(model, train_loader, criterion, optimizer, DEVICE)
        val_acc, val_f1 = evaluate(model, val_loader, DEVICE)
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1}/{EPOCHS}  loss={loss:.4f}  "
                  f"val_acc={val_acc:.4f}  val_f1={val_f1:.4f}")

    # 7. 使用最佳模型在测试集上评估
    print("\n[测试] 使用最佳模型在测试集上评估 ...")
    if best_state is not None:
        model.load_state_dict(best_state)
    test_acc, test_f1 = evaluate(model, test_loader, DEVICE)
    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Test F1-Score: {test_f1:.4f}")

    # 8. 保存结果
    result = {
        'seed': SEED,
        'train_ratio': TRAIN_RATIO,
        'val_ratio': VAL_RATIO,
        'test_ratio': TEST_RATIO,
        'n_train': int(len(train_idx)),
        'n_val': int(len(val_idx)),
        'n_test': int(len(test_idx)),
        'best_epoch': int(best_epoch + 1),
        'test_accuracy': float(test_acc),
        'test_f1': float(test_f1),
        'model': 'EEGNetv4_raw',
        'n_trials': int(n_trials),
        'n_chans': int(n_chans),
        'n_times': int(n_times),
    }
    os.makedirs(FEATURE_DIR, exist_ok=True)
    out_path = os.path.join(FEATURE_DIR, 'eegnet_raw_fatigue_result.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存到: {out_path}")
    print("=" * 60)


if __name__ == '__main__':
    main()
