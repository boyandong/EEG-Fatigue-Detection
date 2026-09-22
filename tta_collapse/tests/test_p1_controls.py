"""Prove every Phase-1 control can FAIL (prompt §26: a check that cannot fail is not a check).

Run:  python tests/test_p1_controls.py
Each control is fed a clean object and a deliberately corrupted one; it must pass the
first and fail the second.  Prints `n/n controls bite`.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

# This suite is run BOTH by a human at a console and as a captured subprocess by
# `90_verify_phase1.py` H1 / `_refactor/80_verify_refactor.py` C2. On Windows the default
# encoding of a *piped* stdout is the ANSI code page (here cp1252), so a single non-ASCII
# character in one print used to abort the whole suite with UnicodeEncodeError and make the
# verifier's result depend on the operator's locale. Pin stdout to UTF-8; never let the
# reporting channel decide whether the controls ran.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):      # pragma: no cover - non-reconfigurable stream
        pass

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import p1_arms as A        # noqa: E402
import p1_common as P      # noqa: E402
import p1_controls as C    # noqa: E402
import p1_controls_semantics as S  # noqa: E402

RESULTS = []


def _real_tent_probe():
    """Run the REAL `entropy_forward` once and return (scored, entropy_logits, loss).

    Uses the tiny synthetic model only: no real data, no adaptation history.  The model and
    input are cached on the function so the runtime forward-count probe can reuse them.
    """
    import torch

    if getattr(_real_tent_probe, "model", None) is None:
        cfg = {"eegnet": {"F1": 2, "D": 2, "F2": 4, "kernel_length": 16,
                          "depthwise_kernel_length": 8, "drop_prob": 0.5,
                          "final_layer_with_constraint": True, "norm_rate": 0.25}}
        maker = _tiny_maker()
        state = {k: v.clone() for k, v in maker().state_dict().items()}
        model, _params, _audit = A.build_arm_model(cfg, state, "tent_literal", builder=maker)
        torch.manual_seed(0)
        _real_tent_probe.model = model
        _real_tent_probe.x = torch.randn(6, 4, 128)
    model, x = _real_tent_probe.model, _real_tent_probe.x
    A.prepare_adaptation_mode("tent_literal", model)
    with torch.enable_grad():
        logits, _loss = A.entropy_forward("tent_literal", model, x)
    scored = logits.detach().clone()
    entropy_logits = logits.detach().clone()
    return scored.numpy(), entropy_logits.numpy(), float(_loss)


_real_tent_probe.model = None
_real_tent_probe.x = None


def _tiny_maker():
    import torch
    from braindecode.models import EEGNet

    def make(cfg=None):
        torch.manual_seed(7)
        return EEGNet(n_chans=4, n_outputs=2, n_times=128, sfreq=500,
                      F1=2, D=2, F2=4, kernel_length=16, depthwise_kernel_length=8,
                      drop_prob=0.5, final_layer_with_constraint=True, norm_rate=0.25)
    return make


def check(name, passed, detail=""):
    RESULTS.append((name, bool(passed)))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}"
          + (f"   {detail}" if detail and passed else ""))
    return bool(passed)


def fake_run(subject="sub-01", arm="tent_literal", sessions=("ses-1",),
             batch_sizes=None, dropout_active=None, batch_size=32):
    """Build a self-consistent fake unit: batches are cut inside each session, a session's
    trailing batch keeps its true size, and `block_span` is that session's window count."""
    if dropout_active is None:
        dropout_active = (arm == "tent_literal")
    if batch_sizes is None:
        batch_sizes = {s: [2, 2] if i == 0 else [2, 2] for i, s in enumerate(sessions)}
    rows, brows = [], []
    bi = pos = 0
    for block_i, session in enumerate(sessions):
        sizes = list(batch_sizes[session])
        span = sum(sizes)
        for j, n in enumerate(sizes):
            for k in range(n):
                rows.append({"subject": subject, "seed": 0, "arm": arm, "batch_index": bi,
                             "block": block_i, "session": session, "stream_position": pos,
                             "segment_id": f"{subject}_{session}_s{pos:04d}",
                             "y_true": pos % 2, "source_epoch_index": sum(sizes[:j]) + k,
                             "p_positive": 0.5, "y_pred": pos % 2, "batch_n": n})
                pos += 1
            brows.append({"subject": subject, "seed": 0, "arm": arm, "batch_index": bi,
                          "session": session, "block": block_i, "batch_n": n,
                          "block_span": span, "is_final_batch_of_block": j == len(sizes) - 1,
                          "batch_grad_norm": 0.0, "batch_entropy_loss": 0.5,
                          "batch_mean_entropy": 0.6, "batch_marginal_q1": 0.5,
                          "batch_pred_positive_frac": 0.5, "batch_true_positive_frac": 0.5,
                          "batch_mean_max_conf": 0.7, "affine_drift_l2": 0.0,
                          "dropout_active_during_forward": dropout_active,
                          "dropout_active_during_adaptation": dropout_active})
            bi += 1
    profile = {}
    for b in brows:
        profile.setdefault(b["session"], []).append(b["batch_n"])
    return {"arm": arm, "subject": subject, "seed": 0,
            "session_block_order": "metadata_order",
            "visit_pair": list(sessions),
            "n_windows": len(rows), "n_batches": len(brows),
            "batch_size_profile": profile,
            "batch_sizes_observed": sorted({n for v in profile.values() for n in v}),
            "scores": {r["segment_id"]: 0.5 for r in rows},
            "window_rows": rows, "batch_rows": brows,
            "norm_audit": [], "source_meta": {"state_sha256": "deadbeef"},
            "dropout_audit": {"n_dropout_modules": 2, "dropout_names": ["d1", "d2"],
                              "dropout_any_training": bool(dropout_active),
                              "dropout_all_training": bool(dropout_active)},
            "n_trainable_tensors": 0, "n_trainable_scalars": 0, "trainable_names": [],
            "affine_norm_initial": 0.0, "state_unchanged": True,
            "batch_size": batch_size}


def fake_stream(n_epochs=8):
    rows = [{"subject": "sub-01", "session": "ses-1", "label": str(i % 2),
             "source_epoch_index": i, "segment_id": f"s{i}"} for i in range(n_epochs)]
    return [{"block": 0, "session": "ses-1", "block_span": n_epochs, "rows": rows[i:i + 4]}
            for i in range(0, n_epochs, 4)]


def main():
    cfg_path = P.LEGACY / "configs" / "baselines.json"
    import json

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    print("NC1 - adaptation region contains no target label")
    r = C.nc1_no_labels_inside_adaptation_region()
    check("NC1 clean pipeline passes", r["passed"])
    r = C.nc1_no_labels_inside_adaptation_region(source_text=(
        "def run_arm():\n# ---- BEGIN ADAPTATION REGION\n    y = r['label']\n    loss = f(y)\n"
        "# ---- END ADAPTATION REGION\n"))
    check("NC1 injected label read is caught", not r["passed"])
    r = C.nc1_no_labels_inside_adaptation_region(source_text="def run_arm():\n    pass\n")
    check("NC1 missing sentinel is caught", not r["passed"])

    print("NC2 - held-out checkpoint mapping")
    splits = P.load_splits()
    r = C.nc2_checkpoint_mapping("sub-01", P.FORMAL_RESULTS / "eegnet" / "sub-01" / "seed_0", splits)
    check("NC2 correct fold passes", r["passed"])
    r = C.nc2_checkpoint_mapping("sub-01", P.FORMAL_RESULTS / "eegnet" / "sub-02" / "seed_0", splits)
    check("NC2 wrong-fold checkpoint is caught", not r["passed"])

    print("NC3 - no cross-subject leakage")
    runs = [fake_run("sub-01"), fake_run("sub-02")]
    hashes = {"sub-01": "deadbeef", "sub-02": "deadbeef"}
    r = C.nc3_no_cross_subject_leakage(runs, hashes)
    check("NC3 matched start states pass", r["passed"])
    bad = copy.deepcopy(runs)
    bad[1]["source_meta"]["state_sha256"] = "0000"
    r = C.nc3_no_cross_subject_leakage(bad, hashes)
    check("NC3 wrong start state is caught", not r["passed"])

    print("NC4 - SOURCE arm frozen")
    src = fake_run(arm="source")
    r = C.nc4_source_arm_frozen(src)
    check("NC4 frozen source passes", r["passed"])
    bad = copy.deepcopy(src)
    bad["n_trainable_tensors"] = 6
    check("NC4 trainable source is caught", not C.nc4_source_arm_frozen(bad)["passed"])
    bad = copy.deepcopy(src)
    bad["state_unchanged"] = False
    check("NC4 mutated source state is caught", not C.nc4_source_arm_frozen(bad)["passed"])

    print("NC5 - BN_ONLY produces no gradient")
    bn = fake_run(arm="bn_only")
    check("NC5 clean BN-only passes", C.nc5_bn_only_no_gradient(bn)["passed"])
    bad = copy.deepcopy(bn)
    bad["batch_rows"][1]["batch_grad_norm"] = 0.01
    check("NC5 nonzero BN-only gradient is caught", not C.nc5_bn_only_no_gradient(bad)["passed"])
    bad = copy.deepcopy(bn)
    bad["n_trainable_tensors"] = 1
    check("NC5 trainable BN-only is caught", not C.nc5_bn_only_no_gradient(bad)["passed"])

    print("NC6 - TENT updates only normalization affine")
    import torch

    model = P.build_model_from_config(cfg)
    names = [f"{n}.{p}" for n, m in model.named_modules()
             if isinstance(m, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d))
             for p in ("weight", "bias")]
    tent = fake_run(arm="tent_literal")
    tent["trainable_names"] = names
    tent["n_trainable_tensors"] = len(names)
    check("NC6 exact BN affine set passes", C.nc6_tent_updates_only_norm(tent, cfg)["passed"])
    bad = copy.deepcopy(tent)
    bad["trainable_names"] = names + ["conv_temporal.weight"]
    check("NC6 extra non-norm parameter is caught", not C.nc6_tent_updates_only_norm(bad, cfg)["passed"])
    bad = copy.deepcopy(tent)
    bad["trainable_names"] = names[:-1]
    check("NC6 missing affine parameter is caught", not C.nc6_tent_updates_only_norm(bad, cfg)["passed"])

    print("NC7/NC8 - stream not shuffled, temporal order preserved")
    stream = fake_stream()
    check("NC7 ordered stream passes", C.nc7_stream_not_shuffled(stream, None)["passed"])
    shuffled = copy.deepcopy(stream)
    shuffled[0]["rows"] = list(reversed(shuffled[0]["rows"]))
    check("NC7 shuffled stream is caught", not C.nc7_stream_not_shuffled(shuffled, None)["passed"])
    check("NC8 strictly ascending epochs pass", C.nc8_temporal_order_preserved(stream)["passed"])
    gapped = copy.deepcopy(stream)
    gapped[0]["rows"][2]["source_epoch_index"] = 1  # duplicate epoch -> caught
    check("NC8 duplicate epoch is caught", not C.nc8_temporal_order_preserved(gapped)["passed"])
    reordered = copy.deepcopy(stream)
    reordered[0]["rows"] = list(reversed(reordered[0]["rows"]))
    check("NC8 reversed block is caught", not C.nc8_temporal_order_preserved(reordered)["passed"])

    print("NC9/NC10 - identical sample sets and batch boundaries")
    arms = {a: fake_run(arm=a) for a in A.ARMS}
    check("NC9 identical sets pass", C.nc9_identical_sample_sets(arms)["passed"])
    bad = copy.deepcopy(arms)
    bad["tent_det"]["scores"].pop(next(iter(bad["tent_det"]["scores"])))
    check("NC9 missing window is caught", not C.nc9_identical_sample_sets(bad)["passed"])
    check("NC10 identical boundaries pass", C.nc10_identical_batch_boundaries(arms)["passed"])
    bad = copy.deepcopy(arms)
    bad["tent_literal"]["batch_rows"][0]["batch_n"] = 3
    check("NC10 differing batch boundary is caught", not C.nc10_identical_batch_boundaries(bad)["passed"])

    print("NC11 - no future batch")
    check("NC11 monotone stream passes", C.nc11_no_future_batches(fake_run())["passed"])
    bad = fake_run()
    bad["window_rows"][0]["stream_position"] = 99
    check("NC11 non-monotone stream is caught", not C.nc11_no_future_batches(bad)["passed"])

    print("NC12 - subject-level aggregation")
    good = {"unit": "subject", "n_subjects_reported": 68, "n_windows": 9390,
            "stat": {"n": 68}}
    check("NC12 subject unit passes", C.nc12_subject_level_aggregation(good)["passed"])
    bad = {"unit": "subject", "n_subjects_reported": 68, "n_windows": 9390, "stat": {"n": 9390}}
    check("NC12 window-level aggregation is caught", not C.nc12_subject_level_aggregation(bad)["passed"])
    bad = {"unit": "window", "n_subjects_reported": 68, "n_windows": 9390, "stat": {"n": 68}}
    check("NC12 window unit label is caught", not C.nc12_subject_level_aggregation(bad)["passed"])

    print("NC13 - session label is not a model input")
    check("NC13 clean pipeline passes", C.nc13_session_label_not_model_input(fake_run())["passed"])
    r = C.nc13_session_label_not_model_input(fake_run(), source_text=(
        "def run_arm():\n# ---- BEGIN ADAPTATION REGION\n    x = torch.from_numpy(session_oh)\n"
        "# ---- END ADAPTATION REGION\n"))
    check("NC13 session tensor is caught", not r["passed"])

    print("NC14 - SessionOrder, not clock time, governs visit order")
    clock = P.load_clock_times()
    pair1 = tuple(P.session_block_order_for("sub-01"))
    good_runs = [fake_run("sub-01", arm=a, sessions=pair1) for a in A.ARMS]
    r = C.nc14_session_order_governs_visit_order(good_runs, None, clock)
    check("NC14 correct metadata ordering passes", r["passed"], json.dumps(r["detail"])[:150])
    wrong = [fake_run("sub-01", arm=a, sessions=tuple(reversed(pair1))) for a in A.ARMS]
    r = C.nc14_session_order_governs_visit_order(wrong, None, clock)
    check("NC14 wrong block order is caught", not r["passed"])
    # ordering must be independent of whatever clock set is supplied
    uniform = {pid: (8 * 60, 9 * 60) for pid in clock}
    r = C.nc14_session_order_governs_visit_order(good_runs, None, uniform)
    check("NC14 ordering is independent of the clock set (uniform clock cannot corrupt it)",
          r["passed"])

    print("NC15 - batches never cross a visit boundary")
    sizes = {"ses-1": [4, 4, 3], "ses-2": [4, 4, 2]}
    bs4 = 4
    good = [fake_run("sub-01", arm=a, sessions=("ses-1", "ses-2"), batch_sizes=sizes, batch_size=bs4)
            for a in A.ARMS]
    r = C.nc15_no_batch_crosses_a_visit_boundary(good)
    check("NC15 clean per-visit batching passes", r["passed"], json.dumps(r["detail"])[:150])
    # a batch that genuinely straddles the visit boundary must be caught: take the last
    # window of visit 1 and the first window of visit 2 into a single batch
    crossed = [fake_run("sub-01", arm=a, sessions=("ses-1", "ses-2"), batch_sizes=sizes,
                        batch_size=bs4) for a in A.ARMS]
    for run in crossed:
        v1 = [w for w in run["window_rows"] if w["session"] == "ses-1"]
        v2 = [w for w in run["window_rows"] if w["session"] == "ses-2"]
        last1, first2 = v1[-1], v2[0]
        last1["batch_index"] = first2["batch_index"]  # now one batch holds both visits
    r = C.nc15_no_batch_crosses_a_visit_boundary(crossed)
    check("NC15 a batch straddling the visit boundary is caught", not r["passed"])
    # a silently padded final batch must be caught
    padded = [fake_run("sub-01", arm=a, sessions=("ses-1", "ses-2"), batch_sizes=sizes, batch_size=bs4)
              for a in A.ARMS]
    for run in padded:
        run["batch_size_profile"]["ses-1"] = [4, 4, 4]
    r = C.nc15_no_batch_crosses_a_visit_boundary(padded)
    check("NC15 silently padded final batch is caught", not r["passed"])
    # a truncated small visit must NOT be flagged (sub-04 has one 4-window visit)
    tiny = [fake_run("sub-01", arm=a, sessions=("ses-1", "ses-2"),
                     batch_sizes={"ses-1": [4], "ses-2": [32, 30]}, batch_size=32) for a in A.ARMS]
    r = C.nc15_no_batch_crosses_a_visit_boundary(tiny)
    check("NC15 a genuine 4-window visit passes (small sessions retained)", r["passed"],
          json.dumps(r["detail"])[:150])

    print("NC16/NC17 - Dropout mode distinguishes the two TENT arms")
    lit = [fake_run("sub-01", arm="tent_literal", dropout_active=True)]
    det = [fake_run("sub-01", arm="tent_det", dropout_active=False)]
    check("NC16 literal-with-dropout passes",
          C.nc16_tent_literal_keeps_dropout_train(lit)["passed"])
    check("NC16 literal-without-dropout is caught",
          not C.nc16_tent_literal_keeps_dropout_train(det)["passed"])
    check("NC17 det-without-dropout passes",
          C.nc17_tent_det_keeps_dropout_eval(det)["passed"])
    check("NC17 det-with-dropout is caught",
          not C.nc17_tent_det_keeps_dropout_eval(lit)["passed"])
    check("NC16 empty arm set is caught (a check must not pass vacuously)",
          not C.nc16_tent_literal_keeps_dropout_train(det)["passed"])

    print("NC18 - LITERAL vs DET differ only in Dropout")
    import torch as _t

    model = P.build_model_from_config(cfg)
    names = [f"{n}.{p}" for n, m in model.named_modules()
             if isinstance(m, (_t.nn.BatchNorm1d, _t.nn.BatchNorm2d))
             for p in ("weight", "bias")]
    audit = [{"name": m, "track_running_stats": False, "running_mean_is_none": True}
             for m in ("bnorm_temporal", "bnorm_1", "bnorm_2")]
    base = dict(trainable_names=names, n_trainable_tensors=len(names),
                n_trainable_scalars=80, norm_audit=audit, subject="sub-01", seed=0)
    lit_run = {**fake_run("sub-01", arm="tent_literal", dropout_active=True), **base,
               "dropout_audit": {"n_dropout_modules": 2, "dropout_any_training": True}}
    det_run = {**fake_run("sub-01", arm="tent_det", dropout_active=False), **base,
               "dropout_audit": {"n_dropout_modules": 2, "dropout_any_training": False}}
    r = C.nc18_literal_vs_det_differ_only_in_dropout([lit_run, det_run], cfg)
    check("NC18 genuine Dropout-only difference passes", r["passed"], json.dumps(r["detail"])[:160])
    bad_det = {**det_run, "n_trainable_scalars": 79}
    r = C.nc18_literal_vs_det_differ_only_in_dropout([lit_run, bad_det], cfg)
    check("NC18 a second (non-Dropout) difference is caught", not r["passed"])
    same_mode = {**det_run, "batch_rows": lit_run["batch_rows"],
                 "dropout_audit": {"n_dropout_modules": 2, "dropout_any_training": True}}
    r = C.nc18_literal_vs_det_differ_only_in_dropout([lit_run, same_mode], cfg)
    check("NC18 identical Dropout mode is caught", not r["passed"])

    print("NC19 - all four arms share identical geometry")
    pair = tuple(P.session_block_order_for("sub-01"))
    arms4 = [fake_run("sub-01", arm=a, sessions=pair,
                      batch_sizes={pair[0]: [4, 4], pair[1]: [4, 4]}) for a in A.ARMS]
    r = C.nc19_all_four_arms_identical_geometry(arms4)
    check("NC19 identical geometry passes", r["passed"], json.dumps(r["detail"])[:150])
    short = [dict(run) for run in arms4]
    short[-1] = {**short[-1],
                 "window_rows": short[-1]["window_rows"][:-1]}
    r = C.nc19_all_four_arms_identical_geometry(short)
    check("NC19 a differing window set is caught", not r["passed"])
    missing = arms4[:-1]
    r = C.nc19_all_four_arms_identical_geometry(missing)
    check("NC19 a missing arm is caught", not r["passed"])

    print("NC20-NC26 - literal scoring semantics and RNG convention (correction blocker)")
    import numpy as _np

    good_probe = lambda: (_np.array([[0.1, 0.9]]), _np.array([[0.1, 0.9]]), 0.3)
    bad_probe = lambda: (_np.array([[0.1, 0.9]]), _np.array([[0.2, 0.8]]), 0.3)
    check("NC20 identical scored/entropy logits pass",
          S.nc20_scored_logits_are_entropy_logits(good_probe)["passed"])
    check("NC20 a divergent scoring forward is caught",
          not S.nc20_scored_logits_are_entropy_logits(bad_probe)["passed"])

    check("NC20 real pipeline: one forward, identical logits",
          S.nc20_scored_logits_are_entropy_logits(
              lambda: _real_tent_probe())["passed"])
    check("NC21 real pipeline has no separate scoring forward",
          S.nc21_no_separate_scoring_forward()["passed"])
    # runtime guard: instrument the model and count actual forward invocations
    _real_tent_probe()
    real_calls = S.count_forwards("tent_literal", _real_tent_probe.model,
                                  [_real_tent_probe.x] * 4,
                                  seed_for_batch=lambda i: A.unit_rng_seed(
                                      0, "syn", "tent_literal", "metadata_order", i))
    check("NC21 runtime: exactly one forward per batch (not two)",
          S.nc21_no_separate_scoring_forward(
              observed_forward_calls={"actual": real_calls, "expected": 4})["passed"],
          f"observed {real_calls} forwards for 4 batches")
    check("NC21 runtime: a second forward per batch is caught",
          not S.nc21_no_separate_scoring_forward(
              observed_forward_calls={"actual": 8, "expected": 4})["passed"])
    check("NC21 injected second forward is caught",
          not S.nc21_no_separate_scoring_forward(source_text=(
              "def entropy_forward(arm, model, x):\n    logits = model(x)\n    return logits, 0\n"
              "# ---- BEGIN ADAPTATION REGION\n"
              "with torch.enable_grad():\n"
              "    logits, loss = entropy_forward(arm, model, x)\n"
              "    logits = model(x)\n"
              "# ---- END ADAPTATION REGION\n"))["passed"])
    check("NC21 a separate scoring tensor forward is caught",
          not S.nc21_no_separate_scoring_forward(source_text=(
              "def entropy_forward(arm, model, x):\n    logits = model(x)\n    return logits, 0\n"
              "# ---- BEGIN ADAPTATION REGION\n"
              "with torch.enable_grad():\n"
              "    logits, loss = entropy_forward(arm, model, x)\n"
              "    scored = model(x_scoring)\n"
              "# ---- END ADAPTATION REGION\n"))["passed"])

    pair = tuple(P.session_block_order_for("sub-01"))
    lit_run = fake_run("sub-01", arm="tent_literal", sessions=pair, dropout_active=True)
    det_run = fake_run("sub-01", arm="tent_det", sessions=pair, dropout_active=False)
    for run in (lit_run, det_run):
        run["scoring_semantics"] = {
            "single_pre_update_forward": True,
            "scored_logits_are_the_entropy_logits": True,
            "separate_scoring_forward": False,
            "dropout_active_in_scored_forward": run["arm"] == "tent_literal",
            "rng_convention_version": A.RNG_CONVENTION_VERSION,
            "rng_domain": A.RNG_DOMAIN,
        }
        run["n_trainable_scalars"] = 80
        run["n_trainable_tensors"] = 6
        run["affine_norm_initial"] = 9.0
        run["trainable_names"] = [f"bn{i}.{p}" for i in range(3) for p in ("weight", "bias")]
        for i, br in enumerate(run["batch_rows"]):
            br["batch_grad_norm"] = 0.01
            br["affine_drift_l2"] = 8.9e-3 * (i + 1) / len(run["batch_rows"])
    check("NC22 LITERAL scored forward has Dropout active",
          S.nc22_literal_scored_forward_has_dropout_active(lit_run)["passed"])
    check("NC22 LITERAL with Dropout off is caught",
          not S.nc22_literal_scored_forward_has_dropout_active(det_run)["passed"])
    check("NC23 DET scored forward has Dropout inactive",
          S.nc23_det_scored_forward_has_dropout_eval(det_run)["passed"])
    check("NC23 DET with Dropout active is caught",
          not S.nc23_det_scored_forward_has_dropout_eval(lit_run)["passed"])

    r = S.nc24_literal_vs_det_differ_only_in_dropout([lit_run, det_run])
    check("NC24 genuine Dropout-only difference passes", r["passed"],
          json.dumps(r["detail"])[:150])
    bad_det = copy.deepcopy(det_run)
    bad_det["n_trainable_scalars"] = 79
    r = S.nc24_literal_vs_det_differ_only_in_dropout([lit_run, bad_det])
    check("NC24 a second (non-Dropout) difference is caught", not r["passed"])
    same_mode = copy.deepcopy(det_run)
    same_mode["batch_rows"] = copy.deepcopy(lit_run["batch_rows"])
    r = S.nc24_literal_vs_det_differ_only_in_dropout([lit_run, same_mode])
    check("NC24 identical Dropout mode is caught", not r["passed"])
    r = S.nc24_literal_vs_det_differ_only_in_dropout([lit_run])
    check("NC24 a missing arm is caught", not r["passed"])

    check("NC25 RNG independent of execution order",
          S.nc25_rng_independent_of_execution_order(0, "sub-01", "tent_literal")["passed"])
    # inject: a seed function that depends on a mutable counter must be caught
    real_fn = A.unit_rng_seed
    state = {"n": 0}
    A.unit_rng_seed = lambda *a, **k: (state.__setitem__("n", state["n"] + 1), state["n"])[1]
    r = S.nc25_rng_independent_of_execution_order(0, "sub-01", "tent_literal")
    A.unit_rng_seed = real_fn
    check("NC25 a mutable-counter RNG is caught", not r["passed"])

    a = fake_run("sub-01", arm="tent_literal", sessions=pair)
    import copy as _copy  # noqa: E402

    b = _copy.deepcopy(a)
    check("NC26 replay reproduces the unit", S.nc26_literal_replay_reproduces_unit(a, b)["passed"])
    b["window_rows"][0]["p_positive"] = 0.12345
    check("NC26 a divergent replay is caught",
          not S.nc26_literal_replay_reproduces_unit(a, b)["passed"])

    print("NC27 - first-step drift is Adam-scaled (replaces a wrong 'drift == 0' check)")
    expected = A.PROTOCOL["lr"] * (80 ** 0.5)
    adam = fake_run("sub-01", arm="tent_literal", sessions=pair)
    adam["n_trainable_scalars"] = 80
    adam["n_trainable_tensors"] = 6
    adam["trainable_names"] = [f"bn{i}.{p}" for i in range(3) for p in ("weight", "bias")]
    adam["affine_norm_initial"] = 9.0
    for i, br in enumerate(adam["batch_rows"]):
        br["batch_grad_norm"] = 0.01
        br["affine_drift_l2"] = expected * (i + 1) / len(adam["batch_rows"])
    check("NC27 a genuine Adam first step passes",
          S.nc27_first_step_drift_is_adam_scaled(adam)["passed"],
          f"expected lr*sqrt(P)={expected:.3e}")
    zero = _copy.deepcopy(adam)
    for br in zero["batch_rows"]:
        br["affine_drift_l2"] = 0.0
    check("NC27 an arm that never updated is caught",
          not S.nc27_first_step_drift_is_adam_scaled(zero)["passed"])
    huge = _copy.deepcopy(adam)
    for br in huge["batch_rows"]:
        br["affine_drift_l2"] = 1e3
    check("NC27 a runaway first step is caught",
          not S.nc27_first_step_drift_is_adam_scaled(huge)["passed"])
    nograd = _copy.deepcopy(adam)
    nograd["batch_rows"][1]["batch_grad_norm"] = 0.0
    check("NC27 a batch with no gradient is caught",
          not S.nc27_first_step_drift_is_adam_scaled(nograd)["passed"])
    wrongarm = _copy.deepcopy(adam)
    wrongarm["arm"] = "bn_only"
    check("NC27 a non-TENT arm is caught",
          not S.nc27_first_step_drift_is_adam_scaled(wrongarm)["passed"])

    n = len(RESULTS)
    ok = sum(1 for _, p in RESULTS if p)
    print(f"\n{n} controls exercised, {ok}/{n} bite correctly")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
