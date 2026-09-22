"""TCN blocks: causal conv, temporal attention, multi-scale branches."""

from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class LayerNorm1d(nn.Module):
    """LayerNorm on channel dim for [B, C, T]: permute to [B, T, C], norm, permute back."""

    def __init__(self, channels: int, eps: float = 1e-5):
        super(LayerNorm1d, self).__init__()
        self.norm = nn.LayerNorm(channels, eps=eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.norm(x.permute(0, 2, 1)).permute(0, 2, 1)


class Chomp1d(nn.Module):
    """Causal conv chomp: remove last chomp_size time steps."""
    def __init__(self, chomp_size: int):
        super(Chomp1d, self).__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.chomp_size == 0:
            return x
        return x[:, :, :-self.chomp_size].contiguous()


class DepthwiseSeparableConv1d(nn.Module):
    """Depthwise Conv -> BN -> GELU -> Pointwise Conv -> BN -> GELU."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int,
                 stride: int = 1, padding: int = 0, dilation: int = 1, bias: bool = False):
        super(DepthwiseSeparableConv1d, self).__init__()
        self.depthwise = nn.Conv1d(
            in_channels, in_channels, kernel_size,
            stride=stride, padding=padding, dilation=dilation,
            groups=in_channels, bias=bias
        )
        self.norm1 = nn.BatchNorm1d(in_channels)
        self.gelu1 = nn.GELU()
        self.pointwise = nn.Conv1d(in_channels, out_channels, kernel_size=1, bias=bias)
        self.norm2 = nn.BatchNorm1d(out_channels)
        self.gelu2 = nn.GELU()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.depthwise(x)
        x = self.norm1(x)
        x = self.gelu1(x)
        x = self.pointwise(x)
        x = self.norm2(x)
        x = self.gelu2(x)
        return x

class StochasticDropout(nn.Module):
    """Stochastic channel dropout; at eval scale by (1-p) for same expectation as train."""

    def __init__(self, p: float = 0.3):
        super(StochasticDropout, self).__init__()
        self.p = p

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.p == 0:
            return x
        if not self.training:
            return x * (1.0 - self.p)

        batch_size, channels, seq_len = x.shape
        num_drop = int(channels * self.p)
        if num_drop == 0:
            return x
        drop_indices = torch.randperm(channels, device=x.device)[:num_drop]
        drop_mask = torch.ones(channels, device=x.device, dtype=x.dtype)
        drop_mask[drop_indices] = 0
        drop_mask = drop_mask.view(1, channels, 1)
        return x * drop_mask


class MaskedTemporalAttention(nn.Module):
    """Temporal self-attention with optional length mask for variable-length sequences."""

    def __init__(self, 
                 channels: int,
                 num_heads: int = 8,
                 dropout: float = 0.1,
                 use_bias: bool = False,
                 use_shared_qkv: bool = True):
        super(MaskedTemporalAttention, self).__init__()
        assert channels % num_heads == 0, f"channels {channels} must be divisible by num_heads {num_heads}"
        
        self.channels = channels
        self.num_heads = num_heads
        self.head_dim = channels // num_heads
        self.scale = self.head_dim ** -0.5
        self.use_shared_qkv = use_shared_qkv

        if use_shared_qkv:
            self.qkv_conv = nn.Conv1d(channels, channels * 3, kernel_size=1, bias=use_bias)
        else:
            self.q_conv = nn.Conv1d(channels, channels, kernel_size=1, bias=use_bias)
            self.k_conv = nn.Conv1d(channels, channels, kernel_size=1, bias=use_bias)
            self.v_conv = nn.Conv1d(channels, channels, kernel_size=1, bias=use_bias)

        self.out_conv = nn.Conv1d(channels, channels, kernel_size=1, bias=use_bias)
        self.dropout = nn.Dropout(dropout)
        self.init_weights()

    def init_weights(self):
        if self.use_shared_qkv:
            nn.init.kaiming_uniform_(self.qkv_conv.weight, mode='fan_in', nonlinearity='relu')
        else:
            nn.init.kaiming_uniform_(self.q_conv.weight, mode='fan_in', nonlinearity='relu')
            nn.init.kaiming_uniform_(self.k_conv.weight, mode='fan_in', nonlinearity='relu')
            nn.init.kaiming_uniform_(self.v_conv.weight, mode='fan_in', nonlinearity='relu')
        nn.init.kaiming_uniform_(self.out_conv.weight, mode="fan_in", nonlinearity="relu")

    def _create_length_mask(self, lengths: torch.Tensor, max_len: int) -> torch.Tensor:
        batch_size = lengths.shape[0]
        mask = torch.arange(max_len, device=lengths.device).expand(
            batch_size, max_len
        ) < lengths.unsqueeze(1)
        mask = mask.unsqueeze(1).unsqueeze(2)  # [B, 1, 1, T]
        mask = mask.expand(-1, -1, max_len, -1)
        return mask
    
    def forward(self, x: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, C, T = x.shape
        if self.use_shared_qkv:
            qkv = self.qkv_conv(x)
            q, k, v = qkv.chunk(3, dim=1)
        else:
            q = self.q_conv(x)  # [B, C, T]
            k = self.k_conv(x)  # [B, C, T]
            v = self.v_conv(x)
        q = q.view(B, self.num_heads, self.head_dim, T)
        k = k.view(B, self.num_heads, self.head_dim, T)
        v = v.view(B, self.num_heads, self.head_dim, T)
        q = q.permute(0, 1, 3, 2)
        k = k.permute(0, 1, 3, 2)
        v = v.permute(0, 1, 3, 2)
        attn = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        if lengths is not None:
            length_mask = self._create_length_mask(lengths, T)
            attn = attn.masked_fill(~length_mask, float("-inf"))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)
        out = torch.matmul(attn, v)
        out = out.permute(0, 1, 3, 2).contiguous().view(B, C, T)
        out = self.out_conv(out)
        return out


class TemporalBlock(nn.Module):
    """Single TCN block: DCC -> BN -> GELU -> SD -> DCC -> BN -> GELU -> SD -> optional Attn -> residual."""

    def __init__(self, 
                 in_channels: int, 
                 out_channels: int, 
                 kernel_size: int, 
                 dilation: int, 
                 dropout: float = 0.3,
                 use_attention: bool = True,
                 num_attention_heads: int = 8,
                 attention_dropout: float = 0.1,
                 use_depthwise_separable: bool = False):
        super(TemporalBlock, self).__init__()
        
        padding = (kernel_size - 1) * dilation
        self.use_depthwise_separable = use_depthwise_separable

        ConvLayer = DepthwiseSeparableConv1d if use_depthwise_separable else nn.Conv1d

        self.conv1 = ConvLayer(
            in_channels, out_channels, kernel_size,
            stride=1, padding=padding, dilation=dilation, bias=False
        )
        self.chomp1 = Chomp1d(padding)
        if not use_depthwise_separable:
            self.norm1 = nn.BatchNorm1d(out_channels)
            self.gelu1 = nn.GELU()
        self.sd1 = StochasticDropout(dropout)

        self.conv2 = ConvLayer(
            out_channels, out_channels, kernel_size,
            stride=1, padding=padding, dilation=dilation, bias=False
        )
        self.chomp2 = Chomp1d(padding)
        if not use_depthwise_separable:
            self.norm2 = nn.BatchNorm1d(out_channels)
            self.gelu2 = nn.GELU()
        self.sd2 = StochasticDropout(dropout)
        self.use_attention = use_attention
        if use_attention:
            self.attention = MaskedTemporalAttention(
                channels=out_channels,
                num_heads=num_attention_heads,
                dropout=attention_dropout,
                use_shared_qkv=True,
            )

        if in_channels != out_channels:
            self.shortcut_conv = nn.Conv1d(in_channels, out_channels, kernel_size=1, bias=False)
        else:
            self.shortcut_conv = None
        self.init_weights()

    def init_weights(self):
        if self.use_depthwise_separable:
            nn.init.kaiming_uniform_(self.conv1.depthwise.weight, mode="fan_in", nonlinearity="relu")
            nn.init.kaiming_uniform_(self.conv1.pointwise.weight, mode="fan_in", nonlinearity="relu")
            nn.init.kaiming_uniform_(self.conv2.depthwise.weight, mode="fan_in", nonlinearity="relu")
            nn.init.kaiming_uniform_(self.conv2.pointwise.weight, mode="fan_in", nonlinearity="relu")
        else:
            nn.init.kaiming_uniform_(self.conv1.weight, mode="fan_in", nonlinearity="relu")
            nn.init.kaiming_uniform_(self.conv2.weight, mode="fan_in", nonlinearity="relu")
        if self.shortcut_conv is not None:
            nn.init.kaiming_uniform_(self.shortcut_conv.weight, mode="fan_in", nonlinearity="relu")

    def forward(self, x: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        out = self.conv1(x)
        out = self.chomp1(out)
        if not self.use_depthwise_separable:
            out = self.norm1(out)
            out = self.gelu1(out)
        out = self.sd1(out)

        out = self.conv2(out)
        out = self.chomp2(out)
        if not self.use_depthwise_separable:
            out = self.norm2(out)
            out = self.gelu2(out)
        out = self.sd2(out)

        if self.use_attention:
            attn_out = self.attention(out, lengths)
            out = out + attn_out
        if self.shortcut_conv is not None:
            shortcut = self.shortcut_conv(x)
            out = out + shortcut
        else:
            out = out + x
        return out


class TCN_block(nn.Module):
    """Stack of TemporalBlocks with custom start dilation and exponential growth; attention on last layer only."""

    def __init__(self,
                 input_dimension: int,
                 depth: int,
                 kernel_size: int,
                 filters: int,
                 dropout: float = 0.3,
                 use_attention: bool = True,
                 num_attention_heads: int = 8,
                 attention_dropout: float = 0.1,
                 start_dilation: int = 1,
                 use_depthwise_separable: bool = False,
                 attention_on_last_only: bool = True):
        super(TCN_block, self).__init__()
        if attention_on_last_only and use_attention:
            first_use_attn = depth == 1  # 只有一层时，first_block 就是“跨度最大”
            last_only_attn = True
        else:
            first_use_attn = use_attention
            last_only_attn = False

        self.first_block = TemporalBlock(
            in_channels=input_dimension,
            out_channels=filters,
            kernel_size=kernel_size,
            dilation=start_dilation,
            dropout=dropout,
            use_attention=first_use_attn,
            num_attention_heads=num_attention_heads,
            attention_dropout=attention_dropout,
            use_depthwise_separable=use_depthwise_separable
        )

        self.blocks = nn.ModuleList([
            TemporalBlock(
                in_channels=filters,
                out_channels=filters,
                kernel_size=kernel_size,
                dilation=start_dilation * (2 ** (i + 1)),
                dropout=dropout,
                use_attention=use_attention and (not last_only_attn or i == depth - 2),
                num_attention_heads=num_attention_heads,
                attention_dropout=attention_dropout,
                use_depthwise_separable=use_depthwise_separable
            )
            for i in range(depth - 1)
        ])

    def forward(self, input_layer: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = self.first_block(input_layer, lengths)
        for block in self.blocks:
            x = block(x, lengths)
        return x


class GatedFusion(nn.Module):
    """Gated fusion of multi-scale branch outputs."""

    def __init__(self, num_branches: int, channels: int):
        super(GatedFusion, self).__init__()
        self.gate_net = nn.Sequential(
            nn.Conv1d(channels * num_branches, channels, kernel_size=1),
            nn.GELU(),
            nn.Conv1d(channels, num_branches, kernel_size=1),
            nn.Softmax(dim=1)
        )
        self.fusion_conv = nn.Conv1d(channels * num_branches, channels, kernel_size=1)

    def forward(self, features_list: List[torch.Tensor]) -> torch.Tensor:
        concat_features = torch.cat(features_list, dim=1)
        gate_weights = self.gate_net(concat_features)
        stacked = torch.stack(features_list, dim=1)
        gate_weights = gate_weights.unsqueeze(2)
        weighted_sum = (stacked * gate_weights).sum(dim=1)
        fused = self.fusion_conv(concat_features)
        return fused + weighted_sum


class MultiScaleBranch(nn.Module):
    """Multiple TCN branches with different start dilations, fused by GatedFusion."""

    def __init__(self, 
                 in_channels: int, 
                 out_channels: int, 
                 kernel_size: int,
                 dilations: List[int],
                 depth: int = 3,
                 dropout: float = 0.3,
                 use_attention: bool = True,
                 num_attention_heads: int = 8,
                 attention_dropout: float = 0.1,
                 use_depthwise_separable: bool = False):
        super(MultiScaleBranch, self).__init__()
        self.num_branches = len(dilations)
        self.branches = nn.ModuleList([
            TCN_block(
                input_dimension=in_channels,
                depth=depth,
                kernel_size=kernel_size,
                filters=out_channels,
                dropout=dropout,
                use_attention=use_attention,
                num_attention_heads=num_attention_heads,
                attention_dropout=attention_dropout,
                start_dilation=dilation,
                use_depthwise_separable=use_depthwise_separable
            )
            for dilation in dilations
        ])
        
        self.gated_fusion = GatedFusion(self.num_branches, out_channels)
        self.scale = nn.Parameter(torch.ones(1))

    def forward(self, x: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        outputs = [branch(x, lengths) for branch in self.branches]
        out = self.gated_fusion(outputs)
        return out * self.scale

class block(nn.Module):
    """EEG特征提取模块：输入[B, C, T]，输出[B, Filters, T]"""
    def __init__(self, 
                 num_channels: int = 64,
                 seq_length: int = 32,
                 num_filters: int = 32,
                 kernel_size: int = 3,
                 tcn_depth: int = 3,
                 dropout: float = 0.3,
                 use_attention: bool = True,
                 num_attention_heads: int = 8,
                 attention_dropout: float = 0.1,
                 use_depthwise_separable: bool = False,
                 dilations: Optional[List[int]] = None):
        super(block, self).__init__()
        if dilations is not None:
            dilations = list(dilations)
        else:
            dilations = [1, 2, 4] if seq_length <= 16 else [1, 2, 4, 8]
        
        self.spatial_proj = nn.Conv1d(num_channels, num_filters, kernel_size=1, padding=0)
        self.norm_proj = LayerNorm1d(num_filters)
        self.ms_tcn = MultiScaleBranch(
            in_channels=num_filters,
            out_channels=num_filters,
            kernel_size=kernel_size,
            dilations=dilations,
            depth=tcn_depth,
            dropout=dropout,
            use_attention=use_attention,
            num_attention_heads=num_attention_heads,
            attention_dropout=attention_dropout,
            use_depthwise_separable=use_depthwise_separable
        )
        self.init_weights()

    def init_weights(self):
        nn.init.kaiming_uniform_(self.spatial_proj.weight, mode="fan_in", nonlinearity="relu")
        if self.spatial_proj.bias is not None:
            nn.init.constant_(self.spatial_proj.bias, 0)

    def forward(self, x: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        if x.dim() != 3:
            raise ValueError(f"Expected input of shape [B, C, T], got {x.shape}")
        
        x = self.spatial_proj(x)
        x = self.norm_proj(x)
        features = self.ms_tcn(x, lengths)
        return features


def create_model(
    num_channels: int = 64,
    seq_length: int = 32,
    num_filters: int = 32,
    kernel_size: int = 3,
    tcn_depth: int = 3,
    dropout: float = 0.3,
    use_attention: bool = True,
    num_attention_heads: int = 8,
    attention_dropout: float = 0.1,
    use_depthwise_separable: bool = False,
):
    """Factory for TCN block with optional attention."""
    return block(
        num_channels=num_channels,
        seq_length=seq_length,
        num_filters=num_filters,
        kernel_size=kernel_size,
        tcn_depth=tcn_depth,
        dropout=dropout,
        use_attention=use_attention,
        num_attention_heads=num_attention_heads,
        attention_dropout=attention_dropout,
        use_depthwise_separable=use_depthwise_separable
    )


