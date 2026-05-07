from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from resume_tailor.models import Education, Experience, ResumeData
from resume_tailor.parsing.delta_resume_parser import _clean_text, _emu_to_inch, parse_delta_resume


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

WORD_NAMESPACES = {
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "cx1": "http://schemas.microsoft.com/office/drawing/2015/9/8/chartex",
    "cx2": "http://schemas.microsoft.com/office/drawing/2015/10/21/chartex",
    "cx3": "http://schemas.microsoft.com/office/drawing/2016/5/9/chartex",
    "cx4": "http://schemas.microsoft.com/office/drawing/2016/5/10/chartex",
    "cx5": "http://schemas.microsoft.com/office/drawing/2016/5/11/chartex",
    "cx6": "http://schemas.microsoft.com/office/drawing/2016/5/12/chartex",
    "cx7": "http://schemas.microsoft.com/office/drawing/2016/5/13/chartex",
    "cx8": "http://schemas.microsoft.com/office/drawing/2016/5/14/chartex",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "aink": "http://schemas.microsoft.com/office/drawing/2016/ink",
    "am3d": "http://schemas.microsoft.com/office/drawing/2017/model3d",
    "o": "urn:schemas-microsoft-com:office:office",
    "oel": "http://schemas.microsoft.com/office/2019/extlst",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v": "urn:schemas-microsoft-com:vml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w10": "urn:schemas-microsoft-com:office:word",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16": "http://schemas.microsoft.com/office/word/2018/wordml",
    "w16sdtdh": "http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash",
    "w16se": "http://schemas.microsoft.com/office/word/2015/wordml/symex",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "a14": "http://schemas.microsoft.com/office/drawing/2010/main",
    "mac": "http://schemas.microsoft.com/office/mac/drawingml/2011/main",
}


class DeltaTemplatePatcher:
    """Patch the original Delta Lebenslauf DOCX while preserving layout.

    The Delta template stores content in DrawingML/VML text boxes. This class
    finds text boxes by their page coordinates, maps their current content to
    replacement paragraphs, then patches every matching text box occurrence in
    the document XML, including compatibility fallback copies.
    """

    def __init__(self, template_docx: Path) -> None:
        self.template_docx = template_docx

    def render(self, resume: ResumeData, out_path: Path) -> None:
        if not self.template_docx.exists():
            raise FileNotFoundError(f"Template not found: {self.template_docx}")

        with zipfile.ZipFile(self.template_docx, "r") as source:
            document_xml = source.read("word/document.xml")
            root = ET.fromstring(document_xml)
            replacements = self._build_replacements(root, resume)
            self._apply_replacements(root, replacements)
            _register_word_namespaces()
            patched_xml = _ensure_namespace_declarations(ET.tostring(root, encoding="utf-8", xml_declaration=True))

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as target:
                for item in source.infolist():
                    data = patched_xml if item.filename == "word/document.xml" else source.read(item.filename)
                    target.writestr(item, data)
        self._verify_patch(resume, out_path)

    def _build_replacements(self, root, resume: ResumeData) -> dict[tuple[str, ...], list[str]]:
        anchors = _anchors(root)
        replacements: dict[tuple[str, ...], list[str]] = {}

        def put(match, paragraphs: list[str]) -> None:
            block = _find_anchor(anchors, **match)
            if block is not None:
                replacements[_key(block["paragraphs"])] = paragraphs

        put({"x": (1.7, 2.1), "y": (-0.45, 0.35)}, ["KURZPROFIL"])
        put({"x": (1.6, 2.1), "y": (0.0, 0.5)}, [_fit_text(resume.profile, 720)])

        put({"x": (-0.2, 0.3), "y": (1.45, 1.95)}, [resume.first_name])
        put({"x": (-0.2, 0.3), "y": (2.0, 2.4)}, [resume.last_name.upper()])
        put({"x": (-1.35, -0.9), "y": (3.6, 3.95)}, [resume.phone])
        put({"x": (-1.35, -0.9), "y": (3.95, 4.25)}, [resume.email])
        put({"x": (-1.35, -0.9), "y": (4.25, 4.65)}, [_fit_text(resume.address, 90)])
        put({"x": (-0.2, 0.3), "y": (5.35, 5.9)}, resume.skills[:9])
        put(
            {"x": (-0.2, 0.3), "y": (9.2, 10.0)},
            [f"{language.name}: {language.level}" for language in resume.languages[:3]],
        )

        experience_slots = [
            {
                "title": {"x": (1.6, 2.1), "y": (2.0, 2.3)},
                "company": {"x": (1.6, 2.1), "y": (2.3, 2.5)},
                "date": {"x": (1.6, 2.1), "y": (2.5, 2.8)},
                "bullets": {"x": (1.4, 1.8), "y": (2.8, 3.1)},
                "max_bullets": 4,
            },
            {
                "title": {"x": (1.6, 2.1), "y": (4.6, 4.9)},
                "company": {"x": (1.6, 2.1), "y": (4.9, 5.15)},
                "date": {"x": (1.6, 2.1), "y": (5.15, 5.35)},
                "bullets": {"x": (1.4, 1.8), "y": (5.35, 5.75)},
                "max_bullets": 4,
            },
            {
                "title": {"x": (1.6, 2.1), "y": (7.0, 7.4)},
                "company": {"x": (1.6, 2.1), "y": (7.35, 7.65)},
                "date": {"x": (1.6, 2.1), "y": (7.65, 7.95)},
                "bullets": {"x": (1.4, 1.8), "y": (7.9, 8.2)},
                "max_bullets": 2,
            },
        ]
        for exp, slot in zip(resume.experiences, experience_slots):
            self._put_experience(anchors, replacements, exp, slot)

        education_slots = [
            {
                "degree": {"x": (1.6, 2.1), "y": (8.95, 9.25)},
                "date": {"x": (1.6, 2.1), "y": (9.25, 9.55)},
            },
            {
                "degree": {"x": (1.6, 2.1), "y": (9.55, 9.85)},
                "date": {"x": (1.6, 2.1), "y": (9.85, 10.2)},
            },
        ]
        for edu, slot in zip(resume.education, education_slots):
            self._put_education(anchors, replacements, edu, slot)

        return replacements

    def _put_experience(self, anchors, replacements, exp: Experience, slot: dict) -> None:
        for field, value in [
            ("title", [exp.title]),
            ("company", [exp.company]),
            ("date", [_period_location(exp)]),
            ("bullets", [_fit_text(item, 145) for item in exp.bullets[: slot["max_bullets"]]]),
        ]:
            block = _find_anchor(anchors, **slot[field])
            if block is not None:
                replacements[_key(block["paragraphs"])] = value

    def _put_education(self, anchors, replacements, edu: Education, slot: dict) -> None:
        degree = f"{edu.degree}, {edu.institution}" if edu.institution else edu.degree
        detail = edu.period
        if edu.details:
            detail = f"{detail} | {edu.details}" if detail else edu.details
        for field, value in [("degree", [degree]), ("date", [detail])]:
            block = _find_anchor(anchors, **slot[field])
            if block is not None:
                replacements[_key(block["paragraphs"])] = value

    def _apply_replacements(self, root, replacements: dict[tuple[str, ...], list[str]]) -> None:
        for txbx in root.findall(".//w:txbxContent", NS):
            paragraphs = [_paragraph_text(p) for p in txbx.findall("w:p", NS)]
            key = _key(paragraphs)
            if key in replacements:
                _replace_textbox_paragraphs(txbx, replacements[key])

    def _verify_patch(self, resume: ResumeData, out_path: Path) -> None:
        parsed = parse_delta_resume(out_path)
        expected_skills = resume.skills[: len(parsed.skills)]
        if parsed.skills and parsed.skills != expected_skills:
            raise RuntimeError(
                "Template patch verification failed: Fähigkeiten in output do not match optimized skills."
            )


def _anchors(root) -> list[dict]:
    result = []
    for anchor in root.findall(".//wp:anchor", NS):
        extent = anchor.find("wp:extent", NS)
        pos_x = anchor.find("wp:positionH/wp:posOffset", NS)
        pos_y = anchor.find("wp:positionV/wp:posOffset", NS)
        if extent is None or pos_y is None:
            continue
        txbx = anchor.find(".//w:txbxContent", NS)
        if txbx is None:
            continue
        paragraphs = [_paragraph_text(p) for p in txbx.findall("w:p", NS)]
        paragraphs = [p for p in paragraphs if p]
        if not paragraphs:
            continue
        result.append(
            {
                "x": _emu_to_inch(pos_x.text) if pos_x is not None and pos_x.text else 0.0,
                "y": _emu_to_inch(pos_y.text),
                "width": _emu_to_inch(extent.get("cx", "0")),
                "height": _emu_to_inch(extent.get("cy", "0")),
                "paragraphs": paragraphs,
            }
        )
    return result


def _find_anchor(anchors: list[dict], x: tuple[float, float], y: tuple[float, float]) -> dict | None:
    candidates = [block for block in anchors if x[0] <= block["x"] <= x[1] and y[0] <= block["y"] <= y[1]]
    if not candidates:
        return None
    return sorted(candidates, key=lambda block: (block["y"], block["x"]))[0]


def _replace_textbox_paragraphs(txbx, new_paragraphs: list[str]) -> None:
    paragraphs = txbx.findall("w:p", NS)
    if not paragraphs:
        return
    template = paragraphs[-1]
    while len(paragraphs) < len(new_paragraphs):
        clone = copy.deepcopy(template)
        txbx.append(clone)
        paragraphs.append(clone)
    while len(paragraphs) > len(new_paragraphs) and len(paragraphs) > 1:
        txbx.remove(paragraphs.pop())
    for paragraph, text in zip(paragraphs, new_paragraphs):
        _set_paragraph_text(paragraph, text)


def _set_paragraph_text(paragraph, text: str) -> None:
    text_nodes = paragraph.findall(".//w:t", NS)
    if not text_nodes:
        return
    text_nodes[0].text = text
    text_nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for node in text_nodes[1:]:
        node.text = ""


def _paragraph_text(paragraph) -> str:
    return _clean_text("".join(node.text or "" for node in paragraph.findall(".//w:t", NS)))


def _key(paragraphs: list[str]) -> tuple[str, ...]:
    return tuple(_clean_text(p).lower() for p in paragraphs if _clean_text(p))


def _period_location(exp: Experience) -> str:
    return f"{exp.period}, {exp.location}" if exp.location else exp.period


def _register_word_namespaces() -> None:
    for prefix, uri in WORD_NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def _ensure_namespace_declarations(xml_bytes: bytes) -> bytes:
    xml = xml_bytes.decode("utf-8")
    start = xml.find("<w:document ")
    if start == -1:
        return xml_bytes
    insert_at = start + len("<w:document")
    additions = []
    for prefix, uri in WORD_NAMESPACES.items():
        declaration = f"xmlns:{prefix}="
        if declaration not in xml[: xml.find(">", start)]:
            additions.append(f' xmlns:{prefix}="{uri}"')
    if additions:
        xml = xml[:insert_at] + "".join(additions) + xml[insert_at:]
    return xml.encode("utf-8")


def _fit_text(text: str, max_chars: int) -> str:
    text = _clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip(" ,.;") + "…"
