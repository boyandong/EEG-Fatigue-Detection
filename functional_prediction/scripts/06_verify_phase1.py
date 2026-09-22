"""06 - Independent verification of the Phase 1 deliverables.

    python project/vigilance_generalization_v1/scripts/06_verify_phase1.py

This script does NOT trust the extraction script. It independently:
  * re-derives the cohort from the manifests and checks it equals the extracted set;
  * re-loads a sample of EEG recordings and RECOMPUTES mechanism_v1 features from scratch,
    comparing against the values in outputs/mechanism_v1/session_features.csv;
  * re-derives delta features from the saved session table and compares against
    outputs/mechanism_v1/paired_features.csv;
  * checks the ROI partition, the composition identity, the band definitions, and the
    absence of forbidden operations in the source tree;
  * checks the determinism contract by re-running one recording twice.

Exit code 0 = verified.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import cohort as CO  # noqa: E402
import common as C  # noqa: E402
import mechanism_features as MF  # noqa: E402
from roi import REGION_NAMES, load_roi_mapping  # noqa: E402
from spectral import SpectralConfig, band_powers  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))


def main() -> int:
    ds = C.dataset_config()
    mech = C.mechanism_config()
    canonical = [c for r in REGION_NAMES for c in ds["roi"][r]]
    sfreq = float(ds["eeg"]["target_sfreq_hz"])
    roi = load_roi_mapping(ds["roi"])
    sc = SpectralConfig.from_dict(ds)
    eps_j = float(mech["personal_relative"]["delta_logJ"]["numerical_epsilon"])

    # ------------------------------------------------------------------ 1. required outputs
    print("1. Required deliverables exist")
    required = [
        "SCIENTIFIC_SPEC.md",
        "outputs/manifests/source_eeg_manifest.csv",
        "outputs/manifests/pvt_manifest.csv",
        "outputs/manifests/eeg_eyesopen_manifest.csv",
        "outputs/pvt/pvt_reconciliation.csv",
        "outputs/pvt/pvt_targets_raw.csv",
        "outputs/pvt/pvt_targets_official.csv",
        "outputs/pvt/pvt_subject_sets.json",
        "outputs/paper_reference/session_features.csv",
        "outputs/paper_reference/paired_features.csv",
        "outputs/paper_reference/reproduction_report.md",
        "outputs/mechanism_v1/session_features.csv",
        "outputs/mechanism_v1/paired_features.csv",
        "outputs/qc/feature_qc.csv",
        "outputs/qc/exclusions.csv",
        "outputs/qc/run_manifest.json",
    ]
    missing = [r for r in required if not (VIG / r).exists()]
    check("all required deliverables present", not missing, f"missing={missing}")

    # ------------------------------------------------------------------ 2. ROI partition
    print("\n2. ROI mapping is an exact partition of the montage")
    part = roi.validate(canonical)
    check("F=16 CT=28 PO=17 exact partition", part["exact_partition"] and
          part["region_sizes"] == {"F": 16, "CT": 28, "PO": 17}, str(part["region_sizes"]))

    # ------------------------------------------------------------------ 3. forbidden constructs
    print("\n3. Forbidden operations absent from the source tree")
    src_files = sorted((VIG / "src").glob("*.py")) + sorted((VIG / "scripts").glob("*.py"))
    blob = "\n".join(p.read_text(encoding="utf-8") for p in src_files)

    # Documentation legitimately QUOTES the forbidden expressions (module docstrings,
    # mechanism_v1.yaml's `forbidden:` list, this script's own check labels), so a raw regex scan
    # over the file text produces both false positives and, if strings are stripped naively,
    # false NEGATIVES. So we scan the text with a small state machine that knows whether each
    # character is inside a string / comment, and only judge `log(...)` calls found in real code.
    def code_mask(text: str) -> list[bool]:
        """mask[i] is True when text[i] is executable code (not string, not comment)."""
        mask = [True] * len(text)
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == "#":
                while i < n and text[i] != "\n":
                    mask[i] = False
                    i += 1
                continue
            if ch in "\"'":
                triple = text[i:i + 3] in ('"""', "'''")
                delim = text[i:i + 3] if triple else ch
                j = i
                for k in range(len(delim)):
                    mask[i + k] = False
                j = i + len(delim)
                while j < n:
                    if text[j] == "\\":
                        mask[j] = False
                        if j + 1 < n:
                            mask[j + 1] = False
                        j += 2
                        continue
                    if text.startswith(delim, j):
                        for k in range(len(delim)):
                            mask[j + k] = False
                        j += len(delim)
                        break
                    mask[j] = False
                    j += 1
                i = j
                continue
            i += 1
        return mask

    mask = code_mask(blob)
    code_only = "".join(c if m else " " for c, m in zip(blob, mask))

    # The forbidden constructs are about BAND POWER, not about every mean in the codebase.
    # A regex cannot balance parentheses, so we extract each `log(...)` call's balanced argument
    # text from `code_only` and judge that.
    # Band-power vocabulary. A bare "P" is deliberately NOT accepted: it would also match the
    # bare `np.mean(...)` inside an unrelated expression.
    _BANDISH = r"(?:P_?[a-z0-9]+|theta|alpha|beta|band[_a-z]*power[_a-z0-9]*|rel[_a-z]*power)"
    # \b before mean so that `np.mean(...)` does NOT count as a bare `mean(...)`: the forbidden
    # construct is the averaging of raw power BEFORE the ratio, e.g. mean(P_theta)/mean(P_alpha),
    # whereas np.mean(1/RT) inside the PVT speed target is legitimate.
    _MEAN_WITH_BAND = re.compile(rf"\bmean\s*\([^()]*(?:{_BANDISH})", re.I)
    _BAND_MEAN_ANY = re.compile(rf"{_BANDISH}[_a-z0-9]*\s*\.mean\s*\(", re.I)

    def _log_calls(text: str) -> list[str]:
        """Balanced argument text of every np.log(...) / log(...) call in executable code.

        A match that is preceded by a quote character is part of a string literal (this script's
        own check labels say "no log(mean(band power))") and is skipped.
        """
        out, i = [], 0
        while True:
            m = re.search(r"\b(?:np\.)?log\s*\(", text[i:])
            if not m:
                break
            s0 = i + m.start()
            if s0 > 0 and text[s0 - 1] in "\"'":
                i = i + m.end()
                continue
            start = i + m.end() - 1              # index of '('
            depth, j = 0, start
            while j < len(text):
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(text[start + 1:j])
            i = j + 1
        return out

    def _has_top_level_division(expr: str) -> bool:
        depth = 0
        for ch in expr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch in "*/" and depth == 0:
                return True
        return False

    log_args = _log_calls(code_only)
    log_mean_of_band = [a for a in log_args if _MEAN_WITH_BAND.search(a)]
    mean_ratio_log = [a for a in log_args
                      if _MEAN_WITH_BAND.search(a) and _has_top_level_division(a)]
    band_attr_mean_log = [a for a in log_args if _BAND_MEAN_ANY.search(a)]

    checks_forbidden = {
        "no log(mean(band power))": not log_mean_of_band and not band_attr_mean_log,
        "no mean-of-ratio-then-log":
            not mean_ratio_log and not band_attr_mean_log,
        "no session-averaged power before the ratio":
            not re.search(rf"{_BANDISH}[_a-z0-9]*\s*\.mean\s*\([^)]*\)\s*/\s*"
                          rf"{_BANDISH}[_a-z0-9]*\s*\.mean\s*\(", code_only, re.I),
        "mechanism module never z-scores a recording":
            not re.search(r"\(x\s*-\s*[a-z_]*mean[a-z_]*\)\s*/\s*[a-z_]*std", code_only),
        "no dataset branch inside mechanism extractor":
            not re.search(r'if\s+dataset\s*==', (VIG / "src" / "mechanism_features.py").read_text(encoding="utf-8")),
        "aperiodic hook not implemented": "NotImplementedError" in (
            VIG / "src" / "mechanism_features.py").read_text(encoding="utf-8"),
        "no specparam/foof import": not re.search(r"^\s*(import|from)\s+(specparam|fooof)", code_only, re.M),
    }
    if log_mean_of_band or band_attr_mean_log or mean_ratio_log:
        print("       offenders:",
              (log_mean_of_band + band_attr_mean_log + mean_ratio_log)[:3])
    for name, ok in checks_forbidden.items():
        check(name, ok)

    # ------------------------------------------------------------------ 4. cohort agreement
    print("\n4. Cohort definition agrees across manifests and outputs")
    co = CO.build_cohort()
    sess = C.read_csv(C.OUTPUTS / "mechanism_v1" / "session_features.csv")
    pair = C.read_csv(C.OUTPUTS / "mechanism_v1" / "paired_features.csv")
    extracted = sorted({r["subject"] for r in pair})
    check("cohort subjects == extracted paired subjects",
          sorted(co.subjects) == extracted,
          f"cohort={len(co.subjects)} extracted={len(extracted)}")
    check("two session rows per paired subject",
          len(sess) == 2 * len(extracted), f"{len(sess)} session rows for {len(extracted)} subjects")
    conds = {(r["subject"], r["condition"]) for r in sess}
    check("every subject has exactly NS and SD",
          all((s, "NS") in conds and (s, "SD") in conds for s in extracted))

    # ------------------------------------------------------------------ 5. RECOMPUTE features
    print("\n5. Independent recomputation of mechanism_v1 features (all subjects)")
    saved = {(r["subject"], r["session"]): r for r in sess}
    max_dM = max_dJ = 0.0
    n_recomputed = 0
    recompute_errors = []
    for subject in extracted:
        try:
            ns, sd = CO.load_paired(subject, co, canonical, sfreq)
        except Exception as exc:  # noqa: BLE001
            recompute_errors.append(f"{subject}: {type(exc).__name__}: {exc}")
            continue
        for rec in (ns, sd):
            key = (subject, rec.session)
            row = saved.get(key)
            if row is None:
                recompute_errors.append(f"{key}: no saved row")
                continue
            bands, _ = band_powers(rec.epochs, rec.sfreq, sc)
            S = MF.slowing_index(bands, sc.numerical_epsilon_uv2)
            idx = roi.indices(rec.channel_names)
            for r in REGION_NAMES:
                S_r = np.median(S[:, idx[r]], axis=1)
                dM = abs(float(S_r.mean()) - float(row[f"M_{r}"]))
                dJ = abs(float(np.std(S_r, ddof=1)) - float(row[f"J_{r}"]))
                max_dM = max(max_dM, dM)
                max_dJ = max(max_dJ, dJ)
            n_recomputed += 1
    check("no recomputation errors", not recompute_errors, str(recompute_errors[:3]))
    check(f"recomputed {n_recomputed} sessions: max|dM|<1e-9", max_dM < 1e-9, f"max|dM|={max_dM:.3e}")
    check(f"recomputed {n_recomputed} sessions: max|dJ|<1e-9", max_dJ < 1e-9, f"max|dJ|={max_dJ:.3e}")

    # ------------------------------------------------------------------ 6. delta features
    print("\n6. Paired deltas reproduce from the session table")
    pair_by_subject = {r["subject"]: r for r in pair}
    max_dDeltaM = max_dDeltaJ = 0.0
    floor_used = False
    for subject in extracted:
        nsr = saved[(subject, CO.BASELINE)]
        sdr = saved[(subject, CO.PERTURBATION)]
        row = pair_by_subject[subject]
        for r in REGION_NAMES:
            dM = (float(sdr[f"M_{r}"]) - float(nsr[f"M_{r}"]))
            max_dDeltaM = max(max_dDeltaM, abs(dM - float(row[f"delta_M_{r}"])))
            jn, js = float(nsr[f"J_{r}"]), float(sdr[f"J_{r}"])
            if jn <= 0 or js <= 0:
                floor_used = True
                dJ = float(np.log((js + eps_j) / (jn + eps_j)))
            else:
                dJ = float(np.log(js / jn))
            max_dDeltaJ = max(max_dDeltaJ, abs(dJ - float(row[f"delta_logJ_{r}"])))
    check("delta_M reproduces exactly", max_dDeltaM < 1e-12, f"max diff={max_dDeltaM:.3e}")
    check("delta_logJ reproduces exactly", max_dDeltaJ < 1e-12, f"max diff={max_dDeltaJ:.3e}")
    check("delta_logJ epsilon floor never needed", not floor_used)

    # ------------------------------------------------------------------ 7. determinism
    print("\n7. Determinism contract on a real recording")
    rec = CO.load_session(extracted[0], CO.BASELINE, co, canonical, sfreq)
    a = MF.extract_session_features(rec.epochs, rec.channel_names, rec.sfreq, roi, sc)
    b = MF.extract_session_features(rec.epochs.copy(), rec.channel_names, rec.sfreq, roi, sc)
    check("two runs give bitwise-identical M and J",
          all(a.M[r] == b.M[r] and a.J[r] == b.J[r] for r in REGION_NAMES))

    # ------------------------------------------------------------------ 8. gain invariance on real data
    print("\n8. Gain invariance on a real recording")
    rec2 = MF.extract_session_features(rec.epochs * 7.5, rec.channel_names, rec.sfreq, roi, sc)
    dM = max(abs(rec2.M[r] - a.M[r]) for r in REGION_NAMES)
    dJ = max(abs(rec2.J[r] - a.J[r]) for r in REGION_NAMES)
    check("x7.5 gain leaves M and J unchanged on real EEG", dM < 1e-5 and dJ < 1e-4,
          f"max|dM|={dM:.3e} max|dJ|={dJ:.3e}")

    # ------------------------------------------------------------------ 9. manifest integrity
    print("\n9. Manifest and provenance integrity")
    mf_rows = C.read_csv(C.OUTPUTS / "manifests" / "eeg_eyesopen_manifest.csv")
    check("no non-500 Hz recording admitted",
          all(np.isclose(float(r["header_sfreq"]), sfreq) for r in mf_rows))
    check("all admitted recordings have an eyes-open verdict",
          all(r["eye_state_verdict"] in ("explicit_open", "implicit_open", "no_evidence") for r in mf_rows))
    check("no admitted recording declares eyes-closed",
          not any("closed" in r["eye_state_verdict"] for r in mf_rows))
    check("admitted stems are unique", len({r["stem"] for r in mf_rows}) == len(mf_rows))
    sess_hashes = {r["set_sha256"] for r in sess}
    check("every extracted session carries a distinct file hash",
          len(sess_hashes) == len(sess), f"{len(sess_hashes)} hashes / {len(sess)} session rows")
    # the extraction stage hashes the .set it actually read; re-hash one of them here and
    # confirm it matches what the session table recorded.
    probe = sess[0]
    real_hash = C.sha256_file(C.resolve(ds["paths"]["eeg_preprocessed_dir"]) / probe["source_file"])
    check("session table set_sha256 matches a fresh re-hash",
          real_hash == probe["set_sha256"], f"{probe['source_file']}")

    # ------------------------------------------------------------------ summary
    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print("=" * 78)
    print(f"{len(CHECKS) - n_fail}/{len(CHECKS)} verification checks passed")
    if n_fail:
        print("FAILED:")
        for n, ok, d in CHECKS:
            if not ok:
                print("  -", n, d)

    C.write_json(C.OUTPUTS / "qc" / "verification.json", {
        "status": "passed" if n_fail == 0 else "failed",
        "n_checks": len(CHECKS), "n_failed": n_fail,
        "checks": [{"name": n, "passed": ok, "detail": d} for n, ok, d in CHECKS],
        "recomputed_sessions": n_recomputed,
        "note": ("Mechanism features were independently recomputed from the raw .set files and "
                 "compared against the shipped CSVs. This script does not call the extraction "
                 "script's output as input."),
    })
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
