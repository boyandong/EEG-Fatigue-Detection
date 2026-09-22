# GITHUB_REFRESH_INVENTORY.md

Audit produced **before** any modification or push, during the 2026-09-22 public-repository
refresh of `github.com/boyandong/EEG-Fatigue-Detection`.

**Refresh branch:** `repo-refresh-20260922` · **Remote `main` preserved untouched.**

---

## 0. Environment and starting state

| item | finding |
|---|---|
| working directory | `C:\Users\董伯言\Desktop\srtp` |
| is the working directory a git repository? | **No.** `git rev-parse` reports *not a git repository*. |
| `origin` configured? | **No** — there was no repository, so no remote. |
| untracked / modified files | **Not applicable** — no repository existed at the workspace root. |
| nested git repository found | **Yes, one:** `data/ds004902/metadata_behavior/.git`, a **git-annex clone of `OpenNeuroDatasets/ds004902`**. It is a **source dataset checkout, not project code.** It must not be confused with, or committed into, the project repository. |
| git available | `git 2.51.1.windows.1` |
| GitHub authentication | `gh` CLI **logged in as `boyandong`** (token scopes `gist`, `read:org`, `repo`, `workflow`) |
| provenance note | The local scientific project explicitly records that it is **not** a git repository and that provenance rests on **file-content SHA-256** (`AGENTS.md` §3.9). This refresh therefore had to decide *what to publish*, not *what to push* — there was no local history to preserve or rewrite. |

### The remote repository at audit time

| item | finding |
|---|---|
| branch | `main` |
| commits | **1** — `625dc3b901bb710cd5ab377dbbb85a81517c85b1` "Initial commit: EEG fatigue classification (NS vs SD)" |
| tracked files | **36** |
| `README.md` | Chinese; defines the project as *"EEG 疲劳识别（正常睡眠 vs 睡眠剥夺）"* — an NS vs SD classifier |
| directories | `baseline/`, `feature_extracting/`, `model/`, `.vscode/` |
| `.gitignore` | excludes `__pycache__`, checkpoints (`*.pth`), `EEG数据/`, `feature_data/*.npy` |
| `requirements.txt` | present (unpinned: numpy, pandas, scipy, scikit-learn, tqdm, torch, mne, braindecode, matplotlib) |
| gated binary committed | `feature_extracting/feature_data/lstm_fatigue_best.pt` (1.2 MB) |

**Assessment:** the remote describes **Phase 0 only**. It does not mention the ds004902 source
trunk, the PVT negative result, the BCIT behavioural endpoint, the Phase 4A/4A2/4A3 history, the
branch separation, or the entire TTA branch. `main` is nonetheless **preserved as-is**: this
refresh adds a branch, it does not rewrite history.

---

## 1. Local state — authoritative structure

`C:\Users\董伯言\Desktop\srtp\project\srtp` is the scientific source of truth (11,762 files,
**29.46 GB** total).

| top-level | files | size | role |
|---|---:|---:|---|
| `shared/` | 2,567 | 9,074 MB | frozen ds004902 source trunk — single source of truth |
| `functional_prediction/` | 2,279 | 8,667 MB | **Branch A** — EEG → objective functional performance |
| `tta_collapse/` | 1,078 | 134 MB | **Branch B** — test-time adaptation stability |
| `archive/` | 4,242 | 6,686 MB | forensic history, NOT canonical (hosts the one canonical checkpoint set) |
| `data/` | 1,569 | 5,601 MB | immutable raw datasets |
| `_refactor/` | 23 | 1 MB | the 2026-09-20 branch-decoupling record |
| root docs | 4 | 0.08 MB | `README.md`, `AGENTS.md`, `SESSION_HANDOVER.md`, `MIGRATION_MAP.md` |

---

## 2. Classification

### PUBLIC_KEEP — already public, still valid, republished in place

| path | why it stays |
|---|---|
| `baseline/`, `feature_extracting/`, `model/` (from remote) | superseded but historically useful; **migrated** to `archive/legacy/ns_sd_prototype_2026/` |
| `feature_extracting/feature_data/lstm_fatigue_best.pt` | 1.2 MB legacy checkpoint; kept for completeness |
| `requirements.txt` (remote) | audited, **not** carried forward; preserved as `archive/legacy/.../requirements-legacy.txt` |

> **No remote file was deleted.** Everything the remote had still exists, either in place or
> migrated under `archive/legacy/`.

### PUBLIC_UPDATE — kept but substantially rewritten

| path | change |
|---|---|
| `README.md` | **complete rewrite.** Retitled *Reliable EEG Modeling for Vigilance and Functional Performance*; the NS/SD definition no longer defines the project; documents the shared trunk and both branches with honest status |
| `requirements.txt` | regenerated from actual imports + the recorded provenance of the formal run; legacy list moved aside |
| `.gitignore` | rewritten: narrow, name-based rules; explicit exceptions for published evidence and the one permitted checkpoint |

### PUBLIC_NEW — newly published

| path | content |
|---|---|
| `docs/` | `PROJECT_HISTORY.md`, `REPRODUCIBILITY.md`, `verify_public_numbers.py`, `check_links.py` |
| `ENVIRONMENT_AUDIT.md` | dependency derivation + what is not reconstructible |
| `shared/ds004902_source_trunk/` | `README.md`, `legacy_apparatus/` (code + specs + configs), `outputs/source_only_500hz_v1/` (manifests, splits, channels, verification, provenance), `third_party/` (pins only), `checkpoints/` (manifest + guide) |
| `functional_prediction/` | `README.md`, `research_tree.md`, specs, 6 phase reports, `src/`, `scripts/`, `config/`, `tests/`, `evidence/` |
| `tta_collapse/` | `README.md`, `research_tree.md`, method/taxonomy/provenance docs, `src/`, `tests/`, runners, `evidence/` (metrics + 816 units + plots) |
| `archive/legacy/ns_sd_prototype_2026/` | the migrated Phase-0 prototype, verbatim, plus its original Chinese READMEs |

### LOCAL_ONLY — never published

| path | reason |
|---|---|
| `AGENTS.md` | operational rules for the agent workspace; exposes internal process |
| `SESSION_HANDOVER.md` | internal session-handover state |
| `MIGRATION_MAP.md` | internal refactor bookkeeping |
| `_refactor/` (23 files) | execution debris of the decoupling (inventory, plan, executor) |
| `functional_prediction/audit/phase3*/phase4a*/` scripts | ~40 near-duplicate phase scripts; selected reports/specs published instead |
| `functional_prediction/pvt_audit_v1/` | superseded by the published `evidence/pvt/` |
| `functional_prediction/outputs/` (most) | superseded intermediates; selected artifacts republished as `evidence/` |
| `tta_collapse/*.sh` (~30 one-off scripts) | per-server debug/launch debris (`diag_*.sh`, `install_env[2-7].sh`, `*.sh.norm`) |
| `tta_collapse/remote_outputs/` | exact duplicate of `outputs/` |
| `tta_collapse/outputs/remote_state.json` | **credential-bearing runtime state** — withheld (see §3) |
| `tta_collapse/SESSION_HANDOVER_EEGTTA_PHASE1.md` | internal handover; published branch README supersedes it |

### LARGE_BINARY — excluded by policy

| class | files | size | decision |
|---|---:|---:|---|
| BCIT Tier-1 raw payloads (`phase3b/raw`) | 37 | **8,392 MB** | not redistributable; dataset access required |
| ds004902 waveform caches (`*.npy`) | 302 | **9,037 MB** | regenerable via `prepare_data.py` |
| raw ds004902 EEG (`data/ds004902`) | 1,567 | **5,509 MB** | source dataset, not redistributed |
| legacy full-run tarball (`dist/*.tar`) | 2 | **4,381 MB** | superseded archive |
| EEGNet + DeepConvNet checkpoints (`*.pt`) | 4,107 | **1,233 MB** | manifest + hashes published instead |
| legacy BCIT `.cnt` (`data/legacy_cnt`) | 2 | 92 MB | raw data |
| Phase-3C vehicle cache (`*.npz`) | 4 | 229 MB | generated cache |
| `third_party/` vendored source | 2,175 | 34 MB | referenced by pin, not vendored |

### SENSITIVE_OR_RUNTIME — withheld or sanitized

| item | action |
|---|---|
| `tta_collapse/outputs/remote_state.json` | **WITHHELD ENTIRELY** — embedded the SSH **key path**, server host/port/user. Runtime state, not provenance. |
| server host, port, SSH key path | **REDACTED** in `SERVER_RUNBOOK.md`, `05_remote.py`, `KEY_FINDINGS.json` |
| local Windows username (34 occurrences / 28 files) | **REPLACED** with `<HOME>` |
| local Anaconda environment path (61 occurrences / 42 files) | **REPLACED** with `<ENV_ROOT>` or a generic `python` |
| `E:/srtp_phase4a*` external cache paths | **KEPT AS PROSE** — evidence locations, not credentials; no such volume is reachable from this repo |
| SSH password | **Never present.** Read from `EEGTTA_SSH_PASSWORD` at run time; confirmed absent from the repository. |
| private SSH keys / API keys / tokens | **None found** (see `GITHUB_REFRESH_DIFF_REPORT.md` §Secrets) |

### HISTORICAL — preserved as history, explicitly marked

* `archive/legacy/ns_sd_prototype_2026/` — the Phase-0 prototype, verbatim.
* Phase 4A / 4A2 numbers — published **with** the Phase 4A3 resolution attached; see
  `GITHUB_REFRESH_DIFF_REPORT.md` §Scientific-content changes.
* Frozen reports still cite pre-refactor paths — deliberately not rewritten (provenance).

### UNKNOWN — items examined and resolved

| item | resolution |
|---|---|
| `data/ds004902/metadata_behavior/.git` | a **git-annex OpenNeuro checkout**, not project code → excluded |
| `ttaudit/`, `pvt_audit_v1/` exploratory outputs | **not** published; superseded by `evidence/pvt/` |
| “CASE 4” meaning | **NOT guessed.** Read from `tta_collapse/README.md`, `research_tree.md`, `COLLAPSE_TAXONOMY.md` and `evidence/metrics/KEY_FINDINGS.json`. It is the **verdict of an executed and verified formal experiment** (`816/816` units), not a taxonomy label or a plan. |
| Phase 4A/4A2 validation status | **Resolved against local authority.** The refresh brief described them as INVALIDATED; `AGENTS.md` §2, `functional_prediction/README.md`, `SESSION_HANDOVER.md` and Phase 4A3's artifacts all record that the invalidation was **withdrawn** after Phase 4A3 measured the defect to be **inert** (0 of 82,550 rows in any mask; Phase 4A reproduced to ~1e-14). The **local authoritative state was followed**, and the divergence from the brief is reported. |

---

## 3. Secrets / privacy scan — pre-commit gate

| scan | scope | result |
|---|---|---|
| API keys, access tokens, OAuth tokens, cloud keys | all published text | **0 genuine hits** (1 regex false positive on the filename `task-Drive_events.json`) |
| passwords / secrets / tokens in assignment form | all published text | **0** |
| PEM private keys, `ssh-rsa`/`ssh-ed25519` authorized-key lines | all published text | **0** |
| local username, local machine paths, server host, key name | all published text | **0 after sanitization** |
| `.env`, credentials files, `known_hosts` | repository | **0** |

**No hard stop was triggered.** One credential-bearing runtime file was withheld, and four classes
of personal/machine identifier were redacted. Details and the full substitution set:
`GITHUB_REFRESH_DIFF_REPORT.md`.

---

## 4. Publication decision summary

| metric | local tree | published |
|---|---:|---:|
| files | 11,762 | **1,207** |
| size | 29.46 GB | **~87 MB** |
| raw data | 5.6 GB | **0 bytes** |
| waveform caches | 9.0 GB | **0 bytes** |
| checkpoints | 1,233 MB (4,107 files) | **1.2 MB** (1 legacy prototype file) + a 204-row hash manifest |
| BCIT payloads | 8.4 GB | **0 bytes** |

Raw data is not merely excluded — it is **not represented anywhere in the published tree**, and
`docs/REPRODUCIBILITY.md` gives the dataset identifiers, expected local layout and regeneration
entry points instead.
