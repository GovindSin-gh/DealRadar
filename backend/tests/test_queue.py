from datetime import timedelta

import pytest
from sqlalchemy import select

from app import providers, scrape_job, scrape_queue
from app.config import settings
from app.db import Product, ScrapeRequest, SessionLocal, utcnow

FK = "https://www.flipkart.com/orbit-5g/p/itmQUEUE0001"
canon = lambda u: providers.parse_url(u)[0]  # the app stores links without "www." and without tracking parameters
REVIEWS = [("Battery lasts two days, very happy with it.", 5), ("Phone gets hot while gaming.", 2), ("Screen is bright and sharp.", 5)]


@pytest.fixture
def queued(monkeypatch):
    """Pretend the server is in live mode and Flipkart must be fetched by the GitHub worker."""
    monkeypatch.setattr(settings, "live_scraping", True)
    monkeypatch.setattr(settings, "queue_shops", ["flipkart"])
    calls = []
    monkeypatch.setattr(scrape_queue, "dispatch_scrape", lambda url: calls.append(url) or True)
    return calls


def _fake_fetch(url, shop):
    return providers.ProductData("Orbit 5G (128GB)", shop, "smartphone", 22999.0, [(0, 22999.0)], REVIEWS)


def test_unknown_product_is_queued_once_then_served_after_the_worker_ran(client, queued, monkeypatch):
    r1 = client.post("/api/analyze", json={"url": FK})
    assert r1.status_code == 202 and r1.json()["status"] == "pending" and r1.json()["retry_after"] > 0
    assert client.post("/api/analyze", json={"url": FK}).status_code == 202  # asking again does not start a second worker
    assert queued == [canon(FK)]
    monkeypatch.setattr(providers, "fetch_product", _fake_fetch)  # the worker does its job
    with SessionLocal() as db:
        assert scrape_job.run(db, FK)["ok"] is True
        assert db.scalar(select(ScrapeRequest).where(ScrapeRequest.url == canon(FK))).status == "done"
    done = client.post("/api/analyze", json={"url": FK})
    assert done.status_code == 200 and done.json()["title"] == "Orbit 5G (128GB)" and done.json()["review_count"] == 3


def test_worker_failure_is_reported_to_the_visitor(client, queued, monkeypatch):
    url = "https://www.flipkart.com/blocked/p/itmQUEUE0002"
    assert client.post("/api/analyze", json={"url": url}).status_code == 202
    def refuse(u, s): raise providers.ScrapeError("HTTP 429 (the shop is refusing automated requests)", blocked=True)
    monkeypatch.setattr(providers, "fetch_product", refuse)
    with SessionLocal() as db:
        result = scrape_job.run(db, url)
    assert result["ok"] is False and result["blocked"] is True
    r = client.post("/api/analyze", json={"url": url})
    assert r.status_code == 502 and "429" in r.json()["detail"]


def test_failed_request_can_be_retried_after_the_wait(client, queued):
    url = "https://www.flipkart.com/retry/p/itmQUEUE0003"
    client.post("/api/analyze", json={"url": url})
    with SessionLocal() as db:
        req = db.scalar(select(ScrapeRequest).where(ScrapeRequest.url == canon(url)))
        req.status, req.error, req.finished_at = "failed", "old failure", utcnow() - timedelta(minutes=30)
        db.commit()
    assert client.post("/api/analyze", json={"url": url}).status_code == 202
    assert queued.count(canon(url)) == 2


def test_worker_never_saves_sample_data(client, monkeypatch):
    monkeypatch.setattr(settings, "live_scraping", False)
    with SessionLocal() as db:
        result = scrape_job.run(db, "https://www.flipkart.com/sample/p/itmQUEUE0004")
        assert result["ok"] is False and "LIVE_SCRAPING" in result["error"]
        assert db.scalar(select(Product).where(Product.url == "https://www.flipkart.com/sample/p/itmQUEUE0004")) is None


def test_daily_job_serves_requests_nobody_started(client, queued, monkeypatch):
    from app import daily_update
    monkeypatch.setattr(scrape_queue, "dispatch_scrape", lambda url: False)  # no GitHub token configured
    url = "https://www.flipkart.com/nobody/p/itmQUEUE0005"
    assert client.post("/api/analyze", json={"url": url}).json()["message"] == scrape_queue.QUEUED
    monkeypatch.setattr(providers, "fetch_product", _fake_fetch)
    with SessionLocal() as db:
        assert daily_update.run(db)["queued_done"] >= 1
    assert client.post("/api/analyze", json={"url": url}).status_code == 200


def test_dispatch_needs_token_and_repo(monkeypatch):
    monkeypatch.setattr(settings, "github_repo", "")
    assert scrape_queue.dispatch_scrape("https://www.flipkart.com/x/p/itm1") is False
