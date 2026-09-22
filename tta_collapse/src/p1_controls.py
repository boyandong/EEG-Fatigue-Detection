"""Phase 1 negative controls NC1-NC13 (prompt §26).

Each control must be shown to BITE: the function returns (passed, detail).  A control
that cannot fail is not a control, so every check here is exercised against a
deliberately injected violation in `tests/test_p1_controls.py`.

Nothing here trains or adapts anything: the controls are static/dynamic assertions over
recorded structures.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_arms as A  # noqa: E402


def adaptation_region(text):
    """The sentinel-delimited adaptation region, using the LAST occurrence of each marker.

    `run_arm`'s docstring mentions both markers, so `split(marker, 1)` would return the
    docstring rather than the code - a trap that silently made a control vacuous.
    """
    begin, end = "# ---- BEGIN ADAPTATION REGION", "# ---- END ADAPTATION REGION"
    if begin not in text or end not in text:
        raise ValueError("adaptation-region sentinels missing")
    return text.rsplit(begin, 1)[1].rsplit(end, 1)[0]


def _p1_arms_source():
    return (Path(__file__).parent / "p1_arms.py").read_text(encoding="utf-8")


def _result(name, ok, detail):
    return {"control": name, "passed": bool(ok), "detail": detail}


# ---------------------------------------------------------------- static controls
def nc1_no_labels_inside_adaptation_region(source_text=None):
    """NC1: the sentinel-delimited ADAPTATION REGION must contain no target label.

    The region is where data reaches the model and where parameters move; the post-hoc
    evaluator lives outside it and is the only place labels are allowed.
    """
    text = source_text if source_text is not None else _p1_arms_source()
    try:
        region = adaptation_region(text)
    except ValueError as e:
        return _result("NC1 adaptation region contains no target label", False, {"error": str(e)})
    offenders = []
    for ln in region.splitlines():
        code = ln.split("#", 1)[0]
        if '"label"' in code or "'label'" in code or "y_true" in code:
            offenders.append(ln.strip())
    return _result("NC1 adaptation region contains no target label", not offenders,
                   {"label_reads": offenders, "region_lines": len(region.splitlines())})


def nc2_checkpoint_mapping(subject, ckpt_dir, splits):
    """NC2: the checkpoint used must be the fold whose TEST subject is `subject`."""
    fold = next((f for f in splits["folds"] if subject in f["test"]), None)
    ok = fold is not None and fold["test"] == [subject] and f"eegnet/{subject}" in str(ckpt_dir).replace("\\", "/")
    return _result("NC2 held-out checkpoint mapping", ok,
                   {"subject": subject, "fold_test": None if fold is None else fold["test"],
                    "ckpt_dir": str(ckpt_dir)})


def nc3_no_cross_subject_leakage(arm_results, by_subject_state_hashes):
    """NC3: every episode must start from that subject's own source state."""
    bad = []
    for r in arm_results:
        expect = by_subject_state_hashes.get(r["subject"])
        if expect is None or r["source_meta"]["state_sha256"] != expect:
            bad.append(r["subject"])
    return _result("NC3 no adaptation state crosses a subject boundary", not bad,
                   {"subjects_with_wrong_start_state": bad})


def nc4_source_arm_frozen(run):
    """NC4: SOURCE must have no trainable parameter and an unchanged state hash."""
    ok = (run["n_trainable_tensors"] == 0
          and run["trainable_names"] == []
          and run.get("state_unchanged", True))
    return _result("NC4 SOURCE arm performs no optimizer step", ok,
                   {"n_trainable": run["n_trainable_tensors"], "names": run["trainable_names"],
                    "state_unchanged": run.get("state_unchanged")})


def nc5_bn_only_no_gradient(run):
    """NC5: BN_ONLY must have no trainable parameter, no optimizer and zero grad norm."""
    grads = [r["batch_grad_norm"] for r in run["batch_rows"]]
    finite_nonzero = [g for g in grads if g is not None and np.isfinite(g) and g > 0]
    ok = (run["n_trainable_tensors"] == 0 and run["trainable_names"] == []
          and not finite_nonzero
          and not run.get("dropout_audit", {}).get("dropout_any_training", False))
    return _result("NC5 BN_ONLY produces no gradient update and keeps Dropout off", ok,
                   {"n_trainable": run["n_trainable_tensors"], "nonzero_grad_batches": len(finite_nonzero),
                    "dropout_active": run.get("dropout_audit", {}).get("dropout_any_training")})


def nc6_tent_updates_only_norm(run, cfg):
    """NC6: a TENT arm's trainable set must be exactly the BatchNorm affine weight/bias
    tensors - nothing else, and not a subset."""
    import torch

    expected = set()
    model = A.P.build_model_from_config(cfg)
    for name, m in model.named_modules():
        if isinstance(m, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)):
            expected.add(f"{name}.weight")
            expected.add(f"{name}.bias")
    got = set(run["trainable_names"])
    return _result("NC6 TENT updates only normalization affine parameters",
                   got == expected and len(got) > 0,
                   {"missing": sorted(expected - got), "extra": sorted(got - expected),
                    "n_trainable_scalars": run["n_trainable_scalars"]})


def nc7_stream_not_shuffled(stream, manifest):
    """NC7: the stream must not be a hash/random permutation - it must be epoch-ordered."""
    problems = []
    for block_session in {b["session"] for b in stream}:
        idx = [int(r["source_epoch_index"]) for b in stream if b["session"] == block_session for r in b["rows"]]
        if idx != sorted(idx):
            problems.append(block_session)
    return _result("NC7 target stream is not randomly shuffled", not problems, {"unordered_blocks": problems})


def nc8_temporal_order_preserved(stream):
    """NC8: inside each block, `source_epoch_index` must be strictly ascending.

    Strict temporal order is the guarantee, not contiguity: a retained recording may have
    skipped epochs (frozen QC exclusions), which are missing windows rather than reorderings.
    """
    problems = []
    for session in {b["session"] for b in stream}:
        idx = [int(r["source_epoch_index"]) for b in stream if b["session"] == session
               for r in b["rows"]]
        if idx != sorted(idx):
            problems.append({"session": session, "reason": "not ascending"})
        elif len(idx) != len(set(idx)):
            problems.append({"session": session, "reason": "duplicate epoch"})
    return _result("NC8 window temporal order preserved (strictly ascending epochs)",
                   not problems, {"problems": problems})


def nc9_identical_sample_sets(arms):
    """NC9: all arms must score exactly the same segment set."""
    sets = {arm: set(r["scores"]) for arm, r in arms.items()}
    ids = list(sets.values())
    ok = all(s == ids[0] for s in ids)
    return _result("NC9 all arms use an identical window set", ok,
                   {arm: len(s) for arm, s in sets.items()})


def nc10_identical_batch_boundaries(arms):
    """NC10: all arms must cut identical batch boundaries."""
    sig = {}
    for arm, r in arms.items():
        sig[arm] = [(b["session"], b["batch_n"], b["batch_index"]) for b in r["batch_rows"]]
    vals = list(sig.values())
    ok = all(v == vals[0] for v in vals)
    return _result("NC10 all arms use identical batch boundaries", ok,
                   {arm: len(v) for arm, v in sig.items()})


def nc11_no_future_batches(run):
    """NC11: window `stream_position` must be strictly increasing and each batch's rows
    must all precede the next batch's rows (no look-ahead)."""
    rows = run["window_rows"]
    pos = [r["stream_position"] for r in rows]
    ok = pos == list(range(len(pos)))
    # batch index must be monotone non-decreasing along stream position
    bidx = [r["batch_index"] for r in rows]
    ok = ok and bidx == sorted(bidx)
    return _result("NC11 adaptation consumes no future batch", ok,
                   {"n_windows": len(rows), "monotone_position": pos == list(range(len(pos))),
                    "monotone_batch": bidx == sorted(bidx)})


def nc12_subject_level_aggregation(group_stats):
    """NC12: group statistics must be computed over subjects, not over windows."""
    n_subjects = group_stats["n_subjects_reported"]
    ok = (group_stats["unit"] == "subject"
          and group_stats["stat"]["n"] == n_subjects
          and group_stats["stat"]["n"] != group_stats.get("n_windows", -1))
    return _result("NC12 aggregation unit is the subject", ok,
                   {"unit": group_stats["unit"], "stat_n": group_stats["stat"]["n"],
                    "n_subjects": n_subjects, "n_windows": group_stats.get("n_windows")})


def nc13_session_label_not_model_input(run, source_text=None):
    """NC13: condition/session identity must never reach the model tensor."""
    text = source_text if source_text is not None else _p1_arms_source()
    try:
        region = adaptation_region(text)
    except ValueError as e:
        return _result("NC13 session/condition label is not a model input", False, {"error": str(e)})
    offenders = [ln.strip() for ln in region.splitlines()
                 if "session" in ln.split("#", 1)[0]
                 and ("torch.from_numpy" in ln or "model(" in ln or "torch.cat" in ln)]
    return _result("NC13 session/condition label is not a model input", not offenders,
                   {"offending_lines": offenders})


# ------------------------------------------------- controls added by the pre-result corrections
def nc14_session_order_governs_visit_order(runs, manifest, clock_columns):
    """NC14: cross-visit order must follow `SessionOrder`, never the clock-time columns.

    Three independent assertions:
      a) every run's block sequence equals its subject's authoritative visit pair;
      b) the clock-time columns are NOT usable as an orderer (they disagree with
         `SessionOrder` for a large fraction of participants - they are deliberately
         time-of-day-matched across visits, so they cannot encode visit order);
      c) no code path reads a clock-time column to order a stream.
    """
    import p1_common as P  # local import keeps this module import-light

    bad_order = []
    for run in runs:
        expect = list(A.visit_pair(run["subject"]))
        got = []
        for b in run["batch_rows"]:
            if b["session"] not in got:
                got.append(b["session"])
        if got != expect:
            bad_order.append({"subject": run["subject"], "expected": expect, "got": got})

    order = P.load_session_order()
    disagree = 0
    comparable = 0
    for pid, level in order.items():
        ns, sd = clock_columns.get(pid, (None, None))
        if level not in P.SESSION_ORDER_LEVELS or ns is None or sd is None:
            continue
        comparable += 1
        clock_says = "NS->SD" if ns < sd else "SD->NS"
        if clock_says != level:
            disagree += 1

    text = _p1_arms_source()
    try:
        region = adaptation_region(text)
    except ValueError:
        region = ""
    clock_reads = [ln.strip() for ln in region.splitlines()
                   if "SamplingTime" in ln or "clock" in ln.lower()]
    # and the clock columns must not be consulted when building the stream either
    stream_fn = text.split("def build_stream", 1)[1].split("\ndef ", 1)[0]
    clock_in_stream = [ln.strip() for ln in stream_fn.splitlines()
                       if "SamplingTime" in ln or "clock" in ln.lower()]

    # The clock set we are handed is only used to DEMONSTRATE non-informativeness; the
    # ordering verdict must be independent of it.  That independence is the real assertion.
    ok = (not bad_order and disagree > 0 and not clock_reads and not clock_in_stream)
    return _result("NC14 SessionOrder (not clock time) governs cross-visit ordering", ok,
                   {"wrong_block_order": bad_order,
                    "clock_vs_SessionOrder_disagreements": f"{disagree}/{comparable}",
                    "clock_reads_in_adaptation": clock_reads,
                    "clock_reads_in_build_stream": clock_in_stream})


def nc15_no_batch_crosses_a_visit_boundary(runs, batch_size=None):
    """NC15: no batch may mix two sessions, and the trailing batch keeps its real size.

    The expected trailing size uses the run's own declared batch size (defaulting to the
    frozen protocol value), so the check is meaningful for both the real runs and the
    small synthetic fixtures.
    """
    bs_default = batch_size or A.PROTOCOL["batch_size"]
    bad_mixed = []
    bad_padding = []
    for run in runs:
        bs = int(run.get("batch_size", bs_default))
        sessions_per_batch = {}
        for w in run["window_rows"]:
            sessions_per_batch.setdefault(w["batch_index"], set()).add(w["session"])
        for bi, ss in sessions_per_batch.items():
            if len(ss) != 1:
                bad_mixed.append({"subject": run["subject"], "arm": run["arm"], "batch": bi,
                                  "sessions": sorted(ss)})
        # every visit's final batch must have that visit's remainder size, never a full batch
        for session, sizes in run["batch_size_profile"].items():
            span = max(b["block_span"] for b in run["batch_rows"] if b["session"] == session)
            expect_last = span % bs or min(bs, span)
            if sizes[-1] != expect_last:
                bad_padding.append({"subject": run["subject"], "arm": run["arm"],
                                    "session": session, "sizes": list(sizes),
                                    "expected_last": expect_last, "span": span, "batch_size": bs})
        # and the declared profile must agree with the recorded window rows
        for session, sizes in run["batch_size_profile"].items():
            mism = [b["batch_index"] for b in run["batch_rows"] if b["session"] == session
                    and b["batch_n"] != len([w for w in run["window_rows"]
                                             if w["batch_index"] == b["batch_index"]])]
            if mism:
                bad_padding.append({"subject": run["subject"], "session": session,
                                    "batch_n_mismatch_at": mism})
    ok = not bad_mixed and not bad_padding
    return _result("NC15 batches never cross a visit boundary and keep true final size", ok,
                   {"mixed_batches": bad_mixed[:3], "size_problems": bad_padding[:3]})


def nc16_tent_literal_keeps_dropout_train(runs):
    """NC16: TENT_LITERAL's Dropout must be ACTIVE for the scored/entropy forward."""
    checked, bad = 0, []
    for run in runs:
        if run["arm"] != "tent_literal":
            continue
        checked += 1
        flags = [b["dropout_active_during_forward"] for b in run["batch_rows"]]
        if not flags or not all(flags):
            bad.append({"subject": run["subject"], "flags": flags[:5],
                        "n_dropout_modules": run["dropout_audit"]["n_dropout_modules"]})
    return _result("NC16 TENT_LITERAL runs with Dropout active", checked > 0 and not bad,
                   {"runs_checked": checked, "violations": bad[:3]})


def nc17_tent_det_keeps_dropout_eval(runs):
    """NC17: TENT_DET's Dropout must be INACTIVE for the scored/entropy forward."""
    checked, bad = 0, []
    for run in runs:
        if run["arm"] != "tent_det":
            continue
        checked += 1
        flags = [b["dropout_active_during_forward"] for b in run["batch_rows"]]
        if any(flags):
            bad.append({"subject": run["subject"], "n_active_batches": sum(bool(f) for f in flags)})
    return _result("NC17 TENT_DET runs with Dropout inactive", checked > 0 and not bad,
                   {"runs_checked": checked, "violations": bad[:3]})


def nc18_literal_vs_det_differ_only_in_dropout(runs, cfg):
    """NC18: the ONLY intended semantic difference between TENT_LITERAL and TENT_DET is
    Dropout mode.  Everything else the arms declare must be identical."""
    import torch

    exp = {}
    for arm in ("tent_literal", "tent_det"):
        rs = [r for r in runs if r["arm"] == arm]
        if not rs:
            return _result("NC18 TENT_LITERAL vs TENT_DET differ only in Dropout", False,
                           {"error": f"no {arm} runs"})
        exp[arm] = {
            "n_trainable_tensors": {r["n_trainable_tensors"] for r in rs},
            "n_trainable_scalars": {r["n_trainable_scalars"] for r in rs},
            "trainable_names": {tuple(sorted(r["trainable_names"])) for r in rs},
            "norm_layers": {(m["name"], m["track_running_stats"], m["running_mean_is_none"])
                            for r in rs for m in r["norm_audit"]},
            "n_dropout_modules": {r["dropout_audit"]["n_dropout_modules"] for r in rs},
        }
    same = all(exp["tent_literal"][k] == exp["tent_det"][k] for k in
               ("n_trainable_tensors", "n_trainable_scalars", "trainable_names",
                "norm_layers", "n_dropout_modules"))
    # dropout mode must actually differ
    lit = {b["dropout_active_during_forward"] for r in runs if r["arm"] == "tent_literal"
           for b in r["batch_rows"]}
    det = {b["dropout_active_during_forward"] for r in runs if r["arm"] == "tent_det"
           for b in r["batch_rows"]}
    differ = lit == {True} and det == {False}
    return _result("NC18 TENT_LITERAL vs TENT_DET differ only in Dropout", same and differ,
                   {"identical_fields": same, "literal_dropout_flags": sorted(lit),
                    "det_dropout_flags": sorted(det)})


def nc19_all_four_arms_identical_geometry(runs):
    """NC19: all four arms must share subjects, windows, visit boundaries and batch
    boundaries for each (subject, seed)."""
    from collections import defaultdict

    groups = defaultdict(dict)
    for run in runs:
        groups[(run["subject"], run["seed"])][run["arm"]] = run
    problems = []
    for key, per_arm in groups.items():
        if set(per_arm) != set(A.ARMS):
            problems.append({"key": key, "missing_arms": sorted(set(A.ARMS) - set(per_arm))})
            continue
        ref = per_arm["source"]
        ref_ids = sorted((w["segment_id"], w["stream_position"], w["session"])
                         for w in ref["window_rows"])
        ref_batches = [(b["session"], b["batch_index"], b["batch_n"]) for b in ref["batch_rows"]]
        ref_order = ref["visit_pair"]
        for arm, run in per_arm.items():
            ids = sorted((w["segment_id"], w["stream_position"], w["session"])
                         for w in run["window_rows"])
            batches = [(b["session"], b["batch_index"], b["batch_n"]) for b in run["batch_rows"]]
            if ids != ref_ids:
                problems.append({"key": key, "arm": arm, "diff": "window set/order"})
            if batches != ref_batches:
                problems.append({"key": key, "arm": arm, "diff": "batch boundaries"})
            if run["visit_pair"] != ref_order:
                problems.append({"key": key, "arm": arm, "diff": "visit pair"})
    return _result("NC19 all four arms share identical geometry", not problems,
                   {"groups_checked": len(groups), "problems": problems[:3]})
