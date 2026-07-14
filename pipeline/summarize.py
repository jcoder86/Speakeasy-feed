"""NL-samenvatting via Claude Sonnet voor items die de scoringsdrempel halen."""
from __future__ import annotations

import logging
from typing import List

import anthropic

from .config import ANTHROPIC_API_KEY, SONNET_MODEL
from .models import ScoredItem

log = logging.getLogger(__name__)

MAX_RAW_TEXT_CHARS = 1500

_SYSTEM = """Je schrijft Nederlandse samenvattingen voor een persoonlijke nieuwsbrief, in een warm-zakelijke \
toon zonder hype. Per item schrijf je 3-5 zinnen die bevatten:
- een titel-hook die nieuwsgierig maakt,
- wat het is / hoe het werkt / wat de slimme vondst is,
- "Inspirerend omdat: ..." maar alleen als dat niet al evident is uit de rest van de tekst,
- "Wat je nodig hebt: ..." altijd concreet (tools, kennisniveau, tijdsinvestering),
- een inline bronvermelding met de meegegeven URL.

Schrijf platte tekst (geen markdown-koppen), in doorlopende zinnen. Geen emoji's. Geen wervende taal."""


def _client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY ontbreekt in de omgeving.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _summarize_one(client: anthropic.Anthropic, item: ScoredItem) -> str:
    c = item.candidate
    user_prompt = (
        f"Titel: {c.title}\n"
        f"Bron: {c.source}\n"
        f"URL: {c.url}\n"
        f"Tekst/context:\n{c.raw_text[:MAX_RAW_TEXT_CHARS]}"
    )
    message = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text").strip()


def summarize_items(items: List[ScoredItem]) -> List[ScoredItem]:
    if not items:
        return items

    client = _client()
    for item in items:
        try:
            item.summary_nl = _summarize_one(client, item)
        except anthropic.APIError as e:
            log.warning("Samenvatting mislukt voor %s: %s", item.candidate.url, e)
            item.summary_nl = item.candidate.title
    return items
