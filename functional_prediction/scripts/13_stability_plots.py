"""13 - Phase 1.5 plots.

    python project/vigilance_generalization_v1/scripts/13_stability_plots.py

Outputs (outputs/stability_v1/plots/):
  stability_vs_duration.png       Spearman / nMAE / ICC trend across durations, M vs J
  bland_altman_<feature>_<dur>.png  agreement plots for every feature x primary duration
  position_drift_traces.png       early -> middle -> late trajectories
  finite_sample_J.png             relative SD of the sample SD vs k, model vs empirical
  accumulation_convergence.png    prefix-vs-full convergence, labelled as contained
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
import stability as ST  # noqa: E402
from roi import REGION_NAMES  # noqa: E402

PRIMARY_DURS = ("k8", "k15", "k30")
DUR_SECONDS = {"k4": 16, "k8": 32, "k15": 60, "k30": 120}


def main() -> None:
    out = C.OUTPUTS / "stability_v1"
    plots = out / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    dur = C.read_csv(out / "duration_summary.csv")
    ddur = C.read_csv(out / "delta_duration_summary.csv")
    pos = C.read_csv(out / "position_drift.csv")
    acc = C.read_csv(out / "accumulation_convergence.csv")
    fs = C.read_csv(out / "finite_sample_J_simulation.csv")
    sess = C.read_csv(out / "session_window_features.csv")

    def fnum(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return np.nan

    xs = [DUR_SECONDS[d] for d in ("k4", "k8", "k15", "k30")]

    # ---------------------------------------------------------------- 1. trend
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, metric, label in zip(axes, ("spearman_rho", "nmae", "icc_2_1"),
                                 ("Spearman rho between disjoint windows",
                                  "nMAE = median|d| / IQR(population)",
                                  "ICC(2,1) [secondary]")):
        for fam, style in (("M", "-o"), ("J", "--s")):
            for region in REGION_NAMES:
                vals = []
                for d in ("k4", "k8", "k15", "k30"):
                    row = next((r for r in dur if r["feature"] == f"{fam}_{region}" and r["duration"] == d), None)
                    vals.append(fnum(row[metric]) if row else np.nan)
                ax.plot(xs, vals, style, alpha=0.75, label=f"{fam}_{region}")
        ax.set_xlabel("window length (seconds)")
        ax.set_ylabel(label)
        ax.set_title(label.split("=")[0].strip())
        ax.grid(alpha=0.3)
    axes[0].axhline(0.0, color="k", lw=0.8)
    axes[0].legend(fontsize=7, ncol=2)
    axes[1].axhline(1.0, color="r", lw=0.8, ls=":")
    axes[1].text(xs[0], 1.02, "error = population spread", fontsize=7, color="r")
    fig.suptitle("Phase 1.5  within-session estimator stability vs window length "
                 "(J is noisier than M, as predicted)", fontsize=11)
    fig.tight_layout()
    fig.savefig(plots / "stability_vs_duration.png", dpi=150)
    plt.close(fig)

    # ---------------------------------------------------------------- 2. Bland-Altman
    # Pairwise differences are rebuilt directly from the window table (first two disjoint
    # windows of every recording), one panel per primary duration.
    for feature in ST.SESSION_FEATURES:
        fig, axes = plt.subplots(1, len(PRIMARY_DURS), figsize=(14.5, 4.2), sharey=True)
        for ax, d in zip(np.atleast_1d(axes), PRIMARY_DURS):
            by_rec: dict = {}
            for r in sess:
                if r["duration"] != d:
                    continue
                by_rec.setdefault((r["subject"], r["session"]), []).append(r)
            a, b = [], []
            for rows in by_rec.values():
                rows = sorted(rows, key=lambda r: int(r["window_index"]))
                v = np.array([fnum(r[feature]) for r in rows], float)
                v = v[np.isfinite(v)]
                if v.size < 2:
                    continue
                a.append(v[0]); b.append(v[1])
            a = np.array(a); b = np.array(b)
            if a.size < 3:
                ax.set_visible(False)
                continue
            mean = (a + b) / 2.0
            diff = a - b
            ax.scatter(mean, diff, s=12, alpha=0.6)
            ax.axhline(np.median(diff), color="k", lw=1.2, label=f"median diff {np.median(diff):+.3f}")
            ax.axhline(np.percentile(diff, 2.5), color="r", ls="--", lw=1)
            ax.axhline(np.percentile(diff, 97.5), color="r", ls="--", lw=1,
                       label="empirical 2.5-97.5%")
            ax.set_title(f"{d} = {DUR_SECONDS[d]} s   n={a.size}")
            ax.set_xlabel("mean of the two windows")
            ax.grid(alpha=0.3)
            ax.legend(fontsize=7)
        axes[0].set_ylabel("window1 - window2")
        fig.suptitle(f"Bland-Altman (disjoint windows): {feature}", fontsize=11)
        fig.tight_layout()
        fig.savefig(plots / f"bland_altman_{feature}.png", dpi=150)
        plt.close(fig)

    # ---------------------------------------------------------------- 3. position drift
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    ax = axes[0]
    for region in REGION_NAMES:
        vals = [fnum(next((r for r in pos if r["feature"] == f"M_{region}"
                           and r["duration"] == "k15" and r["comparison"] == "early-late"), {}).get("mean_difference"))
                for _ in [0]]
        ax.plot([0, 1, 2], [0, fnum(next((r for r in pos if r["feature"] == f"M_{region}" and r["duration"] == "k15"
                                          and r["comparison"] == "early-middle"), {}).get("mean_difference", np.nan)),
                           fnum(next((r for r in pos if r["feature"] == f"M_{region}" and r["duration"] == "k15"
                                      and r["comparison"] == "early-late"), {}).get("mean_difference", np.nan))],
                "-o", label=f"M_{region}")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["early", "middle", "late"])
    ax.set_ylabel("mean change from early window")
    ax.set_title("M: no systematic position drift")
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax = axes[1]
    for region in REGION_NAMES:
        ax.plot([0, 1, 2], [0, fnum(next((r for r in pos if r["feature"] == f"J_{region}" and r["duration"] == "k15"
                                          and r["comparison"] == "early-middle"), {}).get("mean_difference", np.nan)),
                           fnum(next((r for r in pos if r["feature"] == f"J_{region}" and r["duration"] == "k15"
                                      and r["comparison"] == "early-late"), {}).get("mean_difference", np.nan))],
                "-o", label=f"J_{region}")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["early", "middle", "late"])
    ax.set_ylabel("mean change from early window")
    ax.set_title("J: systematic increase with recording position (k15 = 60 s)")
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle("Experiment B - recording-position sensitivity (135 sessions)", fontsize=11)
    fig.tight_layout()
    fig.savefig(plots / "position_drift_traces.png", dpi=150)
    plt.close(fig)

    # ---------------------------------------------------------------- 4. finite-sample J
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ks = sorted({int(r["k"]) for r in fs})
    for model, style in (("gaussian", "-o"), ("student_t_nu5", "--s"),
                         ("real_empirical_bootstrap", ":^")):
        sub = [r for r in fs if r["model"] == model and r["region"] == "CT"]
        sub = sorted(sub, key=lambda r: int(r["k"]))
        if sub:
            ax.plot([int(r["k"]) for r in sub], [fnum(r["relative_sd"]) for r in sub], style, label=model)
    ax.axhline(0.2, color="r", ls=":", lw=1)
    ax.text(ks[0], 0.205, "20% relative uncertainty", color="r", fontsize=8)
    emp = sorted([r for r in dur if r["feature"] == "J_CT"], key=lambda r: DUR_SECONDS.get(r["duration"], 999))
    ex = [DUR_SECONDS[r["duration"]] for r in emp if r["duration"] in DUR_SECONDS]
    ey = [np.sqrt(max(0.0, (1.0 - fnum(r["spearman_rho"])) / (1.0 + fnum(r["spearman_rho"])))) for r in emp
          if r["duration"] in DUR_SECONDS]
    ax.plot(ex, ey, "-D", color="k", label="empirical J_CT (from Spearman)")
    ax.set_xlabel("epochs per window (k)" if False else "k (epochs per window)")
    ax.set_ylabel("relative SD of the J estimate")
    ax.set_title("Finite-sample behaviour of J (CT region)")
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plots / "finite_sample_J.png", dpi=150)
    plt.close(fig)

    # ---------------------------------------------------------------- 5. accumulation
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for fam, style in (("M", "-o"), ("J", "--s")):
        for region in REGION_NAMES:
            sub = [r for r in acc if r["feature"] == f"{fam}_{region}" and r["duration"] in DUR_SECONDS]
            sub = sorted(sub, key=lambda r: DUR_SECONDS[r["duration"]])
            ax.plot([DUR_SECONDS[r["duration"]] for r in sub], [fnum(r["spearman_rho"]) for r in sub],
                    style, alpha=0.8, label=f"{fam}_{region}")
    ax.set_xlabel("prefix length (seconds)")
    ax.set_ylabel("Spearman rho vs full session")
    ax.set_title("Experiment C - accumulation/convergence\n(prefix is CONTAINED in the full value: "
                 "this is convergence, not independent agreement)", fontsize=9)
    ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(plots / "accumulation_convergence.png", dpi=150)
    plt.close(fig)

    made = sorted(p.name for p in plots.glob("*.png"))
    print(f"wrote {len(made)} plots to outputs/stability_v1/plots/")
    for m in made:
        print("  ", m)


if __name__ == "__main__":
    main()
