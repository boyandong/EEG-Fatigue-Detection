# README claim audit

Every substantive scientific claim in the public Markdown, with its evidentiary basis. Produced by
the 2026-09-22 canonicalization to verify that no sentence promises more than an artifact supports.

**Result: no unsupported claim found.** Three wording risks were corrected during the audit and are
recorded in §3.

Method: read every public `.md` outside `archive/legacy/`; extract sentences asserting a scientific
result, capability or absence; require each to map to an artifact.

---

## 1. Claims in the root `README.md`

| # | claim | file | status | evidence source | allowed? | notes |
|---|---|---|---|---|---|---|
| 1 | 68 valid subjects, 9,390 four-second windows, 61 channels, 500 Hz | README | VALIDATED | `shared/.../source_only_500hz_v1/{subjects.csv,segments.csv,channels.json}` | **yes** | machine-checked by `verify_public_numbers.py` |
| 2 | subject-level LOSO evaluation | README | VALIDATED | `splits.json` (68 folds, seed 20260908) | **yes** | |
| 3 | EEGNet Acc 0.5963 / BAcc 0.5924 / F1 0.5550 / AUC 0.6109 | README | VALIDATED | `summary_variability.csv`; `KEY_FINDINGS.json` | **yes** | scoped by the next row |
| 4 | "These results establish a limited condition-related EEG signal. They do **not** establish functional prediction." | README | VALIDATED (as a scope limit) | `PHASE2_REPORT.md` | **yes** | the scope sentence is what makes row 3 safe |
| 5 | `Q² = −0.0574`, nested permutation `p = 0.7445`, n = 29 | README | VALIDATED | `evidence/phase2/{permutation_summary.json,phase2_summary.json}` | **yes** | |
| 6 | "did not outperform a no-EEG baseline" | README | VALIDATED | negative `Q²` vs `M0` | **yes** | |
| 7 | "does not demonstrate out-of-sample utility for predicting PVT deterioration **in this dataset and protocol**" | README | VALIDATED | Phase 2 | **yes** | the qualifier is load-bearing |
| 8 | "It is **not** evidence that EEG can never predict PVT." | README | **required** negative scope | Phase 2 | **yes** | prevents the forbidden generalization |
| 9 | "branch was stopped rather than extended through additional post-hoc feature or model search" | README | VALIDATED (process fact) | `SESSION_HANDOVER.md`; Phase 2 KILL list | **yes** | |
| 10 | "Lane-control semantics were audited before EEG modeling" | README | VALIDATED | `phase3c/outputs/{lane_geometry.json,lane_endpoint_definition.json}` | **yes** | |
| 11 | "both BN-only adaptation and TENT degraded relative to the frozen source model" | README | VALIDATED | `KEY_FINDINGS.json` four-arm table | **yes** | |
| 12 | "the observed failure cannot be attributed specifically to entropy-gradient updates" | README | VALIDATED | `literal_minus_bn_only_bacc`: +0.00048, t = +0.22 | **yes** | |
| 13 | "does not establish that BatchNorm is the causal mechanism" | README | **required** scope limit | no intervention experiment exists | **yes** | see §3.1 |
| 14 | "nor that TENT universally collapses on EEG" | README | **required** scope limit | `collapse_verdict.json`: `tent_literal_collapse: false` | **yes** | see §3.2 |
| 15 | "816/816 unit checks; 105/105 branch-verifier checks … refer to implementation verification, not experimental sample size" | README | VALIDATED + correctly scoped | `KEY_FINDINGS.json` `verification` | **yes** | see §3.3 |
| 16 | "0 of 82,550 evaluated rows entered any modeling mask" | README | VALIDATED | `mask_definitive.json` | **yes** | |
| 17 | "the numerical effect of the correction was approximately `1e-15`" | README | VALIDATED | `clean_standard_run.json` `contamination_delta_population.mean_delta_R = −4.0e-15` | **yes** | |
| 18 | "Phase 4A/4A2 results therefore remain valid scientific evidence rather than invalidated runs" | README | VALIDATED | `phase4a3/outputs/` | **yes** | see §3.4 |
| 19 | "adaptive SFFS branch … did not establish a reliable positive effect, although its population-level null analysis was not sufficiently large for a stronger formal claim" | README | VALIDATED + correctly scoped | `adaptive_null_summary_FORMAL.json` — `K_per_participant: 8`, `p floor 0.111` | **yes** | see §3.5 |
| 20 | "No repository-wide software license has been assigned yet" | README | VALIDATED | no `LICENSE` file | **yes** | |

## 2. Forbidden claims — verified ABSENT

Each phrase below was searched across all public Markdown. **None appears outside a
`never write` / `forbidden` context**, where it is quoted as a prohibition rather than asserted.

| forbidden claim | present? | where it legitimately appears |
|---|---|---|
| "accurately detects fatigue" | **absent** | — |
| "predicts vigilance decline in unseen users" | **absent** | — |
| "predicts driving risk" / "predicts driving-performance deterioration" | **absent as a claim** | README "What Is Not Yet Demonstrated" (negated) |
| "EEG can predict PVT" | **absent as a claim** | README (negated) |
| "EEG cannot predict PVT" | **absent as a claim** | README (explicitly disclaimed) |
| "generalizes across datasets" | **absent as a claim** | README (negated) |
| "robust to unseen users" | **absent** | — |
| "TENT collapse is caused by BN" | **absent as a claim** | `scientific-status.md` forbidden column; `tta_collapse/README.md` §8 |
| "TENT collapses" | **absent as a claim** | `tta_collapse/README.md` §8 (prohibition) |
| "we solved TTA collapse" | **absent** | — |
| "deployment-ready" | **absent as a claim** | README (negated) |
| "real-time safety monitoring" | **absent** | — |
| "state-of-the-art" | **absent** | — |
| "validated biomarker" | **absent as a claim** | `scientific-status.md` forbidden column |
| "clinical application" | **absent** | — |
| "BMI" / "Brain-Computer Interface" | **absent** | — |

## 3. Corrections made during the audit

### 3.1 The TTA section could have overclaimed, and did not

The verified result is easy to overstate as *"BatchNorm causes TTA collapse."* The README instead
states attribution only and explicitly denies causation. This is the correct reading: the experiment
establishes that the **gradient-free `BN_ONLY` control reproduces the entire degradation**, which
rules *out* entropy minimisation as necessary — but attribution-by-elimination is not a mechanism.
Establishing causation needs an intervention (e.g. freezing BN statistics while keeping the entropy
step) that has not been run.

### 3.2 "Collapse" had to be actively avoided

The branch is named `tta_collapse` and its verdict string contains "INSTABILITY", which invites
writing "collapse". But `collapse_verdict.json` records `tent_literal_collapse: false`,
`tent_det_collapse: false`, `bn_only_collapse: false`, and the diversity metrics move *opposite* to
the collapse signature. The README therefore says "degraded to near chance" and never "collapsed".

### 3.3 Verification counts were separated from sample size

`816/816` and `105/105` are check counts. Presented next to an experimental result without a
qualifier they read as sample size. The README now states explicitly that they are
implementation-verification counts and gives the real sample (68 × 3 × 4, subject-level `n = 68`).

### 3.4 An earlier draft of this repository carried the wrong BCIT status

A prior public draft marked Phase 4A/4A2 as **INVALIDATED by gap contamination**. The authoritative
Phase 4A3 artifacts refute that (`0 of 82,550` rows in any mask; `ΔR ~ 1e-15`). Publishing it would
have been the most serious overclaim in the repository — not an exaggeration of success, but a false
statement of failure that discards valid negative evidence. Corrected.

### 3.5 The Phase 4A2 wording was strengthened *and* bounded

The first correction ("inert, so valid") risked tipping into "the adaptive effect was disproven."
The calibrated null's `K = 8` and p-floor of `0.111` do not support that. The README now says "did
not establish a reliable positive effect" and names the null's limitation in the same sentence.

## 4. Standing rule

When a number or status changes, this file changes with it, and
`docs/verify_public_numbers.py` must still pass. A claim that cannot be traced to an artifact does
not belong in a public README — and if it is worth keeping, the artifact is what needs publishing
first.
