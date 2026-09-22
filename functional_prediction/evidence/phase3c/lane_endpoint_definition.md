# lane_endpoint_definition.md

**Phase 3C deliverable.** The lane-control endpoint family: what it is, why its centre is where
it is, what it measures, and what it does **not** claim. Normative version:
[`BEHAVIOR_ENDPOINT_SPEC.md`](../../BEHAVIOR_ENDPOINT_SPEC.md) §3. This file is the working
definition with the evidence attached.

Artifacts: `audit/phase3c/outputs/lane_geometry.json`, `lane_measurement_qc.csv`,
`event_alignment.json`, `block_structure.json`, `lane_window_metrics.csv`,
`lane_window_metrics_nested.json`, `uncertainty.json`. Code: `10_lane_geometry.py`,
`11_event_alignment.py`, `12_block_structure.py`, `20_window_metrics.py`, `21_uncertainty.py`.

---

## 1. The endpoint

$$
L(t) = \bigl|LN(t)\bigr| \quad\text{[metres]}, \qquad
Y_{i,w} = \operatorname{mean}_{t \in w} L(t)
$$

`LN` is documented verbatim as *"Lane deviation from center line in meters."*
(`*_channels.tsv`, `description` column, both datasets). The task documentation says the subject
was *"instructed to execute corrective steering actions to return the vehicle to the center of
the lane"*, and that lateral perturbing forces *"push the vehicle out of the center of the
lane"*. `mean |LN|` is therefore the direct behavioural read-out of "how far from the lane
centre, on average", which is the release's own statement of the task objective and the
historical BCIT endpoint family.

**`|LN|`, not `LN`, because** the *sign convention* — which side of the centre is positive — is
not documented anywhere in the release, and it is not needed: the endpoint is sign-free.

---

## 2. Is `LN = 0` really the lane centre? (asked, answered, not assumed)

This is the question the brief §15 makes load-bearing. `LN` being *called* a deviation does not
establish that its zero is the centre. The release supplies an independent vocabulary with which
to test it: three lane-position events.

| code | label (verbatim) |
|---|---|
| `4210` | "Vehicle moves into the defined lane of travel from either the left or right side of the lane" |
| `4220` | "Vehicle moves right of the defined lane of travel" |
| `4230` | "Vehicle moves left of the defined lane of travel" |
| `4200` | "Lane position cannot be measured." |

If `LN` were an uncalibrated lane *position*, the "right of lane" and "left of lane" events would
not respect `LN = 0`, and they would not be symmetric about it. Measured, over the four Phase 3C
recordings (valid window only):

| recording | `LN` at `4220` median | frac `LN>0` | `LN` at `4230` median | frac `LN<0` | `LN` at `4210` median |
|---|---|---|---|---|---|
| `1001` calib | +0.9172 | **1.000** (n=12) | −0.9175 | **1.000** (n=8) | +0.9070 |
| `1001` baseline | +0.9171 | **1.000** (n=24) | −0.9166 | **1.000** (n=92) | −0.9123 |
| `3101` calib | +0.9194 | **1.000** (n=4) | −0.9181 | **1.000** (n=14) | −0.9130 |
| `3101` baseline | +0.9184 | **1.000** (n=5) | −0.9173 | **1.000** (n=97) | −0.9132 |

**Findings.**

1. Every `4220` occurs where `LN > 0`; every `4230` where `LN < 0`. **100 %, 4/4 recordings.**
   A mis-centred position channel cannot do this.
2. The boundary is sharp and **symmetric**: `|LN|` at out-of-lane events has a median of
   **0.9168-0.9181 m** across recordings — a spread of **1.4 mm** — with p05-p95 within 6 mm of
   the median in the 73-minute baselines.
3. The lane half-width is therefore **0.917 m** (full width ≈ 1.83 m), read off the data rather
   than assumed.
4. `4210` ("into the lane") events occur at `|LN| ≈ 0.907-0.913 m`, i.e. **at the boundary, on
   either side** (+0.907 for `1001` calibration, −0.912 to −0.913 for the others) — consistent
   with a crossing back through the boundary from either direction, which is exactly what the
   label says.
5. `4200` ("lane position cannot be measured") occurs **zero times** in all four recordings, so
   no interval in the sample has an undefined lane state.

**Verdict: `c(t) = 0` is the lane centre, established from the release's own event semantics
against the real vehicle signal, and the boundary is 0.917 m.** The sign convention remains
undocumented and unused.

---

## 3. Measurement quality

| property | measurement |
|---|---|
| coverage | the four recordings yield 15.4 / 71.5 / 15.4 / 71.3 min of valid window after removing the zero-pad |
| missingness | `LN` has **0 NaN and 0 inf** in every valid window; **0 exact zeros** inside the valid window in all four recordings, so the pad exclusion is exact and no legitimate zero is discarded |
| quantisation | `float32`, 1.86 M-7.14 M distinct values per recording; minimum step between distinct values at float32 epsilon; **no integer lattice**, so there is no quantisation floor to correct |
| clipping | `|LN|` max = 2.05 / 9.38 / 2.07 / 2.89 m; values beyond the 0.917 m boundary are real off-road excursions, not clipping |
| unusual values | sections with `|LN| > 5 m` exist in the `1001` baseline (max 9.38 m) — kept, reported, and not trimmed; they are the excursions `4230` marks |
| reconstruction stability | the valid window re-derived in this lane matches Phase 3B's frozen pad values to floating point (verifier H2, 4/4) |

---

## 4. Window scales (frozen)

| scale | construction | count |
|---|---|---|
| `block` | split the `3200` grid at gaps > **90 s** | 6 blocks per baseline recording, 15-16 tiles each, 9.7-10.7 min |
| `5min` | contiguous spans of **≥ 300 s**, both boundaries on `3200` onsets, overrun ≤ one tile period (≤ 340 s) | 8 complete windows per baseline recording; calibration spans 2 each |

A tail shorter than 300 s is emitted with `complete_300s = false` and excluded from primary
summaries; it is never shrunk. Verifier E1 confirms every window boundary is a documented
condition onset or a block edge; E1b confirms intra-block contiguity; E1c confirms no window
exceeds 340 s.

**Measured durations:** 20/30 windows are complete; the 10 incomplete ones are block tails of
164-281 s.

---

## 5. Within-person dynamic range

`Y = mean |LN|` per complete 5-minute window, Baseline arm:

| recording | n windows | mean | sd | range | IQR | CV |
|---|---|---|---|---|---|---|
| `1001` baseline | 8 | 0.4143 | 0.0854 | **0.2118** | 0.1367 | 0.206 |
| `3101` baseline | 8 | 0.4050 | 0.0878 | **0.2413** | 0.1420 | 0.217 |
| `1001` calibration | 2 | 0.3546 | 0.0226 | 0.0320 | 0.0160 | 0.064 |
| `3101` calibration | 2 | 0.2776 | 0.0500 | 0.0707 | 0.0354 | 0.180 |

Pooled across the 20 complete windows (all arms): REML variance decomposition
`Y = mu + u_i + e_{i,w}` gives **σ²_within = 0.00749**, **σ²_between = 0.00000**,
ρ_between = 0.000. With **2 subjects** the between component rests on **1 df** and must be read
as "no evidence of a between-subject component at this n", not as "there is none".

**This establishes that the target varies within a person. It does not establish that it
declines.** The distinction is the whole point of the brief's §4/§5 and is preserved here.

---

## 6. Uncertainty, with the dependence structure respected

The behavioural series is autocorrelated at the **perturbation-episode** scale, so the episode is
the resampling unit and the block length is fixed by a rule declared beforehand:
`L = ceil(2 × median inter-perturbation interval / 5 s)` → **6-7 episodes**. An iid bootstrap is
run alongside as a **negative control on the method**.

| recording | episodes | block | mean `\|LN\|` | moving-block CI95 | iid CI95 | width ratio (iid/MB) | ACF lag-1 |
|---|---|---|---|---|---|---|---|
| `1001` calib | 57 | 7 | 0.3405 | [0.3089, 0.3775] | [0.3065, 0.3777] | 0.999 | 0.014 |
| `1001` baseline | 240 | 6 | 0.4240 | [0.3860, 0.4635] | [0.3950, 0.4573] | 0.799 | **0.111** |
| `3101` calib | 80 | 5 | 0.3622 | [0.2838, 0.4297] | [0.3203, 0.4026] | **0.552** | **0.643** |
| `3101` baseline | 315 | 5 | 0.4108 | [0.3857, 0.4370] | [0.3947, 0.4276] | **0.632** | **0.440** |

**The negative control matters.** Where the series is autocorrelated — `3101` especially,
lag-1 ρ = 0.64 — the iid interval is **45 % too narrow**. The correction was not cosmetic; an
uncorrected interval would have overstated precision on the very quantity this phase is asked to
establish. Interval half-widths are 0.016-0.079 m against a within-person range of 0.21-0.24 m,
so the range is several times the uncertainty.

---

## 7. What the endpoint actually does over time (descriptive, not a fatigue claim)

**There is no reliable time-on-task effect in this sample, on either time scale, and that is
reported as the result rather than rescued.**

The release documents a **~40 s condition cycle** (`3200` at a median spacing of 38.5-40.2 s in
all four recordings), so `3200` is not an occasional event: it is a grid. Within it, two
interpretations of "local time" were measured, both pre-declared:

| quantity | `1001` calib | `1001` base | `3101` calib | `3101` base |
|---|---|---|---|---|
| within-tile `\|LN\|` slope over the first 30 s (m/s), mean | −0.00071 | +0.00121 | +0.00260 | −0.00056 |
| fraction of tiles with a positive slope | 0.52 | 0.45 | 0.61 | 0.48 |
| second half − first half of the episode series (moving-block CI95) | −0.060 [−0.071, +0.070] | +0.108 [−0.080, +0.085] | +0.271 [−0.156, +0.151] | +0.068 [−0.053, +0.051] |
| mean `\|LN\|` first half vs second half of 10 chunks | 0.373 → 0.310 | 0.366 → 0.426 | 0.238 → 0.500 | 0.356 → 0.458 |

Every second-half-minus-first-half interval contains zero. Individual recordings drift in
opposite directions. **No monotone global degradation, and no uniform within-block drift,
is present at this n.**

Per the brief's §5 correction, this is *not* by itself a failure of the endpoint: the endpoint's
job is to have measurable within-person variation, which it does. Whether that variation is
*systematically* time-related is a separate question that 2 participants cannot settle.

---

## 8. Naive versus condition-aware decomposition

The brief §24's key diagnostic, run as specified (fixed effects, explicit subject dummies, so
R² is a real proportion of variance explained):

| model | R² | `T_session` coefficient | se |
|---|---|---|---|
| `Y ~ T_session + subject` | 0.3407 | **+0.0877 m/h** | 0.0582 |
| `Y ~ T_session + segment + block + subject` | 0.3471 | +0.2623 m/h | 0.5101 |

* F-test naive vs condition-aware: **F = 0.065, df (2, 13), p = 0.938** — the condition-aware
  terms add nothing.
* Per-recording descriptive slopes: `1001` **+0.108 m/h**, `3101` **+0.064 m/h**.

**Direction of the finding.** The brief anticipated a case where an apparent *fatigue trend*
dissolves once condition structure is modelled. Here the naive effect is already
indistinguishable from zero (0.088 ± 0.058 m/h), so there is no apparent time effect for the
condition-aware model to remove. **The condition structure is nonetheless confirmed and
material**: the `3200` grid is a 40 s periodicity present in every recording, and the
naive-versus-condition-aware comparison is constructible — so the requirement to separate the
two is satisfiable rather than blocked.

### 8.1 The perturbation-rate factor is NOT recoverable behaviourally

The 2×2 condition design's second factor is *perturbation rate*. Measured per block:

| recording | perturbation rate per block (per min) | max/min |
|---|---|---|
| `1001` baseline | 3.74, 3.75, 3.83, 3.71, 4.02, 3.80 | **1.08×** |
| `3101` baseline | 4.97, 5.15, 4.55, 4.77, 5.37, 5.37 | **1.18×** |

A two-level rate factor would show a several-fold contrast. It does not. **Therefore the
per-tile condition labels cannot be recovered from the behaviour, a condition-label model is
not fitted, and no label was invented.** The observable cycle (`segment`) and the block are used
instead. This is a documentation limit, recorded not worked around.

---

## 9. The offset caveat, and why it matters

| recording | mean `LN` | frac `LN>0` | \|LN\| p50 | p90 |
|---|---|---|---|---|
| `1001` calib | −0.0147 | 0.465 | 0.266 | 0.703 |
| `1001` baseline | −0.2194 | 0.275 | 0.305 | 0.799 |
| `3101` calib | −0.2160 | 0.278 | 0.298 | 0.764 |
| `3101` baseline | −0.3678 | 0.115 | 0.373 | 0.713 |

The vehicle sits left of centre most of the time, far more so in the Baseline arm than in
Calibration, and the offset grows across three of the four recordings. Consequences:

1. **`mean |LN|` and `sd(LN)` are not the same quantity here.** `mean |LN|` mixes the offset
   with dispersion; `sd(LN)` isolates dispersion. Both are reported; the offset travels with the
   endpoint in every table.
2. It is **not** a fixed simulator bias — a constant bias would appear identically in
   Calibration and Baseline.
3. It is **partly perturbation-driven**: in the Baseline arm the offset is already present in
   the first 5 s after a perturbation (mean `LN` = −0.241 for `1001`, −0.385 for `3101`) and
   persists into the settled 5-20 s portion (−0.245, −0.366).
4. It is **partly asymmetric response**: `4220` (right) fires 5-24 times while `4230` (left)
   fires 92-97 times in the baselines, a 4-19× left dominance, while left/right perturbations
   are nearly balanced (47.5-49.8 % left).

Whether the offset is a fatigue-relevant phenomenon, a strategy difference, or a simulator
property is **not settled by 2 participants** and is stated as open.

---

## 10. Eligibility

**Family A — lane control: ELIGIBLE.** E1-E6 all PASS
(`audit/phase3c/outputs/endpoint_eligibility.json`).

| criterion | verdict | basis |
|---|---|---|
| E1 semantic validity | PASS | `LN` documented as deviation from centre; centre measured at `LN=0`; boundary 0.917 m symmetric |
| E2 measurement validity | PASS | no NaN/inf, no lattice, no clipping artefact, stable re-derivation, pad excluded exactly |
| E3 temporal linkage | PASS | one clock, `sample = onset × srate`, per-sample simulator clock, valid window identified to the sample |
| E4 within-person dynamic range | PASS | 5-min window range 0.21-0.24 m, 4-5× the pre-declared 0.05 m threshold; CV 0.21 |
| E5 confound separability | PASS | documented cycle, block effect and session time all expressible; naive vs condition-aware constructible |
| E6 cohort coverage | PASS (metadata) | Cohort A = **109**, Cohort B = **107**; validated behaviourally on 2 participants |

Caveats carried forward with the eligibility: the offset (§9), the `n = 2` behavioural
validation (§5, §7), and the fact that E6 is a **metadata** count, not a behavioural one.
