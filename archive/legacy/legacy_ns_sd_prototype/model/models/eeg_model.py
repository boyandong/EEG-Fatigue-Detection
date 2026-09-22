"""EEG model: attention -> MSCViT -> TCN -> FC. Ref: AGL-Net (driver fatigue)."""

from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from models.attention_block import frequency_attention_block, spatial_attention_block
from models.mscvit_block.mscvit import Block
from models.tcn_Block import block as TCN_block


class EEGModel(nn.Module):
    """Input [B, num_de_features, num_freq_bands, H, W] -> output [B, num_classes]."""
    
    def __init__(
        self,
        num_de_features: int = 16,
        num_freq_bands: int = 5,
        spatial_h: int = 14,
        spatial_w: int = 14,
        freq_reduction: int = 2,
        mscvit_blocks: int = 2,
        mscvit_dim: int = 64,
        mscvit_num_heads: int = 4,
        mscvit_mlp_ratio: float = 4.0,
        mscvit_sr_ratio: int = 2,
        mscvit_wt_levels: int = 2,
        mscvit_drop_rate: float = 0.1,
        mscvit_attn_drop_rate: float = 0.1,
        mscvit_drop_path_rate: float = 0.1,
        tcn_filters: int = 32,
        tcn_kernel_size: int = 3,
        tcn_depth: int = 3,
        tcn_dropout: float = 0.3,
        tcn_use_attention: bool = True,
        tcn_dilations: Optional[List[int]] = None,
        fc_hidden_dim: int = 128,
        num_classes: int = 2,
        fc_dropout: float = 0.5,
        use_batch_norm: bool = True,
        first_frame_only: bool = False,
    ):
        super(EEGModel, self).__init__()
        self.first_frame_only = first_frame_only
        self.num_de_features = num_de_features
        self.num_freq_bands = num_freq_bands
        self.spatial_h = spatial_h
        self.spatial_w = spatial_w

        self.freq_attention = frequency_attention_block(
            num_bands=num_freq_bands,
            reduction=freq_reduction
        )
        self.spatial_attention = spatial_attention_block(channel=num_freq_bands)

        self.mscvit_proj = nn.Conv2d(
            num_freq_bands, 
            mscvit_dim, 
            kernel_size=1, 
            stride=1, 
            padding=0
        )
        self.mscvit_norm = nn.LayerNorm(mscvit_dim) if use_batch_norm else nn.Identity()
        dpr = [x.item() for x in torch.linspace(0, mscvit_drop_path_rate, mscvit_blocks)]
        self.mscvit_blocks_list = nn.ModuleList([
            Block(
                dim=mscvit_dim,
                num_heads=mscvit_num_heads,
                mlp_ratio=mscvit_mlp_ratio,
                qkv_bias=True,
                qk_scale=None,
                drop=mscvit_drop_rate,
                attn_drop=mscvit_attn_drop_rate,
                drop_path=dpr[i],
                act_layer=nn.GELU,
                norm_layer=nn.LayerNorm,
                sr_ratio=mscvit_sr_ratio,
                layer=i+1,
                wt_levels=mscvit_wt_levels,
            )
            for i in range(mscvit_blocks)
        ])
        self.mscvit_to_seq = nn.Linear(mscvit_dim, 64)
        self.spatial_size = spatial_h * spatial_w
        self.spatial_aggregate = nn.Linear(self.spatial_size, 1)
        self.tcn = TCN_block(
            num_channels=64,
            seq_length=num_de_features,
            num_filters=tcn_filters,
            kernel_size=tcn_kernel_size,
            tcn_depth=tcn_depth,
            dropout=tcn_dropout,
            use_attention=tcn_use_attention,
            dilations=tcn_dilations,
        )
        self.flatten_dim = tcn_filters * num_de_features
        self.fc1 = nn.Linear(self.flatten_dim, fc_hidden_dim)
        self.fc1_first = nn.Linear(64, fc_hidden_dim)
        self.fc_norm = nn.LayerNorm(fc_hidden_dim) if use_batch_norm else nn.Identity()
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(fc_dropout)
        self.fc2 = nn.Linear(fc_hidden_dim, num_classes)
        
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=1.0)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d, nn.LayerNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
        nn.init.zeros_(self.fc2.weight)
        nn.init.zeros_(self.fc2.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B = x.shape[0]
        x_reshaped = x.view(B * self.num_de_features, self.num_freq_bands, self.spatial_h, self.spatial_w)
        x_attn = self.freq_attention(x_reshaped)
        x_attn = self.spatial_attention(x_attn)
        feat = self.mscvit_proj(x_attn)
        B_batch, C, H, W = feat.shape
        feat_seq = feat.flatten(2).permute(0, 2, 1)
        feat_seq = self.mscvit_norm(feat_seq)
        
        for mscvit_block in self.mscvit_blocks_list:
            feat_seq = mscvit_block(feat_seq, H, W)

        feat_seq = self.mscvit_to_seq(feat_seq)
        feat_aggregated = self.spatial_aggregate(feat_seq.permute(0, 2, 1))
        feat_seq_output = feat_aggregated.squeeze(-1).unsqueeze(1)
        de_seq_output = feat_seq_output.view(B, self.num_de_features, 64)

        if self.first_frame_only:
            first_frame = de_seq_output[:, 0, :]
            x = self.fc1_first(first_frame)
        else:
            tcn_input = de_seq_output.permute(0, 2, 1)
            tcn_output = self.tcn(tcn_input)
            tcn_flat = tcn_output.flatten(1)
            x = self.fc1(tcn_flat)
        x = self.fc_norm(x)
        x = self.relu(x)
        x = self.dropout(x)
        output = self.fc2(x)
        return output


def create_eeg_model(
    num_de_features: int = 16,
    num_freq_bands: int = 5,
    spatial_h: int = 14,
    spatial_w: int = 14,
    mscvit_blocks: int = 4,
    num_classes: int = 2,
    **kwargs,
) -> EEGModel:
    """Factory for EEGModel."""
    model = EEGModel(
        num_de_features=num_de_features,
        num_freq_bands=num_freq_bands,
        spatial_h=spatial_h,
        spatial_w=spatial_w,
        mscvit_blocks=mscvit_blocks,
        num_classes=num_classes,
        **kwargs
    )
    return model


if __name__ == "__main__":
    model = create_eeg_model(
        num_de_features=16, num_freq_bands=5, spatial_h=14, spatial_w=14,
        mscvit_blocks=4, num_classes=2,
    )
    x = torch.randn(2, 16, 5, 14, 14)
    out = model(x)
    print(f"Input {x.shape} -> Output {out.shape}")
    n = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n:,}")
