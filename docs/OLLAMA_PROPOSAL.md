# Proposal: Ollama as a local LLM for the chat

Status: CLI side implemented 2026-10-21 (`bot/llm.py`, `bot/rag.py`, dispatcher wiring, tests). API wiring and docs still to do. Ollama is already installed on my laptop and the model is `qwen2.5-coder:7b`, so the setup part is done. The code is what's left.

## Where we are today

The bot has no LLM. It's fully rule-based:

- `bot/intents.py` picks the intent with regex.
- `bot/nlu.py` finds glossary terms (spaCy PhraseMatcher, rapidfuzz as fallback).
- `bot/responses.py` fills canned templates.
- `bot/dispatcher.py` ties it together in `process_turn()`.
- `ins_chatbot_api` wraps the dispatcher in FastAPI (`/session`, `/chat`).

So Ollama is a new layer on top, not a swap of an existing model.

## Decisions made

| Question | Answer |
|---|---|
| What does the LLM do? | RAG-style answers: rules find the terms, Ollama writes the answer from them |
| Model | `qwen2.5-coder:7b` (7B, already pulled on my laptop). Final, not up for comparison |
| Scope | Local only, off by default |
| Streaming | No, full reply, same `/chat` contract |

## How a turn would work

The rules keep control of the flow. Quiz mode, disambiguation, `list_terms`, `list_risks` and the "want the full definition?" follow-up stay rule-based. They're deterministic and a 7B model would still make them worse.

Ollama only handles the content questions: `ASK_DEFINITION`, `ASK_EXAMPLE`, `COMPARE_TERMS` and `FALLBACK`.

1. `EntityMatcher` finds the term(s), same as now. On `FALLBACK`, take the top fuzzy hits instead.
2. A retrieval step collects context per term: definition, examples, related terms, category.
3. `bot/llm.py` sends a prompt to Ollama. The system prompt says:
   - answer only from the glossary context provided
   - plain language, for coworkers with no insurance background
   - say "I don't have that term" if the context doesn't cover it
   - use the user's name and the `is_newcomer` flag for tone
4. The reply comes back as plain text.
5. If Ollama is off, down or times out, fall back to the current template reply. The bot never breaks because of the LLM.

## Changes

| File | Change |
|---|---|
| `ins_chatbot/bot/llm.py` (new) | `OllamaClient` with `generate(...) -> str`, timeout and error handling |
| `ins_chatbot/bot/rag.py` (new) | Builds the context block and prompt from `Term` objects |
| `ins_chatbot/bot/dispatcher.py` | Optional `llm` argument in `__init__`. In `_handle_single_term_intent` and `_handle_compare`, try the LLM first, fall back to `_render()` on failure |
| `ins_chatbot/bot/state.py` | Probably nothing. Chat history for the LLM is optional, skip for v1 |
| `ins_chatbot/paco_chatbot.py` | Build the client if enabled and pass it to `Dispatcher` (CLI) |
| `ins_chatbot_api/app/api_ins_chatbot.py` | Build the client in `lifespan` only if `USE_OLLAMA=true` |
| `ins_chatbot_api/.env`, `.env.example` | `USE_OLLAMA`, `OLLAMA_HOST` (default `http://localhost:11434`), `OLLAMA_MODEL=qwen2.5-coder:7b` |
| `requirements.txt` (both projects) | `httpx` or the `ollama` package |
| `tests/test_llm.py`, `tests/test_rag.py` (new), `tests/test_dispatcher.py` | Mock Ollama. Cover the fallback-on-failure path and that the prompt only contains glossary context |
| `README.md`, `docs/TECHNICAL.md` | Short "run with Ollama" section |

No changes needed in `ins_chatbot_web`, since the response shape stays the same.

## Local setup

Ollama and the model are already installed here. Quick check that it's alive:

```
ollama list                          # qwen2.5-coder:7b should show up
ollama run qwen2.5-coder:7b "hi"     # sanity test
curl http://localhost:11434/api/tags # what the app will talk to
```

If `ollama serve` isn't running, start it (the desktop app usually does it for you). On a fresh machine it's `brew install ollama` and `ollama pull qwen2.5-coder:7b`.

Then set `USE_OLLAMA=true` in the API's `.env`.

## The JSON glossary stays the source of truth

`bot/insurance_terms.json` (loaded by `bot/data.py` into the `TermStore`) is still the only place the bot gets insurance knowledge from. Ollama doesn't replace it, it just rewrites what's in it.

- The model never answers from its own memory. `bot/rag.py` pulls the matched `Term` objects out of the store and pastes their definition, examples, related terms and category into the prompt.
- The system prompt tells the model to use only that block. No match in the glossary means "I don't have that term", not a guess.
- Fixing or adding a term means editing the JSON, nothing else. Both the template replies and the LLM replies pick it up.
- No second copy of the data, no vector DB, no embeddings for v1. The existing spaCy/rapidfuzz matching is the retrieval step.

This also ties to the data quality risk below: the LLM is only as good as the JSON, so checking definitions against a real source is still worth doing.

## What happens in production (no Ollama)

The deployed web version keeps working exactly as today. Three things make that true:

- `USE_OLLAMA` defaults to off. If Render/Vercel never set it, the API doesn't build an `OllamaClient`, the dispatcher gets `llm=None`, and every reply comes from the templates.
- The response shape of `/chat` doesn't change, so `ins_chatbot_web` needs nothing.
- Even with the flag on, any failure (connection refused, timeout) falls back to the template reply.

Two things to watch when we build it:

- Don't let anything import or connect to Ollama at startup unless the flag is on. A missing server must never crash the app.
- If someone turns the flag on in production by mistake, every request would wait for the timeout before falling back. Use a short connect timeout, and check Ollama once in `lifespan`: if it's not reachable, run without the LLM.

A test should cover this: build the dispatcher with `llm=None` and check the replies match the current ones.

## Risks

- **Model fit.** `qwen2.5-coder` is tuned for code, so the tone may come out a bit technical. Decision: we stay with it, since the bot runs locally with Ollama anyway. If the tone bothers us we tweak the system prompt first.
- **Drift.** Even at 7B the model can wander off the context. The strict prompt helps. A cheap extra check is to confirm the reply mentions the matched term, otherwise use the template reply.
- **Data quality.** Most definitions were rewritten with Claude and not verified against a source (see `handoff.md`). The LLM would repeat any mistakes there, probably with more confidence.
- **Latency.** A 7B model is slower than the 3B we first planned. Expect a few seconds per reply, more on the first call while the model loads into memory. The web UI should show a "thinking" state, and the timeout in `OllamaClient` needs to be generous enough for that first call.
- **Deployment.** Render can't reach an Ollama running on a laptop. The deployed version keeps working as today, with no LLM, because the flag is off by default.

## Out of scope for now

- Streaming replies
- Hosting Ollama for the Render/Vercel deployment
- LLM-driven intent detection or replacing the quiz/list flows
- Multi-turn chat history passed to the model

## Why `qwen2.5-coder:7b` and not `llama3.2` (3B)

We started with `llama3.2` mostly because it's small. Then we compared them for this bot:

| | `llama3.2` 3B | `qwen2.5-coder:7b` |
|---|---|---|
| Size on disk | ~2 GB | ~4.7 GB |
| RAM to run | ~3-4 GB | ~6-8 GB |
| Speed on a laptop | faster | slower, first call is the slowest |
| Sticking to the glossary context | okay, drifts more | better |
| Tone | friendlier, general chat | can sound technical, fix with the system prompt |

Not clearly better either way, so we keep the one already installed. If replies feel too slow once it's built, `llama3.2` is a one-line change to `OLLAMA_MODEL` (and an `ollama pull llama3.2`). Sizes are from memory, `ollama list` shows the real ones.

## Where we left off (2026-10-18)

- Proposal is up to date. Nothing implemented.
- Decided: model is `qwen2.5-coder:7b`, JSON glossary stays the source of truth, production runs without Ollama (flag off, template fallback).
- Next: go through the design questions, then start with `bot/llm.py` and `bot/rag.py`, with the tests next to them.

## Possible later

- Swapping the model later is only an `OLLAMA_MODEL` change, no code.
- Streaming endpoint plus a frontend change
- Hosted Ollama (VPS or GPU box) if it should work in the deployed version

## Where we left off (2026-10-21)

- Built: `bot/llm.py`, `bot/rag.py`, optional `llm` arg in `Dispatcher`, `USE_OLLAMA` / `OLLAMA_HOST` / `OLLAMA_MODEL` in `paco_chatbot.py`. Tests in `tests/test_llm.py`, `tests/test_rag.py`, `tests/test_dispatcher.py` (85 passing).
- Tried live with `USE_OLLAMA=true`: works. First reply ~11s (model load), next ~3s.
- Drift check: reply must mention the term (both terms for compare), else template reply.
- Not done: `ins_chatbot_api` wiring (`lifespan` + `.env`), README / `TECHNICAL.md` section, "thinking" state in the web UI.
- FALLBACK with no resolved term still uses templates (nothing to ground the LLM on).
