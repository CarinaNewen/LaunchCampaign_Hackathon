from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from app.core.config import settings


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    raw: dict[str, Any]


class LLMService:
    """
    Pluggable LLM adapter. Prefers Gemini when enabled, falls back to Ollama,
    falls back to deterministic stub when both are disabled.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        use_chat: bool | None = None,
        enabled: bool | None = None,
    ) -> None:
        # Gemini
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        self.gemini_enabled = settings.gemini_enabled and bool(settings.gemini_api_key)

        # Ollama
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds
        self.use_chat = settings.ollama_use_chat if use_chat is None else use_chat
        self.enabled = settings.ollama_enabled if enabled is None else enabled

    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_retries: int = 2,
    ) -> LLMResult:
        """Call the active LLM backend with exponential-backoff retry.

        Retry schedule: 0.4 s, 0.8 s before giving up and raising.
        The disabled stub never retries — it always succeeds immediately.
        """
        if not self.gemini_enabled and not self.enabled:
            return LLMResult(text=prompt, provider="disabled", model=self.model, raw={})

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                if self.gemini_enabled:
                    return self._gemini_chat(prompt=prompt)
                if self.use_chat:
                    return self._chat(prompt=prompt, system_prompt=system_prompt)
                return self._generate(prompt=prompt)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    time.sleep(0.4 * (2 ** attempt))  # 0.4 s → 0.8 s
        raise last_exc  # type: ignore[misc]

    def health(self) -> dict[str, Any]:
        if self.gemini_enabled:
            return {
                "ok": True,
                "provider": "gemini",
                "model": self.gemini_model,
            }
        if not self.enabled:
            return {"ok": False, "reason": "llm disabled", "base_url": self.base_url, "model": self.model}
        url = f"{self.base_url}/api/version"
        try:
            payload = self._post_json(url, {})
            return {"ok": True, "provider": "ollama", "base_url": self.base_url, "model": self.model, "version": payload}
        except Exception as exc:
            return {
                "ok": False,
                "provider": "ollama",
                "base_url": self.base_url,
                "model": self.model,
                "error": str(exc),
            }

    # ── Gemini ──────────────────────────────────────────────────────────────

    def _gemini_chat(self, prompt: str) -> LLMResult:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.9,
                "maxOutputTokens": 512,
            },
        }
        try:
            response = self._post_json(url, payload)
            text = (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            return LLMResult(text=text, provider="gemini", model=self.gemini_model, raw=response)
        except HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini HTTP error {exc.code}: {response_text}") from exc
        except URLError as exc:
            raise RuntimeError(f"Cannot connect to Gemini API: {exc.reason}") from exc

    # ── Ollama ───────────────────────────────────────────────────────────────

    def _generate(self, prompt: str) -> LLMResult:
        url = f"{self.base_url}/api/generate"
        payload = self._post_json(
            url,
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            },
        )
        return LLMResult(
            text=str(payload.get("response", "")).strip(),
            provider="ollama",
            model=self.model,
            raw=payload,
        )

    def _chat(self, prompt: str, system_prompt: str | None = None) -> LLMResult:
        url = f"{self.base_url}/api/chat"
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = self._post_json(
            url,
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
            },
        )
        content = payload.get("message", {}).get("content", "")
        return LLMResult(
            text=str(content).strip(),
            provider="ollama",
            model=self.model,
            raw=payload,
        )

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = response.read().decode("utf-8")
                if not response_data:
                    return {}
                return json.loads(response_data)
        except HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP error {exc.code}: {response_text}") from exc
        except URLError as exc:
            raise RuntimeError(f"URL error: {exc.reason}") from exc
