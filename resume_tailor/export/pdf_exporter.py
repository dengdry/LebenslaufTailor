from __future__ import annotations

import shutil
import subprocess
import uuid
import re
from pathlib import Path


WINDOWS_BROWSER_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]


def export_html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    html_path = html_path.resolve()
    pdf_path = pdf_path.resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"HTML 文件不存在: {html_path}")

    browser = _find_browser()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()

    profile_dir = pdf_path.parent / ".pdf_profiles" / uuid.uuid4().hex
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        last_error = ""
        for headless_arg in ("--headless=new", "--headless"):
            command = [
                str(browser),
                headless_arg,
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=1000",
                f"--user-data-dir={profile_dir}",
                f"--print-to-pdf={pdf_path}",
                html_path.as_uri(),
            ]
            completed = subprocess.run(command, capture_output=True, timeout=90)
            if completed.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
                return pdf_path
            output = completed.stderr or completed.stdout or b""
            last_error = output.decode("utf-8", errors="replace").strip()
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    raise RuntimeError(f"PDF 导出失败。浏览器输出: {last_error or '无输出'}")


def count_pdf_pages(pdf_path: Path) -> int:
    pdf_path = pdf_path.resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    data = pdf_path.read_bytes()

    page_objects = re.findall(rb"/Type\s*/Page(?!s)\b", data)
    if page_objects:
        return len(page_objects)

    counts = [int(value) for value in re.findall(rb"/Count\s+(\d+)", data)]
    if counts:
        return max(counts)

    raise RuntimeError("无法读取 PDF 页数。")


def _find_browser() -> Path:
    for path in WINDOWS_BROWSER_CANDIDATES:
        if path.exists():
            return path

    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return Path(found)

    raise RuntimeError("没有找到可用浏览器。请安装 Microsoft Edge 或 Google Chrome。")
