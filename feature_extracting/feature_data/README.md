# 特征提取结果（Feature Data）

本文件夹**仅存放**从 EEG 预处理数据提取得到的、供 ViT 模型使用的特征及配套元数据，不包含原始 EEG 或中间脚本。

---

## 文件说明

| 文件名 | 说明 |
|--------|------|
| **eeg_features_vit.npy** | 主特征张量。NumPy 数组，形状 `[N, 16, 5, 14, 14]`。其中：N = 总 epoch 数；16 = 时间步（1s 窗、0.2s 步长）；5 = 频带（Delta/Theta/Alpha/Beta/Gamma）；14×14 = 空间网格。数值已做全局标准化（减均值除标准差）。 |
| **eeg_features_vit_metadata.csv** | 每个 epoch 的元信息：`subject`、`file_name`、`epoch_index`（文件内序号）、`global_epoch_index`（全局序号）、`batch_file`（生成时的批次名）。用于按被试/按 session 划分或追溯数据来源。 |
| **eeg_features_vit_config.json** | 提取时使用的配置：频带定义、网格大小、时间窗参数、归一化的均值/标准差、特征形状等。复现或加载时请参考此文件。 |

---

## 如何使用

- **加载特征**（Python）：
  ```python
  import numpy as np
  X = np.load('feature_data/eeg_features_vit.npy')  # 或你的路径
  # X.shape = (N, 16, 5, 14, 14)
  ```

- **与标签/被试对应**：用 `eeg_features_vit_metadata.csv` 中的 `subject`、`file_name`、`epoch_index` 或 `global_epoch_index` 与你的标签表对齐。

- **还原归一化**（若需要）：在 `eeg_features_vit_config.json` 中查看 `normalization.mean` 与 `normalization.std`，用 `X_orig = X * std + mean` 可近似还原到标准化前的尺度（仅作参考，训练时一般直接用标准化后的 `X`）。

---

## 如何生成本文件夹内容

在项目根目录运行特征提取脚本（输出已指向本文件夹）：

```bash
python extract_features_for_vit.py
```

脚本会从 `eeg_structure_summary.csv` 和 `channel_grid_mapping.csv` 读入配置，处理 `EEG数据/.../预处理后的数据` 下的 `.set` 文件，最终将上述三个文件写入 **feature_data** 文件夹。

---

*本目录仅保留特征提取后的数据，便于单独备份、分享或用于下游 ViT 训练。*
