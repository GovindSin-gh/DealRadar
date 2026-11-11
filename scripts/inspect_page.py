#!/usr/bin/env python3
"""See what DealRadar's parsers find on ONE product page, from YOUR computer (one polite request).

  python scripts/inspect_page.py "https://www.amazon.in/.../dp/B0XXXX" [--save page.html]

Use it to tell apart the two reasons a page shows no reviews: (a) the shop sent a reduced page or blocked the request,
or (b) our selectors no longer match. With --save you can open page.html in a browser, or share the part around the
reviews so the selectors can be fixed. Remove any personal data from a saved page before sharing it.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from app import providers, scraper  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--save", help="write the downloaded HTML to this file")
    a = ap.parse_args()
    parsed = providers.parse_url(a.url)
    if not parsed:
        print("Link is not from amazon.in or flipkart.com")
        return 2
    url, shop = parsed
    r = requests.get(a.url, headers=scraper.HEADERS, timeout=25)
    print(f"HTTP {r.status_code}, {len(r.text):,} characters, shop={shop}")
    if a.save:
        Path(a.save).write_text(r.text, encoding="utf-8")
        print("saved to", a.save)
    soup = BeautifulSoup(r.text, "html.parser")
    low = r.text.lower()
    print("looks like a captcha/block page:", any(m in low for m in scraper.AMAZON_BLOCK_MARKERS) or r.status_code in (403, 429, 503))
    print("\nreview markers on the page:")
    for label, sel in [('data-hook="review"', '[data-hook="review"]'), ("#cm-cr-dp-review-list", "#cm-cr-dp-review-list"),
                       ("div.review", "div.review"), ("JSON-LD blocks", 'script[type="application/ld+json"]')]:
        print(f"  {label:26s} {len(soup.select(sel))}")
    for phrase in ["Customers say", "Top reviews", "Ratings & reviews", "Customer reviews", "Sign in"]:
        print(f"  text '{phrase}':".ljust(30), "yes" if re.search(phrase, r.text, re.I) else "no")
    print("\nwhat the parser extracts:")
    try:
        d = (scraper.parse_amazon if shop == "amazon" else scraper.parse_flipkart)(r.text)
        print(f"  title   : {d['title'][:90]}\n  price   : {d['price']}\n  category: {d['category']}\n  reviews : {len(d['reviews'])}")
        for text, stars in d["reviews"][:3]:
            print(f"    ({stars}/5) {text[:100]}")
    except scraper.ScrapeError as e:
        print("  parser failed:", type(e).__name__, "-", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
