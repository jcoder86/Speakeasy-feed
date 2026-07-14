"""Hacker News fetcher via de publieke Firebase API (geen key nodig)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import requests

from ..models import Candidate

log = logging.getLogger(__name__)

BASE = "https://hacker-news.firebaseio.com/v0"
TIMEOUT = 10


def _get(path: str):
    resp = requests.get(f"{BASE}/{path}.json", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch(cfg: dict, category: str) -> Iterable[Candidate]:
    feeds = cfg.get("feeds", ["topstories"])
    min_points = cfg.get("min_points", 15)
    min_comments = cfg.get("min_comments", 5)
    max_items = cfg.get("max_items_per_feed", 60)

    seen_ids = set()
    for feed in feeds:
        try:
            ids = _get(feed)[:max_items]
        except requests.RequestException as e:
            log.warning("HN feed %s ophalen mislukt: %s", feed, e)
            continue

        for item_id in ids:
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            try:
                item = _get(f"item/{item_id}")
            except requests.RequestException as e:
                log.warning("HN item %s ophalen mislukt: %s", item_id, e)
                continue
            if not item or item.get("type") != "story" or item.get("dead") or item.get("deleted"):
                continue

            points = item.get("score", 0)
            comments = item.get("descendants", 0)
            if points < min_points and comments < min_comments:
                continue

            url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            title = item.get("title", "")
            published_at = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc)

            # Simpele velocity-bonus: top van de lijst binnen 24u telt als top-10 op platform.
            rank = ids.index(item_id)
            velocity_bonus = 1 if rank < 10 else 0

            yield Candidate(
                title=title,
                url=url,
                source="hn",
                category=category,
                published_at=published_at,
                raw_text=title,
                engagement={"points": points, "comments": comments},
                velocity_bonus=velocity_bonus,
            )
