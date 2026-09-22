"""07 - Finalize the run manifest and file hashes for Phase 1.

    python project/vigilance_generalization_v1/scripts/07_finalize_run_manifest.py

Collects the per-stage run manifests, hashes every deliverable, and writes the
consolidated outputs/qc/run_manifest.json required by the Phase 1 deliverable list.
"""
from __future__ import annotations

import sys
from pathlib import Path

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402

CONFIGS = ["config/dataset_ds004902.yaml", "config/mechanism_v1.yaml"]
SOURCES = [
    "src/common.py", "src/roi.py", "src/spectral.py", "src/mechanism_features.py",
    "src/data_ds004902.py", "src/pvt_targets.py", "src/cohort.py",
    "src/stability.py", "src/stability_metrics.py", "src/probe_raw_recovery.py",
    "src/dynamic_mechanism.py", "src/pvt_psychometrics.py", "src/phase2_models.py",
    "scripts/00_audit_source_data.py", "scripts/01_build_pvt_targets.py",
    "scripts/02_build_eeg_manifest.py", "scripts/03_extract_features.py",
    "scripts/04_qc_features.py", "scripts/05_paper_reference_check.py",
    "scripts/06_verify_phase1.py", "scripts/07_finalize_run_manifest.py",
    "scripts/10_extract_windows.py", "scripts/11_stability_metrics.py",
    "scripts/12_finite_sample_J.py", "scripts/13_stability_plots.py",
    "scripts/14_verify_phase15.py", "scripts/run_phase1.py", "scripts/run_phase15.py",
    "scripts/20_extract_dynamic.py", "scripts/21_pvt_psychometrics.py",
    "scripts/22_dynamic_stability.py", "scripts/23_verify_phase175.py",
    "scripts/24_dynamic_plots.py", "scripts/run_phase175.py",
    "scripts/30_phase2_models.py", "scripts/31_verify_phase2.py",
    "tests/test_mechanism.py", "tests/test_phase2_ridge.py",
    "SCIENTIFIC_SPEC.md", "PHASE1_REPORT.md", "PHASE1_5_REPORT.md", "PHASE1_75_REPORT.md",
    "PHASE2_REPORT.md",
    "paper_sample_reconciliation.md", "official_raw_recovery_plan.md",
]
OUTPUTS = [
    "outputs/manifests/source_eeg_manifest.csv",
    "outputs/manifests/eeg_eyesopen_manifest.csv",
    "outputs/manifests/pvt_manifest.csv",
    "outputs/pvt/pvt_trial_audit.csv",
    "outputs/pvt/pvt_reconciliation.csv",
    "outputs/pvt/pvt_targets_raw.csv",
    "outputs/pvt/pvt_targets_official.csv",
    "outputs/pvt/pvt_subject_sets.json",
    "outputs/paper_reference/session_features.csv",
    "outputs/paper_reference/paired_features.csv",
    "outputs/paper_reference/reproduction_report.md",
    "outputs/paper_reference/reproduction_stats.json",
    "outputs/mechanism_v1/session_features.csv",
    "outputs/mechanism_v1/paired_features.csv",
    "outputs/qc/source_audit_summary.json",
    "outputs/qc/eeg_manifest_summary.json",
    "outputs/qc/eeg_exclusions.csv",
    "outputs/qc/feature_qc.csv",
    "outputs/qc/qc_report.json",
    "outputs/qc/exclusions.csv",
    "outputs/qc/verification.json",
    # ---- Phase 1.5
    "outputs/stability_v1/session_window_features.csv",
    "outputs/stability_v1/paired_window_features.csv",
    "outputs/stability_v1/window_inventory.csv",
    "outputs/stability_v1/paired_window_inventory.csv",
    "outputs/stability_v1/sample_accounting.json",
    "outputs/stability_v1/duration_summary.csv",
    "outputs/stability_v1/disjoint_agreement.csv",
    "outputs/stability_v1/position_drift.csv",
    "outputs/stability_v1/accumulation_convergence.csv",
    "outputs/stability_v1/delta_sign_stability.csv",
    "outputs/stability_v1/delta_duration_summary.csv",
    "outputs/stability_v1/baseline_scenario.csv",
    "outputs/stability_v1/stability_stats.json",
    "outputs/stability_v1/finite_sample_J_simulation.csv",
    "outputs/stability_v1/finite_sample_J_summary.json",
    "outputs/stability_v1/eeg_quality_200uV.csv",
    "outputs/stability_v1/raw_recovery_probe.json",
    "outputs/qc/verification_phase15.json",
    "outputs/qc/exclusions_stability.csv",
    # ---- Phase 1.75
    "outputs/dynamic_audit/J_V_Jres_session.csv",
    "outputs/dynamic_audit/J_V_Jres_paired.csv",
    "outputs/dynamic_audit/duration_grid_reference.csv",
    "outputs/dynamic_audit/protocol_inventory.csv",
    "outputs/dynamic_audit/stability_comparison.csv",
    "outputs/dynamic_audit/position_effect_comparison.csv",
    "outputs/dynamic_audit/paired_dynamic_stability.csv",
    "outputs/dynamic_audit/burnin_duration_grid.csv",
    "outputs/pvt_psychometrics/pvt_target_uncertainty.csv",
    "outputs/pvt_psychometrics/pvt_trial_parse_audit.csv",
    "outputs/pvt_psychometrics/pvt_split_half.csv",
    "outputs/pvt_psychometrics/pvt_bootstrap_summary.csv",
    "outputs/pvt_psychometrics/target_reliability_summary.csv",
    "outputs/qc/verification_phase175.json",
    "outputs/qc/exclusions_dynamic.csv",
    # ---- Phase 2
    "outputs/phase2/features_used.csv",
    "outputs/phase2/model_results.csv",
    "outputs/phase2/predictions.csv",
    "outputs/phase2/alpha_selection.csv",
    "outputs/phase2/permutation_null.npz",
    "outputs/phase2/permutation_summary.json",
    "outputs/phase2/bootstrap_ci.json",
    "outputs/phase2/confound_sensitivity.csv",
    "outputs/phase2/phase2_summary.json",
    "outputs/qc/verification_phase2.json",
]


def main() -> None:
    hashes: dict[str, str] = {}
    for rel in SOURCES + OUTPUTS:
        p = VIG / rel
        hashes[rel] = C.sha256_file(p) if p.exists() else "MISSING"

    missing = [k for k, v in hashes.items() if v == "MISSING"]
    cfg_hashes = {rel: C.sha256_file(VIG / rel) for rel in CONFIGS}

    stages = {}
    for name in ("01_pvt", "03_features", "10_windows", "20_dynamic", "21_pvt_psychometrics", "30_phase2"):
        p = C.OUTPUTS / "qc" / f"run_manifest_{name}.json"
        if p.exists():
            stages[name] = C.json.loads(p.read_text(encoding="utf-8"))

    man = {
        "branch": "vigilance_generalization_v1",
        "phase": "1 + 1.5 + 1.75 + 2",
        "objective": ("baseline-relative EEG -> baseline-relative objective impairment. "
                      "Phase 1 built the auditable foundation; Phase 1.5 audited whether the "
                      "six-dimensional representation can be estimated reliably from short "
                      "recordings; Phase 1.75 decomposed the dynamic observable (J vs V vs "
                      "J_res), audited Protocol(B,T), and quantified the PVT target's own "
                      "measurement uncertainty. Phase 2 then ran the first EEG->behaviour predictive test. "
                      "The primary hypothesis returned a pre-registered Case C null result."),
        "git_commit": C.git_commit(VIG.parents[1]) or "COMMIT PENDING",
        "python": __import__("platform").python_version(),
        "platform": __import__("platform").platform(),
        "versions": C._versions(),
        "random_seed_used": "Phase 1: none. Phase 1.5: bootstrap CI and Monte-Carlo simulation "
                            "only; seeds explicit (BOOT_SEED=20260916, SEED=20260916). No model "
                            "fitting, no shuffling, no sampling anywhere.",
        "determinism_note": ("Feature extraction and stability metrics are deterministic. Verified "
                             "in scripts/06_verify_phase1.py (25 checks) and "
                             "scripts/14_verify_phase15.py (26 checks)."),
        "config_sha256": cfg_hashes,
        "source_sha256": {k: v for k, v in hashes.items() if k in SOURCES},
        "output_sha256": {k: v for k, v in hashes.items() if k in OUTPUTS},
        "missing": missing,
        "stage_manifests": stages,
        "data_readonly_note": ("data/ was never written to. PVT trial files and EEGLAB .set "
                               "files were opened read-only; PVT parsing records column names "
                               "rather than rewriting headers."),
    }
    C.write_json(C.OUTPUTS / "qc" / "run_manifest.json", man)

    print(f"sources hashed : {len(SOURCES)}")
    print(f"outputs hashed : {len(OUTPUTS)}")
    print(f"missing        : {missing if missing else 'none'}")
    print(f"git commit     : {man['git_commit']}")
    print("wrote outputs/qc/run_manifest.json")


if __name__ == "__main__":
    main()
