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

# What to call the user if, for whatever reason, no name made it through
# (e.g. they just hit enter at the "what's your name?" prompt). Keeps every
# template grammatically fine without a special no-name branch everywhere.
_DEFAULT_NAME = "there"

# A good handful of phrasings per intent so the bot doesn't answer with the
# exact same fill-in-the-blank sentence every single time — a first pass at
# 2-3 templates each still felt repetitive in practice (the same "Here's the
# definition of X" wrapper kept showing up), so these lists are longer, and
# the name's position moves around too (opening address, closing aside, a
# mid-message check-in) rather than sitting in the same spot every time.
# Picked at random rather than round-robin through ConversationState —
# round-robin would need render() to take the conversation state just to
# remember which template it used last, which felt like the wrong module to
# carry that. Random keeps render() a plain, stateless function: same
# inputs, no memory needed.
#
# Every template includes {name} — the user asked for the bot to always
# address them by name, to make the conversation feel personal rather than
# like talking to an anonymous lookup tool.
# Two of these ("Hope that helps" / "does that clear it up") continue the
# sentence right after {definition} with no line break — since ~98% of
# definitions already end with their own period, they use
# {definition_clean} instead (definition with any trailing period
# stripped) to avoid a doubled "..". Every other template either ends the
# message at {definition} (its own period is correct there) or puts the
# continuation on a new line, so they're unaffected and use {definition} as-is.
_DEFINITION_TEMPLATES = [
    "{name}, {term}: {definition}",
    "{term} — {definition_clean}. Hope that helps, {name}.",
    "Good question, {name}. {term}: {definition}",
    "Here's what you're after, {name} — {term}: {definition}",
    "{term}: {definition}\n\nLet me know if you want an example, {name}.",
    "Straight to it, {name}: {term} — {definition}",
    "{term}: {definition_clean} — does that clear it up, {name}?",
    "Sure thing, {name}. {term}: {definition}",
]

# A handful of definitions run several times the glossary's usual length
# (bot/data.py's LONG_DEFINITION_THRESHOLD) -- these show a trimmed version
# first instead, with a nudge toward asking for the rest, rather than
# dumping a dense multi-sentence passage into the reply every time. Every
# variant mentions "full definition" so the follow-up phrasing the
# dispatcher listens for reads naturally as a response to the bot's own
# wording.
_LONG_DEFINITION_TEMPLATES = [
    "{name}, {term} has a longer definition, so here's the short version: {short_definition} Want the full definition?",
    "{term}, in brief, {name}: {short_definition} That's the short version — say the word if you want the full definition.",
    "Good question, {name}. {term}, briefly: {short_definition} Ask for the full definition if you want the rest.",
    "{term}: {short_definition} (That's the short version, {name} — just ask for the full definition to see the whole thing.)",
]

_EXAMPLE_TEMPLATES = [
    "Here's an example for you, {name}: {example}",
    "For example, {name}: {example}",
    "Sure, {name} — here's {term} used in context: {example}",
    "{example}\n\nThat's {term} in action, {name}.",
    "Picture this, {name}: {example}",
    "Good timing, {name} — here's how {term} plays out: {example}",
    "{example}\n\nMakes more sense with a real scenario, right, {name}?",
    "Here you go, {name}: {example}",
]

_COMPARE_TEMPLATES = [
    "{name}, here it is:\n{term}: {definition}\n{other_term}: {other_definition}",
    "Here's how they compare, {name}:\n- {term}: {definition}\n- {other_term}: {other_definition}",
    "Good comparison, {name}. Side by side:\n{term}: {definition}\n{other_term}: {other_definition}",
    "{term}: {definition}\n{other_term}: {other_definition}\n\nHope that clears up the difference, {name}.",
    "Let's break it down, {name}:\n{term} — {definition}\n{other_term} — {other_definition}",
    "Here's the difference, {name}:\n{term}: {definition}\n{other_term}: {other_definition}",
]

_LIST_CATEGORIES_TEMPLATES = [
    "Here are the categories I know about, {name}: {categories}.",
    "{name}, you can browse by any of these categories: {categories}.",
    "Good place to start, {name} — here's what's available: {categories}.",
    "Plenty to explore, {name}: {categories}.",
    "Here's the full list, {name}: {categories}.",
    "{categories}\n\nPick one and I'll walk you through it, {name}.",
]

# Two variants depending on whether the list actually got capped — "here
# are 12 of them" reads oddly when all 12 are shown, so a category small
# enough to show in full gets its own, simpler phrasing instead of
# pretending there's more hiding behind it.
_LIST_TERMS_TRUNCATED_TEMPLATES = [
    "{name}, there are {total} terms under {domain} — here are {shown} of them: {terms}. Ask about any one for the full definition.",
    "{domain} has {total} terms on file, {name}. A few to start with: {terms}.",
    "Good place to browse, {name} — {domain} covers {total} terms. Here are {shown}: {terms}.",
    "{name}, {domain} has quite a few — {total} in total. Here's a sample: {terms}.",
    "There's a lot under {domain}, {name} ({total} terms) — starting with: {terms}.",
]

_LIST_TERMS_FULL_TEMPLATES = [
    "{name}, there are {total} terms under {domain}: {terms}.",
    "{domain} has {total} terms, {name}: {terms}.",
    "Here's everything under {domain}, {name} — all {total}: {terms}.",
    "{total} terms under {domain}, {name}: {terms}.",
]

_LIST_RISKS_TEMPLATES = [
    "{name}, here are the risks I know about under {domain}: {risks}.",
    "Under {domain}, the common risks are: {risks}. Want details on any of them, {name}?",
    "Good question, {name} — {domain} typically covers these risks: {risks}.",
    "{domain} risks I have on file, {name}: {risks}.",
    "Here's what falls under {domain}, {name}: {risks}.",
]

# Used when the message doesn't name a line of business the bot actually has
# risk data for (e.g. just "what are the risks?" with no domain, or a domain
# that has no risk-type entries yet) — lists what's actually available rather
# than a flat "I don't understand", since that list is cheap to compute and
# saves a guessing round-trip.
_LIST_RISKS_CLARIFY_TEMPLATES = [
    "Which line of business, {name}? I have risk info for: {available}.",
    "{name}, I can list risks for any of these: {available}. Which one?",
    "Happy to, {name} — just let me know which one: {available}.",
]

_GREET_TEMPLATES = [
    "Hi {name}! Ask me about any insurance term and I'll explain it.",
    "Hello {name}! I'm here to help with insurance terminology — what would you like to know?",
    "Hey {name}! Curious about a term? Just ask.",
    "Good to see you, {name}! What insurance term is on your mind?",
    "Hey there, {name} — ready when you are.",
    "Welcome back, {name}! What can I help you look up?",
    "Hi {name}, what would you like to learn about today?",
]

_HELP_TEMPLATES = [
    "{name}, you can ask me to define a term, give an example, list categories, or compare two "
    "terms — try \"what is a deductible?\" or \"compare ACV and replacement cost\".",
    "I can explain insurance terms, show you an example sentence, list categories, or compare two "
    "terms side by side, {name}. Just ask naturally, typos and all.",
    "Good question, {name} — here's what I can do: define terms, give examples, list categories, "
    "or compare two terms.",
    "A few things I'm good for, {name}: definitions, examples, category browsing, and comparisons. "
    "Ask away.",
    "{name}, think of me as a glossary you can talk to — ask for a definition, an example, or a "
    "comparison.",
]

_GOODBYE_TEMPLATES = [
    "Goodbye, {name}! Come back anytime you run into a term you don't know.",
    "See you later, {name} — happy learning!",
    "Bye, {name}! Ping me whenever another insurance term trips you up.",
    "Take care, {name} — glad I could help.",
    "Catch you next time, {name}!",
    "Thanks for stopping by, {name} — good luck out there.",
    "Until next time, {name}! Keep those terms straight.",
    "Bye for now, {name} — this glossary isn't going anywhere.",
]

_FALLBACK_TEMPLATES = [
    "I'm not sure what you're asking, {name} — could you rephrase that, or name a specific insurance term?",
    "I didn't quite catch that, {name}. Try asking about a specific term, like \"what is a deductible?\"",
    "Hmm, not sure I follow, {name} — mind trying that a different way?",
    "{name}, I don't think I've got that one. Ask me about a specific term and I'll do my best.",
    "That one's got me stumped, {name} — could you be more specific?",
]

_FALLBACK_DISAMBIGUATION_TEMPLATES = [
    "I'm not sure which term you meant, {name} — did you mean {candidates}?",
    "A couple of options match that, {name}: {candidates}. Which one?",
    "{name}, did you mean {candidates}?",
]

# Same random-choice-from-a-list approach as every other intent above, just
# for the one-time session opener instead of a per-message reply — kept
# roughly the same length and shape across all ten so the experience feels
# consistent regardless of which one gets picked, while the example query
# and phrasing still vary session to session.
#
# Every variant also mentions Basic terms as a place to start (difficulty-
# aware onboarding) — newcomer-agnostic wording rather than a conditional
# branch, since it reads fine whether or not the session is actually a
# newcomer, the same way the 'quit' hint is shown to everyone regardless of
# whether they'll need it. The word "Basic" appears in every variant so a
# test can assert on it as a stable anchor.
_WELCOME_TEMPLATES = [
    "Welcome, {name}! I'm here to help you learn insurance terminology — ask me about any term "
    "and I'll explain it, give you an example, or compare it against another one. Try something "
    "like \"what is a deductible?\" or \"compare ACV and replacement cost\". New to this? Ask to "
    "\"list Basic terms\" in a category to start with the easier ones. Type 'quit' anytime "
    "to leave. Let's get started, {name}!",

    "Hey {name}! Think of me as your insurance glossary — ask about any term and I'll explain it, "
    "show you an example, or compare it to another one. Try \"what's a premium?\" or \"compare "
    "deductible and coinsurance\". If insurance is new to you, ask me to show the Basic terms in a "
    "category first. Type 'quit' whenever you want to leave. Ready when you are, {name}!",

    "Hi there, {name}! I'm here to help with insurance vocabulary — definitions, examples, and "
    "side-by-side comparisons, all on request. Try something like \"what is liability?\" or "
    "\"compare ACV and replacement cost\". Just starting out? \"Show me Basic Auto terms\" is a "
    "good first question. Type 'quit' to exit anytime. Let's dive in, {name}!",

    "Glad you're here, {name}! I can explain any insurance term, give you an example sentence, or "
    "compare two terms for you. Try \"what's a deductible?\" or \"compare premium and coinsurance\". "
    "New to insurance? Ask for the Basic terms in a category before the denser, Technical ones. "
    "Type 'quit' whenever you're done. Go ahead and ask me anything, {name}!",

    "Welcome aboard, {name}! Stuck on insurance jargon? Ask me for a definition, an example, or a "
    "comparison between two terms. Try \"what is subrogation?\" or \"compare loss ratio and combined "
    "ratio\". If you're just getting started, the Basic terms in a category are the easiest place "
    "to begin. Type 'quit' to leave whenever. Let's get you up to speed, {name}!",

    "Hey there, {name}! I'm your go-to for insurance terminology — definitions, examples, "
    "comparisons, just ask. Try \"what's coinsurance?\" or \"compare ACV and replacement cost\". "
    "New to the field? Try \"list Basic Health terms\" to ease in. Type 'quit' anytime to step "
    "away. Fire away, {name}!",

    "Hi {name}, welcome! Whenever an insurance term trips you up, just ask — I'll define it, give "
    "you an example, or compare it to something else. Try \"what is a premium?\" or \"compare "
    "deductible and premium\". First time around? Ask to browse the Basic terms in a category "
    "before the Technical ones. Type 'quit' to leave when you're ready. What would you like to "
    "know, {name}?",

    "Good to have you, {name}! I can walk you through insurance terms — definitions, real examples, "
    "and comparisons between two terms. Try \"what's liability?\" or \"compare ACV and replacement "
    "cost\". New here? Start with the Basic terms in whichever category interests you. Type 'quit' "
    "anytime to wrap up. Take it away, {name}!",

    "Hello, {name}! Consider me your insurance dictionary that talks back — ask for a definition, "
    "an example, or a comparison. Try \"what is reinsurance?\" or \"compare premium and coinsurance\". "
    "Brand new to this? Ask for the Basic terms in a category first, the Technical ones can wait. "
    "Type 'quit' whenever you'd like to stop. Let's get started, {name}!",

    "Welcome, {name}! New insurance term got you stuck? Ask me to define it, show an example, or "
    "compare it with another. Try \"what's a deductible?\" or \"compare loss ratio and combined "
    "ratio\". Still finding your footing? Ask to see the Basic terms in a category before the "
    "denser ones. Type 'quit' any time to leave. Over to you, {name}!",
]


def render(intent: Intent, term: Term | None = None, *, name: str | None = None, **kwargs) -> str:
    """Turn an intent (plus whatever data it needs) into a reply string.

    `name` is the user's name, threaded through from ConversationState by
    the dispatcher — every template uses it, so it's a real parameter here
    rather than just another entry in **kwargs. Falls back to a generic
    `_DEFAULT_NAME` if none was captured, so a reply never reads like
    "Hi !" with a missing word.

    Most intents only need `term` beyond that. A couple need more, passed as
    keyword arguments so this function's signature doesn't have to grow a
    pile of mostly-unused parameters:
    - COMPARE_TERMS needs `other_term` (a second Term) alongside `term`.
    - LIST_CATEGORIES needs `categories` (a list of category name strings).
    - LIST_RISKS needs either (`domain`, `risk_terms`) when a line of
      business was recognized and has risk-type entries, or
      `available_domains` when it wasn't/didn't, to ask which one instead.
    - LIST_TERMS needs `domain`, `term_names` (already capped to what's being
      shown), and `total_count` (the real count before capping, so a huge
      category doesn't just silently show a truncated list with no hint
      there's more).
    - FALLBACK optionally takes `candidates` (a list of term-name strings) —
      when the fuzzy matcher found a few close-but-uncertain guesses, this
      is what turns that into a real "did you mean X or Y?" question
      instead of a flat "I don't understand."
    - ASK_DEFINITION optionally takes `full=True` to force the complete
      definition even for a term whose definition normally gets trimmed —
      this is what the dispatcher passes when the user actually asks for
      the full definition after seeing the short version.
    """
    name = name or _DEFAULT_NAME

    if intent is Intent.ASK_DEFINITION:
        if term.is_long_definition and not kwargs.get("full"):
            return random.choice(_LONG_DEFINITION_TEMPLATES).format(
                term=term.term, short_definition=term.short_definition, name=name
            )
        return random.choice(_DEFINITION_TEMPLATES).format(
            term=term.term,
            definition=term.definition,
            definition_clean=term.definition.rstrip("."),
            name=name,
        )

    if intent is Intent.ASK_EXAMPLE:
        # Every term ships with 5 example sentences (handoff.md §2.24) —
        # picking one at random, not always the first, is what makes "give
        # me another example" actually show something different each time
        # instead of repeating the same sentence with a reworded wrapper.
        # Falling back to the definition would be wrong (that's a different
        # intent's job), so if a term somehow had no example we'd rather say
        # so plainly.
        if not term.examples:
            return f"I don't have an example sentence for {term.term} yet, {name}."
        return random.choice(_EXAMPLE_TEMPLATES).format(
            term=term.term, example=random.choice(term.examples), name=name
        )

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
            name=name,
        )

    if intent is Intent.LIST_CATEGORIES:
        categories: list[str] = kwargs.get("categories", [])
        return random.choice(_LIST_CATEGORIES_TEMPLATES).format(categories=", ".join(sorted(categories)), name=name)

    if intent is Intent.LIST_TERMS:
        domain: str = kwargs["domain"]
        term_names: list[str] = kwargs["term_names"]
        total: int = kwargs["total_count"]
        templates = _LIST_TERMS_FULL_TEMPLATES if len(term_names) >= total else _LIST_TERMS_TRUNCATED_TEMPLATES
        return random.choice(templates).format(
            domain=domain, total=total, shown=len(term_names), terms=", ".join(term_names), name=name
        )

    if intent is Intent.LIST_RISKS:
        domain: str | None = kwargs.get("domain")
        risk_terms: list[str] = kwargs.get("risk_terms") or []
        if domain and risk_terms:
            # Order is the dispatcher's call, not this function's — same
            # convention as LIST_TERMS's term_names below. Re-sorting here
            # would silently discard the difficulty-aware ordering a
            # newcomer session asked for.
            return random.choice(_LIST_RISKS_TEMPLATES).format(
                domain=domain, risks=", ".join(risk_terms), name=name
            )
        available: list[str] = kwargs.get("available_domains") or []
        return random.choice(_LIST_RISKS_CLARIFY_TEMPLATES).format(
            available=", ".join(sorted(available)), name=name
        )

    if intent is Intent.GREET:
        return random.choice(_GREET_TEMPLATES).format(name=name)

    if intent is Intent.HELP:
        return random.choice(_HELP_TEMPLATES).format(name=name)

    if intent is Intent.GOODBYE:
        return random.choice(_GOODBYE_TEMPLATES).format(name=name)

    if intent is Intent.FALLBACK:
        candidates: list[str] | None = kwargs.get("candidates")
        if candidates:
            return random.choice(_FALLBACK_DISAMBIGUATION_TEMPLATES).format(
                candidates=" or ".join(candidates), name=name
            )
        return random.choice(_FALLBACK_TEMPLATES).format(name=name)

    raise ValueError(f"No response template wired up for intent: {intent}")


# Quiz mode is its own little state machine (bot/dispatcher.py), not a
# per-message intent, so — like render_welcome() below — these live as
# their own functions rather than going through render()'s intent dispatch.
# Every quiz message ends with the next question already attached (start
# and feedback alike), so playing feels like one continuous back-and-forth
# rather than a question, an answer, a pause, then another question.
def _format_quiz_question(term: Term) -> str:
    return f"Here's a definition: {term.definition}\n\nWhat term is this? (say \"stop quiz\" to end)"


_QUIZ_START_TEMPLATES = [
    "Let's do it, {name}! I'll give you a definition — you guess the term.\n\n{question}",
    "Quiz time, {name}! Read the definition and tell me the term.\n\n{question}",
    "Alright, {name}, let's test your knowledge.\n\n{question}",
]

_QUIZ_CORRECT_TEMPLATES = [
    "That's right, {name}! It was {term}. Score: {score}/{total}.\n\n{question}",
    "Nice, {name} — {term} it is. Score: {score}/{total}.\n\n{question}",
    "Correct, {name} — {term}! Score: {score}/{total}.\n\n{question}",
]

_QUIZ_INCORRECT_TEMPLATES = [
    "Not quite, {name} — it was {term}. Score: {score}/{total}.\n\n{question}",
    "Close, but no — the answer was {term}, {name}. Score: {score}/{total}.\n\n{question}",
    "Not this time, {name}. It was {term}. Score: {score}/{total}.\n\n{question}",
]

_QUIZ_END_TEMPLATES = [
    "Nice round, {name}! You got {score} out of {total}. Come back anytime for another one.",
    "That's a wrap, {name} — {score}/{total}. Good practice!",
    "Ending the quiz there, {name}. Final score: {score}/{total}.",
]


def render_quiz_start(name: str | None, term: Term) -> str:
    """The message shown when a quiz begins — intro plus the first question."""
    return random.choice(_QUIZ_START_TEMPLATES).format(
        name=name or _DEFAULT_NAME, question=_format_quiz_question(term)
    )


def render_quiz_feedback(
    name: str | None, correct: bool, correct_term: Term, score: int, total: int, next_term: Term
) -> str:
    """Feedback on the just-answered question, with the next one already
    attached — a quiz reads as one continuous flow, not stop-and-go.
    """
    templates = _QUIZ_CORRECT_TEMPLATES if correct else _QUIZ_INCORRECT_TEMPLATES
    return random.choice(templates).format(
        name=name or _DEFAULT_NAME,
        term=correct_term.term,
        score=score,
        total=total,
        question=_format_quiz_question(next_term),
    )


def render_quiz_end(name: str | None, score: int, total: int) -> str:
    """The summary shown when the user stops a quiz in progress."""
    return random.choice(_QUIZ_END_TEMPLATES).format(name=name or _DEFAULT_NAME, score=score, total=total)


def render_welcome(name: str | None) -> str:
    """The one-time greeting shown at the start of a session, right after
    asking for the user's name — separate from Intent.GREET, which handles
    a plain "hi" appearing mid-conversation instead.
    """
    return random.choice(_WELCOME_TEMPLATES).format(name=name or _DEFAULT_NAME)
