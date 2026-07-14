"""Orchestrator: ophalen -> filteren -> scoren -> samenvatten -> publiceren."""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from . import feed_store, filters
from .config import load_sources
from .fetchers import devto, github, hn, rss
from .models import Candidate
from .scoring import score_candidates
from .summarize import summarize_items

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pipeline.main")


def fetch_all(sources: dict) -> list[Candidate]:
    candidates: list[Candidate] = []

    for category, cat_sources in sources.items():
        for name, cfg in cat_sources.items():
            if not cfg.get("enabled", True):
                continue
            source_type = cfg.get("type")
            try:
                if source_type == "hn":
                    items = list(hn.fetch(cfg, category))
                elif source_type == "devto":
                    items = list(devto.fetch(cfg, category))
                elif source_type == "github_search":
                    items = list(github.fetch(cfg, category))
                elif source_type == "rss":
                    items = list(rss.fetch(cfg, category, name))
                else:
                    log.warning("Onbekend brontype %s voor %s, overgeslagen.", source_type, name)
                    continue
            except Exception as e:  # een kapotte bron mag de hele run nooit blokkeren
                log.warning("Bron %s (%s) mislukt, overgeslagen: %s", name, source_type, e)
                continue

            log.info("Bron %s (%s): %d kandidaten opgehaald.", name, category, len(items))
            candidates.extend(items)

    return candidates


def run() -> int:
    now = datetime.now(timezone.utc)
    sources = load_sources()

    raw_candidates = fetch_all(sources)
    log.info("Totaal %d ruwe kandidaten opgehaald.", len(raw_candidates))

    seen = filters.load_seen()
    fresh_candidates = filters.filter_candidates(raw_candidates, seen, now)
    log.info("%d kandidaten over na dedup/leeftijdsfilter/hard-exclusie.", len(fresh_candidates))

    scored_items = score_candidates(fresh_candidates)
    log.info("%d items boven de opnamedrempel na Haiku-scoring.", len(scored_items))

    summarize_items(scored_items)

    feed = feed_store.build_feed(scored_items, now)
    feed_store.write_feed(feed)
    log.info("feed.json geschreven met %d items.", len(feed["items"]))

    seen = filters.mark_seen(seen, raw_candidates, now)
    filters.save_seen(seen)
    log.info("state/seen.json bijgewerkt (%d urls).", len(seen))

    return 0


if __name__ == "__main__":
    sys.exit(run())
