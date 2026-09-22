# SERVER_REQUEST.md — HARD STOP

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Status: READY FOR AN OWNER-APPROVED REMOTE GPU SERVER. No formal adaptation has been run.**

> Updated after the pre-result protocol corrections: primary stream is now `metadata_order`,
> the arm set is now four arms, and the verifier and controls have been extended accordingly.
> Stage-0 verification is **65/65**, negative controls **50/50 bite**, synthetic smoke **PASS**
> (all exit code 0).

---

## 1. Why the run has not started

The standing execution rule for this preset forbids any neural-network training or adaptation
workload on the owner's local machine, and requires a HARD STOP plus an explicit request when
no server is available.

`TENT_LITERAL` and `TENT_DET` are not inference. Each incoming batch performs:

```
forward -> softmax entropy -> loss.backward() -> optimizer.step()   (Adam over BN affine)
```

That is a neural-network adaptation workload by the rule's own definition, over real ds004902
data. So it is not run here.

**The local machine has been used only for what the rule allows:** reading code, reading and
hashing artefacts, writing the implementation, synthetic unit tests, static verification, and
one inference-only SOURCE closure. See §7.

---

## 2. What is done and verified locally

| item | state |
|---|---|
| legacy EEGNet provenance recovery | **DONE** — `LEGACY_EEGNET_PROVENANCE.md` |
| SOURCE closure vs legacy predictions (204 fold-seeds) | **DONE** — max \|Δp\| 8.94e-07, 0 label flips, BAcc exact |
| canonical TENT method audit (reference hash-pinned in-tree) | **DONE** — `TENT_METHOD_SPEC.md` |
| **cross-visit chronology corrected to `SessionOrder`** | **DONE** — authoritative sources quoted in `TARGET_STREAM_PROVENANCE.md` §3 |
| target-stream manifest (`metadata_order`) | **DONE** — 9390 rows |
| batch-size audit incl. trailing sizes | **DONE** — `batch_size_audit.csv` |
| collapse taxonomy + 4-arm interpretation matrix frozen | **DONE** — `COLLAPSE_TAXONOMY.md` |
| four arm implementations | **DONE** — `src/p1_arms.py` |
| independent verifier | **DONE** — **65/65**, exit 0 |
| negative controls NC1–NC19 | **DONE** — **50/50** assertions bite, exit 0 |
| synthetic smoke test (all 4 arms) | **DONE** — PASS, exit 0 |
| **formal adaptation run** | **NOT RUN — needs this server** |

---

## 3. What the server must provide

* **one CUDA GPU** — any modern NVIDIA card. This is a small job (see §5); an 8 GB card is
  ample. GPU is required by the execution rule, not by memory pressure.
* Python 3.11 with the packages in §3.1
* read access to this workspace tree (or a synced copy)
* disk for `audit/eeg_tta_phase1/outputs/units/` — 816 JSON units, ≈0.5–1 GB

### 3.1 Environment

| package | version (local reference) |
|---|---|
| Python | 3.11.13 (3.11.x fine) |
| torch | 2.10.0+cu126 |
| braindecode | 1.3.2 |
| numpy | 2.3.2 |
| scipy | 1.16.1 |
| scikit-learn | 1.7.2 |
| matplotlib | 3.10.5 |

`pandas`/`pyarrow` are **not** required — all artefacts are CSV/JSON (§8).

**Required inputs only:** `project/outputs/source_only_500hz_v1/` (frozen manifest +
waveforms), `project/configs/baselines.json`, `project/third_party/` (reference code),
`formal_results_v1/project/results/formal_autodl_v1/eegnet/**` (204 checkpoints), and
`data/ds004902/metadata_behavior/participants.tsv` (the `SessionOrder` column). The raw
`data/ds004902/preprocessed/` EEG is **not** needed — the pipeline consumes the frozen
waveform cache.

---

## 4. Exact remote command

From the workspace root:

```bash
python audit/eeg_tta_phase1/10_run_phase1.py \
    --variants metadata_order \
    --arms source bn_only tent_literal tent_det \
    --seeds 0 1 2 \
    --device cuda \
    --report
```

Notes:

* `--variants metadata_order` is the **only** permitted primary stream. The orchestrator
  **refuses** `NS_then_SD` / `SD_then_NS` with an explicit error; those are PARKED order
  diagnostics and are not part of the collapse-existence experiment.
* `--seeds 0 1 2` keeps SOURCE numerically identical to the historical benchmark
  (68 subjects × 3 seeds). `--seeds 0` is a coherent but *reduced* variant and must be
  reported as such — it would no longer reproduce `BAcc = 0.5924` exactly.
* The run is **resumable**: one JSON per (variant, arm, seed, subject) under `outputs/units/`,
  and completed units are skipped.

### 4.1 After the run

```bash
python audit/eeg_tta_phase1/20_plots.py          # per-subject trajectories + group median/IQR
python audit/eeg_tta_phase1/90_verify_phase1.py  # now includes J1-J12 and K1-K6
python audit/eeg_tta_phase1/95_write_report.py   # regenerate the report from artefacts
```

The verifier grows from **65** checks (Stage 0) to **65 + J1–J12 + K1–K6** once units exist.
The outcome-dependent checks are *skipped*, not silently passed, while the arms have not run.

---

## 5. Expected scope and runtime

### 5.1 Units, batches, windows

| quantity | value |
|---|---:|
| subjects (held-out folds) | **68** |
| seeds | **3** (`0, 1, 2`) |
| arms | **4** (`source`, `bn_only`, `tent_literal`, `tent_det`) |
| **work units = subjects × seeds × arms** | **68 × 3 × 4 = 816** |
| windows per seed (all 68 subjects) | **9 390** |
| windows per subject per seed | min **66**, max **151**, mean **138.1** |
| batches per subject per seed (2 visits, no batch crosses a visit) | min **3**, max **7**, mean **5.66** |
| **batches per seed (all subjects)** | **385** |
| batches across all seeds | 385 × 3 = **1 155** |
| **total batch-steps across the whole run (× 4 arms)** | 1 155 × 4 = **4 620** |
| windows scored (all arms, all seeds) | 4 × 3 × 9 390 = **112 680** |

Distribution facts that matter for the estimate: `sub-04/ses-1` has **4 windows**, so that
visit is a single batch of size 4; `sub-04/ses-2` is `[32, 30]`. `sub-52` is
`[32, 32, 8]` and `[32, 32, 15]`. Small visits are **kept**, never padded or dropped — the
actual sizes are recorded per subject in `batch_size_audit.csv`.

### 5.2 Measured cost

Measured locally on CPU, `sub-01`, 123 windows / 5 batches:

| arm | wall time | per batch |
|---|---:|---:|
| SOURCE | 8.4 s | 1.67 s |
| TENT | 5.2 s | 1.04 s |

Extrapolating from the measured per-batch cost: 4 620 batch-steps × ~1.3 s ≈ **1.7 CPU-hours**
of forward/backward arithmetic, plus per-unit overhead (checkpoint load + state hashing) of
roughly 0.3–0.5 s × 816 ≈ 5 minutes. **On one GPU this is a small job** — order 10–30 minutes
wall clock, versus roughly 1.5–2.5 hours on a single CPU core. Embarrassingly parallel across
units if desired; the runner itself is sequential, so parallelising means launching several
`--subjects`-scoped invocations writing into the same `outputs/units/` directory (writes are
per-unit files, so this is safe).

`TENT_LITERAL` is stochastic (live Dropout); each unit seeds torch once at unit start, so the
result is reproducible *given that convention* but is a draw from a stochastic process.
`TENT_DET`, `BN_ONLY` and `SOURCE` are deterministic.

---

## 6. Output paths

Under `audit/eeg_tta_phase1/`:

| path | content |
|---|---|
| `outputs/units/<variant>__<arm>__seed<N>__<subject>.json` | **resumability unit** — one JSON per fold-seed-arm |
| `outputs/source_subject_metrics.csv` | per subject × seed metrics, SOURCE |
| `outputs/bn_only_subject_metrics.csv` | ditto, BN_ONLY |
| `outputs/tent_literal_subject_metrics.csv` | ditto, TENT_LITERAL |
| `outputs/tent_det_subject_metrics.csv` | ditto, TENT_DET |
| `outputs/subject_level_comparison.csv` | per-subject deltas vs SOURCE + literal-vs-det disagreement |
| `outputs/<arm>_predictions.csv` | per-window predictions, all four arms |
| `outputs/tent_batch_trajectory.csv` | per-batch trajectory, all four arms |
| `outputs/tent_parameter_drift.csv` | affine drift, both TENT arms |
| `outputs/collapse_subject_summary.csv` | per-subject collapse statistics |
| `outputs/batch_and_skew_audit.csv` | batch sizes, class composition, deltas |
| `outputs/collapse_group_summary.json` | group statistics + verdict |
| `outputs/collapse_verdict.json` | the frozen-taxonomy verdict |
| `outputs/plots/` | per-subject and group trajectory figures |

---

## 7. What was executed locally, exactly

Real-data, inference-only:

1. **`01_source_closure.py --seeds 0 1 2`** — re-ran the 204 frozen checkpoints in
   `model.eval()` + `torch.inference_mode()` over the legacy held-out windows. No optimizer,
   no backward pass, no parameter update, no state mutation (asserted). Result:
   `SOURCE_CLOSED_NUMERICALLY`, max \|Δp\| = 8.94e-07, 0 label flips, BAcc exact 204/204.
2. **`99_norm_inventory.py`** — read one checkpoint to enumerate the normalization layers.

Static / synthetic only:

3. `tests/test_p1_synthetic_smoke.py` — random tensors, 4-channel tiny model, no real data.
4. `tests/test_p1_controls.py` — NC1–NC19 against synthetic fixtures.
5. `90_verify_phase1.py` — Stage 0 gate.
6. `10_run_phase1.py --manifest-only` — built the stream manifest; no model was constructed.

**No real ds004902 window has been adapted, and no adapted weight exists anywhere.**

---

## 8. One documented format deviation

The brief suggested `.parquet` for `*_predictions`, `tent_batch_trajectory` and
`tent_parameter_drift`. **`pyarrow`/`fastparquet` are not installed** in the project
interpreter (measured). The same per-row information is written as `.csv` with identical
columns:

| brief filename | delivered |
|---|---|
| `source_predictions.parquet` | `source_predictions.csv` |
| `bn_only_predictions.parquet` | `bn_only_predictions.csv` |
| `tent_predictions.parquet` | `tent_literal_predictions.csv` + `tent_det_predictions.csv` |
| `tent_batch_trajectory.parquet` | `tent_batch_trajectory.csv` |
| `tent_parameter_drift.parquet` | `tent_parameter_drift.csv` |

If parquet is preferred, `pip install pyarrow` on the server plus a one-line `to_parquet`
conversion suffices — the column set does not change.

---

## 9. What I am asking for

Please provide one of:

**(a)** an owner-approved remote server / GPU environment with this workspace tree available
and the §3.1 environment present — then the §4 command is run as-is; **or**

**(b)** an explicit owner instruction to run on this machine anyway, which overrides the
standing prohibition. I will not assume this from silence.
