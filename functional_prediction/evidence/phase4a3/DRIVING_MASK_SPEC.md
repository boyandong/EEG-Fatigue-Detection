# DRIVING_MASK_SPEC.md — the authoritative driving mask for Phase 4A3

**Phase 4A3:** `SRTP-PHASE4A3-20260920-GAP-CORRECTED-BASELINE`
**Status: FROZEN.** Produced before the first corrected fit. Not adjusted afterwards.

---

## 1. Definition

For participant *i* with frozen block intervals `B_i1 … B_in` (4 Hz grid indices) and valid
(non-zero-padded) window `[lo_i, hi_i)`:

```
driving_i(t) = 1  iff  t ∈ ⋃_b ( B_ib ∩ [lo_i, hi_i) )
gap_i(t)     = 1  iff  t ∈ [lo_i, hi_i)  and  driving_i(t) = 0
```

Only rows with `driving_i(t) = 1` may enter the **target, the training mask, the validation
mask, the smoothing window, or the evaluation set**.

## 2. Provenance of the block intervals — and what is deliberately NOT changed

`B_ib` is the **unchanged frozen block geometry** already carried in every cache
(`npz['blocks']`), itself reconstructed by the frozen rule of `BEHAVIOR_ENDPOINT_SPEC.md` §3.3:
split the `3200` condition/tile grid at gaps > 90 s. It is not re-derived, re-thresholded or
trimmed here.

That is a deliberate constraint, not an oversight. The available alternatives, and why each is
rejected:

| alternative boundary rule | why it is not used |
|---|---|
| anchor each block at its first/last `3200` onset (removing inter-tile dead time) | it is a defensible rule, but the `events.tsv` files survived for **one** recording (`3101`); applying it cohort-wide needs re-downloading 24 payloads, i.e. a PI decision about cohort-scale acquisition, and it would move the boundaries this branch is comparing against |
| trim rows by an observed `|LN|` threshold | **explicitly forbidden.** Choosing a cut from the data it is meant to clean is the researcher-degrees-of-freedom search this workspace bans |
| exclude affected folds instead of masking rows | throws away whole driving blocks to fix rows that are already outside the frozen geometry; strictly worse |

A recorded consequence: the frozen boundaries absorb roughly 25–30 s of inter-tile dead time
per block (measured on `3101`: each block's last `3200` onset sits ~25–27 s before the block's
frozen end, and the tile period is ~39.6 s). Those rows are **kept** because the frozen
geometry keeps them. Any future tile-onset-anchored variant is a **new specification**, and the
fact that dead time remains inside the mask is written down here rather than quietly trimmed.

Legacy `3127` reconstructs **5** blocks, not 6. The mask uses the 5 it has. The fold invariant
stays `Σ_i n_valid_blocks(i)`, never `25 × 6`.

## 3. Self-consistency, checked rather than asserted

| invariant | result |
|---|---|
| `driving ∩ gap = ∅` | ✅ all participants |
| `driving ∪ gap = [lo, hi)` | ✅ all participants |
| `driving = ⋃_b B_ib` | ✅ all participants |
| every train mask ⊆ driving | ✅ all folds |
| every test mask ⊆ driving | ✅ all folds |
| train ∩ test = ∅ | ✅ all folds |

Totals: **149 valid blocks**, **149 usable outer folds** across **25 participants**.

## 4. The corrected target's own range

| statistic | value |
|---|---|
| min | 0.0945 m |
| mean | 0.3752 m |
| max | 3.3501 m |
| lane half-width (measured) | 0.9172 m |

Every value is inside the physical lane, as it must be for a 90 s mean of `|LN|` on a
vehicle that stays in a 1.834 m lane. Compare the shipped array's gap rows, which reached
11 909 m.

## 5. Per-block manifest

Full table: `driving_block_manifest.csv`. Columns: `legacy_labID`, `block_number`,
`grid_start`, `grid_stop`, `n_samples_4hz`, `duration_s`, `start_s`, `stop_s`, `source`,
`provenance`.

| participant | blocks | total driving duration (s) | mean block (s) |
|---|---|---|---|
| `3101` | 6 | 3,467.8 | 578.0 |
| `3102` | 6 | 3,435.5 | 572.6 |
| `3103` | 6 | 3,463.5 | 577.2 |
| `3104` | 6 | 3,437.2 | 572.9 |
| `3105` | 6 | 3,413.5 | 568.9 |
| `3106` | 6 | 3,453.2 | 575.5 |
| `3107` | 6 | 3,426.0 | 571.0 |
| `3108` | 6 | 3,447.2 | 574.5 |
| `3109` | 6 | 3,447.0 | 574.5 |
| `3110` | 6 | 3,442.2 | 573.7 |
| `3111` | 6 | 3,454.2 | 575.7 |
| `3112` | 6 | 3,449.8 | 575.0 |
| `3113` | 6 | 3,455.2 | 575.9 |
| `3114` | 6 | 3,436.8 | 572.8 |
| `3115` | 6 | 3,437.0 | 572.8 |
| `3116` | 6 | 3,435.8 | 572.6 |
| `3117` | 6 | 3,448.8 | 574.8 |
| `3118` | 6 | 3,454.0 | 575.7 |
| `3119` | 6 | 3,463.8 | 577.3 |
| `3120` | 6 | 3,441.5 | 573.6 |
| `3124` | 6 | 3,454.2 | 575.7 |
| `3127` | 5 | 2,869.5 | 573.9 |
| `3201` | 6 | 3,451.5 | 575.2 |
| `3202` | 6 | 3,443.5 | 573.9 |
| `3203` | 6 | 3,443.0 | 573.8 |
