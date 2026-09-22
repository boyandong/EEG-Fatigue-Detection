# REPRODUCIBILITY.md

How to check the claims in this repository yourself, in increasing order of cost. Read §1 before
promising anyone that a number can be regenerated.

> **The short version.** The **data-free verification runs from a clone in about a minute** and
> is the strongest thing most readers can do (§2). Everything past that needs a dataset that this
> repository does not and cannot redistribute (§3), and the TTA result additionally needs a GPU
> host (§5).

---

## 1. What "reproducible" means here, precisely

This project distinguishes three levels, and uses the words exactly:

| level | meaning | needs |
|---|---|---|
| **Re-checkable** | the published numbers can be verified against the published artifacts | a clone |
| **Re-runnable** | the pipeline can be executed end to end | a clone + the datasets |
| **Re-executable** | the original execution environment can be restored | a clone + datasets + the original hardware/container |

This snapshot is **re-checkable** everywhere, **re-runnable** for the ds004902 trunk and the
Phase 1–2 lanes, and **partially re-executable** — the TTA Phase 1 container is gone and the two
branches ran under different Python/torch versions. `docs/environment-audit.md` §5 lists exactly what
is not reconstructible. **Do not describe this repository as fully reproducible.**

The reason the distinction is kept honest: this project's own rule is that a claim is not
accepted until a *separate* script re-derives it, ideally from raw sources rather than from the
pipeline's own intermediate output. That standard is what the published verifiers implement.

---

## 2. Level 1 — data-free verification (no dataset, no GPU)

Install dependencies, then run these three suites directly. **They are plain scripts, not pytest
suites** — `pytest` is not installed in the project interpreter, and each returns a non-zero exit
code on failure.

```bash
pip install -r requirements.txt
```

### 2.1 The representation's mathematical contract — 16/16

```bash
cd functional_prediction && python tests/test_mechanism.py
```

Checks the frozen mechanism mathematics on **synthetic signals**: the `M` / `J` contract,
personal-offset cancellation, bitwise determinism on rerun, the `q_theta + q_alpha + q_beta = 1`
composition identity, the epsilon floor, and the exact ROI partition sizes (F=16, CT=28, PO=17).

### 2.2 The nested-CV and inference machinery — 22/22

```bash
cd functional_prediction && python tests/test_phase2_ridge.py
```

Establishes that the hand-written SVD ridge solver is **numerically equivalent to scikit-learn's
`Ridge`** — the substitution is only legitimate if it is — and that the nested-LOSO machinery
respects the leakage boundary. Also checks the permutation p-value arithmetic
`p = (1 + #{>= obs}) / (B + 1)` and the bootstrap confidence-interval arithmetic against their
closed forms.

This is the test that makes the Phase 2 negative result's *inference* trustworthy, independently
of its *numbers*.

### 2.3 The TTA arm semantics — synthetic smoke

```bash
cd tta_collapse && python tests/test_p1_synthetic_smoke.py
```

Uses a **tiny model**, no data. Proves the properties that make the `CASE 4` verdict literal:

* one pre-update forward serves both scoring and entropy — **max|diff| = 0.000e+00**;
* exactly one forward per batch (4 forwards / 4 batches);
* both TENT arms forward in `model.train()` (official configuration) while `SOURCE` and
  `BN_ONLY` forward in `model.eval()`;
* the per-unit RNG convention is order-independent and per-batch distinct;
* `TENT_LITERAL` **replays bit-exactly**;
* batches never cross a block, and the final batch keeps its true size.

It also reports the normalization-layer inventory of the tiny model and notes the production
figures (3 layers, 80 affine scalars) for comparison.

On the audit machine these produced **16/16**, **22/22** and **SMOKE: PASS**.

### 2.4 Documentation-integrity checks — two scripts

```bash
python docs/verify_public_numbers.py    # every documented number vs its artifact
python docs/check_links.py              # every relative Markdown link resolves
```

`verify_public_numbers.py` is the public counterpart of the project's own rule that a claim is
not accepted until a separate script re-derives it. It re-derives **nothing** from the pipelines —
it reads the published `evidence/` artifacts and asserts that the numbers printed in the READMEs
are the numbers those artifacts actually contain. It covers the trunk manifest (68 subjects /
9,390 windows / 61 channels / 500 Hz / 68 folds), both anchor SHA-256 values, the EEGNet
benchmark, the Phase 2 negative result, all four TTA arms with their confidence intervals, the
`CASE 4` verdict and its directional facts, the checkpoint manifest, and the branch-independence
governance statements. **No dataset, GPU or network required.**

On the audit machine: **60/60 checks passed.**

`check_links.py` fails on any relative Markdown link that does not resolve. External links are
reported but deliberately **not** fetched — it performs no network access. The superseded
prototype under `archive/legacy/` is excluded, because it carries the original project's links and
is not maintained here.

On the audit machine: **21/21 relative links resolve.**

---

## 3. Level 2 — the datasets (not redistributed)

This repository ships **dataset identifiers, expected local layout, preprocessing entry points and
manifest-generation instructions**. It ships **no raw EEG**.

### 3.1 ds004902 — the shared source trunk

| item | value |
|---|---|
| identifier | **ds004902** (OpenNeuro) |
| content used | 4-second eyes-open tonic EEG, two visits per participant |
| access | <https://openneuro.org/datasets/ds004902> |
| expected local layout | `data/ds004902/preprocessed/` — one `<subject>_ses-<N>.set` (+ `.fdt`) per recording, plus `data/ds004902/metadata_behavior/` for the release metadata |
| preprocessing entry point | `shared/ds004902_source_trunk/legacy_apparatus/prepare_data.py` |
| config | `shared/ds004902_source_trunk/legacy_apparatus/configs/source_only_data.json` |
| produces | the 9,390-window manifest, 61-channel order, label mapping, waveform cache, and `splits.json` |

**Only 500 Hz records are admitted**, by a frozen rule in the config — the 5,000 Hz records are
excluded, and the participant who then lacked a usable pair is excluded whole rather than
substituted. Result: **68 valid paired subjects of 71**, **9,390 windows** (class 0: 4,735 /
class 1: 4,655).

The raw tree is **read-only**. `prepare_data.py` writes only under
`legacy_apparatus/outputs/`.

**Anchor hashes** — if your build does not match these two, nothing downstream is comparable:

| artefact | SHA-256 |
|---|---|
| `segments.csv` (9,390-window manifest) | `5eba619fc0dd516f8caf72a86fd36a34ca07c589df9d269b2bcdbd53c1c3a744` |
| `splits.json` (68-fold subject-LOSO, seed 20260908) | `db02bab96f8147bffa4836967a29c0763bc9f8130fa994252ed269649070c184` |

### 3.2 The BCIT driving dataset — Branch A's behavioural endpoint

| item | value |
|---|---|
| content used | real vehicle channels, lane deviation `LN` in metres |
| access | per the dataset's own access terms — the owner must supply the location; payloads are **not** redistributed here |
| expected local layout | an immutable Tier-1 payload tree plus a metadata tree, referenced by config |
| endpoint spec | `functional_prediction/BEHAVIOR_ENDPOINT_SPEC.md` (frozen; not redefinable) |
| pairing key | `legacy_labID` — **never** `sub-NN`; a naive `sub-NN` join is 89 % wrong |

Large Phase-4A-family caches (tens of GB) lived **outside** the repository on a separate volume
and are not republished. They must be regenerated locally; the phase scripts document how.

### 3.3 The trunk checkpoint set

The 204 EEGNet LOSO checkpoints are **not redistributed**. `shared/ds004902_source_trunk/checkpoints/`
ships a hash manifest, the naming convention and regeneration instructions. Regenerate with:

```bash
cd shared/ds004902_source_trunk/legacy_apparatus
python prepare_data.py --config configs/source_only_data.json
python run_baselines.py --config configs/baselines.json     # stage: formal, models: [eegnet]
python verify_baselines.py
```

---

## 4. Level 2b — re-checking the published numbers without re-running anything

Every headline number in the READMEs is backed by a published artifact. To audit a claim, open the
artifact rather than re-running a pipeline:

| claim | artifact |
|---|---|
| trunk benchmark: Acc 0.5963 / BAcc 0.5924 / F1 0.5550 / AUC 0.6109 | `tta_collapse/evidence/metrics/KEY_FINDINGS.json` (`absolute_levels.source`) |
| `Q²_skill(M1) = −0.0574`, `p_perm = 0.7445`, `n = 29` | `functional_prediction/evidence/phase2/permutation_summary.json`, `phase2_summary.json` |
| bootstrap CIs for `Q²`, skill-MAE, Spearman | `functional_prediction/evidence/phase2/bootstrap_ci.json` |
| `CASE 4` verdict and its four-arm numbers | `tta_collapse/evidence/metrics/KEY_FINDINGS.json` (`verdict`, `deltas_vs_source`) |
| per-subject TTA metrics for all four arms | `tta_collapse/evidence/metrics/*_subject_metrics.csv` |
| the 816 executed units, per unit | `tta_collapse/evidence/units/units/` |
| collapse verdict and thresholds | `tta_collapse/evidence/metrics/collapse_verdict.json` |
| SOURCE closure (local and remote) | `tta_collapse/evidence/metrics/source_closure.json`, `source_closure_remote_seed0.json` |
| checkpoint hash manifest | `shared/ds004902_source_trunk/checkpoints/CHECKPOINT_MANIFEST.csv` |
| trunk provenance and version pins | `shared/ds004902_source_trunk/legacy_apparatus/outputs/source_only_500hz_v1/provenance.json` |
| trunk build verification (68 subjects / 9,390 segments / 68 folds) | `…/source_only_500hz_v1/verification.json` |

**This is the intended use of `evidence/`.** It exists so that a reviewer can check a claim in
minutes without acquiring a dataset.

---

## 5. Level 3 — re-running the experiments

### 5.1 The trunk benchmark

Needs ds004902 and produces the 204 checkpoints. Then compare against the published numbers above.
The formal run used an RTX 4090; a different GPU will change wall time and may change nothing
else, but **do not assume that** — assert the anchor hashes of §3.1 first, then compare balanced
accuracy against `0.5924169784325324`.

### 5.2 TTA Phase 1

Needs the trunk corpus **and** the checkpoint set **and** a GPU host. The container used for the
original run is gone.

**Frozen protocol — do not re-derive it from this document:**

* `tta_collapse/TENT_METHOD_SPEC.md` — the reference audit and every frozen choice with rationale,
  including the canonical TENT reference pin (commit `e9e926a668d85244c66a6d5c006efbd2b82e83e8`,
  core source SHA-256 `d854e1f65f741aa1632dfb55420ca1bcf5405c978bef890e45caad04980514c8`).
* `tta_collapse/COLLAPSE_TAXONOMY.md` — the frozen collapse definition, quartiles and the
  four-arm interpretation matrix.
* `tta_collapse/SERVER_RUNBOOK.md` — the environment, gates and the exact command (host redacted).

**Sanity gate before any comparison:** run SOURCE closure and require 0 label flips and the
historical balanced accuracy reproduced exactly. If closure fails, the comparison is against a
drifted re-implementation and is meaningless.

### 5.3 The Phase 1–2 functional lanes

`functional_prediction/scripts/` is the runnable pipeline (`run_phase1.py`, `run_phase15.py`,
`run_phase175.py`, and `30_phase2_models.py`). These need the ds004902 corpus and the PVT-derived
targets, and each has a matching `*_verify_phase*.py` verifier.

---

## 6. Verification gates — the standing contract

Every phase ends with an independent verifier whose non-zero exit gates completion, and every
**static** check must be proved able to catch a deliberately injected violation. The published
verifiers and their published counts:

| lane | verifier | result |
|---|---|---|
| TTA Phase 1 | `tta_collapse/90_verify_phase1.py` | **105/105** |
| TTA Phase 1 controls | `tta_collapse/tests/test_p1_controls.py` | **75/75 bite** (NC1–NC27) |
| Phase 1 | `functional_prediction/scripts/06_verify_phase1.py` | 26/26 |
| Phase 1.5 | `functional_prediction/scripts/14_verify_phase15.py` | 26/26 |
| Phase 1.75 | `functional_prediction/scripts/23_verify_phase175.py` | 44/44 |
| Phase 2 | `functional_prediction/scripts/31_verify_phase2.py` | 43/43 |
| Phase 3B byte audit | `functional_prediction/audit/phase3b/20_verify_phase3b.py` | 46/48 — 2 **expected** failures |
| Phase 3B spec conformance | `functional_prediction/audit/phase3b/26_verify_spec_conformance.py` | 54/56 — 2 **expected** failures |

⚠️ **The Phase 3B "failures" are the guards working, not a regression.** Both verifiers assert
*exactly four* Tier-1 payloads; a fifth was added later under a brief-authorised preflight
allowance, and both verifiers independently detect it. **Do not loosen them** and do not edit the
frozen hash record to silence them — doing so would destroy the evidence that the guards guard.

⚠️ **Coverage is stated, not implied.** Several verifiers need the raw datasets, so they cannot run
from a clone. Where a verifier's coverage is partial — for example a literal search executed on a
subset of folds because the full search is too slow — that is said in the verifier itself rather
than left for the reader to discover.

---

## 7. Path portability

The published code resolves the trunk, the archive and the data tree by **repository-relative
paths** declared in one place per branch (`tta_collapse/src/p1_common.py`, and the configs under
`shared/ds004902_source_trunk/legacy_apparatus/configs/`). No published executable code requires
an absolute machine path.

Two exceptions, both deliberate and both documented:

1. **`archive/legacy/ns_sd_prototype_2026/`** — the superseded prototype still contains the
   original author's hard-coded local paths. It is published verbatim as history and is not
   maintained.
2. **Historical reports and manifests** — some contain the literal absolute paths of the machine
   at execution time. They are **historical records, not live configuration**; nothing reads them
   to locate data. Machine-specific and personal path strings were substituted when this public
   snapshot was produced; see `docs/project-history.md` §"Path portability" for the exact
   substitution classes.

---

## 8. Reporting standard

If you reproduce, extend or contradict anything here, follow the project's own standard:

* lead with the outcome, then the evidence, then the caveats;
* every number traceable to an artifact path, a command, or a fresh recomputation;
* distinguish clearly what was **verified**, what was **inferred**, and what is **unknown**;
* when correcting a previously reported conclusion, say plainly that it is a correction and why;
* report contradictions rather than smoothing them.
