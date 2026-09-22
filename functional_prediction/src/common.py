"""Shared plumbing for vigilance_generalization_v1 scripts.

Config loading, path resolution, hashing, CSV/JSON writing, and the run manifest.
Deliberately dependency-light: a tiny YAML reader is used so that the pipeline does not
require PyYAML to be installed in the braindecode environment.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
SRC = VIG / "src"
CONFIG = VIG / "config"
OUTPUTS = VIG / "outputs"

for _p in (SRC,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# --------------------------------------------------------------------------- config
def _strip_comment(s: str) -> str:
    """Remove a trailing `# comment`, respecting quoted strings.

    A quoted value such as `"density"  # uV^2 / Hz` must keep its quotes and lose the
    comment; a flow list such as `[1, 30]  # note` must lose the comment too.
    """
    out: list[str] = []
    quote: str | None = None
    for ch in s:
        if quote is not None:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(s: str):
    s = _strip_comment(s).strip()
    if s == "":
        return None
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if inner == "":
            return []
        return [_parse_scalar(x) for x in inner.split(",")]
    if s.startswith("{") and s.endswith("}"):
        return s  # left as text; our configs do not use inline maps
    if s in {"true", "True"}:
        return True
    if s in {"false", "False"}:
        return False
    if s in {"null", "None", "~"}:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def load_yaml(path: Path) -> dict:
    """Minimal YAML subset reader: nested maps, lists, flow lists, block scalars.

    Sufficient for the config files in this directory. Supported forms::

        key: value
        key:
          nested: value
        key: [a, b, c]
        key:
          - item
          - other: value
        key: >
          folded text
    """
    lines = path.read_text(encoding="utf-8").splitlines()

    def is_content(s: str) -> bool:
        return bool(s.strip()) and not s.lstrip().startswith("#")

    def ind(s: str) -> int:
        return len(s) - len(s.lstrip(" "))

    def parse_block(i: int, indent: int):
        """Parse a block at column `indent`. Returns (value, next_index)."""
        items: list = []
        mapping: dict = {}
        mode: str | None = None
        while i < len(lines):
            raw = lines[i]
            if not is_content(raw):
                i += 1
                continue
            cur = ind(raw)
            if cur < indent:
                break
            if cur > indent:
                raise ValueError(f"unexpected indent at line {i+1}: {raw!r}")
            line = raw.strip()

            if line.startswith("- "):
                if mode is None:
                    mode = "list"
                if mode != "list":
                    raise ValueError(f"list item inside a mapping at line {i+1}")
                item_txt = _strip_comment(line[2:]).strip()
                if ": " in item_txt or item_txt.endswith(":"):
                    key, _, val = item_txt.partition(":")
                    entry = {key.strip(): _parse_scalar(val)}
                    i += 1
                    # absorb continuation keys of this list entry
                    while i < len(lines):
                        r2 = lines[i]
                        if not is_content(r2):
                            i += 1
                            continue
                        if ind(r2) <= cur or r2.strip().startswith("- "):
                            break
                        k2, _, v2 = r2.strip().partition(":")
                        if _strip_comment(v2).strip() in {">", "|", ">-", "|-"}:
                            folded, i = _fold(lines, i + 1, ind(r2))
                            entry[_strip_comment(k2).strip()] = folded
                        else:
                            entry[_strip_comment(k2).strip()] = _parse_scalar(v2)
                            i += 1
                    items.append(entry)
                else:
                    items.append(_parse_scalar(item_txt))
                    i += 1
                continue

            if mode == "list":
                raise ValueError(f"mapping key inside a list at line {i+1}: {raw!r}")
            mode = "map"
            key, _, val = line.partition(":")
            key = _strip_comment(key).strip()
            val = _strip_comment(val).strip()
            if val in {">", "|", ">-", "|-"}:
                folded, i = _fold(lines, i + 1, cur)
                mapping[key] = folded
                continue
            if val == "":
                nxt = next(((j, lines[j]) for j in range(i + 1, len(lines)) if is_content(lines[j])), None)
                if nxt is None or ind(nxt[1]) <= cur:
                    mapping[key] = None
                    i += 1
                    continue
                child, i = parse_block(nxt[0], ind(nxt[1]))
                mapping[key] = child
                continue
            mapping[key] = _parse_scalar(val)
            i += 1
        return (items if mode == "list" else mapping), i

    def _fold(ls: list[str], i: int, parent_indent: int) -> tuple[str, int]:
        parts = []
        while i < len(ls):
            if not ls[i].strip():
                i += 1
                continue
            if ind(ls[i]) <= parent_indent:
                break
            parts.append(ls[i].strip())
            i += 1
        return " ".join(parts), i

    first = next((j for j in range(len(lines)) if is_content(lines[j])), None)
    if first is None:
        return {}
    value, _ = parse_block(first, ind(lines[first]))
    return value


def dataset_config() -> dict:
    return load_yaml(CONFIG / "dataset_ds004902.yaml")


def mechanism_config() -> dict:
    return load_yaml(CONFIG / "mechanism_v1.yaml")


def resolve(rel: str) -> Path:
    return (VIG / rel).resolve()


# --------------------------------------------------------------------------- io
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=_default), encoding="utf-8")


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = columns or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(r.get(k)) for k in cols})


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return ""
    if isinstance(v, bool):
        return str(v)
    return v


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- provenance
def git_commit(repo: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def run_manifest(script: str, configs: list[Path], extra: dict | None = None) -> dict:
    """Everything needed to reconstruct an execution. COMMIT PENDING if git is unavailable."""
    repo = VIG.parents[1]
    commit = git_commit(repo)
    man = {
        "script": script,
        "script_sha256": sha256_file(Path(script)) if Path(script).exists() else None,
        "config_sha256": {str(p.relative_to(VIG)): sha256_file(p) for p in configs if p.exists()},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit or "COMMIT PENDING",
        "versions": _versions(),
        "random_seed_used": False,
        "determinism_note": "No stochastic component: no shuffling, no sampling, no training.",
    }
    if extra:
        man.update(extra)
    return man


def _versions() -> dict:
    import importlib.metadata as md
    out = {}
    for p in ("numpy", "scipy", "pymatreader", "mne"):
        try:
            out[p] = md.version(p)
        except Exception:  # noqa: BLE001
            out[p] = None
    return out
