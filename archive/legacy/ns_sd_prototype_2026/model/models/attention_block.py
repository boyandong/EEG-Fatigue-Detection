"""Frequency and spatial attention blocks for EEG features."""

import torch
import torch.nn as nn
import torch.nn.functional as F


class frequency_attention_block(nn.Module):
    """Channel-wise frequency attention with adaptive temperature."""

    def __init__(self, num_bands=5, reduction=2):
        super(frequency_attention_block, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Conv2d(num_bands, num_bands // reduction, kernel_size=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(num_bands // reduction, num_bands, kernel_size=1),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x):
        y = self.avg_pool(x)
        features = self.fc(y).squeeze(-1).squeeze(-1)
        temperature = torch.clamp(features.std(dim=1, keepdim=True) * 10, min=0.5, max=2.0)
        freq_weights = F.softmax(features / temperature, dim=1)
        return x * freq_weights.view(-1, features.size(1), 1, 1).expand_as(x)


class spatial_attention_block(nn.Module):
    """Learnable spatial embedding (1,1,H,W) multiplied with input."""

    def __init__(self, channel, spatial_shape=(32, 32)):
        super(spatial_attention_block, self).__init__()
        self.spatial_embed = nn.Parameter(torch.ones(1, 1, spatial_shape[0], spatial_shape[1]))

    def forward(self, x):
        b, f, ch, cw = x.size()
        if self.spatial_embed.shape[2] != ch or self.spatial_embed.shape[3] != cw:
            emb = F.interpolate(
                self.spatial_embed, size=(ch, cw), mode="bilinear", align_corners=False
            )
        else:
            emb = self.spatial_embed
        return x * emb
