"""Regression tests for bot/dispatcher.py's Dispatcher.

These are multi-turn tests, deliberately — the whole point of the
dispatcher is conversation *continuity* (follow-ups, disambiguation), which
a single-message test can't exercise. Uses the real insurance_terms.json via
TermStore.load() rather than fake data, since the specific term ids and
fuzzy-match behavior involved are part of what's being tested.

One of these (test_disambiguation_reply_by_position) is a locked-in
regression for a real bug found during manual testing: a short reply like
"the first one" was getting fuzzy-matched by the entity matcher against
unrelated glossary terms, which silently won over correctly interpreting it
as an answer to the pending "did you mean X or Y?" question.

Run with: python -m unittest tests.test_dispatcher
"""

import unittest

from bot.data import TermStore
from bot.dispatcher import Dispatcher
from bot.intents import Intent
from bot.state import ConversationState


class DispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Loaded once for the whole test class — TermStore/Dispatcher setup
        # isn't free (it builds the spaCy PhraseMatcher over ~1,100 surface
        # forms), and nothing here mutates the store itself.
        cls.store = TermStore.load()

    def setUp(self):
        self.dispatcher = Dispatcher(self.store)
        self.state = ConversationState()

    def _say(self, text: str) -> str:
        reply, self.state = self.dispatcher.process_turn(text, self.state)
        return reply

    def test_readme_pitch_scenario_end_to_end(self):
        # This is the exact multi-turn example used in the README's "Why
        # this exists" section — worth locking in since it's the project's
        # own stated reason to exist.
        self.assertIn("Actual Cash Value", self._say("what's ACV?"))
        self.assertEqual(self.state.last_term_id, "actual-cash-value-acv")

        example_reply = self._say("can you give me an example?")
        self.assertIn("ten-year-old roof", example_reply)  # from the ACV example sentence

        compare_reply = self._say("how's that different from replacement cost?")
        self.assertIn("Actual Cash Value", compare_reply)
        self.assertIn("Replacement Cost", compare_reply)

    def test_bare_term_defaults_to_definition(self):
        reply = self._say("reinsurance")
        self.assertEqual(self.state.last_intent, Intent.ASK_DEFINITION)
        self.assertIn("Reinsurance", reply)

    def test_disambiguation_reply_by_position(self):
        # "workers comp" doesn't exactly match any lookup key, so it should
        # come back as a multi-candidate disambiguation question rather than
        # a guess.
        first_reply = self._say("workers comp")
        self.assertTrue(self.state.pending_disambiguation)
        first_candidate_id = self.state.pending_disambiguation[0]
        expected_term = self.store.get(first_candidate_id).term
        self.assertIn(expected_term, first_reply)

        second_reply = self._say("the first one")
        self.assertEqual(self.state.last_term_id, first_candidate_id)
        self.assertFalse(self.state.pending_disambiguation)
        self.assertIn(expected_term, second_reply)

    def test_disambiguation_reply_by_naming_the_term(self):
        self._say("workers comp")
        candidate_id = self.state.pending_disambiguation[1]
        candidate_name = self.store.get(candidate_id).term

        reply = self._say(candidate_name)
        self.assertEqual(self.state.last_term_id, candidate_id)
        self.assertFalse(self.state.pending_disambiguation)
        self.assertIn(candidate_name, reply)

    def test_unrelated_message_drops_pending_disambiguation(self):
        self._say("workers comp")
        self.assertTrue(self.state.pending_disambiguation)

        self._say("hello")
        self.assertFalse(self.state.pending_disambiguation)
        self.assertEqual(self.state.last_intent, Intent.GREET)

    def test_ask_example_with_no_prior_context_falls_back(self):
        reply = self._say("give me an example")
        self.assertIsNone(self.state.last_term_id)
        self.assertEqual(self.state.last_intent, Intent.FALLBACK)
        self.assertTrue(reply)

    def test_list_categories_does_not_need_a_term(self):
        reply = self._say("what categories do you have")
        for category in self.store.categories:
            self.assertIn(category, reply)

    def test_greet_help_goodbye_round_trip(self):
        for text, expected_intent in [("hi", Intent.GREET), ("help", Intent.HELP), ("bye", Intent.GOODBYE)]:
            with self.subTest(text=text):
                reply = self._say(text)
                self.assertTrue(reply)
                self.assertEqual(self.state.last_intent, expected_intent)

    def test_user_name_is_threaded_through_every_reply(self):
        # Set on the state up front, the way paco_chatbot.py does after
        # asking for it at the start of a session — every reply for the
        # rest of the conversation should address the user by it.
        self.state.user_name = "Paco"
        for text in ("hi", "what is a deductible", "give me an example", "compare deductible and premium"):
            with self.subTest(text=text):
                self.assertIn("Paco", self._say(text))

    def test_list_risks_under_a_recognized_domain(self):
        # The exact motivating question for this feature — asking about a
        # term-shaped intent (definitions) previously answered "Risk"'s own
        # definition instead of listing the risks life insurance covers.
        reply = self._say("what are the usual risks under life insurance")
        self.assertIn("Mortality Risk", reply)
        self.assertIn("Longevity Risk", reply)
        self.assertEqual(self.state.last_intent, Intent.LIST_RISKS)

    def test_list_risks_with_no_domain_lists_available_domains(self):
        reply = self._say("what are the risks?")
        self.assertIn("Life", reply)
        self.assertIn("Auto", reply)
        # "Risk" itself is the cross-cutting tag, not a line of business —
        # shouldn't show up as something to pick.
        self.assertNotIn("Risk,", reply)
        self.assertNotIn("Risk.", reply)

    def test_singular_risk_still_asks_for_the_definition(self):
        # Regression: broadening LIST_RISKS's patterns once accidentally
        # caught singular "risk" too, breaking this.
        reply = self._say("what is risk")
        self.assertEqual(self.state.last_intent, Intent.ASK_DEFINITION)
        self.assertIn("Uncertainty", reply)

    def test_list_terms_for_a_large_category_is_capped_with_total_shown(self):
        reply = self._say("show me Auto terms")
        self.assertEqual(self.state.last_intent, Intent.LIST_TERMS)
        auto_term_count = len(self.store.by_category("Auto"))
        self.assertGreater(auto_term_count, 10)  # confirms this actually exercises the cap
        self.assertIn(str(auto_term_count), reply)

    def test_list_terms_for_a_small_category_shows_everything(self):
        reply = self._say("list Insurance Documentation terms")
        doc_terms = self.store.by_category("Insurance Documentation")
        self.assertLessEqual(len(doc_terms), 10)  # confirms this does NOT exercise the cap
        for term in doc_terms:
            self.assertIn(term.term, reply)

    def test_list_terms_with_no_domain_falls_back_to_list_categories(self):
        reply = self._say("show me terms")
        for category in self.store.categories:
            self.assertIn(category, reply)


if __name__ == "__main__":
    unittest.main()
