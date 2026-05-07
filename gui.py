from __future__ import annotations

from copy import deepcopy
import threading
import os
import re
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    X,
    Y,
    Button,
    Entry,
    Frame,
    Label,
    LabelFrame,
    StringVar,
    Text,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    OptionMenu,
)
from tkinter.scrolledtext import ScrolledText
from tkinter.ttk import Combobox, Notebook, Progressbar

from resume_tailor.config import APP_CONFIG_FILE, LLMSettings
from resume_tailor.export.html_renderer import GermanDeltaHtmlRenderer
from resume_tailor.export.pdf_exporter import count_pdf_pages, export_html_to_pdf
from resume_tailor.language import detect_jd_language
from resume_tailor.llm.factory import build_llm_client
from resume_tailor.models import Education, Experience, Language, ResumeData
from resume_tailor.parsing.delta_resume_parser import preview_resume
from resume_tailor.parsing.html_resume_parser import parse_html_resume
from resume_tailor.rewriting.diff import build_resume_diff, format_diff_markdown, format_diff_text, write_diff_files
from resume_tailor.rewriting.llm_optimizer import optimize_with_optional_llm
from resume_tailor.scoring.german_scorer import GermanScorer
from resume_tailor.scoring.semantic_scorer import DualScoreReport, score_with_optional_llm
from resume_tailor.writers.report_writer import write_match_report


MODEL_CHOICES = {
    "off": [""],
    "openai": ["gpt-5.2", "gpt-5", "gpt-4.1"],
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    "ollama": ["llama3.1", "qwen2.5", "mistral", "gemma3"],
}


class GermanResumeApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("德国简历定制工具")
        self.root.geometry("1120x760")
        self.root.minsize(980, 680)

        self.resume_html_path = StringVar()
        self.output_dir = StringVar(value=str(Path.cwd() / "outputs"))
        env_settings = LLMSettings.load()
        self.llm_provider = StringVar(
            value=env_settings.provider if env_settings.provider in {"off", "openai", "deepseek", "ollama"} else "off"
        )
        self.llm_model = StringVar(value=env_settings.model)
        self.api_key = StringVar(value=self._key_for_provider(env_settings))
        self.last_html_path: Path | None = None
        self.last_pdf_path: Path | None = None
        self.last_diff_path: Path | None = None
        self.last_diff_text = ""
        self.last_original_resume: ResumeData | None = None
        self.last_tailored_resume: ResumeData | None = None
        self.last_photo_path: Path | None = None
        self.last_rewrite_notes: list[str] = []
        self.last_jd = ""
        self.last_resume_language = "de"
        self.status = StringVar(value="就绪")

        self._build()

    def _build(self) -> None:
        outer = Frame(self.root, padx=16, pady=14)
        outer.pack(fill=BOTH, expand=True)

        file_panel = LabelFrame(outer, text="文件", padx=10, pady=8)
        file_panel.pack(fill=X)
        template_hint = Frame(file_panel)
        template_hint.pack(fill=X, pady=(0, 6))
        Label(
            template_hint,
            text="第一次使用：先复制并填写 resume_templates/mustermann_resume_template.html，然后在下方选择填写后的 HTML。",
            anchor="w",
        ).pack(side=LEFT, fill=X, expand=True)
        Button(template_hint, text="填写/编辑简历", command=self.open_master_resume_editor, width=16).pack(
            side=RIGHT, padx=(8, 0)
        )
        Button(template_hint, text="打开模板文件夹", command=self._open_template_folder, width=16).pack(side=RIGHT)
        self._path_row(file_panel, "简历 HTML", self.resume_html_path, self._choose_resume_html)
        self._path_row(file_panel, "输出文件夹", self.output_dir, self._choose_output_dir)
        self._llm_row(file_panel)

        body = Frame(outer)
        body.pack(fill=BOTH, expand=True, pady=(12, 8))

        left = LabelFrame(body, text="岗位描述 JD", padx=10, pady=8)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        self.jd_text = Text(left, wrap="word", height=24, undo=True)
        self.jd_text.pack(fill=BOTH, expand=True)

        right = LabelFrame(body, text="匹配报告", padx=10, pady=8)
        right.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))
        self.report_text = Text(right, wrap="word", height=24)
        self.report_text.pack(fill=BOTH, expand=True)

        action_bar = Frame(outer)
        action_bar.pack(fill=X)
        Button(action_bar, text="1. 分析", command=self.analyze_match, width=12).pack(side=LEFT, padx=(0, 8))
        Button(action_bar, text="2. 生成简历", command=self.generate_html, width=14).pack(side=LEFT, padx=(0, 8))
        Button(action_bar, text="3. 检查与编辑", command=self.open_review_editor, width=16).pack(side=LEFT, padx=(0, 8))
        Button(action_bar, text="4. 预览", command=self.open_html_preview, width=12).pack(side=LEFT, padx=(0, 8))
        Button(action_bar, text="5. 导出 PDF", command=self.export_pdf, width=14).pack(side=LEFT, padx=(0, 8))

        self.progress = Progressbar(action_bar, mode="indeterminate", length=160)
        self.progress.pack(side=RIGHT)

        Label(outer, textvariable=self.status, anchor="w").pack(fill=X, pady=(8, 0))

    def _path_row(self, parent: Frame, label: str, variable: StringVar, command) -> None:
        row = Frame(parent)
        row.pack(fill=X, pady=3)
        Label(row, text=label, width=14, anchor="w").pack(side=LEFT)
        Entry(row, textvariable=variable).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        Button(row, text="浏览", command=command, width=10).pack(side=RIGHT)

    def _llm_row(self, parent: Frame) -> None:
        row = Frame(parent)
        row.pack(fill=X, pady=3)
        Label(row, text="模型服务", width=14, anchor="w").pack(side=LEFT)
        provider_menu = OptionMenu(
            row,
            self.llm_provider,
            self.llm_provider.get(),
            "off",
            "openai",
            "deepseek",
            "ollama",
            command=self._on_provider_change,
        )
        provider_menu.pack(side=LEFT, padx=(0, 8))
        Label(row, text="模型").pack(side=LEFT, padx=(0, 6))
        self.model_combo = Combobox(row, textvariable=self.llm_model, values=MODEL_CHOICES[self.llm_provider.get()])
        self.model_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        Label(row, text="API 密钥").pack(side=LEFT, padx=(0, 6))
        Entry(row, textvariable=self.api_key, show="*", width=32).pack(side=LEFT)
        Button(row, text="保存模型设置", command=self._save_llm_settings, width=18).pack(side=LEFT, padx=(8, 0))
        self._on_provider_change(self.llm_provider.get())

    def _on_provider_change(self, provider: str) -> None:
        choices = MODEL_CHOICES.get(provider, [""])
        self.model_combo.configure(values=choices)
        current = self.llm_model.get().strip()
        if not current or current not in choices:
            self.llm_model.set(choices[0])
        saved = LLMSettings.load()
        self.api_key.set(self._key_for_provider(saved, provider))

    def _save_llm_settings(self) -> None:
        settings = self._llm_settings()
        settings.save()
        self.status.set(f"模型设置已保存: {APP_CONFIG_FILE}")

    def _choose_resume_html(self) -> None:
        path = filedialog.askopenfilename(
            title="选择简历 HTML",
            filetypes=[("HTML 文件", "*.html;*.htm"), ("所有文件", "*.*")],
        )
        if path:
            self.resume_html_path.set(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_dir.set(path)

    def _open_template_folder(self) -> None:
        template_dir = Path(__file__).resolve().parent / "resume_templates"
        os.startfile(template_dir)

    def _default_template_html(self) -> Path:
        return Path(__file__).resolve().parent / "resume_templates" / "mustermann_resume_template.html"

    def analyze_match(self) -> None:
        self._run_background(self._analyze_match)

    def generate_html(self) -> None:
        self._run_background(self._generate_html)

    def export_pdf(self) -> None:
        self._run_background(self._export_pdf)

    def open_review_editor(self) -> None:
        if not self.last_original_resume or not self.last_tailored_resume:
            messagebox.showinfo("检查与编辑", "还没有可检查的修改结果。请先点击“生成简历”。")
            return
        self._open_resume_editor(
            title="检查与编辑",
            subtitle="先查看修改对照，再按需编辑内容。保存后会重新生成 HTML。",
            resume=self.last_tailored_resume,
            diff_text=self.last_diff_text or "暂无修改对照。",
            save_label="保存并重新生成 HTML",
            on_save=self._apply_manual_resume,
        )

    def open_master_resume_editor(self) -> None:
        html_value = self.resume_html_path.get().strip()
        html_path = Path(html_value) if html_value else self._default_template_html()
        if not html_path.exists():
            messagebox.showerror("填写/编辑简历", f"找不到 HTML 模板: {html_path}")
            return
        resume = parse_html_resume(html_path)
        source_photo = self._html_photo(html_path)

        def save_master(edited: ResumeData) -> None:
            out = self._output_dir() / "master_resume.html"
            GermanDeltaHtmlRenderer(fallback_photo=source_photo).render(edited, out)
            self.resume_html_path.set(str(out))
            self.last_photo_path = source_photo
            self._set_status(f"Master Resume 已保存: {out}")
            messagebox.showinfo("填写/编辑简历", f"已保存为:\n{out}\n\n接下来粘贴 JD，然后点击“分析”或“生成简历”。")

        self._open_resume_editor(
            title="填写/编辑简历",
            subtitle="第一次使用时，先把示例内容改成自己的。保存后会生成 master_resume.html，并自动填入“简历 HTML”。",
            resume=resume,
            diff_text=None,
            save_label="保存为 Master Resume",
            on_save=save_master,
        )

    def _open_resume_editor(
        self,
        title: str,
        subtitle: str,
        resume: ResumeData,
        diff_text: str | None,
        save_label: str,
        on_save,
    ) -> None:
        window = Toplevel(self.root)
        window.title(title)
        window.geometry("1040x780")
        window.minsize(820, 580)

        Label(window, text=title, anchor="w", font=("Segoe UI", 12, "bold")).pack(
            fill=X, padx=12, pady=(10, 4)
        )
        Label(window, text=subtitle, anchor="w").pack(fill=X, padx=12, pady=(0, 8))

        notebook = Notebook(window)
        notebook.pack(fill=BOTH, expand=True, padx=12, pady=(0, 8))

        contact_tab = Frame(notebook, padx=8, pady=8)
        profile_tab = Frame(notebook, padx=8, pady=8)
        skills_tab = Frame(notebook, padx=8, pady=8)
        languages_tab = Frame(notebook, padx=8, pady=8)
        experience_tab = Frame(notebook, padx=8, pady=8)
        education_tab = Frame(notebook, padx=8, pady=8)
        if diff_text is not None:
            diff_tab = Frame(notebook, padx=8, pady=8)
            notebook.add(diff_tab, text="修改对照")
        notebook.add(profile_tab, text="个人简介")
        notebook.add(contact_tab, text="个人信息")
        notebook.add(skills_tab, text="技能")
        notebook.add(languages_tab, text="语言")
        notebook.add(experience_tab, text="工作经历")
        notebook.add(education_tab, text="教育")

        if diff_text is not None:
            diff_widget = ScrolledText(diff_tab, wrap="word", undo=False)
            diff_widget.pack(fill=BOTH, expand=True)
            diff_widget.insert("1.0", diff_text)
            diff_widget.configure(state="disabled")

        Label(contact_tab, text="格式：名、姓、邮箱、电话、地址。", anchor="w").pack(fill=X, pady=(0, 6))
        contact_text = ScrolledText(contact_tab, wrap="word", height=12, undo=True)
        contact_text.pack(fill=BOTH, expand=True)
        contact_text.insert("1.0", _format_contact_edit_text(resume))

        profile_text = ScrolledText(profile_tab, wrap="word", height=18, undo=True)
        profile_text.pack(fill=BOTH, expand=True)
        profile_text.insert("1.0", resume.profile)

        Label(skills_tab, text="每行一个技能。", anchor="w").pack(fill=X, pady=(0, 6))
        skills_text = ScrolledText(skills_tab, wrap="word", height=18, undo=True)
        skills_text.pack(fill=BOTH, expand=True)
        skills_text.insert("1.0", "\n".join(resume.skills))

        Label(languages_tab, text="每行一种语言，格式：语言 | 水平。", anchor="w").pack(fill=X, pady=(0, 6))
        languages_text = ScrolledText(languages_tab, wrap="word", height=18, undo=True)
        languages_text.pack(fill=BOTH, expand=True)
        languages_text.insert("1.0", _format_language_edit_text(resume))

        Label(
            experience_tab,
            text="格式：### 序号. 职位 | 公司 | 时间 | 城市；下面每行一个以 - 开头的经历要点。",
            anchor="w",
        ).pack(fill=X, pady=(0, 6))
        experience_text = ScrolledText(experience_tab, wrap="word", height=18, undo=True)
        experience_text.pack(fill=BOTH, expand=True)
        experience_text.insert("1.0", _format_experience_edit_text(resume))

        Label(education_tab, text="每行一段教育经历，格式：学位 | 学校 | 时间 | 备注。", anchor="w").pack(
            fill=X, pady=(0, 6)
        )
        education_text = ScrolledText(education_tab, wrap="word", height=18, undo=True)
        education_text.pack(fill=BOTH, expand=True)
        education_text.insert("1.0", _format_education_edit_text(resume))

        button_bar = Frame(window)
        button_bar.pack(fill=X, padx=12, pady=(0, 12))

        def save_edits() -> None:
            try:
                edited = deepcopy(resume)
                _apply_contact_edit_text(edited, contact_text.get("1.0", END))
                edited.profile = profile_text.get("1.0", END).strip()
                edited.skills = _clean_multiline_items(skills_text.get("1.0", END))
                _apply_language_edit_text(edited, languages_text.get("1.0", END))
                _apply_experience_edit_text(edited, experience_text.get("1.0", END))
                _apply_education_edit_text(edited, education_text.get("1.0", END))
                on_save(edited)
                window.destroy()
            except Exception as exc:
                messagebox.showerror(title, str(exc))

        Button(button_bar, text=save_label, command=save_edits, width=22).pack(side=LEFT, padx=(0, 8))
        Button(button_bar, text="关闭", command=window.destroy, width=10).pack(side=LEFT)

    def open_html_preview(self) -> None:
        path = self.last_html_path or (self._output_dir() / "tailored_lebenslauf.html")
        if not path.exists():
            messagebox.showinfo("预览", "还没有生成修改后的 HTML 简历。")
            return
        os.startfile(path)

    def _analyze_match(self) -> None:
        jd = self._require_jd()
        parsed_resume = self._load_source_resume()
        resume_text = "\n".join(parsed_resume.all_text_parts())
        report = GermanScorer().score(resume_text, jd)
        llm = build_llm_client(self._llm_settings())
        dual_report = score_with_optional_llm(report, resume_text, jd, llm)
        out = self._output_dir() / "match_report.md"
        write_match_report(report, out)
        self._show_report(preview_resume(parsed_resume) + "\n\n" + _format_dual_report(dual_report))
        self._set_status(f"匹配报告已保存: {out}")

    def _generate_html(self) -> None:
        jd = self._require_jd()
        out_dir = self._output_dir()
        out = out_dir / "tailored_lebenslauf.html"
        report_out = out_dir / "tailored_match_report.md"
        diff_json = out_dir / "rewrite_diff.json"
        diff_md = out_dir / "rewrite_diff.md"
        language = detect_jd_language(jd)

        parsed_resume = self._load_source_resume()
        settings = self._llm_settings()
        llm = build_llm_client(settings)
        optimized = optimize_with_optional_llm(parsed_resume, jd, llm, language)
        resume = optimized.resume
        fallback_photo = self._source_html_photo()
        GermanDeltaHtmlRenderer(language=language, fallback_photo=fallback_photo).render(resume, out)
        diff = build_resume_diff(parsed_resume, resume)
        write_diff_files(diff, diff_json, diff_md)
        self.last_diff_path = diff_md
        self.last_diff_text = _format_diff_view(diff, optimized.notes)
        diff_md.write_text(self.last_diff_text, encoding="utf-8")

        report = GermanScorer().score("\n".join(resume.all_text_parts()), jd)
        layout_warnings = _layout_warnings(resume)
        write_match_report(report, report_out)
        _append_layout_warnings(report_out, layout_warnings)
        self._show_report(
            _format_report(report, optimized.mode, optimized.notes, layout_warnings) + "\n\n" + format_diff_text(diff)
        )
        self.last_html_path = out
        self.last_original_resume = parsed_resume
        self.last_tailored_resume = resume
        self.last_photo_path = fallback_photo
        self.last_rewrite_notes = optimized.notes
        self.last_jd = jd
        self.last_resume_language = language
        self._set_status(f"修改后的简历已生成: {out}（语言: {'英语' if language == 'en' else '德语'}）")

    def _export_pdf(self) -> None:
        html_path = self.last_html_path or (self._output_dir() / "tailored_lebenslauf.html")
        if not html_path.exists():
            raise ValueError("请先点击“生成简历”，生成 HTML 简历后再导出 PDF。")
        pdf_path = self._output_dir() / "tailored_lebenslauf.pdf"
        export_html_to_pdf(html_path, pdf_path)
        page_count = count_pdf_pages(pdf_path)
        self.last_pdf_path = pdf_path
        self._set_status(f"PDF 已导出: {pdf_path}（{page_count} 页）")
        if page_count > 1:
            self.root.after(
                0,
                lambda: messagebox.showwarning(
                    "PDF 页数提示",
                    f"当前 PDF 为 {page_count} 页。若目标是单页简历，建议回到“检查与编辑”压缩个人简介、技能或经历要点。",
                ),
            )
        os.startfile(pdf_path)

    def _apply_manual_resume(self, resume: ResumeData) -> None:
        if not self.last_original_resume:
            raise ValueError("没有可用的原始简历数据。请先点击“生成简历”。")
        out_dir = self._output_dir()
        out = out_dir / "tailored_lebenslauf.html"
        report_out = out_dir / "tailored_match_report.md"
        diff_json = out_dir / "rewrite_diff.json"
        diff_md = out_dir / "rewrite_diff.md"
        notes = [*self.last_rewrite_notes, "已应用手动编辑。"]

        GermanDeltaHtmlRenderer(
            language=self.last_resume_language,
            fallback_photo=self.last_photo_path,
        ).render(resume, out)
        diff = build_resume_diff(self.last_original_resume, resume)
        write_diff_files(diff, diff_json, diff_md)
        self.last_diff_path = diff_md
        self.last_diff_text = _format_diff_view(diff, notes)
        diff_md.write_text(self.last_diff_text, encoding="utf-8")

        report = GermanScorer().score("\n".join(resume.all_text_parts()), self.last_jd)
        layout_warnings = _layout_warnings(resume)
        write_match_report(report, report_out)
        _append_layout_warnings(report_out, layout_warnings)
        self._show_report(_format_report(report, "manual", notes, layout_warnings) + "\n\n" + format_diff_text(diff))
        self.last_tailored_resume = resume
        self.last_html_path = out
        self.last_pdf_path = None
        self._set_status(f"手动修改已应用，HTML 已重新生成: {out}")

    def _run_background(self, task) -> None:
        def wrapped() -> None:
            self.root.after(0, self._busy, True)
            try:
                task()
            except Exception as exc:  # pragma: no cover - GUI error boundary
                self.root.after(0, lambda: messagebox.showerror("错误", str(exc)))
                self.root.after(0, lambda: self.status.set("出错"))
            finally:
                self.root.after(0, self._busy, False)

        threading.Thread(target=wrapped, daemon=True).start()

    def _busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(10)
            self.status.set("处理中...")
        else:
            self.progress.stop()

    def _show_report(self, text: str) -> None:
        self.root.after(0, lambda: self._replace_text(self.report_text, text))

    def _set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status.set(text))

    def _replace_text(self, widget: Text, text: str) -> None:
        widget.delete("1.0", END)
        widget.insert("1.0", text)

    def _load_source_resume(self) -> ResumeData:
        html_value = self.resume_html_path.get().strip()
        if not html_value:
            raise ValueError("请先选择填写好的简历 HTML。第一次使用可从 resume_templates/mustermann_resume_template.html 复制一份再修改。")
        html_path = Path(html_value)
        if not html_path.exists():
            raise ValueError(f"简历 HTML 不存在: {html_path}")
        return parse_html_resume(html_path)

    def _source_html_photo(self) -> Path | None:
        html_value = self.resume_html_path.get().strip()
        if not html_value:
            return None
        html_path = Path(html_value)
        if not html_path.exists():
            return None
        return self._html_photo(html_path)

    def _html_photo(self, html_path: Path) -> Path | None:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'<img[^>]+class=["\'][^"\']*\bportrait\b[^"\']*["\'][^>]+src=["\']([^"\']+)["\']', text)
        if not match:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*\bportrait\b[^"\']*["\']', text)
        if not match:
            return None
        src = match.group(1)
        if "://" in src or src.startswith("data:"):
            return None
        photo_path = (html_path.parent / src).resolve()
        return photo_path if photo_path.exists() else None

    def _require_jd(self) -> str:
        jd = self.jd_text.get("1.0", END).strip()
        if not jd:
            raise ValueError("请先粘贴岗位描述 JD。")
        return jd

    def _output_dir(self) -> Path:
        out = Path(self.output_dir.get().strip() or "outputs")
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _llm_settings(self) -> LLMSettings:
        settings = LLMSettings.load()
        settings.provider = self.llm_provider.get().strip().lower()
        key = self.api_key.get().strip()
        if settings.provider == "openai" and key:
            settings.openai_api_key = key
        if settings.provider == "deepseek" and key:
            settings.deepseek_api_key = key
        model = self.llm_model.get().strip()
        if model:
            settings.model = model
        elif settings.provider == "openai":
            settings.model = "gpt-5.2"
        elif settings.provider == "deepseek":
            settings.model = "deepseek-v4-flash"
        elif settings.provider == "ollama":
            settings.model = "llama3.1"
        return settings

    def _key_for_provider(self, settings: LLMSettings, provider: str | None = None) -> str:
        provider = provider or settings.provider
        if provider == "openai":
            return settings.openai_api_key
        if provider == "deepseek":
            return settings.deepseek_api_key
        return ""


def _format_diff_view(diff, notes: list[str] | None = None) -> str:
    lines = ["# 修改前后对照", ""]
    if notes:
        lines.extend(["## 改写备注", ""])
        lines.extend(f"- {note}" for note in notes)
        lines.append("")
    lines.append(format_diff_markdown(diff).strip())
    return "\n".join(lines).rstrip() + "\n"


def _format_contact_edit_text(resume: ResumeData) -> str:
    return "\n".join(
        [
            f"Vorname: {resume.first_name}",
            f"Nachname: {resume.last_name}",
            f"E-Mail: {resume.email}",
            f"Telefon: {resume.phone}",
            f"Adresse: {resume.address}",
        ]
    )


def _apply_contact_edit_text(resume: ResumeData, text: str) -> None:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        values[key.strip().lower()] = value.strip()
    resume.first_name = values.get("vorname", resume.first_name)
    resume.last_name = values.get("nachname", resume.last_name)
    resume.email = values.get("e-mail", resume.email)
    resume.phone = values.get("telefon", resume.phone)
    resume.address = values.get("adresse", resume.address)


def _format_language_edit_text(resume: ResumeData) -> str:
    return "\n".join(f"{item.name} | {item.level}" for item in resume.languages)


def _apply_language_edit_text(resume: ResumeData, text: str) -> None:
    languages: list[Language] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        name = parts[0] if parts else ""
        level = parts[1] if len(parts) > 1 else ""
        if name:
            languages.append(Language(name=name, level=level))
    resume.languages = languages


def _format_experience_edit_text(resume: ResumeData) -> str:
    lines: list[str] = []
    for index, item in enumerate(resume.experiences, start=1):
        lines.append(f"### {index}. {item.title} | {item.company} | {item.period} | {item.location}")
        lines.extend(f"- {bullet}" for bullet in item.bullets)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _apply_experience_edit_text(resume: ResumeData, text: str) -> None:
    experiences: list[Experience] = []
    current: Experience | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            header = line[4:]
            if "." in header:
                header = header.split(".", 1)[1].strip()
            parts = [part.strip() for part in header.split("|")]
            current = Experience(
                title=parts[0] if len(parts) > 0 else "",
                company=parts[1] if len(parts) > 1 else "",
                period=parts[2] if len(parts) > 2 else "",
                location=parts[3] if len(parts) > 3 else "",
                bullets=[],
            )
            experiences.append(current)
            continue
        if current is None:
            continue
        bullet = line[1:].strip() if line.startswith("-") else line
        if bullet:
            current.bullets.append(bullet)

    if experiences:
        resume.experiences = experiences


def _format_education_edit_text(resume: ResumeData) -> str:
    return "\n".join(
        f"{item.degree} | {item.institution} | {item.period} | {item.details}" for item in resume.education
    )


def _apply_education_edit_text(resume: ResumeData, text: str) -> None:
    education: list[Education] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        education.append(
            Education(
                degree=parts[0] if len(parts) > 0 else "",
                institution=parts[1] if len(parts) > 1 else "",
                period=parts[2] if len(parts) > 2 else "",
                details=parts[3] if len(parts) > 3 else "",
            )
        )
    resume.education = education


def _clean_multiline_items(text: str) -> list[str]:
    items = []
    seen = set()
    for line in text.splitlines():
        clean = line.strip().lstrip("-").strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            items.append(clean)
    return items


def _layout_warnings(resume: ResumeData) -> list[str]:
    warnings: list[str] = []
    experience_count = len(resume.experiences)
    total_bullets = sum(len(item.bullets) for item in resume.experiences)
    profile_length = len(resume.profile.strip())
    long_bullets = [
        f"{item.title} | {item.company}"
        for item in resume.experiences
        if any(len(bullet) > 170 for bullet in item.bullets)
    ]

    if profile_length > 520:
        warnings.append("个人简介偏长，单页版式中可能挤压工作经历；建议控制在 4-6 行。")
    if len(resume.skills) > 10:
        warnings.append(f"技能有 {len(resume.skills)} 项，当前 HTML 模板默认展示前 10 项。")
    if experience_count > 4:
        warnings.append(f"工作经历有 {experience_count} 段，单页版式可能溢出；建议保留 3-4 段最相关经历。")
    if total_bullets > 12:
        warnings.append(f"工作经历要点共 {total_bullets} 条，单页版式可能偏满；建议每段保留 2-3 条。")

    overfilled = [item for item in resume.experiences if len(item.bullets) > 4]
    for item in overfilled:
        warnings.append(f"{item.title} | {item.company} 有 {len(item.bullets)} 条要点，HTML 模板默认展示前 4 条。")

    if long_bullets:
        warnings.append("部分经历要点较长，可能导致 PDF 换行过多：" + "；".join(long_bullets[:3]))

    if not warnings and (experience_count >= 4 or total_bullets >= 10 or len(resume.skills) >= 9):
        warnings.append("当前内容接近单页容量上限，导出 PDF 后建议检查是否仍保持一页且版面不拥挤。")
    return warnings


def _append_layout_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        return
    with path.open("a", encoding="utf-8") as file:
        file.write("\n## 版面容量提示\n\n")
        for warning in warnings:
            file.write(f"- {warning}\n")


def _format_report(
    report,
    rewrite_mode: str | None = None,
    notes: list[str] | None = None,
    layout_warnings: list[str] | None = None,
) -> str:
    lines = [
        f"总分: {report.total_score}/100",
    ]
    if rewrite_mode:
        lines.extend(["", f"改写模式: {_mode_label(rewrite_mode)}"])
    if notes:
        lines.extend(["", "改写备注"])
        lines.extend(f"- {note}" for note in notes)
    if layout_warnings:
        lines.extend(["", "版面容量提示"])
        lines.extend(f"- {warning}" for warning in layout_warnings)
    lines.extend(["", "维度评分"])
    for dimension in report.dimensions:
        lines.append(f"- {dimension.name}: {dimension.score}/{dimension.max_score}")
        for note in dimension.notes:
            lines.append(f"  {note}")
    lines.extend(["", "已匹配关键词"])
    lines.append(", ".join(report.matched_keywords) if report.matched_keywords else "无")
    lines.extend(["", "缺失或较弱关键词"])
    lines.append(", ".join(report.missing_keywords) if report.missing_keywords else "无")
    lines.extend(["", "建议"])
    lines.extend(f"- {item}" for item in report.recommendations)
    return "\n".join(lines)


def _format_dual_report(dual: DualScoreReport) -> str:
    lines = [
        f"综合评分: {dual.combined_score}/100",
        f"规则评分: {dual.rule_report.total_score}/100",
    ]
    if dual.semantic_report and dual.semantic_report.mode == "llm":
        lines.append(f"大模型语义评分: {dual.semantic_report.score}/100")
    elif dual.semantic_report and dual.semantic_report.error:
        lines.extend(["大模型语义评分: 不可用", dual.semantic_report.error])
    else:
        lines.append("大模型语义评分: 已关闭")

    lines.extend(["", "规则评分维度"])
    for dimension in dual.rule_report.dimensions:
        lines.append(f"- {dimension.name}: {dimension.score}/{dimension.max_score}")
        for note in dimension.notes:
            lines.append(f"  {note}")

    semantic = dual.semantic_report
    if semantic and semantic.mode == "llm":
        lines.extend(["", "大模型语义评分维度"])
        for name, score in semantic.dimensions.items():
            lines.append(f"- {name}: {score}/100")
        lines.extend(["", "优势"])
        lines.extend(f"- {item}" for item in semantic.strengths) if semantic.strengths else lines.append("无")
        lines.extend(["", "缺口"])
        lines.extend(f"- {item}" for item in semantic.gaps) if semantic.gaps else lines.append("无")
        lines.extend(["", "大模型建议"])
        if semantic.recommendations:
            lines.extend(f"- {item}" for item in semantic.recommendations)
        else:
            lines.append("无")

    lines.extend(["", "规则建议"])
    lines.extend(f"- {item}" for item in dual.rule_report.recommendations)
    return "\n".join(lines)


def _mode_label(mode: str) -> str:
    return {
        "rules": "本地规则",
        "rules-fallback": "本地规则回退",
        "llm": "大模型改写",
        "manual": "手动编辑",
    }.get(mode, mode)


def main() -> None:
    root = Tk()
    GermanResumeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
