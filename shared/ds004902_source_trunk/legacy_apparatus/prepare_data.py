"""Immutable, shared EEG corpus and subject-only LOSO splits. No model fitting."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import warnings
from pathlib import Path

import numpy as np
import scipy
from pymatreader import read_mat


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def records(value):
    if isinstance(value, dict):
        n = len(next((v for v in value.values() if isinstance(v, list)), []))
        if not n:
            return [value]
        return [{k: v[i] if isinstance(v, list) else v for k, v in value.items()} for i in range(n)]
    return list(value) if isinstance(value, (list, np.ndarray)) else []


def read_eeg(path):
    with warnings.catch_warnings(record=True) as caught:
        d = read_mat(str(path))
    e = d.get("EEG", d)
    c, p, t = (int(e[k]) for k in ("nbchan", "pnts", "trials"))
    if min(c, p, t) < 1:
        raise ValueError("Invalid EEG dimensions")
    linked = None
    if isinstance(e["data"], str):
        linked = path.parent / Path(e["data"].replace("\\", "/")).name
        if linked.stat().st_size != c * p * t * 4:
            raise ValueError("FDT byte count does not match header")
        x = np.memmap(linked, dtype="<f4", mode="r", shape=(t, p, c)).transpose(0, 2, 1)
    else:
        a = np.asarray(e["data"])
        if a.shape != (c, p, t):
            if t == 1 and a.shape == (c, p):
                a = a[:, :, None]
            else:
                raise ValueError(f"Unexpected embedded data shape {a.shape}")
        x = a.transpose(2, 0, 1)
    return e, x, linked, [str(w.message) for w in caught]


def qc_epoch(x, qc):
    if not np.isfinite(x).all():
        return ["nonfinite"], {}
    std = np.std(x, axis=1, dtype=np.float64)
    peak = float(np.max(np.abs(x)))
    ptp = float(np.max(np.ptp(x, axis=1)))
    reasons = []
    if peak > qc["max_abs_uv"]:
        reasons.append("excessive_amplitude")
    if ptp > qc["max_peak_to_peak_uv"]:
        reasons.append("excessive_peak_to_peak")
    if np.min(std) < qc["min_channel_std_uv"]:
        reasons.append("flat_channel")
    return reasons, {"max_abs_uv": peak, "max_ptp_uv": ptp, "min_channel_std_uv": float(np.min(std))}


def make_splits(subjects, seed, fraction):
    folds = []
    for test in sorted(subjects):
        pool = sorted(set(subjects) - {test})
        # Stable per-fold seed; independent of model initialization seeds.
        fold_seed = int(hashlib.sha256(f"{seed}:{test}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(fold_seed)
        n = min(len(pool) - 1, max(1, math.ceil(len(pool) * fraction)))
        val = sorted(rng.choice(pool, n, replace=False).tolist())
        train = sorted(set(pool) - set(val))
        assert train and val and not set(train) & set(val)
        assert test not in train + val
        assert set(train + val + [test]) == set(subjects)
        folds.append({"fold_id": f"loso_{test}", "train": train, "validation": val, "test": [test]})
    return folds


def main(config_path):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    root, meta, out = [(config_path.parent / cfg[k]).resolve() for k in ("data_root", "metadata_root", "output_root")]
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}. Use a new output_root for a new version.")
    out.mkdir(parents=True)
    (out / "waveforms").mkdir()
    write_json(out / "config.json", cfg)
    participants_path = meta / "participants.tsv"
    with participants_path.open(encoding="utf-8-sig") as f:
        participants = {r["participant_id"]: r for r in csv.DictReader(f, delimiter="\t")}
    canonical_path = meta / "sub-01/ses-1/eeg/sub-01_ses-1_task-eyesopen_channels.tsv"
    with canonical_path.open(encoding="utf-8-sig") as f:
        canonical = [r["name"] for r in csv.DictReader(f, delimiter="\t") if r["type"] == "EEG"]
    write_json(out / "channels.json", canonical)
    all_segments, audits = [], []
    hashes = {str(p.relative_to(meta)): digest(p) for p in [participants_path, meta / "README", canonical_path]}
    for index, path in enumerate(sorted(root.glob("*.set"))):
        subject, session = path.stem.split("_")
        row = {"subject": subject, "session": session, "label": cfg["labels"].get(session), "file": path.name, "status": "excluded", "reason": ""}
        try:
            if subject not in participants or session not in cfg["labels"]:
                raise ValueError("Unknown subject/session")
            e, x, linked, read_warnings = read_eeg(path)
            fs = float(e["srate"])
            row["sfreq"] = fs
            if fs not in cfg["allowed_source_sfreq"]:
                raise ValueError("source_sfreq_excluded_by_config")
            names = [str(c["labels"]) for c in records(e["chanlocs"])]
            if len(set(names)) != len(names) or set(names) != set(canonical):
                raise ValueError("Channel set mismatch or duplicate channel names")
            order = [names.index(c) for c in canonical]
            row.update(sfreq=fs, channels=len(names), channel_order_matches=names == canonical,
                       source_epochs=len(x), samples_per_epoch=x.shape[-1], retained_duration_seconds=len(x)*x.shape[-1]/fs,
                       source_unit="uV (EEGLAB convention; raw metadata corroborates)",
                       reference=str(e.get("ref", "unknown")), reader_warnings="; ".join(read_warnings),
                       set_sha256=digest(path), fdt_sha256=digest(linked) if linked else "embedded")
            sidecar = meta / subject / session / "eeg" / f"{subject}_{session}_task-eyesopen_eeg.json"
            channels = sidecar.with_name(sidecar.name.replace("_eeg.json", "_channels.tsv"))
            if not sidecar.exists() or not channels.exists():
                raise ValueError("Missing metadata sidecars")
            raw_meta = json.loads(sidecar.read_text(encoding="utf-8-sig"))
            with channels.open(encoding="utf-8-sig") as f:
                raw_ch = list(csv.DictReader(f, delimiter="\t"))
            if any(r["units"] != cfg["input_unit"] for r in raw_ch if r["type"] == "EEG"):
                raise ValueError("Unsupported metadata signal units")
            row.update(metadata_sfreq=raw_meta["SamplingFrequency"], metadata_duration_seconds=raw_meta.get("RecordingDuration"),
                       metadata_sfreq_matches=float(raw_meta["SamplingFrequency"]) == fs)
            hashes[str(sidecar.relative_to(meta))] = digest(sidecar)
            hashes[str(channels.relative_to(meta))] = digest(channels)
            # Current source corpus is already epoched: never concatenate epochs.
            n = round(fs * cfg["segment_seconds"])
            if not np.isclose(n, fs * cfg["segment_seconds"]):
                raise ValueError("Nonintegral segment sample count")
            if len(x) == 1 and x.shape[-1] != n:
                raise ValueError("Continuous/single non-4s recording requires explicit boundary handling")
            if fs != cfg["target_sfreq"]:
                raise ValueError("Resampling is disabled for this experiment")
            events = records(e.get("event", []))
            boundaries = [float(v["latency"]) for v in events if str(v.get("type", "")).lower() == "boundary"]
            epoch_events = {}
            for ev in events:
                if "epoch" in ev:
                    epoch_events.setdefault(int(ev["epoch"]), []).append(ev)
            kept, local = [], []
            for ep, epoch in enumerate(x):
                for start in range(0, epoch.shape[-1] - n + 1, n):
                    seg = {"segment_id": f"{path.stem}_e{ep:04d}_s{start:06d}", "subject": subject,
                           "session": session, "label": cfg["labels"][session], "source_file": path.name,
                           "source_epoch_index": ep, "start_sample_in_epoch": start, "stop_sample_exclusive": start+n,
                           "source_sfreq": fs, "sfreq": cfg["target_sfreq"], "unit": cfg["output_unit"],
                           "waveform_file": f"waveforms/{path.stem}.npy", "array_index": -1,
                           "source_urevents": json.dumps([float(v["urevent"]) for v in epoch_events.get(ep+1, []) if np.isscalar(v.get("urevent"))]),
                           "qc_pass": False, "included": False}
                    a = np.asarray(epoch[order, start:start+n], dtype=np.float32)
                    reasons, measures = qc_epoch(a, cfg["qc"])
                    # EEGLAB boundary latencies are 1-based, often half-integers.
                    if any(ep*epoch.shape[-1]+start+1 < b <= ep*epoch.shape[-1]+start+n for b in boundaries):
                        reasons.append("boundary_crossing")
                    seg.update(measures)
                    if not reasons:
                        a = a.copy()
                        if a.shape != (len(canonical), cfg["target_sfreq"] * cfg["segment_seconds"]) or not np.isfinite(a).all():
                            raise ValueError("Invalid resampled waveform")
                        seg["array_index"] = len(kept)
                        seg["qc_pass"] = True
                        kept.append(a.astype(np.float32))
                    seg["exclusion_reason"] = ";".join(reasons)
                    local.append(seg)
            row.update(candidate_segments=len(local), qc_pass_segments=len(kept), rejected_segments=len(local)-len(kept),
                       discarded_tail_samples=len(x)*(x.shape[-1] % n), resampled=fs != cfg["target_sfreq"],
                       max_abs_uv=max((r.get("max_abs_uv", 0) for r in local), default=0))
            if kept:
                np.save(out / "waveforms" / f"{path.stem}.npy", np.stack(kept))
            row["status"] = "readable"
            all_segments.extend(local)
        except Exception as exc:
            row["reason"] = f"{type(exc).__name__}: {exc}"
        audits.append(row)
        print(f"[{index+1}] {path.stem}: {row['status']} {row.get('qc_pass_segments', 0)} segments {row['reason']}", flush=True)
    counts = {(r["subject"], r["session"]): r.get("qc_pass_segments", 0) if r["status"] == "readable" else 0 for r in audits}
    usable = sorted(s for s in participants if all(counts.get((s, session), 0) >= cfg["qc"]["min_segments_per_session"] for session in cfg["labels"]))
    for seg in all_segments:
        seg["included"] = seg["qc_pass"] and seg["subject"] in usable
        if seg["qc_pass"] and not seg["included"]:
            seg["exclusion_reason"] = "subject_missing_usable_session"
    subject_rows = [{"subject": s, "included": s in usable, "ses1_segments": counts.get((s, "ses-1"), 0),
                     "ses2_segments": counts.get((s, "ses-2"), 0),
                     "reason": "" if s in usable else "missing_or_insufficient_usable_session"} for s in sorted(participants)]
    write_csv(out / "recordings.csv", audits)
    write_csv(out / "segments_all.csv", all_segments)
    valid = [r for r in all_segments if r["included"]]
    write_csv(out / "segments.csv", valid)
    write_csv(out / "subjects.csv", subject_rows)
    if len(usable) < 3:
        raise ValueError("Fewer than three paired subjects; see audit outputs")
    folds = make_splits(usable, cfg["split_seed"], cfg["validation_fraction"])
    write_json(out / "splits.json", {"manifest_sha256": digest(out / "segments.csv"), "split_seed": cfg["split_seed"],
               "shared_by": ["EEGNet", "DeepConvNet", "RBF-SVM"], "pilot_test_subjects": cfg["pilot_test_subjects"],
               "pilot_available": all(s in usable for s in cfg["pilot_test_subjects"]), "folds": folds})
    versions = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    write_json(out / "provenance.json", {"versions": versions, "metadata_hashes": hashes,
               "script_sha256": digest(Path(__file__)), "config_sha256": digest(config_path),
               "output_hashes": {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    report = ["# Source Only 数据检查报告", "", f"检查 {len(audits)} 份 SET，成功读取 {sum(r['status']=='readable' for r in audits)} 份。",
              f"成对可用受试者 {len(usable)}/{len(participants)}；最终共享片段 {len(valid)} 个（0类 {sum(r['label']==0 for r in valid)}，1类 {sum(r['label']==1 for r in valid)}）。",
              "", "ses-1=0 正常睡眠；ses-2=1 睡眠剥夺实验条件，不等于实际危险。依据本地 metadata_behavior/README。PVT 未参与标签、筛选或划分。",
              "", "## 切片与质量规则", "",
              "源文件已分段；每个原有 epoch 内按4秒不重叠切分，丢弃尾部，不拼接不同 epoch。索引从0开始，stop为开区间。源epoch索引不是原始连续时间；urevent仅用于追溯。",
              "61通道按 channels.json 排序，仅纳入原采样率500 Hz，每段形状(61,2000)，float32，uV。按用户要求排除5000 Hz记录；该受试者因缺少可用配对场次整体排除。本版不降采样。",
              "单位依据EEGLAB存储惯例和对应原始 channels.tsv 的uV；预处理文件缺少独立的单位标定证明，因此保留此溯源限制。",
              f"预先固定规则：{json.dumps(cfg['qc'], ensure_ascii=False)}。任一通道非有限值、过大振幅、过大峰峰值或近乎平坦时整段排除。每个场次至少1个通过片段才能成对纳入。阈值为首版工程规则，不能视为人工伪迹审查或质量认证。",
              "未根据类别效果、测试分数或数据分位数调阈值；未做标准化。预处理历史不完整，无法证明原有预处理完全没有跨受试者拟合；Source Only约束从本次共享输入开始。",
              "", "## 按人划分", "",
              f"固定种子 {cfg['split_seed']}；每折留1人测试，其余人向上取整20%验证，剩余训练。两场次始终同行。神经网络初始化种子不改变名单；SVM只需使用同一名单。",
              f"预先指定试跑测试人：{', '.join(cfg['pilot_test_subjects'])}；本轮未训练模型。",
              "测试阶段必须eval关闭Dropout并冻结BN；输入标准化和特征选择只在train拟合，validation仅选参，test只作最后评估，禁用TTA。",
              "", "## 逐记录摘要", "", "|记录|Hz|保留秒数|通过/候选片段|状态/原因|", "|---|---:|---:|---:|---|"]
    for r in audits:
        report.append(f"|{r['file']}|{r.get('sfreq','')}|{r.get('retained_duration_seconds','')}|{r.get('qc_pass_segments',0)}/{r.get('candidate_segments',0)}|{r['status']} {r['reason']}|")
    report += ["", "详见 recordings.csv（文件/通道/采样率/时长/哈希）、segments_all.csv（全部候选与排除理由）、segments.csv（唯一训练输入名单）、subjects.csv（成对纳入）、splits.json（全部LOSO）。", "", "极短场次不会被人为补齐；受试者间样本数差异必须在后续逐受试者指标中报告。眼睛状态与预处理确切步骤需保留来源限制，当前文件名没有独立任务标记。"]
    (out / "report.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(f"DONE: {len(usable)} subjects, {len(valid)} segments")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs/source_only_data.json")
    args = parser.parse_args()
    main(args.config.resolve())
