# DealRadar frontend (Part 2)

React + Vite + Tailwind. Talks to the FastAPI backend from Part 1.

## Run locally
```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL=http://localhost:8000
npm run dev               # http://localhost:5173
```
Start the backend first (`uvicorn app.main:app --reload` in `backend/`).

## Deploy on Vercel (free)
Import the repo, set **Root Directory** to `frontend`, add the environment variable
`VITE_API_URL` = your Render backend URL, then deploy. Afterwards set `CORS_ORIGINS` on Render to your Vercel URL.
