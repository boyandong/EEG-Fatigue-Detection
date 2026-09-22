"""11 - Phase 1.5 stability metrics: Experiments A, B, C, plus delta and baseline scenarios.

    python project/vigilance_generalization_v1/scripts/11_stability_metrics.py

Implements the Phase 1.5 brief:
  section 6  Experiment A  disjoint-window stability        (PRIMARY)
  section 7  Experiment B  recording-position sensitivity
  section 8  Experiment C  accumulation / convergence       (explicitly NOT independent)
  section 9  Level 1 session features + Level 2 paired change
  section 10 long-baseline -> short-current, duration-matched
  section 11 metrics: Spearman, median|d|, P90|d|, nMAE, Bland-Altman, sign stability
  section 12 ICC as a labelled secondary metric

All agreement is reported with its source labelled: `disjoint` (independent, equal-length),
`prefix_complement` (unequal length), or `accumulation` (prefix CONTAINED in full).

Outputs
  outputs/stability_v1/duration_summary.csv
  outputs/stability_v1/disjoint_agreement.csv
  outputs/stability_v1/position_drift.csv
  outputs/stability_v1/accumulation_convergence.csv
  outputs/stability_v1/delta_sign_stability.csv
  outputs/stability_v1/baseline_scenario.csv
  outputs/stability_v1/stability_stats.json
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import stability as ST  # noqa: E402
import stability_metrics as SM  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

DUR_ORDER = [n for n, _ in ST.DURATIONS]
DELTA_FEATURES = [f"delta_M_{r}" for r in REGION_NAMES] + [f"delta_logJ_{r}" for r in REGION_NAMES]


# --------------------------------------------------------------------------- helpers
def load_tables():
    sess = C.read_csv(C.OUTPUTS / "stability_v1" / "session_window_features.csv")
    pair = C.read_csv(C.OUTPUTS / "stability_v1" / "paired_window_features.csv")
    for r in sess:
        for f in ST.SESSION_FEATURES:
            r[f] = float(r[f])
        r["n_epochs"] = int(r["n_epochs"])
        r["window_index"] = int(r["window_index"])
    for r in pair:
        for f in DELTA_FEATURES:
            r[f] = float(r[f])
        r["paired_window_index"] = int(r["paired_window_index"])
    return sess, pair


def group_by(rows, keyfn):
    out: dict = {}
    for r in rows:
        out.setdefault(keyfn(r), []).append(r)
    return out


def full_session_values(sess, feature):
    """Between-recording reference scale: all full-session values of a feature."""
    v = np.array([r[feature] for r in sess if r["is_full_session"]], dtype=float)
    return v[np.isfinite(v)]


def summary_row(feature, scope, duration, rho, ad, nmae, ba, icc, n_units, extra=None):
    row = {
        "feature": feature, "scope": scope, "duration": duration,
        "epochs_per_window": None if duration == "full" else int(duration[1:]),
        "seconds_per_window": None if duration == "full" else int(duration[1:]) * 4,
        "n_recordings": n_units,
        "spearman_rho": rho.get("spearman_rho"),
        "spearman_p": rho.get("p_value"),
        "spearman_n": rho.get("n"),
        "median_abs_diff": ad.get("median_abs_diff"),
        "p90_abs_diff": ad.get("p90_abs_diff"),
        "scale_iqr": nmae.get("scale_iqr"),
        "nmae": nmae.get("nmae"),
        "ba_median_diff": ba.get("median_difference"),
        "ba_loa_low": ba.get("empirical_loa_low"),
        "ba_loa_high": ba.get("empirical_loa_high"),
        "ba_bias_classical": ba.get("classical_bias"),
        "ba_slope_vs_mean": ba.get("slope_diff_vs_mean"),
        "icc_2_1": icc.get("icc_2_1"),
        "icc_ci_low": (icc.get("ci95") or [None, None])[0],
        "icc_ci_high": (icc.get("ci95") or [None, None])[1],
    }
    if extra:
        row.update(extra)
    return row


def main() -> None:
    t0 = time.perf_counter()
    out = C.OUTPUTS / "stability_v1"
    (out / "plots").mkdir(parents=True, exist_ok=True)
    sess, pair = load_tables()
    print(f"session window rows: {len(sess)}   paired window rows: {len(pair)}")

    summary_rows: list[dict] = []
    disjoint_rows: list[dict] = []
    stats_blob: dict = {"scope": "within-session estimator stability; NOT test-retest reliability"}

    # ==================================================================== LEVEL 1
    # Experiment A: disjoint-window agreement (PRIMARY)
    print("\n" + "=" * 78)
    print("EXPERIMENT A  disjoint-window stability (PRIMARY)")
    print("=" * 78)
    sess_by_rec = group_by(sess, lambda r: (r["subject"], r["session"], r["duration"]))

    for feature in ST.SESSION_FEATURES:
        for dur in DUR_ORDER:
            if dur == "full":
                continue
            ref = full_session_values(sess, feature)
            scale_iqr = SM.safe_iqr(ref)
            recs = [v for k, v in sess_by_rec.items() if k[2] == dur]
            a_list, b_list, icc_mat, per_rec_stats = [], [], [], []
            for rows in recs:
                rows = sorted(rows, key=lambda r: r["window_index"])
                w = np.array([r[feature] for r in rows], float)
                w = w[np.isfinite(w)]
                if w.size < 2:
                    continue
                for i, j in itertools.combinations(range(w.size), 2):
                    a_list.append(w[i]); b_list.append(w[j])
                icc_mat.append([w[0], w[1]])
                per_rec_stats.append({"subject": rows[0]["subject"], "session": rows[0]["session"],
                                      "n_windows": int(w.size),
                                      "median": float(np.median(w)),
                                      "sd": float(w.std(ddof=1)) if w.size > 1 else float("nan")})
            a = np.array(a_list); b = np.array(b_list)
            rho = SM.rank_stability(a, b)
            ad = SM.absolute_disagreement(a, b)
            nmae = SM.normalized_disagreement(a, b, scale_iqr)
            ba = SM.bland_altman(a, b)
            icc = SM.icc_2_1(np.array(icc_mat)) if icc_mat else {"icc_2_1": float("nan"), "ci95": [None, None]}
            summary_rows.append(summary_row(feature, "session_feature", dur, rho, ad, nmae, ba, icc, len(recs),
                                            extra={"source": "disjoint"}))
            disjoint_rows.append({"feature": feature, "duration": dur, "n_recordings": len(recs),
                                  "n_pairs": int(a.size), **rho, **ad, "nmae": nmae.get("nmae"),
                                  "scale_iqr": scale_iqr, **{f"ba_{k}": v for k, v in ba.items()},
                                  "icc_2_1": icc.get("icc_2_1")})
            stats_blob.setdefault("level1_disjoint", {})[f"{feature}|{dur}"] = {
                **rho, **ad, "nmae": nmae.get("nmae"), "icc_2_1": icc.get("icc_2_1"),
                "n_recordings": len(recs)}
            print(f"  {feature:<8} {dur:<5} recs={len(recs):3d} pairs={a.size:5d} "
                  f"rho={rho['spearman_rho']:+.3f} med|d|={ad['median_abs_diff']:.4f} "
                  f"P90={ad['p90_abs_diff']:.4f} nMAE={nmae['nmae'] if nmae['nmae'] is not None else float('nan'):.3f} "
                  f"ICC={icc.get('icc_2_1', float('nan')):+.3f}")

    # ==================================================================== Experiment B
    print("\n" + "=" * 78)
    print("EXPERIMENT B  recording-position sensitivity (early / middle / late)")
    print("=" * 78)
    position_rows: list[dict] = []
    for feature in ST.SESSION_FEATURES:
        for dur in [d for d in DUR_ORDER if d != "full"]:
            k = int(dur[1:])
            early, middle, late = [], [], []
            for rows in sess_by_rec.values():
                if rows[0]["duration"] != dur:
                    continue
                rows = sorted(rows, key=lambda r: r["window_index"])
                w = np.array([r[feature] for r in rows], float)
                if w.size < 2:
                    continue
                mid = (w.size - 1) // 2
                early.append(w[0]); middle.append(w[mid]); late.append(w[-1])
            if len(early) < 3:
                continue
            e = np.array(early); m = np.array(middle); l = np.array(late)
            for label, x, y in (("early-middle", e, m), ("middle-late", m, l), ("early-late", e, l)):
                d = y - x
                tt = stats.wilcoxon(x, y) if np.any(d != 0) else None
                position_rows.append({
                    "feature": feature, "duration": dur, "comparison": label,
                    "n_recordings": int(len(e)),
                    "mean_first": float(x.mean()), "mean_second": float(y.mean()),
                    "mean_difference": float(d.mean()), "median_difference": float(np.median(d)),
                    "sd_difference": float(d.std(ddof=1)),
                    "cohen_dz": float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) > 0 else None,
                    "wilcoxon_p": float(tt.pvalue) if tt is not None else None,
                    "median_abs_difference": float(np.median(np.abs(d))),
                    "spearman_first_second": float(SM.rank_stability(x, y)["spearman_rho"]),
                })
    for r in position_rows:
        if r["comparison"] == "early-late":
            print(f"  {r['feature']:<8} {r['duration']:<5} early->late "
                  f"meanD={r['mean_difference']:+.4f} dz={r['cohen_dz']:+.3f} "
                  f"p={r['wilcoxon_p']:.4f} rho={r['spearman_first_second']:+.3f} n={r['n_recordings']}")
    stats_blob["experiment_B_position_drift"] = position_rows

    # ==================================================================== Experiment C
    print("\n" + "=" * 78)
    print("EXPERIMENT C  accumulation / convergence (prefix CONTAINED in full)")
    print("=" * 78)
    acc_rows: list[dict] = []
    full_by_rec = {(r["subject"], r["session"]): r for r in sess if r["is_full_session"]}
    for feature in ST.SESSION_FEATURES:
        for dur in [d for d in DUR_ORDER if d != "full"]:
            a_list, b_list = [], []
            for (subj, ses), frow in full_by_rec.items():
                rows = [r for r in sess_by_rec.get((subj, ses, dur), [])]
                if not rows:
                    continue
                first = sorted(rows, key=lambda r: r["window_index"])[0]
                a_list.append(first[feature]); b_list.append(frow[feature])
            if len(a_list) < 3:
                continue
            a = np.array(a_list); b = np.array(b_list)
            scale_iqr = SM.safe_iqr(np.array([r[feature] for r in full_by_rec.values()], float))
            rho = SM.rank_stability(a, b)
            ad = SM.absolute_disagreement(a, b)
            nmae = SM.normalized_disagreement(a, b, scale_iqr)
            acc_rows.append({"feature": feature, "duration": dur, "n_recordings": len(a),
                             "source": "accumulation_prefix_contained_in_full", **rho, **ad,
                             "nmae": nmae.get("nmae"), "scale_iqr": scale_iqr,
                             "median_signed_difference": float(np.median(a - b))})
            print(f"  {feature:<8} {dur:<5} rho={rho['spearman_rho']:+.3f} "
                  f"med|d|={ad['median_abs_diff']:.4f} P90={ad['p90_abs_diff']:.4f} "
                  f"nMAE={nmae['nmae']:.3f} medSigned={np.median(a-b):+.4f}")
    stats_blob["experiment_C_accumulation"] = acc_rows

    # ==================================================================== LEVEL 2
    print("\n" + "=" * 78)
    print("LEVEL 2  personal-relative (delta) stability: disjoint paired windows")
    print("=" * 78)
    pair_by_sub = group_by(pair, lambda r: (r["subject"], r["duration"]))
    delta_rows: list[dict] = []
    delta_summary: list[dict] = []
    full_delta = {}
    for feature in DELTA_FEATURES:
        for dur in [d for d in DUR_ORDER if d != "full"]:
            a_list, b_list, icc_mat = [], [], []
            for (subj, d), rows in pair_by_sub.items():
                if d != dur:
                    continue
                rows = sorted(rows, key=lambda r: r["paired_window_index"])
                w = np.array([r[feature] for r in rows], float)
                w = w[np.isfinite(w)]
                if w.size < 2:
                    continue
                for i, j in itertools.combinations(range(w.size), 2):
                    a_list.append(w[i]); b_list.append(w[j])
                icc_mat.append([w[0], w[1]])
            if len(a_list) < 3:
                continue
            a = np.array(a_list); b = np.array(b_list)
            # reference scale: full-duration delta values
            if dur == "k4":
                pass
            ref = np.array([r[feature] for r in pair if r["duration"] == "full"], float)
            ref = ref[np.isfinite(ref)]
            scale_iqr = SM.safe_iqr(ref)
            rho = SM.rank_stability(a, b); ad = SM.absolute_disagreement(a, b)
            nmae = SM.normalized_disagreement(a, b, scale_iqr)
            icc = SM.icc_2_1(np.array(icc_mat)) if icc_mat else {"icc_2_1": float("nan"), "ci95": [None, None]}
            delta_rows.append({"feature": feature, "duration": dur, "source": "disjoint",
                               "n_subjects_pairs": int(a.size), **rho, **ad,
                               "nmae": nmae.get("nmae"), "scale_iqr": scale_iqr,
                               "icc_2_1": icc.get("icc_2_1")})
            delta_summary.append(summary_row(feature, "delta_feature", dur, rho, ad, nmae,
                                             SM.bland_altman(a, b), icc, int(a.size),
                                             extra={"source": "disjoint"}))
            print(f"  {feature:<14} {dur:<5} pairs={a.size:5d} rho={rho['spearman_rho']:+.3f} "
                  f"med|d|={ad['median_abs_diff']:.4f} P90={ad['p90_abs_diff']:.4f} "
                  f"nMAE={nmae['nmae']:.3f} ICC={icc.get('icc_2_1', float('nan')):+.3f}")
    stats_blob["level2_delta_disjoint"] = delta_rows

    # sign stability of delta features, labelled by agreement source
    print("\n  sign stability of paired change (reference = full-duration delta)")
    sign_rows: list[dict] = []
    for feature in DELTA_FEATURES:
        fref = {r["subject"]: r[feature] for r in pair if r["duration"] == "full"}
        for dur in [d for d in DUR_ORDER if d != "full"]:
            shorts, refs = [], []
            for (subj, d), rows in pair_by_sub.items():
                if d != dur or subj not in fref:
                    continue
                rows = sorted(rows, key=lambda r: r["paired_window_index"])
                shorts.append(rows[0][feature]); refs.append(fref[subj])
            st = SM.sign_stability(np.array(shorts), np.array(refs))
            sign_rows.append({"feature": feature, "duration": dur,
                              "short_source": "first_disjoint_window",
                              "reference_source": "full_session_containing_short",
                              **st})
    for r in sign_rows:
        if r["duration"] in ("k8", "k15", "k30"):
            print(f"    {r['feature']:<14} {r['duration']:<5} sign agreement="
                  f"{r['sign_agreement']:.3f} (n={r['n_comparable']})")
    stats_blob["delta_sign_stability"] = sign_rows

    # ==================================================================== section 10
    print("\n" + "=" * 78)
    print("SECTION 10  long-baseline -> short-current (duration-matched baseline)")
    print("=" * 78)
    # baseline (NS) is cut into k-length disjoint windows; the reference is their MEDIAN.
    # current (SD) uses ONE k-length window. Same k on both sides, so the estimator sample
    # size is identical and J comparisons are apples-to-apples.
    # NB: raw M_/J_ values live in the SESSION table; the paired table stores deltas only.
    base_rows: list[dict] = []
    for dur in ["k8", "k15", "k30"]:
        for region in REGION_NAMES:
            for family in ("M", "J"):
                key = f"{family}_{region}"
                errs_full, errs_base = [], []
                for subject in sorted({r["subject"] for r in sess}):
                    sd_rows = sorted([r for r in sess if r["subject"] == subject
                                      and r["session"] == "ses-2" and r["duration"] == dur],
                                     key=lambda r: r["window_index"])
                    ns_rows = sorted([r for r in sess if r["subject"] == subject
                                      and r["session"] == "ses-1" and r["duration"] == dur],
                                     key=lambda r: r["window_index"])
                    if not sd_rows or len(ns_rows) < 2:
                        continue
                    ns_vals = np.array([r[key] for r in ns_rows], float)
                    ns_vals = ns_vals[np.isfinite(ns_vals)]
                    if ns_vals.size < 2:
                        continue
                    sd_val = float(sd_rows[0][key])
                    base_med = float(np.median(ns_vals))
                    base_first = float(ns_vals[0])
                    if family == "M":
                        errs_full.append(sd_val - base_med)
                        errs_base.append(sd_val - base_first)
                    else:
                        if base_med > 0 and base_first > 0 and sd_val > 0:
                            errs_full.append(float(np.log(sd_val / base_med)))
                            errs_base.append(float(np.log(sd_val / base_first)))
                if len(errs_full) < 3:
                    continue
                ef = np.array(errs_full); eb = np.array(errs_base)
                rho = SM.rank_stability(eb, ef)
                base_rows.append({
                    "duration": dur, "region": region, "family": family,
                    "n_subjects": int(ef.size),
                    "median_delta_matched_baseline": float(np.median(ef)),
                    "iqr_delta_matched_baseline": SM.safe_iqr(ef),
                    "median_delta_single_window_baseline": float(np.median(eb)),
                    "iqr_delta_single_window_baseline": SM.safe_iqr(eb),
                    "spearman_single_vs_matched": rho["spearman_rho"],
                    "median_abs_diff_single_vs_matched": float(np.median(np.abs(eb - ef))),
                })
                print(f"  {dur:<5} {family} {region:<3} n={ef.size:2d} "
                      f"matched-baseline median={np.median(ef):+.4f} IQR={SM.safe_iqr(ef):.4f} | "
                      f"single-window median={np.median(eb):+.4f} IQR={SM.safe_iqr(eb):.4f} | "
                      f"rho={rho['spearman_rho']:+.3f}")
    stats_blob["section10_baseline_scenario"] = base_rows

    # ==================================================================== write
    cols_summary = ["feature", "scope", "duration", "epochs_per_window", "seconds_per_window",
                    "source", "n_recordings", "spearman_rho", "spearman_p", "spearman_n",
                    "median_abs_diff", "p90_abs_diff", "scale_iqr", "nmae",
                    "ba_median_diff", "ba_loa_low", "ba_loa_high", "ba_bias_classical",
                    "ba_slope_vs_mean", "icc_2_1", "icc_ci_low", "icc_ci_high"]
    # Experiment A summary is the "duration_summary.csv"
    dur_summary = [r for r in summary_rows if r["scope"] == "session_feature"]
    C.write_csv(out / "duration_summary.csv", dur_summary, cols_summary)
    C.write_csv(out / "disjoint_agreement.csv", disjoint_rows)
    C.write_csv(out / "position_drift.csv", position_rows)
    C.write_csv(out / "accumulation_convergence.csv", acc_rows)
    C.write_csv(out / "delta_sign_stability.csv", sign_rows)
    C.write_csv(out / "baseline_scenario.csv", base_rows)
    C.write_csv(out / "delta_duration_summary.csv", delta_summary, cols_summary)
    C.write_json(out / "stability_stats.json", stats_blob)
    print(f"\nelapsed {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/stability_v1/{duration_summary,disjoint_agreement,position_drift,")
    print("      accumulation_convergence,delta_sign_stability,baseline_scenario}.csv")


if __name__ == "__main__":
    main()
