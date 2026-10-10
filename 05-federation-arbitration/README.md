# Federation Graph — Code Companion

A runnable implementation of a central code-shaped idea in multi-plant
agent coordination: two excellent, isolated,
**site-scoped** optimization agents — Pune's and Nashik's allocation
agents — each with a fully accurate view of only its own plant, nearly
causing a jointly bad outcome the moment a limited, observe-only pilot
connection lets them see past their own boundary for the first time. The
fix isn't a smarter agent. It's an explicit
**observe / recommend / act tier model** for cross-boundary autonomy, and
an **arbitration layer**: no agent may commit another plant's resources
without a *named* human on *both* sides confirming the transfer —
specifically Neha Joshi (Pune's procurement lead) and Shalini Rao
(Nashik's procurement lead).

This is built on **LangGraph**.

## The scenario, precisely

Pune's agent, observing Nashik's live demand signal under the pilot
connection, correctly sees its own surplus of a fastener family could
cover Nashik's shortfall. In the *same cycle*, Nashik's agent —
independently watching the same shared supplier's confirmed shipment
schedule — correctly sees it could solve its own shortfall by placing a
rush order against that supplier's open capacity. Neither agent did
anything wrong by its own narrow logic. Acted on simultaneously, without
either side knowing about the other, the two recommendations would have
jointly produced a bad outcome: Nashik over-receiving, Pune losing
surplus it might want back, and an unnecessary rush order. Vikram names
this directly as the same mechanism as a stale-report problem, one level
up — multiple locally-accurate actors, no shared visibility, a jointly
wrong outcome.

## Demo video

<video src="../demo-videos/05-federation-arbitration-demo.mp4" controls width="100%"></video>

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

Streams three cycles through the arbitration graph, each stage —
SENSE, ARBITRATE, (CONFIRM), ACT/FALLBACK, LOG — printed as it actually
fires, in true chronological order:

1. **The near-miss scenario.** Pune's surplus offer collides with
   Nashik's independent rush order on the same fastener family. The
   connection's tier is `recommend` (this federation's default), so the
   collision routes to two separate `interrupt()` calls — Neha's, then
   Shalini's. Both confirm, and the graph resolves it into one
   coordinated transfer, with Nashik's rush order cancelled, instead of
   both executing side by side.
2. **A non-colliding cycle that shows the observe tier distinctly.**
   Pune's agent genuinely looks at Nashik's position under the same
   pilot connection — but Nashik isn't short this cycle, so Pune's agent
   produces no cross-boundary recommendation at all. No collision, no
   interrupt, each site acts within its own tier.
3. **The same near-miss, except Shalini declines.** Neha confirms Pune's
   side; Shalini isn't convinced the transfer closes in time and
   declines. The graph falls back to each site handling its own shortfall
   independently — the pre-fix behavior, but now visible and logged
   instead of silently colliding.

## Run the tests

```bash
python3 -m unittest test_federation_graph.py -v
```

## Files

| File | What it is |
|---|---|
| `site_agents.py` | The two site-scoped agents' local logic: `evaluate_pune_position()` (surplus math, plus what the observe-tier grant into Nashik's position does and doesn't let it conclude) and `evaluate_nashik_position()` (shortfall math against the shared supplier's open capacity). Plain, deterministic threshold/arithmetic — no model. |
| `federation_graph.py` | The LangGraph `StateGraph`: parallel `sense_pune` / `sense_nashik` converging on `arbitrate`, collision detection, the tier constants (`TIER_OBSERVE` / `TIER_RECOMMEND` / `TIER_ACT`), and the two separate `interrupt()` calls — `confirm_neha` then `confirm_shalini` — that gate `coordinated_act` behind both named humans' sign-off, with `fallback_independent` as the no-silent-collision default on a decline. |
| `demo.py` | Drives three cycles through the graph — the near-miss scenario, a non-colliding observe-tier cycle, and a Shalini-declines fallback — streaming every stage in order and resuming past each `interrupt()` with `Command(resume=...)`. |
| `data/federation_scenarios.json` | The scripted sample data behind the three demo cases: the shared supplier's capacity and each site-position variant (Pune's surplus, Nashik's shortfall, Nashik's comfortable cycle) — loaded by `demo.py` at runtime rather than hardcoded in it. |
| `test_federation_graph.py` | Unit tests: a genuine collision requiring both Neha's and Shalini's confirmation before acting, a case with only one of the two confirmations in hand (action must not proceed), declines by each named human (falls back, doesn't crash), a non-colliding case that never escalates, the observe tier producing local awareness with no cross-boundary recommendation, a contrast case showing what the (never-default) `act` tier would bypass, and an assertion that this federation's default tier is `recommend`, not `act`. |
| `requirements.txt` | Just `langgraph`. Nothing else — both sites' sensing logic and the collision check are deliberately rule-based, not an LLM call, so the demo is deterministic and needs no API key. (The full-stack demo's `backend/main.py` separately exposes an optional `/api/chat` panel that calls OpenAI when `OPENAI_API_KEY` is set — tested against a real key — but it sits outside the sensing/collision logic entirely.) |

## The observe / recommend / act tier model, and why the confirmation is dual

This model names three distinct, escalating levels of
cross-boundary trust, and insists they be granted deliberately and
separately rather than assumed to come bundled with visibility:

1. **Observe** — an agent may see another site's data to inform its own
   recommendations. Low-risk, default-safe. This is what a "limited
   pilot connection... approved for observation only" grants Pune
   here, and what `observe_nashik_from_pune` models.
2. **Recommend** — an agent may surface a recommendation that touches
   another site's resources, but it is only ever surfaced to humans on
   both sides — no auto-action. `DEFAULT_CONNECTION_TIER` in
   `federation_graph.py` is set to this tier, and
   `test_default_connection_tier_is_recommend_not_act` asserts it stays
   that way.
3. **Act** — an agent may unilaterally commit another site's resources
   across the boundary with no human confirmation. `act_unilateral()` and
   `test_act_tier_would_bypass_confirmation_entirely` model what this
   tier would do *if* it were granted, specifically to make the risk
   visible — most organizations should not grant it to a federation of
   agents before the simpler tiers have earned trust over time, if ever.

The confirmation at the `recommend` tier is **dual**, not single, because
the resource being committed sits on both sides of the boundary at once:
Pune is releasing surplus it might want back, and Nashik is accepting a
transfer in place of an order it had already queued. `confirm_neha` and
`confirm_shalini` are two genuinely separate `interrupt()` calls — the
graph does not reach `coordinated_act` on one signature alone, exactly as
`test_only_one_confirmation_does_not_act_yet` checks. This formalizes
something Neha and Shalini were already doing informally, by picking up
the phone, rather than inventing a new kind of agent intelligence: the
arbitration layer's whole job is to make sure that phone call still
happens — on the record, every time — now that two agents can see enough
of each other to make the call necessary in the first place.

---

*Vimana Auto Components, Pune, Nashik, and the scenario replayed here are
fictional. This code is an original illustration of a general federated
multi-agent coordination and cross-boundary governance pattern, and is
not based on any vendor's proprietary architecture.*
