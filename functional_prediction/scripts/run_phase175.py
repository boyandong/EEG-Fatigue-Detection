"""Run the Phase 1.75 pipeline in order.

    python project/vigilance_generalization_v1/scripts/run_phase175.py

  20  dynamic observable extraction (J, V, J_res, D, M) over the duration and Protocol(B,T) grids
  21  PVT target psychometrics (target-only; no EEG feature is read)
  22  J vs V vs J_res stability comparison and the Protocol(B,T) audit
  24  plots
  23  independent verification

Never trains a model, never computes an EEG-PVT association, never reads PVT for selection.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

VIG = Path(__file__).resolve().parents[1]
PY = sys.executable

STAGES = [
    ("20 dynamic extraction", "scripts/20_extract_dynamic.py"),
    ("21 PVT psychometrics", "scripts/21_pvt_psychometrics.py"),
    ("22 dynamic stability", "scripts/22_dynamic_stability.py"),
    ("24 plots", "scripts/24_dynamic_plots.py"),
    ("23 verification", "scripts/23_verify_phase175.py"),
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
        rc = subprocess.run([PY, "-X", "utf8", str(script)], cwd=str(VIG)).returncode
        if rc != 0:
            print(f"\nFAILED at {label} (exit {rc}) after {time.perf_counter()-t:.1f}s")
            return rc
        print(f"  -> ok in {time.perf_counter()-t:.1f}s", flush=True)
    print(f"\nPHASE 1.75 PIPELINE COMPLETE in {time.perf_counter()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
