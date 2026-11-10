import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=10, max_length=500)


class PricePoint(BaseModel):
    date: datetime
    price: float


class PriceStats(BaseModel):
    average: float
    lowest: float
    highest: float
    percent_vs_average: float


class AspectOut(BaseModel):
    aspect: str
    mentions: int
    positive_pct: int
    negative_pct: int
    snippets: list[str]


class Analysis(BaseModel):
    summary: str
    pros: list[str]
    cons: list[str]
    value_score: float
    verdict: str
    source: str  # "qwen" or "fallback"
    aspects: list[AspectOut] = []
    model_version: str | None = None


class ProductOut(BaseModel):
    id: int
    title: str
    shop: str
    category: str
    url: str
    current_price: float
    review_count: int
    price_history: list[PricePoint]
    price_stats: PriceStats
    analysis: Analysis
    analyzed_at: datetime
    cached: bool


class WatchRequest(BaseModel):
    product_id: int
    email: str = Field(min_length=5, max_length=254)
    target_price: float = Field(gt=0)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v.strip()):
            raise ValueError("Enter a valid email address")
        return v.strip().lower()


class WatchOut(BaseModel):
    ok: bool
    message: str
    current_price: float
