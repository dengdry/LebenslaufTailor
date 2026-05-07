# Resume Tailor Local

[English](README.md) | [Deutsch](README.de.md) | [中文](README.zh.md)

Resume Tailor Local ist ein datenschutzbewusstes Desktop-Tool zur Anpassung von Lebensläufen an Stellenanzeigen. Es liest einen Lebenslauf, bewertet ihn gegen eine eingefügte Stellenbeschreibung, kann ihn optional mit einem LLM umformulieren und exportiert einen angepassten HTML-Lebenslauf sowie ein PDF.

Der aktuelle Schwerpunkt liegt auf deutschen und europäischen Lebensläufen. Die Anwendung kann die Ausgabesprache je nach Sprache der Stellenbeschreibung zwischen Deutsch und Englisch wechseln.

## Funktionen

- Liest `.docx`-Lebensläufe, einschließlich normaler Absätze und Word-Textfelder.
- Liest HTML-Lebensläufe, die mit diesem Tool erzeugt wurden, und nutzt sie als zukünftigen Master Resume.
- Erstellt nach dem Einfügen einer Stellenbeschreibung einen Matching-Bericht.
- Kombiniert regelbasierte Bewertung mit optionaler semantischer LLM-Bewertung.
- Unterstützt OpenAI, DeepSeek, Ollama oder einen rein lokalen Regelmodus ohne LLM.
- Formuliert Kurzprofil, Fähigkeiten und Erfahrungs-Bullets passend zur Stellenbeschreibung um.
- Nutzt einfache Fakten-Schutzregeln, um unbelegte Aussagen wie erfundene Projekte, Kunden, Zertifikate oder Jobtitel zu vermeiden.
- Erstellt deutsche oder englische Lebensläufe abhängig von der Sprache der Stellenbeschreibung.
- Exportiert HTML/CSS und erzeugt PDFs über lokal installiertes Microsoft Edge oder Google Chrome.
- Bietet in der GUI Vergleich, manuelle Bearbeitung, HTML-Vorschau und PDF-Export.
- Speichert LLM-Antworten im Cache, um bei wiederholten Tests Token zu sparen.

## Voraussetzungen

- Windows 10/11
- Python 3.11 oder neuer
- Microsoft Edge oder Google Chrome für den HTML-zu-PDF-Export
- Optional: OpenAI- oder DeepSeek-API-Key oder lokales Ollama

Abhängigkeiten installieren:

```bash
python -m pip install -r requirements.txt
```

GUI starten:

```bash
python gui.py
```

Unter Windows kann auch diese Datei per Doppelklick gestartet werden:

```bat
start_gui.bat
```

`start_gui.bat` erstellt automatisch eine lokale `.venv` und installiert die Abhängigkeiten. `.venv/` wird von Git ignoriert.

## Schnellstart

1. Kopiere `resume_templates/mustermann_resume_template.html` und ersetze die fiktiven Inhalte durch den eigenen Lebenslauf.
2. Wähle die bearbeitete HTML-Datei bei `Resume HTML` aus.
3. Füge die Stellenbeschreibung in das JD-Textfeld ein.
4. Wähle einen LLM-Anbieter: `off`, `openai`, `deepseek` oder `ollama`.
5. Klicke auf `1. Analyze`, um Matching-Scores zu erzeugen.
6. Klicke auf `2. Generate Resume`, um einen angepassten HTML-Lebenslauf zu erstellen.
7. Klicke auf `3. Review & Edit`, um das Ergebnis zu prüfen und manuell anzupassen.
8. Klicke auf `4. Preview`, um das HTML zu öffnen.
9. Klicke auf `5. Export PDF`, um die finale Bewerbungsdatei zu erstellen.

Die GUI enthält aktuell chinesische Labels, da das Projekt ursprünglich als lokaler persönlicher Workflow entstanden ist. Internationalisierung ist als Verbesserung geplant.

## Erste Nutzung Ohne Eigenen Lebenslauf

Öffne die ausgefüllte Beispielvorlage:

```text
resume_templates/mustermann_resume_template.html
```

Kopiere sie, ersetze die fiktiven Max-Mustermann-Inhalte durch eigene Angaben und nutze die bearbeitete HTML-Datei anschließend in der App als `Resume HTML`.

## HTML Als Master Resume

Empfohlener Workflow:

```text
ausgefüllter HTML-Lebenslauf -> neue JD -> angepasstes HTML/PDF
```

Die GUI ist bewusst HTML-first. DOCX-Parsing bleibt in der CLI erhalten, aber der Desktop-Workflow ist auf editierbare HTML-Vorlagen ausgerichtet.

## LLM-Einstellungen

Wenn ein API-Key in der GUI eingetragen und gespeichert wird, landet die Konfiguration hier:

```text
.config/settings.json
```

`.config/` wird von Git ignoriert.

Alternativ kann die App über Umgebungsvariablen konfiguriert werden:

```bash
RESUME_TAILOR_LLM=deepseek
RESUME_TAILOR_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=your_api_key
```

```bash
RESUME_TAILOR_LLM=openai
RESUME_TAILOR_MODEL=gpt-5.2
OPENAI_API_KEY=your_api_key
```

```bash
RESUME_TAILOR_LLM=ollama
RESUME_TAILOR_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

## LLM-Cache

Die App speichert LLM-Antworten im Cache, um wiederholte Testkosten zu reduzieren.

- Cache-Verzeichnis: `.cache/llm/`
- Cache-Schlüssel: Anbieter, Modellname, System-Prompt und User-Prompt
- Lösche `.cache/llm/`, um einen neuen LLM-Aufruf zu erzwingen

`.cache/` wird von Git ignoriert.

## CLI-Beispiele

```bash
python app.py analyze --resume "path/to/resume.docx" --jd jd.txt --out outputs/match_report.md
python app.py analyze --html outputs/tailored_lebenslauf.html --jd jd.txt --out outputs/match_report.md
python app.py tailor-html --resume "path/to/resume.docx" --jd jd.txt --template "path/to/template.docx" --out outputs/tailored_lebenslauf.html
python app.py export-pdf --html outputs/tailored_lebenslauf.html --out outputs/tailored_lebenslauf.pdf
```

## Projektstruktur

```text
.
├── app.py                         # CLI-Einstiegspunkt
├── gui.py                         # Tkinter-GUI
├── resume_tailor/
│   ├── export/                    # HTML/PDF/DOCX-Export
│   ├── llm/                       # OpenAI-, DeepSeek- und Ollama-Clients
│   ├── parsing/                   # DOCX-/HTML-Parsing
│   ├── rewriting/                 # regelbasierte und LLM-Umformulierung
│   ├── scoring/                   # Matching-Bewertung
│   └── writers/                   # Berichtsausgabe
├── templates/                     # Renderer-Vorlagen
├── resume_templates/              # ausgefüllte Vorschauvorlagen
├── examples/                      # anonymer Beispiel-Lebenslauf und Beispiel-JD
├── requirements.txt
└── start_gui.bat
```

## Datenschutz

Dies ist ein lokales Tool. Lebensläufe, Stellenbeschreibungen und erzeugte Dateien werden standardmäßig auf dem eigenen Rechner gespeichert.

Wenn OpenAI oder DeepSeek aktiviert ist, sendet die App die Stellenbeschreibung und den strukturierten Lebenslauf an den ausgewählten API-Anbieter. Wenn Datenschutz besonders wichtig ist, nutze den `off`-Modus, lokales Ollama, anonymisierte Testdaten und regelmäßiges Löschen von `.config/`, `.cache/` und `outputs/`.

## Lizenz

MIT License. Siehe [LICENSE](LICENSE).
