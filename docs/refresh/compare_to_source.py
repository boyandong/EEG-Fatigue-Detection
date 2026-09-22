"""Compare the public snapshot against the local scientific source tree, path by path.

Produces the authoritative "what actually changed" list for the refresh diff report:
  - files byte-identical to their local source  (the overwhelming majority)
  - files that were edited (sanitization only, declared)
  - files that are new in the public snapshot (documentation written for publication)
  - files present locally but not published (by design)

    python docs/refresh/compare_to_source.py <local_repo_root>

Exit code 0 always; this is a reporting tool, not a gate.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

PUB = pathlib.Path(__file__).resolve().parents[2]
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                   r"<WORKSPACE>\project\srtp")


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# Map: public path -> local source path. Anything not listed is "new".
PAIRS: list[tuple[str, str]] = []


def add(pub: str, src_rel: str) -> None:
    PAIRS.append((pub, src_rel))


TRUNK = "shared/ds004902_source_trunk"
LA = f"{TRUNK}/legacy_apparatus"
OUT = f"{LA}/outputs/source_only_500hz_v1"

for f in ["prepare_data.py", "run_baselines.py", "verify_data.py", "verify_baselines.py",
          "verify_portable_bundle.py", "download_sources.py", "BASELINES.md", "SOURCE_AUDIT.md",
          "requirements.txt", "requirements-train.txt"]:
    add(f"{LA}/{f}", f"{LA.replace('/', chr(92))}\\{f}")
add(f"{LA}/configs/baselines.json", f"{LA}\\configs\\baselines.json")
add(f"{LA}/configs/source_only_data.json", f"{LA}\\configs\\source_only_data.json")
for f in ["segments.csv", "segments_all.csv", "splits.json", "channels.json", "subjects.csv",
          "recordings.csv", "config.json", "provenance.json", "verification.json"]:
    add(f"{OUT}/{f}", f"{OUT}\\{f}")
add(f"{TRUNK}/third_party/sources.json", f"{TRUNK}\\third_party\\sources.json")
add(f"{TRUNK}/third_party/tent_official_commit.json", f"{TRUNK}\\third_party\\tent_official_commit.json")

FP = "functional_prediction"
for f in ["PHASE1_REPORT.md", "PHASE1_5_REPORT.md", "PHASE1_75_REPORT.md", "PHASE2_REPORT.md",
          "PHASE3_DATASET_AUDIT.md", "PHASE3C_BEHAVIOR_ENDPOINT_REPORT.md", "SCIENTIFIC_SPEC.md",
          "BEHAVIOR_ENDPOINT_SPEC.md", "research_tree.md", "official_raw_recovery_plan.md",
          "paper_sample_reconciliation.md"]:
    add(f"{FP}/{f}", f"{FP}\\{f}")
add(f"{FP}/phase3_metadata_survey_2026.md", f"{FP}\\docs\\phase3_metadata_survey_2026.md")
add(f"{FP}/config/dataset_ds004902.yaml", f"{FP}\\config\\dataset_ds004902.yaml")
add(f"{FP}/config/mechanism_v1.yaml", f"{FP}\\config\\mechanism_v1.yaml")
# branch READMEs exist locally but were rewritten for publication: report them as edited, not new.
add(f"{FP}/README.md", f"{FP}\\README.md")

for sub in ["src", "scripts", "tests"]:
    for p in sorted((SRC / FP / sub).glob("*.py")):
        add(f"{FP}/{sub}/{p.name}", f"{FP}\\{sub}\\{p.name}")

# evidence
for pub_dir, src_dir in [
    (f"{FP}/evidence/pvt", f"{FP}\\outputs\\pvt"),
    (f"{FP}/evidence/phase2", f"{FP}\\outputs\\phase2"),
    (f"{FP}/evidence/paper_reference", f"{FP}\\outputs\\paper_reference"),
    (f"{FP}/evidence/manifests", f"{FP}\\outputs\\manifests"),
]:
    for p in sorted((SRC / src_dir).glob("*")):
        if p.is_file():
            add(f"{pub_dir}/{p.name}", f"{src_dir}\\{p.name}")
for p in sorted((SRC / FP / "outputs" / "dynamic_audit").glob("*.csv")):
    add(f"{FP}/evidence/dynamic_audit/{p.name}", f"{FP}\\outputs\\dynamic_audit\\{p.name}")

TTA = "tta_collapse"
for p in sorted((SRC / TTA).glob("*.py")):
    add(f"{TTA}/{p.name}", f"{TTA}\\{p.name}")
for p in sorted((SRC / TTA).glob("*.md")):
    add(f"{TTA}/{p.name}", f"{TTA}\\{p.name}")
for sub in ["src", "tests"]:
    for p in sorted((SRC / TTA / sub).glob("*.py")):
        add(f"{TTA}/{sub}/{p.name}", f"{TTA}\\{sub}\\{p.name}")
for p in sorted((SRC / TTA / "outputs").glob("*.csv")):
    add(f"{TTA}/evidence/metrics/{p.name}", f"{TTA}\\outputs\\{p.name}")
for p in sorted((SRC / TTA / "outputs").glob("*.json")):
    if p.name == "remote_state.json":
        continue
    add(f"{TTA}/evidence/metrics/{p.name}", f"{TTA}\\outputs\\{p.name}")
for p in sorted((SRC / TTA / "outputs" / "plots").glob("*.png")):
    add(f"{TTA}/evidence/plots/{p.name}", f"{TTA}\\outputs\\plots\\{p.name}")
for p in sorted((SRC / TTA / "outputs" / "units").glob("*.json")):
    add(f"{TTA}/evidence/units/units/{p.name}", f"{TTA}\\outputs\\units\\{p.name}")
add(f"{TTA}/evidence/metrics/CHECKPOINT_MANIFEST.csv", "")  # handled below
PAIRS.pop()
add(f"{TRUNK}/checkpoints/CHECKPOINT_MANIFEST.csv", f"{TTA}\\outputs\\legacy_checkpoint_inventory.csv")

identical, edited, missing_src = [], [], []
for pub, src_rel in PAIRS:
    dp = PUB / pub
    if not dp.exists():
        missing_src.append((pub, "PUBLIC FILE MISSING"))
        continue
    sp = SRC / src_rel
    if not sp.exists():
        missing_src.append((pub, f"SOURCE NOT FOUND: {src_rel}"))
        continue
    (identical if sha(dp) == sha(sp) else edited).append(pub)

published = {p.relative_to(PUB).as_posix() for p in PUB.rglob("*") if p.is_file()
             and ".git" not in p.parts}
mapped = {pub for pub, _ in PAIRS}
new = sorted(published - mapped)

print(f"local source root : {SRC}")
print(f"published files   : {len(published)}")
print()
print(f"BYTE-IDENTICAL to local source : {len(identical)}")
print(f"EDITED (sanitization only)     : {len(edited)}")
for p in sorted(edited):
    print(f"    {p}")
print(f"NEW in public snapshot         : {len(new)}")
for p in new:
    print(f"    {p}")
if missing_src:
    print(f"UNRESOLVED                     : {len(missing_src)}")
    for p, why in missing_src[:40]:
        print(f"    {p}  ({why})")
