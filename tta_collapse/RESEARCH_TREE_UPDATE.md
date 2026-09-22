# RESEARCH_TREE_UPDATE.md

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Lane:** `audit/eeg_tta_phase1/`
**Status: PHASE 1 COMPLETE — HARD STOP REACHED.**

The workspace's canonical Research Tree lives in `AGENTS.md` §2b and belongs to the **BCIT /
SRTP behavioural-regression mainline**. Per the session brief that tree is **not** edited from
this lane; `AGENTS.md` §2c carries a pointer here.

---

## 1. THE ANSWER

> **Does canonical episodic TENT produce harmful prediction collapse on the frozen
> cross-subject ds004902 EEGNet benchmark, and if so, is the first evidence more consistent
> with entropy-driven adaptation or normalization instability?**

**No harmful prediction collapse occurs in any arm.** All three adapted arms fall to
near-chance performance, and they are **statistically indistinguishable from one another**.
The degradation is therefore attributable to the **test-batch normalization-statistics
switch**, and **not** to entropy minimisation — the entropy gradient is inert.

| arm | BAcc | ΔBAcc vs SOURCE | 95 % CI |
|---|---:|---:|---|
| `SOURCE` (frozen) | **0.5924** | — | — |
| `BN_ONLY` (no gradient) | 0.5039 | −0.0886 | [−0.1253, −0.0520] |
| `TENT_LITERAL` (canonical) | 0.5043 | −0.0881 | [−0.1248, −0.0510] |
| `TENT_DET` | 0.5035 | −0.0889 | [−0.1258, −0.0522] |

`TENT_LITERAL − BN_ONLY` = **+0.00048** (t = +0.22). `TENT_LITERAL − TENT_DET` = **+0.00082**
(t = +0.39). `BN_ONLY` and `TENT_DET` agree on **99.65 %** of windows.

**Verdict: `CASE 4 — BN/NORMALIZATION INSTABILITY`.** Executed 816/816 units on the
owner-approved RTX 4090; verifier **105/105**, controls **75/75 bite**, remote SOURCE closure
**PASS**.

---

## 2. TRUNK — verified, now including a successful remote reproduction

| element | status |
|---|---|
| ds004902, 500 Hz, 61 ch, 4 s windows, 68 subjects, 9390 windows | **VERIFIED** |
| frozen subject-LOSO split (68 folds, 53/14/1, seed 20260908) | **VERIFIED** |
| frozen legacy EEGNet trunk (204 checkpoints) | **VERIFIED** on both machines |
| **SOURCE closure on the remote 4090** | **PASSED** — max \|Δp\| 9.537e-07, 0 label flips, BAcc exact |
| **SOURCE reproduces the historical headline exactly** | BAcc **0.5924169784325324** vs recorded 0.5924169784325324; Acc 0.5963370… vs 0.5963 |
| cross-visit order = `SessionOrder` | **VERIFIED** (39 NS-first / 29 SD-first) |
| four-arm protocol + frozen interpretation matrix | **EXECUTED** |
| per-unit RNG convention | **VERIFIED** on real runs (816 units re-derived) |
| independent verifier | **105/105** (Stage 0 + outcome) |
| negative controls NC1–NC27 | **75/75 bite** |

---

## 3. KEEP

* The whole provenance + closure + stream + taxonomy + verifier apparatus. It caught **four**
  protocol defects before the run and **three** implementation bugs during it, including one
  that would have reported a **vacuously passing** control.
* **The four-arm design.** It is the reason the verdict is decidable at all: without
  `BN_ONLY` and `TENT_DET` the result would have read "TENT collapses", which is wrong.
* **The per-unit RNG convention** — reproducibility for a stochastic canonical arm without
  de-stochasticising it.
* The negative-control discipline: `nc16`/`nc17` originally passed **vacuously** on an empty
  arm set, and that was caught by an injected-violation test, not by inspection.
* The measured architecture invariants (3 BatchNorm layers / 6 tensors / 80 affine scalars /
  6322 params) asserted on both machines.

## 4. TEST NOW — **nothing**

**Phase 1's hard stop is reached.** The single question is answered, and the answer is
`CASE 4`. The brief forbids starting any rescue, sweep, or new TTA method, and forbids
choosing a successor before the outcome. This section is therefore intentionally empty.

If the owner wants a Phase 2, the **highest-information** next step is *not* an anti-collapse
method. It is a **targeted diagnostic of the batch-statistics switch**, because that is now
the only surviving explanation for a −8.9-point drop that occurs **with no gradient at all**:

1. **Statistics-geometry diagnostic** — per batch, compare the source running statistics
   (μ, σ from training) against the test-batch statistics (μ_t, σ_t) the adapted forward
   actually used, and quantify the per-channel/per-layer discrepancy and its correlation with
   the per-subject ΔBAcc. This asks *whether* the switch moved the features where the model
   was calibrated, and it is cheap (no adaptation needed — it can be computed from SOURCE and
   `bn_only` runs).
2. **Batch-size diagnostic** — the frozen batch size is 32, inherited from training. Niu et
   al. (ICLR 2023) identify small-batch batch-statistics as a cause of TTA error accumulation;
   `sub-04/ses-1` has a batch of **4**. A batch-size sensitivity curve would test whether the
   degradation scales with batch-statistics noise. **This is a sweep and therefore requires a
   new PI decision.**

Both are diagnostics, not rescues. Neither is licensed by Phase 1.

## 5. PARK — unchanged and now additionally motivated

All previously parked items remain parked: forced `NS_then_SD`/`SD_then_NS` order streams,
shuffled/balanced streams, learning-rate sensitivity, step-count sensitivity, continual TENT,
EATA, SAR, CoTTA, MEMO, diversity regularisation, confidence filtering, reset mechanisms, any
custom anti-collapse method.

**The result makes this list more important, not less.** Because the entropy gradient was
inert, every method in that list that is *motivated by entropy-minimisation collapse* has lost
its premise **on this benchmark**. Adding one would be building a remedy for a phenomenon that
did not occur.

## 6. KILL

| killed | why |
|---|---|
| the pre-existing legacy TENT prototype's **protocol** (`project/run_tent_rbf_baselines.py`) | four protocol violations (SHA-256 stream order, label-based lr selection, post-update scoring, no per-subject reset) |
| **the hypothesis that entropy minimisation is the cause of degradation on this benchmark** | `TENT_LITERAL − BN_ONLY` BAcc = +0.00048 (t = +0.22); `BN_ONLY` and `TENT_DET` agree on 99.65 % of windows. The gradient is not necessary for the degradation and contributes nothing measurable. |

Note the second entry is a **measured** kill, not a preference: it is a paired contrast over
68 subjects with a CI containing zero.

## 7. Phase-1 verdict summary

```
EEG TEST-TIME ADAPTATION STABILITY
  TRUNK        verified (incl. remote reproduction of the historical baseline)
  TEST NOW     canonical TENT collapse existence  ->  EXECUTED, 816/816 units
  RESULT       CASE 4 - BN/NORMALIZATION INSTABILITY
               no harmful collapse in any arm; entropy gradient inert
  TEST NEXT    none in Phase 1 (hard stop)
  PARK         all anti-collapse methods (and now, less motivated)
  KILL         entropy-minimisation-as-cause on this benchmark (measured)
```
