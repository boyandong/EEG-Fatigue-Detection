import os
import mne
import numpy as np
import pandas as pd

# ================= 基本设置 =================
_FE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_FE_DIR)
data_path = os.path.join(_ROOT, 'EEG数据', 'EEG数据', '预处理后的数据')
sample_file = 'sub-01_ses-1.set'  # 任意一个文件，通道位置信息在所有文件里应该是一样的
fpath = os.path.join(data_path, sample_file)

print("=" * 60)
print("提取通道位置信息并构建网格映射表")
print("=" * 60)

# ================= 方法1：用 MNE 读取通道位置 =================
print(f"\n正在读取示例文件: {sample_file}")

try:
    epochs = mne.read_epochs_eeglab(fpath, verbose='ERROR')
    ch_names = epochs.ch_names
    n_channels = len(ch_names)
    
    print(f"✓ 成功读取，总通道数: {n_channels}")
    print(f"前10个通道名: {ch_names[:10]}")
    
    # 提取通道位置信息
    pos_3d = []
    has_valid_pos = False
    
    for ch_name in ch_names:
        ch_idx = epochs.ch_names.index(ch_name)
        ch_info = epochs.info['chs'][ch_idx]
        if 'loc' in ch_info and ch_info['loc'] is not None:
            # loc 前3个元素通常是 X, Y, Z
            loc = ch_info['loc'][:3]
            if not np.isnan(loc).any() and np.any(loc != 0):
                pos_3d.append(loc)
                has_valid_pos = True
            else:
                pos_3d.append([np.nan, np.nan, np.nan])
        else:
            pos_3d.append([np.nan, np.nan, np.nan])
    
    pos_3d = np.array(pos_3d)
    
    if has_valid_pos and not np.isnan(pos_3d).all():
        print(f"\n✓ 成功从 MNE 提取到通道位置信息")
        print(f"坐标范围: X[{pos_3d[:, 0].min():.3f}, {pos_3d[:, 0].max():.3f}], "
              f"Y[{pos_3d[:, 1].min():.3f}, {pos_3d[:, 1].max():.3f}], "
              f"Z[{pos_3d[:, 2].min():.3f}, {pos_3d[:, 2].max():.3f}]")
        
        method = 'mne'
        
    else:
        print("\n⚠ MNE 读取的位置信息为空或无效，尝试方法2...")
        method = None
        
except Exception as e:
    print(f"\n⚠ MNE 读取失败: {e}")
    method = None

# ================= 方法2：用 pymatreader 直接从 EEGLAB 结构读取 =================
if method is None:
    try:
        import pymatreader
        
        print("\n尝试用 pymatreader 直接从 EEGLAB 原始结构读取...")
        data = pymatreader.read_mat(fpath)
        
        if 'EEG' in data and 'chanlocs' in data['EEG']:
            chanlocs = data['EEG']['chanlocs']
            
            # 提取通道名
            ch_names = []
            if isinstance(chanlocs, dict):
                # 如果只有一个通道的情况（不太可能，但处理一下）
                ch_names = [chanlocs.get('labels', 'Unknown')]
            elif isinstance(chanlocs, list):
                ch_names = [ch.get('labels', f'Ch{i}') for i, ch in enumerate(chanlocs)]
            else:
                raise ValueError("无法解析 chanlocs 结构")
            
            n_channels = len(ch_names)
            print(f"✓ 成功读取，总通道数: {n_channels}")
            
            # 提取坐标
            pos_3d = []
            has_theta_phi = False
            has_xyz = False
            
            for ch in (chanlocs if isinstance(chanlocs, list) else [chanlocs]):
                # 优先尝试球面坐标 theta, phi
                if 'theta' in ch and 'sph_theta' in ch:
                    theta = ch.get('theta', np.nan)
                    phi = ch.get('sph_theta', np.nan)  # 或 sph_phi
                    if not np.isnan(theta) and not np.isnan(phi):
                        # 球面坐标转 3D 笛卡尔坐标
                        theta_rad = np.deg2rad(theta)
                        phi_rad = np.deg2rad(phi)
                        x = np.sin(phi_rad) * np.cos(theta_rad)
                        y = np.sin(phi_rad) * np.sin(theta_rad)
                        z = np.cos(phi_rad)
                        pos_3d.append([x, y, z])
                        has_theta_phi = True
                    else:
                        pos_3d.append([np.nan, np.nan, np.nan])
                
                # 或者直接用 X, Y, Z
                elif 'X' in ch and 'Y' in ch and 'Z' in ch:
                    x = ch.get('X', np.nan)
                    y = ch.get('Y', np.nan)
                    z = ch.get('Z', np.nan)
                    if not np.isnan(x) and not np.isnan(y) and not np.isnan(z):
                        pos_3d.append([x, y, z])
                        has_xyz = True
                    else:
                        pos_3d.append([np.nan, np.nan, np.nan])
                else:
                    pos_3d.append([np.nan, np.nan, np.nan])
            
            pos_3d = np.array(pos_3d)
            
            if (has_theta_phi or has_xyz) and not np.isnan(pos_3d).all():
                print(f"✓ 成功从 EEGLAB 原始结构提取到通道位置信息")
                print(f"坐标范围: X[{pos_3d[:, 0].min():.3f}, {pos_3d[:, 0].max():.3f}], "
                      f"Y[{pos_3d[:, 1].min():.3f}, {pos_3d[:, 1].max():.3f}], "
                      f"Z[{pos_3d[:, 2].min():.3f}, {pos_3d[:, 2].max():.3f}]")
                method = 'pymatreader'
            else:
                raise ValueError("无法从 EEGLAB 结构提取有效的位置信息")
        else:
            raise ValueError("EEGLAB 数据结构中未找到 chanlocs")
            
    except ImportError:
        print("\n⚠ pymatreader 未安装，跳过方法2")
        print("提示：如果 MNE 方法失败，可以安装 pymatreader: pip install pymatreader")
        method = None
    except Exception as e:
        print(f"\n⚠ pymatreader 读取失败: {e}")
        method = None

# ================= 如果两种方法都失败 =================
if method is None:
    print("\n" + "=" * 60)
    print("错误：无法提取通道位置信息")
    print("=" * 60)
    print("\n可能的原因：")
    print("1. .set 文件中没有保存通道位置信息")
    print("2. 通道位置信息格式不被识别")
    print("\n建议：")
    print("1. 检查 EEGLAB 中是否设置了通道位置（Channel locations）")
    print("2. 或者手动创建一个通道映射表 CSV 文件")
    exit(1)

# ================= 将 3D 坐标投影到 2D 网格 =================
print("\n" + "=" * 60)
print("构建通道到网格的映射")
print("=" * 60)

# 使用 X-Y 平面投影（假设 Z 是高度，X-Y 是水平面）
pos_2d = pos_3d[:, :2]  # 只用 X, Y

# 归一化到 [0, 1] 范围
pos_2d_min = pos_2d.min(axis=0)
pos_2d_max = pos_2d.max(axis=0)
pos_2d_range = pos_2d_max - pos_2d_min
pos_2d_range[pos_2d_range < 1e-10] = 1.0  # 避免除零

pos_2d_norm = (pos_2d - pos_2d_min) / pos_2d_range

# 确定网格大小：需要能容纳所有通道
# 61 个通道，使用 10×10=100 个位置（更宽松，减少重叠）
H, W = 10, 10
if n_channels > H * W:
    # 如果通道数超过 10×10，自动调整
    grid_size = int(np.ceil(np.sqrt(n_channels)))
    H, W = grid_size, grid_size
    print(f"通道数 ({n_channels}) 超过 10×10，自动调整为 {H}×{W} 网格")

print(f"使用网格大小: {H}×{W} = {H*W} 个位置（可容纳 {n_channels} 个通道）")

# 映射到网格索引
grid_positions = np.zeros((n_channels, 2), dtype=int)

for i in range(n_channels):
    # 将归一化坐标映射到网格索引
    r = int(pos_2d_norm[i, 1] * (H - 1))  # Y -> row
    c = int(pos_2d_norm[i, 0] * (W - 1))  # X -> col
    # 确保索引在有效范围内
    r = max(0, min(r, H - 1))
    c = max(0, min(c, W - 1))
    grid_positions[i] = [r, c]

# ================= 创建映射表 =================
mapping_table = pd.DataFrame({
    'channel_name': ch_names,
    'channel_index': range(n_channels),
    'grid_row': grid_positions[:, 0],
    'grid_col': grid_positions[:, 1],
    'x_3d': pos_3d[:, 0],
    'y_3d': pos_3d[:, 1],
    'z_3d': pos_3d[:, 2],
    'x_2d_norm': pos_2d_norm[:, 0],
    'y_2d_norm': pos_2d_norm[:, 1],
})

print("\n=== 通道到网格映射表（前20行）===")
print(mapping_table.head(20).to_string())

# 检查是否有重叠（多个通道映射到同一个网格位置）
grid_occupancy = {}
for i, ch_name in enumerate(ch_names):
    r, c = grid_positions[i]
    key = (r, c)
    if key not in grid_occupancy:
        grid_occupancy[key] = []
    grid_occupancy[key].append(ch_name)

overlaps = {k: v for k, v in grid_occupancy.items() if len(v) > 1}
if overlaps:
    print(f"\n⚠ 警告：发现 {len(overlaps)} 个网格位置有多个通道重叠")
    print("重叠位置示例（前5个）：")
    for (r, c), ch_list in list(overlaps.items())[:5]:
        print(f"  位置 ({r}, {c}): {ch_list}")
    print("\n提示：重叠是正常的，因为通道位置可能很接近。")
    print("在构建特征张量时，可以对重叠位置求平均或选择其中一个通道。")
else:
    print("\n✓ 所有通道都映射到不同的网格位置，无重叠")

# ================= 可视化网格布局 =================
print("\n" + "=" * 60)
print("网格布局预览")
print("=" * 60)

grid_vis = np.full((H, W), '  ', dtype='U10')
grid_count = np.zeros((H, W), dtype=int)

for i, ch_name in enumerate(ch_names):
    r, c = grid_positions[i]
    # 只显示通道名前2个字符（避免网格太挤）
    if grid_vis[r, c] == '  ':
        grid_vis[r, c] = ch_name[:2] if len(ch_name) >= 2 else ch_name
    else:
        # 如果位置已被占用，标记为 '++'
        grid_vis[r, c] = '++'
    grid_count[r, c] += 1

print(f"\n网格布局 ({H}×{W}):")
print("行\\列", end="")
for c in range(W):
    print(f"  {c:2d}", end="")
print()

for r in range(H):
    print(f" {r:2d}  ", end="")
    for c in range(W):
        print(f" {grid_vis[r, c]:<4}", end="")
    print()

print("\n图例：")
print("  - 通道名（前2字符）表示该位置有通道")
print("  - '++' 表示多个通道重叠在该位置")
print("  - '  ' 表示该位置为空")

# ================= 保存映射表 =================
output_csv = os.path.join(_FE_DIR, 'channel_grid_mapping.csv')
mapping_table.to_csv(output_csv, index=False, encoding='utf-8-sig')
print(f"\n" + "=" * 60)
print(f"✓ 映射表已保存到: {output_csv}")
print("=" * 60)

print("\n映射表包含以下列：")
print("  - channel_name: 通道名称")
print("  - channel_index: 通道索引（0-based）")
print("  - grid_row, grid_col: 在 H×W 网格中的行列位置")
print("  - x_3d, y_3d, z_3d: 3D 坐标")
print("  - x_2d_norm, y_2d_norm: 归一化的 2D 坐标")

print("\n下一步：")
print("  1. 检查 channel_grid_mapping.csv 确认映射是否正确")
print("  2. 如果网格布局不合理，可以调整 H, W 参数或投影方法")
print("  3. 使用此映射表构建最终的 [batch, 16, 5, H, W] 特征张量")
