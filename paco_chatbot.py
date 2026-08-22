"""The chatbot's entry point: a command-line REPL that talks to the
Dispatcher, so this is now an actual (if bare-bones) conversation, not just
a term-matching smoke test.
"""

from bot.data import TermStore
from bot.dispatcher import Dispatcher
from bot.intents import Intent
from bot.responses import render, render_welcome
from bot.state import ConversationState


def main():
    # Load the glossary and build the matcher once, up front — this is the
    # slightly slower "startup" work that shouldn't happen per message.
    store = TermStore.load()
    dispatcher = Dispatcher(store)

    # Asking for the name up front, before the loop starts, is what lets
    # every later reply address the user personally instead of feeling like
    # an anonymous lookup tool.
    name = input("Before we start, what's your name? ").strip()

    # Difficulty-aware onboarding: asked once, right after the name, same
    # forgiving no-validation posture as the name prompt itself — anything
    # not starting with "y" is treated as "no."
    newcomer_answer = input("Are you new to insurance terminology? (y/n) ").strip().lower()
    is_newcomer = newcomer_answer.startswith("y")

    state = ConversationState(user_name=name, is_newcomer=is_newcomer)
    print(render_welcome(name))

    while True:
        text = input("> ").strip()
        if text.lower() in {"quit", "exit"}:
            # A random goodbye here too — same GOODBYE templates used when
            # someone types "bye" mid-conversation, since the sentiment is
            # identical either way, just reached by typing the literal exit
            # command instead of a conversational farewell.
            print(render(Intent.GOODBYE, name=state.user_name))
            break
        if not text:
            continue

        reply, state = dispatcher.process_turn(text, state)
        print(reply)


if __name__ == "__main__":
    main()
