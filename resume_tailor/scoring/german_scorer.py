from __future__ import annotations

import re

from resume_tailor.models import MatchReport, ScoreDimension


COMMON_STOPWORDS = {
    "und",
    "oder",
    "mit",
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "für",
    "von",
    "zur",
    "zum",
    "als",
    "im",
    "in",
    "am",
    "an",
    "bei",
    "wir",
    "sie",
    "du",
    "you",
    "and",
    "the",
    "with",
    "for",
}

IMPORTANT_TERMS = {
    "deutsch",
    "englisch",
    "python",
    "test",
    "software",
    "system",
    "batterie",
    "bms",
    "elektromobilität",
    "anforderungen",
    "dokumentation",
    "analyse",
    "entwicklung",
    "zertifikat",
}


class GermanScorer:
    def score(self, resume_text: str, jd_text: str) -> MatchReport:
        resume_terms = _terms(resume_text)
        jd_terms = _terms(jd_text)
        jd_keywords = sorted((jd_terms & IMPORTANT_TERMS) | _top_terms(jd_text, limit=18))

        matched = [term for term in jd_keywords if term in resume_terms]
        missing = [term for term in jd_keywords if term not in resume_terms]

        keyword_score = round(30 * _ratio(len(matched), len(jd_keywords)))
        language_score = self._language_score(resume_text, jd_text)
        timeline_score = self._timeline_score(resume_text)
        german_format_score = self._german_format_score(resume_text)
        experience_score = min(25, keyword_score // 2 + self._experience_bonus(resume_text, jd_text))

        dimensions = [
            ScoreDimension("JD keyword coverage", keyword_score, 30, _keyword_notes(matched, missing)),
            ScoreDimension("Relevant experience signal", experience_score, 25),
            ScoreDimension("Language fit", language_score, 15),
            ScoreDimension("Timeline clarity", timeline_score, 15),
            ScoreDimension("German Lebenslauf fit", german_format_score, 15),
        ]
        total = sum(item.score for item in dimensions)
        recommendations = _recommendations(missing, language_score, timeline_score)
        return MatchReport(total, dimensions, matched, missing, recommendations)

    def _language_score(self, resume_text: str, jd_text: str) -> int:
        resume = resume_text.lower()
        jd = jd_text.lower()
        needs_german = "deutsch" in jd or "german" in jd
        needs_english = "englisch" in jd or "english" in jd
        score = 15
        if needs_german and "deutsch" not in resume:
            score -= 8
        if needs_english and "englisch" not in resume and "english" not in resume:
            score -= 5
        if "muttersprache" in resume or re.search(r"\b[abc][12]\b", resume):
            score += 1
        return max(0, min(15, score))

    def _timeline_score(self, resume_text: str) -> int:
        dates = re.findall(r"\b(?:0[1-9]|1[0-2])[/.-]\d{4}\b|\b(?:19|20)\d{2}\b", resume_text)
        return min(15, 5 + len(dates))

    def _german_format_score(self, resume_text: str) -> int:
        text = resume_text.lower()
        score = 0
        for heading in ["berufserfahrung", "ausbildung", "sprachen", "kenntnisse", "fähigkeiten", "kontakt"]:
            if heading in text:
                score += 2
        if "lebenslauf" in text or "kurzprofil" in text:
            score += 2
        if re.search(r"\b\d{2}/\d{4}\b", text):
            score += 1
        return min(15, score)

    def _experience_bonus(self, resume_text: str, jd_text: str) -> int:
        resume = resume_text.lower()
        jd = jd_text.lower()
        bonus = 0
        for marker in ["entwicklung", "test", "analyse", "projekt", "anforderung", "dokumentation"]:
            if marker in resume and marker in jd:
                bonus += 3
        return min(15, bonus)


def _terms(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-ZÄÖÜäöüß][a-zA-ZÄÖÜäöüß0-9+#.-]{2,}", text.lower())
    return {term.strip(".-") for term in raw if term not in COMMON_STOPWORDS}


def _top_terms(text: str, limit: int) -> set[str]:
    counts: dict[str, int] = {}
    for term in _terms(text):
        if len(term) < 4:
            continue
        counts[term] = counts.get(term, 0) + text.lower().count(term)
    return {term for term, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]}


def _ratio(value: int, total: int) -> float:
    if total == 0:
        return 1.0
    return value / total


def _keyword_notes(matched: list[str], missing: list[str]) -> list[str]:
    notes = []
    if matched:
        notes.append("Matched: " + ", ".join(matched[:12]))
    if missing:
        notes.append("Missing or weak: " + ", ".join(missing[:12]))
    return notes


def _recommendations(missing: list[str], language_score: int, timeline_score: int) -> list[str]:
    recs = []
    if missing:
        recs.append("Prüfen, welche fehlenden JD-Schlüsselbegriffe wahrheitsgemäß aus vorhandener Erfahrung ergänzt werden können.")
    if language_score < 15:
        recs.append("Sprachniveau mit CEFR-Angabe ergänzen, z. B. Deutsch B2/C1 und Englisch B2/C1.")
    if timeline_score < 12:
        recs.append("Zeitangaben im Format MM/YYYY - MM/YYYY vereinheitlichen und Lücken sichtbar erklären.")
    recs.append("Kurzprofil auf die konkrete Stelle zuschneiden und auf 5-7 Zeilen begrenzen.")
    return recs
