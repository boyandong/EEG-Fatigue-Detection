# Reliable EEG Modeling for Vigilance and Functional Performance

**Cross-subject EEG modeling, functional-performance validation, and test-time adaptation.**

![status](https://img.shields.io/badge/status-research%20in%20progress-blue)
![python](https://img.shields.io/badge/python-3.11-blue)
![license](https://img.shields.io/badge/license-not%20yet%20assigned-lightgrey)

---

## What this project asks

> **Can an EEG model become trustworthy for a user it has never seen?**

That question has two halves, and they are not the same question:

* Does a *useful objective functional signal* exist in EEG at all, for an unseen user?
* What happens to a source EEG model when it is *adapted online at test time* on an unseen
  subject's stream?

This repository contains two **scientifically independent** branches addressing those halves on
top of a **shared, frozen source trunk**. Neither branch is evidence for the other; they share
infrastructure, not conclusions.

---

## This repository evolved

**This repository evolved from an NS-vs-SD EEG classification project into two related but
scientifically independent research branches.**

The early project was a *condition* classifier: normal sleep (`ses-1`) versus sleep deprivation
(`ses-2`), with `baseline/`, `feature_extracting/` and `model/` directories holding LSTM,
EEGNet and MSCViT+TCN prototypes. That code is preserved unchanged under
[`archive/legacy/`](archive/legacy/) for historical fidelity.

The project was later **reframed toward objective functional performance and test-time
adaptation reliability**. The reason is a question the original formulation could not answer:
a condition label is a *between-visit* contrast, and separating it does not demonstrate that a
model tracks a participant's *within-visit, time-on-task functional decline* — which is what a
safety-relevant vigilance application would need. The prototype also had no objective
performance endpoint at all.

See [`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md) for the full narrative. The history is
not rewritten anywhere in this repository: the old code, its original (Chinese) README, and the
dated reports all remain as they were written.

---

## Structure

```
.
├── shared/ds004902_source_trunk/   the frozen source trunk both branches read
├── functional_prediction/          BRANCH A — EEG -> objective functional performance
├── tta_collapse/                   BRANCH B — test-time adaptation stability
├── archive/legacy/                 the superseded NS-vs-SD prototype, verbatim
└── docs/                           project history, reproducibility, environment audit
```

---

## 1. Shared source trunk — `shared/ds004902_source_trunk/`

Both branches read **one** physical copy of every shared artefact. Nothing is forked.

| artefact | value |
|---|---|
| dataset | **ds004902** (OpenNeuro) — 4 s tonic eyes-open EEG |
| valid paired subjects | **68** of 71 |
| 4-second windows | **9,390** (class 0: 4,735 / class 1: 4,655) |
| sampling rate | **500 Hz** (records at 5,000 Hz excluded by rule) |
| channels | **61** in a frozen order |
| label mapping | `ses-1 -> 0` (normal sleep), `ses-2 -> 1` (sleep deprivation) |
| split | subject-level LOSO, **68 folds**, seed `20260908` |
| source model | **EEGNet** (braindecode 1.3.2), frozen architecture + hyper-parameters |

The dataset is **not** redistributed here. See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
for the dataset identifier, expected local layout, and the preprocessing entry point.

**Historical source-only benchmark (EEGNet, 68 subjects x 3 seeds).** Subject-mean
accuracy **0.5963**, balanced accuracy **0.5924**, F1 **0.5550**, ROC-AUC **0.6109**. These are
the trunk's published reference numbers, reproduced exactly during TTA Phase 1 (balanced
accuracy `0.5924169784325324`, matching the record to 16 digits).

This benchmark is a **condition classifier**, and it is reported here as exactly that — a
reference for whether the trunk is intact, not as a vigilance result.

---

## 2. Branch A — Functional Prediction

**Question.** Can EEG provide reliable, objective functional-performance information for *unseen*
users?

**Current answer: no EEG → objective-functional-decline predictor has been demonstrated in this
project.** One sub-branch is a rigorous negative result; the other is still under clean-baseline
validation.

### 2.1 The ds004902 `M → PVT` branch — a NEGATIVE result, kept visible

The hypothesis: a short-duration tonic resting-EEG representation predicts deterioration in
objective psychomotor vigilance (PVT) performance for an unseen subject, under strict nested
leave-one-subject-out cross-validation against a **no-EEG baseline**, with permutation inference.

**Result.** The representation was *reproducibly measurable* — that part replicated, and it is a
genuine measurement property. It **did not demonstrate out-of-sample predictive skill** for the
PVT target.

| statistic | value |
|---|---|
| out-of-sample skill `Q²_skill(M1)` | **−0.0574** |
| permutation `p` (5,000 permutations, seed 20260916) | **0.7445** |
| subjects | **29** |
| cross-validation | outer LOSO(29) x inner LOSO(28); scaling and alpha selection strictly inside the outer training fold |

A negative `Q²` means the model did worse than the no-EEG baseline. The permutation null is
centred negative (mean `−0.0361`), so this is not a borderline call.

> **This is representation-, task- and dataset-specific.** It is **not** evidence that EEG cannot
> predict PVT in general, and it does not license that generalization. What it establishes is
> that *this* predefined tonic resting-EEG representation, on *these* 29 subjects, with *this*
frozen protocol, carries no demonstrated out-of-sample skill for *this* target.

Two things must travel together here, and neither alone is honest:

* it is a **valid negative**, not an invalidated one — the apparatus worked and the hypothesis was
  not supported;
* `M` survives only as a **measurement property** (repeatable, short-term stable, a tonic
  spectral proxy). It is **not** a validated vigilance biomarker and has no predictive validity.

**Hard rule, frozen:** no further feature, model or protocol search on those 29 subjects. Longer-duration
rescue, median-RT rescue, and feature-block rescue attempts are all closed. Reopening any of them
requires a new scientific branch, not debugging.

### 2.2 The BCIT objective-behaviour branch — endpoint validated, no modelling claim

This sub-branch moved to an **objective behavioural endpoint** measured from a driving task.

**What is established:**

* `mean |LN|` — mean absolute lateral lane deviation in **metres** — is the project's first
  **eligibility-passed objective target**, passing all six pre-registered eligibility checks
  (E1–E6).
* The `3200` marker was measured to be a **~40 s periodic grid** (median 38.5–40.2 s) delimiting
  **6 protocol blocks**, not an occasional event. Analysis windows are >= 300 s and are cut
  **only on `3200` onsets**, inside the valid (non-zero-padded) span.
* `LN = 0` **is** the lane centre, verified from the release's own `4220`/`4230` events with 100 %
  agreement in 5/5 recordings; the lane half-width measures **0.917 m** (spread 1.9 mm across
  three site classes).
* The 2x2 condition labels are **not** behaviourally recoverable — the perturbation-rate factor
  varies by only 1.08–1.18x across blocks. They are not invented anywhere in this project.

**What is NOT established:**

* That the BCIT endpoint supports any EEG modelling claim. It remains under clean-baseline
  validation, and **no BCIT objective-behaviour modelling result is claimed.**
* That any time-on-task effect exists: the naive `T_session` coefficient is
  **+0.088 ± 0.058 m/h** with a condition-aware F-test **p = 0.94**.

### 2.3 The Phase 4A / 4A2 history — a defect that was real but inert

This is the part most likely to be misread, so it is stated in full.

Phase 4A (historical baseline) and Phase 4A2 (adaptive SFFS) fitted within-person models on the
BCIT endpoint. Afterwards, a possible **apparatus defect** was identified: the smoothing helper
left every row outside the protocol-block intervals holding values no 90 s mean can produce — the
target reaching **11,909 m** against a 0.917 m lane half-width, predictors reaching ±79,769
log-units. A finding was raised claiming this **invalidated** Phase 4A and 4A2, because those
values were thought to sit inside every training mask.

**Phase 4A3 measured the impact claim and refuted it:**

* the defect is **real** — those values were manufactured by the smoothing helper, not measured;
* it is **inert** — **0 of 82,550** defective rows appear in any training or test mask of any of
  the 149 folds;
* the corrected pipeline reproduces Phase 4A to **~1e-14** (mean R `−0.04993651757569635` versus
  `−0.04993651757569237`) and the adaptive ΔR to full precision.

**Therefore the `INVALIDATED` status is WITHDRAWN.** Phase 4A and 4A2 stand as published:
standard-arm mean R **−0.0499**, adaptive-arm mean R **+0.0044**, ΔR **+0.0543** over 25
participants / 149 folds. The adaptive channel-selection branch nonetheless shows **0/25**
participants decidable against a calibrated null, with fold-to-fold selection stability Jaccard
**0.118** — so the adaptive branch is closed, and Phase 4B (cross-subject) is **not licensed**.

**How to read this section:** presenting Phase 4A/4A2 as a clean negative is false. Presenting
them as invalidated-by-contamination *without* citing Phase 4A3 is also false. The authoritative
reading is Phase 4A3.

### 2.4 What is deliberately not claimed

No cross-subject BCIT modelling, no personalisation, no deployment claim. Full specification and
status: [`functional_prediction/README.md`](functional_prediction/README.md).

---

## 3. Branch B — Test-Time Adaptation Stability

**Question.** Does online test-time adaptation — especially entropy minimisation — become
unstable or **collapse** on unseen-subject EEG streams, and what mechanism drives it?

**Status: Phase 1 is COMPLETE and at a hard stop.** Verdict
**`CASE 4 — BN/NORMALIZATION INSTABILITY`**, established by a real formal experiment (816/816
units executed on the owner-approved server), not by a taxonomy or a specification.

### 3.1 The setting

A **frozen** ds004902 EEGNet source trunk (204 LOSO checkpoints) is adapted **online** to each
unseen subject's stream, **episodically** — parameters, batch-norm state and optimiser state are
reset from that fold's checkpoint at episode start and discarded at the end. No adaptation
crosses a subject. Visit order follows the release's own `SessionOrder` field; batches never
cross a visit.

### 3.2 The four arms — and the distinction that matters

| arm | BN statistics | trainable | entropy step | Dropout in scored forward | canonical? |
|---|---|---|---|---|---|
| `SOURCE` | frozen source running stats | none | none | off | baseline |
| `BN_ONLY` | test-batch | none | none | off | gradient-free control |
| `TENT_LITERAL` | test-batch | BN affine γ/β (80 scalars) | 1/batch | **ON** | **yes — literal TENT** |
| `TENT_DET` | test-batch | BN affine γ/β (80 scalars) | 1/batch | OFF | no — diagnostic control |

`TENT_DET` is **never** called canonical TENT. Only `TENT_LITERAL` follows the official reference
semantics, and that reference is hash-pinned (`commit e9e926a6`).

### 3.3 Collapse taxonomy

`collapse` requires **two** things together: reliable performance degradation **and** reliable
prediction-diversity contraction. Either alone is not collapse.

* conditional entropy falling alone is *the objective working* — never evidence of collapse;
* accuracy dropping alone is *degradation*;
* diversity contracting without degradation is *concentration*.

The statistical unit is the **subject**, with a 10,000-resample paired bootstrap — never the
9,390 windows.

### 3.4 Result

| arm | balanced accuracy | Δ vs SOURCE (95% CI) | Δ dominant-class share | Δ marginal entropy |
|---|---:|---|---:|---:|
| `SOURCE` | 0.5924 | — | — | — |
| `BN_ONLY` | 0.5039 | −0.0886 [−0.1253, −0.0520] | −0.1689 | +0.1504 |
| `TENT_LITERAL` | 0.5043 | −0.0881 [−0.1248, −0.0510] | −0.1657 | +0.1504 |
| `TENT_DET` | 0.5035 | −0.0889 [−0.1258, −0.0522] | −0.1679 | +0.1501 |

Three facts carry the verdict:

1. **No harmful collapse in any arm.** The diversity change runs the *opposite* way to the
   collapse signature: dominant-class share falls 0.7104 → ~0.542 and marginal entropy *rises*
   0.5358 → ~0.686. The adapted model stopped making a confident near-constant prediction and
   drifted to chance.
2. **The entropy gradient is inert.** `TENT_LITERAL − BN_ONLY` = **+0.00048** balanced accuracy
   (t = +0.22), and `BN_ONLY` vs `TENT_DET` agree on **99.65 %** of windows.
3. **The normalisation switch is sufficient.** The gradient-free `BN_ONLY` control reproduces the
   entire ~8.9-point degradation.

The degradation is therefore attributable to the **test-batch normalisation switch**, not to
entropy minimisation. What this branch has **not** established is *why* that switch harms
performance — that is a separate question requiring a new PI decision.

### 3.5 Verification

| gate | result |
|---|---|
| independent verifier `90_verify_phase1.py` | **105/105** |
| negative controls `tests/test_p1_controls.py` | **75/75 bite** (NC1–NC27) |
| synthetic smoke test | PASS |
| remote SOURCE closure (RTX 4090) | max abs Δp 9.537e-07, **0 label flips** |
| executed units | **816/816** (68 subjects x 3 seeds x 4 arms) |

### 3.6 Parked — not started, no artefact exists

> SAR · DELTA · T-TIME · T3A · CoTTA · BFT · EATA · MEMO · diversity regularisation · confidence
> filtering · reset mechanisms · anti-collapse redesign · hyper-parameter sweeps · batch-size
> sweeps · continual TENT

Every one of these appears **only as prose in a park list**. None is implemented and none is
described as completed anywhere in this repository. The highest-information *candidate* next step
is a **statistics-geometry diagnostic** comparing source running statistics against the
test-batch statistics actually used — cheap, and requiring no adaptation. It is a proposal.

Full detail: [`tta_collapse/README.md`](tta_collapse/README.md).

---

## 4. How correctness is enforced

This project's central discipline is that **a check that cannot fail is not a check.**

* **Nested CV or nothing.** Scaling, feature selection and hyper-parameter choice happen strictly
  inside the outer training fold. Whole-data preprocessing is forbidden.
* **Freeze before fitting.** Target, protocol, feature set, CV scheme and inference are fixed in a
  written specification *before* the first fit. No researcher-degrees-of-freedom search: if a
  hypothesis returns null, that is the result.
* **Every phase ends with an independent verifier** whose exit code gates completion, and every
  new static check must be proved able to catch a deliberately injected violation. The negative
  controls are as much a deliverable as the verifier. Independent verification means a *separate*
  script re-derives the result, ideally from raw sources rather than the pipeline's own
  intermediate output.
* **Contradictions are reported, not smoothed.** Where an artifact disagrees with a report, the
  repository says so.
* **Executed state is never fabricated.** `PLANNED` / `IMPLEMENTED` / `EXECUTED` / `VERIFIED` are
  distinguished everywhere. "The code should work" is not evidence.

Reproduce the public parts — including the verifiers and controls you can run without any data —
following [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md). The fastest check is:

```bash
pip install -r requirements.txt
python docs/verify_public_numbers.py   # every number in these READMEs, vs its artifact
python docs/check_links.py             # every relative link resolves
cd functional_prediction && python tests/test_mechanism.py && python tests/test_phase2_ridge.py
cd ../tta_collapse && python tests/test_p1_synthetic_smoke.py
```

None of these needs a dataset, a GPU or a network connection.

---

## 5. Honest status summary

| item | status |
|---|---|
| ds004902 source trunk (EEGNet condition benchmark) | **EXECUTED / VERIFIED** — reference numbers reproduced |
| ds004902 `M → PVT` predictive branch | **NEGATIVE** — valid, published, closed |
| BCIT behavioural endpoint (`mean |LN|`) | **VALIDATED** (eligibility E1–E6) |
| BCIT objective-behaviour EEG modelling | **NOT CLAIMED** — no result established |
| Phase 4A / 4A2 historical baseline numbers | **STAND AS PUBLISHED** — invalidation withdrawn by Phase 4A3 |
| Phase 4A2 adaptive branch | **CLOSED** — 0/25 decidable against a calibrated null |
| Phase 4B cross-subject | **NOT LICENSED** |
| TTA Phase 1 collapse-existence experiment | **EXECUTED / VERIFIED** — `CASE 4` |
| TTA anti-collapse methods, sweeps, interventions | **PARKED — not started** |
| Any deployment, safety-layer or real-time claim | **NOT MADE** |

---

## 6. Data and artefacts

* **No raw EEG is redistributed.** The ds004902 and BCIT payloads stay at their sources; this
  repository ships the dataset identifiers, the preprocessing entry points, and the expected local
  layout.
* **No model checkpoints are committed** except the 1.2 MB legacy prototype checkpoint under
  `archive/legacy/`. The trunk's 204 EEGNet checkpoints (6.55 MB total) are represented by a
  **manifest with SHA-256 hashes**, naming convention and regeneration instructions — see
  [`shared/ds004902_source_trunk/checkpoints/README.md`](shared/ds004902_source_trunk/checkpoints/README.md).
* **Third-party code is referenced, not vendored.** Version and commit pins live in
  `shared/ds004902_source_trunk/third_party/sources.json`.
* Selected lightweight evidence (per-subject metrics, collapse summaries, the executed units) is
  published under each branch's `evidence/` directory so that reported numbers can be checked
  without re-running anything.

---

## 7. Environment

Core execution environment: **Python 3.11**, numpy 2.3.2, scipy 1.16.1, scikit-learn 1.7.2,
torch 2.10.0+cu126, braindecode 1.3.2.

> **The original environment is not fully reconstructible.** The formal ds004902 run was executed
> on a remote RTX 4090 under Python 3.11.16 / torch 2.10.0+cu126, while TTA Phase 1 executed under
> Python 3.12.3 / torch 2.8.0+cu128 because that is what the approved server provided. That
> difference was *checked, not assumed*: SOURCE reproduced the historical baseline exactly.
> Dependencies are listed with the versions actually present in the environment that produced the
> published numbers — see [`ENVIRONMENT_AUDIT.md`](ENVIRONMENT_AUDIT.md) for the evidence and the
> gaps.

---

## 8. License

**No license has been assigned to this repository yet.** It is public for review and
collaboration; absent a `LICENSE` file, default copyright applies and no reuse rights are
granted. A license will be added once the owner has chosen one deliberately. Third-party
dependencies keep their own licenses.

---

## 9. Citing

No citation is claimed while no license and no publication exist. If you are a collaborator or
reviewer and need a machine-readable reference, use the repository URL and the commit SHA.
