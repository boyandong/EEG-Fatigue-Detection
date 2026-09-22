# PHASE1_75_REPORT.md — Dynamic-Mechanism Decomposition & Target Psychometrics

Branch: `vigilance_generalization_v1`. Governed by [`SCIENTIFIC_SPEC.md`](SCIENTIFIC_SPEC.md) §17
(Phase 1.75 amendments). Builds on [`PHASE1_5_REPORT.md`](PHASE1_5_REPORT.md).

**No EEG→PVT predictor was trained. No PVT value was used to select `J`/`V`/`J_res`, burn-in,
duration, or target. The 100–2000 ms trial rule is unchanged. No subject was removed.**

Answers required by Part L:

| | question | short answer |
|---|---|---|
| **Q1** | which of `J`, `V`, `J_res` has the best target-independent short-duration stability? | **`J`**, marginally — and `V` is *worse* than `J` at 32 s. None of the three is usable at 32 s. |
| **Q2** | which is least affected by recording position? | **`V`** at 32 s, but the ranking flips at 120 s; all three are far worse than `M`. |
| **Q3** | is there a defensible `Protocol(B,T)` fixable without PVT? | **Yes: `B = 60 s`, `T = 60 s`** — keeps all 67 subjects and cuts position bias ~4×. |
| **Q4** | how large is the finite-trial uncertainty of `Y_RT` and `Y_speed`? | `Y_RT` **SE/point-SD = 0.54**, `R_approx = 0.70`; `Y_speed` **0.42**, `R_approx = 0.81`. |

---

## A. Dynamic decomposition

### A.1 Measurement model (now frozen in the spec)

\[
\boxed{\;S_{e,r} = \mu_r + g_r(t_e) + u_{e,r} + \eta_{e,r}\;}
\qquad\Longrightarrow\qquad
M_r \approx \mu_r + \overline{g_r},\quad
J_r^2 = \operatorname{Var}[g_r + u_{e,r} + \eta_{e,r}]
\]

`SCIENTIFIC_SPEC.md` §17.1 now states this explicitly. `J` is defined as **total
within-recording temporal dispersion** and the wording `J ≡ vigilance instability` is
**withdrawn**. Phase 1.5's sentence *"J is temporal instability, this is a statement about the
state"* is **retracted**: `J` mixes slow drift, local fluctuation and measurement noise, and the
data cannot separate them.

### A.2 What the data shows about the components

Phase 1.5 established the mixture empirically (9 of 24 early→late comparisons significant, **all
of them `J`**, none of them `M`). Phase 1.75 adds a direct decomposition diagnostic
(`D_r` = total linear change across the window, `J_res` = dispersion after removing it):

| observable | definition | role |
|---|---|---|
| `M_r` | `mean_e S` | tonic level proxy (primary) |
| `J_r` | `SD_e S`, ddof 1 | total temporal dispersion (mixture) |
| `V_r` | `sqrt(Σ(S_{e+1}−S_e)² / (2(N−1)))` | local epoch-to-epoch spectral volatility proxy |
| `D_r` | OLS slope of `S` on centred `τ_e` | **diagnostic** — slow linear drift |
| `J_res_r` | `SD` of detrended `S` | **diagnostic** — dispersion after linear drift |

`mechanism_v1` was **not modified**. The new representation is
`mechanism_v1_1_dynamic_audit`, written to `outputs/dynamic_audit/`.

### A.3 `V` is a genuinely different estimator — and the difference is a scaling law

> **CORRECTED after PI review.** The table below is numerically right, but the conclusion first
> drawn from it — that `V` has an intrinsic recording-length `1/N` penalty that hurts
> cross-dataset portability — **was wrong and is withdrawn.** For a fixed per-step slope
> \(S_e=a+be\), \(V=|b|/\sqrt2\) independently of \(N\); for \(S(t)=a+qt\) sampled at fixed
> stride \(\Delta t\), \(V=|q|\Delta t/\sqrt2\), again independent of recording length. The
> \(1/N\) pattern appears **only** because the table holds the total span fixed while increasing
> \(N\), which forces \(b=\Delta/(N-1)\). `V` is sensitive to the **epoch stride \(\Delta t\)**,
> not to the number of epochs. See `SCIENTIFIC_SPEC.md` §17.2.2.

The brief's concern was that differencing amplifies noise
(`Var(η_{e+1}−η_e) = 2σ_η²`). Verified (see §B.4). A second property also surfaced: the listed
`V/J` ratio is not constant across window length **when the total span is held fixed**:

| window | N | `J` | `V` | `V/J` (fixed total span) |
|---|---|---|---|---|
| 60 s | 15 | 0.3194 | 5.05e−02 | 0.158 |
| 120 s | 30 | 0.3036 | 2.44e−02 | 0.080 |
| 280 s | 70 | 0.2949 | 1.03e−02 | 0.035 |

That table describes a rescaling experiment, not the estimator's behaviour. What it correctly
shows is that `V` is *far* less sensitive to a slow trend than `J`. Consequences:

1. `V` and `J` are **not two estimates of the same quantity** and must not be described as if
   one replaces the other. `J` = total dispersion including slow drift; `V` ≈ dispersion of the
   high-frequency component only.
2. Because `V` depends on \(\Delta t\), **every future dataset must fix epoch = 4 s and
   stride = 4 s** for `V` to be comparable. This is now a binding requirement in the spec.
3. `V` is still **not adopted as a predictor**, but on measured grounds (§B): it is less
   reliable than `J` at every tested duration, exactly as its noise-amplifying definition
   predicts.

### A.4 Decomposition diagnostics are available but not adopted

`D_r` and `J_res_r` are computed for every window (columns in
`outputs/dynamic_audit/J_V_Jres_session.csv`). They are **diagnostics**. Per the brief and
§17.2, `J_res` is **not** adopted merely because it turns out to be marginally the most stable
of the three (see §B).

---

## B. J vs V vs J_res stability

68 subjects / 136 sessions. Disjoint equal-length windows; every window recomputed through the
full chain. Overlap never used to reach an n. nMAE reference scale = IQR of the full-session
values.

### B.1 Session-level disjoint-window stability (ρ, 3 ROIs averaged)

| observable | 32 s | 60 s | 120 s | full |
|---|---|---|---|---|
| **`M`** | **0.820** | **0.862** | **0.889** | — |
| `J` | **0.421** | 0.561 | 0.706 | — |
| `V` | 0.358 | 0.493 | 0.673 | — |
| `J_res` | 0.380 | 0.552 | 0.700 | — |

nMAE (window-to-window error ÷ population IQR):

| observable | 32 s | 60 s | 120 s |
|---|---|---|---|
| `M` | 0.249 | 0.202 | 0.162 |
| `J` | 0.638 | 0.478 | 0.374 |
| `V` | **0.789** | 0.598 | 0.460 |
| `J_res` | 0.666 | 0.478 | 0.374 |

### B.2 Paired personal-relative stability (ρ of `Δlog`, 3 ROIs averaged)

| observable | 32 s | 60 s | 120 s | nMAE 32 / 60 / 120 |
|---|---|---|---|---|
| `ΔlogJ` | **0.223** | 0.380 | **0.484** | 1.124 / 0.804 / 0.740 |
| `ΔlogV` | 0.188 | 0.326 | 0.444 | 1.154 / 0.817 / 0.635 |
| `ΔlogJ_res` | 0.200 | 0.374 | 0.454 | 1.160 / 0.750 / 0.668 |

### B.3 Answer to Q1

> **`J` is the best of the three, but the margin is small and none of them is usable at 32 s.**

* At 32 s: `J` ρ = 0.421, `V` = 0.358, `J_res` = 0.380. **`V` is the worst**, despite being
  designed to be cleaner.
* At 120 s: `J` = 0.706, `J_res` = 0.700, `V` = 0.673 — effectively tied.
* All three have `nMAE ≥ 1` for the **paired change** at 32–60 s, meaning the typical
  window-to-window disagreement in `ΔlogJ`/`ΔlogV` **exceeds the entire population IQR** of that
  change. A paired dynamic coordinate measured at 32–60 s carries essentially no usable
  between-person information.
* `J_res` is at best marginally better than `J`. **It is not adopted**, because choosing it
  would be selecting the observable on stability alone, and because adopting it would silently
  redefine the dynamic family after seeing the data.

**`V` does not earn a replacement of `J`.** Per the brief, replacement was conditional on `V`
being measurably better; it is not.

### B.4 The noise-amplification caveat, verified

\[
\operatorname{Var}(\eta_{e+1}-\eta_e) = 2\sigma_\eta^2
\]

confirmed numerically (`Var(diff)/2 = 1.0004` on 10⁵ i.i.d. draws). Combined with §A.3, `V`
trades a **1/N reduction in drift sensitivity** for a **2× increase in noise variance** per
difference. On real data that trade is net negative at short durations.

---

## C. Position dependence

Early / middle / late windows by deterministic index; no random seed.

### C.1 Early → late, |Cohen's dz|, 3 ROIs averaged

| observable | 32 s | 60 s | 120 s |
|---|---|---|---|
| `M` | **0.076** | **0.118** | **0.118** |
| `J` | 0.372 | 0.250 | 0.158 |
| `V` | 0.316 | 0.225 | **0.191** |
| `J_res` | 0.387 | 0.291 | 0.199 |

### C.2 Answer to Q2

> **`V` is least position-dependent at 32 s, but the ordering is not stable across durations,
> and every dynamic observable is 2–5× more position-dependent than `M`.**

* At 32 s: `V` (0.316) < `J` (0.372) < `J_res` (0.387).
* At 120 s: `J` (0.158) < `V` (0.191) < `J_res` (0.199).
* `M` is position-stable at every duration (|dz| ≤ 0.12).

**Restricted reporting language (Part F, binding).** This is a **recording-position effect** —
a **slow within-recording drift**. It is **not** to be described as "genuine vigilance drift".
The data cannot exclude: acquisition settling, electrode/contact settling, residual
preprocessing, cognitive adaptation to resting, post-eye-opening habituation, or the
recording-onset protocol. Any of these, or a mixture, would produce the same observation.

---

## D. Burn-in / duration protocol

`Protocol(B, T)` over the pre-declared grid. B = 0 is the duration grid itself (`k8`/`k15`/`k30`)
— deliberately not duplicated under a second label. `B = 60, T = 120` is **infeasible** and is
reported as such rather than quietly dropped: with ~230–320 s of usable data per session, 60 s of
burn-in leaves too little for two disjoint 120 s windows (1 session of 136; 0 subjects).

| protocol | B | T | sessions ≥2 windows | subjects ≥2 paired | ρ disjoint | ρ paired Δ | sign agreement | mean \|dz\| early→late |
|---|---|---|---|---|---|---|---|---|
| B0_T32 | 0 | 32 | 135 | 67 | 0.386 | 0.204 | 0.570 | 0.358 |
| B0_T60 | 0 | 60 | 135 | 67 | 0.535 | 0.360 | 0.680 | 0.255 |
| B0_T120 | 0 | 120 | 129 | 61 | 0.693 | 0.461 | 0.760 | 0.183 |
| **B32_T32** | 32 | 32 | 135 | **67** | **0.406** | **0.225** | **0.647** | **0.214** |
| **B32_T60** | 32 | 60 | 135 | **67** | **0.578** | 0.339 | **0.733** | **0.217** |
| B32_T120 | 32 | 120 | 104 | 43 | 0.724 | 0.554 | 0.834 | 0.170 |
| B60_T32 | 60 | 32 | 135 | **67** | 0.430 | 0.269 | 0.688 | 0.187 |
| **B60_T60** | 60 | 60 | 135 | **67** | **0.591** | **0.447** | 0.720 | **0.064** |
| B60_T120 | 60 | 120 | **1** | **0** | — | — | 0.837 | — |

### D.1 Effect of burn-in at fixed T

Burn-in helps, and it helps **position bias** most:

| comparison | Δρ disjoint | Δρ paired | Δsign | Δ\|dz\| |
|---|---|---|---|---|
| B0_T32 → B32_T32 | +0.020 | +0.021 | +0.077 | **−0.144 (−40 %)** |
| B0_T60 → B32_T60 | +0.043 | −0.021 | +0.053 | −0.038 (−15 %) |
| B0_T60 → B60_T60 | +0.056 | **+0.087** | +0.040 | **−0.191 (−75 %)** |

### D.2 Subject cost

`B = 32, T = 120` and `B = 60, T = 120` are expensive: only 43 and 0 of 67 subjects retain two
paired windows. Crucially, **`B32_T120` would break Phase 2 directly**: it leaves exactly **21 of
the 29** PVT-paired subjects with both sessions eligible. `B = 32, T = 60` and `B = 60, T = 60`
keep **all 67** subjects, and all 29 Phase 2 subjects.

### D.3 Answer to Q3

> **Yes. `Protocol(B = 60 s, T = 60 s)` is the defensible freeze.**

Reasoning, in the order the brief specifies (stability → position bias → paired stability →
usable n), and using no PVT information:

1. **Position bias**: |dz| = **0.064**, the lowest of every feasible cell — a ~4× reduction
   versus the same 60 s window with no burn-in (0.255).
2. **Usable n**: **67/67** subjects keep ≥2 paired windows, and all **29** Phase 2 subjects are
   retained. No attrition cost.
3. **Paired-change stability**: ρ = **0.447**, the best of any cell that retains 67 subjects
   (vs 0.360 at B0_T60, 0.339 at B32_T60).
4. **Session-level stability**: ρ = 0.591, and sign agreement 0.720.

**The runner-up is `B = 32, T = 60`**: it also keeps 67 subjects and costs only 32 s of user
time, with ρ_paired = 0.339 and |dz| = 0.217. If measurement burden matters more than bias,
this is the alternative. I am **not** choosing between them by looking for a finer optimum:
per the brief, once a 32–60 s burn-in removes most of the systematic effect we **stop** and do
not search 40/48/56 s. Both cells are reported; the choice is a PI decision.

### D.4 A confound that must be stated

Burn-in and recording position are **not independent**: adding burn-in shifts the measured
segment later in the recording. The comparison is therefore *"measured from onset"* versus
*"measured after onset"*, **not** a clean manipulation of settling. A protocol with burn-in is
strictly better *as a protocol*, because it measures where the signal is stable; we cannot claim
from this design that we have identified settling as the mechanism.

---

## E. PVT median-RT measurement uncertainty

29 raw-PVT-paired subjects, trials filtered to 100–2000 ms, **5000 within-session bootstrap
replicates, seed 20260916**. Resampling is within-session with replacement: the two sessions are
separate strata, so the pairing is preserved and an SD trial can never stand in for an NS trial.

Valid trials per session: NS 44–95 (median 48), SD 45–92 (median 50).

\[
Y^{RT}_i = \ln\frac{R^{\text{med}}_{i,SD}}{R^{\text{med}}_{i,NS}}
\]

| quantity | value |
|---|---|
| point estimate, mean ± SD | **+0.1187 ± 0.1014** |
| mean bootstrap SE | **0.0542** |
| **SE / between-subject SD** | **0.535** |
| range of SE | 0.031 – 0.085 |
| one-sample t vs 0 | t(28) = 6.31, p = 2.7e−6 |
| subjects whose 95% CI excludes 0 | **16 / 29** |
| `σ_ε² = mean(SE²)` | 0.00310 |
| `s_Y² = Var(Y)` | 0.01027 |

Per-subject values, CIs and trial counts: `outputs/pvt_psychometrics/pvt_target_uncertainty.csv`.

**Reading.** The group mean is clearly non-zero (t = 6.31), but **more than half of the
between-subject spread is finite-trial measurement error**: `SE/sd = 0.54`. For **13 of 29**
subjects the subject's own bootstrap CI includes zero, i.e. that individual's change is not
distinguishable from no change at the trial-sampling level.

> Note also that the source paper reports median RT showing **no significant group change**
> (t(29) = 0.04, p = 0.97), while RT SD and lapses did change. Our raw-trial recomputation gives
> a clearly positive group median-RT change on this 29-subject subsample. That discrepancy is a
> **target-definition fact**, not a feature-selection opportunity, and it is reported rather than
> resolved by choosing whichever target looks better.

---

## F. Response-speed measurement uncertainty

\[
Q_{i,s} = \operatorname{mean}_j (1/RT_{i,s,j}),
\qquad
Y^{\text{speed}}_i = \ln\frac{Q_{i,NS}}{Q_{i,SD}}
\]

Same bootstrap, same seeds, computed in the **same resampling pass** as `Y_RT`.

| quantity | value | vs `Y_RT` |
|---|---|---|
| point estimate, mean ± SD | **+0.1188 ± 0.0962** | nearly identical mean |
| mean bootstrap SE | **0.0407** | **25 % smaller** |
| **SE / between-subject SD** | **0.423** | better |
| range of SE | 0.025 – 0.061 | — |
| one-sample t vs 0 | t(28) = 6.65, p = 1.3e−6 | — |
| subjects whose 95% CI excludes 0 | **19 / 29** | +3 subjects |
| `σ_ε²` | 0.00173 | **44 % smaller** |
| `s_Y²` | 0.00925 | similar |

**Reading.** Response speed is the psychometrically quieter of the two: the same group effect
with ~25 % less finite-trial noise, and it resolves 19 instead of 16 individuals. It is also the
target with a defensible pre-existing motivation (it is a rate, it uses every trial rather than
an order statistic, and it is not sensitive to the RT floor).

> **Selection discipline.** This comparison is *measurement stability only*. It is **not** a
> licence to pick the target that will correlate better with EEG — no EEG feature was read in
> this part of the analysis, and none may be used to revisit this. The PI decides
> primary/secondary on measurement grounds plus literature; the evidence for `Y_speed` being the
> quieter target is now on the table, and the counter-consideration (median RT is the published,
> citable convention) is equally on the table.

---

## G. Approximate target reliability

\[
R_Y^{\text{approx}} = \max\left(0,\; 1 - \frac{\sigma_\epsilon^2}{s_Y^2}\right),
\qquad
\sigma_\epsilon^2 = \frac1n\sum_i SE_i(Y)^2
\]

| target | `R_approx` | `σ_ε²` | `s_Y²` | measurement share of observed variance |
|---|---|---|---|---|
| `Y_RT` | **0.698** | 0.00310 | 0.01027 | **30.2 %** |
| `Y_speed` | **0.813** | 0.00173 | 0.00925 | **18.7 %** |

> **Label: approximate finite-trial reliability proxy.**
> This is **not** test–retest reliability. The bootstrap sees only finite-trial sampling
> uncertainty; it cannot estimate day-to-day variability, circadian change, or true
> within-person state variation. The true reliability is therefore **lower** than these numbers,
> by an unknown amount.

### G.1 Interleaved split-half sensitivity (Part J)

Odd vs even trials, which preserves the time-on-task distribution. A first-half / second-half
split is deliberately **not** used as the primary split, because PVT performance itself drifts
with time on task.

| target | Spearman(odd, even) | Spearman–Brown corrected | median \|Δ\| | P90 \|Δ\| | sign agreement |
|---|---|---|---|---|---|
| `Y_RT` | +0.611 | **0.766** | 0.108 | 0.356 | **0.931** |
| `Y_speed` | +0.725 | **0.856** | 0.093 | 0.315 | 0.897 |

The split-half estimates (0.77 / 0.86 after Spearman–Brown) sit **above** the bootstrap-based
`R_approx` (0.70 / 0.81) but agree on the ordering and the magnitude. They are not the same
quantity: the split-half asks whether two halves of the *same* session agree; the bootstrap
asks how much the estimate would move under trial resampling.

### G.2 Practical consequence for Phase 2

With `Y_RT` at `R ≈ 0.70`, an EEG coordinate that predicts the *true* `Y` with correlation
`r_true` can be expected to show an observed correlation of roughly `r_true × sqrt(0.70) ≈ 0.84
r_true`. At `n = 29`, a true `r_true = 0.5` would be attenuated to ≈ 0.42, whose 95 % CI at
n = 29 easily includes zero. **A null Phase 2 result on `Y_RT` would therefore be substantially
uninformative unless the reliability ceiling is reported alongside it.** This is exactly why the
target audit was worth doing before fitting anything.

---

## H. Remaining scientific limitations

1. **`J` remains a mixture.** `D` and `J_res` describe a *linear* drift only; non-linear slow
   change (settling curves, state transitions) is not separated and still inflates `J`.
2. **The position effect's mechanism is unidentified.** Acquisition settling, contact settling,
   residual preprocessing, adaptation, eye-state compliance and the onset protocol all remain
   live explanations. The reporting language restriction of §C.2 is binding until they can be
   separated — which would need a study designed for it (e.g. repeated recordings, or a
   counterbalanced onset delay), not this dataset.
3. **Burn-in and position are confounded** (§D.4). A `Protocol(B,T)` freezes a *measurement
   position*, not a physiological settling time.
4. **`V`'s 1/N drift scaling** means `V` is not comparable across recording lengths without
   explicit normalisation, which weakens its cross-dataset portability — the property it was
   supposed to improve.
5. **Target reliability is bounded from below only.** `R_approx` is an upper bound on true
   reliability, since the bootstrap cannot see between-session variability. The true ceiling on
   any predictable signal is therefore **≤ 0.70** for `Y_RT`.
6. **`Y_RT`'s group change disagrees with the published analysis** — **now resolved, not
   unexplained.** The dataset paper prints \(t(29)=0.04\) under the median-RT label, but the
   project's PVT audit recomputed the paired statistics from `participants.tsv` and found
   \(t\approx 0.042\) (item 1), \(-7.308\) (item 2), \(-4.715\) (item 3) against the paper's
   printed median RT → 0.04, RT SD → −7.31, lapses → −4.72: the values match numerically but are
   assigned **cyclically** to the wrong labels. Accordingly the paper's textual median-RT
   statistic is **not** used to validate the direction or magnitude of our reconstructed raw
   median-RT target. See `SCIENTIFIC_SPEC.md` §17.7 and `pvt_audit_v1/`.
7. **The official `participants.tsv` targets cannot be audited at trial level**, so they remain
   sensitivity-only and are not used to select anything.
8. **Eyes-open provenance is still family-level** (see `PHASE1_REPORT.md` F2), and the
   preprocessing is still third-party and non-reproducible. The
   `official_raw_recovery_plan.md` branch would close this and is still unimplemented.

---

## I. Proposed frozen Mechanism-v2 + target protocol

**Proposal only. Not implemented. No Phase 2 code written.**

### I.1 Representation

The measurement audit does **not** support replacing `J` with `V` or `J_res`:

| candidate | 32 s ρ | 60 s ρ | 120 s ρ | position bias | verdict |
|---|---|---|---|---|---|
| `J` | 0.421 | 0.561 | **0.706** | moderate | **keep** |
| `V` | 0.358 | 0.493 | 0.673 | slightly better at 32 s, worse at 120 s | **not adopted** |
| `J_res` | 0.380 | 0.552 | 0.700 | worse at all durations | **not adopted** |

Proposed frozen input, pending PI decision:

\[
\boxed{\;
X_i=\big[\Delta M_F,\Delta M_{CT},\Delta M_{PO},\;\Delta\log J_F,\Delta\log J_{CT},\Delta\log J_{PO}\big]
\;}
\]

with `D` and `J_res` retained **only** as reported diagnostics, and `V` retained as a
**reported secondary audit observable** rather than a model input.

I would flag one honest alternative for the PI: because `J`'s 120 s performance is only
"approaching usable" and `M`'s is excellent at 32 s, a **two-tier** Phase 2 is defensible —
`M`-only as the primary hypothesis, `ΔlogJ` as an exploratory secondary with the reliability
ceiling attached. That is a scientific framing decision, not mine to make.

### I.2 Measurement protocol

Freeze `Protocol(B = 60 s, T = 60 s)` as the primary, with `Protocol(B = 32 s, T = 60 s)` as a
declared lower-burden sensitivity analysis. Both retain all 67 subjects and all 29 Phase 2
subjects. **Do not** search for a better cell.

### I.3 Target

Both targets exist, are audited, and are computed from the same frozen trial rule. The evidence
favours `Y_speed` on measurement stability (`R_approx` 0.81 vs 0.70; SE 25 % smaller; 19/29 vs
16/29 individually resolved). The counter-consideration is that `Y_RT` is the published
convention and is directly comparable to the source paper. **Decision deferred to the PI.**

Whichever is chosen:

\[
\boxed{\;Y_i=\ln\frac{\text{current functional latency}_i}{\text{personal alert latency}_i}\;}
\]

with the **reliability ceiling reported next to every correlation**.

### I.4 Phase 2 protocol sketch (unchanged in structure from Phase 1.5's proposal)

Nested LOSO over the 29 subjects; inner loop for the ridge penalty only; model ladder
`M0` (intercept) → `M1` (ΔM only) → `M2` (ΔlogJ only) → `M3` (both); **subject-level permutation
null ≥ 5000**; effect sizes with bootstrap CIs; the Phase 1.5/1.75 reliability of every
predictor reported alongside its coefficient so a null can be attributed to measurement rather
than to absence of effect. Confound audit (`session_order`, clock-time gaps, epoch-count
difference) before modelling; those variables never enter the predictor.

**Not started.**

---

## Reproduce

```powershell
cd project/vigilance_generalization_v1
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/20_extract_dynamic.py      # ~350 s
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/21_pvt_psychometrics.py    # ~1 s
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/22_dynamic_stability.py    # ~1 s
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/24_dynamic_plots.py
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/23_verify_phase175.py
```

Independent verification: **44/44 checks pass**, including recomputation of 252 window
observables from the raw `.set` files (`max|Δ| = 0.000e+00` across `M`, `J`, `V`, `D`, `J_res`),
the `V`-on-ramp scaling law at three values of N, the noise-amplification identity, window and
burn-in geometry (`floor((N−burn_in)/T)`), PVT target direction conventions, bootstrap CI
containment, reproduction of `R_approx` from the per-subject table, and a scan confirming **no
PVT column reaches `outputs/dynamic_audit/`**.

New files: `outputs/dynamic_audit/` (5 CSV + 4 plots), `outputs/pvt_psychometrics/` (4 CSV +
2 plots), `src/dynamic_mechanism.py`, `src/pvt_psychometrics.py`, `scripts/20`–`24`.
`SCIENTIFIC_SPEC.md` §17 added; §8.2 and §9 corrected.
