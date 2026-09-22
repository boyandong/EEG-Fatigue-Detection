# Research Tree — Branch B: Test-Time Adaptation Stability

**Branch:** `tta_collapse/`
**Question:** does canonical test-time entropy minimisation produce harmful prediction collapse
in cross-subject EEG streams, and if so, what mechanism drives it?

This is this branch's own tree. Branch A (`functional_prediction/`) has a separate tree and does
not share this one. Do not merge them, and do not let one branch's verdict justify the other's.

---

## North Star

For an unseen subject, does online entropy-minimisation adaptation stay **stable**, or does it
degenerate — becoming confidently and uniformly wrong — and if it degenerates, **which mechanism**
is responsible?

---

## TRUNK — verified, and now including a successful remote reproduction

| element | status |
|---|---|
| frozen ds004902 source trunk (borrowed from `../shared/`) | **VERIFIED** on both machines |
| 204 EEGNet LOSO checkpoints (68 folds × 3 seeds), 204 distinct contents | **VERIFIED** |
| SOURCE closure, local **and** on the remote 4090 | **PASSED** — max abs Δp 9.5e-07, 0 label flips |
| SOURCE reproduces the historical benchmark exactly | **VERIFIED** — `BAcc = 0.5924169784325324` |
| target stream, visit order from `SessionOrder` | **VERIFIED** |
| four-arm protocol + frozen interpretation matrix | **EXECUTED** (816/816 units) |
| per-unit RNG convention | **VERIFIED** on real runs |
| independent verifier | **105/105** |
| negative controls NC1–NC27 | **75/75 bite** |

---

## KEEP

| item | why |
|---|---|
| the frozen ds004902 source trunk | shared, single copy, hash-verified |
| EEGNet source-baseline provenance | the trunk's identity is proven, not assumed |
| the **external TENT reference audit** | the pinned official implementation is vendored and hash-pinned; the method spec traces every choice to it |
| the **four-arm design** | it is the reason the verdict is decidable at all |
| the **collapse taxonomy** | a definition that can distinguish degradation from collapse |
| the per-unit RNG convention | reproducibility for a stochastic canonical arm without removing its stochasticity |
| the negative-control discipline | it caught a control that passed **vacuously** on an empty arm set |

---

## RESULT — Phase 1 EXECUTED and VERIFIED

**Verdict: `CASE 4 — BN/NORMALIZATION INSTABILITY`. No harmful prediction collapse in any arm.**

Reported measurements (68 subjects, 3 seeds, paired over subjects):

| arm | BAcc | ΔBAcc vs SOURCE (95 % CI) |
|---|---:|---|
| `SOURCE` | 0.5924 | — |
| `BN_ONLY` (no gradient) | 0.5039 | −0.0886 [−0.1253, −0.0520] |
| `TENT_LITERAL` (canonical) | 0.5043 | −0.0881 [−0.1248, −0.0510] |
| `TENT_DET` | 0.5035 | −0.0889 [−0.1258, −0.0522] |

* `TENT_LITERAL − BN_ONLY` = **+0.00048** BAcc (t = +0.22)
* `BN_ONLY` vs `TENT_DET` agree on **99.65 %** of windows
* diversity runs **opposite** to the collapse signature: dominant share 0.7104 → ~0.542,
  marginal entropy 0.5358 → ~0.686

The entropy gradient is **inert**; the entire degradation is reproduced by the gradient-free
normalisation-only control.

---

## TEST NEXT — **nothing**. Phase 1 is at a hard stop.

The single question Phase 1 asked is answered. The brief forbids starting any rescue, sweep or
new TTA method, and forbids choosing a successor before the outcome. This section is
intentionally empty.

**Not licensed, and not yet asked:** *why* does the test-batch normalisation switch harm
performance? That is a Phase-2 question requiring a new PI decision. The highest-information
candidate is a **statistics-geometry diagnostic** (compare source running μ,σ against the
test-batch μ_t,σ_t actually used, and relate the discrepancy to per-subject ΔBAcc) — cheap, and
it requires no adaptation. A batch-size sensitivity curve is second, and being a sweep it needs
explicit authorisation.

---

## PARK — not started, not licensed; no artefact exists for any of these

> SAR · DELTA · T-TIME · T3A · CoTTA · BFT · EATA · MEMO · diversity regularisation ·
> confidence filtering · reset mechanisms · anti-collapse redesign · hyper-parameter sweeps ·
> batch-size sweeps · continual TENT · forced `NS_then_SD` / `SD_then_NS` order diagnostics

**The result makes this list more important, not less.** Because the entropy gradient was inert,
every method here that is motivated by *entropy-minimisation collapse* has lost its premise on
this benchmark. Adding one would be building a remedy for a phenomenon that did not occur.

The refactor verifier asserts that no `.py` in this branch carries any parked-method name.

---

## KILL

| killed | why |
|---|---|
| the legacy TENT prototype's **protocol** (`archive/.../killed_tent_prototype/`) | four violations: SHA-256 stream order, label-based lr selection, post-update scoring, no per-subject reset |
| **entropy minimisation as the cause of degradation on this benchmark** | a *measured* kill: `TENT_LITERAL − BN_ONLY` = +0.00048, CI containing zero |

---

## A single measured contradiction, retained

`BN_ONLY` vs `TENT_LITERAL` and `TENT_LITERAL` vs `TENT_DET` both report exactly **3 827**
differing windows. The flip *sets* are not identical, and 67.9 % of flips lie within 0.05 of
the 0.5 threshold — the mechanism is understood, the identical count is not. Recorded rather
than smoothed over.

---

## What this branch does NOT claim

* That TENT "collapses" on EEG. It did not.
* That entropy minimisation caused the degradation. The gradient-free control reproduces it.
* That the diversity change is a collapse. It is the opposite direction.
* Any claim of novelty for TTA collapse as a phenomenon — the general literature already has it.
  What is established is its **absence**, and the localisation of the degradation, on this
  specific frozen benchmark.
