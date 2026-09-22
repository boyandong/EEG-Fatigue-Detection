# Validation protocols

The evaluation rules this project holds itself to. They are stated here because they are the actual
scientific contribution: the numbers change with the dataset, but the discipline does not.

Each rule below is followed by **how it can fail** and **what catches it**, because a rule with no
failure mode is not a rule.

---

## 1. Subject-level separation

**Rule.** For any cross-subject claim, a participant appears in **exactly one** of train / validation
/ test. Both of a participant's sessions are co-assigned — a subject is never split across folds.

**Applied as:** subject-LOSO, 68 folds, frozen seed `20260908`
(`shared/.../source_only_500hz_v1/splits.json`).

**Failure mode it prevents:** within-subject leakage, which inflates cross-subject performance
because the model recognises the person rather than the state.

**How it fails.** A split can be subject-clean and still leak — through normalisation statistics, or
through feature selection, or through a shared preprocessing step fitted on all data.

**What catches it.** `splits.json` carries the manifest hash it was built from, and
`verification.json` asserts *disjoint subject splits* and *deterministic splits* as explicit checks.
The branch test suites re-assert the leakage boundary directly.

---

## 2. Train-only preprocessing and tuning

**Rule.** Every fitted transform — scaling, PCA, feature selection, hyper-parameter choice — is
fitted **strictly inside the outer training fold**. Whole-data preprocessing is forbidden.

**Applied as:** nested CV. Phase 2 uses outer LOSO(29) × inner LOSO(28), with scaling and alpha
selection inside the outer training fold (`phase2_summary.json: cv`). Phase 4A-family uses
leave-one-BLOCK-out with the mask defined in `DRIVING_MASK_SPEC.md`.

**Failure mode it prevents:** selection leakage — the subtle case where a choice made after seeing
all the data is silently baked into a "clean" split.

**How it fails.** It is easy to fit a scaler once, globally, and pass it down. Nothing errors.

**What catches it.**
`functional_prediction/tests/test_phase2_ridge.py` establishes that the nested-LOSO machinery
**respects the leakage boundary** — 22/22 checks. `phase4a3/outputs/sffs_equivalence.json` pins the
optimised selection criterion against the frozen reference (max per-subset difference `1.1e-16`).

---

## 3. A no-model baseline

**Rule.** Every predictive claim is scored against a **no-information baseline** on the same folds,
with the same metric. Skill is reported relative to it, not as a raw correlation.

**Applied as:** `M0` — a no-EEG baseline — for the PVT branch. `Q²_skill` is the skill *over* `M0`.

**Why it matters here specifically.** In the Phase 2 measurement, `Q²_skill(M1) = −0.0574` is
**negative**: the model did worse than the baseline. A raw correlation would have looked like a
result; the baseline is what makes the negative visible.

**Failure mode it prevents:** reporting an in-sample-looking number as if it were predictive skill.

---

## 4. Permutation inference, with the null reported honestly

**Rule.** Significance comes from a permutation null that **re-runs the whole pipeline** per
replicate — not from a t-test on the observed predictions.

**Applied as:** 5,000 permutations, seed `20260916`, each replicate re-running outer LOSO + inner
LOSO + scaling + alpha selection
(`permutation_summary.json: each_replicate`). p-value arithmetic:
`p = (1 + #{>= observed}) / (B + 1)`.

**The part that is easy to get wrong.** The null here is **centred negative** (mean `−0.0361`,
SD `0.0648`), so a `Q²` near zero is *not* "no worse than chance" in this design. Publishing the
p-value without the null mean would mislead.

**Failure mode it prevents:** a null that is cheaper than the analysis it is meant to calibrate, and
which therefore does not actually test the pipeline.

---

## 5. Calibrated nulls over post-hoc nulls

**Rule.** When a null exists, it is chosen **before** seeing the result, and it is reported alongside
any historical null. No single null may be selected after the fact.

**Applied as:** Phase 4A2 reports both the historical null (14/25 significant) and the calibrated
block-wise iAAFT full-pipeline null (0/25 significant), with
`null_chosen_post_hoc: false` recorded in `adaptive_null_summary_FORMAL.json`.

**The honest caveat, which travels with the result.** That calibrated null has
**`K = 8` replicates per participant** (`K_per_participant: 8`, `K_achieved_min: 8`), giving a
p-value floor of `1/9 = 0.111`. **`K = 8` cannot resolve a 5 % effect.** The correct public wording is
therefore *"no reliable positive effect was established"* — **not** *"the effect is disproven"*. The
resource plan for a larger `K` exists; the run requires a server and was not performed.

**Failure mode it prevents:** quietly swapping in whichever null yields significance.

---

## 6. Independent verification, and checks that can fail

**Rule.** A result is not accepted until a **separate** script re-derives it — ideally from raw
sources rather than the pipeline's own intermediate output. And every **static** check must be proved
able to catch a **deliberately injected violation**.

**Why the second half is not optional.** This project has already shipped one forbidden-pattern
checker that silently passed real violations. It was found only by negative controls. A check that
cannot fail is not a check.

**Applied as:** every phase ends with a verifier whose non-zero exit gates completion, paired with
negative controls. Counts and their expected-failure exceptions are tabulated in
[`reproducibility.md`](reproducibility.md) §6.

---

## 7. Freeze before fitting

**Rule.** Target, protocol, feature set, CV scheme, endpoint and inference are fixed in a **written
specification before the first fit**.

**Applied as:** `SCIENTIFIC_SPEC.md`, `BEHAVIOR_ENDPOINT_SPEC.md`, `DRIVING_MASK_SPEC.md`,
`TENT_METHOD_SPEC.md`, `COLLAPSE_TAXONOMY.md`.

**Consequence, stated as a hard rule:** if a hypothesis returns null, **that is the result**. No
researcher-degrees-of-freedom search. Adding features, swapping algorithms or re-tuning protocols
until something turns significant is forbidden at the project level — it was learned the expensive
way. The Phase 2 branch was **stopped**, not extended.

---

## 8. Test-time adaptation protocol

**Setting.** A frozen source model is adapted **online** to each unseen subject's stream using
unlabeled test data only.

**Episodic per subject.** Parameters, batch-norm state and optimiser state are reset from that fold's
checkpoint at episode start and discarded at the end. **No adaptation crosses a subject.** This is
stricter than the reference implementation, which is a pooled stream.

**The four arms, and why the distinction is the whole experiment:**

| arm | BN statistics | trainable | entropy step | Dropout in scored forward | role |
|---|---|---|---|---|---|
| `SOURCE` | frozen source running stats | none | none | off | baseline |
| `BN_ONLY` | test-batch | none | none | off | **gradient-free control** |
| `TENT_LITERAL` | test-batch | BN affine γ/β (80 scalars) | 1/batch | **ON** | **canonical TENT** |
| `TENT_DET` | test-batch | BN affine γ/β (80 scalars) | 1/batch | OFF | diagnostic control |

**`TENT_DET` is never called canonical TENT.** Only `TENT_LITERAL` follows the pinned reference
semantics.

**One pre-update forward serves both scoring and entropy.** `entropy_forward` returns
`(logits, loss)` together, so the recorded prediction and the adaptation objective cannot diverge.
This is what makes the literal arm literal, and it is falsifiable: the smoke test asserts
`max|diff| = 0.000e+00` and exactly one forward per batch.

**`BN_ONLY` is the load-bearing control.** Without a gradient-free adaptation arm, a degradation
would be attributed to entropy minimisation by default. With it, the attribution changes — which is
what happened here.

**Frozen, no sweep:** Adam `lr 1e-3`, β `(0.9, 0.999)`, `wd 0`, 1 step/batch, batch size 32; batches
never cross a visit.

**Statistical unit: the subject**, with a 10,000-resample paired bootstrap. **Never the 9,390
windows** — windows within a subject are not independent.

---

## 9. What "collapse" means here — and what it does not

Collapse requires **two** things together: reliable performance degradation **and** reliable
prediction-diversity contraction. Either alone is something else:

| observation | what it is | what it is NOT |
|---|---|---|
| conditional entropy `H_cond` falls | *the objective working* | never evidence of collapse |
| accuracy falls | *degradation* | not collapse |
| diversity contracts, accuracy holds | *concentration* | not collapse |

Both criteria must hold, so this definition can **fail to fire** — and in the executed experiment it
did not fire in any arm. That is the finding.

---

## 10. Branch isolation

**Rule.** The two branches are independent hypothesis trees that share infrastructure. They are not
one another's evidence.

**Forbidden:** modifying one branch because the other returned a null; using one branch's result to
support the other's hypothesis; mixing `outputs/` across branches; copying anything out of `shared/`
into a branch.

**Why.** A null in the PVT branch says nothing about TTA stability — different questions, different
targets, different endpoints. A shared trunk does not make shared conclusions.

**Allowed, and the only allowed form of sharing:** reading the frozen trunk by relative path; reusing
helpers by import, never by copy; and *provenance* queries in either direction (e.g. verifying that
the trunk being adapted is the same one the baseline used). That is auditing, not evidence
inheritance.
