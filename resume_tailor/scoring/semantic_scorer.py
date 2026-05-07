from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from resume_tailor.llm.base import LLMClient


@dataclass
class SemanticScore:
    score: int
    dimensions: dict[str, int] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    mode: str = "llm"
    error: str = ""


@dataclass
class DualScoreReport:
    rule_report: object
    semantic_report: SemanticScore | None
    combined_score: int
    mode: str


def score_with_optional_llm(rule_report, resume_text: str, jd_text: str, llm: LLMClient | None) -> DualScoreReport:
    if llm is None:
        return DualScoreReport(rule_report, None, rule_report.total_score, "rules")
    try:
        raw = llm.complete(_system_prompt(), _user_prompt(resume_text, jd_text))
        parsed = _parse_json(raw)
        semantic = SemanticScore(
            score=_clamp_int(parsed.get("score", 0), 0, 100),
            dimensions={
                str(key): _clamp_int(value, 0, 100)
                for key, value in dict(parsed.get("dimensions", {})).items()
            },
            strengths=_string_list(parsed.get("strengths")),
            gaps=_string_list(parsed.get("gaps")),
            recommendations=_string_list(parsed.get("recommendations")),
            mode="llm",
        )
        combined = round(rule_report.total_score * 0.4 + semantic.score * 0.6)
        return DualScoreReport(rule_report, semantic, combined, "dual")
    except Exception as exc:
        semantic = SemanticScore(
            score=0,
            mode="llm-fallback",
            error=f"大模型语义评分失败: {exc}",
        )
        return DualScoreReport(rule_report, semantic, rule_report.total_score, "rules-fallback")


def _system_prompt() -> str:
    return (
        "You are a German recruiting and Lebenslauf matching evaluator. "
        "Score how well a resume matches a German job description. "
        "Do not reward invented or unsupported assumptions. "
        "Evaluate semantic fit, not just keyword overlap. "
        "Return JSON only."
    )


def _user_prompt(resume_text: str, jd_text: str) -> str:
    payload = {
        "job_description": jd_text,
        "resume_text": resume_text,
        "scoring_scale": "0-100",
        "dimensions": {
            "skills_fit": "Technical and tool match to JD",
            "experience_fit": "Relevant responsibilities, domain, seniority, and project evidence",
            "language_fit": "German/English requirements and stated language level",
            "education_certification_fit": "Education, certifications, formal qualifications",
            "german_application_fit": "Lebenslauf clarity, factual tone, timeline, German market fit",
        },
        "return_schema": {
            "score": 0,
            "dimensions": {
                "skills_fit": 0,
                "experience_fit": 0,
                "language_fit": 0,
                "education_certification_fit": 0,
                "german_application_fit": 0,
            },
            "strengths": [],
            "gaps": [],
            "recommendations": [],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_json(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?", "", clean).strip()
        clean = re.sub(r"```$", "", clean).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _clamp_int(value, minimum: int, maximum: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
