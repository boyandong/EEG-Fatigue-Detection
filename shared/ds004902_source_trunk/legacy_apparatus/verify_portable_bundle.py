"""Verify the allowlisted Source Only training bundle without raw EEGLAB files."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    expected_hashes = provenance["output_hashes"]

    with (root / "segments.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    subjects = sorted({row["subject"] for row in rows})
    waveform_files = sorted({row["waveform_file"].replace("\\", "/") for row in rows})
    required = [
        "channels.json",
        "config.json",
        "segments.csv",
        "splits.json",
        "subjects.csv",
        *waveform_files,
    ]
    for relative in required:
        expected = expected_hashes.get(relative) or expected_hashes.get(relative.replace("/", "\\"))
        assert expected is not None, f"missing expected hash: {relative}"
        assert digest(root / relative) == expected, f"hash mismatch: {relative}"

    assert len(rows) == 9390
    assert len(subjects) == 68
    assert len(waveform_files) == 136
    assert not set(subjects) & {"sub-39", "sub-43", "sub-44"}
    assert len({row["segment_id"] for row in rows}) == len(rows)
    assert {row["label"] for row in rows} == {"0", "1"}
    assert sum(row["label"] == "0" for row in rows) == 4735
    assert sum(row["label"] == "1" for row in rows) == 4655
    for subject in subjects:
        assert {row["session"] for row in rows if row["subject"] == subject} == {"ses-1", "ses-2"}
        assert {row["label"] for row in rows if row["subject"] == subject} == {"0", "1"}
    for row in rows:
        assert row["label"] == str(config["labels"][row["session"]])
        assert float(row["source_sfreq"]) == 500.0
        assert row["included"] == "True"

    splits = json.loads((root / "splits.json").read_text(encoding="utf-8"))
    assert splits["manifest_sha256"] == digest(root / "segments.csv")
    assert len(splits["folds"]) == len(subjects)
    assert sorted(fold["test"][0] for fold in splits["folds"]) == subjects
    for fold in splits["folds"]:
        train, validation, test = map(set, (fold["train"], fold["validation"], fold["test"]))
        assert len(test) == 1 and len(train) == 53 and len(validation) == 14
        assert not (train & validation or train & test or validation & test)
        assert train | validation | test == set(subjects)

    cache = {}
    for relative in waveform_files:
        array = np.load(root / relative, mmap_mode="r")
        assert array.dtype == np.float32
        assert array.ndim == 3 and array.shape[1:] == (61, 2000)
        assert np.isfinite(array).all()
        cache[relative] = array
    for row in rows:
        relative = row["waveform_file"].replace("\\", "/")
        index = int(row["array_index"])
        assert 0 <= index < len(cache[relative])

    result = {
        "status": "passed",
        "scope": "portable_allowlisted_bundle",
        "subjects": len(subjects),
        "segments": len(rows),
        "class_0": 4735,
        "class_1": 4655,
        "waveform_records": len(waveform_files),
        "folds": len(splits["folds"]),
        "shape": [61, 2000],
        "sampling_rate_hz": 500,
        "checks": [
            "SHA256 for every bundled training input",
            "unique segment ids",
            "paired subject sessions and labels",
            "500 Hz only",
            "waveform shape dtype and finiteness",
            "68 disjoint subject-level LOSO folds",
        ],
    }
    (root / "portable_verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs/source_only_500hz_v1",
    )
    verify(parser.parse_args().data_root)
