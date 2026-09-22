"""Phase 1 collapse taxonomy and subject-level statistics.

The taxonomy is FROZEN before any adaptation run (prompt §13, §15, §16, §17).  Nothing
here may be tuned after seeing a trajectory.

Definitions
-----------
q(t)          : prediction marginal of batch t = mean over the batch of p(y=1|x)
H_cond(t)     : mean over the batch of the conditional predictive entropy
H_marg(t)     : binary entropy of q(t)
dominant(t)   : max(q(t), 1-q(t))
first/last quartile windows are frozen by batch count, not chosen post hoc:
    first = batches [0, floor(n/4))
    last  = batches [ceil(3n/4), n)
"""
from __future__ import annotations

import math

import numpy as np

MIN_BATCHES_FOR_QUARTILES = 4  # below this many batches the quartile split is undefined


# ------------------------------------------------------------------ per-window
def binary_entropy(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


def metrics_from_probs(y, p, threshold=0.5):
    """Accuracy / balanced accuracy / F1 / ROC-AUC.  Mirrors legacy `run_baselines.metrics`."""
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                                 f1_score, roc_auc_score)

    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pred = (p >= threshold).astype(int)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1": float(f1_score(y, pred, pos_label=1, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        "n_windows": int(len(y)),
        "n_true_positive_class": int(y.sum()),
        "n_predicted_positive": int(pred.sum()),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
    }


# ------------------------------------------------------------------ per-batch
def batch_row(y_batch, p_batch):
    """Unsupervised batch statistics + evaluation-only fractions."""
    y = np.asarray(y_batch, dtype=int)
    p = np.asarray(p_batch, dtype=float)
    pred = (p >= 0.5).astype(int)
    q1 = float(p.mean())
    ent = binary_entropy(p)
    return {
        "batch_n": int(len(p)),
        "H_cond": float(ent.mean()),
        "q1": q1,
        "H_marg": float(binary_entropy(q1)),
        "dominant_share": float(max(q1, 1 - q1)),
        "mean_max_conf": float(np.mean(np.maximum(p, 1 - p))),
        "pred_positive_frac": float(pred.mean()),
        "true_positive_frac": float(y.mean()) if len(y) else float("nan"),
        "batch_accuracy": float((pred == y).mean()) if len(y) else float("nan"),
        "batch_balanced_accuracy": _bacc(y, pred),
    }


def _bacc(y, pred):
    pos = y == 1
    neg = ~pos
    if pos.sum() == 0 or neg.sum() == 0:
        return float("nan")
    return float(0.5 * ((pred[pos] == 1).mean() + (pred[neg] == 0).mean()))


def quartile_indices(n_batches):
    """Frozen quartile boundaries.  Returns (first_slice, last_slice) as index ranges."""
    if n_batches < MIN_BATCHES_FOR_QUARTILES:
        return None, None
    k = n_batches // 4
    return (0, k), (math.ceil(3 * n_batches / 4), n_batches)


def segment_summary(batch_rows):
    """Aggregate a per-batch trajectory into first-quartile / last-quartile summaries."""
    n = len(batch_rows)
    first, last = quartile_indices(n)
    out = {"n_batches": n, "quartile_defined": first is not None}
    if first is None:
        return out

    def agg(key, sl):
        vals = [r[key] for r in batch_rows[sl[0]:sl[1]]]
        vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return float(np.mean(vals)) if vals else None

    for key in ("H_cond", "H_marg", "dominant_share", "mean_max_conf", "q1",
                "pred_positive_frac", "true_positive_frac", "batch_balanced_accuracy"):
        out[f"first_{key}"] = agg(key, first)
        out[f"last_{key}"] = agg(key, last)
        out[f"delta_{key}"] = (None if out[f"first_{key}"] is None or out[f"last_{key}"] is None
                               else out[f"last_{key}"] - out[f"first_{key}"])
    return out


# ------------------------------------------------------------------ group stats
def paired_bootstrap_ci(deltas, n_resample=10000, seed=20260920, alpha=0.05):
    """95 % paired bootstrap CI over SUBJECTS (the statistical unit; prompt §16).

    Subjects are the resampling unit; windows are never treated as independent.
    """
    d = np.asarray([x for x in deltas if x is not None and np.isfinite(x)], dtype=float)
    if len(d) < 2:
        return {"n": int(len(d)), "mean": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_resample, len(d)))
    means = d[idx].mean(axis=1)
    return {
        "n": int(len(d)),
        "mean": float(d.mean()),
        "median": float(np.median(d)),
        "sd": float(d.std(ddof=1)),
        "q1": float(np.percentile(d, 25)),
        "q3": float(np.percentile(d, 75)),
        "iqr": float(np.percentile(d, 75) - np.percentile(d, 25)),
        "ci_low": float(np.percentile(means, 100 * alpha / 2)),
        "ci_high": float(np.percentile(means, 100 * (1 - alpha / 2))),
        "n_improved": int((d > 0).sum()),
        "n_harmed": int((d < 0).sum()),
        "n_tied": int((d == 0).sum()),
    }


def reliable_lower(stat):
    return stat["ci_high"] is not None and stat["ci_high"] < 0


def reliable_higher(stat):
    return stat["ci_low"] is not None and stat["ci_low"] > 0


# ------------------------------------------------------------------ verdict
CASE1 = "CASE 1 - NO MATERIAL TENT HARM"
CASE2 = "CASE 2 - PERFORMANCE DEGRADATION WITHOUT COLLAPSE"
CASE3 = "CASE 3 - TENT-SPECIFIC HARMFUL COLLAPSE"
CASE4 = "CASE 4 - BN/NORMALIZATION INSTABILITY"
CASE5 = "CASE 5 - SUBJECT-SPECIFIC / HETEROGENEOUS FAILURE"
CASE6 = "CASE 6 - TRAIN-MODE/DROPOUT SEMANTICS IMPLICATED"

DEGRADE_EPS = 0.01      # |mean dBAcc| below this counts as "materially similar"
CONCENTRATION_EPS = 0.02  # dominant-share change below this counts as "no concentration"
SUBJECT_COLLAPSE_DROP = 0.10  # per-subject dBAcc at or below this is "strongly harmed"


def _collapsed(stat_bacc, stat_dom):
    """Frozen two-part collapse test: reliable degradation AND reliable concentration."""
    return (reliable_lower(stat_bacc) and stat_bacc["mean"] <= -DEGRADE_EPS
            and reliable_higher(stat_dom) and stat_dom["mean"] >= CONCENTRATION_EPS)


def _degraded(stat_bacc):
    return reliable_lower(stat_bacc) and stat_bacc["mean"] <= -DEGRADE_EPS


def _concentrated(stat_dom):
    return reliable_higher(stat_dom) and stat_dom["mean"] >= CONCENTRATION_EPS


def decide_case(inputs):
    """Frozen decision rule over group-level statistics (prompt §17 + the pre-result
    interpretation matrix, prompt correction 4).

    inputs: dict with
      literal : {'bacc': stat, 'dominant': stat, 'h_marg': stat}
      det     : {'bacc': stat, 'dominant': stat, 'h_marg': stat}
      bn      : {'bacc': stat, 'dominant': stat}
      per_subject : list of {'subject', 'delta_bacc_tent'/'delta_bacc_tent_literal', ...}
      h_cond_differs : bool - whether the two TENT arms' conditional-entropy trajectories
                       differ materially (recorded, not used as a gate)

    Matrix (owner-specified, frozen before any result):
      * LITERAL collapses and DET does not
            -> do NOT attribute collapse to entropy minimisation alone;
               Dropout / train-mode semantics are implicated.           [CASE 6]
      * LITERAL and DET both collapse, BN_ONLY stable
            -> more consistent with entropy-driven BN-affine adaptation. [CASE 3]
      * BN_ONLY also collapses
            -> normalization / batch-statistics instability implicated.  [CASE 4]
      * none collapse
            -> collapse not established; do not tune hyperparameters.     [CASE 1]
    """
    lit_b, lit_d = inputs["literal"]["bacc"], inputs["literal"]["dominant"]
    det_b, det_d = inputs["det"]["bacc"], inputs["det"]["dominant"]
    bn_b, bn_d = inputs["bn"]["bacc"], inputs["bn"]["dominant"]

    lit_collapse = _collapsed(lit_b, lit_d)
    det_collapse = _collapsed(det_b, det_d)
    bn_collapse = _collapsed(bn_b, bn_d)

    lit_degraded, lit_concentrated = _degraded(lit_b), _concentrated(lit_d)
    det_degraded, det_concentrated = _degraded(det_b), _concentrated(det_d)
    bn_degraded, bn_concentrated = _degraded(bn_b), _concentrated(bn_d)

    per_subject = inputs["per_subject"]
    strongly_harmed = [r for r in per_subject
                       if r.get("delta_bacc_tent_literal") is not None
                       and r["delta_bacc_tent_literal"] <= -SUBJECT_COLLAPSE_DROP
                       and r.get("delta_dominant_tent_literal") is not None
                       and r["delta_dominant_tent_literal"] >= CONCENTRATION_EPS]
    frac_harmed = len(strongly_harmed) / max(1, len(per_subject))

    attribution = None
    if lit_collapse and not det_collapse:
        case = CASE6
        attribution = ("Dropout / train-mode semantics are implicated: the literal arm "
                       "collapsed while the deterministic-dropout arm did not, so collapse "
                       "may NOT be attributed to entropy minimisation alone.")
    elif bn_collapse:
        # BN_ONLY collapses -> normalization statistics suffice; a TENT-specific claim is barred.
        case = CASE4
        attribution = ("Normalization / batch-statistics instability is implicated: the "
                       "non-gradient BN_ONLY control degenerated as well, so 'entropy "
                       "minimisation caused collapse' is not writable.")
    elif lit_collapse and det_collapse:
        case = CASE3
        attribution = ("More consistent with entropy-driven BN-affine adaptation: both "
                       "entropy arms collapsed while the BN_ONLY control did not.")
    elif bn_degraded and not bn_concentrated and not lit_concentrated and not det_concentrated:
        # FIXED ORDERING BUG: the previous rule only consulted BN_ONLY when it *collapsed*.
        # Here BN_ONLY is degraded WITHOUT concentration, so no arm shows the collapse
        # signature at all - yet the control that contains no gradient is degraded just as
        # much as the two arms that do. That is a positive attribution to the
        # normalization-statistics switch, not merely an absence of collapse.
        case = CASE4
        attribution = ("Degradation is present but the collapse signature is absent in every "
                       "arm, INCLUDING the gradient-free BN_ONLY control. Normalization-"
                       "statistics adaptation is therefore implicated as sufficient for the "
                       "degradation, and the entropy gradient is not required for it.")
    elif lit_degraded and not lit_concentrated and not det_concentrated:
        case = CASE2
        attribution = ("Performance degrades without prediction-diversity contraction; "
                       "this is degradation, not collapse. Study adaptation mismatch.")
    else:
        case = CASE1
        attribution = ("Collapse is not established under the frozen protocol. Do not tune "
                       "hyperparameters to manufacture it.")
    if case in (CASE1, CASE2) and 0 < frac_harmed <= 0.25 and len(strongly_harmed) >= 2:
        case = CASE5
        attribution = ("Population-wide collapse is not established, but subject-specific "
                       "vulnerability exists.")

    return {
        "case": case,
        "attribution": attribution,
        "tent_literal_collapse": bool(lit_collapse),
        "tent_det_collapse": bool(det_collapse),
        "bn_only_collapse": bool(bn_collapse),
        "tent_literal_degraded": bool(lit_degraded),
        "tent_literal_concentrated": bool(lit_concentrated),
        "tent_det_degraded": bool(det_degraded),
        "tent_det_concentrated": bool(det_concentrated),
        "bn_degraded": bool(bn_degraded),
        "bn_concentrated": bool(bn_concentrated),
        "literal_vs_det_differ": bool(lit_collapse != det_collapse),
        "h_cond_trajectories_differ": bool(inputs.get("h_cond_differs")),
        "n_strongly_harmed_subjects": len(strongly_harmed),
        "frac_strongly_harmed_subjects": frac_harmed,
        "strongly_harmed_subjects": [r["subject"] for r in strongly_harmed],
        "thresholds": {"DEGRADE_EPS": DEGRADE_EPS, "CONCENTRATION_EPS": CONCENTRATION_EPS,
                       "SUBJECT_COLLAPSE_DROP": SUBJECT_COLLAPSE_DROP},
    }
