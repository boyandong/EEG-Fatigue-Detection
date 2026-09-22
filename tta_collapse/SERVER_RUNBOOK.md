# SERVER_RUNBOOK.md

**Session:** `EEGTTA-PHASE1-20260920-TENT-COLLAPSE-EXISTENCE`
**Server status: OWNER-APPROVED** (2026-09-20). This file supersedes the "HARD STOP / request"
framing of `SERVER_REQUEST.md`; that file remains as the historical request record.

---

## 1. Server

| field | value |
|---|---|
| host | `<SERVER_HOST>` |
| port | `26466` |
| user | `root` |
| container | `autodl-container-5l8crzl3la-735c0c9e` |
| GPU | **NVIDIA GeForce RTX 4090**, 1 visible device, capability (8, 9) |
| driver | 580.105.08, driver CUDA capability **13.0** |
| host kernel | `Linux 5.15.0-78-generic`, glibc 2.35 |
| CPU / RAM | 208 cores / 503 GB |
| remote root | `/root/srtp/` (mirrors the workspace layout) |
| interpreter | `/root/miniconda3/bin/python` (Python 3.12.3) |

**Access.** A dedicated ed25519 key was installed once via password auth and is used for
every subsequent command:

```
<HOME>\.ssh\<key-name>
ssh -p 26466 -i <key> root@<SERVER_HOST>
```

Helpers: `05_remote.py` (run/put/get/collect-env), `06_remote_verify.py`
(env | provenance | gate). The password is never stored in this repository.

**Driver-vs-runtime note (owner instruction §6).** The host driver advertises CUDA 13.0, which
is *newer* than the PyTorch CUDA runtime. This is expected and harmless — the driver is
backward-compatible with the runtime. **No packages were upgraded because of the driver
version**, and `torch` was deliberately left at the container's build rather than replaced.

---

## 2. Environment status

| package | frozen target | container has | action |
|---|---|---|---|
| Python | 3.11 | **3.12.3** | keep (reported as a documented difference, see §2.1) |
| torch | 2.10.0+cu126 | **2.8.0+cu128** | **kept** — already a working CUDA build; upgrading risks ABI churn |
| numpy | 2.3.2 | **2.3.2** | exact match |
| matplotlib | 3.10.5 | **3.10.5** | exact match |
| scipy | 1.16.1 | installed | pinned install |
| scikit-learn | 1.7.2 | installed | pinned install |
| braindecode | 1.3.2 | installed | pinned install, `--no-deps` |
| mne | 1.11.0 | installed | pinned install |
| pandas / pyarrow / joblib / h5py | any | installed | needed by mne/braindecode import paths |

### 2.1 Why the Python/torch difference is recorded rather than "fixed"

The frozen environment is a *provenance* claim, not a superstition. Two facts make the
container's differing versions acceptable **for this lane specifically**, and they are checked
rather than assumed:

1. **The model code path is version-insensitive.** Phase 1 reconstructs EEGNet through
   `braindecode.models.EEGNet` with an explicit keyword configuration and then loads a
   `state_dict` with `strict=True`. The verifier asserts 21 entries / 3 BatchNorm layers /
   80 affine scalars / 6322 parameters from the *actual* checkpoint, so an architecture
   drift would fail loudly rather than silently.
2. **SOURCE closure is re-run on this server.** The closure gate compares re-inference
   against the legacy `predictions.csv` produced by the original RTX 4090 run. If a
   torch/CUDA difference changed the forward pass materially, the closure would report it.

What is *not* claimed: that a torch 2.8.0 result is bit-identical to a torch 2.10.0 result.
The forward pass may differ at the 1e-7 level (it already does between CPU and the original
4090 — see `LEGACY_EEGNET_PROVENANCE.md` §3.1). That is why the closure re-run is a gate and
why Phase 1 reports its **own** SOURCE numbers as the Δ reference.

---

## 3. Data synced to the server

| item | size | purpose |
|---|---|---|
| `project/outputs/source_only_500hz_v1/waveforms/` | 4 470 MB | the 136 `.npy` waveform caches |
| `project/outputs/source_only_500hz_v1/{segments,splits,channels,config,provenance,subjects,recordings}` | small | frozen manifest + hashes |
| `formal_results_v1/project/results/formal_autodl_v1/eegnet/` | 104 MB | 204 checkpoints + `normalization.npz` + legacy `predictions.csv` |
| `formal_results_v1/project/results/formal_autodl_v1/provenance.json` | small | the hash authority |
| `project/configs/baselines.json`, `project/run_baselines.py` | small | frozen config + runner |
| `project/third_party/tent-official-e9e926a/` | small | the pinned TENT reference |
| `data/ds004902/metadata_behavior/participants.tsv|json` | small | `SessionOrder` |
| `audit/eeg_tta_phase1/` (code, tests, specs, stage-0 artefacts) | 2 MB | this lane |

The raw `data/ds004902/preprocessed/` EEG is **not** synced: the pipeline consumes the frozen
waveform cache, and the whole point is that Phase 1 reuses the legacy windows unchanged.

---

## 4. The command (only after every gate in §5 passes)

```bash
cd /root/srtp/audit/eeg_tta_phase1
/root/miniconda3/bin/python 10_run_phase1.py \
    --variants metadata_order \
    --arms source bn_only tent_literal tent_det \
    --seeds 0 1 2 --device cuda --report
```

Scope: **68 subjects × 3 seeds × 4 arms = 816 units**; 9 390 windows and 385 batches per
seed; ≈4 620 batch-steps. Resumable per unit at
`outputs/units/<variant>__<arm>__seed<N>__<subject>.json`.

**PARKED and refused by the runner:** `NS_then_SD`, `SD_then_NS`. Do not add variants, do not
add hyper-parameter sweeps, do not add TTA methods.

**Ownership:** exactly one writer process. If parallelising, scope each worker with
`--subjects` so unit files are disjoint. A worker must never share a unit with another.

---

## 5. Gate sequence (all must pass before §4)

| # | gate | how | pass condition |
|---|---|---|---|
| 1 | protocol correction verified locally | `90_verify_phase1.py`, `tests/test_p1_controls.py`, `tests/test_p1_synthetic_smoke.py` | 73/73, 70/70 bite, SMOKE PASS |
| 2 | remote environment | `06_remote_verify.py env` | CUDA available on the 4090; required imports present |
| 3 | remote provenance | `06_remote_verify.py provenance` | runner/manifest/splits/config hashes match; 204 checkpoints; 136 waveform files; 9390 rows; **0 units present**; no stale weights |
| 4 | remote verifier + controls | `06_remote_verify.py gate` | same pass counts as local |
| 5 | remote SOURCE closure (bounded) | one subject, seed 0, all 4 arms | sources reproduce the legacy probabilities within fp tolerance, **0 label flips** |
| 6 | formal-semantics smoke (predeclared) | seeds `0`, subjects `sub-01 sub-04` | see §6 |

Gate 6's subjects are predeclared **now**: `sub-01` (a normal-sized subject) and `sub-04`
(the 4-window session, so the tiny-batch path and the trailing-batch rule are exercised).
Scientific performance from gate 5/6 is **monitoring-only** and must not alter the protocol.

---

## 6. Expected geometry and runtime

| quantity | value |
|---|---:|
| units (68 × 3 × 4) | **816** |
| batches per seed | 385 |
| batch-steps total | ≈ 4 620 |
| windows scored | 112 680 |
| measured per-batch CPU cost | ~1.0–1.7 s |
| expected on the 4090 | order **10–30 minutes** wall clock |

---

## 7. After the run

```bash
python 20_plots.py
python 30_analyze_collapse.py --seeds 0 1 2
python 90_verify_phase1.py        # now 73 + J + K
python 95_write_report.py
```
Then retrieve `outputs/` and update the Research Tree, then **HARD STOP**.
