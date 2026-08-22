"""Regression tests for bot/data.py's TermStore.

test_plain_multi_word_term_names_resolve_from_themselves is a dataset-wide
integrity check, not a narrow one-off regression: it locks in a real bug
found during manual testing of the list_terms feature, where 21 of the 23
newly-merged risk terms (e.g. "Collision Damage Risk", "Mortality Risk")
never had their own plain display name registered as a lookup key at all —
so asking about them by their exact, natural name silently matched some
unrelated shorter word contained inside it instead (e.g. the bare "Collision"
entry). Fixed by adding each term's own name as a lookup key; this test
exists so a future merge that reintroduces the same gap gets caught
immediately across the whole dataset, not just for these 23 terms.

Deliberately scoped to display names with *no* punctuation (parens, hyphens,
slashes, etc.) — plenty of terms elsewhere in the dataset (e.g. "Actual Cash
Value (ACV)") intentionally have lookup keys that strip punctuation from the
display name rather than match it verbatim (handoff.md §2.6/§2.8, done to
keep lookup keys regex-metacharacter-free). Testing the strict "resolves from
its own exact display name" invariant against those would be testing against
the wrong thing — this only asserts it for the (large majority of) terms
where nothing about the name should need any transformation at all.

Run with: python -m unittest tests.test_data
"""

import re
import unittest

from bot.data import TermStore

_PLAIN_NAME = re.compile(r"[A-Za-z' ]+")


class TermStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = TermStore.load()

    def test_plain_multi_word_term_names_resolve_from_themselves(self):
        failures = []
        for term in self.store.all_terms():
            if not _PLAIN_NAME.fullmatch(term.term):
                continue  # has punctuation — a different, deliberate design choice (see module docstring)
            if self.store.resolve_surface_form(term.term) != term.id:
                failures.append(term.term)
        self.assertEqual(failures, [], f"{len(failures)} terms don't resolve from their own plain display name")

    def test_collision_damage_risk_resolves_from_its_own_name(self):
        # The exact case that surfaced this bug live.
        self.assertEqual(self.store.resolve_surface_form("Collision Damage Risk"), "auto-collision-risk")


if __name__ == "__main__":
    unittest.main()
