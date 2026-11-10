URL = "https://www.amazon.in/Nova-X-Pro/dp/B0TEST123?ref=abc"


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_rejects_unsupported_shop(client):
    r = client.post("/api/analyze", json={"url": "https://example.com/some-phone"})
    assert r.status_code == 422


def test_analyze_then_cache(client):
    first = client.post("/api/analyze", json={"url": URL})
    assert first.status_code == 200
    d = first.json()
    assert d["cached"] is False and d["shop"] == "amazon"
    assert len(d["price_history"]) == 90 and d["review_count"] == 40
    assert 0 <= d["analysis"]["value_score"] <= 10 and d["analysis"]["source"] == "fallback"

    second = client.post("/api/analyze", json={"url": URL})
    assert second.json()["cached"] is True and second.json()["id"] == d["id"]


def test_query_string_does_not_create_duplicate(client):
    a = client.post("/api/analyze", json={"url": URL}).json()
    b = client.post("/api/analyze", json={"url": "https://amazon.in/Nova-X-Pro/dp/B0TEST123"}).json()
    assert a["id"] == b["id"]


def test_get_product(client):
    pid = client.post("/api/analyze", json={"url": URL}).json()["id"]
    assert client.get(f"/api/products/{pid}").status_code == 200
    assert client.get("/api/products/99999").status_code == 404


def test_aspects_when_champion_model_exists(client):
    import pytest
    from app.classifier import _load
    if _load() is None:
        pytest.skip("no champion model trained yet")
    d = client.post("/api/analyze", json={"url": "https://www.flipkart.com/vertex-book-14/p/itmAAA"}).json()
    a = d["analysis"]["aspects"]
    assert a and all(x["positive_pct"] + x["negative_pct"] == 100 for x in a)
    assert d["analysis"]["model_version"]


def test_rate_limit_blocks_fresh_but_not_cached(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "rate_limit_per_hour", 2)
    h = {"X-Forwarded-For": "203.0.113.9"}
    post = lambda n: client.post("/api/analyze", json={"url": f"https://www.amazon.in/RL/dp/B0RATE{n}"}, headers=h)
    assert post(0).status_code == 200 and post(1).status_code == 200
    blocked = post(9)
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers
    assert post(0).status_code == 200  # cached, so free
