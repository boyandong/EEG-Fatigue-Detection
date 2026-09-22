# P2_GATE_CORRECTION.md — the fold invariant, corrected

**Phase 4A2:** `SRTP-PHASE4A2-20260918-ADAPTIVE-SFFS`
**Status:** implementation/verifier correction. **Not** a hypothesis change and **not** a
cohort-eligibility rule. No scientific result changes (evidence in §5).

---

## 1. The old invariant, verbatim

`audit/phase4a/50_run_all.py` (as of the Phase 4A run) asserted:

```python
folds = list(csv_rows(OUT / "standard_fold_predictions.csv"))
n_ok = sum(1 for r in folds if r.get("status") == "OK")
c("P2_folds", n_ok >= 25 * 6, f"{n_ok} OK folds for 25 participants")
```

i.e. **`N_folds == N_participants × 6`**. `phase4a_standard_gate.json` recorded:

```
P2_folds  FAIL  "149 OK folds for 25 participants"
```

and, because the gate is a conjunction, `standard_pipeline_pass = false` — which closed A3.

## 2. Why it was wrong

The assertion presumes every recording reconstructs exactly **six** protocol blocks. One does not.
`FIVE_BLOCK_DEVIATION.md` documents that legacy `3127` (`sub-72`, T3, 256 ch) reconstructs **five**
block-width clusters under the frozen >90 s rule, so its leave-one-block-out CV legitimately has
five folds.

Measured directly from the built caches (`blocks.shape[0]`, this session):

| blocks per participant | participants |
|---|---|
| 6 | 24 |
| 5 | 1 (`3127`) |
| **`sum_i n_blocks(i)`** | **149** |

So `149` is the *correct* count, and the old assertion conflated two different things:

* **"this recording has fewer blocks than the design"** — a property of the DATA; and
* **"a fold was silently dropped"** — a pipeline defect.

The old check could not tell them apart, so it fired on the former.

## 3. The corrected invariant

`50_run_all.standard_gate()` now asserts, **per participant against that participant's own cache**:

```
N_folds == sum_i n_valid_blocks(i)          (total)
for every i:  |{blocks tested for i}| == n_blocks(i)     (per participant)
every participant in the frozen cohort contributes folds, and no one else does
every tested block index lies inside that participant's own reconstructed block range
```

implemented as checks `P2_folds`, `P2_folds_total`, `P2_blocks`. The block counts are read from the
caches by `frozen_cohort_block_counts()`, so the gate asserts a property of the **data**, not a
hard-coded row count.

**This is option (a) of `PHASE4A_VERDICT.md` §6.1**, the option the Phase 4A verifier already used
(99/99). Option (b) — requiring ≥6 blocks — would have excluded `3127` by a rule invented after the
data was seen, and was not taken.

## 4. Does the corrected check still bite?

An invariant that cannot fail is not an invariant. `01_prove_p2_gate_bites.py` injects deliberate
violations into **copies** of the standard artifacts, re-runs the **production** gate function, and
requires the corresponding check to fail. Result — `outputs/p2_gate_negative_controls.json`:

| # | injected violation | required to fire | observed |
|---|---|---|---|
| V0 | untouched copy (**the control control**) | gate PASSES | PASS, `failures=[]` |
| V1 | one OK fold row silently deleted | `P2_folds`, `P2_folds_total` | both fired |
| V2 | a phantom 6th fold for the five-block recording | `P2_folds`, `P2_folds_total` | both fired (+`P2_blocks`) |
| V3 | a fold row for a participant outside the cohort | `P2_folds` | fired (+`P2_folds_total`) |
| V4 | a block index outside the participant's own range | `P2_blocks` | fired |

**5/5 behaved as required.** V0 is the important one: the clean copy passes *every* check, so the
gate's pass is not an artefact of a weakened assertion.

## 5. Did any scientific number change?

**No.** The correction touches only the gate's bookkeeping. Evidence:

* the standard pipeline was **not re-run**. `--gate-only` re-evaluates P1–P5 from the existing
  artifacts; `standard_subject_results.csv`, `standard_fold_predictions.csv`,
  `standard_null_results.csv` and `standard_run.json` are byte-unchanged;
* `P2_run` still reports `n_participants_ok=25`; `P4_reported` still reports
  `mean_R = −0.04993651757569237`; `P5_nulls` still reports `12/25` historical and `0/25` iAAFT;
* the only file rewritten is `outputs/phase4a_standard_gate.json`, which now records
  `failures = []` and `standard_pipeline_pass = true`. The previous version is preserved in this
  document (§1) and in `PHASE4A_VERDICT.md` §6, and the old artifact is not deleted.

## 6. Governance

* the old artifact and its wording are recorded above and **not overwritten in history**;
* the Phase 4A lane is untouched otherwise; all new content lives in `audit/phase4a2/`;
* this correction is what opens A3. It is not a licence to change anything else, and §5-§7 of the
  Phase 4A2 brief list what A3 may and may not vary.
