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
import re
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
check("root README states the project began as NS-vs-SD classification",
      "began as a normal-sleep vs. sleep-deprivation EEG classification task" in texts["README.md"])
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
section("Corrected statuses (v2 canonicalization)")
# ---------------------------------------------------------------------------
# These two checks exist because an earlier public draft got BOTH of these wrong, in opposite
# directions. They are regression tests against re-introducing either error.

# (a) Phase 4A/4A2 must NOT be published as invalidated-by-contamination.
mask = load_json("functional_prediction/evidence/phase4a3/mask_definitive.json")
clean = load_json("functional_prediction/evidence/phase4a3/clean_standard_run.json")
check("Phase 4A3 records 0 of 82,550 gap rows inside any training mask",
      mask["total_gap_rows"] == 82550
      and mask["total_gap_rows_inside_phase4a_training_masks"] == 0
      and mask["total_gap_rows_inside_phase4a_test_masks"] == 0,
      f"gap={mask['total_gap_rows']} train={mask['total_gap_rows_inside_phase4a_training_masks']}")
delta = abs(clean["contamination_delta_population"]["mean_delta_R"])
check("the gap correction moves mean R by ~1e-15 (inert)", delta < 1e-12, f"|delta|={delta:.3e}")
for p in ["README.md", "functional_prediction/README.md"]:
    t = (ROOT / p).read_text(encoding="utf-8")
    check(f"{p} does NOT publish Phase 4A/4A2 as INVALIDATED",
          "INVALIDATED —" not in t and "**INVALIDATED**" not in t,
          "no bare INVALIDATED status label")
    check(f"{p} states the earlier results remain valid evidence", "remain valid" in t)

# (b) The calibrated adaptive null must be bounded by its own K.
null = load_json("functional_prediction/evidence/phase4a2/adaptive_null_summary_FORMAL.json")
check("adaptive calibrated null is K = 8 per participant",
      null["K_per_participant"] == 8 and null["K_achieved_min"] == 8,
      f"K={null['K_per_participant']}")
check("its p-value floor is 1/9, so it cannot resolve 5%",
      abs(null["calibrated_p_floor"] - 1 / 9) < 1e-9, f"floor={null['calibrated_p_floor']:.4f}")
check("no post-hoc null selection was used", null["null_chosen_post_hoc"] is False)
check("Phase 4A2 wording says 'no reliable positive effect', not 'disproven'",
      "NO RELIABLE POSITIVE EFFECT" in texts["functional_prediction/README.md"]
      and "definitively disproven" not in texts["functional_prediction/README.md"])

# (c) The TTA counts must be labelled as verification, not sample size.
check("root README separates verification counts from sample size",
      "not experimental sample size" in texts["README.md"]
      or "refer to implementation verification, not" in texts["README.md"])
check("root README states the real sample (68 x 3 x 4)",
      "68 subjects × 3 seeds × 4 arms" in texts["README.md"])
check("root README denies BatchNorm causation",
      "does not establish that BatchNorm is the causal mechanism" in texts["README.md"])
check("root README denies universal TENT collapse",
      "nor that TENT universally collapses on EEG" in texts["README.md"])

# (d) The lane-centre count must be 4 recordings, not 5.
check("root/branch README does not claim 5/5 sign agreement",
      "5/5" not in texts["functional_prediction/README.md"],
      "the sign test covers 4 recordings")

# (e) No license is claimed while provenance is unresolved.
check("README states no repository-wide license is assigned",
      "No repository-wide software license is currently granted" in texts["README.md"])
check("no LICENSE file is shipped",
      not (ROOT / "LICENSE").exists() and not (ROOT / "LICENSE.md").exists())
check("third-party provenance audit exists and flags mscvit",
      "NEEDS VERIFICATION" in (ROOT / "docs/third-party-provenance.md").read_text(encoding="utf-8"))

# (f) Legacy archive is complete and marked superseded.
legacy = ROOT / "archive/legacy/legacy_ns_sd_prototype"
check("legacy archive retains the original 备忘录.md (restored from commit 625dc3b)",
      (legacy / "备忘录.md").exists())
check("legacy archive retains the original baseline/README.md",
      (legacy / "baseline/README.md").exists())
check("legacy archive README marks it superseded",
      "superseded" in (legacy / "README.md").read_text(encoding="utf-8").lower())

# ---------------------------------------------------------------------------
section("Final-framing regression guards")
# ---------------------------------------------------------------------------
# Each guard below exists because a specific wrong sentence was actually shipped once, or was
# explicitly forbidden by the owner. They are STRING checks over documentation: the numbers they
# protect are checked numerically in the sections above. Keeping the two kinds separate is
# deliberate -- a string check can only catch wording drift, never a wrong number.

DOCS = {p: (ROOT / p).read_text(encoding="utf-8") for p in [
    "README.md", "functional_prediction/README.md", "tta_collapse/README.md",
    "docs/scientific-status.md", "docs/project-history.md", "docs/third-party-provenance.md",
    "docs/validation-protocols.md", "docs/data-boundaries.md",
]}
ALL_TEXT = "\n".join(DOCS.values())

# (g) TTA causal language: attribution yes, causation no.
for p in ["README.md", "functional_prediction/README.md", "tta_collapse/README.md",
          "docs/project-history.md"]:
    t = DOCS[p]
    check(f"{p}: does not claim the degradation IS CAUSED by normalization",
          "causes the degradation" not in t and "is caused by the normalization switch" not in t)
    check(f"{p}: does not assert harmful prediction collapse as the Phase 1 result",
          "harmful collapse was observed" not in t
          and "the model collapsed" not in t)
check("some public doc states the normalization switch is SUFFICIENT (the supported claim)",
      "sufficient to reproduce" in ALL_TEXT)
check("some public doc states the entropy gradient is inert",
      "entropy gradient is inert" in ALL_TEXT.lower() or "entropy gradient is **inert**" in ALL_TEXT)
check("some public doc denies BatchNorm causal status",
      "not establish that BatchNorm" in ALL_TEXT
      or "does not establish that BatchNorm" in ALL_TEXT)
check("some public doc states TTA mechanism is not yet established",
      "NOT YET ESTABLISHED" in ALL_TEXT or "not the mechanism underneath" in ALL_TEXT)

# (h) 816 must never be presented as a sample of participants.
check("816 is not presented as a participant/sample count",
      "816 participants" not in ALL_TEXT and "816 subjects" not in ALL_TEXT
      and "816-sample" not in ALL_TEXT)
check("816 is labelled as implementation verification / executed units",
      "implementation-verification counts" in ALL_TEXT
      or "implementation verification, not" in ALL_TEXT
      or "verification counts" in ALL_TEXT)
check("the real subject-level sample is stated",
      "68 subjects × 3 seeds × 4 arms" in ALL_TEXT and "n = 68" in ALL_TEXT)

# (i) The PVT negative must never be generalized.
#     The disclaimer exists in two equivalent forms; either is acceptable, but one must be present
#     in the docs that report the result, and no doc may assert the generalization as a finding.
check("public docs carry the PVT non-generalization disclaimer",
      ("not evidence that EEG can never predict PVT" in ALL_TEXT)
      or ("not evidence that EEG cannot predict PVT" in ALL_TEXT))
check("no bare assertion that EEG cannot predict PVT",
      "EEG cannot predict PVT." not in ALL_TEXT
      and "that EEG cannot predict PVT in general" in ALL_TEXT)
check("the PVT negative is scoped to representation/dataset/protocol",
      "representation-, task- and" in ALL_TEXT or "dataset and protocol" in ALL_TEXT)

# (j) Lane-centre sign test: derive the count from the artifact, then check the docs agree.
#     This is a CONTENT check, not a string check: the number of recordings is read from
#     lane_geometry.json, so if the artifact ever grows to 5 recordings this check changes with it
#     rather than silently going stale.
geo = load_json("functional_prediction/evidence/phase3c/lane_geometry.json")
recs = geo["recordings"]
n_sign_tested = 0
for _rid, blob in recs.items():
    sa = blob.get("geometry", {}).get("sign_agreement", {})
    if sa.get("4220_right_fires_with_LN_positive") == 1.0 and \
       sa.get("4230_left_fires_with_LN_negative") == 1.0:
        n_sign_tested += 1
check("lane_geometry.json carries exactly 4 sign-tested recordings", n_sign_tested == 4,
      f"n={n_sign_tested}")
check("lane-centre sign test is stated as 4 recordings, not 5",
      "4 audited lane-geometry recordings" in ALL_TEXT
      and "all 4 audited" in ALL_TEXT)
check("no public doc asserts 100% agreement in 5/5 recordings",
      "5/5 recordings" not in ALL_TEXT)
check("the two lane-coverage quantities are distinguished",
      "behavioural-audit scale" in ALL_TEXT)

# (k) Phase 4A/4A2 must not be described as contaminated or invalidated.
check("no public doc calls Phase 4A/4A2 contaminated results",
      "contaminated scientific result" not in ALL_TEXT
      and "contaminated results" not in ALL_TEXT)
check("no public doc restores a bare INVALIDATED status label",
      "INVALIDATED —" not in ALL_TEXT and "**INVALIDATED**" not in ALL_TEXT)
check("Phase 4A2 is never ASSERTED as definitively disproven",
      # Two legitimate appearances: inside an explicit negation ("is *not* \"definitively
      # disproven\"") and echoed in the forbidden-overclaim column of the status table. What must
      # never appear is an affirmative assertion.
      "is definitively disproven" not in ALL_TEXT
      and "was definitively disproven" not in ALL_TEXT
      and ALL_TEXT.count("definitively disproven") == 2,
      f"occurrences={ALL_TEXT.count('definitively disproven')} (expect 2, both non-assertive)")
check("the K=8 null limitation is stated where Phase 4A2 is reported",
      "K = 8" in ALL_TEXT or "K=8" in ALL_TEXT)

# (l) "published" must not be used for internal artifacts.
check("no public doc uses 'stand as published' for internal artifacts",
      "stand as published" not in ALL_TEXT and "stands as published" not in ALL_TEXT)
check("no public doc uses 'valid, published, closed'",
      "valid, published, closed" not in ALL_TEXT)
check("Phase 4A/4A2 status uses 'remain scientifically valid under their frozen protocols'",
      "remain scientifically" in ALL_TEXT)

# (m) Third-party: no blanket "referenced, not vendored".
check("no public doc claims blanket non-vendoring",
      "Third-party code is referenced, not vendored" not in ALL_TEXT)
check("the legacy third-party exception is disclosed in the root README",
      "legacy archive retains several historical third-party-derived components"
      in DOCS["README.md"])
check("no repository-wide license is asserted",
      "No repository-wide software license is currently granted" in DOCS["README.md"])
check("license and citation are separate sections/claims",
      "## License" in DOCS["README.md"] and "## Citation" in DOCS["README.md"])
check("citation correctness is decoupled from licensing",
      "Absence of\na license does not by itself prevent citation" in DOCS["README.md"]
      or "does not by itself prevent citation" in DOCS["README.md"])

# (n) The public status table must exist and carry the owner's rows.
check("root README has a Scientific Status table", "## Scientific Status" in DOCS["README.md"])
for row in ["VALID NEGATIVE / CLOSED", "VALIDATED FOR ENDPOINT ELIGIBILITY",
            "VALID EXECUTED EVIDENCE", "VALID EXECUTED / CLOSED", "NOT LICENSED",
            "EXECUTED / VERIFIED", "IN PROGRESS / NOT YET ESTABLISHED",
            "PARKED / NOT STARTED", "NOT DEMONSTRATED"]:
    check(f"status table carries '{row}'", row in DOCS["README.md"])

# (o) CASE 4 must not be the headline of the public result.
check("CASE 4 / Case 4 appears only as a parenthetical in the root README",
      DOCS["README.md"].count("Case 4") <= 1 and "CASE 4" not in DOCS["README.md"])
check("the meaning is stated before the label",
      "no harmful collapse" in DOCS["README.md"].lower()
      and "normalization-switch degradation established" in DOCS["README.md"])

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
