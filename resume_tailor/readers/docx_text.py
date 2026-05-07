from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_docx_text(path: Path) -> str:
    """Extract text from normal DOCX content and text boxes.

    The current Delta template stores most text inside drawing/VML text boxes,
    so python-docx paragraph extraction is not enough. Reading all w:t nodes is
    intentionally low-level and works for both regular paragraphs and textboxes.
    """
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")

    root = ET.fromstring(xml)
    texts = [node.text or "" for node in root.findall(".//w:t", WORD_NS)]
    return "\n".join(_dedupe_template_text_nodes(texts))


def extract_first_image(path: Path, out_path: Path) -> Path | None:
    with zipfile.ZipFile(path) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
        if not media:
            return None
        image_name = media[0]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(archive.read(image_name))
        return out_path


def _dedupe_template_text_nodes(texts: list[str]) -> list[str]:
    """Remove exact duplicated runs caused by dual DrawingML/VML text boxes."""
    result: list[str] = []
    seen_window: list[str] = []
    for text in texts:
        clean = text.strip()
        if not clean:
            continue
        if clean in seen_window[-80:]:
            continue
        result.append(clean)
        seen_window.append(clean)
    return result
