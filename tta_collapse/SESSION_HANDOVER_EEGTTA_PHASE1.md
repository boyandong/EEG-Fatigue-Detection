# SESSION_HANDOVER — EEG-TTA Phase 1

**Outgoing session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Branch/lane:** `audit/eeg_tta_phase1/` — **completely separate** from the BCIT/SRTP
behavioural-regression mainline. Nothing in `project/vigilance_generalization_v1/`,
`audit/phase3*`, `audit/phase4*` or `formal_results_v1/` was modified.
(The root `SESSION_HANDOVER.md` is the **BCIT** handover and is unchanged apart from a
two-lane pointer banner.)
**Handover written:** 2026-09-20 (**final** — Phase 1 executed, verified, at hard stop)
**Status:** **PHASE 1 COMPLETE.** 816/816 units on the owner-approved RTX 4090. Verifier
**105/105**, negative controls **75/75 bite**, remote SOURCE closure **PASS**.
Verdict **`CASE 4 — BN/NORMALIZATION INSTABILITY`**.

> ## THE ANSWER, IN ONE PARAGRAPH
>
> **No harmful prediction collapse occurred in any arm.** All three adapted arms fall to
> near-chance and are statistically indistinguishable from one another: `BN_ONLY` BAcc
> 0.5039, `TENT_LITERAL` 0.5043, `TENT_DET` 0.5035, against `SOURCE` 0.5924. The paired
> contrast `TENT_LITERAL - BN_ONLY` is **+0.00048 (t = +0.22)**, and `BN_ONLY` vs `TENT_DET`
> agree on **99.65 %** of windows. The entire ~8.9-point degradation is therefore produced by
> the **switch to test-batch normalization statistics**, which happens with **no gradient at
> all**; the entropy gradient is **inert**. `SOURCE` reproduced the historical benchmark
> exactly (BAcc `0.5924169784325324`), so the comparison is against the real baseline.

---

## 1. Verified state

| item | state | evidence |
|---|---|---|
| legacy trunk identity | VERIFIED | hashes match formal provenance on **both** machines |
| **remote SOURCE closure** | **PASSED** | max abs dp 9.537e-07, 0 label flips, BAcc exact, 68 folds |
| **SOURCE reproduces the historical headline** | **VERIFIED** | BAcc 0.5924169784325324 = recorded value |
| target stream (`metadata_order`) | VERIFIED | 9390 rows; per-subject `SessionOrder` order |
| **formal run** | **EXECUTED** | 816/816 units, 204 per arm; 8 reused from the predeclared smoke |
| arm invariants on real runs | VERIFIED | verifier J1-J20 |
| scoring semantics (single pre-update forward) | VERIFIED | J13-J15, NC20-NC24 |
| per-unit RNG on real runs | VERIFIED | J16 re-derived every seed for all 816 units |
| independent verifier | **105/105** | `90_verify_phase1.py`, exit 0 |
| negative controls NC1-NC27 | **75/75 bite** | `tests/test_p1_controls.py`, exit 0 |
| remote environment | VERIFIED | `outputs/remote_env.json`; `SERVER_RUNBOOK.md` §2 |
| **verdict** | **CASE 4** | `outputs/collapse_verdict.json` |

### 1.1 Contaminated / unknown results

* Nothing is contaminated. Every number traces to a unit file and the verifier that checked it.
* **UNKNOWN / unexplained (recorded, not smoothed):** `BN_ONLY` vs `TENT_LITERAL` and
  `TENT_LITERAL` vs `TENT_DET` both report exactly **3 827** differing windows. The flip
  *sets* are **not** identical, so the equal count is not a bookkeeping artefact; both
  comparisons are dominated by the same near-threshold window population (67.9 % of flips lie
  within 0.05 of the 0.5 threshold).

### 1.2 Corrections made during this session (do not re-derive)

1. **Cross-visit chronology** — corrected to `SessionOrder`; the clock columns are
   time-of-day-matched by design and carry no ordering information.
2. **Arms 3 to 4** — the official `model.train()` is global, so canonical TENT runs with EEGNet
   Dropout **live**; both literal and deterministic arms are run.
3. **Scoring semantics** — an earlier draft scored a *second*, Dropout-off forward while
   calling the arm literal. Now exactly **one** pre-update forward serves both scoring and
   entropy (`entropy_forward` returns `(logits, loss)` together).
4. **`bs` NameError** — `run_arm` lost its `batch_size` binding during an edit; caught by the
   remote smoke, fixed, re-verified. The smoke gate earned its place.
5. **J5 was a wrong assertion, not a code bug.** It demanded `affine_drift_l2 == 0` at batch 0.
   Adam's first step is ~`-lr*sign(g)`, so its norm is ~`lr*sqrt(P)` = 8.9e-3 irrespective of
   gradient size. A staged instrument showed drift is **exactly 0** through build, mode,
   forward and backward, and appears only at `optimizer.step()`. J5 now asserts an
   Adam-scaled first step (NC27).
6. **`decide_case` ordering bug, repaired post-run.** The code required `BN_ONLY` to *collapse*
   before barring the entropy attribution, instead of merely being *degraded*. Recorded in
   `COLLAPSE_TAXONOMY.md` §5.4 as an **implementation repair, not a protocol revision**: no
   threshold or definition changed, and the branch cannot manufacture a result because it
   fires only when a gradient-free arm is degraded.
7. **Other earlier claims corrected:** `sub-28/ses-2` skips epoch 39 in the **interior**
   (the guarantee is "strictly ascending", not "contiguous"); the BN affine scalar count is
   **80**; controls `nc16`/`nc17` originally passed **vacuously** on an empty arm set and were
   fixed after an injected-violation test.

---

## 2. Git / worktree state

**This workspace is not a git repository.** Provenance rests on file-content SHA-256 only
(`git_commit: COMMIT PENDING`). Files written outside `audit/eeg_tta_phase1/`: a two-lane
pointer banner at the top of the root `SESSION_HANDOVER.md`, and `AGENTS.md` §2c plus one §4
verifier row. **Nothing in the BCIT lane was touched.**

---

## 3. External processes

The formal run finished. **No process is running on the server.** The server remains
provisioned at `/root/srtp/` with a working environment and all 816 units
(`/root/eegtta_units.tgz`, `/root/eegtta_results.tgz`).

**A successor must re-verify runtime state rather than trusting this paragraph.**

---

## 4. What a successor session should do

1. **Re-verify before trusting this handover** (~2 min; unit files are also present locally
   under `outputs/units/`):
   ```bash
   python audit/eeg_tta_phase1/90_verify_phase1.py        # expect 105/105, exit 0
   python audit/eeg_tta_phase1/tests/test_p1_controls.py  # expect 75/75, exit 0
   ```
2. **Read `EEGTTA_PHASE1_TENT_COLLAPSE_REPORT.md` §0 and §7.5** before quoting any single
   arm's number.
3. **STOP.** Phase 1 is complete. Do **not** start a rescue, a sweep, or a new TTA method.

### 4.1 Traps

* **Do not report "TENT collapses" or "TENT is bad for EEG".** TENT did not collapse; it
  degraded to chance, and so did the gradient-free control, by the same amount.
* **Do not attribute the degradation to entropy minimisation.** The paired contrast over 68
  subjects is +0.00048 with a CI containing zero.
* **Do not call the diversity change a collapse.** Dominant share *fell* (0.7104 to ~0.542) and
  marginal entropy *rose* (0.5358 to ~0.686): the adapted model stopped making a confident
  constant-ish prediction and drifted toward chance. That is the **opposite** of the harmful
  collapse signature.
* **Do not reuse `project/run_tent_rbf_baselines.py`** — its protocol is KILLed.
* **Do not run the PARKED order streams**, and do not treat 9390 windows as `n`.
* **Do not call `TENT_DET` canonical TENT** — only `TENT_LITERAL` is literal.
* **Do not confuse the two torch versions.** The formal run used the container's
  **torch 2.8.0+cu128 / Python 3.12.3**, not the locally frozen 2.10.0+cu126 / 3.11. The
  consequence was *checked* (SOURCE reproduced the historical baseline exactly), not assumed.

---

## 5. Recommended successor session name

```
EEGTTA-PHASE2-<YYYYMMDD>-NORMALIZATION-STATISTICS-DIAGNOSTIC
```

…**only** if the owner issues a new PI decision. Phase 2 is **not** licensed by Phase 1. The
highest-information next diagnostic is the statistics-geometry one described in
`RESEARCH_TREE_UPDATE.md` §4 — cheap, and it requires no adaptation. A batch-size sensitivity
curve is second, and is a **sweep**, so it needs explicit authorisation.

---

## 6. Answer to the phase's single question

> "Does canonical episodic TENT produce harmful prediction collapse on the frozen
> cross-subject ds004902 EEGNet benchmark, and if so, is the first evidence more consistent
> with entropy-driven adaptation or normalization instability?"

**Answered.** No harmful prediction collapse occurs under the frozen protocol, in any of the
four arms. The degradation that does occur (-8.9 BAcc) is **not** attributable to entropy
minimisation: it is fully reproduced by the gradient-free normalization-only control, and the
two entropy arms are statistically indistinguishable from that control and from each other.
The first, and only surviving, evidence points to **normalization-statistics instability**:
CASE 4.
