# COLLAPSE_TAXONOMY.md

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Status:** FROZEN before any adaptation run (prompt §13, §15, §16, §17, §4 of the pre-result
corrections).

> **Revision note:** this taxonomy was revised once, *before* any adaptation ran, to add the
> fourth arm's branch (`CASE 6`) and the interpretation matrix in §5.1. No trajectory had been
> observed at the time of the revision. Post-result revision of this file is forbidden.

The point of freezing this first is that "collapse" is otherwise a word one reaches for
whenever a number goes down. Here it is a measurable, two-part property, and
"performance went down" is explicitly *not* enough to earn the word.

---

## 1. Why "accuracy dropped" is not collapse

TENT minimises conditional predictive entropy. A method that does that is *expected* to
raise confidence. So:

* `H_cond ↓` on its own is **the objective being optimised**, not evidence of anything;
* `H_cond ↓` together with `BAcc ↓` is **performance degradation**, and may have nothing to
  do with prediction diversity;
* `H_marg ↓` / `dominant_share ↑` together with `BAcc ↓` is the actual collapse signature.

The dangerous pattern this taxonomy exists to catch is: **the model becomes more confident
while becoming more uniformly wrong / single-class**.

---

## 2. Per-batch definitions

For batch *t* containing windows with predicted positive-class probabilities `p_i`:

| symbol | definition |
|---|---|
| `q1(t)` | `mean_i p_i` — the prediction marginal (positive-class share) |
| `H_cond(t)` | `mean_i [ -Σ_k p(y=k|x_i) log p(y=k|x_i) ]` — mean conditional predictive entropy |
| `H_marg(t)` | `-Σ_k q_k(t) log q_k(t)` with `q_0 = 1-q1`, `q_1 = q1` — entropy of the marginal |
| `dominant_share(t)` | `max(q1(t), 1-q1(t))` |
| `mean_max_conf(t)` | `mean_i max_k p(y=k|x_i)` |
| `pred_positive_frac(t)` | fraction of the batch predicted positive at threshold 0.5 |
| `true_positive_frac(t)` | fraction of the batch that is truly positive ← **evaluation only, never an adaptation input** |
| `batch_balanced_accuracy(t)` | subject-of-the-batch balanced accuracy ← evaluation only |

`H_marg` is the binary entropy of `q1`, so `H_marg ↓ ⟺ dominant_share ↑` exactly; both are
reported because they are the two conventions used in the literature.

---

## 3. Frozen quartile windows

Diversity contraction is measured on a **fixed partition of the stream by batch count**:

```
first = batches [0, floor(n/4))
last  = batches [ceil(3n/4), n)
```

where `n` is the number of batches in that subject's episode. If `n < 4` the quartile split
is **undefined** and is reported as `quartile_defined = False` rather than being replaced by
an ad-hoc window. No "last 10 %", no "last 20 %", no window chosen after looking at the
trajectory (prompt §15).

For each metric `X`: `delta_X = mean(X over last) - mean(X over first)`.

Group-level diversity statistics compare **TENT's last quartile to SOURCE's last quartile on
the identical windows**.

---

## 4. The four per-subject concepts

| label | condition |
|---|---|
| **A. PERFORMANCE DEGRADATION** | TENT BAcc < SOURCE BAcc, with no material prediction concentration |
| **B. PREDICTION CONCENTRATION** | `H_marg ↓` and `dominant_share ↑` over the stream, regardless of whether accuracy moved |
| **C. CONFIDENCE INCREASE** | `H_cond ↓` / `mean_max_conf ↑`. **Not** a success and **not** a collapse on its own |
| **D. HARMFUL COLLAPSE** | **both** (i) reliable performance degradation **and** (ii) reliable diversity contraction |

Only **D** may be called *harmful prediction collapse / collapse-like degeneration*.

---

## 5. Group-level decision rule (frozen, in `src/p1_collapse.py::decide_case`)

The statistical unit is the **subject**, never the window (prompt §16). The 9390 windows are
not independent samples: they come from 68 people and are temporally autocorrelated within a
person. Treating windows as `n` would inflate significance by orders of magnitude. Every group
statistic is therefore computed over 68 paired subject deltas with a **10 000-resample paired
bootstrap 95 % CI** (`seed = 20260920`).

Inputs: per-arm `Δ balanced accuracy` and `Δ last-quartile dominant share` for `TENT_LITERAL`,
`TENT_DET`, `BN_ONLY`, each versus `SOURCE` on the identical windows.

Frozen thresholds:

| constant | value | meaning |
|---|---:|---|
| `DEGRADE_EPS` | 0.01 | `|mean ΔBAcc|` below this counts as "materially similar" |
| `CONCENTRATION_EPS` | 0.02 | `Δ dominant_share` below this counts as "no concentration" |
| `SUBJECT_COLLAPSE_DROP` | 0.10 | per-subject `ΔBAcc` at or below this is "strongly harmed" |

Primitives:

```
degraded(A)     = CI(ΔBAcc_A) entirely < 0      AND mean ΔBAcc_A      <= -0.01
concentrated(A) = CI(Δdom_A)  entirely > 0      AND mean Δdom_A       >= +0.02
collapsed(A)    = degraded(A) AND concentrated(A)          # the two-part test
```

### 5.1 The four-arm interpretation matrix (frozen before any result)

| observation | verdict | what may be written |
|---|---|---|
| `TENT_LITERAL` collapses, `TENT_DET` does not | **CASE 6 — TRAIN-MODE/DROPOUT SEMANTICS IMPLICATED** | Collapse **may not** be attributed to entropy minimisation alone; Dropout / train-mode semantics are implicated. |
| `TENT_LITERAL` and `TENT_DET` both collapse, `BN_ONLY` stable | **CASE 3 — TENT-SPECIFIC HARMFUL COLLAPSE** | Evidence is more consistent with **entropy-driven BN-affine adaptation**. |
| `BN_ONLY` also collapses | **CASE 4 — BN/NORMALIZATION INSTABILITY** | Normalization / batch-statistics instability is implicated; "entropy minimisation caused collapse" is **not** writable. |
| none collapses | **CASE 1 — NO MATERIAL TENT HARM** | Collapse is not established under the frozen protocol. **Do not tune hyperparameters to manufacture it.** |
| `TENT_LITERAL` degrades without concentration | **CASE 2 — DEGRADATION WITHOUT COLLAPSE** | TENT degrades performance; collapse is not established. Study adaptation mismatch. |
| few subjects strongly harmed, no population effect | **CASE 5 — SUBJECT-SPECIFIC / HETEROGENEOUS FAILURE** | Population-wide collapse is not established; subject-specific vulnerability exists. |

The evaluation order is exactly the one the pre-result correction specifies: the
literal-versus-deterministic split is examined **first**, because if it fires, the
entropy-attribution question is not the one that has been answered.

Every verdict also carries an explicit `attribution` sentence so the report cannot silently
promote a co-occurrence into a cause. Verifier checks `H6`–`H10` construct each branch of the
matrix and assert that `decide_case` returns the specified case, so the rule is proven to
branch rather than merely present.

### 5.2 Why "BN_ONLY also collapses" outranks "both TENT arms collapse" when both hold

If `BN_ONLY` degenerates, the phenomenon is reachable **without any gradient at all**.
Attributing it to entropy minimisation would then be attributing to the mechanism that is not
necessary to produce it. The more conservative attribution wins (prompt §18).

### 5.3 The literal-vs-det branch, stated exactly

Because `TENT_LITERAL` is the *only* arm that may be called canonical, the first question the
matrix asks is whether the two entropy arms agree:

| observation | verdict | attribution text |
|---|---|---|
| LITERAL collapses, DET does not | **CASE 6** | *"official train-mode / Dropout stochasticity is implicated; do NOT attribute the result to entropy minimization alone"* |
| both collapse, BN_ONLY stable | **CASE 3** | *"evidence becomes more consistent with entropy-driven BN-affine adaptation"* |
| BN_ONLY also collapses | **CASE 4** | *"normalization / batch-statistics instability remains implicated"* |
| none collapses | **CASE 1** | *"collapse is not established under the frozen protocol; do NOT tune TENT to manufacture collapse"* |

The evaluation order is: **(1)** literal-vs-det split, **(2)** BN_ONLY, **(3)** both-arms
collapse. Step (1) comes first because if it fires, the entropy attribution is not the
inference that has been earned.

Note this is an *implication*, not a mechanism proof: CASE 6 says where to look next
(Dropout vs some other effect of `train()` mode), not what the mechanism is.

### 5.4 Implementation repair made AFTER the run (recorded, not hidden)

The frozen rule in §5.1 is unchanged. One **implementation bug** in `decide_case` was found and
repaired after seeing the results, and it is recorded here because it changed the verdict
string:

* the code routed `BN_ONLY` through the **two-part collapse** test (`degraded AND
  concentrated`) before it ever considered the "degradation without collapse" case. The
  specification says the opposite for the control: if `BN_ONLY` is **degraded** — whether or
  not it is concentrated — the entropy attribution is barred (§5.2's conservative-attribution
  principle);
* with the buggy ordering, a run in which **all three arms degrade without any arm
  concentrating** fell through to CASE 2 ("TENT degrades performance") even though the
  gradient-free control was degraded by the same amount. That under-attributes: it reports an
  absence of collapse while ignoring the strongest positive evidence in the data;
* the repaired rule adds an explicit branch: *BN_ONLY degraded without concentration, and no
  arm concentrated* → **CASE 4**, with the attribution that normalization-statistics
  adaptation is sufficient for the degradation and the entropy gradient is not required for
  it;
* **this is an implementation repair, not a protocol revision.** No threshold, no definition
  and no quartile rule changed. It also cannot manufacture a result: it fires only when a
  gradient-free arm is degraded, which is evidence *against* an entropy-specific claim;
* the branch matrix for genuine collapse (CASE 3 / 4 / 6) is unaffected and remains covered by
  verifier checks `H6`–`H10`, which were not modified.

The repaired implementation is the one used for the reported verdict, and the pre-repair
behaviour is stated in the report so a reader can see both.

---

## 6. The six verdicts

| case | name | permitted conclusion |
|---|---|---|
| 1 | NO MATERIAL TENT HARM | *"Collapse is not established under the frozen canonical TENT protocol."* Do **not** tune lr to hunt for collapse. |
| 2 | PERFORMANCE DEGRADATION WITHOUT COLLAPSE | *"TENT degrades performance, but prediction collapse is not established."* Next step studies adaptation mismatch — not collapse. |
| 3 | TENT-SPECIFIC HARMFUL COLLAPSE | *"Entropy-driven TENT adaptation shows collapse-like degeneration"* — both entropy arms collapsed while BN_ONLY stayed stable. Only now may collapse-mechanism diagnostics start. |
| 4 | BN/NORMALIZATION INSTABILITY | *"Instability is not specific to entropy-gradient TENT; normalization-statistics adaptation is implicated."* |
| 5 | SUBJECT-SPECIFIC / HETEROGENEOUS FAILURE | *"Population-wide collapse is not established; subject-specific vulnerability exists."* |
| 6 | TRAIN-MODE/DROPOUT SEMANTICS IMPLICATED | *"The literal official arm collapsed while the deterministic-dropout control did not; collapse may not be attributed to entropy minimisation alone."* |

---

## 7. Why the two controls decide the attribution

### 7.1 BN_ONLY: entropy gradient vs normalization statistics

| SOURCE | BN_ONLY | TENT arms | what the explanation space collapses to |
|---|---|---|---|
| stable | stable | collapse | **entropy-driven affine adaptation / optimizer dynamics** (CASE 3) |
| stable | collapse | collapse | test-time **normalization statistics** are implicated; "entropy minimisation caused collapse" is **not** writable (CASE 4) |

### 7.2 TENT_DET: canonical train-mode semantics vs the entropy objective

| SOURCE | TENT_DET | TENT_LITERAL | what the explanation space collapses to |
|---|---|---|---|
| stable | stable | collapse | the difference is **Dropout / train-mode semantics**, not the entropy objective (CASE 6) |
| stable | collapse | collapse | the phenomenon does **not** require live Dropout; the entropy-driven BN-affine account survives (CASE 3, subject to §7.1) |

The fourth arm exists precisely so that CASE 3 is only reachable when the canonical,
literature-matching configuration *and* its deterministic twin both degenerate. Without it, a
single arm could not distinguish "TENT collapses" from "TENT-with-dropout collapses".

---

## 8. What is never claimed in Phase 1

* No causal reading of co-occurrence. `affine_drift ↑` while `BAcc ↓` is **co-occurrence**
  (prompt §22, §25).
* No "class imbalance caused collapse". Long same-condition runs and collapse may coincide
  (prompt §24); establishing cause needs a controlled-stream experiment, which is PARKed.
* No "BN drift caused collapse" without an intervention.
* No "Dropout caused collapse" — CASE 6 says Dropout/train-mode is *implicated* by the arm
  contrast, which is a statement about where to look next, not a mechanism proof.
* No generalisation beyond `ds004902 + EEGNet + subject-LOSO + this stream protocol`
  (prompt §35).
* No claim that any of this is new to the field (prompt §31) — see `TENT_METHOD_SPEC.md` §3.
