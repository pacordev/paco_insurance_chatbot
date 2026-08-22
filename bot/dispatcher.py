"""Wires entity matching -> intent routing -> state -> responses into one
turn (handoff.md §5 step 7).

If bot/nlu.py, bot/intents.py, bot/state.py, and bot/responses.py are the
separate ingredients, this is where they actually get combined into a
finished reply for the user on every message.
"""

from __future__ import annotations

from bot.data import TermStore
from bot.nlu import EntityMatcher
from bot.state import ConversationState


class Dispatcher:
    """The bot's main "brain loop" for a single conversation turn."""

    def __init__(self, store: TermStore):
        # Everything needed to answer a question gets set up once here, so
        # process_turn() below can stay cheap and just reuse it per message.
        self.store = store
        self.matcher = EntityMatcher(store)

    def process_turn(self, text: str, state: ConversationState) -> tuple[str, ConversationState]:
        """Handle one user message and return (reply text, updated state).

        TODO (build step 7): recognize_intent(text) -> resolve entities via
        self.matcher, using state.last_term_id for follow-ups when none are
        found in this turn -> render() the response -> update state.
        """
        raise NotImplementedError
