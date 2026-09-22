# Branch B — Test-Time Adaptation Stability

**Question.** Does online test-time adaptation — especially entropy minimisation — become unstable
or **collapse** on unseen-subject EEG streams, and if so, what mechanism drives it?

**Status: Phase 1 is COMPLETE and at a hard stop.** Verdict
**`CASE 4 — BN/NORMALIZATION INSTABILITY`**, established by a real formal experiment that was
executed and independently verified — not by a taxonomy, not by a specification.

This branch is **scientifically independent** of `../functional_prediction/`. It shares **no**
dataset, endpoint, representation or conclusion with it — it reads the frozen ds004902 source
trunk from `../shared/` and nothing else. Neither branch is evidence for the other.

---

## 1. What is shared, and what is not

This branch holds **no copy** of the model trunk. It reaches the frozen ds004902 source trunk
through relative paths declared in one place, `src/p1_common.py`:

| artefact | canonical location | how this branch reaches it |
|---|---|---|
| 9,390-window manifest | `../shared/ds004902_source_trunk/legacy_apparatus/outputs/source_only_500hz_v1/` | `P.ACTIVE_DATA` |
| frozen subject-LOSO split (68 folds, seed 20260908) | same directory, `splits.json` | `P.ACTIVE_DATA` |
| 61-channel order, label mapping | same directory, `channels.json` / `segments.csv` | `P.ACTIVE_DATA` |
| **204 legacy EEGNet checkpoints** | not redistributed — manifest at `../shared/ds004902_source_trunk/checkpoints/` | `P.FORMAL_RESULTS` |
| EEGNet architecture + optimiser + batch size | `../shared/ds004902_source_trunk/legacy_apparatus/configs/baselines.json` | `P.LEGACY` |
| the runner that trained them | `../shared/ds004902_source_trunk/legacy_apparatus/run_baselines.py` | `P.LEGACY` |
| pinned official TENT reference | `../shared/ds004902_source_trunk/third_party/sources.json` (commit `e9e926a6`) | documentation + hash pin |
| raw ds004902 | external dataset — see `../docs/reproducibility.md` | `P.METADATA` |

The checkpoint tree is the **single** source of truth: 204 checkpoints with 204 distinct
contents. The handful of same-architecture checkpoints elsewhere were registered as either proven
byte-identical copies or smoke variants.

---

## 2. The experimental design

| arm | BN statistics | trainable | entropy step | Dropout in the scored forward | canonical? |
|---|---|---|---|---|---|
| `SOURCE` | frozen source running stats | none | none | off | — baseline |
| `BN_ONLY` | test-batch | none | none | off | — gradient-free control |
| `TENT_LITERAL` | test-batch | BN affine γ/β (80 scalars) | 1/batch | **ON** (`model.train()`) | **yes — literal TENT** |
| `TENT_DET` | test-batch | BN affine γ/β (80 scalars) | 1/batch | **OFF** | no — diagnostic control |

Design commitments, each with a reason on record:

* **One pre-update forward serves both scoring and entropy.** `entropy_forward` returns
  `(logits, loss)` together, so the recorded prediction and the adaptation objective cannot
  diverge. This is what makes `TENT_LITERAL` literal rather than approximate.
* **Episodic per subject.** Parameters, BN state and optimiser state are reset from that fold's
  checkpoint at episode start and discarded at the end. **No adaptation crosses a subject.**
* **Visit order is `SessionOrder`** (39 NS-first / 29 SD-first, from the release metadata). The
  time-of-day columns are deliberately time-of-day-matched across visits and carry no ordering
  information; they are never read to order a stream.
* **Batches never cross a visit**; a trailing batch keeps its true size (`sub-04/ses-1` is a
  legitimate batch of 4).
* **Frozen per-unit RNG** so the stochastic literal arm is reproducible without being
  de-stochasticised: `SHA256("EEGTTA-PHASE1|v1|variant|arm|subject|model_seed|batch")`.
* **Frozen hyper-parameters, no sweep:** Adam lr 1e-3, β (0.9, 0.999), wd 0, 1 step per batch,
  batch size 32.
* **`SOURCE` closure was proved before any comparison** — locally and on the remote 4090 — so this
  is a comparison against the real benchmark, not a drifted re-implementation.

---

## 3. The collapse taxonomy

`collapse` requires **two** things: reliable performance degradation **and** reliable
prediction-diversity contraction. Either one alone is not collapse.

* `H_cond ↓` alone is *the objective working* — never evidence of collapse.
* Accuracy dropping alone is *degradation*.
* Diversity contracting without degradation is *concentration*.

The statistical unit is the **subject**, with a **10,000-resample paired bootstrap**. Never the
9,390 windows. Quartile windows are frozen by batch count, not chosen after seeing a trajectory.
Full rule: `COLLAPSE_TAXONOMY.md` and `src/p1_collapse.py`.

---

## 4. Result

**Verdict `CASE 4 — BN/NORMALIZATION INSTABILITY`.**

| arm | BAcc | ΔBAcc vs SOURCE (95% CI) | Δ dominant share | Δ H_marg |
|---|---:|---|---:|---:|
| `SOURCE` | 0.5924 | — | — | — |
| `BN_ONLY` | 0.5039 | −0.0886 [−0.1253, −0.0520] | −0.1689 [−0.1990, −0.1403] | +0.1504 [+0.1132, +0.1906] |
| `TENT_LITERAL` | 0.5043 | −0.0881 [−0.1248, −0.0510] | −0.1657 [−0.1959, −0.1368] | +0.1504 [+0.1129, +0.1908] |
| `TENT_DET` | 0.5035 | −0.0889 [−0.1258, −0.0522] | −0.1679 [−0.1980, −0.1393] | +0.1501 [+0.1130, +0.1905] |

Three facts carry the verdict:

1. **No harmful collapse in any arm.** The diversity change runs the *opposite* way to the
   collapse signature: dominant-class share falls **0.7104 → ~0.542** and marginal entropy
   *rises* **0.5358 → ~0.686**. The adapted model stopped making a confident near-constant
   prediction and drifted toward chance. **0 subjects** met the strongly-harmed criterion.
2. **The entropy gradient is inert.** `TENT_LITERAL − BN_ONLY` = **+0.00048** BAcc (t = +0.22),
   and `BN_ONLY` vs `TENT_DET` agree on **99.65 %** of windows.
3. **The normalisation switch is sufficient.** The gradient-free `BN_ONLY` control reproduces the
   entire ~8.9-point degradation, so entropy minimisation is not required to produce it.

**State the attribution, not a cause.** Switching from frozen source BatchNorm statistics to
target-batch statistics was **sufficient to reproduce** the observed degradation, while the
entropy-gradient step produced **no detectable additional degradation** under this protocol. That
localizes the first-order failure to the normalization switch. It does **not** establish that
BatchNorm statistics are the causal mechanism.

`SOURCE` reproduced the historical baseline exactly (`BAcc = 0.5924169784325324`, matching the
record to 16 digits), so this is a comparison against the real benchmark.

**What is NOT established: *why* the test-batch normalisation switch harms performance.** That is
a separate question and needs a new PI decision. This branch has localized *where* the degradation
arises and shown *that* entropy minimisation is inert — not the mechanism underneath.

---

## 5. Verification

| gate | result |
|---|---|
| independent verifier `90_verify_phase1.py` | **105/105** |
| negative controls `tests/test_p1_controls.py` | **75/75 bite** (NC1–NC27) |
| synthetic smoke test `tests/test_p1_synthetic_smoke.py` | PASS |
| remote SOURCE closure (RTX 4090) | max abs Δp 9.537e-07, **0 label flips** |
| executed units | **816/816** (68 subjects x 3 seeds x 4 arms) |
| windows scored | 112,680 |

The canonical TENT semantics were audited against the **official reference** at commit
`e9e926a668d85244c66a6d5c006efbd2b82e83e8`, hash-pinned in
`../shared/ds004902_source_trunk/third_party/sources.json` (core source SHA-256
`d854e1f65f741aa1632dfb55420ca1bcf5405c978bef890e45caad04980514c8`). The reference is **cited and
hash-pinned, not vendored** into this repository.

---

## 6. Next step — and what is NOT yet proven

**Phase 1 is at a hard stop and licenses nothing further.** Phase 2 requires a **new PI decision**.

The highest-information candidate is a **statistics-geometry diagnostic**: compare the source
running statistics (μ, σ) against the test-batch statistics (μ_t, σ_t) actually used, and relate
the discrepancy to the per-subject ΔBAcc. It is cheap and needs **no adaptation at all**.

**It is a proposal. No artefact for it exists in this repository, and it is not described as
completed anywhere.**

---

## 7. PARKED — not started, not licensed, no artefact exists

> SAR · DELTA · T-TIME · T3A · CoTTA · BFT · EATA · MEMO · diversity regularisation ·
> confidence filtering · reset mechanisms · anti-collapse redesign · hyper-parameter sweeps ·
> batch-size sweeps · continual TENT · forced `NS_then_SD` / `SD_then_NS` order diagnostics

Every one of these appears **only as prose in this list**. None is implemented, and no artefact in
this branch is named for any of them. **Do not describe any of them as completed.**

---

## 8. Never write these

* "TENT collapses" or "TENT is bad for EEG" — TENT did not collapse. It degraded to chance, and so
  did the **gradient-free control**, by the same amount.
* "entropy minimisation caused the degradation" — the paired contrast over 68 subjects is
  **+0.00048** with a confidence interval containing zero.
* "the diversity change is a collapse" — it runs the opposite direction.
* `TENT_DET` called "canonical TENT" — only `TENT_LITERAL` is literal.
* Any claim that the *mechanism* has been identified. Only the attribution has.

---

## 9. Files

| path | what it is |
|---|---|
| `TENT_METHOD_SPEC.md` | reference audit + every frozen choice with rationale |
| `COLLAPSE_TAXONOMY.md` | frozen definitions, quartiles, four-arm interpretation matrix |
| `TARGET_STREAM_PROVENANCE.md` | stream geometry and the corrected chronology finding |
| `LEGACY_EEGNET_PROVENANCE.md` | how the shared frozen trunk was recovered and proved |
| `EEGTTA_PHASE1_TENT_COLLAPSE_REPORT.md` | **the report** |
| `SERVER_RUNBOOK.md` | server class, environment, gates, exact command (host redacted) |
| `RESEARCH_TREE_UPDATE.md` | the branch's research-tree revision history |
| `research_tree.md` | KEEP / TEST NEXT / PARK / KILL, as the agent workspace holds it |
| `src/`, `10_run_phase1.py`, `30_analyze_collapse.py`, `90_verify_phase1.py` | the apparatus |
| `tests/` | negative controls and the synthetic smoke test |
| `evidence/metrics/` | every aggregate artefact of the executed run |
| `evidence/units/` | the 816 per-unit records of the executed run |
| `evidence/plots/` | run plots |

⚠️ **Host redaction.** The remote execution host, its port, and the local SSH key path were
redacted from `SERVER_RUNBOOK.md`, `05_remote.py` and `evidence/metrics/KEY_FINDINGS.json` when
this public snapshot was produced. The SSH password was never stored in this repository — it is
read from the environment variable `EEGTTA_SSH_PASSWORD` at run time only. See
`../docs/project-history.md` §"Path portability".
