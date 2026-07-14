"""Dedup, leeftijdsfilter en hard-exclusieregels vóór de LLM-scoring."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .config import AGE_FILTER_HOURS, STATE_PATH
from .models import Candidate

log = logging.getLogger(__name__)

# Hard-exclusie vóór scoring, alleen voor ai_usecase (zie opdracht-rubric).
_EXCLUDE_PATTERNS = [
    r"\bacquires?\b",
    r"\bacquisition\b",
    r"\bmerger\b",
    r"\braises? \$",
    r"\bfunding round\b",
    r"\bseries [a-e]\b",
    r"\blaunches?\b.*\bmodel\b",
    r"\bannounc(es|ing|ed)\b.*\b(model|release)\b",
    r"^\d+\s+(ways|things|tips|tricks|reasons)\b",
    r"\bwill (change|replace|disrupt|transform)\b",
    r"\bthe future of\b",
]
_EXCLUDE_RE = re.compile("|".join(_EXCLUDE_PATTERNS), re.IGNORECASE)


def load_seen() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("state/seen.json kon niet gelezen worden (%s), start leeg.", e)
        return {}


def save_seen(seen: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, sort_keys=True, ensure_ascii=False)


def is_hard_excluded(candidate: Candidate) -> bool:
    if candidate.category != "ai_usecase":
        return False
    return bool(_EXCLUDE_RE.search(candidate.title))


def filter_candidates(candidates: Iterable[Candidate], seen: dict, now: datetime | None = None) -> List[Candidate]:
    now = now or datetime.now(timezone.utc)
    cutoff_days = AGE_FILTER_HOURS / 24.0

    result = []
    for c in candidates:
        if c.url in seen:
            continue
        if c.age_in_days(now) > cutoff_days:
            continue
        if is_hard_excluded(c):
            continue
        result.append(c)
    return result


def mark_seen(seen: dict, candidates: Iterable[Candidate], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    for c in candidates:
        seen.setdefault(c.url, now.isoformat())
    return seen
