# Tracked file size audit

Performed 2026-09-22 immediately before pushing `repo-refresh-v2-20260922`. The purpose is to
confirm that nothing large is present by accident — no raw data, no waveform cache, no redundant
checkpoint, no generated output that slipped past `.gitignore`.

**Result: clean. No unexpected large artifact found. No blocker.**

**Git LFS is not used**, and no LFS pointer is committed.

---

## 1. Totals

**Regenerated 2026-09-22 from the git tree of `e9222e3` (blob sizes), replacing an earlier revision
that was measured from the working tree before the final commit.**

| metric | value |
|---|---:|
| ref | `e9222e3d32470811da70cd7734db41c61bdbee4b` |
| tracked files | **1,155** |
| tracked bytes | **92,172,769** |
| tracked size | **87.903 MiB** (92.17 MB decimal) |
| largest single file | **2,992,530 bytes (2.85 MiB)** |
| files over 3 MiB | **0** |
| files over 2 MiB | 5 |
| files over 1 MiB | 11 |
| binary blobs | 75 (1 `.pt`, 1 `.npz`, 73 `.png`) |

For reference, GitHub's hard limit is 100 MB per file and its warning threshold is 50 MB. **No file
is within 30× of the hard limit**, and no push approaches a pack-size limit.

> ### This audit describes the commit it names, not the current tip
>
> The tree has since grown by exactly **one** file: `docs/refresh/generate_size_audit.py`, added by
> the follow-up commit that regenerated this document, at **13,450 bytes**. Current branch tip
> (`cb8dd75`) is therefore **1,156 files / 92,186,219 bytes / 87.916 MiB** — one script more than
> the table above, and otherwise identical. Re-run the generator to confirm either state rather than
> trusting this note.
>
> The total growth over the originally reviewed `e9222e3` is **1.3 %**, and it is entirely the
> additions in the follow-up commit: this generator, the secret scanner, the dangling-reference
> repair script, the review addendum, and seven Phase-3C endpoint artifacts.

> **Unit and method note.** Sizes are **blob** sizes read from `git ls-tree -r -l`, i.e. what the
> repository actually stores. They are deliberately **not** working-tree sizes: this checkout runs
> under `core.autocrlf=true`, so every text file is CRLF-expanded on disk and a working-tree sum
> overstates each file by its line count. The earlier revision of this document mixed the two, which
> is why its byte total matched neither commit. Regenerate with:
>
> ```bash
> python docs/refresh/generate_size_audit.py e9222e3    # this audit's ref
> python docs/refresh/generate_size_audit.py HEAD       # current tip
> ```
>
> MiB = 1048576 bytes is used throughout, matching `git`'s reporting.

---

## 2. Distribution by category

| category | files | size | assessment |
|---|---:|---:|---|
| `tta_collapse/` | 941 | **76.68 MiB** | dominated by the executed run's evidence (see §3) |
| `functional_prediction/` | 130 | 5.50 MiB | code + specs + evidence |
| `shared/` | 25 | 3.74 MiB | canonical manifests and splits — required |
| `archive/` | 36 | 1.77 MiB | the byte-preserved legacy prototype |
| `docs/` | 20 | 0.20 MiB | documentation |
| root files | 3 | 0.02 MiB | `README.md`, `requirements.txt`, `.gitignore` |

### Breakdown of the large trees

| path | files | size | what it is |
|---|---:|---:|---|
| `tta_collapse/evidence/units/` | 816 | **43.88 MiB** | one JSON record per executed unit |
| `tta_collapse/evidence/plots/` | 73 | **17.27 MiB** | per-subject trajectory plots |
| `tta_collapse/evidence/metrics/` | 24 | 15.03 MiB | per-window predictions + aggregate metrics |
| `functional_prediction/evidence/dynamic_audit/` | 8 | 3.79 MiB | Phase 1.75 dynamic statistics |

---

## 3. Top 25 tracked files, with justification

| # | bytes | path | category | scientifically justified? | suspicious? |
|---:|---:|---|---|---|---|
| 1 | 2,992,530 | `tta_collapse/evidence/metrics/tent_literal_predictions.csv` | per-window predictions | **yes** — lets a reviewer recompute every TENT_LITERAL statistic independently | no |
| 2 | 2,879,961 | `tta_collapse/evidence/metrics/tent_det_predictions.csv` | per-window predictions | **yes** — the diagnostic control arm | no |
| 3 | 2,851,867 | `tta_collapse/evidence/metrics/bn_only_predictions.csv` | per-window predictions | **yes** — the gradient-free control that carries the verdict | no |
| 4 | 2,823,120 | `tta_collapse/evidence/metrics/source_predictions.csv` | per-window predictions | **yes** — the frozen-source reference arm | no |
| 5 | 2,745,419 | `functional_prediction/evidence/dynamic_audit/J_V_Jres_session.csv` | Phase 1.75 session statistics | **yes** — the dynamic-extension negative rests on it | no |
| 6 | 1,784,689 | `shared/.../source_only_500hz_v1/segments_all.csv` | **pre-exclusion manifest** | **yes** — see §4; this is *not* a duplicate | no |
| 7 | 1,732,130 | `shared/.../source_only_500hz_v1/segments.csv` | canonical manifest | **yes** — anchor hash `5eba619f…`; defines the 9,390 windows | no |
| 8 | 1,690,179 | `tta_collapse/evidence/metrics/tent_batch_trajectory.csv` | per-batch trajectory | **yes** — the collapse-trajectory evidence | no |
| 9 | 1,216,263 | `archive/legacy/legacy_ns_sd_prototype/feature_extracting/feature_data/lstm_fatigue_best.pt` | **legacy binary** | **yes, as history** — see §5 | intentional |
| 10 | 1,206,854 | `functional_prediction/evidence/dynamic_audit/J_V_Jres_paired.csv` | Phase 1.75 paired statistics | **yes** | no |
| 11 | 1,194,406 | `tta_collapse/evidence/metrics/target_stream_manifest.csv` | target stream definition | **yes** — defines the adapted stream order | no |
| 12 | 937,712 | `tta_collapse/evidence/metrics/tent_parameter_drift.csv` | BN affine drift | **yes** — the normalization-drift measurement | no |
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

## 5. The tracked binaries

`archive/legacy/legacy_ns_sd_prototype/feature_extracting/feature_data/lstm_fatigue_best.pt` — **1,216,263 bytes (1.16 MiB)**.

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

The other 74 binaries are the TTA run's trajectory plots (73 `.png`, 17.27 MiB) plus one small
`.npz` evidence array (`functional_prediction/evidence/phase2/permutation_null.npz`, 0.04 MiB) — the
visual and numerical record behind the `CASE 4` verdict and the Phase 2 permutation null.

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
| Any tracked file over 3 MiB? | **no** — largest is 2.85 MiB (`tent_literal_predictions.csv`) |
| Any Git LFS pointer? | **no** |

---

## 7. Honest note on the total

**87.90 MiB is not small for a research repository, and it was not accepted automatically.** The
growth over `main` (≈2 MB) is almost entirely *evidence*: 816 executed-unit records, four arms of
per-window predictions, and the trajectory plots. That evidence is what allows an external reviewer
to recompute the published verdict without acquiring a dataset or a GPU — which is the entire point
of `docs/reproducibility.md`.

The alternatives were considered and rejected:

* **drop the 816 unit records (43.88 MiB)** — this would remove the only per-unit proof that the
  816-unit run actually happened as described;
* **drop the plots (17.27 MiB)** — the trajectory shape *is* the collapse-vs-degradation distinction;
* **Git LFS** — explicitly not used, and would require owner consent;
* **external hosting** — would make the evidence non-durable and non-clonable.

**Conclusion: the size is justified by the evidence it carries, and no artifact is present by
accident.** If the owner later wishes to reduce it, the 73 plots are the cheapest 17 MB to drop
without touching any number.
