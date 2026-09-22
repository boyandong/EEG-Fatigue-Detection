# Tracked file size audit

Performed 2026-09-22 immediately before pushing `repo-refresh-v2-20260922`. The purpose is to
confirm that nothing large is present by accident — no raw data, no waveform cache, no redundant
checkpoint, no generated output that slipped past `.gitignore`.

**Result: clean. No unexpected large artifact found. No blocker.**

**Git LFS is not used**, and no LFS pointer is committed.

---

## 1. Totals

| metric | value |
|---|---:|
| tracked files | **1,144** |
| tracked size | **87.89 MB** (92,155,870 bytes) |
| largest single file | **3.02 MB** |
| files over 3 MB | **0** |
| files over 2 MB | 4 |
| files over 1 MB | 11 |
| binary blobs | 74 (1 `.pt` + 73 `.png`) |

For reference, GitHub's hard limit is 100 MB per file and its warning threshold is 50 MB. **No file
is within 30× of the hard limit**, and no push approaches a pack-size limit.

---

## 2. Distribution by category

| category | files | size | assessment |
|---|---:|---:|---|
| `tta_collapse/` | 941 | **76.82 MB** | dominated by the executed run's evidence (see §3) |
| `functional_prediction/` | 123 | 5.35 MB | code + specs + lightweight evidence |
| `shared/` | 25 | 3.76 MB | canonical manifests and splits — required |
| `archive/` | 36 | 1.78 MB | the byte-preserved legacy prototype |
| `docs/` | 16 | 0.16 MB | documentation |
| root files | 3 | 0.02 MB | `README.md`, `requirements.txt`, `.gitignore` |

### Breakdown of the three large trees

| path | files | size | what it is |
|---|---:|---:|---|
| `tta_collapse/evidence/units/` | 816 | **43.88 MB** | one JSON record per executed unit |
| `tta_collapse/evidence/plots/` | 73 | **17.27 MB** | per-subject trajectory plots |
| `tta_collapse/evidence/metrics/` | 24 | 15.28 MB | per-window predictions + aggregate metrics |
| `functional_prediction/evidence/dynamic_audit/` | 8 | 3.88 MB | Phase 1.75 dynamic statistics |

---

## 3. Top 25 tracked files, with justification

| # | bytes | path | category | scientifically justified? | suspicious? |
|---:|---:|---|---|---|---|
| 1 | 3,020,701 | `tta_collapse/evidence/metrics/tent_literal_predictions.csv` | per-window predictions | **yes** — lets a reviewer recompute every TENT_LITERAL statistic independently | no |
| 2 | 2,908,132 | `tta_collapse/evidence/metrics/tent_det_predictions.csv` | per-window predictions | **yes** — the diagnostic control arm | no |
| 3 | 2,880,038 | `tta_collapse/evidence/metrics/bn_only_predictions.csv` | per-window predictions | **yes** — the gradient-free control that carries the verdict | no |
| 4 | 2,851,291 | `tta_collapse/evidence/metrics/source_predictions.csv` | per-window predictions | **yes** — the frozen-source reference arm | no |
| 5 | 2,752,947 | `functional_prediction/evidence/dynamic_audit/J_V_Jres_session.csv` | Phase 1.75 session statistics | **yes** — the dynamic-extension negative rests on it | no |
| 6 | 1,794,324 | `shared/.../source_only_500hz_v1/segments_all.csv` | **pre-exclusion manifest** | **yes** — see §4; this is *not* a duplicate | no |
| 7 | 1,741,521 | `shared/.../source_only_500hz_v1/segments.csv` | canonical manifest | **yes** — anchor hash `5eba619f…`; defines the 9,390 windows | no |
| 8 | 1,694,800 | `tta_collapse/evidence/metrics/tent_batch_trajectory.csv` | per-batch trajectory | **yes** — the collapse-trajectory evidence | no |
| 9 | 1,216,263 | `archive/legacy/legacy_ns_sd_prototype/feature_extracting/feature_data/lstm_fatigue_best.pt` | **legacy binary** | **yes, as history** — see §5 | intentional |
| 10 | 1,210,485 | `functional_prediction/evidence/dynamic_audit/J_V_Jres_paired.csv` | Phase 1.75 paired statistics | **yes** | no |
| 11 | 1,203,797 | `tta_collapse/evidence/metrics/target_stream_manifest.csv` | target stream definition | **yes** — defines the adapted stream order | no |
| 12 | 940,023 | `tta_collapse/evidence/metrics/tent_parameter_drift.csv` | BN affine drift | **yes** — the normalization-drift measurement | no |
| 13 | 371,389 | `tta_collapse/evidence/plots/subject_sub-01_trajectory.png` | plot | **yes** — per-subject trajectory | no |
| 14–25 | 297,910–328,618 | `tta_collapse/evidence/plots/subject_sub-*.png` (12 more) | plots | **yes** — same class | no |

**Nothing in the top 25 is raw data, a waveform cache, a redundant checkpoint, or a generated
artifact that escaped exclusion.**

---

## 4. The one file worth explaining: `segments_all.csv` is not a duplicate

Two manifests of similar size sit side by side, which looks like duplication. It is not:

| manifest | rows | content |
|---|---:|---|
| `segments.csv` | 9,390 | the **canonical** manifest — every admitted window |
| `segments_all.csv` | 9,634 | the **pre-exclusion** manifest — every candidate, with its verdict |

The 244 rows present only in `segments_all.csv`, and their exclusion reasons:

| reason | count |
|---|---:|
| `subject_missing_usable_session` | 214 |
| `excessive_amplitude;excessive_peak_to_peak` | 16 |
| `excessive_amplitude` | 14 |
| **total excluded** | **244** |

This is the **inclusion/exclusion audit trail**. It is what lets a reviewer confirm that the 68-subject
cohort was produced by a rule applied before the data was seen, rather than by a choice made afterwards.
It is a **required provenance artifact**, and deliberately retained.

---

## 5. The single binary: the legacy LSTM checkpoint

`archive/legacy/legacy_ns_sd_prototype/feature_extracting/feature_data/lstm_fatigue_best.pt` — **1.2 MB**.

**Identified explicitly, as required, and assessed as intentional:**

* it is part of the **byte-preserved legacy snapshot** — it was already public in the repository's
  original commit `625dc3b`, and it verifies identical to that commit;
* removing it would **delete previously public content** without cause, and would not remove it from
  Git history in any case;
* its scientific role is **negligible** — it belongs to a superseded NS-vs-SD prototype that no
  current result depends on;
* it is `.gitignore`-whitelisted **explicitly**, so its presence is a decision rather than an
  oversight.

It is the **only** `.pt` file tracked. The 204 canonical EEGNet checkpoints (6.55 MB) are **not**
tracked; they are represented by `shared/ds004902_source_trunk/checkpoints/CHECKPOINT_MANIFEST.csv`.

The other 73 binaries are the TTA run's trajectory plots (17.27 MB) — the visual record of the
per-subject behaviour behind the `CASE 4` verdict.

---

## 6. Checks performed — each negative

| question | answer |
|---|---|
| Any accidental raw data (`.set`/`.fdt`/`.cnt`/`.edf`)? | **none tracked** |
| Any waveform cache (`.npy` under `waveforms/`)? | **none tracked** |
| Any duplicate evidence? | **no** — `segments_all.csv` is a distinct artifact set (§4) |
| Any generated output that escaped exclusion? | **no** |
| Any unnecessary binary? | **no** — 1 justified `.pt` + 73 plots |
| Any redundant checkpoint? | **no** — only the legacy 1.2 MB file, and it is history |
| Any `.gitignore`d file wrongly tracked? | **no** — ignored count is 0 |
| Any tracked file over 3 MB? | **no** — largest is 3.02 MB |
| Any Git LFS pointer? | **no** |

---

## 7. Honest note on the total

**87.89 MB is not small for a research repository, and it was not accepted automatically.** The
growth over `main` (≈2 MB) is almost entirely *evidence*: 816 executed-unit records, four arms of
per-window predictions, and the trajectory plots. That evidence is what allows an external reviewer
to recompute the published verdict without acquiring a dataset or a GPU — which is the entire point
of `docs/reproducibility.md`.

The alternatives were considered and rejected:

* **drop the 816 unit records (43.9 MB)** — this would remove the only per-unit proof that the
  816-unit run actually happened as described;
* **drop the plots (17.3 MB)** — the trajectory shape *is* the collapse-vs-degradation distinction;
* **Git LFS** — explicitly not used, and would require owner consent;
* **external hosting** — would make the evidence non-durable and non-clonable.

**Conclusion: the size is justified by the evidence it carries, and no artifact is present by
accident.** If the owner later wishes to reduce it, the 73 plots are the cheapest 17 MB to drop
without touching any number.
