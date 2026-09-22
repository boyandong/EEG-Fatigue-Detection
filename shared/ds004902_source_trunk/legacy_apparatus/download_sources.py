"""Download immutable upstream archives and preserve licenses/source hashes."""
import hashlib
import json
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent / "third_party"
SOURCES = [("arl-eegmodels", "vlawhern/arl-eegmodels", "master"),
           ("scikit-learn", "scikit-learn/scikit-learn", "1.7.2")]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "source-only-eeg-research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

if __name__ == "__main__":
    ROOT.mkdir(exist_ok=True)
    manifest = []
    release = json.loads(fetch("https://pypi.org/pypi/braindecode/1.3.2/json"))
    source = next(x for x in release["urls"] if x["packagetype"] == "sdist")
    archive = ROOT / source["filename"]
    archive.write_bytes(fetch(source["url"]))
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == source["digests"]["sha256"]
    with tarfile.open(archive) as tar:
        tar.extractall(ROOT, filter="data")
    manifest.append({"name": "braindecode", "version": "1.3.2", "repository": "https://github.com/braindecode/braindecode", "url": source["url"], "archive": archive.name, "sha256": source["digests"]["sha256"], "note": "Official PyPI sdist; no v1.3.2 Git tag exists"})
    for name, repo, ref in SOURCES:
        commit = json.loads(fetch(f"https://api.github.com/repos/{repo}/commits/{ref}"))["sha"]
        url = f"https://codeload.github.com/{repo}/zip/{commit}"
        path = ROOT / f"{name}-{commit}.zip"
        if not path.exists():
            path.write_bytes(fetch(url))
        dest = ROOT / name
        dest.mkdir(exist_ok=True)
        with zipfile.ZipFile(path) as z:
            for member in z.infolist():
                relative = Path(*Path(member.filename).parts[1:])
                target = (dest / relative).resolve()
                if not target.is_relative_to(dest.resolve()):
                    raise ValueError("Unsafe archive path")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif relative.parts:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(member))
        manifest.append({"name": name, "repository": f"https://github.com/{repo}", "requested_ref": ref,
                         "commit": commit, "url": url, "archive": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "downloaded_utc": datetime.now(timezone.utc).isoformat()})
        print(name, commit, flush=True)
        (ROOT / "sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
