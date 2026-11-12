from app import llm, paste_reviews, providers, scraper
from app.config import settings

PASTE = """Rahul K
5.0 out of 5 stars Great battery
Reviewed in India on 5 October 2026
Colour: Black
Verified Purchase
Battery easily lasts two days and the display is bright.
12 people found this helpful
Helpful
Report
Priya S
2.0 out of 5 stars
Gets hot while gaming
Reviewed in India on 1 October 2026
Phone heats up a lot after 20 minutes of gaming. Disappointed.
Helpful
Report
"""


def _fake_groq(monkeypatch, content):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(llm.settings, "groq_api_key", "k")
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: R())


def test_paste_parser_keeps_text_and_stars_and_drops_names_and_boilerplate():
    got = paste_reviews.parse_pasted(PASTE)
    assert [s for _, s in got] == [5, 2]
    assert "Battery easily lasts two days" in got[0][0] and "Great battery" in got[0][0]
    joined = " ".join(t for t, _ in got)
    assert "Priya" not in joined and "Verified Purchase" not in joined and "found this helpful" not in joined


def test_paste_endpoint_adds_reviews_and_recomputes(client, monkeypatch):
    def bare(url, shop):
        return providers.ProductData("Bare Phone", shop, "smartphone", 15999.0, [(1, 16500.0), (0, 15999.0)], [])
    monkeypatch.setattr(providers, "fetch_product", bare)
    p = client.post("/api/analyze", json={"url": "https://www.amazon.in/Bare/dp/B0PASTE001"}).json()
    assert p["analysis"]["price_only"] is True
    monkeypatch.undo()
    r = client.post("/api/reviews", json={"product_id": p["id"], "text": PASTE})
    d = r.json()
    assert r.status_code == 200 and d["review_count"] == 2 and d["analysis"]["price_only"] is False
    assert d["notice"] == "Added 2 reviews you pasted."
    again = client.post("/api/reviews", json={"product_id": p["id"], "text": PASTE}).json()
    assert again["review_count"] == 2 and "already saved" in again["notice"]


def test_paste_endpoint_validation(client):
    p = client.post("/api/analyze", json={"url": "https://www.amazon.in/Val/dp/B0PASTE002"}).json()
    junk = "hello this is just some random text without any star lines in it at all"
    assert client.post("/api/reviews", json={"product_id": p["id"], "text": junk}).status_code == 422
    assert client.post("/api/reviews", json={"product_id": 99999, "text": PASTE}).status_code == 404
    assert client.post("/api/reviews", json={"product_id": p["id"], "text": "short"}).status_code == 422


def test_llm_review_extraction_rejects_invented_reviews(monkeypatch):
    page = "Top reviews from India\nBattery easily lasts two days and the display is bright.\n5.0 out of 5 stars\nSome other page text here to pass the length check."
    _fake_groq(monkeypatch, '{"reviews": [{"text": "Battery easily lasts two days and the display is bright.", "stars": 5}, '
                            '{"text": "Invented praise that never appears on the page at all.", "stars": 5}, '
                            '{"text": "Battery easily lasts two days and the display is bright.", "stars": 9}]}')
    assert llm.extract_reviews(page) == [("Battery easily lasts two days and the display is bright.", 5)]


def test_amazon_customers_say_and_llm_fallback(monkeypatch):
    html = ('<html><span id="productTitle">Orbit 5G</span><span class="a-price"><span class="a-offscreen">₹11,999</span></span>'
            '<div>Customers say</div><div>Customers like the battery life and the display. Some report heating during long gaming sessions.</div>'
            '<div>Select to learn more</div><h2>Top reviews from India</h2><div><span>Great phone really good battery</span></div></html>')
    monkeypatch.setattr(scraper.llm, "extract_reviews", lambda text: [("Great phone really good battery", 5)] if "Top reviews" in text else [])
    d = scraper.parse_amazon(html)
    assert d["page_summary"].startswith("Customers like the battery life") and "Select to learn" not in d["page_summary"]
    assert d["reviews"] == [("Great phone really good battery", 5)] and "customers_say=True" in d["diag"]


def test_summary_only_product_is_not_price_only(client, monkeypatch):
    def with_summary(url, shop):
        return providers.ProductData("Orbit 5G", shop, "smartphone", 11999.0, [(0, 11999.0)], [],
                                     page_summary="Customers like the battery life. Some report heating while gaming.")
    monkeypatch.setattr(providers, "fetch_product", with_summary)
    a = client.post("/api/analyze", json={"url": "https://www.amazon.in/Sum/dp/B0SUMMARY1"}).json()["analysis"]
    assert a["price_only"] is False and a["page_summary_used"] is True


def test_paused_shop_is_refused_politely(client, monkeypatch):
    monkeypatch.setattr(settings, "enabled_shops", ["amazon"])
    r = client.post("/api/analyze", json={"url": "https://www.flipkart.com/x/p/itmPAUSED01"})
    assert r.status_code == 422 and "not available right now" in r.json()["detail"] and "Amazon.in" in r.json()["detail"]
