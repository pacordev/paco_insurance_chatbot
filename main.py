"""The chatbot's entry point: a command-line REPL that talks to the
Dispatcher, so this is now an actual (if bare-bones) conversation, not just
a term-matching smoke test.
"""

from bot.data import TermStore
from bot.dispatcher import Dispatcher
from bot.state import ConversationState


def main():
    # Load the glossary and build the matcher once, up front — this is the
    # slightly slower "startup" work that shouldn't happen per message.
    store = TermStore.load()
    dispatcher = Dispatcher(store)
    state = ConversationState()

    print(f"Loaded {len(store.all_terms())} terms. Ask about an insurance term, or type 'quit'.")

    while True:
        text = input("> ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue

        reply, state = dispatcher.process_turn(text, state)
        print(reply)


if __name__ == "__main__":
    main()
