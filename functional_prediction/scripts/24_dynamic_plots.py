"""24 - Phase 1.75 plots.

    python project/vigilance_generalization_v1/scripts/24_dynamic_plots.py

Outputs (outputs/dynamic_audit/plots/ and outputs/pvt_psychometrics/plots/):
  stability_J_V_Jres.png       disjoint-window agreement vs duration, four observables
  position_bias_comparison.png early->late standardised bias per observable
  burnin_duration_grid.png     stability and usability across Protocol(B,T)
  local_volatility_scaling.png V vs J response to a slow linear trend (1/N scaling)
  pvt_target_uncertainty.png   per-subject point estimate +/- bootstrap SE, both targets
  pvt_split_half.png           odd vs even interleaved split-half agreement
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import dynamic_mechanism as DM  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

DYN = ("J", "V", "Jres")
ALLF = ("M", "J", "V", "Jres")
DUR_SECONDS = {"k4": 16, "k8": 32, "k15": 60, "k30": 120}
STYLE = {"M": "-o", "J": "--s", "V": ":^", "Jres": "-.d"}


def n(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def main() -> None:
    da = C.OUTPUTS / "dynamic_audit"
    pp = C.OUTPUTS / "pvt_psychometrics"
    (da / "plots").mkdir(parents=True, exist_ok=True)
    (pp / "plots").mkdir(parents=True, exist_ok=True)
    stab = C.read_csv(da / "stability_comparison.csv")
    pos = C.read_csv(da / "position_effect_comparison.csv")
    grid = C.read_csv(da / "burnin_duration_grid.csv")
    unc = C.read_csv(pp / "pvt_target_uncertainty.csv")
    sh = C.read_csv(pp / "pvt_split_half.csv")

    xs = [DUR_SECONDS[d] for d in ("k4", "k8", "k15", "k30")]

    # ------------------------------------------------------------ 1. stability
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))
    for fam in ALLF:
        for ax, metric, lab in ((axes[0], "spearman_rho", "Spearman rho (disjoint windows)"),
                                (axes[1], "nmae", "nMAE = med|d| / IQR(population)")):
            vals = []
            for d in ("k4", "k8", "k15", "k30"):
                v = [n(r[metric]) for r in stab if r["family"] == fam and r["duration"] == d]
                vals.append(np.nanmean(v) if v else np.nan)
            ax.plot(xs, vals, STYLE[fam], alpha=0.85, label=fam)
            ax.set_xlabel("window length (s)")
            ax.set_ylabel(lab)
            ax.grid(alpha=0.3)
    axes[0].axhline(0, color="k", lw=0.8)
    axes[0].legend(fontsize=8, ncol=2)
    axes[1].axhline(1.0, color="r", ls=":", lw=1)
    axes[1].text(xs[0], 1.02, "error = population spread", fontsize=7, color="r")
    fig.suptitle("Phase 1.75  session-level estimator stability: M vs J vs V vs J_res "
                 "(68 subjects / 136 sessions, 3 ROIs averaged)", fontsize=10)
    fig.tight_layout()
    fig.savefig(da / "plots" / "stability_J_V_Jres.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------ 2. position bias
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    width = 0.2
    xpos = np.arange(3)
    for k, fam in enumerate(ALLF):
        vals = []
        for d in ("k8", "k15", "k30"):
            v = [n(r["cohen_dz"]) for r in pos
                 if r["family"] == fam and r["duration"] == d and r["comparison"] == "early-late"]
            vals.append(np.nanmean(np.abs(v)) if v else np.nan)
        ax.bar(xpos + (k - 1.5) * width, vals, width, label=fam)
    ax.set_xticks(xpos); ax.set_xticklabels(["32 s", "60 s", "120 s"])
    ax.set_ylabel("|Cohen dz|  early -> late")
    ax.set_title("Recording-position effect by observable\n"
                 "(systematic early->late bias; M is position-stable, all dynamic observables are not)",
                 fontsize=9)
    ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(da / "plots" / "position_bias_comparison.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------ 3. protocol grid
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))
    labels = [r["protocol"] for r in grid]
    Bs = [int(r["burnin_seconds"]) for r in grid]
    rho = [n(r["mean_rho_session_disjoint"]) for r in grid]
    prho = [n(r["mean_rho_paired_disjoint"]) for r in grid]
    sign = [n(r["mean_sign_agreement_vs_full"]) for r in grid]
    ns = [int(r["n_subjects_with_2plus_paired"]) for r in grid]
    x = np.arange(len(labels))
    ax = axes[0]
    ax.plot(x, rho, "-o", label="disjoint rho (session)")
    ax.plot(x, prho, "--s", label="disjoint rho (paired delta)")
    ax.plot(x, sign, ":^", label="sign agreement vs full")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("stability"); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Protocol(B,T): stability", fontsize=10)
    ax = axes[1]
    colors = ["tab:blue" if b == 0 else "tab:orange" if b == 32 else "tab:green" for b in Bs]
    ax.bar(x, ns, color=colors)
    ax.axhline(29, color="r", ls="--", lw=1)
    ax.text(0, 30, "all 29 PVT-paired subjects", color="r", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("subjects with >=2 paired windows")
    ax.set_title("Protocol(B,T): usable n  (blue B=0, orange B=32, green B=60)", fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    fig.suptitle("Phase 1.75  burn-in x measurement-duration audit", fontsize=11)
    fig.tight_layout()
    fig.savefig(da / "plots" / "burnin_duration_grid.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------ 4. V vs J scaling
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    Ns = np.arange(8, 121)
    ramp_J = np.array([np.linspace(0, 1, N).std(ddof=1) for N in Ns])
    ramp_V = np.array([DM.local_volatility(np.linspace(0, 1, N)) for N in Ns])
    ax = axes[0]
    ax.plot(Ns, ramp_J, "-", label="J  (SD of S)")
    ax.plot(Ns, ramp_V, "--", label="V  (local volatility)")
    ax.set_xlabel("epochs in window (N)"); ax.set_ylabel("value on a unit linear ramp")
    ax.set_yscale("log"); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Response to a slow linear trend:\nJ is N-invariant, V falls as 1/N", fontsize=9)
    ax = axes[1]
    ax.plot(Ns, ramp_V / ramp_J, "-", color="k")
    ax.set_xlabel("epochs in window (N)"); ax.set_ylabel("V / J on a linear ramp")
    ax.grid(alpha=0.3)
    ax.set_title("V's sensitivity to slow drift relative to J\n"
                 f"at N=70 (280 s): V/J = {DM.local_volatility(np.linspace(0,1,70))/np.linspace(0,1,70).std(ddof=1):.4f}",
                 fontsize=9)
    fig.suptitle("Local volatility is a genuinely different estimator, not a rescaling of J", fontsize=10)
    fig.tight_layout()
    fig.savefig(da / "plots" / "local_volatility_scaling.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------ 5. PVT uncertainty
    order = sorted(unc, key=lambda r: n(r["Y_RT_point"]))
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), sharey=False)
    for ax, pre, lab in ((axes[0], "Y_RT", "Y_RT = ln(median RT_SD / median RT_NS)"),
                         (axes[1], "Y_speed", "Y_speed = ln(speed_NS / speed_SD)")):
        x = np.arange(len(order))
        p = np.array([n(r[f"{pre}_point"]) for r in order])
        se = np.array([n(r[f"{pre}_se"]) for r in order])
        ax.errorbar(x, p, yerr=1.96 * se, fmt="o", ms=3, lw=0.8, capsize=2, alpha=0.8)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_xlabel("subjects (sorted)")
        ax.set_ylabel(lab.split("=")[0].strip())
        ax.set_title(f"{pre}: point estimate ± 95% bootstrap CI\n"
                     f"mean SE = {np.nanmean(se):.4f}, sd(point) = {np.nanstd(p, ddof=1):.4f}", fontsize=9)
        ax.grid(alpha=0.3)
    fig.suptitle("PVT change-score finite-trial uncertainty (29 subjects, 5000 within-session "
                 "trial bootstraps)", fontsize=10)
    fig.tight_layout()
    fig.savefig(pp / "plots" / "pvt_target_uncertainty.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------ 6. split-half
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, po, pe, lab in ((axes[0], "Y_RT_odd", "Y_RT_even", "Y_RT"),
                            (axes[1], "Y_speed_odd", "Y_speed_even", "Y_speed")):
        a = np.array([n(r[po]) for r in sh]); b = np.array([n(r[pe]) for r in sh])
        ok = np.isfinite(a) & np.isfinite(b)
        a, b = a[ok], b[ok]
        ax.scatter(a, b, s=18, alpha=0.75)
        lim = [min(a.min(), b.min()) - 0.05, max(a.max(), b.max()) + 0.05]
        ax.plot(lim, lim, "k--", lw=0.8)
        ax.axhline(0, color="grey", lw=0.6); ax.axvline(0, color="grey", lw=0.6)
        rho = np.corrcoef(a, b)[0, 1]
        ax.set_xlabel(f"{lab} odd trials"); ax.set_ylabel(f"{lab} even trials")
        ax.set_title(f"{lab}: interleaved split-half\nPearson r = {rho:.3f}", fontsize=9)
        ax.grid(alpha=0.3)
    fig.suptitle("PVT target interleaved (odd/even) split-half agreement, n = 29", fontsize=10)
    fig.tight_layout()
    fig.savefig(pp / "plots" / "pvt_split_half.png", dpi=150)
    plt.close(fig)

    made = sorted(p.name for p in (da / "plots").glob("*.png")) + \
           sorted("pvt_psychometrics/" + p.name for p in (pp / "plots").glob("*.png"))
    print(f"wrote {len(made)} plots:")
    for m in made:
        print("  ", m)


if __name__ == "__main__":
    main()
