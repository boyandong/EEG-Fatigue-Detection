"""Phase 2 unit tests: the hand-written SVD ridge must equal sklearn's Ridge exactly, and the
nested-LOSO machinery must respect the leakage boundary.

    python project/vigilance_generalization_v1/tests/test_phase2_ridge.py

The permutation test re-runs the whole pipeline thousands of times, so the inner loop uses a
numpy SVD solver instead of sklearn. That substitution is only legitimate if it is numerically
identical to what sklearn would produce -- this file establishes that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import phase2_models as P2  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))


def main() -> int:
    from sklearn.linear_model import Ridge

    rng = np.random.default_rng(20260916)
    print("1. SVD ridge equals sklearn Ridge (unpenalised intercept, same alpha)")

    worst = 0.0
    for trial, (n, p) in enumerate([(28, 3), (28, 6), (12, 3), (5, 3), (40, 6)]):
        X = rng.normal(size=(n, p))
        y = rng.normal(size=n)
        Xte = rng.normal(size=(7, p))
        for alpha in (0.01, 0.1, 1.0, 10.0, 100.0):
            mine, _ = P2.ridge_fit_predict(X, y, Xte, alpha)
            sk = Ridge(alpha=alpha, fit_intercept=True).fit(X, y).predict(Xte)
            worst = max(worst, float(np.max(np.abs(mine - sk))))
    check("max |mine - sklearn| across 25 configurations", worst < 1e-8, f"{worst:.3e}")

    # degeneracy: duplicated (perfectly collinear) columns
    X = rng.normal(size=(20, 3))
    X = np.column_stack([X, 2.0 * X[:, 0]])          # column 4 is collinear with column 1
    y = rng.normal(size=20)
    Xte = rng.normal(size=(4, 4))
    mine, _ = P2.ridge_fit_predict(X, y, Xte, 1.0)
    sk = Ridge(alpha=1.0, fit_intercept=True).fit(X, y).predict(Xte)
    check("collinear columns handled identically", np.allclose(mine, sk, atol=1e-8),
          f"max|d|={np.max(np.abs(mine - sk)):.3e}")

    # also check the training-set fit matches
    print("\n2. Training-set predictions match")
    X = rng.normal(size=(30, 3)); y = rng.normal(size=30)
    for alpha in (0.01, 1.0, 100.0):
        mine, coef = P2.ridge_fit_predict(X, y, X, alpha)
        sk = Ridge(alpha=alpha, fit_intercept=True).fit(X, y)
        check(f"alpha={alpha}: train fit + coefficients",
              np.allclose(mine, sk.predict(X), atol=1e-8)
              and np.allclose(coef, np.concatenate([[sk.intercept_], sk.coef_]), atol=1e-8),
              "")

    print("\n3. Scaling uses training statistics only (leakage boundary)")
    Xtr = rng.normal(10, 3, size=(20, 2))
    Xte = rng.normal(-5, 7, size=(3, 2))
    a, b = P2.standardise(Xtr, Xte)
    check("train block is centred and unit-scaled by its own stats",
          np.allclose(a.mean(axis=0), 0, atol=1e-12) and np.allclose(a.std(axis=0, ddof=0), 1, atol=1e-12))
    check("test block is transformed with the TRAIN statistics, not its own",
          not np.allclose(b.mean(axis=0), 0, atol=1e-6),
          f"test mean after transform = {np.round(b.mean(axis=0), 4)}")
    manual = (Xte - Xtr.mean(axis=0)) / Xtr.std(axis=0, ddof=0)
    check("test transform equals manual (Xte - mu_train)/sd_train", np.allclose(b, manual))

    print("\n4. Inner alpha selection")
    # signal: y is a linear function of column 0, so small alpha should win
    n = 28
    X = rng.normal(size=(n, 3)); y = 2.0 * X[:, 0] + rng.normal(0, 0.2, n)
    alpha, info = P2.inner_select_alpha(X, y)
    check("inner selection returns a grid member", alpha in P2.ALPHA_GRID, f"alpha={alpha}")
    check("inner MSE computed for every grid point", len(info["inner_mse"]) == len(P2.ALPHA_GRID))
    check("inner MSE prefers little penalisation on a clean linear signal", alpha <= 1.0,
          f"alpha={alpha}, mse={ {k: round(v,4) for k,v in info['inner_mse'].items()} }")

    print("\n5. Nested LOSO on null data must not produce skill")
    X = rng.normal(size=(29, 3)); y = rng.normal(size=29)
    r = P2.nested_loso(X, y)
    check("Q2_skill <= 0 on pure noise (no leakage into the held-out subject)",
          r.q2_skill <= 0.05, f"Q2={r.q2_skill:+.4f}")
    check("M0 baseline is the outer-train mean, recomputed per fold",
          np.allclose(r.pred_m0, [y[np.arange(29) != i].mean() for i in range(29)]))
    check("one alpha was chosen per outer fold", r.alphas.size == 29)

    print("\n6. Nested LOSO recovers a strong real signal")
    X = rng.normal(size=(29, 3)); y = 3.0 * X[:, 0] + rng.normal(0, 0.3, 29)
    r = P2.nested_loso(X, y)
    check("Q2_skill strongly positive when the signal is real", r.q2_skill > 0.5,
          f"Q2={r.q2_skill:+.4f}")
    check("Spearman high for a monotone signal", r.spearman > 0.7, f"rho={r.spearman:+.3f}")

    print("\n7. Permutation p-value arithmetic")
    X = rng.normal(size=(29, 3)); y = rng.normal(size=29)
    null = P2.permutation_null_q2(X, y, n_perm=60, seed=1, verbose=False)
    B = null["n_perm"]
    expect = (1 + null["n_perm_ge_observed"]) / (B + 1)
    check("p_perm equals (1+#{>=obs})/(B+1)", abs(null["p_perm"] - expect) < 1e-12,
          f"p={null['p_perm']:.4f}")
    check("null distribution has the requested length", len(null["null_distribution"]) == B)
    check("p on noise is not small", null["p_perm"] > 0.05, f"p={null['p_perm']:.3f}")

    print("\n8. Bootstrap CI arithmetic")
    y = rng.normal(size=29); pred = y + rng.normal(0, 0.5, 29); m0 = np.full(29, y.mean())
    ci = P2.bootstrap_ci(y, pred, m0, n_boot=500, seed=7)
    pt = 1 - np.sum((y - pred) ** 2) / np.sum((y - m0) ** 2)
    check("bootstrap point estimate equals the closed form",
          abs(ci["q2_skill"]["point"] - pt) < 1e-12, f"{pt:+.4f}")
    check("CI brackets the point estimate",
          ci["q2_skill"]["ci95"][0] <= pt <= ci["q2_skill"]["ci95"][1],
          str([round(v, 4) for v in ci["q2_skill"]["ci95"]]))
    check("MAE skill point equals the closed form",
          abs(ci["skill_mae"]["point"] - (1 - np.mean(np.abs(y - pred)) / np.mean(np.abs(y - m0)))) < 1e-12)

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print("=" * 74)
    print(f"{len(CHECKS)-n_fail}/{len(CHECKS)} Phase 2 unit checks passed")
    if n_fail:
        for nm, ok, d in CHECKS:
            if not ok:
                print("  -", nm, d)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
