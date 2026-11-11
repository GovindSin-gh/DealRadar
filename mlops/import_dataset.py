"""Turn a public review dataset (for example one downloaded from Kaggle) into data/reviews_raw.csv,
ready for label_reviews.py. Use this when shop pages do not give you enough reviews to train on.

  python import_dataset.py --src reviews.csv --text-col "Review text" --out data/reviews_raw.csv --limit 3000

Check the dataset's licence allows this use. By default only reviews that mention at least one of the six aspects are
kept (otherwise most rows would just be 'none'), reviews are de-duplicated, and very short or very long ones are dropped.
"""
import argparse
import re

import pandas as pd

KEYWORDS = r"battery|charg|display|screen|perform|speed|lag|hang|heat|hot|warm|camera|photo|picture|price|value|money|worth"


def clean(df: pd.DataFrame, text_col: str, limit: int = 3000, keyword_filter: bool = True,
          min_len: int = 30, max_len: int = 600, seed: int = 1, exclude=None) -> pd.DataFrame:
    if text_col not in df.columns:
        raise SystemExit(f"Column '{text_col}' not found. Columns are: {list(df.columns)}")
    text = df[text_col].dropna().astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    text = text[text.str.len().between(min_len, max_len)].drop_duplicates()
    if exclude:  # keep the gold set disjoint from the training set
        text = text[~text.isin(set(exclude))]
    if keyword_filter:
        text = text[text.str.contains(KEYWORDS, flags=re.I, regex=True)]
    if len(text) > limit:
        text = text.sample(limit, random_state=seed)
    return pd.DataFrame({"review_text": text.tolist()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--text-col", required=True, help="name of the column that holds the review text")
    ap.add_argument("--out", default="data/reviews_raw.csv")
    ap.add_argument("--limit", type=int, default=3000)
    ap.add_argument("--no-keyword-filter", action="store_true")
    ap.add_argument("--exclude", help="CSV with a review_text column whose reviews must NOT be included (use the training file when building the gold set)")
    a = ap.parse_args()
    raw = pd.read_csv(a.src, encoding_errors="replace", on_bad_lines="skip")
    skip = pd.read_csv(a.exclude)["review_text"].astype(str).tolist() if a.exclude else None
    out = clean(raw, a.text_col, a.limit, not a.no_keyword_filter, exclude=skip)
    out.to_csv(a.out, index=False)
    print(f"read {len(raw)} rows, kept {len(out)} reviews -> {a.out}")
