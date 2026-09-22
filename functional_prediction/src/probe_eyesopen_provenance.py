"""Phase 0 gate check: can eyes-open provenance be established for every readable EEG file?

This is a READ-ONLY probe used to decide whether the Phase 1 gate (SCIENTIFIC_SPEC section 5)
passes or hard-stops. It reads the EEGLAB header fields of each readable .set in
data/ds004902/preprocessed/ and reports the original source filename recorded by the
third-party preprocessing step.

Writes project/vigilance_generalization_v1/outputs/manifests/eyesopen_provenance_probe.json
Usage:
  python project/vigilance_generalization_v1/src/probe_eyesopen_provenance.py
"""
from __future__ import annotations

import json
import re
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")
from pymatreader import read_mat  # noqa: E402

BASE = Path(r"<HOME>\Desktop\srtp")
PREPROC = BASE / "data/ds004902/preprocessed"
OUT = BASE / "project/vigilance_generalization_v1/outputs/manifests"

OPEN = re.compile(r"(?:^|[^a-z])(open|openeye|eyesopen|restopen)", re.IGNORECASE)
CLOSED = re.compile(r"(?:^|[^a-z])(closed|eyesclosed|restclosed)", re.IGNORECASE)


def header_fields(path: Path) -> dict:
    m = read_mat(str(path))
    e = m.get("EEG", m)
    comments = e.get("comments", "")
    if isinstance(comments, list):
        comments = " | ".join(str(x) for x in comments)
    return {
        "setname": str(e.get("setname", "")),
        "comments": str(comments),
        "filepath": str(e.get("filepath", "")),
        "nbchan": int(e.get("nbchan", 0)),
        "pnts": int(e.get("pnts", 0)),
        "trials": int(e.get("trials", 0)),
        "srate": float(e.get("srate", 0.0)),
        "ref": str(e.get("ref", "")),
        "xmin": float(e.get("xmin", 0.0)),
        "xmax": float(e.get("xmax", 0.0)),
    }


def main() -> None:
    files = sorted(PREPROC.glob("*.set"))
    records = []
    for p in files:
        f = header_fields(p)
        blob = " ".join([f["setname"], f["comments"], f["filepath"]])
        orig = ""
        mm = re.search(r"Original file:\s*([^|\]]+)", f["comments"])
        if mm:
            orig = mm.group(1).strip()
        records.append({
            "file": p.name,
            "subject": p.stem.split("_")[0],
            "session": p.stem.split("_")[1],
            **f,
            "original_source_name": orig,
            "source_blob": blob.strip(),
            "says_open": bool(OPEN.search(blob)),
            "says_closed": bool(CLOSED.search(blob)),
        })

    no_evidence = [r["file"] for r in records if not (r["says_open"] or r["says_closed"])]
    both = [r["file"] for r in records if r["says_open"] and r["says_closed"]]
    closed = [r["file"] for r in records if r["says_closed"] and not r["says_open"]]

    summary = {
        "n_files": len(records),
        "n_says_open": sum(r["says_open"] for r in records),
        "n_says_closed_only": len(closed),
        "n_both_tokens": len(both),
        "n_no_eye_state_evidence": len(no_evidence),
        "no_evidence_files": no_evidence,
        "both_token_files": both,
        "closed_only_files": closed,
        "distinct_srate": sorted({r["srate"] for r in records}),
        "distinct_nbchan": sorted({r["nbchan"] for r in records}),
        "distinct_trials": sorted({r["trials"] for r in records}),
        "distinct_ref": sorted({r["ref"] for r in records}),
        "setname_prefix_counts": Counter(
            r["setname"].replace("- 4-s epochs pruned with ICA", "").strip() or "<empty>" for r in records
        ).most_common(10),
        "n_with_original_file_field": sum(bool(r["original_source_name"]) for r in records),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "eyesopen_provenance_probe.json").write_text(
        json.dumps({"summary": summary, "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print("=== files WITHOUT any eye-state token (these would block the gate) ===")
    for r in records:
        if not (r["says_open"] or r["says_closed"]):
            print("  ", r["file"], "| setname=", r["setname"][:70], "| comments=", r["comments"][:70])
    print()
    print("=== any file that says CLOSED ===")
    for r in records:
        if r["says_closed"]:
            print("  ", r["file"], "|", r["source_blob"][:120])


if __name__ == "__main__":
    main()
