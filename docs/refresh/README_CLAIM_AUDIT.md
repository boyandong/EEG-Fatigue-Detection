# README claim audit

Every substantive scientific claim in the public Markdown, with its evidentiary basis. Produced by
the 2026-09-22 canonicalization to verify that no sentence promises more than an artifact supports,
and extended by the final-framing pass.

**Result: no unsupported claim found.** Six wording risks were corrected across the two passes;
all are recorded in §3.

Method: read every public `.md` outside `archive/legacy/`; extract sentences asserting a scientific
result, capability or absence; require each to map to an artifact. Every check in §0 is
machine-enforced by `docs/verify_public_numbers.py` (127/127 passing), so a regression fails the
build rather than going unnoticed.

---

## 0. Mandated phrase audit

Each phrase was searched across every public Markdown file. **Status** distinguishes a *claim*
(a scientific assertion) from a *quotation* (the phrase appearing inside a prohibition, a
forbidden-wording column, or an explicit disclaimer).

| phrase | occurrences | status | file(s) | evidence source | allowed? | notes |
|---|---|---|---|---|---|---|
| **collapse** | several | **NOT asserted as the Phase 1 result** | `tta_collapse/README.md` §3, §8; `docs/validation-protocols.md` §9; `docs/scientific-status.md` | `collapse_verdict.json` — `tent_literal_collapse: false`, `tent_det_collapse: false`, `bn_only_collapse: false` | **yes, only as a defined term or a negation** | Appears as (a) the frozen two-part *definition*, (b) "no harmful collapse", (c) an explicit "never write 'TENT collapses'". The branch is *named* `tta_collapse`; the name is not a result |
| **causes** | 1 relevant | **NOT asserted** | `docs/scientific-status.md` (forbidden column) | no intervention experiment exists | **yes, only negated** | "BN causes the degradation" appears solely as a forbidden overclaim |
| **attributable** | 2 | **removed from the public claim** | — | `literature` | **no longer used for the TTA result** | Replaced by "sufficient to reproduce"; the one surviving use is `PHASE2_REPORT.md`'s unrelated "not attributable to a 60 s measurement" |
| **normalization instability** | several | **asserted, scoped** | `tta_collapse/README.md`, `docs/scientific-status.md` | `KEY_FINDINGS.json` four-arm table | **yes** | Permitted as *attribution* ("instability is not specific to entropy-gradient updates"), never as mechanism |
| **predicts PVT** | 0 as a claim | **absent** | — | — | **correctly absent** | The result is a *negative*; the phrase would invert it |
| **predicts vigilance** | 0 as a claim | **absent** | — | — | **correctly absent** | Appears only in the "What Is Not Yet Demonstrated" list |
| **generalizes** | 0 as a claim | **absent** | — | — | **correctly absent** | Negated in the root README |
| **robust** | 0 | **absent** | — | — | **correctly absent** | Not used anywhere as a property of a model |
| **validated** | several | **scoped** | `docs/scientific-status.md`, branch READMEs | per-row artifacts | **yes, only with a named scope** | Used only as `VALIDATED FOR ENDPOINT ELIGIBILITY` (the BCIT endpoint) and for the trunk. **Never** "validated biomarker" or "validated predictor" |
| **biomarker** | 1 | **negated** | `functional_prediction/README.md` | Phase 1 | **yes, only negated** | "`M` is NOT a validated vigilance biomarker" |
| **deployment-ready** | 0 as a claim | **absent** | — | — | **correctly absent** | Negated in the root README |
| **state-of-the-art** | 0 | **absent** | — | — | **correctly absent** | — |
| **published** | ~150 | **retained only where it means "shipped in this repository"** | all docs | — | **yes, with the distinction below** | See §3.5 — two internal-artifact uses were corrected; the file/artifact senses are correct and were kept |
| **"third-party code is referenced, not vendored"** | 0 | **REMOVED — was false** | — | `docs/third-party-provenance.md` | **no longer used** | Replaced by the two-part statement in §3.6 |

### Required confirmations

| must be confirmed | result |
|---|---|
| "collapse" is **not** asserted as the Phase 1 result | **CONFIRMED** — asserted as *absent* in every arm; `*_collapse: false` in all four |
| "BN causes degradation" is **not** asserted | **CONFIRMED** — causation explicitly denied; only sufficiency of the switch is claimed |
| "published" is not used ambiguously for internal artifacts | **CONFIRMED** — 2 occurrences corrected; a machine guard now fails the build if "stand as published" returns |
| the legacy third-party exception is disclosed | **CONFIRMED** — root README + `docs/third-party-provenance.md` §1 summary statement |
| lane-centre sign-test count is **4**, not 5/5 | **CONFIRMED** — derived from `lane_geometry.json` by the verifier (4 sign-tested recordings), and all public prose says 4 |

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

### 3.5 "published" could read as "peer-reviewed", and no longer can

`published` was being used for two different things: (a) *shipped in this repository*, and (b)
*appeared in a paper*. Sense (a) is legitimate and accounts for ~150 occurrences (published files,
published tree, published artifacts) — those were **kept**, because replacing them would be churn
without benefit.

Two uses of sense (b) were **wrong**, because no paper exists:

* `docs/project-history.md` — "Phase 4A and 4A2 **stand as published**" → "**remain scientifically
  valid under their frozen protocols**"
* `functional_prediction/evidence/phase4a3/…` — the same phrase in two inherited artifacts →
  the same correction

A machine guard now fails the build if "stand as published" or "valid, published, closed" returns.

### 3.6 "Third-party code is referenced, not vendored" was false, and was removed

The claim was true of the **active** trees and false of the **archive**, which retains four
third-party-derived components with missing notices. A blanket statement is therefore not
permissible. Replaced with the two-part statement:

> Active research code references pinned external implementations rather than vendoring them. The
> legacy archive retains several historical third-party-derived components whose upstream provenance
> and licensing are still being audited; no repository-wide license is therefore asserted.

Recorded in the root README and as the summary statement of `docs/third-party-provenance.md` §1.

### 3.7 License and citation were entangled, and are now separate

The README previously implied that an unlicensed repository cannot be cited. Those are independent
matters, and conflating them would understate the project's citability. The sections are now
distinct: **License** states that no repository-wide grant is made while provenance is unresolved;
**Citation** states that there is no DOI yet but that the repository URL and commit SHA are the
reference, and that absence of a license does not itself prevent citation.

### 3.8 `CASE 4` was the headline of the public result, and is now a parenthetical

The root README and status table now state the **scientific meaning** first — "EXECUTED / VERIFIED;
no harmful collapse; normalization-switch degradation established" — with "(internally classified as
Case 4)" appended. A machine guard asserts the label never appears in the root README as `CASE 4`.

## 4. Standing rule

When a number or status changes, this file changes with it, and
`docs/verify_public_numbers.py` must still pass. A claim that cannot be traced to an artifact does
not belong in a public README — and if it is worth keeping, the artifact is what needs publishing
first.
