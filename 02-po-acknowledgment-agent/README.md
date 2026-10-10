# PO-Acknowledgment Agent — Code Companion

A runnable implementation of one genuinely code-shaped idea: the
**six-box productivity-agent anatomy** — Trigger → Perceive → Decide →
Act → Escalate → Log — built out, box by box, into a PO-acknowledgment
agent that is designed, tested, and guarded end to end.

It's built on **LangGraph**, running against a small scripted set of
supplier replies that mirror realistic worked examples: a clean
confirmation, a 48-hour silent PO, a supplier who quietly moves a
delivery date by six days inside otherwise routine text, and a supplier
whose standard non-answer is "noted, will advise."

## Demo video

<video src="../demo-videos/02-po-acknowledgment-agent-demo.mp4" controls width="100%"></video>

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

This streams the same graph through three parts:

1. **Two-week supervised go-live** — the staged-autonomy rule: every
   action the agent proposes, *including* a clean "log only, no
   action," sits in an approval queue for Neha before it fires. Watch
   `[APPROVAL QUEUE]` lines appear even for the routine cases.
2. **Earned autonomy** — the same four scenarios, `supervised=False`.
   `log_only` and `send_chase` now fire on their own, but the escalation
   cases still interrupt for Neha — escalations and hard-invariant hits
   never stop requiring a human, in either stage.
3. **Guardrails in action** — the per-supplier exception table applying
   to exactly one supplier and not another with identical text, and the
   stamped-PDF attachment's own confidence score deciding whether a
   "good scan" logs cleanly while a "bad scan" escalates.

## Run the shadow-mode report

```bash
python3 shadow_mode.py
```

Calls `perceive`/`decide` directly — no graph, no `interrupt()`, nothing
sent or logged anywhere live — against 12 scripted historical messages:
6 clean baseline cases, 4 historical failure modes (now closed by the
guardrails), and 2 new, deliberately-unfixed edge cases included to make
the point that shadow-mode testing is a standing practice, not a
one-time gate.

## Run the tests

```bash
python3 -m unittest test_agent_graph.py -v
```

## Files

| File | What it is |
|---|---|
| `agent_graph.py` | The LangGraph `StateGraph`: `trigger` / `perceive` / `decide` / `human_approval` / `act` / `escalate` / `log` nodes, the conditional routing that makes the bounded action space and the escalate branch real graph structure, and the two `interrupt()` call sites — the staged-autonomy approval gate and the always-on escalation handoff. |
| `perception.py` | The `perceive` box's logic: a rule-based text/attachment classifier that returns a situation *and* a confidence score, Neha's per-supplier exception table (guardrail #3), and reference-number matching across email threads regardless of thread (guardrail #2). |
| `demo.py` | Drives the graph through worked scenarios across both autonomy stages, streaming `stream_mode="updates"` and printing each box of the anatomy as it actually fires — true chronological order, not a read-back of final state. |
| `shadow_mode.py` | Calls `perceive`/`decide` directly against 12 scripted historical messages and prints a shadow-mode report — matches vs. ground truth, and a named list of specific failure modes, on the premise that such a list is worth more than a single aggregate accuracy number. |
| `test_agent_graph.py` | Unit tests: a clean confirmation with no interrupt, a 48h chase, an ambiguous reply that escalates, a date mismatch that escalates via the hard invariant *even at high confidence* (the central point), the supplier exception table overriding for one supplier and not another, and supervised-vs-autonomous mode producing different interrupt behavior for the identical input. Its fixtures stay inline and deliberately do not depend on `data/` — tests should be self-contained. |
| `requirements.txt` | Just `langgraph`. Nothing else — `perceive` and `decide` are deliberately rule-based, not LLM calls, so every run here is deterministic and needs no API key. (The full-stack demo's `backend/main.py` separately exposes an optional `/api/chat` panel that calls OpenAI when `OPENAI_API_KEY` is set — tested against a real key — but it sits outside `perceive`/`decide` entirely.) |
| `data/demo_scenarios.json` | The scripted PO/supplier-reply scenarios `demo.py` walks through — the clean confirmation, the 48h chase, the schedule slip, the ambiguous reply, and the four guardrail-demonstration POs — loaded at runtime instead of hardcoded. |
| `data/shadow_mode_fixtures.json` | The 12 scripted historical-message fixtures `shadow_mode.py` runs through `perceive`/`decide` — 6 baseline cases, 4 closed historical failure modes, 2 new illustrative edge cases — loaded at runtime instead of hardcoded. |

## Why LangGraph, and why `perceive`/`decide` aren't LLM calls

LangGraph is doing the job the six-box anatomy actually describes: a
graph with real conditional structure for a bounded action space, a
genuine pause-and-resume mechanism (`interrupt()` / `Command(resume=...)`)
for both the staged-autonomy approval queue and the always-on escalation
handoff, and an auditable log of every box that fired — not a model
doing the reasoning. The hard design problem here is reading messy,
inconsistent supplier replies and setting a confidence threshold
deliberately, by testing it against real cases — not swapping in an LLM
and hoping. Keeping `perceive`/`decide` as rule-based, inspectable
functions is what makes the hard invariant in `decide()` actually
*hard*: a fixed rule that can be read, tested, and proven to never be
out-voted by a confidence score, which is precisely the guarantee a
probability alone can't offer. Swapping either function for an LLM call
later would be a contained change — the graph topology, the bounded
action space, and the escalate/log boxes around it wouldn't need to move
at all.

## Design principles and where they live

| Idea | What it introduces | Where it lives here |
|---|---|---|
| Six-box productivity-agent anatomy | The six boxes; perceive needs a confidence signal; decide works over a bounded, pre-approved action space | `agent_graph.py`'s node/edge structure; `perceive()`'s confidence score on every result |
| Bounded action space & shadow-mode testing | The four-outcome bounded action space; the confidence threshold; shadow-mode testing | `decide()`'s four actions; `CONFIDENCE_ESCALATION_THRESHOLD` in `perception.py`; `shadow_mode.py` |
| Guardrails & staged autonomy | Four distinct guardrail types; staged autonomy with a written exit criterion | `perception.py` (attachment confidence, thread-independent matching, supplier exception table) and `agent_graph.py`'s hard invariant in `decide()` and `supervised` flag |

---

*Vimana Auto Components and the scenario replayed here are fictional.
This code is an original illustration of a general productivity-agent
pattern and is not based on any vendor's proprietary implementation.*
