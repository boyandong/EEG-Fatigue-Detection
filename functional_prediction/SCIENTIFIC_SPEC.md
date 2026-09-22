# SCIENTIFIC_SPEC.md — vigilance_generalization_v1

**Status: FROZEN for Phase 1.** Superseded in part by the Phase 1.75 amendments in §17 below
(measurement model of the dynamic observables, and the target psychometrics requirement).
If code and this document conflict, the code is wrong.

> **Phase 1.75 amendment notice.** Phase 1.5 showed that the quantity previously described as
> "temporal instability" is a *mixture* of slow drift, local fluctuation and measurement noise.
> §8.2, §9 and §17 are updated accordingly. The mathematical definitions of `S`, `M` and `J` are
> **unchanged**; what changes is what we are allowed to claim they mean, plus the addition of
> `V`, `D` and `J_res` as separately-audited observables.

Branch: `vigilance_generalization_v1` — an independent research branch.
All prior work (`NS/SD` classification, EEGNet / DeepConvNet / RBF-SVM, TENT/TTA, old Source
Only, old channel selection) is **legacy** and is not a constraint on anything defined here.

---

## 1. Research question

### 1.1 What this branch does NOT study

\[
EEG \rightarrow NS/SD
\]

NS and SD are **experimental conditions**, not something a real user needs a model to tell
them. Optimising accuracy on that label is out of scope.

### 1.2 What this branch studies

> **When a new user's objective alertness / response capability has declined relative to
> that user's own normal state, can that functional decline be detected from short-duration,
> low-dimensional, physiologically grounded EEG change — and ultimately generalize across
> subjects, tasks, and datasets?**

Current mathematical core:

\[
\Delta EEG \;\longrightarrow\; \Delta\text{Objective Functional Performance}
\]

### 1.3 Role of ds004902 in this branch

| element | role in this branch |
|---|---|
| NS (`ses-1`) | the participant's **personal alert baseline** |
| SD (`ses-2`) | the **experimental perturbation** that produces a state change |
| NS vs SD | **not** a prediction label; only the structure that creates a paired change |
| PVT | the source of the **objective functional target** |

Long-run hypothesis:

\[
\boxed{\text{baseline-relative EEG} \;\rightarrow\; \text{baseline-relative objective impairment}}
\]

and, over the life of the branch, whether this relation holds

1. for an unseen subject;
2. after a change of task;
3. after a change of dataset;
4. after reducing recording time and electrode count;
5. well enough to support future abstention / uncertainty decisions.

**Phase 1 (this round) implements none of 1–5.** It builds only the auditable scientific
foundation: provenance, targets, a frozen representation, and an implementation-validity
check against the source paper. **No model is trained.**

---

## 2. Mechanistic hypothesis graph (NOT a causal identification result)

\[
(H_{i,t},\; C_{i,t},\; V_i,\; E_{i,t})
\;\rightarrow\;
Z_{i,t}
\;\rightarrow\;
M_{i,t}
\;\rightarrow\;
Y_{i,t}
\]

| symbol | meaning |
|---|---|
| \(H_{i,t}\) | homeostatic sleep pressure |
| \(C_{i,t}\) | circadian drive |
| \(V_i\) | trait-like vulnerability |
| \(E_{i,t}\) | acute context / task / noise |
| \(Z_{i,t}\) | latent vigilance capability and stability |
| \(M_{i,t}\) | EEG observable mechanism proxies |
| \(Y_{i,t}\) | objective behavioural performance |

### 2.1 This is a hypothesis graph, not an identified causal model

We do **not** claim to identify any arrow above. In particular \(H\), \(C\), and \(V\) are
**not reliably measurable** in this dataset and are **not model inputs**.

They are written down for exactly two reasons:

1. to explain why \(SD \not\Rightarrow\) identical impairment — two participants can receive the
   same perturbation and land at different \(Z\) because \(H\), \(C\), \(V\) differ;
2. to explain why a **personal baseline** is meaningful — the quantity of interest is the
   change relative to that person, not an absolute level.

### 2.2 Hard implementation rule

> **Do not estimate \(H\) or \(C\) anywhere in code.**

No sleep-diary-derived homeostatic term, no clock-time-derived circadian term, no
vulnerability score. Clock times and `SessionOrder` are **recorded as metadata for later
confound audit only** and must never enter a predictor (see §12.4).

---

## 3. Personal baseline as a mathematical assumption

For one EEG observable \(m\):

\[
m_{i,t} = b_i + \lambda_i Z_{i,t} + \epsilon_{i,t}
\]

| symbol | meaning |
|---|---|
| \(b_i\) | stable personal EEG offset / fingerprint |
| \(\lambda_i\) | individual state sensitivity |
| \(Z_{i,t}\) | latent functional state |
| \(\epsilon_{i,t}\) | measurement noise |

Personal change:

\[
\Delta m_i = m_{i,\text{current}} - m_{i,\text{baseline}}
\]

so that

\[
b_i - b_i = 0 .
\]

Therefore, the operating assumption:

\[
\boxed{\text{individual offset is nuisance; individual response is signal}}
\]

### 3.1 Mandatory limitation (must be carried into every downstream claim)

If

\[
\operatorname{Var}(\epsilon_b) = \operatorname{Var}(\epsilon_c) = \sigma^2
\]

and the two noise terms are independent, then

\[
\operatorname{Var}(\epsilon_c - \epsilon_b) = 2\sigma^2 .
\]

> **Personal baseline reduces between-person bias but can increase measurement noise.**

Consequences to keep explicit:

* A baseline-relative representation is **not** strictly better than an absolute one. It trades
  a bias term for a variance term.
* `baseline duration` is a future **independent research variable**. A short baseline may not
  estimate \(b_i\) well; a long baseline costs user time, which is the entire product point.
* **Phase 1 uses the full available recording** for both NS and SD. No duration subsampling.

### 3.2 \(\lambda_i\) is not estimated in Phase 1

The model above lets \(\lambda_i\) differ per person. Phase 1 does **not** estimate
\(\lambda_i\): it computes \(\Delta m_i\) directly and stops. Any statement about individual
sensitivity is deferred.

---

## 4. Provenance requirement (gating)

Phase 1's first task is to re-establish the EEG data entry point from a **provable source**,
and to report for every recording: subject, session, acquisition order, eyes-open/eyes-closed
provenance, sampling rate, channel list, recording duration, preprocessing provenance,
bad-channel/interpolation provenance, reference, units, PVT availability.

### 4.1 Only eyes-open resting EEG is admissible

\[
\boxed{\text{eyes-open resting EEG only}}
\]

### 4.2 Gate outcome for ds004902 (executed, see `PHASE1_REPORT.md` §A)

* The BIDS tree `data/ds004902/metadata_behavior/` holds 218 `task-eyesopen` and 218
  `task-eyesclosed` recordings — **but every one of them is a broken git-annex symlink**
  (`WinError 1920`); `.git/annex/objects` is absent. **No BIDS EEG content is retrievable
  locally.**
* The only readable EEG is `data/ds004902/preprocessed/` — 142 EEGLAB `.set`/`.fdt` pairs
  (71 subjects × 2 sessions), produced by a **third party** in MATLAB/EEGLAB.
* Each of the 142 files preserves the **original raw filename** in its header. All 142 source
  names are eyes-open family names (`*_open*`, `*openeye*`, `*restopen*`, `rest_ns`, `rest_sd`,
  `_S`, `_D`). **Zero** contain any eyes-closed token. The upstream raw tree, by contrast,
  stored separate `NS/` and `SD/` folders.

**Verdict: eyes-open provenance is established at the level of the source filename family,
with the residual uncertainty recorded in §4.3.** The gate therefore **passes**, and the
limitations below are binding on all downstream interpretation.

### 4.3 Residual provenance uncertainty (binding limitations)

1. **No independent eyes-open verification is possible locally.** The claim rests on filename
   families, not on a task/event marker. Segment-level eye state is **not** recoverable.
2. **Preprocessing is not reproducible from this workspace.** EEGLAB history records
   `D:\data_for_capstone_project\Resting-State-EEG-Dataset-for-SD\03_ica`, external to the repo.
3. **The preprocessing was run on dataset version v1.0.5**, while the local BIDS tree declares
   v1.0.8 (`原始数据集.txt`). Not re-run.
4. **Anti-alias settings for the 5 resampled recordings are not recorded** upstream.
5. **Units** are uV by EEGLAB convention corroborated by BIDS `channels.tsv`; there is no
   independent calibration record in the preprocessed files.
6. **Real segment-level artefact rejection is third-party and unspecified.** We inherit it; we
   do not re-run ICA or add new artefact heuristics (see §6).

---

## 5. Representation: two pipelines, kept strictly separate

### 5.1 `paper_reference` — implementation validity only

**Not our contribution.** Its only purpose is to check that the data entry point and the
spectral extractor are basically correct, by attempting a reproduction of the source paper's
reported statistic.

Per epoch \(e\), channel \(c\):

\[
q_{\theta,e,c}=\frac{P_{\theta,e,c}}{P_{4\text{–}30,e,c}},\qquad
q_{\alpha,e,c}=\frac{P_{\alpha,e,c}}{P_{4\text{–}30,e,c}},\qquad
q_{\beta,e,c}=\frac{P_{\beta,e,c}}{P_{4\text{–}30,e,c}}
\]

with

\[
P_{4\text{–}30} = P_\theta + P_\alpha + P_\beta
\]

which holds **exactly** (not merely within integration error) because of the band definition
fixed in `config/dataset_ds004902.yaml` (`total_band_definition: theta + alpha + beta`).

Per channel, across epochs:

\[
\mu_{\theta,c} = \operatorname{mean}_e\!\big(q_{\theta,e,c}\big),\qquad
\sigma_{\theta,c} = \operatorname{SD}_e\!\big(q_{\theta,e,c}\big)
\]

and likewise for alpha and beta. ROI aggregation for `paper_reference` is the **channel
arithmetic mean**, for compatibility.

### 5.2 `mechanism_v1` — the frozen primary representation

Theta relative power, alpha relative power and beta relative power are **never** treated as
three independent mechanism variables, because

\[
q_\theta + q_\alpha + q_\beta = 1 .
\]

They are **compositional data**. Instead, at the **epoch × channel** level we compute the
isometric log-ratio coordinate

\[
\boxed{
S_{e,c}
=
\sqrt{\tfrac{2}{3}}
\left[
\ln\!\big(P_{\theta,e,c}+\epsilon_P\big)
-
\tfrac12
\Big(
\ln\!\big(P_{\alpha,e,c}+\epsilon_P\big)
+
\ln\!\big(P_{\beta,e,c}+\epsilon_P\big)
\Big)
\right]
}
\]

equivalently

\[
S \;\propto\; \ln \frac{P_\theta}{\sqrt{P_\alpha P_\beta}} .
\]

Semantics: **theta dominance relative to the faster oscillatory background** — not simply
"theta power".

#### \(\epsilon_P\) policy

\(\epsilon_P\) is **only** a `log(0)` guard, with an explicitly tiny value
(`numerical_epsilon_uv2: 1.0e-12`). The number of band powers that actually hit the floor is
recorded per session in `outputs/qc/feature_qc.csv`.

> If a **non-trivial fraction** of values hit \(\epsilon_P\), the PSD pipeline is treated as
> broken and **must not be silently continued**. Threshold and the recorded count are reported
> in `PHASE1_REPORT.md`.

---

## 6. EEG processing rules

Protocol target:

| element | value |
|---|---|
| eye state | eyes-open |
| sampling rate | 500 Hz |
| analysis band | 1–30 Hz |
| reference | average |
| epoch | 4 s, non-overlapping |
| theta | 4–8 Hz |
| alpha | 8–13 Hz |
| beta | 13–30 Hz |

### 6.1 No recording-wise z-score — hard rule

\[
x'=\frac{x-\mu_{\text{same recording}}}{\sigma_{\text{same recording}}}
\]

**is forbidden** as EEG input preprocessing.

Rationale, in order of importance:

1. Our primary representation is already a **spectral log-ratio**, so it is largely invariant
   to a pure multiplicative gain. A recording-wise z-score adds nothing it does not already
   have, while destroying information it does not need to destroy.
2. We do **not** rely on absolute broadband amplitude as a primary signal — that is not this
   branch's research question.
3. Whether absolute amplitude carried condition information in the legacy NS/SD task is
   **explicitly not a research question here**. We do not chase it, we do not build
   experiments around the legacy z-score, and we do not use absolute amplitude for feature
   selection.

### 6.2 Do not invent preprocessing

* Do not tune preprocessing parameters in order to reproduce a literature number.
* If only raw EEG existed without a defined artefact strategy, the correct action would be to
  report the situation rather than to invent heuristic artefact rules. Here the artefact
  handling is inherited from the third party; we add **no** new artefact heuristics.
* Everything we *do* control (filtering, PSD, band edges) is config-driven and lands in
  provenance.

### 6.3 Epoched source is respected

The source `.set` files are **already** 4 s epochs (2000 samples @ 500 Hz). We do not
re-window, concatenate, or flatten them. Each source epoch **is** one analysis epoch.

---

## 7. Channel aggregation order (frozen)

For `mechanism_v1`, the order is:

> **log / log-ratio first → channel aggregation second → time aggregation third.**

\[
S_{e,c}
\;\xrightarrow{\;\text{median over } c\in R_r\;}\;
S_{e,r}
\;\xrightarrow{\;\text{mean / SD over } e\;}\;
M_r,\; J_r
\]

with \(r \in \{F, CT, PO\}\) and

\[
\boxed{ S_{e,r} = \operatorname{median}_{c \in R_r} S_{e,c} }
\]

Explicitly forbidden (and enforced by tests):

* \(\log(\operatorname{mean}(P))\)
* \(\log \dfrac{\operatorname{mean}(P_\theta)}{\operatorname{mean}(P_\alpha)}\)
* session-averaging raw power before forming the ratio

### 7.1 ROI definition

`paper_reference` ROI = channel arithmetic mean. `mechanism_v1` ROI = channel median.
Both use the same three channel sets, which form an **exact partition** of the 61-channel
montage (F=16, CT=28, PO=17; no duplicates, no unmapped channel — verified in
`scripts/04_verify_phase1.py`).

---

## 8. The six coordinates

Per session and ROI:

### 8.1 Mean slowing / theta dominance

\[
\boxed{ M_r = \frac1N \sum_{e=1}^{N} S_{e,r} }
\]

### 8.2 Temporal dispersion — CORRECTED INTERPRETATION (Phase 1.75)

\[
\boxed{ J_r = \text{total within-recording temporal dispersion} }
\]

`J_r` is the sample SD of the epoch series `S_{e,r}`. It is **not** "vigilance instability" and
must never be described as such. Under the measurement model of §17.1,

\[
J_r^2 = \operatorname{Var}\big[g_r(t) + u_{e,r} + \eta_{e,r}\big]
\]

i.e. `J` mixes **slow within-recording drift**, **local fluctuation**, and **measurement noise**.
Phase 1.5 demonstrated this empirically: `J` increases systematically from early to late in the
recording (9 of 24 early→late comparisons significant, all of them `J`, none of them `M`), while
`M` shows no position effect.

* \(M_r\): average spectral slowing / theta dominance over the recording.
* \(J_r\): within-recording temporal dispersion of that EEG state (sample SD, ddof = 1).
* \(J_r\) requires \(N \ge 2\); sessions with \(N < 2\) produce no \(J\) and are excluded from
  the dispersion coordinates with an explicit reason.

> These are **not** to be described as two fully independent physiological mechanisms.
> The correct description is
> \(\boxed{2 \text{ feature families} \times 3 \text{ spatial regions}}\),
> i.e. six coordinates — **not** "six independent mechanisms". And the second family must be
> named by what it computes (dispersion), not by what we hope it reflects.

---

## 9. Personal-relative representation

In ds004902, NS is the personal baseline and SD is the current perturbed state. NS/SD are used
**only to form the paired change**; they are never the final classification target.

Mean coordinate:

\[
\boxed{ \Delta M_{i,r} = M^{SD}_{i,r} - M^{NS}_{i,r} }
\]

Instability coordinate:

\[
\boxed{
\Delta J_{i,r}
=
\ln \frac{J^{SD}_{i,r}+\epsilon_J}{J^{NS}_{i,r}+\epsilon_J}
}
\]

\(\epsilon_J\) is a numerical-safety constant only. If every valid NS recording has
\(J>0\), we report that the floor was **never needed** and compute the ratio without it.

Final representation:

\[
\boxed{
\Delta\mathbf m_i =
\big[\,
\Delta M_F,\;
\Delta M_{CT},\;
\Delta M_{PO},\;
\Delta J_F,\;
\Delta J_{CT},\;
\Delta J_{PO}
\,\big]
}
\]

### 9.1 Frozen feature set — nothing else may be added this round

Additions explicitly forbidden in Phase 1: delta, gamma, entropy, MSE, connectivity,
coherence, PLV, graph metrics, microstates, criticality, channel-wise feature selection,
questionnaires, demographics, legacy network embeddings.

---

## 10. PVT target (re-frozen)

No legacy target file is trusted as ground truth. `src/pvt_targets.py` re-reads the **raw PVT
trial files**.

Rules:

* raw files are **never rewritten**;
* header typos are tolerated, but the **actually parsed column names are recorded**;
* every exclusion carries an explicit reason.

### 10.1 Paper-compatible median RT

Retain \(100 \le RT \le 2000\) ms. Per subject/session:

\[
RT^{\text{med}}_{i,s} = \operatorname{median}\big(RT^{\text{valid}}_{i,s}\big)
\]

\[
\boxed{ \Delta RT_i = RT^{\text{med}}_{i,SD} - RT^{\text{med}}_{i,NS} }
\]

Used **only** for paper-reference reproduction.

### 10.2 Primary candidate target: dimensionless personal-relative impairment

\[
\boxed{
Y^{RT}_i
=
\ln
\frac{RT^{\text{med}}_{i,SD}}{RT^{\text{med}}_{i,NS}}
}
\]

\(Y=0\): no change. \(Y>0\): slower. \(e^{Y}-1\): approximate proportional deterioration.

### 10.3 Secondary candidate: response speed

Over the same filtered trials:

\[
V_{i,s} = \operatorname{mean}_j\!\left(\frac{1}{RT_{i,s,j}}\right),
\qquad
\boxed{
Y^{\text{speed}}_i = \ln \frac{V_{i,NS}}{V_{i,SD}}
}
\]

with \(Y^{\text{speed}}>0\) meaning functional decline.

> Phase 1 **computes and stores** both candidates. It does **not** select between them, and it
> does not rank them by how well they correlate with features.

### 10.4 Reconciliation with the official summary

The official `participants.tsv` targets are saved **alongside** the recomputed ones, never
silently dropped. The reconciliation table records, per subject:
`official_median_rt_ns/sd`, `raw_filtered_median_rt_ns/sd`, `official_delta`, `raw_delta`,
`difference_ns`, `difference_sd`, `raw_trials_ns/sd`, `valid_trials_ns/sd`,
`exclusion_reason`.

> **The choice of target must never be driven by final correlation or model performance.**

If the published summary and the released trial files disagree, both are reported as facts.
If the paper's subject count (≈28) cannot be reproduced, we report
**"cannot reproduce their N-subject selection"** and give the exact set differences rather than
deleting anyone to match.

---

## 11. Paper-reference correctness test

Using the **paper-compatible** features (epoch-wise theta *relative power* across-epoch SD, not
our log-ratio \(J\)):

\[
\Delta\text{theta variability} = J^{\text{paper}}_{SD} - J^{\text{paper}}_{NS}
\]

then

\[
\rho\big(\Delta\text{thetaVar}_{F}, \Delta RT\big),\quad
\rho\big(\Delta\text{thetaVar}_{CT}, \Delta RT\big),\quad
\rho\big(\Delta\text{thetaVar}_{PO}, \Delta RT\big)
\]

Published reference values: \(\rho_F \approx 0.54\), \(\rho_{CT} \approx 0.56\).

> **These are sanity references, not optimisation targets.**

Forbidden: changing preprocessing until \(\rho\) matches; selecting participants to raise
\(\rho\); tuning band boundaries; tuning ROIs; deleting outliers; sweeping PSD parameters and
keeping the best. If the reproduction disagrees, **analyse and report the reason only**.

Also reported: group-level SD−NS ROI differences for theta relative power mean and
theta variability.

---

## 12. Statistical discipline

### 12.1 Effect sizes and unit of analysis

* Unit of analysis: **subject** (one paired observation per subject).
* Report effect sizes with confidence intervals, not just p-values.
* With \(N \approx 28\text{–}40\), researcher degrees of freedom are the dominant risk.

### 12.2 No feature selection

Regardless of results, Phase 1 forbids: picking the highest-correlating ROI; picking best
channels; keeping only significant features; moving bands by p-value; moving ROIs by PVT
result. **All three ROIs and all six coordinates are retained, always.**

### 12.3 QC is independent of the behavioural target

Feature-side QC only: NaN/inf, zero power, epsilon activation, retained-epoch count, session
duration, ROI channel counts, missing channels, feature distributions, extreme values, NS/SD
pair completeness, and deterministic-rerun hash equality.

> It is forbidden to delete features, delete subjects, or change parameters at this stage on
> the basis of \(\operatorname{corr}(\text{feature}, Y)\).

### 12.4 Timing metadata is stored, never used

`SessionOrder`, EEG sampling clock times, and PVT sampling clock times are written into
`paired_features.csv` for a **later confound audit**, and must not enter any predictor.

---

## 13. Phase 2 interface (reserved, NOT built now)

### 13.1 Aperiodic control analysis

Reserved interface hook only (`src/mechanism_features.py::reserved_aperiodic_hook`). The purpose
is a later **mechanism-control** analysis: split each PSD into aperiodic (1/f) and periodic
components and test whether the theta-dominance signal is merely a **broadband spectral-shape
shift** rather than a theta-specific change. Planned coordinates
\(\Delta\chi_F,\Delta\chi_{CT},\Delta\chi_{PO}\) where \(\chi\) = aperiodic exponent.

**Phase 1 does not install, import, or execute FOOOF/specparam.**

### 13.2 Cross-dataset portability

The mechanism extractor must be dataset-agnostic. Forbidden pattern:

```python
if dataset == "ds004902":
    ...
```

Required interface shape:

```python
extract_mechanism_features(epochs, channel_names, sfreq, roi_mapping, spectral_config)
```

Future second dataset = adapter only:

```text
dataset-specific loader  ->  common EEG representation  ->  same mechanism extractor
```

Future cross-dataset target, unified in spirit:

\[
\boxed{ Y = \ln \frac{\text{current functional latency}}{\text{personal alert latency}} }
\]

> PVT RT and driving RT are **not the same task**. A future cross-dataset claim may assume they
> share a *latent vigilance component*; it may **not** assume \(PVT \equiv \text{driving}\).
> Phase 1 does not download or train on a second dataset.

### 13.3 Phase 2 model protocol (frozen later, not now)

Nested-LOSO over \(M_0, M_1, M_2, M_3\) is **not** defined here and must not be started until
Phase 1 is reviewed.

---

## 14. Unit tests (mathematical contract)

| test | property |
|---|---|
| **A** multiplicative gain invariance | \(x' = kx\), \(k \in \{0.1, 10, 100\}\) \(\Rightarrow\) \(S, M, J\) unchanged within tolerance. Proves the representation does not depend on session-wide amplifier gain. |
| **B** theta-specific increase | theta power up, alpha/beta unchanged \(\Rightarrow\) \(S \uparrow\). |
| **C** global broadband scale | theta, alpha, beta all scaled by the same factor \(\Rightarrow\) \(S \approx\) unchanged. |
| **D** instability | two synthetic sessions with equal mean \(S\) but larger epoch-to-epoch fluctuation in the second \(\Rightarrow\) \(M_1 \approx M_2\) and \(J_2 > J_1\). |
| **E** personal offset cancellation | adding the same additive log-ratio offset to both baseline and current leaves \(\Delta M\) unchanged. |
| **F** determinism | same input and config rerun \(\Rightarrow\) identical feature table (or identical within a declared floating tolerance). |

---

## 15. Reporting standard

Phase 1 may claim only: data entry point established; targets rebuilt; whether the reference
feature broadly reproduces; whether the mechanism representation is correctly generated; and
whether the data is of sufficient quality to support a formal prediction experiment.

Phase 1 **must not** claim: a new fatigue biomarker; accident-risk prediction; real-time
fatigue detection; that theta instability causes performance decline; superiority over SOTA; or
deployment readiness.

### 15.1 Feature selection criterion for this branch

\[
\text{ScientificValidity} \times \text{CrossDatasetPortability} \times \text{FewChannelCompatibility} \times \text{ShortTimeReliability}
\]

**not** \(p\)-value, and **not** single-dataset accuracy.

The guiding question is never *"what feature works best on this dataset?"* but
*"what feature has a clear physiological reading, is mathematically self-consistent, is
insensitive to hardware gain, works with few electrodes and short recordings, and can be
computed by the same definition in another dataset?"*

---

## 16. Hard stop

Phase 1 ends after: source provenance audit; eyes-open manifest; PVT reconciliation;
paper-compatible targets; paper-reference features; reproduction sanity check; six-dimensional
`mechanism_v1` extraction; mechanism unit tests; QC; `PHASE1_REPORT.md`.

**Then it stops and reports. No model is trained.**

---

# 17. Phase 1.75 amendments — measurement model and target psychometrics

Added after Phase 1.5 acceptance. These amendments have the same authority as the rest of this
document and **supersede** any earlier wording that conflicts with them.

## 17.1 Measurement model for the dynamic observables

The earlier informal reading `J ≈ state instability` is **withdrawn**. The defensible model is:

\[
\boxed{\;S_{e,r} = \mu_r + g_r(t_e) + u_{e,r} + \eta_{e,r}\;}
\]

| term | meaning |
|---|---|
| \(\mu_r\) | tonic spectral level of that recording |
| \(g_r(t)\) | slow within-recording drift, recording adaptation, slow state change |
| \(u_{e,r}\) | local epoch-to-epoch fluctuation |
| \(\eta_{e,r}\) | measurement noise (PSD estimation, residual artefact) |

Consequences:

\[
M_r \approx \mu_r + \overline{g_r(t)},
\qquad
\boxed{J_r^2 = \operatorname{Var}\big[g_r + u_{e,r} + \eta_{e,r}\big]}
\]

**We do not know, and Phase 1.75 cannot determine, whether the observed early→late change is
genuine vigilance settling, cognitive adaptation to resting, post-eye-opening habituation, the
recording-onset protocol, residual preprocessing, electrode/contact settling, or a mixture.**
Reporting language is therefore restricted to **"recording-position effect"** or
**"slow within-recording drift"**. The phrase **"genuine vigilance drift" is forbidden** unless
future data can exclude those alternatives, which the current data cannot.

## 17.2 Additional observables (mechanism_v1_1_dynamic_audit)

`mechanism_v1` is **not modified**. A parallel representation is added:

\[
\boxed{
V_r = \sqrt{\frac{\sum_{e=1}^{N-1}\big(S_{e+1,r}-S_{e,r}\big)^2}{2\,(N-1)}}
}
\]

* computed on **adjacent 4 s epochs**, in recording order, **never shuffled**;
* the \(1/2\) makes \(V\) an unbiased estimate of \(\operatorname{SD}(S)\) under i.i.d. sampling
  (\(E[(S_{e+1}-S_e)^2] = 2\sigma^2\)), so \(V\) and \(J\) share a scale and are directly
  comparable, while \(V\) responds to adjacent differences rather than total dispersion;
* permitted description: **"local epoch-to-epoch spectral volatility proxy"**. It is **not** a
  validated vigilance biomarker.

Slow-drift diagnostic, with \(\tau_e = \big(e-(N+1)/2\big)/N\) so that the slope is the **total**
change across the window:

\[
S_{e,r} = a_r + d_r \tau_e + \epsilon_{e,r},
\qquad
\boxed{D_r = d_r},
\qquad
\boxed{J^{res}_r = \operatorname{SD}\big(S_{e,r} - \hat a_r - \hat d_r \tau_e\big)}
\]

`D` and `J_res` are **diagnostics**, not primary mechanism features. The primary comparison is
`J` vs `V`. `J_res` must **not** be adopted merely because it is the most stable observable.

### 17.2.1 Differencing amplifies measurement noise — binding caveat

\[
\Delta S_e = (x_{e+1}-x_e) + (\eta_{e+1}-\eta_e),
\qquad
\operatorname{Var}(\eta_{e+1}-\eta_e) = 2\sigma_\eta^2
\]

A conceptually appealing volatility measure can therefore be **worse in practice**. `V` is
admissible only if it passes the same target-blind stability audit as `J`.

### 17.2.2 `V`'s sampling-interval sensitivity — CORRECTED (Phase 2 amendment)

An earlier version of this document claimed that `V` "falls as 1/N" and is therefore
"intrinsically less portable across datasets with different recording lengths". **That
inference was wrong and is withdrawn.** The arithmetic behind it was right; the conclusion
drawn from it was not.

For a **fixed per-step slope**, let \(S_e = a + be\). Then \(S_{e+1}-S_e = b\) for every \(e\),
so

\[
V=\sqrt{\frac{(N-1)b^2}{2(N-1)}}=\frac{|b|}{\sqrt2},
\]

**independent of \(N\).** Likewise for a continuous process \(S(t)=a+qt\) sampled with a fixed
epoch stride \(\Delta t\),

\[
\boxed{\;V=\frac{|q|\,\Delta t}{\sqrt2}\;}
\]

again independent of the total recording length. The apparent \(1/N\) behaviour appears only
when the **total span is held fixed** while \(N\) is increased, which forces the per-step slope
to shrink as \(b=\Delta/(N-1)\). That is a property of the rescaling, not of the estimator.

> **Correct statement.** \(V\) is sensitive to the **temporal sampling interval / epoch stride**
> \(\Delta t\), not to the recording length. Cross-dataset comparability of `V` therefore
> requires the epoch length and stride to be held fixed, not the number of epochs.

**Binding requirement for every future dataset in this branch:**
\(\boxed{\text{epoch} = 4\ \text{s},\ \text{stride} = 4\ \text{s}}\).

`V` still does not enter the Phase 2 predictor (§18.2) — but for the correct reason
(**measured reliability is worse**, §18.1), not for the withdrawn scaling argument.

## 17.3 Latent structure

\[
\boxed{Z(t) = \big[Z^{level}(t),\; Z^{stability}(t)\big]}
\]

with \(Z^{level} \to M\) and \(Z^{stability} \to \{J, V\}\), where \(J\) is a **total temporal
dispersion proxy** and \(V\) is a **local fluctuation proxy**. They are **not** the same thing
and must not be reported as if they were.

**Phase 2 weighting (frozen).** The two families do **not** enter Phase 2 as equal partners:

\[
\boxed{X_M = [\Delta M_F,\Delta M_{CT},\Delta M_{PO}]}\ \text{confirmatory},
\qquad
\boxed{X_J = [\Delta\log J_F,\Delta\log J_{CT},\Delta\log J_{PO}]}\ \text{exploratory incremental}
\]

`V` and `J_res` are audit variables only and are **not** predictors.

## 17.4 Target psychometrics is now mandatory before any prediction

The behavioural target is itself a difference of two noisy measurements:

\[
\ln RT^{obs}_s = \ln RT^{true}_s + \epsilon_s
\;\Longrightarrow\;
Y^{obs} = Y^{true} + \epsilon_{SD} - \epsilon_{NS},
\qquad
\operatorname{Var}(\epsilon_Y) = \operatorname{Var}(\epsilon_{SD}) + \operatorname{Var}(\epsilon_{NS})
\]

Therefore no EEG→behaviour model may be fitted until the target's own finite-trial uncertainty
has been quantified. The reliability coefficient reported from a trial bootstrap is an
**approximate finite-trial reliability proxy** and must **never** be called test–retest
reliability: the bootstrap cannot see day-to-day, circadian, or true within-person state
variability.

**Target selection rule:** primary vs secondary target may be decided only on **measurement
stability** and **pre-existing literature grounds** — never on which target correlates better
with an EEG feature.

## 17.5 Protocol(B, T)

Recording onset has a systematic effect on the dynamic observables. The deployment protocol is
therefore parameterised as

\[
\text{Protocol}(B, T):\quad \text{burn-in } B \text{ for settling},\quad \text{measurement } T
\]

with \(B \in \{0, 32, 60\}\) s and \(T \in \{32, 60, 120\}\) s, **declared a priori**. \(B\) and
\(T\) are chosen on stability, position-bias reduction, paired-change stability and usable
subject count — **never** on PVT. If 32 s of burn-in already removes most of the systematic
effect, we do **not** then search 40/48/56 s for an optimum: that would be protocol overfitting.

**A prefix window `[0, T]` is not an acceptable permanent definition of a `J`/`V` measurement**,
because it would encode the recording-onset response into the feature, and recording onset is
not a comparable physiological event across datasets or devices.

## 17.6 Feature-selection criterion (unchanged, restated)

\[
\text{ScientificValidity} \times \text{CrossDatasetPortability} \times \text{FewChannelCompatibility} \times \text{ShortTimeReliability}
\]

**not** \(p\)-value, and **not** single-dataset accuracy.

## 17.7 Paper PVT label mismatch — resolved, not unexplained

Earlier drafts recorded a discrepancy: the dataset paper reports \(t(29)=0.04\) under the
**median RT** label while our raw-trial reconstruction shows a clearly positive median-RT
change. **This is no longer recorded as an unexplained discrepancy.**

The project's own PVT audit (`pvt_audit_v1/`) recomputed the paired \(t\) statistics from
`participants.tsv` and found \(t \approx 0.042\) (item 1), \(-7.308\) (item 2), \(-4.715\)
(item 3), while the paper's text prints median RT → 0.04, RT SD → −7.31, lapses → −4.72 — the
values match numerically but are assigned **cyclically** to different metric labels.

> **Binding statement.** The dataset paper's textual median-RT statistic is **not** used to
> validate the direction or magnitude of our reconstructed raw median-RT target.

This applies to reporting language only. It changes no target definition and is not a blocker.

---

# 18. Phase 2 — frozen predictive specification

**Phase 2 is the first phase permitted to fit an EEG→behaviour model.** Its single core question:

\[
\boxed{\text{Can personal-baseline-relative EEG predict objective vigilance decline in an unseen subject?}}
\]

Not NS/SD classification, not in-sample correlation, not feature-significance hunting.

## 18.1 Mechanism-v2 (frozen)

Primary confirmatory family:

\[
\boxed{X_M = [\Delta M_F,\ \Delta M_{CT},\ \Delta M_{PO}]},
\qquad
M_r=\operatorname{mean}_e S_{e,r},
\qquad
S_{e,r}=\operatorname{median}_{c\in ROI_r}\!\Big[\sqrt{\tfrac23}\big(\ln P_\theta-\tfrac12(\ln P_\alpha+\ln P_\beta)\big)\Big]
\]

Permitted description: **personal-relative tonic spectral-state change proxy**. Forbidden:
"direct sleep-pressure measurement".

Secondary exploratory dynamic family:

\[
\boxed{X_J = [\Delta\log J_F,\ \Delta\log J_{CT},\ \Delta\log J_{PO}]},
\qquad J_r=\operatorname{SD}_e(S_{e,r})
\]

Permitted description: **total within-recording temporal dispersion**. Forbidden:
"vigilance instability biomarker".

`V` and `J_res` are **audit variables only**. They do not enter any predictor.

## 18.2 Protocol (two, frozen)

\[
\boxed{P_M = (B=0,\ T=60\,\text{s})}\ \text{primary},\qquad
\boxed{P_J = (B=60\,\text{s},\ T=60\,\text{s})}\ \text{dynamic secondary}
\]

NS and SD always use the **same recording position and duration**. `X_M^{full}` is declared in
advance as a long-duration sensitivity analysis. **It is forbidden to change duration or
burn-in after seeing results.**

## 18.3 Targets (frozen)

Primary:

\[
\boxed{Y^{\text{primary}}_i = Y^{\text{speed}}_i = \ln\frac{Q_{i,NS}}{Q_{i,SD}}},\qquad
Q_{i,s}=\operatorname{mean}_j(1/RT_{i,s,j}),\qquad 100\le RT\le 2000\ \text{ms}
\]

\(Y>0\) means response speed fell, i.e. objective deterioration.

Justification permitted: (1) lower finite-trial uncertainty in the target-only psychometric
audit; (2) higher split-half stability; (3) existing PVT literature on response-speed
sensitivity to sleep loss. **Forbidden:** "because it predicts better from EEG" — no EEG–PVT
association was consulted for target selection.

Secondary: \(Y^{RT}_i=\ln(\text{median}RT_{i,SD}/\text{median}RT_{i,NS})\). The
`participants.tsv` official values are **sensitivity only**.

## 18.4 Models (ladder frozen before fitting)

| model | predictors | protocol | role |
|---|---|---|---|
| `M0` | none (outer-train mean) | — | no-EEG baseline |
| `M1` | `X_M` | `P_M` B0/T60 | **primary confirmatory hypothesis** |
| `M1-full` | `X_M` | full session | duration sensitivity |
| `M2` | `X_M` | `P_J` B60/T60 | dynamic-protocol M-only reference |
| `M3` | `X_M + X_J` | `P_J` B60/T60 | dynamic incremental (exploratory) |

`M2` and `M3` must share the **same** B60/T60 window, so that the `M3 − M2` contrast isolates
the incremental value of `J` and not a change of measurement position. `M3` performance must
never be used to override the `M1` primary result.

## 18.5 Nested cross-validation (frozen)

Outer: LOSO over \(n=29\). Every outer fold trains on 28 and predicts the held-out subject.
Inner: LOSO **within** those 28, selecting

\[
\boxed{\lambda\in\{0.01,0.1,1,10,100\}}
\]

by minimum inner MSE. The grid is fixed and must not be extended or re-tuned on results.

**All** centering, scaling and \(\lambda\) selection happen strictly inside the outer training
fold. Whole-data mean/std is forbidden. Feature selection is forbidden: all three ROIs are
retained a priori, always.

## 18.6 Endpoints (frozen)

Primary:

\[
\boxed{Q^2_{\text{skill}} = 1 - \frac{\sum_i (Y_i-\hat Y_i)^2}{\sum_i (Y_i-\hat Y_i^{M0})^2}}
\]

\(Q^2_{\text{skill}}>0\) means the EEG model beats predicting the training-set mean impairment
for an unseen user. Also reported: `MAE`, `Skill_MAE = 1 - MAE_model/MAE_M0`, and
\(\operatorname{Spearman}(\hat Y, Y)\). The confirmatory test concerns \(Q^2_{\text{skill}}\)
only. No "success threshold" such as \(\rho>0.3\) is defined a priori.

## 18.7 Inference (frozen)

**Permutation**, primary hypothesis only (`M1 → Y_speed`): subject-level permutation of \(Y\),
\(B\ge 5000\), each replicate **fully re-running** outer LOSO, inner LOSO, scaling and
\(\lambda\) selection. Fixed seed; the complete null distribution is saved.

\[
p_{\text{perm}}=\frac{1+\#\{b: Q^2_{\text{perm},b}\ge Q^2_{\text{obs}}\}}{B+1}
\]

**Bootstrap CI**: subject-level resampling of the \((Y_i,\hat Y_i,\hat Y_i^{M0})\) tuple,
\(B=10000\), for `Q²`, `Skill_MAE` and Spearman. Bootstrap must not re-select features.

## 18.8 Reliability context — no disattenuation

\(R^{\text{approx}}_{Y_{\text{speed}}}\approx 0.813\) is reported as **interpretation context
only**, explicitly labelled an approximate finite-trial reliability proxy and **not**
test–retest reliability. Disattenuated corrections of the form
\(r/\sqrt{R_xR_y}\) are **forbidden**; the only permitted use is the statement that
behavioural measurement uncertainty attenuates observable predictive performance.

## 18.9 Confound sensitivity (secondary)

The primary model contains no confounds, because no deployed product could use them. A separate
secondary analysis compares

\[
C_0: Y\sim \text{SessionOrder}+\Delta\text{Clock},
\qquad
C_1: Y\sim \text{SessionOrder}+\Delta\text{Clock}+\Delta M
\]

under the **same** outer-LOSO discipline, with all scaling and fitting inside the training fold.
If missing timing reduces \(n\), the actual \(n\) is reported. \(C_1\) is not a deployment model;
the analysis asks only whether EEG adds information beyond known protocol variables.

## 18.10 Pre-registered interpretation matrix (may not be rewritten afterwards)

| case | condition | permitted claim |
|---|---|---|
| **A** | \(M1 > M0\) and \(M1_{60s}\approx M1_{full}\) | short baseline-relative tonic EEG contains predictive information about objective vigilance decline |
| **B** | \(M1_{60s}\not> M0\) but \(M1_{full}> M0\) | the mechanism may carry information, but 60 s measurement is insufficient |
| **C** | both \(\le M0\) | the current Mechanism-v2 tonic representation does not demonstrate out-of-sample predictive value in this dataset |

Dynamic secondary: \(M3>M2\) ⇒ temporal dispersion may add incremental information;
\(M3\le M2\) ⇒ `J` does not justify the extra 60 s acquisition burden under this protocol.
Under case C it is **forbidden** to keep trying features until something becomes significant.

## 18.11 Hard stop

Phase 2 ends after `M0`, `M1` (60 s), `M1-full`, `M2`, `M3`, the `Y_RT` secondary repetition,
the permutation test, the bootstrap CIs, and the confound sensitivity. **No** second algorithm,
**no** extra features, **no** protocol re-tuning, **no** SADT download, **no** cross-dataset
work, **no** TTA. Null results are reported as they are.
