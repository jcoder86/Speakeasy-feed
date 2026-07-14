"""Generieke RSS/Atom fetcher. Faalt nooit hard: ontbrekende/kapotte feeds worden overgeslagen."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import feedparser

from ..models import Candidate

log = logging.getLogger(__name__)


def fetch(cfg: dict, category: str, name: str) -> Iterable[Candidate]:
    url = cfg["url"]
    optional = cfg.get("optional", False)

    try:
        parsed = feedparser.parse(url)
    except Exception as e:  # feedparser slikt de meeste fouten al in, dit is een vangnet
        log.warning("RSS-feed %s (%s) ophalen mislukt: %s", name, url, e)
        return

    if parsed.bozo and not parsed.entries:
        level = log.info if optional else log.warning
        level("RSS-feed %s (%s) leverde geen bruikbare entries op, overgeslagen.", name, url)
        return

    for entry in parsed.entries:
        published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if published_struct:
            published_at = datetime(*published_struct[:6], tzinfo=timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)

        title = entry.get("title", "")
        summary = entry.get("summary", "")

        yield Candidate(
            title=title,
            url=entry.get("link", ""),
            source=f"rss:{name}",
            category=category,
            published_at=published_at,
            raw_text=f"{title}\n{summary}",
            engagement={},
            velocity_bonus=0,
        )
