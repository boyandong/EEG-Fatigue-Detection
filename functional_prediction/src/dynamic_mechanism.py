"""Phase 1.75 dynamic-mechanism decomposition.

mechanism_v1 is NOT modified. This module adds a separate, parallel representation:

    mechanism_v1_1_dynamic_audit

Measurement model (SCIENTIFIC_SPEC.md, updated in Phase 1.75):

    S_{e,r} = mu_r + g_r(t_e) + u_{e,r} + eta_{e,r}

      mu_r    tonic level of that recording
      g_r(t)  slow drift / recording adaptation / slow state change
      u_{e,r} local epoch-to-epoch fluctuation
      eta     measurement noise

Observables on the SAME epoch series S_{e,r}:

    M_r      = mean_e S                        -> mu + mean(g)
    J_r      = SD_e S            (ddof=1)      -> total within-recording temporal dispersion
                                                  J^2 = Var[g + u + eta]
    V_r      = sqrt( sum (S_{e+1}-S_e)^2 / (2(N-1)) )   -> local volatility proxy
                                                  ~= SD of S under i.i.d.; insensitive to slow drift
    D_r      = slope of S on centred time tau  -> slow linear drift diagnostic
    J_res_r  = SD of the linearly detrended S  -> dispersion after removing linear drift

IMPORTANT INTERPRETIVE LIMITS (binding on any report built from this module):
  * J is NOT "vigilance instability". It is a MIXTURE of slow drift, local fluctuation and
    measurement noise. Phase 1.5 cannot separate them.
  * V is a "local epoch-to-epoch spectral volatility proxy". It is NOT a validated biomarker.
  * D and J_res are DIAGNOSTICS, not primary mechanism features.
  * Differencing amplifies measurement noise: Var(eta_{e+1} - eta_e) = 2 sigma_eta^2. That is
    exactly why V must pass the same target-blind stability audit as J before it can replace it.
  * Epoch order is preserved everywhere. The series is never shuffled.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from roi import REGION_NAMES

# Names of every observable this module produces, per region.
DYNAMIC_OBSERVABLES = ("M", "J", "V", "Jres", "D")


def centred_time(n: int) -> np.ndarray:
    """tau_e = (e - (N+1)/2) / N for e = 1..N, so tau is centred and spans about (-0.5, 0.5).

    With this normalisation the fitted slope d_r is the TOTAL change of S across the window,
    not a per-epoch rate, which makes D_r comparable across window lengths.
    """
    e = np.arange(1, n + 1, dtype=np.float64)
    return (e - (n + 1) / 2.0) / n


def local_volatility(S: np.ndarray) -> float:
    """V = sqrt( sum_{e=1}^{N-1} (S_{e+1}-S_e)^2 / (2(N-1)) ).

    The 1/2 makes V an unbiased estimate of SD(S) when S is i.i.d.: under i.i.d. sampling
    E[(S_{e+1}-S_e)^2] = 2 sigma^2, so V ~= sigma. It is therefore on the SAME SCALE as J,
    which is what makes a direct J vs V comparison meaningful, yet it responds to adjacent
    differences rather than to total dispersion, so a slow monotone ramp contributes far less.
    Requires at least 2 epochs (one difference).
    """
    S = np.asarray(S, dtype=np.float64)
    n = S.size
    if n < 2:
        return float("nan")
    d = np.diff(S)
    return float(np.sqrt(np.sum(d * d) / (2.0 * (n - 1))))


@dataclass
class DriftFit:
    intercept: float
    slope: float                 # total change of S across the window
    slope_se: float              # naive OLS standard error of the slope
    slope_t: float
    residual_sd: float           # J_res, ddof = N-2
    residual: np.ndarray


def drift_fit(S: np.ndarray) -> DriftFit:
    """OLS of S on centred time tau. Returns D_r = slope and J_res = SD of the residual."""
    S = np.asarray(S, dtype=np.float64)
    n = S.size
    if n < 3:
        return DriftFit(float("nan"), float("nan"), float("nan"), float("nan"), float("nan"),
                        np.full(n, np.nan))
    tau = centred_time(n)
    st = float(np.sum(tau * tau))
    slope = float(np.sum(tau * (S - S.mean())) / st) if st > 0 else float("nan")
    intercept = float(S.mean())
    resid = S - intercept - slope * tau
    dof = n - 2
    rss = float(np.sum(resid * resid))
    resid_sd = float(np.sqrt(rss / dof)) if dof > 0 else float("nan")
    se = float(resid_sd / np.sqrt(st)) if st > 0 and np.isfinite(resid_sd) else float("nan")
    t = float(slope / se) if se and np.isfinite(se) and se > 0 else float("nan")
    return DriftFit(intercept, slope, se, t, resid_sd, resid)


def dynamic_features(S_by_region: dict[str, np.ndarray]) -> dict:
    """All observables for one window, from the per-epoch ROI time series S_{e,r}.

    `S_by_region[r]` must be the ROI-aggregated series (median over channels) in EPOCH ORDER.
    """
    out: dict[str, float] = {}
    for r in REGION_NAMES:
        S = np.asarray(S_by_region[r], dtype=np.float64)
        n = S.size
        out[f"M_{r}"] = float(S.mean()) if n else float("nan")
        out[f"J_{r}"] = float(S.std(ddof=1)) if n >= 2 else float("nan")
        out[f"V_{r}"] = local_volatility(S)
        fit = drift_fit(S)
        out[f"D_{r}"] = fit.slope
        out[f"Dse_{r}"] = fit.slope_se
        out[f"Dt_{r}"] = fit.slope_t
        out[f"Jres_{r}"] = fit.residual_sd
    return out


def delta_log(short: float, reference: float, eps: float = 1e-12) -> float:
    """ln(a/b) with a floor used only if a value is non-positive; floor use is reported."""
    if not (np.isfinite(short) and np.isfinite(reference)):
        return float("nan")
    if short > 0 and reference > 0:
        return float(np.log(short / reference))
    return float(np.log((short + eps) / (reference + eps)))


def decomposition_identity(S: np.ndarray) -> dict:
    """Explicitly show that J is a mixture, not a pure fluctuation measure.

    Computes the variance account: total, that explained by the linear drift, and the residual.
    """
    S = np.asarray(S, dtype=np.float64)
    n = S.size
    if n < 3:
        return {}
    fit = drift_fit(S)
    tot = float(S.var(ddof=1))
    res = float(fit.residual.var(ddof=2)) if n > 2 else float("nan")
    return {
        "var_total": tot,
        "var_residual_after_linear_drift": res,
        "fraction_of_variance_from_linear_drift": (1.0 - res / tot) if tot > 0 else float("nan"),
        "slope": fit.slope,
        "slope_t": fit.slope_t,
        "n_epochs": int(n),
    }
