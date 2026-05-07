from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Language:
    name: str
    level: str


@dataclass
class Experience:
    title: str
    company: str
    period: str
    location: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class Education:
    degree: str
    institution: str
    period: str
    details: str = ""


@dataclass
class ResumeData:
    first_name: str
    last_name: str
    email: str
    phone: str
    address: str
    profile: str
    skills: list[str] = field(default_factory=list)
    languages: list[Language] = field(default_factory=list)
    experiences: list[Experience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)

    def all_text_parts(self) -> list[str]:
        parts = [
            self.first_name,
            self.last_name,
            self.email,
            self.phone,
            self.address,
            self.profile,
            *self.skills,
        ]
        for language in self.languages:
            parts.append(f"{language.name} {language.level}")
        for experience in self.experiences:
            parts.extend([experience.title, experience.company, experience.period, experience.location])
            parts.extend(experience.bullets)
        for education in self.education:
            parts.extend([education.degree, education.institution, education.period, education.details])
        return [part for part in parts if part]


@dataclass
class ScoreDimension:
    name: str
    score: int
    max_score: int
    notes: list[str] = field(default_factory=list)


@dataclass
class MatchReport:
    total_score: int
    dimensions: list[ScoreDimension]
    matched_keywords: list[str]
    missing_keywords: list[str]
    recommendations: list[str]
