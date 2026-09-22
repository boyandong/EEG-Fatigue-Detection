"""Phase 3C — the two checks that must hold for every behavioural claim in this package.

1. **The scope guard.** Phase 3C is a behavioural lane: the brief forbids every EEG-side
   operation (spectral density, band power, `M`/`J`/`V`, EEG features/embeddings, any
   EEG<->behaviour statistic, any EEG model, endpoint fishing). That prohibition must be
   *enforced*, not stated, so the guard scans the package's own source with
   comment/docstring masking — and is then proved to bite by feeding it files that violate
   each ban. Phase 3B shipped a checker that silently passed real violations; this is the
   negative control that prevents a repeat.

2. **The vehicle-only read contract.** Phase 3C's central structural guarantee is that it
   never touches an EEG row of the payload matrix. `p3c_common.vehicle_indices` is the single
   place that decides which columns are read. These assertions pin that contract: exactly the
   four vehicle channels, in the declared order, and a refusal for anything else.

Run:
    python tests/test_phase3c_scope.py
Exit code gates the phase alongside the verifier.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BRANCH = HERE.parent
PHASE3C = BRANCH / "audit" / "phase3c"
sys.path.insert(0, str(PHASE3C / "src"))

# ONE implementation of the scope guard, shared with `40_verify_phase3c.py`, loaded from its
# own file by path. Phase 3B ships a module with the same basename in `audit/phase3b/src/`,
# and `p3c_common` puts THAT directory on `sys.path` — so a bare `import scope_guard` reached
# Phase 3B's guard instead of this one and reported violations this lane does not commit.
# The module is named `p3c_scope_guard.py` and loaded by path so neither route can collide.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "p3c_scope_guard", PHASE3C / "src" / "p3c_scope_guard.py")
scope_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scope_guard)
scan = scope_guard.scan

RESULTS: list[tuple[str, bool, str]] = []


def check(cid: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((cid, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<60} {detail}")


def main() -> int:
    print("=" * 84)
    print("Phase 3C — scope guard and vehicle-only read contract")
    print("=" * 84)

    EXCLUDE = {"40_verify_phase3c.py", "50_write_report.py", "p3c_scope_guard.py"}
    package = sorted(PHASE3C.glob("*.py")) + sorted((PHASE3C / "src").glob("*.py"))
    package = [p for p in package if p.name not in EXCLUDE]
    hits = scan(package)
    check("S1 no forbidden EEG-side analysis in the Phase 3C package", not hits,
          "; ".join(hits[:4]) or f"scanned {len(package)} files "
          f"(excluded: {sorted(EXCLUDE)})")

    # --- negative controls for the guard itself -----------------------------
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        poison = {
            "welch.py": "from scipy.signal import welch\nf, p = welch(sig, fs=2048)\n",
            "band.py": "theta_power = 1.0\nband_power = theta_power\n",
            "model.py": "from sklearn.linear_model import Ridge\nm = Ridge().fit(X, y)\n",
            "eegcorr.py": "r = np.corrcoef(eeg_window, lane_deviation)[0, 1]\n",
            "conn.py": "plv = compute_connectivity(x)\n",
            "cnn.py": "net = ShallowConvNet(n_chans=64)\n",
            "probe.py": "auc = subject_id_probe(embedding)\n",
            "fish.py": "w = best_window(y, grid)\n",
        }
        caught = []
        for name, src in poison.items():
            f = t / name
            f.write_text(src, encoding="utf-8")
            if scan([f]):
                caught.append(name)
        check("S2 the guard catches every deliberately injected violation",
              len(caught) == len(poison), f"{len(caught)}/{len(poison)}: {sorted(caught)}")

        benign = t / "benign.py"
        benign.write_text(
            '"""We compute no PSD, no theta power, no EEG feature and no EEG model here; '
            'Phase 3C is behavioural."""\n'
            "# no welch, no sklearn, no corrcoef, no ShallowConvNet\n"
            "x = 1\n", encoding="utf-8")
        check("S3 the guard does not flag banned terms inside docstrings/comments",
              not scan([benign]), "masking works")

        allowed = t / "allowed.py"
        allowed.write_text(
            "import numpy as np\n"
            "beta = np.linalg.pinv(X.T @ X) @ (X.T @ y)   # OLS via normal equations\n"
            "u = mannwhitney_u(a, b)\n"
            "b = moving_block_bootstrap(v, block=6)\n", encoding="utf-8")
        check("S4 the guard permits the behavioural statistics the brief requires",
              not scan([allowed]), "OLS / U-test / block bootstrap are in scope")

    # --- vehicle-only read contract ----------------------------------------
    sys.path.insert(0, str(PHASE3C / "src"))
    from p3c_common import VEHICLE_CHANNELS, vehicle_indices  # noqa: E402

    names = ["Fp1", "AF7", "LN", "Fz", "ANG", "SP", "SD", "Cz"]
    idx = vehicle_indices(names)
    check("S5 vehicle_indices returns exactly the four vehicle channels",
          tuple(names[i] for i in idx) == VEHICLE_CHANNELS,
          f"indices={idx} -> {tuple(names[i] for i in idx)}")
    check("S6 vehicle_indices refuses a montage without all four channels",
          _raises(vehicle_indices, ["Fp1", "LN", "ANG", "SP"]),
          "KeyError raised for a missing `SD`")

    # order-independence: the returned columns must follow VEHICLE_CHANNELS, not the montage
    shuffled = ["SD", "Cz", "SP", "Fp1", "ANG", "LN"]
    idx2 = vehicle_indices(shuffled)
    check("S7 the returned order follows VEHICLE_CHANNELS, not the montage order",
          tuple(shuffled[i] for i in idx2) == VEHICLE_CHANNELS,
          f"{tuple(shuffled[i] for i in idx2)}")

    # --- documentation constants must be quoted, not invented ---------------
    from p3c_common import (COURSE_CORRECTION_CRITERION, HEADING_ERROR_DEG,  # noqa: E402
                            STEERING_ANGLE_DEG, event_docs)
    ok_doc = True
    detail = []
    for ds in ("ds004118", "ds004120"):
        doc = event_docs(ds)
        crit = doc["hed_defs"]["Levels"]["course_correction"]
        if crit != COURSE_CORRECTION_CRITERION:
            ok_doc = False
            detail.append(f"{ds}: criterion mismatch")
        if str(HEADING_ERROR_DEG) not in crit or f"{STEERING_ANGLE_DEG:g} degrees" not in crit:
            ok_doc = False
            detail.append(f"{ds}: thresholds absent from the verbatim text")
        for code in ("1111", "1121", "4311", "4312", "3200", "4210", "4220", "4230"):
            if code not in doc["value"]["Levels"]:
                ok_doc = False
                detail.append(f"{ds}: code {code} undocumented")
    check("S8 every behaviour constant is quoted from the release documentation",
          ok_doc, "; ".join(detail) or "criterion + 8 event codes verified in both datasets")

    # --- the cached behaviour data must exist and be vehicle-only -----------
    from p3c_common import CACHE, local_recordings  # noqa: E402
    recs = local_recordings()
    missing = [r.key for r in recs if not (CACHE / f"{r.cache_key}.npz").exists()]
    check("S9 every local recording has a behavioural cache file",
          not missing, f"{len(recs)} recordings, missing={missing}")
    if not missing:
        z = np.load(CACHE / f"{recs[0].cache_key}.npz", allow_pickle=False)
        keys = set(z.files)
        check("S10 the cache holds vehicle channels, the simulator clock and events only",
              keys == {"LN", "ANG", "SP", "SD", "clock", "times_ms", "ev_codes",
                       "ev_onset_s", "ev_sample", "srate", "n_samples",
                       "valid_start", "valid_stop"},
              f"keys={sorted(keys)}")

    return _report()


def _raises(fn, *args) -> bool:
    try:
        fn(*args)
        return False
    except KeyError:
        return True
    except Exception:  # noqa: BLE001
        return False


def _report() -> int:
    n = len(RESULTS)
    ok = sum(1 for _, p, _ in RESULTS if p)
    print("=" * 84)
    print(f"{ok}/{n} checks passed" + ("" if ok == n else " — FAILURES PRESENT"))
    for cid, p, d in RESULTS:
        if not p:
            print(f"  FAIL {cid}: {d}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
