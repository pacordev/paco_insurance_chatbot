"""Smoke-test REPL for the entity-matching layer built so far (data.py, nlu.py).

Not the real chatbot entry point yet — intent routing, conversation state,
and response templates are still stubs (bot/intents.py, bot/responses.py,
bot/dispatcher.py). This just proves a raw utterance resolves to a term, so
we have something runnable to poke at before the rest of the pieces exist.
"""

from bot.data import TermStore
from bot.nlu import EntityMatcher


def main():
    # Load the glossary and build the matcher once, up front — this is the
    # slightly slower "startup" work that shouldn't happen per message.
    store = TermStore.load()
    matcher = EntityMatcher(store)
    print(f"Loaded {len(store.all_terms())} terms. Type a phrase, or 'quit'.")

    while True:
        text = input("> ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue

        # Ask the matcher what term(s), if any, this looks like it's about.
        matches = matcher.extract(text)
        if not matches:
            print("No match found.")
            continue

        for m in matches:
            term = store.get(m.term_id)
            kind = "exact" if m.exact else f"fuzzy ({m.score:.0f})"
            print(f"[{kind}] {term.term}: {term.definition}")


if __name__ == "__main__":
    main()
