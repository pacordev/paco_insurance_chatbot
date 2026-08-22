"""Entity extraction: spaCy PhraseMatcher over known terms, rapidfuzz for
typo/near-miss fallback when nothing matches exactly.

This is the part of the bot that answers one narrow question: "did the user
mention an insurance term, and if so, which one?" It doesn't care about
intent (are they asking for a definition or an example?) — that's a separate
job, handled later in bot/intents.py and bot/dispatcher.py.

Uses a blank spaCy pipeline (no statistical model) — PhraseMatcher only needs
tokenization, per handoff.md §2.10.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import spacy
from rapidfuzz import process, fuzz
from spacy.matcher import PhraseMatcher

from bot.data import TermStore

FUZZY_MATCH_THRESHOLD = 80  # 0-100; below this we treat it as no match
MIN_QUERY_LEN_FOR_FUZZY = 5  # shorter queries are too easy to false-match

# People rarely say just the term name — they wrap it in a question or a
# command ("what is...", "define...", "tell me about..."). Left in place,
# those wrapper words can accidentally look similar to unrelated short terms
# and throw off the fuzzy matcher below (e.g. "what is workers comp" once
# scored higher against an unrelated 8-word term than against "workers
# compensation" itself). So before fuzzy-matching, we peel the wrapper off
# and just compare the actual topic phrase.
# Real intent routing (build step 4) will make this stripping unnecessary,
# since it'll already know which part of the sentence is the topic — this is
# a stand-in for that, needed because the matcher is being tested on its own.
_FILLER_PREFIX = re.compile(
    r"^(what('?s| is)|tell me about|define|explain|describe)\s+(an?\s+)?",
    re.IGNORECASE,
)


def _strip_filler(text: str) -> str:
    """Cut a leading "what is / define / tell me about" style phrase off the
    front of the text, leaving (hopefully) just the term the user meant.
    """
    return _FILLER_PREFIX.sub("", text).strip()


@dataclass(frozen=True)
class EntityMatch:
    """One "we think the user meant this term" result, whether it came from
    an exact match or a fuzzy guess.
    """

    term_id: str
    matched_text: str
    exact: bool
    score: float  # 100.0 for exact PhraseMatcher hits


class EntityMatcher:
    """Wraps spaCy's PhraseMatcher so the rest of the bot can just call
    `.extract(text)` and get back term ids, without knowing anything about
    spaCy itself.
    """

    def __init__(self, store: TermStore):
        # Build the matcher once, up front, from every known phrase in the
        # glossary. This is the expensive-ish setup step; extract() itself
        # should be cheap and fast since it reuses this.
        self.store = store
        self.nlp = spacy.blank("en")
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        patterns = [self.nlp.make_doc(surface) for surface in store.all_surface_forms()]
        self.matcher.add("INSURANCE_TERM", patterns)

    def extract(self, text: str) -> list[EntityMatch]:
        """Try to find glossary terms mentioned in `text`.

        Exact matches (the user's wording lines up with a known lookup key
        or synonym word-for-word) always win when present, since they're
        unambiguous. Only if nothing matches exactly do we reach for fuzzy
        matching, which is slower and less certain but catches typos.
        """
        doc = self.nlp(text)
        hits = self.matcher(doc)
        if hits:
            matches = []
            for _, start, end in hits:
                span = doc[start:end]
                term_id = self.store.resolve_surface_form(span.text)
                if term_id:
                    matches.append(EntityMatch(term_id, span.text, exact=True, score=100.0))
            if matches:
                return matches

        return self._fuzzy_match(text)

    def _fuzzy_match(self, text: str) -> list[EntityMatch]:
        """Last resort, "did you mean...?" style guess when nothing matched
        exactly — usually because of a typo or slightly-off phrasing.

        Uses WRatio rather than partial_ratio: partial_ratio scores a short
        query as a perfect match whenever it aligns with *any* substring of a
        longer candidate, regardless of how much of the candidate is left
        over (e.g. "workers comp" scored 100 against unrelated multi-word
        terms). WRatio blends ratio/partial_ratio/token-sort with a length
        penalty, which avoids that failure mode. Short queries are also
        rejected outright (MIN_QUERY_LEN_FOR_FUZZY) since they're inherently
        too easy to false-match against a 1000+ term vocabulary.
        """
        text = _strip_filler(text)
        if len(text) < MIN_QUERY_LEN_FOR_FUZZY:
            return []

        # Ask rapidfuzz for the handful of surface forms that read closest
        # to what the user typed.
        candidates = self.store.all_surface_forms()
        results = process.extract(text.lower(), candidates, scorer=fuzz.WRatio, limit=5)

        # Several surface forms can belong to the same term (a term's own
        # name plus its synonyms), so we collapse results down to one
        # best-scoring match per term rather than showing duplicates.
        best_by_term: dict[str, EntityMatch] = {}
        for surface, score, _ in results:
            if score < FUZZY_MATCH_THRESHOLD:
                continue
            term_id = self.store.resolve_surface_form(surface)
            if not term_id:
                continue
            existing = best_by_term.get(term_id)
            if existing is None or score > existing.score:
                best_by_term[term_id] = EntityMatch(term_id, surface, exact=False, score=score)

        return sorted(best_by_term.values(), key=lambda m: m.score, reverse=True)[:3]
