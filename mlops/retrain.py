"""Weekly retraining, run by GitHub Actions.
1. Find reviews in the database we have not trained on yet (the delta).
2. Skip the week if there are fewer than MIN_NEW_REVIEWS (default 500).
3. Label the delta with Qwen, add it to data/train_current.csv.
4. Train a challenger and run the champion-vs-challenger gate (train.run).
Writes `trained` and `promoted` to GITHUB_OUTPUT so later workflow steps know what happened."""
import os
import pathlib
import time

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

import label_reviews
import train

load_dotenv()
MIN_NEW = int(os.getenv("MIN_NEW_REVIEWS", "500"))
MAX_LABEL = int(os.getenv("MAX_LABEL_PER_RUN", "1500"))  # protects the free Groq quota
CURRENT, SEED, GOLD = pathlib.Path("data/train_current.csv"), pathlib.Path("data/train_v1.csv"), pathlib.Path("data/gold.csv")


def new_reviews(db_texts, known):
    """Texts in the database that the training set has not seen, without duplicates."""
    seen, out = set(known), []
    for t in db_texts:
        t = str(t).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def label_all(texts, label_fn=label_reviews.label_batch, batch=8, sleep=2):
    rows = []
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        try:
            labels = label_fn(chunk)
        except Exception as e:
            print("labeling batch failed, skipping:", e)
            labels = [None] * len(chunk)
        rows += [{"review_text": t, **l} for t, l in zip(chunk, labels) if l]
        time.sleep(sleep)
    return rows


def set_output(**kw):
    line = "\n".join(f"{k}={v}" for k, v in kw.items()) + "\n"
    print(line, end="")
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(line)


def main():
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
    db_texts = pd.read_sql("select review_text from raw_reviews", create_engine(url))["review_text"].tolist()
    base = pd.read_csv(CURRENT if CURRENT.exists() else SEED)
    fresh = new_reviews(db_texts, base["review_text"])
    print(f"{len(db_texts)} reviews in database, {len(fresh)} new since last training")
    if len(fresh) < MIN_NEW and not os.getenv("FORCE"):
        print(f"Skipping: fewer than {MIN_NEW} new reviews")
        return set_output(trained="false", promoted="false")
    rows = label_all(fresh[:MAX_LABEL])
    print(f"{len(rows)} of {min(len(fresh), MAX_LABEL)} reviews labeled confidently")
    if not rows:
        return set_output(trained="false", promoted="false")
    pd.concat([base, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("review_text").to_csv(CURRENT, index=False)
    res = train.run(str(CURRENT), str(GOLD), "../backend/models/champion", note="weekly")
    set_output(trained="true", promoted=str(res["promoted"]).lower(), version=res["version"])


if __name__ == "__main__":
    main()
