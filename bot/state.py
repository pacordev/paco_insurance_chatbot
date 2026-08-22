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
