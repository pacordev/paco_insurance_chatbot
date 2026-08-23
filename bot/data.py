"""Loads insurance_terms.json once and exposes it as an id-keyed store.

Think of this file as the "librarian" for the glossary: it reads the raw
JSON off disk one time at startup, organizes it into something fast and easy
to query, and hands out terms by id or by whatever phrase a user typed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "insurance_terms.json"

# A handful of definitions (33 of 1,175 at last count) run several times the
# glossary's ~110-character median -- multi-sentence passages up to 800
# characters. Answering with those in full every time reads noticeably
# denser than a typical reply, so ask_definition shows a trimmed version
# first for anything over this length, with the full text available on
# request (bot/dispatcher.py).
LONG_DEFINITION_THRESHOLD = 400


@dataclass(frozen=True)
class RelatedTerm:
    """A pointer to another term, used for "see also" style suggestions."""

    term: str
    id: str


@dataclass(frozen=True)
class Term:
    """One glossary entry, reshaped from raw JSON into a proper Python object
    so the rest of the bot can work with `.attribute` access instead of
    fishing values out of a dict by string key every time.
    """

    id: str
    term: str
    definition: str
    examples: list[str]
    categories: list[str]
    synonyms: list[str]
    related: list[RelatedTerm]
    difficulty: str
    lookup_keys: list[str]

    @property
    def is_long_definition(self) -> bool:
        return len(self.definition) > LONG_DEFINITION_THRESHOLD

    @property
    def short_definition(self) -> str:
        """A trimmed version of a long definition, for the "want the full
        definition?" flow (bot/dispatcher.py) -- prefers cutting at the end
        of the first sentence if that's still reasonably short, otherwise
        hard-truncates at a word boundary.
        """
        stripped = self.definition.strip()
        if not self.is_long_definition:
            return stripped
        limit = LONG_DEFINITION_THRESHOLD // 2
        first_sentence_end = stripped.find(". ")
        if 0 < first_sentence_end <= limit:
            return stripped[: first_sentence_end + 1]
        truncated = stripped[:limit].rsplit(" ", 1)[0]
        return truncated.rstrip(",;: ") + "…"


class TermStore:
    """In-memory lookup over insurance_terms.json, keyed by stable id.

    `lookup_index` maps every lookup_key/synonym surface form (lowercased) to
    its owning term id. Collision-free by construction (validated in data
    prep, see handoff.md §2.6/§2.8) — this class does not re-check that.
    """

    def __init__(self, terms: dict[str, Term], categories: dict[str, int]):
        # `terms` is already built by `load()` below; here we just also
        # build a second index so that later, when a user types some phrase,
        # we can go straight from that phrase to the term id without
        # scanning every term one by one.
        self._terms = terms
        self.categories = categories
        self.lookup_index: dict[str, str] = {}
        for t in terms.values():
            for key in (*t.lookup_keys, *t.synonyms):
                self.lookup_index[key.lower()] = t.id

    @classmethod
    def load(cls, path: Path | str = DEFAULT_DATA_PATH) -> "TermStore":
        """Read insurance_terms.json off disk and turn it into a TermStore.

        This is the one place raw JSON gets parsed — everything downstream
        works with `Term`/`RelatedTerm` objects instead of dicts.
        """
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        terms: dict[str, Term] = {}
        for entry in raw["terms"]:
            terms[entry["id"]] = Term(
                id=entry["id"],
                term=entry["term"],
                definition=entry["definition"],
                examples=entry["examples"],
                categories=entry["categories"],
                synonyms=entry["synonyms"],
                related=[RelatedTerm(**r) for r in entry["related"]],
                difficulty=entry["difficulty"],
                lookup_keys=entry["lookup_keys"],
            )
        return cls(terms, raw["meta"]["categories"])

    def get(self, term_id: str) -> Term | None:
        """Fetch one term by its stable id, or None if it doesn't exist."""
        return self._terms.get(term_id)

    def all_terms(self) -> list[Term]:
        """Every term in the glossary, in no particular order."""
        return list(self._terms.values())

    def all_surface_forms(self) -> list[str]:
        """Every phrase a user might type to refer to a term — the term's own
        lookup keys plus its synonyms/abbreviations — all in one flat list.
        This is what the entity matcher (bot/nlu.py) scans against.
        """
        return list(self.lookup_index.keys())

    def resolve_surface_form(self, text: str) -> str | None:
        """Given a phrase (case doesn't matter), find the term id it belongs
        to, if any. This is a plain dict lookup, not fuzzy — for near-misses
        and typos, see EntityMatcher in bot/nlu.py instead.
        """
        return self.lookup_index.get(text.lower())

    def by_category(self, category: str) -> list[Term]:
        """All terms tagged under a given category, e.g. for "browse by
        category" style features later on.
        """
        return [t for t in self._terms.values() if category in t.categories]

    def by_categories(self, *categories: str) -> list[Term]:
        """All terms tagged under *every* given category — e.g. `by_categories("Life",
        "Risk")` for "what risks fall under life insurance", where a category alone
        (just "Life") would be too broad and a single category alone can't express
        "and it's specifically a risk-type entry."
        """
        wanted = set(categories)
        return [t for t in self._terms.values() if wanted.issubset(t.categories)]
