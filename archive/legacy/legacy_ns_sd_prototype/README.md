# Legacy prototype — NS vs SD EEG classification (superseded)

> **This directory is historical.** It is the *original* state of this repository, preserved so
> that the project's evolution is auditable. It is **not** part of the current scientific
> program, its numbers are **not** results of the current project, and it must not be used as a
> baseline for anything.
>
> `_README_ORIGINAL_ZH.md` is the original Chinese project README, kept verbatim.
> `baseline/README_ORIGINAL_ZH.md` is the original Chinese baseline README, also verbatim.

---

## What this prototype did

A subject-wise binary classifier distinguishing **normal sleep (NS, `ses-1`)** from **sleep
deprivation (SD, `ses-2`)** on the same public dataset. Three model families were prototyped:

| family | entry point | representation |
|---|---|---|
| LSTM | `baseline/train_lstm_fatigue.py` | extracted `[N, 16, 5, 14, 14]` feature grids |
| EEGNet | `baseline/train_eegnet_raw.py` | raw 61-channel EEG, `T = 2000` samples |
| MSCViT + TCN | `model/train.py` | wavelet-convolved ViT blocks + TCN over the feature grids |

with `feature_extracting/extract_features_for_vit.py` producing the feature grids and
`feature_extracting/extract_channel_mapping.py` producing the 14x14 electrode-to-grid mapping.

## What it got right

Three methodological commitments were carried forward into the current project unchanged:

* **subject-wise splitting** — no participant appears in both training and test;
* **train-only normalisation** — downstream standardisation uses training statistics only;
* **no label leakage through preprocessing.**

These were sound from the start and are still the rule.

## Why it was superseded

The NS-vs-SD formulation asks *"which condition is this participant in?"*, not *"what is this
participant's current functional state?"*. Those are different questions, and the first does not
imply the second:

* **`ses-1` / `ses-2` are condition identifiers, not visit-order identifiers.** The dataset
  release counterbalances visit order and records the true order in separate metadata.
* A condition label is a **between-visit** contrast. A model that separates it well has not been
  shown to track **within-visit, time-on-task functional decline**, which is what a
  safety-relevant vigilance application actually needs.
* The prototype had **no objective performance endpoint at all.** "Fatigue" was inferred from the
  experimental condition rather than measured from behaviour.

The project therefore split into two branches that ask sharper questions — see the repository
`README.md` and `docs/PROJECT_HISTORY.md`.

## Status of the code here

* **Not maintained, not tested, and not covered by this repository's verification gates.**
* Paths inside are hard-coded to the original author's local layout — including a Chinese-named
  `EEG数据/` input directory and, in places, an absolute interpreter path. They are left as they
  were, for historical fidelity. This is the one directory in the repository that is *not*
  path-portable, deliberately.
* `feature_extracting/feature_data/lstm_fatigue_best.pt` (1.2 MB) is the single prototype
  checkpoint that was small enough to have been committed to the original repository. It is
  preserved here for completeness only.
* `requirements-legacy.txt` is the prototype's **original** dependency list. It is **not**
  sufficient or correct for the current project — see `ENVIRONMENT_AUDIT.md`.

## Provenance

Migrated from the `main` branch of `github.com/boyandong/EEG-Fatigue-Detection` at commit
`625dc3b` ("Initial commit: EEG fatigue classification (NS vs SD)") during the 2026-09-22
public-repository refresh. File contents are byte-identical to that commit; only the directory
layout was rearranged so that `baseline/` remains a Python package (`__init__.py` retained).
