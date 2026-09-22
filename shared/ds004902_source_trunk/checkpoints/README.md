# EEGNet source checkpoints — manifest only (weights not redistributed)

This directory documents the **204 canonical EEGNet LOSO checkpoints** that both research
branches depend on. **The checkpoint files themselves are not published in this repository.**

---

## Why they are not here

The owner's publication policy for this refresh is that model weights are represented by a
manifest unless they are both small and genuinely required for reproduction. The trunk's
checkpoint set is small in absolute terms, but it is **not self-sufficient**: reproducing any
published number from it also requires the 9,390-window ds004902 corpus, which is not
redistributable here either. Shipping weights that cannot be used without a corpus that is absent
would add binary payload without adding reproducibility.

Instead this directory ships:

* `CHECKPOINT_MANIFEST.csv` — one row per checkpoint with its **SHA-256**, naming convention,
  legacy training metadata (epochs run, validation balanced accuracy, test balanced accuracy,
  test segment count), and the hashes of the sibling artefacts (`result.json`,
  `predictions.csv`, `history.csv`, `model_architecture.txt`, `split.json`).
* the regeneration instructions below.

## Naming convention

```
eegnet/sub-<NN>/seed_<S>/best.pt
```

* `<NN>` — the held-out test subject, `01`…`71`; **68** subjects are valid, all in the frozen
  `splits.json`.
* `<S>` — neural-network initialisation seed, `0`, `1`, `2`.
* `best.pt` — the epoch selected by **validation subject macro balanced accuracy**, not by test
  performance.

In the owner's local scientific tree these live under the archived formal-run tree
(`archive/legacy_or_superseded/formal_results_v1/project/results/formal_autodl_v1/eegnet/`), which
is why the `dir` column of the manifest carries that legacy prefix. **That directory layout is
not reproduced in this repository.** The `dir` column is a historical record of provenance, not a
live path — nothing reads it to locate a file.

## Facts about the set

| property | value |
|---|---|
| checkpoints | **204** = 68 subjects x 3 seeds |
| distinct contents | **204** of 204 (no duplicates) |
| per-checkpoint size | 33,683 bytes, identical across all 204 |
| total size | ~6.55 MB |
| architecture | `braindecode.models.EEGNet`, 61 channels, 2 outputs, 2000 samples, 500 Hz |
| hyper-parameters | frozen in `../legacy_apparatus/configs/baselines.json` |

The identical per-file size is expected: one architecture, one shape, `float32` parameters only.

## How they were produced

1. Build the corpus — `../legacy_apparatus/prepare_data.py` with
   `../legacy_apparatus/configs/source_only_data.json`. This produces the 9,390-window manifest,
   the 61-channel order, the label mapping, the waveform cache and `splits.json`
   (subject-LOSO, seed `20260908`).
2. Train — `../legacy_apparatus/run_baselines.py` with
   `../legacy_apparatus/configs/baselines.json`, `stage: formal`, `models: ["eegnet"]`,
   `seeds: [0, 1, 2]`, `test_subjects: all`.
3. Verify — `../legacy_apparatus/verify_baselines.py`.

The formal run that produced the published numbers used **Python 3.11.16 / torch 2.10.0+cu126 /
braindecode 1.3.2** on an RTX 4090, and its provenance record is reproduced in
`../legacy_apparatus/outputs/source_only_500hz_v1/provenance.json`.

## How to check a set you have

The manifest is the contract. For every row, `sha256_best_pt` is the SHA-256 of that
`best.pt`, and `sha256_normalization_npz` is shared across seeds within a subject — a
`normalization.npz` is derived from the training split, so it does not depend on the seed.

Two independent anchor hashes that the published verifiers assert:

| artefact | SHA-256 |
|---|---|
| `segments.csv` (9,390-window manifest) | `5eba619fc0dd516f8caf72a86fd36a34ca07c589df9d269b2bcdbd53c1c3a744` |
| `splits.json` (68-fold subject-LOSO) | `db02bab96f8147bffa4836967a29c0763bc9f8130fa994252ed269649070c184` |
| `run_baselines.py` (the runner) | `6c7764b71996cad38fb045025349dd7ee51147e3331d4119709f13ed9a59fe49` |
| `configs/baselines.json` | `854a8c598bff49c41f994f0112947cd29889220d484a4de35c0172e03d4899cc` |

TTA Phase 1 additionally asserted, at run time, that the checkpoint set it adapted was this one —
204 checkpoints with 204 distinct contents, matching the formal run on both machines.

## Licence and attribution

These weights were trained by this project from the public **ds004902** release. They are derived
data, and their redistribution status depends on the ds004902 licence, not on this repository's
licence — which is itself not yet assigned (see the root `README.md` §8). They are therefore
withheld here pending an explicit owner decision, rather than included by default.

## If you need the weights

Ask the owner. Publishing them is a one-line policy change — they are 6.55 MB and already
hash-manifested here — but it is a licensing decision, not a technical one, and it is not this
repository's call to make by default.
