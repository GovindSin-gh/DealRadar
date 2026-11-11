# DealRadar

Paste an Amazon.in or Flipkart link for a smartphone or laptop and get price history, what reviewers say about each part (battery, heating, display...), and a buy-or-wait verdict. Runs on free tiers only.

```
User -> React (Vercel) -> FastAPI (Render) -> PostgreSQL (Supabase)
                                   |-> aspect classifier (scikit-learn, in the API)
                                   '-> Qwen via Groq (verdict)
GitHub Actions: daily update | weekly retrain -> DVC + MLflow (DAGsHub) -> quality gate -> commit model -> Render redeploys
```

| Folder | What it is |
|---|---|
| `backend/` | FastAPI app, scraper, daily job, champion model in `models/champion/` |
| `frontend/` | React + Tailwind UI |
| `mlops/` | labeling, training, quality gate, weekly retrain script |
| `.github/workflows/` | CI, daily update, weekly retrain, keep-alive |
| `docs/explainable.html` | **Complete interactive documentation**: architecture, API, ML, deployment checklist, troubleshooting. Open it in any browser. |

> New here? Open `docs/explainable.html` first. It explains everything in plain language and has the full deployment checklist.

## Honest status
- **Data is sample data by default.** Set `LIVE_SCRAPING=true` for best-effort Amazon.in and Flipkart parsing. Both parsers are tested on saved page samples only. Shops block bots and GitHub's IP addresses are often blocked, so expect failures, and check each site's terms first.
- **Reviews:** shop pages often show a program few or no reviews. Then the verdict is labeled "price only". Train the classifier on a public review dataset (`mlops/import_dataset.py`), not on scraped pages.
- **Price-drop emails** need an SMTP account (a Gmail app password works). Without one the daily job skips sending and retries once it is configured.
- **The included model is a demo** trained on synthetic reviews. Replace it with real data (see `mlops/README.md`).

## Features
Price and review analysis, aspect bars from a trained classifier, Qwen verdicts, price history chart, price-drop email alerts with unsubscribe links, Amazon.in and Flipkart parsers, database-backed rate limits, system logs (`GET /api/logs`), daily and weekly automation, and a cross-file audit (`make verify`).

## Setup, in order
1. **Supabase:** create a project, copy the Postgres connection string.
2. **Groq:** create a free API key at console.groq.com.
3. **GitHub:** push this repo (public repos get free Actions minutes).
4. **Render:** new Web Service from the repo. Root `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`. Env vars: `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `CORS_ORIGINS`.
5. **Vercel:** import the repo, root `frontend`, env `VITE_API_URL` = your Render URL.
6. **DAGsHub:** connect the GitHub repo (name it `dealradar`, or edit the URI in `retrain-weekly.yml`). Then, locally:
   ```bash
   pip install "dvc>=3" && dvc init
   dvc remote add origin https://dagshub.com/<user>/dealradar.dvc && dvc remote default origin
   git add .dvc && git commit -m "Set up DVC"
   ```
7. **GitHub secrets** (Settings > Secrets and variables > Actions):

| Name | Kind | Used by |
|---|---|---|
| `DATABASE_URL` | secret | daily update, retrain |
| `GROQ_API_KEY` | secret | retrain (labeling) |
| `DAGSHUB_USER`, `DAGSHUB_TOKEN` | secret | retrain (DVC + MLflow) |
| `RENDER_DEPLOY_HOOK_URL` | secret, optional | deploy after a new model |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | secrets, optional | price-drop emails (daily job) |
| `SMTP_PORT` | variable, optional | mail port, default 587 |
| `API_URL` | variable | keep-alive ping |
| `LIVE_SCRAPING` | variable, optional | daily update |

## How the weekly loop works
Sunday 00:00 UTC (5:30 AM IST): find reviews not yet trained on -> skip the week if fewer than 500 -> Qwen labels them -> DVC snapshots the dataset -> train a challenger -> both models take the same hand-checked gold-set exam -> promote only if F1-macro >= 0.78, at least +0.01 better, and no aspect drops more than 0.03 -> commit the model -> Render redeploys, switching traffic only after `/api/health` passes. **Rollback:** revert the model commit.

## Free-tier traps
Supabase pauses after about 7 idle days (the daily job keeps it active). GitHub disables scheduled workflows after 60 days without repo activity. Render sleeps after about 15 idle minutes (keep-alive workflow plus the UI's waiting message).
