# PHASE2_REPORT.md — Predictive modelling of personal-baseline-relative EEG vs objective vigilance decline

Branch: `vigilance_generalization_v1`. Frozen specification: [`SCIENTIFIC_SPEC.md`](SCIENTIFIC_SPEC.md) §18.
Builds on [`PHASE1_REPORT.md`](PHASE1_REPORT.md), [`PHASE1_5_REPORT.md`](PHASE1_5_REPORT.md),
[`PHASE1_75_REPORT.md`](PHASE1_75_REPORT.md).

**Core question:** can personal-baseline-relative EEG predict objective vigilance decline in an
unseen subject?

## Headline

> **The primary confirmatory hypothesis fails, and it is a clean failure.**
> `Q²_skill` for `M1` (`X_M`, B0/T60 → `Y_speed`) = **−0.0574**, permutation
> **p = 0.7445** (3722/5000 null replicates were at least as good), bootstrap 95 % CI
> **[−0.138, −0.009]**. **No model in the ladder beats the no-EEG baseline.**
> This is **pre-registered Case C**.

---

## A. Frozen protocol verification

Everything below was fixed in `SCIENTIFIC_SPEC.md` §18 **before** fitting, and independently
re-checked afterwards by `scripts/31_verify_phase2.py`.

| frozen element | value | verified |
|---|---|---|
| primary target | `Y_speed = ln(Q_NS/Q_SD)`, `Q = mean(1/RT)`, 100–2000 ms | ✓ task 5 |
| secondary target | `Y_RT = ln(medianRT_SD/medianRT_NS)` | ✓ |
| primary protocol | `P_M = (B=0 s, T=60 s)` → 15 epochs from recording start | ✓ task 4 |
| dynamic protocol | `P_J = (B=60 s, T=60 s)` | ✓ |
| `X_M` | `[ΔM_F, ΔM_CT, ΔM_PO]` — confirmatory | ✓ 3 predictors |
| `X_J` | `[ΔlogJ_F, ΔlogJ_CT, ΔlogJ_PO]` — exploratory incremental | ✓ `M3` = `M2` + exactly 3 |
| α grid | `{0.01, 0.1, 1, 10, 100}`, fixed, not extended | ✓ all chosen α ∈ grid |
| CV | outer LOSO(29) × inner LOSO(28); scaling + α selection inside the outer training fold | ✓ |
| endpoint | `Q²_skill = 1 − SSE_model/SSE_M0` | ✓ recomputed from predictions |
| inference | permutation B=5000 (full pipeline re-run) + bootstrap B=10000 | ✓ |
| `V`, `J_res` | audit variables only, **never predictors** | ✓ feature blocks are only `X_M`, `X_M+X_J` |

Additional verified invariants: `M0` equals the leave-one-out outer-train mean in **every** fold
(max diff 0.00e+00); one α per outer fold; no feature selection, no extra features, no second
algorithm, no protocol re-tuning, no disattenuation (`phase2_summary.json` flags all asserted).

**Corrections made to the record before modelling** (per your review):
* `SCIENTIFIC_SPEC.md` §17.2.2 — the "`V` has an intrinsic 1/N recording-length penalty"
  statement is **withdrawn**. For fixed per-step slope `V = |b|/√2`, independent of `N`; for
  `S(t)=a+qt` at fixed stride `Δt`, `V = |q|Δt/√2`. The apparent 1/N came from holding the total
  span fixed. Correct statement: `V` is sensitive to **epoch stride Δt**, and every future
  dataset must fix **epoch = 4 s, stride = 4 s**. `V` is still excluded from the predictor, but
  now for the correct reason — measured reliability (`PHASE1_75_REPORT.md` §B).
* `SCIENTIFIC_SPEC.md` §17.7 — the median-RT discrepancy is **no longer "unexplained"**. The
  project's PVT audit found recomputed paired statistics `t ≈ 0.042 / −7.308 / −4.715` against
  the paper's printed median RT → 0.04, RT SD → −7.31, lapses → −4.72, i.e. numerically equal but
  **cyclically mis-assigned to labels**. The paper's textual median-RT statistic is therefore
  **not** used to validate our reconstructed target's direction or magnitude.

---

## B. Primary `Y_speed` psychometrics (context, from Phase 1.75)

29 subjects; per-session valid trials NS 44–95 (median 48), SD 45–92 (median 50).

| quantity | value |
|---|---|
| point estimate, mean ± SD | +0.1188 ± 0.0962 |
| mean bootstrap SE | 0.0407 |
| SE / between-subject SD | 0.423 |
| 95 % CI excludes 0 | 19 / 29 subjects |
| `R_approx` (finite-trial) | **0.813** |
| split-half (odd/even, Spearman–Brown) | 0.856 |

`R_approx` is an **approximate finite-trial reliability proxy**, explicitly **not** test–retest
reliability. **No disattenuation was applied anywhere.**

**Consequence for this report, stated in advance:** the observable ceiling on any predictor of
`Y_speed` is bounded by this reliability. A null result here is therefore *partly* expected even
if a true association existed — which is exactly why the interpretation matrix distinguishes
duration-mediated failure (Case B) from representation failure (Case C).

---

## C. M0 baseline

`M0` predicts, for each held-out subject, the **mean `Y_speed` of that fold's 28 training
subjects**. No EEG. Verified to equal the leave-one-out training mean in all 29 folds.

| quantity | value |
|---|---|
| `SSE_M0` | **0.27780** |
| `MAE_M0` | 0.0754 |
| `SD(Y_speed)` | 0.0962 |

This is the bar: *"for a new user, guess the population-average impairment."* It is a
deliberately hard baseline for a between-subject prediction problem, because between-subject
variance in `Y_speed` is the only signal available.

---

## D. M1 primary nested-LOSO result

`M1`: `Y_speed ~ [ΔM_F, ΔM_CT, ΔM_PO]`, protocol `B0/T60`, outer LOSO(29) × inner LOSO(28).

| endpoint | value | 95 % bootstrap CI |
|---|---|---|
| **`Q²_skill`** | **−0.0574** | **[−0.138, −0.009]** |
| `MAE` | 0.0778 | — |
| `Skill_MAE` | **−0.0317** | [−0.065, −0.005] |
| `Spearman(Ŷ, Y)` | **−0.755** | [−0.860, −0.503] |
| `SSE_model / SSE_M0` | **1.0574** | — |
| α selected | 100 in **29/29** folds | — |

**Reading.** The EEG model's held-out error is **5.7 % larger** than simply predicting the
training-set mean. The 95 % CI on `Q²_skill` lies **entirely below zero**, so this is not a
"positive but underpowered" result — it is a point estimate on the wrong side of the baseline.

The large negative Spearman is **not** evidence of a reversed relationship; it is a known
geometric consequence of the baseline. `M0` is the per-fold training mean, which is
mechanically anti-correlated with the held-out subject's own deviation from it. The model's
predictions have SD 0.0087 against `Y`'s SD 0.0962 — i.e. ridge with α = 100 shrinks almost
everything away, and the residual training-set-specific variation it does inject is *not* shared
by the held-out subject. That is precisely the signature of fitting noise.

**Why α = 100 in every fold is itself informative:** the inner LOSO systematically prefers the
heaviest penalty on the frozen grid. Given 28 training subjects and 3 predictors, that means the
training folds contain no cross-validatable linear structure to fit. Had a smaller α been
selected, the model would be claiming to have found structure; it did not.

---

## E. 60 s vs full-duration sensitivity

| model | protocol | epochs | `Q²_skill` | `Skill_MAE` | Spearman |
|---|---|---|---|---|---|
| **`M1`** | B0/T60 (first 60 s) | 15 | **−0.0574** | −0.0317 | −0.755 |
| **`M1_full`** | full session (230–320 s) | 57–74 | **−0.0106** | −0.0217 | −0.397 |
| `M2` | B60/T60 (60–120 s) | 15 | −0.0454 | −0.0267 | −0.718 |

The full-session model is the **best** in the whole ladder — it recovers most of the gap
(−0.011 vs −0.057) — but it still **does not exceed zero**, and its CI
[−0.098, +0.038] spans zero from below.

**This is the decisive row of the report.** Case B ("60 s too short, longer works") requires
`M1_full > M0`. It does not hold. Using **four to five times more EEG** — the entire usable
recording rather than a 60 s window — still fails to beat the no-EEG baseline. So the failure is
**not** attributable to a 60 s measurement being too short.

---

## F. `Y_RT` secondary result

Same protocol and pipeline, secondary target.

| model | `Q²_skill` | CI | `Skill_MAE` | Spearman |
|---|---|---|---|---|
| `M1_RT` (B0/T60) | −0.0588 | [−0.116, −0.023] | −0.0257 | −0.865 |
| `M1_full_RT` (full) | −0.0487 | [−0.176, +0.019] | −0.0210 | −0.629 |

Same pattern, slightly worse. The null does **not** depend on which target is used, which is
expected given the two targets correlate strongly by construction (both are session-pair
response-latency changes) and neither was chosen on EEG grounds.

---

## G. Dynamic incremental value — M3 vs M2

Both use the **same** `B60/T60` window, so the contrast isolates `X_J` and not measurement
position.

| model | predictors | `Q²_skill` | `Skill_MAE` | Spearman |
|---|---|---|---|---|
| `M2` | `X_M` (3) | −0.0454 | −0.0267 | −0.718 |
| `M3` | `X_M + X_J` (6) | **−0.0879** | −0.0423 | −0.762 |
| **Δ (M3 − M2)** | | **−0.0425** | −0.0156 | −0.044 |

> **`M3 ≤ M2`: adding the dynamic block makes held-out prediction worse, not better.**
> `J` therefore **does not justify the additional 60 s burn-in / acquisition burden** under this
> protocol. This is the pre-registered conclusion for this branch of the matrix, and it is a
> genuinely useful engineering result: the deployment protocol can be shortened to **60 s from
> recording onset**, with the dynamic family dropped.

Consistent with Phase 1.75, where `ΔlogJ` had the worst estimator stability of the three
candidates (`nMAE ≥ 0.74` even at 120 s).

---

## H. Permutation null

`M1 → Y_speed` only (the confirmatory hypothesis). Subject-level permutation of `Y`;
**each of the 5000 replicates fully re-ran outer LOSO + inner LOSO + scaling + α selection**
(0.059 s/replicate, i.e. ~600× a single ridge fit — confirming the full pipeline was re-run, as
independently checked).

| quantity | value |
|---|---|
| `Q²_observed` | −0.0574 |
| null mean ± SD | −0.0361 ± 0.0648 |
| null range | [−0.376, +0.403] |
| null quantiles (1, 5, 25, 50, 75, 95, 99) | −0.211, −0.147, −0.058, −0.032, −0.014, +0.054, +0.202 |
| `#(Q²_perm ≥ Q²_obs)` | **3722 / 5000** |
| **`p_perm`** | **0.7445** (resolution 0.0002) |
| fraction of null with `Q² > 0` | 15.3 % |
| seed | 20260916 (full null saved to `permutation_null.npz`) |

**Reading.** The observed value sits **above the median of its own null** (median −0.032).
The null distribution's mean is itself negative — under nested CV with no signal, the honest
expected out-of-sample skill of a fitted ridge on 28 subjects *is below zero*, because the model
must estimate 3 coefficients it cannot validate. Only 15.3 % of null replicates reached `Q² > 0`,
which quantifies how hard this design is: **even pure noise rarely yields positive skill here**.

This is the correct benchmark, and it makes the failure unambiguous: the real EEG does no better
than shuffled EEG.

---

## I. Confidence intervals

Subject-level bootstrap over the `(Y, Ŷ, Ŷ_M0)` tuple, B = 10000, seed 20260916. Features were
**not** re-selected inside the bootstrap.

| model | `Q²_skill` [95 % CI] | `Skill_MAE` [95 % CI] | Spearman [95 % CI] |
|---|---|---|---|
| `M1` | −0.0574 [−0.138, −0.009] | −0.0317 [−0.065, −0.005] | −0.755 [−0.860, −0.503] |
| `M1_full` | −0.0106 [−0.098, +0.038] | −0.0217 [−0.069, +0.015] | −0.397 [−0.648, −0.055] |
| `M2` | −0.0454 [−0.090, −0.019] | −0.0267 [−0.054, −0.004] | −0.718 [−0.852, −0.437] |
| `M3` | −0.0879 [−0.158, −0.027] | −0.0423 [−0.074, −0.012] | −0.762 [−0.885, −0.498] |
| `M1_RT` | −0.0588 [−0.116, −0.023] | −0.0257 [−0.046, −0.007] | −0.865 [−0.937, −0.645] |
| `M1_full_RT` | −0.0487 [−0.176, +0.019] | −0.0210 [−0.066, +0.017] | −0.629 [−0.793, −0.335] |

Every primary/secondary `Q²_skill` CI lies below or straddling zero; **none excludes zero from
above**. `M1_full` is the only model whose CI crosses zero, and its point estimate is still
negative.

---

## J. Confound sensitivity

Secondary analysis, identical outer-LOSO discipline, all scaling and fitting inside the training
fold. `n = 29` for both (timing metadata was available for all 29).

| model | predictors | `Q²_skill` | `Skill_MAE` |
|---|---|---|---|
| `C0` | `SessionOrder + ΔClock` | −0.0147 | −0.0088 |
| `C1` | `SessionOrder + ΔClock + X_M` | −0.0743 | −0.0403 |
| **Δ (C1 − C0)** | | **−0.0596** | −0.0315 |

> **`C1 < C0`.** Adding `X_M` to the protocol variables makes prediction **worse**. There is no
> evidence that EEG carries information beyond `SessionOrder` and the EEG clock-time gap — and
> neither of the two confound models beats `M0` either. So this analysis provides no support for
> EEG incremental value; it also does not accuse the EEG of merely proxying protocol variables,
> because those protocol variables carry no predictive signal to transmit.

---

## K. Reliability-aware interpretation

Per instruction, **no disattenuated correlation was computed** and no `r/√(R_x R_y)` correction
was applied.

What the reliability context legitimately says:

* `R_approx(Y_speed) = 0.813` (approximate finite-trial proxy). Any true association between
  `X_M` and the *latent* vigilance change would be observed at roughly `√0.813 ≈ 0.90` of its
  true size.
* So behavioural noise **alone** cannot explain `Q²_skill = −0.057`. A near-zero true association
  attenuated by 10 % is still near zero; attenuation does not turn a positive effect into a
  reliably **negative** out-of-sample skill.
* Conversely, the reliability ceiling does bound what any future positive result could mean:
  `Q²_skill` here is measured against a *noisy* target, so a genuinely useful predictor of the
  latent state would still post a modest `Q²`. That is a reason to keep the endpoint as
  `Q²_skill` against `M0` rather than to expect large numbers.

The univariate context is consistent: individual correlations of `ΔM_F / ΔM_CT / ΔM_PO` with
`Y_speed` are `+0.03 (p=0.87) / +0.15 (p=0.44) / +0.19 (p=0.32)`. **These were viewed only
after the frozen analysis had run, as a diagnostic to confirm the null was not a coding artefact;
they were not used to select anything and no model was refitted on the basis of them.**

---

## L. Scientific conclusion

**Pre-registered Case C applies.**

\[
M1_{60s}\le M0 \quad\text{and}\quad M1_{full}\le M0
\]

> **The current Mechanism-v2 tonic representation does not demonstrate out-of-sample predictive
> value in this dataset.**

Per the interpretation matrix, the permitted claim is exactly that — and **nothing further was
attempted**: no additional feature, no second algorithm, no protocol change, no feature search
until significance.

**Why this failure is informative rather than merely negative.** Each of the ordinary escape
routes has been closed *before* running the model, by the earlier phases:

| possible excuse for the null | closed by | status |
|---|---|---|
| "the feature extractor is written wrong" | Phase 1: 26 verification checks; Phase 1.5/1.75: 26 + 44 checks, including recomputation of all window observables from raw `.set` (`max|Δ| = 0.000e+00`) | closed |
| "60 s is simply too short" | §E: `M1_full` uses 4–5× more data and **still** fails | closed |
| "the mechanism is there but the target is too noisy" | §B/§K: `R_approx = 0.813`; attenuation cannot manufacture a reliably negative skill | not fully closed, but bounded |
| "NS/SD labels leaked, inflating results" | n/a — this is not a classification task; the primary endpoint is out-of-sample `Q²_skill` against a no-EEG baseline | closed |
| "the model is under-regularised / overfit" | inner LOSO chose **α = 100, the heaviest penalty, in 29/29 folds** | closed |
| "the dynamic family was dropped unfairly" | §G: `M3 < M2`; adding `X_J` makes it worse | closed |
| "protocol / position artefact" | §A: B0/T60 fixed a priori; `M2` at B60/T60 gives the same conclusion | closed |

What remains genuinely open: whether the **latent** association exists but is invisible at this
sample size and target reliability. With `n = 29` and only 15.3 % of null replicates reaching
`Q² > 0`, this design **cannot** resolve a small effect. The correct statement is that the
representation has not been *shown* to predict — not that it has been shown *not* to.

---

## M. Exact next-step recommendation

**Stop the current line. Do not fit another model on these 29 subjects.** Additional modelling on
this sample would be fitting noise with extra steps.

Ranked by information gain per unit cost:

1. **Do not add features, algorithms, or protocols.** The ladder already covers the frozen
   hypothesis space, and the failure is consistent across every cell. Any further search is the
   researcher-degrees-of-freedom failure mode this whole design was built to prevent.
2. **Treat the remaining live question as a power/target problem, and price it explicitly.**
   The one unclosed excuse is "true effect exists but is unresolvable". Resolving it requires
   either (a) more subjects with paired PVT, or (b) a lower-noise target — not a better model.
   Both are data-collection decisions, not analysis decisions.
3. **The `official_raw_recovery_plan.md` branch is now the highest-value technical step**, because
   it addresses the two remaining provenance limits at once: eyes-open status would come from a
   `task-eyesopen` entity rather than a filename family, and the preprocessing would become ours
   and reproducible. It does **not** fix power, and it should not be sold as if it would.
4. **What is worth writing up now, with no further modelling:** the measurement-audit chain
   itself. Three phases established that `M` is a stable, gain-invariant, short-duration tonic
   spectral proxy (32 s ρ = 0.82, position-stable), that `J` is a *mixture* whose short-duration
   estimates are unusable, that `V` trades drift-sensitivity for noise and is worse, that the
   target carries `R_approx ≈ 0.81`, and that on 29 subjects with this target **none of it
   predicts out-of-sample**. That is a coherent, honest, negative result with a fully specified
   protocol — and it is a much stronger contribution than the original "0.59 NS/SD accuracy".

**Explicitly not done, per the hard stop:** no second algorithm, no added features (no `V`, no
`J_res`, no aperiodic, no demographics), no protocol re-tuning, no SADT download, no
cross-dataset work, no TTA.

---

## Reproduce

```powershell
cd project/vigilance_generalization_v1
$env:OMP_NUM_THREADS=1; $env:OPENBLAS_NUM_THREADS=1
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 tests/test_phase2_ridge.py     # 22/22
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/30_phase2_models.py --n-perm 5000 --n-boot 10000 --workers 10
& <ENV_ROOT>/envs/braindecode/python.exe -X utf8 scripts/31_verify_phase2.py    # 43/43
```

Runtime: unit tests ~5 s; modelling **299 s** (296 s of which is the permutation null); verification ~30 s.

### Verification summary

* `tests/test_phase2_ridge.py` — **22/22**. The hand-written SVD ridge equals `sklearn.linear_model.Ridge`
  to **1e-16** across 25 configurations plus a collinear design; the scaling boundary is checked;
  nested LOSO gives `Q² ≤ 0` on noise and `Q² > 0.5` on a real signal.
* `scripts/31_verify_phase2.py` — **43/43**, including:
  * the primary feature matrix **re-derived from the raw `.set` files** (`max|Δ| = 0.000e+00` for
    all three `ΔM` coordinates) — this closes the whole Phase 1 → 1.75 → 2 hand-off;
  * `Y_speed` **re-derived from the raw PVT trial files** (`max|Δ| = 0.000e+00`), with the
    100–2000 ms rule confirmed intact;
  * every endpoint recomputed from `predictions.csv`;
  * the nested LOSO **reproduced with sklearn Ridge** (predictions max|Δ| = 2.8e-17, identical α
    selection);
  * `p_perm` recomputed from the stored null array; observed `Q²` present in the `.npz`;
  * per-replicate cost 0.059 s, confirming full-pipeline re-runs rather than a cached shortcut.

### Files

`outputs/phase2/`: `features_used.csv`, `model_results.csv`, `predictions.csv`,
`alpha_selection.csv`, `permutation_null.npz` (5000 values), `permutation_summary.json`,
`bootstrap_ci.json`, `confound_sensitivity.csv`, `phase2_summary.json`.
New code: `src/phase2_models.py`, `scripts/30_phase2_models.py`, `scripts/31_verify_phase2.py`,
`tests/test_phase2_ridge.py`. Modified: `SCIENTIFIC_SPEC.md` (§17.2.2 correction, §17.7
resolution, new §18), `PHASE1_75_REPORT.md` (two corrections).
