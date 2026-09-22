"""
Baseline 入口：EEGNetv4 疲劳二分类（基于 raw EEG）

说明：
- 复用本目录下 `train_eegnet_raw.py` 中的 `main()` 函数。
- 数据：预处理后的 .set 文件，按受试者做 subject-wise Train/Val/Test 划分。
- 结果保存到项目根目录的 feature_data/eegnet_raw_fatigue_result.json。
"""

from train_eegnet_raw import main


if __name__ == "__main__":
    main()
