# EEG Vigilance Reliability

**Cross-subject EEG research on objective vigilance-related performance and test-time adaptation.**

> **Status:** Active research.
> This repository contains two scientifically independent branches that share a frozen EEG
> source-model trunk. Negative results, refuted invalidation suspicions, and current evidence
> limits are kept explicitly rather than hidden behind final model scores.

---

## Research Question

**How can we determine whether an EEG model is actually reliable for an unseen user?**

This project began as a normal-sleep vs. sleep-deprivation EEG classification task. That
formulation was useful as an engineering baseline, but it did not answer the question I ultimately
cared about: whether EEG can provide information about objective functional deterioration that is
useful for a new person, and whether adapting a model online makes that prediction more or less
reliable.

The project therefore evolved into two separate research branches:

1. **Functional Prediction** — whether short-duration EEG contains out-of-sample information about
   objective vigilance-related functional performance.
2. **Test-Time Adaptation Stability** — what happens when a source EEG model is adapted online to
   an unseen subject using unlabeled test data.

These branches share infrastructure, but they do not share scientific conclusions.

---

## Why It Matters

EEG markers can show population-level associations without necessarily providing useful predictions
for an unseen individual. Likewise, test-time adaptation can reduce distribution shift in principle
while also introducing new failure modes.

For practical biosignal systems, the relevant question is therefore not only whether a signal
exists, but whether it survives:

- subject-level holdout,
- realistic target definitions,
- strict out-of-sample evaluation,
- online adaptation,
- and implementation/protocol auditing.

This repository is organized around those failure points.

---

## Project Structure

### Shared Source Trunk

The two branches share a frozen ds004902 EEG source-model infrastructure:

- **68 valid subjects**
- **9,390 four-second EEG windows**
- **61 channels**
- **500 Hz sampling**
- subject-level leave-one-subject-out evaluation

A historical source-only EEGNet baseline achieved:

- Accuracy: **0.5963**
- Balanced Accuracy: **0.5924**
- F1: **0.5550**
- ROC-AUC: **0.6109**

These results establish a limited condition-related EEG signal. They do **not** establish functional
prediction.

### Branch A — Functional Prediction

This branch asks:

> Can EEG provide out-of-sample information about objective vigilance-related functional
> deterioration?

A predefined tonic resting-EEG representation was first evaluated for measurement reliability and
then tested against psychomotor-vigilance performance.

In a **29-participant strict nested leave-one-subject-out** experiment, the representation did not
outperform a no-EEG baseline:

- `Q² = −0.0574`
- nested permutation `p = 0.7445`

Longer EEG duration, an alternative PVT target, and a bounded dynamic-feature extension did not
recover predictive skill. This branch was therefore stopped rather than extended through additional
post-hoc feature or model search.

The result is deliberately interpreted narrowly:

> A reproducibly measurable EEG representation did not demonstrate out-of-sample utility for
> predicting PVT deterioration in this dataset and protocol.

It is **not** evidence that EEG can never predict PVT.

The functional branch later moved to objective driving behavior using BCIT data. Lane-control
semantics were audited before EEG modeling, including independent checks of lane-center
interpretation and lane geometry.

### Branch B — Test-Time Adaptation Stability

This branch asks:

> What happens when an EEG source model is adapted online to an unseen subject?

Under the frozen ds004902 EEGNet protocol, the completed SOURCE / BN-only / TENT comparison produced
a verified **normalization-instability** outcome: both BN-only adaptation and TENT degraded relative
to the frozen source model, so the observed failure cannot be attributed specifically to
entropy-gradient updates.

This narrows the current failure mechanism from "TENT itself is unstable" toward the behavior of
test-time normalization under the target stream.

The result is interpreted narrowly: it does not establish that BatchNorm is the causal mechanism,
nor that TENT universally collapses on EEG.

The branch implementation and verification suite completed all recorded checks (816/816 unit checks;
105/105 branch-verifier checks). These counts refer to implementation verification, not experimental
sample size — the experiment itself is **68 subjects × 3 seeds × 4 arms**.

Current work focuses on reproducing an external EEGNet + TTA reference pipeline and isolating which
normalization/stream properties produce the observed degradation before evaluating stabilization
methods.

---

## My Role

My work in this project has focused on:

- research-question formulation and reframing,
- experiment and control design,
- subject-level evaluation protocols,
- EEG modeling and baseline selection,
- behavioral-target and dataset auditing,
- reproducibility and provenance checks,
- failure diagnosis,
- and research-direction decisions.

A major goal has been to distinguish three cases that are often conflated:

1. a scientific hypothesis fails,
2. an implementation or experimental apparatus fails,
3. a model works under one evaluation setting but not for an unseen user.

---

## Current Evidence

### Established

- A reproducible cross-subject EEG source-model trunk has been built on 68 subjects.
- A tonic EEG representation can be measured reproducibly over short recordings.
- The tested representation did **not** provide out-of-sample PVT predictive skill under strict
  nested subject-level validation.
- The BCIT lane-control endpoint has been behaviorally and geometrically audited before EEG
  modeling.
- Under the frozen source model, **both** normalization-only adaptation and entropy-minimizing
  adaptation degraded to near chance, and the two are statistically indistinguishable from each
  other.

### Negative result

The ds004902 EEG-to-PVT branch is a genuine negative result under the tested representation and
protocol.

Rather than adding models indefinitely, the branch was stopped after bounded diagnostics failed to
support the original hypothesis.

### Corrective audit

A later forensic audit investigated a suspected inter-block gap-contamination issue in the BCIT
historical-baseline pipeline.

The audit found the suspected contamination to be **inert**:

- 0 of 82,550 evaluated rows entered any modeling mask;
- the numerical effect of the correction was approximately `1e-15`.

The earlier Phase 4A/4A2 results therefore remain valid scientific evidence rather than invalidated
runs.

The fixed historical baseline did not establish a reliable EEG-to-lane-performance signal. The
adaptive SFFS branch likewise did not establish a reliable positive effect, although its
population-level null analysis was not sufficiently large for a stronger formal claim.

---

## What Is Not Yet Demonstrated

This project does **not** currently establish that:

- EEG can predict PVT deterioration in a new user,
- EEG can predict driving-performance deterioration,
- a model generalizes across independent datasets,
- test-time adaptation reliably improves unseen-user EEG decoding,
- normalization statistics are the *causal* mechanism of the observed adaptation degradation,
- TENT necessarily produces prediction collapse on EEG,
- or the system is ready for safety-critical or real-world deployment.

---

## Current Scientific Gate

The active TTA branch asks which normalization/stream properties produce the observed degradation,
and first requires reproducing an external EEGNet + TTA reference pipeline in its original setting.
Once the reference implementation is reproduced, the controlled adaptation mechanism can be
transferred to the frozen ds004902 source model for further SOURCE / BN-only / TENT comparisons.

The functional-prediction branch remains separate and retains its own validation gates and evidence
history.

---

## Repository Structure

The public repository is organized around scientific responsibility rather than chronological code
accumulation:

```text
.
├── shared/                    # frozen source-model definitions and lightweight provenance
├── functional_prediction/    # objective functional-performance branch
├── tta_collapse/             # test-time adaptation stability branch
├── docs/                      # scientific history, protocols, and reproducibility notes
└── archive/                   # superseded early prototype, retained byte-for-byte
```

Detailed historical and forensic artifacts live under `docs/` so that the current scientific state
stays clear.

---

## Data and Reproducibility

Raw EEG data, large waveform caches, full checkpoint collections, and external runtime caches are
**not** distributed in this repository.

Public materials are limited to code, lightweight manifests, protocol definitions, result summaries,
and reproducibility metadata where appropriate.

Train/test separation is performed at the **subject level** for cross-subject claims.

Historical artifacts that were later superseded are retained only with their status clearly marked.

See [`docs/reproducibility.md`](docs/reproducibility.md),
[`docs/data-boundaries.md`](docs/data-boundaries.md) and the branch-specific READMEs for details.

---

## Running the Code

The two scientific branches have different dependencies and evaluation protocols.

Please use the branch-specific instructions rather than treating the repository as a single training
pipeline:

- [`functional_prediction/README.md`](functional_prediction/README.md)
- [`tta_collapse/README.md`](tta_collapse/README.md)

The repository does not require local copies of large datasets or checkpoints to inspect the
scientific protocols and result summaries. Several checks run from a clean clone with no data at
all — see [`docs/reproducibility.md`](docs/reproducibility.md) §2.

---

## Current Work

Current priorities are:

1. reproduce a public EEGNet + TTA reference pipeline in its original benchmark setting;
2. transfer the controlled adaptation mechanism to the frozen ds004902 source trunk;
3. determine whether the observed degradation is driven by normalization behaviour under the target
   stream or by a more specific adaptation failure;
4. only then evaluate established stabilization methods or new interventions.

New mechanisms are not introduced simply to rescue a failed baseline.

---

## Project History

This repository originally contained an NS-vs-SD classifier with LSTM, EEGNet, feature-engineering,
and MSCViT+TCN prototypes.

Those early implementations are preserved under `archive/legacy/legacy_ns_sd_prototype/`, byte-for-
byte as they were published, but they are no longer treated as the scientific definition of the
project.

See [`docs/project-history.md`](docs/project-history.md).

---

## Citation and License

This is an ongoing undergraduate research project. A formal project citation has not yet been
assigned.

**No repository-wide software license has been assigned yet.** The reason is not indecision: parts of
the retained archive derive from third-party implementations whose upstream licensing and
attribution are not fully established. See
[`docs/third-party-provenance.md`](docs/third-party-provenance.md). Until that audit is resolved, no
license is granted for any part of this repository.

Third-party dependencies (`braindecode`, `torch`, `mne`, …) keep their own licenses.
