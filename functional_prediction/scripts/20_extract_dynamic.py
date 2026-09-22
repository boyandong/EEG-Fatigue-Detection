"""20 - Phase 1.75 dynamic-observable extraction.

    python project/vigilance_generalization_v1/scripts/20_extract_dynamic.py

Extracts M, J, V, J_res and the drift diagnostic D for every admissible session of every paired
subject (68 subjects / 136 sessions), at:

  * the Phase 1.5 duration grid (k4 / k8 / k15 / k30 / full), with burn-in B = 0, so the two
    phases are directly comparable; and
  * the Phase 1.75 Protocol(B, T) grid, B in {0, 32, 60} s and T in {32, 60, 120} s.

mechanism_v1 is untouched: nothing here overwrites outputs/mechanism_v1 or outputs/stability_v1.
This writes into outputs/dynamic_audit/.

NO PVT VALUE IS READ. NO PVT COLUMN IS WRITTEN.

Outputs
  outputs/dynamic_audit/J_V_Jres_session.csv
  outputs/dynamic_audit/J_V_Jres_paired.csv
  outputs/dynamic_audit/burnin_duration_grid.csv
  outputs/dynamic_audit/duration_grid_reference.csv
  outputs/dynamic_audit/protocol_inventory.csv
  outputs/qc/run_manifest_20_dynamic.json
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

DURATIONS = ST.DURATIONS                      # k4 / k8 / k15 / k30 / full  (these ARE B = 0)
# Burn-in is only extracted for B > 0: the B = 0 case is exactly the duration grid above, and
# duplicating it under a second label would create two names for one row set.
BURNIN_SECONDS = (32, 60)
MEASURE_SECONDS = (32, 60, 120)
MIN_WINDOWS = 2
EPS_J = 1e-12
OBS = ("M", "J", "V", "Jres", "D")
SESSION_COLS = [f"{o}_{r}" for o in OBS for r in REGION_NAMES]


def windows_after_burnin(est: ST.Estimator, epochs: np.ndarray, burnin_epochs: int, k: int) -> list[dict]:
    """Disjoint contiguous k-epoch windows starting AFTER the burn-in. No overlap, ever."""
    tail = epochs[burnin_epochs:]
    n_win = tail.shape[0] // k
    return [{**est.dynamic_features(tail[i * k:(i + 1) * k]),
             "window_index": i, "start_epoch": burnin_epochs + i * k,
             "n_epochs": int(tail[i * k:(i + 1) * k].shape[0])}
            for i in range(n_win)]


def main() -> None:
    t0 = time.perf_counter()
    est = ST.Estimator.build()
    out_dir = C.OUTPUTS / "dynamic_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    subjects = ST.cohort_subjects()
    pairs = ST.session_pairs()
    print(f"paired subjects: {len(subjects)}   sessions: {len(pairs)}")
    print(f"duration grid   : {[n for n, _ in DURATIONS]}")
    print(f"protocol grid   : B in {BURNIN_SECONDS}s, T in {MEASURE_SECONDS}s")

    sess_rows: list[dict] = []
    inv_rows: list[dict] = []
    errors: list[dict] = []
    # collected[(subject, condition, label)] = {window_index: feature dict}
    collected: dict[tuple[str, str, str], dict[int, dict]] = {}
    # label -> (grid, B, T or None, seconds)
    labels: dict[str, tuple[str, int, int | None, int]] = {}
    for dur_name, k in DURATIONS:
        labels[dur_name] = ("duration", 0, None, ST.seconds(k))
    for B in BURNIN_SECONDS:
        for T in MEASURE_SECONDS:
            labels[f"B{B}_T{T}"] = ("protocol", B, T, T)

    done = 0
    for subject, condition, session_id in pairs:
        try:
            epochs, prov = ST.load_session_epochs(subject, session_id, est)
        except Exception as exc:  # noqa: BLE001
            errors.append({"subject": subject, "session": session_id, "stage": "load",
                           "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc()[-400:]})
            continue
        N = int(epochs.shape[0])

        # ---- Phase 1.5 duration grid, B = 0
        for dur_name, k in DURATIONS:
            kk = N if k is None else k
            wins = windows_after_burnin(est, epochs, 0, kk)
            inv_rows.append({"grid": "duration", "subject": subject, "session": session_id,
                             "condition": condition, "label": dur_name, "burnin_seconds": 0,
                             "measure_seconds": ST.seconds(kk), "session_n_epochs": N,
                             "n_windows": len(wins), "eligible": len(wins) >= MIN_WINDOWS})
            collected[(subject, condition, dur_name)] = {w["window_index"]: w for w in wins}
            for w in wins:
                sess_rows.append({
                    "grid": "duration", "protocol_B": 0, "protocol_T": ST.seconds(kk),
                    "subject": subject, "session": session_id, "condition": condition,
                    "label": dur_name, "epochs_per_window": kk,
                    "seconds_per_window": ST.seconds(kk),
                    "window_index": w["window_index"], "start_epoch": w["start_epoch"],
                    "n_epochs": w["n_epochs"], "is_full_session": bool(k is None),
                    **{c: w[c] for c in SESSION_COLS},
                    "set_sha256": prov["set_sha256"],
                    "eye_state_verdict": prov["eye_state_verdict"]})

        # ---- Phase 1.75 protocol grid
        for B in BURNIN_SECONDS:
            be = B // 4
            for T in MEASURE_SECONDS:
                label = f"B{B}_T{T}"
                if be >= N:
                    inv_rows.append({"grid": "protocol", "subject": subject, "session": session_id,
                                     "condition": condition, "label": label, "burnin_seconds": B,
                                     "measure_seconds": T, "session_n_epochs": N, "n_windows": 0,
                                     "eligible": False, "note": "burn-in exceeds available epochs"})
                    collected[(subject, condition, label)] = {}
                    continue
                wins = windows_after_burnin(est, epochs, be, T // 4)
                inv_rows.append({"grid": "protocol", "subject": subject, "session": session_id,
                                 "condition": condition, "label": label, "burnin_seconds": B,
                                 "measure_seconds": T, "session_n_epochs": N,
                                 "usable_epochs_after_burnin": N - be, "n_windows": len(wins),
                                 "eligible": len(wins) >= MIN_WINDOWS})
                collected[(subject, condition, label)] = {w["window_index"]: w for w in wins}
                for w in wins:
                    sess_rows.append({
                        "grid": "protocol", "protocol_B": B, "protocol_T": T,
                        "subject": subject, "session": session_id, "condition": condition,
                        "label": label, "epochs_per_window": T // 4,
                        "seconds_per_window": T,
                        "window_index": w["window_index"], "start_epoch": w["start_epoch"],
                        "n_epochs": w["n_epochs"], "is_full_session": False,
                        **{c: w[c] for c in SESSION_COLS},
                        "set_sha256": prov["set_sha256"],
                        "eye_state_verdict": prov["eye_state_verdict"]})
        done += 1
        if done % 20 == 0:
            print(f"  processed {done}/{len(pairs)} sessions", flush=True)

    # ---------------------------------------------------------------- paired rows
    paired_rows: list[dict] = []
    for subject in subjects:
        for label, (grid, B, T, secs) in labels.items():
            ns = collected.get((subject, "NS", label), {})
            sd = collected.get((subject, "SD", label), {})
            n_shared = min(len(ns), len(sd))
            for i in range(n_shared):
                a, b = ns[i], sd[i]
                row = {"subject": subject, "grid": grid, "label": label,
                       "protocol_B": B, "protocol_T": T, "seconds_per_window": secs,
                       "paired_window_index": i,
                       "n_epochs_NS": a["n_epochs"], "n_epochs_SD": b["n_epochs"]}
                for r in REGION_NAMES:
                    row[f"delta_M_{r}"] = b[f"M_{r}"] - a[f"M_{r}"]
                    for fam in ("J", "V", "Jres"):
                        x, y = a[f"{fam}_{r}"], b[f"{fam}_{r}"]
                        row[f"delta_log{fam}_{r}"] = (float(np.log(y / x)) if (x > 0 and y > 0)
                                                      else float(np.log((y + EPS_J) / (x + EPS_J))))
                    row[f"delta_D_{r}"] = b[f"D_{r}"] - a[f"D_{r}"]
                paired_rows.append(row)

    # ---------------------------------------------------------------- grid summary
    # B = 0 rows are contributed by the duration grid; add them here so the protocol table is
    # complete without duplicating any window.
    dur_to_proto = {"k8": (0, 32), "k15": (0, 60), "k30": (0, 120)}
    grid_rows: list[dict] = []
    for dur_name, (B, T) in dur_to_proto.items():
        n_elig_session = sum(1 for r in inv_rows
                             if r["grid"] == "duration" and r["label"] == dur_name and r.get("eligible"))
        elig = 0
        n_pw = 0
        for s in subjects:
            ns = collected.get((s, "NS", dur_name), {})
            sd = collected.get((s, "SD", dur_name), {})
            if len(ns) >= MIN_WINDOWS and len(sd) >= MIN_WINDOWS:
                elig += 1
            n_pw += min(len(ns), len(sd))
        grid_rows.append({
            "grid": "protocol", "label": f"B{B}_T{T}", "protocol_B": B, "protocol_T": T,
            "seconds_per_window": T, "burnin_seconds": B, "measure_seconds": T,
            "n_sessions_with_windows": 2 * sum(1 for r in inv_rows
                                               if r["grid"] == "duration" and r["label"] == dur_name
                                               and r["n_windows"] > 0),
            "n_sessions_with_2plus_disjoint_windows": n_elig_session,
            "n_subjects_with_2plus_paired_windows": elig,
            "n_paired_windows_total": n_pw,
            "feasible_for_agreement": elig > 0,
            "source_grid": f"duration:{dur_name}",
        })
    for label, (grid, B, T, secs) in labels.items():
        if grid != "protocol" or B == 0:
            continue
        n_elig_session = sum(1 for r in inv_rows if r["label"] == label and r.get("eligible"))
        elig = 0
        n_pw = 0
        n_with = 0
        for s in subjects:
            ns = collected.get((s, "NS", label), {})
            sd = collected.get((s, "SD", label), {})
            if len(ns) >= MIN_WINDOWS and len(sd) >= MIN_WINDOWS:
                elig += 1
            n_pw += min(len(ns), len(sd))
        for cond in ("NS", "SD"):
            n_with += sum(1 for s in subjects if collected.get((s, cond, label), {}))
        grid_rows.append({
            "grid": grid, "label": label, "protocol_B": B, "protocol_T": T,
            "seconds_per_window": secs, "burnin_seconds": B, "measure_seconds": secs,
            "n_sessions_with_windows": n_with,
            "n_sessions_with_2plus_disjoint_windows": n_elig_session,
            "n_subjects_with_2plus_paired_windows": elig,
            "n_paired_windows_total": n_pw,
            "feasible_for_agreement": elig > 0,
            "source_grid": "protocol",
        })

    C.write_csv(out_dir / "J_V_Jres_session.csv", sess_rows)
    C.write_csv(out_dir / "J_V_Jres_paired.csv", paired_rows)
    C.write_csv(out_dir / "burnin_duration_grid.csv", [g for g in grid_rows if g["grid"] == "protocol"])
    C.write_csv(out_dir / "duration_grid_reference.csv", [g for g in grid_rows if g["grid"] == "duration"])
    C.write_csv(out_dir / "protocol_inventory.csv", inv_rows)
    C.write_csv(C.OUTPUTS / "qc" / "exclusions_dynamic.csv", errors)

    C.write_json(C.OUTPUTS / "qc" / "run_manifest_20_dynamic.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml", C.CONFIG / "mechanism_v1.yaml"],
        {"n_subjects": len(subjects), "n_sessions": len(pairs),
         "n_session_rows": len(sess_rows), "n_paired_rows": len(paired_rows),
         "n_errors": len(errors), "burnin_seconds": list(BURNIN_SECONDS),
         "measure_seconds": list(MEASURE_SECONDS), "observables": list(OBS),
         "note": "no PVT value was read; no PVT column is written",
         "elapsed_seconds": time.perf_counter() - t0}))

    print()
    print("=" * 78)
    print("DYNAMIC EXTRACTION")
    print("=" * 78)
    print(f"  session rows : {len(sess_rows)}   paired rows: {len(paired_rows)}   errors: {len(errors)}")
    print()
    print("  Protocol(B,T) grid")
    print("  %-10s %6s %6s %10s %12s %12s" % ("label", "B(s)", "T(s)", "sess>=2win", "subj>=2pair", "paired win"))
    for g in grid_rows:
        if g["grid"] != "protocol":
            continue
        print("  %-10s %6d %6s %10d %12d %12d" % (
            g["label"], g["protocol_B"], g["protocol_T"],
            g["n_sessions_with_2plus_disjoint_windows"],
            g["n_subjects_with_2plus_paired_windows"], g["n_paired_windows_total"]))
    print(f"\n  elapsed {time.perf_counter()-t0:.1f}s")
    print("wrote outputs/dynamic_audit/")


if __name__ == "__main__":
    main()
