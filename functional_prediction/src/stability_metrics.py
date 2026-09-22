"""Phase 1.5 stability metrics.

Implements exactly the metric set required by the Phase 1.5 brief section 11, plus a
clearly-labelled ICC as a SECONDARY metric (section 12).

Deliberate vocabulary discipline:
  * We measure **within-session estimator stability**, i.e. agreement between feature values
    computed from different time parts of the SAME recording.
  * This is NOT test-retest reliability. There is no repeated session in the same state.
  * Disagreement conflates measurement noise, finite-sample error, and genuine
    within-session state drift. Phase 1.5 cannot separate them.

Agreement sources are always labelled explicitly:
  * `disjoint`           - equal-length, non-overlapping windows of one recording (PRIMARY)
  * `prefix_complement`  - first k epochs vs all remaining epochs (unequal length)
  * `accumulation`       - prefix_k vs full session; the prefix is CONTAINED in the full
                           value, so this is convergence, not independent agreement
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def safe_iqr(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return float("nan")
    q1, q3 = np.percentile(x, [25, 75])
    return float(q3 - q1)


def rank_stability(a: np.ndarray, b: np.ndarray) -> dict:
    """Spearman rho across paired observations."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 3 or len(np.unique(a)) < 2 or len(np.unique(b)) < 2:
        return {"n": int(a.size), "spearman_rho": float("nan"), "p_value": float("nan")}
    r = stats.spearmanr(a, b)
    return {"n": int(a.size), "spearman_rho": float(r.statistic), "p_value": float(r.pvalue)}


def absolute_disagreement(a: np.ndarray, b: np.ndarray) -> dict:
    """median |a-b| and the 90th percentile of |a-b|."""
    d = np.abs(np.asarray(a, float) - np.asarray(b, float))
    d = d[np.isfinite(d)]
    if d.size == 0:
        return {"n": 0, "median_abs_diff": float("nan"), "p90_abs_diff": float("nan"),
                "mean_abs_diff": float("nan")}
    return {"n": int(d.size),
            "median_abs_diff": float(np.median(d)),
            "p90_abs_diff": float(np.percentile(d, 90)),
            "mean_abs_diff": float(d.mean())}


def normalized_disagreement(a: np.ndarray, b: np.ndarray, scale_iqr: float) -> dict:
    """nMAE = median|a-b| / IQR(reference population). Never divides by zero."""
    ad = absolute_disagreement(a, b)
    if not np.isfinite(scale_iqr) or scale_iqr <= 0:
        return {**ad, "scale_iqr": float(scale_iqr), "nmae": None,
                "nmae_note": "reference IQR is zero or non-finite; ratio undefined and NOT computed"}
    return {**ad, "scale_iqr": float(scale_iqr), "nmae": float(ad["median_abs_diff"] / scale_iqr),
            "nmae_note": ""}


def bland_altman(a: np.ndarray, b: np.ndarray) -> dict:
    """Non-parametric agreement summary, because the differences are not Gaussian.

    Returns median difference, empirical 2.5-97.5 percentile limits, and the mean/SD-based
    classical limits of agreement for comparison only.
    """
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 3:
        return {"n": int(a.size)}
    d = a - b
    m = (a + b) / 2.0
    return {
        "n": int(a.size),
        "median_difference": float(np.median(d)),
        "empirical_loa_low": float(np.percentile(d, 2.5)),
        "empirical_loa_high": float(np.percentile(d, 97.5)),
        "classical_bias": float(d.mean()),
        "classical_loa_low": float(d.mean() - 1.96 * d.std(ddof=1)),
        "classical_loa_high": float(d.mean() + 1.96 * d.std(ddof=1)),
        "difference_sd": float(d.std(ddof=1)),
        "mean_of_pair_mean": float(m.mean()),
        "slope_diff_vs_mean": float(stats.linregress(m, d).slope) if m.size > 2 and m.std() > 0 else float("nan"),
        "pearson_diff_vs_mean_r": float(stats.pearsonr(m, d).statistic) if m.size > 2 and m.std() > 0 and d.std() > 0 else float("nan"),
    }


def icc_2_1(matrix: np.ndarray) -> dict:
    """ICC(2,1): two-way random effects, absolute agreement, single measurement.

    SECONDARY metric only. Here the "raters" are two time-windows of the same recording, so
    this is an estimator-agreement coefficient, NOT test-retest reliability.
    matrix: (n_subjects, 2) of paired window values.
    """
    m = np.asarray(matrix, float)
    m = m[np.isfinite(m).all(axis=1)]
    n, k = m.shape
    if n < 3 or k != 2:
        return {"n": int(n), "icc_2_1": float("nan"), "ci95": [float("nan")] * 2}
    grand = m.mean()
    ms_rows = k * ((m.mean(axis=1) - grand) ** 2).sum() / (n - 1)
    ms_cols = n * ((m.mean(axis=0) - grand) ** 2).sum() / (k - 1)
    ss_total = ((m - grand) ** 2).sum()
    ss_err = ss_total - (ms_rows * (n - 1)) - (ms_cols * (k - 1))
    ms_err = ss_err / ((n - 1) * (k - 1))
    denom = ms_rows + (k - 1) * ms_err + k * (ms_cols - ms_err) / n
    if denom <= 0:
        return {"n": int(n), "icc_2_1": float("nan"), "ci95": [float("nan")] * 2}
    icc = (ms_rows - ms_err) / denom
    # F-based 95% CI (Shrout & Fleiss 1979)
    f = ms_rows / ms_err if ms_err > 0 else np.nan
    try:
        f_lo = f / stats.f.ppf(0.975, n - 1, (n - 1) * (k - 1))
        f_hi = f * stats.f.ppf(0.975, (n - 1) * (k - 1), n - 1)
        lo = (f_lo - 1) / (f_lo + k - 1)
        hi = (f_hi - 1) / (f_hi + k - 1)
    except Exception:  # noqa: BLE001
        lo = hi = float("nan")
    return {"n": int(n), "icc_2_1": float(icc), "ci95": [float(lo), float(hi)],
            "icc_type": "ICC(2,1) two-way random, absolute agreement, single measurement",
            "caution": "windows are repetitions within one session, not independent sessions"}


def sign_stability(short: np.ndarray, reference: np.ndarray) -> dict:
    """P[sign(short) == sign(reference)] over paired observations, ignoring exact zeros."""
    s = np.asarray(short, float); r = np.asarray(reference, float)
    ok = np.isfinite(s) & np.isfinite(r)
    s, r = s[ok], r[ok]
    if s.size == 0:
        return {"n": 0, "sign_agreement": float("nan"), "n_zero_in_short": 0, "n_zero_in_reference": 0}
    nz_s = s != 0
    nz_r = r != 0
    both = nz_s & nz_r
    agree = float((np.sign(s[both]) == np.sign(r[both])).mean()) if both.sum() else float("nan")
    return {"n": int(s.size), "n_comparable": int(both.sum()),
            "sign_agreement": agree,
            "n_zero_in_short": int((~nz_s).sum()), "n_zero_in_reference": int((~nz_r).sum())}


def aggregate_window_repetitions(values: list[np.ndarray]) -> dict:
    """Summarise a per-window metric across every window of every recording.

    values: list of per-recording arrays, one entry per disjoint window.
    Reports the mean/median and the spread ACROSS recordings of the within-recording metric,
    plus the fraction of recordings that pass a given agreement bar.
    """
    arrs = [np.asarray(v, float) for v in values if np.size(v) > 0]
    if not arrs:
        return {"n_recordings": 0}
    flat = np.concatenate(arrs)
    return {
        "n_recordings": len(arrs),
        "median_of_recording_values": float(np.median(flat)),
        "p25": float(np.percentile(flat, 25)),
        "p75": float(np.percentile(flat, 75)),
        "min": float(flat.min()), "max": float(flat.max()),
    }
