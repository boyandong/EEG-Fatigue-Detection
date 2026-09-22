# GITHUB_FINAL_REVIEW.md

Final pre-publication pass on `repo-refresh-v2-20260922`, executed 2026-09-22 before its first push.
This document is the record of what the final pass changed and what it verified.

---

## 1. Files changed in this final pass

| file | change class |
|---|---|
| `README.md` | **added** `## Scientific Status` table; **split** `## Citation and License` into `## License` + `## Citation`; corrected third-party statement; removed "published" claim |
| `docs/project-history.md` | TTA causal wording; "stand as published" → "remain scientifically valid"; **lane-centre count 5/5 → 4** |
| `docs/scientific-status.md` | one-sentence summary; §3 naming note rewritten (meaning before label) |
| `docs/third-party-provenance.md` | added §1 summary statement + §5.1 owner decision (files stay) |
| `docs/data-boundaries.md` | third-party wording consistency |
| `tta_collapse/README.md` | TTA causal wording tightened; attribution vs cause made explicit |
| `functional_prediction/README.md` | verification wording |
| `functional_prediction/research_tree.md` | **dangling reference repaired** (§10) |
| `functional_prediction/evidence/phase4a3/GAP_CONTAMINATION_AUDIT.md` | "stand as published" → frozen-protocol wording |
| `functional_prediction/evidence/phase4a3/SESSION_HANDOVER_PHASE4A3.md` | **dangling reference repaired**; "stand as published" corrected; never-generated report marked |
| `docs/verify_public_numbers.py` | **+47 regression guards** (81 → 127 checks); `re` imported |
| `docs/refresh/README_CLAIM_AUDIT.md` | §0 mandated phrase table + required confirmations |
| `docs/refresh/REMAINING_MANUAL_GITHUB_ACTIONS.md` | history-strategy item rewritten |
| **new** `docs/refresh/TRACKED_FILE_SIZE_AUDIT.md` | size audit |
| **new** `docs/refresh/GITHUB_FINAL_REVIEW.md` | this file |
| **new** `docs/refresh/repair_dangling_report_reference.py` | the repair, as a re-runnable script |
| **new** `functional_prediction/evidence/phase3c/` (7 files, 0.19 MB) | lane-geometry and endpoint-eligibility artifacts, so the lane count is machine-derivable |

**No file was deleted.**

---

## 2. Exact scientific-language corrections

### 2.1 TTA causality — attribution, not cause

| before | after |
|---|---|
| "the degradation **is therefore attributable to** the test-batch normalisation switch" | "Switching from frozen source BatchNorm statistics to target-batch statistics was **sufficient to reproduce** the observed degradation, while the entropy-gradient step produced **no detectable additional degradation** under this protocol. That localizes the first-order failure to the normalization switch. It does **not** establish that BatchNorm statistics are the causal mechanism." |

Rationale: `TENT_LITERAL − BN_ONLY = +0.00048` (t = +0.22) rules entropy minimisation **out** as
necessary. Attribution-by-elimination is not mechanism. Establishing causation needs an intervention
that has not been run.

### 2.2 TTA result framing — no harmful collapse

Public summary now reads: *"No harmful prediction collapse was observed. Instead, BN-only and TENT
both degraded to near-chance performance, localizing the first-order failure to the normalization
switch rather than the entropy update."*

### 2.3 Case 4 demoted to a parenthetical

The internal label no longer requires the reader to know the case taxonomy. The status table row
reads **"EXECUTED / VERIFIED — no harmful collapse; normalization-switch degradation established
(internally classified as Case 4)"**.

---

## 3. Lane-centre correction

**One real content error was found and fixed:** `docs/project-history.md` still claimed
"100 % agreement in **5/5** recordings" for the `4220`/`4230` sign test. That count is wrong.

| quantity | authoritative value | source |
|---|---|---|
| **sign-convention test** | **4 recordings** (`1001\|ds004118`, `1001\|ds004120`, `3101\|ds004118`, `3101\|ds004120`), fraction **1.000** each | `phase3c/lane_geometry.json` → `recordings[*].geometry.sign_agreement` |
| broader behavioural-audit scale | 5 recordings / 3 participants | `phase3c/outputs/endpoint_eligibility.json` |

The two are **different quantities** and are now stated as such wherever both could be confused. The
verifier now **derives** the count from `lane_geometry.json` rather than matching a string, so if the
artifact ever grows the check follows it.

---

## 4. TTA causal-language correction

Applied in `tta_collapse/README.md`, `docs/project-history.md`, `docs/scientific-status.md` and the
root README. The distinction enforced throughout:

| supported | not yet supported |
|---|---|
| the normalization switch is **sufficient** to reproduce the degradation | BatchNorm statistics are the **causal** mechanism |
| the entropy gradient is **inert** under this protocol | the precise normalization mechanism has been explained |
| instability is **not specific to** entropy-gradient updates | TENT collapses universally on EEG |

---

## 5. "published" wording removals

Three occurrences removed — each meant *"appeared in a paper"* while no paper exists:

* `docs/project-history.md`: "stand as published" → "remain scientifically valid under their frozen
  protocols"
* `functional_prediction/evidence/phase4a3/GAP_CONTAMINATION_AUDIT.md`: same
* `functional_prediction/evidence/phase4a3/SESSION_HANDOVER_PHASE4A3.md`: same

The ~150 occurrences meaning *"shipped in this repository"* were **deliberately kept** — they are
correct, and replacing them would be churn. A guard now fails on "stand as published" /
"valid, published, closed".

---

## 6. Third-party provenance wording correction

Removed the false blanket claim *"Third-party code is referenced, not vendored"* — true of the
active trees, false of the archive. Replaced with the two-part statement recording the active/legacy
distinction and the unresolved licensing.

Recorded in the root README **and** as the summary statement of `docs/third-party-provenance.md` §1,
which also now carries **§5.1 — the owner decision that the four unresolved files stay in place**,
with the reasoning (history persists past deletion; provenance preservation outranks cosmetic
cleanup; no attribution invented).

**No repository-wide license is asserted and no `LICENSE` file exists.**

---

## 7. License / citation separation

The root README's combined `## Citation and License` is now two sections with distinct claims:

* **License** — no repository-wide grant while provenance is unresolved.
* **Citation** — no DOI yet; use the repository URL and commit SHA; **absence of a license does not
  by itself prevent citation or scholarly reference.**

---

## 8. Tracked-file size audit

Full detail: [`TRACKED_FILE_SIZE_AUDIT.md`](TRACKED_FILE_SIZE_AUDIT.md).

| metric | value |
|---|---:|
| tracked files | 1,151 |
| tracked size | 88.08 MB |
| largest file | 3.02 MB |
| files over 3 MB | **0** |
| accidental raw data | **none** |
| waveform caches | **none** |
| duplicate evidence | **none** — `segments_all.csv` is the distinct pre-exclusion manifest |
| Git LFS | **not used** |

The single binary is the **1.2 MB legacy LSTM checkpoint**
(`archive/legacy/legacy_ns_sd_prototype/feature_extracting/feature_data/lstm_fatigue_best.pt`),
explicitly identified: it is part of the byte-preserved legacy snapshot, already public in
`625dc3b`, and `.gitignore`-whitelisted by decision.

**No unexpected large artifact was found. No blocker.**

---

## 9. Tests and checks

| check | result |
|---|---|
| `docs/verify_public_numbers.py` | **127/127 PASS** (was 81; +46 guards) |
| `docs/check_links.py` | **26/26** relative links resolve |
| `functional_prediction/tests/test_mechanism.py` | **16/16** |
| `functional_prediction/tests/test_phase2_ridge.py` | **22/22** |
| `tta_collapse/tests/test_p1_synthetic_smoke.py` | **SMOKE: PASS** |
| `py_compile` all published `.py` | 0 failures |
| JSON parse | 0 failures |
| CSV parse | 0 failures |
| `.gitignore` ignored-file audit | 0 ignored |

**Not run, deliberately:** training, TENT, BCIT rerun, permutation, SFFS, dataset download.

**Dependency reported honestly:** `tta_collapse/tests/test_p1_controls.py` requires the ds004902
release metadata (`data/ds004902/metadata_behavior/participants.tsv`), which is **intentionally not
published**. It therefore cannot run from a public clone. This is stated in
`docs/reproducibility.md` rather than worked around.

---

## 10. Secret / privacy scan

| scan | scope | result |
|---|---|---|
| API keys / OAuth / cloud (`ghp_`, `gho_`, `sk-`, `AKIA`, `AIza`, `xox`) | all tracked files | **0 genuine** (1 regex false positive: the literal filename `task-Drive_events.json`) |
| passwords / secrets / Bearer tokens | all tracked files | **0** |
| PEM private keys, `ssh-rsa`/`ssh-ed25519` authorized keys | all tracked files | **0** |
| `.env` / credentials files | repository | **0** |
| local username, workspace path, interpreter path | all tracked files | **0 after sanitization** |
| remote host / port / SSH key name | all tracked files | **0 after sanitization** |
| `/root/…` references | active code | present **only** as server-side constants in the remote-execution helpers — **deliberate**, and the host name is redacted |

**No genuine credential found. No hard stop.**

---

## 11. Old-name residue

| pattern | active tree | classification |
|---|---|---|
| `EEG-Fatigue-Detection` | 2 | LEGITIMATE_HISTORICAL — names the repository being renamed |
| `疲劳识别` / `NS vs SD classifier` | 2 | LEGITIMATE_HISTORICAL — quoting the old README in audit records |
| `fatigue classifier` | 1 | LEGITIMATE_HISTORICAL — explains why the topic is excluded |
| `EEG fatigue detection`, `你的用户名`, `你的仓库名`, `codes/` | **0** | — |

No obsolete identity language appears in the root README's first screen or in either branch README.

---

## 12. Unresolved items

| item | status |
|---|---|
| **Third-party licensing** of four archive files | **UNRESOLVED by design** — needs the upstream files; three resolution paths documented; owner decision recorded (files stay) |
| **`CASE 4` mechanism** | **NOT ESTABLISHED** — needs an intervention experiment; a PI decision |
| **Phase 4A2 population null** | `K = 8`, p-floor 1/9 — cannot resolve 5 %; a larger `K` needs a server, not run |
| **`PHASE4A3_GAP_CORRECTED_REPORT.md`** | **never generated.** All citations now point at existing artifacts; a note records why (see `docs/refresh/repair_dangling_report_reference.py`) |
| **`AGENTS.md` internal inconsistency** | `AGENTS.md` §2c and §5 still say the TTA degradation "is caused by the test-batch normalization switch" and mark Phase 4A/4A2 `INVALIDATED` in its directory diagram. **This is local-only governance text, not published**, and was not rewritten in this pass. Reported, not silently changed. |
| **`_refactor/70_write_research_trees.py`** | still contains the old citation string — it is a **frozen generator** whose output was already corrected; rewriting it would falsify the refactor record |

---

## 13. Did any scientific result change?

# **SCIENTIFIC RESULTS CHANGED: NO**

No metric, threshold, verdict, count or algorithm was altered. Every changed number was a
**mis-statement in prose** of a value that its artifact already recorded correctly:

* the lane-centre recording count was written as 5/5 in one document and is **4** in the artifact;
* "attributable to" was narrowed to "sufficient to reproduce" — the underlying measurements
  (`+0.00048`, t = +0.22, the four arm values) are untouched;
* "stand as published" became "remain scientifically valid under their frozen protocols" — same
  status, wording that cannot be mistaken for a citation.

The verifier re-derives 127 checks from the artifacts on every run.

# **PUBLIC SCIENTIFIC INTERPRETATION CORRECTED: YES**

Wording tightened without altering results. Specifically: (1) TTA attribution distinguished from
causation; (2) the lane-centre count corrected; (3) "published" disambiguated; (4) the third-party
vendoring claim corrected to disclose the archive exception; (5) license separated from citation;
(6) the internal `CASE 4` label demoted below the scientific meaning.
