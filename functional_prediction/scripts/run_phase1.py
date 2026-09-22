"""Run the whole Phase 1 pipeline in order.

    python project/vigilance_generalization_v1/scripts/run_phase1.py

Stages (see SCIENTIFIC_SPEC.md section 16):
  00  source EEG provenance audit
  02  eyes-open EEG manifest
  01  PVT target reconstruction + reconciliation
  03  paper_reference + mechanism_v1 feature extraction
  04  feature-side QC
  05  paper-reference reproduction sanity check
  tests  mechanism mathematical unit tests
  06  independent verification (recomputes features from raw .set)
  07  consolidated run manifest (last, so verification.json is included)

Stops at the first failing stage. Never trains a model.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

VIG = Path(__file__).resolve().parents[1]
PY = sys.executable

STAGES = [
    ("00 source provenance audit", "scripts/00_audit_source_data.py"),
    ("02 eyes-open EEG manifest", "scripts/02_build_eeg_manifest.py"),
    ("01 PVT targets + reconciliation", "scripts/01_build_pvt_targets.py"),
    ("03 feature extraction", "scripts/03_extract_features.py"),
    ("04 feature-side QC", "scripts/04_qc_features.py"),
    ("05 paper-reference check", "scripts/05_paper_reference_check.py"),
    ("tests mechanism unit tests", "tests/test_mechanism.py"),
    ("06 independent verification", "scripts/06_verify_phase1.py"),
    ("07 finalize run manifest", "scripts/07_finalize_run_manifest.py"),
]


def main() -> int:
    t0 = time.perf_counter()
    for label, rel in STAGES:
        script = VIG / rel
        if not script.exists():
            print(f"[SKIP] {label}: {rel} not found")
            continue
        print(f"\n{'='*78}\n[{label}]  {rel}\n{'='*78}", flush=True)
        t = time.perf_counter()
        proc = subprocess.run([PY, "-X", "utf8", str(script)], cwd=str(VIG))
        dt = time.perf_counter() - t
        if proc.returncode != 0:
            print(f"\nFAILED at {label} (exit {proc.returncode}) after {dt:.1f}s")
            return proc.returncode
        print(f"  -> ok in {dt:.1f}s", flush=True)
    print(f"\nPHASE 1 PIPELINE COMPLETE in {time.perf_counter()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
