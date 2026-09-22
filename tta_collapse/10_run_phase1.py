"""Phase 1 orchestrator.

Builds the frozen target-stream manifest, then runs the three arms
(SOURCE / BN_ONLY / TENT) under the frozen episodic-per-subject protocol, and finally
computes subject-level metrics, collapse statistics and the verdict.

Resumable: each (variant, arm, seed, subject) unit is written to its own JSON under
`outputs/units/` and skipped if present, so an interrupted run costs at most one unit.

  python 10_run_phase1.py --manifest-only
  python 10_run_phase1.py --variants NS_then_SD --arms source bn_only tent --seeds 0
  python 10_run_phase1.py --variants NS_then_SD SD_then_NS --arms source bn_only tent --seeds 0 1 2

EXECUTION CONSTRAINT: this performs neural-network adaptation and must run on the
owner-approved remote server.  See `SERVER_REQUEST.md`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
import p1_arms as A        # noqa: E402
import p1_collapse as K    # noqa: E402
import p1_common as P      # noqa: E402

UNITS = HERE / "outputs" / "units"
OUT = HERE / "outputs"


# ------------------------------------------------------------------ manifest
def build_manifest_tables(manifest, orders=(A.PRIMARY_VARIANT,)):
    """One row per ordered window.  The PRIMARY stream is `metadata_order` - each subject's
    authoritative `SessionOrder` visit pair.  PARKED order diagnostics may be requested
    explicitly but are never part of the formal experiment."""
    rows = []
    for order in orders:
        for subject in sorted({r["subject"] for r in manifest}):
            if order == A.PRIMARY_VARIANT:
                stream, order_name = A.build_stream(manifest, subject)
                pair = A.visit_pair(subject)
            else:
                stream, order_name = A.build_stream(manifest, subject, order)
                pair = P.SESSION_ORDER_LEVELS[order]
            pos = 0
            for bi, batch in enumerate(stream):
                for off, r in enumerate(batch["rows"]):
                    rows.append({
                        "session_block_order": order_name,
                        "visit_pair": "->".join(pair),
                        "subject": subject,
                        "session": batch["session"],
                        "visit_index": batch["block"],
                        "label": int(r["label"]),
                        "segment_id": r["segment_id"],
                        "source_epoch_index": int(r["source_epoch_index"]),
                        "block_span": batch["block_span"],
                        "stream_position": pos,
                        "within_block_position": int(r["source_epoch_index"]),
                        "batch_index": bi,
                        "batch_n": len(batch["rows"]),
                        "is_final_batch_of_block": batch["is_final_batch_of_block"],
                        "batch_offset": off,
                        "waveform_file": r["waveform_file"],
                        "array_index": int(r["array_index"]),
                    })
                    pos += 1
    return rows


def batch_size_audit(manifest, session_order=None):
    """Actual batch sizes per subject/visit, including the trailing incomplete batch."""
    out = []
    for subject in sorted({r["subject"] for r in manifest}):
        stream, _ = A.build_stream(manifest, subject)
        profile = A.batch_size_profile(stream)
        pair = A.visit_pair(subject)
        max_batches = max(len(v) for v in profile.values())
        for i in range(max_batches):
            row = {"subject": subject, "visit_pair": "->".join(pair),
                   "batch_position_in_visit": i}
            for session, sizes in profile.items():
                row[f"{session}_n_windows"] = sum(sizes)
                row[f"{session}_n_batches"] = len(sizes)
                row[f"{session}_batch_size_at_{i}"] = sizes[i] if i < len(sizes) else None
            out.append(row)
    return out


def subject_inventory(manifest, splits):
    fold_by_test = {f["test"][0]: f for f in splits["folds"]}
    session_order = P.load_session_order()
    out = []
    for subject in sorted({r["subject"] for r in manifest}):
        rows = [r for r in manifest if r["subject"] == subject]
        ses1 = [r for r in rows if r["session"] == "ses-1"]
        ses2 = [r for r in rows if r["session"] == "ses-2"]
        fold = fold_by_test[subject]
        gaps = A.block_epoch_gaps(manifest, subject)
        stream, _ = A.build_stream(manifest, subject)
        profile = A.batch_size_profile(stream)
        pair = A.visit_pair(subject, session_order)
        out.append({
            "subject": subject,
            "SessionOrder": session_order.get(subject),
            "visit_pair": "->".join(pair),
            "first_visit_session": pair[0],
            "first_visit_label": 0 if pair[0] == "ses-1" else 1,
            "n_windows_total": len(rows),
            "n_windows_ses1_NS": len(ses1),
            "n_windows_ses2_SD": len(ses2),
            "n_windows_label0": sum(1 for r in rows if r["label"] == "0"),
            "n_windows_label1": sum(1 for r in rows if r["label"] == "1"),
            "class_share_label1": len(ses2) / len(rows),
            "n_batches": len(stream),
            "batch_sizes_first_visit": ";".join(str(x) for x in profile[pair[0]]),
            "batch_sizes_second_visit": ";".join(str(x) for x in profile[pair[1]]),
            "final_batch_size_first_visit": profile[pair[0]][-1],
            "final_batch_size_second_visit": profile[pair[1]][-1],
            "longest_same_condition_run": _longest_run(rows, pair),
            "fold_id": fold["fold_id"],
            "fold_n_train_subjects": len(fold["train"]),
            "fold_n_validation_subjects": len(fold["validation"]),
            "fold_n_test_subjects": len(fold["test"]),
            "n_runs": _n_runs(rows, pair),
            "ses1_missing_epochs_interior": len(gaps.get("ses-1", {}).get("missing_interior", [])),
            "ses2_missing_epochs_interior": len(gaps.get("ses-2", {}).get("missing_interior", [])),
            "ses1_missing_epochs_tail": gaps.get("ses-1", {}).get("missing_tail", 0),
            "ses2_missing_epochs_tail": gaps.get("ses-2", {}).get("missing_tail", 0),
            "session_source_files": ";".join(sorted({r["source_file"] for r in rows})),
        })
    # subjects present in subjects.csv but absent from the manifest (excluded upstream)
    for r in P.read_csv(P.ACTIVE_DATA / "subjects.csv"):
        if r["subject"] not in {o["subject"] for o in out}:
            out.append({
                "subject": r["subject"], "n_windows_total": 0,
                "n_windows_ses1_NS": 0, "n_windows_ses2_SD": 0,
                "n_windows_label0": 0, "n_windows_label1": 0,
                "class_share_label1": None,
                "fold_id": "NOT_A_FOLD_subject_excluded_upstream",
                "fold_n_train_subjects": None, "fold_n_validation_subjects": None,
                "fold_n_test_subjects": None,
                "n_runs_NS_then_SD": None,
                "longest_same_condition_run_if_NS_then_SD": None,
                "session_source_files": "",
                "exclusion_reason": r["reason"],
            })
    return sorted(out, key=lambda r: r["subject"])


def _n_runs(rows, pair):
    labels = []
    for session in pair:
        labels += [r["label"] for r in sorted([r for r in rows if r["session"] == session],
                                              key=lambda r: int(r["source_epoch_index"]))]
    return sum(1 for i, v in enumerate(labels) if i == 0 or labels[i - 1] != v)


def _longest_run(rows, pair):
    """Longest same-condition run, measured ONLY inside a visit (never across the visit
    boundary, which is a designed block splice rather than a real contiguous stretch)."""
    best = 0
    for session in pair:
        labels = [r["label"] for r in sorted([r for r in rows if r["session"] == session],
                                             key=lambda r: int(r["source_epoch_index"]))]
        cur = 0
        for i, v in enumerate(labels):
            cur = cur + 1 if (i and labels[i - 1] == v) else 1
            best = max(best, cur)
    return best


def checkpoint_inventory(splits):
    rows = []
    for subject in sorted(f["test"][0] for f in splits["folds"]):
        for seed in (0, 1, 2):
            d = P.FORMAL_RESULTS / "eegnet" / subject / f"seed_{seed}"
            entry = {"model": "eegnet", "test_subject": subject, "seed": seed,
                     "dir": str(d.relative_to(P.BASE)).replace("\\", "/")}
            for name in ("best.pt", "normalization.npz", "result.json", "predictions.csv",
                         "history.csv", "model_architecture.txt", "split.json"):
                f = d / name
                entry[f"has_{name.replace('.', '_')}"] = f.exists()
                entry[f"sha256_{name.replace('.', '_')}"] = P.sha256(f) if f.exists() else None
            if (d / "result.json").exists():
                res = json.loads((d / "result.json").read_text(encoding="utf-8"))
                entry["legacy_best_epoch"] = res["details"]["best_epoch"]
                entry["legacy_epochs_run"] = res["details"]["epochs_run"]
                entry["legacy_val_subject_macro_ba"] = res["details"]["best_validation_subject_macro_ba"]
                entry["legacy_test_balanced_accuracy"] = res["test_metrics"]["balanced_accuracy"]
                entry["legacy_test_n_segments"] = res["test_metrics"]["n_segments"]
            rows.append(entry)
    return rows


# ------------------------------------------------------------------ unit runner
def unit_path(variant, arm, seed, subject):
    return UNITS / f"{variant}__{arm}__seed{seed}__{subject}.json"


def run_unit(variant, arm, seed, subject, cfg, manifest, device):
    """Run one unit, or skip it if a COMPLETE unit file already exists.

    Resumability contract:
      * a unit is complete only if its file parses as JSON and carries the fields the
        verifier needs - a truncated or corrupt file is recomputed, never trusted;
      * writes are atomic (temp file + replace), so an interruption cannot leave a unit that
        looks complete but is not.
    """
    path = unit_path(variant, arm, seed, subject)
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            required = ("arm", "subject", "seed", "window_rows", "batch_rows", "scores",
                        "session_block_order", "source_meta")
            if all(k in cached for k in required):
                return cached, True
            print(f"  RECOMPUTING corrupt/incomplete unit (missing fields): {path.name}")
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            print(f"  RECOMPUTING unreadable unit ({type(e).__name__}): {path.name}")
    t0 = time.perf_counter()
    res = A.run_arm(arm, subject, seed, cfg, manifest, variant, device=device)
    res["wall_seconds"] = time.perf_counter() - t0
    res["device"] = str(device)
    path.parent.mkdir(parents=True, exist_ok=True)
    # atomic write: a torn unit file must never be mistaken for a completed unit
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(A.sanitize_for_json(res), allow_nan=False), encoding="utf-8")
    tmp.replace(path)
    return res, False


def load_all_units(variants, arms, seeds):
    out = {}
    for variant in variants:
        for arm in arms:
            for seed in seeds:
                for p in sorted(UNITS.glob(f"{variant}__{arm}__seed{seed}__*.json")):
                    r = json.loads(p.read_text(encoding="utf-8"))
                    out[(variant, arm, seed, r["subject"])] = r
    return out


# ------------------------------------------------------------------ user-facing report
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--variants", nargs="+", default=[A.PRIMARY_VARIANT],
                    help="PRIMARY is metadata_order. PARKED diagnostics "
                         "(NS_then_SD / SD_then_NS) are refused by the primary protocol.")
    ap.add_argument("--arms", nargs="+", default=list(A.ARMS), choices=list(A.ARMS))
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--subjects", nargs="+", default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--report", action="store_true", help="recompute metrics/verdict from stored units")
    args = ap.parse_args()

    parked = [v for v in args.variants if v in A.PARKED_VARIANTS]
    if parked:
        raise SystemExit(
            f"REFUSED: {parked} are PARKED order diagnostics and are not part of the primary "
            f"collapse-existence experiment. PRIMARY_VARIANT is {A.PRIMARY_VARIANT!r}.")

    cfg = json.loads((P.LEGACY / "configs" / "baselines.json").read_text(encoding="utf-8"))
    manifest = P.load_manifest()
    splits = P.load_splits()

    if not (OUT / "target_stream_manifest.csv").exists() or args.manifest_only:
        rows = build_manifest_tables(manifest, tuple(args.variants))
        P.write_csv(OUT / "target_stream_manifest.csv", rows)
        P.write_csv(OUT / "batch_size_audit.csv", batch_size_audit(manifest))
        P.write_csv(OUT / "legacy_subject_inventory.csv", subject_inventory(manifest, splits))
        P.write_csv(OUT / "legacy_checkpoint_inventory.csv", checkpoint_inventory(splits))
        print(f"manifest rows: {len(rows)}  subjects: {len({r['subject'] for r in rows})}")
    if args.manifest_only:
        return 0

    import torch

    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu"
                          else "cpu")
    if args.device == "cuda" and not torch.cuda.is_available():
        print("WARNING: cuda requested but unavailable -> falling back to CPU")
    subjects = args.subjects or sorted({f["test"][0] for f in splits["folds"]})

    n_done = n_skip = 0
    for variant in args.variants:
        for seed in args.seeds:
            for subject in subjects:
                for arm in args.arms:
                    res, skipped = run_unit(variant, arm, seed, subject, cfg, manifest, device)
                    n_skip += skipped
                    n_done += (not skipped)
                    if not skipped:
                        print(f"  {variant} seed{seed} {subject} {arm}: "
                              f"{res['n_windows']} windows, {res['n_batches']} batches, "
                              f"{res['wall_seconds']:.1f}s", flush=True)
    print(f"units run now: {n_done}   already present: {n_skip}")

    if args.report:
        import subprocess

        subprocess.run([sys.executable, str(HERE / "30_analyze_collapse.py"),
                        "--variants", *args.variants, "--seeds", *[str(s) for s in args.seeds]],
                       check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
