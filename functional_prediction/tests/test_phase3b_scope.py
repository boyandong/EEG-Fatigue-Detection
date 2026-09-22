"""Phase 3B — the two checks that must hold for every audit claim in this package.

1. **The scope guard.** The brief forbids, for this session: PSD, band powers, `M`/`J`/`V`,
   connectivity, CSP, embeddings, any EEG-vs-behaviour statistic, any model, any endpoint
   selection. That prohibition must be *enforced*, not merely stated, so the guard below
   scans the package's own source with comment/docstring masking and is then proved to bite
   by feeding it files that violate each ban.

2. **The container contract.** The `.set` files are MATLAB v7.3 / HDF5, and the audit's
   numbers depend on that: `data` is `(n_samples, n_channels)` with channel `c` = column `c`,
   struct-array string fields are HDF5 references, and there is no `.fdt`. These assertions
   are cheap and they are exactly what a wrong assumption would break silently.

Run:
    python tests/test_phase3b_scope.py
Exit code gates the phase alongside the verifier.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PHASE3B = HERE.parent / "audit" / "phase3b"
sys.path.insert(0, str(PHASE3B / "src"))

# ONE implementation of the scope guard, shared with `26_verify_spec_conformance.py`.
# It used to be duplicated in both files and the two copies disagreed: the verifier's copy
# flagged a file whose only offence was describing what it does not do. See src/scope_guard.py.
from scope_guard import strip_code, scan  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(cid: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((cid, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<58} {detail}")


def main() -> int:
    print("=" * 80)
    print("Phase 3B — scope guard and container contract")
    print("=" * 80)

    package = sorted(PHASE3B.glob("*.py")) + sorted((PHASE3B / "src").glob("*.py"))
    # Kept in sync with the verifier's I1 exclusion: these name the prohibited operations
    # (scope statement, container probe, report prose, verifiers) rather than performing them.
    # `tests/test_phase3b_scope.py::S2` is what proves the scan still catches violations.
    EXCLUDE = {"20_verify_phase3b.py", "probe_set_container.py", "30_write_report.py",
               "25_spec_conformance.py", "26_verify_spec_conformance.py", "scope_guard.py"}
    package = [p for p in package if p.name not in EXCLUDE]
    hits = scan(package)
    check("S1 no forbidden analysis in the Phase 3B audit package",
          not hits, "; ".join(hits[:4]) or f"scanned {len(package)} files "
          f"(excluded: {sorted(EXCLUDE)})")

    # --- negative controls for the guard itself -----------------------------
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        poison = {
            "welch.py": "from scipy.signal import welch\nx = welch(sig, fs=2048)\n",
            "band.py": "theta = 4.0\nband_power = 1.0\n",
            "model.py": "from sklearn.linear_model import Ridge\nm = Ridge().fit(X, y)\n",
            "corr.py": "r = np.corrcoef(eeg, vehicle)[0, 1]\n",
            "conn.py": "plv = compute_connectivity(x)\n",
        }
        caught = []
        for name, src in poison.items():
            f = t / name
            f.write_text(src, encoding="utf-8")
            if scan([f]):
                caught.append(name)
        check("S2 the guard catches every deliberately injected violation",
              len(caught) == len(poison), f"{len(caught)}/{len(poison)}: {sorted(caught)}")

        # and it must NOT flag a mention inside a docstring or comment
        benign = t / "benign.py"
        benign.write_text('"""We do not compute a PSD, theta power or connectivity here."""\n'
                          "# no welch, no sklearn, no corrcoef\nx = 1\n", encoding="utf-8")
        check("S3 the guard does not flag banned terms inside docstrings/comments",
              not scan([benign]), "masking works")

    # --- container contract -------------------------------------------------
    ref = PHASE3B / "raw" / "ds004118" / "sub-01" / "ses-01" / "eeg" / \
        "sub-01_ses-01_task-Drive_run-1_eeg.set"
    if not ref.exists():
        check("S4 container contract", False, f"reference payload missing: {ref}")
        return _report()
    from bcit_set import BcitSet  # noqa: E402

    with BcitSet(ref) as s:
        check("S4 container is MATLAB v7.3 / HDF5",
              s.container_kind() == "matlab-v7.3-hdf5", s.container_kind())
        hdr = s.read()
        check("S5 `data` is (n_samples, n_channels) so MATLAB channel c is HDF5 column c",
              hdr.data_hdf5_shape[0] == hdr.n_samples
              and hdr.data_hdf5_shape[1] == hdr.n_channels,
              f"shape={hdr.data_hdf5_shape} n_samples={hdr.n_samples} n_ch={hdr.n_channels}")
        check("S6 no `.fdt` companion exists for this recording",
              not ref.with_suffix(".fdt").exists() and not ref.parent.joinpath(
                  ref.name.replace("_eeg.set", "_eeg.fdt")).exists(),
              "release ships a self-contained .set")
        idx = {n: i for i, n in enumerate(hdr.channel_names)}
        rows = [idx[c] for c in ("LN", "ANG", "SP", "SD") if c in idx]
        check("S7 the four vehicle channels are addressable by name in the payload",
              len(rows) == 4, f"indices={rows}")
        block = s.channels(rows)
        check("S8 the channel slice returns (n_channels, n_samples) of finite floats",
              block.shape == (4, hdr.n_samples) and np.isfinite(block).all(),
              f"shape={block.shape} dtype={block.dtype}")
        # Cross-check the slice against a single-column read: if the transpose convention
        # were wrong, these would disagree.
        one = s.channel(idx["LN"])
        check("S9 column-index convention agrees between the slice and the single-channel read",
              np.array_equal(one, block[rows.index(idx["LN"])]),
              f"max|diff|={np.max(np.abs(one - block[rows.index(idx['LN'])]))}")
        check("S10 root strings decode as MATLAB char arrays (ref/setname present)",
              bool(hdr.ref) and bool(hdr.setname), f"ref={hdr.ref!r}")
        check("S11 struct-array string fields decode via HDF5 references",
              len(hdr.channel_names) == hdr.n_channels
              and hdr.channel_names[:3] == ["Fp1", "AF7", "AF3"],
              f"first3={hdr.channel_names[:3]}")
        check("S12 etc/TrialData/subject reads out as the legacy_labID",
              hdr.trial_data.get("subject") == "1001", f"subject={hdr.trial_data.get('subject')!r}")
        check("S13 the payload carries a per-sample vehicle clock in etc/timestamp",
              s.vehicle_timestamps() is not None
              and s.vehicle_timestamps().size == hdr.n_samples,
              f"n={0 if s.vehicle_timestamps() is None else s.vehicle_timestamps().size}")
    return _report()


def _report() -> int:
    n = len(RESULTS)
    ok = sum(1 for _, p, _ in RESULTS if p)
    print("=" * 80)
    print(f"{ok}/{n} checks passed" + ("" if ok == n else " — FAILURES PRESENT"))
    for cid, p, d in RESULTS:
        if not p:
            print(f"  FAIL {cid}: {d}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
