"""04a - Feature-side QC. Independent of the behavioural target.

    python project/vigilance_generalization_v1/scripts/04_qc_features.py

Per SCIENTIFIC_SPEC.md section 12.3 this stage may look ONLY at feature-side properties.
It must NOT delete features, delete subjects, or change parameters on the basis of
corr(feature, Y). Nothing here reads the PVT target except to confirm the column exists.

Outputs
  outputs/qc/feature_qc.csv          (regenerated, feature-side columns only)
  outputs/qc/qc_report.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402

FEATURES = ["delta_M_F", "delta_M_CT", "delta_M_PO",
            "delta_logJ_F", "delta_logJ_CT", "delta_logJ_PO"]
SESSION_FEATURES = ["M_F", "M_CT", "M_PO", "J_F", "J_CT", "J_PO"]


def main() -> None:
    ds = C.dataset_config()
    mech = C.mechanism_config()

    sess = C.read_csv(C.OUTPUTS / "mechanism_v1" / "session_features.csv")
    pair = C.read_csv(C.OUTPUTS / "mechanism_v1" / "paired_features.csv")
    flags: list[dict] = []

    def flag(check: str, status: str, detail) -> None:
        flags.append({"check": check, "status": status, "detail": detail})

    # ---------------------------------------------------------------- 1. finiteness
    nonfinite = []
    for r in sess:
        for f in SESSION_FEATURES:
            v = r.get(f)
            if v in (None, "") or not np.isfinite(float(v)):
                nonfinite.append({"table": "session", "subject": r["subject"],
                                  "session": r["session"], "field": f, "value": v})
    for r in pair:
        for f in FEATURES:
            v = r.get(f)
            if v in (None, "") or not np.isfinite(float(v)):
                nonfinite.append({"table": "paired", "subject": r["subject"], "field": f, "value": v})
    flag("nonfinite_or_missing_features", "PASS" if not nonfinite else "FAIL", nonfinite)

    # ---------------------------------------------------------------- 2. zero power / eps
    eps_hits_total = 0
    min_band = {"theta": np.inf, "alpha": np.inf, "beta": np.inf}
    max_band = {"theta": 0.0, "alpha": 0.0, "beta": 0.0}
    n_band_min_observed = 0
    for r in sess:
        for b in ("theta", "alpha", "beta"):
            eps_hits_total += int(float(r.get(f"eps_hits_{b}", 0) or 0))
            mb = r.get(f"band_power_min_{b}")
            if mb not in (None, ""):
                n_band_min_observed += 1
                min_band[b] = min(min_band[b], float(mb))
            xb = r.get(f"band_power_max_{b}")
            if xb not in (None, ""):
                max_band[b] = max(max_band[b], float(xb))
    eps_frac_max = max((float(r.get("eps_hits_fraction", 0) or 0) for r in sess), default=0.0)
    ident_dev = max((abs(float(r.get("composition_identity_max_dev", 0) or 0)) for r in sess), default=0.0)
    n_expected_band_min = 3 * len(sess)
    flag("band_power_extremes_available",
         "PASS" if n_band_min_observed == n_expected_band_min else "FAIL",
         f"{n_band_min_observed}/{n_expected_band_min} values present")
    flag("epsilon_floor_activations_total", "PASS" if eps_hits_total == 0 else "FAIL", eps_hits_total)
    flag("epsilon_floor_max_fraction", "PASS" if eps_frac_max == 0.0 else "FAIL", eps_frac_max)
    flag("min_band_power_uv2", "PASS" if all(v > 1e-6 for v in min_band.values()) else "FAIL",
         {k: float(v) for k, v in min_band.items()})
    flag("max_band_power_uv2", "PASS" if all(np.isfinite(v) for v in max_band.values()) else "FAIL",
         {k: float(v) for k, v in max_band.items()})
    flag("composition_identity_max_deviation", "PASS" if ident_dev < 1e-12 else "FAIL", ident_dev)

    # ---------------------------------------------------------------- 3. epochs / duration
    n_epochs = np.array([int(r["n_epochs"]) for r in sess], dtype=float)
    durations = np.array([float(r["duration_seconds"]) for r in sess], dtype=float)
    expected_dur = n_epochs * float(ds["eeg"]["epoch_seconds"])
    flag("epochs_per_session", "PASS" if n_epochs.min() >= 2 else "FAIL",
         {"min": int(n_epochs.min()), "max": int(n_epochs.max()), "mean": float(n_epochs.mean())})
    flag("duration_matches_epochs_x_4s", "PASS" if np.allclose(durations, expected_dur, atol=1e-9) else "FAIL",
         {"max_abs_diff": float(np.max(np.abs(durations - expected_dur)))})
    flag("sessions_below_2_epochs", "PASS" if int((n_epochs < 2).sum()) == 0 else "FAIL",
         int((n_epochs < 2).sum()))

    # ---------------------------------------------------------------- 4. ROI channel counts
    ok_channels = all(int(r["n_channels_F"]) == 16 and int(r["n_channels_CT"]) == 28
                      and int(r["n_channels_PO"]) == 17 for r in sess)
    missing_channel_rows = [r["subject"] for r in sess
                            if int(r["n_channels_F"]) + int(r["n_channels_CT"]) + int(r["n_channels_PO"]) != 61]
    flag("roi_channel_counts_16_28_17", "PASS" if ok_channels else "FAIL",
         {"n_rows_wrong": len(missing_channel_rows), "subjects": missing_channel_rows[:10]})

    # ---------------------------------------------------------------- 5. pair completeness
    per_subject: dict[str, set] = {}
    for r in sess:
        per_subject.setdefault(r["subject"], set()).add(r["condition"])
    incomplete = {s: sorted(v) for s, v in per_subject.items() if v != {"NS", "SD"}}
    flag("ns_sd_pair_complete", "PASS" if not incomplete else "FAIL",
         {"n_subjects": len(per_subject), "incomplete": incomplete})

    # ---------------------------------------------------------------- 6. distribution / extremes
    dist = {}
    for f in FEATURES:
        v = np.array([float(r[f]) for r in pair], dtype=float)
        q1, q3 = np.percentile(v, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
        outliers = [pair[i]["subject"] for i in np.where((v < lo) | (v > hi))[0]]
        dist[f] = {"n": int(v.size), "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
                   "min": float(v.min()), "max": float(v.max()),
                   "median": float(np.median(v)), "iqr": float(iqr),
                   "n_far_outliers_3iqr": len(outliers), "far_outliers": outliers}
    flag("feature_distributions", "PASS", dist)

    # ---------------------------------------------------------------- 7. J floor usage
    eps_used = {f"eps_J_used_{r}": sum(1 for x in pair if str(x.get(f"eps_J_used_{r}", "")).lower() == "true")
                for r in ("F", "CT", "PO")}
    all_j_positive = all(float(x[f"J_{c}_{r}"]) > 0 for x in pair
                         for c in ("NS", "SD") for r in ("F", "CT", "PO"))
    flag("delta_logJ_epsilon_floor_used", "PASS" if sum(eps_used.values()) == 0 else "WARN", eps_used)
    flag("all_J_strictly_positive", "PASS" if all_j_positive else "WARN",
         "=> delta_logJ needs no epsilon floor at all")

    # ---------------------------------------------------------------- 8. session-order balance
    order_counts: dict[str, int] = {}
    for r in pair:
        order_counts[r.get("session_order", "")] = order_counts.get(r.get("session_order", ""), 0) + 1
    flag("session_order_balance", "PASS", order_counts)

    # ---------------------------------------------------------------- 9. target columns present
    targets = [f for f in ("Y_log_medianRT_raw", "Y_log_response_speed_raw",
                           "delta_median_rt_ms_paper_compatible") if f in (pair[0] if pair else {})]
    n_target_missing = sum(1 for r in pair if r.get("Y_log_medianRT_raw") in (None, ""))
    flag("target_columns_present", "PASS" if len(targets) == 3 else "FAIL", targets)
    flag("primary_target_complete", "PASS" if n_target_missing == 0 else "FAIL", n_target_missing)

    qc_csv = [{"check": f["check"], "status": f["status"],
               "detail": C.json.dumps(f["detail"], ensure_ascii=False)[:2000]} for f in flags]
    C.write_csv(C.OUTPUTS / "qc" / "feature_qc.csv", qc_csv)

    n_fail = sum(1 for f in flags if f["status"] == "FAIL")
    n_warn = sum(1 for f in flags if f["status"] == "WARN")
    report = {
        "n_checks": len(flags), "n_fail": n_fail, "n_warn": n_warn,
        "scope": "feature-side only; no feature/subject removal based on the behavioural target",
        "checks": flags,
    }
    C.write_json(C.OUTPUTS / "qc" / "qc_report.json", report)

    print("=" * 78)
    print("FEATURE-SIDE QC")
    print("=" * 78)
    for f in flags:
        mark = {"PASS": "ok  ", "WARN": "warn", "FAIL": "FAIL"}[f["status"]]
        d = f["detail"]
        if isinstance(d, dict) and len(str(d)) > 110:
            d = str(d)[:110] + "..."
        print(f"  [{mark}] {f['check']:<38} {d}")
    print()
    print(f"  {len(flags)} checks, {n_fail} FAIL, {n_warn} WARN")
    if n_fail:
        raise SystemExit(f"{n_fail} QC checks FAILED")
    print("wrote outputs/qc/feature_qc.csv")


if __name__ == "__main__":
    main()
