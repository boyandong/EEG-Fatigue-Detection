# PHASE3_DATASET_AUDIT.md

**Phase:** Phase 3 — Dataset / Endpoint Feasibility Audit (metadata round 1)
**Branch:** `project/vigilance_generalization_v1/`
**Conducted:** 2026-09-17 (local, UTC+08:00)
**Nature of this round:** metadata feasibility only. **No EEG payload was downloaded. No model was
fitted. No feature was extracted. No channel was selected.** Every claim below carries an evidence
level: `VERIFIED` / `INFERRED` / `UNKNOWN`.

Machine-readable companions (all in `audit/phase3/outputs/`):

| artifact | contents |
|---|---|
| `bcit_identity_audit.json` | Gate 1 — participant identity and overlap |
| `bcit_cohort_structure.json` | independent N, multiplicity, sampling strata, release completeness |
| `bcit_recording_index.csv` | one row per released recording (375 rows) |
| `bcit_index_followup.json` | sampling-rate strata vs site; visit structure |
| `bcit_time_gap.json` | calibration → baseline elapsed time per pair |
| `bcit_endpoint_audit.json` | behavioural endpoint statistics and variance decomposition |
| `bcit_censoring.json` | uncorrected-trial (censoring) audit |
| `bcit_trajectory_structure.json` | recording adequacy, condition markers, ordered-bin count |
| `bcit_montage_harmonisation.json` | 64-channel ↔ 256-channel electrode mapping distances |
| `bcit_metadata_ledger.json` | SHA-256 + byte count for all 1 784 fetched sidecars (10.29 MB) |
| `sadt_audit.json` | SADT audit |
| `../docs/phase3_metadata_survey_2026.md` | commissioned wider-landscape survey (leads, §O) |

Reproduce with `10_`, `11b_`, `12_`–`19_*.py` in `audit/phase3/`. All are idempotent.
`11_fetch_bcit_metadata.py` is the superseded serial variant (kept for the audit trail only).

**Independent verifier:** `audit/phase3/20_verify_phase3.py` → **34/34 checks passed, exit 0**
(`outputs/phase3_verification.json`). It re-derives the headline numbers from the raw fetched
sidecars rather than trusting the audit's own JSON, and it includes negative controls (D1 destroys
the identity key and requires Gate 1 to fail; J3 requires the report not to claim an EEG download).
**The verifier found two bugs — both in itself, not in the pipeline** (a first-session pairing rule
that produced 104 instead of 102 same-day pairs, and an invented expected latency). Both are
retained in the code as comments, because "the check was wrong and the pipeline was right" is
itself the evidence that the check was independent.

---

## A. Search scope

Searched, read, or fetched in this round:

* **BCIT family (NEMAR / OpenNeuro).** `ds004118` / `on004118` (Calibration Driving),
  `ds004120` / `on004120` (Baseline Driving). Read: `README.md`, `dataset_description.json`,
  `participants.tsv`, `participants.json`, per-subject `*_sessions.tsv`, per-recording
  `*_scans.tsv`, `*_eeg.json`, `*_channels.tsv`, `*_events.tsv`, `code/task-*_events.json`,
  `code/samplingRates.tsv`. Sibling BCIT datasets referenced but **not** audited:
  `ds004106` (Advanced Guard Duty), `ds004119` (Basic Guard Duty), `ds004121` (Mind Wandering),
  `ds004122` (Speed Control), `ds004123` (Traffic Complexity).
* **SADT.** NEMAR `nm000275` (BIDS repack of Cao et al. 2019). Read the full released sidecar set
  for all 62 sessions plus the mirror's own copy of the source paper full text
  (`sourcedata/meta/pmc_PMC6472414_fulltext.xml`) and the paper's supplementary Event-Related
  Potentials tables.
* **ds004902** — not re-audited; frozen Phase 2 state used as the reference design only.
* **Landscape survey (commissioned, returned mid-audit).** A separate metadata sweep covered
  SEED-VIG, DROZY, the BCIT sibling datasets, an OpenNeuro title sweep (1 889 datasets), PhysioNet
  `drivedb`, `ds007509`, MPD-DF and DD-Database. Its full text is
  `docs/phase3_metadata_survey_2026.md`; its conclusions are folded in at §O **with their evidence
  level attached**, because a commissioned summary is not primary evidence.

**Scope statement.** This audit is **complete for BCIT and SADT**, where every claim rests on
released metadata that was downloaded, hashed (`bcit_metadata_ledger.json`, 1 784 files,
10.29 MB) and re-parsed by the scripts in this directory. It is **incomplete for the wider
landscape**: the survey in §O is a lead-generation pass whose negative claims have not all been
independently re-verified.

---

## B. BCIT participant identity mapping (Gate 1) — **PASS**

### B.1 The naive join is wrong, and we can measure by how much

`sub-NN` in `ds004118` and `sub-NN` in `ds004120` are **independent, per-dataset sequential
relabellings**. They are not the same person. `VERIFIED` by computing both joins:

| join key | pairs found |
|---|---|
| `sub-NN` (naive) | 109 candidate pairs, of which **95 are provably the wrong person** |
| `legacy_labID` (correct) | **107 pairs** |

For the 107 true pairs, the two datasets assign the **same** `sub-NN` label in only **14** cases;
in **93** cases the label differs (e.g. one person is `sub-09` in Calibration and `sub-10` in
Baseline). A naive `sub-NN` join would therefore be **89 % wrong** and would silently mis-pair
almost every subject. This is exactly the failure mode the audit was designed to catch.

### B.2 The correct key, and why it is the correct key

`participants.tsv` in both datasets contains an explicit **`legacy_labID`** column, documented in
`participants.json` as *"labID used to reference the subject in ESS"*, and both READMEs state:
*"Legacy subject IDs are unique across the entire BCIT program."* Site ranges are documented and
observed: `1xxx` = T1 ARL Aberdeen, `2xxx` = T2 Teledyne Durham, `3xxx` = T3 SAIC Louisville.

Three independent checks confirm the key denotes a person:

1. `legacy_labID` is unique within each dataset (156/156 and 109/109). `VERIFIED`.
2. **Year of birth agrees for 90 of 90 pairs** where both datasets record it (19 pairs have
   `n/a`). Zero conflicts. `VERIFIED`.
3. `ESS_subjectLabID` in `*_sessions.tsv` **equals** `legacy_labID` for every recording.
   `VERIFIED`.

### B.3 The answer

| quantity | value |
|---|---|
| Calibration Driving nominal N | **156** |
| Baseline Driving nominal N | **109** |
| **N_paired = \|I_C ∩ I_D\|** | **107** |
| Calibration-only | 49 |
| Baseline-only | 2 |
| Paired, both recordings usable and same-day | **102** |
| Paired same-day, 256-ch T3 layout | 54 |
| Paired same-day, 64-ch layout (T1 + T2) | 48 |
| Paired by site (any date) | T1 21, T2 27, T3 59 |

The 2 "baseline-only" subjects are the artefact of the numbering shift: legacy `1009` and `1010`
appear as Calibration `sub-09`/`sub-10` only if present — the precise sets are in
`bcit_identity_audit.json` (`calibration_only_ids_sorted`, `baseline_only_ids_sorted`).

> **Gate 1 verdict: PASS.** Identity is established by an explicit, documented, cross-corroborated
> key, not by label coincidence. `N_paired = 107`, of which **102** are within-visit pairs.

---

## C. BCIT calibration semantics (Gate 2) — **PASS**

### C.1 What the calibration recording actually is

`VERIFIED` from `ds004118/README.md`, quoted directly:

> *"Calibration data sets were designed to be the first component of every recording session within
> the BCIT program"* … *"When analyzed with other same-subject data, involving much longer tasks,
> the calibration data sets can be used as the basis for non-fatigue state performance."*

and from `ds004120/README.md`:

> *"in contrast with the (non-fatigued) Calibration driving session for the subject"* …
> *"Subjects always began recording sessions by performing a Calibration Driving task, which was a
> 15-minute drive where the subject controlled only the steering"* … *"The Calibration Driving run
> was always conducted first."*

So calibration is **not** a resting recording, not an electrode calibration, not an unrelated
visit. It is a **15-minute driving task performed in the non-fatigued state, immediately before the
long task, by the same person.** That is the intended baseline semantics of the application
hypothesis, stated by the data producers themselves.

### C.2 The within-visit structure is confirmed by metadata, not just by prose

`VERIFIED` from `audit/phase3/outputs/bcit_time_gap.json`, computed over all 107 pairs:

| check | result |
|---|---|
| same acquisition **date** | **102 / 107** |
| calibration is in-session recording **#1** | **107 / 107** |
| baseline is in-session recording **#2** | 0 / 107 (see below) |
| median calibration → baseline gap | **0 days** |

The five exceptions are all T3 SAIC and are **not** within-visit pairs:

| legacy ID | calibration date | baseline date | gap |
|---|---|---|---|
| `3115` | 2017-08-04 | 2016-01-02 | **−580 d** |
| `3120` | 2017-08-04 | 2017-10-03 | +60 d |
| `3204` | 2015-07-05 | 2015-03-05 | **−122 d** |
| `3208` | 2017-09-02 | 2016-09-01 | **−366 d** |
| `3210` | 2017-07-04 | 2016-11-01 | **−245 d** |

Three of these have the baseline recorded **before** the calibration, which contradicts the stated
protocol order. For these 5 subjects the calibration→baseline pair is **not** a clean
within-visit non-fatigued→fatigued contrast, and they must be excluded from any paired estimate
that relies on that semantics.

**Recommended paired analysis set: the 102 same-day pairs.** T1: 21, T2: 27, T3: 54.
(This is a scientific-set definition, not an implementation detail — see §N, item 2.)

### C.3 A correction to a documented claim

`ds004120/README.md` states *"Some of the subjects in this dataset performed either the BCIT Basic
Guard Duty Task (ds004118) or the BCIT Advanced Guard Duty Task (ds004106) counterbalanced during
the same session."* **The parenthesised `ds004118` is a documentation error**: `ds004118` is
Calibration Driving, and Basic Guard Duty is `ds004119`. `VERIFIED` by cross-checking
`dataset_description.json` (`Name: BCIT Calibration Driving`) against the README's own reference
list. Reported here because it is precisely the kind of identifier slip that produces wrong joins.

> **Gate 2 verdict: PASS.** The calibration recording is a documented, producer-asserted
> non-fatigued baseline of the same task in the same person, ordered first in its visit in
> 107/107 cases and same-day in 102/107. The `ΔX = X_current − X_baseline` construction is
> scientifically licensed for the 102 same-day pairs.

---

## D. BCIT objective behavioural endpoints

### D.1 The decisive discovery: continuous vehicle signals are released, co-registered with EEG

My first read of the release concluded that the 100 Hz vehicle log named in the README
(*"continuous performance based on vehicle log (steering wheel angle, lane position, heading
error, etc.)"*) was **absent**, because the file tree contains only discrete `*_events.tsv`.

**That was wrong, and the correction matters.** `*_channels.tsv` declares 74 channels per
recording, of which 64 are EEG and **10 are not**:

| channel | type | units | description (verbatim) |
|---|---|---|---|
| `LHEOG`, `RHEOG`, `UVEOG`, `LVEOG` | EOG | uV | left/right horizontal, upper/lower vertical |
| `LMAST`, `RMAST` | MISC | uV | left / right mastoid |
| **`LN`** | OTHER | n/a | **"Lane deviation from center line in meters."** |
| **`ANG`** | OTHER | n/a | **"Steering wheel deviation angle in degrees."** |
| **`SP`** | OTHER | n/a | **"Vehicle speed in mph."** |
| **`SD`** | OTHER | n/a | "Vehicle speed deviation." |

`VERIFIED`: this exact 4-channel vehicle set appears in **all 375 recordings** across both
datasets (100 %). `LN` has physical units (metres) and is stored **inside the same data matrix as
the EEG**, at the declared sampling frequency. Continuous lane deviation — the quantity Touryan et
al. 2014 used as the driving performance criterion — is therefore **available and sample-locked**.

### D.2 Per-perturbation response latency

`VERIFIED` from `code/task-Drive_events.json` + `code/task-DriveWithSpeedChange_events.json`:
perturbation onset (`1111` left / `1121` right), correction onset (`4311`), correction offset
(`4312`), lane-position events (`4210` in lane, `4220` right of lane, `4230` left of lane), plus
tile/condition markers (`3200`) and trial markers (`3111`/`3112`).

Every event row is `onset, duration, sample, value`, and `sample` is at the recording sampling
frequency — an **explicit sample index on the EEG clock.** `VERIFIED`.

Measured over the full release (`bcit_endpoint_audit.json`):

| endpoint | ds004118 Calibration | ds004120 Baseline |
|---|---|---|
| recordings with events | 247 | 128 |
| total events | 97 971 | 162 851 |
| perturbation onsets | 17 171 | 30 392 |
| **paired response-latency observations** | **17 061** | **30 086** |
| subjects with ≥ 1 observation | 155 | 109 |
| latency mean / median | 1.515 s / 1.441 s | 1.637 s / 1.504 s |
| latency p05 / p95 | 1.020 / 2.055 s | 0.997 / 2.750 s |
| between-subject SD of per-subject median | **0.562 s** | 0.582 s |
| per-subject median range | 1.183 – 4.604 s | 1.210 – 4.060 s |

The between-subject spread is not driven by one outlier: the distribution of per-subject medians
has an across-subject median of **1.456 s** while individual subjects sit anywhere from ≈ 1.2 s to
≈ 4.6 s. (`sub-01`, used as the verifier's worked example, has a median of 4.247 s over 56 paired
perturbations — a slow responder, not an error.)

### D.3 Three candidate operationalisations, and which one the source paper endorses

The dataset README says only *"reaction times to perturbations"* and never defines it. Rather than
choose silently, all three were computed:

| definition | n (ds004118) | mean | ICC (single measure) | within-subject var |
|---|---|---|---|---|
| `4311 − perturbation_onset` (**response initiation**) | 17 061 | 1.515 s | **0.531** | 0.174 |
| `4312 − perturbation_onset` (correction complete) | 16 230 | 4.666 s | 0.199 | 3.092 |
| `4312 − 4311` (steering duration) | 16 230 | 3.180 s | 0.199 | 2.591 |

`VERIFIED` from the primary source: the accompanying publication (Touryan, Apker, Lance, Kerick,
Ries & McDowell 2014, *Front. Neurosci.* 8:155, listed in both `dataset_description.json`
files as `HowToAcknowledge`) uses **continuous lane deviation**, reporting *"the average
correlation coefficient between the actual and estimated lane deviation was 0.37 ± 0.22"*.
The `4311`-based endpoint is a defensible analogue but is **not** the endpoint that publication
used.

**Recommendation (for PI decision, not adopted here):** `4311 − perturbation_onset` is the best
per-trial latency because its ICC is 2.7× the alternatives' — it is the only one of the three that
is predominantly a *trait-like* per-subject measure rather than a mixture of trait and
task-coupling noise. `LN`-based continuous metrics (SDLP, RMS lane deviation, time-in-lane) are the
endpoint family with published precedent for this task.

### D.4 Measurement-quality audit: censoring is negligible and flat

A perturbation that is never corrected would be silently dropped by the obvious estimator,
biasing the endpoint toward better performers. Quantified rather than assumed
(`bcit_censoring.json`, 10 s window):

| quantity | ds004118 | ds004120 |
|---|---|---|
| perturbations | 17 171 | 30 392 |
| never corrected within 10 s | 109 (**0.63 %**) | 306 (**1.01 %**) |
| per-recording censoring rate, median / p95 / max | 0.000 / 0.031 / 0.119 | 0.004 / 0.041 / 0.117 |
| recordings with **zero** censoring | 161 / 247 | 42 / 128 |
| censoring drift, last quarter − first quarter | median 0.0 (54/246 rising) | median 0.0 (42/128 rising) |
| trials with > 1 correction in window | 51 (0.30 %) | 98 (0.32 %) |

`VERIFIED`. Censoring is ~1 % and does **not** grow over the session, so it neither drives a
spurious decline signal nor requires an elaborate survival model. Assigning censored trials the
window value is an adequate sensitivity check. Note also that `4311` (correction onset) commonly
occurs while the car is already outside the lane — `4311` and `4220`/`4230` are **not** redundant
events (lane exceedances are ~5–10× more frequent than censored trials).

### D.5 Endpoint dynamic range — the quantity that decides feasibility

`VERIFIED`: per-trial latency **does** vary substantially within persons
(p05 = 1.0 s, p95 = 2.06 s in calibration; p95 = 2.75 s in baseline) and **between** persons
(per-subject median range 1.18 → 4.60 s, between-subject SD 0.56 s).

Variance decomposition of the best endpoint (`4311`-based), one-way random effects, per dataset:

| component | ds004118 | ds004120 |
|---|---|---|
| between-subject SD | 0.444 s | 0.548 s |
| within-subject SD | 0.417 s | 0.567 s |
| ICC(single trial) | 0.531 | 0.483 |
| observations | 17 061 | 30 086 |

With ~70 (calibration) or ~270 (baseline) trials per person, the per-subject **mean** latency has
standard error `SD_within/√n` ≈ **0.050 s** and **0.035 s** respectively — i.e. the per-subject
endpoint is estimated **far** more precisely than ds004902's `Y_speed`, whose approximate
finite-trial reliability was only `R ≈ 0.81`. This is the single most important structural
improvement over the Phase 2 dataset.

### D.6 Condition structure — a confound that must be handled, not ignored

Both datasets declare a 2 × 2 design in `code/task-*_events.json`
(`3200 = "All at high-perturbation rate with low visual complexity"`, HED
`(Condition-Variable/High-perturbation-rate, Condition-Variable/Low-visual-complexity)`).
`VERIFIED`: the `3200` marker occurs **inside** recordings, median **23×** per calibration
recording and **86×** per baseline recording.

Consequently a naive "performance declines over time" analysis is **confounded with
task-difficulty changes** and must either be stratified by condition or restricted to
condition-stable stretches. `UNKNOWN`: whether `3200` marks a genuine difficulty change each time
or is a repeated state log — this cannot be settled from metadata and requires reading `LN`/`SP`.

---

## E. EEG ↔ performance synchrony (Gate 3) — **PASS**

Answering the audit's five-way question explicitly:

| question | answer | evidence |
|---|---|---|
| Synchronous? | **Yes** | `LN`/`ANG`/`SP`/`SD` are channels in the same matrix as the EEG |
| Same trial? | **Yes** | every perturbation onset carries a `sample` index on the EEG clock; a matching `4311` gives a per-trial latency |
| Same short window? | **Yes** | `LN` is continuous at the recording rate, so any window ≥ 4 s is available |
| Same session, offset? | Not the operative case | behaviour is not a separate session |
| Different experiment? | **No** | — |

Formally, both of the structures the Phase 3 brief asked for are available:

```
(X_{i,t}, Y_{i,t})   trial-level   : EEG window ending at perturbation onset  ↔  latency to 4311
(X_{i,t}, Y_{i,t})   window-level  : EEG window  ↔  LN-derived metric over the same window
B_i                  within-visit  : the 15-min calibration recording of the same person
```

`Δt_XY = 0` at the sample level for the paired event stream. `VERIFIED`.

**Three caveats, all binding:**

1. **Three successive corrections were needed in this audit** — first the belief that the
   continuous vehicle channels were unreleased, then the `acq_time` encoding (twice), and finally
   the claim that all sites share a 64-channel montage. Every one was caught by recomputation
   rather than by review, but they are a standing reminder that *"the metadata says so"* is not
   evidence until it has been parsed and checked. Recorded here because the report's credibility
   rests on the corrections being visible, not on the final text looking clean.
2. **Within-visit offset in minutes is `UNKNOWN`.** `acq_time` carries date resolution only
   (`hhmmss = 000000` for every recording). The README's *"always conducted first"* plus
   `recording #1 in 107/107` establishes **order**; the elapsed minutes between calibration end
   and baseline start are not in the metadata.
3. **The T3 coordinates are template CTF positions with `EEGCoordinateUnits: n/a`.** Cross-frame
   comparability is *assumed*, and the montage-subsetting result in §F.3 inherits that assumption
   until it is checked against real signal topography.

> **Gate 3 verdict: PASS**, and materially better than the brief's minimum bar: this is
> trial-locked and window-locked synchrony at the sample level, not session-aggregate.

---

## F. Candidate dataset scorecard — BCIT

No numeric scores, no tiers, no "best dataset". Facts only.

### F.1 Calibration Driving (ds004118 / on004118)

| dimension | evidence |
|---|---|
| **Independent N** | `VERIFIED` 156 subjects, 247 recordings (122 with 1, 14 with 2, 10 with 3, 7 with 6–7 recording sessions). 155 subjects yield ≥ 1 usable latency. Not trials-as-subjects. |
| **Personal baseline** | `VERIFIED` each recording **is** the non-fatigued baseline (15 min, steering only, speed simulator-controlled, always first in its visit). 102 of 107 paired subjects also have a same-day Baseline Driving recording. |
| **Objective endpoint** | `VERIFIED` per-perturbation latency (17 061 obs, 155 subjects); continuous `LN` lane deviation in metres; incident-like events `4210`/`4220`/`4230` (9 058 in-lane, 3 208 right, 6 040 left). `KSS`/`VAS-F`/`TIFS` exist but are **questionnaire-only and available on request** — correctly de-prioritised. |
| **Temporal resolution** | `VERIFIED` per-trial events with sample indices, plus continuous vehicle channels. Delta-able at any window ≥ one epoch. |
| **Longitudinal structure** | `VERIFIED` 15.4 min median span; **4** populated 5-minute bins per recording; 122 subjects have only one session so between-visit structure is thin. Within-*visit* trajectory exists but is only ~15 min long. |
| **Behavioural dynamic range** | `VERIFIED` p05 1.02 s → p95 2.06 s per trial; between-subject SD of per-subject median 0.562 s; ICC 0.531. |
| **EEG quality** | `VERIFIED` **three distinct layouts, fixed per site and identical across subjects at that site**: T1 = 64 EEG @ **2048 Hz**, T2 = 64 EEG @ **1024 Hz**, T3 = **256 EEG @ 1024 Hz**; each with 4 EOG + 2 mastoid + 4 vehicle channels. Reference `CMS`; 60 Hz powerline; `SoftwareFilters: n/a`. Zero within-dataset mixed-rate subjects, zero mixed-montage subjects, and **zero paired subjects whose two recordings differ in channel count**. |
| **Cross-dataset compatibility** | `VERIFIED` 4 s / 4 s grid at 500 Hz is available from both 2048 and 1024 Hz. T1/T2 use 10-20 names; **T3 uses raw BioSemi grid labels `A1…H32`**, but `*_electrodes.tsv` ships coordinates for both, and the 64-channel targets map **uniquely** onto the 256-channel grid (§F.4). 60 Hz powerline → the 1–30 Hz band is clean. |
| **Accessibility** | `VERIFIED` NEMAR `on004118` v1.0.0, derived from OpenNeuro `ds004118` v1.0.1; **licence CC0**; public, no request form, no authentication. Metadata is 10.3 MB total. |
| **Likely scientific role** | Baseline/reference state for a within-visit contrast; short-task stress test. **Not** a stand-alone discovery set for decline. |

### F.2 Baseline Driving (ds004120 / on004120)

| dimension | evidence |
|---|---|
| **Independent N** | `VERIFIED` 109 subjects, 128 recordings (91 with 1, 17 with 2, 1 with 3). 107 paired with Calibration. |
| **Personal baseline** | `VERIFIED` the paired 15-min Calibration recording, same visit, calibration first. |
| **Objective endpoint** | `VERIFIED` same event vocabulary + same 4 vehicle channels. 30 086 latency obs; 13 631 in-lane, 5 187 right, 8 560 left. 5 undocumented `4411`/`4421` events (2 subjects) and 5xxx codes (3 subjects) — 39 events total, rare but real. |
| **Temporal resolution** | `VERIFIED` per-trial + continuous. |
| **Longitudinal structure** | `VERIFIED` **68.6 min** median span, **14** populated 5-min bins per recording, up to 332 perturbations per person. This is the phase's structurally most important number: ~14 ordered within-person measurements instead of ds004902's 2. |
| **Behavioural dynamic range** | `VERIFIED` p05 0.997 s → p95 2.750 s; between-subject SD of per-subject median 0.582 s; ICC 0.483. 5 recordings are < 50 % of nominal duration (i.e. < 30 min). |
| **EEG quality** | `VERIFIED` as Calibration. T1 = 64 ch @ 2048 Hz (22 recordings), T2 = 64 ch @ 1024 Hz, T3 = 256 ch @ 1024 Hz. |
| **Cross-dataset compatibility** | `VERIFIED` as Calibration; T2 has the 2×2 visual-complexity × perturbation-rate manipulation, so site and design are partially confounded. |
| **Accessibility** | `VERIFIED` NEMAR `on004120` v1.0.0 ← OpenNeuro `ds004120` v1.0.0; **CC0**; public. |
| **Likely scientific role** | **Primary discovery set** for within-person objective-decline structure; evaluation set for unseen-subject prediction. |

### F.3 Montage harmonisation — the majority group is not 10-20, and it is fixable

**(Added as a correction.** An earlier draft of this audit described the core EEG set as
"64 + 4 EOG + 2 M + 4 veh" for all recordings. That is false for T3, which is **59 of the 107
paired subjects**.)

`VERIFIED` from `bcit_recording_index.csv`:

| site | EEG channels | sampling | recordings (ds004118 / ds004120) | paired subjects |
|---|---|---|---|---|
| T1 ARL Aberdeen | 64, 10-20 names | 2048 Hz | 21 / 22 | 21 |
| T2 Teledyne Durham | 64, 10-20 names | 1024 Hz | 98 / 28 | 27 |
| **T3 SAIC Louisville** | **256, grid labels `A1…H32`** | 1024 Hz | **128 / 78** | **59** |

The dense T3 grid is **not** anatomically named. That would normally kill ROI mapping for the
majority of the sample — but the release ships coordinates, and they resolve it:

* `*_electrodes.tsv` carries `name, x, y, z` for all 256 grid positions and all 64 named
  positions. `VERIFIED`.
* The frame is **left-positive with +x anterior**, established from the data (not assumed):
  `Fpz.x = 1.000 > Oz.x = −1.000`, and midline channels (`Fpz`, `Cz`, `Oz`) have `y ≈ 0`.
  `coordsystem.json` declares `EEGCoordinateSystem: CTF`, `EEGCoordinateUnits: n/a`.
* Nearest-neighbour matching of the 64 named targets onto the 256-point grid
  (`19_montage_harmonisation.py`, `bcit_montage_harmonisation.json`):

| statistic | value |
|---|---|
| median match distance | **0.0742** normalised head units |
| p95 / max | 0.1146 / **0.1252** |
| targets within 0.10 | 54 / 64 |
| targets within 0.15 | **64 / 64** |
| unique matches (no two targets claiming one dense electrode) | **64 / 64**, 0 collisions |

* Layouts are **fixed per site**: the T3 grid is bit-identical across two different T3 subjects
  (`sub-98`, `sub-99`), and the 64-channel layout is identical between T1 (`sub-01`) and T2
  (`sub-22`). `VERIFIED` — so this is a *site* montage, not a per-subject cap placement.
* 10 of 266 (resp. 74) electrode rows have missing coordinates — exactly the 4 EOG + 2 mastoid +
  4 vehicle channels. No EEG electrode is missing coordinates. `VERIFIED`.

**Consequence:** a single shared ROI definition (e.g. the SPEC §7 F/CT/PO partition) can be applied
to all three layouts by selecting, in each, the electrodes nearest the ROI's defining positions —
which preserves all 107 paired subjects instead of cutting the sample to 48. This is the difference
between an `n ≈ 48` and an `n ≈ 107` phase, so it is a first-order feasibility result, not a detail.

**Caveat that remains binding:** both coordinate sets are *template/CTF* positions, not measured
digitised positions, and `EEGCoordinateUnits: n/a` means the two frames are assumed comparable
rather than proven comparable. The observed distances (~0.07–0.13 head units, i.e. of the order of
one inter-electrode spacing on a 64-channel cap) are consistent with a genuine common montage, but
the alignment should be validated against the `Cz`/`Fpz`/`Oz` landmarks and, ultimately, against
real signal topography on Tier-1 data before any cross-site model is fitted.

### F.4 Effective independent N and exclusion structure

| quantity | value | level |
|---|---|---|
| Calibration subjects | 156 | VERIFIED |
| Baseline subjects | 109 | VERIFIED |
| Paired subjects (any date) | 107 | VERIFIED |
| **Paired same-day (recommended analysis set)** | **102** | VERIFIED |
| Paired same-day with Calibration at 1024 Hz | 81 (T2 27 + T3 54) | VERIFIED |
| Paired same-day at 2048 Hz (T1) | 21 | VERIFIED |
| Calibration-only subjects | 49 | VERIFIED |
| Baseline-only subjects | 2 | VERIFIED |
| Same-day pairs with a "short" baseline (< 30 min) | to be recomputed on the 102 subset | derived in `bcit_trajectory_structure.json` |

**Do not report 156 + 109 = 265.** The independent-sample count for a paired design is **107**
(any-date) or **102** (same-day). Sessions and trials are not subjects: 375 recordings and
47 147 latency observations resolve to 102–107 independent people.

---

## G. Candidate mathematical endpoints (definitions only — no modelling)

Direction convention, as required: **`D > 0` means deterioration.** For every endpoint the
"allows zero / negative" and ceiling–floor questions are answered before the log-ratio is
proposed.

### G.1 Why the log-ratio is defensible here

`VERIFIED`: latencies are strictly positive by construction (`4311` always follows perturbation
onset in-window; observed minimum 1.0 s at p05). Zeros and negatives are structurally impossible,
so `ln` is safe without a floor term. The lane-deviation channel `LN` **is** signed (metres from
centre line), so a log-ratio must be applied to a magnitude functional, not to `LN` itself.

### G.2 Proposed latency endpoint (primary candidate)

Let `L_{i,r,j}` = latency of perturbation `j` in recording `r` of subject `i`,
with `r ∈ {calib, base}`.

```
A_{i,r}  = mean_j ( 1 / L_{i,r,j} )                      response speed;  ↑ = better
Y^{lat}_i = ln( A_{i,calib} / A_{i,base} )               ↑ = slower  ⇒ D > 0 = deterioration
```

This deliberately mirrors the frozen Phase 2 `Y_speed` definition (SPEC §18.3) so that the two
are *formally* comparable — **not** so that they can be pooled. `UNKNOWN`: whether the Phase 2
target and this one share a latent component; that is a research question (§I).

Robustness variants to be declared before fitting, not selected after:

```
Y^{med}_i    = ln( median_j L_{i,base} / median_j L_{i,calib} )
Y^{cens}_i   = as Y^{lat}, with censored perturbations pinned at the 10 s window
Y^{perbin}_i = the same functional computed on each 5-minute bin → a trajectory, not a scalar
```

### G.3 Proposed lane-keeping endpoint (secondary candidate)

`LN(t)` in metres, signed. On a window `W`:

```
SDLP_{i,W}   = sqrt( mean_{t in W} ( LN(t) - mean_W LN )^2 )          metres, ↑ = worse
RMSdev_{i,W} = sqrt( mean_{t in W} LN(t)^2 )                          metres, ↑ = worse
Y^{SDLP}_i   = ln( SDLP_{i,base,W} / SDLP_{i,calib,W'} )              ↑ = D > 0
```

**Ceiling/floor caveat, must be checked before use:** if a participant never exceeds the lane
boundary in the calibration window, `SDLP` is a small positive number whose sampling distribution
is heavily skewed; the log-ratio then has an unstable denominator. Equally, `SDLP` is **not**
bounded above (`|LN| ≤ 3.75/2 m` only while on-road). Both must be measured on real `LN` before
this endpoint is adopted.

### G.4 Guardrails to declare with any endpoint

1. **The interval `W` must be identical** for calibration and baseline, and must not start at
   recording onset (SPEC §17.5: a prefix window encodes the onset response).
2. **Condition stratification**: any time-based comparison must be stratified by the `3200`
   condition state, or restricted to condition-stable stretches (D.6).
3. **Finite-trial uncertainty must be reported** for every `D`, as in Phase 1.75 §17.4 — the
   target is again a difference of two noisy measurements, `Var(ε_Y) = Var(ε_c) + Var(ε_b)`.
4. **Do not choose between `Y^{lat}` and `Y^{SDLP}` on the basis of which correlates better with
   EEG.** Target selection is by measurement stability and pre-existing literature only
   (SPEC §17.4, §18.3).
5. **A single scalar per person is not the objective.** The structural gain here is ~14 ordered
   bins per person; collapsing to one number discards it.

### G.5 Do not assume the personal-baseline form is superior

Per SPEC §3.1 and the Phase 3 brief §8: `ΔX` trades a bias term for a variance term. BCIT's design
supports a **fair, pre-declared comparison** of `X_current` vs `X_current − X_baseline` *because*
it provides both a same-visit calibration recording and a long recording. That comparison is a
hypothesis to be tested, not a premise.

---

## H. SADT audit (NEMAR `nm000275`)

### H.1 Identity

| field | value | level |
|---|---|---|
| Name | Multi-channel EEG recordings during a sustained-attention driving task | VERIFIED |
| "SADT" expansion | **Sustained-Attention Driving Task** — not "Simulated Attack" / "Sleep Attack" | VERIFIED |
| Paper | Cao, Chuang, King & Lin, *Sci Data* **6**:19 (2019), doi:10.1038/s41597-019-0027-4 | VERIFIED |
| Raw data | figshare `10.6084/m9.figshare.6427334` (v5), CC BY 4.0 | VERIFIED (via mirror `sourcedata/`) |
| Preprocessed | figshare `10.6084/m9.figshare.7666055` | VERIFIED |
| BIDS repack | NEMAR `nm000275` v1.0.0, doi:10.82901/nemar.nm000275 | VERIFIED |
| OpenNeuro ID | **none** | VERIFIED |
| On-disk size | raw ≈ 19.56 GB; preprocessed ≈ 16.61 GB (per mirror `sourcedata/` records) | VERIFIED |
| Access | public; `.set` payloads in the GitHub mirror are annex pointer files (6 510 bytes for all, i.e. no bytes) | VERIFIED |

### H.2 Participants and sessions

`VERIFIED` from `participants.tsv` (27 rows) and the tree (62 `*_events.tsv`):

* **27 independent subjects**, original IDs `s01…s55` with gaps (`s03, s07, s08, s10, s15–s21,
  s24–s30, s32–s34, s36–s39, s46, s47, s51`). ≥ 28 allocated IDs were never released; reason
  `UNKNOWN`.
* **62 sessions** total, 1–5 per subject — the same person contributes repeated sessions.
* No participant is formally excluded; effective usable N = **27**.

### H.3 Structure — and the decisive negative

| dimension | evidence |
|---|---|
| **Personal baseline** | **ABSENT.** `VERIFIED` the tree contains exactly one task (`task-driving`); no resting, eyes-open, or alert-driving task exists. The only baseline-like object is behavioural: *"For each subject, the RTs collected from the first 10 minutes of the experiment were used to construct a null distribution of optimal RTs"* — a per-subject, per-session RT window, **shipped as no separate file**. |
| **Degradation mechanism** | `VERIFIED` time-on-task within one ~41–118 min session, under a **sleep-normalised** protocol. **This is not a sleep-deprivation dataset.** |
| **Objective endpoint** | `VERIFIED` RT := response onset − deviation onset, at sample resolution. 27 192 observations; median 0.956 s, p05 0.504 s, p95 6.352 s. Plus `vehicle_position` as a MISC data channel (0–255 quantised) → SDLP derivable. |
| **Temporal resolution** | `VERIFIED` trial-locked; every event row carries `sample` at 500 Hz, and I verified `onset × 500 == sample` for **0 mismatches** in sub-01/ses-01 (597 events) and sub-55/ses-01 (1 923 events). |
| **Longitudinal structure** | `VERIFIED` 188–716 deviation trials per session (median 380); within-session halves: **35 / 62** sessions have a slower second half (median first-half 0.927 s vs second-half 0.938 s in the released events). |
| **EEG** | `VERIFIED` 500 Hz, 16-bit, 32 channels = 30 scalp + A1/A2 mastoid (both recorded as data channels), ref mastoid, 60 Hz powerline, `SoftwareFilters: n/a`, `RecordingType: continuous`. Coordinates are nominal template, not measured. |
| **Curation transparency** | `VERIFIED` the repack documents an undocumented trigger `255` present only in sub-54/sub-55 (21 occurrences) rather than dropping it. Good practice, and a reason to trust the rest. |
| **Likely role** | Trial-locked external validation of a *time-on-task* EEG→RT relation; **not** a sleep-deprivation set, and **not** usable for a personal-alert-baseline design. |

### H.4 A discrepancy worth recording (contradiction, not smoothed)

`VERIFIED`: Table 2 of the source paper sums to **8 5715 = 81 571** events over 62 sessions,
while the paper's own Figure 3 caption and the released data both give **81 576**. The difference
is exactly **5**. The released file counts are: `deviation_onset_left` 13 522 +
`deviation_onset_right` 13 670 + `response_onset` 27 192 + `response_offset` 27 171 +
`undocumented_255` 21 = **81 576**; excluding the 21 undocumented triggers gives **81 555**, which
matches neither figure. So the source table, the source caption and the released bytes are not all
mutually consistent. Reported as-is; it does not affect the endpoint definition (RT is
`253 − (251|252)`), and it does not affect any count used in this audit.

### H.5 One unreproducible source claim

A commissioned landscape note asserted SEED-VIG is a *"self-reported vigilance"* / subjective-only
dataset. I could not verify that (SEED-VIG was understood to carry a `vigilance` score derived
from eye-movement/PERCLOS behaviour, which would make it a third *-objective-adjacent* stream).
**That claim is UNKNOWN and is not repeated as fact here.** It belongs in the next round's checklist.

---

## I. Cross-dataset compatibility (fields, not scores)

| field | ds004902 (frozen Phase 2) | BCIT ds004118 | BCIT ds004120 | SADT nm000275 |
|---|---|---|---|---|
| task | resting eyes-open, 2 states | steering-only driving | speed+steering driving | lane-departure driving |
| states | NS vs SD (sleep-deprived) | non-fatigued (calibration) | time-on-task | time-on-task |
| baseline semantics | NS = personal alert baseline | *is* the baseline | calibration recording | **none** |
| within-person samples | 2 | 1 (15 min) | ~14 bins (69 min) | 1 session, 188–716 trials |
| endpoint | PVT response speed | latency / `LN` | latency / `LN` | RT / `vehicle_position` |
| endpoint ↔ EEG | different recordings | same matrix | same matrix | same matrix |
| sfreq | 500 Hz (resampled from source) | 2048 (T1) / 1024 (T2,T3) | 2048 / 1024 | 500 Hz |
| ref | average | `CMS` | `CMS` | mastoid A1/A2 |
| channels | 61 | 64 + 4 EOG + 2 M + 4 veh | same | 30 scalp + 2 M + 1 veh |
| 4 s / 4 s at 500 Hz | yes | yes (integer decimation) | yes | yes (identity) |
| powerline | `UNKNOWN` | 60 Hz | 60 Hz | 60 Hz |
| N independent | 29 | 156 (102 paired) | 109 (102 paired) | 27 |
| licence | — | **CC0** | **CC0** | CC BY 4.0 |

`VERIFIED` unless marked. Two portability hazards are now explicit rather than latent:
**site-dependent sampling rate** (T1 2048 vs T2/T3 1024 Hz — a perfect site fingerprint if
handled carelessly) and **site-confounded task design** (T2's 2×2 manipulation). Any pooled model
must carry site as a *grouping* factor for evaluation, not as a predictor.

---

## J. The three hard gates

```
Gate 1  subject identity / overlap
        ds004118 <-> ds004120 : PASS
          key = legacy_labID (explicit column + documented program-unique + yob corroboration)
          N_paired = 107 ; same-day subset = 102
          negative control: a naive sub-NN join would be 89 % wrong
        SADT                  : N/A (single dataset, no pairing required)

Gate 2  scientifically valid baseline relationship
        ds004118 + ds004120   : PASS
          calibration = documented "non-fatigue state performance", same task, same visit,
          recorded first in 107/107, same-day in 102/107
        SADT                  : FAIL
          no alert/normal-state EEG baseline exists in the release; the only baseline-like
          object is a behavioural first-10-min RT window, not shipped

Gate 3  EEG <-> objective performance temporal linkage
        ds004118 + ds004120   : PASS
          trial-locked (sample indices on the EEG clock) + continuous vehicle channels in the
          same matrix, with published precedent for the continuous-lane-deviation endpoint
        SADT                  : PASS
          trial-locked at 500 Hz; onset x 500 == sample verified with 0 mismatches
```

**BCIT `G1 ∧ G2 ∧ G3 = TRUE`** → the personal-baseline route **proceeds to a minimal download**.

**SADT `G2 = FAIL`** → SADT **cannot** test the application hypothesis as a personal-baseline
design. It remains usable as a *trial-locked, time-on-task external validation* set under a
different, weaker hypothesis (no personal alert baseline). **The gate is not lowered to keep SADT
alive.**

---

## K. Critical unknowns — what only downloading data can answer

1. **The true sampling frequency of the vehicle channels.** `channels.tsv` declares 2048 Hz for
   all 74 channels, but the README says the vehicle log was 100 Hz. If `LN`/`ANG`/`SP`/`SD` are a
   zero-order-held 100 Hz signal written at 2048 Hz, their **effective bandwidth is 50 Hz** and
   they must be decimated before any SDLP computation. Only bytes can settle this — the test is
   whether consecutive samples repeat in blocks of ~20.
2. **Whether `3200` marks a real condition change each occurrence** or is a repeated state log.
   Determines whether the time-on-task analysis must be stratified.
3. **The within-visit offset in minutes** between calibration end and baseline start
   (`acq_time` is date-resolution only).
4. **LN quantisation and units.** The description says metres; the actual numeric range,
   quantisation step and on/off-road clipping are unverified.
5. **Interval between the calibration run and any preceding practice** (10–15 min of simulator
   practice precedes EEG setup per README) — relevant to whether the first minutes of calibration
   are itself a practice-affected window.
6. **A real EEG data-quality read**: line noise at 60 Hz, impedance records, and whether
   T1's 2048 Hz recordings are genuine 2048 Hz acquisition or an upsampled 1024 Hz stream.
7. **Cross-frame comparability of the montages** (§F.3): both coordinate sets are template
   positions with `EEGCoordinateUnits: n/a`, so the 64→256 subsetting rests on an assumption that
   must be falsified against real topography.
8. **Whether the 49 calibration-only subjects have counterpart recordings** in the sibling BCIT
   datasets — `ds004105` (Auditory Cueing, N = 17), `ds004119` (Basic Guard Duty),
   `ds004121` (Mind Wandering, N = 21), `ds004122` (Speed Control, N = 32),
   `ds004123` (Traffic Complexity, N = 29). Metadata-only and cheap; could lift paired N above 107
   and add longer tasks. **Note:** `ds004122`'s README indicates its calibration run may live in a
   separate dataset, so the pairing must be re-derived per dataset, not assumed.
9. **The wider landscape** (§N). A commissioned metadata survey returned mid-audit and is
   summarised in §O; it is *not* independent of this report's own evidence levels and its
   load-bearing negative claims still need re-verification.

---

## L. Minimal next download

Not "download everything". The smallest set that falsifies or confirms §K.

**Tier 0 — behaviour only, no EEG (≈ 10 MB, minutes).** Already done. This *is* the audit.

**Tier 1 — two subjects, both recordings, to settle the endpoint and montage encoding.** Pick two
same-day pairs from the 102, deliberately **one from each montage class** (see
`bcit_recording_index.csv` for the exact `participant_id` of every `legacy_labID`):

* a **T3 256-channel** pair — e.g. legacy `3101`, which is `ds004118/sub-98` and `ds004120/sub-51`,
  both `ses-01`, same acquisition date, 1024 Hz;
* a **T2 64-channel** pair — e.g. legacy `2002`, which is `ds004118/sub-22` and `ds004120/sub-23`,
  both `ses-01`, same acquisition date, 1024 Hz.

Four recordings, eight files (`*_eeg.set` + `*.fdt` each). Order of work:

1. **Vehicle-channel truth test (§K.1).** Read `LN`/`ANG`/`SP`/`SD` and check whether consecutive
   samples repeat in blocks (a zero-order-held 100 Hz log would repeat ~20×) or vary
   sample-to-sample. This decides whether the vehicle signals are 100 Hz or genuine ~1 kHz data,
   and therefore whether `LN` may be treated as a genuine high-rate signal.
2. **Montage check (§F.3).** Confirm the 64-channel subset selected on the dense T3 grid has
   plausible topography — e.g. that alpha/theta power at the chosen `PO` electrodes behaves like
   the T2 `PO` group. This is the one place where the template-coordinate assumption can be
   falsified cheaply.
3. **Clock and grid check.** Confirm event `sample` indices land on the declared EEG clock, and
   that a 4 s / 4 s grid at 500 Hz is constructible from 1024 Hz **with an explicit anti-alias
   filter** (none is declared: `SoftwareFilters: n/a`).
4. **`LN` range and quantisation**, then a first `SDLP`; test the §G.3 ceiling/floor caveat.
5. **Condition-marker semantics (§K.2).** Correlate `SP`/`LN` against the `3200` markers to learn
   whether they mark real difficulty changes.

**Explicitly not yet:** the remaining 373 recordings, any EEG→behaviour model, any feature
extraction, any channel selection beyond the length-preserving montage subset.

**Tier 2 — a 10–12 subject stratified sample.** Balanced across **both montage classes and both
sampling strata** (T1 64 ch/2048 Hz, T2 64 ch/1024 Hz, T3 256 ch/1024 Hz) and across the endpoint's
between-subject range (include at least one subject from each tail of the per-subject median
latency distribution, e.g. ≈ 1.2 s and ≈ 4.0 s). Purpose: estimate endpoint reliability, check the
4 s / 4 s portability claim, and check that the 256→64 subset produces comparable ROI features
across sites. **Byte cost `UNKNOWN`** — file sizes were not fetched in this round; the whole
calibration dataset is on the order of 124 GB, so a 10–12 subject subset is on the order of a few
GB, but that must be measured before it is promised.

**Explicitly not yet:** the remaining ~360 recordings, any EEG→behaviour model, any feature
extraction, any channel selection beyond the length-preserving montage subset.

**SADT:** no download. `G2 = FAIL` for the application hypothesis.

---

## M. Scientific blockers and contradictions found

1. **Corrected during this audit, three times.** (a) I first concluded the continuous vehicle data
   was not released; it is, as `OTHER`-type channels. (b) I mis-decoded `acq_time` twice before
   checking the position of the literal `'T'`. (c) I described all sites as 64-channel when T3 is
   256-channel. All three were caught by recomputation, and all three are recorded because the
   report's credibility rests on them being visible, not on the final text looking clean.
2. **A dataset-set definition is required from the PI:** `N_paired = 107` (any date) or
   **102** (same-day only). This changes the scientific claim, not just the sample size.
3. **Endpoint definition is required from the PI:** per-trial response latency (`4311`-based,
   ICC 0.531, no published precedent for this dataset) vs continuous lane deviation
   (`LN`-based, published precedent in Touryan et al. 2014, needs `LN` bytes to validate).
   Selecting whichever predicts better from EEG would be a researcher degree of freedom.
4. **Condition confound:** the 2×2 `3200` manipulation lives inside the recordings. Ignoring it
   risks reading task difficulty as fatigue.
5. **Documentation errors found in the source datasets** (reported, not smoothed):
   `ds004120/README.md` cites `ds004118` where `ds004119` (Basic Guard Duty) is meant;
   SADT's Table 2 total (81 571) disagrees with its own Figure 3 caption and the released data
   (81 576).
6. **Not a blocker, but a standing limitation:** SADT has no alert baseline and cannot carry the
   application hypothesis, whatever its trial-level quality.

---

## N. Proposed next step

1. **PI decision — analysis set.** Confirm 102 (same-day) vs 107 (any-date) as the paired set.
2. **PI decision — primary endpoint family.** Latency vs continuous lane deviation, declared
   *before* any download, on measurement-stability and literature grounds only.
3. **PI decision — montage strategy.** Confirm the 64→256 nearest-neighbour subset (§F.3) as the
   harmonisation route, versus restricting the phase to the 48 paired T1/T2 subjects.
4. **PI decision — the degradation mechanism** (§O). BCIT's "degraded" state is within-visit
   time-on-task fatigue, **not** sleep deprivation. DROZY is the only found dataset with a genuine
   rested→sleep-deprived within-person contrast, and it has N = 14 and 5 electrodes. Choosing
   between "large N, time-on-task" and "small N, true sleep deprivation" changes what the phase can
   ever claim, so it must be decided before any download.
5. **Then, and only then, Tier 1 download** (§L): two same-day pairs, one per montage class.
6. **Verify the sibling BCIT datasets** (`ds004105`, `ds004119`, `ds004121`–`ds004123`) for
   additional same-subject sessions — metadata only, cheap, and could raise paired N above 107.
7. **Treat §O as leads, not findings.** Re-verify the survey's load-bearing negative claims against
   the primary records before any of them changes the plan.

---

## O. Wider landscape (commissioned survey, leads only)

Full text: `docs/phase3_metadata_survey_2026.md`. Evidence levels below are as reported by that
survey; **only claims I re-verified myself are marked VERIFIED here.**

| candidate | what it offers | what disqualifies it for *this* hypothesis | level |
|---|---|---|---|
| **DROZY** (ULiège; WACV 2016) | 14 subjects, **3 PVTs across 28–30 h of waking**: PVT1 rested ≈10:00, PVT2 ≈03:30, PVT3 ≈12:00. Per-trial RT, lapses = RT ≥ 500 ms, "perfectly time-synchronized". 512 Hz, but only **5 EEG channels** (Fz, Pz, Cz, C3, C4). 2.46 GB, direct download | **N = 14**; 5 electrodes; **no driving task at all** — the paper mentions a simulator once, in a reference | reported; landing page and licence PDF resolved, licence text not machine-readable |
| **BCIT siblings** — `ds004105` (N=17), `ds004121` (N=21), `ds004122` (N=32), `ds004123` (N=29) | Same CC0 BioSemi pipeline, perturbation-locked RTs, vehicle log; each README names a non-fatigued calibration contrast | Whether each ships **its own** calibration run is `UNKNOWN`; `ds004122` reportedly keeps calibration in a separate dataset | titles/counts reported; not re-derived here |
| **ds004902** | already frozen | resting state, **not** behaviour-locked; effective PVT N = 29 | frozen Phase 2 |
| **MPD-DF** (Sci Data 2026) | 50 subjects, 2 h simulated drive, 32 ch @ 500 Hz raw EDF, 11.1 GB | endpoint is **physician annotation** (Wakefulness/Fatigue1-4), no behavioural endpoint; protocol requires ≥ 7 h sleep | reported |
| **SEED-VIG** | 23 subjects, 2 h monotonous drive, 1 Hz continuous labels | no alert condition (sessions start post-lunch at the circadian peak); label is **PERCLOS from eye-tracking**, not a driving-performance measure; and **raw EEG is not in the public release** (feature tensors only) | reported |
| **dd-Database** (Dryad) | 10 subjects, 2 × 2 h driving simulator, 4 EEG + 2 EOG + 1 ECG | N = 10; annotation semantics `UNKNOWN` | reported |
| **PhysioNet `drivedb`** | — | **no EEG at all** (ECG, EMG, GSR, respiration); stress ratings not released | reported |
| **`ds007509` "1hrPVT"** | 69 subjects, CC0, directly downloadable, "PVT" in the title | declared `response_time` field is claimed **never populated** — events carry stimulus markers only | **NOT re-verified here**: my reconstruction of the file path returned 404, so the trap-claim stands unconfirmed either way |

**The structural conclusion, and it is uncomfortable:** *no* public dataset found so far satisfies
all five requirements at once. The two halves are split:

* **within-person alert baseline + per-trial objective endpoint** exists (DROZY) but at N = 14 and
  without driving;
* **large N + raw EEG + objective driving performance** exists (BCIT) but its "degraded" state is
  **time-on-task fatigue, not sleep deprivation**.

BCIT is the only candidate that reaches the handover's own `N_paired ≳ 80` bar, and it does so by
trading sleep deprivation for within-visit time-on-task. **Whether that trade is acceptable is a
`WHAT` decision and belongs to the PI, not to this audit.** It is the single most consequential
open question the phase has surfaced.

**Hard stop reached.** No EEG downloaded, no model written, no feature extracted, no channel
selected, no protocol tuned. The 29 ds004902 PVT subjects were not touched.
