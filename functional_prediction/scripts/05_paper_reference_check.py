"""05 - Paper-reference reproduction sanity check.

    python project/vigilance_generalization_v1/scripts/05_paper_reference_check.py

PURPOSE: implementation-validity check only. This is NOT our contribution and NOT an
optimisation target. Per SCIENTIFIC_SPEC.md section 11, if the reproduction disagrees with
the published values we ANALYSE AND REPORT the reason. We do not tune preprocessing, bands,
ROIs, subject sets or outliers to move rho.

Statistic:
  Delta theta variability_r = sigma_theta_r(SD) - sigma_theta_r(NS)
  rho = Spearman( Delta theta variability_r , Delta median RT )
where sigma_theta is the across-epoch SD of epoch-wise theta RELATIVE power (the paper's
definition), not our log-ratio J.

Reference values quoted from the source paper: rho_F ~ 0.54, rho_CT ~ 0.56.

Outputs
  outputs/paper_reference/reproduction_report.md
  outputs/paper_reference/reproduction_stats.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402

REGIONS = ("F", "CT", "PO")
REFERENCE = {"F": 0.54, "CT": 0.56, "PO": None}
N_BOOT = 5000
BOOT_SEED = 20260916


def _col(rows: list[dict], key: str) -> np.ndarray:
    return np.array([float(r[key]) for r in rows if r.get(key) not in (None, "")], dtype=float)


def spearman_with_ci(x: np.ndarray, y: np.ndarray, n_boot: int = N_BOOT) -> dict:
    rho, p = stats.spearmanr(x, y)
    # subject-level bootstrap CI for the rank correlation
    rng = np.random.default_rng(BOOT_SEED)
    n = len(x)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(x[idx])) < 2 or len(np.unique(y[idx])) < 2:
            continue
        boots.append(stats.spearmanr(x[idx], y[idx]).statistic)
    lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if boots else (np.nan, np.nan)
    return {"n": int(n), "spearman_rho": float(rho), "p_value": float(p),
            "bootstrap_ci95": [lo, hi], "n_bootstrap": len(boots)}


def main() -> None:
    pp = C.read_csv(C.OUTPUTS / "paper_reference" / "paired_features.csv")
    sess = C.read_csv(C.OUTPUTS / "paper_reference" / "session_features.csv")
    n = len(pp)
    print(f"paired subjects: {n}")

    # -------------------------------------------------------------- primary statistic
    out: dict = {"n_subjects": n, "reference_values": REFERENCE, "regions": {}}

    d_rt_ms = _col(pp, "delta_median_rt_ms_paper_compatible")
    d_rt_log = _col(pp, "Y_log_medianRT_raw")

    print()
    print("=" * 78)
    print("rho( Delta theta variability , Delta median RT )   [paper: F~0.54, CT~0.56]")
    print("=" * 78)
    for r in REGIONS:
        v = _col(pp, f"delta_theta_sigma_{r}")
        s_ms = spearman_with_ci(v, d_rt_ms)
        s_log = spearman_with_ci(v, d_rt_log)
        pear = stats.pearsonr(v, d_rt_ms)
        delta_mean = float(v.mean())
        t, p_t = stats.ttest_1samp(v, 0.0)
        out["regions"][r] = {
            "delta_theta_variability_mean": delta_mean,
            "delta_theta_variability_sd": float(v.std(ddof=1)),
            "delta_theta_variability_paired_t": float(t),
            "delta_theta_variability_p": float(p_t),
            "spearman_vs_delta_rt_ms": s_ms,
            "spearman_vs_log_rt": s_log,
            "pearson_vs_delta_rt_ms": {"r": float(pear.statistic), "p": float(pear.pvalue)},
            "reference_rho": REFERENCE[r],
            "difference_from_reference": (None if REFERENCE[r] is None
                                          else float(s_ms["spearman_rho"] - REFERENCE[r])),
        }
        ref = "n/a" if REFERENCE[r] is None else f"{REFERENCE[r]:+.2f}"
        print(f"  {r:<3} rho={s_ms['spearman_rho']:+.3f} p={s_ms['p_value']:.4f} "
              f"CI95=[{s_ms['bootstrap_ci95'][0]:+.3f},{s_ms['bootstrap_ci95'][1]:+.3f}]  "
              f"| reference {ref}  | rho(logRT)={s_log['spearman_rho']:+.3f}")
    print()
    print("  Delta theta variability group change (SD - NS):")
    for r in REGIONS:
        m = out["regions"][r]
        print(f"    {r:<3} mean={m['delta_theta_variability_mean']:+.4f} "
              f"sd={m['delta_theta_variability_sd']:.4f} p={m['delta_theta_variability_p']:.4f}")

    # -------------------------------------------------------------- theta mean change
    print()
    print("=" * 78)
    print("Group-level SD-NS change, theta RELATIVE POWER mean (paper-compatible)")
    print("=" * 78)
    out["theta_relative_mean_change"] = {}
    for r in REGIONS:
        v = _col(pp, f"delta_theta_mu_{r}")
        t, p = stats.ttest_1samp(v, 0.0)
        se = v.std(ddof=1) / np.sqrt(len(v))
        out["theta_relative_mean_change"][r] = {
            "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
            "ci95": [float(v.mean() - 1.96 * se), float(v.mean() + 1.96 * se)],
            "t": float(t), "p": float(p), "cohen_dz": float(v.mean() / v.std(ddof=1)),
        }
        print(f"  {r:<3} delta={v.mean():+.4f} CI95=[{v.mean()-1.96*se:+.4f},{v.mean()+1.96*se:+.4f}] "
              f"t={t:+.2f} p={p:.4f} dz={v.mean()/v.std(ddof=1):+.3f}")

    # -------------------------------------------------------------- alpha / beta context
    print()
    print("=" * 78)
    print("Context: same statistic for alpha and beta variability")
    print("=" * 78)
    out["other_bands"] = {}
    for band in ("alpha", "beta"):
        out["other_bands"][band] = {}
        cells = []
        for r in REGIONS:
            v = _col(pp, f"delta_{band}_sigma_{r}")
            s = spearman_with_ci(v, d_rt_ms, n_boot=1000)
            out["other_bands"][band][r] = s
            cells.append(f"{r}:{s['spearman_rho']:+.3f}(p={s['p_value']:.3f})")
        print(f"  {band:<6} " + "  ".join(cells))

    # -------------------------------------------------------------- per-session table
    print()
    print("=" * 78)
    print("Per-session theta relative power and variability (ROI means)")
    print("=" * 78)
    print(f"  {'subject':<8}{'cond':<5}{'mu_F':>9}{'mu_CT':>9}{'mu_PO':>9}"
          f"{'sig_F':>9}{'sig_CT':>9}{'sig_PO':>9}")
    for row in sess:
        print(f"  {row['subject']:<8}{row['condition']:<5}"
              f"{float(row['mu_theta_F']):9.4f}{float(row['mu_theta_CT']):9.4f}{float(row['mu_theta_PO']):9.4f}"
              f"{float(row['sigma_theta_F']):9.4f}{float(row['sigma_theta_CT']):9.4f}{float(row['sigma_theta_PO']):9.4f}")

    # -------------------------------------------------------------- sensitivity (report only)
    sets = C.json.loads((C.OUTPUTS / "pvt" / "pvt_subject_sets.json").read_text(encoding="utf-8"))
    cand = sets.get("published_n_alternative_filters", {})
    out["n28_filter_sensitivity"] = {
        "note": ("Reported for transparency only. We do NOT adopt any of these filters; the "
                 "working cohort is the unfiltered 29 raw-PVT-paired subjects with EEG."),
        "candidates_yielding_28": cand.get("filters_yielding_28", []),
        "counts": {c["filter"]: c["n"] for c in cand.get("candidates", [])},
    }
    if cand.get("filters_yielding_28"):
        drop = set()
        for c in cand["candidates"]:
            if c["yields_28"]:
                drop = set(c["removes"])
        keep = [r for r in pp if r["subject"] not in drop]
        out["n28_filter_sensitivity"]["rho_if_that_filter_were_applied"] = {}
        for r in REGIONS:
            v = _col(keep, f"delta_theta_sigma_{r}")
            y = _col(keep, "delta_median_rt_ms_paper_compatible")
            s = spearman_with_ci(v, y, n_boot=1000)
            out["n28_filter_sensitivity"]["rho_if_that_filter_were_applied"][r] = s
            print(f"\n  [sensitivity, NOT adopted] dropping {sorted(drop)}: "
                  f"{r} rho={s['spearman_rho']:+.3f} (p={s['p_value']:.3f})")

    C.write_json(C.OUTPUTS / "paper_reference" / "reproduction_stats.json", out)

    # -------------------------------------------------------------- markdown report
    md = ["# Paper-reference reproduction report", "",
          f"Paired subjects: **n = {n}**  ",
          "Cohort: admissible eyes-open 500 Hz EEG **and** raw-PVT-paired, both sessions.  ",
          "Reference values quoted from the source paper: rho_F ~ 0.54, rho_CT ~ 0.56.", "",
          "> This is an implementation-validity check, not our contribution and not an",
          "> optimisation target. Preprocessing, bands, ROIs and the subject set were held",
          "> fixed; nothing was tuned to move rho.", "",
          "## Primary statistic", "",
          "| ROI | rho(Delta theta var, Delta median RT) | p | bootstrap CI95 | reference | diff |",
          "|---|---|---|---|---|---|"]
    for r in REGIONS:
        m = out["regions"][r]
        s = m["spearman_vs_delta_rt_ms"]
        ref = "n/a" if m["reference_rho"] is None else f"{m['reference_rho']:+.2f}"
        dif = "n/a" if m["difference_from_reference"] is None else f"{m['difference_from_reference']:+.3f}"
        md.append(f"| {r} | {s['spearman_rho']:+.3f} | {s['p_value']:.4f} | "
                  f"[{s['bootstrap_ci95'][0]:+.3f}, {s['bootstrap_ci95'][1]:+.3f}] | {ref} | {dif} |")
    md += ["", "## Group-level SD-NS change", "",
           "| ROI | Delta theta variability (SD-NS) | p | Delta theta relative power | p |",
           "|---|---|---|---|---|"]
    for r in REGIONS:
        m = out["regions"][r]
        t = out["theta_relative_mean_change"][r]
        md.append(f"| {r} | {m['delta_theta_variability_mean']:+.4f} | {m['delta_theta_variability_p']:.4f} "
                  f"| {t['mean']:+.4f} | {t['p']:.4f} |")
    md += ["", "## Context: alpha and beta variability", "",
           "| band | F | CT | PO |", "|---|---|---|---|"]
    for band in ("alpha", "beta"):
        cells = " | ".join(f"{out['other_bands'][band][r]['spearman_rho']:+.3f} "
                           f"(p={out['other_bands'][band][r]['p_value']:.3f})" for r in REGIONS)
        md.append(f"| {band} | {cells} |")
    md += ["", "## Subject-count sensitivity (reported, NOT adopted)", "",
           "The working cohort is the unfiltered 29 raw-PVT-paired subjects with admissible",
           "eyes-open EEG. The published analysis has ~28. The only a-priori filter found in",
           "this workspace that yields exactly 28 is reported below; it is **not** applied.", "",
           "```json", C.json.dumps(out["n28_filter_sensitivity"], indent=2, ensure_ascii=False), "```", ""]
    (C.OUTPUTS / "paper_reference" / "reproduction_report.md").write_text(
        "\n".join(md), encoding="utf-8")
    print("\nwrote outputs/paper_reference/reproduction_report.md")


if __name__ == "__main__":
    main()
