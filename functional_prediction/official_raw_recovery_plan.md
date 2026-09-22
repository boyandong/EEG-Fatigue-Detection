# Official raw data recovery plan

Feasibility audit only. **Nothing was downloaded.** This document records whether the original
ds004902 EEG can still be obtained as real file content, which version, whether eyes-open
recordings are reachable, the expected size, and what a canonical preprocessing branch would
cost.

Machine evidence: `outputs/stability_v1/raw_recovery_probe.json` (produced by
`src/probe_raw_recovery.py`, read-only HTTP HEAD/GET).

---

## 1. The problem this addresses

The largest provenance limitation in this branch is inherited, not created here:

| limitation | consequence |
|---|---|
| `data/ds004902/metadata_behavior/` contains only **broken git-annex symlinks** (218 `.set` + 218 `.fdt`, `WinError 1920`, `.git/annex/objects` absent) | the official raw EEG is **not** locally readable |
| the only readable EEG is `data/ds004902/preprocessed/` (142 pairs) | produced by a **third party**, MATLAB/EEGLAB, unknown ICA settings, repo-external path |
| that preprocessing ran on **v1.0.5** while the local BIDS declares **v1.0.8** | version mismatch we cannot correct locally |
| `pop_resample(EEG, 500)` on 5 recordings with **unrecorded anti-alias settings** | 5 sessions have unknown spectral history |
| two operator trees mixed in one folder | heterogeneity in artefact handling |

A canonical branch `official raw → reproducible preprocessing → mechanism_v1` would remove all
of these at once, and would also let us re-derive eyes-open provenance from event/task markers
instead of filename families.

---

## 2. Verdict: **RECOVERABLE**

### 2.1 The files are real, not pointers

| probe | result |
|---|---|
| `HEAD https://data.nemar.org/on004902/v1.0.0/participants.tsv` | **200**, `Content-Length: 12014` |
| `HEAD .../dataset_description.json` | **200**, 642 bytes |
| `GET .../manifest.json` | **200**, **1233 entries**, full file index with `size` and `bytes_url` |
| `HEAD .../sub-01/ses-1/eeg/sub-01_ses-1_task-eyesopen_eeg.set` | **200**, **198 722 bytes** (194.1 KB) |
| `HEAD .../sub-01/ses-1/eeg/sub-01_ses-1_task-eyesopen_eeg.fdt` | **200**, **36 600 000 bytes** (34.9 MB) |
| `HEAD .../sub-39/ses-2/eeg/sub-39_ses-2_task-eyesopen_eeg.fdt` | **200**, **366 000 000 bytes** (349.0 MB) |

`Content-Length` matching the manifest size means these are **substantive objects served over
plain HTTPS**, not annex pointers. This is the decisive difference from the local tree.

### 2.2 Version available

* OpenNeuro DOI referenced by the dataset record on disk: **v1.0.8**
  (`dataset_description.json`, `DatasetDOI: doi:10.18112/openneuro.ds004902.v1.0.8`).
* The **paper describes v1.0.4** (`10.18112/openneuro.ds004902.v1.0.4`).
* The NEMAR mirror `on004902` is at **v1.0.0** and is derived from OpenNeuro **v1.0.8**;
  its interface notes that NEMAR reads OpenNeuro pulls as major bumps and that intermediate
  versions are NEMAR-side fixes.
* `原始数据集.txt` records that our inherited preprocessing was done on **v1.0.5**.

So neither our files nor the mirror correspond to the paper's v1.0.4. **A canonical branch
should pin an explicit version and record which one**, and the honest choice for
paper-comparability is to fetch **v1.0.4** if OpenNeuro still serves it — that needs an
explicit version query at download time, which the OpenNeuro GraphQL endpoint refused from this
environment (HTTP 400 on the ad-hoc query). The NEMAR v1.0.0 mirror is the fallback.

### 2.3 Eyes-open is reachable and separable

From the manifest:

| subset | files | size |
|---|---|---|
| total dataset | 1233 entries | **8.90 GB** |
| `*_task-eyesopen_eeg.{set,fdt}` | **284** (142 `.set` + 142 `.fdt`) | **6.11 GB** |
| `*_task-eyesclosed_eeg.{set,fdt}` | 152 (76 `.set` + 76 `.fdt`) | 2.79 GB |
| behavioural (`/beh/`) | 67 | 0.03 MB |

**eyes-open is a separate `task-` entity in the filename**, so a targeted download of the
eyes-open subset is straightforward and needs **6.11 GB instead of 8.90 GB**.

The 284 eyes-open files correspond exactly to 142 recordings = 71 subjects × 2 sessions. This
matches our readable set one-for-one, which is a useful cross-check: our third-party
preprocessing did select exactly one eyes-open recording per subject-session, with no extras.

### 2.4 Download routes

| route | command | notes |
|---|---|---|
| NEMAR CLI (recommended) | `nemar dataset download on004902` | pinned version, resumable; `--subjects`/`--sessions`/`--tasks` filters exist |
| DataLad | `datalad clone https://github.com/nemarDatasets/on004902 && datalad get .` | fetches annex content on demand |
| per-file HTTPS | `https://data.nemar.org/on004902/v1.0.0/<path>` | range-resumable; works with a plain HTTP client, which is what the probe used |
| OpenNeuro | `openneuro.org/datasets/ds004902` → version selector | needs an explicit version pin; not verifiable from this environment |

A task-filtered, per-file HTTPS pull driven by the manifest is the lowest-dependency option and
is what I would use: it needs no `npm`, no DataLad, and no git-annex.

---

## 3. What a canonical branch would cost

| item | estimate |
|---|---|
| download (eyes-open only + behaviour) | **6.11 GB** |
| disk for raw + derived | ≥ 15 GB comfortable |
| wall time | hours, mostly download; not a compute problem |
| implementation | a new adapter behind the existing loader interface; `mechanism_features.py` is already dataset-agnostic and would not change |
| main risk | reproducing the paper's own QC (visual inspection, manual bad-channel choice, ICLabel or manual ICA component selection) is **not** fully automatable, so a canonical branch would still differ from the paper in the artefact step |

Important scoping note: a canonical branch does **not** by itself make the paper-reference
reproduction match. The paper's pipeline includes a **visual examination** step and
unspecified ICA component choices; a reproducible reimplementation will be *documented and
deterministic*, not *identical*. Its value is provenance and eyes-open certainty, not ρ.

---

## 4. Recommendation

**Worth doing before the final paper-level experiments, not before Phase 2 modelling.**

Reasoning:

* Phase 1.5 and the Phase 2 nested-LOSO protocol test *our* representation's stability and
  predictive value. Neither depends on the raw lineage; both can run on the current 68-subject
  corpus. Blocking them on a 6 GB download would delay the scientific question for a
  provenance improvement.
* But the final claim — "this representation is portable and computable by the same definition
  elsewhere" — is much stronger with a branch whose preprocessing is **ours and reproducible**,
  and whose eyes-open status comes from a `task-eyesopen` entity rather than a filename family.
* The eyes-open/family-level uncertainty (F2 in `PHASE1_REPORT.md`) is the single remaining
  provenance item that a download would fully close.

Proposed sequencing when authorised:

1. Pin the version (prefer **v1.0.4** for paper comparability; fall back to NEMAR v1.0.0).
2. Pull the 284 eyes-open files + 67 `beh` files by manifest-driven HTTPS.
3. Verify SHA-256 against the manifest for every file.
4. Write `src/data_ds004902_raw.py` adapter emitting the **same common representation**
   (`epochs`, `channel_names`, `sfreq`) — the mechanism extractor stays untouched.
5. Re-run `scripts/10..12` and compare the six coordinates and the stability metrics against
   the current corpus. **Disagreement is informative, not a failure**: it measures how much of
   our signal is inherited-preprocessing-specific.
6. Only then re-run the paper-reference check, and report the comparison as a provenance
   study rather than a reproduction attempt.

**This is a proposal. Nothing has been downloaded, and I will not start it without instruction.**
