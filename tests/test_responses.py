"""Regression tests for bot/responses.py's render().

Less about "is the wording good" (that's a judgment call, not something a
test can verify) and more about the structural things that are easy to get
wrong: does every intent actually produce non-empty text, does the random
template variety still contain the data it's supposed to (the term name,
the definition, etc.), and do the two intents that need extra keyword data
(compare_terms, and fallback's optional disambiguation candidates) still
work when that data is present or absent.

Run with: python -m unittest tests.test_responses
"""

import unittest

from bot.data import RelatedTerm, Term
from bot.intents import Intent
from bot.responses import render


def _make_term(id_: str, term: str, definition: str, examples: list[str] | None = None) -> Term:
    return Term(
        id=id_,
        term=term,
        definition=definition,
        examples=examples or [],
        categories=["General Insurance Concepts"],
        synonyms=[],
        related=[RelatedTerm(term="Related", id="related")],
        difficulty="Basic",
        lookup_keys=[term.lower()],
    )


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.acv = _make_term(
            "actual-cash-value", "Actual Cash Value",
            "The cost to replace an item minus depreciation.",
            examples=["The insurer paid the actual cash value of the totaled car."],
        )
        self.replacement_cost = _make_term(
            "replacement-cost", "Replacement Cost",
            "The cost to replace an item with a new one of similar kind, with no deduction for depreciation.",
        )

    def test_ask_definition_includes_term_and_definition(self):
        # Run several times since the wording is picked at random — every
        # draw should still contain the actual content, just phrased
        # differently.
        for _ in range(10):
            reply = render(Intent.ASK_DEFINITION, term=self.acv)
            self.assertIn(self.acv.term, reply)
            self.assertIn(self.acv.definition, reply)

    def test_ask_example_uses_the_example_sentence(self):
        reply = render(Intent.ASK_EXAMPLE, term=self.acv)
        self.assertIn(self.acv.examples[0], reply)

    def test_ask_example_without_an_example_says_so_instead_of_crashing(self):
        # replacement_cost was built with no examples on purpose, to make
        # sure a missing example is handled gracefully instead of raising
        # (or silently falling back to the definition, which would be
        # answering the wrong question).
        reply = render(Intent.ASK_EXAMPLE, term=self.replacement_cost)
        self.assertNotIn(self.replacement_cost.definition, reply)
        self.assertIn(self.replacement_cost.term, reply)

    def test_compare_terms_includes_both_terms_and_definitions(self):
        reply = render(Intent.COMPARE_TERMS, term=self.acv, other_term=self.replacement_cost)
        self.assertIn(self.acv.term, reply)
        self.assertIn(self.acv.definition, reply)
        self.assertIn(self.replacement_cost.term, reply)
        self.assertIn(self.replacement_cost.definition, reply)

    def test_list_categories_includes_every_category_given(self):
        reply = render(Intent.LIST_CATEGORIES, categories=["Auto", "Property", "Life"])
        for category in ("Auto", "Property", "Life"):
            self.assertIn(category, reply)

    def test_greet_help_goodbye_need_no_term(self):
        for intent in (Intent.GREET, Intent.HELP, Intent.GOODBYE):
            with self.subTest(intent=intent):
                self.assertTrue(render(intent))

    def test_fallback_without_candidates_is_a_generic_apology(self):
        reply = render(Intent.FALLBACK)
        self.assertTrue(reply)

    def test_fallback_with_candidates_asks_a_disambiguation_question(self):
        reply = render(Intent.FALLBACK, candidates=["Actual Cash Value", "Replacement Cost"])
        self.assertIn("Actual Cash Value", reply)
        self.assertIn("Replacement Cost", reply)


if __name__ == "__main__":
    unittest.main()
