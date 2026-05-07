from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from resume_tailor.models import ResumeData


@dataclass
class TextChange:
    label: str
    before: str
    after: str


@dataclass
class ListChange:
    label: str
    before: list[str]
    after: list[str]
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


@dataclass
class ResumeDiff:
    profile_changed: bool
    skill_order_changed: bool
    changed_experiences: int
    text_changes: list[TextChange]
    list_changes: list[ListChange]
    warnings: list[str]


def build_resume_diff(before: ResumeData, after: ResumeData) -> ResumeDiff:
    text_changes: list[TextChange] = []
    list_changes: list[ListChange] = []
    warnings: list[str] = []

    if before.profile.strip() != after.profile.strip():
        text_changes.append(TextChange("个人简介", before.profile, after.profile))

    if before.skills != after.skills:
        list_changes.append(_list_change("技能", before.skills, after.skills))

    before_exp = {(item.title, item.company, item.period): item for item in before.experiences}
    before_exp_by_company_period = {(item.company, item.period): item for item in before.experiences}
    changed_experiences = 0
    for after_exp in after.experiences:
        key = (after_exp.title, after_exp.company, after_exp.period)
        before_exp_item = before_exp.get(key) or before_exp_by_company_period.get((after_exp.company, after_exp.period))
        if not before_exp_item:
            warnings.append(f"输出中出现新的工作经历块: {after_exp.title} | {after_exp.company}")
            continue
        if before_exp_item.bullets != after_exp.bullets:
            changed_experiences += 1
            list_changes.append(
                _list_change(
                    f"工作经历: {after_exp.title} | {after_exp.company}",
                    before_exp_item.bullets,
                    after_exp.bullets,
                )
            )

    allowed_skills = {skill.lower() for skill in before.skills}
    unexpected_skills = [skill for skill in after.skills if skill.lower() not in allowed_skills]
    if unexpected_skills:
        warnings.append("输出中包含原简历未出现的技能: " + ", ".join(unexpected_skills))

    return ResumeDiff(
        profile_changed=bool(text_changes),
        skill_order_changed=before.skills != after.skills,
        changed_experiences=changed_experiences,
        text_changes=text_changes,
        list_changes=list_changes,
        warnings=warnings,
    )


def write_diff_files(diff: ResumeDiff, json_path: Path, markdown_path: Path) -> None:
    json_path.write_text(json.dumps(asdict(diff), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(format_diff_markdown(diff), encoding="utf-8")


def format_diff_markdown(diff: ResumeDiff) -> str:
    lines = ["# 修改前后对照", ""]
    if not diff.text_changes and not diff.list_changes:
        lines.append("没有检测到内容变化。")
    if diff.warnings:
        lines.extend(["## 提示", ""])
        lines.extend(f"- {warning}" for warning in diff.warnings)
        lines.append("")

    for change in diff.text_changes:
        lines.extend([f"## {change.label}", "", "**修改前**", "", change.before, "", "**修改后**", "", change.after, ""])

    for change in diff.list_changes:
        lines.extend([f"## {change.label}", "", "**修改前**"])
        lines.extend(f"- {item}" for item in change.before)
        lines.extend(["", "**修改后**"])
        lines.extend(f"- {item}" for item in change.after)
        if change.added:
            lines.extend(["", "**新增**"])
            lines.extend(f"- {item}" for item in change.added)
        if change.removed:
            lines.extend(["", "**删除**"])
            lines.extend(f"- {item}" for item in change.removed)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_diff_text(diff: ResumeDiff) -> str:
    markdown = format_diff_markdown(diff)
    return markdown.replace("# ", "").replace("## ", "")


def _list_change(label: str, before: list[str], after: list[str]) -> ListChange:
    before_set = {item.lower(): item for item in before}
    after_set = {item.lower(): item for item in after}
    added = [after_set[key] for key in after_set.keys() - before_set.keys()]
    removed = [before_set[key] for key in before_set.keys() - after_set.keys()]
    return ListChange(label, before, after, added, removed)
