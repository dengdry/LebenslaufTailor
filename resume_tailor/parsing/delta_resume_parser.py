from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from resume_tailor.models import Education, Experience, Language, ResumeData


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


@dataclass
class AnchorBlock:
    x: float
    y: float
    width: float
    height: float
    paragraphs: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


def parse_delta_resume(path: Path) -> ResumeData:
    anchors = _read_anchor_blocks(path)
    if not anchors:
        raise ValueError("没有找到 Word 文本框。当前解析器需要使用 Delta Lebenslauf 模板格式的 DOCX。")

    return ResumeData(
        first_name=_first_name(anchors),
        last_name=_last_name(anchors),
        email=_email(anchors),
        phone=_phone(anchors),
        address=_address(anchors),
        profile=_profile(anchors),
        skills=_skills(anchors),
        languages=_languages(anchors),
        experiences=_experiences(anchors),
        education=_education(anchors),
    )


def preview_resume(resume: ResumeData) -> str:
    lines = [
        "简历解析预览",
        "",
        f"姓名: {resume.first_name} {resume.last_name}",
        f"邮箱: {resume.email}",
        f"电话: {resume.phone}",
        f"地址: {resume.address}",
        "",
        "个人简介:",
        resume.profile,
        "",
        "技能:",
        *[f"- {skill}" for skill in resume.skills],
        "",
        "语言:",
        *[f"- {language.name}: {language.level}" for language in resume.languages],
        "",
        "工作经历:",
    ]
    for exp in resume.experiences:
        lines.extend([f"- {exp.title} | {exp.company} | {exp.period} | {exp.location}"])
        lines.extend([f"  - {bullet}" for bullet in exp.bullets])
    lines.extend(["", "教育经历:"])
    for edu in resume.education:
        detail = f" | {edu.details}" if edu.details else ""
        lines.append(f"- {edu.degree}, {edu.institution} | {edu.period}{detail}")
    return "\n".join(lines)


def _read_anchor_blocks(path: Path) -> list[AnchorBlock]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    blocks: list[AnchorBlock] = []
    for anchor in root.findall(".//wp:anchor", NS):
        extent = anchor.find("wp:extent", NS)
        pos_x = anchor.find("wp:positionH/wp:posOffset", NS)
        pos_y = anchor.find("wp:positionV/wp:posOffset", NS)
        if extent is None or pos_y is None:
            continue
        x = _emu_to_inch(pos_x.text) if pos_x is not None and pos_x.text else 0.0
        y = _emu_to_inch(pos_y.text)
        width = _emu_to_inch(extent.get("cx", "0"))
        height = _emu_to_inch(extent.get("cy", "0"))
        paragraphs = []
        for paragraph in anchor.findall(".//w:p", NS):
            text = _paragraph_text(paragraph)
            if text:
                paragraphs.append(text)
        if paragraphs:
            blocks.append(AnchorBlock(x, y, width, height, paragraphs))
    return blocks


def _paragraph_text(paragraph) -> str:
    pieces = [node.text or "" for node in paragraph.findall(".//w:t", NS)]
    return _clean_text("".join(pieces))


def _clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.:;])", r"\1", text)
    text = re.sub(r"([@])\s+", r"\1", text)
    return text


def _emu_to_inch(value: str | None) -> float:
    if value is None:
        return 0.0
    return int(value) / 914400


def _first_name(anchors: list[AnchorBlock]) -> str:
    candidates = [block for block in anchors if -0.1 <= block.x <= 0.2 and 1.3 <= block.y <= 2.0]
    return _first_text(candidates) or ""


def _last_name(anchors: list[AnchorBlock]) -> str:
    candidates = [block for block in anchors if -0.1 <= block.x <= 0.2 and 2.0 <= block.y <= 2.5]
    return _first_text(candidates) or ""


def _email(anchors: list[AnchorBlock]) -> str:
    for block in anchors:
        text = block.text.replace(" ", "")
        if "@" in text:
            return text
    return ""


def _phone(anchors: list[AnchorBlock]) -> str:
    for block in anchors:
        text = block.text
        if "+49" in text or re.search(r"\+\d{2}", text):
            return re.sub(r"\s+", " ", text)
    return ""


def _address(anchors: list[AnchorBlock]) -> str:
    contact_blocks = [block for block in anchors if block.x < -0.7 and 4.1 <= block.y <= 4.8]
    if contact_blocks:
        return _clean_text(", ".join(block.text for block in sorted(contact_blocks, key=lambda item: item.y)))
    for block in anchors:
        text = block.text.lower()
        if any(token in text for token in ["straße", "str.", "krozingen", "plz"]):
            return _clean_text(block.text)
    return ""


def _profile(anchors: list[AnchorBlock]) -> str:
    long_blocks = [p for block in anchors for p in block.paragraphs if len(p) > 120]
    return max(long_blocks, key=len) if long_blocks else ""


def _skills(anchors: list[AnchorBlock]) -> list[str]:
    candidates = [
        block
        for block in anchors
        if -0.2 <= block.x <= 0.3 and 5.0 <= block.y <= 6.1 and len(block.paragraphs) >= 3
    ]
    if not candidates:
        return []
    return _unique(candidates[0].paragraphs)


def _languages(anchors: list[AnchorBlock]) -> list[Language]:
    candidates = [
        block
        for block in anchors
        if -0.2 <= block.x <= 0.3 and 9.1 <= block.y <= 10.8 and len(block.paragraphs) >= 1
    ]
    if not candidates:
        return []
    text = "\n".join(candidates[0].paragraphs)
    pairs = re.findall(r"(Deutsch|Englisch|English|Chinesisch|Chinese)\s*:\s*([^\n]+)", text, flags=re.I)
    if pairs:
        return [Language(_title_language(name), level.strip()) for name, level in pairs]

    tokens = [item for paragraph in candidates[0].paragraphs for item in re.split(r"\s*:\s*|\n", paragraph) if item]
    result: list[Language] = []
    index = 0
    while index < len(tokens) - 1:
        if tokens[index].lower() in {"deutsch", "englisch", "english", "chinesisch", "chinese"}:
            result.append(Language(_title_language(tokens[index]), tokens[index + 1]))
            index += 2
        else:
            index += 1
    return result


def _experiences(anchors: list[AnchorBlock]) -> list[Experience]:
    right = sorted(
        [
            block
            for block in anchors
            if block.x > 1.3 and 1.8 <= block.y <= 8.8 and not _is_heading(block.text)
        ],
        key=lambda block: (block.y, block.x),
    )
    starts: list[int] = []
    for i in range(len(right) - 2):
        if (
            len(right[i].paragraphs) == 1
            and len(right[i + 1].paragraphs) == 1
            and len(right[i + 2].paragraphs) == 1
            and _is_dateish(right[i + 2].text)
            and not _is_dateish(right[i].text)
            and not _is_dateish(right[i + 1].text)
        ):
            starts.append(i)

    experiences: list[Experience] = []
    for position, start in enumerate(starts):
        next_start = starts[position + 1] if position + 1 < len(starts) else len(right)
        title = right[start].paragraphs[0]
        company = right[start + 1].paragraphs[0]
        period, location = _split_period_location(right[start + 2].text)
        bullet_blocks = right[start + 3 : next_start]
        bullets = [paragraph for block in bullet_blocks for paragraph in block.paragraphs if not _is_dateish(paragraph)]
        experiences.append(Experience(title, company, period, location, _unique(bullets)))
    return experiences


def _education(anchors: list[AnchorBlock]) -> list[Education]:
    blocks = sorted(
        [block for block in anchors if block.x > 1.3 and 8.8 <= block.y <= 10.4 and not _is_heading(block.text)],
        key=lambda block: (block.y, block.x),
    )
    degree_indices = [i for i, block in enumerate(blocks) if re.search(r"\b[BM]\.Sc", block.text)]
    result: list[Education] = []
    for pos, index in enumerate(degree_indices):
        degree, institution = _split_degree_institution(blocks[index].text)
        next_index = degree_indices[pos + 1] if pos + 1 < len(degree_indices) else len(blocks)
        details = [block.text for block in blocks[index + 1 : next_index]]
        period = ""
        extra = ""
        for detail in details:
            if re.search(r"\b(?:19|20)\d{2}\b", detail):
                period = detail
            else:
                extra = detail if not extra else f"{extra} | {detail}"
        result.append(Education(degree, institution, period, extra))
    return result


def _split_period_location(text: str) -> tuple[str, str]:
    parts = [part.strip(" ,") for part in text.split(",", 1)]
    return parts[0], parts[1] if len(parts) > 1 else ""


def _split_degree_institution(text: str) -> tuple[str, str]:
    parts = [part.strip() for part in text.split(",", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return text, ""


def _is_dateish(text: str) -> bool:
    return bool(re.search(r"\b(?:0[1-9]|1[0-2])[/.-]\d{4}\b|\b(?:19|20)\d{2}\b", text))


def _is_heading(text: str) -> bool:
    stripped = text.strip()
    return stripped.upper() in {"KURZPROFIL", "BERUFSERFAHRUNG", "AUSBILDUNG", "SPRACHEN", "KONTAKT", "FÄHIGKEITEN"}


def _first_text(blocks: list[AnchorBlock]) -> str | None:
    if not blocks:
        return None
    return sorted(blocks, key=lambda block: (block.y, block.x))[0].paragraphs[0]


def _unique(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        clean = _clean_text(item)
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _title_language(name: str) -> str:
    mapping = {"english": "Englisch", "chinese": "Chinesisch"}
    return mapping.get(name.lower(), name[:1].upper() + name[1:].lower())
