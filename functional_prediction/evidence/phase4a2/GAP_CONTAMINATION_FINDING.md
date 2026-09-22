# GAP_CONTAMINATION_FINDING.md — the frozen target's inter-block gaps hold non-physical values

**Phase 4A2:** `SRTP-PHASE4A2-20260918-ADAPTIVE-SFFS`
**Status:** provenance finding + a documented deviation in OUR null only. **A3 is NOT silently
repaired.** This document exists so the finding cannot be lost.

---

## 1. What was measured

The frozen target is `y4_smoothed` = the block-local 90 s-smoothed `mean |LN|`, in metres, on the
4 Hz grid. Partitioning each participant's valid span into the six protocol blocks and the
**inter-block gaps** gives:

| participant | in-block `n` | in-block mean | in-block **max** | in-gap `n` | in-gap mean | in-gap **max** |
|---|---|---|---|---|---|---|
| `3101` | 13 871 | 0.419 m | **0.67 m** | 3 244 | 3 173.9 | **6 007.8** |
| `3102` | 13 742 | 0.561 m | **0.93 m** | 2 865 | 4 584.9 | **7 401.1** |
| `3203` | 13 772 | 0.481 m | **0.87 m** | 4 295 | 4 000.4 | **7 231.0** |

Every **in-block** value is physically coherent: the lane half-width is a measured **0.917 m**
(`BEHAVIOR_ENDPOINT_SPEC.md`), and no protocol block exceeds **0.93 m**.

Every **in-gap** value is non-physical: thousands of metres of lane deviation. They are not
outliers inside blocks — **zero** in-block values exceed 5 m, and **all** in-gap values do.

## 2. Is this new?

**The in-block numbers are not new** — they are exactly what Phase 4A reported
(`target_mean_abs_LN_m` = 0.4186 for `3101`, 0.5610 for `3102`; `n_test_points` 13 871 / 13 742,
reproduced to the digit this session). The endpoint itself is clean.

**What is new is the gap.** The inter-block stretches inside the valid span carry values two to four
orders of magnitude beyond the physical range, and **no earlier artifact of this project reports,
excludes or flags them**.

## 3. Why it matters

`40_standard_pipeline.run_participant` builds its training mask as, for every block *other than the
held-out one*, the intersection of that block with the valid span:

```python
for b2, (s2, e2) in enumerate(blocks):
    if b2 == b: continue
    tr[max(lo, s2):min(hi, e2)] = True
```

The gaps between those blocks lie inside `[lo, hi]`, satisfy `(b2 != b)`, and are therefore **in the
training set**. The training target `y[tr]` contains gap rows. Consequence:

* the published Phase 4A standard result was produced by a model **trained with those rows in `y`**;
* the A3 arms inherit exactly the same training rows, because A3 reuses this fold geometry and this
  target unchanged;
* so A3-vs-standard remains an **apples-to-apples** comparison — but the absolute level of every R in
  this family is affected by training on a partially non-physical target.

**This is a documented defect in the shared target, not an A3 defect, and it is not an A3 variable.**
Repairing it — masking the gaps out of training, interpolating them, or rejecting affected folds —
would change the pipeline that BOTH arms share, i.e. it would be a change to the frozen
`BEHAVIOR_ENDPOINT_SPEC.md` target. That is a `WHAT` decision, and it is **escalated, not taken**.

## 4. What was NOT done

* the frozen target is **unchanged**;
* `40_standard_pipeline.py` is **unchanged**;
* neither A3 arm was repaired, re-weighted or re-masked;
* no Phase 4A artifact was edited.

The A3 run therefore reports the honest number for the frozen pipeline, contaminated training rows
and all.

## 5. The one place it DID have to be handled: the surrogate

Support construction requires the surrogate target to be finite on every row the pipeline reads.
`blockwise_surrogate` therefore:

1. fills the whole valid span with one iAAFT surrogate of `mean |LN|` (so the inter-block stretches
   carry surrogate values with the target's own amplitude distribution and spectrum, never a NaN and
   never a fabricated constant); then
2. overwrites **each protocol block** with its own block-local iAAFT surrogate, drawn from the TRUE
   block values, so the block's own marginal distribution and spectrum are the ones matched;
3. leaves everything outside the valid span exactly as it was; those rows are never read.

**Declared deviation:** the inter-block bridge is a surrogate of the whole valid span rather than a
per-block surrogate, because the gaps are not blocks. It preserves the amplitude distribution, the
spectrum and the autocorrelation of the target, and it introduces no NaN. It is not a statement about
what the gaps "should" contain — that is the open question in §3.

Verified on legacy `3102`: surrogate finite everywhere, per-block `sd` reproduced to 4 decimals
(0.1917/0.0443/0.0573/0.0610/0.0898/0.1192), per-block lag-1 autocorrelation 0.998-0.9998, and
per-block power-spectrum correlation **0.9999**.

## 6. What would settle §3

One targeted diagnostic, not run here because it is outside A3's single scientific variable:

> trace `|LN|` through `20_extract_cache.py` for the inter-block stretches of the five cached
> recordings in hand, and determine whether the gaps contain (a) genuine post-block driving at a
> divergent scale, (b) an artefact of the resampling/smoothing path, or (c) a sidecar/vehicle-channel
> discontinuity at block boundaries.

Until that is done, **the absolute R values of the historical baseline family should be read with
this caveat attached**, and any comparison across it must continue to use the identical target.
