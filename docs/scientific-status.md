# Scientific status

One compact table of what this project has and has not established. **Every row cites the artifact
it is derived from.** If a claim is not in this table, it is not a claim this repository makes.

Verification vocabulary, used strictly and never loosely:

| term | meaning |
|---|---|
| **VALIDATED / ESTABLISHED** | executed, independently verified, and reproducible from the published artifacts |
| **NEGATIVE** | a valid, pre-specified test in which the apparatus passed verification but the hypothesis was not supported — a *result*, not a failure of the apparatus. **This does not assert statistical power**: the project has run no formal power analysis, so "well-powered" is not a claim any row below makes |
| **REFUTED** | a *suspicion or correction* that was itself tested and not supported |
| **IN PROGRESS** | designed or partially executed; no verdict yet |
| **NOT DEMONSTRATED** | never tested at the required standard; absence of evidence |
| **PARKED** | deliberately not started; no artifact exists |

---

## 1. Master status table

| # | claim | status | evidence artifact | allowed public wording | forbidden overclaim |
|---|---|---|---|---|---|
| 1 | ds004902 source trunk exists: 68 valid paired subjects, 9,390 four-second windows, 61 channels, 500 Hz, 68-fold subject-LOSO | **VALIDATED** | `shared/.../source_only_500hz_v1/{segments.csv,subjects.csv,channels.json,splits.json,verification.json}` — `verification.json: status=passed` | "a reproducible cross-subject EEG trunk on 68 subjects" | "the dataset is clean" / "the cohort is representative" |
| 2 | Legacy source-only EEGNet condition benchmark: Acc 0.5963, BAcc 0.5924, F1 0.5550, AUC 0.6109 | **VALIDATED** | `archive/.../formal_autodl_v1/summary_variability.csv`; reproduced in `tta_collapse/evidence/metrics/KEY_FINDINGS.json` | "a historical source-only EEGNet baseline on a condition-classification task" | any claim that this is a *vigilance* result |
| 3 | A tonic spectral representation `M` is reproducibly measurable over short recordings | **VALIDATED** (as a measurement property only) | `functional_prediction/PHASE1_REPORT.md` | "reproducibly measurable" | "validated vigilance biomarker" |
| 4 | `M` carries out-of-sample information about PVT deterioration | **NEGATIVE** | `functional_prediction/evidence/phase2/{permutation_summary.json,phase2_summary.json}` — `Q²_skill(M1) = −0.0574`, `p_perm = 0.7445`, `n = 29` | "did not demonstrate out-of-sample utility for this representation, dataset and protocol" | **"EEG cannot predict PVT"** |
| 5 | Longer duration, an alternative PVT target, or a dynamic `J` extension rescues claim 4 | **NEGATIVE** | `functional_prediction/evidence/dynamic_audit/`, `PHASE1_75_REPORT.md` | "bounded diagnostics did not recover predictive skill" | "all EEG→PVT approaches fail" |
| 6 | The BCIT lane-control endpoint is physically and behaviourally coherent | **VALIDATED** | `functional_prediction/audit/phase3c/outputs/{lane_geometry.json,lane_endpoint_definition.json,endpoint_eligibility.json}`, `BEHAVIOR_ENDPOINT_SPEC.md` §3.2 | "`LN = 0` is the lane centre; half-width 0.9172 m" | "the endpoint measures safety" |
| 7 | The 2×2 BCIT condition labels are behaviourally recoverable | **REFUTED** | `phase3c/outputs/perturbation_endpoint.json` — rate factor varies only 1.08–1.18× | "not behaviourally recoverable" | any invented condition label |
| 8 | A time-on-task effect exists in BCIT baseline driving | **NOT DEMONSTRATED** | `phase3c/outputs/time_on_task_models.json` — naive `T_session` +0.088 ± 0.058 m/h; condition-aware F-test `p = 0.94` | "not established" | "fatigue degrades driving" |
| 9 | BCIT Phase 4A fixed historical baseline: mean R = −0.0499 over 25 participants / 149 folds | **VALID EXECUTION / NEGATIVE EVIDENCE** | `phase4a3/outputs/clean_standard_run.json`, `PHASE4A_HISTORICAL_BASELINE_REPORT.md` | "did not establish a reliable EEG→lane-performance signal" | presenting it as a positive result, or as invalidated |
| 10 | BCIT Phase 4A2 adaptive SFFS: mean ΔR = +0.0543, 15/25 positive, paired t `p = 0.140`, 0/25 decidable | **VALID EXECUTION / NO RELIABLE POSITIVE EFFECT** | `phase4a2/outputs/{adaptive_null_summary_FORMAL.json,adaptive_subject_results_FORMAL.csv}`, `PHASE4A2_ADAPTIVE_SFFS_REPORT.md` | "did not establish a reliable positive effect; the population-level null was not large enough for a stronger formal claim" | "definitively disproven" — the population null has `K = 8` |
| 11 | Inter-block gap contamination invalidated Phase 4A / 4A2 | **REFUTED** | `phase4a3/outputs/mask_definitive.json` — `total_gap_rows = 82550`, `…inside_phase4a_training_masks = 0`, `…inside_phase4a_test_masks = 0`; `clean_standard_run.json` — `mean_delta_R = −4.0e-15` | "the suspected contamination was found to be inert" | **"Phase 4A/4A2 are invalidated"** |
| 12 | The gap defect itself is real | **VALIDATED** | `phase4a2/GAP_CONTAMINATION_FINDING.md` (raises it), `phase4a3/outputs/GAP_CONTAMINATION_AUDIT.md` (confirms mechanism, refutes impact) | "real defect in the smoothing helper, no effect on any mask" | "the defect was imaginary" |
| 13 | Under the frozen ds004902 EEGNet protocol, BN-only adaptation and TENT both degrade relative to the frozen source model | **VALIDATED** | `tta_collapse/evidence/metrics/KEY_FINDINGS.json` — SOURCE 0.5924 vs BN_ONLY 0.5039 / TENT_LITERAL 0.5043 / TENT_DET 0.5035; `collapse_verdict.json` | "both normalization-only and entropy-minimizing adaptation degraded, and are indistinguishable from each other" | **"TENT collapses"** / **"BN causes the collapse"** |
| 14 | The degradation is attributable to entropy minimisation | **REFUTED** | `KEY_FINDINGS.json` — `literal_minus_bn_only_bacc.mean = +0.00048`, `t = +0.22`; the gradient-free control reproduces the effect | "the entropy gradient is inert" | "entropy minimisation caused it" |
| 15 | The degradation has the *collapse* signature | **REFUTED** | `KEY_FINDINGS.json` `last_quartile` — dominant share **falls** 0.7104 → 0.5414, marginal entropy **rises** 0.5358 → 0.6862 | "the diversity change runs opposite to a collapse signature" | "prediction collapse was observed" |
| 16 | BatchNorm statistics are the **causal** mechanism of the adaptation degradation | **NOT DEMONSTRATED** | no intervention experiment exists in the repository | "normalization behaviour is implicated as the first-order failure mode" | **"BatchNorm is the cause"** |
| 17 | Test-time adaptation reliably improves unseen-user EEG decoding | **NOT DEMONSTRATED** | — | nothing | any positive TTA claim |
| 18 | Any EEG model generalizes across independent datasets | **NOT DEMONSTRATED** | — | nothing | "generalizes" |
| 19 | EEG predicts driving-performance deterioration | **NOT DEMONSTRATED** | — | nothing | "predicts driving risk" |
| 20 | The system is deployment-ready / real-time / safety-certified | **NOT DEMONSTRATED** | — | nothing | **"deployment-ready"**, "real-time safety monitoring" |
| 21 | Anti-collapse methods (EATA, SAR, CoTTA, MEMO, T3A, DELTA, T-TIME, BFT, …) were evaluated | **PARKED** | no artifact exists — verified by `_refactor/80_verify_refactor.py` | "parked, not started" | describing any of them as completed |

---

## 2. The one-sentence version

> A reproducible cross-subject EEG trunk was built and a predefined tonic representation did not
> demonstrate out-of-sample PVT predictive skill; the suspicion that this invalidated a later
> behavioural-baseline family was itself tested and refuted; and under the frozen source model both
> normalization-only and entropy-minimizing adaptation degraded to near chance, **without harmful
> prediction collapse**, localizing the first-order failure to the normalization switch rather than
> the entropy update.

---

## 3. Naming note: what "CASE 4" is, and how it may be written

The internal session label `CASE 4 — BN/NORMALIZATION INSTABILITY` is the **frozen verdict string**
of an executed and verified experiment. It is recorded verbatim in
`tta_collapse/outputs/collapse_verdict.json` and `evidence/metrics/KEY_FINDINGS.json`.

**For public writing, the scientific meaning is stated first, and the internal label follows in
parentheses — never the other way round.** A reader must not need the internal case taxonomy to
understand the result:

> **TTA Phase 1 — EXECUTED / VERIFIED. No harmful collapse; normalization-switch degradation
> established.** Switching from frozen source BatchNorm statistics to target-batch statistics was
> sufficient to reproduce the observed degradation, while the entropy-gradient step produced no
> detectable additional degradation under this protocol. *(Internally classified as Case 4.)*

The branch README may retain the label as its heading, because a reader who reaches it has already
seen the meaning. The **root README and the status table state the meaning**, and the label appears
only as a parenthetical.

**Scope that must travel with it:** the verdict establishes *attribution*, not *mechanism*. It does
not establish that BatchNorm statistics are the causal mechanism (that needs an intervention
experiment), and it does not establish that TENT collapses universally on EEG. In this dataset, TENT
did not collapse at all — it degraded to chance, exactly as the gradient-free control did.

**Implementation verification vs. experimental sample size.** `816/816 units` and `105/105 verifier
checks` are **verification counts** and belong in reproducibility material, never presented as
sample size or effect. The experiment's sample is **68 subjects × 3 seeds × 4 arms**, and the
statistical unit for the paired contrasts is the **subject** (`n = 68`), not the window.

---

## 4. How to re-check this table

```bash
python docs/verify_public_numbers.py    # every number above, re-derived from its artifact
```

Rows 1–16 are machine-checked by that script against the published evidence. Rows 17–21 are
assertions of absence; the script checks the strongest available proxy — that the park list exists
and that no artifact is named for any parked method.
