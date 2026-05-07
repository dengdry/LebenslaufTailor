from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from resume_tailor.models import Education, Experience, Language, ResumeData
from resume_tailor.readers.docx_text import extract_first_image
from resume_tailor.rewriting.serialization import resume_to_dict


TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


class GermanDeltaHtmlRenderer:
    def __init__(
        self,
        template_docx: Path | None = None,
        language: str = "de",
        fallback_photo: Path | None = None,
    ) -> None:
        self.template_docx = template_docx
        self.language = language if language in {"de", "en"} else "de"
        self.fallback_photo = fallback_photo

    def render(self, resume: ResumeData, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        css_source = TEMPLATE_DIR / "german_delta.css"
        css_target = out_path.parent / "german_delta.css"
        if css_source.exists():
            shutil.copyfile(css_source, css_target)

        template = (TEMPLATE_DIR / "german_delta.html").read_text(encoding="utf-8")
        html_text = _replace_many(
            template,
            {
                **_labels(self.language),
                "full_name": f"{resume.first_name} {resume.last_name}".strip(),
                "first_name": resume.first_name,
                "last_name": resume.last_name.upper(),
                "photo_block": self._photo_block(out_path),
                "contact_items": _contact_items(resume),
                "skill_items": _list_items(resume.skills[:10]),
                "language_items": _language_items(resume.languages, self.language),
                "profile": resume.profile,
                "experience_items": _experience_items(resume.experiences),
                "education_items": _education_items(resume.education),
                "resume_json": _resume_json(resume),
            },
        )
        out_path.write_text(html_text, encoding="utf-8")

    def _photo_block(self, out_path: Path) -> str:
        if self.template_docx and self.template_docx.exists():
            photo_path = extract_first_image(self.template_docx, out_path.parent / "portrait.jpg")
            if not photo_path:
                return ""
            src = "portrait.jpg"
        elif self.fallback_photo and self.fallback_photo.exists():
            src = self.fallback_photo.name
            target = out_path.parent / src
            if self.fallback_photo.resolve() != target.resolve():
                shutil.copyfile(self.fallback_photo, target)
        else:
            return ""
        alt = "Application photo" if self.language == "en" else "Bewerbungsfoto"
        return f'<img class="portrait" src="{_e(src)}" alt="{alt}" />'


def _replace_many(template: str, values: dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{{ " + key + " }}", value)
    return result


def _contact_items(resume: ResumeData) -> str:
    return _list_items([resume.phone, resume.email, resume.address])


def _language_items(languages: list[Language], language: str) -> str:
    return "\n".join(
        f"<li>{_e(_language_label(item.name, language))}: {_e(_language_level(item.level, language))}</li>"
        for item in languages
        if item.name and item.level
    )


def _experience_items(experiences: list[Experience]) -> str:
    chunks = []
    for item in experiences:
        meta = item.period
        if item.location:
            meta = f"{meta}, {item.location}"
        chunks.append(
            "\n".join(
                [
                    '<article class="experience">',
                    f'  <h3 class="role">{_e(item.title)}</h3>',
                    f'  <p class="company">{_e(item.company)}</p>',
                    f'  <p class="meta">{_e(meta)}</p>',
                    '  <ul class="bullets">',
                    _list_items(item.bullets[:4]),
                    "  </ul>",
                    "</article>",
                ]
            )
        )
    return "\n".join(chunks)


def _education_items(education: list[Education]) -> str:
    chunks = []
    for item in education:
        degree = f"{item.degree}, {item.institution}" if item.institution else item.degree
        meta = item.period
        if item.details:
            meta = f"{meta} | {item.details}" if meta else item.details
        chunks.append(
            "\n".join(
                [
                    '<article class="education-item">',
                    f'  <h3 class="degree">{_e(degree)}</h3>',
                    f'  <p class="education-meta">{_e(meta)}</p>',
                    "</article>",
                ]
            )
        )
    return "\n".join(chunks)


def _list_items(items: list[str]) -> str:
    return "\n".join(f"<li>{_e(item)}</li>" for item in items if item)


def _e(value: str) -> str:
    return html.escape(str(value), quote=True)


def _resume_json(resume: ResumeData) -> str:
    return json.dumps(resume_to_dict(resume), ensure_ascii=False).replace("</", "<\\/")


def _labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "html_lang": "en",
            "document_title": "Resume",
            "contact_label": "Contact",
            "skills_label": "Skills",
            "languages_label": "Languages",
            "profile_label": "Profile",
            "experience_label": "Experience",
            "education_label": "Education",
        }
    return {
        "html_lang": "de",
        "document_title": "Lebenslauf",
        "contact_label": "Kontakt",
        "skills_label": "Fähigkeiten",
        "languages_label": "Sprachen",
        "profile_label": "Kurzprofil",
        "experience_label": "Berufserfahrung",
        "education_label": "Ausbildung",
    }


def _language_label(name: str, language: str) -> str:
    if language != "en":
        return name
    mapping = {
        "deutsch": "German",
        "englisch": "English",
        "english": "English",
        "chinesisch": "Chinese",
        "chinese": "Chinese",
    }
    return mapping.get(name.lower(), name)


def _language_level(level: str, language: str) -> str:
    if language != "en":
        return level
    mapping = {
        "muttersprache": "Native",
        "fließend": "Fluent",
        "fliessend": "Fluent",
        "verhandlungssicher": "Business fluent",
        "gute kenntnisse": "Good working knowledge",
        "grundkenntnisse": "Basic knowledge",
    }
    return mapping.get(level.lower(), level)
