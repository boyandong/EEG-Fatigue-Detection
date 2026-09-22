"""Spectral estimation. Dataset-agnostic.

All PSD and band parameters come from a config dict; nothing is hard-coded here.
The only exported function that matters is `band_powers`, which returns one band-power
vector per epoch. It never z-scores, never normalises by recording statistics, and never
touches absolute broadband scale beyond what a band power inherently is.

See SCIENTIFIC_SPEC.md sections 5.2, 6.1 and 15 for why.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import welch


@dataclass(frozen=True)
class SpectralConfig:
    method: str
    window: str
    nperseg: int
    noverlap: int
    nfft: int
    detrend: str
    scaling: str
    average: str
    integration: str
    band_bin_rule: str
    bands_hz: dict[str, tuple[float, float]]
    analysis_band_hz: tuple[float, float]
    total_band_definition: str
    numerical_epsilon_uv2: float

    @staticmethod
    def from_dict(cfg: dict) -> "SpectralConfig":
        """Build from the dataset config.

        `analysis_band_hz` is an EEG-level property (the integration range), while the rest
        are PSD-level. Both are read explicitly and a clear error is raised if either block
        is missing a required key, so a config typo cannot silently change the spectrum.
        """
        s = cfg["spectral"]
        e = cfg["eeg"]

        def need(block: dict, key: str, block_name: str):
            if key not in block or block[key] is None:
                raise KeyError(f"config {block_name}.{key} is required but missing/None")
            return block[key]

        return SpectralConfig(
            method=need(s, "method", "spectral"),
            window=need(s, "window", "spectral"),
            nperseg=int(need(s, "nperseg", "spectral")),
            noverlap=int(need(s, "noverlap", "spectral")),
            nfft=int(need(s, "nfft", "spectral")),
            detrend=need(s, "detrend", "spectral"),
            scaling=need(s, "scaling", "spectral"),
            average=need(s, "average", "spectral"),
            integration=need(s, "integration", "spectral"),
            band_bin_rule=need(s, "band_bin_rule", "spectral"),
            bands_hz={k: tuple(v) for k, v in need(s, "bands_hz", "spectral").items()},
            analysis_band_hz=tuple(need(e, "analysis_band_hz", "eeg")),
            total_band_definition=need(s, "total_band_definition", "spectral"),
            numerical_epsilon_uv2=float(need(s, "numerical_epsilon_uv2", "spectral")),
        )

    def describe(self) -> dict:
        """Everything that must reach provenance."""
        return {
            "method": self.method, "window": self.window, "nperseg": self.nperseg,
            "noverlap": self.noverlap, "nfft": self.nfft, "detrend": self.detrend,
            "scaling": self.scaling, "average": self.average, "integration": self.integration,
            "band_bin_rule": self.band_bin_rule,
            "bands_hz": {k: list(v) for k, v in self.bands_hz.items()},
            "analysis_band_hz": list(self.analysis_band_hz),
            "total_band_definition": self.total_band_definition,
            "numerical_epsilon_uv2": self.numerical_epsilon_uv2,
            "units_in": "uV", "units_band_power": "uV^2",
        }


def psd(epochs: np.ndarray, sfreq: float, cfg: SpectralConfig) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD of every epoch.

    Parameters
    ----------
    epochs : (n_epochs, n_channels, n_times) in uV
    Returns
    -------
    freqs : (n_freqs,), psd : (n_epochs, n_channels, n_freqs)
    """
    if epochs.ndim != 3:
        raise ValueError(f"expected (epochs, channels, times), got {epochs.shape}")
    if cfg.method != "welch":
        raise ValueError(f"unsupported psd method {cfg.method!r}")
    freqs, p = welch(
        epochs, fs=sfreq, window=cfg.window, nperseg=cfg.nperseg, noverlap=cfg.noverlap,
        nfft=cfg.nfft, detrend=cfg.detrend, scaling=cfg.scaling, axis=-1, average=cfg.average,
    )
    return freqs, p


def band_mask(freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Strict [lo, hi] inclusive inclusion rule, fixed in config."""
    return (freqs >= lo) & (freqs <= hi)


def integrate_band(p: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Trapezoid integration over [lo, hi]; returns array shaped like p[..., 0]."""
    m = band_mask(freqs, lo, hi)
    if not m.any():
        raise ValueError(f"no frequency bins inside [{lo}, {hi}] on this grid")
    return np.trapezoid(p[..., m], freqs[m], axis=-1)


def band_powers(epochs: np.ndarray, sfreq: float, cfg: SpectralConfig
                ) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Band powers per epoch/channel.

    Returns
    -------
    bands : {band_name: (n_epochs, n_channels)} in uV^2
    freqs : (n_freqs,)
    """
    freqs, p = psd(epochs, sfreq, cfg)
    out = {}
    for name, (lo, hi) in cfg.bands_hz.items():
        out[name] = integrate_band(p, freqs, lo, hi)
    if cfg.total_band_definition == "theta + alpha + beta":
        out["total_4_30"] = out["theta"] + out["alpha"] + out["beta"]
    else:
        raise ValueError(f"unsupported total_band_definition {cfg.total_band_definition!r}")
    return out, freqs


def verify_composition_identity(bands: dict[str, np.ndarray], rtol: float = 1e-12) -> dict:
    """q_theta + q_alpha + q_beta == 1 must hold exactly by construction."""
    total = bands["total_4_30"]
    if not np.all(total > 0):
        raise ValueError("non-positive total band power encountered")
    q = {b: bands[b] / total for b in ("theta", "alpha", "beta")}
    s = q["theta"] + q["alpha"] + q["beta"]
    return {
        "max_abs_deviation_from_one": float(np.max(np.abs(s - 1.0))),
        "identity_holds": bool(np.allclose(s, 1.0, rtol=rtol, atol=rtol)),
    }
