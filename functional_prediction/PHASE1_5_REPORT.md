# PHASE1_5_REPORT.md — Temporal Stability & Deployability Audit

Branch: `vigilance_generalization_v1`. Governed by [`SCIENTIFIC_SPEC.md`](SCIENTIFIC_SPEC.md).
Builds on [`PHASE1_REPORT.md`](PHASE1_REPORT.md).

**Question:** can Mechanism-v1 be estimated reliably enough from short EEG recordings?

\[
\Delta\mathbf m=[\Delta M_F,\Delta M_{CT},\Delta M_{PO},\Delta\log J_F,\Delta\log J_{CT},\Delta\log J_{PO}]
\]

**No PVT target was touched. No model was trained. No feature was removed.**

Vocabulary discipline (brief §3): everything below is **within-session estimator stability**
or **short-duration convergence**. This is **not** test–retest reliability — there is no
repeated session in the same state. Disagreement conflates measurement noise, finite-sample
error, and genuine within-session state drift, and Phase 1.5 cannot fully separate them
(§D quantifies how much of it is drift).

---

## A. Sample accounting

| quantity | n |
|---|---|
| paired subjects (both sessions admissible, eyes-open 500 Hz) | **68** |
| sessions | **136** |
| subjects with a PVT pair | 29 — **not used in this phase** |

Session-level, disjoint contiguous windows:

| duration | seconds | sessions | with ≥2 disjoint windows | total windows | median / session |
|---|---|---|---|---|---|
| `k4` (exploratory) | 16 | 136 | 135 | 2309 | 17 |
| `k8` | 32 | 136 | **135** | 1129 | 8 |
| `k15` | 60 | 136 | **135** | 535 | 4 |
| `k30` | 120 | 136 | **129** | 264 | 2 |
| `full` | ~228–316 | 136 | 0 (by construction) | 136 | 1 |

Paired (personal-relative) level — NS and SD must share the same duration:

| duration | subjects | with ≥2 paired windows |
|---|---|---|
| `k8` | 68 | **67** |
| `k15` | 68 | **67** |
| `k30` | 68 | **61** |

Ineligibility is always explicit, never papered over with overlap:
`outputs/stability_v1/window_inventory.csv` records `session_n_epochs` and
`n_disjoint_windows` for **every session × duration**, including zeros. The 7 ineligible
sessions at `k30` are the ones with fewer than 60 epochs; one session
(`sub-04_ses-1`, 4 epochs) is ineligible at every duration ≥ 8. Overlap was never permitted
to reach a target n.

Effective n per analysis: **Level 1** = 135 recordings × pairwise window comparisons
(129 at `k30`); **Level 2** = 67 subjects × pairwise paired-window comparisons (61 at `k30`).

---

## B. Session-feature stability (Level 1, Experiment A)

Primary metric: disjoint equal-length windows of one recording, all window pairs pooled across
recordings. Source labelled `disjoint` throughout. Reference scale for nMAE = IQR of the
full-session values (population spread).

### B.1 Mean slowing `M`

| feature | duration | ρ | median\|Δ\| | P90\|Δ\| | nMAE | ICC(2,1) |
|---|---|---|---|---|---|---|
| M_F | 32 s | **0.805** | 0.1424 | 0.4106 | 0.232 | 0.839 |
| M_F | 60 s | **0.848** | 0.1177 | 0.3475 | 0.192 | 0.902 |
| M_F | 120 s | **0.872** | 0.0986 | 0.2875 | 0.161 | 0.897 |
| M_CT | 32 s | **0.843** | 0.1291 | 0.3736 | 0.218 | 0.894 |
| M_CT | 60 s | **0.881** | 0.1070 | 0.3224 | 0.181 | 0.920 |
| M_CT | 120 s | **0.912** | 0.0851 | 0.2789 | 0.144 | 0.928 |
| M_PO | 32 s | **0.812** | 0.1492 | 0.4329 | 0.229 | 0.845 |
| M_PO | 60 s | **0.859** | 0.1167 | 0.3484 | 0.179 | 0.920 |
| M_PO | 120 s | **0.882** | 0.0895 | 0.2926 | 0.137 | 0.916 |

Full duration detail (incl. 16 s) in `outputs/stability_v1/duration_summary.csv`.

**M is already usable at 32 s.** ρ ≥ 0.81, ICC ≥ 0.84, and the window-to-window error is
~22–23 % of the population spread. Ranking subjects from 32 s of EEG is essentially as good as
ranking them from the full 4–5 min.

### B.2 Temporal instability `J`

| feature | duration | ρ | median\|Δ\| | P90\|Δ\| | nMAE | ICC(2,1) |
|---|---|---|---|---|---|---|
| J_F | 32 s | 0.374 | 0.0924 | 0.2537 | 0.495 | 0.428 |
| J_F | 60 s | 0.528 | 0.0677 | 0.1970 | 0.363 | 0.578 |
| J_F | 120 s | **0.701** | 0.0525 | 0.1550 | 0.281 | 0.735 |
| J_CT | 32 s | 0.435 | 0.0789 | 0.2173 | 0.469 | 0.408 |
| J_CT | 60 s | 0.570 | 0.0626 | 0.1759 | 0.372 | 0.566 |
| J_CT | 120 s | **0.718** | 0.0428 | 0.1482 | 0.255 | 0.695 |
| J_PO | 32 s | 0.454 | 0.0951 | 0.2602 | 0.458 | 0.484 |
| J_PO | 60 s | 0.585 | 0.0686 | 0.2185 | 0.330 | 0.621 |
| J_PO | 120 s | **0.698** | 0.0621 | 0.1850 | 0.299 | 0.682 |

**J is much harder.** At 32 s, ρ ≈ 0.37–0.45 and nMAE ≈ 0.46–0.50: about half of the observed
window-to-window difference is as large as the entire population spread. At 120 s, ρ ≈ 0.70.

### B.3 The theoretical prediction confirmed

We predicted `M` (a mean statistic) would be easier to estimate from short recordings than `J`
(a dispersion statistic). Confirmed, and the gap is large:

| duration | ρ(M), mean over ROIs | ρ(J), mean over ROIs | ratio of nMAE J/M |
|---|---|---|---|
| 32 s | 0.820 | 0.421 | ~2.1× |
| 60 s | 0.863 | 0.561 | ~1.9× |
| 120 s | 0.889 | 0.706 | ~1.8× |

Not a surprise, and not a reason to drop `J` (brief §13). It is a duration requirement.

### B.4 Bland–Altman construction

Non-parametric agreement is reported for every feature × duration, because the differences are
not Gaussian. Per feature: median difference, empirical 2.5–97.5 % limits, plus the classical
mean ± 1.96 SD for comparison, and the slope of difference-vs-mean (proportional-bias check).
Plots: `outputs/stability_v1/plots/bland_altman_<feature>.png`; numeric columns in
`duration_summary.csv` (`ba_*`).

---

## C. Personal-relative (Level 2) stability

The final representation is the **change**, so this is the more important result. NS and SD
always use the **same** duration, so the estimator sample size is identical on both sides and
`J`'s finite-sample behaviour is not confounded.

### C.1 `ΔM`

| feature | duration | ρ | median\|Δ\| | P90\|Δ\| | nMAE | ICC(2,1) |
|---|---|---|---|---|---|---|
| ΔM_F | 32 s | 0.638 | 0.1992 | 0.5924 | 0.521 | 0.739 |
| ΔM_F | 60 s | 0.713 | 0.1672 | 0.4640 | 0.437 | 0.832 |
| ΔM_F | 120 s | **0.743** | 0.1108 | 0.3727 | 0.290 | 0.872 |
| ΔM_CT | 32 s | 0.550 | 0.1937 | 0.5465 | 0.568 | 0.803 |
| ΔM_CT | 60 s | 0.646 | 0.1627 | 0.4289 | 0.477 | 0.857 |
| ΔM_CT | 120 s | **0.699** | 0.1574 | 0.3552 | 0.462 | 0.865 |
| ΔM_PO | 32 s | 0.619 | 0.2173 | 0.6225 | 0.518 | 0.720 |
| ΔM_PO | 60 s | 0.707 | 0.1705 | 0.4826 | 0.406 | 0.843 |
| ΔM_PO | 120 s | **0.783** | 0.1503 | 0.3882 | 0.358 | 0.860 |

### C.2 `ΔlogJ`

| feature | duration | ρ | median\|Δ\| | P90\|Δ\| | nMAE | ICC(2,1) |
|---|---|---|---|---|---|---|
| ΔlogJ_F | 32 s | 0.205 | 0.4398 | 1.0627 | 1.161 | 0.101 |
| ΔlogJ_F | 60 s | 0.372 | 0.2883 | 0.7329 | 0.761 | 0.288 |
| ΔlogJ_F | 120 s | 0.481 | 0.3141 | 0.5270 | 0.829 | 0.504 |
| ΔlogJ_CT | 32 s | 0.272 | 0.4378 | 1.0679 | 0.985 | 0.216 |
| ΔlogJ_CT | 60 s | 0.448 | 0.3153 | 0.7675 | 0.710 | 0.447 |
| ΔlogJ_CT | 120 s | **0.594** | 0.2460 | 0.5360 | 0.554 | 0.586 |
| ΔlogJ_PO | 32 s | 0.193 | 0.4301 | 1.0449 | 1.224 | 0.169 |
| ΔlogJ_PO | 60 s | 0.321 | 0.3308 | 0.7676 | 0.942 | 0.315 |
| ΔlogJ_PO | 120 s | 0.378 | 0.2940 | 0.6302 | 0.837 | 0.379 |

**`ΔlogJ` is the weak coordinate, and at 120 s it is still marginal.** nMAE > 1 means the
typical window-to-window disagreement exceeds the population IQR of the full-duration change.
A ratio of two noisy dispersions inherits both dispersions' error, which is why `ΔlogJ` is
worse than either `J` alone or `ΔM`.

### C.3 Paired-change sign stability

P[sign(short) = sign(full)], short = first disjoint window, reference labelled
`full_session_containing_short` (i.e. **not** independent — it is the contained comparison):

| feature | 32 s | 60 s | 120 s |
|---|---|---|---|
| ΔM_F | 0.716 | 0.776 | **0.866** |
| ΔM_CT | 0.731 | 0.836 | **0.881** |
| ΔM_PO | 0.731 | 0.821 | **0.836** |
| ΔlogJ_F | 0.582 | 0.746 | 0.761 |
| ΔlogJ_CT | 0.612 | 0.657 | 0.701 |
| ΔlogJ_PO | 0.552 | 0.627 | 0.776 |

(n = 67 comparable pairs at every cell; complete table with `short_source` and
`reference_source` columns in `outputs/stability_v1/delta_sign_stability.csv`.)

For **`ΔM` at 120 s, the direction of a person's change is recovered 84–88 % of the time.**
For `ΔlogJ`, 32 s is close to a coin flip (0.55–0.61).

---

## D. Recording-position effect (Experiment B)

Question: is instability caused by short duration, or by the person's state drifting during the
recording? Early / middle / late windows are selected by **deterministic index** (first, middle,
last disjoint window); no random seed is involved.

### D.1 Early → late, all durations

| feature | 16 s | 32 s | 60 s | 120 s |
|---|---|---|---|---|
| M_F | −0.029 (p=.32) | −0.036 (p=.12) | −0.023 (p=.21) | −0.024 (p=.054) |
| M_CT | +0.032 (p=.32) | +0.020 (p=.81) | +0.024 (p=.32) | +0.014 (p=.71) |
| M_PO | +0.039 (p=.42) | +0.018 (p=.95) | +0.042 (p=.22) | +0.026 (p=.66) |
| **J_F** | **+0.057 (p=.002)** | **+0.047 (p=.005)** | +0.018 (p=.26) | +0.005 (p=.64) |
| **J_CT** | **+0.057 (p<.001)** | **+0.060 (p<.0001)** | **+0.034 (p=.002)** | +0.015 (p=.088) |
| **J_PO** | **+0.099 (p<.0001)** | **+0.078 (p<.001)** | **+0.043 (p=.003)** | **+0.027 (p=.018)** |

**9 of 24 early→late comparisons are significant at p < 0.05, and all 9 are `J`. Zero `M`
comparisons are significant at any duration.**

### D.2 Where the drift happens (60 s windows)

| feature | early→middle | middle→late |
|---|---|---|
| J_F | +0.021 (p = .076) | −0.003 (p = .95) |
| J_CT | **+0.030 (p = .002)** | +0.004 (p = .86) |
| J_PO | **+0.027 (p = .009)** | +0.016 (p = .15) |
| M_F / M_CT / M_PO | n.s. | n.s. |

### D.3 Answer

> **Yes — there is a systematic recording-position drift, and it is specific to `J`.**

* It is **not** an artefact of window length: it is present at every duration, and it shrinks as
  windows get longer only because longer windows average over more of the recording.
* The drift is **front-loaded**: most of the increase happens from the first to the second
  window, then plateaus (`middle → late` is non-significant for every feature).
* **`M` is position-independent.** Its early→late differences never reach significance and its
  effect sizes are ≤ 0.16 in absolute value.
* This is a substantive finding, not a nuisance: `J` is a *temporal instability* measure, so
  "instability is lower at the start of a resting recording and settles upward" is a
  physiological statement about the state, not estimator error.

**Binding consequence:** a single short window taken from the **start** of a recording
systematically under-estimates `J` relative to a full recording. Short `J` measurement is
therefore biased in a *predictable direction*, and any deployment protocol must fix the window's
position — or use a duration-matched baseline from the same position (see §E).

---

## E. Long-baseline / short-current scenario

Scenario: the user records a longer baseline once, then performs short current screenings.

**Method (as required):** the baseline (NS) recording is cut into **k-length disjoint windows**,
and the duration-matched reference is their **median**:

\[
\tilde M^{base}_{k}=\operatorname{median}_w M^{base}_{k,w},\qquad
\tilde J^{base}_{k}=\operatorname{median}_w J^{base}_{k,w}
\]

The current (SD) side uses **one** k-length window. Both sides therefore have the **same
estimator sample size** — the invalid comparison `J^{current}_{60s}` vs `J^{baseline}_{full}` is
never made. Output: `outputs/stability_v1/baseline_scenario.csv`.

| k | family | ROI | median Δ (matched baseline) | IQR | median Δ (single-window baseline) | IQR | ρ(single vs matched) |
|---|---|---|---|---|---|---|---|
| 32 s | M | F | +0.034 | 0.465 | −0.108 | 0.461 | 0.867 |
| 32 s | J | F | +0.004 | 0.608 | +0.027 | 0.561 | 0.812 |
| 32 s | J | CT | −0.025 | 0.539 | +0.018 | 0.617 | 0.805 |
| 60 s | M | F | −0.007 | 0.413 | −0.021 | 0.360 | 0.902 |
| 60 s | M | PO | +0.025 | 0.520 | +0.027 | 0.518 | **0.953** |
| 60 s | J | CT | +0.064 | 0.372 | +0.109 | 0.440 | 0.855 |
| 60 s | J | PO | +0.019 | 0.342 | +0.084 | 0.473 | 0.766 |
| 120 s | M | PO | +0.030 | 0.453 | +0.032 | 0.412 | **0.985** |
| 120 s | M | F | +0.007 | 0.397 | −0.006 | 0.342 | **0.959** |
| 120 s | J | F | +0.134 | 0.355 | +0.128 | 0.408 | 0.915 |
| 120 s | J | CT | +0.049 | 0.403 | +0.020 | 0.441 | 0.940 |
| 120 s | J | PO | +0.117 | 0.334 | +0.172 | 0.369 | 0.860 |

### Answer

> **Yes, a duration-matched baseline keeps the representation comparable — and it matters.**

* The two baseline conventions rank subjects almost identically (ρ = 0.75–0.99), so the
  *ordering* of users is robust to how the baseline is built.
* But the **magnitude** differs. At 32 s, using a single baseline window instead of the median
  of the baseline's windows shifts the group median ΔM_F from **+0.034 to −0.108** — it flips
  the apparent sign of the group effect while the IQR barely changes.
* The discrepancy shrinks monotonically with k: at 120 s, matched and single-window medians
  agree to within ~0.005 for `M` and ~0.01–0.06 for `J`.
* **Practical rule:** the median-over-windows baseline at 60–120 s is the right construct; a
  single 32 s baseline window is not sufficient, even though its ranking is fine.

This is a **deployment extension**, stored for later use. It does **not** change any
Mechanism-v1 mathematical definition.

---

## F. Finite-sample `J` behaviour

`J` is a sample SD over k epochs, so part of its short-duration instability is pure estimator
error. Quantified three ways (`outputs/stability_v1/finite_sample_J_simulation.csv`,
20 000 replicates, seed 20260916). The `J` definition was **not** modified.

Relative SD of the `J` estimate (region CT; F and PO agree to ±0.005):

| model | k=4 (16 s) | k=8 (32 s) | k=15 (60 s) | k=30 (120 s) | k=60 |
|---|---|---|---|---|---|
| Gaussian (textbook) | 0.389 | 0.262 | 0.188 | 0.130 | 0.092 |
| Student-t, ν=5 | 0.478 | 0.351 | 0.281 | 0.206 | 0.157 |
| **real empirical bootstrap** | **0.420** | **0.299** | **0.219** | **0.157** | **0.110** |

Bias (mean(s) − σ)/σ from the real bootstrap: **−0.098** (k=4), −0.052 (k=8), −0.031 (k=15),
−0.018 (k=30), −0.013 (k=60). The sample SD is downward-biased at small k.

Real per-epoch `S` dispersion: σ_F = 0.396, σ_CT = 0.350, σ_PO = 0.413. The real `S`
distribution is mildly leptokurtic (excess kurtosis 1.00–1.21) and nearly symmetric
(skew 0.05–0.17), which is why the empirical bootstrap sits between the Gaussian and t models.

### Answer

> **At 32 s, `J` carries ~30 % relative estimator uncertainty from epoch count alone; at 60 s,
> ~22 %; at 120 s, ~16 %.**

Two implications:

1. **`ΔlogJ` is the harder target, and part of that is arithmetic.** Using the same k on both
   sides (which we do) makes the *bias* largely cancel in the ratio, but the **variance does
   not**: the relative SD of a ratio of two independent SD estimates is ≈ √2 × the relative SD
   of each. That alone predicts ~42 % relative error in `ΔlogJ` at 32 s, ~31 % at 60 s and
   ~22 % at 120 s — before any real state drift.
2. **The empirical instability is far below what pure estimator noise would allow.** If
   estimator noise were the only source of disagreement, a noise level of 0.30 relative at
   32 s implies a split-half Spearman of ≈ 0.84 (using ρ ≈ (1−R²)/(1+R²)). Observed for `J`:
   0.37–0.45. The same calculation gives a noise-only floor of **0.91 at 60 s** and **0.95 at
   120 s**, against observed 0.53–0.59 and 0.70–0.72. **`J`'s short-recording instability is
   therefore not primarily a statistical artefact** — it is real within-recording state
   variation, exactly what `J` is defined to measure and consistent with §D's systematic drift.

   For contrast, `M`'s observed ρ at 32 s (0.81–0.86) sits *at* the noise-only floor, i.e. `M`
   is already estimator-limited rather than state-limited at 32 s.

---

## G. Literature / sample reconciliation

Full detail: [`paper_sample_reconciliation.md`](paper_sample_reconciliation.md).

| | paper | ours |
|---|---|---|
| start | 71 | 71 |
| valid paired EEG | 64 (their own raw pipeline) | **68** (file-level admissibility on inherited preprocessing) |
| paired EEG + PVT | 28 | **29** (raw trial files) |

The PVT-based explanation for the gap (`<45 valid trials` → drops `sub-11`) is **withdrawn** as
the leading hypothesis. Nothing new was explored on the PVT side.

Replacement finding: **`sub-32` is the worst-quality subject among our 29** — 56.3 % of its
epochs exceed 200 µV in one session, versus a median of 0 % across all 136 sessions. A 200 µV
epoch-rejection rule of the kind the paper describes would flag `sub-32` hardest, and dropping
it gives exactly 28. **It is not adopted**: the paper publishes no per-subject artefact counts,
so this cannot be confirmed; the threshold is not unique; and choosing who to drop so a count
matches a published N is exactly the researcher degree of freedom we are trying to eliminate.

**Required statement:** `paper n=28 cannot be exactly reconstructed from published participant
identifiers.`

The frontal ρ mismatch is recorded as a **provenance limitation**, not a blocker:
our group-level spectral changes already match the paper closely
(theta relative power F/CT/PO: 0.0114/0.0297/0.0259 paper vs +0.0102/+0.0273/+0.0264 ours;
theta variability 0.0177/0.0206/0.0251 vs +0.0085/+0.0179/+0.0186), their pipeline differs
(raw v1.0.4, self-run visual examination + ICA) from our inherited third-party pruning, and
ρ is a correlation on a PVT subsample. No preprocessing, band, ROI or participant set was
adjusted to chase it.

---

## H. Raw-data recovery

Full detail: [`official_raw_recovery_plan.md`](official_raw_recovery_plan.md).

**Verdict: recoverable.** Evidence (`outputs/stability_v1/raw_recovery_probe.json`):

| probe | result |
|---|---|
| `HEAD` on NEMAR `sub-01_ses-1_task-eyesopen_eeg.fdt` | **200, 36 600 000 bytes** (= manifest size) |
| `HEAD` on `..._eeg.set` | 200, 198 722 bytes |
| `HEAD` on `sub-39_ses-2_task-eyesopen_eeg.fdt` | 200, 366 000 000 bytes |
| NEMAR manifest | 1233 entries, full index with sizes and per-file HTTPS URLs |
| total dataset | **8.90 GB** |
| eyes-open subset (`task-eyesopen`, 284 files) | **6.11 GB** |
| eyes-closed subset | 2.79 GB |
| behavioural | 0.03 MB |

Content-Length equal to the manifest size is the decisive point: these are **real objects over
HTTPS, not annex pointers** — unlike the local tree. eyes-open is a separate `task-` entity, so
a targeted 6.11 GB pull is enough. Versions: NEMAR mirror is v1.0.0 ← OpenNeuro v1.0.8; the
paper used **v1.0.4**; our inherited preprocessing used **v1.0.5**. A canonical branch should
pin one explicitly.

**Recommendation:** worth doing **before the final paper-level experiments, not before Phase 2
modelling**. Both the stability audit and the Phase 2 protocol run on the current corpus; the
download buys provenance and closes the eyes-open-at-family-level uncertainty, not predictive
power. Nothing was downloaded.

---

## I. Scientific conclusion

Answering only the four permitted questions.

**I.1 Which durations already show adequate estimator stability for Mechanism-v1?**

| coordinate | verdict | evidence |
|---|---|---|
| `M_F`, `M_CT`, `M_PO` | **adequate from 32 s**; comfortable at 60 s | ρ 0.81–0.86 at 32 s, 0.85–0.88 at 60 s; nMAE 0.22–0.23 → 0.18–0.19; ICC ≥ 0.84 |
| `J_F`, `J_CT`, `J_PO` | **not adequate at 32 s**; marginal at 60 s; approaching usable at 120 s | ρ 0.37–0.45 (32 s), 0.53–0.59 (60 s), 0.70–0.72 (120 s) |
| `ΔM_F`, `ΔM_CT`, `ΔM_PO` | **usable at 60 s**; best at 120 s | ρ 0.55–0.71 (60 s), 0.70–0.78 (120 s); sign agreement 0.78–0.87 at 120 s |
| `ΔlogJ_*` | **not adequate at any tested duration** | ρ 0.19–0.27 (32 s) → 0.38–0.59 (120 s); nMAE ≥ 0.55 even at 120 s |

**I.2 Which feature family is most duration-sensitive?**

`J` / `ΔlogJ`, decisively. The `M` family is nearly saturated at 32 s (its ρ gains only
0.07 from 32 s → 120 s), whereas the `J` family gains 0.27–0.33 over the same range.
`ΔlogJ` is the most duration-sensitive and the least reliable coordinate measured.
Spatially, the three ROIs behave consistently — no ROI is an outlier.

**I.3 Is there serious recording-position drift?**

Yes, and it is **specific to `J`**: `J` increases from early to late in 9 of 24 early→late
comparisons (all p < 0.05), all of them `J`, none of them `M`; the drift is front-loaded
(early→middle significant, middle→late not) and present at every duration. `M` shows no
systematic position effect. This is a statement about the state, not just the estimator, and
it means a short `J` window taken at the start of a recording is biased low in a predictable
direction.

**I.4 Is there evidence that short-time measurement is itself infeasible?**

**No — but the two families must be treated differently.**

* Short-time measurement of **`M` is clearly feasible**: 32 s already gives ρ ≥ 0.81 and
  ICC ≥ 0.84, and `ΔM` at 60–120 s is usable with sign recovery ~0.78–0.87.
* Short-time measurement of **`J` is not yet demonstrated**. Its estimator uncertainty at 32 s
  is ~30 % relative from epoch count alone, its observed stability is worse than that floor,
  and it drifts systematically with recording position. `ΔlogJ` compounds both dispersions and
  is the weakest coordinate measured.
* What would settle `J` is not a longer recording per se, but a **fixed-position,
  fixed-duration protocol** plus an explicit drift model. That is a design question for the
  deployment-duration experiment, not a reason to abandon the coordinate.

**No PVT prediction is discussed here, by instruction.**

---

## J. Proposed Phase 2

**Protocol draft only. Not run. Awaiting PI freeze.**

### J.0 What Phase 1.5 changes about the plan

The stability results should be *carried into* the protocol rather than ignored:

* `ΔlogJ` at 32–60 s is close to noise. A predictive result there would be uninterpretable, so
  **the primary Phase 2 analysis should use 120 s (or full) coordinates**, with the short
  durations reported as a pre-declared degradation curve, not as candidate winners.
* Because `J` drifts with position, **all windows must be taken from a fixed position**
  (the recording start) in a fixed-duration protocol.
* Because `ΔM` and `ΔlogJ` have very different reliability, the model ladder should make the
  incremental value of each family separately visible.

### J.1 Targets

* primary: `Y_log_medianRT_raw`
* secondary: `Y_log_response_speed_raw`
* Both already computed and frozen in Phase 1. No selection between them on results.

### J.2 Predictors

Exactly the six frozen coordinates at a **fixed duration** (default 120 s; full as a
sensitivity check). No selection, no addition, no channel selection.

### J.3 Design

* **Nested LOSO** over the 29 PVT-paired subjects. Outer loop holds out one subject; the inner
  loop over the remaining 28 selects any hyperparameter (ridge penalty only). The test subject
  never influences its own model — including the choice of duration.
* Explicit nested model ladder, each a distinct hypothesis:

  | model | predictors |
  |---|---|
  | `M0` | intercept only (chance floor) |
  | `M1` | ΔM_F, ΔM_CT, ΔM_PO |
  | `M2` | ΔlogJ_F, ΔlogJ_CT, ΔlogJ_PO |
  | `M3` | all six |

  `M2` and `M3` exist to test whether the instability family earns its place **over** mean
  slowing. Given §C–D, `M2` may well fail; that is a legitimate result and must be reported,
  not engineered away.

### J.4 Required reporting

* per-subject held-out predictions (all 29), not just a summary statistic;
* **subject-level permutation null** (≥5000 permutations) for every reported correlation —
  with n = 29 the null must be shown, not assumed;
* effect sizes with bootstrap CIs, not p-values alone;
* the Phase 1.5 reliability of each predictor alongside its coefficient, so a null result can
  be attributed to unreliable measurement rather than to an absent effect;
* the pre-declared duration-degradation curve (32 / 60 / 120 / full) as a secondary analysis.

### J.5 Confound audit before modelling

Regress each coordinate on `session_order`, EEG clock-time gap, PVT clock-time gap, and
epoch-count difference; report. These variables never enter the predictor set.

### J.6 Explicitly out of scope for Phase 2

Cross-dataset training, channel reduction, baseline-duration optimisation, TTA/TENT,
NS/SD classification, and any form of feature selection. Those follow only if Phase 2
produces a non-null result.

---

## Non-claims

Phase 1.5 does **not** claim test–retest reliability, a biomarker, real-time detection, or that
`J` is a metastability or dynamic-network marker. It reports **within-session estimator
stability** and **short-duration convergence** for six pre-declared coordinates, plus a
recording-position effect that is specific to the instability family.

## Reproduce

```powershell
cd project/vigilance_generalization_v1
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/run_phase15.py   # ~327 s end to end
```

Independent verification: `scripts/14_verify_phase15.py` — **26/26 checks pass**, including
recomputation of 343 window features and all 2120 paired-window deltas from the raw `.set`
files (`max|Δ| = 0.000e+00`), disjointness/order/count checks, and a scan confirming no PVT
target column reaches any stability table.

Full list of new files: `outputs/stability_v1/` (13 CSV + 3 JSON + 10 plots),
`PHASE1_5_REPORT.md`, `paper_sample_reconciliation.md`, `official_raw_recovery_plan.md`,
`src/stability.py`, `src/stability_metrics.py`, `src/probe_raw_recovery.py`,
`scripts/10..14`, `scripts/run_phase15.py`. Hashes in `outputs/qc/run_manifest.json`.
