## Baseline 实验说明

本文件夹用于组织 **跨受试者疲劳识别 Baseline 模型**，统一记录数据来源、评估协议和运行入口，方便后续和 ViT 等模型做公平对比。

### 1. 数据与特征

- **特征来源**：`feature_extracting/extract_features_for_vit.py` 生成的 ViT 输入特征  
  - 路径：`feature_extracting/feature_data/eeg_features_vit_NS.npy`、`feature_extracting/feature_data/eeg_features_vit_SD.npy`  
  - 形状：`[N, 16, 5, 14, 14]`
- **标签定义**（在 `train_lstm_fatigue.py` 中统一使用）：
  - `ses-1`（正常睡眠，NS） → `label = 0`
  - `ses-2`（睡眠剥夺，SD） → `label = 1`

### 2. 评价协议（当前版本）

目前代码默认使用 **按受试者划分的单次 Train/Val/Test 划分**：

- 先按 `subject` 去重，随机打乱；
- 按比例切分受试者集合：
  - `TRAIN_RATIO = 0.7`
  - `VAL_RATIO = 0.15`
  - `TEST_RATIO = 0.15`
- 每个受试者只出现在三个集合之一，避免同一人的 epoch 被同时用于训练和测试。

> 备注：后续如果需要完全对齐论文的 **LOO Cross‑Subject** 协议，可以在此文件夹下增加专门的 `*_loo.py` 入口，循环每个受试者做一次测试，并在 README 中单独说明。

### 3. 已配置的 Baseline 模型

本目录下包含两个 Baseline 脚本及对应入口，路径均相对项目根目录解析（可从任意 cwd 运行）。

#### 3.1 LSTM 疲劳二分类 Baseline

- 代码位置：`baseline/train_lstm_fatigue.py`
- Baseline 入口：`baseline/run_lstm_baseline.py`
- 模型结构：
  - 将输入 `[B, 16, 5, 14, 14]` 展平为空间维度，送入 LSTM：
    - 输入序列：`[B, 16, 980]`
    - `HIDDEN_SIZE = 64`
    - `NUM_LAYERS = 2`
    - `DROPOUT = 0.2`
  - 取最后时间步输出，接全连接 + Sigmoid 做二分类。
- 训练细节：
  - Batch size: `BATCH_SIZE = 64`
  - Epochs: `EPOCHS = 50`
  - Optimizer: `Adam (lr=1e-3)`
  - Loss: `BCELoss`
  - 归一化：使用 **train 集的 mean/std** 对 train/val/test 一起做 z-score。
- 输出结果：
  - 最佳模型参数：`feature_extracting/feature_data/lstm_fatigue_best.pt`
  - 单次 subject‑wise 划分的结果：`feature_extracting/feature_data/lstm_fatigue_result.json`

#### 3.2 EEGNetv4 疲劳二分类 Baseline（raw EEG）

- 代码位置：`baseline/train_eegnet_raw.py`
- Baseline 入口：`baseline/run_eegnet_baseline.py`
- 输入：预处理后的 EEG epoch 波形 `[N, C, T]`（T=2000），通道顺序与 `feature_extracting/channel_grid_mapping.csv` 一致。
- 模型：`braindecode.models.EEGNetv4`，按受试者划分 train/val/test。
- 输出结果：`feature_extracting/feature_data/eegnet_raw_fatigue_result.json`

### 4. 运行说明

在项目根目录下运行（任选其一）：

```bash
# LSTM Baseline（基于 ViT 特征）
python baseline/run_lstm_baseline.py

# EEGNet Baseline（基于 raw EEG）
python baseline/run_eegnet_baseline.py
```

两套入口均使用 **subject‑wise Train/Val/Test 划分**，结果保存在 `feature_extracting/feature_data` 下。

