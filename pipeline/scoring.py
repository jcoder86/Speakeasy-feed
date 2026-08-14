"""Relevantie-scoring cascade via Claude Haiku, per rubric en in batches."""
from __future__ import annotations

import json
import logging
from typing import List

import anthropic

from .config import (
    AI_RELEASE_MIN_REALITEIT,
    AI_RELEASE_MIN_TOTAL,
    AI_USECASE_MIN_ROI,
    AI_USECASE_MIN_TOTAL,
    ANTHROPIC_API_KEY,
    HAIKU_MODEL,
    MACRO_MIN_TOTAL,
)
from .models import Candidate, ScoredItem

log = logging.getLogger(__name__)

BATCH_SIZE = 15
MAX_RAW_TEXT_CHARS = 500

_AI_USECASE_SYSTEM = """Je bent een strenge redacteur die kandidaat-artikelen scoort voor een AI-nieuwsbrief \
gericht op individuele bouwers (Python + API-niveau, Claude als pair-programmer).

Scoor elk item op deze rubric, elk als geheel getal binnen de aangegeven range:
- lifehack (0-2): is dit een concrete, direct toepasbare truc/workflow?
- roi (0-3): verhouding opbrengst/inspanning voor een individu.
- disruptief (0-2): verandert dit hoe iemand werkt/bouwt?
- nuttig (0-2): praktisch nut voor een individuele bouwer.
- praktisch (0-2): haalbaar met Python + API's door één persoon, geen team/budget nodig.

Extra regel: als het item overduidelijk een LinkedIn/X-post is zonder concrete cijfers of demo, \
trek je 1 punt af van de som van de vijf scores hierboven (mag negatief resulteren, dat is prima).

Antwoord ALLEEN met geldige JSON: een lijst van objecten in dezelfde volgorde als de input, \
elk met exact de velden: index, lifehack, roi, disruptief, nuttig, praktisch, penalty (0 of -1)."""

_MACRO_SYSTEM = """Je bent een strenge redacteur die kandidaat-artikelen scoort voor een macro-economie/\
geopolitiek-nieuwsbrief met beursimpact.

Scoor elk item op deze rubric, elk als geheel getal binnen de aangegeven range:
- significantie (0-3): hoe belangrijk/globaal relevant is dit nieuws?
- beursimpact (0-3): directe of indirecte impact op financiele markten.
- actualiteit (0-2): hoe vers/tijdgevoelig is dit nieuws?

Antwoord ALLEEN met geldige JSON: een lijst van objecten in dezelfde volgorde als de input, \
elk met exact de velden: index, significantie, beursimpact, actualiteit."""

_AI_RELEASE_SYSTEM = """Je scoort nieuwsberichten over AI-tools/modellen voor iemand die AI-tools gebruikt en \
ermee bouwt. Het gaat hier specifiek om ECHTE, NU BESCHIKBARE releases van labs zoals Anthropic, OpenAI, \
Google/Gemini en Meta — nieuwe modellen, features, API's of tools die je vandaag kunt gebruiken.

Scoor elk item op deze rubric, elk als geheel getal binnen de aangegeven range:
- realiteit (0-2): is dit een release die NU beschikbaar/live is? 0 als het een aankondiging is voor de \
toekomst, een roadmap-item, "coming soon", preview-wachtlijst e.d. 2 als het vandaag te gebruiken is.
- relevantie (0-3): hoe relevant is dit voor iemand die dagelijks met AI-tools werkt/bouwt (nieuwe \
capability, prijswijziging, API-verandering, nieuw model)?
- impact (0-2): hoe groot is de verandering t.o.v. wat er al bestond?

Antwoord ALLEEN met geldige JSON: een lijst van objecten in dezelfde volgorde als de input, \
elk met exact de velden: index, realiteit, relevantie, impact."""


def _client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY ontbreekt in de omgeving.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _chunk(items: List, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _build_user_prompt(batch: List[Candidate]) -> str:
    payload = [
        {
            "index": i,
            "title": c.title,
            "text": c.raw_text[:MAX_RAW_TEXT_CHARS],
        }
        for i, c in enumerate(batch)
    ]
    return json.dumps(payload, ensure_ascii=False)


def _parse_json_array(text: str) -> list:
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"Geen JSON-array gevonden in modelrespons: {text[:200]!r}")
    return json.loads(text[start : end + 1])


def _score_batch(client: anthropic.Anthropic, system: str, batch: List[Candidate]) -> list:
    message = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": _build_user_prompt(batch)}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    return _parse_json_array(text)


def score_candidates(candidates: List[Candidate]) -> List[ScoredItem]:
    if not candidates:
        return []

    client = _client()
    scored: List[ScoredItem] = []

    ai_items = [c for c in candidates if c.category == "ai_usecase"]
    macro_items = [c for c in candidates if c.category == "macro"]
    release_items = [c for c in candidates if c.category == "ai_release"]

    for batch in _chunk(ai_items, BATCH_SIZE):
        try:
            results = _score_batch(client, _AI_USECASE_SYSTEM, batch)
        except (anthropic.APIError, ValueError, json.JSONDecodeError) as e:
            log.warning("ai_usecase scoring-batch mislukt, batch overgeslagen: %s", e)
            continue
        for r in results:
            idx = r.get("index")
            if idx is None or idx >= len(batch):
                continue
            c = batch[idx]
            rubric = {
                "lifehack": r.get("lifehack", 0),
                "roi": r.get("roi", 0),
                "disruptief": r.get("disruptief", 0),
                "nuttig": r.get("nuttig", 0),
                "praktisch": r.get("praktisch", 0),
                "velocity_bonus": c.velocity_bonus,
                "penalty": r.get("penalty", 0),
            }
            total = sum(rubric.values())
            if total >= AI_USECASE_MIN_TOTAL and rubric["roi"] >= AI_USECASE_MIN_ROI:
                scored.append(ScoredItem(candidate=c, scores=rubric, score=total))

    for batch in _chunk(macro_items, BATCH_SIZE):
        try:
            results = _score_batch(client, _MACRO_SYSTEM, batch)
        except (anthropic.APIError, ValueError, json.JSONDecodeError) as e:
            log.warning("macro scoring-batch mislukt, batch overgeslagen: %s", e)
            continue
        for r in results:
            idx = r.get("index")
            if idx is None or idx >= len(batch):
                continue
            c = batch[idx]
            rubric = {
                "significantie": r.get("significantie", 0),
                "beursimpact": r.get("beursimpact", 0),
                "actualiteit": r.get("actualiteit", 0),
            }
            total = sum(rubric.values())
            if total >= MACRO_MIN_TOTAL:
                scored.append(ScoredItem(candidate=c, scores=rubric, score=total))

    for batch in _chunk(release_items, BATCH_SIZE):
        try:
            results = _score_batch(client, _AI_RELEASE_SYSTEM, batch)
        except (anthropic.APIError, ValueError, json.JSONDecodeError) as e:
            log.warning("ai_release scoring-batch mislukt, batch overgeslagen: %s", e)
            continue
        for r in results:
            idx = r.get("index")
            if idx is None or idx >= len(batch):
                continue
            c = batch[idx]
            rubric = {
                "realiteit": r.get("realiteit", 0),
                "relevantie": r.get("relevantie", 0),
                "impact": r.get("impact", 0),
            }
            total = sum(rubric.values())
            if total >= AI_RELEASE_MIN_TOTAL and rubric["realiteit"] >= AI_RELEASE_MIN_REALITEIT:
                scored.append(ScoredItem(candidate=c, scores=rubric, score=total))

    return scored
