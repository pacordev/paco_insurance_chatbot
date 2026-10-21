"""Tiny client for talking to a local Ollama server.

This is the only file that knows Ollama exists. Everything else just calls
`generate()` and, if anything goes wrong, catches `LLMError` and falls back
to the normal template reply. The bot should never break because the LLM
did.
"""

from __future__ import annotations

import httpx

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"

# Short connect timeout so a dead/missing server fails fast, long read
# timeout because the very first call has to load the model into memory
# and that can take a while.
CONNECT_TIMEOUT = 2.0
READ_TIMEOUT = 60.0


class LLMError(Exception):
    """Anything that went wrong talking to Ollama (down, slow, bad reply)."""


class OllamaClient:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        model: str = DEFAULT_MODEL,
        connect_timeout: float = CONNECT_TIMEOUT,
        read_timeout: float = READ_TIMEOUT,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        # httpx lets us set each timeout separately, which is the whole point here.
        self._timeout = httpx.Timeout(read_timeout, connect=connect_timeout)

    def is_available(self) -> bool:
        """Quick "is the server up and does it have our model?" check.

        Meant to be run once at startup so we can decide to run without
        the LLM instead of timing out on every single message.
        """
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=httpx.Timeout(2.0))
            resp.raise_for_status()
            names = {m.get("name") for m in resp.json().get("models", [])}
        except (httpx.HTTPError, ValueError):
            return False
        return self.model in names

    def generate(self, system: str, prompt: str) -> str:
        """Send one prompt and return the full reply text (no streaming)."""
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            # low temperature = stick to the glossary, don't get creative
            "options": {"temperature": 0.2},
        }
        try:
            resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self._timeout)
            resp.raise_for_status()
            text = resp.json().get("response", "")
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError covers a reply that isn't valid JSON
            raise LLMError(f"Ollama request failed: {exc}") from exc

        text = text.strip()
        if not text:
            raise LLMError("Ollama returned an empty reply")
        return text
