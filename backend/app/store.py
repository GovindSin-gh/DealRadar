"""Saves scraped product data (product row, price points, new reviews) to the database."""
from sqlalchemy import select

from . import providers
from .db import PriceHistory, Product, RawReview


def save_product_data(db, url: str, shop: str, data) -> Product:
    product = db.scalar(select(Product).where(Product.url == url))
    if product is None:
        product = Product(url=url, shop=shop, title=data.title, category=data.category, current_price=data.price)
        db.add(product)
        db.flush()
        db.add_all(PriceHistory(product_id=product.id, price=p, scraped_at=providers.history_dates(d)) for d, p in data.history)
    else:
        product.current_price = data.price
        db.add(PriceHistory(product_id=product.id, price=data.price))
    known = {t for (t,) in db.execute(select(RawReview.review_text).where(RawReview.product_id == product.id))}
    for text, rating in data.reviews:  # skip reviews we already stored on an earlier visit
        if text not in known:
            db.add(RawReview(product_id=product.id, review_text=text, rating=rating))
    db.commit()
    return product
