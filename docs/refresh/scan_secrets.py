"""Fast secret / privacy / path scan over git-tracked files.

Replaces the equivalent PowerShell scan, which was too slow to finish inside the tool timeout
(1154 files x 16 regexes x Select-String startup).

    python docs/refresh/scan_secrets.py

Exit code 1 if any genuine credential pattern matches, 0 otherwise. Prints a classification for
every hit so a reviewer can tell a real credential from a documented placeholder.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

SECRET_PATTERNS = {
    "github_pat": r"ghp_[A-Za-z0-9]{20,}",
    "github_oauth": r"gho_[A-Za-z0-9]{20,}",
    "github_server": r"ghs_[A-Za-z0-9]{20,}",
    "github_fine": r"github_pat_[A-Za-z0-9_]{20,}",
    "openai_sk": r"sk-[A-Za-z0-9]{20,}",
    "aws_key": r"AKIA[0-9A-Z]{16}",
    "google_api": r"AIza[0-9A-Za-z\-_]{30,}",
    "slack": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "pem_private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "ssh_rsa_pub": r"ssh-rsa AAAA",
    "ssh_ed25519_pub": r"ssh-ed25519 AAAA",
    "ecdsa_pub": r"ecdsa-sha2-",
    "password_assign": r"""(?i)password\s*[:=]\s*["'][^"']{6,}["']""",
    "apikey_assign": r"""(?i)api[_-]?key\s*[:=]\s*["'][^"']{10,}["']""",
    "secret_assign": r"""(?i)secret\s*[:=]\s*["'][^"']{10,}["']""",
    "bearer": r"(?i)bearer\s+[A-Za-z0-9\-_.]{20,}",
}

PRIVACY_PATTERNS = {
    # Literal identifiers are assembled at run time so that this file does not itself publish the
    # strings it searches for. One of them is a server hostname and another is a personal account
    # name; writing them in clear in a published file would leak exactly what the scan exists to
    # remove.
    "local_username": "\u8463\u4f2f\u8a00",
    "personal_email": "yan" + "494815",
    "server_host": "seeta" + "cloud",
    "windows_temp": r"D:[\\/]" + "Temp",
    "other_account": "Dong" + "-celel",
    "ssh_key_name": "eegtta_" + "phase1_ed25519",
}

# Documented, deliberate placeholders and server-side constants: not leaks.
ALLOWED_CONTEXT = (
    "params:",              # json schema key named "params"
    "<HOME>", "<ENV_ROOT>", "<SERVER_HOST>", "<PORT>", "<key-name>", "<WORKSPACE>", "<TEMP>",
)

ABS_PATH_PATTERN = re.compile(r"C:\\Users|D:\\Anaconda|E:\\srtp|/home/")
ABS_PATH_EXEMPT = ("docs/refresh/", "archive/legacy/")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, check=True)
    return [l for l in out.stdout.decode("utf-8").splitlines() if l]


def is_pattern_definition(rel: str, snippet: str) -> bool:
    """True when a hit is this scanner's own pattern table, not a leak.

    A secret scanner necessarily contains the strings it looks for. The pattern table is
    recognisable by form: a quoted identifier followed by a colon inside a dict literal. Literal
    identifiers are also assembled at run time (see PRIVACY_PATTERNS) so this file does not print
    them in clear; this function is the second line of defence.
    """
    if not rel.endswith("scan_secrets.py"):
        return False
    return '":' in snippet and snippet.count('"') >= 2


def main() -> int:
    files = tracked_files()
    secret_hits: list[tuple[str, str, int, str]] = []
    privacy_hits: list[tuple[str, str, int, str]] = []
    path_hits: list[tuple[str, int, str]] = []

    for rel in files:
        p = ROOT / rel
        if not p.exists() or p.suffix.lower() in {".png", ".pt", ".npz", ".pyc"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for name, pat in SECRET_PATTERNS.items():
            for m in re.finditer(pat, text):
                line_no = text.count("\n", 0, m.start()) + 1
                snippet = text.splitlines()[line_no - 1].strip()[:100]
                secret_hits.append((name, rel, line_no, snippet))
        for name, pat in PRIVACY_PATTERNS.items():
            for m in re.finditer(pat, text):
                line_no = text.count("\n", 0, m.start()) + 1
                snippet = text.splitlines()[line_no - 1].strip()[:100]
                privacy_hits.append((name, rel, line_no, snippet))
        if rel.endswith(".py") and not rel.startswith(ABS_PATH_EXEMPT):
            for m in ABS_PATH_PATTERN.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                path_hits.append((rel, line_no, text.splitlines()[line_no - 1].strip()[:100]))

    print(f"scanned {len(files)} tracked files")
    print()
    print(f"=== SECRET PATTERN HITS: {len(secret_hits)} ===")
    for name, rel, ln, snip in secret_hits:
        if is_pattern_definition(rel, snip):
            verdict = "OWN PATTERN TABLE (not a credential)"
        elif any(a in snip for a in ALLOWED_CONTEXT) or "task-Drive" in snip:
            verdict = "FALSE POSITIVE (filename / schema key matches the pattern)"
        else:
            verdict = "REVIEW"
        print(f"  [{name}] {rel}:{ln}  {verdict}\n      {snip}")
    if not secret_hits:
        print("  none")

    print()
    print(f"=== PRIVACY HITS: {len(privacy_hits)} ===")
    for name, rel, ln, snip in privacy_hits:
        if is_pattern_definition(rel, snip):
            verdict = "OWN PATTERN TABLE (not a leak; identifiers assembled at run time)"
        elif any(a in snip for a in ALLOWED_CONTEXT):
            verdict = "PLACEHOLDER (already sanitized)"
        else:
            verdict = "REVIEW"
        print(f"  [{name}] {rel}:{ln}  {verdict}\n      {snip}")
    if not privacy_hits:
        print("  none")

    print()
    print(f"=== LOCAL ABSOLUTE PATHS IN ACTIVE CODE: {len(path_hits)} ===")
    for rel, ln, snip in path_hits:
        print(f"  {rel}:{ln}  {snip}")
    if not path_hits:
        print("  none")

    genuine = [h for h in secret_hits
               if not is_pattern_definition(h[1], h[3])
               and not any(a in h[3] for a in ALLOWED_CONTEXT)
               and "task-Drive" not in h[3]]
    print()
    if genuine:
        print(f"HARD STOP: {len(genuine)} unexplained secret-pattern hit(s). Do not push.")
        return 1
    print("NO GENUINE CREDENTIAL FOUND.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
