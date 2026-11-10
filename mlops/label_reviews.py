"""Uses Qwen on Groq to label reviews. Input: CSV with a review_text column. Output: labeled CSV.
Usage: python label_reviews.py data/reviews_raw.csv data/train_v1.csv --limit 200
Spot-check about 10% of the output by hand before training on it."""
import argparse
import json
import os
import re
import time

import httpx
import pandas as pd
from dotenv import load_dotenv

from aspects import ASPECTS, LABELS

load_dotenv()
URL = "https://api.groq.com/openai/v1/chat/completions"
SYSTEM = (
    "You label smartphone and laptop reviews. For EACH review decide, for each aspect in "
    f"{ASPECTS}, whether the reviewer is 'positive', 'negative', or 'none' (aspect not mentioned). "
    "Reply with ONLY a JSON array with one object per review, in the same order, with exactly those aspect keys."
)


def parse_labels(raw: str, n: int):
    """Turn the model reply into n label dicts. Invalid items become None so they can be dropped."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    s, e = raw.find("["), raw.rfind("]")
    items = json.loads(raw[s : e + 1]) if s != -1 and e != -1 else []
    out = []
    for i in range(n):
        item = items[i] if i < len(items) and isinstance(items[i], dict) else None
        if item and all(item.get(a) in LABELS for a in ASPECTS):
            out.append({a: item[a] for a in ASPECTS})
        else:
            out.append(None)
    return out


def label_batch(texts):
    body = {
        "model": os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        "temperature": 0,
        "max_tokens": 2500,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(f"{i + 1}. {t[:400]}" for i, t in enumerate(texts))},
        ],
    }
    r = httpx.post(URL, json=body, headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}, timeout=60)
    r.raise_for_status()
    return parse_labels(r.json()["choices"][0]["message"]["content"], len(texts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"), ap.add_argument("dst")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args()
    texts = pd.read_csv(a.src)["review_text"].dropna().drop_duplicates().tolist()[: a.limit]
    rows = []
    for i in range(0, len(texts), a.batch):
        chunk = texts[i : i + a.batch]
        try:
            labels = label_batch(chunk)
        except Exception as ex:
            print("batch failed, skipping:", ex)
            labels = [None] * len(chunk)
        rows += [{"review_text": t, **l} for t, l in zip(chunk, labels) if l]
        print(f"{min(i + a.batch, len(texts))}/{len(texts)} labeled, {len(rows)} kept")
        time.sleep(2)  # stay under the free-tier rate limit
    pd.DataFrame(rows).to_csv(a.dst, index=False)
    print("wrote", a.dst)
