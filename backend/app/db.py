from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from .config import settings


def utcnow() -> datetime:
    """Naive UTC time, so SQLite and Postgres behave the same."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    shop: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_json: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prices = relationship("PriceHistory", cascade="all, delete-orphan")
    reviews = relationship("RawReview", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RawReview(Base):
    __tablename__ = "raw_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RequestCount(Base):
    """How many fresh analyses one visitor (hashed IP) ran in one clock hour. Lives in the database, not memory,
    because Render's free server forgets everything when it sleeps."""
    __tablename__ = "request_counts"
    client_id: Mapped[str] = mapped_column(String, primary_key=True)
    window: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. 2026110813
    count: Mapped[int] = mapped_column(Integer, default=0)


class Watch(Base):
    """A visitor asked to be emailed when a product falls to target_price or lower."""
    __tablename__ = "watchlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # used by the unsubscribe link
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)


class SystemLog(Base):
    """Simple monitoring: scraper failures, job summaries. Read through GET /api/logs."""
    __tablename__ = "system_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ScrapeRequest(Base):
    """A product the visitor asked for that a GitHub Actions worker must fetch (see scrape_queue.py)."""
    __tablename__ = "scrape_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    shop: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending | done | failed
    error: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


def log_event(db, level: str, source: str, message: str) -> None:
    db.add(SystemLog(level=level, source=source, message=message[:1000]))
    db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
