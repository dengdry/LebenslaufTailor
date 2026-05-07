# Security Policy

## Sensitive Data

This application processes resumes and job descriptions, which can contain highly sensitive personal data.

Do not commit:

- real resumes;
- real job descriptions;
- API keys;
- `.config/`;
- `.cache/`;
- `outputs/`.

## LLM Providers

When OpenAI or DeepSeek is enabled, the application sends the structured resume and JD text to the selected provider.

Use `off` mode or a local Ollama model if the data must stay on the local machine.

## Reporting Issues

Please avoid including private resume content in public GitHub issues. Use anonymized examples whenever possible.
