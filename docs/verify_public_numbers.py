"""Verify every headline number in this repository's documentation against its artifact.

This is the public counterpart of the project's internal rule: *a claim is not accepted until a
separate script re-derives it*. It re-derives nothing from the pipeline -- it reads the published
evidence artifacts and asserts that the numbers printed in the READMEs are the numbers those
artifacts actually contain.

    python docs/verify_public_numbers.py

Exit code 0 = every documented number matches its artifact.

No dataset, no GPU and no network are required. This is the strongest check a reader can run from
a clone, and it is deliberately separate from the pipelines it audits.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def load_json(rel: str):
    return json.load(open(ROOT / rel, encoding="utf-8"))


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


TRUNK = "shared/ds004902_source_trunk/legacy_apparatus/outputs/source_only_500hz_v1"
TTA = "tta_collapse/evidence/metrics/KEY_FINDINGS.json"


def section(title: str) -> None:
    print()
    print(title)


# ---------------------------------------------------------------------------
section("Shared source trunk (README section 1)")
# ---------------------------------------------------------------------------
segs = list(csv.DictReader(open(ROOT / TRUNK / "segments.csv", encoding="utf-8-sig")))
subs = list(csv.DictReader(open(ROOT / TRUNK / "subjects.csv", encoding="utf-8-sig")))
chans = json.load(open(ROOT / TRUNK / "channels.json", encoding="utf-8"))
splits = json.load(open(ROOT / TRUNK / "splits.json", encoding="utf-8"))

included = [r for r in subs if r["included"].strip().lower() == "true"]
n_pos = sum(1 for r in segs if r["label"] == "1")
n_neg = sum(1 for r in segs if r["label"] == "0")

check("68 valid paired subjects of 71", len(included) == 68 and len(subs) == 71,
      f"included={len(included)} total={len(subs)}")
check("9,390 four-second windows", len(segs) == 9390, f"rows={len(segs)}")
check("class 0 = 4,735 / class 1 = 4,655", n_neg == 4735 and n_pos == 4655,
      f"0={n_neg} 1={n_pos}")
check("61 channels", len(chans) == 61, f"n={len(chans)}")
check("500 Hz only", all(r["sfreq"] == "500" for r in segs))
check("68-fold subject LOSO", len(splits["folds"]) == 68, f"folds={len(splits['folds'])}")
check("split seed 20260908", splits["split_seed"] == 20260908, str(splits["split_seed"]))

check("segments.csv anchor SHA-256 (as documented in REPRODUCIBILITY.md)",
      sha256(f"{TRUNK}/segments.csv") == "5eba619fc0dd516f8caf72a86fd36a34ca07c589df9d269b2bcdbd53c1c3a744")
check("splits.json anchor SHA-256 (as documented in REPRODUCIBILITY.md)",
      sha256(f"{TRUNK}/splits.json") == "db02bab96f8147bffa4836967a29c0763bc9f8130fa994252ed269649070c184")

vr = load_json(f"{TRUNK}/verification.json")
check("trunk build verification record says 'passed'", vr["status"] == "passed", vr["status"])
check("verification record agrees: 68 / 9390 / 68",
      vr["subjects"] == 68 and vr["segments"] == 9390 and vr["folds"] == 68)

# ---------------------------------------------------------------------------
section("Historical EEGNet source-only benchmark (README section 1)")
# ---------------------------------------------------------------------------
tta = load_json(TTA)
src = tta["absolute_levels"]["source"]
for name, doc in [("accuracy", 0.5963), ("balanced_accuracy", 0.5924),
                  ("f1", 0.5550), ("roc_auc", 0.6109)]:
    check(f"EEGNet {name} = {doc}", round(src[name], 4) == doc, f"artifact={src[name]}")
check("SOURCE balanced accuracy reproduces the historical value to 16 digits",
      src["balanced_accuracy"] == 0.5924169784325324, repr(src["balanced_accuracy"]))

# ---------------------------------------------------------------------------
section("Branch A -- the ds004902 M -> PVT NEGATIVE result (README section 2.1)")
# ---------------------------------------------------------------------------
perm = load_json("functional_prediction/evidence/phase2/permutation_summary.json")
p2 = load_json("functional_prediction/evidence/phase2/phase2_summary.json")
check("Q2_skill(M1) = -0.0574", round(perm["q2_observed"], 4) == -0.0574, str(perm["q2_observed"]))
check("permutation p = 0.7445", round(perm["p_perm"], 4) == 0.7445, str(perm["p_perm"]))
check("n = 29 subjects", p2["n_subjects"] == 29, str(p2["n_subjects"]))
check("5,000 permutations, seed 20260916",
      perm["n_perm"] == 5000 and perm["seed"] == 20260916)
check("null mean = -0.0361 (null is centred NEGATIVE)", round(perm["null_mean"], 4) == -0.0361,
      str(perm["null_mean"]))
check("null SD = 0.0648", round(perm["null_sd"], 4) == 0.0648, str(perm["null_sd"]))
check("fraction of null replicates > 0 = 0.1528", round(perm["frac_null_positive"], 4) == 0.1528)
check("inference re-runs the whole pipeline per replicate",
      "outer LOSO + inner LOSO" in perm["each_replicate"])

# ---------------------------------------------------------------------------
section("Branch B -- TTA Phase 1 verdict (README section 3)")
# ---------------------------------------------------------------------------
check("verdict is CASE 4 - BN/NORMALIZATION INSTABILITY",
      tta["verdict"]["case"] == "CASE 4 - BN/NORMALIZATION INSTABILITY", tta["verdict"]["case"])

lv, dl = tta["absolute_levels"], tta["deltas_vs_source"]
for arm, doc in [("bn_only", 0.5039), ("tent_literal", 0.5043), ("tent_det", 0.5035)]:
    check(f"{arm} balanced accuracy = {doc}", round(lv[arm]["balanced_accuracy"], 4) == doc,
          str(round(lv[arm]["balanced_accuracy"], 4)))
for arm, doc in [("bn_only", -0.0886), ("tent_literal", -0.0881), ("tent_det", -0.0889)]:
    check(f"{arm} delta balanced accuracy = {doc}", round(dl[arm]["bacc"]["mean"], 4) == doc,
          str(round(dl[arm]["bacc"]["mean"], 4)))
for arm, lo_doc, hi_doc in [("bn_only", -0.1253, -0.0520), ("tent_literal", -0.1248, -0.0510),
                            ("tent_det", -0.1258, -0.0522)]:
    lo, hi = dl[arm]["bacc"]["ci_low"], dl[arm]["bacc"]["ci_high"]
    check(f"{arm} 95% CI = [{lo_doc}, {hi_doc}]",
          round(lo, 4) == lo_doc and round(hi, 4) == hi_doc, f"[{lo:.4f}, {hi:.4f}]")

lm = tta["literal_minus_bn_only_bacc"]
check("TENT_LITERAL - BN_ONLY = +0.00048 (entropy gradient inert)",
      round(lm["mean"], 5) == 0.00048, str(lm["mean"]))
check("paired contrast t = +0.22", abs(lm["t"] - 0.22) < 0.005, str(lm["t"]))
dis = tta["arm_to_arm_prediction_disagreement"]["bn_only_vs_tent_det"]
check("BN_ONLY vs TENT_DET agree on 99.65% of windows",
      abs(dis - 0.00348) < 0.0001, f"agreement={(1 - dis) * 100:.2f}%")

check("all four arms x 68 subjects x 3 seeds = 816 units executed",
      tta["execution"]["units"] == 816 and tta["execution"]["units_per_arm"] == 204)
check("68 subjects, seeds [0, 1, 2]",
      tta["execution"]["subjects"] == 68 and tta["execution"]["seeds"] == [0, 1, 2])
check("112,680 windows scored", tta["execution"]["windows_scored"] == 112680,
      str(tta["execution"]["windows_scored"]))
check("independent verifier 105/105", tta["verification"]["verifier"] == "105/105")
check("negative controls 75/75 bite", tta["verification"]["controls"] == "75/75 bite")
check("remote SOURCE closure 9.537e-07, 0 label flips",
      "9.537e-07" in tta["verification"]["remote_source_closure"] and
      "0 label flips" in tta["verification"]["remote_source_closure"])
check("0 subjects strongly harmed (no harmful collapse)",
      tta["verdict"]["n_strongly_harmed_subjects"] == 0)
for k in ("tent_literal_collapse", "tent_det_collapse", "bn_only_collapse"):
    check(f"verdict asserts {k} = false", tta["verdict"][k] is False)

# The two directional facts that make the verdict 'no collapse' rather than 'collapse'.
lq = tta["last_quartile"]
check("dominant-class share FALLS 0.7104 -> ~0.542 (opposite of collapse)",
      round(lq["last_dominant_share_source"], 4) == 0.7104
      and lq["last_dominant_share_bn_only"] < lq["last_dominant_share_source"],
      f"{lq['last_dominant_share_source']:.4f} -> {lq['last_dominant_share_bn_only']:.4f}")
check("marginal entropy RISES 0.5358 -> ~0.686 (opposite of collapse)",
      round(lq["last_H_marg_source"], 4) == 0.5358
      and lq["last_H_marg_tent_literal"] > lq["last_H_marg_source"],
      f"{lq['last_H_marg_source']:.4f} -> {lq['last_H_marg_tent_literal']:.4f}")

# ---------------------------------------------------------------------------
section("Checkpoint manifest (checkpoints/README.md)")
# ---------------------------------------------------------------------------
ck = list(csv.DictReader(open(ROOT / "shared/ds004902_source_trunk/checkpoints/CHECKPOINT_MANIFEST.csv",
                             encoding="utf-8-sig")))
check("204 checkpoints = 68 subjects x 3 seeds", len(ck) == 204, f"rows={len(ck)}")
check("204 distinct SHA-256 (no duplicate contents)",
      len({r["sha256_best_pt"] for r in ck}) == 204)
check("seeds are exactly {0, 1, 2}", sorted({r["seed"] for r in ck}) == ["0", "1", "2"])
check("naming convention eegnet/sub-NN/seed_S/best.pt",
      all(r["dir"].endswith(f"{r['test_subject']}/seed_{r['seed']}") for r in ck))
check("no checkpoint bytes are shipped (manifest only)",
      not list((ROOT / "shared/ds004902_source_trunk/checkpoints").glob("**/*.pt")))

# ---------------------------------------------------------------------------
section("Branch independence governance")
# ---------------------------------------------------------------------------
texts = {p: (ROOT / p).read_text(encoding="utf-8") for p in
         ["README.md", "functional_prediction/README.md", "tta_collapse/README.md"]}
check("both branch READMEs state they are independent",
      "independent" in texts["functional_prediction/README.md"]
      and "independent" in texts["tta_collapse/README.md"])
check("root README states the repository evolved from NS-vs-SD",
      "evolved from an NS-vs-SD" in texts["README.md"])
check("Branch A README presents the PVT result as a NEGATIVE",
      "NEGATIVE" in texts["functional_prediction/README.md"])
check("Branch A README warns that both Phase 4A readings must travel together",
      "Both readings must travel together" in texts["functional_prediction/README.md"])
check("Branch B README forbids calling TENT_DET canonical TENT",
      "never called canonical TENT" in texts["tta_collapse/README.md"].lower()
      or "TENT_DET` called \"canonical TENT\"" in texts["tta_collapse/README.md"])
check("Branch B README records the parked methods as not started",
      "not started" in texts["tta_collapse/README.md"])

# ---------------------------------------------------------------------------
print()
print("=" * 72)
if FAILURES:
    print(f"{CHECKS - len(FAILURES)}/{CHECKS} checks passed; {len(FAILURES)} FAILED:")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print(f"ALL {CHECKS}/{CHECKS} documented numbers and claims verified against their artifacts.")
print("=" * 72)
