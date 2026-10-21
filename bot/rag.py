"""Builds the prompt for the LLM out of glossary terms.

The glossary JSON stays the only source of truth. The model never answers
from its own memory, it just gets the matched terms pasted into the prompt
and rewrites them in a friendlier way.
"""

from __future__ import annotations

import re

from bot.data import Term

SYSTEM_PROMPT = """\
You are Paco, a friendly insurance glossary helper for coworkers who have no insurance background.

Rules:
- Answer ONLY using the glossary entries in the context block. Never use outside knowledge.
- If the context doesn't cover what was asked, say "I don't have that term" and stop.
- Use plain, everyday language. Short sentences. No jargon unless you explain it.
- Keep it under 120 words.
- Don't mention "context" or "glossary entries" in your answer, just answer naturally.
"""


def build_context(terms: list[Term]) -> str:
    """One block per term: name, definition, examples, related, category."""
    blocks = []
    for term in terms:
        lines = [f"Term: {term.term}", f"Definition: {term.definition.strip()}"]
        if term.examples:
            lines.append("Examples: " + " | ".join(term.examples))
        if term.related:
            lines.append("Related terms: " + ", ".join(r.term for r in term.related))
        if term.categories:
            lines.append("Category: " + ", ".join(term.categories))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_prompt(question: str, terms: list[Term], user_name: str | None, is_newcomer: bool) -> str:
    """The user-side prompt: who's asking, the glossary context, the question."""
    who = user_name or "the user"
    level = (
        "They are new to insurance, so keep it extra simple."
        if is_newcomer
        else "They know a bit of insurance already, so you can be a little more direct."
    )
    return (
        f"You are talking to {who}. {level}\n\n"
        f"--- GLOSSARY CONTEXT ---\n{build_context(terms)}\n--- END CONTEXT ---\n\n"
        f"Question: {question}"
    )


def mentions_terms(reply: str, terms: list[Term]) -> bool:
    """Drift check: does the reply mention at least one of the matched terms
    (or one of its synonyms)? If not, the model probably wandered off.
    """
    lowered = reply.lower()
    for term in terms:
        for name in [term.term, *term.synonyms]:
            if name and re.search(rf"\b{re.escape(name.lower())}\b", lowered):
                return True
    return False
