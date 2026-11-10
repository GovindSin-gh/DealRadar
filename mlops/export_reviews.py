"""Dump reviews from the app database to CSV, ready for label_reviews.py."""
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
url = os.getenv("DATABASE_URL", "sqlite:///../backend/dealradar.db").replace("postgres://", "postgresql://", 1)
dst = sys.argv[1] if len(sys.argv) > 1 else "data/reviews_raw.csv"
pd.read_sql("select review_text from raw_reviews", create_engine(url)).to_csv(dst, index=False)
print("wrote", dst)
