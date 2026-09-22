# PUBLICATION_SCOPE.md

What this public repository publishes, what it deliberately does not, and the rule behind each
decision. Produced during the 2026-09-22 refresh.

**Principle.** The local scientific tree is the **source of truth**. The public repository is a
**research and portfolio interface** to it. The two are not meant to be identical, and this
document states the difference explicitly rather than leaving it implicit.

The scope was decided from three inputs only — the project's own `.gitignore` intent, **measured
file sizes**, and the **artefact's role in reproduction** — not from a general sense of what looks
heavy.

---

## 1. Publication targets

| target | status |
|---|---|
| current scientific structure | **published** — `shared/`, `functional_prediction/`, `tta_collapse/`, `archive/legacy/`, `docs/` |
| representative runnable code | **published** — loaders, model config, trainer, evaluators, TTA runner, collapse metrics, verifiers, tests, configs |
| clear provenance | **published** — manifests, splits, anchor SHA-256 values, version pins, third-party commit pins |
| honest status | **published** — negative results, the withdrawn invalidation, parked work, and what is *not* claimed |
| safe lightweight artefacts | **published** — selected `evidence/`, the checkpoint hash manifest, the plot set |

---

## 2. PUBLISHED — and the rule

### 2.1 Code with long-term value

| what | where | rule |
|---|---|---|
| data preparation + manifest builder | `shared/.../legacy_apparatus/prepare_data.py` | it *is* the corpus definition |
| LOSO runner that trained the trunk | `shared/.../legacy_apparatus/run_baselines.py` | without it the benchmark is not reproducible |
| trunk verifiers | `verify_data.py`, `verify_baselines.py`, `verify_portable_bundle.py` | the verification discipline is a deliverable |
| frozen architecture + hyper-parameters | `shared/.../configs/baselines.json` | hash-pinned; defines EEGNet for both branches |
| Phase 1–2 pipeline | `functional_prediction/src/`, `scripts/` | the NEGATIVE branch's actual apparatus |
| phase verifiers + unit tests | `functional_prediction/scripts/*_verify_*.py`, `tests/` | contract: every phase ends with an independent verifier |
| TTA apparatus | `tta_collapse/src/`, `10_run_phase1.py`, `30_analyze_collapse.py`, `90_verify_phase1.py` | the `CASE 4` result's actual apparatus |
| negative controls + smoke test | `tta_collapse/tests/` | a check that cannot fail is not a check |
| configs | `functional_prediction/config/` | required to run anything |
| public verifiers | `docs/verify_public_numbers.py`, `docs/check_links.py` | new; let a reviewer check the READMEs without a dataset |

### 2.2 Lightweight evidence

| what | size | why it is worth the bytes |
|---|---:|---|
| TTA per-window predictions (4 arms) | ~11.7 MB | lets a reviewer recompute every arm statistic independently |
| TTA per-subject metrics + batch trajectory + parameter drift | ~5 MB | the subject is the statistical unit; these are the units |
| 816 per-unit records of the executed run | 43.9 MB | the raw evidence that the run happened and what each unit produced |
| TTA plots (73 PNG) | 17.3 MB | the visual record of the trajectories behind the verdict |
| Phase 2 permutation/bootstrap/alpha summaries | <1 MB | the negative result is only trustworthy if its inference is inspectable |
| PVT target audit + manifests | <1 MB | the target's provenance |
| dynamic-audit statistics | 3.9 MB | Phase 1.75's measurements |
| trunk manifests, splits, channels, verification, provenance | 3.6 MB | **required** to interpret anything downstream |
| checkpoint hash manifest | 128 KB | replaces 6.55 MB of weights with something checkable |

### 2.3 History

| what | rule |
|---|---|
| `archive/legacy/ns_sd_prototype_2026/` | the superseded prototype is **preserved, not deleted**, so the project's evolution is auditable. It carries a README stating plainly that it is historical, superseded and unmaintained. |

**Guiding rule for code:** prefer the artefact that a future reader needs to understand or
re-run a *result*. Publish one implementation, not the dozens of near-duplicate phase scripts.

---

## 3. NOT PUBLISHED — and the rule

### 3.1 Raw data (0 bytes published)

| class | measured | rule |
|---|---:|---|
| ds004902 EEG (`.set`/`.fdt`) | 5,509 MB | never redistribute a public dataset's copy |
| BCIT Tier-1 payloads (`.set`) | 8,392 MB | access-controlled; the owner must supply the location |
| legacy BCIT `.cnt` | 92 MB | raw data |

**Replaced by:** dataset identifiers, expected local layout, preprocessing entry points, manifest
generation instructions and anchor hashes — `docs/REPRODUCIBILITY.md` §3.

### 3.2 Large arrays and caches

| class | measured | rule |
|---|---:|---|
| ds004902 waveform caches (`.npy`) | 9,037 MB | regenerable bit-deterministically from `prepare_data.py`; 136 files |
| Phase-3C vehicle cache (`.npz`) | 229 MB | generated; rebuild with `02_extract_vehicle.py` |
| fold Gram caches (`E:/srtp_phase4a*`) | tens of GB | outside the repository by design; machine-specific |

### 3.3 Checkpoints

**4,107 checkpoint files, 1,233 MB — none published.**

Of those, **204 are the canonical EEGNet LOSO checkpoints (6.55 MB total)** that both branches
depend on. They are small. They are nevertheless **not published**, for a reason that is about
licensing and sufficiency rather than size:

* they are **derived** weights trained on a public dataset whose redistribution terms are not this
  repository's to extend;
* they are **not self-sufficient** — reproducing any published number also needs the 9,390-window
  corpus, which is not redistributable here. Shipping weights that cannot be used without an
  absent corpus adds binary payload without adding reproducibility.

**Replaced by:** a 204-row manifest carrying each checkpoint's **SHA-256**, the naming convention,
legacy training metadata, sibling-artefact hashes, and regeneration instructions —
`shared/ds004902_source_trunk/checkpoints/`.

**Git LFS was not used**, and no LFS pointer is committed. Per the refresh constraints, LFS
requires explicit owner consent.

**The one published binary exception:** `archive/legacy/ns_sd_prototype_2026/feature_extracting/
feature_data/lstm_fatigue_best.pt` (1.2 MB). It was **already public** in the remote's initial
commit; removing it would have deleted public content without cause. It is `.gitignore`-whitelisted
explicitly.

### 3.4 Third-party code

**2,175 files, 34 MB of vendored third-party source — not published.** It is installable from its
own upstream, so vendoring it would duplicate someone else's repository without benefit.

**Replaced by:** `shared/ds004902_source_trunk/third_party/sources.json` — name, version,
repository URL, commit SHA, archive SHA-256, and (for TENT) the pinned **core source** SHA-256.
The READMEs cite the reference by **commit SHA**, not by copy.

### 3.5 Internal process and runtime debris

| class | rule |
|---|---|
| `AGENTS.md`, `SESSION_HANDOVER.md`, `MIGRATION_MAP.md` | internal operating documents; they address a successor *agent session*, not a reader |
| `_refactor/` (23 files) | the decoupling's execution machinery; its *conclusions* are published, its debris is not |
| ~30 one-off `.sh` scripts in `tta_collapse/` | per-server debug/launch scratch, including `install_env[2-7].sh` and `*.sh.norm` normalisation copies |
| `tta_collapse/remote_outputs/` | an exact duplicate of `outputs/` |
| `functional_prediction/audit/phase*/` scripts | ~40 near-duplicate phase scripts; their **reports and specs** are published instead |
| `__pycache__` | build output |
| `outputs/qc/run_manifest*.json` | embedded absolute execution-machine paths; historical records nothing reads |

### 3.6 Sensitive and credential-bearing

| class | action | rule |
|---|---|---|
| `tta_collapse/outputs/remote_state.json` | **withheld entirely** | it embedded the SSH key path plus host/port/user. Runtime state, not provenance. |
| server host, port, SSH key path | redacted in 3 files | a live-ish execution endpoint is not publication material |
| local Windows username; local environment root | substituted in 15 files | a personal identifier is not a scientific artifact |

Full substitution set: `GITHUB_REFRESH_DIFF_REPORT.md` §“Privacy and path substitutions”.

---

## 4. Size ledger

| | files | size |
|---|---:|---:|
| local scientific tree | 11,762 | **29.46 GB** |
| excluded: raw data | 1,606 | 13.99 GB |
| excluded: caches | 306 | 9.27 GB |
| excluded: checkpoints + archives | 4,109 | 5.61 GB |
| excluded: third-party vendor | 2,175 | 0.03 GB |
| excluded: internal process/debris | ~300 | 0.01 GB |
| **published** | **~1,100** | **~87 MB** |

**Ratio: 0.30 % of the local tree by size.** Every published byte is either code, a text artifact
under 3.1 MB, or a plot.

---

## 5. What the public repository can and cannot do

| can, from a clone | cannot, from a clone |
|---|---|
| run 60/60 documented-number checks and 21/21 link checks | train or evaluate any model |
| run 16/16 mechanism unit tests | reproduce the EEGNet benchmark |
| run 22/22 nested-CV and inference tests | re-execute the TTA experiment |
| run the TTA synthetic smoke test | load a single checkpoint |
| read the frozen specs, manifests and splits | access any raw EEG |
| inspect every aggregate statistic behind every claim | — |

This asymmetry is stated in the root `README.md` §5–§6 and in `docs/REPRODUCIBILITY.md`, which
grades the repository as **re-checkable everywhere, re-runnable for the trunk and Phase 1–2, and
only partially re-executable** — rather than claiming full reproducibility.
