"""Phase 1 analysis: subject metrics, trajectories, collapse statistics, verdict.

Consumes the stored per-unit JSONs (no model runs).  Primary stream is the subject's
authoritative `SessionOrder` visit pair (`metadata_order`).

Writes:
  source_subject_metrics.csv / bn_only_subject_metrics.csv
  tent_literal_subject_metrics.csv / tent_det_subject_metrics.csv
  subject_level_comparison.csv
  <arm>_predictions.csv          (per-window, all four arms)
  tent_batch_trajectory.csv      (per-batch, all four arms)
  tent_parameter_drift.csv       (the two TENT arms)
  collapse_subject_summary.csv
  collapse_group_summary.json
  collapse_verdict.json

  python 30_analyze_collapse.py --seeds 0 1 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
import p1_arms as A        # noqa: E402
import p1_collapse as K    # noqa: E402
import p1_common as P      # noqa: E402

OUT = HERE / "outputs"
UNITS = OUT / "units"
LABEL = {"source": "source", "bn_only": "bn_only",
         "tent_literal": "tent_literal", "tent_det": "tent_det"}


def _load_units(variant, arm, seed):
    out = {}
    for p in sorted(UNITS.glob(f"{variant}__{arm}__seed{seed}__*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["subject"]] = r
    return out


def _batch_rows(res):
    """Rebuild per-batch trajectory rows with the collapse metrics attached."""
    out = []
    by_batch = {}
    for w in res["window_rows"]:
        by_batch.setdefault(w["batch_index"], []).append(w)
    for b in res["batch_rows"]:
        ws = by_batch.get(b["batch_index"], [])
        if not ws:
            continue
        row = {**b, **K.batch_row([w["y_true"] for w in ws], [w["p_positive"] for w in ws])}
        row["subject"] = res["subject"]
        row["seed"] = res["seed"]
        row["arm"] = res["arm"]
        row["session_block_order"] = res["session_block_order"]
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=A.PRIMARY_VARIANT)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--arms", nargs="+", default=list(A.ARMS))
    args = ap.parse_args()

    if args.variant in A.PARKED_VARIANTS:
        raise SystemExit(f"REFUSED: {args.variant} is a PARKED order diagnostic.")

    data = {(arm, seed): _load_units(args.variant, arm, seed)
            for arm in args.arms for seed in args.seeds}
    incomplete = {k: len(v) for k, v in data.items() if len(v) != 68}
    if incomplete:
        print("WARNING: incomplete units (arm, seed) ->", incomplete)

    # ---------------------------------------------------------------- per-arm subject metrics
    def subject_metric(arm, seed, subject):
        res = data[(arm, seed)].get(subject)
        if res is None:
            return None
        rows = res["window_rows"]
        return K.metrics_from_probs([r["y_true"] for r in rows], [r["p_positive"] for r in rows])

    for arm in args.arms:
        table = []
        for seed in args.seeds:
            for subject in sorted(data[(arm, seed)]):
                m = subject_metric(arm, seed, subject)
                table.append({"subject": subject, "seed": seed, "arm": arm,
                              "session_block_order": args.variant, **m})
        P.write_csv(OUT / f"{arm}_subject_metrics.csv", table)

    def seed_mean(arm, subject, metric):
        vals = []
        for seed in args.seeds:
            m = subject_metric(arm, seed, subject)
            if m is not None and m[metric] is not None:
                vals.append(m[metric])
        return float(np.mean(vals)) if vals else None

    subjects = sorted(set.intersection(*[set(data[(a, args.seeds[0])]) for a in args.arms])) \
        if all(data[(a, args.seeds[0])] for a in args.arms) else sorted(data[("source", args.seeds[0])])

    comparison = []
    for subject in subjects:
        row = {"subject": subject,
               "SessionOrder": P.load_session_order().get(subject),
               "visit_pair": "->".join(A.visit_pair(subject))}
        for metric in ("accuracy", "balanced_accuracy", "f1", "roc_auc"):
            for arm in args.arms:
                row[f"{metric}_{arm}"] = seed_mean(arm, subject, metric)
                src = row[f"{metric}_source"]
                row[f"delta_{metric}_{arm}_vs_source"] = (
                    None if row[f"{metric}_{arm}"] is None or src is None
                    else row[f"{metric}_{arm}"] - src)
        # last-quartile stream summaries per arm
        for arm in args.arms:
            segs = []
            for seed in args.seeds:
                res = data[(arm, seed)].get(subject)
                if res is None:
                    continue
                segs.append(K.segment_summary(_batch_rows(res)))
            keys = ("last_H_marg", "last_dominant_share", "last_H_cond", "last_mean_max_conf",
                    "last_q1", "last_pred_positive_frac", "last_true_positive_frac",
                    "last_batch_balanced_accuracy", "delta_H_marg", "delta_dominant_share",
                    "delta_H_cond", "delta_mean_max_conf")
            for k in keys:
                vals = [s[k] for s in segs if s.get(k) is not None]
                row[f"{k}_{arm}"] = float(np.mean(vals)) if vals else None
        for k in ("last_H_marg", "last_dominant_share", "last_H_cond", "last_mean_max_conf"):
            for arm in args.arms:
                if arm == "source":
                    continue
                a, b = row.get(f"{k}_{arm}"), row.get(f"{k}_source")
                row[f"delta_{k}_{arm}_vs_source"] = None if a is None or b is None else a - b
        # per-window disagreement with SOURCE
        for arm in args.arms:
            if arm == "source":
                continue
            dis = []
            for seed in args.seeds:
                s, a2 = data[("source", seed)].get(subject), data[(arm, seed)].get(subject)
                if s is None or a2 is None:
                    continue
                sm = {r["segment_id"]: r["y_pred"] for r in s["window_rows"]}
                am = {r["segment_id"]: r["y_pred"] for r in a2["window_rows"]}
                if set(sm) == set(am):
                    dis.append(float(np.mean([sm[k] != am[k] for k in sm])))
            row[f"pred_disagreement_vs_source_{arm}"] = float(np.mean(dis)) if dis else None
        # TENT_LITERAL vs TENT_DET agreement: the diagnostic of interest
        if "tent_literal" in args.arms and "tent_det" in args.arms:
            dis = []
            for seed in args.seeds:
                a, b = data[("tent_literal", seed)].get(subject), data[("tent_det", seed)].get(subject)
                if a is None or b is None:
                    continue
                am = {r["segment_id"]: r["y_pred"] for r in a["window_rows"]}
                bm = {r["segment_id"]: r["y_pred"] for r in b["window_rows"]}
                if set(am) == set(bm):
                    dis.append(float(np.mean([am[k] != bm[k] for k in am])))
            row["pred_disagreement_literal_vs_det"] = float(np.mean(dis)) if dis else None
        row["n_windows"] = sum(
            data[("source", seed)][subject]["n_windows"]
            for seed in args.seeds if subject in data[("source", seed)])
        comparison.append(row)
    P.write_csv(OUT / "subject_level_comparison.csv", comparison)

    # ---------------------------------------------------------------- trajectories
    all_batch = []
    for arm in args.arms:
        for seed in args.seeds:
            for subject in sorted(data[(arm, seed)]):
                all_batch += _batch_rows(data[(arm, seed)][subject])
    P.write_csv(OUT / "tent_batch_trajectory.csv", all_batch)
    P.write_csv(OUT / "tent_parameter_drift.csv",
                [r for r in all_batch if r["arm"] in A.TENT_ARMS])

    for arm in args.arms:
        pred_rows = []
        for seed in args.seeds:
            for subject in sorted(data[(arm, seed)]):
                for r in data[(arm, seed)][subject]["window_rows"]:
                    pred_rows.append({"arm": arm, "seed": seed,
                                      "session_block_order": args.variant, **r})
        P.write_csv(OUT / f"{arm}_predictions.csv", pred_rows)

    # ---------------------------------------------------------------- collapse statistics
    def stat_of(key):
        return K.paired_bootstrap_ci([r.get(key) for r in comparison])

    stats = {arm: {"bacc": stat_of(f"delta_balanced_accuracy_{arm}_vs_source"),
                   "dominant": stat_of(f"delta_last_dominant_share_{arm}_vs_source"),
                   "h_marg": stat_of(f"delta_last_H_marg_{arm}_vs_source"),
                   "h_cond": stat_of(f"delta_last_H_cond_{arm}_vs_source"),
                   "conf": stat_of(f"delta_last_mean_max_conf_{arm}_vs_source"),
                   "accuracy": stat_of(f"delta_accuracy_{arm}_vs_source"),
                   "f1": stat_of(f"delta_f1_{arm}_vs_source"),
                   "auc": stat_of(f"delta_roc_auc_{arm}_vs_source")}
             for arm in args.arms}

    per_subject = [{
        "subject": r["subject"],
        **{f"delta_bacc_{arm}": r.get(f"delta_balanced_accuracy_{arm}_vs_source")
           for arm in args.arms},
        **{f"delta_dominant_{arm}": r.get(f"delta_last_dominant_share_{arm}_vs_source")
           for arm in args.arms},
        **{f"delta_hmarg_{arm}": r.get(f"delta_last_H_marg_{arm}_vs_source")
           for arm in args.arms},
        "disagreement_literal_vs_det": r.get("pred_disagreement_literal_vs_det"),
    } for r in comparison]
    P.write_csv(OUT / "collapse_subject_summary.csv", per_subject)

    # ---------------------------------------------------------------- batch / skew audit
    manifest = P.load_manifest()
    skew = []
    for subject in subjects:
        rows = [x for x in manifest if x["subject"] == subject]
        s1 = len([x for x in rows if x["session"] == "ses-1"])
        s2 = len([x for x in rows if x["session"] == "ses-2"])
        stream, _ = A.build_stream(manifest, subject)
        profile = A.batch_size_profile(stream)
        pair = A.visit_pair(subject)
        c = next(r for r in comparison if r["subject"] == subject)
        skew.append({
            "subject": subject, "visit_pair": "->".join(pair),
            "n_windows": s1 + s2, "share_ses2_SD": s2 / (s1 + s2),
            "n_batches": len(stream), "batch_size": A.PROTOCOL["batch_size"],
            "final_batch_size_first_visit": profile[pair[0]][-1],
            "final_batch_size_second_visit": profile[pair[1]][-1],
            "n_batches_of_size_1": sum(1 for v in profile.values() for x in v if x == 1),
            **{f"delta_bacc_{arm}": c.get(f"delta_balanced_accuracy_{arm}_vs_source")
               for arm in args.arms},
            **{f"delta_dominant_{arm}": c.get(f"delta_last_dominant_share_{arm}_vs_source")
               for arm in args.arms},
        })
    P.write_csv(OUT / "batch_and_skew_audit.csv", skew)

    verdict_inputs = {
        "literal": {"bacc": stats["tent_literal"]["bacc"],
                    "dominant": stats["tent_literal"]["dominant"],
                    "h_marg": stats["tent_literal"]["h_marg"]},
        "det": {"bacc": stats["tent_det"]["bacc"],
                "dominant": stats["tent_det"]["dominant"],
                "h_marg": stats["tent_det"]["h_marg"]},
        "bn": {"bacc": stats["bn_only"]["bacc"], "dominant": stats["bn_only"]["dominant"]},
        "per_subject": [{"subject": r["subject"],
                         "delta_bacc_tent_literal": r["delta_bacc_tent_literal"],
                         "delta_dominant_tent_literal": r["delta_dominant_tent_literal"]}
                        for r in per_subject],
        "h_cond_differs": None,
    }
    # does the literal/det split actually move the conditional-entropy trajectory?
    if "tent_literal" in stats and "tent_det" in stats:
        a, b = stats["tent_literal"]["h_cond"], stats["tent_det"]["h_cond"]
        verdict_inputs["h_cond_differs"] = bool(
            a["mean"] is not None and b["mean"] is not None
            and abs(a["mean"] - b["mean"]) > 0.01)
    verdict = K.decide_case(verdict_inputs)

    group = {
        "primary_variant": args.variant,
        "arms": list(args.arms),
        "seeds": args.seeds,
        "batch_size": A.PROTOCOL["batch_size"],
        "lr": A.PROTOCOL["lr"],
        "optimizer": A.PROTOCOL["optimizer"],
        "steps_per_batch": A.PROTOCOL["steps_per_batch"],
        "adaptation": A.PROTOCOL["adaptation"],
        "unit": "subject",
        "n_subjects": len(subjects),
        "n_windows_total": int(sum(r["n_windows"] for r in comparison)) // max(1, len(args.seeds)),
        "arms_vs_source": {
            arm: {k: stats[arm][k] for k in ("bacc", "accuracy", "f1", "auc",
                                             "dominant", "h_marg", "h_cond", "conf")}
            for arm in args.arms if arm != "source"},
        "verdict": verdict,
    }
    P.dump(OUT / "collapse_group_summary.json", group)
    P.dump(OUT / "collapse_verdict.json", verdict)
    print(json.dumps({"case": verdict["case"], "attribution": verdict["attribution"],
                      "bacc": {a: stats[a]["bacc"]["mean"] for a in args.arms},
                      "dominant": {a: stats[a]["dominant"]["mean"] for a in args.arms}},
                     indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
