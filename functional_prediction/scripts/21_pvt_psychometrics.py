"""21 - PVT target psychometrics.

    python project/vigilance_generalization_v1/scripts/21_pvt_psychometrics.py

Studies the TARGET only. Reads no EEG feature and produces no EEG-behaviour number.
Trial rule stays frozen at 100 <= RT <= 2000 ms. Raw files are never written.

Outputs
  outputs/pvt_psychometrics/pvt_target_uncertainty.csv
  outputs/pvt_psychometrics/pvt_bootstrap_summary.csv
  outputs/pvt_psychometrics/pvt_split_half.csv
  outputs/pvt_psychometrics/target_reliability_summary.csv
  outputs/qc/run_manifest_21_pvt_psychometrics.json
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import pvt_psychometrics as PP  # noqa: E402
import pvt_targets as PT  # noqa: E402

N_BOOT = 5000
SEED = 20260916
MIN_RT_MS = 100.0
MAX_RT_MS = 2000.0


def main() -> None:
    t0 = time.perf_counter()
    cfg = C.dataset_config()
    out = C.OUTPUTS / "pvt_psychometrics"
    out.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ cohort
    sets = C.json.loads((C.OUTPUTS / "pvt" / "pvt_subject_sets.json").read_text(encoding="utf-8"))
    cohort = list(sets["raw_trial_paired_intersect_eeg"])
    print(f"raw-PVT-paired subjects with admissible EEG: {len(cohort)}")

    bids = C.resolve(cfg["paths"]["bids_root"])
    found = {(s, ses): p for s, ses, p in PT.discover_trial_files(bids)}

    # ------------------------------------------------------------------ parse trials
    trials: dict[tuple[str, str], PP.SessionTrials] = {}
    parse_rows = []
    for subject in cohort:
        for session in ("ses-1", "ses-2"):
            path = found.get((subject, session))
            if path is None:
                continue
            ts, audit = PT.parse_trial_file(path, subject, session, MIN_RT_MS, MAX_RT_MS)
            trials[(subject, session)] = PP.SessionTrials(
                subject=subject, session=session, rt=ts.valid_rt, n_raw_rows=ts.n_rows,
                n_valid=int(ts.valid_rt.size),
                n_removed_out_of_range=int(audit["n_out_of_range_removed"]),
                n_missing=int(audit["n_missing"]) + int(audit["n_invalid"]))
            parse_rows.append({"subject": subject, "session": session,
                               "trial_column": ts.trial_column, "response_column": ts.response_column,
                               "header_variant": ts.header_variant,
                               "n_rows": ts.n_rows, "n_valid": int(ts.valid_rt.size),
                               "n_out_of_range_removed": audit["n_out_of_range_removed"],
                               "n_missing_or_invalid": audit["n_missing"] + audit["n_invalid"]})
    print(f"parsed {len(trials)} subject-sessions")

    # ------------------------------------------------------------------ bootstrap
    recon = {r["subject"]: r for r in C.read_csv(C.OUTPUTS / "pvt" / "pvt_reconciliation.csv")}
    unc_rows, boot_rows = [], []
    for subject in cohort:
        ns = trials.get((subject, "ses-1"))
        sd = trials.get((subject, "ses-2"))
        if ns is None or sd is None:
            continue
        r = PP.paired_trial_bootstrap_both(ns, sd, n_boot=N_BOOT, seed=SEED)
        off = recon.get(subject, {})
        off_ns = off.get("official_median_rt_ns")
        off_sd = off.get("official_median_rt_sd")

        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        off_ns, off_sd = _f(off_ns), _f(off_sd)
        unc_rows.append({
            "subject": subject,
            "n_valid_trials_NS": r["n_trials_ns"], "n_valid_trials_SD": r["n_trials_sd"],
            "median_rt_NS": r["median_rt_ns"], "median_rt_SD": r["median_rt_sd"],
            "speed_NS": r["speed_ns"], "speed_SD": r["speed_sd"],
            "Y_RT_point": r["Y_RT_point"], "Y_RT_se": r["Y_RT_se"],
            "Y_RT_ci_low": r["Y_RT_ci_low"], "Y_RT_ci_high": r["Y_RT_ci_high"],
            "Y_speed_point": r["Y_speed_point"], "Y_speed_se": r["Y_speed_se"],
            "Y_speed_ci_low": r["Y_speed_ci_low"], "Y_speed_ci_high": r["Y_speed_ci_high"],
            "Y_RT_ci_excludes_zero": bool(np.isfinite(r["Y_RT_ci_low"]) and r["Y_RT_ci_low"] > 0
                                          or np.isfinite(r["Y_RT_ci_high"]) and r["Y_RT_ci_high"] < 0),
            "Y_speed_ci_excludes_zero": bool(np.isfinite(r["Y_speed_ci_low"]) and r["Y_speed_ci_low"] > 0
                                             or np.isfinite(r["Y_speed_ci_high"]) and r["Y_speed_ci_high"] < 0),
            "n_boot_used": r["n_boot_used"],
            # --- official summary values: SENSITIVITY ONLY, never used to choose a target
            "official_median_rt_NS": off_ns, "official_median_rt_SD": off_sd,
            "official_delta_ms": (off_sd - off_ns) if (off_ns is not None and off_sd is not None) else None,
            "raw_minus_official_NS": (r["median_rt_ns"] - off_ns) if off_ns is not None else None,
            "raw_minus_official_SD": (r["median_rt_sd"] - off_sd) if off_sd is not None else None,
        })

    # ------------------------------------------------------------------ split-half
    sh_rows = []
    for subject in cohort:
        ns = trials.get((subject, "ses-1"))
        sd = trials.get((subject, "ses-2"))
        if ns is None or sd is None:
            continue
        ns_o, ns_e = PP.interleaved_split_half(ns.rt)
        sd_o, sd_e = PP.interleaved_split_half(sd.rt)
        y_rt_o = PP.y_median_rt(ns_o, sd_o)
        y_rt_e = PP.y_median_rt(ns_e, sd_e)
        y_sp_o = PP.y_speed(ns_o, sd_o)
        y_sp_e = PP.y_speed(ns_e, sd_e)
        sh_rows.append({
            "subject": subject,
            "Y_RT_odd": y_rt_o, "Y_RT_even": y_rt_e,
            "Y_speed_odd": y_sp_o, "Y_speed_even": y_sp_e,
            "n_odd_NS": int(ns_o.size), "n_even_NS": int(ns_e.size),
            "n_odd_SD": int(sd_o.size), "n_even_SD": int(sd_e.size),
            "Y_RT_full": PP.y_median_rt(ns.rt, sd.rt),
            "Y_speed_full": PP.y_speed(ns.rt, sd.rt),
        })

    # ------------------------------------------------------------------ reliability
    def rel(rows, prefix):
        y = np.array([r[f"{prefix}_point"] for r in rows], float)
        se = np.array([r[f"{prefix}_se"] for r in rows], float)
        return PP.approximate_reliability(y, se)

    rel_rt = rel(unc_rows, "Y_RT")
    rel_sp = rel(unc_rows, "Y_speed")

    def split_half_stats(rows, prefix):
        a = np.array([r[f"{prefix}_odd"] for r in rows], float)
        b = np.array([r[f"{prefix}_even"] for r in rows], float)
        ok = np.isfinite(a) & np.isfinite(b)
        a, b = a[ok], b[ok]
        if a.size < 3:
            return {"n": int(a.size)}
        rho = stats.spearmanr(a, b)
        pear = stats.pearsonr(a, b)
        # Spearman-Brown correction for the split-half length (2 x half = full)
        sb = 2 * pear.statistic / (1 + pear.statistic) if pear.statistic > -1 else float("nan")
        d = a - b
        nz = (a != 0) & (b != 0)
        return {
            "n": int(a.size),
            "spearman_odd_even": float(rho.statistic), "p_value": float(rho.pvalue),
            "pearson_odd_even": float(pear.statistic),
            "spearman_brown_corrected": float(sb),
            "median_abs_difference": float(np.median(np.abs(d))),
            "p90_abs_difference": float(np.percentile(np.abs(d), 90)),
            "median_signed_difference": float(np.median(d)),
            "sign_agreement": float((np.sign(a[nz]) == np.sign(b[nz])).mean()) if nz.sum() else float("nan"),
            "n_comparable_sign": int(nz.sum()),
        }

    sh_rt = split_half_stats(sh_rows, "Y_RT")
    sh_sp = split_half_stats(sh_rows, "Y_speed")

    # ------------------------------------------------------------------ write
    C.write_csv(out / "pvt_target_uncertainty.csv", unc_rows)
    C.write_csv(out / "pvt_trial_parse_audit.csv", parse_rows)
    C.write_csv(out / "pvt_split_half.csv", sh_rows)

    boot_summary = []
    for name, rows, prefix in (("Y_RT", unc_rows, "Y_RT"), ("Y_speed", unc_rows, "Y_speed")):
        y = np.array([r[f"{prefix}_point"] for r in rows], float)
        se = np.array([r[f"{prefix}_se"] for r in rows], float)
        ok = np.isfinite(y) & np.isfinite(se)
        boot_summary.append({
            "target": name, "n_subjects": int(ok.sum()),
            "point_mean": float(y[ok].mean()), "point_sd": float(y[ok].std(ddof=1)),
            "point_median": float(np.median(y[ok])),
            "mean_SE": float(se[ok].mean()), "median_SE": float(np.median(se[ok])),
            "min_SE": float(se[ok].min()), "max_SE": float(se[ok].max()),
            "mean_SE_over_point_sd": float(se[ok].mean() / y[ok].std(ddof=1)),
            "frac_positive_point": float((y[ok] > 0).mean()),
            "n_ci_excluding_zero": int(sum(1 for r in rows if r[f"{prefix}_ci_excludes_zero"])),
            "n_boot": N_BOOT, "seed": SEED,
        })
    C.write_csv(out / "pvt_bootstrap_summary.csv", boot_summary)

    rel_rows = [
        {"target": "Y_RT", **rel_rt, **{f"split_half_{k}": v for k, v in sh_rt.items()}},
        {"target": "Y_speed", **rel_sp, **{f"split_half_{k}": v for k, v in sh_sp.items()}},
    ]
    C.write_csv(out / "target_reliability_summary.csv", rel_rows)

    C.write_json(C.OUTPUTS / "qc" / "run_manifest_21_pvt_psychometrics.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml"],
        {"n_cohort": len(cohort), "n_boot": N_BOOT, "seed": SEED,
         "rt_window_ms": [MIN_RT_MS, MAX_RT_MS],
         "note": "target-only audit; no EEG feature was read; no EEG-behaviour statistic computed",
         "elapsed_seconds": time.perf_counter() - t0}))

    # ------------------------------------------------------------------ report
    print()
    print("=" * 78)
    print("PVT TARGET PSYCHOMETRICS")
    print("=" * 78)
    for b in boot_summary:
        print(f"  {b['target']:<8} n={b['n_subjects']}  point {b['point_mean']:+.4f} "
              f"(sd {b['point_sd']:.4f})  mean SE {b['mean_SE']:.4f}  "
              f"SE/sd {b['mean_SE_over_point_sd']:.3f}  CI excl 0: {b['n_ci_excluding_zero']}/{b['n_subjects']}")
    print()
    for r in rel_rows:
        print(f"  {r['target']:<8} R_approx = {r['R_approx']:.4f}   "
              f"(sigma_eps^2 {r['sigma_eps_squared']:.5f} / s_Y^2 {r['s_Y_squared']:.5f})   "
              f"split-half rho {r.get('split_half_spearman_odd_even', float('nan')):+.3f}  "
              f"SB {r.get('split_half_spearman_brown_corrected', float('nan')):+.3f}  "
              f"sign {r.get('split_half_sign_agreement', float('nan')):.3f}")
    print(f"\n  elapsed {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/pvt_psychometrics/")


if __name__ == "__main__":
    main()
