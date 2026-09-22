"""PVT target psychometrics (Phase 1.75, Parts G-K).

This module studies the TARGET only. It never reads an EEG feature, and it produces no
EEG-to-behaviour number of any kind.

Why this is necessary (SCIENTIFIC_SPEC, Phase 1.75 part A):

    ln RT_obs(s) = ln RT_true(s) + eps_s
    Y_obs = Y_true + eps_SD - eps_NS
    Var(eps_Y) = Var(eps_SD) + Var(eps_NS)      (independent)

The change score is a difference of two noisy measurements, exactly as with the EEG delta.
If the target is unreliable, no model can be expected to predict it well, so the target's own
finite-trial uncertainty has to be quantified BEFORE any prediction is attempted.

Everything here is a **finite-trial sampling** quantity. It cannot capture day-to-day
variability, circadian change, or true within-person state variation, so the resulting
reliability coefficient is labelled an **approximate finite-trial reliability proxy**, never
test-retest reliability.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ------------------------------------------------------------------ target definitions
DELTA_NOTE = "Y > 0 means functional deterioration in both definitions"


def median_rt(rt: np.ndarray) -> float:
    rt = np.asarray(rt, dtype=float)
    return float(np.median(rt)) if rt.size else float("nan")


def response_speed(rt: np.ndarray) -> float:
    """Q = mean(1/RT) over trials."""
    rt = np.asarray(rt, dtype=float)
    rt = rt[rt > 0]
    return float(np.mean(1.0 / rt)) if rt.size else float("nan")


def y_median_rt(rt_ns: np.ndarray, rt_sd: np.ndarray) -> float:
    """Y_RT = ln( median(RT_SD) / median(RT_NS) ).  Y > 0 => slower => deterioration."""
    a, b = median_rt(rt_ns), median_rt(rt_sd)
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0 or b <= 0:
        return float("nan")
    return float(np.log(b / a))


def y_speed(rt_ns: np.ndarray, rt_sd: np.ndarray) -> float:
    """Y_speed = ln( Q_NS / Q_SD ) with Q = mean(1/RT).  Y > 0 => slower => deterioration."""
    a, b = response_speed(rt_ns), response_speed(rt_sd)
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0 or b <= 0:
        return float("nan")
    return float(np.log(a / b))


@dataclass
class SessionTrials:
    subject: str
    session: str
    rt: np.ndarray          # already filtered to 100..2000 ms
    n_raw_rows: int
    n_valid: int
    n_removed_out_of_range: int
    n_missing: int


@dataclass
class BootstrapResult:
    point: float
    se: float
    ci_low: float
    ci_high: float
    n_boot_used: int
    median_rt_ns: float
    median_rt_sd: float
    speed_ns: float
    speed_sd: float
    n_trials_ns: int
    n_trials_sd: int


def paired_trial_bootstrap(ns: SessionTrials, sd: SessionTrials, *,
                           n_boot: int = 5000, seed: int = 20260916) -> BootstrapResult:
    """Resample trials WITHIN each session, independently, and recompute both targets.

    The two sessions are separate strata: an SD trial can never stand in for an NS trial
    (that would destroy the pairing), so the resampling is within-session with replacement.
    Each replicate recomputes the median / speed for each session and then the paired target.
    """
    rng = np.random.default_rng(seed)
    a, b = ns.rt, sd.rt
    if a.size == 0 or b.size == 0:
        return BootstrapResult(float("nan"), float("nan"), float("nan"), float("nan"), 0,
                               median_rt(a), median_rt(b), response_speed(a), response_speed(b),
                               int(a.size), int(b.size))
    ia = rng.integers(0, a.size, size=(n_boot, a.size))
    ib = rng.integers(0, b.size, size=(n_boot, b.size))
    sa = a[ia]                       # (n_boot, n_a)
    sb = b[ib]
    med_a = np.median(sa, axis=1)
    med_b = np.median(sb, axis=1)
    y_rt = np.log(med_b / med_a)
    sp_a = np.mean(1.0 / sa, axis=1)
    sp_b = np.mean(1.0 / sb, axis=1)
    y_sp = np.log(sp_a / sp_b)

    point = y_median_rt(a, b)
    # SE is taken from the bootstrap distribution of the RT target; the speed target's SE is
    # returned separately by paired_trial_bootstrap_both.
    return BootstrapResult(
        point=point, se=float(np.std(y_rt, ddof=1)),
        ci_low=float(np.percentile(y_rt, 2.5)), ci_high=float(np.percentile(y_rt, 97.5)),
        n_boot_used=int(n_boot),
        median_rt_ns=median_rt(a), median_rt_sd=median_rt(b),
        speed_ns=response_speed(a), speed_sd=response_speed(b),
        n_trials_ns=int(a.size), n_trials_sd=int(b.size),
    )


def paired_trial_bootstrap_both(ns: SessionTrials, sd: SessionTrials, *,
                                n_boot: int = 5000, seed: int = 20260916) -> dict:
    """One resampling pass, both targets. Returns point estimates, SEs and 95% CIs."""
    rng = np.random.default_rng(seed)
    a, b = ns.rt, sd.rt
    out = {
        "n_trials_ns": int(a.size), "n_trials_sd": int(b.size),
        "median_rt_ns": median_rt(a), "median_rt_sd": median_rt(b),
        "speed_ns": response_speed(a), "speed_sd": response_speed(b),
        "Y_RT_point": y_median_rt(a, b), "Y_speed_point": y_speed(a, b),
        "n_boot_requested": n_boot,
    }
    if a.size == 0 or b.size == 0:
        out.update({"Y_RT_se": float("nan"), "Y_RT_ci_low": float("nan"), "Y_RT_ci_high": float("nan"),
                    "Y_speed_se": float("nan"), "Y_speed_ci_low": float("nan"),
                    "Y_speed_ci_high": float("nan"), "n_boot_used": 0})
        return out
    ia = rng.integers(0, a.size, size=(n_boot, a.size))
    ib = rng.integers(0, b.size, size=(n_boot, b.size))
    sa, sb = a[ia], b[ib]
    y_rt = np.log(np.median(sb, axis=1) / np.median(sa, axis=1))
    y_sp = np.log(np.mean(1.0 / sa, axis=1) / np.mean(1.0 / sb, axis=1))
    out.update({
        "Y_RT_se": float(np.std(y_rt, ddof=1)),
        "Y_RT_ci_low": float(np.percentile(y_rt, 2.5)),
        "Y_RT_ci_high": float(np.percentile(y_rt, 97.5)),
        "Y_speed_se": float(np.std(y_sp, ddof=1)),
        "Y_speed_ci_low": float(np.percentile(y_sp, 2.5)),
        "Y_speed_ci_high": float(np.percentile(y_sp, 97.5)),
        "n_boot_used": int(n_boot),
    })
    return out


def interleaved_split_half(rt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Odd-indexed vs even-indexed trials, preserving the time-on-task distribution.

    A first-half / second-half split would confound the split with PVT time-on-task drift,
    which is exactly what we must not do, so the interleaved split is the primary one.
    """
    rt = np.asarray(rt, dtype=float)
    return rt[0::2], rt[1::2]


def approximate_reliability(y: np.ndarray, se: np.ndarray) -> dict:
    """R_approx = max(0, 1 - sigma_eps^2 / s_Y^2).

    sigma_eps^2 = mean_i SE_i(Y)^2 is the finite-trial measurement-error variance;
    s_Y^2 = Var_i(Y) is the observed between-person variance of the change score.
    Labelled an APPROXIMATE FINITE-TRIAL RELIABILITY PROXY: the bootstrap sees only trial
    sampling noise, not day-to-day or circadian variability.
    """
    y = np.asarray(y, float); se = np.asarray(se, float)
    ok = np.isfinite(y) & np.isfinite(se)
    y, se = y[ok], se[ok]
    n = y.size
    if n < 3:
        return {"n": int(n), "s_Y_squared": float("nan"), "sigma_eps_squared": float("nan"),
                "R_approx": float("nan"), "label": "approximate finite-trial reliability proxy"}
    s2 = float(np.var(y, ddof=1))
    e2 = float(np.mean(se ** 2))
    r = max(0.0, 1.0 - e2 / s2) if s2 > 0 else float("nan")
    return {
        "n": int(n), "s_Y_squared": s2, "s_Y": float(np.sqrt(s2)),
        "sigma_eps_squared": e2, "sigma_eps": float(np.sqrt(e2)),
        "ratio_measurement_to_observed_variance": (e2 / s2) if s2 > 0 else float("nan"),
        "R_approx": r,
        "mean_SE": float(np.mean(se)), "median_SE": float(np.median(se)),
        "label": "approximate finite-trial reliability proxy",
        "caution": ("bootstrap captures only finite-trial sampling uncertainty; it cannot "
                    "estimate day-to-day, circadian or true within-person state variability"),
    }
