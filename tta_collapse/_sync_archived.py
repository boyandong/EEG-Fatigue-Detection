import importlib.util
import sys
from pathlib import Path

HERE = Path(r"<HOME>\Desktop\srtp\audit\eeg_tta_phase1")
spec = importlib.util.spec_from_file_location("remote", HERE / "05_remote.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SRC = Path(r"C:\eegtta_sync")
R = "/root/srtp"

# scp will not create intermediate directories - make them explicitly first
rc, out, err = m.ssh_run(
    f"mkdir -p {R}/formal_results_v1/project/outputs/source_only_500hz_v1 "
    f"{R}/formal_results_v1/project/configs {R}/formal_results_v1/project/third_party && echo MKDIR_OK")
print("mkdir:", out.strip(), err.strip()[:200])

# archived data copy (verifier A6 compares live vs archived)
for f in ("segments.csv", "splits.json", "channels.json", "config.json", "provenance.json",
          "subjects.csv", "recordings.csv", "report.md", "segments_all.csv"):
    rc = m.put(SRC / "formal_results_v1/project/outputs/source_only_500hz_v1" / f,
               f"{R}/formal_results_v1/project/outputs/source_only_500hz_v1/{f}")
    print(f"archived/{f}: {rc}")

# archived configs + sources manifest
for f in ("baselines.json",):
    print(f"archived configs/{f}:",
          m.put(SRC / "formal_results_v1/project/configs" / f,
                f"{R}/formal_results_v1/project/configs/{f}"))
print("archived third_party/sources.json:",
      m.put(SRC / "formal_results_v1/project/third_party/sources.json",
            f"{R}/formal_results_v1/project/third_party/sources.json"))

# wave-cache integrity: confirm the archived tree has no waveforms dir (A6 only needs manifests)
rc, out, err = m.ssh_run(
    "ls /root/srtp/formal_results_v1/project/outputs/source_only_500hz_v1/ | head -20; "
    "echo '--- live vs archived hash diff ---'; "
    "cd /root/srtp && sha256sum project/outputs/source_only_500hz_v1/segments.csv "
    "formal_results_v1/project/outputs/source_only_500hz_v1/segments.csv; "
    "sha256sum project/outputs/source_only_500hz_v1/splits.json "
    "formal_results_v1/project/outputs/source_only_500hz_v1/splits.json")
print(out)
print("ERR:", err[:400] if err else "(none)")
sys.exit(0)
