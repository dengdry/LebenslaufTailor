from __future__ import annotations

from copy import deepcopy

from resume_tailor.models import ResumeData


def optimize_resume_for_jd(resume: ResumeData, jd_text: str) -> ResumeData:
    """Small deterministic tailoring pass until the LLM rewriter is connected.

    This keeps the pipeline honest: it only reorders existing skills and content.
    It does not invent new experience or metrics.
    """
    tailored = deepcopy(resume)
    jd = jd_text.lower()
    tailored.skills = sorted(
        tailored.skills,
        key=lambda skill: (_skill_relevance(skill, jd), skill.lower()),
        reverse=True,
    )
    return tailored


def _skill_relevance(skill: str, jd: str) -> int:
    score = 0
    for token in skill.lower().replace("/", " ").replace("-", " ").split():
        if len(token) >= 3 and token in jd:
            score += 1
    return score
