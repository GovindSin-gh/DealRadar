"""Best-effort live parsers for Amazon.in and Flipkart product pages.

Honest limits: shops change their HTML and block automated traffic. When that happens we raise ScrapeError
(or Blocked for 403/429/503/captcha pages) and the app degrades gracefully. We do NOT try to defeat bot
protection (no captcha solving, fingerprint spoofing or stealth browsers): check each site's terms and keep the
request volume low. The parsers are tested on saved page samples, so you can fix selectors without hitting the sites.
"""
import json
import logging
import re

import requests
from bs4 import BeautifulSoup

from . import llm
from .config import settings

log = logging.getLogger("dealradar.scraper")
REQUEST_TIMEOUT = 25
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
}
AMAZON_BLOCK_MARKERS = ("enter the characters you see below", "api-services-support@amazon.com", "type the characters you see in this image")


class ScrapeError(Exception):
    pass


class Blocked(ScrapeError):
    """The shop refused us (HTTP 403/429/503 or a captcha page). Callers should stop hitting that shop for a while."""


def _number(text) -> float | None:
    m = re.search(r"[\d,]+(?:\.\d+)?", str(text or ""))
    try:
        v = float(m.group().replace(",", "")) if m else None
    except ValueError:
        return None
    return v if v and v > 0 else None


def _category(title: str) -> str:
    return "laptop" if re.search(r"laptop|notebook|macbook|ideapad|thinkpad|vivobook|aspire|inspiron", title, re.I) else "smartphone"


def _get(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise ScrapeError(f"network error: {e}") from e
    if r.status_code in (403, 429, 503):
        raise Blocked(f"HTTP {r.status_code} (the shop is refusing automated requests)")
    if r.status_code != 200:
        raise ScrapeError(f"HTTP {r.status_code}")
    return r.text


def _first_text(soup, selectors):
    for sel in selectors:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            return node.get_text(" ", strip=True)
    return None


def _star_review(nodes, body_sel, star_sel) -> list[tuple[str, int]]:
    out = []
    for r in nodes:
        body, star = r.select_one(body_sel), r.select_one(star_sel)
        stars = _number(star.get_text()) if star else None
        if body and stars:
            out.append((" ".join(body.get_text(" ", strip=True).split()), max(1, min(5, round(stars)))))
    return out


# ------------------------------------------------------------------ Amazon.in
def parse_amazon(html: str) -> dict:
    low = html.lower()
    if any(m in low for m in AMAZON_BLOCK_MARKERS):
        raise Blocked("captcha page (Amazon is asking for a human check)")
    soup = BeautifulSoup(html, "html.parser")
    title = _first_text(soup, ["#productTitle", "#title"])
    if not title:
        og = soup.select_one('meta[property="og:title"]')
        title = og.get("content") if og else None
    price = None
    for sel in ["span.a-price span.a-offscreen", "#corePrice_feature_div span.a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice", "span.a-price-whole"]:
        node = soup.select_one(sel)
        price = _number(node.get_text()) if node else None
        if price:
            break
    if not title or not price:
        raise ScrapeError("could not find title or price (page layout changed?)")
    nodes = soup.select('[data-hook="review"]') or soup.select("#cm-cr-dp-review-list .review, div.review")
    reviews = _star_review(
        nodes,
        '[data-hook="review-body"], .review-text-content',
        '[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"], i.review-rating, .a-icon-alt',
    )
    return {"title": title.strip()[:200], "price": price, "category": _category(title), "reviews": reviews}


def fetch_amazon(url: str) -> dict:
    return parse_amazon(_get(url))


# ------------------------------------------------------------------ Flipkart
# Flipkart scrambles its CSS class names and changes them often, so we try several layers, best first.
FK_PRICE = ["div.Nx9bqj.CxhGGd", "div.Nx9bqj", "div._30jeq3._16Jk6d", "div._30jeq3"]
FK_TITLE = ["span.VU-ZEz", "span.B_NuCI", "h1.yhB1nd", "h1"]


def _ld_products(soup):
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


def _page_text(soup) -> str:
    ld = [t.string.strip() for t in soup.select('script[type="application/ld+json"]') if t.string]
    head = soup.title.string.strip() if soup.title and soup.title.string else ""
    for t in soup(["script", "style", "noscript", "svg", "img", "link"]):
        t.decompose()
    return f"PAGE TITLE: {head}\nJSON-LD: {' '.join(ld)[:3000]}\nVISIBLE TEXT: {re.sub(r'[ \\t\\r\\n]+', ' ', soup.get_text(' ', strip=True))}"[:12000]


def parse_flipkart(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = price = None
    reviews: list[tuple[str, int]] = []
    prod = next(_ld_products(soup), None)  # layer 1: structured data
    if prod:
        title = str(prod.get("name") or "").strip() or None
        offers = prod.get("offers")
        offers = offers[0] if isinstance(offers, list) and offers else offers
        if isinstance(offers, dict):
            price = _number(offers.get("price") or offers.get("lowPrice"))
        raw = prod.get("review") or []
        for r in [raw] if isinstance(raw, dict) else raw:
            rating = r.get("reviewRating") if isinstance(r, dict) else None
            body = r.get("reviewBody") or r.get("description") if isinstance(r, dict) else None
            stars = _number(rating.get("ratingValue")) if isinstance(rating, dict) else None
            if body and stars:
                reviews.append((" ".join(str(body).split()), max(1, min(5, round(stars)))))
    if price is None:  # layer 2: CSS selectors
        for sel in FK_PRICE:
            node = soup.select_one(sel)
            price = _number(node.get_text()) if node else None
            if price:
                break
    title = title or _first_text(soup, FK_TITLE)
    if price is None:  # layer 3: price quoted in the page description
        meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        blob = " ".join(filter(None, [meta.get("content") if meta else "", soup.title.string if soup.title and soup.title.string else ""]))
        m = re.search(r"₹\s?([\d,]+(?:\.\d+)?)", blob)
        price = _number(m.group(1)) if m else None
    if price is None:  # layer 4: ask Qwen to read the page text (answer is verified against the text)
        found = llm.extract_product(_page_text(soup))
        if found:
            price, title = found["price"], title or found["title"]
    if not title or not price:
        raise ScrapeError("could not find title or price (blocked, or layout changed)")
    return {"title": title[:200], "price": price, "category": _category(title), "reviews": reviews}


def fetch_flipkart(url: str) -> dict:
    return parse_flipkart(_get(url))
