"""Per-session conversation state (handoff.md §2.11).

This is the bot's short-term memory. Without it, every message would be
treated as if it were the very first thing the user ever said — so "give me
an example" right after asking about a term would mean nothing, because the
bot wouldn't remember what term was just discussed. This object is what
gets passed back and forth between turns to fix that.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationState:
    """One user's ongoing conversation with the bot.

    A fresh instance should be created per session/user — this is not
    meant to be shared across different conversations.
    """

    # Set once at the start of a session (see paco_chatbot.py) so every
    # reply can address the user by name, making the conversation feel
    # personal rather than like talking to an anonymous lookup tool.
    user_name: str | None = None

    # Also set once at the start of a session, right after user_name — lets
    # category-browsing (list_terms/list_risks) surface easier (Basic)
    # terms before denser (Technical) ones for someone new to insurance
    # vocabulary, without changing anything else about how the bot talks.
    is_newcomer: bool = False

    # The last term the bot talked about. Lets a follow-up like "give me an
    # example" work without the user having to repeat the term name.
    last_term_id: str | None = None

    # The last intent the bot recognized (e.g. "ask_definition"). Useful for
    # deciding how to interpret a short, ambiguous follow-up message.
    last_intent: str | None = None

    # If the fuzzy matcher came back with a few close-but-not-certain
    # guesses, they get parked here while the bot asks the user "did you
    # mean X or Y?" — and get resolved (or cleared) on the next message.
    pending_disambiguation: list[str] = field(default_factory=list)

    # Quiz mode is a genuine "mode" rather than a per-message intent: once
    # `quiz_term_id` is set, the dispatcher treats *every* incoming message
    # as an answer attempt (or a request to stop) instead of running normal
    # intent recognition, until the user ends the quiz. `quiz_domain` scopes
    # question-picking to one category for the whole session (None = any
    # term); `quiz_asked_ids` avoids repeating a question within one quiz.
    quiz_term_id: str | None = None
    quiz_domain: str | None = None
    quiz_score: int = 0
    quiz_total: int = 0
    quiz_asked_ids: set[str] = field(default_factory=set)
