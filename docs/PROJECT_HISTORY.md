# PROJECT_HISTORY.md

The full narrative of how this repository got from an NS-vs-SD classifier to two independent
research branches. Written so that a reader can tell **what was believed when**, and can see
where earlier conclusions were corrected rather than quietly replaced.

Dates are the project's own session stamps.

---

## Phase 0 — NS vs SD EEG classification (the original repository)

**Question asked:** can a model distinguish *normal sleep* (`ses-1`, labelled NS) from *sleep
deprivation* (`ses-2`, labelled SD) from EEG?

**What was built.** Three model families, under `baseline/`, `feature_extracting/` and `model/`:

* an LSTM over extracted `[N, 16, 5, 14, 14]` feature grids;
* an EEGNet over raw 61-channel EEG;
* an MSCViT + TCN model over wavelet-convolved feature grids;

with a feature extractor, a 14x14 electrode-to-grid mapping, and a subject-wise train/val/test
split. The original README was written in Chinese.

**What was sound and survived.** Subject-wise splitting (no participant in both train and test);
train-only normalisation; no label leakage through preprocessing. These three commitments are
still the rule in the current project.

**Why it was not enough.** The formulation answers *"which condition is this participant in?"*,
not *"what is this participant's current functional state?"*:

* `ses-1`/`ses-2` are **condition identifiers, not visit-order identifiers** — the release
  counterbalances visit order and records the true order separately, so the contrast is a
  between-visit contrast;
* separating a between-visit condition label does **not** demonstrate tracking of **within-visit,
  time-on-task functional decline**, which is what a safety-relevant application needs;
* there was **no objective performance endpoint** at all — "fatigue" was inferred from the
  experimental condition rather than measured from behaviour.

The original code is preserved verbatim under `archive/legacy/ns_sd_prototype_2026/`, including
its original Chinese READMEs, so that this phase remains auditable.

---

## Phase 1 — measurement audit of a tonic EEG representation (`M`)

**Question:** is there a short-duration tonic EEG representation that is *reproducibly
measurable* across sessions and subjects?

**Result — NEGATIVE for the stronger claim, positive as a measurement property.** `M` (a
short-duration tonic spectral proxy) is repeatable and short-term stable. It is **not** a
validated vigilance biomarker.

The distinction that this phase established, and that the project has kept ever since:
**measurement validity is not predictive validity.** A quantity can be reliably measurable and
still carry no out-of-sample information about anything.

---

## Phase 1.5 — the `J` / `V` measurement audit

**Result — NEGATIVE.** `J` is a mixture with no incremental value over `M`. `V` is audit-only.
A scaling claim about `V` made during this phase was later found to be wrong and corrected; that
correction is one of the two the project records as having been caught by the user rather than by
its own verifiers.

---

## Phase 1.75 — dynamic / stability extension

**Result — NEGATIVE.** The dynamic extension of the same branch did not rescue it. Retained as
negative evidence, with its artifacts under `functional_prediction/`.

---

## Phase 2 — the `M → PVT` predictive branch, and its negative result

**Question, sharpened:** can a **personal-baseline-relative** EEG representation predict
objective vigilance decline (`Y_speed`, derived from PVT) in an **unseen** subject?

**Protocol, frozen before fitting:** outer LOSO over 29 subjects x inner LOSO; scaling and alpha
selection strictly inside the outer training fold; a **no-EEG baseline** `M0` as the reference
model; permutation inference with 5,000 replicates; bootstrap confidence intervals with 10,000
subject-level resamples.

**Result — NEGATIVE:**

| statistic | value |
|---|---|
| `Q²_skill(M1)` | −0.0574 |
| permutation `p` | 0.7445 |
| `n` | 29 |
| null mean / SD | −0.0361 / 0.0648 |
| fraction of null replicates > 0 | 0.1528 |

A negative `Q²` means the model did **worse** than the no-EEG baseline. The permutation null is
centred negative, so this is not a borderline call.

**This was accepted as the result, not worked around.** The project's rule against
researcher-degrees-of-freedom search was written from the experience of this phase. Longer-duration
rescue, median-RT rescue, `J`-incremental rescue and `V`/`J_res` replacement are all **closed**.
No further feature, model or protocol search is permitted on those 29 subjects.

**Scope, which must travel with the number:** the result is representation-, task- and
dataset-specific. It is not evidence that EEG cannot predict PVT in general.

---

## Phase 3 — BCIT/EEG metadata audit

The PVT branch had no comparable objective *performance* endpoint available at cohort scale, so
the project acquired and audited a driving dataset with real vehicle measurements (BCIT). Phase 3
audited its metadata: identity linkage, session structure, event semantics, and whether the
recorded channels mean what the documentation implies.

---

## Phase 3B — Tier-1 raw byte audit

The audit was re-run against **actual bytes** rather than metadata. This established, among other
things, that the vehicle channels are **zero-padded** at both ends of every recording by the
pre/post-logging span, so a lane statistic over whole-file bounds would include fabricated perfect
performance.

Two verifier checks in this lane report **expected failures** because a fifth payload was added
later under a preflight allowance, and both verifiers independently detect it. **They are not
loosened** — the failure is the guard working, and silencing it would destroy the evidence that
the guards guard.

A recorded sampling-rate fact was also corrected here: one legacy payload is **2048 Hz**, not
1024 Hz as an earlier document stated. No conclusion depends on it.

---

## Phase 3C — behavioural endpoint validation

**Question:** is there a defensible, objective, eligibility-passed behavioural target in BCIT?

**Result — the project's first eligibility-passed objective target.** Family A, `mean |LN|` — mean
absolute lane deviation in metres — passes all six pre-registered eligibility checks (E1–E6).

Measurements that constrain every later phase:

* `LN` is a **signed** deviation about the lane centre; `LN = 0` **is** the centre, verified from
  the release's own `4220`/`4230` events with 100 % agreement in 5/5 recordings. Lane half-width is
  **0.917 m**, spread 1.9 mm across three site classes.
* The `3200` marker is a **~40 s periodic grid** (median 38.5–40.2 s) delimiting **6 protocol
  blocks** — not an occasional event. Analysis windows are >= 300 s and are cut only on `3200`
  onsets.
* The 2x2 condition **labels are not behaviourally recoverable** (the perturbation-rate factor
  varies by only 1.08–1.18x across blocks). The project does not invent them.
* `legacy_labID` is the pairing key; a naive `sub-NN` join is **89 % wrong**.
* BCIT's "degraded" state is **within-visit time-on-task fatigue, not sleep deprivation.**

**Also established — and negative:** no reliable time-on-task effect was found in the baseline
driving condition (naive `T_session` coefficient +0.088 ± 0.058 m/h; condition-aware F-test
p = 0.94).

---

## Phase 4A — historical baseline reconstruction

**What ran.** A within-person leave-one-BLOCK-out model on the BCIT endpoint, N = 25 participants,
149 folds, using a reconstruction of a published historical baseline scheme.

**Result.** Standard-arm mean R **−0.0499**; 0/25 participants decidable against a calibrated
block-wise iAAFT null. The published literature value `R ≈ 0.374` was **not** reproduced. That
value remains a **reference, never a target** — no code path reads it as an objective, stopping
rule or threshold, and tuning toward it is forbidden.

A gate in this lane was corrected from an assumed `25 × 6 = 150` fold total to the honest
per-participant invariant `sum_i n_blocks(i) = 149`, because one participant's recording
reconstructs only 5 blocks. No scientific result changed.

---

## Phase 4A2 — adaptive SFFS historical branch

**What ran.** Sequential floating forward selection over a 64-channel candidate space on the same
endpoint, to test whether the fixed historical scheme was simply mis-specified.

**Result — NEGATIVE.** Mean ΔR **+0.0543**; 15/25 participants positive; paired t-test
**p = 0.140**; **0/25** decidable against the calibrated null; population mean p = 0.111 at a K
that cannot resolve 5 %; fold-to-fold selection stability **Jaccard 0.118** with 136 distinct
subsets across 149 folds.

**Closed, with no second rescue.** Changing the channel count, criterion, frequency range,
smoothing, PCA, regression or cohort is a **new scientific branch**, not debugging.

---

## The gap-contamination episode — and its resolution

**This episode is the project's most important correction, and it runs in two directions.**

After Phase 4A2, a defect was found in `20_extract_cache.py`'s `moving_average`: every row outside
the protocol-block intervals held values **no 90 s mean can produce** — the target reaching
**11,909 m** of lane deviation against a 0.917 m lane half-width, predictors reaching **±79,769**
log-units against a legitimate range of −3.45…+9.82. The underlying `abs_ln4` in those rows is
physically normal (mean 0.343 m, max 1.51 m), so the values were **manufactured by the smoothing
helper**, not measured. 82,550 rows (13.8 %–27.4 % of each valid span) were affected.

A finding was published claiming those rows sat inside every training mask, which would have
**invalidated Phase 4A and 4A2**. That status was applied.

**Phase 4A3 then measured the impact claim and refuted it:**

* **0 of 82,550** defective rows appear in any training or test mask of any of the 149 folds;
* the corrected pipeline reproduces Phase 4A to **~1e-14** on all 25 participants
  (mean R `−0.04993651757569635` versus `−0.04993651757569237`);
* the corrected series is exactly the shipped series restricted to the blocks, verified to float32
  precision, reconstructible with **no re-extraction**.

**The `INVALIDATED` status was therefore WITHDRAWN.** Phase 4A and 4A2 stand as published.

One audit-instrumentation discrepancy remains unexplained: read literally, Phase 4A's mask loop
should include the defective rows; executed, it does not. Both candidate readings were evaluated
and only one reproduces the published R, so the discrepancy is a question about the audit script
and **cannot change a number**.

**The rule this episode produced:** presenting Phase 4A/4A2 as a clean negative is false;
presenting them as invalidated-by-contamination without citing Phase 4A3 is also false. Both
readings travel together.

---

## Phase 4A3 — the gap-correction audit (resolution)

Covered above. Its conclusion is the current authoritative reading of the Phase 4A family.

---

## TTA Phase 1 — the second branch opens

**Question, deliberately independent of everything above:** does canonical test-time entropy
minimisation produce **harmful prediction collapse** on unseen-subject EEG streams, and what
mechanism drives it?

This branch was opened as a genuinely separate hypothesis tree. It shares **no** dataset,
endpoint, representation or conclusion with the functional-prediction branch — only the frozen
ds004902 source trunk in `shared/`.

**What was established before any experiment:** the legacy trunk was recovered and **proved**
original (204 EEGNet LOSO checkpoints; manifest, split and config hashes matching the formal run
on both machines), and **SOURCE closure passed** locally and on the remote GPU — max abs Δp
9.537e-07, **0 label flips**, and the historical headline reproduced exactly
(`BAcc = 0.5924169784325324`, to 16 digits). Without that closure the comparison would have been
against a drifted re-implementation.

**The four arms**, run as **816/816 units** on the owner-approved remote server:

| arm | BN statistics | trainable | entropy step | Dropout in scored forward |
|---|---|---|---|---|
| `SOURCE` | frozen source | none | none | off |
| `BN_ONLY` | test-batch | none | none | off |
| `TENT_LITERAL` | test-batch | BN affine γ/β | 1/batch | ON |
| `TENT_DET` | test-batch | BN affine γ/β | 1/batch | OFF (diagnostic) |

**Verdict `CASE 4 — BN/NORMALIZATION INSTABILITY`.** Under the frozen protocol **no harmful
prediction collapse occurs in any arm.** All three adapted arms fall to near-chance and are
mutually indistinguishable — `BN_ONLY` 0.5039, `TENT_LITERAL` 0.5043, `TENT_DET` 0.5035 versus
`SOURCE` 0.5924. `TENT_LITERAL − BN_ONLY` = **+0.00048** (t = +0.22); `BN_ONLY` and `TENT_DET`
agree on **99.65 %** of windows.

The degradation is therefore attributable to the **test-batch normalisation switch**, not to
entropy minimisation. **The entropy gradient is inert.** What remains unexplained — *why* the
normalisation switch harms performance — is a separate question requiring a new PI decision.

**Verification:** independent verifier **105/105**; negative controls NC1–NC27 **75/75 bite**;
synthetic smoke PASS; remote environment, provenance, closure and smoke gates all PASS.

**`CASE 4` names a verdict of an executed experiment.** It is not a taxonomy entry, and it is not
a proposal. The parked methods (SAR, DELTA, T-TIME, T3A, CoTTA, BFT, EATA, MEMO, and the rest)
exist **only as prose in a park list** — there is no artefact for any of them.

---

## The 2026-09-20 branch decoupling

Two hypothesis trees had been sharing one directory, which made them look like one continuous
model experiment. They are not. The tree was reorganised into `shared/`, `functional_prediction/`
and `tta_collapse/`.

**Safety of that refactor, stated plainly:** 608 artefacts were SHA-256'd before and after the
move and **all 608 matched**; exactly two files' *content* changed at move time (a frozen config's
raw-data root and the TTA lane's own path constants), both declared before execution; a further
declared stage-2 set covered documentation path repair and one test-script encoding fix. The
refactor verifier reports **54/54 checks** with **9/9 injected violations detected**. No training,
no re-run, no re-analysis, no download. Large data was moved by same-volume rename and never
copied.

**Governance that came out of it:** the two branches are independent hypothesis trees that share
infrastructure. Modifying one because the other returned a null is forbidden. Mixing `outputs/`,
research-tree verdicts or result directories across branches is forbidden. Copying anything out of
`shared/` into a branch is forbidden — it would fork the trunk.

---

## The 2026-09-22 public-repository refresh

The public GitHub repository still described Phase 0. It was updated to describe the current
program, on a working branch, without force-pushing or rewriting history.

**What changed, in one line:** the public README now describes the shared trunk and the two
branches; the superseded prototype moved to `archive/legacy/`; selected lightweight evidence and
the runnable apparatus were published; machine-specific paths and credentials were removed from
published text.

### Path portability — the declared substitutions

The public snapshot is **not** a byte-identical copy of the local scientific tree, and this is
stated rather than hidden. Two classes of text differ:

1. **Machine-specific and personal paths.** The local Windows home directory, the local
   Anaconda environment root, a temporary path, the remote execution host and port, and the local
   SSH key path were replaced in published text. Historical *reports* were included in this
   substitution, because the alternative — publishing a personal username and an SSH key path —
   is a privacy and security failure, not a scientific one.
2. **One credential-bearing runtime artefact was withheld entirely:** the remote-execution state
   file, which embedded the local SSH key path. It is runtime state, not provenance, and nothing
   in the published apparatus needs it.

**What did NOT change anywhere:** no scientific result, no measurement, no statistic, no
threshold, no verdict, no conclusion, and no algorithm. The substitutions are path and
credential strings only. The SSH password was never stored in the repository — it is read from an
environment variable at run time — so no secret was published and then withdrawn.

Readers who need the unmodified bytes can regenerate the same artifacts from the datasets and the
published code, or ask the owner.

---

## Standing rules this history produced

1. **Never fabricate an executed state.** `PLANNED` / `IMPLEMENTED` / `EXECUTED` / `VERIFIED` are
   distinguished everywhere.
2. **Raw data is immutable.**
3. **No researcher-degrees-of-freedom search.** If a hypothesis returns null, that is the result.
4. **Freeze before fitting** — target, protocol, feature set, CV scheme, endpoint and inference
   fixed in writing before the first fit.
5. **Nested CV or nothing.** Scaling, selection and hyper-parameter choice strictly inside the
   outer training fold.
6. **Verify independently** — a separate script re-derives the result, ideally from raw sources.
7. **A check that cannot fail is not a check.** Every static check must be proved able to catch a
   deliberately injected violation. This project has already shipped one forbidden-pattern checker
   that silently passed real violations; negative controls found it.
8. **Report contradictions, do not smooth them.**
9. **No provenance inflation.**
