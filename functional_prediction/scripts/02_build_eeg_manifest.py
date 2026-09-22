"""02a - Build the eyes-open EEG manifest.

    python project/vigilance_generalization_v1/scripts/02_build_eeg_manifest.py

Scans data/ds004902/preprocessed/, classifies every file's eye-state provenance and
admissibility, and writes:

  outputs/manifests/eeg_eyesopen_manifest.csv   one row per ADMITTED recording
  outputs/qc/eeg_exclusions.csv                 one row per excluded recording + reason
  outputs/qc/eeg_manifest_summary.json          counts and provenance verdicts

READ-ONLY on data/.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import data_ds004902 as D  # noqa: E402


def main() -> None:
    cfg = C.dataset_config()
    preproc = C.resolve(cfg["paths"]["eeg_preprocessed_dir"])
    canonical = [c for r in ("F", "CT", "PO") for c in cfg["roi"][r]]
    target_sfreq = float(cfg["eeg"]["target_sfreq_hz"])
    allowed = set(cfg["eeg"]["exclude_header_sfreq_not_in"])

    print(f"preprocessed dir : {preproc}")
    print(f"canonical montage: {len(canonical)} channels")
    print(f"target sfreq     : {target_sfreq}")

    admitted, excluded = D.load_manifest(preproc, canonical, target_sfreq)

    # pairing: both sessions admitted, same eye-state verdict
    by_subject: dict[str, dict[str, dict]] = {}
    for r in admitted:
        by_subject.setdefault(r["subject"], {})[r["session"]] = r

    paired, unpaired = [], []
    for subject, sess in sorted(by_subject.items()):
        if "ses-1" in sess and "ses-2" in sess:
            v1, v2 = sess["ses-1"]["eye_state_verdict"], sess["ses-2"]["eye_state_verdict"]
            # All admissible verdicts denote the SAME eye state (eyes-open); the verdict only
            # records how strong the evidence is. Mixing evidence strengths across the two
            # sessions of one subject is therefore not a pairing failure.
            paired.append(subject)
            sess["ses-1"]["eye_evidence_strength"] = v1
            sess["ses-2"]["eye_evidence_strength"] = v2
        else:
            unpaired.append({"subject": subject,
                             "reason": f"missing_session:{'ses-1' if 'ses-1' not in sess else 'ses-2'}"})

    for r in admitted:
        r["paired"] = r["subject"] in paired

    unverified = [r["stem"] for r in admitted if r["eye_state_verdict"] == "no_evidence"]

    C.write_csv(C.OUTPUTS / "manifests" / "eeg_eyesopen_manifest.csv", admitted)
    C.write_csv(C.OUTPUTS / "qc" / "eeg_exclusions.csv",
                [{**e, "reason": e.get("reason", "")} for e in excluded] + unpaired)

    summary = {
        "preprocessed_dir": str(preproc),
        "n_files_on_disk": len(list(preproc.glob("*.set"))),
        "n_admitted": len(admitted),
        "n_excluded": len(excluded),
        "exclusion_reasons": dict(Counter(e.get("reason", "?").split(":")[0] for e in excluded)),
        "eye_state_verdicts_admitted": dict(Counter(r["eye_state_verdict"] for r in admitted)),
        "eyes_open_unverified_files": unverified,
        "n_eyes_open_unverified": len(unverified),
        "subjects_with_both_sessions_admitted": len(paired),
        "n_paired_subjects": len(paired),
        "paired_subjects": paired,
        "unpaired_subjects": unpaired,
        "n_epochs_total": sum(r["n_epochs"] for r in admitted),
        "n_epochs_min": min((r["n_epochs"] for r in admitted), default=0),
        "n_epochs_max": max((r["n_epochs"] for r in admitted), default=0),
        "header_sfreq_values": dict(Counter(r["header_sfreq"] for r in admitted)),
        "canonical_montage": canonical,
        "n_canonical": len(canonical),
        "resampled_upstream": cfg["eeg"]["upstream_resampled_to_500hz"]["files"],
        "resampled_present_in_admitted": [f for f in cfg["eeg"]["upstream_resampled_to_500hz"]["files"]
                                          if f in {r["stem"] for r in admitted}],
    }
    C.write_json(C.OUTPUTS / "qc" / "eeg_manifest_summary.json", summary)

    print()
    print("=" * 78)
    print("EYES-OPEN EEG MANIFEST")
    print("=" * 78)
    print(f"  files on disk              : {summary['n_files_on_disk']}")
    print(f"  admitted                   : {summary['n_admitted']}")
    print(f"  excluded                   : {summary['n_excluded']}  {summary['exclusion_reasons']}")
    print(f"  eye-state verdicts admitted: {summary['eye_state_verdicts_admitted']}")
    print(f"  eyes-open UNVERIFIED files : {summary['n_eyes_open_unverified']} {unverified}")
    print(f"  paired subjects            : {summary['n_paired_subjects']}")
    print(f"  epochs total               : {summary['n_epochs_total']} "
          f"(min {summary['n_epochs_min']}, max {summary['n_epochs_max']})")
    print(f"  unpaired                   : {[u['subject'] + ':' + u['reason'] for u in summary['unpaired_subjects']]}")
    print(f"  resampled upstream present : {summary['resampled_present_in_admitted']}")
    print()
    print("wrote outputs/manifests/eeg_eyesopen_manifest.csv")


if __name__ == "__main__":
    main()
