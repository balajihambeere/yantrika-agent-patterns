# Vimana Harness Allocation — Reasoning Loop Companion

A runnable implementation of the central code-shaped idea here: the shift
from a **rule** to **reasoning**, and the **continuous reasoning loop**
that reasoning requires once it has to run against a live, never-finished
situation.

- Replacing a single two-tier priority rule (Tier 1 contracted accounts
  always win) — backtested against 41 historical shortfall events and
  correct in only 26 of them — with five explicit, weighted factors:
  contract penalty exposure, strategic account trajectory, downstream
  production impact, confidence in the next replenishment, and the cost
  to close the gap some other way. A continuous reasoning system needs a
  different shape than a bounded Trigger→Perceive→Decide→Act→Escalate→
  Log agent anatomy: **Sense → Weigh → Recommend → Escalate →
  Log → back to Sense.** A loop, not a line.
- Turning that loop into an actual system scoped to the 4200-series
  harness category: a **bounded autonomy threshold** agreed in writing
  before anything runs live, a backtest that beats the old rule 36/41 vs.
  26/41 including every two-Tier-1 standoff the rule couldn't touch, and
  a live three-way allocation scenario — Bosch, a mid-tier account, and
  Continental Fasteners all competing for the same shrinking batch —
  where the system's shadow-mode recommendation matches what Arjun
  reaches independently.

This is built on **LangGraph**, running the loop against scripted
sensing cycles instead of a live ledger.

## Demo video

<video src="../demo-videos/03-reasoning-loop-allocation-demo.mp4" controls width="100%"></video>

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

Streams three sensing cycles through the graph, each stage — SENSE,
WEIGH, RECOMMEND, ESCALATE, ACT, LOG — printed as it actually fires, in
true chronological order:

1. **A low-stakes cycle** (two small accounts competing for a routine
   batch) where the five factors clearly agree and the exposure on the
   losing side is comfortably under the agreed rupee threshold — the
   system allocates on its own, no interrupt.
2. **The three-way scenario** — Bosch's regular shipment, a
   mid-tier account's smaller order (already slipped once this quarter),
   and Continental Fasteners' second order, all drawing on the same
   shrinking harness batch. Exposure is well above threshold, so the
   graph genuinely pauses on a real `interrupt()`, carrying the full
   per-factor reasoning — not a bare recommendation — out to a human.
   Arjun, reasoning independently, reaches the identical call, including
   the 80% Continental split.
3. **The divergence that surfaces at the end of the month** — the
   weights flag a contracted account as urgent, but a human knows
   something none of the five inputs capture (a plant mid-shutdown) and
   overrides the recommendation. The log keeps both: what the system
   weighed, and what was actually decided, and why.

## Run the backtest

```bash
python3 backtest.py
```

Calls `reasoning_factors.score_order()` directly — no graph, no
interrupt — against 10 small, honestly-labeled illustrative shortfall
cases (clean single-factor cases, two-Tier-1 standoffs the old rule
can't resolve, cases a second or third factor overturns, and two
genuinely hard misses) and compares the weighted model's pick against a
naive Tier 1/Tier 2 rule's pick, case by case. This is explicitly *not*
a reproduction of a real 41-event backtest — it's a small
reconstruction of the same shape of result, labeled as such.

## Run the tests

```bash
python3 -m unittest test_reasoning_graph.py -v
```

## Files

| File | What it is |
|---|---|
| `reasoning_factors.py` | The five-factor weighing logic: explicit weights and normalization constants (each with a one-line rationale comment), `score_order()`, ranking, greedy allocation, exposure-on-the-losing-side, and the bounded-autonomy-threshold check. Plain, deterministic arithmetic — no model. |
| `reasoning_graph.py` | The LangGraph `StateGraph`: `sense` / `weigh` / `recommend` / `escalate` / `act` / `log` nodes, conditional routing on the bounded-autonomy threshold, and the `interrupt()` call that genuinely pauses execution for a human decision. `act` loops back to `log` loops back to `sense`. |
| `demo.py` | Drives three sensing cycles through the graph — a low-stakes autonomous case, the three-way Bosch/mid-tier/Continental conflict, and a human-override divergence case — streaming every stage in order and resuming past each `interrupt()` with `Command(resume=...)`. |
| `backtest.py` | Calls the scoring logic directly against 10 scripted historical-shape cases and reports a match-rate comparison against a naive tier rule, echoing a 26/41-vs-36/41 framing at a small, honestly-labeled illustrative scale. |
| `test_reasoning_graph.py` | Unit tests: a clear-agreement/low-exposure case that allocates with no interrupt, a close call that escalates even at zero exposure, a high-exposure case that escalates even when factors clearly agree, a log entry that retains the actual per-factor weights/scores (not just the allocation), and a human-override case where the final decision diverges from the system's own recommendation. Its fixtures are inline and self-contained — deliberately not loaded from `data/`. |
| `data/sensing_cycles.json` | The three scripted sensing cycles `demo.py` streams through the graph (low-stakes case, Bosch/mid-tier/Continental three-way conflict, plant-shutdown divergence), loaded at runtime instead of being inlined in `demo.py`. |
| `data/backtest_cases.json` | The 10 scripted illustrative shortfall cases `backtest.py` scores (clean single-factor cases, two-Tier-1 standoffs, and the two genuinely hard misses), loaded at runtime instead of being inlined in `backtest.py`. |
| `requirements.txt` | Just `langgraph`. Nothing else — `weigh()`/`recommend()` are deliberately rule-based, not an LLM call, so the demo is deterministic and needs no API key. (The full-stack demo's `backend/main.py` separately exposes an optional `/api/chat` panel that calls OpenAI when `OPENAI_API_KEY` is set — tested against a real key — but it sits outside `weigh`/`recommend` entirely.) |

## Why this is a loop with no finish line, not a bounded task

A bounded-task agent anatomy — Trigger, Perceive, Decide, Act, Escalate,
Log — fits a bounded task: a PO lands, the agent reacts, logs the
outcome, and is done until the next one arrives. There is no equivalent
finish line here. The state of every order against the same constrained
SKU is shifting by the hour — a new order lands, a delivery slips, a
quality hold changes the available count — and the right allocation can
change without any single triggering event. `reasoning_graph.py`'s `act`
node routes to `log`, which routes straight back to `sense`, not to
`END`; the only way the graph in this repository stops is that `sense()`
is handed a *bounded* queue of scripted cycles for the demo and tests to
run against. In a live system, that queue would simply never run dry.

## Why weighing stays rule-based and explicit, not an LLM call

The core argument is that the hard part was never the
arithmetic — it was making Vimana's implicit values explicit enough to
write down, argue with, and defend out loud. `reasoning_factors.py`'s
five weights (`WEIGHT_CONTRACT_PENALTY`, `WEIGHT_DOWNSTREAM_IMPACT`,
`WEIGHT_STRATEGIC_TRAJECTORY`, `WEIGHT_REPLENISHMENT_CONFIDENCE`,
`WEIGHT_EXPEDITE_COST`) and the normalization constants beside them are
exactly that first pass, each with its rationale in a comment next to
the number — the same spirit as the decision-rights map Vikram refers
back to. An LLM making this call would hide that arithmetic inside a
model nobody in the room could point at and argue with. Keeping it as
plain, deterministic scoring is what makes the bounded-autonomy
threshold enforceable at all: the system can only be trusted to act
alone within a line Suresh and Anand agreed on *in writing*, and that
line has to be checked against numbers a human can audit, not a
probability a model reports about itself.

This is also why the "shadow mode" distinction in `demo.py`'s closing
note matters. A conventional supervised agent logs its predictions and
gets graded against a fixed historical set after a set window.
A continuous reasoning system's ground truth keeps shifting with the
situation it's reasoning about, so shadow mode here means running
alongside live human decisions in real time and comparing outcomes
directly — agreement and divergence both logged, both fed back in —
not a one-time grade against history.

---

*Vimana Auto Components and the scenario replayed here are fictional.
This code is an original illustration of a general weighted-reasoning
and bounded-autonomy pattern and is not based on any vendor's
proprietary implementation.*
