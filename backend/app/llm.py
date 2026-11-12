"""Turns reviews + price stats into a verdict. Uses Qwen on Groq, falls back to a simple local summary."""
import json
import logging
import re

import httpx

from .config import settings

log = logging.getLogger("dealradar.llm")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM = (
    "You are a careful shopping analyst. Reply with ONE JSON object and nothing else, with keys: "
    '"summary" (2-3 sentences), "pros" (list of up to 4 short strings), "cons" (list of up to 4 short strings), '
    '"value_score" (number 0-10), "verdict" (one sentence: buy now, wait, or skip, and why). '
    "Use only the facts given. Prices are in Indian rupees. If no reviews are provided, say clearly that the verdict is based on price only, "
    "and do not invent customer opinions. If a customer-feedback summary written by the shop is provided, you may rely on it and say so."
)


def _extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON in model reply")
    return json.loads(text[start : end + 1])


def _clean(d: dict) -> dict:
    score = max(0.0, min(10.0, float(d["value_score"])))
    return {
        "summary": str(d["summary"])[:600],
        "pros": [str(x)[:120] for x in d.get("pros", [])][:4],
        "cons": [str(x)[:120] for x in d.get("cons", [])][:4],
        "value_score": round(score, 1),
        "verdict": str(d["verdict"])[:300],
    }


def _groq(title, price, stats, reviews, page_summary="") -> dict:
    sample = "\n".join(f"- ({r}/5) {t[:300]}" for t, r in reviews[:30]) or "(no reviews were available)"
    user = (
        f"Product: {title}\nCurrent price: Rs {price:,.0f}\n"
        f"90-day average: Rs {stats['avg']:,.0f}, lowest: Rs {stats['min']:,.0f}, highest: Rs {stats['max']:,.0f}\n"
        f"Reviews:\n{sample}"
    ) + (f"\nCustomer-feedback summary shown on the shop page: {page_summary[:1200]}" if page_summary else "")
    body = {
        "model": settings.groq_model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    r = httpx.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {settings.groq_api_key}"}, timeout=30)
    r.raise_for_status()
    return _clean(_extract_json(r.json()["choices"][0]["message"]["content"]))


ASPECTS = {
    "battery": ["battery"], "display": ["display", "screen"], "camera": ["camera", "photo"],
    "performance": ["performance", "smooth", "lag"], "heating": ["hot", "heat"], "value for money": ["worth", "value", "expensive"],
}


def _verdict_from_price(price, stats) -> str:
    if price <= stats["min"] * 1.02:
        return "Buy now: this is the lowest price in the tracked period."
    if price <= stats["avg"] * 0.97:
        return "Good time to buy: the price is below its average."
    if price >= stats["avg"] * 1.03:
        return "Consider waiting: the price is above its average."
    return "Fair price: close to its average."


def _price_only(title, price, stats, page_summary="") -> dict:
    note = f" The shop's customer summary says: {page_summary[:300]}" if page_summary else ""
    return {
        "summary": (f"{title}: no individual reviews could be read for this product, so this verdict is based on price" + (" and the shop's own summary." if page_summary else " only.")) + note,
        "pros": ["Review data not available"], "cons": [],
        "value_score": 5.0, "verdict": _verdict_from_price(price, stats), "source": "fallback",
    }


def _fallback(title, price, stats, reviews, page_summary="") -> dict:
    if not reviews:
        return _price_only(title, price, stats, page_summary)
    avg_rating = sum(r for _, r in reviews) / len(reviews)
    pos, neg = {a: 0 for a in ASPECTS}, {a: 0 for a in ASPECTS}
    for text, rating in reviews:
        low = text.lower()
        for a, words in ASPECTS.items():
            if any(w in low for w in words):
                (pos if rating >= 4 else neg)[a] += 1
    pros = [f"Reviewers praise the {a} ({pos[a]} positive mentions)" for a in sorted(pos, key=lambda a: pos[a] - neg[a], reverse=True) if pos[a] > neg[a]][:3]
    cons = [f"Complaints about {a} ({neg[a]} mentions)" for a in sorted(neg, key=lambda a: neg[a] - pos[a], reverse=True) if neg[a] > pos[a]][:3]
    score = avg_rating * 2 + (0.5 if price <= stats["avg"] * 0.95 else -0.5 if price >= stats["avg"] * 1.05 else 0)
    if price <= stats["min"] * 1.02:
        verdict = "Buy now: this is the lowest price in the tracked period."
    elif price <= stats["avg"] * 0.97:
        verdict = "Good time to buy: the price is below its average."
    elif price >= stats["avg"] * 1.03:
        verdict = "Consider waiting: the price is above its average."
    else:
        verdict = "Fair price: close to its average."
    return {
        "summary": f"{title}: {len(reviews)} reviews average {avg_rating:.1f} out of 5. This is an automatic summary, the AI writer was not available.",
        "pros": pros or ["Not enough review data for clear strengths"],
        "cons": cons or ["No repeated complaints found"],
        "value_score": round(max(0.0, min(10.0, score)), 1),
        "verdict": verdict,
    }


def analyze(title, price, stats, reviews, page_summary="") -> dict:
    out = _analyze(title, price, stats, reviews, page_summary)
    out["price_only"] = not reviews and not page_summary
    out["page_summary_used"] = bool(page_summary) and not reviews
    return out


def _analyze(title, price, stats, reviews, page_summary="") -> dict:
    if settings.groq_api_key:
        try:
            return {**_groq(title, price, stats, reviews, page_summary), "source": "qwen"}
        except Exception as e:  # network, quota, bad JSON: never break the request
            log.warning("Groq failed, using fallback: %s", e)
    return {**_fallback(title, price, stats, reviews, page_summary), "source": "fallback"}


def extract_product(page_text: str) -> dict | None:
    """Fallback parser for when page selectors break: Qwen reads the title and price from the page text.
    The answer is only accepted if the price really appears in that text, so it cannot be invented."""
    if not (settings.groq_api_key and settings.llm_extract_fallback):
        return None
    system = (
        "You extract product data from a shopping page. Return the MAIN product's title and its current selling "
        "price in INR (not MRP, EMI, exchange or related-product prices). Reply with ONLY JSON: "
        '{"title": string, "price": number or null}. Numeric price only. Use null if the price is not present.'
    )
    body = {"model": settings.groq_model, "temperature": 0, "max_tokens": 600,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": page_text[:12000]}]}
    try:
        r = httpx.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {settings.groq_api_key}"}, timeout=40)
        r.raise_for_status()
        data = _extract_json(r.json()["choices"][0]["message"]["content"])
        price = float(str(data.get("price")).replace(",", ""))
    except Exception as e:
        log.warning("LLM page extraction failed: %s", e)
        return None
    plain = re.sub(r"(?<=\d),(?=\d)", "", page_text)  # '1,29,999' -> '129999'
    if price <= 0 or str(int(price)) not in plain:
        log.warning("LLM price %s not found in the page text, rejected", price)
        return None
    return {"title": str(data.get("title") or "")[:200], "price": price}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')).strip().lower()


def extract_reviews(page_text: str, limit: int = 15) -> list[tuple[str, int]]:
    """Qwen reads customer reviews out of page text our selectors could not parse.
    Every review it returns must appear word for word in the text (none can be invented) and carry a 1-5 star rating."""
    if not (settings.groq_api_key and settings.llm_extract_fallback) or len(page_text) < 80:
        return []
    system = (
        "From the text, copy the customer reviews EXACTLY as written (never rephrase or invent). Reply with ONLY JSON: "
        '{"reviews": [{"text": string (verbatim, max 400 characters), "stars": integer 1 to 5}]}. '
        "Skip anything that is not a customer review. Use an empty list if there are none."
    )
    body = {"model": settings.groq_model, "temperature": 0, "max_tokens": 2500,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": page_text[:9000]}]}
    try:
        r = httpx.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {settings.groq_api_key}"}, timeout=40)
        r.raise_for_status()
        items = _extract_json(r.json()["choices"][0]["message"]["content"]).get("reviews", [])
    except Exception as e:
        log.warning("LLM review extraction failed: %s", e)
        return []
    haystack, out = _norm(page_text), []
    for it in items if isinstance(items, list) else []:
        try:
            text, stars = str(it.get("text", "")).strip(), int(round(float(it.get("stars"))))
        except (TypeError, ValueError, AttributeError):
            continue
        if len(text) >= 20 and 1 <= stars <= 5 and _norm(text) in haystack:
            out.append((text[:400], stars))
        if len(out) >= limit:
            break
    return out
