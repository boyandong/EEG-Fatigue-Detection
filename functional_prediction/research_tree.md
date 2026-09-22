# Research Tree — Branch A: Functional Prediction

**Branch:** `functional_prediction/`
**Question:** can EEG provide reliable, objective functional-performance information for
*unseen* users, ultimately supporting safety-relevant decisions?

This is this branch's own tree. Branch B (`tta_collapse/`) has a separate tree and does not
share this one. Do not merge them.

---

## North Star

For an unseen user, does short-duration EEG carry generalisable information that predicts
**objective functional decline**?

**Current answer: no such predictor has been demonstrated in this project.**

---

## TRUNK — the only things currently reliable

* Auditable data/QC pipeline; immutable raw data; manifests and hashes.
* **Subject-level split discipline** (subject-LOSO, both sessions co-assigned).
* Independent verifiers, negative controls, and a provenance model based on content SHA-256.
* The frozen ds004902 source trunk (borrowed from `../shared/`, not owned here).
* The BCIT behavioural apparatus: identity linkage, real vehicle channels, one clock.

---

## KEEP

| item | why it survives |
|---|---|
| `M` as a **measurement property** | repeatable, short-term stable, a tonic spectral proxy. **`M` is NOT a validated vigilance biomarker and has no predictive validity.** |
| `LN` as a measured lane-control channel | centre at `LN = 0`, lane half-width measured at **0.917 m**, units in metres |
| Family A `mean |LN|` | the project's **first eligibility-passed objective target** |
| The `3200` grid | a measured ~40 s condition cycle delimiting **6 blocks**; windows cut only on its onsets |
| The moving-block-over-episodes uncertainty method | with its iid negative control, worth up to 45 % of interval width on an autocorrelated series |
| The calibrated block-wise iAAFT full-pipeline null | *the* significance procedure for this data; surrogate null measured centred **negative** (−0.0439 ± 0.212, 200 runs) |
| The ds004902 NEGATIVE result itself | an experiment whose validity is independently established, reporting a hypothesis that was not supported |
| Phase 4A3's gap audit | defect characterised, measured inert, and the numbers re-derived to ~1e-14 |

---

## NEGATIVE / KILL

**NEGATIVE** means the experiment was valid and the hypothesis was not supported. These stay in
the record as findings.

| branch | statement |
|---|---|
| ds004902 tonic `M → PVT` predictive branch | **NEGATIVE.** `M` was reproducibly measurable; it showed **no out-of-sample predictive value** for PVT deterioration (`Q²_skill(M1) = −0.0574`, `p_perm = 0.7445`, n = 29). |
| `J` incremental branch | **NEGATIVE.** `J` is a mixture with no incremental value. |
| `V` | audit-only; no predictive role. |

**KILL** means it must not be reopened without new independent evidence:

* any further feature / model / protocol search **on those 29 subjects**;
* longer-duration rescue; median-RT rescue; `J` incremental rescue; `V`/`J_res` replacement rescue;
* SADT as a personal-alert-baseline dataset.

A null result is the result. Re-tuning until something turns significant is a project-level
forbidden pattern.

---

## INVALIDATED — an empty category, and one withdrawn entry

**`INVALIDATED`** means an apparatus or data defect was found, so the run may not be used for a
hypothesis verdict. It is a *different* category from `NEGATIVE`, and the two must not be merged.

**No branch currently holds this status.** One entry was assigned it and later withdrawn:

| branch | status |
|---|---|
| Phase 4A — historical BCIT baseline | **INVALIDATION WITHDRAWN** — see below. Stands as valid negative evidence under its frozen protocol. |
| Phase 4A2 — adaptive SFFS historical branch | **INVALIDATION WITHDRAWN** — see below. Valid executed branch; no reliable positive effect established. |

⚠️ **Phase 4A and 4A2 were marked `INVALIDATED`, and that status was subsequently WITHDRAWN by
Phase 4A3.** The defect is real but **inert**: 0 of 82 550 defective rows appeared in any training
or test mask, and the corrected run reproduces Phase 4A to **~1e-14** per participant
(population-level `mean ΔR` = **−4.0e-15**). Both the defect history and the resolution must travel
together — see `evidence/phase4a3/GAP_CONTAMINATION_AUDIT.md` §3 (impact claim refuted),
`evidence/phase4a3/mask_definitive.json` (0 of 82,550) and
`evidence/phase4a3/clean_standard_run.json` (the reproduction).

**Do not present these as clean negatives, and do not present them as invalidated.** Presenting
either reading alone is false; the withdrawal is part of the result. These are the project's most
easily misread entries.

**Phase 4A2's limit must travel with it too:** the calibrated null had only **`K = 8`** replicates
per participant (p-value floor `1/9 = 0.111`), so it cannot resolve a 5 % effect. The honest
statement is *"no reliable positive effect established"*, **not** *"disproven"*.

---

## TEST NEXT — PI decisions, not automatic continuations

1. **The raw `|LN|`-in-gap question** — needs the payloads re-downloaded. A PI acquisition
   decision.
2. **A formal calibrated null for the corrected effect.** Cost measured in
   `functional_prediction/audit/phase4a3/FULL_NULL_RESOURCE_PLAN.md`. **Requires a remote CPU server; not permitted
   on this machine.**
3. **A mature-baseline literature reassessment** — is there an independent, modern trunk worth
   testing against the frozen endpoint?

---

## PARK — frozen; a session may not touch these

* **Phase 4B (cross-subject) is NOT licensed.** Subject-LOSO, cross-site, cross-person,
  zero-shot, few-shot and personal calibration were **not run**.
* **Family B perturbation-RT** — INCONCLUSIVE, pending a targeted diagnostic. Not killed, not
  usable.
* personal-relative vs absolute current-state representation; Calibration subtraction as a
  fatigue contrast; new EEG features; new networks; latent impairment; SADT external validation;
  few-channel deployment; uncertainty/abstention; safety decision layer.
* the historical **≈90 s centred smoothing** as a deployment definition — it uses future
  samples. Admissible only as a historical replication sensitivity, and never across a block or
  condition boundary.

---

## Open PI decisions

1. Is `mean |LN|` and hard safety failure **one target or two**?
2. Does the systematic leftward offset belong in the **target** or in the **nuisance**?
3. Authorise cohort-scale behavioural acquisition (302.5 GiB / ≥ 23 h), or proceed on the
   3-participant validation?

---

## What this branch does NOT claim

* That EEG predicts functional decline for an unseen user. It has not been shown.
* That the BCIT endpoint supports a modelling claim. It is under clean-baseline validation.
* That the historical ≈0.374 reference reproduces. It is a **reference, never a target**.
