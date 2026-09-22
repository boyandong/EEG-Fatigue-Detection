"""Phase 1.5 windowing framework.

Turns the frozen mechanism_v1 extractor into a multi-resolution estimator so that
within-session estimator stability can be measured.

CRITICAL DISCIPLINE (SCIENTIFIC_SPEC.md, and Phase 1.5 brief sections 6 and 9):

  * Every window is computed by the FULL chain, independently, from raw epochs:
        window epochs -> band powers -> S_{e,c} -> ROI median -> window M_r, J_r
    A window value is NEVER derived from a full-session value.
  * Windows for a given duration are DISJOINT contiguous blocks from the start of the
    recording, in recording order. Epochs are never randomly scattered: a real device
    records continuous EEG.
  * Overlap is never permitted just to reach a target n. Sessions that cannot yield two
    disjoint windows at a duration are counted as ineligible and reported.

Window construction for duration k on a session with N epochs:
    W_1 = epochs[0 : k], W_2 = epochs[k : 2k], ...  W_{floor(N/k)}
Prefix/complement construction (used ONLY for the supplementary convergence analysis):
    prefix = epochs[0 : k], complement = epochs[k : N]
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import common as C
import data_ds004902 as D
import mechanism_features as MF
from roi import REGION_NAMES, load_roi_mapping
from spectral import SpectralConfig

# Duration grid. `full` = the whole available recording.
DURATIONS: tuple[tuple[str, int | None], ...] = (
    ("k4", 4), ("k8", 8), ("k15", 15), ("k30", 30), ("full", None),
)
EXPLORATORY = ("k4",)          # 16 s: exploratory only, J is crude with 4 observations
PRIMARY = ("k8", "k15", "k30", "full")

SESSION_FEATURES = ("M_F", "M_CT", "M_PO", "J_F", "J_CT", "J_PO")


def seconds(k: int | None) -> int | None:
    return None if k is None else k * 4


@dataclass
class Estimator:
    """Frozen mechanism_v1 estimator, reusable on any epoch subset."""

    roi: object
    spectral_cfg: SpectralConfig
    channel_names: list[str]
    sfreq: float
    eps: float

    @staticmethod
    def build(cfg: dict | None = None) -> "Estimator":
        ds = cfg or C.dataset_config()
        return Estimator(
            roi=load_roi_mapping(ds["roi"]),
            spectral_cfg=SpectralConfig.from_dict(ds),
            channel_names=[c for r in REGION_NAMES for c in ds["roi"][r]],
            sfreq=float(ds["eeg"]["target_sfreq_hz"]),
            eps=float(ds["spectral"]["numerical_epsilon_uv2"]),
        )

    def features(self, epochs: np.ndarray) -> dict:
        """M_r and J_r from an arbitrary epoch subset. Raises on <2 epochs."""
        n = epochs.shape[0]
        if n < 2:
            raise ValueError(f"need >= 2 epochs for J, got {n}")
        sf = MF.extract_session_features(epochs, self.channel_names, self.sfreq,
                                         self.roi, self.spectral_cfg)
        out = {f"M_{r}": sf.M[r] for r in REGION_NAMES}
        out.update({f"J_{r}": sf.J[r] for r in REGION_NAMES})
        out["n_epochs"] = n
        return out

    def slowing_series(self, epochs: np.ndarray) -> dict[str, np.ndarray]:
        """Per-epoch ROI-aggregated slowing index S_{e,r} (median over the ROI's channels).

        This is the series the Phase 1.75 dynamic observables are computed from. Epoch order
        is preserved; the channel reduction (median) happens before any time aggregation, and
        the ROI median is applied to S, never to raw power.
        """
        import mechanism_features as MF  # local import keeps this module import-light
        from spectral import band_powers
        bands, _ = band_powers(epochs, self.sfreq, self.spectral_cfg)
        S = MF.slowing_index(bands, self.eps)
        idx = self.roi.indices(self.channel_names)
        return {r: np.median(S[:, idx[r]], axis=1) for r in REGION_NAMES}

    def dynamic_features(self, epochs: np.ndarray) -> dict:
        """M, J, V, D, J_res for one epoch window (Phase 1.75)."""
        import dynamic_mechanism as DM
        return DM.dynamic_features(self.slowing_series(epochs))

    def window_series(self, epochs: np.ndarray, k: int) -> list[dict]:
        """Disjoint contiguous k-epoch windows, in recording order. No overlap ever."""
        n = epochs.shape[0]
        n_win = n // k
        return [{**self.features(epochs[i * k:(i + 1) * k]), "window_index": i, "start_epoch": i * k}
                for i in range(n_win)]

    def n_disjoint(self, n_epochs: int, k: int) -> int:
        return n_epochs // k


def load_session_epochs(subject: str, session: str, est: Estimator):
    """Return (epochs, provenance) for one session, read fresh from the .set file."""
    cfg = C.dataset_config()
    manifest = C.read_csv(C.OUTPUTS / "manifests" / "eeg_eyesopen_manifest.csv")
    row = next((r for r in manifest if r["subject"] == subject and r["session"] == session), None)
    if row is None:
        raise KeyError(f"{subject} {session} not in the eyes-open manifest")
    path = C.resolve(cfg["paths"]["eeg_preprocessed_dir"]) / row["file"]
    rec = D.make_recording(path, est.channel_names, est.sfreq)
    return rec.epochs, {"file": row["file"], "set_sha256": row.get("set_sha256", ""),
                        "eye_state_verdict": row["eye_state_verdict"],
                        "n_epochs": int(rec.epochs.shape[0])}


def cohort_subjects() -> list[str]:
    """All subjects with both sessions admissible (no PVT requirement)."""
    manifest = C.read_csv(C.OUTPUTS / "manifests" / "eeg_eyesopen_manifest.csv")
    by: dict[str, set] = {}
    for r in manifest:
        by.setdefault(r["subject"], set()).add(r["session"])
    return sorted(s for s, v in by.items() if {"ses-1", "ses-2"} <= v)


def session_pairs() -> list[tuple[str, str, str]]:
    """(subject, condition, session_id) for every admissible session of every paired subject."""
    out = []
    for s in cohort_subjects():
        out.append((s, "NS", "ses-1"))
        out.append((s, "SD", "ses-2"))
    return out
