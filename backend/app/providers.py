"""Where product data comes from.

Part 1 uses deterministic SAMPLE data so the whole app works with no scraping.
Part 3 replaces fetch_product() with real Amazon.in / Flipkart scrapers,
keeping the same return shape, so nothing else has to change.
"""
import hashlib
import logging
import random
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from . import scraper
from .config import settings
from .db import utcnow

SUPPORTED = {"amazon.in": "amazon", "flipkart.com": "flipkart"}


@dataclass
class ProductData:
    title: str
    shop: str
    category: str
    price: float
    history: list[tuple[int, float]]  # (days_ago, price)
    reviews: list[tuple[str, int]]  # (text, rating 1-5)


def parse_url(url: str) -> tuple[str, str] | None:
    """Return (canonical_url, shop) or None if the link is not supported."""
    p = urlparse(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.")
    for domain, shop in SUPPORTED.items():
        if host == domain or host.endswith("." + domain):
            if p.scheme in ("http", "https") and p.path.strip("/"):
                return f"https://{host}{p.path.rstrip('/')}", shop
    return None


CATALOGUE = [
    ("Nova X Pro 256GB", "smartphone", 41999),
    ("Orbit 5G 128GB", "smartphone", 22999),
    ("Vertex Book 14 i5 16GB", "laptop", 58990),
    ("Aero Slim 15 Ryzen 5", "laptop", 49990),
]
REVIEWS = [
    ("The display is stunning and very bright outdoors.", 5),
    ("Display colours are great for the price.", 5),
    ("Daylight camera photos are excellent.", 5),
    ("Camera struggles in low light, photos look soft.", 3),
    ("Performance is smooth, no lag in daily use.", 5),
    ("Fast and smooth, apps open instantly.", 4),
    ("Gets hot while gaming, frame rate drops after 20 minutes.", 2),
    ("Phone feels hot when charging, a bit worrying.", 2),
    ("Battery easily lasts a full day with normal use.", 5),
    ("Battery drains fast on 5G, needs charging by evening.", 2),
    ("Worth the price, great value at this cost.", 5),
    ("A bit expensive for what you get, not worth it at launch price.", 2),
    ("No charger in the box, had to buy one separately.", 3),
    ("Solid build quality, feels premium.", 4),
]


def _sample(url: str, shop: str) -> ProductData:
    rng = random.Random(int(hashlib.md5(url.encode()).hexdigest(), 16))
    title, category, base = rng.choice(CATALOGUE)
    price, history = base * rng.uniform(1.1, 1.2), []
    for days_ago in range(89, -1, -1):
        price += rng.uniform(-0.01, 0.009) * base
        history.append((days_ago, round(price / 10) * 10))
    history[-1] = (0, float(base))
    reviews = [rng.choice(REVIEWS) for _ in range(40)]
    return ProductData(title, shop, category, float(base), history, reviews)


def history_dates(days_ago: int):
    return utcnow() - timedelta(days=days_ago)


class ScrapeError(Exception):
    pass


def fetch_product(url: str, shop: str) -> ProductData:
    """Sample data by default. With LIVE_SCRAPING=true, real data or a clear error, never a silent mix."""
    if not settings.live_scraping:
        return _sample(url, shop)
    fetchers = {"amazon": scraper.fetch_amazon, "flipkart": scraper.fetch_flipkart}
    try:
        d = fetchers[shop](url)
    except scraper.ScrapeError as e:
        logging.getLogger("dealradar.providers").warning("live scrape failed for %s: %s", url, e)
        raise ScrapeError(str(e)) from e
    return ProductData(d["title"], shop, d["category"], d["price"], [(0, d["price"])], d["reviews"])
