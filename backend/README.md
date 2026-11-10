# DealRadar backend (Part 1)

Paste an Amazon.in or Flipkart link, get price history, a Qwen-written verdict and a value score.
Part 1 runs on **sample data**, so it works with no scraping. Real scrapers come in a later part.

## Run locally
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # add GROQ_API_KEY to use Qwen
uvicorn app.main:app --reload
```
Open http://localhost:8000/docs and try `POST /api/analyze` with
`{"url": "https://www.amazon.in/some-phone/dp/B0EXAMPLE"}`.

Tests: `pytest`

## Use Supabase instead of SQLite
Copy the Postgres connection string from Supabase into `DATABASE_URL` in `.env`. Tables are created on startup (`schema.sql` is the same thing for reference).

## Deploy on Render (free)
New Web Service, root directory `backend`, build `pip install -r requirements.txt`,
start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check path `/api/health`.
Set `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `CORS_ORIGINS` (your Vercel URL) as environment variables.
