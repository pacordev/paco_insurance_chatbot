"""Wires entity matching -> intent routing -> state -> responses into one
turn (handoff.md §5 step 7).

If bot/nlu.py, bot/intents.py, bot/state.py, and bot/responses.py are the
separate ingredients, this is where they actually get combined into a
finished reply for the user on every message.
"""

from __future__ import annotations

from bot.data import Term, TermStore
from bot.intents import Intent, recognize_intent
from bot.nlu import EntityMatch, EntityMatcher
from bot.responses import render
from bot.state import ConversationState

# When the bot asked "did you mean X or Y?" and the user answers with a
# position ("the first one") instead of repeating the term name, this is
# how that gets mapped back to one of the candidates that were offered.
_ORDINAL_WORDS = {
    "1": 0, "one": 0, "first": 0,
    "2": 1, "two": 1, "second": 1,
    "3": 2, "three": 2, "third": 2,
}


class Dispatcher:
    """The bot's main "brain loop" for a single conversation turn."""

    def __init__(self, store: TermStore):
        # Everything needed to answer a question gets set up once here, so
        # process_turn() below can stay cheap and just reuse it per message.
        self.store = store
        self.matcher = EntityMatcher(store)

    def process_turn(self, text: str, state: ConversationState) -> tuple[str, ConversationState]:
        """Handle one user message and return (reply text, updated state)."""
        intent = recognize_intent(text)

        # Conversational scaffolding never needs a term, so it's handled
        # before we bother asking the entity matcher anything.
        if intent in (Intent.GREET, Intent.HELP, Intent.GOODBYE):
            return self._respond(render(intent), intent, state)

        if intent is Intent.LIST_CATEGORIES:
            categories = list(self.store.categories.keys())
            return self._respond(render(intent, categories=categories), intent, state)

        matches = self.matcher.extract(text)

        # If we were mid-way through a "did you mean X or Y?" question,
        # check whether this reply answers it *before* trusting whatever the
        # entity matcher found on its own. This has to take priority over
        # `matches`, not just fill in when `matches` is empty — a short
        # reply like "the first one" is exactly the kind of generic phrase
        # the fuzzy matcher can accidentally latch onto (it found real
        # candidate terms for that phrase in testing, unrelated to the
        # question being answered), which would otherwise silently win.
        if state.pending_disambiguation:
            chosen_id = self._resolve_pending_choice(text, state.pending_disambiguation)
            if chosen_id:
                matches = [EntityMatch(chosen_id, text, exact=True, score=100.0)]

        if intent is Intent.COMPARE_TERMS:
            return self._handle_compare(matches, state)

        return self._handle_single_term_intent(intent, matches, state)

    def _handle_single_term_intent(
        self, intent: Intent, matches: list[EntityMatch], state: ConversationState
    ) -> tuple[str, ConversationState]:
        """Covers ASK_DEFINITION, ASK_EXAMPLE, and FALLBACK — anything that
        ultimately boils down to "figure out one term, then answer about it."
        """
        term = self._resolve_primary_term(matches)

        if term is None and intent in (Intent.ASK_DEFINITION, Intent.ASK_EXAMPLE) and state.last_term_id:
            # "Give me an example" right after asking about a term shouldn't
            # require repeating the term's name — this is what makes that
            # kind of follow-up work. Restricted to real content intents on
            # purpose: a message that recognize_intent() couldn't classify
            # at all (FALLBACK) shouldn't silently latch onto whatever was
            # discussed a moment ago, since it might just be unrelated noise.
            term = self.store.get(state.last_term_id)

        if term is None:
            if self._is_ambiguous(matches):
                candidate_ids = [m.term_id for m in matches]
                names = [self.store.get(tid).term for tid in candidate_ids]
                state.last_intent = intent
                state.pending_disambiguation = candidate_ids
                return render(Intent.FALLBACK, candidates=names), state
            return self._respond(render(Intent.FALLBACK), Intent.FALLBACK, state)

        # A bare term with no question wrapped around it comes back from
        # recognize_intent() as FALLBACK on purpose (see bot/intents.py) —
        # this is the promotion that docstring describes: since we *did*
        # manage to resolve a term, default to treating it as a definition
        # request, which is this bot's core, most common use case.
        effective_intent = Intent.ASK_DEFINITION if intent is Intent.FALLBACK else intent
        reply = render(effective_intent, term=term)
        return self._respond(reply, effective_intent, state, term_id=term.id)

    def _handle_compare(self, matches: list[EntityMatch], state: ConversationState) -> tuple[str, ConversationState]:
        term_ids = self._unique_term_ids(matches)

        # "How's that different from replacement cost?" only names one term
        # explicitly — "that" refers to whatever was just being discussed.
        if len(term_ids) == 1 and state.last_term_id and state.last_term_id != term_ids[0]:
            term_ids = [state.last_term_id, term_ids[0]]

        if len(term_ids) < 2:
            # Not enough to compare. This reuses the generic fallback
            # wording rather than a dedicated "I need two terms" message —
            # good enough for now, worth a nicer message later if it turns
            # out to come up a lot in practice.
            return self._respond(render(Intent.FALLBACK), Intent.COMPARE_TERMS, state)

        term_a = self.store.get(term_ids[0])
        term_b = self.store.get(term_ids[1])
        reply = render(Intent.COMPARE_TERMS, term=term_a, other_term=term_b)
        return self._respond(reply, Intent.COMPARE_TERMS, state, term_id=term_b.id)

    def _resolve_primary_term(self, matches: list[EntityMatch]) -> Term | None:
        """Pick the term to answer about, when there's a single clear answer.

        An exact match always wins outright, since it's unambiguous by
        definition. A single fuzzy guess is treated as good enough too —
        asking "did you mean X?" when X is the only candidate is just a more
        annoying way of saying the same thing. Multiple fuzzy candidates are
        genuinely ambiguous, and left for the caller to handle instead (see
        _is_ambiguous below).
        """
        if not matches:
            return None
        if matches[0].exact or len(matches) == 1:
            return self.store.get(matches[0].term_id)
        return None

    def _is_ambiguous(self, matches: list[EntityMatch]) -> bool:
        return len(matches) > 1 and not matches[0].exact

    def _unique_term_ids(self, matches: list[EntityMatch]) -> list[str]:
        seen: list[str] = []
        for m in matches:
            if m.term_id not in seen:
                seen.append(m.term_id)
        return seen

    def _resolve_pending_choice(self, text: str, candidate_ids: list[str]) -> str | None:
        """Match a short reply like "the first one" or "2" back to one of
        the candidate term ids offered in the last "did you mean...?"
        question.
        """
        words = text.strip().lower().split()
        for word, index in _ORDINAL_WORDS.items():
            if word in words and index < len(candidate_ids):
                return candidate_ids[index]
        return None

    def _respond(
        self, reply: str, intent: Intent, state: ConversationState, term_id: str | None = None
    ) -> tuple[str, ConversationState]:
        """Every normal return path funnels through here so the state
        updates happen in exactly one place, instead of being repeated (and
        potentially forgotten) at each return statement above.
        """
        state.last_intent = intent
        if term_id is not None:
            state.last_term_id = term_id
        state.pending_disambiguation = []
        return reply, state
