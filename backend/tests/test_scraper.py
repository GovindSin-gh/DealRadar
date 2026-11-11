import pytest
from app.scraper import ScrapeError, parse_amazon

PAGE = """<html><body><span id="productTitle"> Nova X Pro (8GB, 256GB) </span>
<span class="a-price"><span class="a-offscreen">₹41,999.00</span></span>
<div data-hook="review"><i data-hook="review-star-rating"><span>4.0 out of 5 stars</span></i>
<span data-hook="review-body"><span>Great   screen,
battery is average.</span></span></div>
<div data-hook="review"><i data-hook="review-star-rating"><span>1.0 out of 5 stars</span></i>
<span data-hook="review-body"><span>Gets very hot.</span></span></div></body></html>"""


def test_parses_title_price_reviews():
    d = parse_amazon(PAGE)
    assert d["title"] == "Nova X Pro (8GB, 256GB)" and d["price"] == 41999.0 and d["category"] == "smartphone"
    assert d["reviews"] == [("Great screen, battery is average.", 4), ("Gets very hot.", 1)]


def test_captcha_and_layout_change_raise():
    with pytest.raises(ScrapeError):
        parse_amazon("<html>Enter the characters you see below</html>")
    with pytest.raises(ScrapeError):
        parse_amazon("<html><body>nothing here</body></html>")


FLIPKART = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"Product","name":"Vertex Book 14 Laptop (16GB, 512GB)",
"offers":{"@type":"Offer","price":"58990","priceCurrency":"INR"},
"review":[{"@type":"Review","reviewBody":"Fast and the display is great.","reviewRating":{"ratingValue":"5"}},
{"@type":"Review","reviewBody":"Fan is loud and it gets hot.","reviewRating":{"ratingValue":2}}]}]}
</script></head><body></body></html>"""


def test_flipkart_json_ld():
    from app.scraper import parse_flipkart
    d = parse_flipkart(FLIPKART)
    assert d["price"] == 58990.0 and d["category"] == "laptop"
    assert d["reviews"] == [("Fast and the display is great.", 5), ("Fan is loud and it gets hot.", 2)]


def test_flipkart_without_data_raises():
    from app.scraper import parse_flipkart
    with pytest.raises(ScrapeError):
        parse_flipkart("<html><body>Access denied</body></html>")


# ---- layered Flipkart parsing and shop-refusal handling ----
def test_flipkart_css_selector_fallback():
    from app.scraper import parse_flipkart
    html = '<html><body><span class="VU-ZEz">Orbit 5G (128GB)</span><div class="Nx9bqj CxhGGd">₹1,29,999</div></body></html>'
    d = parse_flipkart(html)
    assert d["price"] == 129999.0 and d["title"] == "Orbit 5G (128GB)" and d["reviews"] == []


def test_flipkart_meta_description_fallback():
    from app.scraper import parse_flipkart
    html = '<html><head><title>Orbit 5G</title><meta name="Description" content="Buy Orbit 5G at ₹22,999. Free delivery"></head><body><h1>Orbit 5G</h1></body></html>'
    assert parse_flipkart(html)["price"] == 22999.0


def test_llm_fallback_accepts_only_prices_present_in_page(monkeypatch):
    from app import llm
    from app.scraper import parse_flipkart
    page = "<html><body><h1>Orbit 5G</h1><p>Special price 26,499 today</p></body></html>"
    class R:
        def __init__(self, price): self.price = price
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": '{"title": "Orbit 5G", "price": %s}' % self.price}}]}
    monkeypatch.setattr(llm.settings, "groq_api_key", "k")
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: R(26499))
    assert parse_flipkart(page)["price"] == 26499.0
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: R(11111))  # invented price: must be rejected
    with pytest.raises(ScrapeError):
        parse_flipkart(page)


def test_amazon_older_review_markup():
    from app.scraper import parse_amazon
    html = ('<html><span id="productTitle">Vertex Laptop</span><span class="a-price"><span class="a-offscreen">₹58,990</span></span>'
            '<div id="cm-cr-dp-review-list"><div class="review"><i class="review-rating"><span class="a-icon-alt">5.0 out of 5 stars</span></i>'
            '<span class="review-text-content"><span>Great screen</span></span></div></div></html>')
    d = parse_amazon(html)
    assert d["reviews"] == [("Great screen", 5)] and d["category"] == "laptop"


def test_http_403_is_reported_as_blocked(monkeypatch):
    from app import scraper
    class R: status_code = 403; text = ""
    monkeypatch.setattr(scraper.requests, "get", lambda *a, **k: R())
    with pytest.raises(scraper.Blocked):
        scraper.fetch_flipkart("https://www.flipkart.com/x/p/itm1")
    class Ok: status_code = 200; text = "Enter the characters you see below"
    monkeypatch.setattr(scraper.requests, "get", lambda *a, **k: Ok())
    with pytest.raises(scraper.Blocked):
        scraper.fetch_amazon("https://www.amazon.in/x/dp/B0")
