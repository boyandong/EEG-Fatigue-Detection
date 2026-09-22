"""22 - Phase 1.75 stability comparison: J vs V vs J_res, and the Protocol(B,T) audit.

    python project/vigilance_generalization_v1/scripts/22_dynamic_stability.py

Part D  repeats the Phase 1.5 audit for the three dynamic observables J, V, J_res:
          disjoint-window stability, recording-position sensitivity, 32 / 60 / 120 s,
          session-level and paired NS-SD.
Part E  audits Protocol(B, T) on stability, position bias, paired stability and usable n.

NO PVT ASSOCIATION IS COMPUTED ANYWHERE.

Outputs
  outputs/dynamic_audit/stability_comparison.csv
  outputs/dynamic_audit/position_effect_comparison.csv
  outputs/dynamic_audit/paired_dynamic_stability.csv
  outputs/dynamic_audit/burnin_duration_grid.csv   (enriched)
  outputs/qc/run_manifest_22_dynamic.json
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
import stability_metrics as SM  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

FAMS = ("M", "J", "V", "Jres")
DYN_FAMS = ("J", "V", "Jres")
DUR_LABELS = ("k8", "k15", "k30")
DUR_SECONDS = {"k4": 16, "k8": 32, "k15": 60, "k30": 120}
# Protocol grid: B = 0 is represented by the duration grid (k8/k15/k30), because the two are
# exactly the same windows and must not be duplicated under two names. B > 0 comes from the
# protocol grid.
PROTO_MAP = [
    ("B0_T32", "k8", 0, 32), ("B0_T60", "k15", 0, 60), ("B0_T120", "k30", 0, 120),
    ("B32_T32", "B32_T32", 32, 32), ("B32_T60", "B32_T60", 32, 60), ("B32_T120", "B32_T120", 32, 120),
    ("B60_T32", "B60_T32", 60, 32), ("B60_T60", "B60_T60", 60, 60), ("B60_T120", "B60_T120", 60, 120),
]


def n(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def main() -> None:
    t0 = time.perf_counter()
    out = C.OUTPUTS / "dynamic_audit"
    sess = C.read_csv(out / "J_V_Jres_session.csv")
    pair = C.read_csv(out / "J_V_Jres_paired.csv")
    print(f"session rows {len(sess)}   paired rows {len(pair)}")

    def rec(rows):
        d: dict = {}
        for r in rows:
            d.setdefault((r["subject"], r["session"], r["label"]), []).append(r)
        return d

    by_rec = rec(sess)
    by_pair = {}
    for r in pair:
        by_pair.setdefault((r["subject"], r["label"]), []).append(r)

    # ===================================================== session-level stability
    stab_rows, pos_rows, paired_rows = [], [], []

    for label in DUR_LABELS:
        secs = DUR_SECONDS[label]
        recs = [(k, v) for k, v in by_rec.items() if k[2] == label]
        for fam in FAMS:
            for region in REGION_NAMES:
                col = f"{fam}_{region}"
                # ---- full-session reference scale for this observable
                ref = np.array([n(r[col]) for r in sess if r["is_full_session"].lower() == "true"], float)
                ref = ref[np.isfinite(ref)]
                scale = SM.safe_iqr(ref)

                a, b, icc, per_first, per_second = [], [], [], [], []
                for _, rows in recs:
                    rows = sorted(rows, key=lambda r: int(r["window_index"]))
                    w = np.array([n(r[col]) for r in rows], float)
                    w = w[np.isfinite(w)]
                    if w.size < 2:
                        continue
                    per_first.append(w[0]); per_second.append(w[1])
                    icc.append([w[0], w[1]])
                    for i, j in itertools.combinations(range(w.size), 2):
                        a.append(w[i]); b.append(w[j])
                if len(a) < 3:
                    continue
                a = np.array(a); b = np.array(b)
                rho = SM.rank_stability(a, b)
                ad = SM.absolute_disagreement(a, b)
                nd = SM.normalized_disagreement(a, b, scale)
                ic = SM.icc_2_1(np.array(icc)) if icc else {"icc_2_1": float("nan"), "ci95": [None, None]}
                stab_rows.append({
                    "level": "session", "family": fam, "region": region,
                    "observable": col, "duration": label, "seconds": secs,
                    "n_recordings": len(recs), "n_pairs": int(a.size),
                    "spearman_rho": rho["spearman_rho"], "p_value": rho["p_value"],
                    "median_abs_diff": ad["median_abs_diff"], "p90_abs_diff": ad["p90_abs_diff"],
                    "scale_iqr": scale, "nmae": nd["nmae"],
                    "icc_2_1": ic["icc_2_1"],
                    "icc_ci_low": ic["ci95"][0], "icc_ci_high": ic["ci95"][1],
                })

                # ---- recording-position effect: first / middle / last window
                if len(per_first) >= 3:
                    e = np.array(per_first); m_ = np.array(per_second)
                    mid_idx, late_idx = [], []
                    for _, rows in recs:
                        rows = sorted(rows, key=lambda r: int(r["window_index"]))
                        w = np.array([n(r[col]) for r in rows], float)
                        w = w[np.isfinite(w)]
                        if w.size < 2:
                            continue
                        mid_idx.append(w[(w.size - 1) // 2]); late_idx.append(w[-1])
                    mid = np.array(mid_idx); late = np.array(late_idx)
                    for name, x, y in (("early-middle", e, mid), ("middle-late", mid, late),
                                       ("early-late", e, late)):
                        d = y - x
                        if np.any(d != 0):
                            p = float(stats.wilcoxon(x, y).pvalue)
                        else:
                            p = float("nan")
                        pos_rows.append({
                            "family": fam, "region": region, "observable": col,
                            "duration": label, "seconds": secs, "comparison": name,
                            "n_recordings": int(x.size),
                            "mean_first": float(x.mean()), "mean_second": float(y.mean()),
                            "mean_difference": float(d.mean()),
                            "median_difference": float(np.median(d)),
                            "cohen_dz": float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) > 0 else None,
                            "wilcoxon_p": p,
                        })

    # ===================================================== paired-level stability
    for label in DUR_LABELS:
        secs = DUR_SECONDS[label]
        for fam in DYN_FAMS:
            for region in REGION_NAMES:
                col = f"delta_log{fam}_{region}"
                ref = np.array([n(r[col]) for r in pair if r["label"] == "full"], float)
                ref = ref[np.isfinite(ref)]
                scale = SM.safe_iqr(ref)
                a, b, icc = [], [], []
                for (subj, lab), rows in by_pair.items():
                    if lab != label:
                        continue
                    rows = sorted(rows, key=lambda r: int(r["paired_window_index"]))
                    w = np.array([n(r[col]) for r in rows], float)
                    w = w[np.isfinite(w)]
                    if w.size < 2:
                        continue
                    icc.append([w[0], w[1]])
                    for i, j in itertools.combinations(range(w.size), 2):
                        a.append(w[i]); b.append(w[j])
                if len(a) < 3:
                    continue
                a = np.array(a); b = np.array(b)
                rho = SM.rank_stability(a, b)
                ad = SM.absolute_disagreement(a, b)
                nd = SM.normalized_disagreement(a, b, scale)
                ic = SM.icc_2_1(np.array(icc)) if icc else {"icc_2_1": float("nan"), "ci95": [None, None]}
                paired_rows.append({
                    "level": "paired", "family": fam, "region": region, "observable": col,
                    "duration": label, "seconds": secs, "n_pairs": int(a.size),
                    "spearman_rho": rho["spearman_rho"], "p_value": rho["p_value"],
                    "median_abs_diff": ad["median_abs_diff"], "p90_abs_diff": ad["p90_abs_diff"],
                    "scale_iqr": scale, "nmae": nd["nmae"], "icc_2_1": ic["icc_2_1"],
                })

    C.write_csv(out / "stability_comparison.csv", stab_rows)
    C.write_csv(out / "position_effect_comparison.csv", pos_rows)
    C.write_csv(out / "paired_dynamic_stability.csv", paired_rows)

    # ===================================================== Protocol(B, T) audit
    grid_rows = []
    for proto_label, data_label, B, T in PROTO_MAP:
        label = data_label          # which rows in the session/paired tables to read
        secs = T
        # session-level disjoint stability, averaged over the three dynamic families
        fam_rho, fam_nmae, fam_pos, n_sessions, n_subj_pair, pair_rho, pair_sign = [], [], [], 0, 0, [], []
        per_fam = {}
        for fam in DYN_FAMS:
            vals_rho, vals_nmae, vals_pos = [], [], []
            for region in REGION_NAMES:
                col = f"{fam}_{region}"
                ref = np.array([n(r[col]) for r in sess if r["is_full_session"].lower() == "true"], float)
                ref = ref[np.isfinite(ref)]
                scale = SM.safe_iqr(ref)
                a, b, e, m_, l_ = [], [], [], [], []
                for (subj, ses, lab), rows in by_rec.items():
                    if lab != label:
                        continue
                    rows = sorted(rows, key=lambda r: int(r["window_index"]))
                    w = np.array([n(r[col]) for r in rows], float)
                    w = w[np.isfinite(w)]
                    if w.size < 2:
                        continue
                    e.append(w[0]); m_.append(w[(w.size - 1) // 2]); l_.append(w[-1])
                    for i, j in itertools.combinations(range(w.size), 2):
                        a.append(w[i]); b.append(w[j])
                if len(a) < 3:
                    continue
                a = np.array(a); b = np.array(b)
                rr = SM.rank_stability(a, b)
                nd = SM.normalized_disagreement(a, b, scale)
                vals_rho.append(rr["spearman_rho"]); vals_nmae.append(nd["nmae"])
                if len(e) >= 3:
                    d = np.array(l_) - np.array(e)
                    vals_pos.append(abs(float(d.mean() / d.std(ddof=1))) if d.std(ddof=1) > 0 else np.nan)
            per_fam[fam] = {"rho": float(np.nanmean(vals_rho)) if vals_rho else np.nan,
                            "nmae": float(np.nanmean(vals_nmae)) if vals_nmae else np.nan,
                            "abs_dz_early_late": float(np.nanmean(vals_pos)) if vals_pos else np.nan}
            fam_rho.append(per_fam[fam]["rho"]); fam_nmae.append(per_fam[fam]["nmae"])
            fam_pos.append(per_fam[fam]["abs_dz_early_late"])

        # paired delta stability for this protocol
        for fam in DYN_FAMS:
            for region in REGION_NAMES:
                col = f"delta_log{fam}_{region}"
                a, b = [], []
                for (subj, lab), rows in by_pair.items():
                    if lab != label:
                        continue
                    rows = sorted(rows, key=lambda r: int(r["paired_window_index"]))
                    w = np.array([n(r[col]) for r in rows], float)
                    w = w[np.isfinite(w)]
                    if w.size < 2:
                        continue
                    for i, j in itertools.combinations(range(w.size), 2):
                        a.append(w[i]); b.append(w[j])
                if len(a) >= 3:
                    pair_rho.append(SM.rank_stability(np.array(a), np.array(b))["spearman_rho"])

        # sign agreement of paired change, first window vs the full-session delta
        for fam in DYN_FAMS:
            for region in REGION_NAMES:
                col = f"delta_log{fam}_{region}"
                fref = {r["subject"]: n(r[col]) for r in pair if r["label"] == "full"}
                shorts, refs = [], []
                for (subj, lab), rows in by_pair.items():
                    if lab != label or subj not in fref:
                        continue
                    rows = sorted(rows, key=lambda r: int(r["paired_window_index"]))
                    if rows:
                        shorts.append(n(rows[0][col])); refs.append(fref[subj])
                st = SM.sign_stability(np.array(shorts), np.array(refs))
                if np.isfinite(st["sign_agreement"]):
                    pair_sign.append(st["sign_agreement"])

        n_sessions = sum(1 for (s, ses, lab), rows in by_rec.items()
                         if lab == label and len(rows) >= 2)
        n_subj_pair = sum(1 for (s, lab), rows in by_pair.items() if lab == label and len(rows) >= 2)
        grid_rows.append({
            "protocol": proto_label, "data_label": label,
            "burnin_seconds": B, "measure_seconds": T,
            "n_sessions_eligible": n_sessions,
            "n_subjects_with_2plus_paired": n_subj_pair,
            "mean_rho_session_disjoint": float(np.nanmean(fam_rho)) if fam_rho else np.nan,
            "mean_nmae_session_disjoint": float(np.nanmean(fam_nmae)) if fam_nmae else np.nan,
            "mean_abs_dz_early_late": float(np.nanmean(fam_pos)) if fam_pos else np.nan,
            "mean_rho_paired_disjoint": float(np.nanmean(pair_rho)) if pair_rho else np.nan,
            "mean_sign_agreement_vs_full": float(np.nanmean(pair_sign)) if pair_sign else np.nan,
            **{f"rho_{fam}": per_fam[fam]["rho"] for fam in DYN_FAMS},
            **{f"nmae_{fam}": per_fam[fam]["nmae"] for fam in DYN_FAMS},
            **{f"absdz_{fam}": per_fam[fam]["abs_dz_early_late"] for fam in DYN_FAMS},
        })

    C.write_csv(out / "burnin_duration_grid.csv", grid_rows)
    C.write_json(C.OUTPUTS / "qc" / "run_manifest_22_dynamic.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml", C.CONFIG / "mechanism_v1.yaml"],
        {"n_stability_rows": len(stab_rows), "n_position_rows": len(pos_rows),
         "n_paired_rows": len(paired_rows), "n_grid_rows": len(grid_rows),
         "note": "no PVT association was computed; observables are EEG-side only",
         "elapsed_seconds": time.perf_counter() - t0}))

    # ===================================================== report
    print()
    print("=" * 78)
    print("J vs V vs J_res  -  session-level disjoint stability (rho), 3 ROIs averaged")
    print("=" * 78)
    print("  %-8s %8s %8s %8s | %8s %8s %8s" % ("observable", "32s", "60s", "120s",
                                                "nMAE32", "nMAE60", "nMAE120"))
    for fam in FAMS:
        cells = []
        for lab in DUR_LABELS:
            v = [n(r["spearman_rho"]) for r in stab_rows if r["family"] == fam and r["duration"] == lab]
            cells.append(np.nanmean(v) if v else np.nan)
        nmae = []
        for lab in DUR_LABELS:
            v = [n(r["nmae"]) for r in stab_rows if r["family"] == fam and r["duration"] == lab]
            nmae.append(np.nanmean(v) if v else np.nan)
        print("  %-8s %8.3f %8.3f %8.3f | %8.3f %8.3f %8.3f" % (fam, *cells, *nmae))
    print()
    print("=" * 78)
    print("Recording-position effect  |mean dz| early->late, 3 ROIs averaged")
    print("=" * 78)
    for fam in FAMS:
        cells = []
        for lab in DUR_LABELS:
            v = [n(r["cohen_dz"]) for r in pos_rows
                 if r["family"] == fam and r["duration"] == lab and r["comparison"] == "early-late"]
            cells.append(np.nanmean(np.abs(v)) if v else np.nan)
        print("  %-8s 32s %.3f   60s %.3f   120s %.3f" % (fam, *cells))
    print()
    print("=" * 78)
    print("Protocol(B,T) grid")
    print("=" * 78)
    print("  %-10s %6s %6s %10s %10s %12s %10s %10s" % ("protocol", "B", "T", "sess>=2",
                                                         "subj>=2", "rho_disc", "pair_rho", "sign_agr"))
    for g in grid_rows:
        print("  %-10s %6d %6d %10d %10d %12s %10s %10s" % (
            g["protocol"], g["burnin_seconds"], g["measure_seconds"], g["n_sessions_eligible"],
            g["n_subjects_with_2plus_paired"],
            f"{g['mean_rho_session_disjoint']:.3f}" if np.isfinite(g["mean_rho_session_disjoint"]) else "-",
            f"{g['mean_rho_paired_disjoint']:.3f}" if np.isfinite(g["mean_rho_paired_disjoint"]) else "-",
            f"{g['mean_sign_agreement_vs_full']:.3f}" if np.isfinite(g["mean_sign_agreement_vs_full"]) else "-"))
    print(f"\n  elapsed {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/dynamic_audit/stability_comparison.csv (+ position, paired, grid)")


if __name__ == "__main__":
    main()
