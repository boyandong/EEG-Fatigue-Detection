# Paper sample reconciliation

Purpose: reconcile `paper 71 → 64 valid paired EEG → 28 paired EEG+PVT` with our
`71 → 68 paired EEG → 29 raw EEG+PVT`, and determine whether the one-subject gap can be
explained.

Status: **cannot be exactly reconstructed from published participant identifiers.**
A concrete, testable candidate mechanism is identified below, but it is **not** adopted.

---

## 1. What the source paper actually states

Read from the published article: Xiang, Fan, Bai, Lv & Lei, *A resting-state EEG dataset for
sleep deprivation*, **Sci Data 11, 427 (2024)**, doi:10.1038/s41597-024-03268-2
([PMC11043390](https://pmc.ncbi.nlm.nih.gov/articles/PMC11043390/); dataset version
`10.18112/openneuro.ds004902.v1.0.4`).

| statement in the paper | text |
|---|---|
| total sample | "A total of 71 participants were involved in our study." |
| eyes-open recordings released | "The final shared resting-state EEG data comprises 71 participants with eyes open and 38 participants with eyes closed." |
| eyes-closed | "a small group of participants (n = 38) also underwent an additional five minutes of closed-eye state testing" |
| recording length | "The recording duration was standardized to 5 minutes." |
| **preprocessing of the released data** | "**Notably, no preprocessing was applied to any of the uploaded data.**" |
| PVT analysis n | "t(29) = −7.31, p < 0.001" and "t(29) = −4.72, p < 0.001" → **df = 29, i.e. n = 30 sessions pairs** |
| PANAS analysis n | "t(67) = −7.89" → n = 68 |
| SSS n | "t(34)" → n = 35; KSS "t(32)" → n = 33; ATQ "t(24)" → n = 25; SAI "t(30)" → n = 31 |
| trait scale n | "n(EQ) = 56, n(BPAQ) = 55, n(PSQI) = 66" |
| time-of-day alignment | "the number of participants with a difference within the time of day between NS and SD of less than 1.5 hours was 58, accounting for 81.59% of the total" (58/0.8159 = 71.1 → the 71 cohort) |

### 1.1 What the paper does **not** state

* **No per-subject inclusion/exclusion list** for any analysis — not for PVT, not for EEG.
* No table of which of the 71 participants were dropped, or why.
* No per-subject artifact-rejection counts.
* **No explicit "64" figure appears in the article text.** The nearest published numbers are
  the analysis-specific n's in the table above.
* The code availability statement says only that spectral-analysis and topography code was
  uploaded with the dataset; there is no published exclusion script.

### 1.2 Preprocessing the paper describes (for its own Fig. 4–5 analysis)

"This dataset's EEG power spectrum" section: MATLAB R2021b + EEGLAB 2021;
bandpass 0.2–45 Hz; visual examination; **"the 5-minute EEG data was segmented to 75 epochs
with 4 seconds"**; **"epochs containing notable artifacts were eliminated, with an average
artifact epoch range of 1.46 (2.02) across all participants"**; mean bad electrodes 2.39%
(interpolated); ICA for muscle/ocular artifacts; re-reference to average.

So the paper's published analysis used a **self-run pipeline on the raw 5-minute eyes-open
recording with 75 4-second epochs**, i.e. ~300 s, with an average of only ~1.5 epochs rejected.

---

## 2. Our pipeline

| step | n | rule |
|---|---|---|
| participants in `participants.tsv` | 71 | — |
| readable EEG files locally | 142 | third-party preprocessed `.set`/`.fdt` |
| admitted eyes-open 500 Hz | 139 | `srate == 500`, eyes-open provenance, 61 ch |
| excluded | 3 | `sub-39/43/44_ses-2` declare **5000 Hz** |
| **both sessions admitted** | **68** | the only inclusion rule applied |
| official PVT paired | 30 | `participants.tsv` has both sessions |
| **raw-trial PVT paired** | **29** | `sub-05` has no raw NS trial file |

Our rule is deliberately minimal: no artifact threshold, no bad-channel threshold, no
"valid paired EEG" judgement beyond file-level admissibility. **The third-party preprocessing
already removed epochs via unspecified ICA pruning**, and we inherit that rather than adding
thresholds of our own.

---

## 3. Candidate mechanism for the one-subject gap

Full detail: `outputs/stability_v1/eeg_quality_200uV.csv` (per-session, all 136 sessions).

We computed, for every epoch of every session, the maximum absolute amplitude across all 61
channels, and the fraction of epochs exceeding 200 µV.

| fact | value |
|---|---|
| sessions with **zero** epochs above 200 µV | 86 / 136 |
| median fraction of epochs above 200 µV | 0.000 |
| 90th percentile of that fraction | 0.133 |
| maximum | 0.932 (`sub-35_ses-1`) |

Worst-quality sessions overall (candidate paper EEG exclusions):

| subject | worst-session fraction of epochs > 200 µV | in our 29? |
|---|---|---|
| sub-35 | 0.932 | no |
| sub-67 | 0.905 | no |
| **sub-32** | **0.563** | **yes** |
| sub-02 | 0.543 | yes |
| sub-28 | 0.500 | no |
| sub-37 | 0.369 | no |
| sub-54 | 0.310 | no |
| sub-29 | 0.264 | yes |

**The single worst-quality subject among our 29 is `sub-32`.** Dropping it gives exactly 28.

This is a **mechanistically plausible** explanation for the one-subject gap: a 200 µV epoch
rejection rule, applied by the authors to raw data, would flag `sub-32` hardest among the
subjects who also have PVT.

### 3.1 Why we do not adopt it

1. **It is not verifiable.** The paper publishes no per-subject artifact counts, so we cannot
   confirm that `sub-32` is one of the subjects they excluded rather than, say, `sub-02`.
2. **The candidate is not unique.** A threshold of >0.25 also selects 3 subjects; >0.20
   selects 4; >0.15 selects 5. Only the "drop exactly one" framing singles out `sub-32`.
3. **It selects on the outcome-adjacent variable.** Choosing the subject to drop because the
   count then matches a published N is precisely the kind of researcher degree of freedom the
   programme is trying to eliminate.
4. **Our cohort is defined differently by construction.** Our 68 comes from file-level
   admissibility on third-party-pruned data; their 64 comes from their own raw pipeline. Those
   are different populations, and equating them is not justified.

> **Decision: our working cohort stays at 29 for the PVT-linked analyses.**
> `sub-32` is reported here as the leading candidate and flagged as a data-quality outlier;
> it is **not** removed.

### 3.2 Also tested and rejected

The earlier Phase 1 hypothesis — a `<45 valid PVT trials` filter, which also yields 28 by
removing `sub-11` — is **withdrawn as the leading explanation**. It remains in the Phase 1
record as an explored-but-unadopted rule only. Nothing new is explored on the PVT side.

---

## 4. Can any extra information resolve this?

| source | checked | result |
|---|---|---|
| article text | fetched in full | no exclusion list; no 64 figure |
| article tables | fetched | per-scale n's only |
| code availability statement | read | spectral/topography code only, no exclusion script |
| local BIDS tree `participants.tsv` | present and complete (71 rows) | no exclusion column |
| local `metadata_behavior/` | 218 `_eeg.json` + `_channels.tsv` | no QC or exclusion fields |

**Conclusion (required wording):**

> `paper n=28 cannot be exactly reconstructed from published participant identifiers.`

---

## 5. Does this matter for our conclusions?

No. The Phase 1 paper-reference sensitivity check showed that dropping `sub-11` from 29 → 28
moved ρ_F from +0.102 to +0.093, ρ_CT from +0.393 to +0.387, ρ_PO from +0.346 to +0.334 —
the frontal non-reproduction is not caused by the one-subject discrepancy, and no conclusion
we have drawn turns on which single subject is dropped.

Per the acceptance review, the frontal ρ mismatch is now recorded as a **provenance
limitation** (different preprocessing lineage: their raw pipeline vs our inherited third-party
pruning; their v1.0.4 vs our v1.0.5-era files), not as a blocker, because our group-level
spectral changes already sit close to theirs:

| quantity (SD − NS) | paper | ours (n = 29) |
|---|---|---|
| theta relative power F / CT / PO | 0.0114 / 0.0297 / 0.0259 | +0.0102 / +0.0273 / +0.0264 |
| theta variability F / CT / PO | 0.0177 / 0.0206 / 0.0251 | +0.0085 / +0.0179 / +0.0186 |

Direction and order of magnitude agree in all six cells; frontal is the weakest on both sides.
