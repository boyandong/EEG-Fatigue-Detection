"""Phase 0/1 provenance audit: full EEGLAB lineage for every readable EEG file.

Extracts, for each `data/ds004902/preprocessed/*.set`:
  * the pop_loadbv source path + filename (original raw recording)
  * the pop_epoch event code and window (which condition segment was epoched)
  * channel removal / interpolation history
  * reference, units, sampling rate, channel names, epoch count
  * an explicit eyes-open evidence verdict

This is READ-ONLY on the data tree.

Usage:
  python project/vigilance_generalization_v1/scripts/00_audit_source_data.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pymatreader import read_mat  # noqa: E402

BASE = Path(r"<HOME>\Desktop\srtp")
VIG = BASE / "project/vigilance_generalization_v1"
PREPROC = BASE / "data/ds004902/preprocessed"
BIDS = BASE / "data/ds004902/metadata_behavior"
OUT_MAN = VIG / "outputs/manifests"
OUT_QC = VIG / "outputs/qc"

RE_LOADBV = re.compile(r"pop_loadbv\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*\[([^\]]*)\]\s*,\s*\[([^\]]*)\]\s*\)")
RE_POPEPOCH = re.compile(r"pop_epoch\(\s*EEG,\s*\{\s*'([^']*)'\s*\}\s*,\s*\[([^\]]*)\]\s*(?:,\s*'newname'\s*,\s*'([^']*)')?")
RE_RMCHAN = re.compile(r"pop_select\(\s*EEG,\s*'rmchannel'\s*,\s*\{([^}]*)\}\s*\)")
RE_INTERP = re.compile(r"pop_interp\(([^)]*)\)", re.IGNORECASE)
RE_REF = re.compile(r"pop_reref\(EEG,\s*(\[\]|\d+)\)")
RE_RESAMPLE = re.compile(r"pop_resample\(([^)]*)\)", re.IGNORECASE)
RE_SETNAME = re.compile(r"EEG\.setname\s*=\s*'([^']*)'")

OPEN_RE = re.compile(r"(?:^|[^a-zA-Z])(open|openeye|eyesopen|restopen)", re.IGNORECASE)
CLOSED_RE = re.compile(r"(?:^|[^a-zA-Z])(closed|eyesclosed|restclosed)", re.IGNORECASE)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def flat(x) -> str:
    if isinstance(x, list):
        return " || ".join(str(i).strip() for i in x)
    return "" if x is None else str(x)


def parse_one(path: Path) -> dict:
    m = read_mat(str(path))
    e = m.get("EEG", m)
    hist = flat(e.get("history"))
    comments = flat(e.get("comments"))
    setname = str(e.get("setname", ""))
    filepath = str(e.get("filepath", ""))

    chanlocs = e.get("chanlocs")
    names = []
    try:
        if isinstance(chanlocs, dict) and "labels" in chanlocs:
            names = [str(x) for x in chanlocs["labels"]]
        elif isinstance(chanlocs, list):
            names = [str(c["labels"]) if isinstance(c, dict) else str(c) for c in chanlocs]
        elif hasattr(chanlocs, "dtype") and chanlocs.dtype.names and "labels" in chanlocs.dtype.names:
            names = [str(x) for x in np.ravel(chanlocs["labels"])]
    except Exception as exc:  # noqa: BLE001
        names = []
        print(f"    WARN channel-name extraction failed for {path.name}: {exc}")

    lb = RE_LOADBV.search(hist)
    pe = RE_POPEPOCH.search(hist)
    rm = RE_RMCHAN.search(hist)
    it = RE_INTERP.search(hist)
    rf = RE_REF.search(hist)
    rs = RE_RESAMPLE.search(hist)

    orig = ""
    mm = re.search(r"Original file:\s*([^\|\]\n]+)", comments)
    if mm:
        orig = mm.group(1).strip()

    blob = " ".join([setname, comments, filepath, hist[:4000]])
    says_open = bool(OPEN_RE.search(blob))
    says_closed = bool(CLOSED_RE.search(blob))
    src_name = lb.group(2) if lb else orig
    src_path = lb.group(1) if lb else ""

    trials = int(e.get("trials", 0))
    pnts = int(e.get("pnts", 0))
    srate = float(e.get("srate", 0.0))

    return {
        "file": path.name,
        "subject": path.stem.split("_")[0],
        "session": path.stem.split("_")[1],
        "set_sha256": sha256(path),
        "fdt_present": (path.with_suffix(".fdt")).exists(),
        "nbchan": int(e.get("nbchan", 0)),
        "n_epochs": trials,
        "pnts": pnts,
        "epoch_seconds": round(pnts / srate, 6) if srate else None,
        "srate_header_hz": srate,
        "xmin": float(e.get("xmin", 0.0)),
        "xmax": float(e.get("xmax", 0.0)),
        "reference_field": str(e.get("ref", "")),
        "channel_names": names,
        "n_channel_names": len(names),
        "setname": setname,
        "source_filepath_field": filepath,
        "original_source_name": orig,
        "loadbv_source_dir": src_path,
        "loadbv_source_file": lb.group(2) if lb else "",
        "loadbv_sample_range": lb.group(3) if lb else "",
        "loadbv_channel_idx_n": (len([x for x in lb.group(4).split()]) if lb else 0),
        "epoch_event_code": pe.group(1) if pe else "",
        "epoch_window": pe.group(2) if pe else "",
        "epoch_newname": (pe.group(3) or "") if pe else "",
        "removed_channels": rm.group(1).strip() if rm else "",
        "interp_history": it.group(1).strip()[:200] if it else "",
        "reref_history": rf.group(1) if rf else "",
        "resample_history": rs.group(1)[:120] if rs else "",
        "history_chars": len(hist),
        "says_open": says_open,
        "says_closed": says_closed,
        "eye_state_evidence": ("explicit_open" if says_open and not says_closed
                               else "explicit_closed" if says_closed and not says_open
                               else "both" if says_open and says_closed
                               else "none"),
    }


def main() -> None:
    OUT_MAN.mkdir(parents=True, exist_ok=True)
    OUT_QC.mkdir(parents=True, exist_ok=True)
    files = sorted(PREPROC.glob("*.set"))
    recs = []
    for i, p in enumerate(files, 1):
        try:
            recs.append(parse_one(p))
        except Exception as exc:  # noqa: BLE001
            recs.append({"file": p.name, "subject": p.stem.split("_")[0], "session": p.stem.split("_")[1],
                         "parse_error": f"{type(exc).__name__}: {exc}"})
        if i % 25 == 0:
            print(f"  parsed {i}/{len(files)}", flush=True)

    cols = list(dict.fromkeys(k for r in recs for k in r))
    cols.remove("channel_names")
    cols.insert(cols.index("n_channel_names") + 1, "channel_names")
    csv_path = OUT_MAN / "source_eeg_manifest.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            w.writerow({k: (json.dumps(r.get(k), ensure_ascii=False)
                            if isinstance(r.get(k), (list, dict)) else r.get(k, ""))
                        for k in cols})

    summary = {
        "n_files": len(recs),
        "n_parse_error": sum(1 for r in recs if "parse_error" in r),
        "eye_state_evidence": dict(Counter(r.get("eye_state_evidence", "parse_error") for r in recs)),
        "distinct_srate": dict(Counter(r.get("srate_header_hz") for r in recs)),
        "distinct_nbchan": dict(Counter(r.get("nbchan") for r in recs)),
        "epoch_event_codes": dict(Counter(r.get("epoch_event_code", "") for r in recs)),
        "epoch_windows": dict(Counter(r.get("epoch_window", "") for r in recs).most_common(15)),
        "removed_channels": dict(Counter(r.get("removed_channels", "") for r in recs).most_common(20)),
        "reref_history": dict(Counter(r.get("reref_history", "") for r in recs)),
        "resample_history": dict(Counter(r.get("resample_history", "") for r in recs)),
        "reference_field": dict(Counter(r.get("reference_field", "") for r in recs)),
        "loadbv_source_dirs": dict(Counter(r.get("loadbv_source_dir", "") for r in recs).most_common(10)),
        "n_with_loadbv": sum(1 for r in recs if r.get("loadbv_source_file")),
        "n_channel_name_variants": len({tuple(r.get("channel_names") or []) for r in recs}),
        "n_files_with_61_channels": sum(1 for r in recs if len(r.get("channel_names") or []) == 61),
    }
    (OUT_QC / "source_audit_summary.json").write_text(
        json.dumps({"summary": summary, "records": recs}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
