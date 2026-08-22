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
from bot.responses import render, render_welcome


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
        # differently. Checked without the definition's own trailing period
        # since one template legitimately drops it in favor of a dash
        # ("...depreciation — does that clear it up?") — that's a real
        # stylistic choice, not missing content, so the check shouldn't
        # demand the period back.
        for _ in range(10):
            reply = render(Intent.ASK_DEFINITION, term=self.acv)
            self.assertIn(self.acv.term, reply)
            self.assertIn(self.acv.definition.rstrip("."), reply)

    def test_ask_definition_never_produces_a_doubled_period(self):
        # Regression: a couple of templates continue the sentence right
        # after {definition} with no line break ("...basis. Hope that
        # helps, Paco.") — since ~98% of real definitions already end with
        # their own period, doing that naively produced "..". self.acv's
        # definition ends with a period on purpose, to catch this.
        self.assertTrue(self.acv.definition.endswith("."))
        for _ in range(30):
            reply = render(Intent.ASK_DEFINITION, term=self.acv, name="Paco")
            self.assertNotIn("..", reply)

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

    def test_list_risks_with_a_domain_includes_the_domain_and_every_risk(self):
        reply = render(Intent.LIST_RISKS, domain="Life", risk_terms=["Mortality Risk", "Longevity Risk"])
        self.assertIn("Life", reply)
        self.assertIn("Mortality Risk", reply)
        self.assertIn("Longevity Risk", reply)

    def test_list_risks_without_a_domain_lists_available_domains_instead(self):
        reply = render(Intent.LIST_RISKS, available_domains=["Auto", "Life"])
        self.assertIn("Auto", reply)
        self.assertIn("Life", reply)

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

    def test_every_intent_addresses_the_user_by_name_when_given(self):
        # The whole point of threading a name through is that every single
        # reply uses it, not just a greeting — check that directly for each
        # intent rather than trusting it by inspection.
        cases = [
            (Intent.ASK_DEFINITION, {"term": self.acv}),
            (Intent.ASK_EXAMPLE, {"term": self.acv}),
            (Intent.COMPARE_TERMS, {"term": self.acv, "other_term": self.replacement_cost}),
            (Intent.LIST_CATEGORIES, {"categories": ["Auto"]}),
            (Intent.LIST_RISKS, {"domain": "Life", "risk_terms": ["Mortality Risk"]}),
            (Intent.LIST_RISKS, {"available_domains": ["Auto", "Life"]}),
            (Intent.GREET, {}),
            (Intent.HELP, {}),
            (Intent.GOODBYE, {}),
            (Intent.FALLBACK, {}),
            (Intent.FALLBACK, {"candidates": ["Actual Cash Value", "Replacement Cost"]}),
        ]
        # Each template list now has 5-8+ hand-written variants — drawing
        # only once per intent would leave most of them unchecked, so this
        # loops enough times per case that, statistically, every variant in
        # even the longest list gets a real chance to be exercised.
        for intent, kwargs in cases:
            with self.subTest(intent=intent, kwargs=kwargs):
                for _ in range(30):
                    reply = render(intent, name="Paco", **kwargs)
                    self.assertIn("Paco", reply)

    def test_missing_name_falls_back_to_a_generic_greeting_word(self):
        # No name given (e.g. the user hit enter at the name prompt) should
        # still read naturally, not leave a blank where the name should go.
        reply = render(Intent.GREET)
        self.assertIn("there", reply.lower())

    def test_render_welcome_includes_the_name(self):
        # Run several times since the welcome message is now picked at
        # random from ten variants (like every other intent's templates) —
        # every draw should still include the name.
        for _ in range(20):
            reply = render_welcome("Paco")
            self.assertIn("Paco", reply)


if __name__ == "__main__":
    unittest.main()
