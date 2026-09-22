"""
EEG 特征提取脚本：生成用于 ViT 模型的 5D 张量
输出格式: [Batch, 16, 5, 14, 14]
- Batch: 所有 epoch 的总数
- 16: 时间步数（使用滑动窗口：1秒窗口，0.2秒步长）
- 5: 频带数（Delta, Theta, Alpha, Beta, Gamma）
- 14×14: 空间拓扑图（通过 cubic 插值生成）

处理方式：
- 滑动窗口：每个时间步使用1秒窗口，步长为0.2秒（重叠窗口）
- GPU加速：使用PyTorch GPU批量计算所有通道的DE（FFT频域滤波）
- 批次保存：每处理完一个文件就保存一次，最后合并所有批次
- 自动归一化：对最终特征进行全局归一化

性能优化：
- 批量处理：所有通道、所有频带的DE计算在GPU上并行完成
- 减少传输：尽量减少CPU-GPU数据传输次数
- 内存管理：定期清理GPU缓存，避免内存溢出
"""

import os
import numpy as np
import pandas as pd
import mne
from scipy.interpolate import griddata
import torch
import torch.nn.functional as F
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# 检查GPU可用性
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# ================= 配置参数 =================
# 路径相对项目根：本脚本在 feature_extracting/ 下，数据和输出均在对应目录
_FE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_FE_DIR)
DATA_PATH = os.path.join(_ROOT, 'EEG数据', 'EEG数据', '预处理后的数据')
MAPPING_CSV = os.path.join(_FE_DIR, 'channel_grid_mapping.csv')
INFO_CSV = os.path.join(_FE_DIR, 'eeg_structure_summary.csv')

# 条件设置：
#   - "NS" 表示只处理 Normal sleep (ses-1)
#   - "SD" 表示只处理 Sleep deprivation (ses-2)
#   - 其他值（例如 ""）表示不区分条件，处理所有 ses（保持向后兼容）
CONDITION = "NS"  # 需要处理 SD 时手动改成 "SD"

# 特征提取结果统一输出到 feature_extracting/feature_data
OUTPUT_DIR = os.path.join(_FE_DIR, 'feature_data')

# 根据条件给输出文件加后缀，方便生成 NS / SD 两套特征
if CONDITION == "NS":
    FILE_SUFFIX = "_NS"
elif CONDITION == "SD":
    FILE_SUFFIX = "_SD"
else:
    FILE_SUFFIX = ""

OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"eeg_features_vit{FILE_SUFFIX}.npy")

# 频带定义
FREQ_BANDS = {
    'Delta': (1, 4),
    'Theta': (4, 8),
    'Alpha': (8, 14),
    'Beta': (14, 31),
    'Gamma': (31, 51),
}
BAND_NAMES = list(FREQ_BANDS.keys())
N_BANDS = len(BAND_NAMES)
N_TIME_STEPS = 16
GRID_SIZE = 14  # 14×14 网格

# 调试开关：用于诊断“特征几乎不变 / 大量常数值”的问题
DEBUG_GLOBAL_STATS = True

# 是否在每个时间窗、每个频带上对通道 DE 做“局部通道内归一化”
# 你现在希望使用“全局统一的 mean/std”，而不是每窗一套参数，因此这里默认关闭
USE_CHANNELWISE_DE_ZSCORE = False

# ======== 全局 DE 统计量（用于后续统一归一化）========
# 我们只在“61 个真实通道的 DE 值”上计算全局 mean/std，
# 不让插值 padding 0 参与统计，从而保证归一化参数不被污染。
GLOBAL_DE_SUM = 0.0
GLOBAL_DE_SQ_SUM = 0.0
GLOBAL_DE_COUNT = 0

# ================= 核心函数：计算微分熵 (DE) - GPU加速版本 =================
def compute_de_batch_gpu(signal_data_gpu, sfreq, fmin, fmax):
    """
    批量计算所有通道的微分熵（GPU加速）
    
    参数:
        signal_data_gpu: (n_channels, n_times) torch.Tensor，已在GPU上
        sfreq: 采样率
        fmin, fmax: 频带范围
    
    返回:
        de_values: (n_channels,) torch.Tensor，所有通道的DE值
    """
    n_channels, n_times = signal_data_gpu.shape
    
    # 使用FFT做频域滤波（比scipy的butter快很多）
    # 计算FFT
    fft_data = torch.fft.rfft(signal_data_gpu, dim=1)
    freqs = torch.fft.rfftfreq(n_times, 1/sfreq, device=signal_data_gpu.device)
    
    # 创建频域掩码（带通滤波）
    mask = (freqs >= fmin) & (freqs <= fmax)
    mask = mask.unsqueeze(0)  # (1, n_freqs)
    
    # 应用掩码
    fft_filtered = fft_data * mask
    
    # 逆FFT回到时域
    filtered = torch.fft.irfft(fft_filtered, n=n_times, dim=1)
    
    # 批量计算方差（所有通道一起）
    variance = torch.var(filtered, dim=1)  # (n_channels,)
    variance = torch.clamp(variance, min=1e-12)  # 避免log(0)
    
    # 批量计算DE
    de_values = 0.5 * torch.log(2 * np.pi * np.e * variance)
    
    return de_values

# ================= 核心函数：插值到网格 =================
def interpolate_to_grid(channel_coords, channel_values, grid_size=14, method='cubic', fill_value=0.0):
    """
    将通道的 DE 值插值到指定大小的网格上
    
    参数:
        channel_coords: (n_channels, 2) 数组，通道的归一化坐标 [x, y]
        channel_values: (n_channels,) 数组，每个通道的 DE 值
        grid_size: 网格大小（grid_size × grid_size）
        method: 插值方法 ('linear', 'cubic', 'nearest')
        fill_value: 超出范围的填充值
    
    返回:
        grid_image: (grid_size, grid_size) 数组，插值后的网格图像
    """
    # 生成目标网格坐标
    xi = np.linspace(0, 1, grid_size)
    yi = np.linspace(0, 1, grid_size)
    xi_grid, yi_grid = np.meshgrid(xi, yi)
    grid_points = np.column_stack([xi_grid.ravel(), yi_grid.ravel()])
    
    # 执行插值
    grid_values = griddata(
        channel_coords,
        channel_values,
        grid_points,
        method=method,
        fill_value=fill_value
    )
    
    # 重塑为网格形状
    grid_image = grid_values.reshape(grid_size, grid_size)
    
    # 处理可能的 NaN（边缘区域）
    grid_image = np.nan_to_num(grid_image, nan=fill_value)
    
    return grid_image

# ================= 处理单个 epoch（GPU加速版本）=================
def process_epoch(epoch_data, sfreq, channel_coords, n_time_steps=16, grid_size=14, debug=False):
    """
    处理单个 epoch，生成 [16, 5, 14, 14] 的特征张量
    使用重叠滑动窗口：1秒窗口，0.2秒步长
    GPU加速：批量处理所有通道和频带
    
    参数:
        epoch_data: (n_channels, n_times) 数组，单个 epoch 的数据
        sfreq: 采样率
        channel_coords: (n_channels, 2) 数组，通道坐标
        n_time_steps: 时间步数
        grid_size: 网格大小
        debug: 若为 True，在第一个时间窗打印原始信号方差范围与 DE 前 5 通道，用于检验是否因单位方差导致 DE 常数化
    
    返回:
        features: (n_time_steps, n_bands, grid_size, grid_size) 数组
    """
    n_channels, n_times = epoch_data.shape
    
    # 滑动窗口参数：1秒窗口，0.2秒步长
    window_len = int(sfreq * 1.0)  # 1秒窗口（500点 @ 500Hz）
    stride = int(sfreq * 0.2)      # 0.2秒步长（100点 @ 500Hz）
    
    # 将epoch数据移到GPU（一次性传输）
    epoch_data_gpu = torch.from_numpy(epoch_data).float().to(device)
    
    # 预分配特征数组
    features = np.zeros((n_time_steps, N_BANDS, grid_size, grid_size), dtype=np.float32)
    
    # 预分配所有时间步的DE值（在GPU上）
    all_de_values = torch.zeros((n_time_steps, N_BANDS, n_channels), 
                                dtype=torch.float32, device=device)

    # 若开启调试：记录某个频带（这里选 Delta）的 DE 随时间窗的变化情况
    if debug:
        delta_de_mean_per_t = []
        delta_de_min_per_t = []
        delta_de_max_per_t = []
    
    # 批量处理所有时间步和频带
    for t in range(n_time_steps):
        start_idx = t * stride
        end_idx = start_idx + window_len
        
        # 边界检查：确保不超出数据范围
        if end_idx > n_times:
            end_idx = n_times
            start_idx = end_idx - window_len
            if start_idx < 0:
                start_idx = 0
        
        window_data_gpu = epoch_data_gpu[:, start_idx:end_idx]  # (n_channels, window_len)
        
        # 调试：仅第一个 epoch 的第一个时间窗打印，检验“单位方差导致 DE 常数”的假设
        if debug and t == 0:
            var_per_ch = torch.var(window_data_gpu, dim=1)
            print(f"\n  [调试] 原始信号方差范围（首窗、每通道）: min={var_per_ch.min().item():.6f}, max={var_per_ch.max().item():.6f}")
        
        # 批量计算所有频带的DE（在GPU上）
        for bi, (band_name, (fmin, fmax)) in enumerate(FREQ_BANDS.items()):
            de_values_gpu = compute_de_batch_gpu(window_data_gpu, sfreq, fmin, fmax)

            # 可选：在每个时间窗 / 频带上，对所有通道的 DE 做一次通道内 z-score 归一化
            # 注意：这里只基于 61 个真实通道的 DE 值做归一化，尚未进行 2D 插值，因此不会把 padding 区域计入统计
            if USE_CHANNELWISE_DE_ZSCORE:
                mean_de = torch.mean(de_values_gpu)
                std_de = torch.std(de_values_gpu)
                # 避免方差过小导致数值不稳定
                de_values_gpu = (de_values_gpu - mean_de) / (std_de + 1e-8)

            # 无论是否做局部 z-score，都在这里累积“真实通道 DE 值”的全局统计量，
            # 仅基于 61 个通道的 DE，而不是插值后的 14×14 网格。
            global GLOBAL_DE_SUM, GLOBAL_DE_SQ_SUM, GLOBAL_DE_COUNT
            # 使用 double 精度以提升全局统计的数值稳定性
            de_cpu = de_values_gpu.detach().cpu().double()
            GLOBAL_DE_SUM += de_cpu.sum().item()
            GLOBAL_DE_SQ_SUM += (de_cpu ** 2).sum().item()
            GLOBAL_DE_COUNT += de_cpu.numel()

            all_de_values[t, bi, :] = de_values_gpu
            # 调试：记录 Delta 频带在每个时间窗上的 DE 统计量（均值 / min / max）
            if debug and band_name == 'Delta':
                delta_de_mean_per_t.append(de_values_gpu.mean().item())
                delta_de_min_per_t.append(de_values_gpu.min().item())
                delta_de_max_per_t.append(de_values_gpu.max().item())
            if debug and t == 0 and bi == 0:
                print(f"  [调试] DE 特征值（前5个通道）: {de_values_gpu[:5].cpu().numpy()}")

    # 若开启调试：打印 Delta 频带在 16 个时间窗上的整体变化情况
    if debug:
        import numpy as _np  # 仅用于调试打印
        print("\n  [调试] Delta 频带各时间窗 DE 均值:")
        print("    ", _np.round(_np.array(delta_de_mean_per_t), 6))
        print("  [调试] Delta 频带各时间窗 DE 最小值:")
        print("    ", _np.round(_np.array(delta_de_min_per_t), 6))
        print("  [调试] Delta 频带各时间窗 DE 最大值:")
        print("    ", _np.round(_np.array(delta_de_max_per_t), 6))
        
    # 一次性将DE值传回CPU（减少传输次数）
    all_de_values_cpu = all_de_values.cpu().numpy()
    
    # 在CPU上做插值（scipy的griddata不支持GPU，但可以批量处理）
    for t in range(n_time_steps):
        for bi in range(N_BANDS):
            de_values = all_de_values_cpu[t, bi, :]
            
            # 插值到网格（使用 cubic 方法）
            grid_image = interpolate_to_grid(
                channel_coords,
                de_values,
                grid_size=grid_size,
                method='cubic',
                fill_value=0.0
            )
            
            features[t, bi, :, :] = grid_image
    
    return features

# ================= 主函数 =================
def main():
    print("=" * 60)
    print("EEG 特征提取：生成 ViT 模型输入张量（GPU加速版本）")
    print("=" * 60)
    
    # GPU信息
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        print(f"\nGPU信息:")
        print(f"  设备: {torch.cuda.get_device_name(0)}")
        print(f"  内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    else:
        print("\n⚠ 警告：未检测到GPU，将使用CPU（速度较慢）")
    
    # 1. 加载通道映射表
    print("\n1. 加载通道映射表...")
    mapping_df = pd.read_csv(MAPPING_CSV)
    channel_coords = mapping_df[['x_2d_norm', 'y_2d_norm']].values  # (61, 2)
    channel_names = mapping_df['channel_name'].tolist()
    print(f"   ✓ 加载了 {len(channel_names)} 个通道的坐标")
    
    # 2. 加载文件信息表
    print("\n2. 加载文件信息表...")
    info_df = pd.read_csv(INFO_CSV)
    info_df = info_df[info_df['status'] == 'ok'].reset_index(drop=True)
    
    # 根据 CONDITION 只选择对应 ses 的文件：
    # - CONDITION == "NS": 只保留 file_name 中包含 "ses-1" 的 Normal sleep 数据
    # - CONDITION == "SD": 只保留 file_name 中包含 "ses-2" 的 Sleep deprivation 数据
    # - 其他值: 不做过滤（处理所有 ses）
    if CONDITION == "NS":
        info_df = info_df[info_df["file_name"].str.contains("ses-1")].reset_index(drop=True)
        print("   当前条件: NS (Normal sleep, ses-1)")
    elif CONDITION == "SD":
        info_df = info_df[info_df["file_name"].str.contains("ses-2")].reset_index(drop=True)
        print("   当前条件: SD (Sleep deprivation, ses-2)")
    else:
        print("   当前条件: ALL (不区分 ses，处理所有文件)")
    
    print(f"   ✓ 找到 {len(info_df)} 个可用的 .set 文件")
    
    # 3. 预计算总 epoch 数（用于进度条）
    total_epochs = info_df['n_epochs'].sum()
    print(f"\n3. 总 epoch 数: {total_epochs}")
    
    # 4. 创建输出目录和临时文件列表（最终结果写入 feature_data，临时批次在 features_batches）
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_dir = 'features_batches'
    os.makedirs(output_dir, exist_ok=True)
    batch_files = []
    metadata = []
    
    # 5. 批量处理所有文件（按文件批次保存）
    print("\n4. 开始批量处理（按文件批次保存）...")
    epoch_counter = 0
    file_counter = 0
    
    for idx, row in tqdm(info_df.iterrows(), total=len(info_df), desc="处理文件"):
        file_name = row['file_name']
        subject = row['subject']
        n_epochs = int(row['n_epochs'])
        sfreq = row['sfreq']
        
        file_path = os.path.join(DATA_PATH, file_name)
        
        try:
            # 读取 epochs
            epochs = mne.read_epochs_eeglab(file_path, verbose='ERROR')
            
            # 确保通道顺序与映射表一致
            epoch_ch_names = epochs.ch_names
            if epoch_ch_names != channel_names:
                # 重新排序通道
                epochs = epochs.reorder_channels(channel_names)
            
            # 获取数据: (n_epochs, n_channels, n_times)
            epoch_data_array = epochs.get_data()
            
            # 为当前文件预分配批次数组
            batch_features = np.zeros(
                (n_epochs, N_TIME_STEPS, N_BANDS, GRID_SIZE, GRID_SIZE),
                dtype=np.float32
            )
            
            # 处理每个 epoch
            for e in range(n_epochs):
                epoch_data = epoch_data_array[e]  # (n_channels, n_times)
                # 仅对第一个文件的第一个 epoch 做调试打印（方差 + DE 前5通道），用于检验单位方差导致 DE 常数化
                is_first_epoch = (file_counter == 0 and e == 0)
                features = process_epoch(
                    epoch_data,
                    sfreq,
                    channel_coords,
                    n_time_steps=N_TIME_STEPS,
                    grid_size=GRID_SIZE,
                    debug=is_first_epoch
                )
                
                # 存储到批次数组
                batch_features[e] = features
                
                # 存储元信息
                metadata.append({
                    'subject': subject,
                    'file_name': file_name,
                    'epoch_index': e,
                    'global_epoch_index': epoch_counter,
                    'batch_file': f'batch_{file_counter:04d}.npy'
                })
                
                epoch_counter += 1
            
            # 保存当前文件的批次
            batch_file = os.path.join(output_dir, f'batch_{file_counter:04d}.npy')
            np.save(batch_file, batch_features)
            batch_files.append(batch_file)
            file_counter += 1
            
            # 清理GPU缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            print(f"\n  ✓ {file_name}: 已保存 {n_epochs} 个 epoch 到 {batch_file}")
                
        except Exception as e:
            print(f"\n  ⚠ 处理 {file_name} 时出错: {e}")
            # 跳过这个文件，继续处理下一个
            continue
    
    # 6. 合并所有批次文件
    print(f"\n5. 合并所有批次文件（共 {len(batch_files)} 个批次）...")
    all_batches = []
    for batch_file in tqdm(batch_files, desc="加载批次"):
        batch_data = np.load(batch_file)
        all_batches.append(batch_data)
    
    # 合并所有批次
    all_features = np.concatenate(all_batches, axis=0)
    print(f"   ✓ 合并完成，总 epoch 数: {epoch_counter}")
    print(f"   ✓ 特征数组形状: {all_features.shape}")
    
    # 6+. 归一化前的统计信息（基于插值后的特征，用于诊断数值是否“几乎不变”）
    if DEBUG_GLOBAL_STATS:
        print("\n6. 归一化前特征统计（全数据，插值后，尚未统一归一化）...")
        flat = all_features.reshape(-1)
        orig_min, orig_max = flat.min(), flat.max()
        orig_mean, orig_std = flat.mean(), flat.std()
        zero_ratio = np.mean(np.isclose(flat, 0.0))
        print(f"   原始特征 min/max: {orig_min:.6f} / {orig_max:.6f}")
        print(f"   原始特征 mean/std: {orig_mean:.6f} / {orig_std:.6f}")
        print(f"   精确等于 0 的元素比例: {zero_ratio * 100:.2f}%")

        # 查看几个具体位置随时间的变化（未归一化）
        if all_features.shape[0] > 0:
            center_i = GRID_SIZE // 2
            center_j = GRID_SIZE // 2
            sample0_center_band0 = all_features[0, :, 0, center_i, center_j]
            print(f"   样本 0、Delta 频带、中心点随时间的值: {np.round(sample0_center_band0, 6)}")

    # 7. 基于“真实通道 DE 值”的全局统计信息（不包含插值 padding）
    #    这里只做统计和记录，不再对特征做全局数值缩放，避免在特征阶段引入跨 subject 的数据泄漏。
    print("\n7. 基于 DE 通道值的全局统计信息（仅记录，不用于缩放特征）...")
    if GLOBAL_DE_COUNT == 0:
        raise RuntimeError("GLOBAL_DE_COUNT 为 0，说明在累积 DE 统计时出现问题。")
    global_de_mean = GLOBAL_DE_SUM / GLOBAL_DE_COUNT
    global_de_var = GLOBAL_DE_SQ_SUM / GLOBAL_DE_COUNT - global_de_mean ** 2
    global_de_var = max(global_de_var, 1e-12)
    global_de_std = float(np.sqrt(global_de_var))
    global_de_mean = float(global_de_mean)
    print(f"   global_de_mean: {global_de_mean:.6f}")
    print(f"   global_de_std : {global_de_std:.6f}")

    # 8. 不对特征做全局缩放。后续模型（LSTM / ViT / EEGNet 等）在训练阶段
    #    应自行使用“train 集的统计量”做归一化，这样更安全也更灵活。
    #    这里只根据未缩放的特征构造 padding 掩码。
    print("\n8. 不对特征做全局缩放，直接构造 padding 掩码供下游模型使用...")
    padding_mask = (all_features == 0.0)

    # 9. 派生一个“空间 padding 掩码”（哪些 grid 位置在所有样本 / 时间 / 频带上始终是 padding）
    #    方便你在 ViT 训练时使用（可选）
    spatial_padding_mask = padding_mask.all(axis=(0, 1, 2))  # 形状: (GRID_SIZE, GRID_SIZE)
    
    # 10. 保存最终结果
    print(f"\n9. 保存最终特征到 {OUTPUT_FILE}...")
    np.save(OUTPUT_FILE, all_features)
    print(f"   ✓ 特征数组形状: {all_features.shape}")
    print(f"   ✓ 文件大小: {all_features.nbytes / 1024 / 1024:.2f} MB")
    
    # 同时保存空间 padding 掩码（仅一张 14×14 的二维布尔图）
    padding_mask_file = OUTPUT_FILE.replace('.npy', '_padding_mask.npy')
    np.save(padding_mask_file, spatial_padding_mask.astype(np.bool_))
    print(f"   ✓ 空间 padding 掩码已保存到: {padding_mask_file}")
    
    # 11. 保存元信息
    metadata_df = pd.DataFrame(metadata)
    metadata_file = OUTPUT_FILE.replace('.npy', '_metadata.csv')
    metadata_df.to_csv(metadata_file, index=False, encoding='utf-8-sig')
    print(f"   ✓ 元信息已保存到: {metadata_file}")
    
    # 10. 保存配置信息
    config = {
        'n_samples': epoch_counter,
        'n_time_steps': N_TIME_STEPS,
        'n_bands': N_BANDS,
        'band_names': BAND_NAMES,
        'freq_bands': FREQ_BANDS,
        'grid_size': GRID_SIZE,
        'feature_shape': list(all_features.shape),
        'window_config': {
            'window_length_sec': 1.0,
            'stride_sec': 0.2,
            'method': 'sliding_window'
        },
        'normalization': {
            # 基于“真实通道 DE 值”计算得到，并用于特征统一归一化的全局参数
            'mean': float(global_de_mean),
            'std': float(global_de_std)
        }
    }
    
    import json
    config_file = OUTPUT_FILE.replace('.npy', '_config.json')
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"   ✓ 配置信息已保存到: {config_file}")
    
    # 11. 清理临时批次文件（可选）
    print(f"\n8. 清理临时批次文件...")
    for batch_file in batch_files:
        try:
            os.remove(batch_file)
        except:
            pass
    print(f"   ✓ 已清理 {len(batch_files)} 个临时批次文件")
    
    print("\n" + "=" * 60)
    print("处理完成！")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  - {OUTPUT_FILE}: 特征张量 [Batch, 16, 5, 14, 14]")
    print(f"  - {metadata_file}: 元信息（subject, file_name, epoch_index）")
    print(f"  - {config_file}: 配置信息")
    print(f"\n处理方式:")
    print(f"  - 使用滑动窗口：1秒窗口，0.2秒步长")
    print(f"  - 按文件批次保存，最后合并")
    print(f"\n下一步:")
    print(f"  1. 检查特征张量的形状和数值范围")
    print(f"  2. 使用此张量训练 ViT 模型")
    print(f"  3. 建议 ViT 的 patch_size=2（因为输入是 14×14）")

if __name__ == '__main__':
    main()
