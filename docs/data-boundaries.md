# Data boundaries

What this repository distributes, what it deliberately does not, and where to get what is missing.
The rule behind every exclusion: **do not redistribute a copy of a dataset that has its own
authoritative source, and do not commit bytes that can be regenerated.**

---

## 1. What is distributed here

| class | what it is |
|---|---|
| code | preprocessing, model definitions, runners, evaluators, verifiers, tests |
| lightweight manifests | the 9,390-window segment manifest, the 68-fold split, channel order |
| protocol definitions | endpoint specs, mask specs, method specs, collapse taxonomy |
| result summaries | per-subject metrics, permutation/bootstrap summaries, verdicts |
| provenance metadata | SHA-256 anchor hashes, third-party commit pins, version records |
| documentation | history, scientific status, reproducibility, validation protocols |
| selected evidence | the executed TTA run's per-unit records and aggregate metrics |

## 2. What is NOT distributed

| class | measured size | why |
|---|---:|---|
| raw ds004902 EEG (`.set` / `.fdt`) | 5,509 MB | the dataset has an authoritative public source; re-download it |
| ds004902 waveform caches (`.npy`) | 9,037 MB | regenerable bit-deterministically by `prepare_data.py` |
| BCIT Tier-1 raw payloads | 8,392 MB | access-controlled; the owner must supply the location |
| legacy BCIT `.cnt` | 92 MB | raw data |
| EEGNet + DeepConvNet checkpoints (4,107 files) | 1,233 MB | represented by a hash manifest; see §4 |
| Phase-3C vehicle cache (`.npz`) | 229 MB | generated cache, rebuildable |
| legacy full-run tarball | 4,381 MB | superseded archive |
| vendored third-party source | 34 MB | referenced by commit pin instead |
| external phase caches (fold Grams) | tens of GB | lived outside the repository on a separate volume |

**These are not excluded by `.gitignore` alone — most were never staged at all.** The public tree is
curated, not filtered.

---

## 3. Dataset sources and expected layout

### 3.1 ds004902 — the shared source trunk

| item | value |
|---|---|
| identifier | **ds004902** (OpenNeuro) |
| content used | 4-second eyes-open tonic EEG, two visits per participant |
| source | <https://openneuro.org/datasets/ds004902> |
| expected local layout | `data/ds004902/preprocessed/` — one `<subject>_ses-<N>.set` (+ `.fdt`) per recording; `data/ds004902/metadata_behavior/` for the release metadata |
| preprocessing entry point | `shared/ds004902_source_trunk/legacy_apparatus/prepare_data.py` |
| config | `shared/ds004902_source_trunk/legacy_apparatus/configs/source_only_data.json` |

**Admission rule, frozen before the data was seen:** only **500 Hz** records are admitted; the
5,000 Hz records are excluded, and the participant who then lacked a usable pair is excluded
**whole** rather than substituted. Result: **68 valid paired subjects of 71**, **9,390 windows**
(class 0: 4,735 / class 1: 4,655).

The raw tree is **read-only**. `prepare_data.py` writes only under `legacy_apparatus/outputs/`.

**Anchor hashes — if your build does not match these, nothing downstream is comparable:**

| artifact | SHA-256 |
|---|---|
| `segments.csv` (9,390-window manifest) | `5eba619fc0dd516f8caf72a86fd36a34ca07c589df9d269b2bcdbd53c1c3a744` |
| `splits.json` (68-fold subject-LOSO, seed 20260908) | `db02bab96f8147bffa4836967a29c0763bc9f8130fa994252ed269649070c184` |

### 3.2 BCIT — Branch A's behavioural endpoint

| item | value |
|---|---|
| content used | real vehicle channels; lane deviation `LN` in metres |
| source | per the dataset's own access terms — **the owner must supply the location** |
| expected local layout | an immutable Tier-1 payload tree plus a metadata tree, referenced by config |
| endpoint spec | [`../functional_prediction/BEHAVIOR_ENDPOINT_SPEC.md`](../functional_prediction/BEHAVIOR_ENDPOINT_SPEC.md) — frozen, not redefinable |
| pairing key | **`legacy_labID`** — never `sub-NN`; a naive `sub-NN` join is **89 % wrong** |

The five audited recordings span three participants and are the behavioural-audit scale. Cohort-scale
acquisition was **not** performed and is a PI acquisition decision.

**Large Phase-4A-family caches lived outside the repository** on a separate volume and are not
republished. A different machine must regenerate them; the phase scripts document how.

---

## 4. Checkpoint policy

The **204 canonical EEGNet LOSO checkpoints** (6.55 MB total) are **not** redistributed.

They are small, so size is not the reason. The reasons are:

1. they are **derived** weights trained on a public dataset whose redistribution terms are not this
   repository's to extend;
2. they are **not self-sufficient** — using them also requires the raw corpus, which is absent here,
   so shipping them would add binary payload without adding reproducibility.

**Instead:** `shared/ds004902_source_trunk/checkpoints/CHECKPOINT_MANIFEST.csv` ships one row per
checkpoint — SHA-256 of `best.pt`, the sibling-artifact hashes, the naming convention
(`eegnet/sub-<NN>/seed_<S>/best.pt`), and legacy training metadata — plus regeneration instructions.

**Git LFS is not used**, and no LFS pointer is committed.

**One binary is published:** `archive/legacy/legacy_ns_sd_prototype/feature_extracting/feature_data/lstm_fatigue_best.pt`
(1.2 MB). It was already public in the repository's original state; removing it would have deleted
public content without cause. It is `.gitignore`-whitelisted explicitly.

---

## 5. Participant identifiers

The published manifests contain only **public-dataset pseudonymous identifiers** (`sub-01` …
`sub-71`, and the BCIT legacy lab IDs), which are the same identifiers the releasing repositories
publish.

This repository contains **no** participant names, contact details, demographics, clinical notes,
or any other re-identifying information — there is nothing to redact because nothing of that kind was
ever in scope.

Subject-level structure *is* published deliberately, because it is the scientific content: which
subject is held out in which fold is exactly what a reviewer needs to check that no cross-subject
leakage occurred.

---

## 6. What was removed from the public tree for privacy or security reasons

Not a data-boundary decision, but recorded here because it is the same class of question. During the
2026-09-22 refresh:

* one **runtime state file** was withheld entirely — it embedded a local SSH key path plus a
  host/port/user, and nothing published needs it;
* a **server host, port and SSH key name** were redacted from three files;
* a **local username and machine paths** were substituted in the reports and configs that carried
  them.

**No credential was ever committed and then withdrawn.** The SSH password was read from an
environment variable at run time and never stored. Full substitution list:
[`refresh/GITHUB_REFRESH_DIFF_REPORT.md`](refresh/GITHUB_REFRESH_DIFF_REPORT.md) §7.

---

## 7. If you need the excluded bytes

| you want | how to get it |
|---|---|
| the raw EEG corpus | re-download ds004902 from OpenNeuro, then run `prepare_data.py`; verify against the anchor hashes in §3.1 |
| the waveform caches | produced by the same run; they are deterministic given the config |
| the checkpoints | retrain with `run_baselines.py` (`stage: formal`, `models: ["eegnet"]`), or ask the owner |
| the BCIT endpoint data | contact the dataset's access authority |
| the Phase-4A fold caches | regenerate locally; see the phase scripts under `functional_prediction/` |

Publishing the checkpoints is a one-line policy change — they are 6.55 MB and already
hash-manifested here. It is a **licensing** decision, not a technical one, and it is not this
repository's call to make by default.
