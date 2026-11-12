"""Worker: fetch ONE product page and save it to the database.   python -m app.scrape_job --url URL
Runs in GitHub Actions (workflow scrape-on-demand.yml). Also used by the daily job for requests nobody started."""
import argparse
import logging
import sys

from sqlalchemy import select

from . import providers
from .config import settings
from .db import Base, ScrapeRequest, SessionLocal, engine, log_event, utcnow
from .store import save_product_data

log = logging.getLogger("dealradar.scrape_job")


def run(db, url: str) -> dict:
    parsed = providers.parse_url(url)
    if not parsed:
        return {"ok": False, "error": "unsupported link", "blocked": False}
    url, shop = parsed
    req = db.scalar(select(ScrapeRequest).where(ScrapeRequest.url == url))
    if req is None:
        req = ScrapeRequest(url=url, shop=shop, status="pending", requested_at=utcnow())
        db.add(req)
        db.flush()
    blocked = False
    try:
        if not settings.live_scraping:  # never write sample data as if it were real
            raise providers.ScrapeError("the worker has LIVE_SCRAPING switched off")
        save_product_data(db, url, shop, providers.fetch_product(url, shop))
        req.status, req.error = "done", None
    except Exception as e:
        blocked = bool(getattr(e, "blocked", False))
        req.status, req.error = "failed", str(e)[:300]
        log_event(db, "warning", "scrape_job", f"{url}: {e}")
    req.finished_at = utcnow()
    db.commit()
    return {"ok": req.status == "done", "error": req.error, "blocked": blocked}


def process_pending(db, blocked_shops: set) -> int:
    """Serve requests that were never picked up (for example when no GitHub token is set). Returns how many succeeded."""
    if not settings.live_scraping:
        return 0
    done = 0
    for req in db.scalars(select(ScrapeRequest).where(ScrapeRequest.status == "pending")).all():
        if req.shop in blocked_shops or req.shop not in settings.enabled_shops:
            continue
        result = run(db, req.url)
        done += result["ok"]
        if result["blocked"]:
            blocked_shops.add(req.shop)
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        result = run(session, ap.parse_args().url)
    print(result)
    sys.exit(0 if result["ok"] else 1)
