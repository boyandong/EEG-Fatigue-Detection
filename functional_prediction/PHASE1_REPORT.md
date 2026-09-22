# PHASE1_REPORT.md — vigilance_generalization_v1

Branch: `vigilance_generalization_v1` (independent; all legacy NS/SD work is out of scope)
Status: **Phase 1 complete. No model trained. Awaiting PI review before Phase 2.**
Governed by [`SCIENTIFIC_SPEC.md`](SCIENTIFIC_SPEC.md).

---

## A. Data provenance

### A.1 Which source files were actually used

| layer | path | usable? |
|---|---|---|
| BIDS raw EEG | `data/ds004902/metadata_behavior/sub-*/ses-*/eeg/*_task-eyes{open,closed}_eeg.{set,fdt}` | **NO** |
| BIDS metadata | same tree: `participants.tsv`, `*_eeg.json`, `*_channels.tsv`, `beh/*task-pvt_beh.tsv` | **YES** (text files intact) |
| legacy preprocessed EEG | `data/ds004902/preprocessed/*.set` + `.fdt` | **YES** — the only readable EEG |

**Why the BIDS raw EEG is unusable:** all 218 `.set` and 218 `.fdt` under
`metadata_behavior/` are **broken git-annex symlinks** (`WinError 1920`,
reparse tag `0xa000001d` pointing at `../../../.git/annex/objects/...`).
`.git/annex/objects` does not exist and there is no file >1 MB under `.git`/`.datalad`.
Machine-checked, not inferred:

```
BIDS tree: 218 .set, 218 .fdt
  .set status: Counter({'BROKEN(1920)': 218})
  .fdt status: Counter({'BROKEN(1920)': 218})
files >1MB under .git/.datalad: 0
all .set in workspace: readable 142, broken 218
```

The eyes-open/eyes-closed separation exists **only** in the filename entity of that
unreadable tree. It cannot be exploited locally without re-downloading the dataset.

### A.2 How eyes-open is proven

The third-party preprocessing preserved the **original raw filename** in each header
(`comments: "Original file: ..."`, `setname`, EEGLAB `history` `pop_loadbv(...)` paths).
Verdicts over the 139 admitted recordings:

| verdict | n | basis |
|---|---|---|
| `explicit_open` | 121 | source name contains an explicit open token: `*_sleep_open`, `*_D_open`, `*_Rest_openeyes_*`, `*_restOpen_*`, `*_sleep_openeye`, `xiaojiayi_D_open_5min` |
| `implicit_open` | 17 | matches a known eyes-open resting family (`*_rest_ns`, `*_rest_sd`, `*_Rest_ns`, `*_S.vhdr`, `*_D.vhdr`) without an inline token |
| `no_evidence` | 1 | `sub-54_ses-1` — no eye-state token anywhere in the header |
| `closed` | **0** | — |

Decisive arguments:

1. **Zero of the 142 readable files carries any eyes-closed token.** The upstream raw corpus
   stored eyes-closed recordings with a `closed` token in the same naming scheme; none appears.
2. The preprocessing pipeline selected **exactly one recording per session**, and every one of
   those selections is an eyes-open family name.
3. The BIDS sidecars confirm both `task-eyesopen` and `task-eyesclosed` existed upstream, so
   this is a genuine selection, not an accident of a corpus that only had eyes-open.

**Residual uncertainty, binding on interpretation:** this rests on filename families, not on a
task/event marker. `sub-54_ses-1` is admitted with **`eyes_open_unverified`** status and is
counted separately — it cannot be silently absorbed. Segment-level eye state is not recoverable
at all.

### A.3 Sampling / channels / duration

| property | value | how verified |
|---|---|---|
| sampling rate | 500 Hz for 139/142 | EEGLAB header `srate` |
| channels | 61, all 139 | header `nbchan`; two montage **orderings** exist (124 / 18 files) → every recording is reordered by channel **name** |
| reference | `average` for all 142 | header `ref` |
| units | µV | BIDS `channels.tsv` + EEGLAB convention; **no independent calibration record exists** |
| epoch | 4 s (2000 samples), pre-epoched in the source | `pnts/srate`; never re-windowed, never concatenated |
| epochs per session | 57–74 in the working cohort (4–79 over all 139) | header `trials` |

### A.4 Preprocessing provenance

* Performed by a **third party** in MATLAB/EEGLAB 2023.0; repo-external path
  `D:\data_for_capstone_project\Resting-State-EEG-Dataset-for-SD\03_ica`.
* `setname` everywhere: `"... - 4-s epochs pruned with ICA"`.
* `pop_epoch` recorded for 56 files: event code `S 33`, window `[0 300]` → a 300 s segment was
  epoched to 4 s, then pruned to the surviving trials.
* Non-uniform channel subtraction across files (5 patterns): `''`×78, `'ECG','HEOR'`×38,
  `'ECG','FT9','FT10'`×21, `'IO','HEOG','VEOG'`×4, `'E1','E2'`×1.
* `pop_resample(EEG, 500)` recorded for **5 files**: `sub-40_ses-2`, `sub-47_ses-1`,
  `sub-50_ses-1`, `sub-50_ses-2`, `sub-53_ses-1`. **Anti-alias settings are not recorded** and
  the paired session of the same subject is usually not resampled. Flagged, not excluded.
* **No `pop_reref` in any history**; average reference is inherited from upstream.
* **Version mismatch:** `原始数据集.txt` records that preprocessing ran on dataset **v1.0.5**;
  the local BIDS `dataset_description.json` declares **v1.0.8**. Not re-run. Recorded as a
  provenance limitation.
* Real artefact rejection (ICA component removal) happened upstream and is **not reproducible
  from this workspace**. We add **no** new artefact heuristics.

### A.5 Subjects

| quantity | n |
|---|---|
| participants in `participants.tsv` | 71 |
| readable EEG recordings | 142 (71 × 2) |
| admitted (eyes-open, 500 Hz, 61 ch) | **139** |
| excluded | 3 — `sub-39/43/44_ses-2` declare **5000 Hz** (`pnts=20000`, 10× `.fdt` size) |
| subjects with **both** sessions admitted | **68** |
| paired **and** PVT-available (**working cohort**) | **29** |

Exclusions and reasons (`outputs/qc/eeg_exclusions.csv`):
`sub-39/43/44: missing_session (ses-2 header 5000 Hz)`.

### A.6 Cohort attrition 71 → 29

| step | removed | reason |
|---|---|---|
| 71 → 68 | sub-39, sub-43, sub-44 | `ses-2` is a 5000 Hz header → not 500 Hz |
| 68 → 40 (approx.) | 28 subjects | **no PVT trial file at all** (`sub-39…sub-69` have no `beh/` directory) |
| → 30 | 8 subjects | only **one** session has a PVT trial file |
| official-paired | 30 | both sessions present in `participants.tsv` |
| → **29** | sub-05 | **official summary exists but the raw NS trial file does not exist** |

---

## B. PVT reconciliation

### B.1 Counts

| set | n |
|---|---|
| raw PVT trial files found | 67 |
| parse errors | **0** |
| **official paired** (`participants.tsv` has both sessions) | **30** |
| **raw-trial paired** (both sessions have a usable trial file) | **29** |
| after 100–2000 ms filtering | **29** (no session lost its median) |
| official paired ∩ eyes-open EEG | 30 |
| raw paired ∩ eyes-open EEG | 29 |
| published reference N | **28** |
| **difference from published** | **+1** |

Header variants actually parsed and recorded per file (`outputs/manifests/pvt_manifest.csv`):
`trial|response_time` ×63, `trail|response_time` ×1, `trial|resoonse_time` ×1,
`trial|respones_time` ×1, `trial|response` ×1. Raw files were never rewritten.

### B.2 Official vs raw disagreement

Per-subject differences are in `outputs/pvt/pvt_reconciliation.csv`
(`difference_ns`, `difference_sd`). Both values are preserved; neither is treated as truth.

| subject | official NS | raw-filtered NS | difference |
|---|---|---|---|
| sub-02 | 303.0 | **328.0** | +25.0 |
| sub-03 | 349.0 | 313.5 | −35.5 |
| sub-07 | 328.0 | 330.0 | +2.0 |
| sub-11 | 296.0 | **330.0** | +34.0 |
| sub-12 | 349.0 | **300.0** | −49.0 |
| sub-17 | 366.0 | 367.0 | +1.0 |
| sub-32 | 308.5 | 308.5 | 0.0 |
| sub-70 | 280.0 | 280.0 | 0.0 |

The official and recomputed medians agree exactly for several subjects (e.g. `sub-18`,
`sub-25`, `sub-30`) and disagree by up to ~50 ms for others. **No target was chosen on the basis
of which one correlates better with any feature.**

### B.3 Why the published N is 28 and we get 29 — exact answer

> **CORRECTION (superseding, added during Phase 1.5).** The `<45 valid trials` hypothesis below
> was **withdrawn as the leading explanation** after the acceptance review observed that the
> paper's flow is `71 → 64 valid paired EEG → 28 paired EEG+PVT`, not "screen 30 PVT subjects
> down to 28". The one-subject gap is now attributed to a **paper-side EEG exclusion** rather
> than a PVT filter. See [`paper_sample_reconciliation.md`](paper_sample_reconciliation.md) for
> the corrected analysis, which identifies `sub-32` (563 of its epochs exceed 200 µV in one
> session — the worst of our 29) as the leading candidate and explains why it is **not**
> adopted. The `<45 trials` rule is retained below **only** as an explored-but-unrejected
> record; it was never applied.

The single subject in dispute is **sub-05**: `participants.tsv` reports both NS and SD PVT
summaries, but there is **no raw NS trial file** on disk. So sub-05 is official-paired but not
raw-paired. That accounts for the 30 → 29 step exactly.

Starting from our 29, we searched for an **a priori, data-level** filter that yields 28
(`outputs/pvt/pvt_subject_sets.json → published_n_alternative_filters`):

| candidate filter | n | removes | yields 28? |
|---|---|---|---|
| ≥40 valid trials per session | 29 | – | no |
| **≥45 valid trials per session** | **28** | **sub-11** | **yes** |
| ≥48 valid trials per session | 13 | 16 subjects | no |
| median RT ∈ [200, 1000] ms | 29 | – | no |
| median RT ∈ [250, 600] ms | 29 | – | no |
| exclude sub-70/sub-71 (≈90 trials vs ≈47) | 27 | 2 | no |
| positive responders only (**not defensible**) | 27 | 2 | no |
| require official *and* raw in both sessions | 29 | – | no |

**Only** `≥45 valid trials per session` reproduces 28. `sub-11` has 44 valid NS trials after the
100–2000 ms filter (2 of 46 responses out of range).

> **Conclusion: we cannot reproduce the published ~28-subject selection from the released data
> alone.** A 45-valid-trial criterion is a plausible but unstated rule; adopting it to match a
> published N would be selecting a subject set to fit, so it is **reported and not applied**.
> The working cohort stays at **29**. Sensitivity of every reported statistic to that single
> drop is given in §C.4.
>
> *(Phase 1.5 correction: this rule is superseded as the explanation — see the note at the top
> of this section and `paper_sample_reconciliation.md`. The numbers below remain historical
> fact.)*

---

## C. Paper-reference reproduction

n = 29. Features: epoch-wise theta **relative** power, across-epoch SD, ROI = channel
arithmetic mean. Reference values quoted from the source paper: ρ_F ≈ 0.54, ρ_CT ≈ 0.56.

### C.1 Primary statistic

| ROI | ρ(Δtheta var, Δmedian RT) | p | bootstrap CI95 | reference | difference |
|---|---|---|---|---|---|
| **F** | **+0.102** | 0.599 | [−0.295, +0.476] | +0.54 | **−0.438** |
| **CT** | **+0.393** | **0.035** | [+0.030, +0.692] | +0.56 | **−0.167** |
| **PO** | +0.346 | 0.066 | [−0.031, +0.644] | n/a | n/a |

Using the log target `Y_logRT` instead: F +0.041, CT +0.329, PO +0.296.

**Verdict: CT is in the right direction and nominally significant; F does not reproduce.**
The direction, the ordering (CT > PO > F) and the significance of CT are consistent with the
reference. The frontal value is far below the published 0.54.

### C.2 Group-level SD−NS changes

| ROI | Δ theta variability | p | Δ theta relative power | p |
|---|---|---|---|---|
| F | +0.0085 | 0.237 | +0.0102 | 0.502 |
| **CT** | **+0.0179** | **0.006** | **+0.0273** | **0.017** |
| **PO** | **+0.0186** | **0.020** | +0.0264 | 0.083 |

Also explicitly computed (formula **and** values): frontal Δ theta relative power mean =
+0.0102, CT = +0.0273, PO = +0.0264. Theta variability increases most in CT/PO; the frontal
change is the weakest on both statistics.

### C.3 Possible reasons for the discrepancy — analysis only, nothing was tuned

1. **Different PSD parameters (most likely).** The paper does not report its Welch settings. We
   fixed `nperseg=2000, noverlap=0, nfft=2000, hann, detrend=constant, density` **a priori**.
   Different epoch-ensemble averaging changes across-epoch SD of relative power directly.
2. **Different subject set.** We use 29; the paper uses ~28, and the screening rule is not
   stated in the released data (see §B.3).
3. **Unknown upstream artefact handling.** ICA component rejection happened outside this
   repository with unknown criteria; it affects exactly the kind of epoch-to-epoch variability
   being measured.
4. **Two preprocessing families.** The 142 files come from at least two operator trees
   (`D:\...` and `/Users/ruirui/...`), and 5 recordings were resampled with unknown anti-alias
   settings.
5. **Our frontal ROI is `Fp1…F8` only; the paper's exact frontal definition is not verifiable
   here.** The ROI list we used was supplied by the PI and forms an exact 61-channel partition;
   a slightly different frontal channel set could move ρ_F substantially at n = 29.

### C.4 Sensitivity (reported, **not** adopted)

Dropping `sub-11` (the only subject implied by a 45-valid-trial rule): F +0.093 (p = 0.638),
CT +0.387 (p = 0.042), PO +0.334 (p = 0.083). **The conclusions do not change**, so the
one-subject discrepancy is not what drives the frontal mismatch.

### C.5 What this check does and does not establish

It **does** establish that the data entry point and the spectral extractor produce numbers of
the right order with the right sign structure in the right ROIs — an implementation is not
obviously broken. It **does not** establish a reproduction of the published statistic, and per
`SCIENTIFIC_SPEC.md` §11 nothing was tuned to make it look better.

---

## D. Mechanism v1

### D.1 Definitions as implemented (verbatim from `src/mechanism_features.py`)

\[
S_{e,c}=\underbrace{0.816496580927726}_{\sqrt{2/3}}\Big[\ln(P_{\theta,e,c}+\epsilon)-\tfrac12\big(\ln(P_{\alpha,e,c}+\epsilon)+\ln(P_{\beta,e,c}+\epsilon)\big)\Big]
\]

\[
S_{e,r}=\operatorname{median}_{c\in R_r} S_{e,c}
\qquad
M_r=\frac1N\sum_{e=1}^{N}S_{e,r}
\qquad
J_r=\sqrt{\frac{1}{N-1}\sum_{e=1}^{N}\big(S_{e,r}-M_r\big)^2}
\]

\[
\Delta M_{i,r}=M^{SD}_{i,r}-M^{NS}_{i,r}
\qquad
\Delta \log J_{i,r}=\ln\frac{J^{SD}_{i,r}+\epsilon_J}{J^{NS}_{i,r}+\epsilon_J}
\]

Six coordinates: `delta_M_F`, `delta_M_CT`, `delta_M_PO`, `delta_logJ_F`, `delta_logJ_CT`,
`delta_logJ_PO`. **2 feature families × 3 spatial regions.** No other feature exists in this
representation.

ROI partition: F = 16, CT = 28, PO = 17, total **61** — an exact partition of the montage, no
duplicates, no unmapped channel.

### D.2 Numeric ranges (n = 29 paired subjects)

| coordinate | mean | SD | min | max | paired t | p | dz |
|---|---|---|---|---|---|---|---|
| `delta_M_F` | +0.0508 | 0.3145 | −0.7316 | +0.6013 | +0.87 | 0.392 | +0.162 |
| `delta_M_CT` | +0.1172 | 0.2414 | −0.3457 | +0.5989 | +2.61 | 0.014 | +0.485 |
| `delta_M_PO` | +0.1142 | 0.3519 | −0.6284 | +0.9544 | +1.75 | 0.091 | +0.325 |
| `delta_logJ_F` | +0.1136 | 0.3106 | −0.7216 | +0.5409 | +1.97 | 0.059 | +0.366 |
| `delta_logJ_CT` | +0.1738 | 0.3754 | −0.4381 | +1.0897 | +2.49 | 0.019 | +0.463 |
| `delta_logJ_PO` | +0.1708 | 0.2626 | −0.4996 | +0.5613 | +3.50 | 0.002 | +0.650 |

> These are **descriptive group statistics on 29 subjects**, reported because the deliverable
> requires the numeric range. They are **not** a result, **not** a biomarker claim, and **not**
> a selection criterion. No coordinate is dropped or reweighted because of its p-value.

Per-session values (`M_F…J_PO`) are in `outputs/mechanism_v1/session_features.csv`:
median `M_F` ≈ 0.30–0.34, `J` per session ≈ 0.06–0.24, `n_epochs` 57–74.

### D.3 NaN / inf

**None.** All 58 session rows × 6 coordinates and all 29 paired rows × 6 coordinates are finite
and non-empty (`outputs/qc/qc_report.json`, check `nonfinite_or_missing_features`).

### D.4 Epsilon usage

* `epsilon_floor_activations_total` = **0** (no band power ever reached
  `1e-12 µV²`; minimum observed band power: theta 0.129, alpha 0.115, beta 0.264 µV²;
  maximum: theta 1901.7, alpha 1030.9, beta 1205.2 µV²).
* `eps_J_used_*` = **0** for all three regions → **every NS and SD recording has J > 0**, so
  `delta_logJ` needs no numerical floor at all. This is the preferred outcome flagged in
  `SCIENTIFIC_SPEC.md` §9.
* Composition identity `q_θ+q_α+q_β = 1` holds to `2.22e-16` (machine epsilon).

### D.5 Retained epochs / missing channels

* Epochs per session: 57–74 in the cohort (mean 69.9); `duration = n_epochs × 4 s` exactly.
* No session has fewer than 2 epochs → every session yields a defined `J`.
* **No missing channels.** 58/58 sessions report F = 16, CT = 28, PO = 17.
* `channel_order_reordered` is recorded per session: two montage orderings exist on disk and
  every recording is reordered by channel **name** before use, so the `.fdt` channel-major
  layout cannot silently permute the montage.

### D.6 Synthetic unit tests (`tests/test_mechanism.py`, 16/16 pass)

| test | property | result |
|---|---|---|
| A | `x' = kx`, k ∈ {0.1, 10, 100} → S, M, J unchanged | PASS, max\|ΔM\| ≤ 2.1e−11 |
| B | theta ↑ with alpha, beta fixed → S ↑ | PASS, all three ROIs |
| C | theta/alpha/beta all × c → S unchanged | PASS (c ∈ {0.25, 4, 25}), max\|ΔM\| ≤ 3.4e−12 |
| D | equal mean S, larger epoch fluctuation → J₂ > J₁, M similar | PASS, \|ΔM\| = 0.124, J 0.0000 → 0.6806 |
| E | common session-wide gain ×3.7 (and a common additive offset) → ΔM, ΔlogJ unchanged | PASS, max\|ΔΔM\| = 3.0e−14 / 1.1e−16 |
| F | same input + config rerun → bitwise-identical | PASS |
| G | composition identity exact | PASS, 2.22e−16 |
| H | epsilon floor unused on realistic power | PASS |
| I | ROI partition 16/28/17 | PASS |

**Test A is the key hardware property:** the representation is invariant to any session-wide
amplifier gain, so it does not depend on the absolute amplitude calibration of a device.
Also re-checked on **real** EEG (`scripts/06_verify_phase1.py` §8): ×7.5 gain gives
max\|ΔM\| = 5.6e−09, max\|ΔJ\| = 4.2e−09.

---

## E. Reproducibility

### E.1 Files added (all new; nothing existing was modified)

Everything lives under `project/vigilance_generalization_v1/`:

* `SCIENTIFIC_SPEC.md`, `README.md`, `PHASE1_REPORT.md`
* `config/dataset_ds004902.yaml`, `config/mechanism_v1.yaml`
* `src/`: `common.py`, `roi.py`, `spectral.py`, `mechanism_features.py`, `data_ds004902.py`,
  `pvt_targets.py`, `cohort.py`, `probe_eyesopen_provenance.py`
* `scripts/`: `00_audit_source_data.py`, `01_build_pvt_targets.py`, `02_build_eeg_manifest.py`,
  `03_extract_features.py`, `04_qc_features.py`, `05_paper_reference_check.py`,
  `06_verify_phase1.py`, `07_finalize_run_manifest.py`, `run_phase1.py`
* `tests/test_mechanism.py`
* `outputs/…` (all deliverables listed in §22 of the brief)

**Nothing under `data/` was written.** No legacy result directory was touched.

### E.2 Command

```powershell
cd project/vigilance_generalization_v1
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/run_phase1.py
```

### E.3 Config

`config/dataset_ds004902.yaml` (provenance-annotated adapter; every PSD parameter, the band
edges, the ROI lists, the PVT window, the eye-state requirement) and
`config/mechanism_v1.yaml` (frozen representation). All PSD parameters are config-driven; none
is hard-coded. Parameters the source paper does not report are explicitly marked
`not_specified_by_source_paper` with the value and the reason it was fixed a priori.

### E.4 Random seed

**None used.** There is no shuffling, sampling, initialisation or training in Phase 1. The run
manifest records `"random_seed_used": false`. The only stochastic step anywhere is the bootstrap
CI in the reproduction check, seeded explicitly (`BOOT_SEED = 20260916`).

### E.5 Runtime

Full pipeline **152.0 s** on the local machine (RTX 4060 Laptop / CPU-bound):

| stage | s |
|---|---|
| 00 source audit | 36.9 |
| 02 EEG manifest | 36.8 |
| 01 PVT | 0.4 |
| 03 feature extraction | 36.0 |
| 04 QC | 0.2 |
| 05 reproduction check | 16.9 |
| unit tests | 2.0 |
| 06 verification | 22.3 |
| 07 finalize | 0.4 |

### E.6 Hashes

`outputs/qc/run_manifest.json` carries SHA-256 for **16 source files, 2 configs and 21 output
files**, plus the nested per-stage manifests. `missing: []`.
Every admitted EEG recording has a distinct `.set` SHA-256 recorded in
`outputs/mechanism_v1/session_features.csv`; a fresh re-hash of `sub-02_ses-1.set` matches.

`git_commit: COMMIT PENDING` — this branch is not committed yet, so provenance currently rests
on file-content hashes only, as permitted by the working principles.

### E.7 Tests

* `tests/test_mechanism.py`: **16/16 PASS**
* `scripts/04_qc_features.py`: **18 checks, 0 FAIL, 0 WARN**
* `scripts/06_verify_phase1.py`: **25/25 PASS**

Verification is not self-referential: `06_verify_phase1.py` re-loads the raw `.set` files and
**recomputes** `M` and `J` for **all 58 sessions** from scratch, then compares against the
shipped CSVs — `max|ΔM| = 0.000e+00`, `max|ΔJ| = 0.000e+00`. It also re-derives all paired
deltas from the session table (exact), confirms the cohort definition agrees with the
manifests, and scans the source tree for forbidden constructs
(`log(mean(P))`, mean-of-ratio-then-log, recording-wise z-scoring, `if dataset ==`,
specparam/FOOOF imports) — all clean.

---

## F. Scientific blockers

Only items that genuinely affect the validity of the next stage.

**F1 — Only ~40 % of the dataset can ever be used, and this is a hard data limit.**
PVT exists for ≈40 of 71 subjects; combined with eyes-open + 500 Hz, the working cohort is
**29**. Any Phase 2 protocol is an n ≈ 29 study, which fixes the achievable statistical power
and makes researcher degrees of freedom the dominant validity threat. This is a property of the
released data, not of our pipeline.

**F2 — Eyes-open provenance is family-level, not event-level.**
Zero eyes-closed tokens among 142 files, and upstream demonstrably had both eye states, so the
inference is strong; but there is no task marker and one recording (`sub-54_ses-1`) has no token
at all. Segment-level eye state is unrecoverable. If a reviewer requires event-level proof, the
only route is re-downloading the BIDS tree — which is currently impossible locally.

**F3 — Upstream preprocessing is neither reproducible nor fully characterised.**
Third-party MATLAB/EEGLAB on a v1.0.5 dataset while the local BIDS declares v1.0.8; unknown ICA
component selection; 5 recordings resampled with unrecorded anti-alias settings; two operator
trees mixed in one folder. **The across-epoch variability family (`J`) is the feature most
exposed to this**, because it is exactly what unspecified artefact rejection modifies.

**F4 — The paper-reference frontal statistic does not reproduce (ρ_F = +0.10 vs ≈ +0.54).**

> **REVISED during Phase 1.5 acceptance: no longer treated as a scientific blocker.**
> It is now recorded as a **provenance limitation**. Our group-level spectral changes sit close
> to the paper's in all six ROI × statistic cells (see `paper_sample_reconciliation.md` §5),
> and the paper used its own preprocessing on **v1.0.4** (visual examination, self-run ICA)
> while we inherit third-party pruned files of **v1.0.5-era** origin. The mismatch is therefore
> most consistent with a preprocessing-plus-subsample difference affecting the correlation, not
> with a defective spectral estimator. Recorded, not chased.

CT reproduces in direction and (marginally) in significance. The cause is not identifiable from
this workspace; the leading candidate is the unreported PSD ensemble parameters. This does not
block Phase 2 — `mechanism_v1` is not the paper's feature — but it means **we do not have an
independent confirmation that our spectral extractor matches the field's convention**, and that
uncertainty should be carried forward.

**F5 — Non-blocking but must be carried:**
* One subject (`sub-11`) separates our n = 29 from the published ~28, via an unstated
  45-valid-trial rule. Reported, not applied.
* `units` rest on EEGLAB convention + BIDS sidecar; there is no calibration record. This is
  harmless for `mechanism_v1` (log-ratios are unit-free) and matters only for absolute power.
* Timing metadata (session order 11 NS→SD / 18 SD→NS; EEG-clock gap median −50 min, 24/29
  within ±90 min) is stored and **not used**. It exists for a later confound audit.

**Not blockers, explicitly:** the legacy baseline, legacy TTA, the missing
`segments.csv` episode, and the legacy channel-selection work have no bearing on this branch and
are not carried forward.

---

## G. Proposed next step

**Recommendation: freeze the Phase 2 protocol as a nested-LOSO predictive test on the frozen
six coordinates, and run it only after PI approval.** Concretely, the protocol I would propose
for review (not started):

* **Targets:** primary `Y_log_medianRT_raw`; secondary `Y_log_response_speed_raw`. Both already
  exist. No target selection based on results.
* **Predictors:** exactly the six frozen coordinates. No selection, no addition.
* **Design:** nested LOSO — outer loop over the 29 held-out subjects, inner loop over the
  remaining 28 for any hyperparameter (ridge penalty only), so that no test subject ever
  influences its own model. Assert model classes `M0…M3` explicitly (e.g. intercept-only,
  ΔM-only, ΔlogJ-only, both) so that any incremental value of instability over mean slowing is
  measured rather than assumed.
* **Required reporting:** per-subject predictions, subject-level permutation null, and effect
  sizes with CIs — **not** a headline correlation. With n = 29 the null distribution must be
  shown, not assumed.
* **Confound audit before modelling:** regress each coordinate on `SessionOrder`, EEG clock gap
  and epoch-count difference; report. These variables stay out of the predictor set.

**Two cheaper alternatives I would also accept, and which I think are worth considering first:**

1. **Baseline-duration study (proposed in `SCIENTIFIC_SPEC.md` §3.1).** Recompute the six
   coordinates using only the first *k* epochs (k = 8, 16, 32, full) and report how ΔM/ΔlogJ and
   their reliability degrade. This directly tests the "short time + personal baseline" premise
   the whole branch rests on, is deterministic, needs no model, and is **the cheapest experiment
   that could falsify the operating assumption**.
2. **Split-half reliability of the six coordinates** within each session. If a coordinate has
   poor within-session reliability at ~70 epochs, no amount of modelling will make it a usable
   product feature — and this is knowable in minutes.

I recommend (1) and (2) **before** any Ridge, because they determine whether a predictive
result would even be interpretable. I will not begin either until told to.

---

## Explicit non-claims

Phase 1 does **not** claim: a new fatigue biomarker; accident-risk prediction; real-time fatigue
detection; that theta instability causes performance decline; superiority over any baseline or
SOTA; deployment readiness; or that the paper-reference reproduction succeeded.

What it does claim, and can back with artifacts: the eyes-open data entry point is established
and auditable; the PVT targets are rebuilt and reconciled, with the published-N discrepancy
localised to a single subject and an unstated filter; the reference feature broadly behaves like
the published one in CT/PO but not F; the six-dimensional mechanism representation is generated
under frozen mathematics with 16/16 property tests and 25/25 independent verification checks;
and the data is of sufficient quality to attempt a formal prediction experiment.
