"""Daily job: refresh price and new reviews for every tracked product, then send price-drop emails.   python -m app.daily_update"""
import json
import logging
import random
import sys
import time
from datetime import timedelta

from sqlalchemy import select

from . import alerts, providers, scrape_job
from .config import settings
from .db import Base, PriceHistory, Product, RawReview, SessionLocal, engine, log_event, utcnow

log = logging.getLogger("dealradar.daily")


def run(db, force: bool = False) -> dict:
    stats = {"products": 0, "price_points": 0, "new_reviews": 0, "failed": 0, "skipped_blocked": 0}
    blocked_shops: set[str] = set()  # a shop that refused us once is left alone for the rest of the run
    stats["queued_done"] = scrape_job.process_pending(db, blocked_shops)  # requests nobody started
    for p in db.scalars(select(Product)).all():
        stats["products"] += 1
        if p.shop in blocked_shops:
            stats["skipped_blocked"] += 1
            continue
        try:
            data = providers.fetch_product(p.url, p.shop)
        except Exception as e:  # one broken product must not stop the others
            stats["failed"] += 1
            if getattr(e, "blocked", False):
                blocked_shops.add(p.shop)
                log_event(db, "warning", "daily_update", f"{p.shop} is refusing requests; skipping its other products today")
            log.warning("failed %s: %s", p.url, e)
            log_event(db, "warning", "daily_update", f"{p.url}: {e}")
            continue
        if settings.live_scraping and settings.daily_delay_seconds:
            time.sleep(random.uniform(settings.daily_delay_seconds, settings.daily_delay_seconds * 1.7))  # be polite
        last = db.scalar(select(PriceHistory).where(PriceHistory.product_id == p.id).order_by(PriceHistory.scraped_at.desc()).limit(1))
        if force or last is None or utcnow() - last.scraped_at > timedelta(hours=12):
            db.add(PriceHistory(product_id=p.id, price=data.price))
            stats["price_points"] += 1
        p.current_price = data.price
        known = {t for (t,) in db.execute(select(RawReview.review_text).where(RawReview.product_id == p.id))}
        for text, rating in data.reviews:
            if text not in known:
                known.add(text)
                db.add(RawReview(product_id=p.id, review_text=text, rating=rating))
                stats["new_reviews"] += 1
        db.commit()
    stats.update(alerts.check_alerts(db))
    log_event(db, "info", "daily_update", json.dumps(stats))
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        result = run(session)
    print(result)
    sys.exit(1 if result["products"] and result["failed"] + result["skipped_blocked"] == result["products"] else 0)
