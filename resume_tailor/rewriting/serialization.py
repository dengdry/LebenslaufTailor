from __future__ import annotations

from resume_tailor.models import Education, Experience, Language, ResumeData


def resume_to_dict(resume: ResumeData) -> dict:
    return {
        "first_name": resume.first_name,
        "last_name": resume.last_name,
        "email": resume.email,
        "phone": resume.phone,
        "address": resume.address,
        "profile": resume.profile,
        "skills": resume.skills,
        "languages": [{"name": item.name, "level": item.level} for item in resume.languages],
        "experiences": [
            {
                "title": item.title,
                "company": item.company,
                "period": item.period,
                "location": item.location,
                "bullets": item.bullets,
            }
            for item in resume.experiences
        ],
        "education": [
            {
                "degree": item.degree,
                "institution": item.institution,
                "period": item.period,
                "details": item.details,
            }
            for item in resume.education
        ],
    }


def resume_from_dict(data: dict, fallback: ResumeData) -> ResumeData:
    return ResumeData(
        first_name=str(data.get("first_name") or fallback.first_name),
        last_name=str(data.get("last_name") or fallback.last_name),
        email=str(data.get("email") or fallback.email),
        phone=str(data.get("phone") or fallback.phone),
        address=str(data.get("address") or fallback.address),
        profile=str(data.get("profile") or fallback.profile),
        skills=_string_list(data.get("skills"), fallback.skills),
        languages=[
            Language(str(item.get("name", "")), str(item.get("level", "")))
            for item in data.get("languages", [])
            if isinstance(item, dict) and item.get("name")
        ]
        or fallback.languages,
        experiences=[
            Experience(
                title=str(item.get("title", "")),
                company=str(item.get("company", "")),
                period=str(item.get("period", "")),
                location=str(item.get("location", "")),
                bullets=_string_list(item.get("bullets"), []),
            )
            for item in data.get("experiences", [])
            if isinstance(item, dict) and item.get("title")
        ]
        or fallback.experiences,
        education=[
            Education(
                degree=str(item.get("degree", "")),
                institution=str(item.get("institution", "")),
                period=str(item.get("period", "")),
                details=str(item.get("details", "")),
            )
            for item in data.get("education", [])
            if isinstance(item, dict) and item.get("degree")
        ]
        or fallback.education,
    )


def _string_list(value, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    result = [str(item).strip() for item in value if str(item).strip()]
    return result or fallback
