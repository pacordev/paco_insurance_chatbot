"""Regression tests for bot/nlu.py's EntityMatcher.

test_longest_exact_match_wins_over_a_contained_shorter_term locks in a real
bug found during manual testing after merging in a batch of new terms: many
short, generic single words are themselves real glossary entries ("Risk",
"Loss"), and plenty of longer terms contain one as a literal substring
("Risk Adjustment", "Loss Ratio"). Before the fix, a question about the
longer term would also register an exact hit on the shorter one buried
inside it, and the shorter (wrong) one won because it happened to come first
in the raw match list — e.g. "what is risk adjustment" answered about
"Risk" instead of "Risk Adjustment".

Run with: python -m unittest tests.test_nlu
"""

import unittest

from bot.data import TermStore
from bot.nlu import EntityMatcher


class EntityMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = TermStore.load()
        cls.matcher = EntityMatcher(cls.store)

    def test_longest_exact_match_wins_over_a_contained_shorter_term(self):
        cases = [
            ("risk adjustment", "risk-adjustment"),
            ("loss ratio", "loss-ratio"),
            ("absolute liability", "absolute-liability"),
        ]
        for text, expected_id in cases:
            with self.subTest(text=text):
                matches = self.matcher.extract(text)
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0].term_id, expected_id)

    def test_two_separate_longer_terms_in_one_message_both_resolve(self):
        matches = self.matcher.extract("compare loss ratio and combined ratio")
        term_ids = {m.term_id for m in matches}
        self.assertEqual(term_ids, {"loss-ratio", "combined-ratio"})


if __name__ == "__main__":
    unittest.main()
