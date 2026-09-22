"""EEG-TTA Phase 1 — shared provenance plumbing.

This module deliberately reads the SHARED frozen source trunk through its LEGACY code path
(`shared/ds004902_source_trunk/legacy_apparatus/run_baselines.py`) so that SOURCE closure is
tested against the original implementation rather than a re-implementation.

Nothing here writes to the shared trunk, the archive, or the raw data tree.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

# Repo root after the 2026-09-20 branch decoupling: <repo>/tta_collapse/src/ -> <repo>.
# The branch reaches the shared frozen trunk and the archive ONLY through these relative
# references; it never holds a copy of any of them. See ../MIGRATION_MAP.md.
BASE = Path(__file__).resolve().parents[2]
LEGACY = BASE / "shared" / "ds004902_source_trunk" / "legacy_apparatus"
LEGACY_DATA = LEGACY / "outputs" / "source_only_500hz_v1"
FORMAL = (BASE / "archive" / "legacy_or_superseded" / "formal_results_v1" / "project")
FORMAL_RESULTS = FORMAL / "results" / "formal_autodl_v1"
ACTIVE_DATA = LEGACY_DATA  # byte-identical to the formal copy (see LEGACY_EEGNET_PROVENANCE.md)
METADATA = BASE / "data" / "ds004902" / "metadata_behavior"
PARTICIPANTS = METADATA / "participants.tsv"
DATASET_README = METADATA / "README"

AUDIT = BASE / "tta_collapse"

# Recorded in formal_results_v1/project/results/formal_autodl_v1/provenance.json
EXPECTED = {
    "runner_sha256": "6c7764b71996cad38fb045025349dd7ee51147e3331d4119709f13ed9a59fe49",
    "manifest_sha256": "5eba619fc0dd516f8caf72a86fd36a34ca07c589df9d269b2bcdbd53c1c3a744",
    "splits_sha256": "db02bab96f8147bffa4836967a29c0763bc9f8130fa994252ed269649070c184",
    "config_sha256": "854a8c598bff49c41f994f0112947cd29889220d484a4de35c0172e03d4899cc",
    "source_manifest_sha256": "37e0f99fef857f88b302942c569fbafa360313ce5dad0b293913f9d6b5ff3e44",
    "gpu": "NVIDIA GeForce RTX 4090",
}

# The reported project-record aggregates (prompt §2).  Aggregation rule verified as:
#   mean over the 3 seed-level subject-means  (summary_variability.csv)
REPORTED_EEGNET = {
    "accuracy": 0.5963,
    "balanced_accuracy": 0.5924,
    "f1": 0.5550,
    "roc_auc": 0.6109,
}

METRICS = ("accuracy", "balanced_accuracy", "f1", "roc_auc")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def load_manifest(root: Path = ACTIVE_DATA):
    """Legacy shared input list, in legacy file order (this order is *not* used as a stream)."""
    rows = read_csv(root / "segments.csv")
    assert len({r["segment_id"] for r in rows}) == len(rows)
    return rows


def load_splits(root: Path = ACTIVE_DATA):
    splits = json.loads((root / "splits.json").read_text(encoding="utf-8"))
    assert sha256(root / "segments.csv") == splits["manifest_sha256"]
    return splits


SESSION_ORDER_LEVELS = {"NS->SD": ("ses-1", "ses-2"), "SD->NS": ("ses-2", "ses-1")}


def load_session_order():
    """Authoritative per-participant visit order, from the ds004902 release metadata.

    `participants.tsv:SessionOrder` is the release's own record of which visit happened
    first.  `participants.json` documents it as:

        "SessionOrder": {"Description": "Participant session order label",
                         "Levels": {"NS->SD": "First normal sleep session, then sleep
                                    deprivation session",
                                    "SD->NS": "First sleep deprivation session, then
                                    normal sleep session"}}

    and the dataset README states that `ses-1`/`ses-2` are condition identifiers, *not*
    time order, with the real order counterbalanced and recorded in metadata.  The paper
    (Xiang et al., Sci Data 11:427, 2024) adds that the two visits were separated by a
    **minimum of 7 days and a maximum of one month** and were *"ideally aligned within the
    same time of day"*.

    The time-of-day columns therefore carry no visit-order information (they are
    deliberately matched across visits), and this function never reads them.
    """
    rows = read_csv(PARTICIPANTS)
    # participants.tsv is tab-separated despite the .tsv suffix being handled by read_csv's
    # default; re-read explicitly to be robust.
    with open(PARTICIPANTS, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    out = {}
    for r in rows:
        pid = (r.get("participant_id") or "").strip()
        val = (r.get("SessionOrder") or "").strip()
        if pid:
            out[pid] = val
    return out


def session_block_order_for(subject, session_order=None):
    """Map a subject to its authoritative ('first_session', 'second_session') visit pair."""
    order = session_order if session_order is not None else load_session_order()
    level = order.get(subject)
    if level not in SESSION_ORDER_LEVELS:
        raise RuntimeError(f"no authoritative SessionOrder for {subject!r}: {level!r}")
    return SESSION_ORDER_LEVELS[level]


CLOCK_COLUMNS = ("EEG_SamplingTime_Open_NS", "EEG_SamplingTime_Open_SD")


def load_clock_times():
    """Time-of-day columns, read ONLY to demonstrate they cannot order the visits.

    The paper states the two visits were *"ideally aligned within the same time of day for
    each subject"* (58/71 within 1.5 h), so these columns are matched across visits by
    design and carry no visit-order information.  Nothing in the pipeline orders a stream
    with them; NC14 asserts exactly that, and asserts the disagreement numerically.
    """
    with open(PARTICIPANTS, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    def mins(s):
        import re

        s = (s or "").strip()
        if not re.match(r"^\d{1,2}:\d{2}:\d{2}$", s):
            return None
        h, m, sec = (int(x) for x in s.split(":"))
        return h * 60 + m + sec / 60

    return {r["participant_id"].strip(): (mins(r.get(CLOCK_COLUMNS[0])),
                                          mins(r.get(CLOCK_COLUMNS[1])))
            for r in rows if (r.get("participant_id") or "").strip()}


def build_model_from_config(cfg):
    """Exactly the legacy construction: braindecode EEGNet, 61 chans, 2 out, 2000 samples."""
    from braindecode.models import EEGNet

    return EEGNet(n_chans=61, n_outputs=2, n_times=2000, sfreq=500, **cfg["eegnet"])
