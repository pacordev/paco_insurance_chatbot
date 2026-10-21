"""Tests for bot/rag.py, using the real glossary."""

import pytest

from bot.data import TermStore
from bot.rag import build_context, build_prompt, mentions_terms


@pytest.fixture(scope="module")
def store() -> TermStore:
    return TermStore.load()


@pytest.fixture(scope="module")
def term(store):
    return store.all_terms()[0]


def test_context_has_term_and_definition(term):
    ctx = build_context([term])
    assert term.term in ctx
    assert term.definition.strip() in ctx


def test_prompt_only_contains_given_terms(store):
    # the prompt should hold the matched terms and nothing else from the glossary
    a, b, c = store.all_terms()[:3]
    prompt = build_prompt("what is it?", [a], "Paco", False)
    assert a.definition.strip() in prompt
    assert b.definition.strip() not in prompt
    assert c.definition.strip() not in prompt


def test_prompt_includes_name_question_and_newcomer_tone(term):
    prompt = build_prompt("what is it?", [term], "Paco", True)
    assert "Paco" in prompt
    assert "what is it?" in prompt
    assert "new to insurance" in prompt


def test_mentions_terms_true_and_false(term):
    assert mentions_terms(f"Sure, {term.term} means something.", [term])
    assert not mentions_terms("Totally unrelated pizza talk.", [term])
