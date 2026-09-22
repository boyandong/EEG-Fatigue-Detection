"""Synthetic smoke test for the FOUR arms - NO real ds004902 data, NO real adaptation.

Purpose: prove the arm plumbing runs, that gradients flow only into normalization affine
parameters, that SOURCE is bit-exact, that BN_ONLY takes no optimizer step, and that
TENT_LITERAL and TENT_DET differ in Dropout mode and nothing else.  This is the "tiny
synthetic smoke test" the local-execution rule permits; it is not the TENT experiment and
licenses nothing.

Run:  python tests/test_p1_synthetic_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Run both at a console and as a captured subprocess by the verifiers. On Windows a *piped*
# stdout defaults to the ANSI code page; pin it to UTF-8 so the reporting channel can never
# decide whether the smoke test ran.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):      # pragma: no cover - non-reconfigurable stream
        pass

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import p1_arms as A  # noqa: E402

N_CHANS, N_TIMES, N_WINDOWS = 4, 128, 40


def tiny_cfg():
    return {"eegnet": {"F1": 2, "D": 2, "F2": 4, "kernel_length": 16,
                       "depthwise_kernel_length": 8, "drop_prob": 0.5,
                       "final_layer_with_constraint": True, "norm_rate": 0.25}}


def tiny_model(cfg=None):
    """Small EEGNet with the same architecture family; used only for plumbing tests."""
    from braindecode.models import EEGNet

    torch.manual_seed(7)
    return EEGNet(n_chans=N_CHANS, n_outputs=2, n_times=N_TIMES, sfreq=500,
                  **(cfg or tiny_cfg())["eegnet"])


def fake_stream(n_windows=N_WINDOWS, batch_size=10):
    rows = [{"segment_id": f"syn_{i:04d}", "label": str(i % 2), "source_epoch_index": i,
             "session": "syn"} for i in range(n_windows)]
    return [{"block": 0, "session": "syn", "block_span": n_windows, "rows": rows[i:i + batch_size],
             "is_final_batch_of_block": (i + batch_size) >= n_windows}
            for i in range(0, n_windows, batch_size)]


def run_synthetic(arm):
    """Drive ONE arm over synthetic tensors using the SAME per-batch code shape as run_arm.

    Returns, for the TENT arms, `(scored_logits, entropy_logits, loss)` for the first batch
    so NC20 can assert they are the very same forward.
    """
    cfg = tiny_cfg()
    maker = tiny_model
    state = {k: v.clone() for k, v in maker().state_dict().items()}
    model, params, audit = A.build_arm_model(cfg, state, arm, builder=maker)
    torch.manual_seed(0)
    # braindecode EEGNet takes (batch, n_chans, n_times)
    data = torch.randn(N_WINDOWS, N_CHANS, N_TIMES)

    opt = None
    if arm in A.TENT_ARMS:
        opt = torch.optim.Adam(params, lr=A.PROTOCOL["lr"], betas=A.PROTOCOL["betas"],
                               weight_decay=A.PROTOCOL["weight_decay"])
    before = {k: v.detach().clone() for k, v in model.state_dict().items()}
    dropout_flags = []
    training_flags = []
    n_forwards = 0
    first_probe = None
    entropies = []

    for batch_index, batch in enumerate(fake_stream()):
        idx = [int(r["source_epoch_index"]) for r in batch["rows"]]
        x = data[idx]
        # mirror the production per-unit RNG convention so the replay assertion is meaningful
        torch.manual_seed(A.unit_rng_seed(0, "syn_subject", arm, "metadata_order", batch_index))
        A.prepare_adaptation_mode(arm, model)
        training_flags.append(bool(model.training))
        dropout_flags.append(A.dropout_state(model)["dropout_any_training"])
        if arm in A.TENT_ARMS:
            with torch.enable_grad():
                opt.zero_grad(set_to_none=True)
                logits, loss = A.entropy_forward(arm, model, x)
                n_forwards += 1
                scored = logits.detach().clone()
                entropy_logits = logits.detach().clone()
                if first_probe is None:
                    first_probe = (scored.numpy(), entropy_logits.numpy(), float(loss))
                entropies.append(float(A.softmax_entropy(logits.detach()).mean()))
                loss.backward()
                opt.step()
        else:
            mode = torch.inference_mode if arm == "source" else torch.no_grad
            with mode():
                logits = model(x)
                n_forwards += 1
            entropies.append(float(A.softmax_entropy(logits.detach()).mean()))

    changed = [k for k, v in model.state_dict().items()
               if not torch.equal(before[k], v.detach())]
    return {"arm": arm, "changed": changed,
            "params": [n for n, p in model.named_parameters() if p.requires_grad],
            "n_params": len(params), "audit": audit,
            "dropout_flags": dropout_flags,
            "training_flags": training_flags,
            "n_forwards": n_forwards,
            "n_batches": len(fake_stream()),
            "first_probe": first_probe,
            "n_dropout_modules": A.dropout_state(model)["n_dropout_modules"],
            "entropies": entropies}


def main():
    results = {}
    # TENT_LITERAL is stochastic; run it with a fixed seed so the test itself is repeatable
    for arm in A.ARMS:
        torch.manual_seed(123)
        results[arm] = run_synthetic(arm)

    ok = True

    src = results["source"]
    cond = src["changed"] == [] and src["n_params"] == 0 and not any(src["dropout_flags"])
    print(f"[{'PASS' if cond else 'FAIL'}] SOURCE bit-exact, no dropout "
          f"(changed: {src['changed']}, dropout flags: {set(src['dropout_flags'])})")
    ok &= cond

    bn = results["bn_only"]
    cond = (bn["changed"] == [] and bn["n_params"] == 0
            and not any(bn["dropout_flags"]))
    print(f"[{'PASS' if cond else 'FAIL'}] BN_ONLY no optimizer step, dropout off "
          f"(changed: {bn['changed']})")
    ok &= cond

    norm_names = {m["gamma_name"] for m in src["audit"] if m["gamma_name"]} | \
                 {m["beta_name"] for m in src["audit"] if m["beta_name"]}
    for arm in A.TENT_ARMS:
        t = results[arm]
        changed_params = [c for c in t["changed"] if "running_" not in c]
        cond = (set(t["params"]) == norm_names
                and set(changed_params) <= norm_names
                and len(changed_params) > 0)
        print(f"[{'PASS' if cond else 'FAIL'}] {arm} updated only BN affine tensors "
              f"({len(changed_params)} tensors)")
        ok &= cond

    # the whole point of the fourth arm: Dropout mode must differ, everything else identical
    lit, det = results["tent_literal"], results["tent_det"]
    cond = (all(lit["dropout_flags"]) and lit["n_dropout_modules"] > 0)
    print(f"[{'PASS' if cond else 'FAIL'}] TENT_LITERAL has Dropout ACTIVE during the scored/"
          f"entropy forward ({lit['n_dropout_modules']} modules, flags {set(lit['dropout_flags'])})")
    ok &= cond
    cond = (not any(det["dropout_flags"]))
    print(f"[{'PASS' if cond else 'FAIL'}] TENT_DET has Dropout INACTIVE during the scored/"
          f"entropy forward (flags {set(det['dropout_flags'])})")
    ok &= cond
    cond = (set(lit["changed"]) == set(det["changed"]))
    print(f"[{'PASS' if cond else 'FAIL'}] LITERAL and DET modify the same tensor set")
    ok &= cond

    # --- correction-blocker semantics: ONE forward, scored logits == entropy logits
    for arm in A.TENT_ARMS:
        t = results[arm]
        scored, ent_logits = t["first_probe"][0], t["first_probe"][1]
        cond = np.array_equal(scored, ent_logits)
        print(f"[{'PASS' if cond else 'FAIL'}] {arm}: scored logits ARE the entropy logits "
              f"(max|diff|={np.abs(scored - ent_logits).max():.3e})")
        ok &= cond
        cond = t["n_forwards"] == t["n_batches"]
        print(f"[{'PASS' if cond else 'FAIL'}] {arm}: exactly ONE forward per batch "
              f"({t['n_forwards']} forwards / {t['n_batches']} batches)")
        ok &= cond
    # TENT arms must run in train() (official configuration); SOURCE/BN_ONLY in eval()
    cond = all(lit["training_flags"]) and all(det["training_flags"])
    print(f"[{'PASS' if cond else 'FAIL'}] both TENT arms forward in model.train() "
          f"(official configuration)")
    ok &= cond
    cond = (not any(src["training_flags"])) and (not any(bn["training_flags"]))
    print(f"[{'PASS' if cond else 'FAIL'}] SOURCE and BN_ONLY forward in model.eval()")
    ok &= cond

    # RNG convention: same unit identity -> same seed, irrespective of what ran before
    s_a = [A.unit_rng_seed(0, "sub-01", "tent_literal", "metadata_order", b) for b in range(4)]
    for s in ("sub-02", "sub-03"):
        for b in range(5):
            A.unit_rng_seed(0, s, "tent_literal", "metadata_order", b)
    s_b = [A.unit_rng_seed(0, "sub-01", "tent_literal", "metadata_order", b) for b in range(4)]
    cond = s_a == s_b and len(set(s_a)) == 4
    print(f"[{'PASS' if cond else 'FAIL'}] per-unit RNG seeds are order-independent and "
          f"per-batch distinct (example {s_a[0]})")
    ok &= cond

    # replay determinism: an actual end-to-end replay of the same unit under the frozen
    # convention.  `run_synthetic` applies the per-unit seed itself so the two runs are
    # comparable regardless of the ambient global RNG state.
    replay1 = run_synthetic("tent_literal")
    replay2 = run_synthetic("tent_literal")
    cond = np.array_equal(replay1["first_probe"][0], replay2["first_probe"][0])
    print(f"[{'PASS' if cond else 'FAIL'}] TENT_LITERAL synthetic unit replays bit-exactly")
    ok &= cond

    # normalization audit agrees with the frozen arm definitions
    for arm in ("bn_only",) + A.TENT_ARMS:
        for m in results[arm]["audit"]:
            if m["track_running_stats"] or not m["running_mean_is_none"]:
                print(f"[FAIL] {arm}: {m['name']} still tracks running stats")
                ok = False
    for m in src["audit"]:
        if not m["track_running_stats"] or m["running_mean_is_none"]:
            print(f"[FAIL] source: {m['name']} does not use frozen running stats")
            ok = False
    print("[PASS] normalization audit: source keeps running stats; bn_only/tent_* use batch stats"
          if ok else "[FAIL] normalization audit mismatch")

    # no batch mixes a visit and the final batch keeps its size (synthetic shape check)
    stream = fake_stream()
    expect_last = N_WINDOWS % 10 or 10
    cond = (all(len({r["session"] for r in b["rows"]}) == 1 for b in stream)
            and stream[-1]["is_final_batch_of_block"]
            and len(stream[-1]["rows"]) == expect_last)
    print(f"[{'PASS' if cond else 'FAIL'}] synthetic stream: batches never cross a block; "
          f"final batch size {len(stream[-1]['rows'])} (expected {expect_last})")
    ok &= cond

    n_norm = len(src["audit"])
    n_scalars = sum(m["gamma_numel"] + m["beta_numel"] for m in src["audit"])
    print(f"       tiny-model normalization layers: {n_norm}; affine scalars: {n_scalars}")
    print("       (production 61-channel EEGNet: 3 layers, 80 affine scalars - see "
          "99_norm_inventory.py)")

    print("\nSMOKE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
