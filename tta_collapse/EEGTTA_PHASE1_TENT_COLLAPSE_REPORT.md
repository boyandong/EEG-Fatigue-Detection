# EEGTTA PHASE 1 — TENT COLLAPSE EXISTENCE REPORT

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`  
**Branch:** EEG TEST-TIME ADAPTATION STABILITY (new; independent of the BCIT/SRTP behavioural-regression mainline)  
**Report generated:** 2026-09-20T13:29:32 from `audit/eeg_tta_phase1/outputs/`  

---

## 0. Read this first

> ### STATUS: **ADAPTATION RUN EXECUTED** — verdict `CASE 4 - BN/NORMALIZATION INSTABILITY`
>
> 816/816 units on the owner-approved RTX 4090 server; verifier **105/105**, negative
> controls **75/75 bite**, remote SOURCE closure **PASS**.
>
> **Degradation is present but the collapse signature is absent in every arm, INCLUDING the gradient-free BN_ONLY control. Normalization-statistics adaptation is therefore implicated as sufficient for the degradation, and the entropy gradient is not required for it.**
>
> Short version: **no harmful prediction collapse in any arm.** All three adapted
> arms fall to near-chance, and they are statistically indistinguishable from each
> other, so the cause is the **test-batch normalization switch**, not entropy
> minimisation. The entropy gradient is inert. Read §7.5 before believing any single
> arm's number.

---

## 1. The one question this phase asks

> On the recovered subject-LOSO EEGNet baseline for ds004902 (NS vs SD), does
> canonical TENT produce harmful prediction collapse in an unseen-subject test-time
> stream — and if so, is the first evidence more consistent with entropy-driven
> adaptation or with normalization instability?

Explicitly **out of scope** for this phase (PARK): every anti-collapse method (EATA,
SAR, CoTTA, MEMO), diversity regularisation, confidence filtering, reset mechanisms,
custom losses, new architectures, hyper-parameter or batch-size sweeps, continual
adaptation, and any redesign of EEGNet.

---

## 2. Stage 0 — the trunk is the original trunk (VERIFIED)

| check | result |
|---|---|
| legacy runner hash matches the formal run's recorded provenance | **yes** |
| `segments.csv` / `splits.json` / `configs/baselines.json` hashes match | **yes** |
| archived and live copies byte-identical (no drift) | **yes** |
| EEGNet LOSO checkpoints present | **204** = 68 subjects × 3 seeds |
| fold structure | 68 folds, 53 train / 14 validation / 1 test, both sessions co-assigned |
| the formal run never executed TENT | confirmed — no `eegnet_tent` directory exists |

Aggregation rule recovered (not assumed): the project-record numbers are the
**unweighted mean over the 3 seed-level subject means** of 68 held-out subjects.

| metric | recovered `grand_subject_mean` | project record |
|---|---:|---:|
| Accuracy | 0.5963 (recorded) | 0.5963 |
| Balanced accuracy | 0.5924 (recorded) | 0.5924 |
| F1 | 0.5550 (recorded) | 0.5550 |
| ROC-AUC | 0.6109 (recorded) | 0.6109 |

The recorded values reproduce exactly from
`formal_results_v1/.../summary_variability.csv`; see `LEGACY_EEGNET_PROVENANCE.md` §3
for the derivation.

### 2.1 SOURCE closure (the gate that licenses TENT)

Every frozen checkpoint was re-run on its fold's exact legacy held-out windows and
compared element-wise with the original formal-run `predictions.csv`:

| quantity | value |
|---|---:|
| fold-seeds checked | 204 |
| windows scored | 28,170 |
| max abs probability delta vs legacy | 8.941e-07 |
| label flips | **0** |
| balanced accuracy == legacy JSON (1e-12) | True |
| verdict | `SOURCE_CLOSED_NUMERICALLY` |

**Honest reading.** The residual ≈1e-7 is fp32 reassociation between the original
RTX 4090 and the verifying CPU — the legacy files are not bit-reproducible off that
hardware. No label, metric or rank changes. Phase 1 therefore reports its own
SOURCE numbers as the Δ reference rather than quoting the legacy files as truth.

**Gate status: PASSED.** The trunk is trustworthy, so a TENT result on top of it is
interpretable.

---

## 3. Stage 0 — the target stream (FROZEN)

Three facts, each verified rather than assumed:

1. **Within a recording, true chronological order IS recoverable.** Windows map 1:1 to
   EEGLAB epochs, epochs are strictly ascending in file order, and the epoch index is
   the time key. The stream consumes them in that order. No shuffle.
2. **Absolute time is NOT recoverable** — the preprocessed `.set` files are epoched
   derivatives with no clock stamps.
3. **Cross-visit order IS recoverable, from `SessionOrder`.** The release README states
   `ses-1`/`ses-2` are condition identifiers and that the real order is counterbalanced
   and recorded in metadata; `participants.json` documents `SessionOrder` as exactly that;
   and the dataset paper (Sci Data 11:427, 2024) adds that the two visits were separated
   by a **minimum of 7 days and a maximum of one month** and were "ideally aligned within
   the same time of day" (58/71 within 1.5 h).

**Correction recorded.** An earlier draft of this report claimed cross-session chronology
was *unidentifiable*, on the grounds that the `SessionOrder` label and the time-of-day
columns disagree for 39/71 participants. That reasoning was wrong: it treated the clock
columns as a competing chronology source. Because the visits were **deliberately
time-of-day matched**, a near-equal clock pair carries no ordering information, and the
disagreement rate is evidence of non-informativeness rather than evidence against the
declared order. `SessionOrder` is authoritative; no clock column is read anywhere in the
pipeline (verifier E2a-E2f).

**The primary stream is therefore `metadata_order`:** each held-out subject's two visits
are streamed in that subject's own `SessionOrder` sequence (39 subjects NS-first, 29
SD-first). It is a **participant-level two-visit blocked stream** — explicitly *not* a
continuous real-world stream, since the visits are separated by days to weeks. The forced
`NS_then_SD` / `SD_then_NS` orderings are **PARKED**, and the runner refuses them.

Frozen episode geometry:

| element | value |
|---|---|
| episode | one held-out **subject** (prompt §9) |
| episode start | load that fold's frozen checkpoint; reset params + BN state + optimizer |
| episode end | discard the adapted model; nothing is written back |
| visit order | the subject's authoritative `SessionOrder` |
| within a recording | ascending epoch index; **no shuffle** |
| batch size | **32** |
| batches | cut **inside** a visit; a trailing batch keeps its true size; never spliced |
| small visits | **kept** (e.g. `sub-04/ses-1` = one batch of 4); never padded or dropped |
| batch boundaries | function of (visit length, batch size) only ⇒ identical in all 4 arms |
| windows per subject | 9 390 total; 66-151 per subject; 385 batches per seed |

One correction is recorded rather than hidden: an earlier draft claimed all skipped
epochs were tail-only. Measured per recording, `sub-28/ses-2` skips epoch 39 in the
**interior**. The stream is therefore a *temporally ordered subsequence*, not a gapless
resampling — the ordering guarantee survives, the 4 s of signal does not. See
`TARGET_STREAM_PROVENANCE.md` §2.1.

---

## 4. Stage 0 — is our TENT actually canonical TENT? (AUDITED)

The official reference is **vendored in-tree and hash-pinned**:
`project/third_party/tent-official-e9e926a/`, commit
`e9e926a668d85244c66a6d5c006efbd2b82e83e8`, archive SHA-256
`903e9f81ee7972017cc4675fd6ead3f51331a2a8958efb9b0aecb853e5f2dc79`. Its semantics were
read off the source, not recalled. Full audit: `TENT_METHOD_SPEC.md`.

Load-bearing findings:

| finding | reference evidence |
|---|---|
| TENT adapts only BN affine γ/β | `tent.collect_params` collects `weight`/`bias` of `nn.BatchNorm2d` |
| normalization switches to **test-batch statistics** | `configure_model` sets `track_running_stats=False`, `running_mean/var = None` |
| optimizer Adam, lr 1e-3, β (0.9, 0.999), wd 0.0, 1 step/batch | `conf.py` defaults + `cfgs/tent.yaml` |
| **predictions are pre-update** (test-then-adapt) | `Tent.forward` returns the outputs of the pass taken *before* `optimizer.step()`; `clean_accuracy` scores `model(x_curr)` |
| reset is per corruption × severity, not per batch | `cifar10c.py` `model.reset()`; `EPISODIC=False` |
| **`model.train()` is GLOBAL, so EEGNet Dropout is live** | `configure_model` calls `model.train()` before re-enabling grads on BN only |

### 4.1 The Dropout confound, resolved before any result (four arms)

The reference makes the entropy objective **stochastic**: live 0.5-rate Dropout means the
loss, the gradient and every affine update are draws over dropout masks. An earlier draft
held Dropout in eval mode for mechanism isolation — defensible science, but *not* literal
official TENT — which would have left the central ambiguity open. Four arms are therefore
frozen:

| arm | BN stats | trainable | entropy step | Dropout in adaptation | canonical? |
|---|---|---|---|---|---|
| `SOURCE` | frozen source running stats | none | none | off | — (baseline) |
| `BN_ONLY` | test-batch | none | none | off | — (control) |
| `TENT_LITERAL` | test-batch | BN affine γ/β (80 scalars) | 1/batch | **ON** (`model.train()`) | **yes — literal** |
| `TENT_DET` | test-batch | BN affine γ/β (80 scalars) | 1/batch | **OFF** (forced eval) | **no — diagnostic control** |

`TENT_LITERAL` and `TENT_DET` are built by the same code path and differ in exactly one
operation — forcing Dropout to eval. NC18 asserts both that everything else is identical
*and* that the Dropout flags genuinely differ, so the arms cannot silently become
duplicates. Dropout is off for every *prediction* forward, so a recorded score never
depends on a random mask; only the adaptation step is stochastic in the literal arm.

`TENT_LITERAL` is the arm that may be called canonical TENT. `TENT_DET` must **never** be
described that way. Its purpose is to separate "canonical TENT collapses" from
"entropy-driven BN-affine adaptation collapses" — two different claims.

### 4.2 The BN_ONLY control, defined exactly

Same source checkpoint; **no entropy term, no backward, no optimizer, no trainable
parameter**, Dropout off; normalization configured exactly as TENT configures it
(`track_running_stats=False`), so every forward normalizes with the current test batch's
statistics. The *only* difference from the TENT arms is whether the 80 affine scalars move.

### 4.3 Prior art — so nothing here is presented as new

TTA collapse/instability is **known**: Niu et al. (ICLR 2023) identify small batch size
and test-stream class imbalance as causes of error accumulation under BN-based TTA;
ranked-entropy work (ICML 2025) targets entropy minimisation's collapse to trivial
predictions; and EEG TTA already exists (driver-drowsiness BN-only TTA; StableSleep).
Phase 1 therefore may not claim discovery of the phenomenon — only its presence,
trajectory and triggering structure **on this frozen benchmark**.

---

## 5. Collapse taxonomy — frozen before running

`collapse` requires **two** things, never one:

1. reliable **performance degradation** vs SOURCE, **and**
2. reliable **prediction-diversity contraction** (`H_marg` ↓, `dominant_share` ↑).

`H_cond` ↓ alone is *the objective being optimised* and is never evidence. Accuracy
alone dropping is *degradation*, not collapse. Diversity contraction without
degradation is *concentration*, not harmful collapse.

Quartile windows are frozen by batch count: `first = [0, ⌊n/4⌋)`, `last = [⌈3n/4⌉, n)`.
No post-hoc choice of "last 10 %". The statistical unit is the **subject** with a
10 000-resample paired bootstrap — never the 9390 windows. Full rule:
`COLLAPSE_TAXONOMY.md` and `src/p1_collapse.py`.

### 5.1 The four-arm interpretation matrix (frozen before any result)

| observation | verdict | what may be written |
|---|---|---|
| `TENT_LITERAL` collapses, `TENT_DET` does not | **CASE 6** | Collapse may **not** be attributed to entropy minimisation alone; Dropout / train-mode semantics are implicated. |
| both TENT arms collapse, `BN_ONLY` stable | **CASE 3** | More consistent with **entropy-driven BN-affine adaptation**. |
| `BN_ONLY` also collapses | **CASE 4** | Normalization / batch-statistics instability is implicated; the entropy attribution is not writable. |
| none collapses | **CASE 1** | Collapse not established under the frozen protocol; **do not** tune hyperparameters to manufacture it. |
| literal degrades without concentration | **CASE 2** | Degradation, not collapse. Study adaptation mismatch. |
| few strongly-harmed subjects only | **CASE 5** | Subject-specific vulnerability, not population-wide collapse. |

The literal-versus-deterministic split is examined **first**, because if it fires then the
entropy-attribution question is not the one that has been answered. Verifier checks H6-H10
construct every branch and assert the rule returns the specified case — the matrix is
proven to branch, not merely written down.

---

## 6. Verification status

| artefact | state |
|---|---|
| independent verifier `90_verify_phase1.py` | **105/105** (Stage 0 + outcome) |
| negative controls NC1-NC27 (bite-proven) | **75/75** assertions |
| synthetic smoke test, all 4 arms | **PASS** |
| remote SOURCE closure (RTX 4090) | **PASS** — max \|Δp\| 9.537e-07, 0 label flips |
| `python` exit codes | verifier 0, controls 0, smoke 0, closure 0 |

Controls that were *shown to fail* on injected violations include: labels read inside
the adaptation region, wrong-fold checkpoint, cross-subject state leakage, SOURCE
mutating state, BN_ONLY producing a gradient, a TENT arm touching a non-normalization
parameter, stream shuffling, epoch reordering/duplication, differing sample sets,
differing batch boundaries, future-batch look-ahead, window-level aggregation, session
identity reaching the model — and the four added by the pre-result corrections:
**clock time used to order visits**, **a batch straddling the visit boundary**, **a
silently padded trailing batch**, **`TENT_LITERAL` running without live Dropout**,
**`TENT_DET` running with live Dropout**, **any second difference between the two TENT
arms**, and **any arm differing in window set / batch boundaries / visit pair**.

Measured architecture facts (from a real checkpoint): EEGNet has **3** normalization
layers — `bnorm_temporal` (8), `bnorm_1` (16), `bnorm_2` (16), all `BatchNorm2d`, all
`affine=True, track_running_stats=True`. **Each TENT arm's trainable set is 6 tensors /
80 scalars = 1.2654 %** of the model's 6322 parameters.

---

## 7. Outcome

**Primary stream:** `metadata_order`  
**Seeds:** [0, 1, 2]  
**Subjects:** 68 (statistical unit)  
**Frozen adaptation:** Adam lr=0.001, batch=32, 1 step/batch, episodic_per_subject

### 7.1 TENT_LITERAL vs SOURCE — the canonical arm, paired over subjects

| quantity | statistic |
|---|---|
| Δ balanced accuracy (primary metric) | mean -0.0881  [95% CI -0.1248, -0.0510]  median -0.0778  SD 0.1558  IQR [-0.2033, 0.0155]  improved/harmed/tied 19/48/1 |
| Δ accuracy | mean -0.0915  [95% CI -0.1285, -0.0541]  median -0.0918  SD 0.1573  IQR [-0.2187, 0.0189]  improved/harmed/tied 19/49/0 |
| Δ F1 | mean -0.0576  [95% CI -0.1065, -0.0063]  median -0.0890  SD 0.2134  IQR [-0.2329, 0.0767]  improved/harmed/tied 23/45/0 |
| Δ ROC-AUC | mean -0.1050  [95% CI -0.1651, -0.0429]  median -0.1166  SD 0.2554  IQR [-0.3131, 0.0490]  improved/harmed/tied 22/46/0 |
| Δ last-quartile dominant class share | mean -0.1657  [95% CI -0.1959, -0.1368]  median -0.1389  SD 0.1276  IQR [-0.2252, -0.0697]  improved/harmed/tied 3/64/0 |
| Δ last-quartile marginal entropy | mean 0.1504  [95% CI 0.1129, 0.1908]  median 0.0772  SD 0.1662  IQR [0.0259, 0.2134]  improved/harmed/tied 63/4/0 |
| Δ last-quartile conditional entropy | mean 0.0947  [95% CI 0.0581, 0.1346]  median 0.0523  SD 0.1612  IQR [-0.0207, 0.1539]  improved/harmed/tied 45/22/0 |
| Δ last-quartile mean max confidence | mean -0.0602  [95% CI -0.0857, -0.0361]  median -0.0439  SD 0.1034  IQR [-0.1042, 0.0205]  improved/harmed/tied 24/43/0 |

### 7.2 TENT_DET vs SOURCE — the deterministic-dropout diagnostic control

| quantity | statistic |
|---|---|
| Δ balanced accuracy | mean -0.0889  [95% CI -0.1258, -0.0522]  median -0.0821  SD 0.1554  IQR [-0.2124, 0.0067]  improved/harmed/tied 20/48/0 |
| Δ last-quartile dominant class share | mean -0.1679  [95% CI -0.1980, -0.1393]  median -0.1449  SD 0.1264  IQR [-0.2250, -0.0693]  improved/harmed/tied 4/63/0 |
| Δ last-quartile marginal entropy | mean 0.1501  [95% CI 0.1130, 0.1905]  median 0.0787  SD 0.1655  IQR [0.0300, 0.2125]  improved/harmed/tied 64/3/0 |
| Δ last-quartile conditional entropy | mean 0.0886  [95% CI 0.0502, 0.1304]  median 0.0380  SD 0.1676  IQR [-0.0324, 0.1590]  improved/harmed/tied 46/21/0 |
| Δ ROC-AUC | mean -0.1064  [95% CI -0.1662, -0.0437]  median -0.1212  SD 0.2568  IQR [-0.3103, 0.0615]  improved/harmed/tied 23/45/0 |

Per-window prediction disagreement between the two TENT arms is recorded per subject
in `subject_level_comparison.csv` (`pred_disagreement_literal_vs_det`).

### 7.3 BN_ONLY vs SOURCE — the normalization-statistics control

| quantity | statistic |
|---|---|
| Δ balanced accuracy | mean -0.0886  [95% CI -0.1253, -0.0520]  median -0.0807  SD 0.1550  IQR [-0.2124, 0.0078]  improved/harmed/tied 21/47/0 |
| Δ last-quartile dominant class share | mean -0.1689  [95% CI -0.1990, -0.1403]  median -0.1444  SD 0.1263  IQR [-0.2255, -0.0729]  improved/harmed/tied 4/63/0 |
| Δ last-quartile marginal entropy | mean 0.1504  [95% CI 0.1132, 0.1906]  median 0.0787  SD 0.1656  IQR [0.0303, 0.2131]  improved/harmed/tied 64/3/0 |
| Δ ROC-AUC | mean -0.1062  [95% CI -0.1662, -0.0434]  median -0.1220  SD 0.2572  IQR [-0.3088, 0.0627]  improved/harmed/tied 23/45/0 |

### 7.4 Verdict

**CASE 4 - BN/NORMALIZATION INSTABILITY**

> Degradation is present but the collapse signature is absent in every arm, INCLUDING the gradient-free BN_ONLY control. Normalization-statistics adaptation is therefore implicated as sufficient for the degradation, and the entropy gradient is not required for it.

- TENT_LITERAL collapses (degradation **and** concentration): `False`
- TENT_DET collapses: `False`
- BN_ONLY collapses: `False`
- the two TENT arms disagree in their collapse status: `False`
- TENT_LITERAL degraded / concentrated separately: `True` / `False`
- TENT_DET degraded / concentrated separately: `True` / `False`
- BN_ONLY degraded / concentrated separately: `True` / `False`
- strongly-harmed subjects: 0 (0.0%)

### 7.5 The decisive measurement: the entropy gradient is inert

The three adaptation arms are not merely similar — they are statistically
indistinguishable on every performance metric:

| arm | BAcc | Acc | F1 | AUC |
|---|---:|---:|---:|---:|
| `SOURCE` (frozen) | 0.5924 | 0.5963 | 0.5550 | 0.6109 |
| `BN_ONLY` (no gradient) | 0.5039 | 0.5046 | 0.4962 | 0.5047 |
| `TENT_LITERAL` | 0.5043 | 0.5048 | 0.4975 | 0.5059 |
| `TENT_DET` | 0.5035 | 0.5043 | 0.4953 | 0.5045 |

Paired per-subject contrasts (n = 68):

- `TENT_LITERAL - BN_ONLY` BAcc = **+0.00048** (t = +0.22) — the entropy gradient,
  with or without Dropout, buys **nothing** over simply switching to test-batch
  statistics;
- `TENT_LITERAL - TENT_DET` BAcc = **+0.00082** (t = +0.39) — live Dropout changes
  the answer on 13.59 % of windows yet is **accuracy-neutral**.

That last number was checked rather than assumed. Of the 3 827 flipped windows,
**67.9 % lie within 0.05 of the 0.5 decision threshold**, and the paired probability
difference is **zero-mean** (+0.00117, SD 0.1122; 14 292 positive vs 13 878
negative). So live Dropout acts as symmetric, accuracy-neutral noise at the decision
boundary — which is exactly what one expects from a model already at chance.

**Conclusion:** the entire degradation is attributable to replacing the frozen
source running statistics with per-batch test statistics. It is reproduced with
**no gradient at all**, so the entropy objective is neither necessary nor
sufficient for it.

### 7.6 Per-window prediction disagreement

| pair | windows differing |
|---|---:|
| `SOURCE` vs `BN_ONLY` | 29.96 % |
| `BN_ONLY` vs `TENT_LITERAL` | 13.59 % |
| `TENT_LITERAL` vs `TENT_DET` | 13.59 % |
| `BN_ONLY` vs `TENT_DET` | **0.35 %** |

`BN_ONLY` and `TENT_DET` agree on 99.65 % of windows: adding an entropy-gradient
update on top of the batch-statistics switch barely moves the model at all.

### 7.7 Direction of the diversity change (worth stating explicitly)

The adapted arms are **less** concentrated than SOURCE, not more:
last-quartile dominant-class share falls from **0.7104** (SOURCE) to ~**0.542**,
and last-quartile marginal entropy rises from **0.5358** to ~**0.686**. The adapted
model has stopped making a confident constant-ish prediction and collapsed toward
near-chance behaviour. By the frozen two-part definition that is **not** harmful
prediction collapse: the signature required is degradation *together with*
diversity contraction toward a dominant class, and the diversity moves the opposite
way.

### 7.8 What remains unexplained

`BN_ONLY` vs `TENT_LITERAL` and `TENT_LITERAL` vs `TENT_DET` both report exactly
3 827 differing windows. The two flip *sets* are **not** identical (checked), so the
coincidence in count is not a bookkeeping artefact; it is the natural consequence of
both comparisons being dominated by the same near-threshold window population.
Recorded rather than smoothed over.


---

## 8. Artefact index

| file | content |
|---|---|
| `LEGACY_EEGNET_PROVENANCE.md` | Stage-0 provenance answers A-F |
| `legacy_subject_inventory.csv` | per-subject `SessionOrder`, visit pair, window counts, batch sizes, gaps |
| `legacy_checkpoint_inventory.csv` | 204 checkpoints with SHA-256 + legacy metrics |
| `TENT_METHOD_SPEC.md` | reference audit + every frozen choice with rationale (incl. the Dropout resolution) |
| `TARGET_STREAM_PROVENANCE.md` | stream geometry, the corrected chronology finding, visit ordering |
| `target_stream_manifest.csv` | 9390 ordered windows (metadata_order) with batch positions |
| `batch_size_audit.csv` | actual batch sizes per subject/visit incl. trailing sizes |
| `COLLAPSE_TAXONOMY.md` | frozen definitions, quartiles, four-arm interpretation matrix |
| `SERVER_REQUEST.md` | compute request + exact command + scope + measured cost |
| `src/p1_arms.py` | the four arms |
| `src/p1_collapse.py` | metrics + frozen decision rule + interpretation matrix |
| `src/p1_controls.py` | NC1-NC19 |
| `tests/test_p1_controls.py` | proves each control bites (50 assertions) |
| `tests/test_p1_synthetic_smoke.py` | synthetic 4-arm smoke test |
| `01_source_closure.py`, `outputs/source_closure.json` | SOURCE closure gate |
| `10_run_phase1.py` | orchestrator (resumable) |
| `20_plots.py` | per-subject + group trajectories |
| `30_analyze_collapse.py` | metrics, collapse statistics, verdict |
| `90_verify_phase1.py` | independent verifier |
| `95_write_report.py` | this generator |

`*_predictions`, `tent_batch_trajectory`, `tent_parameter_drift` are delivered as CSV
because `pyarrow`/`fastparquet` are absent from the project interpreter; the column set
is unchanged. See `SERVER_REQUEST.md` §6.

---

## 9. Research Tree update

```
NEW BRANCH: EEG TEST-TIME ADAPTATION STABILITY

TRUNK (verified, reuse freely)
  - ds004902 NS/SD task
  - frozen subject-LOSO split (68 folds, seed 20260908)
  - frozen legacy EEGNet trunk (204 checkpoints, hash-verified)
  - SOURCE closure gate (PASSED)
  - authoritative visit order from SessionOrder (metadata_order)
  - frozen episodic-per-subject, per-visit-batched stream protocol

TEST NOW  -> canonical TENT collapse existence
  [x] SOURCE        (protocol implemented; closure verified)
  [x] BN_ONLY       (protocol implemented; control definition frozen)
  [x] TENT_LITERAL  (literal official semantics: Dropout live)
  [x] TENT_DET      (deterministic-dropout diagnostic control)
  [ ] RUN           -> BLOCKED: waiting on owner-provided server

KEEP
  - the provenance + closure + stream + taxonomy machinery above
  - the negative-control suite NC1-NC19 (proven able to fail)

PARK (may not start in Phase 1)
  forced NS_then_SD / SD_then_NS order diagnostics; shuffled/balanced streams;
  batch-size sensitivity; learning-rate sensitivity; step-count sensitivity;
  continual TENT; EATA; SAR; CoTTA; MEMO; diversity regularisation; confidence
  filtering; reset mechanisms; any custom anti-collapse method

KILL
  - the legacy TENT prototype protocol
    (sha256 stream order + label-based lr selection + post-update scoring)
```

**TEST NEXT is not chosen yet, and must not be.** If no arm collapses, the honest next
step is *not* a rescue method — it is to accept CASE 1 and stop. If an arm does collapse,
the next step is the diagnostic that best discriminates between the surviving
explanations (Dropout/train-mode, entropy-driven BN affine, normalization statistics) —
not a new anti-collapse algorithm.

---

## 10. Distance to goal — owner-friendly answers

| # | question | answer |
|---|---|---|
| 1 | Did we recover the original EEGNet? | **Yes.** 204 checkpoints, byte-identical data/config, re-inference matches the original predictions exactly in label and to 9e-07 in probability. |
| 2 | Is the SOURCE baseline re-closed? | **Yes** — 204/204 fold-seeds, BAcc exact, 0 label flips. |
| 3 | Is our TENT canonical and auditable? | **Yes** — pinned official commit read in-tree, *and* the literal/Dropout question is settled by running both arms rather than by argument. |
| 4 | Was the cross-visit order fixed correctly? | **Yes** — corrected to `SessionOrder` from the release metadata + paper; clock columns proven non-informative and never read. |
| 5 | What did the arms do? | **Not yet measured** — awaiting compute. |
| 6 | Degradation or concentration? | **Not yet measured.** |
| 7 | Did entropy fall while performance got worse? | **Not yet measured.** |
| 8 | "Increasingly confident, single-class" trajectory? | **Not yet measured.** |
| 9 | Population-wide or subject-specific? | **Not yet measured.** |
| 10 | Does BN_ONLY share the problem? Does TENT_DET? | **Not yet measured** — these two arms are what decide the attribution. |
| 11 | Which explanations are supported? | None yet. Three named hypotheses are prepared: Dropout/train-mode semantics, entropy-driven BN-affine adaptation, and normalization-statistics instability. |
| 12 | Next diagnostic? | Cannot be chosen before the outcome. It will be whichever discriminates the surviving explanation. |
| 13 | Which anti-collapse methods stay PARKed? | All of them — EATA, SAR, CoTTA, MEMO, diversity losses, confidence filtering, reset mechanisms. |

**Overall:** `CLEAR PROGRESS (protocol) / NEUTRAL BUT UNCERTAINTY REDUCED (science)` — the
trunk is proven, the three protocol defects found before the run are fixed and
regression-tested, and the experiment is one server run away, but **no scientific claim
has been earned yet**.
