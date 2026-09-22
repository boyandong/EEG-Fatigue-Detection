"""01 - Rebuild PVT targets from the raw trial files and reconcile against participants.tsv.

READ-ONLY on data/. Writes only into outputs/pvt/ and outputs/manifests/.

    python project/vigilance_generalization_v1/scripts/01_build_pvt_targets.py

Produces
  outputs/manifests/pvt_manifest.csv
  outputs/pvt/pvt_reconciliation.csv
  outputs/pvt/pvt_targets_raw.csv
  outputs/pvt/pvt_targets_official.csv
  outputs/pvt/pvt_subject_sets.json
  outputs/pvt/pvt_trial_audit.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import pvt_targets as P  # noqa: E402


def _explore_28(raw: dict, official: dict, sets: dict) -> dict:
    """Try to find a DATA-LEVEL reason the published analysis has ~28 subjects, not 29.

    Each candidate filter below is declared before looking at any feature-target relation.
    We report which filters produce n=28 and exactly whom they remove. We do NOT adopt any of
    them; the working set stays at the unfiltered raw-PVT intersect EEG.
    """
    import numpy as np

    base = list(sets.get("raw_trial_paired_intersect_eeg", []))
    out: dict = {"base_n": len(base), "base_subjects": base, "candidates": []}

    def emit(name: str, keep: list[str], rationale: str) -> None:
        removed = sorted(set(base) - set(keep))
        out["candidates"].append({
            "filter": name, "n": len(keep), "removes": removed, "rationale": rationale,
            "yields_28": len(keep) == 28,
        })

    # A. any session with < K valid trials
    for k in (40, 45, 48, 50):
        keep = [s for s in base
                if all((raw.get(s, {}).get(ses, {}) or {}).get("n_valid", 0) >= k
                       for ses in ("ses-1", "ses-2"))]
        emit(f"A_min_valid_trials_{k}_per_session", keep,
             f"require >= {k} valid trials in BOTH sessions")

    # B. median RT inside a stricter window
    for lo, hi in ((200, 1000), (250, 600), (100, 1000)):
        keep = [s for s in base if all(
            lo <= ((raw.get(s, {}).get(ses, {}) or {}).get("median_rt_ms") or np.nan) <= hi
            for ses in ("ses-1", "ses-2"))]
        emit(f"B_median_rt_within_{lo}_{hi}", keep,
             f"require median RT in [{lo}, {hi}] ms in both sessions")

    # C. exclude the two late-recruited subjects with a much longer protocol
    emit("C_exclude_sub70_sub71", [s for s in base if s not in {"sub-70", "sub-71"}],
         "sub-70/sub-71 have ~90 trials per session vs ~47 for everyone else")

    # D. drop non-positive Y (negative responders) - reported only, NOT a defensible filter
    keep = []
    for s in base:
        ns = (raw.get(s, {}).get("ses-1", {}) or {}).get("median_rt_ms")
        sd = (raw.get(s, {}).get("ses-2", {}) or {}).get("median_rt_ms")
        if ns and sd and sd > ns:
            keep.append(s)
    emit("D_positive_responders_only_DO_NOT_USE", keep,
         "NOT DEFENSIBLE: selects on the sign of the outcome; listed only to show it exists")

    # E. require both official AND raw values present
    keep = [s for s in base
            if all(P._num(official.get(s, {}).get(k)) is not None for k in ("PVT_item2_NS", "PVT_item2_SD"))]
    emit("E_official_and_raw_both_present", keep, "require official summary AND raw trials in both sessions")

    out["n_filters_yielding_28"] = sum(1 for c in out["candidates"] if c["yields_28"])
    out["filters_yielding_28"] = [c["filter"] for c in out["candidates"] if c["yields_28"]]
    out["conclusion"] = (
        "This workspace cannot reproduce the published ~28-subject selection from released data "
        "alone. The defensible, data-level count is 29 raw-PVT-paired subjects that also have "
        "admissible eyes-open 500 Hz EEG. The single-subject gap is reported, not closed by "
        "deleting a participant."
    )
    return out


def main() -> None:
    cfg = C.dataset_config()
    paths = cfg["paths"]
    bids_root = C.resolve(paths["bids_root"])
    participants = C.resolve(paths["participants_tsv"])
    min_rt = float(cfg["pvt"]["min_rt_ms"])
    max_rt = float(cfg["pvt"]["max_rt_ms"])

    print(f"bids_root   = {bids_root}")
    print(f"participants= {participants}")
    print(f"RT window   = [{min_rt}, {max_rt}] ms")

    # ---------------------------------------------------------------- trial files
    found = P.discover_trial_files(bids_root)
    print(f"raw PVT trial files found: {len(found)}")

    trial_audit, manifest_rows = [], []
    raw: dict[str, dict[str, dict]] = {}
    parse_errors: list[dict] = []
    for subject, session, path in found:
        try:
            ts, audit = P.parse_trial_file(path, subject, session, min_rt, max_rt)
        except Exception as exc:  # noqa: BLE001
            parse_errors.append({"subject": subject, "session": session, "file": path.name,
                                 "error": f"{type(exc).__name__}: {exc}"})
            continue
        st = P.session_targets(ts)
        audit.update({"subject": subject, "session": session, **{k: v for k, v in st.items()}})
        trial_audit.append(audit)
        raw.setdefault(subject, {})[session] = {"n_rows": ts.n_rows, **st}
        manifest_rows.append({
            "subject": subject, "session": session, "file": path.name,
            "relative_path": str(path.relative_to(bids_root)).replace("\\", "/"),
            "sha256": C.sha256_file(path), "n_rows": ts.n_rows,
            "trial_column": ts.trial_column, "response_column": ts.response_column,
            "header_variant": ts.header_variant,
        })

    official = P.load_official(participants)

    # ---------------------------------------------------------------- reconciliation
    subjects = sorted(official)
    recon = P.reconcile(subjects, raw, official)
    sets = P.subject_sets(recon)

    # exclude EEG-invalid subjects from the *sets*, but keep every row in the table
    eeg_manifest_path = C.OUTPUTS / "manifests" / "eeg_eyesopen_manifest.csv"
    eeg_valid: list[str] = []
    if eeg_manifest_path.exists():
        eeg_valid = sorted({r["subject"] for r in C.read_csv(eeg_manifest_path)})
        sets["eeg_valid_subjects"] = eeg_valid
        sets["n_eeg_valid"] = len(eeg_valid)
        for key in ("official_paired", "raw_trial_paired"):
            inter = sorted(set(sets[key]) & set(eeg_valid))
            sets[f"{key}_intersect_eeg"] = inter
            sets[f"n_{key}_intersect_eeg"] = len(inter)

    # ------------------------------------------------------------------ raw targets
    raw_rows = []
    for subject, sessions in sorted(raw.items()):
        ns = sessions.get("ses-1", {}) or {}
        sd = sessions.get("ses-2", {}) or {}
        pair = P.paired_targets(ns, sd)
        raw_rows.append({
            "subject": subject,
            "n_valid_trials_NS": ns.get("n_valid"), "n_valid_trials_SD": sd.get("n_valid"),
            "median_rt_ms_NS": ns.get("median_rt_ms"), "median_rt_ms_SD": sd.get("median_rt_ms"),
            "response_speed_per_s_NS": ns.get("response_speed_per_s"),
            "response_speed_per_s_SD": sd.get("response_speed_per_s"),
            "delta_median_rt_ms_paper_compatible": pair["delta_median_rt_ms"],
            "Y_log_medianRT_raw": pair["Y_log_medianRT_raw"],
            "Y_log_response_speed_raw": pair["Y_log_response_speed_raw"],
            "target_computed": pair["computed"], "target_reason": pair["reason"],
        })

    # diagnostics: why is a subject not raw-paired?
    why = {}
    for subject in subjects:
        sess = raw.get(subject, {})
        has_ns, has_sd = "ses-1" in sess, "ses-2" in sess
        ns_med = (sess.get("ses-1") or {}).get("median_rt_ms")
        sd_med = (sess.get("ses-2") or {}).get("median_rt_ms")
        if has_ns and has_sd and ns_med is not None and sd_med is not None:
            why[subject] = "raw_paired"
        elif not has_ns and not has_sd:
            why[subject] = "no_trial_file_in_either_session"
        elif not has_ns:
            why[subject] = "no_NS_trial_file"
        elif not has_sd:
            why[subject] = "no_SD_trial_file"
        elif ns_med is None:
            why[subject] = "NS_no_valid_trial_after_filter"
        else:
            why[subject] = "SD_no_valid_trial_after_filter"
    from collections import Counter
    print("  raw pairing status:", dict(Counter(why.values())))

    official_rows = []
    for subject in subjects:
        o = official[subject]
        official_rows.append({
            "subject": subject,
            "PVT_item1_lapses_NS": o.get("PVT_item1_NS"), "PVT_item1_lapses_SD": o.get("PVT_item1_SD"),
            "PVT_item2_median_rt_NS": o.get("PVT_item2_NS"), "PVT_item2_median_rt_SD": o.get("PVT_item2_SD"),
            "PVT_item3_sd_rt_NS": o.get("PVT_item3_NS"), "PVT_item3_sd_rt_SD": o.get("PVT_item3_SD"),
            "PVT_SamplingTime_NS": o.get("PVT_SamplingTime_NS"),
            "PVT_SamplingTime_SD": o.get("PVT_SamplingTime_SD"),
            "SessionOrder": o.get("SessionOrder"),
        })

    # ---------------------------------------------------------------------- write
    C.write_csv(C.OUTPUTS / "manifests" / "pvt_manifest.csv", manifest_rows)
    C.write_csv(C.OUTPUTS / "pvt" / "pvt_trial_audit.csv", trial_audit)
    C.write_csv(C.OUTPUTS / "pvt" / "pvt_reconciliation.csv", recon, [
        "subject", "official_median_rt_ns", "official_median_rt_sd",
        "raw_filtered_median_rt_ns", "raw_filtered_median_rt_sd",
        "official_delta", "raw_delta", "difference_ns", "difference_sd",
        "raw_trials_ns", "raw_trials_sd", "valid_trials_ns", "valid_trials_sd",
        "exclusion_reason",
    ])
    C.write_csv(C.OUTPUTS / "pvt" / "pvt_targets_raw.csv", raw_rows)
    C.write_csv(C.OUTPUTS / "pvt" / "pvt_targets_official.csv", official_rows)

    sets["parse_errors"] = parse_errors
    sets["published_reference_n"] = 28
    sets["note_published_n"] = (
        "The 2026 same-dataset paper reports roughly 28 PVT subjects. We do NOT delete anyone "
        "to match it; we report the exact set differences and the data-level reason."
    )
    sets["n_difference_vs_published"] = sets.get("n_raw_trial_paired_intersect_eeg", 0) - 28
    sets["published_n_alternative_filters"] = _explore_28(raw, official, sets)
    C.write_json(C.OUTPUTS / "pvt" / "pvt_subject_sets.json", sets)

    C.write_json(C.OUTPUTS / "qc" / "run_manifest_01_pvt.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml"],
        {"n_trial_files": len(found), "n_parse_errors": len(parse_errors),
         "rt_window_ms": [min_rt, max_rt]}))

    # ---------------------------------------------------------------------- report
    print()
    print("=" * 78)
    print("PVT TARGET RECONSTRUCTION")
    print("=" * 78)
    print(f"  trial files found           : {len(found)}")
    print(f"  parse errors                : {len(parse_errors)}")
    print(f"  header variants             : "
          f"{ {k: sum(1 for a in trial_audit if a['header_variant'] == k) for k in sorted({a['header_variant'] for a in trial_audit})} }")
    print(f"  official paired subjects    : {sets['n_official_paired']}")
    print(f"  raw-trial paired subjects   : {sets['n_raw_trial_paired']}")
    if "n_official_paired_intersect_eeg" in sets:
        print(f"  official paired ∩ EEG       : {sets['n_official_paired_intersect_eeg']}")
        print(f"  raw paired ∩ EEG            : {sets['n_raw_trial_paired_intersect_eeg']}")
    print(f"  published reference N       : 28")
    print(f"  in official not raw         : {sets['in_official_not_raw']}")
    print(f"  in raw not official         : {sets['in_raw_not_official']}")
    print()
    print("wrote outputs/pvt/* and outputs/manifests/pvt_manifest.csv")


if __name__ == "__main__":
    main()
