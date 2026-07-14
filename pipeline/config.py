"""Laden van sources.yaml en omgevingsinstellingen."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = REPO_ROOT / "sources.yaml"
STATE_PATH = REPO_ROOT / "state" / "seen.json"
FEED_PATH = REPO_ROOT / "feed.json"

# Modelkeuzes: goedkope batch-scoring op Haiku, samenvatting op Sonnet.
HAIKU_MODEL = os.environ.get("HAIKU_MODEL", "claude-haiku-4-5-20251001")
SONNET_MODEL = os.environ.get("SONNET_MODEL", "claude-sonnet-5")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # optioneel, verhoogt rate limit voor Search API

AGE_FILTER_HOURS = 48

# Rubric-drempels
AI_USECASE_MIN_TOTAL = 6
AI_USECASE_MIN_ROI = 1
MACRO_MIN_TOTAL = 5

FEED_FINAL_SCORE_THRESHOLD = 4
DECAY_PER_DAY = 0.1


def load_sources() -> dict:
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
