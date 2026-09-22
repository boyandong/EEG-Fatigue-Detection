"""Phase 1 arm runner: SOURCE / BN_ONLY / TENT under one frozen episodic protocol.

Frozen decisions (do not edit without a new specification):

* episodic **per subject** (prompt §9): parameters, BatchNorm state and optimizer state
  are taken from the held-out subject's own frozen source checkpoint at episode start
  and discarded at episode end.  No adaptation crosses a subject boundary.
* within a subject, the two recordings are streamed as **session blocks** in a frozen
  order (prompt §10).  Within each recording, windows are in true chronological order
  (legacy `source_epoch_index`, verified contiguous 0..k and monotone in file order).
* batches are cut **within a session block only** - never across a block boundary -
  so batch-statistic health is not confounded by an NS/SD splice.
* batch boundaries depend on `len(rows)` and `batch_size` **only**, hence are identical
  in all three arms by construction.
* prequential semantics (prompt §12): for each incoming batch, forward -> record
  prediction -> entropy objective -> backward -> optimizer step -> next batch.
  This is exactly the official reference's ordering (`cifar10c.py` -> `clean_accuracy`
  does `output = model(x)`; `tent.forward` returns the outputs of the *pre-update* pass).
* labels are never read inside an arm; `label` is used only by the post-hoc evaluator.
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_common as P  # noqa: E402

ARMS = ("source", "bn_only", "tent_literal", "tent_det")
TENT_ARMS = ("tent_literal", "tent_det")
BATCH_STAT_ARMS = ("bn_only", "tent_literal", "tent_det")

# Frozen canonical TENT optimization hyper-parameters (prompt §8).  Source: official
# `conf.py` defaults / `cfgs/tent.yaml` (Adam, lr 1e-3, beta1 0.9, wd 0, 1 step/batch).
PROTOCOL = {
    "adaptation": "episodic_per_subject",
    "batch_size": 32,
    "optimizer": "Adam",
    "lr": 1e-3,
    "betas": (0.9, 0.999),
    "weight_decay": 0.0,
    "steps_per_batch": 1,
    "non_norm_modules_mode": "train_for_tent_literal / eval_for_tent_det",
}

# PRIMARY stream = the subject's authoritative visit order recorded in the release metadata.
PRIMARY_VARIANT = "metadata_order"
# PARKED order diagnostics (prompt correction 1: not run in the primary experiment).
PARKED_VARIANTS = ("NS_then_SD", "SD_then_NS")


# --------------------------------------------------------------------------- stream
def visit_pair(subject, session_order=None):
    """The subject's ('first_visit', 'second_visit') session ids, from `SessionOrder`."""
    return P.session_block_order_for(subject, session_order)


def build_stream(manifest, subject, session_block_order=None, batch_size=None,
                 session_order=None):
    """Deterministic target stream for one subject.

    The two visits are ordered by the subject's authoritative `SessionOrder` metadata
    (PRIMARY).  `NS_then_SD` / `SD_then_NS` remain available only as PARKED order
    diagnostics and are never used by the primary experiment.

    Two-level temporal structure:
      * the STREAM is a two-visit blocked sequence (visits separated by 7 days - 1 month,
        so it is emphatically NOT a continuous real-world stream);
      * WITHIN each visit, windows run in true chronological order.

    Batches are cut inside a visit only: a visit's trailing incomplete batch keeps its
    actual size and is never padded from the next visit.
    """
    bs = batch_size or PROTOCOL["batch_size"]
    # `PRIMARY_VARIANT` and `None` both mean "use this subject's authoritative SessionOrder".
    if session_block_order in (None, PRIMARY_VARIANT):
        sessions = visit_pair(subject, session_order)
        order_name = PRIMARY_VARIANT
    elif session_block_order in P.SESSION_ORDER_LEVELS:
        sessions = P.SESSION_ORDER_LEVELS[session_block_order]
        order_name = session_block_order
    elif session_block_order in PARKED_VARIANTS:
        raise RuntimeError(
            f"{session_block_order!r} is a PARKED order diagnostic and must not be used by "
            f"the primary protocol; use PRIMARY_VARIANT={PRIMARY_VARIANT!r}")
    else:
        raise ValueError(f"unknown session_block_order {session_block_order!r}")

    ordered = []
    for block_i, session in enumerate(sessions):
        rows = [r for r in manifest if r["subject"] == subject and r["session"] == session]
        rows.sort(key=lambda r: int(r["source_epoch_index"]))
        epochs = [int(r["source_epoch_index"]) for r in rows]
        # The guarantee we rely on is STRICT TEMPORAL ORDER (ascending epoch index), not
        # contiguity: a retained recording may skip epochs that the frozen QC rule excluded.
        # A skipped epoch is a missing window, not a reordering, so order survives.
        if epochs != sorted(set(epochs)) or len(epochs) != len(set(epochs)):
            raise RuntimeError(
                f"{subject}/{session}: source_epoch_index is not strictly ascending/unique: {epochs}")
        for j in range(0, len(rows), bs):
            ordered.append({"block": block_i, "session": session,
                            "block_span": len(rows), "rows": rows[j:j + bs],
                            "is_final_batch_of_block": (j + bs) >= len(rows)})
    return ordered, order_name


def block_epoch_gaps(manifest, subject, session_block_order=None, session_order=None):
    """Recorded provenance: which epochs a recording skipped, and where.

    Interior gaps are reported, not repaired - the stream continues across them in order.
    """
    if session_block_order in (None, PRIMARY_VARIANT):
        sessions = visit_pair(subject, session_order)
    else:
        sessions = P.SESSION_ORDER_LEVELS[session_block_order]
    out = {}
    for session in sessions:
        epochs = sorted(int(r["source_epoch_index"]) for r in manifest
                        if r["subject"] == subject and r["session"] == session)
        if not epochs:
            continue
        full = set(range(epochs[0], epochs[-1] + 1))
        missing = sorted(full - set(epochs))
        out[session] = {
            "n_windows": len(epochs),
            "epoch_min": epochs[0],
            "epoch_max": epochs[-1],
            "missing_epochs": missing,
            "missing_interior": [m for m in missing if m < epochs[-1]],
            "missing_tail": len(missing) - len([m for m in missing if m < epochs[-1]]),
        }
    return out


def batch_size_profile(stream):
    """Actual batch sizes per visit, in stream order (prompt correction 2).

    Records the trailing incomplete batch's REAL size instead of silently padding or
    dropping it - `sub-04/ses-1` has only 4 windows, so its single batch is 4.
    """
    out = {}
    for b in stream:
        out.setdefault(b["session"], []).append(len(b["rows"]))
    return out


def stream_windows(stream):
    """Flat (ordered) list of all windows in the stream, for manifest output."""
    return [r for batch in stream for r in batch["rows"]]


# --------------------------------------------------------------------------- model
_SPLITS_CACHE: dict = {}


def _verify_fold_identity(subject):
    """The fold identity is carried by the directory name (root/<model>/<test-subject>/seed_<s>),
    which is how the legacy runner wrote it; assert the frozen split agrees."""
    if "splits" not in _SPLITS_CACHE:
        _SPLITS_CACHE["splits"] = P.load_splits()
    splits = _SPLITS_CACHE["splits"]
    fold = next((f for f in splits["folds"] if f["test"] == [subject]), None)
    if fold is None:
        raise RuntimeError(f"subject {subject} is not the test subject of any frozen fold")
    return fold


def load_source(subject, seed):
    """Frozen legacy source checkpoint for the fold that held out `subject`."""
    ckpt_dir = P.FORMAL_RESULTS / "eegnet" / subject / f"seed_{seed}"
    if not (ckpt_dir / "result.json").exists():
        raise RuntimeError(f"missing legacy fold artifacts for {subject} seed {seed}")
    ckpt = torch.load(ckpt_dir / "best.pt", map_location="cpu", weights_only=False)
    if ckpt["model"] != "eegnet":
        raise RuntimeError(f"unexpected checkpoint model {ckpt['model']!r}")
    if int(ckpt["seed"]) != int(seed):
        raise RuntimeError(f"checkpoint seed mismatch for {subject}: {ckpt['seed']} != {seed}")
    fold = _verify_fold_identity(subject)
    if subject not in fold["test"]:
        raise RuntimeError(f"subject {subject} is not its own fold's test subject")
    norm = np.load(ckpt_dir / "normalization.npz")
    meta = {
        "checkpoint": str(ckpt_dir / "best.pt"),
        "checkpoint_sha256": P.sha256(ckpt_dir / "best.pt"),
        "normalization_sha256": P.sha256(ckpt_dir / "normalization.npz"),
        "epoch": ckpt["epoch"],
        "validation_score": ckpt["validation_score"],
        "seed": ckpt["seed"],
        "fold_id": fold["fold_id"],
        "state_sha256": state_sha256(ckpt["state_dict"]),
    }
    return ckpt["state_dict"], norm["mean"], norm["std"], meta


def state_sha256(state):
    import hashlib

    h = hashlib.sha256()
    for k in sorted(state):
        h.update(k.encode())
        h.update(np.ascontiguousarray(state[k].detach().cpu().numpy()).tobytes())
    return h.hexdigest()


def norm_modules(model):
    """Every normalization layer this EEGNet actually has, with its live settings.

    Recorded so that the arm's normalization behaviour is auditable rather than assumed
    (prompt §3D, §23).
    """
    out = []
    for name, m in model.named_modules():
        if isinstance(m, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)):
            out.append({
                "name": name,
                "type": type(m).__name__,
                "num_features": int(m.num_features),
                "eps": float(m.eps),
                "momentum": None if m.momentum is None else float(m.momentum),
                "affine": bool(m.affine),
                "track_running_stats": bool(m.track_running_stats),
                "running_mean_is_none": m.running_mean is None,
                "running_var_is_none": m.running_var is None,
                "gamma_name": f"{name}.weight" if m.weight is not None else None,
                "beta_name": f"{name}.bias" if m.bias is not None else None,
                "gamma_numel": int(m.weight.numel()) if m.weight is not None else 0,
                "beta_numel": int(m.bias.numel()) if m.bias is not None else 0,
            })
    return out


def dropout_modules(model):
    """Locate Dropout modules without tripping over torch's module-level __getattr__."""
    found = []
    for name, m in model.named_modules():
        try:
            is_drop = isinstance(m, torch.nn.modules.dropout._DropoutNd)
        except TypeError:
            continue
        if is_drop:
            found.append((name, m))
    return found


def set_dropout_mode(model, training):
    for _, m in dropout_modules(model):
        m.train(training)


def dropout_state(model):
    mods = dropout_modules(model)
    return {
        "n_dropout_modules": len(mods),
        "dropout_names": [n for n, _ in mods],
        "dropout_any_training": any(m.training for _, m in mods),
        "dropout_all_training": all(m.training for _, m in mods) if mods else None,
    }


def build_arm_model(cfg, state_dict, arm, builder=None):
    """Build the model for one arm and return (model, trainable_params, norm_audit).

    Frozen four-arm design (prompt correction 3):

    source
        FROZEN LEGACY inference semantics: `eval()`, frozen source running statistics,
        no gradients, Dropout eval.
    bn_only
        Test-time normalization control: batch statistics (`track_running_stats=False`,
        running buffers detached), **no** entropy gradient, **no** affine optimizer,
        Dropout eval.  SOURCE's frozen weights otherwise.
    tent_literal
        The pinned official TENT `configure_model` semantics **literally**: `model.train()`
        so every module (including EEGNet's two Dropout layers) is in training mode;
        BN statistics from the current test batch; only BN affine gamma/beta trainable;
        pre-update logits scored.
    tent_det
        Diagnostic control: identical entropy objective, optimizer, BN statistics and
        BN-affine updates; the **only** difference is that Dropout is forced to eval.
        This is NOT literal canonical TENT and must never be called that.

    Invariant: `tent_literal` and `tent_det` differ in Dropout mode and nothing else.
    `builder` exists only so the synthetic smoke test can inject a smaller architecture.
    """
    if arm not in ARMS:
        raise ValueError(arm)
    model = (builder or P.build_model_from_config)(cfg)
    model.load_state_dict(state_dict, strict=True)

    if arm == "source":
        model.eval()
        model.requires_grad_(False)
        return model, [], norm_modules(model)

    # --- shared normalization configuration for bn_only / tent_literal / tent_det
    # (official tent.configure_model: force batch statistics in all modes)
    for m in model.modules():
        if isinstance(m, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)):
            m.track_running_stats = False
            m.running_mean = None
            m.running_var = None

    params = []
    if arm == "bn_only":
        model.eval()
        model.requires_grad_(False)
        return model, [], norm_modules(model)

    # --- TENT arms: literal official semantics, then the sole Dropout deviation
    model.train()
    model.requires_grad_(False)
    for name, m in model.named_modules():
        if isinstance(m, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)):
            for pname, p in m.named_parameters(recurse=False):
                if pname in {"weight", "bias"} and p is not None:
                    p.requires_grad_(True)
                    params.append(p)
    if not params:
        raise RuntimeError("TENT requires BatchNorm affine parameters")
    if arm == "tent_det":
        set_dropout_mode(model, False)
    return model, params, norm_modules(model)


def prepare_adaptation_mode(arm, model):
    """Official TENT semantics: the entropy arms stay in `model.train()`.

    Called before the entropy forward so that the mode is re-asserted every batch and cannot
    silently drift.
      * `tent_literal` -> `model.train()`: Dropout LIVE for the scored/entropy forward.
      * `tent_det`     -> `model.train()`, then Dropout forced to eval.
      * non-TENT arms  -> `eval()`.
    """
    if arm in TENT_ARMS:
        model.train()
        if arm == "tent_det":
            set_dropout_mode(model, False)
    else:
        model.eval()


def prepare_prediction_mode(arm, model):
    """Kept for the non-TENT arms and for explicit mode assertions in tests."""
    model.eval()
    if arm == "tent_det":
        set_dropout_mode(model, False)


def entropy_forward(arm, model, x):
    """THE single pre-update forward for the entropy arms.

    Returns `(logits, loss)`.  `logits` IS the tensor the entropy is computed from, so the
    recorded prediction and the adaptation objective are by construction the same forward
    pass - this is what makes `TENT_LITERAL` literal.  There is deliberately no second,
    Dropout-off scoring forward anywhere in this module.

    Mode at this call:
      * `tent_literal` -> the model is in `train()` (official TENT configuration), so
        EEGNet's Dropout layers are ACTIVE and the scored logits contain the dropout effect.
      * `tent_det`     -> Dropout forced to eval, everything else identical.
    """
    logits = model(x)
    loss = softmax_entropy(logits).mean(0)
    return logits, loss


def softmax_entropy(logits):
    return -(logits.softmax(1) * logits.log_softmax(1)).sum(1)


def _finite_or_none(x):
    """JSON-safe: NaN/inf become None.

    Used for quantities that are genuinely NOT APPLICABLE to an arm (e.g. `entropy_loss` and
    `grad_norm` for SOURCE/BN_ONLY, which have no objective and no gradient). `None` is the
    honest encoding - it means "this arm does not have this quantity", not "it was zero".
    """
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return x
    return f if math.isfinite(f) else None


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        return _finite_or_none(obj)
    return obj


# --------------------------------------------------------------- RNG convention
RNG_DOMAIN = "EEGTTA-PHASE1"
RNG_CONVENTION_VERSION = 1
RNG_UNIT_SEED_MODULUS = 2 ** 31 - 1


def unit_rng_seed(seed, subject, arm, variant=PRIMARY_VARIANT, batch_index=0):
    """Deterministic Dropout RNG seed for one (unit, batch), derived from immutable ids.

    `TENT_LITERAL` is stochastic by construction (live Dropout).  To keep the experiment
    reproducible *without* removing that stochasticity, every forward pass draws from a
    generator seeded ONLY by the frozen identity of the unit it belongs to:

        seed = H(RNG_DOMAIN | v{RNG_CONVENTION_VERSION} | variant | arm | subject |
                 model_seed | batch_index)  mod  2**31-1

    with `H` = SHA-256 over the UTF-8, `|`-joined string with integer fields rendered
    decimal.  Consequences, each asserted by NC20/NC21:

    * a rerun of the same unit reproduces it bit-for-bit;
    * units cannot inherit mutable RNG state from previously processed units, so
      **completing, skipping or reordering units cannot change any other unit's trajectory**
      (this is what makes resume semantics sound);
    * there is no single global RNG stream that resumption could desynchronise.

    Post-result RNG sweeps are NOT part of Phase 1; a stochastic-replicate analysis would be
    a separately licensed diagnostic branch.
    """
    payload = "|".join([RNG_DOMAIN, f"v{RNG_CONVENTION_VERSION}", variant, arm, subject,
                        str(int(seed)), str(int(batch_index))])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % RNG_UNIT_SEED_MODULUS


def unit_rng_payload(seed, subject, arm, variant=PRIMARY_VARIANT, batch_index=0):
    """The exact string the seed is hashed from - recorded so the mapping is hashable."""
    return "|".join([RNG_DOMAIN, f"v{RNG_CONVENTION_VERSION}", variant, arm, subject,
                     str(int(seed)), str(int(batch_index))])


# --------------------------------------------------------------------------- runner
def run_arm(arm, subject, seed, cfg, manifest, session_block_order=None,
            batch_size=None, device="cpu"):
    """Run one arm over one subject episode.  Returns predictions + trajectory rows.

    `session_block_order=None` (the default, and what the primary experiment uses) means
    "this subject's authoritative `SessionOrder` visit pair".  Passing `NS_then_SD` or
    `SD_then_NS` is rejected: those are PARKED order diagnostics.

    Structure matters for auditability.  Guarded by the sentinels
    `# ---- BEGIN ADAPTATION REGION` / `# ---- END ADAPTATION REGION`, which must contain
    no target label at all (negative control NC1).  Within the region, batch t's
    prediction is computed and stored into `batch_probs` *before* any optimizer step
    (the prequential / test-then-adapt convention).  Labels are attached outside the
    region, in the post-hoc evaluator, and are never an input to adaptation.
    """
    bs = batch_size or PROTOCOL["batch_size"]
    stream, order_name = build_stream(manifest, subject, session_block_order, bs)
    # ---- BEGIN ADAPTATION REGION
    state_dict, mean, std, meta = load_source(subject, seed)
    model, params, norm_audit = build_arm_model(cfg, state_dict, arm)
    model = model.to(device)

    optimizer = None
    if arm in TENT_ARMS:
        optimizer = torch.optim.Adam(params, lr=PROTOCOL["lr"], betas=PROTOCOL["betas"],
                                     weight_decay=PROTOCOL["weight_decay"])

    theta0 = None
    drift_floor = 0.0
    if arm in TENT_ARMS:
        with torch.no_grad():
            theta0 = torch.cat([p.detach().reshape(-1).clone() for p in params])
            drift_floor = float(theta0.norm().item())

    frozen_sha = state_sha256(dict(model.state_dict()))
    batch_probs = []
    batch_rows = []
    for batch_index, batch in enumerate(stream):
        rows = batch["rows"]
        x = np.stack([((_wave(r).astype(np.float32) - mean) / std) for r in rows])
        x = torch.from_numpy(np.ascontiguousarray(x)).to(device)

        # ---- per-unit RNG: deterministic, independent of execution/resume order
        rng_seed = unit_rng_seed(seed, subject, arm, order_name, batch_index)
        rng_seed_before = torch.initial_seed()
        torch.manual_seed(rng_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(rng_seed)

        entropy_loss = float("nan")
        grad_norm = float("nan")
        if arm in TENT_ARMS:
            # (1-4) ONE pre-update forward in the official TENT train-mode configuration.
            #       `logits` below is BOTH the scored prediction and the entropy source.
            prepare_adaptation_mode(arm, model)
            dropout_active = dropout_state(model)["dropout_any_training"]
            with torch.enable_grad():
                for _ in range(PROTOCOL["steps_per_batch"]):
                    optimizer.zero_grad(set_to_none=True)
                    logits, loss = entropy_forward(arm, model, x)
                    if not torch.isfinite(loss):
                        raise RuntimeError(f"non-finite TENT entropy {subject}/{batch_index}")
                    # (5) record the prediction BEFORE any parameter moves
                    probs = torch.softmax(logits.detach(), dim=1)
                    batch_probs.append((logits.detach().clone(),
                                        probs[:, 1].cpu().numpy(),
                                        probs.argmax(dim=1).cpu().numpy()))
                    # (6-8) backward + update only the allowed BN affine parameters
                    loss.backward()
                    grad_norm = float(torch.sqrt(sum(
                        (p.grad.detach() ** 2).sum() for p in params if p.grad is not None)).item())
                    optimizer.step()
                entropy_loss = float(loss.detach().cpu())
            del loss
            if not torch.isfinite(logits).all():
                raise RuntimeError(f"non-finite logits {subject}/{batch_index}")
        else:
            # SOURCE / BN_ONLY: plain frozen-inference semantics, deterministic.
            prepare_adaptation_mode(arm, model)
            dropout_active = dropout_state(model)["dropout_any_training"]
            mode = torch.inference_mode if arm == "source" else torch.no_grad
            with mode():
                logits = model(x)
            probs = torch.softmax(logits.detach(), dim=1)
            batch_probs.append((logits.detach().clone(),
                                probs[:, 1].cpu().numpy(),
                                probs.argmax(dim=1).cpu().numpy()))

        row_extra = {
            "batch_index": batch_index,
            "subject": subject, "seed": seed, "arm": arm,
            "session_block_order": order_name,
            "session": batch["session"], "block": batch["block"],
            "block_span": batch["block_span"],
            "is_final_batch_of_block": batch["is_final_batch_of_block"],
            "batch_n": len(rows),
            "rng_seed": rng_seed,
            "rng_seed_payload": unit_rng_payload(seed, subject, arm, order_name, batch_index),
            "rng_seed_restored": rng_seed_before,
            "model_training_flag_during_forward": bool(model.training),
            "dropout_active_during_forward": dropout_active,
            "batch_mean_entropy": float(softmax_entropy(logits.detach()).mean().cpu()),
            "batch_marginal_q1": float(probs[:, 1].mean().cpu()),
            "batch_pred_positive_frac": float((probs[:, 1] >= 0.5).float().mean().cpu()),
            "batch_mean_max_conf": float(probs.max(dim=1).values.mean().cpu()),
            "batch_entropy_loss": entropy_loss,
            "batch_grad_norm": grad_norm,
        }
        if arm in TENT_ARMS:
            with torch.no_grad():
                theta = torch.cat([p_.detach().reshape(-1).clone() for p_ in params])
                row_extra["affine_drift_l2"] = float((theta - theta0).norm().item())
                row_extra["affine_norm_l2"] = float(theta.norm().item())
        batch_rows.append(row_extra)

    if arm == "source":
        if state_sha256(dict(model.state_dict())) != frozen_sha:
            raise RuntimeError("SOURCE arm violated: model state changed during evaluation")
    if arm == "bn_only":
        if any(p.requires_grad for p in model.parameters()):
            raise RuntimeError("BN_ONLY arm violated: some parameter requires grad")
        if optimizer is not None:
            raise RuntimeError("BN_ONLY arm violated: optimizer present")
        if dropout_state(model)["dropout_any_training"]:
            raise RuntimeError("BN_ONLY arm violated: Dropout is active")
    trainable_names = [n for n, p in model.named_parameters() if p.requires_grad]
    # ---- END ADAPTATION REGION

    # post-hoc evaluator: target labels touch the record only from here on
    scores = {}
    window_rows = []
    pos = 0
    for batch_index, (batch, (_logits, p1, argmax)) in enumerate(zip(stream, batch_probs)):
        for r, prob, am in zip(batch["rows"], p1.tolist(), argmax.tolist()):
            scores[r["segment_id"]] = float(prob)
            window_rows.append({
                "subject": subject, "seed": seed, "arm": arm,
                "session_block_order": order_name,
                "batch_index": batch_index,
                "block": batch["block"], "session": batch["session"],
                "stream_position": pos, "segment_id": r["segment_id"],
                "y_true": int(r["label"]),
                "source_epoch_index": int(r["source_epoch_index"]),
                "p_positive": float(prob), "y_pred": int(am),
                "batch_n": len(batch["rows"]),
            })
            pos += 1

    if set(scores) != {r["segment_id"] for r in stream_windows(stream)}:
        raise RuntimeError(f"{arm}/{subject}: output does not cover the stream exactly once")
    if len(batch_probs) != len(stream):
        raise RuntimeError(f"{arm}/{subject}: {len(batch_probs)} scored forwards for "
                           f"{len(stream)} batches (steps_per_batch must not change mid-run)")

    ds_final = dropout_state(model)
    return {
        "arm": arm, "subject": subject, "seed": seed,
        "session_block_order": order_name,
        "visit_pair": list(visit_pair(subject)),
        "n_windows": len(stream_windows(stream)),
        "n_batches": len(stream),
        "batch_size_profile": batch_size_profile(stream),
        "batch_sizes_observed": sorted({len(b["rows"]) for b in stream}),
        "scores": scores,
        "window_rows": window_rows,
        "batch_rows": [{"session_block_order": order_name, **r} for r in batch_rows],
        "norm_audit": norm_audit,
        "source_meta": meta,
        "dropout_audit": ds_final,
        "scoring_semantics": {
            "single_pre_update_forward": True,
            "scored_logits_are_the_entropy_logits": True,
            "separate_scoring_forward": False,
            "dropout_active_in_scored_forward": bool(
                batch_rows[0]["dropout_active_during_forward"]) if batch_rows else None,
            "rng_convention_version": RNG_CONVENTION_VERSION,
            "rng_domain": RNG_DOMAIN,
        },
        "n_trainable_tensors": len(params),
        "n_trainable_scalars": int(sum(p.numel() for p in params)),
        "trainable_names": trainable_names,
        "affine_norm_initial": drift_floor,
        "state_unchanged": (state_sha256(dict(model.state_dict())) == frozen_sha) if arm == "source" else None,
    }


_WAVE_CACHE: dict = {}


def _wave(rows):
    name = rows["waveform_file"]
    if name not in _WAVE_CACHE:
        _WAVE_CACHE[name] = np.load(P.ACTIVE_DATA / name, mmap_mode="r")
    return np.asarray(_WAVE_CACHE[name][int(rows["array_index"])])
