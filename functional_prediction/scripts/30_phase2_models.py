"""30 - Phase 2: the first EEG -> PVT predictive modelling in this project.

    python project/vigilance_generalization_v1/scripts/30_phase2_models.py [--n-perm 5000] [--workers 8]

Frozen specification: SCIENTIFIC_SPEC.md section 18. Summary of what is fixed in advance:

  primary target     Y_speed = ln(Q_NS / Q_SD),  Q = mean(1/RT),  100 <= RT <= 2000 ms
  secondary target   Y_RT    = ln(medianRT_SD / medianRT_NS)
  primary protocol   P_M = (B = 0 s, T = 60 s)          -> X_M
  dynamic protocol   P_J = (B = 60 s, T = 60 s)         -> X_M and X_J on the SAME window
  X_M = [dM_F, dM_CT, dM_PO]                            confirmatory
  X_J = [dlogJ_F, dlogJ_CT, dlogJ_PO]                   exploratory incremental
  ladder             M0 (train mean) | M1 (X_M, P_M) | M1-full (X_M, full) |
                     M2 (X_M, P_J) | M3 (X_M+X_J, P_J)
  CV                 outer LOSO (29 folds) x inner LOSO (28) for lambda in {0.01..100}
                     scaling and lambda selection strictly inside the outer training fold
  endpoint           Q2_skill = 1 - SSE_model / SSE_M0
  inference          subject-level permutation (B >= 5000, full pipeline re-run) on M1 only;
                     subject-level bootstrap (B = 10000) for CIs
  confound sens.     C0: Y ~ SessionOrder + dClock ;  C1: C0 + dM   (same outer LOSO)

No feature selection, no extra features, no second algorithm, no protocol re-tuning.

Outputs (outputs/phase2/)
  features_used.csv          the exact feature matrix and target vector per model
  model_results.csv          per-model Q2 / MAE / skill / Spearman
  predictions.csv            per-subject held-out predictions for every model
  alpha_selection.csv        which lambda the inner loop chose, per outer fold
  permutation_null.npz       the full null distribution for M1 -> Y_speed
  permutation_summary.json
  bootstrap_ci.json
  confound_sensitivity.csv
  phase2_summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import phase2_models as P2  # noqa: E402

OUT = None
X_M_COLS = ["delta_M_F", "delta_M_CT", "delta_M_PO"]
X_J_COLS = ["delta_logJ_F", "delta_logJ_CT", "delta_logJ_PO"]

# (model, feature columns, protocol label, window rule, target)
LADDER = [
    ("M1", X_M_COLS, "k15", "first", "speed"),
    ("M1_full", X_M_COLS, "full", "first", "speed"),
    ("M2", X_M_COLS, "B60_T60", "first", "speed"),
    ("M3", X_M_COLS + X_J_COLS, "B60_T60", "first", "speed"),
    ("M1_RT", X_M_COLS, "k15", "first", "rt"),
    ("M1_full_RT", X_M_COLS, "full", "first", "rt"),
]


# --------------------------------------------------------------------------- data assembly
def load_tables():
    pair = C.read_csv(C.OUTPUTS / "dynamic_audit" / "J_V_Jres_paired.csv")
    unc = {r["subject"]: r for r in C.read_csv(
        C.OUTPUTS / "pvt_psychometrics" / "pvt_target_uncertainty.csv")}
    # confound variables come from the frozen Phase 1 paired table (metadata only)
    meta = {r["subject"]: r for r in C.read_csv(C.OUTPUTS / "mechanism_v1" / "paired_features.csv")}
    return pair, unc, meta


def window0(pair, label):
    """The FIRST disjoint window of the given label, per subject. Never pooled, never averaged."""
    out = {}
    for r in pair:
        if r["label"] != label:
            continue
        if int(r["paired_window_index"]) != 0:
            continue
        out[r["subject"]] = r
    return out


def build(rows: dict, subjects: list[str], cols: list[str]) -> np.ndarray:
    return np.array([[float(rows[s][c]) for c in cols] for s in subjects], dtype=float)


def yvec(unc: dict, subjects: list[str], target: str) -> np.ndarray:
    key = "Y_speed_point" if target == "speed" else "Y_RT_point"
    return np.array([float(unc[s][key]) for s in subjects], dtype=float)


# --------------------------------------------------------------------------- permutation worker
def _perm_chunk(args):
    """Run a contiguous chunk of permutations. Module-level so multiprocessing can pickle it."""
    X, y, start, count, seed = args
    rng = np.random.default_rng(seed)
    n = y.size
    out = np.empty(count)
    for k in range(count):
        yp = y[rng.permutation(n)]
        out[k] = P2.nested_loso(X, yp).q2_skill
    return start, out


def permutation_null(X, y, n_perm, seed, workers):
    """Reproducible parallel permutation null; each replicate re-runs the entire pipeline."""
    import multiprocessing as mp
    base = np.random.default_rng(seed)
    # Pre-generate every permutation's seed on the master so results do not depend on scheduling.
    seeds = base.integers(0, 2**32 - 1, size=n_perm)
    chunks = []
    per = max(1, n_perm // max(1, workers))
    i = 0
    while i < n_perm:
        cnt = min(per, n_perm - i)
        chunks.append((X, y, i, cnt, int(seeds[i])))
        i += cnt
    q2 = np.empty(n_perm)
    if workers <= 1 or len(chunks) == 1:
        for ch in chunks:
            s, v = _perm_chunk(ch)
            q2[s:s + v.size] = v
        return q2
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(workers, len(chunks))) as pool:
        done = 0
        for s, v in pool.imap_unordered(_perm_chunk, chunks):
            q2[s:s + v.size] = v
            done += v.size
            print(f"    perm {done}/{n_perm}", flush=True)
    return q2


def main() -> None:
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-perm", type=int, default=5000)
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    ap.add_argument("--seed", type=int, default=20260916)
    args = ap.parse_args()

    t0 = time.perf_counter()
    OUT = C.OUTPUTS / "phase2"
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"permutations={args.n_perm}  bootstrap={args.n_boot}  workers={args.workers}  seed={args.seed}")

    pair, unc, meta = load_tables()
    subjects = sorted(unc)
    print(f"cohort: {len(subjects)} subjects")

    # ---------------------------------------------------------------- confound variables
    def clock_minutes(s: str):
        try:
            h, m, _ = s.split(":")
            return int(h) * 60 + int(m)
        except Exception:  # noqa: BLE001
            return np.nan

    conf_rows, n_conf = [], 0
    for s in subjects:
        m = meta.get(s, {})
        a = clock_minutes(m.get("eeg_clock_NS", ""))
        b = clock_minutes(m.get("eeg_clock_SD", ""))
        d = np.nan
        if np.isfinite(a) and np.isfinite(b):
            d = b - a
            if d > 720:
                d -= 1440
            if d < -720:
                d += 1440
            n_conf += 1
        order = 1.0 if m.get("session_order", "") == "NS->SD" else 0.0
        conf_rows.append({"subject": s, "session_order_NS_first": order, "delta_clock_min": d})
    print(f"confound variables available for {n_conf}/{len(subjects)} subjects")

    # ---------------------------------------------------------------- assemble models
    feats_by_label = {lab: window0(pair, lab) for lab in ("k15", "full", "B60_T60")}
    for lab, d in feats_by_label.items():
        print(f"  protocol {lab:9s}: {len(d)} subjects with a window-0 pair")

    results, pred_rows, alpha_rows, feat_rows = [], [], [], []
    cv_cache: dict[str, P2.CvResult] = {}
    for name, cols, lab, rule, tgt in LADDER:
        rows = feats_by_label[lab]
        subs = [s for s in subjects if s in rows]
        if len(subs) < 10:
            print(f"  [{name}] SKIPPED: only {len(subs)} subjects")
            continue
        X = build(rows, subs, cols)
        y = yvec(unc, subs, tgt)
        r = P2.nested_loso(X, y, subs)
        cv_cache[name] = r
        results.append({
            "model": name, "target": "Y_speed" if tgt == "speed" else "Y_RT",
            "protocol": lab, "feature_block": "X_M" if cols == X_M_COLS else "X_M+X_J",
            "n_predictors": len(cols), "n_subjects": r.n,
            "q2_skill": r.q2_skill, "sse_model": r.sse_model, "sse_m0": r.sse_m0,
            "mae": r.mae, "mae_m0": r.mae_m0, "skill_mae": r.skill_mae,
            "spearman": r.spearman, "pearson": r.pearson,
            "alpha_median": float(np.median(r.alphas)),
            "alpha_values": ";".join(str(a) for a in r.alphas),
        })
        for i, s in enumerate(subs):
            pred_rows.append({"model": name, "subject": s, "y_true": float(y[i]),
                              "y_pred": float(r.pred[i]), "y_pred_m0": float(r.pred_m0[i]),
                              "alpha_used": float(r.alphas[i])})
        for i, s in enumerate(subs):
            alpha_rows.append({"model": name, "subject": s, "alpha_selected": float(r.alphas[i])})
        print(f"  [{name}] n={r.n} p={len(cols)} Q2={r.q2_skill:+.4f} "
              f"MAE={r.mae:.4f} skillMAE={r.skill_mae:+.4f} rho={r.spearman:+.3f} "
              f"alpha_med={np.median(r.alphas):g}")

    C.write_csv(OUT / "model_results.csv", results)
    C.write_csv(OUT / "predictions.csv", pred_rows)
    C.write_csv(OUT / "alpha_selection.csv", alpha_rows)

    # ---------------------------------------------------------------- feature dump
    for name, cols, lab, rule, tgt in LADDER:
        rows = feats_by_label[lab]
        for s in subjects:
            if s not in rows:
                continue
            rec = {"model": name, "subject": s, "protocol": lab, "target": tgt}
            for c in cols:
                rec[c] = float(rows[s][c])
            rec["Y"] = float(unc[s]["Y_speed_point" if tgt == "speed" else "Y_RT_point"])
            feat_rows.append(rec)
    C.write_csv(OUT / "features_used.csv", feat_rows)

    # ---------------------------------------------------------------- permutation (M1 only)
    print("\npermutation test: M1 -> Y_speed (full pipeline re-run per replicate)")
    rows = feats_by_label["k15"]
    subs = [s for s in subjects if s in rows]
    Xp = build(rows, subs, X_M_COLS)
    yp = yvec(unc, subs, "speed")
    t_perm = time.perf_counter()
    null = permutation_null(Xp, yp, args.n_perm, args.seed, args.workers)
    q2_obs = cv_cache["M1"].q2_skill
    n_ge = int(np.sum(null >= q2_obs))
    perm_summary = {
        "hypothesis": "M1 (X_M, B0/T60) -> Y_speed",
        "q2_observed": float(q2_obs),
        "n_perm": int(args.n_perm), "seed": int(args.seed),
        "n_perm_ge_observed": n_ge,
        "p_perm": float((1 + n_ge) / (1 + args.n_perm)),
        "p_perm_resolution": float(1.0 / (1 + args.n_perm)),
        "null_mean": float(np.mean(null)), "null_sd": float(np.std(null, ddof=1)),
        "null_min": float(np.min(null)), "null_max": float(np.max(null)),
        "null_quantiles": {str(q): float(np.percentile(null, q)) for q in (1, 5, 25, 50, 75, 95, 99)},
        "frac_null_positive": float(np.mean(null > 0)),
        "each_replicate": "outer LOSO + inner LOSO + scaling + alpha selection, all re-run",
        "elapsed_seconds": time.perf_counter() - t_perm,
    }
    np.savez_compressed(OUT / "permutation_null.npz", q2_null=null,
                        q2_observed=np.array([q2_obs]))
    C.write_json(OUT / "permutation_summary.json", perm_summary)
    print(f"  Q2_obs={q2_obs:+.4f}  null mean={perm_summary['null_mean']:+.4f} "
          f"sd={perm_summary['null_sd']:.4f}  p_perm={perm_summary['p_perm']:.4f} "
          f"({perm_summary['elapsed_seconds']:.0f}s)")

    # ---------------------------------------------------------------- bootstrap CIs
    print("\nbootstrap CIs (subject-level, (Y, pred, pred_M0) tuple)")
    boot = {}
    for name in ("M1", "M1_full", "M2", "M3", "M1_RT", "M1_full_RT"):
        r = cv_cache.get(name)
        if r is None:
            continue
        boot[name] = P2.bootstrap_ci(r.y, r.pred, r.pred_m0, n_boot=args.n_boot, seed=args.seed)
        b = boot[name]
        print(f"  [{name}] Q2 {b['q2_skill']['point']:+.4f} "
              f"CI[{b['q2_skill']['ci95'][0]:+.3f},{b['q2_skill']['ci95'][1]:+.3f}]  "
              f"rho CI[{b['spearman']['ci95'][0]:+.3f},{b['spearman']['ci95'][1]:+.3f}]")
    C.write_json(OUT / "bootstrap_ci.json", boot)

    # ---------------------------------------------------------------- confound sensitivity
    print("\nconfound sensitivity (secondary)")
    conf_subj = [s for s in subjects if s in feats_by_label["k15"]
                 and np.isfinite(conf_rows[subjects.index(s)]["delta_clock_min"])]
    crows = {r["subject"]: r for r in conf_rows}
    conf_res = []
    if len(conf_subj) >= 10:
        Xc = np.array([[crows[s]["session_order_NS_first"], crows[s]["delta_clock_min"]]
                       for s in conf_subj], float)
        Xm = build(feats_by_label["k15"], conf_subj, X_M_COLS)
        yc = yvec(unc, conf_subj, "speed")
        r0 = P2.nested_loso(Xc, yc, conf_subj)
        r1 = P2.nested_loso(np.hstack([Xc, Xm]), yc, conf_subj)
        conf_res = [
            {"model": "C0_confounds_only", "predictors": "SessionOrder + deltaClock",
             "n_subjects": r0.n, "q2_skill": r0.q2_skill, "mae": r0.mae, "skill_mae": r0.skill_mae,
             "spearman": r0.spearman},
            {"model": "C1_confounds_plus_dM", "predictors": "SessionOrder + deltaClock + X_M",
             "n_subjects": r1.n, "q2_skill": r1.q2_skill, "mae": r1.mae, "skill_mae": r1.skill_mae,
             "spearman": r1.spearman},
        ]
        print(f"  n={r0.n}  C0 Q2={r0.q2_skill:+.4f}   C1 Q2={r1.q2_skill:+.4f}   "
              f"delta={r1.q2_skill - r0.q2_skill:+.4f}")
    else:
        conf_res = [{"model": "insufficient", "n_subjects": len(conf_subj)}]
        print(f"  only {len(conf_subj)} subjects with timing metadata; reported as insufficient")
    C.write_csv(OUT / "confound_sensitivity.csv", conf_res)

    # ---------------------------------------------------------------- summary
    summary = {
        "phase": 2,
        "core_question": ("can personal-baseline-relative EEG predict objective vigilance "
                          "decline in an unseen subject?"),
        "n_subjects": len(subjects),
        "primary_target": "Y_speed",
        "primary_protocol": "B0_T60",
        "primary_model": "M1",
        "alpha_grid": list(P2.ALPHA_GRID),
        "cv": "outer LOSO(29) x inner LOSO(28); scaling and alpha selection inside outer train",
        "models": results,
        "permutation": perm_summary,
        "bootstrap": {k: {kk: vv for kk, vv in v.items()} for k, v in boot.items()},
        "confound": conf_res,
        "feature_selection": "none; all three ROIs retained a priori in every model",
        "extra_features_used": False,
        "second_algorithm_tried": False,
        "protocol_retuned": False,
        "reliability_context": {
            "R_approx_Y_speed": 0.813, "R_approx_Y_RT": 0.698,
            "label": "approximate finite-trial reliability proxy, NOT test-retest reliability",
            "disattenuation_applied": False,
        },
        "elapsed_seconds": time.perf_counter() - t0,
    }
    C.write_json(OUT / "phase2_summary.json", summary)
    C.write_json(C.OUTPUTS / "qc" / "run_manifest_30_phase2.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml", C.CONFIG / "mechanism_v1.yaml"],
        {"n_perm": args.n_perm, "n_boot": args.n_boot, "seed": args.seed,
         "models_run": [r["model"] for r in results], "elapsed_seconds": time.perf_counter() - t0}))

    print(f"\nPhase 2 modelling complete in {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/phase2/")


if __name__ == "__main__":
    main()
