"""03 - Extract paper_reference and mechanism_v1 features for the paired cohort.

    python project/vigilance_generalization_v1/scripts/03_extract_features.py

Both pipelines consume the SAME loaded epochs, so the two representations cannot differ
through data handling. No recording-wise normalisation is applied anywhere.

Outputs
  outputs/paper_reference/session_features.csv
  outputs/paper_reference/paired_features.csv
  outputs/mechanism_v1/session_features.csv
  outputs/mechanism_v1/paired_features.csv
  outputs/qc/feature_qc.csv
  outputs/qc/exclusions.csv
  outputs/qc/run_manifest_03_features.json
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import cohort as CO  # noqa: E402
import common as C  # noqa: E402
import mechanism_features as MF  # noqa: E402
from roi import REGION_NAMES, load_roi_mapping  # noqa: E402
from spectral import SpectralConfig, band_powers  # noqa: E402

BANDS = ("theta", "alpha", "beta")


def _num(x):
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def paper_reference_features(epochs: np.ndarray, channel_names: list[str], sfreq: float,
                             roi, spectral_cfg: SpectralConfig) -> dict:
    """Paper-compatible features.

        q_{b,e,c}    = P_{b,e,c} / P_{4-30,e,c},  P_{4-30} = P_theta + P_alpha + P_beta
        mu_{b,c}     = mean_e q_{b,e,c}
        sigma_{b,c}  = SD_e q_{b,e,c}          (ddof=1: the across-epoch variability feature)

    ROI aggregation is the channel ARITHMETIC MEAN, for paper compatibility. This is
    deliberately NOT the mechanism_v1 median rule.
    """
    bands, _ = band_powers(epochs, sfreq, spectral_cfg)
    total = bands["total_4_30"]
    if not np.all(total > 0):
        raise ValueError("non-positive total 4-30 Hz power")
    q = {b: bands[b] / total for b in BANDS}
    idx = roi.indices(channel_names)

    out: dict[str, float] = {}
    for b in BANDS:
        mu_c = q[b].mean(axis=0)
        sd_c = (q[b].std(axis=0, ddof=1) if q[b].shape[0] >= 2
                else np.full(mu_c.shape, np.nan))
        for r in REGION_NAMES:
            out[f"mu_{b}_{r}"] = float(mu_c[idx[r]].mean())
            out[f"sigma_{b}_{r}"] = float(sd_c[idx[r]].mean())
    for r in REGION_NAMES:
        out[f"n_channels_{r}"] = int(len(idx[r]))
    return out


def main() -> None:
    t_start = time.perf_counter()
    ds = C.dataset_config()
    mech = C.mechanism_config()
    canonical = [c for r in REGION_NAMES for c in ds["roi"][r]]
    target_sfreq = float(ds["eeg"]["target_sfreq_hz"])
    roi = load_roi_mapping(ds["roi"])
    spectral_cfg = SpectralConfig.from_dict(ds)
    eps_j = float(mech["personal_relative"]["delta_logJ"]["numerical_epsilon"])

    co = CO.build_cohort()
    print(f"cohort: {len(co.subjects)} paired subjects")
    print(f"  excluded: {sorted(set(co.reasons.values()))}")

    rec0 = CO.load_session(co.subjects[0], CO.BASELINE, co, canonical, target_sfreq)
    partition = roi.validate(rec0.channel_names)
    print(f"  ROI partition: {partition['region_sizes']} exact={partition['exact_partition']}")
    if not partition["exact_partition"]:
        raise SystemExit("ROI mapping is not an exact partition; refusing to continue")

    papersess: list[dict] = []
    mechsess: list[dict] = []
    qc: list[dict] = []
    errors: list[dict] = []
    paper_paired: list[dict] = []
    mech_paired: list[dict] = []

    for i, subject in enumerate(co.subjects, 1):
        try:
            ns, sd = CO.load_paired(subject, co, canonical, target_sfreq)
        except Exception as exc:  # noqa: BLE001
            errors.append({"subject": subject, "session": "", "stage": "load",
                           "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc()[-600:]})
            continue

        per_session_paper: dict[str, dict] = {}
        per_session_mech: dict[str, MF.SessionFeatures] = {}
        failed = False
        for label, rec in (("NS", ns), ("SD", sd)):
            session_id = CO.BASELINE if label == "NS" else CO.PERTURBATION
            try:
                pf = paper_reference_features(rec.epochs, rec.channel_names, rec.sfreq, roi, spectral_cfg)
                mf = MF.extract_session_features(rec.epochs, rec.channel_names, rec.sfreq, roi, spectral_cfg)
            except Exception as exc:  # noqa: BLE001
                errors.append({"subject": subject, "session": session_id, "stage": "features",
                               "error": f"{type(exc).__name__}: {exc}",
                               "traceback": traceback.format_exc()[-600:]})
                failed = True
                break
            per_session_paper[label] = pf
            per_session_mech[label] = mf
            duration = float(rec.epochs.shape[0] * rec.epochs.shape[-1] / rec.sfreq)
            papersess.append({"subject": subject, "session": session_id, "condition": label,
                              "n_epochs": int(rec.epochs.shape[0]),
                              "duration_seconds": duration, **pf})
            mechsess.append({
                "subject": subject, "session": session_id, "condition": label,
                "n_epochs": mf.n_epochs,
                "n_channels_F": mf.n_channels_per_region["F"],
                "n_channels_CT": mf.n_channels_per_region["CT"],
                "n_channels_PO": mf.n_channels_per_region["PO"],
                **{f"M_{r}": mf.M[r] for r in REGION_NAMES},
                **{f"J_{r}": mf.J[r] for r in REGION_NAMES},
                # per-session band-power extremes: carried into session_features so the QC
                # stage can audit the epsilon floor without recomputing the PSD.
                **{f"band_power_min_{b}": mf.audit["bands_summary"][b]["min"] for b in BANDS},
                **{f"band_power_max_{b}": mf.audit["bands_summary"][b]["max"] for b in BANDS},
                **{f"eps_hits_{b}": mf.audit["epsilon_hits"][b] for b in BANDS},
                "eps_hits_fraction": mf.audit["epsilon_hits"]["fraction"],
                "composition_identity_max_dev":
                    mf.audit["composition_identity"]["max_abs_deviation_from_one"],
                "duration_seconds": duration,
                "source_file": rec.path.name,
                "set_sha256": rec.provenance["set_sha256"],
                "eye_state_verdict": rec.eye_state_evidence,
                "channel_order_reordered": rec.provenance["channel_order_reordered"],
            })
            qc.append({
                "subject": subject, "session": session_id, "condition": label,
                "source_file": rec.path.name, "n_epochs": mf.n_epochs,
                "duration_seconds": duration,
                "channel_order_reordered": rec.provenance["channel_order_reordered"],
                "eye_state_verdict": rec.eye_state_evidence,
                "S_min": mf.audit["S_min"], "S_max": mf.audit["S_max"], "S_mean": mf.audit["S_mean"],
                **{f"M_{r}": mf.M[r] for r in REGION_NAMES},
                **{f"J_{r}": mf.J[r] for r in REGION_NAMES},
                **{f"J_floor_needed_{r}": mf.audit["J_floor_needed"][r] for r in REGION_NAMES},
                **{f"eps_hits_{b}": mf.audit["epsilon_hits"][b] for b in BANDS},
                "eps_hits_fraction": mf.audit["epsilon_hits"]["fraction"],
                **{f"band_min_{b}": mf.audit["bands_summary"][b]["min"] for b in BANDS},
                "composition_identity_max_dev":
                    mf.audit["composition_identity"]["max_abs_deviation_from_one"],
            })
        if failed or len(per_session_mech) != 2:
            continue

        d = MF.delta_features(per_session_mech["NS"], per_session_mech["SD"], eps_j)
        row = co.pvt[subject]
        p = co.participants[subject]

        common_paired = {
            "subject": subject,
            "delta_median_rt_ms_paper_compatible": _num(row.get("delta_median_rt_ms_paper_compatible")),
            "Y_log_medianRT_raw": _num(row.get("Y_log_medianRT_raw")),
            "Y_log_response_speed_raw": _num(row.get("Y_log_response_speed_raw")),
            "official_median_rt_NS": _num(co.official[subject].get("PVT_item2_NS")),
            "official_median_rt_SD": _num(co.official[subject].get("PVT_item2_SD")),
            "n_valid_trials_NS": _num(row.get("n_valid_trials_NS")),
            "n_valid_trials_SD": _num(row.get("n_valid_trials_SD")),
            # timing / confound metadata: STORED ONLY, never a predictor
            "session_order": p.get("SessionOrder", ""),
            "eeg_clock_NS": p.get("EEG_SamplingTime_Open_NS", ""),
            "eeg_clock_SD": p.get("EEG_SamplingTime_Open_SD", ""),
            "pvt_clock_NS": p.get("PVT_SamplingTime_NS", ""),
            "pvt_clock_SD": p.get("PVT_SamplingTime_SD", ""),
            "n_epochs_NS": per_session_mech["NS"].n_epochs,
            "n_epochs_SD": per_session_mech["SD"].n_epochs,
            "eye_evidence_NS": ns.eye_state_evidence,
            "eye_evidence_SD": sd.eye_state_evidence,
            "source_NS": ns.path.name, "source_SD": sd.path.name,
        }

        mech_paired.append({
            **common_paired,
            **{f"delta_M_{r}": d["features"][f"delta_M_{r}"] for r in REGION_NAMES},
            **{f"delta_logJ_{r}": d["features"][f"delta_logJ_{r}"] for r in REGION_NAMES},
            **{f"eps_J_used_{r}": d["detail"][r]["eps_J_used"] for r in REGION_NAMES},
            **{f"J_NS_{r}": d["detail"][r]["NS_J"] for r in REGION_NAMES},
            **{f"J_SD_{r}": d["detail"][r]["SD_J"] for r in REGION_NAMES},
        })

        def delta(band: str, stat: str, region: str):
            a = per_session_paper["NS"].get(f"{stat}_{band}_{region}")
            b = per_session_paper["SD"].get(f"{stat}_{band}_{region}")
            return None if a is None or b is None else float(b) - float(a)

        paper_paired.append({
            **common_paired,
            **{f"delta_{band}_{stat}_{r}": delta(band, stat, r)
               for band in BANDS for stat in ("mu", "sigma") for r in REGION_NAMES},
        })

        if i % 10 == 0:
            print(f"  processed {i}/{len(co.subjects)}", flush=True)

    C.write_csv(C.OUTPUTS / "paper_reference" / "session_features.csv", papersess)
    C.write_csv(C.OUTPUTS / "paper_reference" / "paired_features.csv", paper_paired)
    C.write_csv(C.OUTPUTS / "mechanism_v1" / "session_features.csv", mechsess)
    C.write_csv(C.OUTPUTS / "mechanism_v1" / "paired_features.csv", mech_paired)
    C.write_csv(C.OUTPUTS / "qc" / "feature_qc.csv", qc)
    C.write_csv(C.OUTPUTS / "qc" / "exclusions.csv", errors)
    C.write_json(C.OUTPUTS / "qc" / "run_manifest_03_features.json", C.run_manifest(
        __file__, [C.CONFIG / "dataset_ds004902.yaml", C.CONFIG / "mechanism_v1.yaml"],
        {"n_cohort": len(co.subjects), "n_sessions_extracted": len(mechsess),
         "n_paired_rows": len(mech_paired), "n_errors": len(errors),
         "spectral_config": spectral_cfg.describe(), "roi_partition": partition,
         "cohort_exclusions": co.reasons, "eps_J": eps_j,
         "elapsed_seconds": time.perf_counter() - t_start}))

    print()
    print("=" * 78)
    print("FEATURE EXTRACTION")
    print("=" * 78)
    print(f"  cohort subjects    : {len(co.subjects)}")
    print(f"  sessions extracted : {len(mechsess)}")
    print(f"  mechanism paired   : {len(mech_paired)}")
    print(f"  paper paired       : {len(paper_paired)}")
    print(f"  errors             : {len(errors)}")
    print(f"  elapsed            : {time.perf_counter()-t_start:.1f} s")
    print("wrote outputs/paper_reference/* and outputs/mechanism_v1/*")


if __name__ == "__main__":
    main()
