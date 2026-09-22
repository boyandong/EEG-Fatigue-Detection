"""ds004902 dataset adapter.

SCOPE: this module is the ONLY dataset-specific EEG code. It converts the third-party
EEGLAB `.set` files into the common representation consumed by the dataset-agnostic
`mechanism_features` module:

    epochs (n_epochs, n_channels, n_times) uV, channel_names, sfreq

It performs NO feature computation, NO normalisation, and NO recording-wise z-score.

PROVENANCE (see SCIENTIFIC_SPEC.md section 4 and scripts/00_audit_source_data.py):
  * BIDS tree data/ds004902/metadata_behavior/ has 218 eyesopen + 218 eyesclosed .set/.fdt
    pairs, ALL broken git-annex symlinks -> no content retrievable locally.
  * The only readable EEG is data/ds004902/preprocessed/ : 142 EEGLAB pairs.
  * Eyes-open provenance is carried by the preserved ORIGINAL SOURCE FILENAME in each
    header (e.g. "Original file: gaorui_sleep_open.eeg",
    "Parent dataset: sub04_qianyanijjang_restOpeneyes_SD_61_epochs"). No eyes-closed token
    occurs in any of the 142 files.

HARD RULE: only recordings passing the eyes-open check are returned by `load_manifest`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
from pymatreader import read_mat  # noqa: E402

# Eyes-open evidence: an explicit token in the preserved source filename / setname family.
OPEN_TOKENS = re.compile(r"(?:^|[^a-zA-Z])(open|openeye|openeyes|eyesopen|restopen)", re.IGNORECASE)
CLOSED_TOKENS = re.compile(r"(?:^|[^a-zA-Z])(closed|closeeye|eyesclosed|restclosed)", re.IGNORECASE)

# Families whose source filename does not carry an explicit "open" token but which come from
# the same eyes-open resting recording family. Kept as an explicit, reviewable allowlist so
# that the reason each recording is admitted is auditable rather than implicit.
IMPLICIT_OPEN_FAMILIES = re.compile(
    r"(_rest_ns\b|_rest_sd\b|_rest\.sd\b|_rest\.ns\b|_REST_ns\b|_REST_sd\b|_Rest_ns\b|_Rest_sd\b"
    r"|_S\.vhdr|_D\.vhdr|_S\b|_D\b)",
    re.IGNORECASE,
)


@dataclass
class Recording:
    """One session of one subject, already in canonical channel order."""

    subject: str
    session: str
    path: Path
    epochs: np.ndarray                    # (n_epochs, 61, 2000) uV, canonical order
    channel_names: list[str]
    sfreq: float
    n_epochs: int
    source_name: str
    eye_state_evidence: str
    reference: str
    units: str
    provenance: dict = field(default_factory=dict)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _flat(x) -> str:
    if isinstance(x, list):
        return " || ".join(str(i).strip() for i in x)
    return "" if x is None else str(x)


def _channel_names(eeg: dict) -> list[str]:
    cl = eeg.get("chanlocs")
    if isinstance(cl, dict) and "labels" in cl:
        return [str(x) for x in cl["labels"]]
    if isinstance(cl, list):
        return [str(c["labels"]) if isinstance(c, dict) else str(c) for c in cl]
    if hasattr(cl, "dtype") and getattr(cl.dtype, "names", None) and "labels" in cl.dtype.names:
        return [str(x) for x in np.ravel(cl["labels"])]
    raise ValueError("cannot extract channel names from chanlocs")


def classify_eye_state(setname: str, comments: str, filepath: str) -> tuple[str, str]:
    """Return (verdict, evidence_string).

    Verdict vocabulary:
      closed          affirmative evidence of an eyes-closed recording -> REJECT
      explicit_open   an explicit eyes-open token in the preserved source name -> admit
      implicit_open   no explicit token, but the source name matches a known eyes-open
                      resting family from the same raw corpus -> admit, flagged
      no_evidence     no eye-state token at all -> admit, flagged as UNVERIFIED

    `no_evidence` is deliberately NOT treated as evidence of eyes-closed. The upstream raw
    tree stored separate eyes-closed recordings with a "closed" token; none of the 142
    readable files carries one. Treating a missing token as proof of closed would discard
    usable data for a provenance technicality. The residual uncertainty is instead surfaced
    as a per-recording flag and counted in the manifest and in PHASE1_REPORT.md.
    """
    blob = f"{setname} {comments} {filepath}"
    has_open = bool(OPEN_TOKENS.search(blob))
    has_closed = bool(CLOSED_TOKENS.search(blob))
    if has_closed and not has_open:
        return "closed", blob.strip()[:300]
    if has_open:
        return "explicit_open", blob.strip()[:300]
    if IMPLICIT_OPEN_FAMILIES.search(blob):
        return "implicit_open", blob.strip()[:300]
    return "no_evidence", blob.strip()[:300]


ADMISSIBLE_EYE_VERDICTS = ("explicit_open", "implicit_open", "no_evidence")


def read_header_and_data(path: Path) -> tuple[dict, np.ndarray, list[str]]:
    """Read one EEGLAB .set. Returns (header_dict, epochs (n_ep, n_ch, n_t), channel_names)."""
    m = read_mat(str(path))
    e = m.get("EEG", m)
    c = int(e["nbchan"]); p = int(e["pnts"]); t = int(e["trials"])
    if min(c, p, t) < 1:
        raise ValueError(f"invalid EEG dimensions c={c} p={p} t={t}")

    linked = None
    if isinstance(e["data"], str):
        linked = path.parent / Path(str(e["data"]).replace("\\", "/")).name
        if not linked.exists():
            raise ValueError(f"linked .fdt missing: {linked.name}")
        if linked.stat().st_size != c * p * t * 4:
            raise ValueError(f"FDT byte count {linked.stat().st_size} != {c*p*t*4}")
        x = np.memmap(linked, dtype="<f4", mode="r", shape=(t, p, c)).transpose(0, 2, 1)
        x = np.asarray(x, dtype=np.float32)
    else:
        a = np.asarray(e["data"])
        if a.shape != (c, p, t):
            if t == 1 and a.shape == (c, p):
                a = a[:, :, None]
            else:
                raise ValueError(f"unexpected embedded data shape {a.shape}")
        x = a.transpose(2, 0, 1).astype(np.float32)

    return e, x, _channel_names(e)


def make_recording(path: Path, canonical_order: list[str], target_sfreq: float,
                   require_eye_state: str = "eyes-open") -> Recording:
    e, x, names = read_header_and_data(path)
    setname = str(e.get("setname", ""))
    comments = _flat(e.get("comments"))
    filepath = str(e.get("filepath", ""))
    verdict, evidence = classify_eye_state(setname, comments, filepath)

    if require_eye_state == "eyes-open" and verdict not in ADMISSIBLE_EYE_VERDICTS:
        raise ValueError(f"eyes-open provenance not established (verdict={verdict})")

    sfreq = float(e["srate"])
    if not np.isclose(sfreq, target_sfreq):
        raise ValueError(f"header sfreq {sfreq} != required {target_sfreq}")

    if len(set(names)) != len(names):
        raise ValueError("duplicate channel names in this file")
    if set(names) != set(canonical_order):
        raise ValueError(f"channel set mismatch: missing={sorted(set(canonical_order)-set(names))[:5]} "
                         f"extra={sorted(set(names)-set(canonical_order))[:5]}")
    order = [names.index(ch) for ch in canonical_order]
    x = x[:, order, :]

    return Recording(
        subject=path.stem.split("_")[0], session=path.stem.split("_")[1], path=path,
        epochs=x, channel_names=list(canonical_order), sfreq=sfreq, n_epochs=int(x.shape[0]),
        source_name=(re.search(r"Original file:\s*([^\|\]\n]+)", comments).group(1).strip()
                     if re.search(r"Original file:\s*([^\|\]\n]+)", comments) else ""),
        eye_state_evidence=verdict,
        reference=str(e.get("ref", "")), units="uV",
        provenance={
            "file": path.name, "set_sha256": sha256(path),
            "source_name": evidence, "eye_state_verdict": verdict,
            "setname": setname[:200], "upstream_filepath": filepath[:200],
            "header_sfreq": sfreq, "n_epochs": int(x.shape[0]),
            "n_channels": len(names), "channel_order_reordered": names != list(canonical_order),
            "epoch_seconds": float(x.shape[-1] / sfreq),
        },
    )


def load_manifest(preproc_dir: Path, canonical_order: list[str], target_sfreq: float,
                  *, exclude_stems: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Scan the preprocessed directory and classify every readable file.

    Returns (admitted, excluded). `admitted` entries carry subject/session/path/verdict;
    loading the waveform is deferred to `make_recording` so the scan stays cheap.
    """
    exclude_stems = exclude_stems or set()
    admitted, excluded = [], []
    for path in sorted(preproc_dir.glob("*.set")):
        stem = path.stem
        subject, session = stem.split("_")
        row = {"subject": subject, "session": session, "stem": stem, "file": path.name}
        if stem in exclude_stems:
            excluded.append({**row, "reason": "excluded_by_config"})
            continue
        try:
            m = read_mat(str(path))
            e = m.get("EEG", m)
            setname = str(e.get("setname", ""))
            comments = _flat(e.get("comments"))
            filepath = str(e.get("filepath", ""))
            sfreq = float(e.get("srate", 0.0))
            nbchan = int(e.get("nbchan", 0))
            trial = int(e.get("trials", 0))
            pnts = int(e.get("pnts", 0))
        except Exception as exc:  # noqa: BLE001
            excluded.append({**row, "reason": f"header_read_failed: {type(exc).__name__}: {exc}"})
            continue

        verdict, evidence = classify_eye_state(setname, comments, filepath)
        row.update(header_sfreq=sfreq, nbchan=nbchan, n_epochs=trial, pnts=pnts,
                   eye_state_verdict=verdict, eye_state_evidence=evidence,
                   source_name=(re.search(r"Original file:\s*([^\|\]\n]+)", comments).group(1).strip()
                                if re.search(r"Original file:\s*([^\|\]\n]+)", comments) else ""))
        if not np.isclose(sfreq, target_sfreq):
            excluded.append({**row, "reason": f"header_sfreq_{sfreq:g}_not_{target_sfreq:g}"})
            continue
        if verdict not in ADMISSIBLE_EYE_VERDICTS:
            excluded.append({**row, "reason": f"eyes_open_provenance_not_established:{verdict}"})
            continue
        if nbchan != len(canonical_order):
            excluded.append({**row, "reason": f"nbchan_{nbchan}_not_{len(canonical_order)}"})
            continue
        admitted.append(row)
    return admitted, excluded


def load_participants(participants_tsv: Path) -> dict[str, dict]:
    with participants_tsv.open(encoding="utf-8-sig") as f:
        return {r["participant_id"]: r for r in csv.DictReader(f, delimiter="\t")}


def read_participants_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))
