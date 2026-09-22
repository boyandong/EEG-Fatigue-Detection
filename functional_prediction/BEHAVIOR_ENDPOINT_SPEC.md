# BEHAVIOR_ENDPOINT_SPEC.md — the frozen behavioural target for BCIT

**Phase:** `SRTP-PHASE3C-20260917-BEHAVIOR-ENDPOINT`
**Status:** frozen at the end of Phase 3C. Phase 4 (mature baseline trunk) must consume this
document unchanged, or state explicitly that it is changing it and why.
**Scope:** behaviour only. No EEG feature, no EEG↔behaviour statistic, no model was used to
produce anything in this specification.

---

## 1. What is being specified

One question:

> Does BCIT Baseline Driving contain at least one objective performance variable, reconstructed
> from the real vehicle behaviour, with enough semantic clarity, measurement quality,
> within-person dynamic range and temporal structure to serve as a **frozen prediction target**
> for a later EEG study?

The answer Phase 3C reached is in `PHASE3C_BEHAVIOR_ENDPOINT_REPORT.md` §6-§8 and
`audit/phase3c/outputs/endpoint_eligibility.json`. This document fixes the *definitions* that
answer rests on, so that a later phase cannot quietly redefine the target.

---

## 2. Frozen input contract

| item | value | source |
|---|---|---|
| dataset | `ds004120` Baseline Driving (NEMAR `on004120`, CC0) | `audit/phase3/outputs/bcit_recording_index.csv` |
| calibration arm | `ds004118` Calibration Driving (`on004118`) | same |
| identity key | **`legacy_labID`**, never `sub-NN` | `SESSION_HANDOVER.md` §2; re-verified §4.2 |
| behaviour channels | `LN`, `ANG`, `SP`, `SD` — columns of the EEG matrix, `type=OTHER` | `*_channels.tsv` |
| primary channel | **`LN`** = *"Lane deviation from center line in meters."* (verbatim) | `*_channels.tsv` `description` |
| units field | `n/a` for all four channels — **no machine-readable unit** | `*_channels.tsv` |
| time base | one clock: `event/sample == onset × srate`, slope = srate, intercept 0 | `audit/phase3b/outputs/temporal_alignment.csv` |
| simulator clock | `etc/timestamp`, per sample, monotone, tick = `1/srate` to ~16 ppm | same |

### 2.1 The valid (driving) window — mandatory

Every recording's vehicle channels are **zero-padded at both ends** by the pre/post-logging
span. The pad is *not* driving data and reads exactly `0.0`.

```
valid_start = max over the four vehicle channels of (leading constant-run length)
valid_stop  = n_samples - max over the four channels of (trailing constant-run length)
```

Measured in the Phase 3C sample: lead pads of **44.1 / 59.3 / 90.1 / 151.8 s** and trail pads of
**34.9 / 26.3 / 22.7 / 14.4 s**; the first task event begins within **0.5-2 ms** of the lead
pad's end in all four. **No statistic may be computed over file bounds.**

---

## 3. Family A — lane-control endpoint (the frozen primary target)

### 3.1 Definition

$$
\boxed{\;L(t) = \bigl|LN(t)\bigr|\;\ \text{[metres]}, \qquad
Y_{i,w} = \operatorname{mean}_{t \in w} L(t)\;}
$$

`LN` is a **signed lateral deviation about the lane centre**, and `LN = 0` is that centre. This
was not assumed; it was measured (§3.2). `|LN|` is used because the *sign convention* — which
side is positive — is undocumented and the endpoint does not need it.

### 3.2 Why `LN = 0` is the lane centre (the geometry test)

The release's own lane vocabulary (`code/task-*_events.json`) fires where the vehicle is
"right of" or "left of" the defined lane of travel. If `LN` were an uncalibrated lane position,
those events would not respect `LN = 0` as a centre. Measured:

| test | result |
|---|---|
| fraction of `4220` ("moves right of the lane") events at `LN > 0` | **1.000** in all 4 recordings |
| fraction of `4230` ("moves left of the lane") at `LN < 0` | **1.000** in all 4 recordings |
| median `\|LN\|` at out-of-lane events | **0.9172 / 0.9168 / 0.9181 / 0.9175 m** (spread 1.4 mm) |
| `\|LN\|` at `4210` ("moves into the lane") | 0.907-0.913 m — i.e. at the boundary, on either side |
| `4200` ("lane position cannot be measured") | **0 events** in all 4 recordings |

Consequence: the lane half-width is **0.917 m** and the boundary is sharp and symmetric about
`LN = 0`. `c(t) = 0` is therefore the documented and measured lane centre, not a convention.
`SDLP_w = sd_{t∈w}(LN(t))` is *also* a legitimate dispersion measure, because `LN = x − c` is
available directly; it is reported as a secondary descriptive summary, not promoted.

### 3.3 Frozen window scales

Two, and only two, descriptive scales:

| scale | definition | note |
|---|---|---|
| `block` | the protocol block, reconstructed by splitting the `3200` grid at gaps > **90 s** | 6 blocks per baseline recording, 15-16 tiles each, 9.7-10.7 min |
| `5min` | contiguous windows of **≥ 300 s**, both boundaries placed **on `3200` onsets**, overrunning by at most one tile period (≤ 340 s) | 8 complete windows per baseline recording |

A tail shorter than 300 s is emitted with `complete_300s = false` and **excluded** from primary
summaries. It is never shrunk to fit.

### 3.4 Frozen secondary summaries (descriptive, never promoted)

`median |LN|`, `P90 |LN|`, `sd(LN)` (SDLP-like), `mean LN` (**offset diagnostic** — see §5),
fraction of time with `|LN| > 0.917 m`, excursion count, perturbation count.

### 3.5 Smoothing

The historical BCIT work used a **≈90 s centred** moving average. A centred window uses future
samples, so it **cannot** be a deployment definition. It is admissible only as a historical
replication sensitivity, must never cross a block or condition boundary, and is **not** part of
this specification.

---

## 4. Family B — perturbation-response endpoint

### 4.1 Definition

$$
\boxed{\;RT_j = t_{\text{onset}}(4311)_j - t_{\text{onset}}(\text{perturbation})_j\;}
$$

* perturbation onset: event **`1111`** (left) or **`1121`** (right), *"Start of left/right
  perturbation"*;
* response onset: event **`4311`**, *"Driver starts correcting lane position."*;
* the release documents the detection criterion for `4311`/`4312` verbatim:

> "Course correction has been detected because the vehicle has a heading error of more than
> **5.1566 degrees** from the forward direction **or** the driver is steering away from the
> perturbation with a steering angle of more than **4 degrees**."

So the response criterion belongs to the producer. **No threshold, percentile, derivative rule
or latency cutoff was chosen by Phase 3C.** The only quantity this specification adds is a
**search bound** of **10 s** for the first `4311` after a perturbation — a bound, not a
criterion, and it is recorded as such.

### 4.2 Secondary

`correction duration = onset(4312) − onset(4311)`.

### 4.3 Status

**Family B is INCONCLUSIVE, not eligible** (`endpoint_eligibility.json`). Measured with the
identical definition on all three site classes in the sample:

| | T1 (`1001`) | T2 (`1010`) | T3 (`3101`) |
|---|---|---|---|
| median RT | 3.6528 s | 1.4399 s | 1.4189 s |
| IQR | 2.6414 s | 0.4302 s | 0.2871 s |
| CV | 0.5025 | 0.3226 | 0.2421 |
| frac RT > 5 s | 25.5 % | 0.0 % | 0.0 % |
| left − right median | −0.649 s (p = 0.013) | −0.075 s | 0.000 s |

The structure is **two clusters**: T2 and T3 agree to within 21 ms in median, T1 is separated by
2.5× in median and 6-9× in IQR with a quarter of responses above 5 s. Both use the same event
codes and the same documented criterion, so this is either a site/protocol difference or a
marker that does not measure the same thing everywhere. **Do not build on Family B until that is
resolved**, and do not resolve it by choosing a different threshold — the marker is the
producer's, so the ambiguity is about meaning, not about the cut.

---

## 5. Documented semantic caveat of the primary endpoint

`10_lane_geometry.py` and `11_event_alignment.py` measured a **systematic lateral offset**: the
vehicle sits left of `LN = 0` for most of the session, increasingly so in the Baseline arm.

| recording | mean `LN` (m) | frac `LN>0` | \|LN\| p50 |
|---|---|---|---|
| `1001` calibration | −0.0147 | 0.465 | 0.266 |
| `1001` baseline | −0.2194 | 0.275 | 0.305 |
| `3101` calibration | −0.2160 | 0.278 | 0.298 |
| `3101` baseline | −0.3678 | 0.115 | 0.373 |

Consequences that a downstream phase must carry:

1. `mean |LN|` mixes **where the driver sits** (offset) with **how much they wander**
   (dispersion). `sd(LN)` isolates dispersion. Both are reported; the offset is reported
   alongside, always.
2. The offset is **not** a fixed simulator bias: it is small in Calibration and large in
   Baseline, and it grows within three of the four recordings.
3. It is present already in the first 5 s after a perturbation in the Baseline arm, in the
   direction the perturbation pushed — so a substantial part of it is perturbation- and
   recovery-driven, not a free-standing drift.

---

## 6. Prohibited operations in any later phase that uses this target

* no endpoint substituted because its trend is larger;
* no window scale, smoothing length or threshold adjusted after seeing a result;
* no `3200`-crossing window, no whole-file statistic, no centred smoothing in a deployment path;
* no `sub-NN` cross-dataset join;
* no Calibration subtraction as a pure fatigue contrast (see §7);
* no iid bootstrap on these series — they are autocorrelated at the episode scale.

---

## 7. Calibration: frozen role

Producer documentation supports Calibration as a **candidate non-fatigued personal reference**
(≈15 min, steering only, simulator-controlled speed, first in the visit). Phase 3C confirms on
its own bytes that Calibration and Baseline are **different task configurations**, and adds one
behavioural fact that settles the arm question further:

> Calibration recordings in this sample contain perturbation onsets **and** lane events but
> **zero `4311` course-correction markers** (`1001`: 57 perturbations, 0 corrections; `3101`:
> 80 perturbations, 1 correction). Baseline recordings carry hundreds.

**Frozen:** Calibration is a candidate non-fatigued reference, and
`Baseline − Calibration ≠ pure fatigue` (task-demand, speed-control responsibility, order and
context differ). **Calibration subtraction does not define the Phase 3C deterioration target**
and remains PARK.

---

## 8. Evaluation target for Phase 4, if Family A is used

* target: `Y_{i,w} = mean_{t∈w}|LN(t)|` over the frozen `5min` windows, Baseline arm,
  `complete_300s = true` only, computed inside the valid window;
* contrast: `WithinPerson` **vs** `CrossSubject zero-shot`, both against the no-EEG `M0` bar;
* reporting: the **failure profile**, not a leaderboard — per-subject slope distribution,
  the condition-aware vs naive gap, and the site strata;
* the endpoint's own dispersion (`sd(LN)`) and offset (`mean LN`) travel with every report of
  `mean |LN|`.

---

## 9. Provenance

Every number in this specification is reproducible from:

```
audit/phase3c/02_extract_vehicle.py    -> outputs/vehicle_extraction_qc.json, cache/*.npz
audit/phase3c/10_lane_geometry.py      -> outputs/lane_geometry.json, lane_measurement_qc.csv
audit/phase3c/11_event_alignment.py    -> outputs/event_alignment.json
audit/phase3c/12_block_structure.py    -> outputs/block_structure.json
audit/phase3c/20_window_metrics.py     -> outputs/lane_window_metrics.csv
audit/phase3c/21_uncertainty.py        -> outputs/uncertainty.json
audit/phase3c/30_perturbation_endpoint.py -> outputs/perturbation_endpoint.json
audit/phase3c/31_endpoint_eligibility.py  -> outputs/endpoint_eligibility.json
audit/phase3c/40_verify_phase3c.py     -> outputs/phase3c_verification.json
```

Workspace is **not** a git repository: `git_commit: COMMIT PENDING` is correct here, and
provenance rests on file-content hashes.
