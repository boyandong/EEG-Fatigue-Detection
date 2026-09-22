"""Unit tests for the frozen mechanism_v1 mathematics (SCIENTIFIC_SPEC.md section 14).

Tests A-F are the mathematical contract of the representation. They run on synthetic signals
and require no project data, so they can be executed at any time.

    python project/vigilance_generalization_v1/tests/test_mechanism.py

Exit code 0 = all passed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

VIG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIG / "src"))

import common as C  # noqa: E402
import mechanism_features as MF  # noqa: E402
from roi import load_roi_mapping  # noqa: E402
from spectral import SpectralConfig  # noqa: E402

SFREQ = 500.0
N_TIMES = 2000          # 4 s
RNG = np.random.default_rng(20260916)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def make_epochs(n_epochs: int, channels: list[str], *, theta: float, alpha: float, beta: float,
                noise: float = 0.0, seed: int = 0) -> np.ndarray:
    """Synthetic EEG: three band-limited components with prescribed amplitudes, in uV.

    Amplitudes are RMS in uV; power in a band is therefore proportional to amplitude^2 with
    the same constant for every band, which is what the gain and scaling tests need.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(N_TIMES) / SFREQ
    out = np.zeros((n_epochs, len(channels), N_TIMES), dtype=np.float64)
    for e in range(n_epochs):
        ph = rng.uniform(0, 2 * np.pi, size=3)
        sig = (theta * np.sin(2 * np.pi * 6.0 * t + ph[0])
               + alpha * np.sin(2 * np.pi * 10.0 * t + ph[1])
               + beta * np.sin(2 * np.pi * 20.0 * t + ph[2]))
        out[e] = sig[None, :]
        if noise:
            out[e] += rng.normal(0, noise, size=(len(channels), N_TIMES))
    return out


def cfg() -> tuple[SpectralConfig, object, list[str]]:
    ds = C.dataset_config()
    sc = SpectralConfig.from_dict(ds)
    roi = load_roi_mapping(ds["roi"])
    channels = [c for r in ("F", "CT", "PO") for c in ds["roi"][r]]
    return sc, roi, channels


def main() -> int:
    sc, roi, channels = cfg()
    print(f"mechanism_v1 unit tests  (sfreq={SFREQ}, n_times={N_TIMES}, "
          f"n_channels={len(channels)}, eps={sc.numerical_epsilon_uv2})\n")

    # ------------------------------------------------------------------ A: gain invariance
    print("Test A - multiplicative gain invariance  x' = k*x  =>  S, M, J unchanged")
    base = make_epochs(12, channels, theta=6.0, alpha=4.0, beta=2.0, noise=0.5, seed=1)
    f0 = MF.extract_session_features(base, channels, SFREQ, roi, sc)
    for k in (0.1, 10.0, 100.0):
        fk = MF.extract_session_features(base * k, channels, SFREQ, roi, sc)
        dM = max(abs(fk.M[r] - f0.M[r]) for r in ("F", "CT", "PO"))
        dJ = max(abs(fk.J[r] - f0.J[r]) for r in ("F", "CT", "PO"))
        # J scales with k only through the residual eps floor; with real power it is invariant.
        check(f"A  gain k={k:<6g} max|dM|={dM:.3e} max|dJ|={dJ:.3e}",
              dM < 1e-9 and dJ < 1e-6, "")

    # ------------------------------------------------------------------ B: theta-specific
    print("\nTest B - theta-specific increase (alpha, beta held fixed)  =>  S up")
    b0 = make_epochs(12, channels, theta=4.0, alpha=4.0, beta=4.0, noise=0.5, seed=2)
    b1 = make_epochs(12, channels, theta=8.0, alpha=4.0, beta=4.0, noise=0.5, seed=2)
    r0 = MF.extract_session_features(b0, channels, SFREQ, roi, sc)
    r1 = MF.extract_session_features(b1, channels, SFREQ, roi, sc)
    ok = all(r1.M[r] > r0.M[r] for r in ("F", "CT", "PO"))
    check("B  theta x2 => M increases in all three ROIs",
          ok, " ".join(f"{r}:{r0.M[r]:.3f}->{r1.M[r]:.3f}" for r in ("F", "CT", "PO")))

    # ------------------------------------------------------------------ C: broadband scale
    print("\nTest C - global broadband scale (theta, alpha, beta all x c)  =>  S unchanged")
    c0 = make_epochs(12, channels, theta=5.0, alpha=3.0, beta=2.0, noise=0.0, seed=3)
    rc0 = MF.extract_session_features(c0, channels, SFREQ, roi, sc)
    for c in (0.25, 4.0, 25.0):
        rc = MF.extract_session_features(c0 * c, channels, SFREQ, roi, sc)
        dM = max(abs(rc.M[r] - rc0.M[r]) for r in ("F", "CT", "PO"))
        check(f"C  uniform scale x{c:<5g} max|dM|={dM:.3e}", dM < 1e-9, "")

    # ------------------------------------------------------------------ D: instability
    print("\nTest D - equal mean S but larger epoch-to-epoch fluctuation  =>  J2 > J1")
    # Epochs whose per-epoch theta amplitude alternates little vs a lot, same mean.
    n_ep = 20
    stable = make_epochs(n_ep, channels, theta=5.0, alpha=4.0, beta=3.0, noise=0.0, seed=4)
    amps = np.linspace(2.0, 8.0, n_ep)          # mean 5.0, large spread
    wobbly = np.empty_like(stable)
    for e in range(n_ep):
        wobbly[e] = make_epochs(1, channels, theta=float(amps[e]), alpha=4.0, beta=3.0,
                                noise=0.0, seed=100 + e)[0]
    fs = MF.extract_session_features(stable, channels, SFREQ, roi, sc)
    fw = MF.extract_session_features(wobbly, channels, SFREQ, roi, sc)
    for r in ("F", "CT", "PO"):
        dM = abs(fw.M[r] - fs.M[r])
        check(f"D  {r}: M similar (|dM|={dM:.3f}) and J2>J1 ({fs.J[r]:.4f} -> {fw.J[r]:.4f})",
              dM < 0.25 and fw.J[r] > fs.J[r], "")

    # ------------------------------------------------------------------ E: offset cancellation
    print("\nTest E - personal offset cancels: a session-wide gain shared by both sessions")
    print("         leaves delta_M and delta_logJ unchanged (b_i - b_i = 0)")
    # S is scale-invariant (Test A), so a session-wide gain changes S by the SAME amount in
    # both sessions. Delta M, being a difference of the two, must therefore be unchanged.
    ns_x = make_epochs(12, channels, theta=5.0, alpha=4.0, beta=3.0, noise=0.4, seed=5)
    sd_x = make_epochs(12, channels, theta=7.0, alpha=4.0, beta=3.0, noise=0.4, seed=6)
    ns = MF.extract_session_features(ns_x, channels, SFREQ, roi, sc)
    sd = MF.extract_session_features(sd_x, channels, SFREQ, roi, sc)
    d_plain = MF.delta_features(ns, sd)["features"]

    k = 3.7
    ns_g = MF.extract_session_features(ns_x * k, channels, SFREQ, roi, sc)
    sd_g = MF.extract_session_features(sd_x * k, channels, SFREQ, roi, sc)
    d_gain = MF.delta_features(ns_g, sd_g)["features"]

    dM = max(abs(d_gain[f"delta_M_{r}"] - d_plain[f"delta_M_{r}"]) for r in ("F", "CT", "PO"))
    dJ = max(abs(d_gain[f"delta_logJ_{r}"] - d_plain[f"delta_logJ_{r}"]) for r in ("F", "CT", "PO"))
    check("E  shared gain x3.7 leaves delta_M and delta_logJ unchanged",
          dM < 1e-9 and dJ < 1e-6,
          f"max|d delta_M|={dM:.3e} max|d delta_logJ|={dJ:.3e}")

    # additive-offset form: S shifted by a constant in both sessions must also cancel
    from dataclasses import replace as _replace
    shift = 0.37
    ns_s = _replace(ns, M={r: ns.M[r] + shift for r in ("F", "CT", "PO")})
    sd_s = _replace(sd, M={r: sd.M[r] + shift for r in ("F", "CT", "PO")})
    d_shift = MF.delta_features(ns_s, sd_s)["features"]
    dM2 = max(abs(d_shift[f"delta_M_{r}"] - d_plain[f"delta_M_{r}"]) for r in ("F", "CT", "PO"))
    check("E  common additive offset +0.37 leaves delta_M unchanged (exact)",
          dM2 < 1e-12, f"max|d delta_M|={dM2:.3e}")

    # ------------------------------------------------------------------ F: determinism
    print("\nTest F - determinism: same input + same config => identical output")
    x = make_epochs(15, channels, theta=6.0, alpha=3.0, beta=2.0, noise=0.7, seed=7)
    a = MF.extract_session_features(x, channels, SFREQ, roi, sc)
    b = MF.extract_session_features(x.copy(), channels, SFREQ, roi, sc)
    same_M = all(a.M[r] == b.M[r] for r in ("F", "CT", "PO"))
    same_J = all(a.J[r] == b.J[r] for r in ("F", "CT", "PO"))
    check("F  bitwise-identical M and J on rerun", same_M and same_J, "")

    # --------------------------------------------------- G: composition identity exactness
    print("\nTest G - q_theta + q_alpha + q_beta == 1 exactly by construction")
    from spectral import band_powers, verify_composition_identity
    bands, _ = band_powers(x, SFREQ, sc)
    ident = verify_composition_identity(bands)
    check("G  composition identity", ident["identity_holds"],
          f"max deviation from 1 = {ident['max_abs_deviation_from_one']:.3e}")

    # --------------------------------------------------- H: epsilon floor never triggered
    print("\nTest H - epsilon floor unused on realistic synthetic power")
    fh = MF.extract_session_features(x, channels, SFREQ, roi, sc)
    hits = fh.audit["epsilon_hits"]
    check("H  no band power at or below eps", hits["theta"] == hits["alpha"] == hits["beta"] == 0,
          f"hits={ {k: hits[k] for k in ('theta','alpha','beta')} }, "
          f"min theta power={fh.audit['bands_summary']['theta']['min']:.3e}")

    # --------------------------------------------------- I: ROI channel counts
    print("\nTest I - ROI partition sizes")
    check("I  F=16 CT=28 PO=17 exact partition",
          fh.n_channels_per_region == {"F": 16, "CT": 28, "PO": 17},
          str(fh.n_channels_per_region))

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{'='*70}\n{n_pass}/{len(RESULTS)} checks passed")
    if n_pass != len(RESULTS):
        print("FAILED:")
        for n, ok, d in RESULTS:
            if not ok:
                print("  -", n, d)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
