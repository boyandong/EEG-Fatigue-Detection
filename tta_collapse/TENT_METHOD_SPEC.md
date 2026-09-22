# TENT_METHOD_SPEC.md

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Status:** FROZEN before the first adaptation run (prompt §7, §8, §12, §30).

This document separates **documented facts** (what the reference actually says/does) from
**our implementation choices** (what we decided, and why). Every frozen number is justified
from the reference, not from memory.

---

## 0. Audit scope and sources

| source | identity | how pinned here |
|---|---|---|
| TENT paper | Wang, Shelhamer, Liu, Olshausen, Darrell, *Tent: Fully Test-Time Adaptation by Entropy Minimization*, ICLR 2021 (spotlight) | OpenReview `uXl3bZLkr3c` |
| official implementation | `github.com/DequanWang/tent` @ `e9e926a668d85244c66a6d5c006efbd2b82e83e8` | **vendored** at `project/third_party/tent-official-e9e926a/`, archive SHA-256 `903e9f81ee7972017cc4675fd6ead3f51331a2a8958efb9b0aecb853e5f2dc79`, `tent.py` SHA-256 `d854e1f65f741aa1632dfb55420ca1bcf5405c978bef890e45caad04980514c8` |
| official example loop | `cifar10c.py` in the same checkout | vendored, read directly |
| official config | `conf.py` defaults + `cfgs/tent.yaml`, `cfgs/norm.yaml`, `cfgs/source.yaml` | vendored, read directly |
| pre-existing legacy TENT prototype in this repo | `project/run_tent_rbf_baselines.py`, `project/configs/tent_rbf_svm.json` | read, **rejected** — see `LEGACY_EEGNET_PROVENANCE.md` §5 |

The dense, 10-page-specific audit the brief envisages is compressed to the above because the
reference implementation is present in-tree and hash-pinned: the semantics below are read
off the actual source rather than paraphrased.

---

## 1. Documented facts (from the reference, not from memory)

### F1 — Configuration order: which mode is which

`conf.py`: `_C.MODEL.ADAPTATION ∈ {source, norm, tent}`. `cifar10c.py` maps
`source → setup_source`, `norm → setup_norm`, `tent → setup_tent`. The official example
therefore already compares exactly the three arms Phase 1 needs.

### F2 — What TENT adapts

`tent.collect_params` walks named modules and collects, for every `nn.BatchNorm2d`, only the
parameters named `weight` and `bias` — i.e. the channel-wise affine scale γ and shift β.
Nothing else.

### F3 — How the adapted model is configured

`tent.configure_model(model)` does three things:

1. `model.train()` — training mode;
2. `model.requires_grad_(False)` — freeze everything;
3. for every `nn.BatchNorm2d`: `m.requires_grad_(True)`, **`m.track_running_stats = False`**,
   **`m.running_mean = None`**, **`m.running_var = None`** — *"force use of batch stats in
   train and eval modes"*.

So under TENT the normalization layers estimate μ/σ **from the current test batch** and do
not consult source running statistics at all. `configure_model` deliberately leaves
normalization modules in `train()` mode while all other modules were set to `train()` by
`model.train()` and then had `requires_grad` disabled.

### F4 — The update

`tent.forward_and_adapt(x, model, optimizer)`:

```
outputs = model(x)                                   # forward
loss = softmax_entropy(outputs).mean(0)              # entropy objective
loss.backward()                                      # gradients
optimizer.step()                                     # update
optimizer.zero_grad()                                # clear
return outputs
```

with `softmax_entropy(x) = -(x.softmax(1) * x.log_softmax(1)).sum(1)` — the entropy of the
softmax distribution, minimised. `@torch.enable_grad()` decorates the function so grads flow
even inside a `no_grad` testing context.

### F5 — Prequential semantics are a property of the reference

`tent.Tent.forward` returns the `outputs` produced by `forward_and_adapt`, i.e. **the logits
of the forward pass taken before that batch's `optimizer.step()`**. The official evaluation
driver `cifar10c.py` calls `robustbench.utils.clean_accuracy(model, x, y, batch_size)`, which
iterates batches and does `output = model(x_curr)` then scores — the prediction for batch *t*
is computed with the model state that existed *before* batch *t*'s update.

⇒ **the official reference is test-then-adapt (prequential) in effect.** A prediction is
never made with a model that has already seen that same batch.

### F6 — Reset granularity in the official example

`cifar10c.py` calls `model.reset()` once per **corruption × severity** combination — *"reset
adaptation for each combination of corruption x severity; note: for evaluation protocol, but
not necessarily needed"*. `cfg.MODEL.EPISODIC = False` by default, so `tent.Tent.forward`
does **not** reset per batch: adaptation is online and updates persist across batches within
a (corruption, severity) episode.

### F7 — Frozen hyper-parameters from the reference

`conf.py` defaults, confirmed by `cfgs/tent.yaml`:

| setting | reference value |
|---|---|
| optimizer | **Adam** (`OPTIM.METHOD: Adam`) |
| learning rate | **1e-3** (`OPTIM.LR: 1e-3`, and the README's usage snippet uses `lr=1e-3`) |
| β₁ | **0.9** (`OPTIM.BETA`) |
| β₂ | 0.999 (`optim.Adam(..., betas=(cfg.OPTIM.BETA, 0.999))`) |
| weight decay | **0.0** (`OPTIM.WD: 0.`) |
| steps per batch | **1** (`OPTIM.STEPS: 1`) |
| batch size | 128 (`conf.py`) / 200 (`cfgs/tent.yaml`), illustrative |
| episodic | `False` (online, persistent) |
| RNG seed | 1 |

`setup_optimizer` advises *"use the settings from the end of training, if known, or start with
a low learning rate (like 0.001) if not"*, and Adam is a documented-advised choice
(*"we advise choosing Adam or SGD+momentum"*).

Note the reference's README caveat: *"The purpose of the example is explanation, not
reproduction: exact details of the model architecture, optimization settings, etc. may differ
from the paper."*

### F8 — The `norm` control

`norm.configure_model(model, eps, momentum, reset_stats, no_stats)` puts every `nn.BatchNorm2d`
into `train()` mode, sets `eps` and `momentum`, and **optionally** (`reset_stats=False`,
`no_stats=False` by default in `cifar10c.setup_norm`) additionally resets or disables running
statistics. `Norm.forward` is just `self.model(x)` — **no loss, no backward, no optimizer**.
`Norm.reset()` restores a deep-copied state dict.

In the example's default configuration the control changes *feature statistics to test-batch
statistics* while the affine parameters keep their source values and `requires_grad` is
untouched.

---

## 2. Our implementation choices (decided, with rationale)

Each choice is tagged: **[DIRECT]** = the reference fixes it; **[MINIMAL ADAPTATION]** = the
reference is silent and we chose the smallest faithful option; **[PROTOCOL]** = forced by the
Phase 1 brief.

| # | choice | value | basis |
|---|---|---|---|
| C1 | arms | `SOURCE`, `BN_ONLY`, `TENT_LITERAL`, `TENT_DET` | [PROTOCOL] pre-result correction 3 |
| C2 | adapted parameters | the 6 BatchNorm affine tensors of `bnorm_temporal`, `bnorm_1`, `bnorm_2` (80 scalars, 1.2654 % of 6322 model parameters) | [DIRECT] F2 |
| C3 | normalization statistics under every adaptation arm | `track_running_stats=False`, `running_mean=None`, `running_var=None`, batch statistics | [DIRECT] F3 |
| C4 | optimizer | `torch.optim.Adam` | [DIRECT] F7 |
| C5 | lr / β / wd | `1e-3` / `(0.9, 0.999)` / `0.0` | [DIRECT] F7 |
| C6 | steps per incoming batch | `1` | [DIRECT] F7 |
| C7 | batch size | **32** | [MINIMAL ADAPTATION] see §2.2 |
| C8 | episodic granularity | **per subject** (reset model + BN state + optimizer state at episode start, discard at episode end) | [PROTOCOL] §9 — stricter than the reference, which resets per corruption×severity (F6) |
| C9 | prediction semantics | forward → record → entropy → backward → step | [DIRECT] F5 |
| C10 | weight decay | `0.0`, and **no explicit L2 term added to the loss** | [DIRECT] the reference's `forward_and_adapt` never adds `wd·‖θ‖²` |
| C11 | Dropout: `TENT_LITERAL` | **active during the adaptation step**, disabled for the prediction forward | [DIRECT] literal official `model.train()` |
| C12 | Dropout: `TENT_DET` | **disabled throughout**; everything else identical to `TENT_LITERAL` | [PROTOCOL] diagnostic control, see §2.3 |
| C13 | stream order | per-subject `SessionOrder` visit pair; true within-recording temporal order; batches never cross a visit | [PROTOCOL] `TARGET_STREAM_PROVENANCE.md` |
| C14 | `eps` / `momentum` | untouched PyTorch defaults (`1e-5`, `0.1`) | [MINIMAL ADAPTATION] |
| C15 | seeds | the legacy training seeds `0, 1, 2` | [PROTOCOL] §6 — keeps SOURCE exactly the historical benchmark |

### 2.1 BN_ONLY — exact frozen definition

`BN_ONLY` is the **normalization-statistics control**: it isolates the effect of *estimating
feature statistics from the test batch* from the effect of *gradient descent on entropy*.

1. load the same frozen source checkpoint;
2. **no** entropy term, **no** `loss.backward()`, **no** `optimizer`, **no** optimizer step;
3. **no** parameter is trainable (`requires_grad` is `False` throughout);
4. normalization layers configured exactly as TENT configures them —
   `track_running_stats=False`, `running_mean=None`, `running_var=None` — so every forward
   pass normalizes with **statistics of the current test batch**;
5. Dropout **off** (eval mode), matching SOURCE's determinism.

Relation to the reference: this is `norm`'s stochastic-statistics configuration (F8) applied
to TENT's normalization setup (F3), minus the optimizer. It is deliberately **not** the
`norm` variant that keeps updating running statistics.

Under BN_ONLY *and* both TENT arms running statistics are never read and never updated, so the
only difference between BN_ONLY and the TENT arms is whether the 80 affine scalars move.
SOURCE keeps the checkpoint's frozen running statistics, as the legacy evaluation did.

### 2.2 Batch size 32 — rationale

The reference does not fix a batch size (`conf.py` says 128, `cfgs/tent.yaml` says 200, both
labelled as example settings) and explicitly invites tuning — which Phase 1 forbids.

Frozen choice: **32**, because it is already fixed elsewhere in this apparatus and is therefore
not a new researcher degree of freedom: `baselines.json` uses `batch_size: 32` for the legacy
EEGNet training, and the legacy prototype used 32 too. It matches the training batch size —
the regime in which source BatchNorm statistics are meaningful — and it is small enough that
per-batch statistics are a plausible failure mechanism, which is exactly what Phase 1 must be
able to observe (prompt §23). **Not swept.**

### 2.3 The Dropout / train-mode confound — resolved BEFORE results exist

This is the most consequential correction made before the formal run, so it is documented in
full.

**The problem.** The official reference's `configure_model` calls `model.train()` on the whole
model and then re-enables gradients only on BatchNorm. Because `model.train()` is global, EEGNet's
two 0.5-rate `Dropout` layers are **live** during TENT's entropy forward. That means the entropy
objective the optimizer sees is **stochastic**, and every recorded quantity — the scored
logits, the entropy value, the gradient, and the resulting affine update — is a *random draw*
over dropout masks. An earlier version of this lane deliberately held Dropout in eval mode for
mechanism isolation. That is defensible science but it is **not literal official TENT**, and
shipping only that arm would have left a hole.

**The resolution.** Freeze **four** arms:

| arm | BN statistics | trainable | entropy step | Dropout in the scored/entropy forward | is this canonical? |
|---|---|---|---|---|---|
| `SOURCE` | frozen source running stats | none | none | off (eval) | — (baseline) |
| `BN_ONLY` | test-batch | none | none | off (eval) | — (control) |
| `TENT_LITERAL` | test-batch | BN affine γ/β | 1/batch | **ON** (`model.train()`) | **yes — literal official semantics** |
| `TENT_DET` | test-batch | BN affine γ/β | 1/batch | **OFF** (forced eval) | **no — diagnostic control only** |

### 2.3.1 One forward, used for both scoring and entropy

This was the remaining blocker and it is now fixed in code, not just in prose. For every
incoming batch the entropy arms execute **exactly one** forward:

```
logits_pre = model(x)            # official TENT train-mode configuration
record(logits_pre)               # <-- the SCORED prediction for this batch
loss = softmax_entropy(logits_pre).mean(0)
loss.backward()
optimizer.step()                 # only the 80 BN affine scalars
```

`logits_pre` is **the same tensor object** that the entropy is computed from. There is **no
second, Dropout-off scoring forward** anywhere in the module — `entropy_forward` is the single
entry point, and it returns `(logits, loss)` together so the two cannot diverge. Consequences:

* under `TENT_LITERAL` the scored logits **contain the effect of active Dropout**. That is what
  "literal" means here, and it is the whole point of the arm;
* under `TENT_DET` the scored logits are deterministic w.r.t. Dropout, and are likewise both
  scored and used for the update;
* the prequential guarantee is preserved: the parameters have **not** moved when the batch is
  scored, because `optimizer.step()` comes after `record(...)`.

An earlier draft of this spec said "Dropout is off for the prediction forward". That was
internally inconsistent with calling the arm literal, and the owner correctly caught it. The
current code has no such second forward.

**Verification.** NC20 asserts scored and entropy logits are numerically identical; NC21
asserts exactly one `model(x)` call site in the adaptation region, one inside
`entropy_forward`, and — via a runtime `forward_pre_hook` — exactly one forward invocation per
batch (not two); NC22/NC23 assert the Dropout mode of *that* forward per arm; NC24 asserts the
two TENT arms agree on sample geometry, batch geometry, BN configuration, optimizer, learning
rate, adapted parameter set, step count and scoring timing, differing only in Dropout mode.
Every one of those has an injected violation and is proven to bite.

**What is still `eval()` and why.** `SOURCE` and `BN_ONLY` never leave `eval()`. For `BN_ONLY`
this is numerically inert: with `track_running_stats=False`, PyTorch's `BatchNorm*` uses batch
statistics in **both** modes, which is why the arm is defined by that flag rather than by the
training flag. Verifier `H2d`/`H2d2` assert the modes at runtime.

### 2.3.2 RNG convention for the stochastic arm

`TENT_LITERAL` is inherently stochastic and **we do not remove that stochasticity**. Instead a
deterministic seeding convention is frozen before any result exists:

```
seed(unit, batch) = SHA256("EEGTTA-PHASE1|v1|{variant}|{arm}|{subject}|{model_seed}|{batch}")
                    mod (2**31 - 1)
```

with `variant = metadata_order`. Requirements this satisfies, each asserted:

* **a rerun of the same unit reproduces it bit-for-bit** (NC26 asserts an actual end-to-end
  replay of a synthetic unit);
* **units cannot inherit mutable RNG state** from previously processed units, so *completing,
  skipping or reordering units cannot change any other unit's trajectory* (NC25 asserts
  stability, distinctness across subjects/arms/model-seeds/batches, and independence from
  derivation order);
* there is no single global RNG stream that resumption could desynchronise.

`torch.manual_seed` (and `torch.cuda.manual_seed_all` when CUDA is present) are re-applied
**before every batch's scored forward**, from that batch's derived seed. The exact payload
string is recorded per batch as `rng_seed_payload`, so the mapping is hashable and auditable
after the fact.

**Stated plainly:** *`TENT_LITERAL` is one reproducible stochastic realization of the literal
reference method.* It is not an average over dropout masks, and no post-result RNG sweep is
part of Phase 1 — a stochastic-replicate analysis would be a separately licensed diagnostic
branch.

**Relation to the legacy prototype.** `project/run_tent_rbf_baselines.py` set
`dropout_during_adaptation: false` and raised if Dropout was active. Its verdict on this point
agrees with `TENT_DET`; but its wider protocol is KILLed for four other reasons
(`LEGACY_EEGNET_PROVENANCE.md` §5).

### 2.4 Reset semantics, stated exactly

At the start of subject *i*'s episode:

* parameters ← the source checkpoint's `state_dict` (all 21 entries, i.e. parameters *and*
  BatchNorm running buffers);
* TENT arms only: a **fresh** `Adam` optimizer is constructed, so its moment estimates are
  zero — no optimizer state is inherited from subject *i−1*;
* the stream position is reset to 0.

At the end of subject *i*'s episode the adapted model is dropped. Nothing is written back to
the checkpoint, and no adapted weights are reused. Enforced by NC3 (every episode's starting
state hash equals that subject's checkpoint state hash).

**Not run in Phase 1:** continual-across-subject adaptation (prompt §9, §37). It is a
different hypothesis and is PARKed.

### 2.5 Optimizer-state detail that differs between our code and the reference, deliberately

The reference's `forward_and_adapt` calls `loss.backward()` **without** a preceding
`zero_grad()`, then steps, then zeroes. With `STEPS = 1` (frozen here, F7) the two orderings
are numerically identical because gradients start from `.grad is None`. Our implementation
calls `optimizer.zero_grad(set_to_none=True)` **before** `backward()` — the conventional
PyTorch order.

This is recorded as a **[MINIMAL ADAPTATION]** deviation. It cannot change any Phase 1 number
because `steps_per_batch = 1` is frozen; if a later phase raises `steps_per_batch`, the
gradient-accumulation semantics must be revisited *before* the change is made, not after.

### 2.6 Phase-cycle semantics, per arm

The runner re-asserts the model mode before every forward, so no arm can silently drift into
the wrong mode:

```
for each batch x_t:
    prepare_adaptation_mode(arm, model)
        # TENT_LITERAL: model.train()              -> Dropout LIVE
        # TENT_DET:     model.train() + Dropout eval
        # SOURCE/BN_ONLY: model.eval()
    torch.manual_seed(unit_rng_seed(unit, t))     # frozen per-unit RNG convention

    if arm in TENT arms:
        logits, loss = entropy_forward(arm, model, x_t)   # THE single forward
        record(logits)                                    # scored prediction
        loss.backward(); optimizer.step()                 # BN affine only
    else:
        logits = model(x_t) under no_grad / inference_mode
        record(logits)
```

`BN_ONLY` never leaves `eval()`; its normalization still uses batch statistics because
`track_running_stats` is `False`, so the training flag has no numerical effect there.

### 2.7 What is NOT implemented

No EATA, SAR, CoTTA, MEMO, diversity regularisation, confidence filtering, reset mechanism,
anti-collapse loss, custom normalisation, or batch-ensemble. No modification to EEGNet. No
change to the loss. Phase 1 is an existence test (prompt §0, §27C, §37).

---

## 3. Known collapse / instability in the literature — so nothing here is presented as new

Phase 1 is an existence test on a specific frozen benchmark; the general phenomenon is
**already known**, and the report must say so (prompt §31). Relevant prior work:

* **BatchNorm statistics under distribution shift** — Niu et al., *Towards Stable Test-time
  Adaptation in Dynamic Wild World* (ICLR 2023 spotlight), identifies **small batch size** and
  **class imbalance in the test stream** as the two causes of error accumulation /
  degeneracy in test-time adaptation, and introduces a sharpness-aware, reliable-sampling
  remedy. That is precisely the mechanism family BN_ONLY is designed to separate from
  entropy descent.
* **Entropy-minimisation degeneracy** — Han et al., *Ranked Entropy Minimization for
  Continual Test-Time Adaptation* (ICML 2025) [arXiv:2505.16441](https://ar5iv.labs.arxiv.org/html/2505.16441)
  targets the known failure of naive entropy minimisation to produce trivial, collapsed
  predictions, motivating a ranked objective.
* **EEG-domain TTA already exists** — e.g. *Calibration-Free EEG-based Driver Drowsiness
  Detection with Online Test-Time Adaptation* (arXiv:2511.22030) updates only BatchNorm
  parameters on test samples; *StableSleep* (arXiv:2509.02982) couples source-free TTA for
  sleep staging with explicit safety rails. So "TTA on EEG" is not a novel setting.

**Therefore Phase 1 may not claim**: *"we discovered that entropy-minimization TTA can
collapse"*, *"TENT is bad for EEG"*, or *"class imbalance causes collapse"*. What Phase 1 can
establish is bounded and stated in §4.

---

## 4. What a Phase 1 result is allowed to mean

Permitted claim shape (prompt §35):

> Under the frozen ds004902 + EEGNet + subject-LOSO + session-blocked stream protocol,
> canonical episodic TENT did / did not show collapse-like degeneration, where "collapse-like"
> means a reliable drop in balanced accuracy **together with** a reliable contraction of
> prediction diversity as defined in `COLLAPSE_TAXONOMY` (see the report and
> `src/p1_collapse.py`).

Forbidden: population claims beyond this dataset/protocol; causal claims from co-occurrence
(parameter drift ↑ while BAcc ↓ is *co-occurrence*, not causation — prompt §22, §25);
mechanism claims that an intervention has not tested; and any statement that Phase 1 solved
anything (prompt §35).
