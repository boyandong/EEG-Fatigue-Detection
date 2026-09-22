"""Repair the dangling Phase 4A3 report citation in the governance documents.

`AGENTS.md`, `SESSION_HANDOVER.md` and `functional_prediction/research_tree.md` cite
`functional_prediction/audit/phase4a3/PHASE4A3_GAP_CORRECTED_REPORT.md`. That file does not exist:
`95_write_report.py` was written to produce it (`HERE / "PHASE4A3_GAP_CORRECTED_REPORT.md"`) but was
never run, so the synthesised report was never created. The authoritative Phase 4A3 content lives in
the artifacts under `phase4a3/outputs/`.

This is GOVERNANCE/PATH MAINTENANCE ONLY. No scientific statement is altered: every replacement
points at the artifact that already carries the same claim.

    python docs/refresh/repair_dangling_report_reference.py <workspace-root>

Dry-run by default; pass --apply to write.
"""
from __future__ import annotations

import os
import pathlib
import sys

APPLY = "--apply" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]

# The workspace root is supplied by the caller, or taken from DSH_WORKSPACE. It is deliberately NOT
# defaulted to an absolute local path: this file is published, and a machine-specific home
# directory does not belong in it.
_env_root = os.environ.get("DSH_WORKSPACE")
if ARGS:
    ROOT = pathlib.Path(ARGS[0])
elif _env_root:
    ROOT = pathlib.Path(_env_root) / "project" / "srtp"
else:
    sys.exit("usage: repair_dangling_report_reference.py <workspace-root> [--apply]\n"
             "   or: set DSH_WORKSPACE and run without arguments")

# (relative path, literal old text, literal new text)
EDITS = [
    (
        "AGENTS.md",
        "`functional_prediction/audit/phase4a3/PHASE4A3_GAP_CORRECTED_REPORT.md`,\n"
        "`functional_prediction/audit/phase4a3/outputs/GAP_CONTAMINATION_AUDIT.md`)",
        "`functional_prediction/audit/phase4a3/outputs/GAP_CONTAMINATION_AUDIT.md` — the\n"
        "impact claim refuted, §3 — and `…/outputs/clean_standard_run.json`, the reproduction)",
    ),
    (
        "SESSION_HANDOVER.md",
        "| report | `PHASE4A3_GAP_CORRECTED_REPORT.md` |",
        "| report | `PHASE4A3_GAP_CORRECTED_REPORT.md` — **NEVER GENERATED.** "
        "`95_write_report.py` was written to emit it but was not run. Cite "
        "`outputs/GAP_CONTAMINATION_AUDIT.md` (§3) and `outputs/clean_standard_run.json`. |",
    ),
    (
        "SESSION_HANDOVER.md",
        "   `functional_prediction/audit/phase4a3/PHASE4A3_GAP_CORRECTED_REPORT.md` §0, then\n"
        "   `functional_prediction/audit/phase4a3/outputs/GAP_CONTAMINATION_AUDIT.md` §3b.",
        "   `functional_prediction/audit/phase4a3/outputs/GAP_CONTAMINATION_AUDIT.md` §1 and §3\n"
        "   (the headline, and the impact claim refuted), then its §3b (the unresolved\n"
        "   instrumentation discrepancy).",
    ),
]

report = []
for rel, old, new in EDITS:
    p = ROOT / rel
    if not p.exists():
        report.append(("SKIP (missing)", rel, 0))
        continue
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    if n == 0:
        report.append(("NO MATCH", rel, 0))
        continue
    if APPLY:
        p.write_text(text.replace(old, new), encoding="utf-8")
    report.append(("APPLIED" if APPLY else "WOULD EDIT", rel, n))

for status, rel, n in report:
    print(f"{status:14} x{n}  {rel}")

print()
print("mode:", "APPLY" if APPLY else "dry-run (pass --apply to write)")
