"""Best-effort live scrapers for Amazon.in (page selectors) and Flipkart (schema.org JSON-LD data).

Amazon changes its HTML and blocks automated traffic (GitHub's shared IPs especially), so treat this as
fragile: it raises ScrapeError instead of guessing. Check the site's terms and robots.txt before using it.
The parser is tested against a saved HTML sample, so you can fix selectors without hitting the site.
"""
import json
import re

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}


class ScrapeError(Exception):
    pass


def _number(text: str) -> float | None:
    m = re.search(r"[\d,]+(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else None


def parse_amazon(html: str) -> dict:
    low = html.lower()
    if "enter the characters you see below" in low or "api-services-support@amazon.com" in low:
        raise ScrapeError("blocked by a captcha page")
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("#productTitle")
    price_el = soup.select_one("span.a-price span.a-offscreen") or soup.select_one("span.a-price-whole")
    price = _number(price_el.get_text()) if price_el else None
    if not title_el or not price:
        raise ScrapeError("could not find title or price (page layout changed?)")
    title = title_el.get_text(strip=True)
    reviews = []
    for r in soup.select('[data-hook="review"]'):
        body = r.select_one('[data-hook="review-body"]')
        star = r.select_one('[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"]')
        stars = _number(star.get_text()) if star else None
        if body and stars:
            reviews.append((" ".join(body.get_text(" ", strip=True).split()), max(1, min(5, round(stars)))))
    return {"title": title[:200], "price": price, "category": _category(title), "reviews": reviews}


def _category(title: str) -> str:
    return "laptop" if re.search(r"laptop|notebook|macbook|ideapad|thinkpad", title, re.I) else "smartphone"


def _get(url: str) -> str:
    try:
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
    except httpx.HTTPError as e:
        raise ScrapeError(f"network error: {e}") from e
    if r.status_code != 200:
        raise ScrapeError(f"HTTP {r.status_code}")
    return r.text


def fetch_amazon(url: str) -> dict:
    return parse_amazon(_get(url))


def _ld_products(soup):
    """Yield every schema.org Product object found in the page's JSON-LD blocks."""
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                t = x.get("@type")
                if t == "Product" or (isinstance(t, list) and "Product" in t):
                    yield x
                if "@graph" in x:
                    stack.append(x["@graph"])


def parse_flipkart(html: str) -> dict:
    """Flipkart's CSS class names are scrambled and change often, so we read the structured data it embeds for search engines."""
    prod = next(_ld_products(BeautifulSoup(html, "html.parser")), None)
    if not prod:
        raise ScrapeError("no product data found (blocked, or layout changed)")
    offers = prod.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = _number(str(offers.get("price") or offers.get("lowPrice") or "")) if isinstance(offers, dict) else None
    title = str(prod.get("name") or "").strip()
    if not title or not price:
        raise ScrapeError("product data has no title or price")
    raw = prod.get("review") or []
    reviews = []
    for r in [raw] if isinstance(raw, dict) else raw:
        if not isinstance(r, dict):
            continue
        body = r.get("reviewBody") or r.get("description")
        rating = r.get("reviewRating") or {}
        stars = _number(str(rating.get("ratingValue", ""))) if isinstance(rating, dict) else None
        if body and stars:
            reviews.append((" ".join(str(body).split()), max(1, min(5, round(stars)))))
    return {"title": title[:200], "price": price, "category": _category(title), "reviews": reviews}


def fetch_flipkart(url: str) -> dict:
    return parse_flipkart(_get(url))
