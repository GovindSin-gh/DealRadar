"""Train a challenger, test it on the gold set, run the gate, promote if it passes.
python train.py --train data/train_v1.csv --gold data/gold.csv"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
from datetime import datetime, timezone

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from aspects import ASPECTS
from gate import decide


def load(path):
    df = pd.read_csv(path).dropna(subset=["review_text"])
    return df["review_text"].tolist(), {a: df[a].tolist() for a in ASPECTS}


def fit(texts, labels, version, note=""):
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    X = vec.fit_transform(texts)
    models = {}
    for a in ASPECTS:
        if len(set(labels[a])) < 2:
            raise ValueError(f"aspect '{a}' has only one class in the training data")
        models[a] = LogisticRegression(C=4, class_weight="balanced", max_iter=1000).fit(X, labels[a])
    return {"vectorizer": vec, "models": models, "aspects": ASPECTS, "version": version, "note": note}


def evaluate(art, texts, labels):
    X = art["vectorizer"].transform(texts)
    per = {a: float(f1_score(labels[a], art["models"][a].predict(X), average="macro")) for a in ASPECTS}
    return {"f1_macro": sum(per.values()) / len(per), "per_aspect": per}


def log_mlflow(params, metrics, art_path, decision):
    if not os.getenv("MLFLOW_TRACKING_URI"):
        return
    import mlflow  # optional dependency
    mlflow.set_experiment("dealradar-aspects")
    with mlflow.start_run():
        mlflow.log_params(params)
        mlflow.log_metrics({"f1_macro": metrics["f1_macro"], **{f"f1_{a}": v for a, v in metrics["per_aspect"].items()}})
        mlflow.set_tag("gate_decision", decision)
        mlflow.log_artifact(art_path)


def run(train_path, gold_path, champion_dir, note="", promote_allowed=True):
    """Train a challenger, test both models on the gold set, apply the gate, promote if it passes."""
    data_hash = hashlib.sha256(pathlib.Path(train_path).read_bytes()).hexdigest()[:7]
    version = f"{datetime.now(timezone.utc):%Y%m%d}-{data_hash}"
    texts, labels = load(train_path)
    gold_texts, gold_labels = load(gold_path)
    challenger = fit(texts, labels, version, note)
    ch_metrics = evaluate(challenger, gold_texts, gold_labels)

    champ_dir = pathlib.Path(champion_dir)
    champ_path, champion, champ_metrics = champ_dir / "model.joblib", None, None
    if champ_path.exists():
        champion = joblib.load(champ_path)
        champ_metrics = evaluate(champion, gold_texts, gold_labels)  # same exam for both

    promote, reasons = decide(ch_metrics, champ_metrics)
    print(f"challenger {version}: F1-macro {ch_metrics['f1_macro']:.3f}")
    for k, v in ch_metrics["per_aspect"].items():
        print(f"   {k:16s} {v:.3f}")
    if champ_metrics:
        print(f"champion {champion['version']}: F1-macro {champ_metrics['f1_macro']:.3f}")
    print("DECISION:", "PROMOTE" if promote else "REJECT", "-", "; ".join(reasons))

    tmp = pathlib.Path("models") / version
    tmp.mkdir(parents=True, exist_ok=True)
    joblib.dump(challenger, tmp / "model.joblib")
    (tmp / "metrics.json").write_text(json.dumps({**ch_metrics, "decision": promote, "reasons": reasons}, indent=2))
    log_mlflow({"train": str(train_path), "data_hash": data_hash, "train_rows": len(texts)}, ch_metrics, str(tmp / "model.joblib"), str(promote))
    promoted = promote and promote_allowed
    if promoted:
        champ_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(tmp / "model.joblib", champ_path)
        shutil.copy(tmp / "metrics.json", champ_dir / "metrics.json")
        print("promoted to", champ_path)
    return {"promoted": promoted, "version": version, "metrics": ch_metrics, "reasons": reasons}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="data/train_v1.csv")
    ap.add_argument("--gold", default="data/gold.csv")
    ap.add_argument("--champion-dir", default="../backend/models/champion")
    ap.add_argument("--note", default="")
    ap.add_argument("--no-promote", action="store_true")
    a = ap.parse_args()
    run(a.train, a.gold, a.champion_dir, a.note, not a.no_promote)
