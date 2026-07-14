"""Laden, decay toepassen op, mergen met en wegschrijven van feed.json."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List

from dateutil import parser as dateparser

from .config import FEED_FINAL_SCORE_THRESHOLD, FEED_PATH
from .models import ScoredItem

log = logging.getLogger(__name__)


def load_existing_feed() -> List[dict]:
    if not FEED_PATH.exists():
        return []
    try:
        with open(FEED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("items", [])
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Bestaande feed.json kon niet gelezen worden (%s), start leeg.", e)
        return []


def _apply_decay(item: dict, now: datetime) -> dict:
    published_at = dateparser.parse(item["published_at"])
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_days = (now - published_at).total_seconds() / 86400.0
    item = dict(item)
    item["final_score"] = round(item["score"] - 0.1 * age_days, 2)
    return item


def build_feed(new_items: List[ScoredItem], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)

    existing = [_apply_decay(item, now) for item in load_existing_feed()]
    new_dicts = [item.to_feed_dict(now) for item in new_items]

    merged: dict[str, dict] = {item["id"]: item for item in existing}
    for item in new_dicts:
        merged[item["id"]] = item  # nieuwe scoring/samenvatting wint bij een herhaalde url

    kept = [item for item in merged.values() if item["final_score"] >= FEED_FINAL_SCORE_THRESHOLD]
    kept.sort(key=lambda i: i["final_score"], reverse=True)

    return {
        "generated_at": now.isoformat(),
        "items": kept,
    }


def write_feed(feed: dict, path=None) -> None:
    path = path or FEED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)
