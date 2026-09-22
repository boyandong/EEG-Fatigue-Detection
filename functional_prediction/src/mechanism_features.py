"""Dataset-agnostic mechanism feature extraction.

This module knows nothing about ds004902. It consumes a common EEG representation:

    epochs        (n_epochs, n_channels, n_times)  uV
    channel_names list[str]                        length n_channels
    sfreq         float
    roi_mapping   RoiMapping
    spectral_cfg  SpectralConfig

and produces the frozen six coordinates plus everything needed to audit them.

FROZEN DEFINITIONS (SCIENTIFIC_SPEC.md sections 5.2, 7, 8, 9)

    S_{e,c} = sqrt(2/3) * [ ln(P_theta+e) - 0.5*( ln(P_alpha+e) + ln(P_beta+e) ) ]
            = sqrt(2/3) * ln( P_theta / sqrt(P_alpha * P_beta) )

    S_{e,r} = median_{c in R_r} S_{e,c}                  <- channel aggregation SECOND
    M_r     = mean_e S_{e,r}
    J_r     = sample SD_e (S_{e,r})   (ddof=1)           <- time aggregation THIRD

    Delta M_r     = M^SD_r - M^NS_r
    Delta logJ_r  = ln( (J^SD_r + eps) / (J^NS_r + eps) )

Order is frozen: log/log-ratio -> channel reduce -> time reduce.
Forbidden: log(mean(P)), log(mean(P_t)/mean(P_a)), session-averaging power before the ratio.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from roi import REGION_NAMES, RoiMapping
from spectral import SpectralConfig, band_powers, verify_composition_identity

SQRT_2_OVER_3 = float(np.sqrt(2.0 / 3.0))  # 0.816496580927726


@dataclass
class SessionFeatures:
    """Per-session output of the mechanism extractor."""

    n_epochs: int
    n_channels_per_region: dict[str, int]
    M: dict[str, float]                      # mean slowing per region
    J: dict[str, float]                      # temporal instability per region (sample SD)
    audit: dict


def slowing_index(bands: dict[str, np.ndarray], eps: float) -> np.ndarray:
    """S_{e,c} = sqrt(2/3) * [ ln(P_t+e) - 0.5*( ln(P_a+e) + ln(P_b+e) ) ].

    Parameters
    ----------
    bands : {'theta','alpha','beta'} each (n_epochs, n_channels) in uV^2
    eps   : floor added inside each log; must be tiny and is audited by the caller
    """
    lt = np.log(bands["theta"] + eps)
    la = np.log(bands["alpha"] + eps)
    lb = np.log(bands["beta"] + eps)
    return SQRT_2_OVER_3 * (lt - 0.5 * (la + lb))


def epsilon_hits(bands: dict[str, np.ndarray], eps: float) -> dict:
    """Count band powers at or below the log floor. Reported, never absorbed silently."""
    hits = {b: int(np.sum(bands[b] <= eps)) for b in ("theta", "alpha", "beta")}
    total = int(np.prod(bands["theta"].shape)) * 3
    hits["total_values"] = total
    hits["fraction"] = float(sum(v for k, v in hits.items() if k != "total_values") / total) if total else 0.0
    return hits


def extract_session_features(
    epochs: np.ndarray,
    channel_names: list[str],
    sfreq: float,
    roi_mapping: RoiMapping,
    spectral_cfg: SpectralConfig,
    *,
    collect_epoch_series: bool = False,
) -> SessionFeatures:
    """Frozen mechanism_v1 extraction for ONE recording (one subject, one session).

    No recording-wise normalisation of any kind is applied to `epochs`.
    """
    if epochs.ndim != 3:
        raise ValueError(f"expected (epochs, channels, times), got {epochs.shape}")
    if epochs.shape[1] != len(channel_names):
        raise ValueError(f"channel axis {epochs.shape[1]} != {len(channel_names)} channel names")
    if not np.isfinite(epochs).all():
        raise ValueError("non-finite samples in epochs")

    region_idx = roi_mapping.indices(channel_names)

    bands, _ = band_powers(epochs, sfreq, spectral_cfg)
    identity = verify_composition_identity(bands)
    if not identity["identity_holds"]:
        raise ValueError(f"composition identity failed: {identity}")

    eps = spectral_cfg.numerical_epsilon_uv2
    S = slowing_index(bands, eps)                      # (n_epochs, n_channels)

    n_epochs = S.shape[0]
    M: dict[str, float] = {}
    J: dict[str, float] = {}
    series: dict[str, list[float]] = {}
    for r in REGION_NAMES:
        S_r = np.median(S[:, region_idx[r]], axis=1)   # channel aggregation SECOND
        M[r] = float(np.mean(S_r))
        if n_epochs >= 2:
            J[r] = float(np.std(S_r, ddof=1))          # time aggregation THIRD
        else:
            J[r] = float("nan")
        if collect_epoch_series:
            series[r] = [float(x) for x in S_r]

    audit = {
        "n_epochs": int(n_epochs),
        "n_channels_per_region": {r: int(len(region_idx[r])) for r in REGION_NAMES},
        "epsilon_hits": epsilon_hits(bands, eps),
        "composition_identity": identity,
        "S_min": float(np.min(S)), "S_max": float(np.max(S)),
        "S_mean": float(np.mean(S)),
        "bands_summary": {b: {"min": float(np.min(bands[b])), "max": float(np.max(bands[b])),
                              "mean": float(np.mean(bands[b]))} for b in ("theta", "alpha", "beta", "total_4_30")},
        "J_floor_needed": {r: bool(not np.isfinite(J[r]) or J[r] <= 0.0) for r in REGION_NAMES},
    }
    if collect_epoch_series:
        audit["epoch_series_S"] = series

    return SessionFeatures(n_epochs=n_epochs,
                           n_channels_per_region=audit["n_channels_per_region"],
                           M=M, J=J, audit=audit)


def delta_features(ns: SessionFeatures, sd: SessionFeatures, eps_j: float = 1.0e-12) -> dict:
    """Personal-relative representation: Delta M and Delta log J for the three regions."""
    out: dict[str, float] = {}
    details: dict[str, dict] = {}
    for r in REGION_NAMES:
        out[f"delta_M_{r}"] = sd.M[r] - ns.M[r]
        jn, js = ns.J[r], sd.J[r]
        used_floor = bool(not np.isfinite(jn) or not np.isfinite(js) or jn <= 0.0 or js <= 0.0)
        out[f"delta_logJ_{r}"] = (float(np.log((js + eps_j) / (jn + eps_j)))
                                  if used_floor else float(np.log(js / jn)))
        details[r] = {"NS_J": jn, "SD_J": js, "eps_J_used": used_floor,
                      "NS_M": ns.M[r], "SD_M": sd.M[r]}
    return {"features": out, "detail": details}


# --------------------------------------------------------------------------- reserved
def reserved_aperiodic_hook(*_args, **_kwargs):
    """RESERVED for a later mechanism-control analysis (SCIENTIFIC_SPEC section 13.1).

    Planned: decompose each PSD into aperiodic (1/f) and periodic components and test
    whether the theta-dominance signal is merely a broadband spectral-shape shift.
    Planned coordinates: Delta chi_F, Delta chi_CT, Delta chi_PO (chi = aperiodic exponent).

    NOT implemented in Phase 1. specparam / FOOOF is not installed and must not be imported.
    """
    raise NotImplementedError(
        "aperiodic decomposition is reserved for a later secondary block; "
        "it is deliberately not implemented in Phase 1"
    )
