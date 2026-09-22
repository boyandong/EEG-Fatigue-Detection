"""Generate the tracked-file size audit from a git ref (blob sizes, not working-tree sizes).

Working-tree sizes are unreliable on Windows under `core.autocrlf=true`: every text file is
CRLF-expanded on checkout, so summing the working tree overstates every blob by its line count.
This script reads sizes from `git ls-tree -l`, which reports the stored blob size, so the audit
describes what the repository actually contains and is reproducible from a ref alone.

    python docs/refresh/generate_size_audit.py [ref]

Default ref: HEAD.
"""
from __future__ import annotations

import collections
import subprocess
import sys

REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

BINARY_EXT = {".pt", ".pth", ".npy", ".npz", ".png", ".jpg", ".jpeg", ".tar", ".gz", ".zip",
              ".bin", ".ckpt", ".onnx", ".pdf", ".pyc"}


def ls_tree(ref: str) -> list[tuple[str, int]]:
    out = subprocess.run(["git", "ls-tree", "-r", "-l", ref],
                         capture_output=True, check=True).stdout.decode("utf-8")
    rows = []
    for line in out.splitlines():
        # <mode> SP <type> SP <sha> SP* <size> TAB <path>
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 4 or parts[3] == "-":
            continue
        rows.append((path, int(parts[3])))
    return rows


def main() -> int:
    rows = ls_tree(REF)
    total_files = len(rows)
    total_bytes = sum(s for _, s in rows)
    mib = total_bytes / 1048576

    print(f"ref            : {REF}")
    sha = subprocess.run(["git", "rev-parse", REF], capture_output=True,
                         check=True).stdout.decode().strip()
    print(f"resolved sha   : {sha}")
    print(f"tracked files  : {total_files}")
    print(f"tracked bytes  : {total_bytes}")
    print(f"MiB (1048576)  : {mib:.3f}")
    print()

    print("=== BY TOP-LEVEL CATEGORY ===")
    cat = collections.defaultdict(lambda: [0, 0])
    for path, size in rows:
        top = path.split("/")[0]
        if "." in top and "/" not in path:
            top = "(root files)"
        cat[top][0] += 1
        cat[top][1] += size
    for k in sorted(cat, key=lambda k: -cat[k][1]):
        n, s = cat[k]
        print(f"{k:<26} {n:>6} files {s/1048576:>10.2f} MiB")
    print()

    print("=== TOP 25 BY SIZE ===")
    for path, size in sorted(rows, key=lambda r: -r[1])[:25]:
        print(f"{size:>10}  {path}")
    print()

    print("=== SIZE BANDS ===")
    bands = [("over 3 MiB", 3 * 1048576), ("over 2 MiB", 2 * 1048576),
             ("over 1 MiB", 1048576), ("over 512 KiB", 512 * 1024)]
    for label, thresh in bands:
        n = sum(1 for _, s in rows if s > thresh)
        print(f"{label:<16} {n:>4} files")
    print()

    print("=== BINARIES BY EXTENSION ===")
    bins = collections.defaultdict(lambda: [0, 0])
    for path, size in rows:
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in BINARY_EXT:
            bins[ext][0] += 1
            bins[ext][1] += size
    if not bins:
        print("  none")
    for ext in sorted(bins, key=lambda e: -bins[e][1]):
        n, s = bins[ext]
        print(f"{ext:<8} {n:>4} files {s/1048576:>8.2f} MiB")
    print()

    print("=== SUSPICION CHECKS ===")
    def count(pred):
        return sum(1 for p, _ in rows if pred(p))
    checks = [
        ("raw EEG (.set/.fdt/.cnt/.edf/.bdf)",
         count(lambda p: p.endswith((".set", ".fdt", ".cnt", ".edf", ".bdf")))),
        ("waveform caches (waveforms/*.npy)",
         count(lambda p: "/waveforms/" in p and p.endswith(".npy"))),
        ("checkpoints (any .pt/.pth/.ckpt)",
         count(lambda p: p.endswith((".pt", ".pth", ".ckpt")))),
        ("Git LFS pointers", count(lambda p: False)),
        ("files over 3 MiB", sum(1 for _, s in rows if s > 3 * 1048576)),
    ]
    for label, n in checks:
        print(f"  {label:<42} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
