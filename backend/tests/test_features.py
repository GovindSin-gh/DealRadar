from app import alerts, mailer
from app.db import SessionLocal, SystemLog, Watch, Product
from sqlalchemy import select

URL = "https://www.amazon.in/Feat/dp/B0FEATURE1"


def _product(client):
    return client.post("/api/analyze", json={"url": URL}).json()


def test_health_reports_db_and_model(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["db"] is True and "model" in h


def test_watch_flow_and_validation(client):
    p = _product(client)
    ok = client.post("/api/watch", json={"product_id": p["id"], "email": "Ann@Example.com", "target_price": 1000})
    assert ok.status_code == 200 and "ann@example.com" in ok.json()["message"]
    again = client.post("/api/watch", json={"product_id": p["id"], "email": "ann@example.com", "target_price": 900})
    assert again.status_code == 200
    with SessionLocal() as db:
        assert len(db.scalars(select(Watch).where(Watch.email == "ann@example.com")).all()) == 1  # updated, not duplicated
    assert client.post("/api/watch", json={"product_id": p["id"], "email": "nope", "target_price": 5}).status_code == 422
    assert client.post("/api/watch", json={"product_id": 99999, "email": "a@b.co", "target_price": 5}).status_code == 404


def test_alert_sent_once_and_unsubscribe(client, monkeypatch):
    p = _product(client)
    client.post("/api/watch", json={"product_id": p["id"], "email": "bob@example.com", "target_price": p["current_price"] + 1})
    sent = []
    monkeypatch.setattr(alerts, "send_email", lambda to, subj, body: sent.append((to, body)) or True)
    with SessionLocal() as db:
        assert alerts.check_alerts(db)["alerts_sent"] >= 1
        assert alerts.check_alerts(db)["alerts_sent"] == 0  # never emailed twice
    mail = [m for m in sent if m[0] == "bob@example.com"][0]
    token = mail[1].split("token=")[1].split()[0]
    assert client.get(f"/api/unsubscribe?token={token}").status_code == 200
    assert client.get(f"/api/unsubscribe?token={token}").status_code == 404


def test_alert_not_marked_when_email_unconfigured(client):
    p = _product(client)
    client.post("/api/watch", json={"product_id": p["id"], "email": "cy@example.com", "target_price": p["current_price"] + 1})
    with SessionLocal() as db:
        r = alerts.check_alerts(db)
        w = db.scalar(select(Watch).where(Watch.email == "cy@example.com"))
        assert r["alerts_skipped"] >= 1 and w.notified_at is None  # retried once SMTP is set up
    assert mailer.send_email("x@y.co", "s", "b") is False


def test_logs_endpoint_needs_admin_token(client, monkeypatch):
    from app.config import settings
    with SessionLocal() as db:
        db.add(SystemLog(level="info", source="test", message="hello")); db.commit()
    assert client.get("/api/logs").status_code == 404
    monkeypatch.setattr(settings, "admin_token", "secret-token")
    assert client.get("/api/logs", headers={"X-Admin-Token": "wrong"}).status_code == 404
    r = client.get("/api/logs", headers={"X-Admin-Token": "secret-token"})
    assert r.status_code == 200 and r.json()[0]["message"]
