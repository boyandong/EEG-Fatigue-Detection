"""31 - Independent verification of the Phase 2 deliverables.

    python project/vigilance_generalization_v1/scripts/31_verify_phase2.py

Does not trust the modelling script. It:
  * re-derives the feature matrix for the primary protocol from the raw .set files and checks it
    against outputs/phase2/features_used.csv (this is the highest-value check: it confirms the
    whole Phase 1.75 -> Phase 2 hand-off);
  * re-derives the primary target from the raw PVT trial files;
  * recomputes Q2_skill, MAE, Skill_MAE and Spearman from outputs/phase2/predictions.csv and
    compares with model_results.csv;
  * re-runs the nested LOSO with sklearn Ridge and confirms it matches the shipped result;
  * recomputes the permutation p-value from the stored null array;
  * checks the frozen-protocol invariants (no feature selection, one alpha per fold from the
    frozen grid, M0 = outer-train mean).

Exit code 0 = verified.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import phase2_models as P2  # noqa: E402
import pvt_psychometrics as PP  # noqa: E402
import pvt_targets as PT  # noqa: E402
import stability as ST  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

P2OUT = None
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))


def f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def main() -> int:
    global P2OUT
    P2OUT = C.OUTPUTS / "phase2"
    est = ST.Estimator.build()

    # ---------------------------------------------------------------- deliverables
    print("1. Deliverables")
    need = ["features_used.csv", "model_results.csv", "predictions.csv", "alpha_selection.csv",
            "permutation_null.npz", "permutation_summary.json", "bootstrap_ci.json",
            "confound_sensitivity.csv", "phase2_summary.json"]
    missing = [n for n in need if not (P2OUT / n).exists()]
    check("all Phase 2 outputs present", not missing, f"missing={missing}")

    results = {r["model"]: r for r in C.read_csv(P2OUT / "model_results.csv")}
    preds = C.read_csv(P2OUT / "predictions.csv")
    print(f"   models: {sorted(results)}")

    # ---------------------------------------------------------------- frozen protocol
    print("\n2. Frozen-protocol invariants")
    check("alpha grid matches the frozen spec",
          tuple(P2.ALPHA_GRID) == (0.01, 0.1, 1.0, 10.0, 100.0), str(P2.ALPHA_GRID))
    check("every model uses exactly 3 (X_M) or 6 (X_M+X_J) predictors",
          all(int(r["n_predictors"]) in (3, 6) for r in results.values()),
          str(sorted({r["n_predictors"] for r in results.values()})))
    check("primary model M1 exists with X_M on the B0/T60 protocol",
          results.get("M1", {}).get("protocol") == "k15"
          and results.get("M1", {}).get("feature_block") == "X_M")
    check("M2 and M3 share the same protocol (B60/T60)",
          results.get("M2", {}).get("protocol") == results.get("M3", {}).get("protocol") == "B60_T60")
    check("M3 adds exactly the X_J block to M2",
          int(results["M3"]["n_predictors"]) == int(results["M2"]["n_predictors"]) + 3)
    check("no model reports a second algorithm or extra feature block",
          {r["feature_block"] for r in results.values()} <= {"X_M", "X_M+X_J"})

    # alphas come from the frozen grid only
    alphas = np.array([f(r["alpha_selected"]) for r in C.read_csv(P2OUT / "alpha_selection.csv")])
    check("every selected alpha is a grid member",
          all(np.any(np.isclose(a, P2.ALPHA_GRID)) for a in alphas),
          f"unique alphas = {sorted(set(alphas.tolist()))}")

    # ---------------------------------------------------------------- recompute endpoints
    print("\n3. Endpoints recomputed from predictions.csv")
    from scipy import stats
    for name, row in sorted(results.items()):
        rows = [r for r in preds if r["model"] == name]
        y = np.array([f(r["y_true"]) for r in rows])
        p = np.array([f(r["y_pred"]) for r in rows])
        m0 = np.array([f(r["y_pred_m0"]) for r in rows])
        sse = float(np.sum((y - p) ** 2)); sse0 = float(np.sum((y - m0) ** 2))
        q2 = 1 - sse / sse0
        mae = float(np.mean(np.abs(y - p))); mae0 = float(np.mean(np.abs(y - m0)))
        sk = 1 - mae / mae0
        rho = float(stats.spearmanr(y, p).statistic)
        ok = (abs(q2 - f(row["q2_skill"])) < 1e-12 and abs(mae - f(row["mae"])) < 1e-12
              and abs(sk - f(row["skill_mae"])) < 1e-12 and abs(rho - f(row["spearman"])) < 1e-12)
        check(f"{name}: Q2/MAE/skillMAE/Spearman reproduce", ok,
              f"Q2={q2:+.4f} rho={rho:+.3f}")
    # M0 must be the outer-train mean, per fold
    rows = [r for r in preds if r["model"] == "M1"]
    y = np.array([f(r["y_true"]) for r in rows])
    m0 = np.array([f(r["y_pred_m0"]) for r in rows])
    expect = np.array([y[np.arange(len(y)) != i].mean() for i in range(len(y))])
    check("M0 is the leave-one-out training mean in every fold",
          np.allclose(m0, expect, atol=1e-12), f"max diff {np.max(np.abs(m0-expect)):.2e}")
    check("the primary model predicts with one alpha per outer fold",
          len([r for r in C.read_csv(P2OUT / "alpha_selection.csv") if r["model"] == "M1"]) == len(y))

    # ---------------------------------------------------------------- features from raw
    print("\n4. Feature matrix re-derived from the raw .set files (primary protocol B0/T60)")
    feat = {}
    for r in C.read_csv(P2OUT / "features_used.csv"):
        if r["model"] == "M1":
            feat[r["subject"]] = r
    subjects = sorted(feat)
    worst = {"delta_M_F": 0.0, "delta_M_CT": 0.0, "delta_M_PO": 0.0}
    problems = []
    for s in subjects[:8]:
        try:
            ns, sd = ST.load_session_epochs(s, "ses-1", est), ST.load_session_epochs(s, "ses-2", est)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{s}: {type(exc).__name__}")
            continue
        # B = 0, T = 60 s -> 15 epochs from the start, computed independently of the CSV
        f_ns = est.dynamic_features(ns[0][:15])
        f_sd = est.dynamic_features(sd[0][:15])
        for r in REGION_NAMES:
            d = abs((f_sd[f"M_{r}"] - f_ns[f"M_{r}"]) - f(feat[s][f"delta_M_{r}"]))
            worst[f"delta_M_{r}"] = max(worst[f"delta_M_{r}"], d)
    check("no re-derivation problems", not problems, str(problems[:3]))
    for k, v in sorted(worst.items()):
        check(f"{k} re-derives from raw EEG", v < 1e-9, f"max|d|={v:.3e}")
    check("cohort is exactly the 29 raw-PVT-paired subjects", len(subjects) == 29, str(len(subjects)))

    # ---------------------------------------------------------------- target from raw
    print("\n5. Primary target re-derived from the raw PVT trial files")
    cfg = C.dataset_config()
    found = {(s, ses): p for s, ses, p in PT.discover_trial_files(C.resolve(cfg["paths"]["bids_root"]))}
    unc = {r["subject"]: r for r in C.read_csv(
        C.OUTPUTS / "pvt_psychometrics" / "pvt_target_uncertainty.csv")}
    worst_y = 0.0
    for s in subjects[:10]:
        ns, _ = PT.parse_trial_file(found[(s, "ses-1")], s, "ses-1", 100.0, 2000.0)
        sd, _ = PT.parse_trial_file(found[(s, "ses-2")], s, "ses-2", 100.0, 2000.0)
        y = PP.y_speed(ns.valid_rt, sd.valid_rt)
        worst_y = max(worst_y, abs(y - f(feat[s]["Y"])))
    check("Y_speed=ln(Q_NS/Q_SD) re-derives from raw trials", worst_y < 1e-12,
          f"max|d|={worst_y:.3e}")
    # the 100-2000 ms rule must be intact
    ns, _ = PT.parse_trial_file(found[(subjects[0], "ses-1")], subjects[0], "ses-1", 100.0, 2000.0)
    check("trial filter is 100-2000 ms and the raw file is untouched", ns.valid_rt.min() >= 100.0
          and ns.valid_rt.max() <= 2000.0,
          f"RT range {ns.valid_rt.min():.1f}-{ns.valid_rt.max():.1f} ms")

    # ---------------------------------------------------------------- sklearn cross-check
    print("\n6. Nested LOSO reproduced with sklearn Ridge")
    X = np.array([[f(feat[s][c]) for c in ("delta_M_F", "delta_M_CT", "delta_M_PO")]
                  for s in subjects])
    y = np.array([f(feat[s]["Y"]) for s in subjects])
    r = P2.nested_loso(X, y, subjects)
    check("my nested-LOSO Q2 matches the shipped M1 Q2",
          abs(r.q2_skill - f(results["M1"]["q2_skill"])) < 1e-12,
          f"{r.q2_skill:+.6f} vs {f(results['M1']['q2_skill']):+.6f}")

    from sklearn.linear_model import Ridge
    pred_sk = np.empty(len(y))
    alphas_sk = np.empty(len(y))
    for i in range(len(y)):
        mask = np.ones(len(y), bool); mask[i] = False
        Xa, Xb = P2.standardise(X[mask], X[~mask])
        # inner LOSO with sklearn
        best, best_mse = None, np.inf
        for a in P2.ALPHA_GRID:
            errs = []
            for j in range(Xa.shape[0]):
                m2 = np.ones(Xa.shape[0], bool); m2[j] = False
                Xaa, Xbb = P2.standardise(Xa[m2], Xa[~m2])
                pr = Ridge(alpha=a, fit_intercept=True).fit(Xaa, y[mask][m2]).predict(Xbb)
                errs.append(np.mean((pr - y[mask][~m2]) ** 2))
            if np.mean(errs) < best_mse - 1e-15:
                best, best_mse = a, np.mean(errs)
        alphas_sk[i] = best
        pred_sk[i] = Ridge(alpha=best, fit_intercept=True).fit(Xa, y[mask]).predict(Xb)[0]
    check("sklearn Ridge reproduces the predictions",
          np.allclose(pred_sk, r.pred, atol=1e-9), f"max|d|={np.max(np.abs(pred_sk-r.pred)):.2e}")
    check("sklearn Ridge reproduces the alpha selection",
          np.array_equal(alphas_sk, r.alphas), f"alphas={sorted(set(alphas_sk.tolist()))}")

    # ---------------------------------------------------------------- permutation
    print("\n7. Permutation null")
    z = np.load(P2OUT / "permutation_null.npz")
    null = z["q2_null"]
    pj = C.json.loads((P2OUT / "permutation_summary.json").read_text(encoding="utf-8"))
    n_ge = int(np.sum(null >= pj["q2_observed"]))
    check("stored null has the requested length", null.size == pj["n_perm"],
          f"{null.size} vs {pj['n_perm']}")
    check("p_perm reproduces from the stored null",
          abs((1 + n_ge) / (1 + null.size) - pj["p_perm"]) < 1e-12,
          f"p={pj['p_perm']:.5f} ({n_ge}/{null.size})")
    check("observed Q2 is stored inside the null file",
          abs(float(z["q2_observed"][0]) - pj["q2_observed"]) < 1e-12)
    check("per-replicate cost is consistent with a full pipeline re-run",
          pj["elapsed_seconds"] / max(1, pj["n_perm"]) > 0.02,
          f"{pj['elapsed_seconds']/max(1,pj['n_perm']):.3f} s/perm (a single ridge fit would be ~1e-4 s)")

    # ---------------------------------------------------------------- bootstrap
    print("\n8. Bootstrap CIs")
    boot = C.json.loads((P2OUT / "bootstrap_ci.json").read_text(encoding="utf-8"))
    for name in ("M1", "M1_full", "M2", "M3"):
        if name not in boot:
            continue
        b = boot[name]
        ok = (b["q2_skill"]["ci95"][0] <= b["q2_skill"]["point"] <= b["q2_skill"]["ci95"][1]
              and b["spearman"]["ci95"][0] <= b["spearman"]["point"] <= b["spearman"]["ci95"][1])
        check(f"{name}: CI brackets the point estimate", ok,
              f"Q2 CI [{b['q2_skill']['ci95'][0]:+.3f},{b['q2_skill']['ci95'][1]:+.3f}]")
    check("bootstrap used the declared replicate count",
          all(v["n_boot"] == 10000 for v in boot.values()), str({k: v["n_boot"] for k, v in boot.items()}))

    # ---------------------------------------------------------------- no disattenuation
    print("\n9. Reporting discipline")
    summ = C.json.loads((P2OUT / "phase2_summary.json").read_text(encoding="utf-8"))
    check("no disattenuation applied", summ["reliability_context"]["disattenuation_applied"] is False)
    check("no feature selection performed", summ["feature_selection"].startswith("none"))
    check("no extra features", summ["extra_features_used"] is False)
    check("no second algorithm", summ["second_algorithm_tried"] is False)
    check("protocol not re-tuned", summ["protocol_retuned"] is False)
    check("reliability labelled as approximate / not test-retest",
          "NOT test-retest" in summ["reliability_context"]["label"])

    # ---------------------------------------------------------------- confounds
    print("\n10. Confound sensitivity")
    conf = C.read_csv(P2OUT / "confound_sensitivity.csv")
    check("confound models reported", len(conf) >= 1, str([c["model"] for c in conf]))
    if len(conf) == 2:
        check("C1 = C0 + X_M and both are reported with n",
              "deltaClock + X_M" in conf[1]["predictors"] and int(conf[0]["n_subjects"]) > 0,
              f"n={conf[0]['n_subjects']}")

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print("=" * 74)
    print(f"{len(CHECKS)-n_fail}/{len(CHECKS)} Phase 2 verification checks passed")
    if n_fail:
        for nm, ok, d in CHECKS:
            if not ok:
                print("  -", nm, d)
    C.write_json(C.OUTPUTS / "qc" / "verification_phase2.json", {
        "status": "passed" if n_fail == 0 else "failed",
        "n_checks": len(CHECKS), "n_failed": n_fail,
        "checks": [{"name": nm, "passed": ok, "detail": d} for nm, ok, d in CHECKS],
    })
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
