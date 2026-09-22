"""Official raw-data recovery feasibility probe (read-only, network).

Checks whether the original ds004902 EEG can still be obtained from OpenNeuro / NEMAR with
real file content (not git-annex pointers), which version is available, whether eyes-open
recordings are included, and the expected download size.

Writes project/vigilance_generalization_v1/outputs/stability_v1/raw_recovery_probe.json
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from pathlib import Path

# Resolve the branch root through the shared config module rather than by counting parents,
# so this script writes to the same place no matter which directory it is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

VIG = C.VIG
OUT = C.OUTPUTS / "stability_v1"
CTX = ssl.create_default_context()
UA = {"User-Agent": "vigilance-generalization-audit/1.0"}


def head(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return {"status": r.status, "length": r.headers.get("Content-Length"),
                    "type": r.headers.get("Content-Type")}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def get(url: str, timeout: int = 40, n: int = 2000) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(n).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _human(n) -> str:
    if not isinstance(n, (int, float)):
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def main() -> None:
    res: dict = {}

    # 1. NEMAR direct-file availability
    res["nemar_direct_files"] = {}
    for label, url in [
        ("participants.tsv", "https://data.nemar.org/on004902/v1.0.0/participants.tsv"),
        ("dataset_description.json", "https://data.nemar.org/on004902/v1.0.0/dataset_description.json"),
        ("manifest.json", "https://data.nemar.org/on004902/v1.0.0/manifest.json"),
    ]:
        res["nemar_direct_files"][label] = head(url)
        print(f"  NEMAR {label:<26} {res['nemar_direct_files'][label]}")

    # 2. OpenNeuro graphql: versions
    q = ("https://openneuro.org/crn/graphql?query="
         "%7Bdataset(id%3A%22ds004902%22)%7Bid%20latestSnapshot%7Btag%20created%7D"
         "%20snapshots%7Btag%20created%7D%7D%7D")
    st, body = get(q, n=3000)
    res["openneuro_graphql_status"] = st
    try:
        data = json.loads(body)
        snaps = data.get("data", {}).get("dataset", {}).get("snapshots", []) or []
        res["openneuro_versions"] = [s.get("tag") for s in snaps]
        res["openneuro_latest"] = (data.get("data", {}).get("dataset", {})
                                   .get("latestSnapshot", {}) or {}).get("tag")
    except Exception:  # noqa: BLE001
        res["openneuro_versions"] = None
        res["openneuro_raw"] = body[:500]

    # 3. NEMAR manifest -> file inventory and total size
    st, body = get("https://data.nemar.org/on004902/v1.0.0/manifest.json", n=4_000_000)
    res["nemar_manifest_status"] = st
    entries: list = []
    st_manifest_ok = False
    if st == 200:
        try:
            entries = json.loads(body)
            sizes = [e.get("size") for e in entries if isinstance(e, dict)]
            paths = [e.get("path", "") for e in entries if isinstance(e, dict)]
            res["nemar_manifest_entries"] = len(entries)
            res["nemar_total_bytes"] = int(sum(s for s in sizes if isinstance(s, (int, float))))
            res["nemar_n_set"] = sum(1 for p in paths if p.endswith(".set"))
            res["nemar_n_fdt"] = sum(1 for p in paths if p.endswith(".fdt"))
            res["nemar_n_eyesopen_set"] = sum(1 for p in paths if "eyesopen" in p and p.endswith(".set"))
            res["nemar_n_eyesclosed_set"] = sum(1 for p in paths if "eyesclosed" in p and p.endswith(".set"))
            res["nemar_eeg_bytes"] = int(sum(
                e.get("size", 0) for e in entries if isinstance(e, dict)
                and (e.get("path", "").endswith(".set") or e.get("path", "").endswith(".fdt"))))
            res["nemar_example_paths"] = paths[:6]
            st_manifest_ok = True
        except Exception as exc:  # noqa: BLE001
            res["nemar_manifest_parse_error"] = f"{type(exc).__name__}: {exc}"
    else:
        res["nemar_manifest_raw"] = body[:400]

    # 4. repos (best effort; a network hiccup here must not fail the probe)
    res["repos"] = {}
    for name, url in [("OpenNeuroDatasets/ds004902", "https://api.github.com/repos/OpenNeuroDatasets/ds004902"),
                      ("nemarDatasets/on004902", "https://api.github.com/repos/nemarDatasets/on004902")]:
        st, body = get(url, n=1500)
        try:
            d = json.loads(body) if st == 200 else {}
            res["repos"][name] = {"status": st, "size_kb": d.get("size"),
                                  "default_branch": d.get("default_branch"),
                                  "pushed_at": d.get("pushed_at")}
        except Exception:  # noqa: BLE001
            res["repos"][name] = {"status": st, "raw": str(body)[:200]}

    # 4b. exact sizes of representative EEG objects, fetched from the manifest
    res["eeg_file_sizes"] = {}
    if st_manifest_ok:
        by_path = {e.get("path"): e for e in entries if isinstance(e, dict)}
        for p in ["sub-01/ses-1/eeg/sub-01_ses-1_task-eyesopen_eeg.set",
                  "sub-01/ses-1/eeg/sub-01_ses-1_task-eyesopen_eeg.fdt",
                  "sub-39/ses-2/eeg/sub-39_ses-2_task-eyesopen_eeg.fdt"]:
            e = by_path.get(p)
            if e:
                url = e.get("bytes_url") or e.get("url") or ""
                res["eeg_file_sizes"][p] = {"manifest_size": e.get("size"),
                                            "size_human": _human(e.get("size")),
                                            "bytes_url_present": bool(e.get("bytes_url")),
                                            "head": head(url) if url else None}
    res["manifest_url_template"] = ("https://data.nemar.org/on004902/v1.0.0/"
                                    "{path}  (per-file HTTPS, range-resumable per NEMAR docs)")

    # 5. local preprocessed size, for comparison
    local = Path(r"<HOME>\Desktop\srtp\data\ds004902\preprocessed")
    if local.exists():
        tot = sum(p.stat().st_size for p in local.iterdir() if p.is_file())
        res["local_preprocessed_bytes"] = tot
        res["local_preprocessed_files"] = len([p for p in local.iterdir() if p.is_file()])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw_recovery_probe.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print()
    print(json.dumps({k: v for k, v in res.items() if k != "nemar_manifest_raw"}, indent=2)[:4000])
    print(f"\nwrote {OUT / 'raw_recovery_probe.json'}")


if __name__ == "__main__":
    main()
