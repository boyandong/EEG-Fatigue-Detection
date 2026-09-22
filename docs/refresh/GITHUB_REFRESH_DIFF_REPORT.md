# GITHUB_REFRESH_DIFF_REPORT.md

Diff review produced **before** pushing, comparing the public snapshot against both the local
scientific source tree and the previous remote `main`.

**Refresh branch:** `repo-refresh-20260922`
**Baseline:** `main` @ `625dc3b901bb710cd5ab377dbbb85a81517c85b1` (1 commit, 36 files)
**Remote `main` after this refresh: UNCHANGED.**

---

## 1. SCIENTIFIC RESULTS CHANGED

# **NO**

No scientific result, measurement, statistic, threshold, verdict, conclusion or algorithm changed.

The one line that requires care: **17 published files differ from their local source**, and every
one of those differences is a **path or credential string substitution**, plus **two branch
READMEs that were rewritten as documentation**. The independent content comparison below is the
evidence.

| class | files | content delta |
|---|---:|---|
| byte-identical to local source | **1,034** | none |
| edited | **17** | path/credential substitutions; 2 of them also documentation rewrites |
| new in public snapshot | **46** | new documentation + the migrated Phase-0 prototype |

**No data file, manifest, split, evidence artifact, frozen report number or verifier was
changed.** All 842 published JSON files parse, all 50 CSV files parse, and 60/60 documented
numbers were re-derived from the artifacts they claim to come from (`docs/verify_public_numbers.py`).

---

## 2. Files added

### 2.1 Documentation written for publication (10)

| path | purpose |
|---|---|
| `README.md` | complete rewrite — the repository's new definition of itself |
| `ENVIRONMENT_AUDIT.md` | dependency derivation + what is not reconstructible |
| `functional_prediction/README.md` | Branch A: negative result, endpoint validation, defect history |
| `tta_collapse/README.md` | Branch B: `CASE 4`, taxonomy, verification, parked work |
| `shared/ds004902_source_trunk/checkpoints/README.md` | checkpoint policy, naming, hash anchors, regeneration |
| `archive/legacy/ns_sd_prototype_2026/README.md` | marks the legacy prototype as superseded |
| `docs/PROJECT_HISTORY.md` | the full narrative, including both corrections |
| `docs/REPRODUCIBILITY.md` | how to check the claims, graded in three levels |
| `docs/verify_public_numbers.py` | **new verifier** — 60 checks of documented numbers vs artifacts |
| `docs/check_links.py` | **new check** — relative Markdown links must resolve |

### 2.2 Audit records (4)

`docs/refresh/GITHUB_REFRESH_INVENTORY.md`, `docs/refresh/PUBLICATION_SCOPE.md`,
`docs/refresh/GITHUB_REFRESH_DIFF_REPORT.md`, `docs/refresh/compare_to_source.py`.

### 2.3 Migrated from the previous remote (32)

The entire Phase-0 prototype, moved to `archive/legacy/ns_sd_prototype_2026/` — `baseline/`,
`feature_extracting/`, `model/`, its original Chinese READMEs, its original dependency list, and
`lstm_fatigue_best.pt`. **Content is byte-identical to remote commit `625dc3b`.**

### 2.4 Carried from the local tree into public view (~1,000)

`shared/ds004902_source_trunk/` (aperture code, configs, manifests, splits, provenance,
third-party pins, checkpoint manifest), `functional_prediction/` (src, scripts, config, tests,
specs, 6 reports, selected evidence), `tta_collapse/` (src, tests, runners, documentation,
metrics, 816 unit records, 73 plots).

---

## 3. Files moved

Moving within the *published* tree, relative to the local layout. No local file was moved or
altered — the public tree is a separate staging copy.

| local path | public path | why |
|---|---|---|
| `project/srtp/{README,AGENTS,SESSION_HANDOVER,MIGRATION_MAP}.md` | *(not published)* | internal operating docs |
| `functional_prediction/outputs/{pvt,phase2,paper_reference,manifests,dynamic_audit}` | `functional_prediction/evidence/*` | separates **published evidence** from generated output |
| `functional_prediction/docs/phase3_metadata_survey_2026.md` | `functional_prediction/` | its own relative links required the branch root |
| `tta_collapse/outputs/*.{csv,json}` | `tta_collapse/evidence/metrics/` | same separation |
| `tta_collapse/outputs/units/` | `tta_collapse/evidence/units/units/` | same |
| `tta_collapse/outputs/plots/` | `tta_collapse/evidence/plots/` | same |
| `tta_collapse/outputs/legacy_checkpoint_inventory.csv` | `shared/.../checkpoints/CHECKPOINT_MANIFEST.csv` | it is a **trunk** artifact, not a TTA artifact |
| `shared/.../third_party/{braindecode,tent,arl-eegmodels,scikit-learn}/` + archives | *(not published)* | referenced by commit pin instead |
| remote `baseline/`, `feature_extracting/`, `model/` | `archive/legacy/ns_sd_prototype_2026/` | preserve Phase 0 under a dated legacy path |

**Deliberate exception to the "keep it at the branch root" instinct:** two initial attempts put the
phase reports under a `reports/` subdirectory and the survey under `docs/`. That **broke the
original documents' own relative links** (8 broken links, caught by `docs/check_links.py`), so the
files were returned to the branch root, where their internal links resolve. Documentation
integrity won over layout tidiness.

---

## 4. Files removed from public view

Nothing was deleted from git history, and **no previously public file was destroyed** — every file
in remote `625dc3b` is either still published or migrated under `archive/legacy/`.

Files removed from the *rendered* public tree (all still exist locally):

| removed from public tree | count | reason |
|---|---:|---|
| `AGENTS.md`, `SESSION_HANDOVER.md`, `MIGRATION_MAP.md` | 3 | internal operating documents |
| `_refactor/` | 23 | decoupling execution debris |
| `tta_collapse/*.sh` (one-off server scripts, `*.sh.norm` copies) | ~30 | per-server debug scratch |
| `tta_collapse/remote_outputs/` | 25 | exact duplicate of `outputs/` |
| `functional_prediction/audit/` phase scripts | ~40 | near-duplicates; reports/specs published instead |
| `functional_prediction/pvt_audit_v1/` | 8 | superseded by `evidence/pvt/` |
| `functional_prediction/outputs/` remaining | many | superseded intermediates |
| `tta_collapse/outputs/remote_state.json` | 1 | **credential-bearing runtime state — withheld** |
| `tta_collapse/SESSION_HANDOVER_EEGTTA_PHASE1.md` | 1 | superseded by the branch README |
| `.vscode/settings.json` (from remote) | 1 | IDE-local |
| remote `README.md` | 1 | **replaced**, with the original preserved as `archive/legacy/.../_README_ORIGINAL_ZH.md` |
| remote `requirements.txt` | 1 | **replaced**, original preserved as `requirements-legacy.txt` |

---

## 5. Files modified

### 5.1 Content edits — the complete, declared set (17 files)

Every edited file was edited **only** to remove a personal identifier, a machine path, or an
execution endpoint. **No number, definition, verdict or algorithm was touched.**

| # | file | substitution | count |
|---|---|---|---:|
| 1 | `tta_collapse/evidence/metrics/KEY_FINDINGS.json` | server `host:port` label → *"owner-approved GPU server, host redacted"* | 1 |
| 2 | `tta_collapse/05_remote.py` | `<HOME>`; generic `ssh.exe`; `<SERVER_HOST>`; `PORT = 26466` → **`PORT = int(os.environ.get("EEGTTA_SSH_PORT", "0"))`**; `<key-name>` | 5 |
| 3 | `tta_collapse/SERVER_RUNBOOK.md` | `<HOME>`; `<SERVER_HOST>`; `<key-name>` | 3 |
| 4 | `tta_collapse/_sync_archived.py` | `<HOME>`; `<ENV_ROOT>` | 1 |
| 5 | `tta_collapse/README.md` | **documentation rewrite** (new branch README) | — |
| 6 | `shared/.../legacy_apparatus/BASELINES.md` | `<HOME>`; `<ENV_ROOT>` | 2 |
| 7 | `functional_prediction/README.md` | **documentation rewrite** (new branch README) | — |
| 8 | `functional_prediction/PHASE1_REPORT.md` | `<HOME>`; `<ENV_ROOT>` | 1 |
| 9 | `functional_prediction/PHASE1_5_REPORT.md` | `<HOME>`; `<ENV_ROOT>` | 1 |
| 10 | `functional_prediction/PHASE1_75_REPORT.md` | `<HOME>`; `<ENV_ROOT>` | 5 |
| 11 | `functional_prediction/PHASE2_REPORT.md` | `<HOME>`; `<ENV_ROOT>` | 3 |
| 12 | `functional_prediction/PHASE3C_BEHAVIOR_ENDPOINT_REPORT.md` | `<HOME>`; `<ENV_ROOT>` | 2 |
| 13 | `functional_prediction/scripts/00_audit_source_data.py` | `<HOME>`; `<ENV_ROOT>` | 1 |
| 14 | `functional_prediction/src/probe_eyesopen_provenance.py` | `<HOME>`; `<ENV_ROOT>` | 1 |
| 15 | `functional_prediction/src/probe_raw_recovery.py` | `<HOME>`; `<ENV_ROOT>` | 1 |
| 16 | `functional_prediction/tests/test_phase3b_scope.py` | `<HOME>`; `python` for the interpreter path | 1 |
| 17 | `functional_prediction/tests/test_phase3c_scope.py` | `<HOME>`; `python` for the interpreter path | 1 |

**Every edited `.py` file was compiled** (17 files, `py_compile`, 0 failures), and all four
data-free test suites were re-run **after** editing and still pass.

### 5.2 Documentation-only changes

`README.md`, `requirements.txt`, `.gitignore`, and the four new `docs/`/branch-README documents.
No code outside §5.1 changed.

### 5.3 A refused change, recorded on purpose

The refresh brief described the BCIT Phase 4A / 4A2 results as **INVALIDATED** by inter-block gap
contamination, and instructed that they be marked as such. **The local authoritative state says
otherwise, and the local state was followed.**

`AGENTS.md` §2, `functional_prediction/README.md` §3, `SESSION_HANDOVER.md` §2 and Phase 4A3's own
artifacts all record that Phase 4A3 **measured the impact claim and refuted it** — the defect is
real but **inert**: **0 of 82,550** defective rows appear in any training or test mask of any of
the 149 folds, and the corrected pipeline reproduces Phase 4A to **~1e-14**. The
`INVALIDATED FOR SCIENTIFIC VERDICT` status was **withdrawn**.

The README therefore documents the *entire* episode: the defect, the invalidation, its refutation,
and the standing rule that **both readings must travel together**. Publishing only the invalidation
would have been a scientific error; publishing only "clean negative" would also have been one.

`AGENTS.md` §21 of the refresh brief — *"任何数字必须从 authoritative local artifact 核验后才能写"* —
is exactly the rule that resolves this. The audit followed the artifacts.

---

## 6. Ignored large artifacts

| class | files | size | mechanism |
|---|---:|---:|---|
| BCIT Tier-1 raw payloads | 37 | 8,392 MB | never staged |
| ds004902 waveform caches (`.npy`) | 302 | 9,037 MB | never staged; `**/waveforms/`, `*.npy` |
| raw ds004902 EEG | 1,567 | 5,509 MB | never staged; `/data/` |
| legacy full-run tarball | 2 | 4,381 MB | never staged; `*.tar`, `*.tar.gz` |
| EEGNet + DeepConvNet checkpoints | 4,107 | 1,233 MB | never staged; `*.pt` |
| legacy BCIT `.cnt` | 2 | 92 MB | never staged |
| Phase-3C vehicle cache (`.npz`) | 4 | 229 MB | never staged |
| vendored third-party source | 2,175 | 34 MB | never staged |

**`.gitignore` was verified, not assumed:** after `git add -A`, **0 files** were reported ignored
and **1,097** were tracked — and the four whitelist exceptions were individually confirmed present
(`lstm_fatigue_best.pt`, `permutation_null.npz`, `segments.csv`, `sources.json`). An early draft of
the file had conflicting rules that would have silently dropped a published artifact; it was
replaced with narrow, name-based rules and re-verified.

---

## 7. Secrets scan result

| scan | scope | hits |
|---|---|---|
| API keys / OAuth / cloud (`ghp_`, `gho_`, `sk-`, `AKIA`, `AIza`, `xox`) | all 1,097 tracked files | **0 genuine** (1 regex false positive: the literal filename `task-Drive_events.json` matched the `sk-` pattern) |
| passwords / secrets / tokens in assignment form | all tracked files | **0** |
| PEM private keys, `ssh-rsa` / `ssh-ed25519` authorized-key lines | all tracked files | **0** |
| local username | all tracked files | **0 after substitution** |
| local machine paths, environment root, temp path | all tracked files | **0 after substitution** |
| server host / port / SSH key name | all tracked files | **0 after substitution** |
| credential-bearing runtime file | repository | **1 withheld** (`tta_collapse/outputs/remote_state.json`) |

**One file was withheld entirely** rather than sanitized: `remote_state.json` embedded the SSH key
path plus host/port/user. It is runtime state, not provenance, and nothing published needs it.

**The SSH password was never in the repository.** It is read from the environment variable
`EEGTTA_SSH_PASSWORD` at run time. Nothing was published and then withdrawn.

**No hard stop was triggered. No secret was found in the published set.**

---

## 8. Repository size

| metric | remote `main` @ `625dc3b` | `repo-refresh-20260922` |
|---|---:|---:|
| tracked files | 36 | **1,097** |
| working-tree size | ~2.0 MB | **~87.5 MB** |
| largest tracked file | 1.2 MB (`lstm_fatigue_best.pt`) | 3.02 MB (`tent_literal_predictions.csv`) |
| binary blobs | 4 (1 `.pt`, 3 `.csv`) | 2 classes: 1 `.pt` (1.2 MB, pre-existing) + 73 `.png` (17.3 MB) |
| Git LFS used | no | **no** |

**GitHub limits:** the largest file is 3.02 MB — far below the 100 MB hard limit and the 50 MB
warning. No single file, and no push, is near a limit. No LFS was introduced, per the refresh
constraint requiring explicit owner consent.

### Largest 15 tracked files

| bytes | path |
|---:|---|
| 3,020,701 | `tta_collapse/evidence/metrics/tent_literal_predictions.csv` |
| 2,908,132 | `tta_collapse/evidence/metrics/tent_det_predictions.csv` |
| 2,880,038 | `tta_collapse/evidence/metrics/bn_only_predictions.csv` |
| 2,851,291 | `tta_collapse/evidence/metrics/source_predictions.csv` |
| 2,752,947 | `functional_prediction/evidence/dynamic_audit/J_V_Jres_session.csv` |
| 1,794,324 | `shared/.../source_only_500hz_v1/segments_all.csv` |
| 1,741,521 | `shared/.../source_only_500hz_v1/segments.csv` |
| 1,694,800 | `tta_collapse/evidence/metrics/tent_batch_trajectory.csv` |
| 1,216,263 | `archive/legacy/.../lstm_fatigue_best.pt` |
| 1,210,485 | `functional_prediction/evidence/dynamic_audit/J_V_Jres_paired.csv` |
| 1,203,797 | `tta_collapse/evidence/metrics/target_stream_manifest.csv` |
| 940,023 | `tta_collapse/evidence/metrics/tent_parameter_drift.csv` |
| 371,389 | `tta_collapse/evidence/plots/subject_sub-01_trajectory.png` |
| 328,618 | `tta_collapse/evidence/plots/subject_sub-02_trajectory.png` |
| 321,685 | `tta_collapse/evidence/plots/subject_sub-24_trajectory.png` |

---

## 9. Verification run before commit

| check | result |
|---|---|
| every documented number vs its artifact | **60/60 PASS** (`docs/verify_public_numbers.py`) |
| relative Markdown links resolve | **21/21 PASS** (`docs/check_links.py`) |
| mechanism unit tests | **16/16 PASS** |
| nested-CV / inference unit tests | **22/22 PASS** |
| TTA synthetic smoke test | **PASS** |
| Python syntax across all published `.py` (84 files) | **0 failures** |
| JSON parse across all published `.json` (842 files) | **0 failures** |
| CSV parse across all published `.csv` (50 files) | **0 failures** |
| secrets / private keys / tokens | **0 genuine hits** |
| personal identifiers, machine paths, endpoints | **0 after substitution** |
| `.gitignore` exceptions intact | **4/4 confirmed tracked** |

**Not run — deliberately, per the refresh constraint:** no training, no TTA experiment, no BCIT
re-run, no dataset download, no regeneration of any scientific result. `tta_collapse/tests/test_p1_controls.py`
requires the ds004902 metadata and therefore cannot run from a clone; this is stated in
`docs/REPRODUCIBILITY.md` rather than worked around.

---

## 10. Commit plan

| # | message | contents |
|---|---|---|
| 1 | `refactor: align public repository with current research branches` | `shared/`, `functional_prediction/` code+specs+reports+evidence, `tta_collapse/`, `archive/legacy/` |
| 2 | `docs: update scientific status and reproducibility notes` | root/branch READMEs, `docs/PROJECT_HISTORY.md`, `docs/REPRODUCIBILITY.md`, `ENVIRONMENT_AUDIT.md`, checkpoint guide |
| 3 | `chore: harden paths, gitignore, and public environment metadata` | `.gitignore`, `requirements.txt`, sanitization of the 15 path/credential files |
| 4 | `docs: record the public-repository refresh audit` | `docs/refresh/*` |

Splits follow real semantic boundaries, not cosmetic ones. No commit mixes a code move with a
documentation rewrite.

---

## 11. Push plan

* push **only** `repo-refresh-20260922` to `origin`
* **no force**, no history rewrite, no `main` merge
* `main` remains at `625dc3b901bb710cd5ab377dbbb85a81517c85b1`
* compare URL reported after push
