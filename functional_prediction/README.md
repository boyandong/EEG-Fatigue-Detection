# Branch A — Functional Prediction

**Question.** Can EEG provide reliable, objective functional-performance information for *unseen*
users — ultimately supporting safety-relevant decisions?

**Current answer: no EEG → objective-functional-decline predictor has been demonstrated in this
project.** One sub-branch is a rigorous negative result; the other is still under clean-baseline
validation.

This branch is **scientifically independent** of `../tta_collapse/`. They share the frozen source
trunk in `../shared/` and nothing else. Neither branch's result licenses a conclusion about the
other, and no number may be quoted outside the branch that produced it.

---

## 1. What this branch owns, and what it borrows

This branch **owns** its phase history, its endpoint specifications and its BCIT apparatus. It
**borrows** the frozen ds004902 source trunk from `../shared/` — it holds no copy of the manifest,
the split or the EEGNet checkpoints.

| borrowed artefact | canonical location |
|---|---|
| 9,390-window manifest | `../shared/ds004902_source_trunk/legacy_apparatus/outputs/source_only_500hz_v1/segments.csv` |
| frozen subject-LOSO split (68 folds, seed 20260908) | same directory, `splits.json` |
| 61-channel order, label mapping | same directory, `channels.json` / `config.json` |
| EEGNet architecture + hyper-parameters | `../shared/ds004902_source_trunk/legacy_apparatus/configs/baselines.json` |
| 204 EEGNet LOSO checkpoints | manifest at `../shared/ds004902_source_trunk/checkpoints/` (weights not redistributed) |
| raw ds004902 and BCIT payloads | external datasets — see `../docs/REPRODUCIBILITY.md` |

---

## 2. The ds004902 phase family — a NEGATIVE result

| phase | status | finding |
|---|---|---|
| Phase 1 | **NEGATIVE** | The short-duration tonic EEG representation `M` is **reproducibly measurable**: repeatable, short-term stable, a tonic spectral proxy. |
| Phase 1.5 | **NEGATIVE** | `J` / `V` measurement audit. `J` is a mixture with no incremental value; `V` is audit-only. |
| Phase 1.75 | **NEGATIVE** | Dynamic / stability extension of the same branch. |
| Phase 2 | **NEGATIVE — CLOSED** | `M → PVT`: **no out-of-sample predictive value**, under nested LOSO with a no-EEG baseline and permutation inference. |

**The Phase 2 result, in the form it should be quoted:**

> A predefined tonic resting-EEG representation was reproducibly measurable but did not
> demonstrate out-of-sample skill for predicting PVT deterioration under strict nested
> leave-one-subject-out cross-validation.

| statistic | value | artifact |
|---|---|---|
| `Q²_skill(M1)` | **−0.0574** | `evidence/phase2/permutation_summary.json` |
| permutation `p` (5,000 permutations, seed 20260916) | **0.7445** | `evidence/phase2/permutation_summary.json` |
| subjects `n` | **29** | `evidence/phase2/phase2_summary.json` |
| null mean / SD | −0.0361 / 0.0648 | `evidence/phase2/permutation_summary.json` |
| fraction of null replicates > 0 | 0.1528 | `evidence/phase2/permutation_summary.json` |
| cross-validation | outer LOSO(29) x inner LOSO(28); scaling and alpha selection strictly inside the outer training fold | `evidence/phase2/phase2_summary.json` |

**This is a valid negative, not an invalidated one.** The apparatus worked; the hypothesis was
not supported. The distinction matters and must not be blurred.

**Scope — read this before quoting the number.** The result is representation-, task- and
dataset-specific. It is **not** evidence that EEG cannot predict PVT in general, and it does not
license that generalization. Note also that the permutation null is centred **negative**
(mean `−0.0361`), so a `Q²` near zero is not "no worse than chance" in this design.

What **survives** as a measurement property: `M` is repeatable and stable. What does **not**
survive: any claim that `M` is a validated vigilance biomarker or has predictive validity. It is
not, and it does not.

**Hard rule, frozen:** no further feature, model or protocol search on those 29 subjects.
Longer-duration rescue, median-RT rescue, `J`-incremental rescue and `V`/`J_res` replacement are
all closed. Reopening any of them is a **new scientific branch**, not debugging.

---

## 3. The BCIT family — endpoint validated, with a defect history

| phase | status | finding |
|---|---|---|
| Phase 3 | HISTORICAL | BCIT metadata audit. |
| Phase 3B | HISTORICAL | Tier-1 raw byte audit. |
| Phase 3C | **VALIDATED** | Behavioural endpoint validation. `mean |LN|` is the project's first **eligibility-passed objective target** (E1–E6). |
| Phase 4A | **STANDS AS PUBLISHED** | Historical baseline. An apparatus defect was found afterwards and then measured to be **inert**. |
| Phase 4A2 | **STANDS AS PUBLISHED — branch CLOSED** | Adaptive SFFS historical branch; same defect, same inert verdict. |
| Phase 4A3 | **THE RESOLUTION** | The defect is **real but inert**: 0 of 82,550 defective rows touched any mask; Phase 4A reproduces to ~1e-14. The `INVALIDATED` status was **withdrawn**. |

### 3.1 Frozen BCIT endpoint facts (do not re-derive)

* `LN` is a *signed* lateral deviation about the lane centre. `LN = 0` **is** that centre —
  verified from the release's own `4220`/`4230` events with 100 % agreement in 5/5 recordings.
  The lane half-width measures **0.917 m** (spread 1.9 mm across three site classes). Units are
  metres.
* The `3200` marker is a measured **~40 s periodic grid** (median 38.5–40.2 s) delimiting
  **6 protocol blocks**. Analysis windows are >= 300 s and are cut **only on `3200` onsets**
  (<= 340 s apart), inside the valid (non-zero-padded) window.
* The 2x2 condition **labels are NOT behaviourally recoverable** — the perturbation-rate factor
  varies by only 1.08–1.18x across blocks. **Do not invent condition labels.**
* `legacy_labID` is the calibration→baseline pairing key — **never** `sub-NN` (a naive `sub-NN`
  join is 89 % wrong).
* BCIT's "degraded" state is **within-visit time-on-task fatigue, not sleep deprivation.**
* Every recording's vehicle channels are **zero-padded** at both ends; a lane statistic over
  whole-file bounds would include fabricated perfect performance.

### 3.2 What is NOT established for BCIT

* That the BCIT endpoint supports any EEG modelling claim. It is under clean-baseline validation,
  and **no BCIT objective-behaviour modelling result is claimed.**
* That a time-on-task effect exists: naive `T_session` coefficient **+0.088 ± 0.058 m/h**,
  condition-aware F-test **p = 0.94**.

### 3.3 The gap-contamination episode — how to read Phase 4A / 4A2

An apparatus defect was found **after** Phases 4A and 4A2 had run: `20_extract_cache.py`'s
`moving_average` left every row outside the protocol-block intervals holding values no 90 s mean
can produce — the target reaching **11,909 m** of lane deviation against a 0.917 m lane
half-width, predictors reaching **±79,769** log-units against a legitimate range of −3.45…+9.82.
The underlying `abs_ln4` in those rows is physically normal (mean 0.343 m, max 1.51 m), so the
values were **manufactured by the smoothing helper**, not measured. **82,550** rows across the
cohort (13.8 %–27.4 % of each valid span) are affected.

A finding then claimed those rows sat inside every training mask, which would have invalidated
both phases. **Phase 4A3 measured it and refuted the impact claim:**

* **0 of 82,550** defective rows appear in any training or test mask of any of the 149 folds
  (`mask_definitive.json`);
* the corrected pipeline reproduces Phase 4A to **~1e-14** on all 25 participants
  (mean R `−0.04993651757569635` versus `−0.04993651757569237`), and the A3 per-participant ΔR to
  full precision;
* the corrected series is the shipped series restricted to the blocks, verified to float32
  precision with **no re-extraction**.

**Therefore the `INVALIDATED FOR SCIENTIFIC VERDICT` status attached to Phase 4A / 4A2 is
WITHDRAWN.** One audit-instrumentation discrepancy remains unexplained and changes no number.

⚠️ **Both readings must travel together.** Presenting Phase 4A/4A2 as a clean negative is false.
Presenting them as invalidated-by-contamination *without* citing Phase 4A3 is also false. The
authoritative reading is Phase 4A3: the defect is real, it is in the smoothing helper rather than
the driving, and it changed no number.

### 3.4 The Phase 4A-family numbers, and why the branch is closed

Cohort N = 25, within-person, leave-one-BLOCK-out over **149 folds**, target `mean |LN|` in
metres.

| statistic | standard (control) | adaptive (A3) | ΔR |
|---|---|---|---|
| mean R | **−0.0499** | **+0.0044** | **+0.0543** |
| SD R | 0.2455 | 0.2666 | — |
| median R | −0.0265 | −0.0089 | — |
| participants R > 0 | 12/25 | — | — |

**No significance claim is made.** There is no calibrated null for these observed effects. On the
adaptive branch specifically: 15/25 positive, paired t-test **p = 0.140**, **0/25** decidable
against the calibrated block-wise iAAFT full-pipeline null, and fold-to-fold selection stability
**Jaccard 0.118** with 136 distinct channel subsets across 149 folds. The adaptive lifetime ends
here; changing the channel count, criterion, frequency range, smoothing, PCA, regression or cohort
is a **new scientific branch**, not debugging.

The published `R ≈ 0.374` from the historical literature is a **reference, never a target.** No
code path reads it as an objective, stopping rule or threshold. Tuning toward it is forbidden
without a new specification.

---

## 4. What is NOT proven

* That any EEG feature predicts objective functional decline for an unseen user.
* That the BCIT objective-behaviour endpoint supports any modelling claim — it is under
  clean-baseline validation.
* That the historical `R ≈ 0.374` reference is reproducible; it is a reference, never a target.
* Anything cross-subject: **Phase 4B is NOT licensed.**
* Any deployment, personalisation, domain-adaptation, few-channel, uncertainty/abstention or
  safety-decision-layer claim.

---

## 5. TEST NEXT — PI decisions, not automatic continuations

1. A **formal calibrated null** for the corrected effect. Cost is measured in the local resource
   plan; it **requires a remote CPU server** and is **not permitted on this machine**.
2. A **mature-baseline literature reassessment** — does an independent, modern, mature trunk exist
   that is worth testing against the frozen endpoint?
3. The raw `|LN|`-in-gap question — needs the payloads re-downloaded; a PI acquisition decision,
   parked.

---

## 6. PARK — not licensed

Cross-subject BCIT modelling; personalisation; domain adaptation; deployment; few-channel work;
uncertainty/abstention; safety decision layer; the historical ≈90 s centred smoothing as a
deployment definition (it uses future samples, and is admissible only as a historical replication
sensitivity that never crosses a block or condition boundary).

---

## 7. Verification gates

Every phase ends with an independent verifier whose exit code gates completion, and every static
check has proved negative controls. Full table and run instructions:
`../docs/REPRODUCIBILITY.md`. The public, data-free baseline is:

```bash
python tests/test_mechanism.py        # unit tests, no data required
python tests/test_phase2_ridge.py     # unit tests, no data required
```

The phase verifiers additionally require the frozen trunk artifacts, and the later-phase verifiers
additionally require the raw datasets — their coverage is stated rather than implied.

---

## 8. Files

| path | what it is |
|---|---|
| `SCIENTIFIC_SPEC.md` | branch scientific specification |
| `BEHAVIOR_ENDPOINT_SPEC.md` | the frozen BCIT behavioural target |
| `research_tree.md` | KEEP / TEST NEXT / PARK / KILL, as the agent workspace holds it |
| `PHASE1_REPORT.md`, `PHASE1_5_REPORT.md`, `PHASE1_75_REPORT.md`, `PHASE2_REPORT.md` | the NEGATIVE ds004902 phase family |
| `PHASE3_DATASET_AUDIT.md`, `PHASE3C_BEHAVIOR_ENDPOINT_REPORT.md` | BCIT audit and behavioural endpoint validation |
| `phase3_metadata_survey_2026.md` | BCIT metadata survey supporting Phase 3 |
| `official_raw_recovery_plan.md`, `paper_sample_reconciliation.md` | PVT target recovery and sample reconciliation |
| `src/`, `scripts/`, `config/`, `tests/` | the live pipeline (Phases 1–2) |
| `evidence/` | selected lightweight evidence: the Phase 2 permutation/bootstrap summaries, PVT target audit, pilot manifests, dynamic-audit statistics |

⚠️ Some reports and manifests contain the **literal absolute paths of the machine at execution
time**. They are **historical records, not live configuration** — nothing reads them to locate
data. See `../docs/PROJECT_HISTORY.md` §"Path portability" for the declared substitutions made
when this public snapshot was produced.
