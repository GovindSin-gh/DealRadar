from app import daily_update
from app.db import SessionLocal


def test_daily_update_adds_price_point(client):
    client.post("/api/analyze", json={"url": "https://www.amazon.in/Orbit/dp/B0DAILY1"})
    with SessionLocal() as db:
        stats = daily_update.run(db, force=True)
    assert stats["failed"] == 0 and stats["price_points"] >= 1


def test_live_mode_scrape_failure_returns_clear_error(client, monkeypatch):
    from app import providers, scraper
    monkeypatch.setattr(providers.settings, "live_scraping", True)
    def blocked(url):
        raise scraper.ScrapeError("HTTP 403")
    monkeypatch.setattr(scraper, "fetch_flipkart", blocked)
    r = client.post("/api/analyze", json={"url": "https://www.flipkart.com/some-phone/p/itmLIVE1"})
    assert r.status_code == 502 and "Could not read" in r.json()["detail"]
