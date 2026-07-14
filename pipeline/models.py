"""Gedeelde datastructuren voor de curatiepipeline."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def make_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


@dataclass
class Candidate:
    """Een ruw item zoals opgehaald uit een bron, vóór scoring."""

    title: str
    url: str
    source: str  # bv. "hn", "devto", "github", "rss:anthropic_news"
    category: str  # "macro" | "ai_usecase"
    published_at: datetime
    raw_text: str = ""  # samenvatting/beschrijving/body die de LLM ziet
    engagement: dict = field(default_factory=dict)  # points, comments, stars, reactions...
    velocity_bonus: int = 0

    @property
    def id(self) -> str:
        return make_id(self.url)

    def age_in_days(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc)
        published = self.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return (now - published).total_seconds() / 86400.0


@dataclass
class ScoredItem:
    candidate: Candidate
    scores: dict  # rubric-velden -> score
    score: int  # totaal vóór decay
    summary_nl: Optional[str] = None

    def to_feed_dict(self, now: Optional[datetime] = None) -> dict:
        c = self.candidate
        age_days = c.age_in_days(now)
        final_score = round(self.score - 0.1 * age_days, 2)
        return {
            "id": c.id,
            "title": c.title,
            "summary_nl": self.summary_nl or "",
            "url": c.url,
            "source": c.source,
            "category": c.category,
            "score": self.score,
            "final_score": final_score,
            "published_at": c.published_at.astimezone(timezone.utc).isoformat(),
        }
