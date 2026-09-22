# LEGACY_EEGNET_PROVENANCE.md

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Question this document answers:** is the frozen legacy ds004902 EEGNet trunk recoverable,
and is it the *same* trunk the project's historical record refers to?

**Status:** `VERIFIED` (every claim below is backed by a hash, a file listing, or a
re-execution recorded in `outputs/source_closure.json`).

---

## 0. Answer in one line

Yes. The 68 held-out-subject EEGNet checkpoints, the shared window manifest, the frozen
LOSO split and the frozen training config are all present and **byte-identical to the
formal run that produced the historical numbers**. SOURCE closure was re-executed on the
exact legacy held-out windows and reproduces the legacy per-window predictions with
`max |Δp| = 8.94e-07`, **0 label flips**, and balanced accuracy matching the legacy JSON
to full double precision in 204/204 fold-seeds.

---

## 1. Where the legacy apparatus lives

| role | path | note |
|---|---|---|
| legacy code | `project/run_baselines.py` | one file trains and evaluates all baseline models |
| legacy data builder | `project/prepare_data.py` | produced the shared window manifest |
| frozen training config | `project/configs/baselines.json` | hashed in the formal provenance |
| shared window manifest | `project/outputs/source_only_500hz_v1/` | `segments.csv`, `splits.json`, `waveforms/` |
| **formal run output** | `formal_results_v1/project/results/formal_autodl_v1/` | the historical numbers come from here |
| formal run logs | `formal_results_v1/logs/` | `formal.screen.log`, `formal.resume1.screen.log` |
| archived copy of the code | `formal_results_v1/project/run_baselines.py` | byte-identical to the live copy |

### 1.1 Byte-identity of the artefacts actually used

| artefact | SHA-256 | matches formal provenance |
|---|---|---|
| `project/run_baselines.py` (and its archived copy) | `6c7764b71996cad38fb045025349dd7ee51147e3331d4119709f13ed9a59fe49` | ✅ `runner_sha256` |
| `segments.csv` (live and archived copies) | `5eba619fc0dd516f8caf72a86fd36a34ca07c589df9d269b2bcdbd53c1c3a744` | ✅ `manifest_sha256` |
| `splits.json` (live and archived copies) | `db02bab96f8147bffa4836967a29c0763bc9f8130fa994252ed269649070c184` | ✅ `splits_sha256` |
| `configs/baselines.json` (live and archived copies) | `854a8c598bff49c41f994f0112947cd29889220d484a4de35c0172e03d4899cc` | ✅ `config_sha256` |

Live and archived copies are identical, so there is **no drift** between the code/data in
the working tree and the code/data that produced the formal results.
`prepare_data.py` is present only in the live tree (the archived bundle did not carry it);
this affects reproducibility of the *manifest build*, not of anything Phase 1 does — Phase 1
consumes the already-frozen manifest and never rebuilds it.

---

## 2. Point-by-point answers to the Stage-0 questions

### A. What training structure produced the legacy numbers?

**68 independent LOSO folds × 3 seeds for EEGNet** (plus the same for DeepConvNet, and
68 × 1 for RBF-SVM). Every fold trains a *fresh* network from scratch on its own
train/validation split; there is no shared trunk and no fine-tuning chain.

Formal stage configuration (`configs/baselines.json` → `stages.formal`):
`test_subjects = "all"`, `seeds = [0, 1, 2]`, `max_epochs = 50`,
`max_segments_per_subject_session = null`.

Every fold is `53 train / 14 validation / 1 test` subjects, with **both sessions of a
subject always in the same split** (`prepare_data.py` guarantees this; re-verified: the
three subject sets are pairwise disjoint and their union is exactly the 68-subject set).

Checkpoint inventory on disk:

| model | subject dirs | seeds | `.pt` files |
|---|---:|---|---:|
| `eegnet` | 68 | `seed_0, seed_1, seed_2` | 204 |
| `deepconvnet` | 68 | `seed_0, seed_1, seed_2` | 204 |
| `rbf_svm` | 68 | `seed_0` | 0 (`.joblib` only) |

The 408 `.pt` files in the bundle therefore account for both neural models exactly, with
**no missing fold** and **no extra fold**.

### B. Which checkpoint corresponds to which held-out subject?

`formal_results_v1/project/results/formal_autodl_v1/eegnet/<test-subject>/seed_<s>/best.pt`.

The directory name *is* the held-out subject; `seed_<s>` selects the training seed. That
mapping is asserted at load time by `01_source_closure.py` and by
`src/p1_arms.load_source` (which additionally checks `ckpt["seed"]` and that the subject is
its own fold's test subject). Full inventory:
`legacy_checkpoint_inventory.csv`.

### C. Is the legacy preprocessing fully recoverable?

Yes — completely, for everything Phase 1 depends on. Per window the manifest records:

* `segment_id` = `{subject}_{session}_e{epoch:04d}_s{start:06d}` — globally unique, 9390 rows
* `subject`, `session` (`ses-1` / `ses-2`), `label` (`ses-1`→0 = NS, `ses-2`→1 = SD)
* `source_file`, `source_epoch_index`, `source_urevents`
* `start_sample_in_epoch` (always 0), `stop_sample_exclusive` (always 2000)
* `source_sfreq` / `sfreq` (500 Hz), `unit` (`uV`)
* `waveform_file`, `array_index`
* QC columns `qc_pass`, `included`, `max_abs_uv`, `max_ptp_uv`, `min_channel_std_uv`,
  `exclusion_reason`

Frozen generation rules (from the manifest report, `report.md`):
4 s non-overlapping cuts **inside each pre-existing epoch**, tail dropped, no stitching
across epochs; 61 channels in `channels.json` order; only 500 Hz recordings; float32 µV;
shape `(61, 2000)` per window.

**Channel order** is frozen in `project/outputs/source_only_500hz_v1/channels.json`:
`Fp1, AF3, AF7, Fz, F1, F3, F5, F7, FC1, FC3, FC5, FT7, Cz, C1, C3, C5, T7, CP1, CP3, CP5,
TP7, TP9, Pz, P1, P3, P5, P7, PO3, PO7, Oz, O1, Fpz, Fp2, AF4, AF8, F2, F4, F6, F8, FC2,
FC4, FC6, FT8, C2, C4, C6, T8, CPz, CP2, CP4, CP6, TP8, TP10, P2, P4, P6, P8, POz, PO4,
PO8, O2` — 61 channels, cross-checked against the EEGLAB `.set` channel list and MNE's
montage read (identical order).

**Input normalisation** is the per-channel train-set mean/std:
`run_baselines.fit_wave_scaler(corpus, split["train"])` → saved per fold as
`normalization.npz`. It is fitted **only on training subjects** and applied unchanged to
validation and test. Phase 1 reuses the saved file, never refits it.

**Labels**: `ses-1` = 0 = normal sleep (NS); `ses-2` = 1 = sleep deprivation (SD). The
legacy report is explicit that SD is an experimental condition and **not** actual danger.

**Subject split**: `splits.json`, `split_seed = 20260908`, 68 folds, both sessions always
co-assigned.

### D. What normalization layers does the EEGNet actually contain?

Read directly from a checkpoint. The architecture is braindecode 1.3.2 `EEGNet` with
`n_chans=61, n_outputs=2, n_times=2000, sfreq=500` and
`F1=8, D=2, F2=16, kernel_length=250, depthwise_kernel_length=64, drop_prob=0.5,
final_layer_with_constraint=true, norm_rate=0.25`.

| # | module name | type | features | affine | track_running_stats | γ (weight) | β (bias) |
|---|---|---|---:|---|---|---|---|
| 1 | `bnorm_temporal` | `BatchNorm2d` | 8 | `True` | `True` | `bnorm_temporal.weight` | `bnorm_temporal.bias` |
| 2 | `bnorm_1` | `BatchNorm2d` | 16 | `True` | `True` | `bnorm_1.weight` | `bnorm_1.bias` |
| 3 | `bnorm_2` | `BatchNorm2d` | 16 | `True` | `True` | `bnorm_2.weight` | `bnorm_2.bias` |

**BatchNorm layer count: 3.** Affine scalars: 8 + 8 + 16 + 16 + 16 + 16 = **80**, held in
6 tensors (`weight` and `bias` of each layer). TENT's trainable set is exactly those 6
tensors / 80 scalars — **1.2654 %** of the model's 6322 parameters. All three layers are
`affine=True, track_running_stats=True`, i.e. **the trunk has usable affine parameters for
TENT and usable frozen running statistics for SOURCE**.

*(Correction made during verification and kept visible: an earlier draft of this document
first mis-stated the total, and the synthetic smoke test reports **20** affine scalars
because it uses a 4-channel tiny model (2·2 + 2·4 + 2·4 = 20). Only the 61-channel
production model's number, **80**, is authoritative; it is re-derived from the real
checkpoint by `99_norm_inventory.py` and re-checked by the Phase 1 verifier.)*

Each layer also stores `running_mean` (n), `running_var` (n) and `num_batches_tracked` (scalar).
All three are `affine=True, track_running_stats=True`, i.e. **the trunk has usable affine
parameters for TENT and usable frozen running statistics for SOURCE**.

No other normalization layer exists in the trunk: there is no `LayerNorm`, no `GroupNorm`,
no input-level normalization module — the input scaling is the external `normalization.npz`
step, not a module. This matters: TENT can only reach these three layers.

Model-level facts: 21 `state_dict` entries; 6322 parameters; `conv_spatial` weight lives
under `conv_spatial.parametrizations.weight.original` (shape `(16, 1, 61, 1)`) and the
classifier under `final_layer.linearconstraint.parametrizations.weight.original`
(shape `(2, 992)`), because of braindecode's norm-rate parametrization. TENT is only ever
allowed to touch the six affine tensors named above (negative control NC6).

### E. Did the legacy evaluation ever random-shuffle target windows?

**No.** `run_baselines.train_neural` builds its test loader as
`DataLoader(datasets["test"], batch_size=…, shuffle=k == "train", …)`, i.e. `shuffle=False`
for validation and test; only the training loader shuffles. `predict()` additionally
asserts `all(not m.training for m in model.modules())` before every evaluation and
`assert before == after` on the model state hash, and re-runs the test pass to prove the
scores are bit-identical on repeat.

The legacy TENT prototype (`project/run_tent_rbf_baselines.py`) *did* define a
non-temporal order (`stream_order = "sha256_segment_id"`). **That prototype is not the
Phase 1 apparatus** and is not reused — see §5.

### F. Can the per-window temporal provenance be recovered?

Yes, and this is the load-bearing fact for a sequential TTA experiment.

* `source_epoch_index` is the EEGLAB epoch number inside the corresponding `.set` file.
* Verified for all 136 recording files: within each file, rows appear in strictly ascending
  `source_epoch_index` order, and `array_index` is exactly `0..n-1` (so array position and
  epoch index agree).
* Exactly **6 of 136 recordings** have any missing epoch index, and in **all six the missing
  epochs are only at the tail** (the recording's retained epochs are a contiguous block
  `0..k`). There is therefore **no interior gap** in any recording's retained stream.
* Every retained epoch contributes exactly one window (`start_sample_in_epoch = 0`,
  `stop_sample_exclusive = 2000` for all 9390 rows), so window → epoch is one-to-one.
* The `.set` files are **epoched** (e.g. `sub-01_ses-1`: 69 epochs × 61 chans × 2000
  samples at 500 Hz, EEGLAB event grid at 0, 2000, 4000, …).

Consequences, stated precisely:

* **Within a recording, true chronological order IS recoverable** and is used as the stream
  order.
* **Absolute time is NOT recoverable**: the epochs carry no clock time and the preprocessed
  files are a derivative of the original recordings, not the recordings themselves.
* **Cross-session chronology is NOT identifiable** — see
  `TARGET_STREAM_PROVENANCE.md` §2, which also records a metadata contradiction.

---

## 3. The historical aggregate metrics, and the aggregation rule

The numbers in the project record are exactly the `eegnet` rows of
`formal_results_v1/project/results/formal_autodl_v1/summary_variability.csv`:

| metric | grand_subject_mean (68 subjects × 3 seeds) | project record |
|---|---:|---:|
| accuracy | 0.5963370366036311 | 0.5963 |
| balanced accuracy | **0.5924169784325324** | 0.5924 |
| f1 | 0.5550204299453863 | 0.5550 |
| roc_auc | 0.6109230390089248 | 0.6109 |

**Aggregation rule (recovered, not assumed):** for each seed, take the per-subject metric
values over the 68 held-out subjects (`summary_per_seed.csv`), then take the *unweighted
mean of the three seed-level subject means* (`summary_variability.csv`,
`grand_subject_mean`). Equivalently: mean over seeds of mean over subjects. It is **not** a
pooled window-level mean, and **not** a single-seed number.

Seed-level subject means (balanced accuracy): seed 0 = 0.589407232564001,
seed 1 = 0.5915601505934751, seed 2 = 0.596283552140121 →
mean = 0.5924169784325324. ✅ reproduces the record.

Between-seed SD of the subjects' means is small for EEGNet
(`balanced_accuracy` = 0.0035) relative to between-subject SD (0.1548), so the subject
dimension dominates the variance — which is why the Phase 1 statistics use the subject as
the unit.

### 3.1 SOURCE closure result

`01_source_closure.py` re-ran every frozen checkpoint over that fold's exact legacy
held-out windows and compared element-wise against the legacy `predictions.csv`:

| quantity | value |
|---|---:|
| fold-seeds checked | 204 (68 subjects × 3 seeds) |
| windows scored | 28 170 (= 3 × 9390) |
| **max abs probability delta vs legacy** | **8.94e-07** |
| median per-fold max abs delta | 1.94e-07 |
| **label flips** | **0** |
| balanced accuracy == legacy JSON (to 1e-12) | 204/204 |
| fold-seeds with exactly zero delta | 0 |

Verdict: `SOURCE_CLOSED_NUMERICALLY`.

**Honest reading of the residual.** The legacy numbers were produced on an RTX 4090
(`provenance.json: "gpu": "NVIDIA GeForce RTX 4090"`, `os: Linux`); this closure was run on
the local machine. A ~1e-7 probability difference is ordinary fp32 reassociation between
CUDA and CPU kernels. It changes no label, no metric, and no rank. It does mean the legacy
`predictions.csv` files are **not bit-reproducible off the original hardware**, and Phase 1
therefore reports its own SOURCE numbers as the reference for every Δ it quotes, rather
than quoting the legacy files as ground truth.

The legacy `predictions.csv` files are preserved and are used as the closure *target* only
in `01_source_closure.py`; nothing else reads them.

---

## 4. Related historical branches that Phase 1 does NOT inherit

* **DeepConvNet** (`deepconvnet`, 204 checkpoints) — out of scope for Phase 1.
* **RBF-SVM** (`rbf_svm`, 68 `.joblib`) — out of scope; not a TTA substrate (no
  differentiable normalization).
* **`audit/eeg_tta_phase1/`** is isolated from `project/vigilance_generalization_v1/`; no
  BCIT Phase 3/4 artefact, endpoint or verdict is read, written or re-interpreted here.

---

## 5. The pre-existing legacy TENT prototype — read, and rejected as the Phase 1 apparatus

`project/run_tent_rbf_baselines.py` + `project/configs/tent_rbf_svm.json` +
`project/TENT_BASELINE.md` already exist and implement a TENT variant. It was **never run at
the formal stage**: `formal_results_v1/.../formal_autodl_v1/` contains only `eegnet`,
`deepconvnet`, `rbf_svm` — there is **no `eegnet_tent` directory**. The only TENT artefacts in
the workspace are a 3-subject pilot under `pilot_autodl_v1/` (which contains no `*_tent`
directory either — its `eegnet`/`deepconvnet`/`rbf_svm` dirs are source-only baselines).

That prototype is **not** a valid Phase 1 apparatus, for four independent reasons, each of
which would on its own break the frozen protocol:

| # | prototype behaviour | why Phase 1 cannot use it |
|---|---|---|
| 1 | `stream_order = "sha256_segment_id"` (`stream_rows()` sorts by SHA-256 of the segment id) | destroys temporal order; violates prompt §10 and NC7/NC8 |
| 2 | `select_tent_lr()` picks the learning rate by **validating on labelled validation subjects** and taking the argmax | label-based hyper-parameter tuning; violates prompt §8 |
| 3 | `adapt_subject()` records `probs` from the logits of the **post-update** pass | violates prequential semantics (prompt §12) |
| 4 | one `adapt_subject` call over *all* test rows with `reset_per_subject: true` only in config prose | no per-subject episode reset in the data path |

It is retained as historical evidence and is **explicitly not imported**. Phase 1 implements
its own arms in `src/p1_arms.py`.

---

## 6. Open provenance items (recorded, not blocking)

1. **`prepare_data.py` is not in the archived bundle.** The manifest it built is frozen and
   hash-verified, so Phase 1 is unaffected; rebuilding the manifest from raw `.set` files is
   not required and was not attempted.
2. **EEG unit.** The manifest says `uV`, justified by EEGLAB storage convention and the
   source `channels.tsv`. The legacy report itself flags that the preprocessed files carry no
   independent unit calibration. This is inherited unchanged; it affects only absolute scale,
   which the per-channel source normalization already removes.
3. **Reference electrode contradiction** (`CMS` in the sidecar vs common-average) and the
   zero-padding facts recorded in `AGENTS.md` belong to the BCIT lane's `ds004120` payloads,
   **not** to ds004902, and play no role here.
4. **`sub-04`** has only 4 windows in `ses-1` (16 s). It is kept because the legacy split and
   the legacy numbers include it; its per-subject statistics are reported with its `n` so
   that no reader mistakes it for a well-powered subject.
5. **No git repository** — provenance rests on file-content SHA-256 only (`COMMIT PENDING`).
