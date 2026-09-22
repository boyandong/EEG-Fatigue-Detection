# EEG 疲劳识别（正常睡眠 vs 睡眠剥夺）

基于 EEG 的二分类项目：区分正常睡眠（NS, ses-1）与睡眠剥夺（SD, ses-2）。包含特征提取、Baseline（LSTM / EEGNet）与 ViT 风格模型（MSCViT+TCN）训练流程。

---

## 项目结构

```
codes/
├── EEG数据/                    # 预处理后的 EEG 数据（.set 等）
│   └── EEG数据/预处理后的数据/
├── feature_extracting/         # 特征提取
│   ├── extract_features_for_vit.py   # 生成 [N, 16, 5, 14, 14] 特征
│   ├── channel_grid_mapping.csv
│   ├── eeg_structure_summary.csv
│   └── feature_data/           # 输出：NS/SD 的 .npy、metadata、config
├── baseline/                   # LSTM、EEGNet 等 Baseline
│   ├── train_lstm_fatigue.py
│   ├── train_eegnet_raw.py
│   ├── run_lstm_baseline.py
│   └── run_eegnet_baseline.py
├── model/                      # MSCViT+TCN 模型训练
│   ├── train.py                # 需指定 --test_subject_id（按人划分）
│   ├── eeg_features_vit_*_metadata_list.csv
│   └── models/
└── README.md
```

---

## 数据说明

本仓库**不包含**原始 EEG 与特征 `.npy` 文件（体积较大，未上传）。使用前需自行准备：

- **EEG数据**：将预处理后的 EEG 文件（`.set` 等）放入 `EEG数据/EEG数据/预处理后的数据/`，并按 `ses-1`（NS）/ `ses-2`（SD）区分。
- **feature_data**：运行 `feature_extracting/extract_features_for_vit.py` 后会在 `feature_extracting/feature_data/` 下生成：
  - `eeg_features_vit_NS.npy` / `eeg_features_vit_SD.npy`（形状 `[N, 16, 5, 14, 14]`）
  - 以及 `*_metadata.csv`、`*_config.json`、`*_padding_mask.npy` 等（小文件会随仓库提交）。

即：先准备 EEG 数据 → 运行特征提取 → 再运行 baseline 或 model。

---

## 环境与依赖

- Python 3.8+
- 安装：`pip install -r requirements.txt`
- 主要依赖：`numpy`, `pandas`, `torch`, `mne`, `scipy`, `scikit-learn`, `tqdm`, `matplotlib`, `braindecode`
- model（MSCViT）：见 `model/` 内 `models/` 子模块（无额外 pip 包）

建议使用虚拟环境并安装上述包后再运行。

---

## 运行方式

**1. 特征提取**（在项目根目录）

```bash
# 先确保 EEG数据 与 channel_grid_mapping、eeg_structure_summary 就绪
# 分别运行 NS / SD（需在 extract_features_for_vit.py 中修改 CONDITION）
python feature_extracting/extract_features_for_vit.py
```

**2. Baseline**

```bash
# LSTM（基于 feature_data 中的特征）
python baseline/run_lstm_baseline.py

# EEGNet（基于 raw EEG）
python baseline/run_eegnet_baseline.py
```

**3. model（MSCViT+TCN）**

需按受试者划分，指定一个 subject 作为测试集，例如：

```bash
cd model
python train.py --test_subject_id 01
```

或从项目根目录：

```bash
python -m model.train --test_subject_id 01
```

做留一法（LOO）时，对每个 subject ID（01, 02, …）各跑一次并汇总结果。

---

## 注意事项

- 划分方式：Baseline 与 model 均按**受试者**划分 train/val/test，避免同一人数据同时出现在训练与测试中。
- 归一化：下游使用**训练集**统计量做标准化，不依赖测试集，避免数据泄露。
- 原始 EEG 与 `feature_data/*.npy` 已加入 `.gitignore`，不随仓库推送；小体积的 metadata、config、padding_mask 等会保留在仓库中。

---

## 上传到 GitHub

在项目根目录（`codes/`）下执行：

```bash
# 1. 初始化仓库（若尚未 git init）
git init

# 2. 添加所有文件（.gitignore 已排除 __pycache__、checkpoints 等）
git add .
git status   # 确认 EEG数据、feature_data 等是否按预期被加入或忽略

# 3. 首次提交
git commit -m "Initial commit: EEG fatigue classification (NS vs SD)"

# 4. 在 GitHub 网页新建仓库后，添加远程并推送（替换为你的仓库地址）
git remote add origin https://github.com/你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

（原始 EEG 与特征 npy 已通过 `.gitignore` 排除，仅代码与小配置文件会被推送。）
