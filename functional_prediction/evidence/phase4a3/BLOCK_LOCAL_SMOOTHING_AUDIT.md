# BLOCK_LOCAL_SMOOTHING_AUDIT.md — edge handling for the 90 s historical filter

**Phase 4A3:** `SRTP-PHASE4A3-20260920-GAP-CORRECTED-BASELINE`

---

## 1. The order of operations, and why the obvious order is forbidden

Required structure (`raw → block segmentation → block-local processing → block-local
smoothing`), implemented literally in `src/p4a3_common.py`:

```python
def block_local_mean(x, bounds, half):
    out = np.full(x.size, np.nan)                      # NOT np.empty: off-block rows are NaN
    csum = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
    for s, e in bounds:
        s2, e2 = max(s, 0), min(e, n)
        idx = np.arange(s2, e2)
        lo = np.clip(idx - half, s2, e2)               # clamped to THIS block, both ends
        hi = np.clip(idx + half + 1, s2, e2)
        out[s2:e2] = (csum[hi] - csum[lo]) / np.maximum(hi - lo, 1)
    return out
```

The forbidden order — whole recording → 90 s smoothing → remove gaps — is exactly the order
the shipped cache used, and it is the defect: it produced values in the gaps that no window of
the signal supports, and left them inside every training mask.

## 2. Edge handling, stated exactly

| question | answer | how it is guaranteed |
|---|---|---|
| does block 1's tail read the gap after it? | **No** | `hi = min(idx+half+1, e2)` and `e2` is block 1's stop |
| does block 2's head read the gap before it? | **No** | `lo = max(idx-half, s2)` and `s2` is block 2's start |
| does block *b* read block *b±1*? | **No** | the window is clamped to `[s2, e2)` for that iteration, and the blocks are disjoint |
| can a training block's smoothing read the held-out block? | **No** | each block's rows are written only from its own window; the held-out block's rows are not touched |
| is the centred 90 s window used anywhere across a boundary? | **No** | see above |
| how is the window handled at a block's own edge? | **clamped** — shrunk to the in-block part, with the divisor `hi - lo` matching the shrunk length, i.e. an ordinary mean of the samples actually used |
| is padding used? | **No.** No value from another block or from a gap is ever used as padding |

## 3. Proof obligations, and their measurements

### 3.1 The corrected in-block series is the shipped in-block series

If the corrected smoothing differed from the shipped smoothing *inside* a block, this phase
would silently be a new estimator rather than a corrected mask. Measured on all 25
participants by `01_check_clean_reconstruction.py`:

| array | within-block max abs diff, cohort worst |
|---|---|
| features (`logpsd_smoothed4`, resmoothed from `logpsd_raw`) | **2.38e-07** |
| target (`y4_smoothed`, resmoothed from `abs_ln4`) | **1.20e-07** |

Both are float32 storage precision — the caches store these arrays as `float32`, so the
agreement cannot be better than ~1e-7 relative. The corrected arrays are therefore the shipped
arrays restricted to the blocks, and **the only difference between Phase 4A and Phase 4A3 is
which rows survive.**

### 3.2 No corrected driving row depends on a gap row

Value-level check: the largest shipped gap value across the cohort is 11 909 m and the largest
shipped **in-block** value is a few metres; if any in-block row's window had reached a gap row,
its value would be visibly inflated. It is not — every in-block value is reproduced by a window
that stays in its block (§3.1).

### 3.3 The interpolation step is global, and that is correct

One honest caveat: the 90 s mean filter is block-local, but the PSD-epoch → 4 Hz
interpolation that precedes it is a **global** `np.interp` over the epoch knot sequence by
construction, so a knot from just outside a block can influence an interpolated sample just
inside it. This is not contamination: the knots are measurements, the corrected blocks are
built from the same knots the shipped blocks were, and §3.1 shows the resulting in-block values
reproduce exactly. It is recorded so that "block-local" is not over-claimed to mean "no
global operation anywhere in the chain".

## 4. Consequences carried forward

1. **The target is unchanged as a definition.** `mean |LN|`, metres, 90 s block-local mean,
   4 Hz grid — identical to `BEHAVIOR_ENDPOINT_SPEC.md` and to Phase 4A. What changed is which
   rows are eligible, and those rows were never part of any protocol block.
2. **The 90 s centred filter remains non-causal** (it uses future samples). It is admissible
   only as historical reproduction, is applied block-locally, and every output carries:

   > historical non-causal smoothing; not deployment-compatible.

3. **No hyperparameter was chosen here.** The window length (90 s), the block rule (>90 s tile
   gap), the grid (4 Hz) and the clamp rule are all inherited frozen values.
