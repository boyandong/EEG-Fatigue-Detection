"""Phase 1 gate 1 — SOURCE closure.

Re-runs the frozen legacy EEGNet checkpoints on the exact legacy held-out windows and
compares, element by element, against the legacy `predictions.csv` written by the
original formal run on the AutoDL RTX 4090.

This is inference only: no optimizer, no gradient, model.eval(), torch.inference_mode().
It is the gate that licenses any TENT experiment (prompt §6, §29).

Usage:
  python 01_source_closure.py --seeds 0            # fast, one seed
  python 01_source_closure.py --seeds 0 1 2        # full closure
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import p1_common as P  # noqa: E402


def legacy_test_rows(manifest, fold):
    """Reproduce run_baselines.Corpus.split_rows(fold, cap=None) for key='test'.

    Legacy logic: iterate the manifest in file order, keep rows whose subject is in
    fold['test']; with cap=None every session's rows are kept.  Interleaving of
    ses-1/ses-2 rows is identical to the legacy code because the manifest order is
    reused verbatim.
    """
    want = set(fold["test"])
    rows = [r for r in manifest if r["subject"] in want]
    assert {r["label"] for r in rows} == {"0", "1"}, "legacy assertion: both classes present"
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--subjects", nargs="+", default=None)
    ap.add_argument("--out", type=Path, default=P.AUDIT / "outputs" / "source_closure.json")
    args = ap.parse_args()

    cfg = P.load_splits  # keep import used
    import json

    baselines_cfg = json.loads((P.LEGACY / "configs" / "baselines.json").read_text(encoding="utf-8"))
    manifest = P.load_manifest()
    splits = P.load_splits()
    torch.set_num_threads(baselines_cfg["torch_threads"])

    by_id = {r["segment_id"]: r for r in manifest}
    wave_cache: dict[str, np.ndarray] = {}

    def wave(file_name: str) -> np.ndarray:
        if file_name not in wave_cache:
            wave_cache[file_name] = np.load(P.ACTIVE_DATA / file_name, mmap_mode="r")
        return wave_cache[file_name]

    per_fold = []
    worst_prob = 0.0
    worst_row_id = None
    n_rows = 0
    n_mismatch_label = 0

    folds = splits["folds"]
    if args.subjects:
        folds = [f for f in folds if f["test"][0] in set(args.subjects)]
    print(f"folds to check: {len(folds)}  seeds={args.seeds}", flush=True)

    from sklearn.metrics import balanced_accuracy_score

    for fold in folds:
        subject = fold["test"][0]
        rows = legacy_test_rows(manifest, fold)
        for seed in args.seeds:
            ckpt_dir = P.FORMAL_RESULTS / "eegnet" / subject / f"seed_{seed}"
            model = P.build_model_from_config(baselines_cfg)
            state = torch.load(ckpt_dir / "best.pt", map_location="cpu", weights_only=False)
            model.load_state_dict(state["state_dict"], strict=True)
            model.eval()
            assert all(not m.training for m in model.modules())

            norm = np.load(ckpt_dir / "normalization.npz")
            mean, std = norm["mean"], norm["std"]

            scores = np.empty(len(rows), dtype=np.float64)
            bs = baselines_cfg["batch_size"]
            with torch.inference_mode():
                for start in range(0, len(rows), bs):
                    chunk = rows[start : start + bs]
                    x = np.stack([(np.asarray(wave(r["waveform_file"])[int(r["array_index"])]) - mean) / std
                                  for r in chunk])
                    logits = model(torch.from_numpy(x.astype(np.float32)))
                    scores[start : start + len(chunk)] = torch.softmax(logits, dim=1)[:, 1].numpy()

            legacy = P.read_csv(ckpt_dir / "predictions.csv")
            assert [r["segment_id"] for r in legacy] == [r["segment_id"] for r in rows], \
                f"legacy test set/order mismatch for {subject} seed {seed}"
            legacy_score = np.array([float(r["score"]) for r in legacy])
            legacy_pred = np.array([int(r["y_pred"]) for r in legacy])
            new_pred = (scores >= 0.5).astype(int)

            delta = np.abs(scores - legacy_score)
            i = int(np.argmax(delta))
            n_rows += len(rows)
            n_mismatch_label += int((new_pred != legacy_pred).sum())
            if delta[i] > worst_prob:
                worst_prob, worst_row_id = float(delta[i]), f"{subject}/seed_{seed}/{legacy[i]['segment_id']}"

            y = np.array([int(r["label"]) for r in rows])
            result = json.loads((ckpt_dir / "result.json").read_text(encoding="utf-8"))
            per_fold.append({
                "subject": subject, "seed": seed, "n_segments": len(rows),
                "max_abs_prob_delta": float(delta.max()),
                "mean_abs_prob_delta": float(delta.mean()),
                "n_label_flips": int((new_pred != legacy_pred).sum()),
                "bacc_recomputed": float(balanced_accuracy_score(y, new_pred)),
                "bacc_legacy_json": float(result["test_metrics"]["balanced_accuracy"]),
                "bacc_match": bool(abs(balanced_accuracy_score(y, new_pred)
                                       - result["test_metrics"]["balanced_accuracy"]) < 1e-12),
            })
            print(f"  {subject} seed{seed}: n={len(rows)} max_dp={delta.max():.3e} "
                  f"flips={int((new_pred != legacy_pred).sum())} BA={balanced_accuracy_score(y, new_pred):.6f}",
                  flush=True)

    del cfg
    max_delta = max(r["max_abs_prob_delta"] for r in per_fold)
    all_bacc = all(r["bacc_match"] for r in per_fold)
    payload = {
        "definition": "Re-inference of frozen legacy EEGNet checkpoints on the exact legacy "
                      "held-out windows, compared against the original formal-run predictions.csv.",
        "seeds": args.seeds,
        "n_folds": len(per_fold),
        "n_rows": n_rows,
        "runner_sha256": P.sha256(P.LEGACY / "run_baselines.py"),
        "max_abs_prob_delta": max_delta,
        "worst_row": worst_row_id,
        "n_label_flips": n_mismatch_label,
        "all_bacc_match_exact": all_bacc,
        "verdict": "SOURCE_CLOSED" if (max_delta == 0.0 and n_mismatch_label == 0 and all_bacc)
                   else ("SOURCE_CLOSED_NUMERICALLY" if max_delta < 1e-6 and all_bacc else "SOURCE_MISMATCH"),
        "per_fold": per_fold,
    }
    P.dump(args.out, payload)
    print(f"\nmax abs prob delta = {max_delta:.3e}   label flips = {n_mismatch_label}   "
          f"BA exact = {all_bacc}")
    print("VERDICT:", payload["verdict"])
    print("wrote", args.out)
    return 0 if payload["verdict"].startswith("SOURCE_CLOSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
