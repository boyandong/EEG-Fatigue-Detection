"""EEG binary classification: normal sleep vs sleep deprivation.

与项目约定对齐：
- 特征来自 feature_extracting/feature_data（eeg_features_vit_NS.npy / eeg_features_vit_SD.npy）
- 仅支持按受试者划分（--test_subject_id 必填），避免同一人同时出现在 train/test 造成数据泄露
- metadata list CSV 默认在 model/ 目录，npy 在 data_dir（默认 feature_extracting/feature_data）
"""

import argparse
import csv
import json
import os
import random
import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm

from models.eeg_model import create_eeg_model

warnings.filterwarnings("ignore")

# 路径：与 feature_extracting 输出对齐
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_DATA_DIR = os.path.join(_ROOT, "feature_extracting", "feature_data")
DEFAULT_METADATA_DIR = _SCRIPT_DIR  # model/ 目录，存放 metadata list CSV

# 与 feature_extracting 输出的 npy 文件名一致
NPY_NORMAL = "eeg_features_vit_NS.npy"
NPY_DEPRIV = "eeg_features_vit_SD.npy"
# CSV 列: start_row, end_row, subject_id, row_count（按 subject 聚合的行范围）
DEFAULT_CSV_NS = "eeg_features_vit_NS_metadata_list.csv"
DEFAULT_CSV_SD = "eeg_features_vit_SD_metadata_list.csv"

if getattr(torch, "amp", None) is not None:
    _autocast = lambda enabled: torch.amp.autocast("cuda", enabled=enabled)
    _GradScaler = lambda: torch.amp.GradScaler("cuda")
else:
    _autocast = lambda enabled: torch.cuda.amp.autocast(enabled=enabled)
    _GradScaler = lambda: torch.cuda.amp.GradScaler()


class EEGDataset(Dataset):
    """EEG feature dataset: 0=normal sleep, 1=sleep deprivation."""

    def __init__(self, features, labels):
        self.features = torch.FloatTensor(features)
        self.labels = torch.LongTensor(labels)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]


def _read_subject_csv(csv_path):
    """Read CSV with columns start_row,end_row,subject_id,row_count. Return list of (start_row, end_row, subject_id)."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for rec in r:
            rows.append((
                int(rec["start_row"]),
                int(rec["end_row"]),
                rec["subject_id"].strip(),
            ))
    return rows


def _get_shape_from_npy(npy_path):
    """Return shape of npy without loading into memory (mmap)."""
    arr = np.load(npy_path, mmap_mode="r")
    return arr.shape


def build_subject_split_ranges(data_dir, metadata_dir, csv_ns_name, csv_sd_name, test_subject_id, val_ratio=0.1, val_seed=42):
    """
    Build train/val/test ranges from subject CSVs. One subject = test; rest = train (+ val from train).
    data_dir: 存放 npy 的目录；metadata_dir: 存放 list CSV 的目录。
    Returns: train_ranges, val_ranges, test_ranges, config.
    Each ranges is list of (npy_basename, label, start_row, end_row).
    """
    csv_ns = os.path.join(metadata_dir, csv_ns_name)
    csv_sd = os.path.join(metadata_dir, csv_sd_name)
    if not os.path.isfile(csv_ns) or not os.path.isfile(csv_sd):
        raise FileNotFoundError(f"Metadata CSVs not found: {csv_ns}, {csv_sd}")
    ns_rows = _read_subject_csv(csv_ns)
    sd_rows = _read_subject_csv(csv_sd)
    # Align by subject_id (assume same subject set in both)
    ns_by_subj = {r[2]: (r[0], r[1]) for r in ns_rows}
    sd_by_subj = {r[2]: (r[0], r[1]) for r in sd_rows}
    all_subjects = sorted(set(ns_by_subj) | set(sd_by_subj))
    if test_subject_id not in all_subjects:
        raise ValueError(f"test_subject_id '{test_subject_id}' not in CSV subject_id. Available: {all_subjects}")
    train_subjects = [s for s in all_subjects if s != test_subject_id]
    # Build segments: (npy_basename, label, start_row, end_row)
    def segs_for_subjects(subject_list):
        segs = []
        for sid in subject_list:
            if sid in ns_by_subj:
                s, e = ns_by_subj[sid]
                segs.append((NPY_NORMAL, 0, s, e))
            if sid in sd_by_subj:
                s, e = sd_by_subj[sid]
                segs.append((NPY_DEPRIV, 1, s, e))
        return segs
    test_ranges = segs_for_subjects([test_subject_id])
    train_val_segs = segs_for_subjects(train_subjects)
    # Split train_val_segs into train (1-val_ratio) and val (val_ratio)
    rng = random.Random(val_seed)
    idx = list(range(len(train_val_segs)))
    rng.shuffle(idx)
    n_val = max(1, int(len(idx) * val_ratio))
    val_idx = set(idx[:n_val])
    train_ranges = [train_val_segs[i] for i in idx[n_val:]]
    val_ranges = [train_val_segs[i] for i in idx[:n_val]]
    # Config from first npy (shape only, no full load)
    npy_path = os.path.join(data_dir, NPY_NORMAL)
    if not os.path.isfile(npy_path):
        npy_path = os.path.join(data_dir, NPY_DEPRIV)
    shape = _get_shape_from_npy(npy_path)
    # shape (N, T, B, H, W) or (N, B, T, H, W)
    if len(shape) == 5:
        n_t, n_b = shape[1], shape[2]
        if n_t == 5 and n_b == 16:
            n_t, n_b = 16, 5
        h, w = int(shape[3]), int(shape[4])
    else:
        n_t, n_b, h, w = 16, 5, 14, 14
    config = {
        "n_time_steps": int(n_t),
        "n_bands": int(n_b),
        "grid_size": int(h),
        "n_samples": None,
        "class_names": ["正常睡眠", "睡眠剥夺"],
    }
    return train_ranges, val_ranges, test_ranges, config


class EEGDatasetFromRanges(Dataset):
    """EEG dataset that reads by row ranges from npy (mmap), no full load. Each item is (feature, label)."""

    def __init__(self, ranges, data_dir, norm_config=None):
        # ranges: list of (npy_basename, label, start_row, end_row); end_row inclusive
        self.data_dir = data_dir
        self.norm_config = norm_config
        self._ranges = []
        self._cumlen = [0]
        for npy_name, label, start, end in ranges:
            n = end - start + 1
            self._ranges.append((npy_name, label, start, end))
            self._cumlen.append(self._cumlen[-1] + n)
        self._length = self._cumlen[-1]

    def __len__(self):
        return self._length

    def _resolve_idx(self, idx):
        # Which segment and local offset
        for i in range(len(self._cumlen) - 1):
            if idx < self._cumlen[i + 1]:
                return i, idx - self._cumlen[i]
        return len(self._ranges) - 1, idx - self._cumlen[-2]

    def __getitem__(self, idx):
        seg_i, offset = self._resolve_idx(idx)
        npy_name, label, start, end = self._ranges[seg_i]
        path = os.path.join(self.data_dir, npy_name)
        arr = np.load(path, mmap_mode="r")
        row = arr[start + offset].copy()
        if row.ndim == 5:
            pass
        elif row.ndim == 4:
            # (T, B, H, W) -> maybe (5,16,H,W) -> (16,5,H,W)
            if row.shape[0] == 5 and row.shape[1] == 16:
                row = np.transpose(row, (1, 0, 2, 3))
        x = torch.from_numpy(row.astype(np.float32))
        if self.norm_config is not None:
            mean = np.array(self.norm_config["mean"], dtype=np.float32)
            scale = np.array(self.norm_config["scale"], dtype=np.float32)
            flat = x.numpy().reshape(-1)
            flat = (flat - mean) / np.maximum(scale, 1e-8)
            x = torch.from_numpy(flat.reshape(x.shape))
        return x, torch.tensor(label, dtype=torch.long)


def load_data(data_dir="data"):
    """Load features and labels; return features [N,16,5,H,W], labels, config. 仅作备用，main 已强制按 subject 划分."""
    print("Loading data...")
    normal_path = os.path.join(data_dir, NPY_NORMAL)
    normal_features = np.load(normal_path)
    normal_labels = np.zeros(len(normal_features), dtype=np.int64)
    print(f"正常睡眠数据形状: {normal_features.shape}")

    depriv_path = os.path.join(data_dir, NPY_DEPRIV)
    depriv_features = np.load(depriv_path)
    depriv_labels = np.ones(len(depriv_features), dtype=np.int64)
    print(f"Sleep deprivation: {depriv_features.shape}")

    features = np.concatenate([normal_features, depriv_features], axis=0)
    labels = np.concatenate([normal_labels, depriv_labels], axis=0)
    print(f"Total: {features.shape}, labels 0: {np.sum(labels == 0)}, 1: {np.sum(labels == 1)}")

    *_, h, w = features.shape
    if features.ndim == 5:
        n_t, n_b = features.shape[1], features.shape[2]
        if n_t == 5 and n_b == 16:
            print("[Note] Transposing (N,5,16,H,W) -> (N,16,5,H,W).")
            features = np.transpose(features, (0, 2, 1, 3, 4))
            n_t, n_b = 16, 5
        else:
            n_t, n_b = features.shape[1], features.shape[2]
    else:
        n_t, n_b = 16, 5
    config = {
        "n_time_steps": int(n_t),
        "n_bands": int(n_b),
        "grid_size": int(h),
        "n_samples": len(features),
        "class_names": ["正常睡眠", "睡眠剥夺"],
    }
    return features, labels, config




def split_data(features, labels, test_size=0.2, val_size=0.1, random_state=42):
    """Split into train/val/test with stratification."""
    X_temp, X_test, y_temp, y_test = train_test_split(
        features, labels, test_size=test_size, random_state=random_state, stratify=labels
    )
    val_size_adjusted = val_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=val_size_adjusted, random_state=random_state, stratify=y_temp
    )
    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    return X_train, X_val, X_test, y_train, y_val, y_test


def normalize_fit_transform(train_f, val_f, test_f):
    """在训练集上拟合 StandardScaler，对 train/val/test 做相同变换。"""
    N_train, *rest = train_f.shape
    flat_train = train_f.reshape(N_train, -1)
    scaler = StandardScaler()
    scaler.fit(flat_train)
    train_f = scaler.transform(flat_train).reshape(train_f.shape).astype(np.float32)
    N_val, N_test = val_f.shape[0], test_f.shape[0]
    val_f = scaler.transform(val_f.reshape(N_val, -1)).reshape(val_f.shape).astype(np.float32)
    test_f = scaler.transform(test_f.reshape(N_test, -1)).reshape(test_f.shape).astype(np.float32)
    norm_config = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "n_features": int(np.prod(rest)),
    }
    return train_f, val_f, test_f, norm_config


def normalize_fit_from_ranges_dataset(train_dataset, sample_cap=50000, seed=42):
    """Fit StandardScaler by sampling from a range-based train dataset (no full npy load)."""
    n = len(train_dataset)
    rng = random.Random(seed)
    size = min(n, sample_cap)
    indices = rng.sample(range(n), size)
    samples = []
    batch = 2000
    for i in range(0, len(indices), batch):
        chunk = [train_dataset[indices[j]][0].numpy() for j in range(i, min(i + batch, len(indices)))]
        samples.append(np.stack(chunk, axis=0))
    X = np.concatenate(samples, axis=0)
    X_flat = X.reshape(len(X), -1)
    scaler = StandardScaler()
    scaler.fit(X_flat)
    return {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "n_features": int(X_flat.shape[1]),
    }


def apply_normalize(features, norm_config):
    """Apply saved normalization config for inference."""
    mean = np.array(norm_config["mean"], dtype=np.float32)
    scale = np.array(norm_config["scale"], dtype=np.float32)
    n = features.shape[0]
    flat = features.reshape(n, -1)
    flat = (flat - mean) / np.maximum(scale, 1e-8)
    return flat.reshape(features.shape).astype(np.float32)


def train_epoch(model, dataloader, criterion, optimizer, device, scaler=None):
    """Train one epoch with optional AMP."""
    model.train()
    total_loss = 0.0
    preds_list = []
    labels_list = []
    use_amp = scaler is not None

    pbar = tqdm(dataloader, desc="Train")
    for batch_idx, (features, labels) in enumerate(pbar):
        features = features.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with _autocast(use_amp):
            outputs = model(features)
            loss = criterion(outputs, labels)
            preds = torch.argmax(outputs, dim=1)
        if use_amp:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()
        loss_item = loss.item()
        total_loss += loss_item
        preds_list.append(preds)
        labels_list.append(labels)
        avg_loss_so_far = total_loss / (batch_idx + 1)
        pbar.set_postfix({"loss": f"{loss_item:.4f}", "avg_loss": f"{avg_loss_so_far:.4f}"})

    avg_loss = total_loss / len(dataloader)
    all_preds = torch.cat(preds_list, dim=0).cpu().numpy()
    all_labels = torch.cat(labels_list, dim=0).cpu().numpy()
    accuracy = accuracy_score(all_labels, all_preds)
    return avg_loss, accuracy


def validate(model, dataloader, criterion, device, use_amp=False):
    """Validate; return loss, accuracy, precision, recall, f1, and positive-class probs."""
    model.eval()
    total_loss = 0.0
    preds_list = []
    labels_list = []
    probs_list = []

    pbar = tqdm(dataloader, desc="Val")
    with torch.no_grad():
        for batch_idx, (features, labels) in enumerate(pbar):
            features = features.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            with _autocast(use_amp):
                outputs = model(features)
                loss = criterion(outputs, labels)
                probs = torch.softmax(outputs, dim=1)
                preds = torch.argmax(outputs, dim=1)
                probs_list.append(probs[:, 1])
            loss_item = loss.item()
            total_loss += loss_item
            preds_list.append(preds)
            labels_list.append(labels)
            avg_loss_so_far = total_loss / (batch_idx + 1)
            pbar.set_postfix({"loss": f"{loss_item:.4f}", "avg_loss": f"{avg_loss_so_far:.4f}"})
    avg_loss = total_loss / len(dataloader)
    all_preds = torch.cat(preds_list, dim=0).cpu().numpy()
    all_labels = torch.cat(labels_list, dim=0).cpu().numpy()
    all_probs = torch.cat(probs_list, dim=0).cpu().numpy()
    accuracy = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds, average='binary', zero_division=0)
    recall = recall_score(all_labels, all_preds, average='binary', zero_division=0)
    f1 = f1_score(all_labels, all_preds, average='binary', zero_division=0)

    pred_0 = int((all_preds == 0).sum())
    pred_1 = int((all_preds == 1).sum())
    if abs(accuracy - 0.5) < 0.01 and (recall > 0.99 or recall < 0.01):
        print(f"\n[验证诊断] 预测全为同一类: 0={pred_0}, 1={pred_1}")
    return avg_loss, accuracy, precision, recall, f1, all_probs


def test(model, dataloader, criterion, device, use_amp=False):
    """Evaluate on test set."""
    return validate(model, dataloader, criterion, device, use_amp=use_amp)


def plot_training_history(history, save_path="training_history.png"):
    """Plot training/validation loss and accuracy."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(history["train_loss"], label="Train Loss")
    axes[0].plot(history["val_loss"], label="Val Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_title("Training and Validation Loss")
    axes[0].legend()
    axes[0].grid(True)
    axes[1].plot(history["train_acc"], label="Train Acc")
    axes[1].plot(history["val_acc"], label="Val Acc")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_title("Training and Validation Accuracy")
    axes[1].legend()
    axes[1].grid(True)
    plt.tight_layout()
    plt.savefig(save_path)
    print(f"Saved: {save_path}")


def main():
    parser = argparse.ArgumentParser(description="EEG training script (subject-wise split only, no data leakage)")
    parser.add_argument("--data_dir", type=str, default=DEFAULT_DATA_DIR,
                        help="Directory with eeg_features_vit_NS.npy and eeg_features_vit_SD.npy (default: feature_extracting/feature_data)")
    parser.add_argument("--test_subject_id", type=str, default=None, required=True,
                        help="Subject ID held out as test set (e.g. 01). Required for subject-wise split; for LOO, run in a loop.")
    parser.add_argument("--metadata_dir", type=str, default=DEFAULT_METADATA_DIR,
                        help="Directory containing metadata list CSVs (default: model/)")
    parser.add_argument("--metadata_csv_ns", type=str, default=DEFAULT_CSV_NS,
                        help="CSV for normal sleep: start_row,end_row,subject_id,row_count")
    parser.add_argument("--metadata_csv_sd", type=str, default=DEFAULT_CSV_SD,
                        help="CSV for sleep deprivation: start_row,end_row,subject_id,row_count")
    parser.add_argument("--batch_size", type=int, default=96, help="Batch size")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--lr", type=float, default=0.003, help="Learning rate")
    parser.add_argument("--weight_decay", type=float, default=1e-5, help="Weight decay")
    parser.add_argument("--num_classes", type=int, default=2,
                        help="Num classes (2=CrossEntropy, 1=BCEWithLogits)")
    parser.add_argument("--save_dir", type=str, default=os.path.join(_SCRIPT_DIR, "checkpoints"),
                        help="Checkpoint directory (default: model/checkpoints)")
    parser.add_argument("--device", type=str,
                        default="cuda" if torch.cuda.is_available() else "cpu", help="Device")
    parser.add_argument("--val_size", type=float, default=0.1,
                        help="Fraction of train subjects used for validation (when using --test_subject_id)")
    parser.add_argument("--num_workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--amp", action="store_true", help="Mixed precision (AMP)")
    parser.add_argument("--compile", action="store_true", help="torch.compile (PyTorch 2.0+)")
    parser.add_argument("--normalize", action="store_true",
                        help="StandardScaler on train, same transform for val/test")
    parser.add_argument("--fast", action="store_true",
                        help="Lightweight preset: fewer blocks, no TCN attention")
    parser.add_argument("--mscvit_blocks", type=int, default=None, help="MSCViT block count (default 4)")
    parser.add_argument("--mscvit_wt_levels", type=int, default=None, help="Wavelet levels (2=fast, 5=paper)")
    parser.add_argument("--tcn_no_attn", action="store_true", help="Disable TCN attention")
    parser.add_argument("--tcn_dilations", type=str, default=None,
                        help="TCN dilations, comma-separated e.g. 1,2")
    parser.add_argument("--first_frame_only", action="store_true",
                        help="Use only first time frame, skip TCN (for debugging)")
    args = parser.parse_args()

    # --fast preset
    if args.fast:
        if args.mscvit_blocks is None:
            args.mscvit_blocks = 2
        if args.mscvit_wt_levels is None:
            args.mscvit_wt_levels = 2
        args.tcn_no_attn = True
        if args.tcn_dilations is None:
            args.tcn_dilations = '1,2'
    if args.tcn_dilations is not None:
        args.tcn_dilations = [int(x) for x in args.tcn_dilations.split(",")]

    os.makedirs(args.save_dir, exist_ok=True)
    device = torch.device(args.device)
    print(f"Device: {device}")
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        use_amp = args.amp
    else:
        use_amp = False
    if use_amp:
        print("AMP enabled")

    norm_config = None
    # 仅支持按受试者划分，避免数据泄露（与 baseline 约定一致）
    print(f"Subject split: test_subject_id={args.test_subject_id}, reading CSV metadata...")
    train_ranges, val_ranges, test_ranges, config = build_subject_split_ranges(
        args.data_dir,
        args.metadata_dir,
        args.metadata_csv_ns,
        args.metadata_csv_sd,
        args.test_subject_id,
        val_ratio=args.val_size,
    )
    n_train = sum(r[3] - r[2] + 1 for r in train_ranges)
    n_val = sum(r[3] - r[2] + 1 for r in val_ranges)
    n_test = sum(r[3] - r[2] + 1 for r in test_ranges)
    print(f"Train: {n_train}, Val: {n_val}, Test: {n_test} (by subject ranges)")
    train_dataset = EEGDatasetFromRanges(train_ranges, args.data_dir, norm_config=None)
    val_dataset = EEGDatasetFromRanges(val_ranges, args.data_dir, norm_config=None)
    test_dataset = EEGDatasetFromRanges(test_ranges, args.data_dir, norm_config=None)
    if args.normalize:
        print("Fitting StandardScaler on train sample (range-based)...")
        norm_config = normalize_fit_from_ranges_dataset(train_dataset)
        config["normalize"] = norm_config
        train_dataset = EEGDatasetFromRanges(train_ranges, args.data_dir, norm_config=norm_config)
        val_dataset = EEGDatasetFromRanges(val_ranges, args.data_dir, norm_config=norm_config)
        test_dataset = EEGDatasetFromRanges(test_ranges, args.data_dir, norm_config=norm_config)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        persistent_workers=(args.num_workers > 0),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        persistent_workers=(args.num_workers > 0),
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        persistent_workers=(args.num_workers > 0),
    )

    model_kwargs = dict(
        num_de_features=config["n_time_steps"],
        num_freq_bands=config["n_bands"],
        spatial_h=config["grid_size"],
        spatial_w=config["grid_size"],
        num_classes=args.num_classes,
    )
    model_kwargs["mscvit_blocks"] = args.mscvit_blocks if args.mscvit_blocks is not None else 4
    if args.mscvit_wt_levels is not None:
        model_kwargs["mscvit_wt_levels"] = args.mscvit_wt_levels
    if args.tcn_no_attn:
        model_kwargs["tcn_use_attention"] = False
    if args.tcn_dilations is not None:
        model_kwargs["tcn_dilations"] = args.tcn_dilations
    model_kwargs["first_frame_only"] = False
    print(f"MSCViT blocks: {model_kwargs['mscvit_blocks']}")
    model = create_eeg_model(**model_kwargs).to(device)
    if args.first_frame_only:
        print("Mode: first frame only (skip TCN)")

    if args.compile and hasattr(torch, "compile"):
        print("Compiling model with torch.compile...")
        model = torch.compile(model, mode="reduce-overhead")

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nParameters: total={total_params:,}, trainable={trainable_params:,}")

    if args.num_classes == 1:
        criterion = nn.BCEWithLogitsLoss()
    else:
        criterion = nn.CrossEntropyLoss()
    
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5)
    scaler = _GradScaler() if use_amp else None

    history = {
        "train_loss": [], "train_acc": [],
        "val_loss": [], "val_acc": [], "val_f1": [],
    }
    best_val_f1 = 0.0
    patience_counter = 0
    patience = 10

    print("\nTraining...")
    print(f"Classes: {config['class_names']}")
    print("=" * 50)

    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device, scaler=scaler)
        val_loss, val_acc, val_precision, val_recall, val_f1, _ = validate(
            model, val_loader, criterion, device, use_amp=use_amp
        )
        scheduler.step(val_loss)

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)
        
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}, Val Precision: {val_precision:.4f}, Val Recall: {val_recall:.4f}, Val F1: {val_f1:.4f}")
        
        # 保存最佳模型
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            patience_counter = 0
            state_to_save = model.state_dict() if not hasattr(model, '_orig_mod') else model._orig_mod.state_dict()
            torch.save({
                'epoch': epoch,
                'model_state_dict': state_to_save,
                'optimizer_state_dict': optimizer.state_dict(),
                'val_f1': val_f1,
                'config': config  # 含 normalize 时含 norm_config，检测时用同一套预处理
            }, os.path.join(args.save_dir, 'best_model.pth'))
            print(f"保存最佳模型 (Val F1: {val_f1:.4f})")
        else:
            patience_counter += 1
        
        # 早停
        if patience_counter >= patience:
            print(f"验证指标在{patience}个epoch内未提升，提前停止训练")
            break
    
    # 绘制训练历史
    plot_training_history(history, os.path.join(args.save_dir, 'training_history.png'))
    
    # 加载最佳模型进行测试
    print("\n加载最佳模型进行测试...")
    checkpoint = torch.load(os.path.join(args.save_dir, 'best_model.pth'), weights_only=True)
    load_model = getattr(model, '_orig_mod', model)
    load_model.load_state_dict(checkpoint['model_state_dict'])
    # 测试
    test_loss, test_acc, test_precision, test_recall, test_f1, test_probs = test(model, test_loader, criterion, device, use_amp=use_amp)
    
    print("\n" + "="*50)
    print("测试集结果（二分类：正常睡眠 vs 睡眠剥夺）:")
    print(f"Loss: {test_loss:.4f}")
    print(f"Accuracy: {test_acc:.4f}")
    print(f"Precision: {test_precision:.4f}")
    print(f"Recall: {test_recall:.4f}")
    print(f"F1 Score: {test_f1:.4f}")
    print("=" * 50)

    results = {
        "test_loss": float(test_loss),
        "test_accuracy": float(test_acc),
        "test_precision": float(test_precision),
        "test_recall": float(test_recall),
        "test_f1": float(test_f1),
    }
    with open(os.path.join(args.save_dir, "test_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDone. Checkpoints and results: {args.save_dir}")


if __name__ == "__main__":
    main()
