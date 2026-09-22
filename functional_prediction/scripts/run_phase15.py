"""Run the Phase 1.5 pipeline in order.

    python project/vigilance_generalization_v1/scripts/run_phase15.py

  10  window feature extraction (all 68 subjects / 136 sessions, duration grid)
  11  stability metrics: Experiments A/B/C, delta stability, baseline scenario
  12  finite-sample behaviour of J
  13  plots
  14  independent verification
  probe  official raw-data recovery feasibility (network, read-only)

Never touches a PVT target for selection and never trains a model.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

VIG = Path(__file__).resolve().parents[1]
PY = sys.executable

STAGES = [
    ("10 window extraction", "scripts/10_extract_windows.py"),
    ("11 stability metrics", "scripts/11_stability_metrics.py"),
    ("12 finite-sample J", "scripts/12_finite_sample_J.py"),
    ("13 plots", "scripts/13_stability_plots.py"),
    ("14 verification", "scripts/14_verify_phase15.py"),
    ("raw recovery probe", "src/probe_raw_recovery.py"),
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
    print(f"\nPHASE 1.5 PIPELINE COMPLETE in {time.perf_counter()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
