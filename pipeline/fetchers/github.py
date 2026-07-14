"""GitHub Search API fetcher: recent aangemaakte repo's als vervanging voor Trending."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests
from dateutil import parser as dateparser

from ..models import Candidate

log = logging.getLogger(__name__)
TIMEOUT = 10
API_URL = "https://api.github.com/search/repositories"


def fetch(cfg: dict, category: str) -> Iterable[Candidate]:
    days = cfg.get("days", 7)
    min_stars_per_week = cfg.get("min_stars_per_week", 10)
    max_results = cfg.get("max_results", 50)

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "q": f"created:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(max_results, 100),
    }
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(API_URL, params=params, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except (requests.RequestException, ValueError) as e:
        log.warning("GitHub Search API ophalen mislukt: %s", e)
        return

    now = datetime.now(timezone.utc)
    for idx, repo in enumerate(items):
        try:
            created_at = dateparser.parse(repo["created_at"])
        except (KeyError, ValueError, TypeError):
            continue
        age_weeks = max((now - created_at).total_seconds() / (86400 * 7), 1 / 7)
        stars = repo.get("stargazers_count", 0)
        stars_per_week = stars / age_weeks
        if stars_per_week < min_stars_per_week:
            continue

        title = repo.get("full_name", "")
        description = repo.get("description") or ""
        velocity_bonus = 1 if idx < 10 else 0

        yield Candidate(
            title=title,
            url=repo.get("html_url", ""),
            source="github",
            category=category,
            published_at=created_at,
            raw_text=f"{title}\n{description}",
            engagement={"stars": stars, "stars_per_week": round(stars_per_week, 1)},
            velocity_bonus=velocity_bonus,
        )
