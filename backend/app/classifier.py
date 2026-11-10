"""Runs the champion aspect classifier (trained in /mlops) on a product's reviews."""
import logging
from functools import lru_cache
from pathlib import Path

import joblib

from .config import settings

log = logging.getLogger("dealradar.classifier")
MIN_MENTIONS = 3  # hide an aspect if too few reviews talk about it


@lru_cache
def _load():
    path = Path(settings.model_path)
    if not path.exists():
        log.warning("No champion model at %s, aspect bars disabled", path)
        return None
    try:
        return joblib.load(path)
    except Exception as e:  # corrupt file or incompatible scikit-learn version
        log.warning("Could not load model: %s", e)
        return None


def predict(texts: list[str]) -> tuple[list[dict], str | None]:
    art = _load()
    if art is None or not texts:
        return [], None
    X = art["vectorizer"].transform(texts)
    out = []
    for aspect in art["aspects"]:
        model = art["models"][aspect]
        proba, classes = model.predict_proba(X), list(model.classes_)
        pred = [classes[i] for i in proba.argmax(axis=1)]
        pos, neg = pred.count("positive"), pred.count("negative")
        n = pos + neg
        if n < MIN_MENTIONS:
            continue
        dominant = "positive" if pos >= neg else "negative"
        order = sorted((i for i, p in enumerate(pred) if p == dominant), key=lambda i: -proba[i][classes.index(dominant)])
        snippets = []
        for i in order:
            t = texts[i][:200]
            if t not in snippets:
                snippets.append(t)
            if len(snippets) == 2:
                break
        p = round(100 * pos / n)
        out.append({"aspect": aspect, "mentions": n, "positive_pct": p, "negative_pct": 100 - p, "snippets": snippets})
    return out, art.get("version")
