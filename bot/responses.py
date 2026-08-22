"""Response templates (handoff.md §2.11 point 4).

This is where the bot's "voice" lives — turning a (term, intent) pair into
an actual sentence to show the user. Kept separate from the dispatch logic
so that wording can be tweaked or expanded later without touching how the
bot decides what to say, only how it phrases it.
"""

from __future__ import annotations

import random

from bot.data import Term
from bot.intents import Intent

# A few phrasings per intent so the bot doesn't answer with the exact same
# fill-in-the-blank sentence every single time. Picked at random rather than
# round-robin through ConversationState — round-robin would need render()
# to take the conversation state just to remember which template it used
# last, which felt like the wrong module to carry that. Random keeps
# render() a plain, stateless function: same inputs, no memory needed.
_DEFINITION_TEMPLATES = [
    "{term}: {definition}",
    "Here's the definition of {term}: {definition}",
    "{term} — {definition}",
]

_EXAMPLE_TEMPLATES = [
    "Here's an example: {example}",
    "For example: {example}",
    "Sure — here's {term} used in context: {example}",
]

_COMPARE_TEMPLATES = [
    "{term}: {definition}\n{other_term}: {other_definition}",
    "Here's how they compare:\n- {term}: {definition}\n- {other_term}: {other_definition}",
]

_LIST_CATEGORIES_TEMPLATES = [
    "Here are the categories I know about: {categories}.",
    "You can browse by any of these categories: {categories}.",
]

_GREET_TEMPLATES = [
    "Hi! Ask me about any insurance term and I'll explain it.",
    "Hello! I'm here to help with insurance terminology — what would you like to know?",
    "Hey there! Curious about a term? Just ask.",
]

_HELP_TEMPLATES = [
    "You can ask me to define a term, give an example, list categories, or compare two terms — "
    "try \"what is a deductible?\" or \"compare ACV and replacement cost\".",
    "I can explain insurance terms, show you an example sentence, list categories, or compare two "
    "terms side by side. Just ask naturally, typos and all.",
]

_GOODBYE_TEMPLATES = [
    "Goodbye! Come back anytime you run into a term you don't know.",
    "See you later — happy learning!",
    "Bye! Ping me whenever another insurance term trips you up.",
]

_FALLBACK_TEMPLATES = [
    "I'm not sure what you're asking — could you rephrase that, or name a specific insurance term?",
    "I didn't quite catch that. Try asking about a specific term, like \"what is a deductible?\"",
]

_FALLBACK_DISAMBIGUATION_TEMPLATE = "I'm not sure which term you meant — did you mean {candidates}?"


def render(intent: Intent, term: Term | None = None, **kwargs) -> str:
    """Turn an intent (plus whatever data it needs) into a reply string.

    Most intents only need `term`. A couple need more, passed as keyword
    arguments so this function's signature doesn't have to grow a pile of
    mostly-unused parameters:
    - COMPARE_TERMS needs `other_term` (a second Term) alongside `term`.
    - LIST_CATEGORIES needs `categories` (a list of category name strings).
    - FALLBACK optionally takes `candidates` (a list of term-name strings) —
      when the fuzzy matcher found a few close-but-uncertain guesses, this
      is what turns that into a real "did you mean X or Y?" question
      instead of a flat "I don't understand."
    """
    if intent is Intent.ASK_DEFINITION:
        return random.choice(_DEFINITION_TEMPLATES).format(term=term.term, definition=term.definition)

    if intent is Intent.ASK_EXAMPLE:
        # Every term ships with exactly one example today (handoff.md
        # §2.5), so the variety here comes from the wrapper sentence, not
        # from picking among several examples. Falling back to the
        # definition would be wrong (that's a different intent's job), so
        # if a term somehow had no example we'd rather say so plainly.
        if not term.examples:
            return f"I don't have an example sentence for {term.term} yet."
        return random.choice(_EXAMPLE_TEMPLATES).format(term=term.term, example=term.examples[0])

    if intent is Intent.COMPARE_TERMS:
        # Deliberately kept as two separate, self-contained sentences rather
        # than stitched into one ("X is <definition of Y>...") — a random
        # sample of insurance_terms.json showed definitions are phrased
        # inconsistently (some are noun phrases, some start mid-sentence
        # like "refers to..."), so grammatically splicing one into a larger
        # sentence would read broken for a chunk of the glossary.
        other_term: Term = kwargs["other_term"]
        return random.choice(_COMPARE_TEMPLATES).format(
            term=term.term,
            definition=term.definition,
            other_term=other_term.term,
            other_definition=other_term.definition,
        )

    if intent is Intent.LIST_CATEGORIES:
        categories: list[str] = kwargs.get("categories", [])
        return random.choice(_LIST_CATEGORIES_TEMPLATES).format(categories=", ".join(sorted(categories)))

    if intent is Intent.GREET:
        return random.choice(_GREET_TEMPLATES)

    if intent is Intent.HELP:
        return random.choice(_HELP_TEMPLATES)

    if intent is Intent.GOODBYE:
        return random.choice(_GOODBYE_TEMPLATES)

    if intent is Intent.FALLBACK:
        candidates: list[str] | None = kwargs.get("candidates")
        if candidates:
            return _FALLBACK_DISAMBIGUATION_TEMPLATE.format(candidates=" or ".join(candidates))
        return random.choice(_FALLBACK_TEMPLATES)

    raise ValueError(f"No response template wired up for intent: {intent}")
