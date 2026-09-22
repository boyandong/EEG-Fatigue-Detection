"""14 - Independent verification of the Phase 1.5 stability deliverables.

    python project/vigilance_generalization_v1/scripts/14_verify_phase15.py

Does NOT trust the extraction script. It:
  * re-loads raw .set files and RECOMPUTES window features for a sample of records and
    durations, comparing against session_window_features.csv;
  * verifies that disjoint windows are truly disjoint and count correctly;
  * verifies that a `full` row equals the features of the whole session;
  * re-derives paired-window deltas from the session table and compares;
  * confirms every stability CSV has the required columns;
  * confirms the duration grid and that no PVT target column entered any stability table
    used for duration selection.

Exit code 0 = verified.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import stability as ST  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []
OUT = None


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))


def main() -> int:
    global OUT
    OUT = C.OUTPUTS / "stability_v1"
    est = ST.Estimator.build()

    required = ["session_window_features.csv", "paired_window_features.csv",
                "duration_summary.csv", "position_drift.csv", "disjoint_agreement.csv",
                "accumulation_convergence.csv", "delta_sign_stability.csv",
                "finite_sample_J_simulation.csv", "plots"]
    print("1. Required deliverables")
    missing = [r for r in required if not (OUT / r).exists()]
    check("all stability_v1 deliverables present", not missing, f"missing={missing}")
    check("plots directory non-empty", len(list((OUT / "plots").glob("*.png"))) >= 5,
          f"{len(list((OUT / 'plots').glob('*.png')))} png")

    sess = C.read_csv(OUT / "session_window_features.csv")
    pair = C.read_csv(OUT / "paired_window_features.csv")
    print(f"\n   session window rows: {len(sess)}   paired window rows: {len(pair)}")

    # ------------------------------------------------------------------ 2. grid
    print("\n2. Duration grid")
    durs = sorted({r["duration"] for r in sess})
    check("duration grid is exactly k4/k8/k15/k30/full", durs == ["full", "k15", "k30", "k4", "k8"],
          str(durs))
    for d, k in ST.DURATIONS:
        rows = [r for r in sess if r["duration"] == d]
        exp_ep = "full" if k is None else k
        exp_sec = None if k is None else k * 4
        got_ep = {int(r["epochs_per_window"]) if not r["is_full_session"].lower() == "true" else None
                  for r in rows}
        check(f"{d}: epochs_per_window consistent", len(got_ep) == 1, str(got_ep))

    # ------------------------------------------------------------------ 3. disjointness
    print("\n3. Disjoint, contiguous, non-overlapping windows in recording order")
    # NB: in session_window_features.csv, `n_epochs` is the number of epochs IN THE WINDOW.
    # The session total lives in window_inventory.csv as `session_n_epochs`.
    inv = C.read_csv(OUT / "window_inventory.csv")
    session_n = {(r["subject"], r["session"]): int(r["session_n_epochs"]) for r in inv}
    bad_overlap, bad_order, bad_count = [], [], []
    for (subj, ses, d), rows in _group(sess):
        rows = sorted(rows, key=lambda r: int(r["window_index"]))
        k = int(rows[0]["epochs_per_window"])
        if d == "full":
            continue
        spans = []
        for i, r in enumerate(rows):
            s = int(r["start_epoch"])
            spans.append((s, s + k))
            if s != i * k:
                bad_order.append(f"{subj}_{ses}_{d}_w{i}")
        for a, b in zip(spans, spans[1:]):
            if a[1] > b[0]:
                bad_overlap.append(f"{subj}_{ses}_{d}")
        N = session_n[(subj, ses)]
        if len(spans) != N // k:
            bad_count.append(f"{subj}_{ses}_{d}: got {len(spans)} expected {N//k}")
    check("no overlapping windows", not bad_overlap, str(bad_overlap[:3]))
    check("windows start at 0, k, 2k, ... (recording order)", not bad_order, str(bad_order[:3]))
    check("window count == floor(session_epochs/k)", not bad_count, str(bad_count[:3]))

    # ------------------------------------------------------------------ 4. recompute
    print("\n4. Independent recomputation of window features")
    subjects = sorted({r["subject"] for r in sess})
    sample_subjects = subjects[:6]
    max_dM = max_dJ = 0.0
    n_checked = 0
    problems = []
    for subject in sample_subjects:
        for session in ("ses-1", "ses-2"):
            try:
                epochs, _ = ST.load_session_epochs(subject, session, est)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{subject} {session}: {type(exc).__name__}")
                continue
            for d, k in ST.DURATIONS:
                kk = epochs.shape[0] if k is None else k
                saved = [r for r in sess if r["subject"] == subject and r["session"] == session
                         and r["duration"] == d]
                if not saved or epochs.shape[0] // kk < 1:
                    continue
                wins = est.window_series(epochs, kk) if k is not None else [est.features(epochs)]
                for i, w in enumerate(wins):
                    row = next((r for r in saved if int(r["window_index"]) == i), None)
                    if row is None:
                        problems.append(f"{subject} {session} {d} w{i}: no saved row")
                        continue
                    for r in REGION_NAMES:
                        max_dM = max(max_dM, abs(w[f"M_{r}"] - float(row[f"M_{r}"])))
                        max_dJ = max(max_dJ, abs(w[f"J_{r}"] - float(row[f"J_{r}"])))
                    n_checked += 1
    check("no recomputation problems", not problems, str(problems[:3]))
    check(f"recomputed {n_checked} windows: max|dM| = 0", max_dM < 1e-9, f"max|dM|={max_dM:.3e}")
    check(f"recomputed {n_checked} windows: max|dJ| = 0", max_dJ < 1e-9, f"max|dJ|={max_dJ:.3e}")

    # ------------------------------------------------------------------ 5. paired deltas
    print("\n5. Paired-window deltas re-derive from the session table")
    saved_sess = {(r["subject"], r["session"], r["duration"], int(r["window_index"])): r for r in sess}
    max_dDelta = 0.0
    n_pair_checked = 0
    pair_problems = []
    for r in pair:
        key_ns = (r["subject"], "ses-1", r["duration"], int(r["paired_window_index"]))
        key_sd = (r["subject"], "ses-2", r["duration"], int(r["paired_window_index"]))
        if key_ns not in saved_sess or key_sd not in saved_sess:
            pair_problems.append(str(key_ns))
            continue
        a, b = saved_sess[key_ns], saved_sess[key_sd]
        for reg in REGION_NAMES:
            exp = float(b[f"M_{reg}"]) - float(a[f"M_{reg}"])
            max_dDelta = max(max_dDelta, abs(exp - float(r[f"delta_M_{reg}"])))
            jn, js = float(a[f"J_{reg}"]), float(b[f"J_{reg}"])
            expj = float(np.log(js / jn)) if (jn > 0 and js > 0) else float(np.log((js + 1e-12) / (jn + 1e-12)))
            max_dDelta = max(max_dDelta, abs(expj - float(r[f"delta_logJ_{reg}"])))
        n_pair_checked += 1
    check("no missing window joins", not pair_problems, str(pair_problems[:3]))
    check(f"recomputed {n_pair_checked} paired windows: deltas exact", max_dDelta < 1e-12,
          f"max diff={max_dDelta:.3e}")

    # ------------------------------------------------------------------ 6. columns
    print("\n6. Required columns in stability outputs")
    need = {
        "duration_summary.csv": ["feature", "duration", "spearman_rho", "median_abs_diff",
                                 "p90_abs_diff", "nmae", "icc_2_1", "seconds_per_window"],
        "disjoint_agreement.csv": ["feature", "duration", "spearman_rho", "median_abs_diff", "nmae"],
        "position_drift.csv": ["feature", "duration", "comparison", "mean_difference", "wilcoxon_p"],
        "accumulation_convergence.csv": ["feature", "duration", "spearman_rho", "median_abs_diff"],
        "delta_sign_stability.csv": ["feature", "duration", "sign_agreement", "reference_source"],
        "finite_sample_J_simulation.csv": ["model", "region", "k", "relative_sd", "bias"],
    }
    for fname, cols in need.items():
        rows = C.read_csv(OUT / fname)
        head = set(rows[0].keys()) if rows else set()
        miss = [c for c in cols if c not in head]
        check(f"{fname} has required columns", not miss, f"missing={miss}")

    # ------------------------------------------------------------------ 7. target isolation
    print("\n7. PVT target isolation")
    pvt_cols = ("Y_log", "median_rt", "y_log", "pvt", "target")
    leaked = {}
    for fname in ("session_window_features.csv", "paired_window_features.csv",
                  "duration_summary.csv", "disjoint_agreement.csv", "position_drift.csv",
                  "accumulation_convergence.csv", "delta_sign_stability.csv",
                  "finite_sample_J_simulation.csv", "baseline_scenario.csv"):
        p = OUT / fname
        if not p.exists():
            continue
        head = C.read_csv(p)[0].keys() if C.read_csv(p) else []
        hit = [c for c in head if any(t in c.lower() for t in pvt_cols)]
        if hit:
            leaked[fname] = hit
    check("no PVT target column in any stability table used for duration choice",
          not leaked, str(leaked))

    # ------------------------------------------------------------------ 8. sign stability labels
    print("\n8. Agreement-source labelling")
    ss = C.read_csv(OUT / "delta_sign_stability.csv")
    check("every sign-stability row states its reference source",
          all(r.get("reference_source") for r in ss),
          str(sorted({r.get("reference_source") for r in ss})))
    acc = C.read_csv(OUT / "accumulation_convergence.csv")
    check("accumulation rows are labelled as contained",
          all("contained" in str(r.get("source", "")) for r in acc),
          str(sorted({r.get("source") for r in acc})))
    ds = C.read_csv(OUT / "disjoint_agreement.csv")
    check("disjoint rows are labelled disjoint",
          all(r.get("source") == "disjoint" for r in ds) if "source" in (ds[0] if ds else {}) else True,
          "")

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print("=" * 78)
    print(f"{len(CHECKS)-n_fail}/{len(CHECKS)} Phase 1.5 verification checks passed")
    if n_fail:
        for n, ok, d in CHECKS:
            if not ok:
                print("  -", n, d)
    C.write_json(C.OUTPUTS / "qc" / "verification_phase15.json", {
        "status": "passed" if n_fail == 0 else "failed",
        "n_checks": len(CHECKS), "n_failed": n_fail,
        "recomputed_windows": n_checked, "recomputed_paired_windows": n_pair_checked,
        "checks": [{"name": n, "passed": ok, "detail": d} for n, ok, d in CHECKS],
    })
    return 1 if n_fail else 0


def _group(rows):
    out: dict = {}
    for r in rows:
        out.setdefault((r["subject"], r["session"], r["duration"]), []).append(r)
    return out.items()


if __name__ == "__main__":
    raise SystemExit(main())
