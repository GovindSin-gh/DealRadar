"""Turns reviews that a visitor copied from the shop page and pasted into DealRadar into (text, stars) pairs.
This is the dependable source of reviews: the visitor's own browser shows the reviews, nothing is scraped for them."""
import re

from . import llm

STAR = re.compile(r"(\d(?:\.\d)?)\s*out of\s*5\s*stars?", re.I)
JUNK = re.compile(
    r"^(reviewed in .*|verified purchase|helpful|report|report abuse|read more|read less|\d+ (people|person) found this helpful|"
    r"one person found this helpful|vine customer review.*|top contributor.*|colou?r( name)?:.*|size( name)?:.*|"
    r"style( name)?:.*|pattern name:.*|translate review.*|sponsored)$", re.I)


def parse_pasted(text: str, limit: int = 30) -> list[tuple[str, int]]:
    lines = [l.strip() for l in text.replace("\r", "").split("\n")]
    starts = [i for i, l in enumerate(lines) if STAR.search(l)]
    found: list[tuple[str, int]] = []
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        stars = round(float(STAR.search(lines[i]).group(1)))
        head = STAR.sub("", lines[i]).strip(" :-\u2013")  # the review title is often on the same line as the stars
        body = [l for l in lines[i + 1:end] if l and not JUNK.match(l)]
        if n + 1 < len(starts) and body and len(body[-1]) <= 50 and not re.search(r"[.!?]$", body[-1]):
            body = body[:-1]  # that short last line is the NEXT reviewer's name: do not store people's names
        review = " ".join(([head] if head else []) + body).strip()
        if len(review) >= 15 and 1 <= stars <= 5:
            found.append((review[:600], stars))
    if not found:  # a different layout: let Qwen try (every review it returns must appear word for word in the paste)
        found = llm.extract_reviews(text)
    seen, out = set(), []
    for t, s in found:
        if t not in seen:
            seen.add(t)
            out.append((t, s))
    return out[:limit]
