import os
import mne
import pandas as pd

# ================= 基本设置 =================
_FE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_FE_DIR)
data_path = os.path.join(_ROOT, 'EEG数据', 'EEG数据', '预处理后的数据')
output_csv = os.path.join(_FE_DIR, 'eeg_structure_summary.csv')

print("当前 mne 版本:", mne.__version__)

# 确认 mne 是否支持 read_epochs_eeglab，如果不支持直接提示升级
if not hasattr(mne, "read_epochs_eeglab"):
    raise RuntimeError(
        "当前 mne 版本不支持 mne.read_epochs_eeglab。\n"
        "请先在终端运行: pip install -U mne\n"
        "升级后再运行本脚本。"
    )

# ================= 扫描 .set 文件 =================
set_files = sorted(
    f for f in os.listdir(data_path)
    if f.lower().endswith('.set')
)

print(f"在目录中找到 {len(set_files)} 个 .set 文件。")

rows = []

for fname in set_files:
    fpath = os.path.join(data_path, fname)
    print(f"\n正在处理文件: {fname}")

    row = {
        'file_name': fname,
        'subject': fname.split('_')[0] if '_' in fname else fname.replace('.set', ''),
    }

    try:
        # 只按 Epochs 读取（因为从错误信息看，这些 .set 全部是多 trial 的 epoched 数据）
        # 注意：在当前 mne 版本中 read_epochs_eeglab 不再支持 preload 参数
        # 这里直接使用默认行为（通常会预加载数据），对结构统计没有影响
        epochs = mne.read_epochs_eeglab(
            fpath,
            verbose='ERROR'
        )

        # ====== 结构信息 ======
        row['data_type'] = 'epochs'
        row['n_epochs'] = len(epochs)
        row['n_channels'] = len(epochs.ch_names)
        row['sfreq'] = float(epochs.info['sfreq'])

        row['tmin'] = float(epochs.tmin)
        row['tmax'] = float(epochs.tmax)
        row['epoch_duration_sec'] = float(epochs.tmax - epochs.tmin)

        row['n_times'] = len(epochs.times)
        row['duration_sec'] = row['n_times'] / row['sfreq']

        # 事件相关信息（可选，但很有用）
        row['n_events'] = int(epochs.events.shape[0])
        row['unique_event_ids'] = ";".join(
            str(eid) for eid in sorted(set(epochs.events[:, 2]))
        )

        row['status'] = 'ok'
        row['error'] = ''

        print(
            f"  类型: Epochs | "
            f"epoch 数: {row['n_epochs']} | "
            f"每个 epoch 时长: {row['epoch_duration_sec']:.3f} s | "
            f"采样率: {row['sfreq']} Hz | "
            f"通道数: {row['n_channels']}"
        )

    except Exception as e:
        # 读取失败的情况（包括 v7.3、奇怪结构等）
        row['data_type'] = 'unknown'
        row['n_epochs'] = None
        row['n_channels'] = None
        row['sfreq'] = None
        row['tmin'] = None
        row['tmax'] = None
        row['epoch_duration_sec'] = None
        row['n_times'] = None
        row['duration_sec'] = None
        row['n_events'] = None
        row['unique_event_ids'] = None
        row['status'] = 'error'
        row['error'] = f"{type(e).__name__}: {e}"

        print(f"  读取失败，错误信息: {type(e).__name__}: {e}")

    rows.append(row)

# ================= 保存 CSV =================
df = pd.DataFrame(rows)
df.to_csv(output_csv, index=False, encoding='utf-8-sig')

print(f"\n所有文件处理完成，结果已保存到: {output_csv}")