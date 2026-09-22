"""Paired cohort definition and shared EEG extraction driver.

A "cohort" is the set of subjects with, for BOTH sessions:
  * an admissible eyes-open 500 Hz EEG recording, AND
  * a usable PVT target.

This module holds the cohort rule in one place so that the paper_reference and
mechanism_v1 pipelines cannot silently use different subjects.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import common as C
import data_ds004902 as D
import pvt_targets as P

BASELINE = "ses-1"       # NS
PERTURBATION = "ses-2"   # SD


@dataclass
class Cohort:
    subjects: list[str]
    eeg_files: dict[str, dict[str, Path]]      # subject -> session -> .set path
    pvt: dict[str, dict]                       # subject -> raw target row
    official: dict[str, dict]
    participants: dict[str, dict]
    sets: dict
    reasons: dict[str, str]                    # subject -> why excluded (if any)


def build_cohort(*, require_eye_evidence: str | None = None) -> Cohort:
    """Define the paired, eyes-open, PVT-available cohort.

    require_eye_evidence: if given, restrict to subjects where BOTH sessions are at least
    this strong. Used only for the sensitivity check; the working cohort admits all
    admissible verdicts.
    """
    cfg = C.dataset_config()
    manifest = C.read_csv(C.OUTPUTS / "manifests" / "eeg_eyesopen_manifest.csv")
    eeg_files: dict[str, dict[str, Path]] = {}
    for r in manifest:
        eeg_files.setdefault(r["subject"], {})[r["session"]] = C.resolve(cfg["paths"]["eeg_preprocessed_dir"]) / r["file"]

    raw_rows = {r["subject"]: r for r in C.read_csv(C.OUTPUTS / "pvt" / "pvt_targets_raw.csv")}
    official = P.load_official(C.resolve(cfg["paths"]["participants_tsv"]))
    participants = D.load_participants(C.resolve(cfg["paths"]["participants_tsv"]))
    sets = json.loads((C.OUTPUTS / "pvt" / "pvt_subject_sets.json").read_text(encoding="utf-8"))

    verdict = {r["stem"]: r["eye_state_verdict"] for r in manifest}
    strength = {"explicit_open": 3, "implicit_open": 2, "no_evidence": 1}

    subjects, reasons = [], {}
    for subject in sorted(official):
        sess = eeg_files.get(subject, {})
        if BASELINE not in sess or PERTURBATION not in sess:
            reasons[subject] = "missing_admissible_eyesopen_eeg_session"
            continue
        row = raw_rows.get(subject, {})
        if not row or str(row.get("target_computed", "")).lower() != "true":
            reasons[subject] = "no_raw_pvt_pair"
            continue
        if require_eye_evidence is not None:
            lo = min(strength[verdict[f"{subject}_{s}"]] for s in (BASELINE, PERTURBATION))
            if lo < strength[require_eye_evidence]:
                reasons[subject] = f"eye_evidence_below_{require_eye_evidence}"
                continue
        subjects.append(subject)

    return Cohort(subjects=subjects, eeg_files=eeg_files, pvt=raw_rows, official=official,
                  participants=participants, sets=sets, reasons=reasons)


def load_session(subject: str, session: str, cohort: Cohort, canonical: list[str],
                 target_sfreq: float) -> D.Recording:
    """Load one session in canonical channel order. No normalisation is applied."""
    path = cohort.eeg_files[subject][session]
    return D.make_recording(path, canonical, target_sfreq)


def load_paired(subject: str, cohort: Cohort, canonical: list[str], target_sfreq: float
                ) -> tuple[D.Recording, D.Recording]:
    return (load_session(subject, BASELINE, cohort, canonical, target_sfreq),
            load_session(subject, PERTURBATION, cohort, canonical, target_sfreq))


def cohort_summary(cohort: Cohort) -> dict:
    from collections import Counter
    return {
        "n_subjects": len(cohort.subjects),
        "subjects": cohort.subjects,
        "n_excluded": sum(1 for v in cohort.reasons.values() if v),
        "exclusion_reasons": dict(Counter(cohort.reasons.values())),
        "excluded_subjects": {k: v for k, v in sorted(cohort.reasons.items()) if v},
        "pvt_sets": {k: v for k, v in cohort.sets.items() if k.startswith("n_") or k.endswith("_paired")
                     or k.startswith("in_")},
    }
