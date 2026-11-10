"""Price-drop alerts: email every watcher whose target price has been reached. Called at the end of the daily job."""
from sqlalchemy import select

from .config import settings
from .db import Product, Watch, log_event, utcnow
from .mailer import send_email


def check_alerts(db) -> dict:
    sent = failed = skipped = 0
    rows = db.execute(
        select(Watch, Product).join(Product, Watch.product_id == Product.id).where(Watch.notified_at.is_(None))
    ).all()
    for watch, product in rows:
        if product.current_price > watch.target_price:
            continue
        body = (
            f"Good news. {product.title} is now Rs {product.current_price:,.0f}, "
            f"at or below your target of Rs {watch.target_price:,.0f}.\n\n"
            f"Product page: {product.url}\n\n"
            f"Prices change quickly, so check the shop before you buy.\n"
            f"Stop these emails: {settings.public_api_url}/api/unsubscribe?token={watch.token}\n"
        )
        if send_email(watch.email, f"DealRadar: price drop on {product.title}", body):
            watch.notified_at = utcnow()  # only mark as done when the mail really went out
            sent += 1
        elif settings.smtp_host:
            failed += 1
        else:
            skipped += 1  # email not configured: retry automatically once it is
    db.commit()
    if failed:
        log_event(db, "warning", "alerts", f"{failed} alert emails failed to send")
    return {"alerts_sent": sent, "alerts_failed": failed, "alerts_skipped": skipped}
