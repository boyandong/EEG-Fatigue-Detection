"""
Baseline 入口：LSTM 疲劳二分类

说明：
- 复用本目录下 `train_lstm_fatigue.py` 中的 `main()` 函数。
- 当前使用的是一次性的 subject-wise Train/Val/Test 划分（非 LOO），
  主要用于快速得到一个可对比的 LSTM Baseline。
- 后续如需 LOO 版本，可在本文件夹内新增 `run_lstm_baseline_loo.py`，
  并在其中调用对应的 LOO 入口函数（例如 `main_loo()`）。
"""

from train_lstm_fatigue import main


if __name__ == "__main__":
    main()

