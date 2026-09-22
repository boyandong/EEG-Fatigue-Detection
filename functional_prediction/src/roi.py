"""ROI definitions and channel-space validation.

Dataset-agnostic: knows only about channel NAMES. The mapping for ds004902 lives in
config/dataset_ds004902.yaml and is loaded by the caller.

The three ROIs are required to form an exact partition of the montage. Any deviation
(missing channel, duplicate, unmapped channel) raises rather than silently dropping data.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

REGION_NAMES = ("F", "CT", "PO")


@dataclass(frozen=True)
class RoiMapping:
    """Region -> ordered list of channel names, plus the canonical montage order."""

    regions: dict[str, list[str]]
    canonical_order: list[str]

    def validate(self, channel_names: list[str]) -> dict:
        """Check the partition against an actual montage. Returns an audit dict."""
        montage = list(channel_names)
        if len(set(montage)) != len(montage):
            raise ValueError(f"duplicate channel names in montage: {len(montage)} names, "
                             f"{len(set(montage))} unique")

        flat: list[str] = []
        for r in REGION_NAMES:
            if r not in self.regions:
                raise ValueError(f"region {r!r} missing from ROI mapping")
            flat.extend(self.regions[r])
        dupes = sorted({c for c in flat if flat.count(c) > 1})
        if dupes:
            raise ValueError(f"channel appears in more than one ROI: {dupes}")

        unmapped = sorted(set(flat) - set(montage))
        missing = sorted(set(montage) - set(flat))
        if unmapped:
            raise ValueError(f"ROI channels not present in montage: {unmapped}")
        if missing:
            raise ValueError(f"montage channels not assigned to any ROI: {missing}")

        return {
            "n_montage": len(montage),
            "region_sizes": {r: len(self.regions[r]) for r in REGION_NAMES},
            "total_roi_channels": len(flat),
            "exact_partition": sorted(flat) == sorted(montage),
            "region_indices": {r: [montage.index(c) for c in self.regions[r]] for r in REGION_NAMES},
        }

    def indices(self, channel_names: list[str]) -> dict[str, np.ndarray]:
        """Region -> integer column indices into an array ordered as `channel_names`."""
        self.validate(channel_names)
        return {r: np.array([channel_names.index(c) for c in self.regions[r]], dtype=int)
                for r in REGION_NAMES}


def load_roi_mapping(roi_cfg: dict) -> RoiMapping:
    regions = {r: list(roi_cfg[r]) for r in REGION_NAMES}
    canonical = [c for r in REGION_NAMES for c in regions[r]]
    return RoiMapping(regions=regions, canonical_order=canonical)
