# Insurance Terminology Chatbot - v1.5

A little chatbot that came to my mind to help coworkers, or people in general, who aren't insurance people — developers, architects, testers, anyone who joins a project and suddenly has to deal with terms like "ALAE" or "IBNR reserves" — actually understand the vocabulary without having to bug someone or dig through a PDF glossary. It's also, honestly, my excuse to get more comfortable with Python.

This README tells the story of the project as it happens: why it exists, what's been built, what got in the way, and what's still ahead. I'll keep updating it as we go, so it doubles as a running log, not just a static description.

---

## Why this exists

I kept noticing the same pattern: someone new joins a project that touches insurance, and half of onboarding turns into "what does that word mean?" moments — asked in Teams, answered inconsistently, and never written down anywhere useful. A searchable glossary already helps, but a chatbot that can hold a small conversation ("what's a premium?" → "can you give me an example?" → "how's that different from replacement cost?") is a much nicer way to actually learn the terms rather than just look them up once and forget them.

## Scope — what this is, and what it deliberately isn't

**It is:** an internal learning tool for coworkers or any other people with no insurance background. You ask about a term, it explains it, gives you an example, tells you what's related, and can quiz you on what you've learned.

**It is not:** a customer-facing or policyholder-facing bot. There's no account access, no claims lookup, no policy data, no PII of any kind — it only ever talks about the *glossary*, never about a real person's insurance. That boundary matters enough that it shaped actual design decisions (see the intent list further down), and it's worth keeping in mind if this ever gets extended later — the temptation to bolt on "check my claim status" should be resisted, because that's a completely different (and much more sensitive) kind of project.

Secondary, smaller goal: I'm using this as a way to practice writing real Python, not just toy scripts.


---

## Current status

Data is done (for the moment). Architecture is decided. The core conversation loop works end to end:

- The dataset (`insurance_terms.json`) now holds **1,342 terms** across **17 categories**, each with example sentences, validated and ready to build against.
- The entity-matching layer (figuring out *which term* someone means) is built and tested, including preferring the longest match when phrases overlap.
- The intent-recognition layer (figuring out *what they want* — a definition, an example, a comparison, browsing a category's risks or its full term list, a quiz, etc.) is built and tested.
- Response templates (turning a term + intent into actual reply text) are built and tested, with real phrasing variety and every reply personalized by name.
- The dispatcher — the piece that ties all of the above into one real, multi-turn conversation, including follow-ups and "did you mean X or Y?" disambiguation — is built and tested against the real dataset.

In other words: `python paco_chatbot.py` now opens by asking your name and greeting you personally, then holds an actual (if bare-bones) conversation from there — not just a component demo. What's left is mostly about making the experience richer and getting it in front of people — see "What's next" below.

---

## Tech Stack

- **[Python 3](https://www.python.org/)** — the whole project; also the secondary goal of getting more comfortable with the language
- **[spaCy](https://spacy.io/)** — `PhraseMatcher` powers exact entity matching (which glossary term a message is about), preferring the longest match when phrases overlap
- **[rapidfuzz](https://rapidfuzz.github.io/RapidFuzz/)** — typo-tolerant fuzzy matching, used only when the exact match comes up empty
- **[JSON](https://www.json.org/)** (`insurance_terms.json`) — the entire knowledge base; no database yet, the dataset is small enough to load into memory once at startup
- **[unittest](https://docs.python.org/3/library/unittest.html)** (Python standard library) — the regression test suite in `tests/`
- **argparse-free CLI** — `paco_chatbot.py` is a plain `input()`/`print()` REPL, no CLI framework
- **[FastAPI](https://fastapi.tiangolo.com/)** *(planned)* — the backend wrapping the existing `Dispatcher`/`TermStore` core once this gets shipped as an API (see "What's next")
- **[Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)** *(planned)* — containerizing the API for deployment

---

## Project structure

```
ins_chatbot/
├── README.md                # you are here
├── insurance_terms.json      # the glossary itself — the chatbot's entire knowledge base
├── requirements.txt          # pinned Python dependencies (spaCy, rapidfuzz, and their sub-dependencies)
├── paco_chatbot.py           # entry point — a command-line REPL to talk to the bot
├── bot/                       # the actual chatbot package
│   ├── __init__.py
│   ├── data.py                # loads insurance_terms.json into memory, keyed for fast lookup
│   ├── nlu.py                  # figures out which glossary term(s) a message is about
│   ├── state.py                 # remembers context across a conversation (last term discussed, etc.)
│   ├── intents.py               # defines what a user could be asking for
│   ├── responses.py             # turns "this term + this intent" into an actual reply
│   └── dispatcher.py            # ties everything above together into one real conversation turn
└── tests/                      # growing hand-written test suite
    ├── test_intents.py          # regression tests for bot/intents.py
    ├── test_responses.py        # regression tests for bot/responses.py
    ├── test_dispatcher.py        # multi-turn regression tests for bot/dispatcher.py, including quiz mode
    ├── test_nlu.py               # regression tests for bot/nlu.py
    └── test_data.py               # dataset-wide integrity checks for bot/data.py
```

### File by file

**`insurance_terms.json`** — The knowledge base. 1,342 insurance terms across 17 categories (including a cross-cutting `Risk` tag and a dedicated `Insurtech & Technology` category, alongside line-of-business categories like `Life`/`Auto`/`Health`), each with an id, definition, example sentences, categories, a difficulty rating, related-term links, and every phrase/abbreviation ("premium," "workers comp," etc.) someone might use to refer to it. This is the only data file the bot actually needs; everything else was intermediate work to produce it.

**`bot/data.py`** — Reads `insurance_terms.json` off disk exactly once and reshapes it into a `TermStore`: proper Python objects instead of raw dict/JSON, plus an index mapping every possible phrase a user might type straight to the term it belongs to. `by_category()`/`by_categories()` filter terms by one or more category tags (e.g. "Life" + "Risk" together), used for browsing-style questions. Every other module goes through this one to get at the glossary — nothing else touches the JSON file directly.

**`bot/nlu.py`** — Short for "natural language understanding," though really it does one specific job: given a raw message, which glossary term(s) is it about? Two layers: an exact match against known phrases (using spaCy's `PhraseMatcher`, keeping the longest match when phrases overlap), and — only if that comes up empty — a fuzzy, typo-tolerant guess (using `rapidfuzz`) with some extra logic to keep that guess from getting fooled by short or filler-heavy sentences.

**`bot/state.py`** — A small object representing one user's ongoing conversation: their name (captured once at the start of the session), what term was last discussed, what the last thing they asked for was, whether the bot is mid-way through asking "did you mean X or Y?", and whether a quiz is currently running (which term's being asked, the running score, which category it's scoped to, and which terms have already come up so they don't repeat). This is what makes personalized replies, follow-up questions, and quiz mode all possible without the user repeating themselves.

**`bot/intents.py`** — Defines the fixed list of things a user can be trying to do (`ask_definition`, `ask_example`, `list_categories`, `list_risks`, `list_terms`, `start_quiz`, `compare_terms`, plus conversational basics like greeting/help/goodbye, and a fallback for "I don't know what you mean") and `recognize_intent()`, which classifies a raw message into one of them using priority-ordered regex patterns. A bare term with no question wrapped around it comes back as `fallback` on purpose — promoting that to `ask_definition` needs the entity-match result too, which only the dispatcher will have.

**`bot/responses.py`** — Turns "this term, with this intent" into an actual reply sentence via `render()`, with 5-8 phrasings per intent (picked at random, with the user's name woven in at a different spot each time) so answers don't feel robotic. Also handles the two intents that need more than just a term (comparing two terms side by side, listing categories), `render_welcome()` for the randomized session-opening greeting, and a trio of quiz-specific functions (`render_quiz_start`/`render_quiz_feedback`/`render_quiz_end`) since quiz mode isn't a single per-message reply.

**`bot/dispatcher.py`** — The conductor. Every incoming message flows through `Dispatcher.process_turn()`: recognize the intent, resolve the term (falling back to the last-discussed term for follow-ups, or asking "did you mean X or Y?" when the match is genuinely ambiguous), render a reply, update the conversation state for next time. Also resolves a line-of-business "domain" from free text (e.g. "life insurance" → the `Life` category) for `list_risks`/`list_terms`/quiz questions, since that's not something the term-focused entity matcher handles. Once a quiz starts, this is also what intercepts every message as an answer attempt instead of running normal intent recognition, until the user stops it.

**`paco_chatbot.py`** — A command-line REPL that asks your name and whether you're new to insurance terminology, shows a personalized welcome message, then talks to the real `Dispatcher` for the rest of the session — this is the actual way to have a conversation with the bot today (or it'll get replaced by a proper interface later — see "What's next").

---

## Getting started (as it exists today)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python paco_chatbot.py
```

It'll ask your name and whether you're new to insurance terminology first. After that, ask it something like `what's a premium?`, then follow up with `give me an example` or `how's that different from replacement cost?` without repeating the term name — that continuity is the whole point of the dispatcher. If you said you're new, `list_terms`/`list_risks` will show you the Basic terms in a category before the Technical ones. Type `quit` to exit (you'll get a goodbye message too).

---

## What's next

1. **More testing, as it grows** — keep extending `tests/` with misspelled and casually-worded questions as new intents/features get added, since the whole point is that the audience doesn't already know the "correct" insurance vocabulary to type.
2. **Actually shipping it somewhere people can use it.** Landed on the shape of this: a FastAPI backend wrapping the existing `Dispatcher`/`TermStore` core, and a plain static HTML/CSS/JS frontend in front of it (no framework, no build step — this stage doesn't need one). Deliberately three separate repos rather than one — this repo (`ins_chatbot`) stays exactly as it is today, clonable and runnable from the command line with no changes, and gets pip-installed as a dependency (`pip install git+https://github.com/pacordev/paco_insurance_chatbot.git`) by a new API repo rather than merged into it. A third repo holds the frontend. Deploying the API to Render (it needs to stay warm as a persistent process, since loading `TermStore`/spaCy at startup is the expensive part) and the frontend to Vercel (zero-config static hosting).
   - Worked through the security question properly before settling on an approach: the frontend will be public (URL just shared informally with coworkers, not gated), and nothing shipped in public client-side JS can be a real secret — a login form on a static site is visible in devtools regardless of how it's built. Landed on an API key (header-based) plus CORS plus rate limiting: enough to keep out bots/crawlers/casual traffic and to have a clean revocation lever, honestly scoped to what it actually protects rather than pretending to be real access control. If this ever needs to be genuinely restricted to coworkers and no one else, real SSO/OAuth is the actual next step, not attempted yet.
   - Not started — planning only. Full technical plan (repo layout, endpoints, session handling, deployment specifics) is in this project's internal `handoff.md` log.
3. **A Spanish translation of the dictionary.** English isn't everyone's first language on the team (mine included), so I plan to translate `insurance_terms.json` into Spanish as its own language variant, not just a machine-translated afterthought.
4. **Asking the session's language up front.** Once a Spanish dictionary exists, the bot should ask at the start of a session which language to use, and answer consistently in that language for the rest of the conversation.
5. **Business-domain understanding** (not started — a deliberate later addition, `enterprise_domain.json` is sitting ready for it). This is a different kind of question than anything the glossary answers today: not "what does this term mean," but "how is the business organized" — what Underwriting actually does, how it differs from Rating, and how the pieces hand off to each other (Product → Underwriting → Rating → Policy Administration → Claims). The data already links each domain to the ones before/after it, which could support a "what's the order of the policy lifecycle" style orientation question later, not just individual domain lookups.
6. **Keep growing the intent lookup-phrase list, manually or systematically, as long as the bot isn't actually "learning."** The current intent/entity recognition is hand-written regex and lookup phrases, not a trained model — it can only recognize phrasing that's been explicitly taught to it, so covering more of the ways someone might ask a question means continuing to add patterns and phrases by hand (or by mining real failed queries once there's real usage to learn from), not something that happens on its own. That's a real ceiling, not just a to-do list that empties out — it stays true until/unless the recognition layer itself changes to something that generalizes (e.g. an LLM-based approach), which is a bigger architectural shift, not a near-term item.
7. **A side project, separate from the chatbot itself, to grow that phrase list systematically from real usage.** Once the bot has real coworkers actually using it (see item 2), log the messages that hit `fallback` or an ambiguous "did you mean X or Y?", then cluster the unmatched phrasings (embeddings + clustering, or just keyword frequency to start) to surface recurring gaps for review instead of guessing new phrasings blind. Not started, and not worth building until there's enough usage volume for failed queries to cluster into anything meaningful — also needs a clear privacy stance up front (anonymized, no names attached), consistent with the no-PII boundary this project already holds itself to.

## Known limitations (being upfront about these)

- Categories and difficulty ratings are rule-based guesses, not reviewed by an actual insurance expert — good enough to build on, not something to present as authoritative without a spot-check. This applies doubly to the 137 payment-related terms merged in later: their categories and difficulty levels were machine-remapped from a different labeling scheme onto the existing one (e.g. a three-tier difficulty scale folded down into the existing two-tier one), which is an extra layer of approximation on top of the original guesswork.
- About half the glossary terms have no "related terms" suggestions — mostly because their definitions genuinely don't reference another glossary term, not a bug, just a ceiling on how much "see also" richness is possible without a smarter (e.g. embedding-based) approach.
- **Comparing two terms when one of them is misspelled doesn't work as well as it should.** The entity matcher only reaches for its typo-tolerant fuzzy matching when it finds *zero* exact matches in the whole message — so if one of the two terms in "compare premiums and workres comp" matches exactly, the matcher never even attempts to fuzzy-match the misspelled second one, and the dispatcher ends up one term short. Correctly spelled comparisons, and comparisons that lean on the last-discussed term ("how's that different from Y"), both work fine — it's specifically the "two terms, one of them typo'd, both new to this message" case that's weaker than it should be.
- ~~A phrase that was never explicitly taught to the matcher can silently resolve to the wrong, much more generic term, rather than failing loudly~~ — fixed. This kept showing up case by case as the glossary grew (a phrase never registered as a lookup key, but happening to contain a shorter word that is — e.g. "policy schedule" answering about "Policy," "co-insurance" answering about "Insurance"), so I finally ran a systematic audit checking every term in the dataset against the real entity matcher instead of waiting for the next one to surface by accident. It found 60 more instances beyond the ones already caught by hand; all fixed the same way (registering each term's own exact name as a lookup key). Worth rerunning that audit after any future large content merge, since it's cheap and nothing stops a new batch from reintroducing the same gap.
- **`insurance_terms.json` is a manually compiled and hand-edited dataset, not an official or verified source.** It started from scraped web content and has been reshaped, merged, and patched by hand many times over (see "The story so far" below) — which means it can contain inconsistencies, factual errors, or awkward phrasing that show up directly in the bot's responses, since nothing in the pipeline fact-checks the underlying content. Treat what the bot says as a starting point for learning the vocabulary, not an authoritative source — worth a proper review pass before this is trusted for anything beyond internal, informal learning.


---

## The story so far

### Building the actual glossary was half the project

Before any chatbot logic existed, there was a more basic problem: I needed a good dataset. I started from a raw dictionary of insurance terms (`dict_ins_terms.json`, just over a thousand `{term: definition}` pairs) and it was clean but *flat* — no categories, no way to know that "ACV" means the same thing as "Actual Cash Value," no examples, nothing linking related concepts together. This list was compiled from different insurance websites.

In order to have a good dictionary, created a script to normalize the collected data and changes done by hand, which helped build the `insurance_terms.json`, which became the real dataset going forward: every term now has an id, a resolved set of related terms (no more dangling references), and one solid example sentence each.
Of course, I am planning to coninue maintaining this dictionary.

### The RASA plan (python library), and hitting a wall

The original plan was to build this on **RASA**, a well-known Python framework for exactly this kind of intent/entity chatbot. Made sense on paper, but when I actually tried to set up the environment for it, hitted a real wall: RASA is pinned to Python <3.11, and my laptop runs Python 3.14. I didn't want to install an older Python version just to accommodate one library.

Rather than just find a workaround, I looked into *why* RASA was still stuck on old Python and found the real answer: Rasa Open Source is in **maintenance mode**. The company's active development has moved to a different, paid product (Rasa Pro) and a newer engine (CALM). Classic open-source RASA's last release pre-dates this project by over a year. That reframed the Python version mismatch from "too much trouble to install" into "do I really want to build a new project on a framework that's no longer actively developed?" I looked for other actively-maintained, Python-native alternatives that do the same or similar job (intent + entity + light dialogue management) — nothing real turned up. Everything else was either a different kind of tool entirely (open-domain chit-chat engines, not task-oriented bots) or effectively abandoned.   Maybe later I will consider Rasa Pro but not for now.

### Pivoting to a custom build

So the plan changed: build it myself, using **spaCy** for the NLP (Natural Language Processing) building blocks (mainly phrase/entity matching) and **rapidfuzz** for catching typos and near-misses, with the actual conversation logic — intent recognition, dialogue state, response wording — written by hand in plain Python. spaCy, unlike RASA, runs on Python 3.14 without any fuss. This also happens to serve the "get better at Python" goal better than filling out RASA's YAML configuration would have.

Not using RASA also meant losing its built-in dialogue management, so before writing any code I worked through what "conversational" actually needs to mean here. The honest realization: this bot needs continuity within a single Q&A exchange (so "give me an example" after asking about a term doesn't require repeating the term name, and an ambiguous typo can turn into a real "did you mean X or Y?" back-and-forth) — not deep multi-step branching flows, because there's nothing being collected or submitted here. That's a deliberate fitting and not a missing feature.

### Building the first working pieces

With the framework decided, the first real code went in: a data-loading layer that reads `insurance_terms.json` once and organizes it for fast lookup, and an entity-matching layer that scans whatever the user types and figures out which glossary term (if any) they mean.

Testing that matcher early caught something worth mentioning, because it's a good example of why you actually run the thing instead of just trusting that it *should* work: the typo-fallback matching was using a scoring method that gave short queries an unfairly easy time — "what is workers comp" was scoring a *perfect* match against a completely unrelated term, just because part of the sentence happened to line up with part of that term's name. Changing to a better-suited scoring method, and stripping filler words ("what is," "define," "tell me about") before doing the fuzzy comparison, fixed it. this was a good reminder that "the code runs without errors" and "the code gives good answers" are two very different bars to clear.

### Intent recognition, and why testing it will stay a real cost

`bot/nlu.py` answers "which term did they mean?" The next piece, `bot/intents.py`, answers the other half: "what do they actually want done with it?" — a definition, an example, a comparison between two terms, or one of a few conversational basics (greeting, help, goodbye). Since there's no RASA-style trained model anymore, this is hand-written: a priority-ordered list of regex patterns per intent, checked top to bottom, first match wins.

Working through it surfaced something worth stating plainly rather than discovering the hard way later: **this is the part of the project where testing will stay very very intensive** With a trained classifier, adding a new category mostly means adding more labeled examples. With hand-written rules, adding a new intent means checking it against *every existing intent's patterns* for overlap — a new pattern doesn't just need to fire for the phrasing it's meant for, it needs to not accidentally steal phrasing that used to belong to something else.

The mitigating factor is scope: this isn't an open-domain bot fielding phrasing from the general public, it's a fixed, narrow set of people asking about a fixed glossary — so the realistic range of phrasing is bounded, even if it doesn't feel that way while writing the regexes. Given that, the plan going forward is a growing table-driven regression suite (`tests/test_intents.py`) rather than trying to anticipate every phrasing up front.

### Response templates, and a grammar trap I almost walked into

With intents recognized, the next piece was turning them into actual reply text (`bot/responses.py`) — a few phrasings per intent, picked at random, so the bot doesn't answer with the exact same fill-in-the-blank sentence every time.

The one wrinkle worth recording: for `compare_terms`, my first instinct was a single flowing sentence — "X is `<definition of X, lowercased>`, while Y is `<definition of Y, lowercased>`."  So `compare_terms` presents both definitions as their own separate sentences instead — less clever, but correct for all 1,012 terms rather than most of them.

### The dispatcher: making it an actual conversation

Everything up to this point answered one narrow question in isolation — which term, which intent, what wording. The dispatcher (`bot/dispatcher.py`) is where those get wired into something that behaves like a single, continuous conversation rather than a series of unrelated lookups.

The main design question was how much of conversational plan to actually build now versus leave for later, and the honest answer turned out to be "all of it" — none of it is optional if the bot is meant to hold the kind of exchange pitched at the very top of this README ("what's a premium?" → "can you give me an example?" → "how's that different from replacement cost?"). So the dispatcher does three real things: it remembers the last term discussed so a follow-up like "give me an example" or "how's that different from Y" doesn't require repeating the term name; it decides what to do when nothing in the message resolves to a term at all (falling back cleanly rather than guessing wrong); and it turns a genuinely ambiguous fuzzy match into a real "did you mean X or Y?" question, tracked as pending state until the next message resolves it.

First scripted test for this is `tests/test_dispatcher.py`, and it passes against the real dataset.

### Growing the glossary: comparing and merging in 137 new terms

Insurance payment and premium terminology deserved its own dedicated pass, so I put together a separate batch of candidate terms (again, from different insurance websites) — things like `Loss Ratio`, `Risk Adjustment`, `Written Premium` — rather than trying to wedge them into the existing enrichment pipeline.

After filtering all the candidate terms, 137 terms were genuinely new. All terms got normalized into the existing structure first. The glossary now sits at **1,149 terms**.

### Making it personal: asking for a name, and a lot more phrasing variety

Up to this point the bot answered correctly, but it still felt like talking to a lookup tool rather than a conversation. So now, before anything else happens, it asks for your name — and every single reply for the rest of the session addresses you by it, starting with a randomized welcome message (one of ten variants, so two sessions don't open identically) and ending with a randomized goodbye when you type `quit`, not just when you say "bye" mid-conversation.

### Growing the glossary again: insurance documents, and a much lower yield than last time

Testing surfaced a real content gap: no entries at all for the *documents* insurance runs on — policy schedules, declarations pages, exclusions sections, that kind of thing. So I put together a second candidate batch focused specifically on that, the same way as the payment-terms batch before it.

From the 27 unique candidates, only **5 were genuinely new** (`General Conditions`, `Coverage Limits`, `Conditions Precedent`, `Claims Procedure`, `Per-Occurrence Limit`). Most of what got generated re-covered concepts the glossary already had, just reframed through a "documentation" lens rather than actually filling the gap.

The glossary now sits at **1,155 terms**.

### A whole new question shape: "what risks does X cover?"

Manual testing turned up something the bot genuinely couldn't do, not just a wrong answer: asking "what are the usual risks under life insurance" got back the generic definition of "Risk" itself, because every prior intent was built around either one term (definition, example) or two (compare) — never "list every term matching two conditions at once." Answering it properly meant a real, if small, new capability, not just another lookup key fix.

The data came first: a risk taxonomy — Mortality Risk, Collision Damage Risk, Cyber Risk, two dozen more, each tagged to a line of business — mostly wasn't usable as-is. One of the two source files was truncated (missing its closing bracket), a second file turned out to be a near-total duplicate of the first (four of its five entries were identical, and the fifth described the same concept as one in the first file under a *different* id — a good reminder that even within one afternoon's data-generation session, things drift). After sorting that out and checking for duplicates against the existing glossary the usual way, 23 of the source's 30 risk concepts were genuinely new.

The modeling question was how to represent "this is a risk, and it belongs to this line of business" without changing the data schema. The existing `categories` field already supports multiple tags per term, so a risk entry just gets two: its line of business (`Life`, `Auto`, …) and a new cross-cutting `Risk` tag. That's it — no new field, and it reuses a lookup helper (`by_category`) that was already sitting unused in the code from the original v1.5 planning. Answering "what risks does life insurance cover" is just "give me every term tagged both `Life` and `Risk`."

Getting there also meant recognizing the question in the first place, which came with its own trap: the natural pattern for "what are the risks under X" also matches "what is risk" — a completely different, single-term question that should still get the plain definition. Plural vs. singular ("risks" vs. "risk") turned out to be a cheap, reliable enough signal to tell those two apart, but only because I tested the bare singular case explicitly before considering this done — it's exactly the kind of thing that's obvious once caught and invisible until it is.

One of the merged terms also caused a real regression, worth calling out because it's such a specific kind of mistake: the source data gave "Workers' Compensation Injury Risk" the lookup phrase "workers comp" — accurate, but *too* accurate, since that phrase already meant something more general in the existing glossary and was previously (correctly) ambiguous between a few different results. Registering it as an exact match for one narrow new term silently took away that ambiguity instead of adding a new option to it. Caught immediately because the existing test suite already covered that exact ambiguous case — a good example of why the regression suite pays for itself on features that have nothing to do with what it was originally written for.

### Full category browsing, not just risks

`list_risks` only ever answered a narrow slice of "browse by category" — risk-tagged terms within a line of business. Added `list_terms` alongside it for the general case ("show me all Auto terms"), reusing the same domain-resolution logic and the already-existing `by_category()` lookup. Large categories (some run past 300 terms) get capped in the reply with the real total always shown, rather than either dumping everything or silently hiding how much more there is.

### Quiz mode, and reusing the matcher to check answers

The last piece of "v1.5" was a quiz mode — the bot gives a definition, you guess the term. The interesting design question wasn't the quiz itself so much as how to check an answer without building new NLP for it: a guess is just text, and I already had something that turns text into a term id — the same entity matcher used for every normal question. So checking an answer is just running the guess through that matcher and seeing if it lands on the right term, typos and all, for free.

Quiz mode also had to behave differently from everything before it: once it's running, *every* message is either an answer attempt or "stop quiz," not a normal question. Asking "what is a deductible" mid-quiz should be treated as a (wrong) guess, not answered normally — a real behavioral mode switch, not just another intent in the list. `quiz me on Auto terms` scopes a whole session to one category, reusing the same domain-resolution built for `list_risks`/`list_terms` earlier.

Manual testing afterward caught something unrelated but real: asking for more examples of the same term kept giving back the exact same sentence, just reworded around it, even though every term ships with 5. Turned out the code always used the first of the 5, and only the wrapper phrasing was ever randomized. Fixed by picking the example itself at random too — and while checking that, a quick audit of every other template list turned up two more of the same shape of mistake (one reply that could drop the total count, one quiz reply that could skip naming which term was correct), caught only because a specific random phrasing had to come up to notice. Both fixed the same way: pick the wording at random, but never let a specific choice silently omit real information.
