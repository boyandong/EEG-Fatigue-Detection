"""PVT target construction. Raw trial files are READ-ONLY; nothing here writes to data/.

Targets produced (SCIENTIFIC_SPEC.md section 10):

  paper-compatible :  Delta RT_i = median(RT_SD) - median(RT_NS)      [only for the reference check]
  primary candidate:  Y_RT_i     = ln( median(RT_SD) / median(RT_NS) )
  secondary        :  Y_speed_i  = ln( V_NS / V_SD ),  V = mean(1/RT)

Trial filter, fixed a priori: 100 <= RT <= 2000 ms.

The official participants.tsv summaries are carried alongside the recomputed values and are
never silently discarded. `reconcile` produces the full comparison table.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TRIAL_COLUMN_CANDIDATES = ("trial", "trail")
RESPONSE_COLUMN_CANDIDATES = ("response_time", "resoonse_time", "respones_time", "response")

# Header variants observed in ds004902 (see PHASE1_REPORT.md section B).
KNOWN_HEADER_VARIANTS = {
    ("trial", "response_time"): "standard",
    ("trail", "response_time"): "typo_trail",
    ("trial", "resoonse_time"): "typo_resoonse",
    ("trial", "respones_time"): "typo_respones",
    ("trial", "response"): "short_response",
}


@dataclass
class TrialSession:
    """One subject-session of PVT trial data."""

    subject: str
    session: str
    path: Path
    trial_column: str
    response_column: str
    header_variant: str
    n_rows: int
    rt_raw: list[float | None] = field(default_factory=list)
    missing_rows: int = 0
    invalid_rows: int = 0
    duplicate_trial_ids: int = 0

    @property
    def valid_rt(self) -> np.ndarray:
        return np.array([x for x in self.rt_raw if x is not None], dtype=float)


def parse_trial_file(path: Path, subject: str, session: str,
                     min_rt_ms: float, max_rt_ms: float) -> tuple[TrialSession, dict]:
    """Parse one raw PVT trial TSV. Never writes. Returns (TrialSession, audit)."""
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if not rows:
        raise ValueError(f"empty trial file {path.name}")
    headers = list(rows[0].keys())

    trial_col = next((c for c in TRIAL_COLUMN_CANDIDATES if c in headers), None)
    resp_col = next((c for c in RESPONSE_COLUMN_CANDIDATES if c in headers), None)
    if trial_col is None:
        raise ValueError(f"no trial column in {path.name}: headers={headers}")
    if resp_col is None:
        raise ValueError(f"no response column in {path.name}: headers={headers}")
    variant = KNOWN_HEADER_VARIANTS.get((trial_col, resp_col), "unrecognised")

    n_missing = n_invalid = 0
    raw: list[float | None] = []
    ids: list[str] = []
    for r in rows:
        v = (r.get(resp_col) or "").strip()
        if v == "" or v.lower() in {"n/a", "na", "nan", "none"}:
            raw.append(None); n_missing += 1; continue
        try:
            f = float(v)
        except ValueError:
            raw.append(None); n_invalid += 1; continue
        if not np.isfinite(f):
            raw.append(None); n_invalid += 1; continue
        # OUT-OF-RANGE responses are missing, not clamped and not zero-filled.
        raw.append(f if (min_rt_ms <= f <= max_rt_ms) else None)
        ids.append(str(r.get(trial_col, "")))

    seen, dupes = set(), 0
    for i in ids:
        if i in seen:
            dupes += 1
        seen.add(i)

    ts = TrialSession(subject=subject, session=session, path=path, trial_column=trial_col,
                      response_column=resp_col, header_variant=variant, n_rows=len(rows),
                      rt_raw=raw, missing_rows=n_missing, invalid_rows=n_invalid,
                      duplicate_trial_ids=dupes)
    audit = {
        "file": path.name, "headers": headers, "trial_column": trial_col,
        "response_column": resp_col, "header_variant": variant, "n_rows": len(rows),
        "n_missing": n_missing, "n_invalid": n_invalid,
        "duplicate_trial_ids": dupes,
        "n_valid_in_range": int(len(ts.valid_rt)),
    }
    # count how many raw numeric responses fell outside the retained window
    n_numeric, n_out = 0, 0
    for r in rows:
        v = (r.get(resp_col) or "").strip()
        try:
            f = float(v)
        except ValueError:
            continue
        n_numeric += 1
        if not (min_rt_ms <= f <= max_rt_ms):
            n_out += 1
    audit["n_numeric_responses"] = n_numeric
    audit["n_out_of_range_removed"] = n_out
    audit["min_rt_retained_ms"] = min_rt_ms
    audit["max_rt_retained_ms"] = max_rt_ms
    return ts, audit


def discover_trial_files(bids_root: Path) -> list[tuple[str, str, Path]]:
    """Locate every raw PVT trial TSV under a BIDS root."""
    out = []
    for p in sorted(bids_root.glob("sub-*/ses-*/beh/*task-pvt_beh.tsv")):
        parts = p.parts
        subject = next(x for x in parts if re.fullmatch(r"sub-\d+", x))
        session = next(x for x in parts if re.fullmatch(r"ses-\d+", x))
        out.append((subject, session, p))
    return out


def _median(x: list[float]) -> float | None:
    return float(np.median(x)) if len(x) else None


def session_targets(ts: TrialSession) -> dict:
    """Per-session RT statistics over the retained valid trials."""
    rt = ts.valid_rt
    if rt.size == 0:
        return {"n_valid": 0, "median_rt_ms": None, "mean_rt_ms": None,
                "response_speed_per_s": None, "sd_rt_ms": None}
    return {
        "n_valid": int(rt.size),
        "median_rt_ms": _median(list(rt)),
        "mean_rt_ms": float(rt.mean()),
        "response_speed_per_s": float(np.mean(1.0 / rt)),
        "sd_rt_ms": float(rt.std(ddof=1)) if rt.size > 1 else None,
    }


def paired_targets(ns: dict, sd: dict) -> dict:
    """Personal-relative targets. Requires a valid median in both sessions.

    `ns` and `sd` are per-session statistic dicts as returned by `session_targets`.
    Returns a dict that ALWAYS contains the three target keys plus `computed`/`reason`.
    """
    out = {
        "delta_median_rt_ms": None,        # paper-compatible
        "Y_log_medianRT_raw": None,        # primary candidate
        "Y_log_response_speed_raw": None,  # secondary candidate
        "computed": False,
        "reason": "",
    }
    if not ns or not sd:
        out["reason"] = "one or both sessions absent from the trial-file inventory"
        return out
    if ns.get("median_rt_ms") is None or sd.get("median_rt_ms") is None:
        out["reason"] = "median RT missing in at least one session"
        return out
    if ns["median_rt_ms"] <= 0 or sd["median_rt_ms"] <= 0:
        out["reason"] = "non-positive median RT"
        return out
    out["delta_median_rt_ms"] = sd["median_rt_ms"] - ns["median_rt_ms"]
    out["Y_log_medianRT_raw"] = float(np.log(sd["median_rt_ms"] / ns["median_rt_ms"]))
    if ns.get("response_speed_per_s") and sd.get("response_speed_per_s"):
        out["Y_log_response_speed_raw"] = float(np.log(ns["response_speed_per_s"] / sd["response_speed_per_s"]))
        out["reason"] = ""
    else:
        out["reason"] = "response speed unavailable in at least one session"
    out["computed"] = True
    return out


def _num(x):
    """official participants.tsv values -> float or None. 'n/a' stays missing, never 0."""
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in {"n/a", "na", "nan", "none"}:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f if np.isfinite(f) else None


def reconcile(subjects: list[str], raw: dict, official: dict,
              *, baseline_session: str = "ses-1", perturbation_session: str = "ses-2") -> list[dict]:
    """Build the full official-vs-raw comparison table (SCIENTIFIC_SPEC.md section 10.4).

    `raw` is keyed {subject: {session_id: session_statistics}}. Both the session-id keys and
    the NS/SD aliases are accepted, so the caller cannot silently pass the wrong shape.
    """
    rows = []
    for s in subjects:
        o = official.get(s, {})
        r = raw.get(s, {}) or {}
        ns = r.get(baseline_session) or r.get("NS") or {}
        sd = r.get(perturbation_session) or r.get("SD") or {}
        o_ns, o_sd = _num(o.get("PVT_item2_NS")), _num(o.get("PVT_item2_SD"))
        r_ns = ns.get("median_rt_ms")
        r_sd = sd.get("median_rt_ms")
        o_delta = (o_sd - o_ns) if (o_ns is not None and o_sd is not None) else None
        r_delta = (r_sd - r_ns) if (r_ns is not None and r_sd is not None) else None
        reasons = []
        if o_ns is None: reasons.append("official_NS_missing")
        if o_sd is None: reasons.append("official_SD_missing")
        if r_ns is None: reasons.append("raw_NS_missing")
        if r_sd is None: reasons.append("raw_SD_missing")
        rows.append({
            "subject": s,
            "official_median_rt_ns": o_ns, "official_median_rt_sd": o_sd,
            "raw_filtered_median_rt_ns": r_ns, "raw_filtered_median_rt_sd": r_sd,
            "official_delta": o_delta, "raw_delta": r_delta,
            "difference_ns": (r_ns - o_ns) if (r_ns is not None and o_ns is not None) else None,
            "difference_sd": (r_sd - o_sd) if (r_sd is not None and o_sd is not None) else None,
            "raw_trials_ns": ns.get("n_rows"),
            "raw_trials_sd": sd.get("n_rows"),
            "valid_trials_ns": ns.get("n_valid"),
            "valid_trials_sd": sd.get("n_valid"),
            "exclusion_reason": ";".join(reasons),
        })
    return rows


def subject_sets(recon: list[dict]) -> dict:
    """Explicit subject sets used to compare with the published N."""
    official_paired = sorted(r["subject"] for r in recon
                             if r["official_median_rt_ns"] is not None and r["official_median_rt_sd"] is not None)
    raw_paired = sorted(r["subject"] for r in recon
                        if r["raw_filtered_median_rt_ns"] is not None and r["raw_filtered_median_rt_sd"] is not None)
    return {
        "official_paired": official_paired,
        "raw_trial_paired": raw_paired,
        "n_official_paired": len(official_paired),
        "n_raw_trial_paired": len(raw_paired),
        "in_official_not_raw": sorted(set(official_paired) - set(raw_paired)),
        "in_raw_not_official": sorted(set(raw_paired) - set(official_paired)),
        "in_both": sorted(set(official_paired) & set(raw_paired)),
    }


def load_official(participants_tsv: Path) -> dict[str, dict]:
    with participants_tsv.open(encoding="utf-8-sig") as f:
        return {r["participant_id"]: r for r in csv.DictReader(f, delimiter="\t")}


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = columns or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})
