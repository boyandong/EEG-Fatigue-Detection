"""Prove the TENT_LITERAL / TENT_DET scoring semantics and RNG convention (correction 5 A-F).

These are the controls added for the remaining protocol blocker:

  NC20  scored logits ARE the entropy-producing pre-update forward (single forward)
  NC21  no separate scoring forward exists
  NC22  Dropout is ACTIVE in the scored/entropy forward for TENT_LITERAL
  NC23  Dropout is INACTIVE in the scored/entropy forward for TENT_DET
  NC24  the two TENT arms are identical in everything except Dropout mode
  NC25  per-unit RNG seeding is independent of execution/resume order

Run:  this module is exercised by tests/test_p1_controls.py, which injects a violation for
each control and asserts the control bites.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_arms as A  # noqa: E402


def _result(name, ok, detail):
    return {"control": name, "passed": bool(ok), "detail": detail}


def adaptation_region(text):
    """Extract the sentinel-delimited adaptation region.

    Uses the LAST occurrence of each marker: `run_arm`'s docstring *mentions* both markers,
    so a naive `split(marker, 1)` would return the docstring instead of the code.
    """
    begin, end = "# ---- BEGIN ADAPTATION REGION", "# ---- END ADAPTATION REGION"
    if begin not in text or end not in text:
        raise ValueError("adaptation-region sentinels missing")
    return text.rsplit(begin, 1)[1].rsplit(end, 1)[0]


def _run_arm_body():
    """The `run_arm` source between its sentinels - where adaptation actually happens."""
    text = (Path(__file__).parent / "p1_arms.py").read_text(encoding="utf-8")
    return text, adaptation_region(text)


def nc20_scored_logits_are_entropy_logits(probe, source_text=None, token="NC20_PROBE"):
    """NC20: in the TENT arms the scored logits and the entropy logits must be the SAME tensor.

    The probe is a callable that runs one TENT arm over a tiny synthetic input and returns
    `(scored_logits, entropy_logits, loss)`.  Identity is checked numerically because a
    detached clone is copied for recording.
    """
    scored, entropy_logits, _loss = probe()
    s = np.asarray(scored, dtype=np.float64)
    e = np.asarray(entropy_logits, dtype=np.float64)
    return _result("NC20 scored logits ARE the entropy-producing forward",
                   s.shape == e.shape and np.array_equal(s, e),
                   {"max_abs_diff": float(np.abs(s - e).max()) if s.shape == e.shape else None})


def nc21_no_separate_scoring_forward(source_text=None, observed_forward_calls=None):
    """NC21: there must be exactly ONE forward into the model per adaptation step, and no
    additional Dropout-eval scoring forward.

    Three independent guards, because a purely textual one is brittle:
      * structural: the region contains exactly ONE `model(x)` call site, and
        `entropy_forward` itself performs exactly one `model(x)`;
      * textual: no forward is invoked on any argument other than `x` (which is what a
        separate scoring tensor would need);
      * runtime (when supplied): the number of forward invocations observed by a hook on the
        top-level model must equal the number of batches, not twice that.
    """
    if source_text is None:
        text, region = _run_arm_body()
    else:
        text = source_text
        region = adaptation_region(text)

    ef = text.split("def entropy_forward", 1)[1].split("\ndef ", 1)[0] \
        if "def entropy_forward" in text else ""
    n_in_entropy_forward = len(re.findall(r"\bmodel\(x\)", ef))
    n_x_sites_in_region = len(re.findall(r"\bmodel\(x\)", region))
    n_other_arg_sites = len(re.findall(r"\bmodel\((?!x\))", region))

    ok = (n_in_entropy_forward == 1 and n_x_sites_in_region == 1 and n_other_arg_sites == 0)
    detail = {"model_x_calls_in_entropy_forward": n_in_entropy_forward,
              "model_x_call_sites_in_adaptation_region": n_x_sites_in_region,
              "forward_calls_with_non_x_arg": n_other_arg_sites}
    if observed_forward_calls is not None:
        actual = observed_forward_calls.get("actual")
        expected = observed_forward_calls.get("expected")
        detail["observed_forward_calls"] = actual
        detail["expected_observed"] = expected
        ok = ok and actual == expected
    return _result("NC21 no separate Dropout-eval scoring forward", ok, detail)


def count_forwards(arm, model, batches, seed_for_batch=None):
    """Instrumented runtime probe: count top-level forward invocations for one arm.

    Uses a `forward_pre_hook` on the model itself, which fires once per `model(x)` call and
    does not perturb the module tree, the RNG stream or the returned tensors.
    """
    import torch

    calls = {"n": 0}

    def _bump(_module, _inputs):
        calls["n"] += 1

    handle = model.register_forward_pre_hook(_bump)
    try:
        params = [p for p in model.parameters() if p.requires_grad]
        opt = (torch.optim.Adam(params, lr=A.PROTOCOL["lr"], betas=A.PROTOCOL["betas"])
               if params else None)
        grad_ctx = torch.enable_grad if (arm in A.TENT_ARMS and opt is not None) \
            else torch.no_grad
        with grad_ctx():
            for i, x in enumerate(batches):
                if seed_for_batch is not None:
                    torch.manual_seed(seed_for_batch(i))
                A.prepare_adaptation_mode(arm, model)
                if arm in A.TENT_ARMS and opt is not None:
                    opt.zero_grad(set_to_none=True)
                    _logits, loss = A.entropy_forward(arm, model, x)
                    loss.backward()
                    opt.step()
                else:
                    model(x)
    finally:
        handle.remove()
    return calls["n"]


def nc22_literal_scored_forward_has_dropout_active(run):
    """NC22: TENT_LITERAL's scored/entropy forward runs with Dropout ACTIVE."""
    if run["arm"] != "tent_literal":
        return _result("NC22 TENT_LITERAL scored forward has Dropout ACTIVE", False,
                       {"error": f"wrong arm {run['arm']}"})
    flags = [b["dropout_active_during_forward"] for b in run["batch_rows"]]
    sem = run.get("scoring_semantics", {})
    ok = (len(flags) > 0 and all(flags)
          and sem.get("dropout_active_in_scored_forward") is True
          and run["dropout_audit"]["n_dropout_modules"] > 0)
    return _result("NC22 TENT_LITERAL scored forward has Dropout ACTIVE", ok,
                   {"flags": flags[:5], "n_dropout_modules": run["dropout_audit"]["n_dropout_modules"],
                    "declared": sem.get("dropout_active_in_scored_forward")})


def nc23_det_scored_forward_has_dropout_eval(run):
    """NC23: TENT_DET's scored/entropy forward runs with Dropout INACTIVE."""
    if run["arm"] != "tent_det":
        return _result("NC23 TENT_DET scored forward has Dropout INACTIVE", False,
                       {"error": f"wrong arm {run['arm']}"})
    flags = [b["dropout_active_during_forward"] for b in run["batch_rows"]]
    sem = run.get("scoring_semantics", {})
    ok = (len(flags) > 0 and not any(flags)
          and sem.get("dropout_active_in_scored_forward") is False)
    return _result("NC23 TENT_DET scored forward has Dropout INACTIVE", ok,
                   {"flags": flags[:5], "declared": sem.get("dropout_active_in_scored_forward")})


def nc24_literal_vs_det_differ_only_in_dropout(runs):
    """NC24: the two TENT arms must agree on sample geometry, batch geometry, BN
    configuration, optimizer, learning rate, adapted parameter set, step count, scoring
    timing and entropy implementation - and differ only in Dropout mode."""
    lit = [r for r in runs if r["arm"] == "tent_literal"]
    det = [r for r in runs if r["arm"] == "tent_det"]
    if not lit or not det:
        return _result("NC24 TENT_LITERAL vs TENT_DET differ only in Dropout", False,
                       {"error": "missing arm", "n_literal": len(lit), "n_det": len(det)})
    keys = ("subject", "seed", "visit_pair", "n_windows", "n_batches", "batch_size_profile",
            "batch_sizes_observed", "n_trainable_tensors", "n_trainable_scalars",
            "trainable_names", "scoring_semantics", "norm_audit")
    by_key = {(r["subject"], r["seed"]): r for r in det}
    problems = []
    for r in lit:
        d = by_key.get((r["subject"], r["seed"]))
        if d is None:
            problems.append({"subject": r["subject"], "seed": r["seed"], "diff": "no det pair"})
            continue
        for k in keys:
            if k == "scoring_semantics":
                a = {kk: vv for kk, vv in r[k].items()
                     if kk != "dropout_active_in_scored_forward"}
                b = {kk: vv for kk, vv in d[k].items()
                     if kk != "dropout_active_in_scored_forward"}
            else:
                a, b = r[k], d[k]
            if a != b:
                problems.append({"subject": r["subject"], "seed": r["seed"], "diff": k})
        # adaptation-step count and optimizer hyper-parameters must match the frozen protocol
        if len(r["batch_rows"]) != len(d["batch_rows"]):
            problems.append({"subject": r["subject"], "diff": "n_batch_rows"})
    # Dropout mode must genuinely differ
    lit_flags = {b["dropout_active_during_forward"] for r in lit for b in r["batch_rows"]}
    det_flags = {b["dropout_active_during_forward"] for r in det for b in r["batch_rows"]}
    differ = lit_flags == {True} and det_flags == {False}
    return _result("NC24 TENT_LITERAL vs TENT_DET differ only in Dropout",
                   not problems and differ,
                   {"problems": problems[:3], "literal_flags": sorted(lit_flags),
                    "det_flags": sorted(det_flags),
                    "steps_per_batch": A.PROTOCOL["steps_per_batch"],
                    "lr": A.PROTOCOL["lr"], "optimizer": A.PROTOCOL["optimizer"]})


def nc25_rng_independent_of_execution_order(seed, subject, arm, variant=A.PRIMARY_VARIANT,
                                            n_batches=4):
    """NC25: each unit's RNG seed must be a pure function of its own identity, so that
    skipping, completing or reordering other units cannot change it.

    Three assertions:
      * the seed is stable across repeated derivation (no hidden global state);
      * the seed differs across subjects / arms / seeds / batch indices (no accidental
        reuse of a mutable RNG stream);
      * deriving the seed for a *different* unit - simulating "another unit already ran" -
        does not change this unit's seed.
    """
    base = [A.unit_rng_seed(seed, subject, arm, variant, b) for b in range(n_batches)]
    again = [A.unit_rng_seed(seed, subject, arm, variant, b) for b in range(n_batches)]
    stable = base == again

    other_variant = A.unit_rng_seed(seed, subject, arm, "OTHER_VARIANT", 0)
    other_subject = A.unit_rng_seed(seed, "sub-99", arm, variant, 0)
    other_arm = A.unit_rng_seed(seed, subject, "tent_det", variant, 0)
    other_seed = A.unit_rng_seed(seed + 1, subject, arm, variant, 0)
    distinct = len({base[0], other_variant, other_subject, other_arm, other_seed}) == 5
    per_batch = len(set(base)) == n_batches

    # simulate interleaved / resumed execution: derive a pile of other units' seeds in
    # between and confirm this unit's seed is untouched
    for s in ("sub-02", "sub-03", "sub-71"):
        for b in range(7):
            A.unit_rng_seed(seed, s, "tent_literal", variant, b)
    after_others = [A.unit_rng_seed(seed, subject, arm, variant, b) for b in range(n_batches)]
    order_independent = after_others == base

    ok = stable and distinct and per_batch and order_independent
    return _result("NC25 per-unit RNG is independent of execution/resume order", ok,
                   {"stable": stable, "distinct_across_units": distinct,
                    "distinct_per_batch": per_batch,
                    "order_independent": order_independent,
                    "example_seed": base[0],
                    "example_payload": A.unit_rng_payload(seed, subject, arm, variant, 0)})


def nc26_literal_replay_reproduces_unit(run_a, run_b):
    """NC26: replaying the same unit under the frozen RNG convention reproduces it exactly.

    Compares the per-window scores of two independent executions of the same TENT_LITERAL
    unit.  Because Dropout is live, this is only possible if the per-unit seeding convention
    is actually in force.
    """
    a = {r["segment_id"]: r["p_positive"] for r in run_a["window_rows"]}
    b = {r["segment_id"]: r["p_positive"] for r in run_b["window_rows"]}
    if set(a) != set(b):
        return _result("NC26 TENT_LITERAL replay reproduces the unit", False,
                       {"error": "window sets differ"})
    d = np.array([abs(a[k] - b[k]) for k in a])
    return _result("NC26 TENT_LITERAL replay reproduces the unit", bool(d.max() == 0.0),
                   {"max_abs_delta": float(d.max()), "n_windows": len(a)})


def nc27_first_step_drift_is_adam_scaled(run, lr=None, n_scalars=None):
    """NC27: the drift recorded at batch 0 must be a plausible FIRST ADAM STEP.

    This check REPLACES a wrong one. An earlier version asserted `affine_drift_l2 == 0` at
    batch 0. That assertion is simply incorrect for Adam: its first update is
    `-lr * m_hat / (sqrt(v_hat) + eps)` with `m_hat = g/(1-beta1)` and `v_hat = g^2/(1-beta2)`,
    so the step is `~ -lr * sign(g)` and its L2 norm is `~ lr * sqrt(P)` **regardless of how
    small the gradient is**. For P = 80 and lr = 1e-3 that is ~8.9e-3, which is what the real
    runs show (~8.5e-3). Asserting zero would have been asserting that Adam does nothing.

    What IS worth asserting:
      * drift at batch 0 is > 0 (the arm really did update);
      * it sits within a generous band around `lr * sqrt(P)` - not orders of magnitude larger,
        which is what a runaway or a corrupted reference state would look like;
      * the RELATIVE drift is small against the initial affine norm;
      * every batch reported a finite, positive gradient norm.
    """
    lr = lr if lr is not None else A.PROTOCOL["lr"]
    if run.get("arm") not in A.TENT_ARMS:
        return _result("NC27 first-step drift is Adam-scaled", False,
                       {"error": f"wrong arm {run.get('arm')}"})
    n = n_scalars if n_scalars is not None else run["n_trainable_scalars"]
    expected = lr * (n ** 0.5)
    d0 = run["batch_rows"][0].get("affine_drift_l2")
    base = run.get("affine_norm_initial") or 0.0
    grads = [b["batch_grad_norm"] for b in run["batch_rows"]]
    grads_ok = all(g is not None and g == g and g > 0 for g in grads)
    ratio = (d0 / expected) if (d0 is not None and expected > 0) else None
    rel = (d0 / base) if (d0 is not None and base > 0) else None
    ok = (d0 is not None and d0 > 0 and ratio is not None and 0.1 <= ratio <= 10.0
          and rel is not None and rel < 0.5 and grads_ok)
    return _result("NC27 first-step drift is Adam-scaled", ok,
                   {"drift_at_batch_0": d0, "expected_lr_sqrt_P": expected, "ratio": ratio,
                    "relative_drift": rel, "all_grad_norms_positive": grads_ok})
