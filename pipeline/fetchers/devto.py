"""dev.to fetcher via de publieke API (geen auth nodig)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import requests
from dateutil import parser as dateparser

from ..models import Candidate

log = logging.getLogger(__name__)
TIMEOUT = 10


def fetch(cfg: dict, category: str) -> Iterable[Candidate]:
    url = cfg["url"]
    min_reactions = cfg.get("min_reactions", 15)

    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        articles = resp.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("dev.to ophalen mislukt: %s", e)
        return

    for idx, article in enumerate(articles):
        reactions = article.get("public_reactions_count", 0)
        if reactions < min_reactions:
            continue

        published_raw = article.get("published_at") or article.get("published_timestamp")
        try:
            published_at = dateparser.parse(published_raw) if published_raw else datetime.now(timezone.utc)
        except (ValueError, TypeError):
            published_at = datetime.now(timezone.utc)

        title = article.get("title", "")
        description = article.get("description", "")
        velocity_bonus = 1 if idx < 10 else 0

        yield Candidate(
            title=title,
            url=article.get("url", ""),
            source="devto",
            category=category,
            published_at=published_at,
            raw_text=f"{title}\n{description}",
            engagement={"reactions": reactions, "comments": article.get("comments_count", 0)},
            velocity_bonus=velocity_bonus,
        )
