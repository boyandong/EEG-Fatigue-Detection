# Phase 3 — Metadata-only candidate dataset survey (web research, no downloads)

Scope: detect from short scalp EEG whether a NEW user's objective performance declined vs. THAT USER's
own alert baseline. Criteria: (a) within-person alert + degraded, (b) OBJECTIVE endpoint, (c) EEG
time-linked to behaviour, (d) ~80+ independent subjects, (e) downloadable EEG bytes.

All facts below are metadata/web evidence only. Nothing was downloaded or executed. No EEG file was opened.

---

## 1. SEED-VIG — priority 1

- **ID / access**: no DOI on the source page. Distributed via license application.
  https://bcmi.sjtu.edu.cn/home/seed/seed-vig.html · license agreement:
  https://bcmi.sjtu.edu.cn/home/seed/resource/license/SEED-VIG%20license.pdf
- **N = 23** (VERIFIED). Zheng & Lu, *J. Neural Eng.* 14(2):026017 (2017). One session per person, so
  effective N = nominal N = 23. No repeated-person inflation.
- **(a) Personal alert baseline — NO.** VERIFIED, from the source page: "Most experiments were performed
  in the early afternoon after lunch to easily induce fatigue when the circadian rhythm of sleepiness
  reached its peak. The duration of the entire experiment was approximately 2 h." There is one monotonous
  drive; alertness is not manipulated. Within-session drift only.
- **(b) Endpoint — DATA-DERIVED, not a task measure.** VERIFIED: "We then calculated the PERCLOS indicator
  values of the participants during the experiment and used them as vigilance labels." PERCLOS comes from
  SMI eye-tracking glasses, not from driving performance. No lane deviation / steering error / RT.
- **(c) Time-linking — YES, at 1 Hz.** Labels are continuous 0–1 at 885 samples per recording; EEG features
  epoch-aligned. Good temporal resolution.
- **(d) N = 23.** Well below the ~80 target.
- **(e) Raw EEG bytes — NO.** VERIFIED, the released dataset is feature tensors only: PSD/DE at 2 Hz
  resolution (17×885×25) and 5 bands (17×885×5), forehead EEG (4×885×25, 4×885×5), EOG features
  (885×36), and PERCLOS labels. Raw EEG is not part of the public release. This alone breaks (e).
- EEG acquisition was 17 channels (Neuroscan) at 1000 Hz per the BCMI feature channels /
  per secondary reporting; **exact acquisition sample rate = INFERRED** (the 885 figure is samples, not Hz).
- **Verdict**: fails (a), (b), (d), (e). *Attractive but rejects.*

## 2. DROZY — priority 2, strongest overall fit

- **ID**: "The ULg Multimodality Drowsiness Database (called DROZY)", WACV 2016,
  DOI 10.1109/WACV.2016.7477715. https://orbi.uliege.be/handle/2268/191620 (DOI-bearing landing page; the
  http://www.drozy.ulg.ac.be project page did not resolve at survey time).
- **N = 14** (VERIFIED): "Fourteen healthy subjects/participants (3 males, 11 females), aged 22.7 ± 2.3".
  Repeated measures: 3 PVTs per person → 42 sessions. Effective independent N = 14.
- **(a) Personal alert baseline — YES, the best in this survey.** VERIFIED: "called for each subject to
  take three PVTs over two consecutive days, under conditions of increasing sleep deprivation induced by
  acute, prolonged waking"; "Each was asked to maintain a normal sleep pattern for the week prior … and to
  have a full night sleep (of 7 to 8 hours at least) just before this PVT"; "Once a participant took the
  first PVT, he/she was not allowed to sleep until after the third PVT, resulting in a total sleep
  deprivation of 28 to 30 hours." PVT1 ≈ 10:00–11:00 (rested), PVT2 ≈ 03:30–04:00, PVT3 ≈ 12:00–12:30.
- **(b) Endpoint — OBJECTIVE, per trial.** VERIFIED: "PVT: stimulus times and corresponding RTs"; the
  database contains "KSS: the self-reported LoD … just before taking the PVT" (subjective present but not
  the only label). Lapses defined as RT ≥ 500 ms. Per-trial resolution (best possible).
- **(c) Time-linking — YES, and the paper states synchrony explicitly**: "perfectly time-synchronized data
  for each of the 14 subjects, and for each of the three PVTs". Caveat INFERRED: PSG and PVT are separately
  recorded; the synchrony claim is the authors', not independently verified here.
- **EEG (VERIFIED)**: "the portable, laboratory Embla Titanium system to record the Fz, Pz, Cz, C3, and C4
  EEG channels (referenced to A1, in the international 10-20 system), the horizontal and vertical EOG
  channels, the EMG, and the ECG, all sampled at 512 Hz." 5 EEG channels only.
- **(d) N = 14.** Fails the ~80 target badly.
- **(e) Downloadable — YES.** A 2.46 GB `DROZY.zip` is published as an annex on the ORBi record
  (https://orbi.uliege.be/bitstream/2268/191620/4/DROZY.zip), alongside a license-agreement PDF
  (https://orbi.uliege.be/bitstream/2268/191620/5/DROZY-LicenseAgreement-20180718.pdf). Licence terms were
  NOT read as text (PDF fetch returned `unsupported content type`) → licence text = UNKNOWN.
- **Blockers**: N = 14 (fatal for an 80-subject out-of-sample claim); 5 EEG channels; **no driving task at
  all** — the only "driving simulator" mention in the WACV paper is reference [7]; the word "simulator"
  appears once and only in the bibliography. So DROZY is a PVT dataset, not a driving dataset.
- **Within-person variability**: per-subject means by condition are NOT reported in the WACV paper
  (only aggregate modelling results: RMSE 106 ms, r = 0.67). Variability = UNKNOWN from source.

## 3. Sleep deprivation + objective performance

- **ds004902** (already known): **NEW finding — nominal N is 71, not 29.** README: "resting-state EEG data
  (eyes open, partially eyes closed) from 71 participants who underwent two experiments involving normal
  sleep (NS---session1) and sleep deprivation (SD---session2)"; counterbalanced, so it is a genuine
  within-person alert/deprived contrast. participants.tsv carries per-session PVT values
  (`PVT_item1/2/3_NS`, `PVT_item1/2/3_SD`) but they are empty (`n/a`) for several subjects — e.g. sub-01 has
  all `n/a`. EEG 61 electrodes, Brain Products, 500 Hz, CC0, DOI 10.18112/openneuro.ds004902.v1.0.8.
  Resting-state EEG is NOT behaviour-locked (breaks (c)).
- **ds007509 "1hrPVTdataset_allSubjects" — REJECT, deceptive.** 69 subjects (VERIFIED by directory
  listing sub-S010…sub-S087 plus 3 gaps; 70 lines incl. header; NEMAR lists 69), 24 FortyHz / 24 Random /
  21 Light, BioSemi ActiveTwo 32 ch, 512 Hz, ~3109 s per session, CC0, 12–14.8 GB, directly downloadable.
  But: `task-PVT_events.json` declares a `response_time` field while the actual `events.tsv` header is
  `onset duration sample value trial_type` in every subject checked (sub-S010, S011, S030, S050, S087) and
  marker values are only stimulus codes (2, 22). **No RT is present** → no objective endpoint. Fails (b).
- **Drivers Drowsiness Database (DD-Database)**: Dryad DOI 10.5061/dryad.5tb2rbp9c, published 2023-08-25,
  260.04 MB, CC0-ish Dryad terms; 10 subjects (files 01M…10M), 2 trials each of 2 h = 40 h, 4 EEG + 2 EOG +
  1 ECG channels, `.edf` plus `*_annotations.edf`. Abstract: "under a protocol designed to induce
  drowsiness. The annotation files have the time marks of subject´s drowsiness events." Endpoint nature
  (event marks vs. objective behaviour) = UNKNOWN — the README could not be read (403 on
  https://datadryad.org/downloads/file_stream/2523075), so `.edf` contents were not inspected. Judged
  **N=10 + UNKNOWN endpoint → not viable**, but cheap to check.
- **MPD-DF**: Sci Data, DOI 10.1038/s41597-026-06634-4, PMC12929719; raw + preprocessed on figshare
  (article 28455737), code https://github.com/ljyTota/MPD-DF.git. N = 50, 2 h simulated driving, LiveAmp
  32 ch EEG at 500 Hz (raw `.edf`, mean 227.60 MB/subject, 11.1 GB total). Endpoint is **physician
  annotation**, 30-s segments at raw level, 1-s in the preprocessed `.mat` — labels Wakefulness/Fatigue1-4;
  there is NO behavioural performance endpoint. Table 1 lists its own fatigue label as "Physician
  annotations based on EEG". Also: protocol excludes sleep-deprived subjects (requires ≥7 h sleep the night
  before). Fails (a), (b).
- **SADT (nm000275)** known: NEMAR copy 27 participants / 62 sessions, 36.4 GB, CC-BY-4.0, DOI
  10.82901/nemar.nm000275; 32 ch (30 scalp + 2 mastoid), 500 Hz, Neuroscan SynAmps2; 27,000+ lane-departure
  trials. Table 1 in PMC12929719 confirms “Sleep Deprivation: No” and “Fatigue Label: Reaction time”.

## 4. PhysioNet / OpenNeuro with EEG + objective behaviour

- **PhysioNet drivedb — HARD REJECT.** https://physionet.org/content/drivedb/1.0.0/ , DOI
  10.13026/C2SG6B, 108.7 MB, ODC-By 1.0. Abstract: signals are "ECG, EMG (right trapezius), GSR … and
  respiration" — **no EEG**. Also "The stress ratings from the study are not available."
- **BCIT family — the N is real here.** All CC0, raw BioSemi 64 (+8) ch at 2048 Hz, vehicle log at 100 Hz,
  perturbation-locked RTs. Each README states the same design sentence: algorithms are validated "in
  comparison to the objective performance measures, and in contrast with the (non-fatigued) Calibration
  driving session for the subject." Calibration = "a 15-minute drive where the subject controlled only the
  steering".
  - **ds004105 BCIT Auditory Cueing — N = 17** (NEMAR), 20.4/21.2 GB, task DriveRandomSound. NOT previously audited.
  - **ds004121 BCIT Mind Wandering — N = 21**, 23.9 GB. NOT previously audited.
  - **ds004122 BCIT Speed Control — N = 32**, 36.2 GB. NOT previously audited. README: "This dataset has a
    corresponding dataset in the BCIT Calibration Driving ds004118 which has the 15 minute driving task
    performed prior to this one." → calibration is a SEPARATE dataset, i.e. cross-dataset pairing needed
    (UNKNOWN: whether the calibration run is also inside ds004122 itself).
  - **ds004123 BCIT Traffic Complexity — N = 29**, 17.5 GB. NOT previously audited.
  - Known: ds004118 (calibration, N = 156) and ds004120 (baseline driving, N = 109, 302 GB).
  - Dependent variables, verbatim: "Reaction times to perturbations, continuous performance based on
    vehicle log (steering wheel angle, lane position, heading error, etc.), reaction times to target
    vehicles (police), Task-Induced Fatigue Scale (TIFS), Karolinska Sleepiness Scale (KSS), Visual Analog
    Scale of Fatigue (VAS-F)." → objective endpoint VERIFIED; subjective scales available only ON REQUEST
    from cancta.net.
  - **No sleep deprivation anywhere in the BCIT protocols (verified from READMEs).** Degradation is
    time-on-task fatigue within a session.
- **OpenNeuro catalogue sweep**: GraphQL `search` returns `null` and `DatasetFilter` has no text fields, so
  the full catalogue (1,889 datasets) was pulled via `datasets(first:100, after:)` and filtered by title —
  names only, no abstracts. Titles matching sleep/fatigue/drowsy/vigil/driv/attention/PVT were reviewed.
  Non-viable also-rans: ds005416 (N=23, mixed-reality stereo fatigue, resting + movement scenes, no
  objective endpoint), ds004219 Litebook Alertness (only 10 named subjects, adolescent cohort),
  ds005555 Bitbrain sleep (128 nights, sleep staging, no performance task), ds006695 / ds005207 / ds005185 /
  ds005178 (sleep staging), ds006040 gradCPT (N=28, sustained attention but no alert/deprived contrast).

## Ranking by number of requirements (a)-(e) met (factual, not scored)

1. **DROZY** — (a) yes, (b) yes per-trial, (c) yes (authors' synchrony claim), (d) NO (N=14), (e) yes
   (2.46 GB zip). 4/5. Blocked only by N and by having no driving task.
2. **BCIT ds004105 / ds004121 / ds004122 / ds004123** — (a) yes but as a separate calibration session,
   (b) yes, (c) yes (perturbation-locked), (d) yes individually (17/21/32/29) and yes if pooled with
   ds004118 + ds004120, (e) yes (raw, CC0). 5/5 if cross-dataset calibration pairing is acceptable to the PI.
3. **ds004902** — (a) yes (genuine NS vs SD), (b) partial (session-level PVT, many cells empty),
   (c) NO (resting state), (d) nominal 71 / effective ~29, (e) yes. 3/5.
4. **SEED-VIG** — (a) NO, (b) no (PERCLOS-derived), (c) yes at 1 Hz, (d) NO (23), (e) NO (features only). 1/5.
5. **MPD-DF** — (a) partially (within-session Wakefulness→Fatigue), (b) NO (physician label), (c) yes 1 s,
   (d) NO (50), (e) yes. 3/5 but the wrong endpoint.
6. **drivedb / ds007509** — reject.

## Explicitly attractive-but-failing

- SEED-VIG: benchmark-grade, widely used, 1 Hz vigilance labels — but no alert condition, no objective
  task measure, N=23, and **no raw EEG in the release**.
- ds007509: 69 subjects, CC0, 12 GB, PVT in the title — but **no RT column actually present**.
- drivedb: the obvious PhysioNet "driving" answer — **contains no EEG at all**.
- MPD-DF: 50 subjects, raw EDF, physician labels — endpoint is not behaviour.

## Open items (blocking precision, not the conclusion)

- SEED-VIG licence terms and whether raw EEG is obtainable on request — UNKNOWN.
- DROZY licence text — UNKNOWN (PDF not machine-readable via the fetch tool used).
- DD-Database annotation semantics (event marks vs. scored behaviour) — UNKNOWN.
- Whether ds004122/4121/4123/4105 each ship their own calibration run, or only ds004118 does — UNKNOWN.
- Whether BCIT ds004118/ds004120 subjects overlap (same person in calibration and task) — UNKNOWN; needed
  before any pooled subject count is quoted.

## Search queries used

SEED-VIG dataset EEG vigilance driving simulator download · DROZY dataset University of Liege sleep
deprivation EEG PVT Karolinska · PhysioNet drivedb stress recognition automobile drivers dataset ·
OpenNeuro sleep deprivation EEG psychomotor vigilance task dataset · EEG driver fatigue dataset OpenNeuro
lane departure objective performance · NEMAR EEG driving dataset fatigue · sleep deprivation driving
simulator EEG dataset public download · PhysioNet sleep deprivation EEG dataset · SEED-VIG 23 subjects
PERCLOS 885Hz download license bcmi · DROZY database sleep deprivation 14 subjects PVT KSS EEG 32
channels · Multimodal Phenotyping Dataset of Driving Fatigue Scientific Data subjects EEG · CogBeacon
dataset cognitive fatigue EEG download n-back objective performance · OpenNeuro ds007509 1hrPVTdataset
psychomotor vigilance task EEG · large sleep deprivation EEG dataset 100 subjects PVT reaction time open
access · dataset EEG sleep deprivation driving simulator reaction time 80 subjects NEMAR · DROZY ULg
Multimodality Drowsiness Database Massoz 2016 14 participants PVT sleep deprivation protocol · Drivers
Drowsiness Database DD-Database sleep deprivation EEG 10 participants · "ds004105" OR "ds004122" OR
"ds004123" BCIT Touryan lane deviation steering EEG fatigue

## Verification status

`EXECUTED` = HTTP fetches of repository metadata pages, participants.tsv, events.tsv headers, READMEs, and
one published PDF. `NOT RUN` = any EEG file download, any signal inspection, any code.
Every number above is traceable to a URL in this document.
