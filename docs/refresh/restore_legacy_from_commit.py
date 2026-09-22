"""Reconstruct archive/legacy/legacy_ns_sd_prototype/ byte-exactly from the original remote commit.

The v1 refresh migrated the Phase-0 prototype but dropped two files. This script restores every
file from the original commit into the archive at its ORIGINAL relative path, so the archive is a
faithful, verifiable copy of what was public before the refresh.

    python docs/refresh/restore_legacy_from_commit.py [commit-sha]

It writes only under archive/legacy/legacy_ns_sd_prototype/. Existing files are compared
byte-for-byte against the original blob; a genuine difference is REPORTED, never silently
overwritten.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

COMMIT = sys.argv[1] if len(sys.argv) > 1 else "625dc3b901bb710cd5ab377dbbb85a81517c85b1"
ROOT = pathlib.Path(__file__).resolve().parents[2]
DEST = ROOT / "archive" / "legacy" / "legacy_ns_sd_prototype"

# The old README and requirements were replaced at the repository root and are preserved there
# under explicit historical names, so they are not duplicated into the archive.
SKIP = {"README.md", "requirements.txt", ".gitignore"}


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def normalise(data: bytes) -> bytes:
    """Compare content, not checkout line endings.

    Git blobs are stored LF-only, while this checkout is under core.autocrlf=true, so a
    working-tree file legitimately differs from its blob by CRLF expansion. What is being
    verified here is CONTENT fidelity, so line endings are normalised before comparing.
    """
    return data.replace(b"\r\n", b"\n")


# Without this, git escapes non-ASCII paths (`"\\345\\244\\207..."`) and every Chinese-named file
# becomes unreachable.
subprocess.run(["git", "config", "core.quotePath", "false"], cwd=ROOT, check=True)

files = [f for f in git_bytes("ls-tree", "-r", "--name-only", COMMIT).decode("utf-8").splitlines() if f]

restored, identical, conflict, skipped = [], [], [], []
for rel in files:
    if rel in SKIP:
        skipped.append(rel)
        continue
    target = DEST / rel
    blob = git_bytes("show", f"{COMMIT}:{rel}")
    if target.exists():
        if normalise(target.read_bytes()) == normalise(blob):
            identical.append(rel)
        else:
            conflict.append(rel)
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    restored.append(rel)

print(f"source commit : {COMMIT}")
print(f"files in commit: {len(files)}")
print()
print(f"RESTORED (were missing)     : {len(restored)}")
for r in restored:
    print(f"    {r}")
print(f"BYTE-IDENTICAL (already ok) : {len(identical)}")
print(f"CONFLICTS (differ, untouched): {len(conflict)}")
for c in conflict:
    print(f"    {c}")
print(f"SKIPPED (replaced at root)  : {len(skipped)}  {sorted(skipped)}")
