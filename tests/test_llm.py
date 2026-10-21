"""Tests for bot/llm.py. No real Ollama needed, httpx is faked."""

import httpx
import pytest

from bot import llm
from bot.llm import LLMError, OllamaClient


class FakeResponse:
    """Just enough of httpx.Response for the client to work with."""

    def __init__(self, data=None, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


def test_generate_returns_stripped_text(monkeypatch):
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: FakeResponse({"response": "  hello  "}))
    assert OllamaClient().generate("sys", "hi") == "hello"


def test_generate_sends_model_and_no_streaming(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen.update(url=url, json=json)
        return FakeResponse({"response": "ok"})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    OllamaClient(host="http://box:1234/", model="m").generate("sys", "hi")
    assert seen["url"] == "http://box:1234/api/generate"
    assert seen["json"]["model"] == "m"
    assert seen["json"]["stream"] is False


def test_connection_error_becomes_llmerror(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(llm.httpx, "post", boom)
    with pytest.raises(LLMError):
        OllamaClient().generate("sys", "hi")


def test_timeout_becomes_llmerror(monkeypatch):
    def slow(*a, **k):
        raise httpx.ReadTimeout("too slow")

    monkeypatch.setattr(llm.httpx, "post", slow)
    with pytest.raises(LLMError):
        OllamaClient().generate("sys", "hi")


def test_empty_reply_becomes_llmerror(monkeypatch):
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: FakeResponse({"response": "   "}))
    with pytest.raises(LLMError):
        OllamaClient().generate("sys", "hi")


def test_is_available_true_when_model_listed(monkeypatch):
    monkeypatch.setattr(
        llm.httpx, "get", lambda *a, **k: FakeResponse({"models": [{"name": "qwen2.5-coder:7b"}]})
    )
    assert OllamaClient().is_available() is True


def test_is_available_false_when_model_missing(monkeypatch):
    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: FakeResponse({"models": []}))
    assert OllamaClient().is_available() is False


def test_is_available_false_when_server_down(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(llm.httpx, "get", boom)
    assert OllamaClient().is_available() is False
