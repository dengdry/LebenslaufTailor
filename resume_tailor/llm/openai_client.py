from __future__ import annotations

import json
import urllib.error
import urllib.request


class OpenAIResponsesClient:
    def __init__(self, api_key: str, model: str = "gpt-5.2", base_url: str = "https://api.openai.com/v1") -> None:
        if not api_key:
            raise ValueError("使用 OpenAI 时需要填写 API 密钥。")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_prompt,
        }
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI 请求失败: {exc.code} {detail}") from exc

        if data.get("output_text"):
            return data["output_text"]
        chunks: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
        return "\n".join(chunks).strip()
