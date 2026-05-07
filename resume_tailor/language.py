from __future__ import annotations

import re


ENGLISH_SIGNALS = {
    "and",
    "with",
    "for",
    "the",
    "role",
    "responsibilities",
    "requirements",
    "experience",
    "skills",
    "team",
    "engineer",
    "developer",
    "manager",
}

GERMAN_SIGNALS = {
    "und",
    "mit",
    "für",
    "der",
    "die",
    "das",
    "aufgaben",
    "anforderungen",
    "erfahrung",
    "kenntnisse",
    "team",
    "ingenieur",
    "entwickler",
}


def detect_jd_language(text: str) -> str:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß]+", text.lower())
    if not tokens:
        return "de"
    english = sum(1 for token in tokens if token in ENGLISH_SIGNALS)
    german = sum(1 for token in tokens if token in GERMAN_SIGNALS)
    if english > german:
        return "en"
    return "de"


def language_name(code: str) -> str:
    return "English" if code == "en" else "German"
