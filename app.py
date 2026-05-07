from __future__ import annotations

import argparse
from pathlib import Path

from resume_tailor.config import LLMSettings
from resume_tailor.export.html_renderer import GermanDeltaHtmlRenderer
from resume_tailor.export.pdf_exporter import export_html_to_pdf
from resume_tailor.language import detect_jd_language
from resume_tailor.llm.factory import build_llm_client
from resume_tailor.models import Education, Experience, Language, ResumeData
from resume_tailor.parsing.delta_resume_parser import parse_delta_resume, preview_resume
from resume_tailor.parsing.html_resume_parser import parse_html_resume
from resume_tailor.rewriting.diff import build_resume_diff, write_diff_files
from resume_tailor.rewriting.llm_optimizer import optimize_with_optional_llm
from resume_tailor.rewriting.rule_based_optimizer import optimize_resume_for_jd
from resume_tailor.scoring.german_scorer import GermanScorer
from resume_tailor.scoring.semantic_scorer import score_with_optional_llm
from resume_tailor.writers.report_writer import write_match_report


def build_sample_resume() -> ResumeData:
    return ResumeData(
        first_name="Max",
        last_name="Mustermann",
        email="max.mustermann@example.com",
        phone="+49 170 0000000",
        address="Musterstr. 1, 10115 Berlin",
        profile=(
            "Softwareentwickler mit Erfahrung in Webanwendungen, API-Entwicklung "
            "und datengetriebenen internen Tools. Schwerpunkt auf Python, "
            "TypeScript, automatisierten Tests und klarer technischer "
            "Dokumentation in agilen Produktteams."
        ),
        skills=[
            "Python",
            "TypeScript",
            "FastAPI",
            "React",
            "PostgreSQL",
            "REST APIs",
            "Docker",
            "CI/CD",
            "Automatisierte Tests",
            "Technische Dokumentation",
        ],
        languages=[
            Language("Deutsch", "Fließend"),
            Language("Englisch", "Fließend"),
            Language("Spanisch", "Grundkenntnisse"),
        ],
        experiences=[
            Experience(
                title="Softwareentwickler",
                company="MusterTech GmbH",
                period="04/2022 - 12/2025",
                location="Berlin",
                bullets=[
                    "Entwicklung interner Webanwendungen mit Python, FastAPI und React.",
                    "Konzeption und Implementierung von REST APIs für Reporting- und Workflow-Tools.",
                    "Aufbau automatisierter Tests und CI/CD-Pipelines zur stabileren Auslieferung.",
                    "Abstimmung technischer Anforderungen mit Produktmanagement, Design und Fachbereichen.",
                ],
            ),
            Experience(
                title="Junior Softwareentwickler",
                company="Beispiel Software Solutions",
                period="07/2019 - 03/2022",
                location="Hamburg",
                bullets=[
                    "Umsetzung neuer Funktionen in einer SaaS-Anwendung für B2B-Kunden.",
                    "Optimierung von SQL-Abfragen und Datenmodellen für operative Dashboards.",
                    "Bearbeitung von Bugs, Code Reviews und technischer Dokumentation im Scrum-Team.",
                    "Unterstützung bei der Migration einzelner Services in containerisierte Umgebungen.",
                ],
            ),
            Experience(
                title="Werkstudent Softwareentwicklung",
                company="Demo Digital Lab",
                period="10/2017 - 06/2019",
                location="München",
                bullets=[
                    "Entwicklung kleiner Automatisierungsskripte für Datenaufbereitung und Reporting.",
                    "Pflege interner Dokumentation und Unterstützung des Entwicklungsteams bei Tests.",
                ],
            ),
        ],
        education=[
            Education(
                degree="M.Sc. Informatik",
                institution="Technische Universität Berlin",
                period="2017 - 2019",
                details="Schwerpunkt: Software Engineering und Datenbanken",
            ),
            Education(
                degree="B.Sc. Informatik",
                institution="Hochschule Musterstadt",
                period="2013 - 2017",
            ),
        ],
    )


def command_generate_sample(args: argparse.Namespace) -> None:
    from resume_tailor.export.german_delta_docx import GermanDeltaDocxRenderer

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    renderer = GermanDeltaDocxRenderer(template_docx=Path(args.template) if args.template else None)
    renderer.render(build_sample_resume(), out)
    print(f"Generated {out}")


def command_analyze(args: argparse.Namespace) -> None:
    parsed_resume = _load_resume_from_args(args)
    resume_text = "\n".join(parsed_resume.all_text_parts())
    jd_text = Path(args.jd).read_text(encoding="utf-8")
    result = GermanScorer().score(resume_text, jd_text)
    llm = build_llm_client(_llm_settings_from_args(args))
    dual = score_with_optional_llm(result, resume_text, jd_text, llm)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_match_report(result, out)
    print(f"Wrote {out}")
    print(f"Combined score: {dual.combined_score}/100")
    print(f"Rule score: {dual.rule_report.total_score}/100")
    if dual.semantic_report and dual.semantic_report.mode == "llm":
        print(f"LLM semantic score: {dual.semantic_report.score}/100")
    elif dual.semantic_report and dual.semantic_report.error:
        print(f"LLM semantic score unavailable: {dual.semantic_report.error}")
    else:
        print("LLM semantic score: disabled")


def command_tailor_sample(args: argparse.Namespace) -> None:
    out = Path(args.out)
    report_out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)

    jd_text = Path(args.jd).read_text(encoding="utf-8")
    resume = optimize_resume_for_jd(build_sample_resume(), jd_text)
    _render_resume_docx(resume, Path(args.template) if args.template else None, out)

    result = GermanScorer().score("\n".join(resume.all_text_parts()), jd_text)
    write_match_report(result, report_out)
    print(f"Generated {out}")
    print(f"Wrote {report_out}")


def command_parse(args: argparse.Namespace) -> None:
    resume = parse_delta_resume(Path(args.resume))
    print(preview_resume(resume))


def command_tailor(args: argparse.Namespace) -> None:
    out = Path(args.out)
    report_out = Path(args.report)
    diff_json = Path(args.diff_json)
    diff_md = Path(args.diff_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    diff_json.parent.mkdir(parents=True, exist_ok=True)
    diff_md.parent.mkdir(parents=True, exist_ok=True)

    jd_text = Path(args.jd).read_text(encoding="utf-8")
    settings = _llm_settings_from_args(args)
    llm = build_llm_client(settings)
    parsed_resume = parse_delta_resume(Path(args.resume))
    optimized = optimize_with_optional_llm(parsed_resume, jd_text, llm, detect_jd_language(jd_text))
    resume = optimized.resume
    _render_resume_docx(resume, Path(args.template) if args.template else None, out)
    diff = build_resume_diff(parsed_resume, resume)
    write_diff_files(diff, diff_json, diff_md)

    result = GermanScorer().score("\n".join(resume.all_text_parts()), jd_text)
    write_match_report(result, report_out)
    print(f"Generated {out}")
    print(f"Wrote {report_out}")
    print(f"Wrote {diff_json}")
    print(f"Wrote {diff_md}")
    print(f"Rewrite mode: {optimized.mode}")
    for note in optimized.notes:
        print(f"- {note}")


def command_tailor_html(args: argparse.Namespace) -> None:
    out = Path(args.out)
    report_out = Path(args.report)
    diff_json = Path(args.diff_json)
    diff_md = Path(args.diff_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    diff_json.parent.mkdir(parents=True, exist_ok=True)
    diff_md.parent.mkdir(parents=True, exist_ok=True)

    jd_text = Path(args.jd).read_text(encoding="utf-8")
    settings = _llm_settings_from_args(args)
    llm = build_llm_client(settings)
    parsed_resume = _load_resume_from_args(args)
    language = detect_jd_language(jd_text)
    optimized = optimize_with_optional_llm(parsed_resume, jd_text, llm, language)
    resume = optimized.resume
    GermanDeltaHtmlRenderer(template_docx=Path(args.template) if args.template else None, language=language).render(resume, out)
    diff = build_resume_diff(parsed_resume, resume)
    write_diff_files(diff, diff_json, diff_md)

    result = GermanScorer().score("\n".join(resume.all_text_parts()), jd_text)
    write_match_report(result, report_out)
    print(f"Generated {out}")
    print(f"Wrote {report_out}")
    print(f"Wrote {diff_json}")
    print(f"Wrote {diff_md}")
    print(f"Rewrite mode: {optimized.mode}")
    for note in optimized.notes:
        print(f"- {note}")


def command_export_html(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    resume = _load_resume_from_args(args)
    GermanDeltaHtmlRenderer(template_docx=Path(args.template) if args.template else None).render(resume, out)
    print(f"Generated {out}")


def command_export_pdf(args: argparse.Namespace) -> None:
    out = Path(args.out)
    export_html_to_pdf(Path(args.html), out)
    print(f"Generated {out}")


def _llm_settings_from_args(args: argparse.Namespace) -> LLMSettings:
    settings = LLMSettings.from_env()
    if getattr(args, "llm_provider", None):
        settings.provider = args.llm_provider
    if getattr(args, "model", None):
        settings.model = args.model
    return settings


def _load_resume_from_args(args: argparse.Namespace) -> ResumeData:
    html_path = getattr(args, "html", None)
    if html_path:
        return parse_html_resume(Path(html_path))
    if not getattr(args, "resume", None):
        raise ValueError("Please provide --html or --resume.")
    return parse_delta_resume(Path(args.resume))


def _render_resume_docx(resume: ResumeData, template: Path | None, out: Path) -> None:
    from resume_tailor.export.delta_template_patcher import DeltaTemplatePatcher
    from resume_tailor.export.german_delta_docx import GermanDeltaDocxRenderer

    if template and template.exists():
        DeltaTemplatePatcher(template).render(resume, out)
    else:
        GermanDeltaDocxRenderer(template_docx=template).render(resume, out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local German Lebenslauf tailor")
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("generate-sample", help="Generate a sample German DOCX using the Delta layout.")
    sample.add_argument("--template", help="Existing Delta template DOCX, used to reuse the photo.", default=None)
    sample.add_argument("--out", default="outputs/sample_lebenslauf.docx")
    sample.set_defaults(func=command_generate_sample)

    analyze = sub.add_parser("analyze", help="Score a resume against a pasted JD text file.")
    analyze.add_argument("--resume", required=False)
    analyze.add_argument("--html", default=None)
    analyze.add_argument("--jd", required=True)
    analyze.add_argument("--out", default="outputs/match_report.md")
    analyze.add_argument("--llm-provider", choices=["off", "openai", "deepseek", "ollama"], default=None)
    analyze.add_argument("--model", default=None)
    analyze.set_defaults(func=command_analyze)

    tailor = sub.add_parser("tailor-sample", help="Tailor the built-in sample resume to a JD and render DOCX.")
    tailor.add_argument("--jd", required=True)
    tailor.add_argument("--template", help="Existing Delta template DOCX, used to reuse the photo.", default=None)
    tailor.add_argument("--out", default="outputs/tailored_lebenslauf.docx")
    tailor.add_argument("--report", default="outputs/tailored_match_report.md")
    tailor.set_defaults(func=command_tailor_sample)

    parse = sub.add_parser("parse", help="Parse a Delta Lebenslauf DOCX and print structured preview.")
    parse.add_argument("--resume", required=True)
    parse.set_defaults(func=command_parse)

    tailor_real = sub.add_parser("tailor", help="Tailor a parsed Delta resume to a JD and render DOCX.")
    tailor_real.add_argument("--resume", required=True)
    tailor_real.add_argument("--jd", required=True)
    tailor_real.add_argument("--template", help="Existing Delta template DOCX, used to reuse the photo.", default=None)
    tailor_real.add_argument("--out", default="outputs/tailored_lebenslauf.docx")
    tailor_real.add_argument("--report", default="outputs/tailored_match_report.md")
    tailor_real.add_argument("--diff-json", default="outputs/rewrite_diff.json")
    tailor_real.add_argument("--diff-md", default="outputs/rewrite_diff.md")
    tailor_real.add_argument("--llm-provider", choices=["off", "openai", "deepseek", "ollama"], default=None)
    tailor_real.add_argument("--model", default=None)
    tailor_real.set_defaults(func=command_tailor)

    tailor_html = sub.add_parser("tailor-html", help="Tailor a parsed Delta resume to a JD and render HTML/CSS.")
    tailor_html.add_argument("--resume", required=False)
    tailor_html.add_argument("--html", default=None)
    tailor_html.add_argument("--jd", required=True)
    tailor_html.add_argument("--template", help="Existing Delta template DOCX, used to reuse the photo.", default=None)
    tailor_html.add_argument("--out", default="outputs/tailored_lebenslauf.html")
    tailor_html.add_argument("--report", default="outputs/tailored_match_report.md")
    tailor_html.add_argument("--diff-json", default="outputs/rewrite_diff.json")
    tailor_html.add_argument("--diff-md", default="outputs/rewrite_diff.md")
    tailor_html.add_argument("--llm-provider", choices=["off", "openai", "deepseek", "ollama"], default=None)
    tailor_html.add_argument("--model", default=None)
    tailor_html.set_defaults(func=command_tailor_html)

    html_export = sub.add_parser("export-html", help="Export a parsed Delta resume to the HTML/CSS template.")
    html_export.add_argument("--resume", required=False)
    html_export.add_argument("--html", default=None)
    html_export.add_argument("--template", default=None)
    html_export.add_argument("--out", default="outputs/tailored_lebenslauf.html")
    html_export.set_defaults(func=command_export_html)

    pdf_export = sub.add_parser("export-pdf", help="Export an HTML resume to PDF.")
    pdf_export.add_argument("--html", default="outputs/tailored_lebenslauf.html")
    pdf_export.add_argument("--out", default="outputs/tailored_lebenslauf.pdf")
    pdf_export.set_defaults(func=command_export_pdf)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
