# ENVIRONMENT_AUDIT.md

What the current code actually needs, what the published numbers were actually produced with, and
what is **not** reconstructible. Produced during the 2026-09-22 public-repository refresh by
reading the source trees and the frozen provenance records — not from memory, and not by
inheriting the legacy prototype's dependency list.

---

## 1. What was audited

| source | what it establishes |
|---|---|
| import statements across `shared/`, `functional_prediction/`, `tta_collapse/` (58 Python files) | the actual dependency surface |
| `shared/ds004902_source_trunk/legacy_apparatus/outputs/source_only_500hz_v1/provenance.json` | the exact versions of the **formal ds004902 run** |
| `archive/legacy_or_superseded/…/formal_autodl_v1/provenance.json` (record reproduced in §3) | the EEGNet training run |
| `tta_collapse/SERVER_RUNBOOK.md` | the TTA Phase 1 execution environment |
| the live interpreter | version confirmation of every pin in `requirements.txt` |
| `archive/legacy/ns_sd_prototype_2026/requirements-legacy.txt` | what the **superseded prototype** used — deliberately *not* carried forward |

---

## 2. Dependency surface, derived from imports

Third-party imports actually used by the current project, with the number of files importing each:

| package | files | why it is needed |
|---|---:|---|
| `numpy` | 50 | everything |
| `scipy` | 11 | Welch PSD, signal processing, statistics |
| `torch` | 12 | EEGNet training and the TTA arms |
| `braindecode` | 6 | supplies `EEGNet`; the frozen architecture |
| `scikit-learn` | 6 | ridge/SVM baselines, metrics, CV utilities |
| `matplotlib` | 4 | phase plots |
| `mne` | 1 | reads the ds004902 `.set` payloads |
| `pymatreader` | 4 | parses legacy BCIT/EEGLAB headers |
| `joblib` | 1 | parallel phase pipelines |
| `paramiko` | 1 | **optional** — only `tta_collapse/05_remote.py`; not needed for any local verification |

Standard-library-only modules (the large majority of files) need no pin.

**One packaging note:** `scikit-learn` is imported as `sklearn`, and the frozen trunk records
`scikit-learn 1.7.2`. The distribution name is used in `requirements.txt`.

---

## 3. The environments the published numbers came from

### 3.1 Formal ds004902 source run (the 204 EEGNet checkpoints, and the historical headline)

From the run's own provenance record:

| component | version |
|---|---|
| Python | 3.11.16 |
| OS | `Linux-5.15.0-94-generic-x86_64-with-glibc2.31` |
| GPU | NVIDIA GeForce RTX 4090 |
| torch | 2.10.0+cu126 |
| braindecode | 1.3.2 |
| scikit-learn | 1.7.2 |
| numpy | 2.3.2 |
| scipy | 1.16.1 |
| matplotlib | 3.10.5 |

### 3.2 TTA Phase 1 (the `CASE 4` result)

Executed in the **owner-approved server container**, which provided a *different* stack:

| component | formal run | TTA Phase 1 | disposition |
|---|---|---|---|
| Python | 3.11.16 | **3.12.3** | keep — documented difference |
| torch | 2.10.0+cu126 | **2.8.0+cu128** | keep — but the consequence was **checked, not assumed** |
| host driver | — | advertises CUDA 13.0 | irrelevant to the recorded runtime |

**Why the torch difference is not a problem, stated as evidence rather than assurance:** the TTA
lane proved **SOURCE closure** before comparing any arm — locally and on the remote GPU — with
max absolute Δp **9.537e-07**, **0 label flips**, and the historical headline
`BAcc = 0.5924169784325324` reproduced to **16 digits**. If the runtime difference had changed the
forward pass materially, that closure would have reported it. **The two torch builds must not be
treated as interchangeable without that check.**

### 3.3 Where the two environments are recorded in this repository

* formal run: `shared/ds004902_source_trunk/legacy_apparatus/outputs/source_only_500hz_v1/provenance.json`
* TTA Phase 1: `tta_collapse/evidence/metrics/KEY_FINDINGS.json` (`execution` block) and
  `tta_collapse/SERVER_RUNBOOK.md`
* TTA remote environment probe: `tta_collapse/evidence/metrics/remote_env.json`,
  `remote_provenance.json`

---

## 4. The pin set published in `requirements.txt`

Confirmed present, at these exact versions, in the interpreter used for this audit:

| package | pin | status |
|---|---|---|
| numpy | 2.3.2 | confirmed |
| scipy | 1.16.1 | confirmed |
| scikit-learn | 1.7.2 | confirmed |
| torch | 2.10.0 (`+cu126` locally) | confirmed |
| braindecode | 1.3.2 | confirmed |
| mne | 1.11.0 | confirmed |
| pymatreader | 1.1.0 | confirmed |
| matplotlib | 3.10.5 | confirmed |
| joblib | 1.5.2 | confirmed |
| paramiko | not pinned | optional; used only by the remote helper |

Every pin in `requirements.txt` is therefore **evidence-backed**: it is the version that produced
a published number, or the version the source imports and the environment supplies.

---

## 5. What is NOT reconstructible — read this before promising a rebuild

1. **A single unified environment does not exist.** The two branches' published numbers came from
   *different* Python and torch versions. There is no one environment file that reproduces both.
   `requirements.txt` targets the code's needs and the local/formal-run stack; §3 states the TTA
   exception explicitly.
2. **The exact remote container image is not archived.** The TTA server was an
   owner-approved, rented container whose provisioning is recorded in
   `tta_collapse/SERVER_RUNBOOK.md` but whose image is not under this project's control. It is
   gone. Re-executing TTA Phase 1 exactly requires re-establishing an equivalent GPU host.
3. **`pytest` is not installed in the project interpreter, and the test suites are not pytest
   suites.** Every test is a plain script with a non-zero exit on failure; run them directly, as
   `docs/REPRODUCIBILITY.md` shows.
4. **Two datasets are not redistributed** (ds004902 and BCIT). Corpus-dependent verification
   cannot run from a clone alone; see `docs/REPRODUCIBILITY.md`.
5. **The legacy prototype's environment is a separate, older world.** Its
   `requirements-legacy.txt` lists unpinned packages and is **not** a subset of the current pins.
   Do not merge the two lists. It is preserved only as history.
6. **Bulk runtime caches lived outside the repository.** Several Phase-4A-family scripts read
   multi-gigabyte caches from a separate volume (`E:/srtp_phase4a*` in the owner's local layout).
   Those were never part of the repository's provenance and are **not** republished. A
   different machine must regenerate them; the phase scripts document how.

---

## 6. Practical guidance

* **To run the data-free verification** (recommended first step, needs no dataset and no GPU):
  install `requirements.txt` and run the three suites in `docs/REPRODUCIBILITY.md` §2. On the
  audit machine these produced **16/16**, **22/22** and **SMOKE: PASS**.
* **To reproduce the trunk's headline benchmark**, you must re-acquire ds004902 and re-run
  `legacy_apparatus/prepare_data.py` then `run_baselines.py` — the checkpoint weights are not
  redistributed (see `shared/ds004902_source_trunk/checkpoints/README.md`).
* **To re-run TTA Phase 1**, you additionally need a GPU host and the checkpoint set. The
  canonical protocol is frozen in `tta_collapse/TENT_METHOD_SPEC.md` and
  `tta_collapse/COLLAPSE_TAXONOMY.md`; do not re-derive it from this document.
* **A note on this machine:** the local interpreter used for the audit is an Anaconda environment
  kept outside this repository. Its path is machine-specific and is deliberately not published in
  this snapshot.
