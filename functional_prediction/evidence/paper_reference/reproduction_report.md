# Paper-reference reproduction report

Paired subjects: **n = 29**  
Cohort: admissible eyes-open 500 Hz EEG **and** raw-PVT-paired, both sessions.  
Reference values quoted from the source paper: rho_F ~ 0.54, rho_CT ~ 0.56.

> This is an implementation-validity check, not our contribution and not an
> optimisation target. Preprocessing, bands, ROIs and the subject set were held
> fixed; nothing was tuned to move rho.

## Primary statistic

| ROI | rho(Delta theta var, Delta median RT) | p | bootstrap CI95 | reference | diff |
|---|---|---|---|---|---|
| F | +0.102 | 0.5985 | [-0.295, +0.476] | +0.54 | -0.438 |
| CT | +0.393 | 0.0352 | [+0.030, +0.692] | +0.56 | -0.167 |
| PO | +0.346 | 0.0662 | [-0.031, +0.644] | n/a | n/a |

## Group-level SD-NS change

| ROI | Delta theta variability (SD-NS) | p | Delta theta relative power | p |
|---|---|---|---|---|
| F | +0.0085 | 0.2374 | +0.0102 | 0.5017 |
| CT | +0.0179 | 0.0061 | +0.0273 | 0.0165 |
| PO | +0.0186 | 0.0196 | +0.0264 | 0.0831 |

## Context: alpha and beta variability

| band | F | CT | PO |
|---|---|---|---|
| alpha | -0.035 (p=0.857) | +0.032 (p=0.869) | +0.174 (p=0.367) |
| beta | +0.213 (p=0.267) | +0.168 (p=0.384) | +0.083 (p=0.668) |

## Subject-count sensitivity (reported, NOT adopted)

The working cohort is the unfiltered 29 raw-PVT-paired subjects with admissible
eyes-open EEG. The published analysis has ~28. The only a-priori filter found in
this workspace that yields exactly 28 is reported below; it is **not** applied.

```json
{
  "note": "Reported for transparency only. We do NOT adopt any of these filters; the working cohort is the unfiltered 29 raw-PVT-paired subjects with EEG.",
  "candidates_yielding_28": [
    "A_min_valid_trials_45_per_session"
  ],
  "counts": {
    "A_min_valid_trials_40_per_session": 29,
    "A_min_valid_trials_45_per_session": 28,
    "A_min_valid_trials_48_per_session": 13,
    "A_min_valid_trials_50_per_session": 12,
    "B_median_rt_within_200_1000": 29,
    "B_median_rt_within_250_600": 29,
    "B_median_rt_within_100_1000": 29,
    "C_exclude_sub70_sub71": 27,
    "D_positive_responders_only_DO_NOT_USE": 27,
    "E_official_and_raw_both_present": 29
  },
  "rho_if_that_filter_were_applied": {
    "F": {
      "n": 28,
      "spearman_rho": 0.09282586276988913,
      "p_value": 0.638490371055783,
      "bootstrap_ci95": [
        -0.296444578333595,
        0.44951539457304834
      ],
      "n_bootstrap": 1000
    },
    "CT": {
      "n": 28,
      "spearman_rho": 0.3869113395098918,
      "p_value": 0.04195212970879996,
      "bootstrap_ci95": [
        0.042032733477287504,
        0.6854624598570288
      ],
      "n_bootstrap": 1000
    },
    "PO": {
      "n": 28,
      "spearman_rho": 0.3335159317219025,
      "p_value": 0.08284847687713819,
      "bootstrap_ci95": [
        -0.05189479860992594,
        0.6346854442327355
      ],
      "n_bootstrap": 1000
    }
  }
}
```
