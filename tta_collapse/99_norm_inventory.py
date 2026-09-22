"""Derive the authoritative normalization inventory from a real legacy checkpoint."""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import p1_arms as A  # noqa: E402
import p1_common as P  # noqa: E402

cfg = json.loads((P.LEGACY / "configs" / "baselines.json").read_text(encoding="utf-8"))
ck = P.FORMAL_RESULTS / "eegnet" / "sub-01" / "seed_0" / "best.pt"
d = torch.load(ck, map_location="cpu", weights_only=False)
m = P.build_model_from_config(cfg)
m.load_state_dict(d["state_dict"], strict=True)

aud = A.norm_modules(m)
total = 0
print(f"{'module':18s} {'type':13s} {'feat':>4s} affine track  gamma                        beta")
for a in aud:
    print(f"{a['name']:18s} {a['type']:13s} {a['num_features']:4d} {str(a['affine']):>6s} "
          f"{str(a['track_running_stats']):>5s}  {a['gamma_name']:26s} {a['beta_name']}")
    total += a["gamma_numel"] + a["beta_numel"]
print(f"n_norm_layers = {len(aud)}")
print(f"total BN affine scalars = {total}")
print(f"model params total = {sum(p.numel() for p in m.parameters())}")
_, params, _ = A.build_arm_model(cfg, {k: v.clone() for k, v in m.state_dict().items()}, "tent")
print(f"tent trainable tensors = {len(params)}  scalars = {sum(p.numel() for p in params)}")
print(f"tent scalars / model scalars = {sum(p.numel() for p in params)/sum(p.numel() for p in m.parameters()):.6f}")
print("state_dict entries =", len(d["state_dict"]))
