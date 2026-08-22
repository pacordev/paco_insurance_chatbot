"""Intent set and recognition (handoff.md §2.9, §5 step 4).

Where bot/nlu.py answers "which term did they mention?", this file answers
the other half of the question: "what do they actually want done with it?" —
a definition, an example, a comparison, or something else entirely.

The list below is deliberately narrow and stays that way on purpose: this
bot is a glossary for coworkers to learn vocabulary, not a customer-service
bot. There's intentionally no "check my claim status" or "look up my policy"
style intent, because this bot has no account/PII access and was never meant
to grow in that direction.
"""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    ASK_DEFINITION = "ask_definition"      # "what does X mean?"
    ASK_EXAMPLE = "ask_example"            # "can you use X in a sentence?"
    LIST_CATEGORIES = "list_categories"    # "what topics/categories exist?"
    LIST_RISKS = "list_risks"              # "what risks does life insurance cover?"
    LIST_TERMS = "list_terms"              # "show me the terms under Auto insurance"
    START_QUIZ = "start_quiz"              # "quiz me" / "test me on Auto terms"
    COMPARE_TERMS = "compare_terms"        # "what's the difference between X and Y?"
    GREET = "greet"                        # "hi" / "hello"
    HELP = "help"                          # "what can you do?"
    GOODBYE = "goodbye"                    # "bye" / "thanks, that's all"
    FALLBACK = "fallback"                  # couldn't confidently tell what they want


# Recognition is plain keyword/pattern matching, checked in priority order —
# no machine learning here, same rule-based spirit as the enrichment script
# that built the glossary itself (see handoff.md §2.2). Order matters: a
# message is classified as the *first* intent in this list whose patterns
# match, so more specific things (compare, example, categories) are checked
# before the catch-all "ask_definition" patterns, and short conversational
# messages (greet/help/goodbye) are checked first of all since they're the
# easiest to get right and the most likely to get swallowed by a looser
# pattern further down otherwise.
#
# GREET, GOODBYE, and the bare "help" case use `^...$`-anchored patterns —
# they're meant to catch a message that basically *is* that pleasantry, not
# just contains the word somewhere inside a longer, unrelated question.
_INTENT_PATTERNS: list[tuple[Intent, list[re.Pattern]]] = [
    (
        Intent.GOODBYE,
        [
            re.compile(r"^(bye+|goodbye|good\s?bye|see\s?y(a|ou)( later)?|later|quit|exit)[\s!.,]*$", re.I),
            re.compile(r"\bthat'?s all\b", re.I),
            re.compile(r"\bthat is all\b", re.I),
            re.compile(r"\bi'?m done\b", re.I),
            re.compile(r"\bno more questions?\b", re.I),
        ],
    ),
    (
        Intent.GREET,
        [
            re.compile(
                r"^(hi+|hello+|hey+|hiya|yo|sup|good\s(morning|afternoon|evening))"
                r"(\s+(there|everyone|team|folks))?[\s!.,]*$",
                re.I,
            ),
        ],
    ),
    (
        Intent.HELP,
        [
            re.compile(r"^help[\s!.,?]*$", re.I),
            re.compile(
                r"\b(what can you do|how (do|does) (this|it|the bot) work|how (do i|to) use (you|this)|list (of )?commands)\b",
                re.I,
            ),
        ],
    ),
    (
        # Checked before ASK_DEFINITION/ASK_EXAMPLE since "what's the
        # difference between X and Y" would otherwise get caught by the much
        # broader "what's" pattern below.
        Intent.COMPARE_TERMS,
        [
            re.compile(r"\bdifference(s)? between\b", re.I),
            re.compile(r"\bdiffer(s)? from\b", re.I),
            re.compile(r"\bdifferent (from|than)\b", re.I),
            re.compile(r"\bcompar(e|ing|ison)\b", re.I),
            re.compile(r"(^|\s)vs\.?(\s|$)", re.I),
            re.compile(r"\bversus\b", re.I),
        ],
    ),
    (
        # Checked before ASK_DEFINITION for the same reason — "give me an
        # example of X" shouldn't fall through to the definition catch-all.
        Intent.ASK_EXAMPLE,
        [
            re.compile(r"\bexamples?\b", re.I),
            re.compile(r"\bin a sentence\b", re.I),
            re.compile(r"\bfor instance\b", re.I),
            re.compile(r"\bused? in context\b", re.I),
        ],
    ),
    (
        Intent.LIST_CATEGORIES,
        [
            re.compile(r"\bcategor(y|ies)\b", re.I),
            re.compile(r"\btopics\b", re.I),
            re.compile(r"\b(kinds|types) of insurance\b", re.I),
        ],
    ),
    (
        # Checked before ASK_DEFINITION for the same reason as compare/example
        # above — "what are the risks under life insurance" contains "what",
        # which the broad ASK_DEFINITION catch-all would otherwise claim
        # first. Deliberately matches plural "risks" only, not singular
        # "risk" — "what is risk" is almost certainly asking for the
        # definition of the general concept, not a list, and singular vs.
        # plural is a cheap, reliable enough signal to tell those apart.
        Intent.LIST_RISKS,
        [
            re.compile(r"\brisks\b.*\bunder\b", re.I),
            re.compile(r"\brisks\b.*\bcover(s|ed)?\b", re.I),
            re.compile(r"\bwhat('?s| is| are)\b.*\brisks\b", re.I),
            re.compile(r"\blist (the )?risks\b", re.I),
            re.compile(r"\bcommon risks\b", re.I),
            re.compile(r"\brisks (in|for|of)\b", re.I),
        ],
    ),
    (
        # Checked before ASK_DEFINITION for the same reason as LIST_RISKS
        # above, and requires plural "terms" for the same reason that one
        # requires plural "risks" — "define this term" (singular) should
        # stay a normal definition request, not a browsing one.
        Intent.LIST_TERMS,
        [
            re.compile(r"\bshow me\b.*\bterms\b", re.I),
            re.compile(r"\blist\b.*\bterms\b", re.I),
            re.compile(r"\bbrowse\b.*\bterms\b", re.I),
            re.compile(r"\bterms\b.*\bunder\b", re.I),
            re.compile(r"\bwhat terms\b", re.I),
            re.compile(r"\ball\b.*\bterms\b.*\b(under|in|for)\b", re.I),
        ],
    ),
    (
        # Only recognizes the *start* of a quiz — once one is running, the
        # dispatcher intercepts every message as an answer attempt before
        # recognize_intent() is even called (see bot/dispatcher.py), so
        # these patterns only ever need to fire from a cold start.
        Intent.START_QUIZ,
        [
            re.compile(r"\bquiz me\b", re.I),
            re.compile(r"\b(start|begin)\b.*\bquiz\b", re.I),
            re.compile(r"\blet'?s do a quiz\b", re.I),
            re.compile(r"\btest me\b", re.I),
            re.compile(r"\bquiz mode\b", re.I),
        ],
    ),
    (
        # The broad catch-all for "explain this term to me" style phrasing.
        # Deliberately last among the "real" intents so nothing above gets
        # accidentally swallowed by how common these words are.
        Intent.ASK_DEFINITION,
        [
            re.compile(r"\bwhat'?s\b", re.I),
            re.compile(r"\bwhat is\b", re.I),
            re.compile(r"\bwhats\b", re.I),
            re.compile(r"\bdefin(e|ition)\b", re.I),
            re.compile(r"\bmeaning of\b", re.I),
            re.compile(r"\bwhat does .* mean\b", re.I),
            re.compile(r"\bexplain\b", re.I),
            re.compile(r"\bdescribe\b", re.I),
            re.compile(r"\bunderstand\b", re.I),
        ],
    ),
]


def recognize_intent(text: str) -> Intent:
    """Look at one user message and decide which Intent it represents.

    This only looks at *phrasing* — it has no idea whether the message
    actually mentions a real glossary term or not (that's bot/nlu.py's job).
    So a bare, unadorned term with no question wrapped around it (someone
    just typing "ACV" instead of "what is ACV") won't match any pattern here
    and comes back as FALLBACK. That's intentional, not a gap: the dispatcher
    (bot/dispatcher.py, still to be built) is the piece that has both the
    intent *and* the entity-match result at the same time, so it's the right
    place to decide "we got FALLBACK here, but we did recognize a term, so
    let's just treat this as ASK_DEFINITION" — recognize_intent() itself
    stays a simple, honest function of the text alone.
    """
    text = text.strip()
    if not text:
        return Intent.FALLBACK

    for intent, patterns in _INTENT_PATTERNS:
        if any(pattern.search(text) for pattern in patterns):
            return intent

    return Intent.FALLBACK
