"""Regression tests for bot/intents.py's recognize_intent().

Why this file exists, specifically: recognize_intent() is plain rule-based
pattern matching, not a trained classifier — there's no dataset of examples
behind it, just a hand-written, priority-ordered list of regexes. That kind
of system doesn't get harder to build as it grows, but it does get harder to
*verify*: every new intent's patterns can silently steal messages away from
an existing intent's patterns (e.g. "what's the difference between X and Y"
would be swallowed by a much broader "what's" pattern if COMPARE_TERMS
weren't checked before ASK_DEFINITION).

So this isn't really testing "does recognize_intent work" in the abstract —
it's a running record of the specific phrasing collisions we already thought
through, so that adding a new intent later and accidentally breaking one of
these is caught immediately instead of silently.

Run with: python -m unittest tests.test_intents
"""

import unittest

from bot.intents import Intent, recognize_intent


class RecognizeIntentTests(unittest.TestCase):
    def _assert_all(self, cases: list[tuple[str, Intent]]):
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(recognize_intent(text), expected)

    def test_greetings(self):
        # Anchored to "the whole message basically is a greeting" — a
        # greeting word buried inside a longer question shouldn't hijack it.
        self._assert_all([
            ("hi", Intent.GREET),
            ("hello there!", Intent.GREET),
            ("good morning", Intent.GREET),
            ("hey team", Intent.GREET),
        ])

    def test_goodbyes(self):
        self._assert_all([
            ("bye", Intent.GOODBYE),
            ("thanks, that is all", Intent.GOODBYE),
            ("that's all, thanks", Intent.GOODBYE),
        ])

    def test_help(self):
        self._assert_all([
            ("help", Intent.HELP),
            ("what can you do?", Intent.HELP),
        ])

    def test_compare_terms_beats_ask_definition(self):
        # These all contain "what is"/"what's"-shaped wording, which is also
        # the ASK_DEFINITION trigger — the point of this test is confirming
        # COMPARE_TERMS still wins because it's checked first.
        self._assert_all([
            ("what is the difference between ACV and replacement cost?", Intent.COMPARE_TERMS),
            ("how is HMO different from PPO", Intent.COMPARE_TERMS),
            ("collision vs comprehensive", Intent.COMPARE_TERMS),
        ])

    def test_ask_example_beats_ask_definition(self):
        self._assert_all([
            ("can you give me an example of a deductible", Intent.ASK_EXAMPLE),
            ("use liability in a sentence", Intent.ASK_EXAMPLE),
        ])

    def test_list_categories(self):
        self._assert_all([
            ("what categories do you have", Intent.LIST_CATEGORIES),
            ("list the topics", Intent.LIST_CATEGORIES),
        ])

    def test_ask_definition(self):
        self._assert_all([
            ("what is ACV", Intent.ASK_DEFINITION),
            ("define liability", Intent.ASK_DEFINITION),
            ("explain workers comp", Intent.ASK_DEFINITION),
            # "help me understand X" reads like a HELP request on the
            # surface, but it's really someone asking for a definition —
            # HELP only fires on the standalone/capability-question phrasing
            # above, not on "help" appearing anywhere in the message.
            ("help me understand deductible", Intent.ASK_DEFINITION),
            # Singular "risk" is almost certainly about the general concept,
            # not a request to list risks — see test_list_risks_beats_ask_definition
            # for the plural case, which is the opposite call.
            ("what is risk", Intent.ASK_DEFINITION),
        ])

    def test_list_risks_beats_ask_definition(self):
        # All of these contain "what is/are"-shaped wording (the
        # ASK_DEFINITION trigger) — the point is confirming LIST_RISKS wins
        # because it's checked first, same reasoning as compare/example.
        # Uses plural "risks" specifically; see test_ask_definition above
        # for why singular "risk" is intentionally routed differently.
        self._assert_all([
            ("what are the usual risks under life insurance", Intent.LIST_RISKS),
            ("what are the common risks covered under life insurance", Intent.LIST_RISKS),
            ("what risks does life insurance cover", Intent.LIST_RISKS),
            ("what are the risks in auto insurance", Intent.LIST_RISKS),
            ("common risks in health insurance", Intent.LIST_RISKS),
            ("risks covered under home insurance", Intent.LIST_RISKS),
            ("list the risks for auto insurance", Intent.LIST_RISKS),
            ("what are the risks?", Intent.LIST_RISKS),
        ])

    def test_list_terms_beats_ask_definition(self):
        # Requires plural "terms" for the same reason LIST_RISKS requires
        # plural "risks" — "define this term" (singular) is still a normal
        # definition request, not a browsing one.
        self._assert_all([
            ("show me Auto terms", Intent.LIST_TERMS),
            ("list Auto terms", Intent.LIST_TERMS),
            ("browse Life terms", Intent.LIST_TERMS),
            ("what terms are under Auto insurance", Intent.LIST_TERMS),
            ("show me all Life insurance terms", Intent.LIST_TERMS),
            ("define this term", Intent.ASK_DEFINITION),
        ])

    def test_fallback_on_bare_term_or_gibberish(self):
        # A bare term with no question wrapped around it ("ACV" on its own)
        # deliberately comes back FALLBACK here — recognize_intent() only
        # looks at phrasing, it doesn't know a real term was mentioned.
        # Promoting that to ASK_DEFINITION is the dispatcher's job, once it
        # exists, because only the dispatcher has both the intent *and* the
        # entity-match result at the same time (see bot/intents.py docstring).
        self._assert_all([
            ("ACV", Intent.FALLBACK),
            ("asdkfjasldkfj", Intent.FALLBACK),
            ("", Intent.FALLBACK),
        ])


if __name__ == "__main__":
    unittest.main()
