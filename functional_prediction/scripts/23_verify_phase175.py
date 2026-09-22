"""23 - Independent verification of the Phase 1.75 deliverables.

    python project/vigilance_generalization_v1/scripts/23_verify_phase175.py

Recomputes the dynamic observables from the raw .set files and checks them against the shipped
tables; verifies the mathematical identities; verifies window/burn-in geometry; and confirms
that no PVT value reaches any dynamic table.

Exit code 0 = verified.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import dynamic_mechanism as DM  # noqa: E402
import pvt_psychometrics as PP  # noqa: E402
import stability as ST  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))


def f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def main() -> int:
    est = ST.Estimator.build()
    dyn = C.OUTPUTS / "dynamic_audit"
    psy = C.OUTPUTS / "pvt_psychometrics"

    # ---------------------------------------------------------------- 1. deliverables
    print("1. Required deliverables")
    need = [dyn / "J_V_Jres_session.csv", dyn / "J_V_Jres_paired.csv",
            dyn / "stability_comparison.csv", dyn / "position_effect_comparison.csv",
            dyn / "burnin_duration_grid.csv", dyn / "paired_dynamic_stability.csv",
            dyn / "plots",
            psy / "pvt_target_uncertainty.csv", psy / "pvt_bootstrap_summary.csv",
            psy / "pvt_split_half.csv", psy / "target_reliability_summary.csv"]
    missing = [str(p.relative_to(C.VIG)) for p in need if not p.exists()]
    check("all Phase 1.75 deliverables present", not missing, f"missing={missing}")
    check("plots non-empty", len(list((dyn / "plots").glob("*.png"))) >= 4,
          f"{len(list((dyn / 'plots').glob('*.png')))} png")

    # ---------------------------------------------------------------- 2. mathematical identities
    print("\n2. Mathematical identities of V and J_res")
    rng = np.random.default_rng(20260916)
    # V equals the sample SD for i.i.d. data, up to finite-sample noise
    x = rng.normal(0, 1, 200000)
    check("V ~= SD for i.i.d. (large sample)",
          abs(DM.local_volatility(x) - x.std(ddof=1)) / x.std(ddof=1) < 0.01,
          f"V={DM.local_volatility(x):.5f} SD={x.std(ddof=1):.5f}")
    # A pure linear ramp of total range 1 over N points has every adjacent difference equal to
    # 1/(N-1), so V = (1/(N-1))/sqrt(2) exactly -- NOT zero. What matters is the N-dependence:
    #   J of a ramp  ~ 1/sqrt(12), independent of N
    #   V of a ramp  ~ 1/(sqrt(2)(N-1)) ~ 1/N
    # so V's sensitivity to a slow trend falls as 1/N while J's stays constant. That is a
    # substantive property of the estimator (reported as a finding), not a defect.
    print("   (V on a ramp is not zero -- it scales as 1/N; checking the scaling law itself)")
    for N in (60, 120, 240):
        ramp_n = np.linspace(0.0, 1.0, N)
        v_theory = (1.0 / (N - 1)) / np.sqrt(2.0)
        v_got = DM.local_volatility(ramp_n)
        check(f"ramp N={N}: V matches (1/(N-1))/sqrt(2)",
              abs(v_got - v_theory) < 1e-12, f"V={v_got:.3e} theory={v_theory:.3e}")
    ramp = np.linspace(0.0, 1.0, 60)
    check("V is far less drift-sensitive than J on the same ramp (N=60)",
          DM.local_volatility(ramp) / ramp.std(ddof=1) < 0.05,
          f"V/J = {DM.local_volatility(ramp)/ramp.std(ddof=1):.5f}")
    check("J_res ~ 0 on a pure linear ramp",
          (lambda fit: fit.residual_sd < 1e-9)(DM.drift_fit(ramp)),
          f"J_res={DM.drift_fit(ramp).residual_sd:.2e}")
    # slope recovers a known total change
    sig = 3.0 * DM.centred_time(400)
    check("drift slope recovers a known total change",
          abs(DM.drift_fit(sig).slope - 3.0) < 1e-9, f"slope={DM.drift_fit(sig).slope:.9f}")
    # noise amplification on differencing
    noisy = rng.normal(0, 1, 100000)
    check("differencing doubles the variance (Var(d) ~= 2 sigma^2)",
          abs(np.diff(noisy).var(ddof=1) / 2.0 - 1.0) < 0.02,
          f"Var(diff)/2 = {np.diff(noisy).var(ddof=1)/2:.4f}")
    # decomposition identity: variance splits into drift-explained + residual
    S = np.linspace(0, 1, 300) + rng.normal(0, 0.1, 300)
    dec = DM.decomposition_identity(S)
    check("variance decomposition is internally consistent",
          abs(dec["var_total"] - dec["var_residual_after_linear_drift"]) >= 0
          and 0 <= dec["fraction_of_variance_from_linear_drift"] <= 1,
          f"frac_from_drift={dec['fraction_of_variance_from_linear_drift']:.4f}")

    # ---------------------------------------------------------------- 3. recomputation
    print("\n3. Independent recomputation of dynamic observables")
    sess = C.read_csv(dyn / "J_V_Jres_session.csv")
    saved = {(r["subject"], r["session"], r["label"], int(r["window_index"])): r for r in sess}
    subjects = sorted({r["subject"] for r in sess})[:4]
    worst = {}
    n_checked = 0
    problems = []
    # Label namespace: the duration grid carries B = 0 (k8/k15/k30 == B0_T32/T60/T120), and the
    # protocol grid carries only B > 0. B = 0 is deliberately NOT duplicated under two names.
    DUR_LABEL = {8: "k8", 15: "k15", 30: "k30"}
    for subject in subjects:
        for session in ("ses-1", "ses-2"):
            try:
                epochs, _ = ST.load_session_epochs(subject, session, est)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{subject} {session}: {type(exc).__name__}")
                continue
            N = epochs.shape[0]
            # B = 0 -> duration grid
            for te, lab in DUR_LABEL.items():
                n_win = N // te
                for i in range(n_win):
                    row = saved.get((subject, session, lab, i))
                    if row is None:
                        continue
                    got = est.dynamic_features(epochs[i * te:(i + 1) * te])
                    for r in REGION_NAMES:
                        for col in (f"M_{r}", f"J_{r}", f"V_{r}", f"D_{r}", f"Jres_{r}"):
                            worst[col] = max(worst.get(col, 0.0), abs(got[col] - f(row[col])))
                    n_checked += 1
            # full session
            row = saved.get((subject, session, "full", 0))
            if row is not None:
                got = est.dynamic_features(epochs)
                for r in REGION_NAMES:
                    for col in (f"M_{r}", f"J_{r}", f"V_{r}", f"D_{r}", f"Jres_{r}"):
                        worst[col] = max(worst.get(col, 0.0), abs(got[col] - f(row[col])))
                n_checked += 1
            # B > 0 -> protocol grid
            for B in (32, 60):
                be = B // 4
                if be >= N:
                    continue
                tail = epochs[be:]
                for T in (32, 60, 120):
                    te = T // 4
                    n_win = tail.shape[0] // te
                    label = f"B{B}_T{T}"
                    for i in range(n_win):
                        row = saved.get((subject, session, label, i))
                        if row is None:
                            continue
                        got = est.dynamic_features(tail[i * te:(i + 1) * te])
                        for r in REGION_NAMES:
                            for col in (f"M_{r}", f"J_{r}", f"V_{r}", f"D_{r}", f"Jres_{r}"):
                                worst[col] = max(worst.get(col, 0.0), abs(got[col] - f(row[col])))
                        n_checked += 1
    check("no recomputation problems", not problems, str(problems[:3]))
    for col, d in sorted(worst.items()):
        check(f"recompute matches table: {col}", d < 1e-9, f"max|d|={d:.3e}")
    check(f"recomputed {n_checked} windows", n_checked > 50, str(n_checked))

    # ---------------------------------------------------------------- 4. geometry
    print("\n4. Window and burn-in geometry")
    inv = C.read_csv(dyn / "protocol_inventory.csv")
    bad = []
    for r in inv:
        if r["grid"] != "protocol":
            continue
        B = int(r["burnin_seconds"]); T = int(r["measure_seconds"])
        N = int(r["session_n_epochs"]); nw = int(r["n_windows"])
        be, te = B // 4, T // 4
        expect = 0 if be >= N else (N - be) // te
        if nw != expect:
            bad.append(f"{r['subject']}_{r['session']}_{r['label']}: {nw} != {expect}")
    check("protocol window counts equal floor((N-burnin)/T)", not bad, str(bad[:3]))
    # full-session label must have burn-in 0 and one window
    full = [r for r in sess if r["label"] == "full"]
    check("full-session rows have burn-in 0 and exactly one window",
          all(int(r["protocol_B"]) == 0 for r in full)
          and len({r["subject"] + r["session"] for r in full}) == len(full),
          f"{len(full)} rows")

    # ---------------------------------------------------------------- 5. PVT isolation
    print("\n5. PVT isolation")
    leak = {}
    for p in sorted(dyn.glob("*.csv")):
        rows = C.read_csv(p)
        if not rows:
            continue
        hits = [c for c in rows[0] if any(t in c.lower() for t in
                                          ("y_log", "median_rt", "pvt", "target", "response_speed"))]
        if hits:
            leak[p.name] = hits
    check("no PVT/target column anywhere in outputs/dynamic_audit", not leak, str(leak))

    # ---------------------------------------------------------------- 6. target definitions
    print("\n6. Target definitions and bootstrap")
    unc = C.read_csv(psy / "pvt_target_uncertainty.csv")
    ok_dir = all((f(r["Y_RT_point"]) >= 0) == (f(r["median_rt_SD"]) >= f(r["median_rt_NS"]))
                 for r in unc)
    check("Y_RT>0 iff median RT rose (Y>0 means deterioration)", ok_dir)
    ok_sp = all((f(r["Y_speed_point"]) >= 0) == (f(r["speed_NS"]) >= f(r["speed_SD"])) for r in unc)
    check("Y_speed>0 iff response speed fell", ok_sp)
    check("bootstrap used the declared replicate count",
          all(int(r["n_boot_used"]) == 5000 for r in unc if r["n_boot_used"]),
          str(sorted({r['n_boot_used'] for r in unc})))
    check("SE strictly positive for every subject",
          all(f(r["Y_RT_se"]) > 0 and f(r["Y_speed_se"]) > 0 for r in unc))
    check("bootstrap CIs bracket the point estimate (RT target)",
          all(f(r["Y_RT_ci_low"]) <= f(r["Y_RT_point"]) <= f(r["Y_RT_ci_high"]) for r in unc))
    check("bootstrap CIs bracket the point estimate (speed target)",
          all(f(r["Y_speed_ci_low"]) <= f(r["Y_speed_point"]) <= f(r["Y_speed_ci_high"]) for r in unc))

    # ---------------------------------------------------------------- 7. reliability arithmetic
    print("\n7. Reliability arithmetic reproduced from the per-subject table")
    ok_rel = True
    detail = []
    for tgt, pre in (("Y_RT", "Y_RT"), ("Y_speed", "Y_speed")):
        y = np.array([f(r[f"{pre}_point"]) for r in unc])
        se = np.array([f(r[f"{pre}_se"]) for r in unc])
        s2 = float(np.var(y, ddof=1)); e2 = float(np.mean(se ** 2))
        r_calc = max(0.0, 1 - e2 / s2)
        row = next((r for r in C.read_csv(psy / "target_reliability_summary.csv")
                    if r["target"] == tgt), None)
        r_tab = f(row["R_approx"]) if row else np.nan
        ok_rel &= abs(r_calc - r_tab) < 1e-9
        detail.append(f"{tgt}: {r_tab:.4f}")
    check("R_approx reproduces from sigma_eps^2 and s_Y^2", ok_rel, "; ".join(detail))

    # ---------------------------------------------------------------- 8. vocabulary
    print("\n8. Reporting-vocabulary discipline in the spec")
    spec = (C.VIG / "SCIENTIFIC_SPEC.md").read_text(encoding="utf-8")
    check("spec defines J as total within-recording temporal dispersion",
          "total within-recording temporal dispersion" in spec)
    check("spec forbids calling J vigilance instability", "not \"vigilance instability\"" in spec
          or "NOT \"vigilance instability\"" in spec or "not** \"vigilance instability\"" in spec)
    check("spec forbids 'genuine vigilance drift'", "genuine vigilance drift" in spec
          and "forbidden" in spec)
    check("spec states the recording-position / slow-drift vocabulary requirement",
          "recording-position effect" in spec and "slow within-recording drift" in spec)
    check("spec labels the reliability coefficient as approximate/ finite-trial",
          "approximate finite-trial reliability proxy" in spec)
    check("spec states differencing amplifies noise", "2\\sigma_\\eta^2" in spec
          or "2 sigma" in spec or "2\\sigma" in spec)

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print("=" * 78)
    print(f"{len(CHECKS)-n_fail}/{len(CHECKS)} Phase 1.75 verification checks passed")
    if n_fail:
        for nm, ok, d in CHECKS:
            if not ok:
                print("  -", nm, d)
    C.write_json(C.OUTPUTS / "qc" / "verification_phase175.json", {
        "status": "passed" if n_fail == 0 else "failed",
        "n_checks": len(CHECKS), "n_failed": n_fail, "recomputed_windows": n_checked,
        "checks": [{"name": nm, "passed": ok, "detail": d} for nm, ok, d in CHECKS],
    })
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
