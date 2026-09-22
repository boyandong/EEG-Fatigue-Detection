"""Independent integrity, subject leakage, and EEGLAB reader checks."""
import csv
import json
from pathlib import Path
import numpy as np
import mne
from prepare_data import digest, make_splits, qc_epoch

def verify(out):
    cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
    prov = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    for file, expected in prov["output_hashes"].items():
        assert digest(out / file) == expected, file
    with (out / "segments.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len({r["segment_id"] for r in rows}) == len(rows)
    subjects = sorted({r["subject"] for r in rows})
    assert not set(subjects) & {"sub-39", "sub-43", "sub-44"}
    for s in subjects:
        assert {r["label"] for r in rows if r["subject"] == s} == {"0", "1"}
    splits = json.loads((out / "splits.json").read_text(encoding="utf-8"))
    assert splits["manifest_sha256"] == digest(out / "segments.csv")
    assert splits["folds"] == make_splits(subjects, cfg["split_seed"], cfg["validation_fraction"])
    assert sorted(f["test"][0] for f in splits["folds"]) == subjects
    cache = {}
    for r in rows:
        assert r["label"] == str(cfg["labels"][r["session"]])
        assert float(r["source_sfreq"]) == 500 and r["included"] == "True"
        file = r["waveform_file"]
        if file not in cache:
            cache[file] = np.load(out / file, mmap_mode="r")
        x = cache[file][int(r["array_index"])]
        assert x.shape == (61, 2000) and x.dtype == np.float32 and np.isfinite(x).all()
    root = Path(__file__).resolve().parent.parent / "data/ds004902/preprocessed"
    channels = json.loads((out / "channels.json").read_text(encoding="utf-8"))
    checked = []
    for stem in ["sub-01_ses-1", "sub-04_ses-1", "sub-52_ses-2", "sub-71_ses-2"]:
        epochs = mne.io.read_epochs_eeglab(root / f"{stem}.set", verbose="ERROR")
        data = epochs.get_data(copy=True)[:, [epochs.ch_names.index(c) for c in channels], :] * 1e6
        for r in [r for r in rows if r["source_file"] == f"{stem}.set"]:
            np.testing.assert_allclose(cache[r["waveform_file"]][int(r["array_index"])], data[int(r["source_epoch_index"])], rtol=1e-6, atol=1e-5)
        checked.append(stem)
    x = np.tile(np.sin(np.arange(2000)), (61, 1)).astype(np.float32)
    assert not qc_epoch(x, cfg["qc"])[0]
    for bad, reason in [(np.full_like(x, np.nan), "nonfinite"), (np.zeros_like(x), "flat_channel"), (x*2000, "excessive_amplitude")]:
        assert reason in qc_epoch(bad, cfg["qc"])[0]
    result = {"status": "passed", "subjects": len(subjects), "segments": len(rows), "folds": len(splits["folds"]), "independent_mne_checked_recordings": checked, "checks": ["output SHA256", "unique segments", "paired labels", "500 Hz only", "disjoint subject splits", "deterministic splits", "all waveform shapes and finiteness", "MNE sample equality", "QC corruption cases"]}
    (out / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "outputs/source_only_500hz_v1")
    verify(parser.parse_args().output)
