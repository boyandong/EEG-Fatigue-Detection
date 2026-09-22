"""Phase 2 nested cross-validated ridge, with the full frozen protocol inside the loop.

SCIENTIFIC_SPEC.md section 18. Everything here is fixed before any fitting:

  outer   : LOSO over the 29-subject cohort; train on 28, predict the held-out subject
  inner   : LOSO inside those 28 to choose lambda from {0.01, 0.1, 1, 10, 100} by inner MSE
  scaling : centering and scaling computed on the OUTER TRAINING subjects only
  endpoint: Q2_skill = 1 - SSE_model / SSE_M0, with M0 = outer-train mean of Y

Whole-data mean/std is never computed, and no feature is ever selected or dropped.

The permutation test must re-run the WHOLE pipeline for every replicate, so the inner loop is
written with an SVD-based ridge fit (numpy only, no BLAS oversubscription) rather than sklearn.
The SVD solution equals the ridgeless/ridge least-squares solution; this is verified against
sklearn Ridge in tests/test_phase2_ridge.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ALPHA_GRID = (0.01, 0.1, 1.0, 10.0, 100.0)


def ridge_fit_predict(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, alpha: float
                      ) -> tuple[np.ndarray, np.ndarray]:
    """Ridge with an unpenalised intercept, via SVD of the centred training matrix.

    Returns (predictions on Xte, training coefficients including intercept).
    The solution minimises ||ytr - Xtr@w - b||^2 + alpha*||w||^2 with `w` NOT including the
    intercept, which is the same convention as sklearn.linear_model.Ridge.
    """
    Xtr = np.asarray(Xtr, dtype=np.float64)
    ytr = np.asarray(ytr, dtype=np.float64)
    Xte = np.asarray(Xte, dtype=np.float64)
    if Xtr.ndim == 1:
        Xtr = Xtr[:, None]
    if Xte.ndim == 1:
        Xte = Xte[:, None]

    xm = Xtr.mean(axis=0)
    ym = ytr.mean()
    Xc = Xtr - xm
    yc = ytr - ym

    # SVD ridge: w = V diag(s/(s^2+a)) U^T y. Terms with s == 0 vanish, which is the correct
    # pseudo-inverse behaviour at rank deficiency.
    U, s, Vt = np.linalg.svd(Xc, full_matrices=False)
    if alpha <= 0:
        # ridgeless limit handled by an explicit pseudo-inverse with a relative cutoff
        cutoff = np.finfo(float).eps * max(Xc.shape)
        inv = np.array([1.0 / si if si > cutoff else 0.0 for si in s])
    else:
        inv = s / (s * s + alpha)
    w = Vt.T @ (inv * (U.T @ yc))
    b = ym - xm @ w
    return Xte @ w + b, np.concatenate([[b], w])


def standardise(Xtr: np.ndarray, Xte: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Centre and scale using TRAINING statistics only. Zero-variance columns are left as-is."""
    mu = Xtr.mean(axis=0)
    sd = Xtr.std(axis=0, ddof=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (Xtr - mu) / sd, (Xte - mu) / sd


def inner_select_alpha(Xtr: np.ndarray, ytr: np.ndarray, grid=ALPHA_GRID) -> tuple[float, dict]:
    """LOSO inside the training set; pick the alpha with the smallest inner MSE.

    The inner folds standardise on their own inner-training part, so no information from the
    inner-validation subject reaches the scaling either.
    """
    n = Xtr.shape[0]
    if n < 3:
        return float(grid[0]), {"n_inner": int(n), "inner_mse": {float(a): np.nan for a in grid}}
    errs = {float(a): [] for a in grid}
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        Xa, Xb = standardise(Xtr[mask], Xtr[~mask])
        for a in grid:
            pred, _ = ridge_fit_predict(Xa, ytr[mask], Xb, float(a))
            errs[float(a)].append(float(np.mean((pred - ytr[~mask]) ** 2)))
    mse = {a: float(np.mean(v)) for a, v in errs.items()}
    best = min(grid, key=lambda a: (mse[float(a)], float(a)))   # ties -> smaller alpha
    return float(best), {"n_inner": int(n), "inner_mse": mse}


@dataclass
class CvResult:
    y: np.ndarray
    pred: np.ndarray
    pred_m0: np.ndarray
    alphas: np.ndarray
    subjects: list[str]
    q2_skill: float
    mae: float
    mae_m0: float
    skill_mae: float
    spearman: float
    pearson: float
    sse_model: float
    sse_m0: float
    n: int


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy import stats
    if a.size < 3 or np.unique(a).size < 2 or np.unique(b).size < 2:
        return float("nan")
    return float(stats.spearmanr(a, b).statistic)


def nested_loso(X: np.ndarray, y: np.ndarray, subjects: list[str] | None = None,
                grid=ALPHA_GRID) -> CvResult:
    """Frozen nested LOSO. X is (n, p); y is (n,)."""
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = X.shape[0]
    if X.ndim == 1:
        X = X[:, None]
    pred = np.empty(n)
    pred_m0 = np.empty(n)
    alphas = np.empty(n)
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        Xa, Xb = standardise(X[mask], X[~mask])
        ytr = y[mask]
        alpha, _ = inner_select_alpha(Xa, ytr, grid)
        p, _ = ridge_fit_predict(Xa, ytr, Xb, alpha)
        pred[i] = float(p[0])
        pred_m0[i] = float(ytr.mean())
        alphas[i] = alpha
    sse_model = float(np.sum((y - pred) ** 2))
    sse_m0 = float(np.sum((y - pred_m0) ** 2))
    mae = float(np.mean(np.abs(y - pred)))
    mae_m0 = float(np.mean(np.abs(y - pred_m0)))
    from scipy import stats
    pear = float(stats.pearsonr(y, pred).statistic) if np.std(pred) > 0 else float("nan")
    return CvResult(y=y, pred=pred, pred_m0=pred_m0, alphas=alphas,
                    subjects=list(subjects) if subjects else [str(i) for i in range(n)],
                    q2_skill=1.0 - sse_model / sse_m0 if sse_m0 > 0 else float("nan"),
                    mae=mae, mae_m0=mae_m0,
                    skill_mae=1.0 - mae / mae_m0 if mae_m0 > 0 else float("nan"),
                    spearman=_spearman(y, pred), pearson=pear,
                    sse_model=sse_model, sse_m0=sse_m0, n=n)


def permutation_null_q2(X: np.ndarray, y: np.ndarray, n_perm: int, seed: int,
                        grid=ALPHA_GRID, progress_every: int = 250,
                        verbose: bool = True) -> dict:
    """Subject-level permutation of Y, each replicate fully re-running the nested pipeline.

    Returns the observed Q2, the null distribution summary, and the one-sided p-value
        p = (1 + #{Q2_perm >= Q2_obs}) / (1 + B)
    A normal approximation to the null is also reported, derived from the permutation mean and
    SD of the SSE ratio, because a p-value cannot resolve beyond 1/(B+1).
    """
    obs = nested_loso(X, y, grid=grid)
    rng = np.random.default_rng(seed)
    n = y.size
    q2 = np.empty(n_perm)
    for b in range(n_perm):
        yp = y[rng.permutation(n)]
        r = nested_loso(X, yp, grid=grid)
        q2[b] = r.q2_skill
        if verbose and progress_every and (b + 1) % progress_every == 0:
            print(f"    perm {b+1}/{n_perm}  running max Q2={np.nanmax(q2[:b+1]):+.4f}", flush=True)
    n_ge = int(np.sum(q2 >= obs.q2_skill))
    p_perm = (1 + n_ge) / (1 + n_perm)
    mu = float(np.nanmean(q2)); sd = float(np.nanstd(q2, ddof=1)) if n_perm > 1 else float("nan")
    # normal approximation in the SSE-ratio metric (equivalent to Q2 under a fixed denominator)
    rho = 1.0 - q2
    rho_obs = 1.0 - obs.q2_skill
    from scipy import stats as _st
    p_norm = float(_st.norm.cdf((rho_obs - rho.mean()) / rho.std(ddof=1))) if n_perm > 1 and rho.std(ddof=1) > 0 else float("nan")
    return {
        "n_perm": int(n_perm), "seed": int(seed),
        "q2_observed": float(obs.q2_skill),
        "n_perm_ge_observed": n_ge,
        "p_perm": float(p_perm),
        "p_perm_resolution": float(1.0 / (1 + n_perm)),
        "null_mean": mu, "null_sd": sd,
        "null_min": float(np.nanmin(q2)), "null_max": float(np.nanmax(q2)),
        "null_quantiles": {str(q): float(np.nanpercentile(q2, q))
                           for q in (1, 5, 25, 50, 75, 95, 99)},
        "p_normal_approx": p_norm,
        "null_distribution": [float(v) for v in q2],
        "note": ("each replicate re-ran outer LOSO + inner LOSO + scaling + alpha selection; "
                 "p = (1 + #{Q2_perm >= Q2_obs}) / (1 + B)"),
    }


def bootstrap_ci(y: np.ndarray, pred: np.ndarray, pred_m0: np.ndarray,
                 n_boot: int = 10000, seed: int = 20260916) -> dict:
    """Subject-level bootstrap over the (Y, pred, pred_M0) tuple.

    Features are NOT re-selected inside the bootstrap: only the evaluation is resampled.
    """
    y = np.asarray(y, float); pred = np.asarray(pred, float); pred_m0 = np.asarray(pred_m0, float)
    rng = np.random.default_rng(seed)
    n = y.size
    idx = rng.integers(0, n, size=(n_boot, n))
    ys, ps, ms = y[idx], pred[idx], pred_m0[idx]
    sse = np.sum((ys - ps) ** 2, axis=1)
    sse0 = np.sum((ys - ms) ** 2, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        q2 = np.where(sse0 > 0, 1.0 - sse / sse0, np.nan)
    mae = np.mean(np.abs(ys - ps), axis=1)
    mae0 = np.mean(np.abs(ys - ms), axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sk = np.where(mae0 > 0, 1.0 - mae / mae0, np.nan)

    # Spearman per replicate, vectorised by ranking within each replicate
    def _rank(a):
        order = np.argsort(a, axis=1, kind="stable")
        ranks = np.empty_like(order, dtype=float)
        rows = np.arange(a.shape[0])[:, None]
        ranks[rows, order] = np.arange(1, a.shape[1] + 1)
        return ranks
    ry, rp = _rank(ys), _rank(ps)
    ry = ry - ry.mean(axis=1, keepdims=True)
    rp = rp - rp.mean(axis=1, keepdims=True)
    denom = np.sqrt((ry ** 2).sum(axis=1) * (rp ** 2).sum(axis=1))
    with np.errstate(divide="ignore", invalid="ignore"):
        rho = np.where(denom > 0, (ry * rp).sum(axis=1) / denom, np.nan)

    def ci(v):
        v = v[np.isfinite(v)]
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else [np.nan, np.nan]

    return {
        "n_boot": int(n_boot), "seed": int(seed),
        "q2_skill": {"point": float(1 - np.sum((y - pred) ** 2) / np.sum((y - pred_m0) ** 2)),
                     "ci95": ci(q2), "boot_mean": float(np.nanmean(q2)), "boot_sd": float(np.nanstd(q2, ddof=1))},
        "skill_mae": {"point": float(1 - np.mean(np.abs(y - pred)) / np.mean(np.abs(y - pred_m0))),
                      "ci95": ci(sk), "boot_mean": float(np.nanmean(sk)), "boot_sd": float(np.nanstd(sk, ddof=1))},
        "spearman": {"point": float(_spearman(y, pred)), "ci95": ci(rho),
                     "boot_mean": float(np.nanmean(rho)), "boot_sd": float(np.nanstd(rho, ddof=1))},
        "note": "subject-level resampling of the (Y, pred, pred_M0) tuple; no feature re-selection",
    }
