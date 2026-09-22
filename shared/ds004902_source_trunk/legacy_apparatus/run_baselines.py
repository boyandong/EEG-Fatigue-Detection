"""Source Only EEG baselines. One shared manifest and immutable subject splits."""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import joblib
import numpy as np
import torch
from scipy.signal import welch
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from torch.utils.data import Dataset, DataLoader


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def table(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def sync():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def now():
    sync()
    return time.perf_counter()


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


def metrics(y, score, threshold):
    pred = (np.asarray(score) >= threshold).astype(int)
    y = np.asarray(y)
    return {"accuracy": float(accuracy_score(y, pred)), "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "f1": float(f1_score(y, pred, pos_label=1, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else None,
            "n_segments": len(y), "n_true_positive_class": int(y.sum()), "n_predicted_positive": int(pred.sum()),
            "confusion_matrix": confusion_matrix(y, pred, labels=[0,1]).tolist()}


def subject_macro(rows, scores, threshold):
    subjects = sorted({r["subject"] for r in rows})
    return float(np.mean([metrics([r["label"] for r in rows if r["subject"] == s],
                                  [p for r,p in zip(rows,scores) if r["subject"] == s], threshold)["balanced_accuracy"] for s in subjects]))


class Corpus:
    def __init__(self, root):
        self.root = root
        self.splits = json.loads((root / "splits.json").read_text(encoding="utf-8"))
        assert sha(root / "segments.csv") == self.splits["manifest_sha256"]
        with (root / "segments.csv").open(encoding="utf-8-sig") as f:
            self.rows = list(csv.DictReader(f))
        assert len({r["segment_id"] for r in self.rows}) == len(self.rows)
        self.arrays = {}
        for r in self.rows:
            r["label"], r["array_index"] = int(r["label"]), int(r["array_index"])
            assert r["label"] == {"ses-1":0,"ses-2":1}[r["session"]]
            assert float(r["sfreq"]) == 500 and float(r["source_sfreq"]) == 500
            assert r["included"] == "True"
        provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
        expected_hashes = {k.replace("\\", "/"):v for k,v in provenance["output_hashes"].items()}
        for name in sorted({r["waveform_file"] for r in self.rows}):
            assert sha(root / name) == expected_hashes[name], name
            self.arrays[name] = np.load(root / name, mmap_mode="r")

    def wave(self, r):
        return np.asarray(self.arrays[r["waveform_file"]][r["array_index"]])

    def split_rows(self, fold, cap):
        groups = [set(fold[k]) for k in ["train","validation","test"]]
        assert not any(groups[i] & groups[j] for i,j in [(0,1),(0,2),(1,2)])
        assert set.union(*groups) == {r["subject"] for r in self.rows}
        output = {}
        for key in ["train","validation","test"]:
            selected, counts = [], {}
            for r in self.rows:
                pair = (r["subject"],r["session"])
                if r["subject"] in fold[key] and (cap is None or counts.get(pair,0) < cap):
                    selected.append(r)
                    counts[pair] = counts.get(pair,0)+1
            assert {r["label"] for r in selected} == {0,1}
            output[key] = selected
        return output


def fit_wave_scaler(corpus, rows):
    total = np.zeros(61, dtype=np.float64)
    squares = total.copy()
    n = 0
    for r in rows:
        x = corpus.wave(r).astype(np.float64)
        total += x.sum(axis=1)
        squares += np.square(x).sum(axis=1)
        n += x.shape[1]
    mean = total/n
    std = np.sqrt(np.maximum(squares/n - mean**2, 1e-12))
    return mean.astype(np.float32)[:,None], std.astype(np.float32)[:,None]


class Waves(Dataset):
    def __init__(self, corpus, rows, mean, std):
        self.corpus, self.rows, self.mean, self.std = corpus, rows, mean, std
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]
        x = (self.corpus.wave(r)-self.mean)/self.std
        return torch.from_numpy(x.copy()), r["label"]


def state_hash(model):
    h = hashlib.sha256()
    for k,v in model.state_dict().items():
        h.update(k.encode())
        h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def predict(model, loader, device):
    model.eval()
    assert all(not m.training for m in model.modules())
    values = []
    with torch.inference_mode():
        for x,_ in loader:
            logits = model(x.to(device))
            assert logits.ndim == 2 and logits.shape[1] == 2 and torch.isfinite(logits).all()
            values.extend(torch.softmax(logits, dim=1)[:,1].cpu().numpy().tolist())
    return np.array(values)


def build_model(name, cfg):
    from braindecode.models import EEGNet, Deep4Net
    cls = {"eegnet":EEGNet,"deepconvnet":Deep4Net}[name]
    return cls(n_chans=61, n_outputs=2, n_times=2000, sfreq=500, **cfg[name])


def train_neural(name, cfg, stage, corpus, split, out, seed):
    start = now()
    device = torch.device(cfg["device"])
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; choose CPU explicitly")
    seed_all(seed)
    t = now()
    mean,std = fit_wave_scaler(corpus, split["train"])
    np.savez(out / "normalization.npz", mean=mean, std=std)
    norm_time = now()-t
    datasets = {k:Waves(corpus,v,mean,std) for k,v in split.items()}
    loaders = {k:DataLoader(v,batch_size=cfg["batch_size"],shuffle=k=="train",num_workers=cfg["num_workers"],
                            generator=torch.Generator().manual_seed(seed),pin_memory=device.type=="cuda") for k,v in datasets.items()}
    model = build_model(name,cfg).to(device)
    (out / "model_architecture.txt").write_text(str(model),encoding="utf-8")
    optimizer = torch.optim.Adam(model.parameters(),lr=cfg["optimizer"]["lr"],weight_decay=cfg["optimizer"]["weight_decay"])
    criterion = torch.nn.CrossEntropyLoss()
    history, best_score, best_epoch, best, stale = [], -float("inf"), 0, None, 0
    if device.type=="cuda":
        torch.cuda.reset_peak_memory_stats()
    fit_start = now()
    for epoch in range(1,stage["max_epochs"]+1):
        epoch_start = now()
        model.train()
        total_loss,n = 0.0,0
        for x,y in loaders["train"]:
            x,y = x.to(device),y.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            assert logits.shape == (len(y),2)
            loss = criterion(logits,y)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss")
            loss.backward()
            optimizer.step()
            total_loss += loss.item()*len(y)
            n += len(y)
        train_seconds = now()-epoch_start
        val_start = now()
        scores = predict(model,loaders["validation"],device)
        val_seconds = now()-val_start
        ba = subject_macro(split["validation"],scores,0.5)
        history.append({"epoch":epoch,"train_loss":total_loss/n,"validation_subject_macro_balanced_accuracy":ba,
                        "validation_pooled_balanced_accuracy":metrics([r["label"] for r in split["validation"]],scores,0.5)["balanced_accuracy"],
                        "validation_predicted_positive_fraction":float(np.mean(scores>=0.5)),
                        "train_seconds":train_seconds,"validation_seconds":val_seconds,"epoch_seconds":now()-epoch_start})
        table(out / "history.csv",history)
        print(f"{name} seed={seed} epoch={epoch}: loss={total_loss/n:.4f} val_subject_BA={ba:.4f} sec={history[-1]['epoch_seconds']:.1f}",flush=True)
        if ba > best_score+cfg["early_stopping"]["min_delta"]:
            best_score,best_epoch,stale = ba,epoch,0
            best = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            torch.save({"state_dict":best,"epoch":best_epoch,"validation_score":best_score,"seed":seed,"model":name,"config":cfg},out / "best.pt")
        else:
            stale += 1
        if stale >= cfg["early_stopping"]["patience"]:
            break
    fit_seconds = now()-fit_start
    model.load_state_dict(best)
    model.eval()
    before = state_hash(model)
    t = now()
    score = predict(model,loaders["test"],device)
    test_seconds = now()-t
    after = state_hash(model)
    assert before == after, "Source Only violation: parameters or buffers changed on test"
    # Deterministic repeat and state invariance check is verification time, not inference time.
    t = now()
    repeat = predict(model,loaders["test"],device)
    np.testing.assert_array_equal(score,repeat)
    assert after == state_hash(model)
    audit_seconds = now()-t
    train_eval = DataLoader(datasets["train"],batch_size=cfg["batch_size"],shuffle=False,num_workers=0)
    t = now()
    train_score = predict(model,train_eval,device)
    diagnostics_seconds = now()-t
    train_metrics = metrics([r["label"] for r in split["train"]],train_score,0.5)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(1,2,figsize=(10,4))
    axes[0].plot([h["epoch"] for h in history],[h["train_loss"] for h in history])
    axes[0].set(xlabel="Epoch",ylabel="Training cross-entropy")
    axes[1].plot([h["epoch"] for h in history],[h["validation_subject_macro_balanced_accuracy"] for h in history])
    axes[1].axvline(best_epoch,color="gray",linestyle="--")
    axes[1].set(xlabel="Epoch",ylabel="Validation subject-macro balanced accuracy",ylim=(0,1))
    fig.tight_layout(); fig.savefig(out / "curves.png",dpi=160); plt.close(fig)
    return score,0.5,{"best_epoch":best_epoch,"epochs_run":len(history),"best_validation_subject_macro_ba":best_score,
                     "train_metrics":train_metrics,"loss_first":history[0]["train_loss"],"loss_last":history[-1]["train_loss"],
                     "test_state_unchanged":before==after,"test_repeat_identical":True,"test_state_sha256":before,
                     "parameter_count":sum(p.numel() for p in model.parameters()),
                     "runtime": {"normalization_fit_seconds":norm_time,"fit_including_validation_checkpoint_seconds":fit_seconds,
                                 "train_epochs_seconds":sum(h["train_seconds"] for h in history),"validation_epochs_seconds":sum(h["validation_seconds"] for h in history),
                                 "test_inference_seconds":test_seconds,"test_ms_per_segment":test_seconds/len(score)*1000,
                                 "source_only_audit_seconds":audit_seconds,"train_diagnostics_seconds":diagnostics_seconds,
                                 "model_total_seconds":now()-start,"peak_gpu_allocated_bytes":torch.cuda.max_memory_allocated() if device.type=="cuda" else 0}}


def features(corpus, rows, cfg):
    result = []
    for r in rows:
        x = corpus.wave(r).astype(np.float64)
        f,p = welch(x,fs=500,window="hann",nperseg=cfg["welch_nperseg"],noverlap=cfg["welch_noverlap"],
                    nfft=cfg["welch_nperseg"],detrend="constant",scaling="density",axis=-1,average="mean")
        bands = []
        for lo,hi in cfg["bands_hz"]:
            mask = (f>=lo)&(f<=hi)
            bands.append(np.log10(np.maximum(np.trapezoid(p[:,mask],f[mask],axis=-1),cfg["log_floor_uv2"])))
        result.append(np.stack(bands,axis=1).reshape(-1))
    a = np.array(result)
    assert a.shape == (len(rows),305) and np.isfinite(a).all()
    return a


def train_svm(cfg,corpus,split,out):
    start = now()
    times = {}
    X = {}
    for key,rows in split.items():
        t = now(); X[key]=features(corpus,rows,cfg["svm"]); times[key+"_feature_seconds"]=now()-t
    y = {k:np.array([r["label"] for r in rows]) for k,rows in split.items()}
    trials,best,best_score = [],None,-float("inf")
    t = now()
    for C in cfg["svm"]["C"]:
        for gamma in cfg["svm"]["gamma"]:
            pipe = Pipeline([("scale",StandardScaler()),("svc",SVC(kernel="rbf",C=C,gamma=gamma,class_weight=cfg["svm"]["class_weight"],
                        probability=False,cache_size=cfg["svm"]["cache_size_mb"],tol=cfg["svm"]["tol"],max_iter=cfg["svm"]["max_iter"]))])
            tfit=now(); pipe.fit(X["train"],y["train"]); fit_time=now()-tfit
            assert pipe["svc"].fit_status_ == 0
            tv=now(); score=pipe.decision_function(X["validation"]); val_time=now()-tv
            ba=subject_macro(split["validation"],score,0)
            trials.append({"C":C,"gamma":gamma,"validation_subject_macro_ba":ba,"fit_seconds":fit_time,"validation_seconds":val_time,
                           "validation_predicted_positive_fraction":float(np.mean(score>=0)),"fit_status":int(pipe["svc"].fit_status_)})
            if ba>best_score:
                best,best_score=pipe,ba
    times["grid_search_seconds"]=now()-t
    table(out / "svm_search.csv",trials)
    joblib.dump(best,out / "model.joblib")
    before=joblib.hash(best)
    t=now(); score=best.decision_function(X["test"]); times["test_inference_seconds"]=now()-t
    assert joblib.hash(best)==before
    times["test_ms_per_segment"]=times["test_inference_seconds"]/len(score)*1000
    times["test_end_to_end_seconds"]=times["test_inference_seconds"]+times["test_feature_seconds"]
    times["fit_candidates_seconds"]=sum(r["fit_seconds"] for r in trials)
    times["validation_candidates_seconds"]=sum(r["validation_seconds"] for r in trials)
    train_score=best.decision_function(X["train"])
    times["model_total_seconds"]=now()-start
    return score,0,{"definition":cfg["svm"]["definition"],"best_C":best["svc"].C,"best_gamma":best["svc"].gamma,
                    "best_validation_subject_macro_ba":best_score,"train_metrics":metrics(y["train"],train_score,0),
                    "test_state_unchanged":True,"runtime":times}


def aggregate(root):
    results=[json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*/*/seed_*/result.json"))]
    flat=[]
    for r in results:
        flat.append({"model":r["model"],"subject":r["subject"],"seed":r["seed"],
                     **{k:r["test_metrics"][k] for k in ["accuracy","balanced_accuracy","f1","roc_auc","n_segments","n_predicted_positive"]},
                     **r["details"]["runtime"]})
    # Runtime keys differ by model: use a union rather than discarding fields.
    if flat:
        keys=list(dict.fromkeys(k for r in flat for k in r))
        table(root / "per_subject_metrics_runtime.csv",[{k:r.get(k,"") for k in keys} for r in flat])
    per_seed=[]; combined=[]; per_subject=[]
    for model in sorted({r["model"] for r in results}):
        mr=[r for r in results if r["model"]==model]
        for seed in sorted({r["seed"] for r in mr}):
            sr=[r for r in mr if r["seed"]==seed]
            row={"model":model,"seed":seed,"n_subjects":len(sr)}
            for metric in ["accuracy","balanced_accuracy","f1","roc_auc"]:
                a=[r["test_metrics"][metric] for r in sr]
                row[metric+"_subject_mean"]=float(np.mean(a))
                row[metric+"_between_subject_sd"]=float(np.std(a,ddof=1)) if len(a)>1 else None
            per_seed.append(row)
        seeds=sorted({r["seed"] for r in mr})
        subjects=sorted({r["subject"] for r in mr})
        for subject in subjects:
            sr=[r for r in mr if r["subject"]==subject]
            row={"model":model,"subject":subject,"n_seeds":len(sr)}
            for metric in ["accuracy","balanced_accuracy","f1","roc_auc"]:
                a=[r["test_metrics"][metric] for r in sr]
                row[metric+"_seed_mean"]=float(np.mean(a))
                row[metric+"_seed_sd"]=float(np.std(a,ddof=1)) if len(a)>1 else None
            per_subject.append(row)
        if len(mr)==len(seeds)*len(subjects):
            for metric in ["accuracy","balanced_accuracy","f1","roc_auc"]:
                a=np.array([[next(r["test_metrics"][metric] for r in mr if r["subject"]==s and r["seed"]==seed) for s in subjects] for seed in seeds])
                combined.append({"model":model,"metric":metric,"n_subjects":len(subjects),"n_seeds":len(seeds),
                                 "grand_subject_mean":float(a.mean()),"between_subject_sd_after_seed_mean":float(a.mean(0).std(ddof=1)) if len(subjects)>1 else None,
                                 "between_seed_sd_of_subject_means":float(a.mean(1).std(ddof=1)) if len(seeds)>1 else None})
    table(root / "summary_per_seed.csv",per_seed)
    table(root / "summary_variability.csv",combined)
    table(root / "summary_per_subject_across_seeds.csv",per_subject)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",type=Path,default=Path(__file__).parent/"configs/baselines.json")
    parser.add_argument("--stage",choices=["smoke","pilot","formal"],required=True)
    parser.add_argument("--models",nargs="+",choices=["eegnet","deepconvnet","rbf_svm"])
    parser.add_argument("--run-name",required=True)
    parser.add_argument("--data-root",type=Path)
    parser.add_argument("--locked-config-sha256")
    args=parser.parse_args()
    start=now()
    cfg=json.loads(args.config.read_text(encoding="utf-8"))
    if args.stage=="formal" and args.locked_config_sha256!=sha(args.config):
        raise ValueError("Formal stage requires the exact frozen configuration SHA256")
    torch.set_num_threads(cfg["torch_threads"])
    data=(args.data_root or args.config.parent/cfg["data_root"]).resolve()
    root=(args.config.parent/cfg["results_root"]/args.run_name).resolve()
    root.mkdir(parents=True,exist_ok=True)
    provenance={"config_sha256":sha(args.config),"manifest_sha256":sha(data/"segments.csv"),"splits_sha256":sha(data/"splits.json"),
                "runner_sha256":sha(Path(__file__)),"stage":args.stage,"python":platform.python_version(),"os":platform.platform(),
                "gpu":torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "versions":{p:importlib.metadata.version(p) for p in ["torch","braindecode","scikit-learn","numpy","scipy","matplotlib"]}}
    provenance["source_manifest_sha256"]=sha(Path(__file__).parent/"third_party/sources.json")
    if (root/"provenance.json").exists():
        old=json.loads((root/"provenance.json").read_text(encoding="utf-8"))
        assert old==provenance,"Cannot mix settings, code, data or hardware in one run directory"
    dump(root/"provenance.json",provenance); dump(root/"config.json",cfg)
    t=now(); corpus=Corpus(data); load_seconds=now()-t
    stage=cfg["stages"][args.stage]
    folds=[f for f in corpus.splits["folds"] if stage["test_subjects"]=="all" or f["test"][0] in stage["test_subjects"]]
    for fold in folds:
        split=corpus.split_rows(fold,stage["max_segments_per_subject_session"])
        for name in args.models or cfg["models"]:
            seeds=[0] if name=="rbf_svm" else stage["seeds"]
            for seed in seeds:
                out=root/name/fold["test"][0]/f"seed_{seed}"
                if (out/"result.json").exists():
                    continue
                out.mkdir(parents=True,exist_ok=True)
                dump(out/"split.json",fold)
                table(out/"segment_membership.csv",[{"split":k,"segment_id":r["segment_id"],"subject":r["subject"],"label":r["label"]} for k,rr in split.items() for r in rr])
                t=now()
                if name=="rbf_svm":
                    score,threshold,details=train_svm(cfg,corpus,split,out)
                else:
                    score,threshold,details=train_neural(name,cfg,stage,corpus,split,out,seed)
                result={"stage":args.stage,"model":name,"subject":fold["test"][0],"seed":seed,
                        "test_metrics":metrics([r["label"] for r in split["test"]],score,threshold),"details":details}
                result["details"]["runtime"]["fold_model_wall_seconds"]=now()-t
                table(out/"predictions.csv",[{"segment_id":r["segment_id"],"subject":r["subject"],"session":r["session"],"y_true":r["label"],
                     "y_pred":int(s>=threshold),"score":float(s),"score_type":"decision_function" if name=="rbf_svm" else "positive_class_probability"} for r,s in zip(split["test"],score)])
                dump(out/"result.json",result)
                aggregate(root)
    dump(root/"invocation_runtime.json",{"shared_data_integrity_loading_seconds":load_seconds,"invocation_total_seconds":now()-start,
          "note":"Includes only this invocation; completed runs are skipped on resume. Shared loading is not charged to each model."})
    print("Stage completed:",args.stage,flush=True)


if __name__=="__main__":
    main()
