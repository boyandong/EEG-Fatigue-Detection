"""Remote execution helper for the owner-approved EEGTTA Phase-1 server.

Uses paramiko only to bootstrap: it installs a dedicated ed25519 key once, after which all
commands go through plain OpenSSH with the key (no password on any later command line).

The password is read from the environment variable `EEGTTA_SSH_PASSWORD` and is never
written into this repository.

Usage:
  python 05_remote.py install-key
  python 05_remote.py run "<shell command>"
  python 05_remote.py collect-env
  python 05_remote.py put  <local> <remote>
  python 05_remote.py get  <remote> <local>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "outputs" / "remote_state.json"
KEY_PATH = Path(os.environ.get("EEGTTA_SSH_KEY", r"<HOME>\.ssh\<key-name>"))
KEY_PUB = Path(str(KEY_PATH) + ".pub")

HOST = "<SERVER_HOST>"
PORT = int(os.environ.get("EEGTTA_SSH_PORT", "0"))
USER = "root"
SSH = r"ssh.exe"


def _password():
    pw = os.environ.get("EEGTTA_SSH_PASSWORD")
    if not pw:
        raise SystemExit("EEGTTA_SSH_PASSWORD is not set; export it for this command only.")
    return pw


def ensure_key():
    """Generate the project's dedicated ed25519 key if absent."""
    if KEY_PATH.exists() and KEY_PUB.exists():
        return
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C",
                        "eegtta-phase1", "-f", str(KEY_PATH)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ssh-keygen failed: {r.stderr}")


def install_key():
    import paramiko

    ensure_key()
    pub = KEY_PUB.read_text(encoding="utf-8").strip()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=_password(), timeout=30,
                   look_for_keys=False, allow_agent=False)
    cmd = ("mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
           "chmod 600 ~/.ssh/authorized_keys && "
           f"grep -qF '{pub}' ~/.ssh/authorized_keys || echo '{pub}' >> ~/.ssh/authorized_keys; "
           "echo INSTALLED; hostname")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    client.close()
    print(out.strip())
    if err.strip():
        print("stderr:", err.strip()[:400])
    _save({"host": HOST, "port": PORT, "user": USER, "key": str(KEY_PATH),
           "key_installed": "INSTALLED" in out})
    return "INSTALLED" in out


def _save(d):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def ssh_run(command, timeout=600, capture=True):
    """Run a command over the installed key. Returns (rc, stdout, stderr)."""
    base = [SSH, "-p", str(PORT), "-i", str(KEY_PATH), "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=20",
            f"{USER}@{HOST}", command]
    r = subprocess.run(base, capture_output=capture, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout or "", r.stderr or ""


def collect_env():
    """Owner-required environment validation (§6 of the correction brief).

    Deliberately NOT `set -e`: each probe reports its own failure so one missing tool
    cannot hide the rest of the environment.
    """
    script = r"""
echo "=== hostname ==="; hostname; uname -a
echo "=== nvidia-smi ==="; nvidia-smi || echo "nvidia-smi FAILED"
echo "=== python discovery ==="
for p in python python3 python3.11 /root/miniconda3/bin/python /root/miniconda3/envs/*/bin/python \
         /opt/conda/bin/python /opt/conda/envs/*/bin/python /usr/bin/python3; do
  if command -v "$p" >/dev/null 2>&1 || [ -x "$p" ]; then
    echo "CANDIDATE $p -> $("$p" -V 2>&1)"
  fi
done
echo "PATH=$PATH"
echo "=== conda envs ==="; ls -d /root/miniconda3/envs/* /opt/conda/envs/* 2>/dev/null || echo "none"
echo "=== torch probe (first working interpreter) ==="
PY=""
for p in python python3 python3.11 /root/miniconda3/bin/python /opt/conda/bin/python; do
  if command -v "$p" >/dev/null 2>&1; then PY="$p"; break; fi
done
for p in /root/miniconda3/envs/*/bin/python /opt/conda/envs/*/bin/python; do
  [ -x "$p" ] && [ -z "$PY2" ] && PY2="$p"
done
echo "CHOSEN=${PY:-none}  FALLBACK=${PY2:-none}"
for CAND in "$PY" "$PY2"; do
  [ -z "$CAND" ] && continue
  echo "--- probing $CAND ---"
  "$CAND" - <<'PY'
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
                "capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None})
except Exception as e:
    out["torch_error"] = f"{type(e).__name__}: {e}"
for m in ("braindecode","numpy","scipy","sklearn","matplotlib","mne","pandas","pyarrow"):
    try:
        mod = __import__(m); out[m] = getattr(mod, "__version__", "?")
    except Exception as e:
        out[m] = f"MISSING ({type(e).__name__})"
print("ENVJSON " + json.dumps(out))
PY
done
echo "=== disk ==="; df -h /root 2>/dev/null | tail -2 || df -h | tail -3
echo "=== cpu/mem ==="; nproc; free -g | head -2
echo "=== /root listing ==="; ls -la /root 2>/dev/null | head -40
echo "=== any prior eegtta trace ==="; find / -maxdepth 4 -name "*eeg_tta*" -o -maxdepth 4 -name "*eegtta*" 2>/dev/null | head -20 || true
"""
    rc, out, err = ssh_run(script, timeout=600)
    print(out)
    if err.strip():
        print("STDERR:", err.strip()[:2000])
    env = None
    for line in out.splitlines():
        if line.startswith("ENVJSON "):
            env = json.loads(line[len("ENVJSON "):])
    if env:
        _save({**(_load() or {}), "env": env})
    return rc, env


def _load():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None


def put(local, remote_path):
    """Upload a single file/dir with plain OpenSSH scp over the installed key."""
    cmd = ["scp", "-P", str(PORT), "-i", str(KEY_PATH), "-o", "BatchMode=yes",
           "-o", "StrictHostKeyChecking=accept-new", "-q", "-r", str(local),
           f"{USER}@{HOST}:{remote_path}"]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def get(remote_path, local):
    cmd = ["scp", "-P", str(PORT), "-i", str(KEY_PATH), "-o", "BatchMode=yes",
           "-o", "StrictHostKeyChecking=accept-new", "-q", "-r",
           f"{USER}@{HOST}:{remote_path}", str(local)]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def run_script(local_script, interpreter="bash", remote_dir="/root/srtp/_remote", timeout=3000):
    """Upload a shell/python file and execute it remotely.

    This is the robust path: no shell quoting is needed because the program text travels as
    a file, not as an argument.
    """
    p = Path(local_script)
    ssh_run(f"mkdir -p {remote_dir}")
    dest = f"{remote_dir}/{p.name}"
    # Normalize anything a Windows editor may have introduced: a UTF-8 BOM makes bash treat
    # the first command as an unknown name, and CRLF makes it emit "$'\r': command not found".
    data = p.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    if b"\r\n" in data:
        data = data.replace(b"\r\n", b"\n")
    p = p.with_name(p.name + ".norm")
    p.write_bytes(data)
    dest = f"{remote_dir}/{p.name}"
    if put(str(p), dest) != 0:
        raise SystemExit(f"upload failed: {p}")
    if p.suffix == ".py":
        cmd = f"cd {remote_dir} && /root/miniconda3/bin/python {dest}"
    else:
        cmd = f"cd {remote_dir} && bash {dest}"
    return ssh_run(cmd, timeout=timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action",
                    choices=["install-key", "run", "run-script", "collect-env", "put", "get"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    if a.action == "install-key":
        return 0 if install_key() else 1
    if a.action == "collect-env":
        rc, env = collect_env()
        print("\nparsed env:", json.dumps(env, indent=2) if env else "NOT PARSED")
        return rc
    if a.action == "run":
        rc, out, err = ssh_run(" ".join(a.args), timeout=a.timeout)
        print(out)
        if err.strip():
            print("STDERR:", err.strip())
        return rc
    if a.action == "run-script":
        interp = a.args[1] if len(a.args) > 1 else "bash"
        rc, out, err = run_script(a.args[0], interp, timeout=a.timeout)
        print(out)
        if err.strip():
            print("STDERR:", err.strip())
        return rc
    if a.action in ("put", "get"):
        local, remote = a.args[0], a.args[1]
        if a.action == "put":
            cmd = ["scp", "-P", str(PORT), "-i", str(KEY_PATH), "-o", "BatchMode=yes",
                   "-o", "StrictHostKeyChecking=accept-new", "-r", local, f"{USER}@{HOST}:{remote}"]
        else:
            cmd = ["scp", "-P", str(PORT), "-i", str(KEY_PATH), "-o", "BatchMode=yes",
                   "-o", "StrictHostKeyChecking=accept-new", "-r", f"{USER}@{HOST}:{remote}", local]
        return subprocess.run(cmd).returncode
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
