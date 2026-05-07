from __future__ import annotations

import re
import json
from html import unescape
from pathlib import Path

from resume_tailor.models import Education, Experience, Language, ResumeData
from resume_tailor.rewriting.serialization import resume_from_dict


def parse_html_resume(path: Path) -> ResumeData:
    text = path.read_text(encoding="utf-8")
    embedded = _embedded_resume(text)
    if embedded:
        return embedded
    return ResumeData(
        first_name=_first_match(text, r'<div class="first-name">(.*?)</div>'),
        last_name=_first_match(text, r'<div class="last-name">(.*?)</div>'),
        email=_email(_list_items(_section(text, "contact-list"))),
        phone=_phone(_list_items(_section(text, "contact-list"))),
        address=_address(_list_items(_section(text, "contact-list"))),
        profile=_first_match(text, r'<p class="profile">(.*?)</p>'),
        skills=_list_items(_section(text, "skill-list")),
        languages=_languages(_list_items(_section(text, "language-list"))),
        experiences=_experiences(text),
        education=_education(text),
    )


def _embedded_resume(text: str) -> ResumeData | None:
    raw = _first_raw(text, r'<script type="application/json" id="resume-data">(.*?)</script>')
    if not raw:
        return None
    try:
        data = json.loads(raw.replace("<\\/", "</"))
    except json.JSONDecodeError:
        return None
    fallback = ResumeData("", "", "", "", "", "")
    return resume_from_dict(data, fallback)


def _section(text: str, class_name: str) -> str:
    return _first_raw(text, rf'<ul class="{re.escape(class_name)}">(.*?)</ul>')


def _experiences(text: str) -> list[Experience]:
    result: list[Experience] = []
    for chunk in re.findall(r'<article class="experience">(.*?)</article>', text, flags=re.S):
        title = _first_match(chunk, r'<h3 class="role">(.*?)</h3>')
        company = _first_match(chunk, r'<p class="company">(.*?)</p>')
        meta = _first_match(chunk, r'<p class="meta">(.*?)</p>')
        period, location = _split_meta(meta)
        bullets = _list_items(_first_raw(chunk, r'<ul class="bullets">(.*?)</ul>'))
        if title or company or bullets:
            result.append(Experience(title=title, company=company, period=period, location=location, bullets=bullets))
    return result


def _education(text: str) -> list[Education]:
    result: list[Education] = []
    for chunk in re.findall(r'<article class="education-item">(.*?)</article>', text, flags=re.S):
        degree = _first_match(chunk, r'<h3 class="degree">(.*?)</h3>')
        meta = _first_match(chunk, r'<p class="education-meta">(.*?)</p>')
        if degree:
            result.append(Education(degree=degree, institution="", period=meta, details=""))
    return result


def _languages(items: list[str]) -> list[Language]:
    result: list[Language] = []
    for item in items:
        if ":" in item:
            name, level = item.split(":", 1)
            result.append(Language(name.strip(), level.strip()))
        elif item:
            result.append(Language(item.strip(), ""))
    return result


def _list_items(html: str) -> list[str]:
    return [_clean(item) for item in re.findall(r"<li>(.*?)</li>", html, flags=re.S) if _clean(item)]


def _first_match(text: str, pattern: str) -> str:
    return _clean(_first_raw(text, pattern))


def _first_raw(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.S)
    return match.group(1) if match else ""


def _clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _email(items: list[str]) -> str:
    return next((item for item in items if "@" in item), "")


def _phone(items: list[str]) -> str:
    return next((item for item in items if re.search(r"\+?\d[\d\s()/.-]{5,}", item)), "")


def _address(items: list[str]) -> str:
    for item in items:
        if item != _email(items) and item != _phone(items):
            return item
    return ""


def _split_meta(meta: str) -> tuple[str, str]:
    parts = [part.strip() for part in meta.split(",", 1)]
    return parts[0] if parts else "", parts[1] if len(parts) > 1 else ""
