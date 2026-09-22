# TARGET_STREAM_PROVENANCE.md

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Status:** FROZEN before any adaptation run. This file defines the stream; nothing in it may
be adjusted after seeing a trajectory (prompt §10, §12, §15, §19).

---

## 1. Why this file exists

TENT is an online, sequential method. Feeding it a shuffled window set is not a TTA
experiment, it is a different experiment with the same name. So the stream geometry is a
*protocol* artefact and has to be frozen, justified and auditable before anything adapts.

---

## 2. What is recoverable and what is not

| property | status | evidence |
|---|---|---|
| windows that belong to a recording | **RECOVERABLE** | `segments.csv`: `subject`, `session`, `source_file` |
| window order **inside** a recording | **RECOVERABLE** | `source_epoch_index`, strictly ascending in file order, `array_index == 0..n-1` |
| window → 4 s block inside an epoch | **RECOVERABLE** | `start_sample_in_epoch = 0`, `stop_sample_exclusive = 2000` for all 9390 rows |
| one window per retained epoch | **RECOVERABLE** | 9390 windows over 136 recordings, each retained epoch used once |
| **cross-visit order** | **RECOVERABLE** | `participants.tsv:SessionOrder` — see §3 (corrected) |
| absolute clock time of a window | **NOT RECOVERABLE** | the preprocessed `.set` files are epoched derivatives; epochs carry no timestamps (`tmin = 0.0`, EEGLAB event grid 0/2000/4000/…) |
| the wall-clock gap between the two visits | **KNOWN ONLY IN RANGE** | documented as 7 days – 1 month (Sci Data 11:427); not recoverable per subject, and not needed |

### 2.1 Skipped epochs

Of 136 recordings, 6 have missing epoch indices — `sub-28/ses-2`, `sub-32/ses-2`,
`sub-37/ses-2`, `sub-50/ses-2`, `sub-54/ses-1`, `sub-63/ses-1` — all excluded by the frozen
amplitude / peak-to-peak QC rule. The gap structure is **not** tail-only:

| recording | retained | epoch range | skipped | interior skips |
|---|---:|---|---:|---|
| `sub-28/ses-2` | 57 | 0..57 | 1 | **1** (epoch 39) |
| `sub-32/ses-2` | 65 | 0..70 | 6 | 0 (all tail) |
| `sub-37/ses-2` | 51 | 0..64 | 14 | 0 (all tail) |
| `sub-50/ses-2` | 71 | 0..71 | 1 | 0 (tail) |
| `sub-54/ses-1` | 64 | 0..70 | 7 | 0 (all tail) |
| `sub-63/ses-1` | 67 | 0..67 | 1 | 0 (tail) |

*(Correction, recorded because it changed a load-bearing statement: an earlier draft claimed
all six were tail-only. That was wrong — measured per-recording, `sub-28/ses-2` skips epoch 39
in the interior. The corrected rule is below. `legacy_subject_inventory.csv` carries
`ses1/ses2_missing_epochs_interior` and `_tail` per subject so this is auditable.)*

**What the gap does and does not break.** The guarantee the stream needs is **strict
chronological order**, supplied by `source_epoch_index` — *not* contiguity of that index. A
skipped epoch is a **missing window in its right place**: the stream continues from epoch 38
to epoch 40 in the correct order. There is therefore no reordering and no need to re-key the
stream. What is *not* available is the 4 s of signal that epoch 39 would have contributed,
and the 4 s wall-clock gap between the end of epoch 38 and the start of epoch 40 is not
representable — the preprocessed epochs carry no absolute timestamps.

Consequences, stated precisely instead of being papered over:

* the window stream is a **temporally ordered subsequence** of each recording, not a
  gapless resampling of it;
* `stream_position` is the position in that subsequence; it is **not** a wall-clock index;
* the only situation this could mislead is a claim of the form "the model saw the whole
  recording contiguously", which Phase 1 does not make;
* because the excluded epochs were rejected for excessive amplitude, the surviving windows
  are the *cleaner* ones — a mild selection that is inherited unchanged from the frozen
  legacy manifest and applies identically to all three arms.

`build_stream` asserts strictly ascending **and unique** epoch indices per recording, and
refuses to silently fall back to array order (which would be wrong precisely when an interior
epoch is dropped). Enforced by NC8.

---

## 3. Cross-visit chronology — CORRECTED

> **This section replaces an earlier, wrong conclusion.** An earlier draft of this document
> argued that "true cross-session chronology is not identifiable" because the `SessionOrder`
> label and the time-of-day columns disagree for 39/71 participants. That reasoning treated
> the clock columns as a competing chronology signal. They are not one. The conclusion below
> is the corrected one, and the correction is recorded rather than quietly rewritten.

### 3.1 What the authoritative documentation says

Three independent sources, all inspected directly:

1. **Dataset README** (`data/ds004902/metadata_behavior/README`, mirrored verbatim at
   `nemarDatasets/on004902` `v1.0.0`):

   > "The dataset provides resting-state EEG data … from 71 participants who underwent two
   > experiments involving normal sleep (NS—session1) and sleep deprivation (SD—session2). …
   > **(Please note here Session 1 (NS) and Session 2 (SD) is not the time order, the time
   > order is counterbalanced across participants and is listed in metadata.)**"

2. **`participants.json`** documents the column that *is* the time order:

   > `SessionOrder` — *"Participant session order label"*, levels
   > `NS->SD` = *"First normal sleep session, then sleep deprivation session"*,
   > `SD->NS` = *"First sleep deprivation session, then normal sleep session"*.

3. **The dataset paper** (Xiang, Fan, Bai, Lv, Lei, *A resting-state EEG dataset for sleep
   deprivation*, **Sci Data 11:427, 2024**, doi:10.1038/s41597-024-03268-2), Methods →
   Overall design:

   > *"The NS and SD conditions are counterbalanced across participants to eliminate sequence
   > effects. … There was a **minimum of a 7-day and a maximum of a one-month interval**
   > between SD and NS conditions."*

   and, decisively for the clock columns:

   > *"The two sessions are ideally aligned within a fixed timeframe in the morning or in the
   > afternoon for each subject. Specifically, **the number of participants with a difference
   > within the time of day between NS and SD of less than 1.5 hours was 58, accounting for
   > 81.59 % of the total.**"*

### 3.2 Why the clock columns cannot contradict `SessionOrder`

The visits are separated by **7 days to 1 month**, and the design **deliberately matched the
time of day** across the two visits (81.6 % within 1.5 h). The clock columns therefore record
a *time of day* that was engineered to be ~the same on both visits, with **no date column**
anywhere in the release.

A near-equal time-of-day pair carries **no ordering information** — and where it appears to
"disagree" with `SessionOrder`, the disagreement is an artefact of reading a cyclic clock as
if it were a timeline (12-h-wrap ambiguity: e.g. `sub-05` NS `20:37` vs SD `9:09`). The
measured 39/71 disagreement rate is direct evidence of non-informativeness, **not** evidence
against the declared order.

`SessionOrder` is the release's own explicit record of visit order, published precisely
because `ses-1`/`ses-2` are condition identifiers. It is therefore the authoritative source,
and the pipeline uses it.

*(Verifier checks `E2a`–`E2f` assert: every formal subject has an authoritative `SessionOrder`;
the distribution is genuinely counterbalanced; every subject's stream follows its own
`SessionOrder`; the clock columns are numerically demonstrably non-informative; no clock
column is read by the adaptation path or by `build_stream`.)*

### 3.3 What the stream is, and what it is not

* The stream **is** a **participant-level two-visit blocked stream**: visit 1 in full, then
  visit 2 in full, where "visit 1" is that participant's own first visit per `SessionOrder`.
* The stream is **NOT** a continuous real-world stream. The two visits are separated by
  7 days – 1 month, with an entire intervening sleep-wake cycle (the SD visit includes a
  ≥ 24–30 h deprivation period). Any statement of the form "the model saw the participant
  continuously" is false by construction.
* `NS_then_SD` and `SD_then_NS` are **PARKED** as future order diagnostics and are **not run**
  in the primary collapse-existence experiment. `build_stream` raises if they are requested,
  and the orchestrator refuses them at the CLI.

### 3.4 The visit-order distribution over the 68 formal subjects

| `SessionOrder` | n subjects |
|---|---:|
| `NS->SD` (normal sleep first) | 39 |
| `SD->NS` (sleep deprivation first) | 29 |

All 68 subjects have a valid, unambiguous value — no subject is dropped, imputed or guessed.
Three further participants (`sub-39`, `sub-43`, `sub-44`) were already excluded upstream by
the frozen 500 Hz QC rule, before Phase 1, and are unaffected by this document.

---

## 4. The frozen stream

### 4.1 Within a recording

Windows are consumed in ascending `source_epoch_index`. No shuffle of any kind. This is the
PRIMARY RULE and it is enforced by NC7 (not a hash/random permutation) and NC8 (strictly
ascending, unique).

### 4.2 The episode

One episode = one held-out **subject**. Episode start:

1. load that fold's frozen source checkpoint `eegnet/<subject>/seed_<s>/best.pt`;
2. reset parameters, BatchNorm state and optimizer state to the checkpoint;
3. stream the subject's two visits in that subject's **`SessionOrder`** sequence.

Episode end: discard the adapted model entirely. The next subject starts again from step 1.
Adaptation **never** crosses a subject boundary; state is not shared, cached or carried.
Enforced by NC3.

### 4.3 Batch construction — and why batches never cross a visit boundary

Batches are cut **within a visit only**: each visit is chunked into consecutive groups of
`batch_size = 32` in stream order, and a visit's trailing incomplete batch **keeps its actual
size**. It is never padded from the other visit, never dropped, and never merged.

So a subject with 73 windows in visit 1 and 70 in visit 2 gets
`[32, 32, 9]` then `[32, 32, 6]` — 5 batches, sizes `32, 32, 9, 32, 32, 6` in stream order.

Rationale (a real design decision, recorded):

* per-batch BatchNorm statistics are estimated from a test batch; splicing the visit boundary
  into one batch would create a *mixed-condition* statistic corresponding to no real
  deployment situation, and would confound the normalization-stability question directly;
* it keeps visit boundaries aligned with batch boundaries, so a collapse beginning at a visit
  transition is not an artefact of one contaminated batch;
* it is deterministic: batch boundaries depend only on (visit length, batch size).

**Small visits are kept.** `sub-04/ses-1` has 4 windows and therefore one batch of size 4.
No subject is dropped, capped, or excluded on the basis of anticipated BatchNorm instability
— that would be pre-judging the mechanism Phase 1 exists to test. Actual sizes are recorded
for every subject in `batch_size_audit.csv` and `legacy_subject_inventory.csv`
(`batch_sizes_first_visit`, `batch_sizes_second_visit`,
`final_batch_size_first_visit`, `final_batch_size_second_visit`).

Enforced by NC15. Sample set and boundaries are identical across all four arms by
construction; enforced by NC19.

### 4.4 Window counts

9390 windows total; per subject between 4 (`sub-04/ses-1`) and 79 (`sub-52/ses-2`) — see
`legacy_subject_inventory.csv`.

---

## 5. Label discipline

`y = 0` for `ses-1` (normal sleep), `y = 1` for `ses-2` (sleep deprivation).

**No label, class proportion, condition identity or future information reaches any
adaptation step.** The only tensor that enters the model is `X_t`, the normalized window
batch. Labels are attached to the record *after* the adaptation region of `run_arm`
(see the sentinel comments in `src/p1_arms.py`), and are used exclusively by the post-hoc
evaluator. Enforced by NC1 (no `label`/`y_true` token inside the adaptation region) and NC13
(session identity is never a model input).

The pre-declared block order is *metadata used to order the stream*. It is a known property
of the design, not a label read at test time: the ordering is fixed at episode construction
from the frozen order constant, identical for every subject and every seed, and it does not
depend on any label value. Per-window `y_true` never influences order.

---

## 6. What the stream manifest contains

`target_stream_manifest.csv` — one row per (subject, window), 9390 rows:

| column | meaning |
|---|---|
| `session_block_order` | always `metadata_order` (the primary stream) |
| `visit_pair` | that subject's authoritative order, e.g. `ses-2->ses-1` |
| `subject`, `session`, `label` | from the frozen manifest |
| `segment_id` | frozen legacy id |
| `source_epoch_index` | epoch number inside the `.set` file (temporal order key) |
| `visit_index` | 0 = first visit, 1 = second visit |
| `stream_position` | global position within the subject's episode |
| `batch_index` | which batch this window falls in |
| `batch_n` | the size of that batch |
| `is_final_batch_of_block` | true when this batch is its visit's trailing batch |
| `batch_offset` | position inside the batch |
| `within_block_position` | position inside the recording |
| `block_span` | that visit's window count |
| `waveform_file`, `array_index` | where the waveform lives |

Companion artefacts: `batch_size_audit.csv` (actual batch sizes per subject/visit, including
trailing sizes) and `legacy_subject_inventory.csv` (per subject: `SessionOrder`, `visit_pair`,
window counts, both batch-size profiles, missing-epoch counts).

---

## 7. Explicitly out of scope for Phase 1

**PARK:** the forced `NS_then_SD` / `SD_then_NS` orders as separate streams, shuffled streams,
class-balanced streams, batch-size sweeps, learning-rate sweeps, multi-step adaptation, and
continual-across-subject adaptation. These become diagnostics only if the primary protocol
establishes collapse — except that the block-order diagnostic is unlikely to be informative
now, because the primary stream already contains **both** visit directions across different
participants (39 `NS->SD`, 29 `SD->NS`), so order sensitivity is partly probed *within* the
primary design at no extra cost.
