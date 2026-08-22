"""Wires entity matching -> intent routing -> state -> responses into one
turn (handoff.md §5 step 7).

If bot/nlu.py, bot/intents.py, bot/state.py, and bot/responses.py are the
separate ingredients, this is where they actually get combined into a
finished reply for the user on every message.
"""

from __future__ import annotations

import re

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

# For LIST_RISKS and LIST_TERMS: maps how someone would naturally phrase a
# line of business ("life insurance") onto the category name it's actually
# stored under ("Life"). Categories themselves (lowercased) are also checked
# directly, so this only needs to cover phrasings that *don't* already match
# a category name verbatim.
_DOMAIN_ALIASES = {
    "life insurance": "Life",
    "auto insurance": "Auto",
    "car insurance": "Auto",
    "health insurance": "Health",
    "home insurance": "Property",
    "property insurance": "Property",
    "homeowners insurance": "Property",
    "marine insurance": "Marine & Aviation",
    "aviation insurance": "Marine & Aviation",
    "marine and aviation": "Marine & Aviation",
    "liability insurance": "Liability",
    "financial lines": "Financial Lines & Surety",
    "financial lines and surety": "Financial Lines & Surety",
    "workers compensation": "Workers Compensation",
    "workers comp": "Workers Compensation",
}

# LIST_TERMS caps how many term names get listed in one reply — some
# categories (General Insurance Concepts, in particular) run into the
# hundreds, and dumping all of them into one message would be unreadable.
# The total count is always shown alongside the capped list, so it's never
# silently misleading about how much more there is.
_LIST_TERMS_CAP = 10


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
            return self._respond(self._render(intent, state), intent, state)

        if intent is Intent.LIST_CATEGORIES:
            categories = list(self.store.categories.keys())
            return self._respond(self._render(intent, state, categories=categories), intent, state)

        if intent is Intent.LIST_RISKS:
            # Like LIST_CATEGORIES, this never needs a specific *term* — it
            # needs a *domain* (a line of business), resolved from the raw
            # text directly rather than through the entity matcher, which
            # only knows about glossary terms, not category names.
            return self._handle_list_risks(text, state)

        if intent is Intent.LIST_TERMS:
            return self._handle_list_terms(text, state)

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
                return self._render(Intent.FALLBACK, state, candidates=names), state
            return self._respond(self._render(Intent.FALLBACK, state), Intent.FALLBACK, state)

        # A bare term with no question wrapped around it comes back from
        # recognize_intent() as FALLBACK on purpose (see bot/intents.py) —
        # this is the promotion that docstring describes: since we *did*
        # manage to resolve a term, default to treating it as a definition
        # request, which is this bot's core, most common use case.
        effective_intent = Intent.ASK_DEFINITION if intent is Intent.FALLBACK else intent
        reply = self._render(effective_intent, state, term=term)
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
            return self._respond(self._render(Intent.FALLBACK, state), Intent.COMPARE_TERMS, state)

        term_a = self.store.get(term_ids[0])
        term_b = self.store.get(term_ids[1])
        reply = self._render(Intent.COMPARE_TERMS, state, term=term_a, other_term=term_b)
        return self._respond(reply, Intent.COMPARE_TERMS, state, term_id=term_b.id)

    def _handle_list_risks(self, text: str, state: ConversationState) -> tuple[str, ConversationState]:
        domain = self._resolve_domain(text)
        if domain:
            risk_terms = self.store.by_categories(domain, "Risk")
            if risk_terms:
                names = [t.term for t in risk_terms]
                reply = self._render(Intent.LIST_RISKS, state, domain=domain, risk_terms=names)
                return self._respond(reply, Intent.LIST_RISKS, state)

        # Either no domain was recognized at all ("what are the risks?" on
        # its own), or it was but there's no risk-type data for it yet —
        # either way, list what's actually available rather than a flat
        # "I don't understand," since that's cheap to compute and saves a
        # guessing round-trip.
        available = sorted(
            c for c in self.store.categories if c != "Risk" and self.store.by_categories(c, "Risk")
        )
        reply = self._render(Intent.LIST_RISKS, state, available_domains=available)
        return self._respond(reply, Intent.LIST_RISKS, state)

    def _handle_list_terms(self, text: str, state: ConversationState) -> tuple[str, ConversationState]:
        domain = self._resolve_domain(text)
        terms = sorted(self.store.by_category(domain), key=lambda t: t.term) if domain else []
        if not terms:
            # No domain recognized, or (shouldn't normally happen, since
            # domain always comes from a real category) it had nothing in
            # it — either way, this is exactly what LIST_CATEGORIES already
            # answers, so reuse it rather than inventing a near-duplicate
            # "pick a category" prompt.
            categories = list(self.store.categories.keys())
            reply = self._render(Intent.LIST_CATEGORIES, state, categories=categories)
            return self._respond(reply, Intent.LIST_TERMS, state)

        shown = [t.term for t in terms[:_LIST_TERMS_CAP]]
        reply = self._render(Intent.LIST_TERMS, state, domain=domain, term_names=shown, total_count=len(terms))
        return self._respond(reply, Intent.LIST_TERMS, state)

    def _resolve_domain(self, text: str) -> str | None:
        """Find a line-of-business category name mentioned in free text —
        e.g. "life insurance" or bare "Life" both resolve to the "Life"
        category. Prefers the longest match when more than one could apply,
        same principle as the entity matcher preferring the longest term
        (bot/nlu.py) — "life insurance" beating a coincidentally-contained
        shorter alias would be the wrong kind of match here too.
        """
        lowered = text.lower()
        candidates: list[tuple[int, str]] = []
        for alias, canonical in _DOMAIN_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                candidates.append((len(alias), canonical))
        for canonical in self.store.categories:
            if re.search(rf"\b{re.escape(canonical.lower())}\b", lowered):
                candidates.append((len(canonical), canonical))
        if not candidates:
            return None
        return max(candidates, key=lambda c: c[0])[1]

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

    def _render(self, intent: Intent, state: ConversationState, term: Term | None = None, **kwargs) -> str:
        """Thin wrapper around responses.render() that always supplies the
        user's name from state, so every call site doesn't have to remember
        to pass it individually.
        """
        return render(intent, term=term, name=state.user_name, **kwargs)

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
