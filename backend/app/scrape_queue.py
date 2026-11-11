"""Lets a shop that refuses our web server (HTTP 429/403 from Render) be fetched by a GitHub Actions worker instead.

Flow: visitor pastes a link -> API records a ScrapeRequest and starts the 'scrape-on-demand' workflow ->
the page answers 202 'pending' and the browser asks again every few seconds -> the worker saves the product to the
database -> the next ask finds it and runs the analysis. If no GitHub token is configured the request simply waits
for the daily job, which also processes pending requests.
This only changes WHERE the request comes from. It does not hide who we are, rotate addresses or solve captchas.
"""
import logging
from datetime import timedelta

import httpx
from sqlalchemy import select

from .config import settings
from .db import ScrapeRequest, utcnow

log = logging.getLogger("dealradar.queue")
PENDING_MINUTES = 15       # how long we wait for the worker before asking again
RETRY_AFTER_FAIL_MINUTES = 10  # how long a failure is remembered before a visitor can retry
STARTED = "A separate worker is fetching this page. This usually takes 1 to 2 minutes."
QUEUED = "This product is queued and will be fetched in the next scheduled run (within a day)."


def dispatch_scrape(url: str) -> bool:
    """Start the GitHub Actions worker for one URL. False if no token/repo is configured or GitHub refused."""
    if not (settings.github_repo and settings.github_dispatch_token):
        return False
    try:
        r = httpx.post(
            f"https://api.github.com/repos/{settings.github_repo}/actions/workflows/{settings.scrape_workflow}/dispatches",
            headers={"Authorization": f"Bearer {settings.github_dispatch_token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
            json={"ref": settings.github_ref, "inputs": {"url": url}}, timeout=15)
    except httpx.HTTPError as e:
        log.warning("could not reach GitHub: %s", e)
        return False
    if r.status_code != 204:
        log.warning("GitHub refused the dispatch: %s %s", r.status_code, r.text[:200])
    return r.status_code == 204


def request_scrape(db, url: str, shop: str, limiter) -> tuple[str, str]:
    """Returns ("pending" | "failed", message). `limiter` raises HTTP 429 when the visitor asks too often."""
    req = db.scalar(select(ScrapeRequest).where(ScrapeRequest.url == url))
    now = utcnow()
    if req and req.status == "pending" and now - req.requested_at < timedelta(minutes=PENDING_MINUTES):
        return "pending", STARTED
    if req and req.status == "failed" and now - (req.finished_at or req.requested_at) < timedelta(minutes=RETRY_AFTER_FAIL_MINUTES):
        return "failed", req.error or "the worker could not read the page"
    limiter()
    if req is None:
        req = ScrapeRequest(url=url, shop=shop, status="pending", requested_at=now)
        db.add(req)
    else:
        req.status, req.error, req.requested_at, req.finished_at = "pending", None, now, None
    db.commit()
    return "pending", STARTED if dispatch_scrape(url) else QUEUED
