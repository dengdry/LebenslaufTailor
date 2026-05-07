from __future__ import annotations

from pathlib import Path

from resume_tailor.models import MatchReport


def write_match_report(report: MatchReport, out_path: Path) -> None:
    lines = [
        "# 德国简历匹配报告",
        "",
        f"**总分:** {report.total_score}/100",
        "",
        "## 维度评分",
        "",
    ]
    for dimension in report.dimensions:
        lines.append(f"- **{dimension.name}:** {dimension.score}/{dimension.max_score}")
        for note in dimension.notes:
            lines.append(f"  - {note}")

    lines.extend(["", "## 已匹配关键词", ""])
    lines.append(", ".join(report.matched_keywords) if report.matched_keywords else "无")

    lines.extend(["", "## 缺失或较弱关键词", ""])
    lines.append(", ".join(report.missing_keywords) if report.missing_keywords else "无")

    lines.extend(["", "## 建议", ""])
    for rec in report.recommendations:
        lines.append(f"- {rec}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
