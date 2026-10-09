# Agentic Loop — Code Companion

A runnable implementation of a genuinely code-shaped idea: the **agentic
loop** — Observe → Decide → (human can intervene) → Act → Log, repeated,
versus a conversational chatbot's single ask → answer → stop.

![Agentic loop architecture: a LangGraph StateGraph looping START to observe to decide to act and back to observe, with a human_review interrupt() node on the high-risk branch between decide and act, and an END branch off observe when there's nothing left to see.](./architecture.svg)

It's built on **LangGraph**, the same observe/decide/act/escalate shape
real agentic systems use, running against a small scripted scenario: the
4200 series wiring harness bin that a frozen batch report still shows as
340 units while three real overnight transactions quietly draw it down to
12.

## Demo video

<video src="../demo-videos/01-agentic-loop-demo.mp4" controls width="100%"></video>

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the demo

```bash
python3 demo.py
```

This prints two things side by side:

1. **The chatbot** — asked at 7:05 AM whether there's enough stock, and
   answering with a generic, on-brand non-answer, because it never
   consulted anything live. This is `chatbot.py`'s `ConversationalStub`.
2. **The agent** — watching the same ledger continuously overnight,
   handling the low-risk response itself (an alert), and *pausing the
   graph* on a real `interrupt()` the moment the decision becomes
   irreversible and cost-bearing (expediting a replacement shipment),
   waiting for a human sign-off before acting.

## Run the tests

```bash
python3 -m unittest test_agentic_graph.py -v
```

## Files

| File | What it is |
|---|---|
| `agentic_graph.py` | The LangGraph `StateGraph`: `observe` / `decide` / `human_review` / `act` nodes, conditional routing, and the `interrupt()` call that genuinely pauses execution for a human decision. |
| `chatbot.py` | `ConversationalStub` — the one-shot ask → answer system the agentic loop is contrasted against. |
| `demo.py` | Drives both sides, streaming the graph and resuming it past each `interrupt()` with `Command(resume=...)`. |
| `data/overnight_scenario.json` | The scripted scenario `demo.py` loads at runtime: the SKU, the frozen batch-report balance (340), and the three overnight transactions that draw it down to 12. |
| `test_agentic_graph.py` | Unit tests: a low-risk event that never interrupts, a repeated shortfall that escalates twice and ends at the expected balance (12), a human decline, and an empty event queue. Fixtures are inline in the test file and don't depend on `data/`. |
| `requirements.txt` | Just `langgraph`. Nothing else — `decide()` is deliberately rule-based (simple threshold logic), not an LLM call, so the demo is deterministic and needs no API key. |
| `decide_llm.py` | Optional OpenAI-backed replacement for `decide()`, same signature and return shape. Imported only by `demo_llm.py` — never by the core example. |
| `demo_llm.py` | Optional runnable companion to `demo.py`: runs the deterministic `decide()` and `decide_llm.decide()` side by side over 100 events across 8 products and reports where they agree/disagree. |
| `data/harness_products_100.json` | 8 harness product lines (engine, dashboard, left/right door, battery, chassis, transmission, headlamp), 100 scripted events total, with deliberately varied severity — used only by `demo_llm.py`. |
| `requirements-llm.txt` | `requirements.txt` plus `openai` — only needed for the optional `decide_llm.py` / `demo_llm.py` path. |

## Why LangGraph, and why `decide()` isn't an LLM call

LangGraph is doing the job that actually matters here: a graph that
*runs continuously*, routes specific decisions to a human via a real
pause-and-resume mechanism (`interrupt()` / `Command(resume=...)`), and
keeps an auditable log of every cycle — not a model doing the reasoning.
Swapping `decide()` for an LLM call (e.g. via `langchain-anthropic`) would
be a one-function change if you want to extend this; the graph topology
underneath it — the real point being illustrated — wouldn't need to change
at all.

## Optional: live OpenAI-backed decide()

`decide_llm.py` and `demo_llm.py` add a second, **opt-in** decision path:
the same `observe -> decide -> (human_review) -> act` graph from
`agentic_graph.py`, but with `decide()` swapped for a real OpenAI chat
completion (`decide_llm.decide`), wired in via `build_graph(decide_fn=...)`.
This is **not** part of the free/deterministic core example above — it
costs real API usage and is not installed or imported by anything in the
base example (`agentic_graph.py`, `demo.py`, `test_agentic_graph.py` never
import `decide_llm` or `openai`).

Setup:

```bash
pip install -r requirements-llm.txt
cp .env.example .env      # then fill in OPENAI_API_KEY, or export it directly
python3 demo_llm.py                 # full run: 8 products, 100 events
python3 demo_llm.py --limit 10      # cheap smoke test: just the first 10 cycles
```

`demo_llm.py` loads `data/harness_products_100.json` — 8 harness product
lines (engine, dashboard, left/right door, battery, chassis, transmission,
headlamp) and 100 scripted events with deliberately varied severity — and
for each product runs *two* parallel traces over the same events: the
deterministic `decide()` and `decide_llm.decide()`. It then reports, cycle
by cycle, whether the two agreed on the action, the risk level, and
whether a human was required, finishing with a summary of agreement rates
and the specific cycles where they diverged (with both sides' rationale).

This costs a small amount of real OpenAI API usage — about 100 short chat
completions on `gpt-4o-mini` by default for a full run. Because the
model's output is non-deterministic, `demo_llm.py` is a **comparison
report, not a pass/fail test**: re-running it can produce different
disagreement counts from one run to the next.

One thing that does *not* vary: the safety-net invariant. `decide_llm.py`
forces `requires_human = True` (and `approved = False`) in code whenever
the model reports `risk: "high"` — regardless of anything else the model
says. An escalation-worthy risk level always escalates; that gate is a
hard invariant enforced by the code, never a threshold left to the model's
own judgment.

---

*Vimana Auto Components and the scenario replayed here are fictional.
This code is an original illustration of a general agentic-loop pattern
and is not based on any vendor's proprietary implementation.*
