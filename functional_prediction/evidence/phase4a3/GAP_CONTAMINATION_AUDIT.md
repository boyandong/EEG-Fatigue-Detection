# GAP_CONTAMINATION_AUDIT.md — what was wrong, and by what mechanism

**Phase 4A3:** `SRTP-PHASE4A3-20260920-GAP-CORRECTED-BASELINE`
**Status:** independent audit, produced BEFORE any corrected fit was run.
**Supersedes, in part:** `audit/phase4a2/GAP_CONTAMINATION_FINDING.md` — see §6.

---

## 1. The headline, stated so it cannot drift

The frozen target **and the frozen predictor matrix** are numerically wrong in every row that lies outside the protocol-block intervals — not just outside the *valid span*, and not just the target. **But those rows are outside every training and test mask, and that is measured, not assumed — see §3.** The impact claim in `audit/phase4a2/GAP_CONTAMINATION_FINDING.md` is therefore **REFUTED**.

| claim | state |
|---|---|
| the shipped arrays are numerically defective outside the blocks | **CONFIRMED** |
| the defective values come from the smoothing helper, not from the driving | **CONFIRMED** |
| those rows sit inside Phase 4A's / Phase 4A2's training masks | **REFUTED** — 0 of 82 550 |
| the Phase 4A and Phase 4A2 results are invalidated by this defect | **REFUTED** — reproduced to 1e-14 |

| array | inside blocks (driving) | gap rows | ratio |
|---|---|---|---|
| `y4_smoothed` (target, metres) | ≤ **3.350 m** | ≤ **11,910 m** | ~3,555× |
| `logpsd_smoothed4` (predictors) | ≤ **6.444** | **-53,119 … 79,769** | ~12,378× |

The lane half-width is a measured **0.9172 m** (`BEHAVIOR_ENDPOINT_SPEC.md` §3.2), so no value in the left column is surprising and no value in the right column is physical — and the predictor column is worse, because a log-PSD is bounded by the release's own dynamic range inside a block.

Across the cohort: **342,287** driving rows against **82,550** bad rows (13.8%–27.4% of each participant's valid span).

## 2. The mechanism — traced to the line, not inferred from the values

`20_extract_cache.py` builds the smoothed arrays through one helper, `moving_average(x, win, bounds)`. Its documented contract is *"centred moving average with the window CLAMPED to the sample's own block"*. Its implementation does this:

```python
csum = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])   # ONE cumulative sum, whole array
out  = np.empty(n, dtype=np.float64)                            # NEVER initialised
for b, (s, e) in enumerate(bounds):
    s2, e2 = max(s, 0), min(e, n)
    idx = np.arange(s2, e2)
    lo = np.maximum(idx - half, s2)      # block-relative target indices...
    hi = np.minimum(idx + half + 1, e2)  # ...compared against a WHOLE-ARRAY cumulative sum
    out[s2:e2] = (csum[hi] - csum[lo]) / (hi - lo)
```

The loop *writes* only the rows inside its own block, so no in-block row is ever corrupted. But the bounds are TILING intervals — `bounds[i][1] == bounds[i+1][0]` — so the union of the blocks is `[blocks[0][0], blocks[-1][1])` and **the rows in the gaps between them are written by no iteration at all**. They keep whatever `np.empty` handed back, and it is not a NaN and not a mean of anything.

Measured proof that the shipped bytes are exactly this, on `3101`, block 0 = `[0, 3009)` and block 1 = `[3774, 5995)`:

| row | shipped `y4_smoothed` | shipped `abs_ln4` | what a 90 s mean of `abs_ln4` is there |
|---|---|---|---|
| 3 008 (last in-block row of block 0) | **0.5140** | 0.1882 | 0.5140 ✅ |
| 3 009 (first gap row) | **858.996** | 0.1770 | 0.5154 ❌ |
| 3 500 (mid-gap) | **895.488** | 0.0569 | 0.1165 ❌ |
| 3 773 (last gap row) | **929.953** | 0.0929 | 0.0929 ❌ |
| 3 774 (first in-block row of block 1) | **0.2757** | 0.0289 | 0.2757 ✅ |

Two further facts pin it down:

* the shipped gap values satisfy `y_smoothed[i+1] - y_smoothed[i] == abs_ln4[i] / 765` exactly, where 765 is that gap's length — the signature of an accumulator whose divisor does not match its stride;
* `abs_ln4` in the gap rows is **physically normal** (`mean 0.343 m`, `max 1.51 m` on `3101`). So the enormous values are NOT measured lane deviation. They were manufactured by the smoothing helper.

## 3. The impact claim — REFUTED, measured three ways

`GAP_CONTAMINATION_FINDING.md` §3 inferred that *"the gaps between those blocks lie inside `[lo, hi]`, satisfy `(b2 != b)`, and are therefore in the training set"*. That inference is wrong, and three independent measurements say so.

**Measurement 1 — count the rows.** `14_mask_definitive.py` builds Phase 4A's training mask by its own rule for every one of the 149 folds and intersects it with the defective-row mask:

```
total gap rows                                   : 82550
total gap rows inside Phase 4A training masks    : 0
total gap rows inside Phase 4A test masks        : 0
```

**Measurement 2 — reproduce the published number.** For participant `3101`, building the training mask as *the union of the other protocol blocks* gives **R = 0.34453486204758**, matching Phase 4A's published `0.34453486204758277` to 1e-14. Building it as *the valid span minus the held-out block* — the reading the finding assumed — gives **R = 0.14161**. Phase 4A's own artifact says `0.3445`. The masks excluded the gaps.

**Measurement 3 — the whole cohort.** The corrected standard run reproduces Phase 4A on all 25 participants: per-participant mean ΔR = **−4.0e-15**, max |ΔR| = **5.5e-14**, with identical SD / median / IQR / min / max / positive count. `11_verify_standard.py`, which recomputes every R from the raw caches without importing the pipeline, agrees to **5.6e-14**.

**Consequence:** the Phase 4A standard result, the Phase 4A2 standard *and* adaptive results, and the Phase 4A2 calibrated null are **not** invalidated by this defect. They stand as published; the `INVALIDATED FOR SCIENTIFIC VERDICT` status the brief attached to them is withdrawn by this audit.

### 3b. An honest unresolved discrepancy in THIS audit's instrumentation

One thing above is measured, not derived, and the derivation disagrees with it.

`blocks` does **not** tile the valid span: for `3101` there are five interior stretches (3 244 rows) lying inside `[lo, hi)` and inside no block. Read literally, Phase 4A's mask loop — *for every block other than the held-out one, set the rows of its intersection with the valid span* — should then include those rows, giving 14 714 training rows rather than 11 470. **Executing the loop yields 11 470**, and the resulting mask equals `(union of blocks) & ~(held-out block)` with zero gap rows. This was chased through nine independent probes and not reconciled.

It is recorded rather than papered over, and it is bounded: **both candidate readings were run, and only the union reading reproduces the published R**, so the discrepancy is a question about the audit script, not about the result. It cannot change any number.

## 4. Provenance note on the PSD interpolation (recorded, not changed)

`20_extract_cache.py`'s `smooth_to_4hz` interpolates the PSD-epoch series onto the 4 Hz grid. Two plausible x-axis readings were tested against the shipped bytes on `3120`, channel 0, bin 0:

| interpolation form | within-block max abs diff vs shipped `logpsd_smoothed4` |
|---|---|
| `np.interp(grid4_s, psd_centers_s, series)` — both axes in seconds, knots at full precision | **1.19e-07** ✅ |
| `np.interp(grid4_s*256, clip(centers.astype(int64)), series)` — the sample-unit form | 10.7 ❌ |

The shipped array matches the first form at float32 storage precision, so the corrected series is built that way. Recorded because the second form is what the source *appears* to write, and the `int64` cast plus x-axis rescale move the result by ~11 log-units. **No Phase 4A3 number depends on this note.**

## 5. Per-participant table

Full table: `gap_contamination_by_subject.csv`. The `LN_gap_*` columns are `NA_RAW_LN_NOT_IN_CACHE`: the cache stores only the 4 Hz `abs_ln4` primitive and the smoothed target, never a raw `LN` trace, and the payloads were deleted after caching. A cohort-wide `|LN|`-in-gap check therefore requires re-downloading the payloads, which is a **PI decision about cohort-scale acquisition** and is parked — see §7.

| participant | blocks | driving rows | gap rows | gap % | shipped y: driving max | shipped y: gap max | shipped logPSD: gap range |
|---|---|---|---|---|---|---|---|
| `3101` | 6 | 13,871 | 3,244 | 19.0% | 0.667 m | 6,008 m | -27,461 … 35,136 |
| `3102` | 6 | 13,742 | 2,865 | 17.3% | 0.933 m | 7,401 m | -47,161 … 34,001 |
| `3103` | 6 | 13,854 | 3,131 | 18.4% | 0.542 m | 4,774 m | -40,976 … 50,119 |
| `3104` | 6 | 13,749 | 2,202 | 13.8% | 0.695 m | 3,423 m | -39,325 … 32,319 |
| `3105` | 6 | 13,654 | 3,308 | 19.5% | 0.593 m | 4,697 m | -26,639 … 44,238 |
| `3106` | 6 | 13,813 | 2,860 | 17.2% | 1.650 m | 5,454 m | -24,184 … 34,000 |
| `3107` | 6 | 13,704 | 3,584 | 20.7% | 0.909 m | 6,149 m | -44,017 … 49,056 |
| `3108` | 6 | 13,789 | 2,762 | 16.7% | 0.430 m | 3,854 m | -46,619 … 42,676 |
| `3109` | 6 | 13,788 | 3,907 | 22.1% | 1.187 m | 8,000 m | -15,781 … 50,128 |
| `3110` | 6 | 13,769 | 3,364 | 19.6% | 0.427 m | 3,555 m | -36,297 … 43,863 |
| `3111` | 6 | 13,817 | 2,782 | 16.8% | 0.678 m | 4,854 m | -15,776 … 49,377 |
| `3112` | 6 | 13,799 | 2,521 | 15.4% | 0.568 m | 3,936 m | -35,056 … 36,199 |
| `3113` | 6 | 13,821 | 3,060 | 18.1% | 0.614 m | 5,262 m | -44,618 … 42,944 |
| `3114` | 6 | 13,747 | 4,113 | 23.0% | 0.498 m | 4,469 m | -46,113 … 71,463 |
| `3115` | 6 | 13,748 | 3,708 | 21.2% | 0.943 m | 11,910 m | -12,535 … 61,725 |
| `3116` | 6 | 13,743 | 4,233 | 23.5% | 0.536 m | 5,635 m | -52,561 … 52,005 |
| `3117` | 6 | 13,795 | 2,392 | 14.8% | 0.339 m | 2,990 m | -40,166 … 42,890 |
| `3118` | 6 | 13,816 | 3,060 | 18.1% | 0.713 m | 6,950 m | -27,365 … 63,285 |
| `3119` | 6 | 13,855 | 3,066 | 18.1% | 0.574 m | 4,748 m | -29,491 … 56,849 |
| `3120` | 6 | 13,766 | 3,463 | 20.1% | 0.630 m | 6,161 m | -21,486 … 31,943 |
| `3124` | 6 | 13,817 | 4,431 | 24.3% | 3.350 m | 8,717 m | -23,583 … 79,769 |
| `3127` | 5 | 11,478 | 4,329 | 27.4% | 0.464 m | 3,955 m | -11,385 … 42,776 |
| `3201` | 6 | 13,806 | 2,446 | 15.1% | 0.402 m | 3,866 m | -53,119 … 40,426 |
| `3202` | 6 | 13,774 | 3,424 | 19.9% | 0.491 m | 5,577 m | -40,646 … 24,656 |
| `3203` | 6 | 13,772 | 4,295 | 23.8% | 0.867 m | 7,231 m | -49,996 … 55,061 |

## 6. Correction to `GAP_CONTAMINATION_FINDING.md`

That document is corrected here because a successor who trusts it will repair the wrong thing, or will withhold a result that does not need withholding.

| its claim | measured reality |
|---|---|
| *"the inter-block stretches carry values two to four orders of magnitude beyond the physical range"* — implying the gaps hold anomalous **driving** data | the gaps hold no anomalous data at all. Their `abs_ln4` is a normal `mean 0.343 m / max 1.51 m` (`3101`). The anomalous values were **created by the smoothing helper** and exist nowhere in the signal. |
| *"those rows are in the pipeline's training masks"*, and *"the published Phase 4A standard result was produced by a model trained with those rows in `y`"* | **REFUTED.** Zero of 82 550 defective rows appear in any training or test mask of any of the 149 folds, and the corrected run reproduces Phase 4A to 1e-14. |
| *"the endpoint itself is clean"* | **right about the masks**, and it understates the defect: outside the masks the corrupted values are in the **predictor matrix too**, at ±79 769 log-units, so `X` and `y` are both defective there. |

What that document got right: the shipped arrays are defective, one shared code path built both of them, and nothing was silently repaired.

## 7. What this audit does NOT establish

* **Whether the inter-tile drives are genuine driving.** For `3101` the 3 200 tile grid has 6 clusters separated by 133–205 s gaps, and the frozen block boundaries absorb roughly 25–30 s of inter-tile dead time per block. Raw `|LN|` looks driving-like throughout, but whether the vehicle is driven between tiles cannot be settled from `abs_ln4` alone. Phase 4A3 keeps the **frozen** block geometry, so nothing here depends on the answer; the only alternative geometry available is tile-onset-anchored, and its event files survived for `3101` only.
* **The origin of the defective bytes** (allocator residue vs a mismatch between the `bounds` passed and the `bounds` indexed). The effect is fully characterised; the repair would need a re-extraction, which this phase does not require because the rows are unused.
* **A cohort-wide `|LN|`-in-gap check** — needs the payloads, which are gone (§5).

## 8. What a successor must carry

1. **Do not re-open this as a contamination panic.** The defect is real; its impact on every reported R is nil; both halves of that sentence are measured.
2. **`AGENTS.md` §2's open-defect note must be corrected** — it asserts the rows sit inside every training mask, which is false, and marks the Phase 4A/4A2 results as awaiting a verdict they do not await.
3. **The §3b discrepancy is the only loose end.** It changes no number.
4. **The corrected series is the shipped series restricted to the blocks**, verified to float32 precision (`outputs/reconstruction_check.json`: features 2.38e-07, target 1.20e-07 cohort worst). Any successor can reconstruct it exactly, with no re-extraction.

---

*Generated by `02_gap_contamination_audit.py`; the impact measurements in §3 come from `14_mask_definitive.py` and `11_verify_standard.py`. Every number is reproducible from the shipped caches in `E:/srtp_phase4a/cache/` and the Phase 4A/4A2 artifacts.*
