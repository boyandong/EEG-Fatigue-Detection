"""Phase 1 trajectory plots.

Prompt §21 requires participant heterogeneity to survive: every subject gets its own plot,
and the group median/IQR curve is ADDITIONAL, never a replacement.

  python 20_plots.py --variant NS_then_SD --seeds 0 1 2

Writes outputs/plots/:
  subject_<subject>_trajectory.png     per-subject, all three arms overlaid
  group_trajectory.png                 group median with IQR band
  group_delta_bacc_forest.png          per-subject dBAcc with the group CI
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))
import p1_arms as A        # noqa: E402
import p1_collapse as K    # noqa: E402

OUT = HERE / "outputs"
UNITS = OUT / "units"
PLOTS = OUT / "plots"

ARM_STYLE = {
    "source": ("tab:blue", "-"),
    "bn_only": ("tab:green", "--"),
    "tent_literal": ("tab:red", "-"),
    "tent_det": ("tab:orange", "--"),
}


def load(variant, arm, seed):
    out = {}
    for p in sorted(UNITS.glob(f"{variant}__{arm}__seed{seed}__*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["subject"]] = r
    return out


def traj_rows(res):
    rows = []
    by_batch = {}
    for w in res["window_rows"]:
        by_batch.setdefault(w["batch_index"], []).append(w)
    for b in res["batch_rows"]:
        ws = by_batch.get(b["batch_index"], [])
        if not ws:
            continue
        rows.append({"batch_index": b["batch_index"], **K.batch_row(
            [w["y_true"] for w in ws], [w["p_positive"] for w in ws]), **b})
    return rows


def cum_bacc(rows):
    ys, ps = [], []
    out = []
    for w in rows:
        ys.append(w["y_true"])
        ps.append(w["p_positive"])
        out.append(K._bacc(np.array(ys), (np.array(ps) >= 0.5).astype(int)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=A.PRIMARY_VARIANT)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOTS.mkdir(parents=True, exist_ok=True)
    data = {arm: {s: load(args.variant, arm, s) for s in args.seeds} for arm in A.ARMS}
    if not any(data[arm][args.seeds[0]] for arm in A.ARMS):
        print("no units found; nothing to plot (expected before the server run)")
        return 1
    subjects = sorted(set.intersection(
        *[set(data[arm][args.seeds[0]]) for arm in A.ARMS if data[arm][args.seeds[0]]]))
    if not subjects:
        subjects = sorted(data[A.ARMS[0]][args.seeds[0]])

    panels = ["H_cond", "H_marg", "dominant_share", "mean_max_conf", "q1"]
    group = {arm: {k: [] for k in panels} for arm in A.ARMS}

    for subject in subjects:
        fig, axes = plt.subplots(2, 3, figsize=(15, 7.5))
        for arm in A.ARMS:
            color, ls = ARM_STYLE[arm]
            series = {k: [] for k in panels}
            for seed in args.seeds:
                res = data[arm][seed].get(subject)
                if res is None:
                    continue
                rows = traj_rows(res)
                x = [r["batch_index"] for r in rows]
                for k in panels:
                    axes.flat[panels.index(k)].plot(x, [r[k] for r in rows], color=color,
                                                    ls=ls, alpha=0.45, lw=1)
                    series[k].append([r[k] for r in rows])
                # cumulative balanced accuracy is per WINDOW, so plot it against its own
                # window axis on the shared "batch" panel rather than against batch index
                cb = cum_bacc(res["window_rows"])
                if cb:
                    axes.flat[0].plot(
                        [i * len(x) / max(1, len(cb)) for i in range(len(cb))], cb,
                        color=color, ls=":", alpha=0.5, lw=1.2)
            for k in panels:
                if series[k]:
                    n = min(len(v) for v in series[k])
                    m = np.mean([v[:n] for v in series[k]], axis=0)
                    axes.flat[panels.index(k)].plot(range(n), m, color=color, ls=ls, lw=2,
                                                    label=arm)
                    group[arm][k].append(m)
        ym = {k: None for k in panels}
        for k in panels:
            vals = [v for arm in A.ARMS for v in group[arm][k]]
            if vals:
                n = min(len(v) for v in vals)
                ym[k] = (float(np.min([v[:n].min() for v in vals])),
                         float(np.max([v[:n].max() for v in vals])))
        for k in panels:
            ax = axes.flat[panels.index(k)]
            ax.set_title(k)
            ax.set_xlabel("stream batch")
            if ym[k]:
                lo, hi = ym[k]
                pad = 0.05 * (hi - lo + 1e-9)
                ax.set_ylim(lo - pad, hi + pad)
        axes.flat[5].axis("off")
        axes.flat[5].text(0.02, 0.6,
                          "panel 1 (H_cond) also carries\ncumulative balanced accuracy\n"
                          "(dotted, own window axis)",
                          fontsize=8, va="top")
        axes.flat[0].legend(fontsize=8)
        fig.suptitle(f"{subject}  |  {args.variant}  |  seeds {args.seeds}  |  "
                     f"thin = per-seed, thick = seed mean")
        fig.tight_layout()
        fig.savefig(PLOTS / f"subject_{subject}_trajectory.png", dpi=110)
        plt.close(fig)

    # group median / IQR over subjects
    for k in panels:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for arm in A.ARMS:
            curves = group[arm][k]
            if not curves:
                continue
            n = min(len(c) for c in curves)
            M = np.array([c[:n] for c in curves])
            med = np.median(M, axis=0)
            q1 = np.percentile(M, 25, axis=0)
            q3 = np.percentile(M, 75, axis=0)
            color, ls = ARM_STYLE[arm]
            ax.plot(range(n), med, color=color, ls=ls, lw=2, label=f"{arm} median")
            ax.fill_between(range(n), q1, q3, color=color, alpha=0.18)
        ax.set_title(f"group median / IQR across {len(subjects)} subjects: {k}")
        ax.set_xlabel("stream batch")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(PLOTS / f"group_trajectory_{k}.png", dpi=110)
        plt.close(fig)

    # forest plot of per-subject dBAcc
    cmp_path = OUT / "subject_level_comparison.csv"
    if cmp_path.exists():
        import csv

        rows = list(csv.DictReader(cmp_path.open(encoding="utf-8-sig")))
        d = [(r["subject"], float(r["delta_balanced_accuracy_tent"]),
              float(r["delta_balanced_accuracy_bn_only"])) for r in rows
             if r["delta_balanced_accuracy_tent"] not in ("", "None")]
        d.sort(key=lambda x: x[1])
        fig, ax = plt.subplots(figsize=(7, max(6, 0.16 * len(d))))
        y = np.arange(len(d))
        ax.barh(y - 0.2, [x[1] for x in d], height=0.4, color="tab:red", label="TENT - SOURCE")
        ax.barh(y + 0.2, [x[2] for x in d], height=0.4, color="tab:green", label="BN_ONLY - SOURCE")
        ax.set_yticks(y)
        ax.set_yticklabels([x[0] for x in d], fontsize=5)
        ax.axvline(0, color="k", lw=0.8)
        ax.set_xlabel("delta balanced accuracy")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(PLOTS / "group_delta_bacc_forest.png", dpi=110)
        plt.close(fig)

    print(f"wrote {len(list(PLOTS.glob('*.png')))} plots to {PLOTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
