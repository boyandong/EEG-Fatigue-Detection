# REMAINING_MANUAL_GITHUB_ACTIONS.md

Actions the repository owner must perform **in the GitHub web UI**. An automated agent cannot and
must not do these: they change remote repository identity and settings, they are visible to anyone
who has the old URL, and two of them are effectively irreversible.

**Status of the repository at the time of writing:** `main` still carries the original Phase-0
prototype. The canonicalized state lives on local branch `repo-refresh-v2-20260922` and has **not**
been pushed.

---

## 1. Review and adopt the branch (do this first)

Nothing below matters until the canonicalized content is on `main`.

| step | action |
|---|---|
| 1.1 | Review local branch `repo-refresh-v2-20260922` against `repo-refresh-20260922` — the delta is exactly the corrected TTA status, the corrected BCIT status, and the new `docs/`. |
| 1.2 | Decide whether `repo-refresh-20260922` (first refresh snapshot) should be kept, merged, or deleted. **Recommendation: keep it** as an auditable intermediate. |
| 1.3 | Open a pull request from `repo-refresh-v2-20260922` to `main`, or push it and merge. |
| 1.4 | Verify `main` afterwards: `README.md` H1 reads **EEG Vigilance Reliability**, and top-level `baseline/`, `feature_extracting/`, `model/`, `备忘录.md`, `.vscode/` are **gone** (migrated under `archive/legacy/legacy_ns_sd_prototype/`). |

> **Note on branch ancestry.** `repo-refresh-20260922` is an independent root history — it shares no
> common ancestor with `main`. A normal PR from it therefore **cannot** be opened; a merge with
> `--allow-unrelated-histories` would be required. `repo-refresh-v2-20260922` inherits that ancestry.
> If GitHub refuses the PR, the cleanest resolution is a fresh branch based on `main` carrying the
> v2 tree — ask before doing this, since it changes commit identity.

---

## 2. Rename the repository

| | |
|---|---|
| current | `EEG-Fatigue-Detection` |
| recommended | `eeg-vigilance-reliability` |

**Why the current name is now inaccurate.** Three separate problems:

* **`Fatigue`** is narrower than the project. The project is about vigilance, objective functional
  performance, sleep deprivation, cross-subject generalization, and adaptation stability.
* **`Detection`** implies a working detector exists. The project's most important results include
  the opposite: functional prediction is **not** established.
* The project is no longer a **single-model** repository; it is a two-branch research program.

**Where to change it:** Settings → General → Repository name.

**GitHub keeps a redirect from the old URL**, so existing links do not break immediately — but a
redirect is not permanent, especially if anyone later creates a repository with the old name.

### After renaming

```powershell
git remote set-url origin https://github.com/boyandong/eeg-vigilance-reliability.git
```

**Do not run this before the rename is complete** — it will break `git push`/`fetch` until the new
name exists.

**Also re-check** (a scan of this repository found no dependency on the slug in code, so these are
documentation-level): README links and badges, clone instructions in `docs/`, any external
references you control (CV, application materials, slides), and CI workflow paths if any are added
later.

---

## 3. Set the repository description

Settings → General → Description:

```text
Cross-subject EEG research on functional vigilance and test-time adaptation, with explicit negative and corrective evidence.
```

## 4. Add topics

Settings → General → Topics. Exactly six, no more:

```text
eeg
biosignal-processing
vigilance
test-time-adaptation
cross-subject-learning
reproducible-research
```

**Do not add `fatigue-detection`.** It mis-describes the project and would attract exactly the
wrong reader — someone looking for a fatigue classifier rather than a reliability study.

## 5. License — DO NOT SET ONE YET

**Leave the license unset.** This is a deliberate recommendation, not an oversight.

Four files in the retained archive (`mscvit_block/mscvit.py`, `mscvit_block/timm_layers.py`,
`mscvit_block/wtconv/wtconv2d.py`, `mscvit_block/wtconv/util/wavelet.py`) appear to derive from
third-party implementations whose notices were not preserved. Granting a repository-wide license
would therefore **over-claim** — asserting rights over code whose copyright is not this project's
to license.

Full analysis and three resolution paths:
[`../third-party-provenance.md`](../third-party-provenance.md).

**Short version of the options:** (A) verify upstream files and restore notices — likely keeps the
archive intact, since permissive licenses require notice retention rather than removal; (B) scope a
license to this project's own code and explicitly exclude the `mscvit_block/` directory;
(C) remove those four files from the public head, keeping their hashes in the archive README.

Option C is the cheapest and costs nothing scientifically — the affected files are superseded
prototype code that no current result depends on.

## 6. Optional, worth considering

| item | why |
|---|---|
| **Disable the Wiki** | unused; an empty wiki reads as an abandoned repository |
| **Set the default branch** | once `main` carries the canonical state, confirm `main` is default |
| **Enable branch protection on `main`** | prevents a future accidental force-push to the public head |
| **Pin the repository** | if you want it visible on your profile as a research project |
| **Social preview image** | optional; the README's first screen is already the intended signal |

## 7. What must NOT be done from GitHub's UI

| action | why not |
|---|---|
| Deleting `repo-refresh-20260922` without review | it is the only snapshot of the first refresh; review it first |
| Force-pushing over `main` from the UI or CLI | `main` is the public history; the canonicalization is additive |
| Uploading datasets or checkpoints via the web UI | bypasses `.gitignore` and the data-boundary policy — see [`../data-boundaries.md`](../data-boundaries.md) |
| Adding a license before §5 is resolved | over-claims rights over third-party-derived code |

---

## 8. Verification checklist after the manual actions

```bash
git fetch origin
git rev-parse origin/main                  # expect the merged v2 commit
git ls-tree -r --name-only origin/main | grep -E '^(baseline|model|feature_extracting)/'   # expect NO output
git ls-tree -r --name-only origin/main | grep -c .                                          # record the file count
```

Then confirm on the repository home page:

- [ ] H1 reads **EEG Vigilance Reliability**
- [ ] description matches §3
- [ ] topics match §4 and **`fatigue-detection` is absent**
- [ ] license badge reads **not assigned** (no license file)
- [ ] `docs/`, `archive/legacy/legacy_ns_sd_prototype/`, `shared/`, `functional_prediction/`, `tta_collapse/` all present
- [ ] no `备忘录.md`, no `.vscode/`, no top-level `baseline/` · `model/` · `feature_extracting/`
