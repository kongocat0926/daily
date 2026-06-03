from __future__ import annotations

import os
from typing import Any, Dict, List


class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.api_key = os.getenv(self.config.get("api_key_env", "LLM_API_KEY"), "")
        self.base_url = os.getenv(self.config.get("base_url_env", "LLM_BASE_URL"), "")
        self.model = os.getenv(self.config.get("model_env", "LLM_MODEL"), "qwen-plus")
        self.temperature = float(self.config.get("temperature", 0.2))

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def chat(self, messages: List[Dict[str, str]]) -> str:
        if not self.available:
            raise RuntimeError("LLM env is not configured: LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        completion = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
        )
        return completion.choices[0].message.content or ""
