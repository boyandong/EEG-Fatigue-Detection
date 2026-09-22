"""10 - Phase 1.5 window feature extraction.

    python project/vigilance_generalization_v1/scripts/10_extract_windows.py

Computes mechanism_v1 features for every disjoint contiguous window at each duration, for
every admissible session of every paired subject (n = 68 subjects / 136 sessions — the full
EEG cohort, NOT the 29-subject PVT subset).

Every window value comes from a fresh full pass through the frozen chain:
    window epochs -> band powers -> S -> ROI median -> window M, J
Nothing is derived from a full-session value.

Outputs
  outputs/stability_v1/session_window_features.csv
  outputs/stability_v1/paired_window_features.csv
  outputs/stability_v1/window_inventory.csv
  outputs/qc/run_manifest_10_windows.json
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import stability as ST  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

EPS_J = 1e-12


def main() -> None:
    t0 = time.perf_counter()
    ds = C.dataset_config()
    est = ST.Estimator.build(ds)
    out_dir = C.OUTPUTS / "stability_v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    subjects = ST.cohort_subjects()
    pairs = ST.session_pairs()
    print(f"paired subjects: {len(subjects)}   sessions: {len(pairs)}")
    print(f"durations: {[(n, ST.seconds(k)) for n, k in ST.DURATIONS]}")

    session_rows: list[dict] = []
    inventory: list[dict] = []
    errors: list[dict] = []
    # (subject, duration) -> {"NS": {window_index: feats}, "SD": {...}}
    per_subject: dict[tuple[str, str], dict[str, dict[int, dict]]] = {}

    done = 0
    for subject, condition, session_id in pairs:
        try:
            epochs, prov = ST.load_session_epochs(subject, session_id, est)
        except Exception as exc:  # noqa: BLE001
            errors.append({"subject": subject, "session": session_id, "stage": "load",
                           "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc()[-500:]})
            continue

        N = int(epochs.shape[0])
        for dur_name, k in ST.DURATIONS:
            kk = N if k is None else k
            n_win = N // kk
            # record eligibility even when zero windows are possible
            inventory.append({
                "subject": subject, "session": session_id, "condition": condition,
                "duration": dur_name, "epochs_per_window": kk,
                "seconds_per_window": ST.seconds(kk),
                "session_n_epochs": N,
                "n_disjoint_windows": n_win,
                "eligible_for_agreement": bool(n_win >= 2),
                "exploratory": dur_name in ST.EXPLORATORY,
            })
            if n_win < 1:
                continue
            try:
                wins = est.window_series(epochs, kk)
            except Exception as exc:  # noqa: BLE001
                errors.append({"subject": subject, "session": session_id, "stage": f"windows:{dur_name}",
                               "error": f"{type(exc).__name__}: {exc}",
                               "traceback": traceback.format_exc()[-500:]})
                continue
            bucket = per_subject.setdefault((subject, dur_name), {}).setdefault(condition, {})
            for w in wins:
                row = {
                    "subject": subject, "session": session_id, "condition": condition,
                    "duration": dur_name,
                    "epochs_per_window": kk, "seconds_per_window": ST.seconds(kk),
                    "window_index": w["window_index"], "start_epoch": w["start_epoch"],
                    "n_epochs": w["n_epochs"],
                    "is_full_session": bool(k is None),
                    **{f: w[f] for f in ST.SESSION_FEATURES},
                    "set_sha256": prov["set_sha256"],
                    "eye_state_verdict": prov["eye_state_verdict"],
                }
                session_rows.append(row)
                bucket[w["window_index"]] = {**{f: w[f] for f in ST.SESSION_FEATURES},
                                             "n_epochs": w["n_epochs"]}
        done += 1
        if done % 20 == 0:
            print(f"  processed {done}/{len(pairs)} sessions", flush=True)

    # ---------------------------------------------------------------- paired windows
    paired_rows: list[dict] = []
    pair_inventory: list[dict] = []
    for subject in subjects:
        for dur_name, k in ST.DURATIONS:
            ns = per_subject.get((subject, dur_name), {}).get("NS", {})
            sd = per_subject.get((subject, dur_name), {}).get("SD", {})
            n_shared = min(len(ns), len(sd))
            pair_inventory.append({"subject": subject, "duration": dur_name,
                                   "n_windows_NS": len(ns), "n_windows_SD": len(sd),
                                   "n_paired_windows": n_shared,
                                   "eligible_for_delta_agreement": bool(n_shared >= 2)})
            for i in range(n_shared):
                a, b = ns[i], sd[i]
                row = {"subject": subject, "duration": dur_name,
                       "epochs_per_window": (a["n_epochs"]),
                       "seconds_per_window": a["n_epochs"] * 4,
                       "paired_window_index": i,
                       "n_epochs_NS": a["n_epochs"], "n_epochs_SD": b["n_epochs"]}
                for r in REGION_NAMES:
                    row[f"delta_M_{r}"] = b[f"M_{r}"] - a[f"M_{r}"]
                    jn, js = a[f"J_{r}"], b[f"J_{r}"]
                    row[f"delta_logJ_{r}"] = (float(np.log((js + EPS_J) / (jn + EPS_J)))
                                              if (jn <= 0 or js <= 0) else float(np.log(js / jn)))
                    row[f"J_NS_{r}"] = jn
                    row[f"J_SD_{r}"] = js
                paired_rows.append(row)

    C.write_csv(out_dir / "session_window_features.csv", session_rows)
    C.write_csv(out_dir / "paired_window_features.csv", paired_rows)
    C.write_csv(out_dir / "window_inventory.csv", inventory)
    C.write_csv(out_dir / "paired_window_inventory.csv", pair_inventory)
    C.write_csv(C.OUTPUTS / "qc" / "exclusions_stability.csv", errors)

    # ---------------------------------------------------------------- accounting
    import collections
    acc = {}
    for dur_name, k in ST.DURATIONS:
        rows = [r for r in inventory if r["duration"] == dur_name]
        elig = [r for r in rows if r["eligible_for_agreement"]]
        acc[dur_name] = {
            "epochs_per_window": (None if k is None else k),
            "seconds_per_window": (None if k is None else k * 4),
            "n_sessions": len(rows),
            "n_sessions_with_2plus_disjoint_windows": len(elig),
            "n_sessions_ineligible": len(rows) - len(elig),
            "ineligible_sessions": [f"{r['subject']}_{r['session']}" for r in rows
                                    if not r["eligible_for_agreement"]],
            "total_windows": sum(r["n_disjoint_windows"] for r in rows),
            "median_windows_per_session": float(np.median([r["n_disjoint_windows"] for r in rows])) if rows else None,
        }
    pair_acc = {}
    for dur_name, k in ST.DURATIONS:
        rows = [r for r in pair_inventory if r["duration"] == dur_name]
        pair_acc[dur_name] = {
            "n_subjects": len(rows),
            "n_subjects_with_2plus_paired_windows": sum(1 for r in rows if r["eligible_for_delta_agreement"]),
            "n_paired_windows_total": sum(r["n_paired_windows"] for r in rows),
            "median_paired_windows_per_subject": float(np.median([r["n_paired_windows"] for r in rows])) if rows else None,
        }

    C.write_json(out_dir / "sample_accounting.json",
                 {"session_level": acc, "paired_level": pair_acc,
                  "n_paired_subjects": len(subjects), "n_sessions": len(pairs)})
    C.write_json(C.OUTPUTS / "qc" / "run_manifest_10_windows.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml", C.CONFIG / "mechanism_v1.yaml"],
        {"n_subjects": len(subjects), "n_sessions": len(pairs),
         "n_session_window_rows": len(session_rows),
         "n_paired_window_rows": len(paired_rows),
         "n_errors": len(errors), "sample_accounting": acc,
         "elapsed_seconds": time.perf_counter() - t0}))

    print()
    print("=" * 78)
    print("WINDOW EXTRACTION")
    print("=" * 78)
    for dur_name, k in ST.DURATIONS:
        a = acc[dur_name]
        s = "full" if a["seconds_per_window"] is None else f"{a['seconds_per_window']}s"
        print(f"  {dur_name:<5} ({s:>5}) sessions={a['n_sessions']:3d} "
              f"eligible(2+ disjoint)={a['n_sessions_with_2plus_disjoint_windows']:3d} "
              f"windows={a['total_windows']:5d} median/session={a['median_windows_per_session']}")
    print()
    for dur_name, k in ST.DURATIONS:
        p = pair_acc[dur_name]
        print(f"  paired {dur_name:<5} subjects={p['n_subjects']:3d} "
              f"eligible(2+ paired)={p['n_subjects_with_2plus_paired_windows']:3d} "
              f"paired windows={p['n_paired_windows_total']:5d}")
    print(f"\n  errors: {len(errors)}")
    print(f"  elapsed {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/stability_v1/session_window_features.csv (+ paired, inventory)")


if __name__ == "__main__":
    main()
