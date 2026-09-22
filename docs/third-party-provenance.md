# Third-party code provenance

Audit of code retained in this repository that is **not** original to this project, performed
during the 2026-09-22 canonicalization. It exists because a repository-wide license cannot be
granted honestly until it is known which files the author actually owns.

**Bottom line: this repository currently carries NO license, and that is the correct state.**
Retained archive code appears to derive from third-party implementations whose upstream notices
were not preserved. Per-file details and required actions are below.

---

## 1. Scope and method

**Audited:** every source file under `archive/legacy/legacy_ns_sd_prototype/` (the retained Phase-0
prototype), because that is where imported architecture code lives.

**Not audited here:** the current scientific trees (`shared/`, `functional_prediction/`,
`tta_collapse/`). Those were written for this project, and their external dependencies are consumed
as **installed packages**, not vendored — see §4.

> ### Summary statement, for use anywhere else in this repository
>
> **Active research code references pinned external implementations rather than vendoring them. The
> legacy archive retains several historical third-party-derived components whose upstream provenance
> and licensing are still being audited; no repository-wide license is therefore asserted.**
>
> A blanket claim that "third-party code is referenced, not vendored" would be **false for the
> archive** and must not be used. The distinction is between the *active* trees (clean) and the
> *historical* archive (carries derivations with missing notices).

**Method:** read the retained file headers and imports; compare class and function names against
the public implementations they resemble; record exactly what the local evidence supports and mark
the rest `NEEDS VERIFICATION`. **No upstream repository was contacted and no network access was
used.** Upstream license identification below is stated as *expected/typical for that project*, not
as verified fact — that distinction is deliberate and is the whole point of this document.

---

## 2. Findings

### 2.1 `model/models/mscvit_block/mscvit.py` — **DERIVED, ATTRIBUTION MISSING**

| | |
|---|---|
| local evidence | Imports `DropPath, to_2tuple, trunc_normal_` from a local `timm_layers`. Defines `register_model` and `_cfg` **stubs** with the comment: *"Stubs to avoid importing timm (maxxvit dataclass bug on Python 3.11+)"*. Contains `Mlp`, `Block`, and MaxxViT-family layer names. |
| inference supported | This is an adaptation of a **`timm` MaxxViT-family implementation**, reworked to avoid importing `timm`. |
| expected upstream | `huggingface/pytorch-image-models` (timm) — typically **Apache-2.0**. |
| actual upstream file/commit | **NEEDS VERIFICATION** |
| modified locally? | **Yes** — timm imports replaced by stubs; block wiring adapted to 2-D EEG feature grids. |
| attribution present | **No.** No copyright header, no license notice, no source URL. |
| required action | Identify the upstream file/commit; restore the Apache-2.0 notice and `NOTICE` obligations, or remove the file from the public archive. |

### 2.2 `model/models/mscvit_block/timm_layers.py` — **DERIVED, SELF-DECLARED**

| | |
|---|---|
| local evidence | Module docstring states verbatim: *"Local implementations of DropPath, to_2tuple, trunc_normal_ to avoid importing timm (which triggers maxxvit dataclass bug on Python 3.11+)."* Contains `_no_grad_trunc_normal_`, the truncated-normal initialiser associated with timm/BEiT. |
| inference supported | **Self-declared derivative of timm utilities.** The file itself names the upstream. |
| expected upstream | timm — typically **Apache-2.0**; `trunc_normal_` itself traces to earlier BEiT/PyTorch sources. |
| actual upstream file/commit | **NEEDS VERIFICATION** |
| modified locally? | **Yes** — reimplemented rather than imported. |
| attribution present | **Partial**: it names timm in prose but carries no copyright line and no license text. |
| required action | This is the clearest case and the easiest to fix. Add the upstream copyright and Apache-2.0 notice, or replace with a `timm` import. |

### 2.3 `model/models/mscvit_block/wtconv/` — **DERIVED, ATTRIBUTION MISSING**

Files: `wtconv2d.py`, `util/wavelet.py`, `__init__.py`, `util/__init__.py`.

| | |
|---|---|
| local evidence | Defines `WTConv2d` (parameters `wt_levels`, `wt_type`) and `create_wavelet_filter(wave, in_size, out_size, type)`; uses `pywt` wavelet decomposition filters expanded into fixed convolution kernels. These names and signatures match the published **WTConv** reference implementation for the paper *"Wavelet Convolutions for Large Receptive Fields"* (Finder et al.). |
| inference supported | Straightforward port of the WTConv reference implementation. |
| expected upstream | the WTConv authors' repository — typically **Apache-2.0**. |
| actual upstream file/commit | **NEEDS VERIFICATION** |
| modified locally? | **Likely minor** (import paths); not established. |
| attribution present | **No.** No header of any kind. |
| required action | Same as §2.1. Until resolved, treat as **not licensed for redistribution by this project**. |

### 2.4 `model/models/eeg_model.py` — **ORIGINAL, but carries an unattributed design reference**

| | |
|---|---|
| local evidence | Docstring: *"EEG model: attention -> MSCViT -> TCN -> FC. Ref: AGL-Net (driver fatigue)."* |
| assessment | The **file appears original** — it composes locally defined blocks. But it names an external architecture as a design reference and provides **no citation** (no authors, venue, year, or link). |
| required action | Add a full citation for AGL-Net. Citing an architecture is not a licensing obligation, but the current reference is unverifiable as written. |

### 2.5 `model/models/attention_block.py`, `model/models/tcn_Block.py` — **ORIGINAL (no third-party basis found)**

| | |
|---|---|
| local evidence | Original docstrings (*"Frequency and spatial attention blocks for EEG features"*, *"TCN blocks: causal conv, temporal attention, multi-scale branches"*). Contains standard, widely-reimplemented building blocks (`Chomp1d`, `LayerNorm1d`, dilated causal convolutions) that appear in many TCN codebases. |
| assessment | Consistent with original composition of well-known primitives. **No copied header or verbatim upstream marker found.** |
| residual risk | The primitives are near-universal in form, so independent re-derivation and copying are hard to distinguish. Marked **LOW RISK**, not "verified original". |

### 2.6 `baseline/`, `feature_extracting/` — **ORIGINAL**

LSTM/EEGNet training scripts, feature extraction, channel mapping, and metadata. No third-party code
markers. These call `braindecode` / `mne` / `torch` as ordinary installed dependencies.

---

## 3. Summary table

| file | status | attribution present | upstream license | action |
|---|---|---|---|---|
| `mscvit_block/mscvit.py` | DERIVED | **no** | likely Apache-2.0 (timm) | **NEEDS VERIFICATION** |
| `mscvit_block/timm_layers.py` | DERIVED (self-declared) | partial | likely Apache-2.0 (timm) | **NEEDS VERIFICATION** |
| `mscvit_block/wtconv/wtconv2d.py` | DERIVED | **no** | likely Apache-2.0 | **NEEDS VERIFICATION** |
| `mscvit_block/wtconv/util/wavelet.py` | DERIVED | **no** | likely Apache-2.0 | **NEEDS VERIFICATION** |
| `mscvit_block/wtconv/__init__.py` | trivial | n/a | n/a | none |
| `mscvit_block/wtconv/util/__init__.py` | empty | n/a | n/a | none |
| `models/eeg_model.py` | ORIGINAL + design ref | reference uncited | n/a | add AGL-Net citation |
| `models/attention_block.py` | ORIGINAL (low risk) | n/a | n/a | none |
| `models/tcn_Block.py` | ORIGINAL (low risk) | n/a | n/a | none |
| `baseline/*`, `feature_extracting/*` | ORIGINAL | n/a | n/a | none |

---

## 4. Current trees — no vendored third-party code

`shared/`, `functional_prediction/` and `tta_collapse/` contain **no vendored third-party source**.
External code is consumed as ordinary installed dependencies, whose versions and hashes are pinned
in `shared/ds004902_source_trunk/third_party/sources.json`:

| dependency | pin | consumed as |
|---|---|---|
| braindecode | 1.3.2 | installed package (supplies `EEGNet`) |
| scikit-learn | 1.7.2 | installed package |
| arl-eegmodels | commit `4a512e50…` | pin only, hash recorded |
| TENT (official reference) | commit `e9e926a6…`, core source SHA-256 `d854e1f6…` | **cited and hash-pinned, not copied** |

An earlier draft of this repository's public tree considered vendoring this third-party source
(2,175 files, 34 MB). It was **excluded**, which is why this section is short: referencing a pinned
dependency carries no redistribution obligation, whereas vendoring does.

---

## 5. License decision

**No repository-wide license is granted.**

The reasoning, stated plainly:

1. A license is granted by a copyright holder over works they hold copyright in. Four retained
   archive files appear to be derivatives of third-party implementations whose notices were not
   preserved, so their copyright status is not this project's to license.
2. Adding MIT/Apache-2.0/GPL over the whole repository would therefore **over-claim**.
3. The upstream licenses are *probably* permissive, but "probably permissive" is not a basis for
   asserting a license over someone else's code. That question needs the upstream files, not an
   assumption.

**Resolution paths, in order of preference:**

* **A. Verify and attribute.** Identify the exact upstream files/commits, restore their notices, and
  add a `THIRD_PARTY_NOTICES.md`. This likely preserves the archive intact — Apache-2.0 only
  requires notice retention, not removal.
* **B. Scope the license.** Grant a license over this project's own code and explicitly exclude
  `archive/legacy/legacy_ns_sd_prototype/model/models/mscvit_block/` from the grant. Requires a
  clear per-directory notice so the exclusion is unambiguous.
* **C. Remove the affected files** from the public head, keeping the hash and a note in the archive
  README. This is the most conservative and costs the least: the affected files are superseded
  prototype code that no current scientific result depends on.

Until one is chosen, the repository states that no license is granted.

### 5.1 Owner decision recorded 2026-09-22: the files stay

The unresolved legacy third-party-derived files are **retained in place, not deleted**. The reasoning,
which is worth keeping because it will be questioned again:

* they are **historical artifacts** — deleting them from the current tree would *not* remove them
  from the repository's Git history, so the licensing question survives the deletion anyway;
* their **scientific role is negligible**, but **provenance preservation currently matters more than
  superficial cleanup**. A public repository that quietly dropped inconvenient files would be a worse
  artifact than one that keeps them and states the problem;
* **no attribution has been invented.** Nothing has been added to these files that cannot be
  verified.

They remain under `archive/legacy/legacy_ns_sd_prototype/`, marked in the archive README, and this
document is the standing record of their unresolved status.

**Consequence for anyone reading the repository:** the legacy archive is published *for provenance*,
not as a reusable code asset. If you intend to reuse anything under
`archive/legacy/legacy_ns_sd_prototype/model/models/mscvit_block/`, resolve its upstream provenance
yourself first.

---

## 6. What this audit deliberately does not claim

* It does **not** assert what any upstream license is. Every such statement above is marked as
  expected, not verified.
* It does **not** assert that unmarked files are original. §2.5 is marked low-risk, not verified.
* It does **not** conclude that the archive must be deleted. The affected code is superseded and no
  current result depends on it, so the cheapest correct fix may well be path A.
