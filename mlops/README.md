# DealRadar ML (Part 3)

A small classifier that reads review text and, for six aspects (battery, display, performance,
heating, camera, value_for_money), predicts positive / negative / none. The backend uses it for the aspect bars.

## Important: the included model is a DEMO
`make_demo_data.py` creates SYNTHETIC templated reviews, so the included model and its F1 score only prove the pipeline works. Train on real data before trusting it.

## Real workflow
```bash
cd mlops && pip install -r requirements.txt
python export_reviews.py data/reviews_raw.csv                 # reviews from your database
python label_reviews.py data/reviews_raw.csv data/train_v1.csv --limit 200   # Qwen labels (needs GROQ_API_KEY)
# Hand-label about 100 other reviews into data/gold.csv (same columns). Never train on it.
python train.py --train data/train_v1.csv --gold data/gold.csv
```
`train.py` trains a challenger, scores champion and challenger on the same gold set, and promotes only if the gate passes:
F1-macro >= 0.78, at least +0.01 over the champion, no aspect dropping more than 0.03.
Promotion copies the model to `backend/models/champion/` (commit it, it is small). Retraining on unchanged data is correctly REJECTED.

Set `MLFLOW_TRACKING_URI` (plus DAGsHub credentials) and `pip install mlflow` to log runs; this is wired up properly in Part 4.
Tests: `pytest`

## Part 4: automation
`retrain.py` is the weekly entry point (used by `.github/workflows/retrain-weekly.yml`): it finds new reviews, skips the week under 500,
labels them with Qwen, grows `data/train_current.csv` (tracked by DVC), then calls `train.run()`.
Commit your hand-checked `data/gold.csv` to Git (it is small and must never change silently).
