"""Validate shared inputs, saved metrics, train-only scaler and source fidelity."""
import argparse
import csv
import inspect
import json
from pathlib import Path
import numpy as np
import sklearn.svm._classes
import braindecode.models.eegnet
import braindecode.models.deep4
from run_baselines import Corpus, metrics, sha, dump

def read_rows(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def verify(root,data):
    project=Path(__file__).resolve().parent
    comparisons=[(braindecode.models.eegnet, project/"third_party/braindecode-1.3.2/braindecode/models/eegnet.py"),
                 (braindecode.models.deep4, project/"third_party/braindecode-1.3.2/braindecode/models/deep4.py"),
                 (sklearn.svm._classes, project/"third_party/scikit-learn/sklearn/svm/_classes.py")]
    source_checks={str(source.relative_to(project)):Path(inspect.getfile(module)).read_text(encoding="utf-8")==source.read_text(encoding="utf-8") for module,source in comparisons}
    assert all(source_checks.values()),source_checks
    corpus=Corpus(data)
    config=json.loads((root/"config.json").read_text(encoding="utf-8"))
    references={}
    checked=[]
    for result_path in sorted(root.glob("*/*/seed_*/result.json")):
        out=result_path.parent
        result=json.loads(result_path.read_text(encoding="utf-8"))
        membership=read_rows(out/"segment_membership.csv")
        key=result["subject"]
        if key in references:
            assert membership==references[key],"Models or seeds used different segments"
        references[key]=membership
        actual=read_rows(out/"predictions.csv")
        assert [r["segment_id"] for r in actual]==[r["segment_id"] for r in membership if r["split"]=="test"]
        y=np.array([int(r["y_true"]) for r in actual]); score=np.array([float(r["score"]) for r in actual])
        threshold=0 if result["model"]=="rbf_svm" else 0.5
        expected=metrics(y,score,threshold)
        assert expected==result["test_metrics"]
        assert all(int(r["y_pred"])==int(s>=threshold) for r,s in zip(actual,score))
        assert result["details"]["test_state_unchanged"]
        assert all(v>=0 for k,v in result["details"]["runtime"].items() if k.endswith("seconds"))
        if result["model"]!="rbf_svm":
            assert result["details"]["test_repeat_identical"]
            assert (out/"curves.png").stat().st_size>1000
            train_ids={r["segment_id"] for r in membership if r["split"]=="train"}
            # Independent concatenate reduction on smoke only (full corpus would exceed RAM).
            if result["stage"]=="smoke":
                x=np.stack([corpus.wave(r) for r in corpus.rows if r["segment_id"] in train_ids]).astype(np.float64)
                saved=np.load(out/"normalization.npz")
                np.testing.assert_allclose(saved["mean"].ravel(),x.mean(axis=(0,2)),rtol=1e-5,atol=1e-6)
                np.testing.assert_allclose(saved["std"].ravel(),x.std(axis=(0,2)),rtol=1e-5,atol=1e-6)
        checked.append(str(out.relative_to(root)))
    assert checked
    # AUC uses ranking scores: hard predictions here are identical, rankings differ.
    a=metrics([0,1],[0.1,0.4],0.5); b=metrics([0,1],[0.4,0.1],0.5)
    assert a["accuracy"]==b["accuracy"] and a["roc_auc"]==1 and b["roc_auc"]==0
    dump(root/"verification.json",{"status":"passed","checked_runs":checked,"source_matches_after_newline_normalization":source_checks,
             "checks":["shared segment membership across models/seeds","saved metrics recomputed","continuous-score AUC","predictions align to test manifest","train-only normalization independently recomputed for smoke","test state frozen","nonnegative runtime","curve files exist"]})
    print("Verified",len(checked),"runs")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--run-root",type=Path,required=True)
    p.add_argument("--data-root",type=Path,default=Path(__file__).parent/"outputs/source_only_500hz_v1")
    a=p.parse_args(); verify(a.run_root,a.data_root)
