from __future__ import annotations

import json
import re
from dataclasses import dataclass

from resume_tailor.llm.base import LLMClient
from resume_tailor.language import language_name
from resume_tailor.models import ResumeData
from resume_tailor.rewriting.rule_based_optimizer import optimize_resume_for_jd
from resume_tailor.rewriting.serialization import resume_from_dict, resume_to_dict


@dataclass
class OptimizationResult:
    resume: ResumeData
    mode: str
    notes: list[str]


def optimize_with_optional_llm(
    resume: ResumeData, jd_text: str, llm: LLMClient | None, output_language: str = "de"
) -> OptimizationResult:
    rule_based = optimize_resume_for_jd(resume, jd_text)
    if llm is None:
        notes = ["大模型已关闭；已使用本地规则调整技能顺序。"]
        if output_language == "en":
            notes.append("检测到英语 JD，但大模型关闭；正文不会自动翻译，只会切换 HTML 栏目标题。")
        return OptimizationResult(rule_based, "rules", notes)

    try:
        raw = llm.complete(_system_prompt(output_language), _user_prompt(resume, rule_based, jd_text, output_language))
        parsed = _parse_json(raw)
        rewritten = resume_from_dict(parsed.get("resume", parsed), rule_based)
        safe, guard_notes = _truth_guard(rewritten, resume, rule_based, output_language)
        notes = parsed.get("notes", [])
        if not isinstance(notes, list):
            notes = [str(notes)]
        return OptimizationResult(safe, "llm", [str(note) for note in [*guard_notes, *notes][:8]])
    except Exception as exc:
        return OptimizationResult(
            rule_based,
            "rules-fallback",
            [f"大模型改写失败；已回退到本地规则。原因: {exc}"],
        )


def _system_prompt(output_language: str) -> str:
    target_language = language_name(output_language)
    return (
        "You are a German Lebenslauf editor. Rewrite resumes for German job applications. "
        "You must not invent facts, employers, degrees, certifications, dates, locations, tools, or metrics. "
        "Actively mine the resume for transferable evidence that matches the job description. "
        "You may reframe, combine, shorten, and make implicit relevance explicit when it is supported by the resume. "
        "You may use generic JD language such as requirements, testing, documentation, stakeholder communication, "
        "or quality assurance only when the resume contains supporting evidence. "
        "Do not add a new domain, method, tool, industry, responsibility level, achievement, certification, visa status, "
        "or metric unless it appears in the resume. "
        f"Write all resume-facing content in {target_language}. "
        "Keep a factual, restrained tone suitable for Germany. "
        "For English output, do not leave German experience bullets in the resume. "
        "Return JSON only."
    )


def _user_prompt(source_resume: ResumeData, ranked_resume: ResumeData, jd_text: str, output_language: str) -> str:
    target_language = language_name(output_language)
    payload = {
        "job_description": jd_text,
        "output_language": target_language,
        "source_resume": resume_to_dict(source_resume),
        "resume_to_rewrite": resume_to_dict(ranked_resume),
        "instructions": [
            "Rewrite the Kurzprofil more assertively for this JD in 4-6 lines.",
            f"Write profile, skills, job titles where natural, and experience bullets in {target_language}.",
            "For English output, write a substantive profile of 3-5 sentences, roughly 70-110 words.",
            "For English output, translate or rephrase all experience bullets into English; do not leave German bullets.",
            "Derive the profile from evidence across skills, experience, education, and languages.",
            "Do not mention JD requirements in the resume if the source resume does not support them; put those gaps only in notes.",
            "Keep skills limited to the provided meaning of the source skills; translation is allowed, invention is not.",
            "Rewrite experience bullets to emphasize JD-relevant evidence from the same experience block.",
            "You may merge or rephrase bullets, but every concrete claim must be traceable to the source resume.",
            "Keep each experience to 2-4 bullets.",
            "Do not change personal data, employers, dates, locations, education, or languages.",
            "Write notes in Chinese. Briefly mention which source evidence you used and any JD requirement that lacked evidence.",
            "Return an object with keys: resume, notes.",
        ],
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


def _truth_guard(
    candidate: ResumeData, source: ResumeData, ranked: ResumeData, output_language: str
) -> tuple[ResumeData, list[str]]:
    notes: list[str] = []
    candidate.first_name = source.first_name
    candidate.last_name = source.last_name
    candidate.email = source.email
    candidate.phone = source.phone
    candidate.address = source.address
    candidate.languages = source.languages
    candidate.education = source.education
    candidate.profile = _guard_profile(candidate.profile, source, notes, output_language)

    candidate.skills = _guard_skills(candidate.skills, source, ranked, output_language)

    source_by_key = {(item.title, item.company, item.period): item for item in source.experiences}
    source_by_company_period = {(item.company, item.period): item for item in source.experiences}
    guarded = []
    for item in candidate.experiences:
        key = (item.title, item.company, item.period)
        original = source_by_key.get(key) or source_by_company_period.get((item.company, item.period))
        if not original:
            continue
        if not item.title.strip():
            item.title = original.title
        item.location = original.location
        item.bullets = _guard_bullets(item.bullets, original, source, notes, output_language)
        guarded.append(item)
    candidate.experiences = guarded or source.experiences
    return candidate, notes


def _guard_skills(
    candidate_skills: list[str], source: ResumeData, ranked: ResumeData, output_language: str
) -> list[str]:
    if not candidate_skills:
        return ranked.skills
    evidence = " ".join(source.all_text_parts())
    guarded = []
    for skill in candidate_skills:
        limit = 6 if output_language == "en" else 4
        if _content_supported(skill, evidence, max_new_terms=limit, output_language=output_language):
            guarded.append(skill)
        if len(guarded) >= len(source.skills):
            break
    return guarded or ranked.skills


def _guard_profile(candidate_profile: str, source: ResumeData, notes: list[str], output_language: str) -> str:
    if not candidate_profile.strip():
        return source.profile

    evidence = " ".join(source.all_text_parts())
    kept: list[str] = []
    rejected = 0
    for sentence in _split_sentences(candidate_profile):
        max_new_terms = 22 if output_language == "en" else 9
        if _content_supported(sentence, evidence, max_new_terms=max_new_terms, output_language=output_language):
            kept.append(sentence)
        else:
            rejected += 1

    if rejected:
        notes.append(f"个人简介：已删除 {rejected} 个缺少原简历证据支持的句子。")
    if len(" ".join(kept)) >= 80:
        return " ".join(kept)
    if kept:
        return " ".join(kept + _split_sentences(source.profile)[:1])
    notes.append("个人简介：改写内容缺少足够原简历证据，已回退到原文。")
    return source.profile


def _guard_bullets(candidate_bullets, original, source: ResumeData, notes: list[str], output_language: str) -> list[str]:
    if not candidate_bullets:
        return original.bullets[:4]

    experience_evidence = " ".join([original.title, original.company, original.location, *original.bullets])
    full_evidence = " ".join(source.all_text_parts())
    safe_bullets: list[str] = []
    rejected = 0
    for bullet in candidate_bullets[:4]:
        local_limit = 18 if output_language == "en" else 7
        full_limit = 16 if output_language == "en" else 5
        if _content_supported(bullet, experience_evidence, max_new_terms=local_limit, output_language=output_language) or _content_supported(
            bullet, full_evidence, max_new_terms=full_limit, output_language=output_language
        ):
            safe_bullets.append(bullet)
        else:
            rejected += 1

    if rejected:
        notes.append(
            f"{original.title} | {original.company}: 已删除 {rejected} 条证据较弱的改写经历要点。"
        )
    return safe_bullets or original.bullets[:4]


def _content_supported(candidate: str, evidence: str, max_new_terms: int, output_language: str = "de") -> bool:
    evidence_terms = _significant_terms(evidence)
    candidate_terms = _significant_terms(candidate)
    unsupported = candidate_terms - evidence_terms - _generic_resume_terms()
    risky = _risky_terms(candidate) - _risky_terms(evidence)
    if output_language == "en":
        unsupported = unsupported - _english_translation_terms()
    return len(unsupported) <= max_new_terms and not risky


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _risky_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"\b[\w.+#/-]+\b", text, flags=re.UNICODE):
        clean = token.strip(".,;:()[]{}").lower()
        if not clean:
            continue
        if re.search(r"\d", clean):
            terms.add(clean)
            for part in re.split(r"[-_/]", clean):
                if part and re.search(r"\d", part):
                    terms.add(part)
            continue
        if token.isupper() and len(token) >= 3:
            terms.add(clean)
            continue
        if any(mark in clean for mark in ["+", "#", "/", "."]):
            terms.add(clean)
    return terms


def _generic_resume_terms() -> set[str]:
    return {
        "analyse",
        "analysis",
        "anforderungen",
        "application",
        "bewerbung",
        "collaboration",
        "communication",
        "dokumentation",
        "documentation",
        "durchfuehrung",
        "durchführung",
        "engineering",
        "erfahrung",
        "experience",
        "fachlich",
        "fokus",
        "focus",
        "kenntnisse",
        "knowledge",
        "kommunikation",
        "koordination",
        "coordination",
        "lebenslauf",
        "mitarbeit",
        "optimierung",
        "optimization",
        "projekt",
        "projekte",
        "project",
        "projects",
        "qualitaet",
        "qualität",
        "qualitaetssicherung",
        "qualitätssicherung",
        "quality",
        "rolle",
        "role",
        "schnittstellen",
        "stakeholder",
        "systematisch",
        "systematic",
        "technisch",
        "technical",
        "tests",
        "testing",
        "umfeld",
        "unterstuetzung",
        "unterstützung",
        "support",
        "verantwortung",
        "responsibility",
        "zusammenarbeit",
    }


def _english_translation_terms() -> set[str]:
    return {
        "actionable",
        "alignment",
        "assessment",
        "background",
        "capability",
        "carbon",
        "climate",
        "complex",
        "consolidated",
        "coordination",
        "cross",
        "customer",
        "decision",
        "derived",
        "emerging",
        "engagement",
        "environmental",
        "external",
        "fact",
        "framework",
        "functional",
        "impact",
        "indicators",
        "industrial",
        "insight",
        "insights",
        "intelligence",
        "interface",
        "market",
        "material",
        "mobility",
        "partner",
        "partners",
        "process",
        "requirements",
        "response",
        "signals",
        "stakeholder",
        "stakeholders",
        "strategic",
        "structured",
        "sustainability",
        "sustainable",
        "themes",
        "topics",
        "translated",
    }


def _significant_terms(text: str) -> set[str]:
    stopwords = {
        "aber",
        "auch",
        "aus",
        "bei",
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einer",
        "einem",
        "einen",
        "für",
        "mit",
        "und",
        "oder",
        "von",
        "zur",
        "zum",
        "sowie",
        "unter",
        "durch",
        "als",
        "im",
        "in",
        "an",
        "auf",
        "ich",
        "habe",
        "bin",
        "ist",
        "sind",
        "experience",
        "with",
        "and",
        "the",
        "for",
        "als",
        "aufgaben",
        "basis",
        "bereich",
        "bereichen",
        "candidate",
        "dabei",
        "deren",
        "dieser",
        "dieses",
        "eigenen",
        "einem",
        "einen",
        "gute",
        "guten",
        "hohe",
        "hohen",
        "mehr",
        "nach",
        "oder",
        "ohne",
        "passend",
        "relevant",
        "relevante",
        "sehr",
        "sein",
        "seine",
        "ueber",
        "werden",
        "wird",
        "ziel",
    }
    tokens = re.findall(r"[^\W\d_][\w+#.-]{3,}", text.lower(), flags=re.UNICODE)
    return {token.strip(".-") for token in tokens if token not in stopwords}
