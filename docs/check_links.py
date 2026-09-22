"""Check that every relative Markdown link in this repository resolves to a real path.

Documentation rot is silent, so this is a real check rather than a stylistic one: a README that
points a reviewer at a file which does not exist is worse than one that says nothing.

    python docs/check_links.py

Exit code 0 = every relative link resolves.

External http(s) links are reported but NOT fetched -- this script performs no network access.

Note: the superseded prototype under archive/legacy/ is excluded on purpose. It carries the
original project's links, which are historical and are not maintained here.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE = ("archive/legacy",)

LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def main() -> int:
    broken: list[str] = []
    external: list[str] = []
    checked = 0

    for md in sorted(ROOT.rglob("*.md")):
        rel = md.relative_to(ROOT).as_posix()
        if any(rel.startswith(e) for e in EXCLUDE):
            continue
        text = md.read_text(encoding="utf-8")
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                external.append(f"{rel} -> {target}")
                continue
            if target.startswith("#"):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            checked += 1
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                broken.append(f"{rel} -> {target}")

    print(f"relative links checked : {checked}")
    print(f"external links (not fetched): {len(external)}")
    for e in external:
        print(f"    {e}")

    if broken:
        print()
        print(f"BROKEN LINKS: {len(broken)}")
        for b in broken:
            print("   ", b)
        return 1

    print()
    print(f"ALL {checked} relative links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
