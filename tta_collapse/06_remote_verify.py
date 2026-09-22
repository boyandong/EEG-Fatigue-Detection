"""Remote environment / provenance verification for the owner-approved server.

Runs entirely over the installed SSH key.  No password is used or stored.

  python 06_remote_verify.py env          # environment validation
  python 06_remote_verify.py provenance   # hashes, checkpoint count, unit count
  python 06_remote_verify.py gate         # env + provenance + remote verifier + closure smoke
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib.util

spec = importlib.util.spec_from_file_location("remote", HERE / "05_remote.py")
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)

OUT = HERE / "outputs"
PY = "/root/miniconda3/bin/python"
ROOT = "/root/srtp"

MUST_MATCH = {
    "torch": "2.10.0+cu126",
    "braindecode": "1.3.2",
    "numpy": "2.3.2",
    "scipy": "1.16.1",
    "sklearn": "1.7.2",
    "matplotlib": "3.10.5",
}


def run_remote_python(code: str, timeout=900, label="PY"):
    """Write local python to a temp file on the server and execute it."""
    local = OUT / f"_remote_{label}.py"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(code, encoding="utf-8")
    rc1 = remote.put(str(local), f"{ROOT}/{local.name}")
    rc, out, err = remote.ssh_run(f"{PY} {ROOT}/{local.name}", timeout=timeout)
    return rc, out, err


ENV_CODE = r'''
import json, platform, sys
out = {"hostname": platform.node(), "platform": platform.platform(),
       "python": sys.version.split()[0], "executable": sys.executable}
try:
    import torch
    out.update({"torch": torch.__version__, "torch_cuda": torch.version.cuda,
                "cuda_available": bool(torch.cuda.is_available()),
                "device_count": torch.cuda.device_count(),
                "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "cudnn": torch.backends.cudnn.version(),
                "capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None,
                "torch_cuda_arch_list": torch.cuda.get_arch_list(),
                "bf16_supported": bool(torch.cuda.is_bf16_supported()) if torch.cuda.is_available() else None})
except Exception as e:
    out["torch_error"] = f"{type(e).__name__}: {e}"
for m in ("braindecode", "numpy", "scipy", "sklearn", "matplotlib", "mne", "pandas", "pyarrow", "joblib"):
    try:
        mod = __import__(m)
        out[m] = getattr(mod, "__version__", "?")
    except Exception as e:
        out[m] = f"MISSING ({type(e).__name__})"
print("ENVJSON " + json.dumps(out))
'''


PROV_CODE = r'''
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path("/root/srtp")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

res = {}
prov = json.loads((ROOT / "formal_results_v1/project/results/formal_autodl_v1/provenance.json").read_text())
res["expected"] = {k: prov[k] for k in ("runner_sha256", "manifest_sha256", "splits_sha256",
                                        "config_sha256", "source_manifest_sha256", "gpu") if k in prov}
res["actual"] = {
    "runner_sha256": sha(ROOT / "project/run_baselines.py"),
    "runner_archived_sha256": sha(ROOT / "formal_results_v1/project/run_baselines.py"),
    "manifest_sha256": sha(ROOT / "project/outputs/source_only_500hz_v1/segments.csv"),
    "splits_sha256": sha(ROOT / "project/outputs/source_only_500hz_v1/splits.json"),
    "config_sha256": sha(ROOT / "project/configs/baselines.json"),
    "source_manifest_sha256": sha(ROOT / "project/third_party/sources.json"),
}
res["match"] = {k: (res["expected"].get(k) == res["actual"].get(k))
                for k in ("runner_sha256", "manifest_sha256", "splits_sha256", "config_sha256")}

# checkpoints
base = ROOT / "formal_results_v1/project/results/formal_autodl_v1/eegnet"
subs = sorted(d.name for d in base.iterdir() if d.is_dir())
n_pt = len(list(base.glob("*/seed_*/best.pt")))
n_norm = len(list(base.glob("*/seed_*/normalization.npz")))
n_res = len(list(base.glob("*/seed_*/result.json")))
n_pred = len(list(base.glob("*/seed_*/predictions.csv")))
res["checkpoints"] = {"subjects": len(subs), "first": subs[0] if subs else None,
                      "last": subs[-1] if subs else None,
                      "best_pt": n_pt, "normalization_npz": n_norm,
                      "result_json": n_res, "predictions_csv": n_pred}

# waveform cache + manifests
wav = ROOT / "project/outputs/source_only_500hz_v1/waveforms"
res["waveforms"] = {"n_files": len(list(wav.glob("*.npy"))) if wav.exists() else 0}
seg = ROOT / "project/outputs/source_only_500hz_v1/segments.csv"
res["segments_rows"] = sum(1 for _ in seg.open(encoding="utf-8-sig")) - 1 if seg.exists() else None

# audit lane artefacts
lane = ROOT / "audit/eeg_tta_phase1"
res["lane"] = {
    "has_target_stream_manifest": (lane / "outputs/target_stream_manifest.csv").exists(),
    "target_stream_rows": (sum(1 for _ in (lane / "outputs/target_stream_manifest.csv").open(
        encoding="utf-8-sig")) - 1) if (lane / "outputs/target_stream_manifest.csv").exists() else None,
    "has_subject_inventory": (lane / "outputs/legacy_subject_inventory.csv").exists(),
    "has_checkpoint_inventory": (lane / "outputs/legacy_checkpoint_inventory.csv").exists(),
    "has_batch_size_audit": (lane / "outputs/batch_size_audit.csv").exists(),
    "has_source_closure": (lane / "outputs/source_closure.json").exists(),
    "units_present": len(list((lane / "outputs/units").glob("*.json")))
                     if (lane / "outputs/units").exists() else 0,
}
# stale adapted weights / outputs anywhere under the lane?
stale = []
for pat in ("*.pt", "*.pth", "*.ckpt", "*.joblib"):
    stale += [str(p) for p in lane.rglob(pat)]
res["stale_weights_in_lane"] = stale
print("PROVJSON " + json.dumps(res, indent=1))
'''


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "gate"
    ok = True

    if action in ("env", "gate"):
        print("=" * 70, "\nENVIRONMENT\n", "=" * 70, sep="")
        rc, out, err = run_remote_python(ENV_CODE, label="env")
        print(out)
        if err.strip():
            print("STDERR:", err.strip()[:1000])
        env = None
        for line in out.splitlines():
            if line.startswith("ENVJSON "):
                env = json.loads(line.split("ENVJSON ", 1)[1])
        if env:
            (OUT / "remote_env.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
            print("\n-- required-version check --")
            for k, want in MUST_MATCH.items():
                got = env.get(k)
                mark = "OK " if got == want else ("DIFF" if got else "MISSING")
                if got != want:
                    ok = False
                print(f"  [{mark}] {k:12s} want {want:14s} got {got}")
            print(f"  [{'OK ' if env.get('cuda_available') else 'FAIL'}] CUDA available: "
                  f"{env.get('cuda_available')} on {env.get('device_name')} "
                  f"(driver CUDA {env.get('torch_cuda')}, arch list {env.get('torch_cuda_arch_list')})")

    if action in ("provenance", "gate"):
        print("\n" + "=" * 70, "\nPROVENANCE\n", "=" * 70, sep="")
        rc, out, err = run_remote_python(PROV_CODE, label="prov")
        print(out)
        if err.strip():
            print("STDERR:", err.strip()[:1000])
        prov = None
        for line in out.splitlines():
            if line.startswith("PROVJSON "):
                prov = json.loads(out.split("PROVJSON ", 1)[1])
        if not prov:
            # A provenance probe that never produced its JSON is a FAILURE, not a pass.
            print("  [FAIL] provenance probe produced no PROVJSON payload")
            ok = False
        else:
            (OUT / "remote_provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
            print("\n-- gate --")
            for k, v in prov["match"].items():
                print(f"  [{'OK ' if v else 'FAIL'}] {k}")
                ok = ok and v
            c = prov["checkpoints"]
            good = c["subjects"] == 68 and c["best_pt"] == 204 and c["normalization_npz"] == 204
            print(f"  [{'OK ' if good else 'FAIL'}] checkpoints: {c}")
            ok = ok and good
            w = prov["waveforms"]["n_files"]
            print(f"  [{'OK ' if w >= 136 else 'FAIL'}] waveform files: {w}")
            ok = ok and w >= 136
            print(f"  [{'OK ' if prov['segments_rows'] == 9390 else 'FAIL'}] segments rows: "
                  f"{prov['segments_rows']}")
            ok = ok and prov["segments_rows"] == 9390
            print(f"  lane artefacts: {prov['lane']}")
            # BEFORE the formal run: 0 units and no stale weights. AFTER: units are expected,
            # and then the requirement inverts to "every unit is a complete, verified file".
            n_units = prov["lane"]["units_present"]
            if n_units == 0:
                ok = ok and prov["lane"]["has_target_stream_manifest"]
                print("  [OK ] pre-run state: no units yet")
            else:
                print(f"  [i  ] post-run state: {n_units} units present")
            print(f"  [{'OK ' if not prov['stale_weights_in_lane'] else 'FAIL'}] no stale "
                  f"*.pt/*.pth/*.ckpt/*.joblib weights in lane: "
                  f"{prov['stale_weights_in_lane'] or 'none'}")
            ok = ok and not prov["stale_weights_in_lane"]

    if action == "gate":
        print("\n" + "=" * 70, "\nREMOTE VERIFIER + CONTROLS\n", "=" * 70, sep="")
        for cmd in (f"cd {ROOT}/audit/eeg_tta_phase1 && {PY} 90_verify_phase1.py 2>&1 | tail -6",
                    f"cd {ROOT}/audit/eeg_tta_phase1 && {PY} tests/test_p1_controls.py 2>&1 | tail -2",
                    f"cd {ROOT}/audit/eeg_tta_phase1 && {PY} tests/test_p1_synthetic_smoke.py 2>&1 | tail -2"):
            rc, out, err = remote.ssh_run(cmd, timeout=1800)
            print(f"$ {cmd.split('&&')[1].strip()}\n{out.strip()}")
            if err.strip():
                print("STDERR:", err.strip()[:600])
            if rc != 0:
                ok = False
                print(f"  -> NONZERO EXIT {rc}")

    print("\nGATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
