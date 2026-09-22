"""12 - Finite-sample behaviour of J.

    python project/vigilance_generalization_v1/scripts/12_finite_sample_J.py

J_r = sample SD of the epoch-level slowing index S_{e,r} (ddof = 1). Its sampling
uncertainty depends on the number of epochs k, and the brief (section 14) asks us to
quantify how much of the short-duration instability is pure estimator error.

We do NOT change the J definition. This is a quantification exercise only.

Two complementary computations:

  (1) Analytic / textbook: for an i.i.d. Gaussian sample of size k, the sample variance has
      Var(s^2) = 2*sigma^4/(k-1), so SD(s) ~= sigma/sqrt(2(k-1)) for large k. We report this
      alongside the empirical simulation as a cross-check.

  (2) Monte-Carlo: draw from a Gamma model whose parameters are fitted to the OBSERVED
      S-distribution, and from a Gaussian with the same variance, for k = 4, 8, 15, 30, 60.
      Report bias, SD across replicates, and the relative SD of s.

  (3) A heavier-tailed check, because a log-ratio of powers is left-skewed: Student-t with
      matched variance, and a direct empirical bootstrap from real per-epoch S values that
      we re-derive from the data.

Outputs
  outputs/stability_v1/finite_sample_J_simulation.csv
  outputs/stability_v1/finite_sample_J_summary.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import stability as ST  # noqa: E402
from roi import REGION_NAMES  # noqa: E402
from spectral import band_powers  # noqa: E402

KS = (4, 8, 15, 30, 60)
N_REPLICATES = 20000
SEED = 20260916

# Per-epoch S SD implied by the observed J distribution (J *is* the sample SD of S).
SIGMA_BY_REGION = {"F": 0.3863, "CT": 0.3529, "PO": 0.4125}


def analytic_sd_of_sample_sd(sigma: float, k: int) -> float:
    """Large-sample approximation SD(s) ~= sigma / sqrt(2(k-1))."""
    return float(sigma / np.sqrt(2.0 * (k - 1)))


def simulate(sampler, k: int, sigma_true: float, rng: np.random.Generator) -> dict:
    x = sampler(k, N_REPLICATES, rng)
    s = x.std(axis=1, ddof=1)
    return {
        "k": k,
        "mean_s": float(s.mean()),
        "bias": float(s.mean() - sigma_true),
        "relative_bias": float((s.mean() - sigma_true) / sigma_true),
        "sd_s": float(s.std(ddof=1)),
        "relative_sd": float(s.std(ddof=1) / sigma_true),
        "median_s": float(np.median(s)),
        "p05_s": float(np.percentile(s, 5)),
        "p95_s": float(np.percentile(s, 95)),
        "analytic_sd_s": analytic_sd_of_sample_sd(sigma_true, k),
    }


def real_per_epoch_S(estimator: ST.Estimator, subject: str, session: str) -> dict[str, np.ndarray]:
    """Re-derive the actual per-epoch S_{e,r} series for one session."""
    epochs, _ = ST.load_session_epochs(subject, session, estimator)
    bands, _ = band_powers(epochs, estimator.sfreq, estimator.spectral_cfg)
    import mechanism_features as MF
    S = MF.slowing_index(bands, estimator.eps)
    idx = estimator.roi.indices(estimator.channel_names)
    return {r: np.median(S[:, idx[r]], axis=1) for r in REGION_NAMES}


def main() -> None:
    t0 = time.perf_counter()
    out = C.OUTPUTS / "stability_v1"
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    summary: dict = {
        "j_definition": "J_r = sample SD (ddof=1) of epoch-level S_{e,r}",
        "definition_unchanged": True,
        "n_replicates": N_REPLICATES,
        "seed": SEED,
        "sigma_by_region": SIGMA_BY_REGION,
        "note": ("sigma is the per-epoch SD of S, estimated as the mean observed J per region. "
                 "J itself is the sample SD of S, so this is the natural plug-in."),
        "analytic_formula": "SD(s) ~= sigma / sqrt(2(k-1)) for i.i.d. Gaussian samples",
    }

    # ------------------------------------------------------------------ 1. Gaussian model
    for region, sigma in SIGMA_BY_REGION.items():
        for k in KS:
            r = simulate(lambda n, m, g: g.normal(0.0, sigma, size=(m, n)), k, sigma, rng)
            rows.append({"model": "gaussian", "region": region, "sigma_true": sigma, **r})

    # ------------------------------------------------------------------ 2. heavier tails
    # Student-t with nu = 5 scaled to the same variance, matching the left-skew of a log-ratio.
    nu = 5.0
    for region, sigma in SIGMA_BY_REGION.items():
        scale = sigma / np.sqrt(nu / (nu - 2.0))
        for k in KS:
            r = simulate(lambda n, m, g: g.standard_t(nu, size=(m, n)) * scale, k, sigma, rng)
            rows.append({"model": f"student_t_nu{int(nu)}", "region": region, "sigma_true": sigma, **r})

    # ------------------------------------------------------------------ 3. real-data bootstrap
    est = ST.Estimator.build()
    subjects = ST.cohort_subjects()
    pooled: dict[str, np.ndarray] = {}
    n_sessions_used = 0
    print("re-deriving real per-epoch S series ...")
    for i, subject in enumerate(subjects):
        for session in ("ses-1", "ses-2"):
            try:
                series = real_per_epoch_S(est, subject, session)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {subject} {session}: {type(exc).__name__}")
                continue
            for r, v in series.items():
                pooled.setdefault(r, []).append(v)
            n_sessions_used += 1
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(subjects)} subjects", flush=True)
    summary["n_sessions_for_real_bootstrap"] = n_sessions_used

    for region in REGION_NAMES:
        parts = pooled.get(region, [])
        if not parts:
            continue
        allv = np.concatenate([p - p.mean() for p in parts])  # centre each session
        sigma_real = float(np.sqrt(np.mean([p.var(ddof=1) for p in parts])))
        summary.setdefault("real_sigma_by_region", {})[region] = sigma_real
        for k in KS:
            idx = rng.integers(0, allv.size, size=(N_REPLICATES, k))
            s = allv[idx].std(axis=1, ddof=1)
            rows.append({
                "model": "real_empirical_bootstrap", "region": region, "sigma_true": sigma_real,
                "k": k, "mean_s": float(s.mean()), "bias": float(s.mean() - sigma_real),
                "relative_bias": float((s.mean() - sigma_real) / sigma_real),
                "sd_s": float(s.std(ddof=1)), "relative_sd": float(s.std(ddof=1) / sigma_real),
                "median_s": float(np.median(s)),
                "p05_s": float(np.percentile(s, 5)), "p95_s": float(np.percentile(s, 95)),
                "analytic_sd_s": analytic_sd_of_sample_sd(sigma_real, k),
                "kurtosis_of_S": float(stats.kurtosis(allv, fisher=True)),
                "skew_of_S": float(stats.skew(allv)),
            })
        summary.setdefault("real_S_shape", {})[region] = {
            "kurtosis_excess": float(stats.kurtosis(allv, fisher=True)),
            "skew": float(stats.skew(allv)),
        }

    C.write_csv(out / "finite_sample_J_simulation.csv", rows)
    summary["elapsed_seconds"] = time.perf_counter() - t0
    C.write_json(out / "finite_sample_J_summary.json", summary)

    # ------------------------------------------------------------------ report
    print()
    print("=" * 78)
    print("FINITE-SAMPLE BEHAVIOUR OF J  (relative SD of the sample SD)")
    print("=" * 78)
    print(f"  {'model':<26}{'region':<6}" + "".join(f"{('k=%d' % k):>9}" for k in KS))
    for model in ("gaussian", "student_t_nu5", "real_empirical_bootstrap"):
        for region in REGION_NAMES:
            sub = {r["k"]: r for r in rows if r["model"] == model and r["region"] == region}
            if not sub:
                continue
            line = "".join(f"{sub[k]['relative_sd']:>9.3f}" for k in KS if k in sub)
            print(f"  {model:<26}{region:<6}{line}")
    print()
    print("  Bias (mean(s) - sigma) as a fraction of sigma:")
    for model in ("gaussian", "real_empirical_bootstrap"):
        for region in ("CT",):
            sub = {r["k"]: r for r in rows if r["model"] == model and r["region"] == region}
            if not sub:
                continue
            line = "".join(f"{sub[k]['relative_bias']:>9.4f}" for k in KS if k in sub)
            print(f"  {model:<26}{region:<6}{line}")
    print()
    if "real_sigma_by_region" in summary:
        print(f"  real per-epoch S sigma by region: {summary['real_sigma_by_region']}")
    if "real_S_shape" in summary:
        print(f"  real S shape: {summary['real_S_shape']}")
    print(f"\n  elapsed {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/stability_v1/finite_sample_J_simulation.csv (+ summary json)")


if __name__ == "__main__":
    main()
