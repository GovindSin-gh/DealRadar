"""DealRadar API. Routes: POST /api/analyze, GET /api/products/{id}, POST /api/watch,
GET /api/unsubscribe, GET /api/logs (admin), GET /api/health."""
import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from secrets import token_urlsafe

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from . import classifier, llm, providers, scrape_queue, store
from .config import settings
from .db import Base, PriceHistory, Product, RawReview, RequestCount, SystemLog, Watch, engine, get_db, log_event, utcnow
from .schemas import AnalyzeRequest, ProductOut, WatchOut, WatchRequest

MAX_WATCHES_PER_EMAIL = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DealRadar API", version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


# ---------- helpers ----------
def _stats(prices: list[float], current: float) -> dict:
    avg = sum(prices) / len(prices)
    return {"avg": avg, "min": min(prices), "max": max(prices), "pct": (current / avg - 1) * 100}


def _response(p: Product, db: Session, cached: bool) -> dict:
    hist = db.scalars(select(PriceHistory).where(PriceHistory.product_id == p.id).order_by(PriceHistory.scraped_at)).all()
    s = _stats([h.price for h in hist], p.current_price)
    n = db.scalar(select(func.count()).select_from(RawReview).where(RawReview.product_id == p.id))
    return {
        "id": p.id, "title": p.title, "shop": p.shop, "category": p.category, "url": p.url,
        "current_price": p.current_price, "review_count": n,
        "price_history": [{"date": h.scraped_at, "price": h.price} for h in hist],
        "price_stats": {"average": round(s["avg"]), "lowest": s["min"], "highest": s["max"], "percent_vs_average": round(s["pct"], 1)},
        "analysis": json.loads(p.analysis_json), "analyzed_at": p.analyzed_at, "cached": cached,
    }


def _client_id(request: Request) -> str:
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")).split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:16]  # store a hash, never the raw IP


def _check_rate_limit(db: Session, key: str, limit: int, what: str, hint: str = "") -> None:
    """Counts per visitor per clock hour in the database (memory would reset whenever Render's free server sleeps)."""
    now = utcnow()
    window = now.strftime("%Y%m%d%H")
    db.execute(delete(RequestCount).where(RequestCount.window < (now - timedelta(hours=24)).strftime("%Y%m%d%H")))
    row = db.get(RequestCount, (key, window))
    if row and row.count >= limit:
        wait = 3600 - (now.minute * 60 + now.second)
        raise HTTPException(429, f"Limit reached: {limit} {what} per hour. {hint}Try again in {wait // 60 + 1} minutes.", headers={"Retry-After": str(wait)})
    if row:
        row.count += 1
    else:
        db.add(RequestCount(client_id=key, window=window, count=1))
    db.commit()


# ---------- routes ----------
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("select 1"))
        db_ok = True
    except Exception:
        db_ok = False
    art = classifier._load()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "llm": "groq" if settings.groq_api_key else "fallback",
            "model": art.get("version") if art else None, "live_scraping": settings.live_scraping}


@app.post("/api/analyze", response_model=ProductOut,
          responses={202: {"description": "Queued: a worker is fetching the page. Ask again after retry_after seconds."}})
def analyze(req: AnalyzeRequest, request: Request, db: Session = Depends(get_db)):
    parsed = providers.parse_url(req.url)
    if not parsed:
        raise HTTPException(422, "Please paste a product link from amazon.in or flipkart.com")
    url, shop = parsed

    product = db.scalar(select(Product).where(Product.url == url))
    fresh = product and product.analyzed_at and utcnow() - product.analyzed_at < timedelta(hours=settings.cache_hours)
    if fresh:
        return _response(product, db, cached=True)

    client = _client_id(request)
    limit = lambda: _check_rate_limit(db, client, settings.rate_limit_per_hour, "new analyses",
                                      f"Products analyzed in the last {settings.cache_hours}h still load instantly. ")
    queued = settings.live_scraping and shop in settings.queue_shops  # this shop is fetched by the GitHub worker
    if queued and product is None:
        status, message = scrape_queue.request_scrape(db, url, shop, limit)
        if status == "failed":
            raise HTTPException(502, f"Could not read that product page right now ({message}). Please try again later.")
        return JSONResponse(status_code=202, content={"status": "pending", "message": message, "retry_after": 8})

    limit()
    if not queued:  # queued shops: the worker already saved the data, we only analyze it
        try:
            data = providers.fetch_product(url, shop)
        except providers.ScrapeError as e:
            log_event(db, "warning", "analyze", f"{url}: {e}")
            if product is not None and product.analysis_json:  # keep serving what we already have
                out = _response(product, db, cached=True)
                out["notice"] = "The shop would not let us refresh this product right now, so this is the last saved analysis."
                return out
            raise HTTPException(502, f"Could not read that product page right now ({e}). Please try again later.")
        product = store.save_product_data(db, url, shop, data)

    prices = [h.price for h in db.scalars(select(PriceHistory).where(PriceHistory.product_id == product.id))]
    reviews = [(r.review_text, r.rating) for r in db.scalars(select(RawReview).where(RawReview.product_id == product.id))]
    result = llm.analyze(product.title, product.current_price, _stats(prices, product.current_price), reviews)
    result["aspects"], result["model_version"] = classifier.predict([t for t, _ in reviews])
    product.analysis_json, product.analyzed_at = json.dumps(result), utcnow()
    db.commit()
    return _response(product, db, cached=False)


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product or not product.analysis_json:
        raise HTTPException(404, "Product not found")
    return _response(product, db, cached=True)


@app.post("/api/watch", response_model=WatchOut)
def watch(req: WatchRequest, request: Request, db: Session = Depends(get_db)):
    product = db.get(Product, req.product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    _check_rate_limit(db, "w" + _client_id(request), settings.watch_limit_per_hour, "price alerts")
    existing = db.scalar(select(Watch).where(Watch.product_id == product.id, Watch.email == req.email))
    if existing:  # same email and product: just update the target and re-arm the alert
        existing.target_price, existing.notified_at = req.target_price, None
    else:
        if db.scalar(select(func.count()).select_from(Watch).where(Watch.email == req.email)) >= MAX_WATCHES_PER_EMAIL:
            raise HTTPException(400, f"At most {MAX_WATCHES_PER_EMAIL} price alerts per email address.")
        db.add(Watch(product_id=product.id, email=req.email, target_price=req.target_price, token=token_urlsafe(16)))
    db.commit()
    return WatchOut(ok=True, message=f"We will email {req.email} when the price drops to ₹{req.target_price:,.0f} or lower.", current_price=product.current_price)


@app.get("/api/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str = Query(min_length=8, max_length=64), db: Session = Depends(get_db)):
    w = db.scalar(select(Watch).where(Watch.token == token))
    page = "<body style='font-family:system-ui;background:#020617;color:#cbd5e1;padding:48px;text-align:center'><h2>{}</h2></body>"
    if not w:
        return HTMLResponse(page.format("This link is no longer valid."), status_code=404)
    db.delete(w)
    db.commit()
    return HTMLResponse(page.format("Done. You will not get emails about this product any more."))


@app.get("/api/logs")
def logs(x_admin_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Last 100 system events. Disabled (404) unless ADMIN_TOKEN is set and sent in the X-Admin-Token header."""
    if not settings.admin_token or not hmac.compare_digest(x_admin_token or "", settings.admin_token):
        raise HTTPException(404, "Not found")
    rows = db.scalars(select(SystemLog).order_by(SystemLog.id.desc()).limit(100)).all()
    return [{"time": r.created_at, "level": r.level, "source": r.source, "message": r.message} for r in rows]
