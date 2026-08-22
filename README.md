# Insurance Terminology Chatbot - v1.0

A little chatbot that came to my mind to help coworkers, or people in general, who aren't insurance people — developers, architects, testers, anyone who joins a project and suddenly has to deal with terms like "ALAE" or "IBNR reserves" — actually understand the vocabulary without having to bug someone or dig through a PDF glossary. It's also, honestly, my excuse to get more comfortable with Python.

This README tells the story of the project as it happens: why it exists, what's been built, what got in the way, and what's still ahead. I'll keep updating it as we go, so it doubles as a running log, not just a static description.

---

## Why this exists

I kept noticing the same pattern: someone new joins a project that touches insurance, and half of onboarding turns into "what does that word mean?" moments — asked in Teams, answered inconsistently, and never written down anywhere useful. A searchable glossary already helps, but a chatbot that can hold a small conversation ("what's a premium?" → "can you give me an example?" → "how's that different from replacement cost?") is a much nicer way to actually learn the terms rather than just look them up once and forget them.

## Scope — what this is, and what it deliberately isn't

**It is:** an internal learning tool for coworkers or any other people with no insurance background. You ask about a term, it explains it, gives you an example, tells you what's related, maybe quizzes you later.

**It is not:** a customer-facing or policyholder-facing bot. There's no account access, no claims lookup, no policy data, no PII of any kind — it only ever talks about the *glossary*, never about a real person's insurance. That boundary matters enough that it shaped actual design decisions (see the intent list further down), and it's worth keeping in mind if this ever gets extended later — the temptation to bolt on "check my claim status" should be resisted, because that's a completely different (and much more sensitive) kind of project.

Secondary, smaller goal: I'm using this as a way to practice writing real Python, not just toy scripts.

---

## The story so far

### Building the actual glossary was half the project

Before any chatbot logic existed, there was a more basic problem: I needed a good dataset. I started from a raw dictionary of insurance terms (`dicc_ins_terms.json`, just over a thousand `{term: definition}` pairs) and it was clean but *flat* — no categories, no way to know that "ACV" means the same thing as "Actual Cash Value," no examples, nothing linking related concepts together.

So I wrote a rule-based enrichment script to bolt those things on: pull abbreviations out of parenthetical term names, tag each term with a category based on keyword matching, scan definitions for mentions of other glossary terms to build "related terms" links, and guess a rough difficulty level. That worked, but the first pass was noisy — almost everything ended up "related to" the same handful of generic words like "Insurance" or "Claim," because those words show up in nearly every definition. Filtering out overly-common single words (while keeping meaningful multi-word phrases) fixed most of that.

The enrichment script left "examples" empty, though — writing a good, natural example sentence for over a thousand terms isn't really something you can rule-base your way through. That got done by hand instead, as part of building `insurance_terms.json`, which became the real dataset going forward: every term now has an id, a resolved set of related terms (no more dangling references), and one solid example sentence each. Building that file surfaced its own small mess — a handful of terms that collided on the same lookup phrase, and a few pairs of terms that turned out to be true duplicates (ALAE, HMO, and IBNR each had this problem) — both got cleaned up and re-validated before moving on. It sounds like a small detail, but a duplicate or an ambiguous lookup key is exactly the kind of thing that causes a chatbot to give a confusing answer down the line, so it was worth getting right early.
Of course, I am planning to coninue maintaining this dictionary.

### The RASA plan (python library), and hitting a wall

The original plan was to build this on **RASA**, a well-known Python framework for exactly this kind of intent/entity chatbot. Made sense on paper. Then I actually tried to set up the environment for it and hit a real wall: RASA is pinned to Python <3.11, and my laptop runs Python 3.14. I didn't want to install an older Python version just to accommodate one library.

Rather than just find a workaround, I looked into *why* RASA was still stuck on old Python — and found the real answer: Rasa Open Source is in **maintenance mode**. The company's active development has moved to a different, paid product (Rasa Pro) and a newer engine (CALM). Classic open-source RASA's last release pre-dates this project by over a year. That reframed the Python version mismatch from "annoying installation detail" into "do I really want to build a new project on a framework that's no longer actively developed?" I looked for other actively-maintained, Python-native alternatives that do the same job (intent + entity + light dialogue management) — nothing real turned up. Everything else was either a different kind of tool entirely (open-domain chit-chat engines, not task-oriented bots) or effectively abandoned.   Maybe later I will consider Rasa Pro but not for now.

### Pivoting to a custom build

So the plan changed: build it myself, using **spaCy** for the NLP building blocks (mainly phrase/entity matching) and **rapidfuzz** for catching typos and near-misses, with the actual conversation logic — intent recognition, dialogue state, response wording — written by hand in plain Python. spaCy, unlike RASA, runs on Python 3.14 without any fuss. This also happens to serve the "get better at Python" goal better than filling out RASA's YAML configuration would have.

Losing RASA also meant losing its built-in dialogue management, so before writing any code I worked through what "conversational" actually needs to mean here. The honest answer: this bot needs continuity within a single Q&A exchange (so "give me an example" after asking about a term doesn't require repeating the term name, and an ambiguous typo can turn into a real "did you mean X or Y?" back-and-forth) — not deep multi-step branching flows, because there's nothing being collected or submitted here. That's a deliberate right-sizing, not a missing feature.

### Building the first working pieces

With the framework decided, the first real code went in: a data-loading layer that reads `insurance_terms.json` once and organizes it for fast lookup, and an entity-matching layer that scans whatever the user types and figures out which glossary term (if any) they mean.

Testing that matcher early caught something worth mentioning, because it's a good example of why you actually run the thing instead of just trusting that it *should* work: the typo-fallback matching was using a scoring method that gave short queries an unfairly easy time — "what is workers comp" was scoring a *perfect* match against a completely unrelated term, just because part of the sentence happened to line up with part of that term's name. Swapping to a better-suited scoring method, and stripping filler words ("what is," "define," "tell me about") before doing the fuzzy comparison, fixed it. Good reminder that "the code runs without errors" and "the code gives good answers" are two very different bars to clear.

### Intent recognition, and why testing it will stay a real cost

`bot/nlu.py` answers "which term did they mean?" The next piece, `bot/intents.py`, answers the other half: "what do they actually want done with it?" — a definition, an example, a comparison between two terms, or one of a few conversational basics (greeting, help, goodbye). Since there's no RASA-style trained model anymore, this is hand-written: a priority-ordered list of regex patterns per intent, checked top to bottom, first match wins.

Working through it surfaced something worth stating plainly rather than discovering the hard way later: **this is the part of the project where testing will stay genuinely effortful, not a one-time cost.** With a trained classifier, adding a new category mostly means adding more labeled examples. With hand-written rules, adding a new intent means checking it against *every existing intent's patterns* for overlap — a new pattern doesn't just need to fire for the phrasing it's meant for, it needs to not accidentally steal phrasing that used to belong to something else. That's exactly what happened while building the first version: "what's the difference between X and Y" has to be checked as `compare_terms` *before* the much broader "what's" pattern for `ask_definition` gets a chance to claim it, or it never would.

The mitigating factor is scope: this isn't an open-domain bot fielding phrasing from the general public, it's a fixed, narrow set of people asking about a fixed glossary — so the realistic range of phrasing is bounded, even if it doesn't feel that way while writing the regexes. Given that, the plan going forward is a growing table-driven regression suite (`tests/test_intents.py`) rather than trying to anticipate every phrasing up front: cheap to add one line to, and the whole thing gets re-run every time the pattern list changes, so a new intent's collisions with old ones show up immediately instead of silently in production. If pattern collisions ever get genuinely unmanageable despite that, the honest fallback is a small trained classifier instead of hand-written regex — but that reintroduces real complexity, so it's not worth reaching for pre-emptively.

### Response templates, and a grammar trap I almost walked into

With intents recognized, the next piece was turning them into actual reply text (`bot/responses.py`) — a few phrasings per intent, picked at random, so the bot doesn't answer with the exact same fill-in-the-blank sentence every time.

The one wrinkle worth recording: for `compare_terms`, my first instinct was a single flowing sentence — "X is `<definition of X, lowercased>`, while Y is `<definition of Y, lowercased>`." Before committing to that, I pulled a random sample of definitions straight from `insurance_terms.json` to sanity-check it, and the phrasing turned out to be far less consistent than I'd assumed — some are noun phrases ("Coverage for property under construction"), some already read as sentence continuations ("refers to the primary business type under which..."). Splicing that second kind into "X is refers to the primary business type..." is just broken grammar. So `compare_terms` presents both definitions as their own separate sentences instead — less clever, but correct for all 1,012 terms rather than most of them.

### The dispatcher: making it an actual conversation

Everything up to this point answered one narrow question in isolation — which term, which intent, what wording. The dispatcher (`bot/dispatcher.py`) is where those get wired into something that behaves like a single, continuous conversation rather than a series of unrelated lookups.

The main design question was how much of §2.11's conversational plan to actually build now versus leave for later, and the honest answer turned out to be "all of it" — none of it is optional if the bot is meant to hold the kind of exchange pitched at the very top of this README ("what's a premium?" → "can you give me an example?" → "how's that different from replacement cost?"). So the dispatcher does three real things: it remembers the last term discussed so a follow-up like "give me an example" or "how's that different from Y" doesn't require repeating the term name; it decides what to do when nothing in the message resolves to a term at all (falling back cleanly rather than guessing wrong); and it turns a genuinely ambiguous fuzzy match into a real "did you mean X or Y?" question, tracked as pending state until the next message resolves it.

That last piece is where testing caught a real bug before it shipped. Once the bot has asked "did you mean X or Y?", a natural reply is something like "the first one" — and it turns out that phrase is exactly the kind of short, generic text the fuzzy matcher can accidentally match against some unrelated glossary term on its own. My first version only checked "did this answer the pending question" when the entity matcher found *nothing* — so that accidental fuzzy match silently won, and the bot answered a completely different, unrelated question instead of the one it had just asked. The fix was ordering: an open "did you mean" question now gets first right of interpretation over anything the entity matcher guesses on its own, not just when the matcher comes up empty.

With that fixed, the pitch at the top of this README is no longer aspirational — it's the first scripted test in `tests/test_dispatcher.py`, and it passes against the real dataset.

### More examples per term, and a templated filler I had to catch

Every term went from one example sentence to five. Good idea in principle — more variety, less chance of the same answer feeling stale — but checking the actual output caught a real problem before it went further: two of the four new template slots were pasting the raw definition text straight into the "example," verbatim. For an average term that's just redundant filler; for the handful of unusually long, dense definitions flagged earlier as a known limitation, it made things actively worse — the "example" ended up longer and denser than the definition itself. There was also a small grammar bug riding along in the same template ("in a auto file" instead of "in an auto file," missing article agreement for a couple of categories).

Fixed by replacing those two specific templates with ones that don't repeat content, and by computing the article correctly. Small thing, but a good reminder that "more content" and "better content" aren't automatically the same thing — worth actually reading the output, not just checking that the field got populated.

### Growing the glossary: comparing and merging in 137 new terms

Insurance payment and premium terminology deserved its own dedicated pass, so I put together a separate batch of candidate terms — things like `Loss Ratio`, `Risk Adjustment`, `Written Premium` — rather than trying to wedge them into the existing enrichment pipeline.

Before merging anything in, the obvious first step was checking for duplicates, and it's a good thing I did: the new batch had 19 internal duplicates (the same term appearing twice within its own file), plus 55 terms that already existed in the glossary under the same name, plus another 71 that collided on a lookup phrase even though the id or name looked different. One of those was `IBNR` colliding with the exact same term that had already been carefully deduplicated once before, months earlier — a good reminder that "we fixed this duplicate" doesn't mean "this duplicate can never come back," if new content gets added later without checking against what's already there.

After filtering all of that out, 137 terms were genuinely new. Merging them in wasn't just a matter of appending — the new batch used a slightly different schema (different category names, a three-tier difficulty scale instead of the existing two-tier one, related-terms as plain names instead of resolved ids), so all of that got normalized into the existing structure first. The glossary now sits at **1,149 terms**.

### Growth exposed a real matcher bug

Right after merging, a quick round of live testing on some of the new terms turned up something genuinely wrong: asking about "risk adjustment" answered about "Risk" instead — a much more generic, pre-existing term that happens to be a literal substring of the one actually being asked about. Same thing happened comparing "loss ratio" against "combined ratio" — the bot compared "Loss" against "Loss Ratio," dropping the second term entirely.

This turned out not to be a new bug at all — "Risk" and "Loss" have been standalone entries since the very first version of the glossary. The entity matcher was always capable of finding multiple overlapping matches in one phrase, but never had any logic to prefer the longer, more specific one over a shorter one buried inside it — it just used whichever the matching library handed back first. It had simply never been exercised before, because no phrasing tested up to this point happened to combine a longer term with a shorter one contained inside it. Adding 137 new terms — many of them short, common-word compounds like "Risk Adjustment" and "Loss Reserve" — made that gap much more likely to actually get hit.

The fix was small: when multiple exact matches overlap, keep only the longest one. spaCy has a utility built for exactly this. Re-tested both broken cases, plus a known pre-existing example ("absolute liability," which has the same contains-a-shorter-word shape) — all correct now, and it's locked in with a dedicated test file, `tests/test_nlu.py`.

### Making it personal: asking for a name, and a lot more phrasing variety

Up to this point the bot answered correctly, but it still felt like talking to a lookup tool rather than a conversation. So now, before anything else happens, it asks for your name — and every single reply for the rest of the session addresses you by it, starting with a randomized welcome message (one of ten variants, so two sessions don't open identically) and ending with a randomized goodbye when you type `quit`, not just when you say "bye" mid-conversation.

Doing that properly meant going back through every response template and roughly tripling how many phrasings each intent has, since 2-3 variants per intent — which felt fine before — turned out to read as repetitive the moment every single reply also had a name stitched into it in the same spot every time. So the name's position moves around too: sometimes opening the sentence, sometimes closing it, sometimes a mid-message aside ("Good question, Paco...").

That rewrite surfaced a genuinely funny bug: a couple of the new templates continue the sentence right after the definition with no line break ("...basis. Hope that helps, Paco."), and since almost every definition in the glossary already ends in its own period, the naive version produced a doubled period — "...basis.. Hope that helps." Fixed by stripping the definition's own trailing period specifically for those two templates, and locked in with a test that checks for it directly, since it's exactly the kind of small thing that's easy to eyeball right past.

### Growing the glossary again: insurance documents, and a much lower yield than last time

Testing surfaced a real content gap: no entries at all for the *documents* insurance runs on — policy schedules, declarations pages, exclusions sections, that kind of thing. So I put together a second candidate batch focused specifically on that, the same way as the payment-terms batch before it.

The duplicate-check process was the same, but the result was strikingly different: of 27 unique candidates, only **5 were genuinely new** (`General Conditions`, `Coverage Limits`, `Conditions Precedent`, `Claims Procedure`, `Per-Occurrence Limit`) — versus 137 out of 200 last time. Most of what got generated re-covered concepts the glossary already had, just reframed through a "documentation" lens rather than actually filling the gap. Worth remembering for next time: a low yield on a targeted batch is itself useful information, not just a disappointing result — it can mean the gap is smaller than it looked, or that the generation prompt needs to be more specific about what's actually missing.

One of the 5 new terms — `Insurance Documentation` as a category — didn't fit anywhere in the existing 14-category list, so rather than force it into an ill-fitting bucket, it became a genuine 15th category. That's exactly the kind of gap this batch was meant to close.

A sixth term, `Policy Cover`, had been excluded from that first pass — not because it duplicated anything, but because its lookup phrase happened to be the single word "coverage," which was already spoken for by an existing, unrelated generic entry. Once that was pointed out, fixing it was simple: give it a lookup key that doesn't collide (`"policy cover"` instead of `"coverage"`), and it's a perfectly good, distinct entry. I went back and checked whether any of the other excluded candidates had the same shape — a real, distinct concept blocked only by an unlucky shared word — and found three more that were *close* but turned out to be true duplicates once I actually compared definitions (`Co-Insurance`, `Policy Schedule`, and a second `Actual Cash Value` entry all described concepts the glossary already covers, just under different wording), so those stayed out.

That check did catch something else worth fixing, though: asking the bot about "policy schedule" or "co-insurance" — both real phrases someone might actually type — was silently answering about the wrong thing entirely (the bare word "policy" and the bare word "insurance," respectively), because neither the existing `Declarations Page` nor `Coinsurance` entries had ever been taught those phrasings. Added them as extra lookup keys on the existing entries rather than creating new, duplicate ones. The glossary now sits at **1,155 terms**.

### A whole new question shape: "what risks does X cover?"

Manual testing turned up something the bot genuinely couldn't do, not just a wrong answer: asking "what are the usual risks under life insurance" got back the generic definition of "Risk" itself, because every prior intent was built around either one term (definition, example) or two (compare) — never "list every term matching two conditions at once." Answering it properly meant a real, if small, new capability, not just another lookup key fix.

The data came first: a risk taxonomy — Mortality Risk, Collision Damage Risk, Cyber Risk, two dozen more, each tagged to a line of business — mostly wasn't usable as-is. One of the two source files was truncated (missing its closing bracket), a second file turned out to be a near-total duplicate of the first (four of its five entries were identical, and the fifth described the same concept as one in the first file under a *different* id — a good reminder that even within one afternoon's data-generation session, things drift). After sorting that out and checking for duplicates against the existing glossary the usual way, 23 of the source's 30 risk concepts were genuinely new.

The modeling question was how to represent "this is a risk, and it belongs to this line of business" without changing the data schema. The existing `categories` field already supports multiple tags per term, so a risk entry just gets two: its line of business (`Life`, `Auto`, …) and a new cross-cutting `Risk` tag. That's it — no new field, and it reuses a lookup helper (`by_category`) that was already sitting unused in the code from the original v1.5 planning. Answering "what risks does life insurance cover" is just "give me every term tagged both `Life` and `Risk`."

Getting there also meant recognizing the question in the first place, which came with its own trap: the natural pattern for "what are the risks under X" also matches "what is risk" — a completely different, single-term question that should still get the plain definition. Plural vs. singular ("risks" vs. "risk") turned out to be a cheap, reliable enough signal to tell those two apart, but only because I tested the bare singular case explicitly before considering this done — it's exactly the kind of thing that's obvious once caught and invisible until it is.

One of the merged terms also caused a real regression, worth calling out because it's such a specific kind of mistake: the source data gave "Workers' Compensation Injury Risk" the lookup phrase "workers comp" — accurate, but *too* accurate, since that phrase already meant something more general in the existing glossary and was previously (correctly) ambiguous between a few different results. Registering it as an exact match for one narrow new term silently took away that ambiguity instead of adding a new option to it. Caught immediately because the existing test suite already covered that exact ambiguous case — a good example of why the regression suite pays for itself on features that have nothing to do with what it was originally written for.

---

## Current status

Data is done (for the moment). Architecture is decided. The core conversation loop works end to end:

- The dataset (`insurance_terms.json`) now holds **1,178 terms** across **16 categories**, each with 5 example sentences, validated and ready to build against.
- The entity-matching layer (figuring out *which term* someone means) is built and tested, including preferring the longest match when phrases overlap.
- The intent-recognition layer (figuring out *what they want* — a definition, an example, a comparison, a list of risks for a line of business, etc.) is built and tested.
- Response templates (turning a term + intent into actual reply text) are built and tested, with real phrasing variety and every reply personalized by name.
- The dispatcher — the piece that ties all of the above into one real, multi-turn conversation, including follow-ups and "did you mean X or Y?" disambiguation — is built and tested against the real dataset.

In other words: `python paco_chatbot.py` now opens by asking your name and greeting you personally, then holds an actual (if bare-bones) conversation from there — not just a component demo. What's left is mostly about making the experience richer and getting it in front of people — see "What's next" below.

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
    ├── test_dispatcher.py        # multi-turn regression tests for bot/dispatcher.py
    └── test_nlu.py               # regression tests for bot/nlu.py
```

### File by file

**`insurance_terms.json`** — The knowledge base. 1,178 insurance terms across 16 categories (including a cross-cutting `Risk` tag, alongside line-of-business categories like `Life`/`Auto`/`Health`), each with an id, definition, five example sentences, categories, a difficulty rating, related-term links, and every phrase/abbreviation ("premium," "workers comp," etc.) someone might use to refer to it. This is the only data file the bot actually needs; everything else was intermediate work to produce it.

**`bot/data.py`** — Reads `insurance_terms.json` off disk exactly once and reshapes it into a `TermStore`: proper Python objects instead of raw dict/JSON, plus an index mapping every possible phrase a user might type straight to the term it belongs to. `by_category()`/`by_categories()` filter terms by one or more category tags (e.g. "Life" + "Risk" together), used for browsing-style questions. Every other module goes through this one to get at the glossary — nothing else touches the JSON file directly.

**`bot/nlu.py`** — Short for "natural language understanding," though really it does one specific job: given a raw message, which glossary term(s) is it about? Two layers: an exact match against known phrases (using spaCy's `PhraseMatcher`, keeping the longest match when phrases overlap), and — only if that comes up empty — a fuzzy, typo-tolerant guess (using `rapidfuzz`) with some extra logic to keep that guess from getting fooled by short or filler-heavy sentences.

**`bot/state.py`** — A small object representing one user's ongoing conversation: their name (captured once at the start of the session), what term was last discussed, what the last thing they asked for was, and whether the bot is mid-way through asking "did you mean X or Y?" This is what makes both personalized replies and follow-up questions possible without the user repeating themselves.

**`bot/intents.py`** — Defines the fixed list of things a user can be trying to do (`ask_definition`, `ask_example`, `list_categories`, `list_risks`, `compare_terms`, plus conversational basics like greeting/help/goodbye, and a fallback for "I don't know what you mean") and `recognize_intent()`, which classifies a raw message into one of them using priority-ordered regex patterns. A bare term with no question wrapped around it comes back as `fallback` on purpose — promoting that to `ask_definition` needs the entity-match result too, which only the dispatcher will have.

**`bot/responses.py`** — Turns "this term, with this intent" into an actual reply sentence via `render()`, with 5-8 phrasings per intent (picked at random, with the user's name woven in at a different spot each time) so answers don't feel robotic. Also handles the two intents that need more than just a term (comparing two terms side by side, listing categories), and `render_welcome()` for the randomized session-opening greeting.

**`bot/dispatcher.py`** — The conductor. Every incoming message flows through `Dispatcher.process_turn()`: recognize the intent, resolve the term (falling back to the last-discussed term for follow-ups, or asking "did you mean X or Y?" when the match is genuinely ambiguous), render a reply, update the conversation state for next time. Also resolves a line-of-business "domain" from free text (e.g. "life insurance" → the `Life` category) for `list_risks` questions, since that's not something the term-focused entity matcher handles.

**`paco_chatbot.py`** — A command-line REPL that asks your name, shows a personalized welcome message, then talks to the real `Dispatcher` for the rest of the session — this is the actual way to have a conversation with the bot today (or it'll get replaced by a proper interface later — see "What's next").

---

## Getting started (as it exists today)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python paco_chatbot.py
```

It'll ask your name first. After that, ask it something like `what's a premium?`, then follow up with `give me an example` or `how's that different from replacement cost?` without repeating the term name — that continuity is the whole point of the dispatcher. Type `quit` to exit (you'll get a goodbye message too).

---

## What's next

1. **More testing, as it grows** — keep extending `tests/` with misspelled and casually-worded questions as new intents/features get added, since the whole point is that the audience doesn't already know the "correct" insurance vocabulary to type.
2. **"v1.5" features**, once the basics work — the data already supports all of this via the `categories`/`difficulty` fields already in `insurance_terms.json`:
   - ~~**Browsing by category**~~ — done, as `list_risks` ("what risks does X cover?"), which turned out to be the first real use of category-intersection browsing. A more general "show me all Auto terms" (not just the risk-tagged ones) would reuse the same `by_categories()` machinery.
   - **A quiz mode** — testing recall instead of just answering lookups.
   - **Difficulty-aware onboarding** — using the `difficulty` field (Basic/Technical) to guide what a newcomer sees first, easiest terms before the dense ones.
3. **Actually shipping it somewhere people can use it** — still an open question: a simple web/REST interface, or a Teams bot? Affects how replies should be shaped (plain text vs. something richer).
4. **A Spanish translation of the dictionary.** English isn't everyone's first language on the team (mine included), so I plan to translate `insurance_terms.json` into Spanish as its own language variant, not just a machine-translated afterthought.
5. **Asking the session's language up front.** Once a Spanish dictionary exists, the bot should ask at the start of a session which language to use, and answer consistently in that language for the rest of the conversation.

## Known limitations (being upfront about these)

- Categories and difficulty ratings are rule-based guesses, not reviewed by an actual insurance expert — good enough to build on, not something to present as authoritative without a spot-check. This applies doubly to the 137 payment-related terms merged in later: their categories and difficulty levels were machine-remapped from a different labeling scheme onto the existing one (e.g. a three-tier difficulty scale folded down into the existing two-tier one), which is an extra layer of approximation on top of the original guesswork.
- About half the glossary terms have no "related terms" suggestions — mostly because their definitions genuinely don't reference another glossary term, not a bug, just a ceiling on how much "see also" richness is possible without a smarter (e.g. embedding-based) approach.
- A few near-duplicate glossary entries were found and merged (ALAE, HMO, IBNR), but that was only because they happened to collide on the same lookup phrase — there could be other duplicates out there using different wording that haven't been caught yet.
- **33 terms (about 3%) have unusually long, dense definitions** — multi-sentence passages several times the median length (e.g. "Liability" runs 716 characters, versus a ~110-character median across the glossary). The bot currently just passes these through as-is, so an answer for one of these terms will read noticeably denser than a typical one. Not fixed for now — worth a future pass to shorten these for chat, or to show the short version first with a "want the full definition?" follow-up.
- **Comparing two terms when one of them is misspelled doesn't work as well as it should.** The entity matcher only reaches for its typo-tolerant fuzzy matching when it finds *zero* exact matches in the whole message — so if one of the two terms in "compare premiums and workres comp" matches exactly, the matcher never even attempts to fuzzy-match the misspelled second one, and the dispatcher ends up one term short. Correctly spelled comparisons, and comparisons that lean on the last-discussed term ("how's that different from Y"), both work fine — it's specifically the "two terms, one of them typo'd, both new to this message" case that's weaker than it should be.
- **A phrase that was never explicitly taught to the matcher can silently resolve to the wrong, much more generic term**, rather than failing loudly. This is different from the "shorter term wins" bug above (which was about *ordering* between two registered phrases) — this is about a phrase not being registered *at all*, but happening to contain a shorter word that is. Found three times so far ("policy schedule" answering about "Policy," "co-insurance" answering about "Insurance," and a too-generic "workers comp" lookup key silently taking over an existing ambiguous case) and fixed each time by adding/adjusting a lookup key — but there's no way to know how many more of these are lurking until someone happens to type the phrase. Worth keeping an eye out for as the glossary keeps growing, especially with short, common-word-containing terms.
- **`list_risks` only covers 8 of the 16 categories** — Auto, Financial Lines & Surety, Health, Liability, Life, Marine & Aviation, Property, and Workers Compensation have at least one risk-type entry; the rest (Claims, Reinsurance, Regulatory & Legal, Underwriting & Actuarial, Financial / Accounting, General Insurance Concepts, Insurance Documentation) don't yet. Asking about one of those correctly says so and lists what *is* available, rather than pretending to have an answer — but it's a real content gap, not a code limitation.
