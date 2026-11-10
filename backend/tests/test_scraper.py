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
