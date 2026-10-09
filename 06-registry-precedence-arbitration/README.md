# Code Companion

A runnable implementation of a shared lot registry paired with a
**deterministic precedence rulebook** — the design Kavita Iyer's team built
after Pune and Plant Two both placed a hold against the same Nashik
supplier-lot within four minutes of each other — two individually
well-governed agents, each correct on its own accurate local view, with no
shared visibility into one another.

It's built on **LangGraph**, using an observe/decide/act/escalate shape,
running against a small scripted replay of two such collisions. The
precedence rulebook and collision detection are deterministic and
rule-based — no LLM, no API key.

## Demo video

<video src="../demo-videos/06-registry-precedence-arbitration-demo.mp4" controls width="100%"></video>

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

This streams four cases through the same compiled graph, in true
chronological order, against one shared `LotRegistry`:

1. **The discovery case** — the original Monday collision: Pune and Plant
   Two both claim the same Nashik Precision Fasteners lot, four minutes
   apart. Historically the supplier's own system just confirmed whichever
   PO hit first (Pune's) and silently dropped Plant Two's. Replayed through
   the now-built rulebook, the answer is different: commitment tiers tie,
   so it falls to days-of-cover, and Plant Two — genuinely more urgent —
   is who the rule says should have held the lot.
2. **The success case** — three weeks later, Pune and the newest of the
   four plants reach for the same lot again. This time the registry
   catches the collision *before* either request becomes a confirmed
   hold. Commitment tier alone resolves it cleanly, and the losing plant
   gets an immediate, specific alternate-cover suggestion instead of a
   hold that would quietly turn out to be worthless.
3. **A non-colliding claim** — Plant Three requests an unrelated lot.
   Granted immediately: no arbitration, no human, no delay.
4. **A genuine dead heat** — Pune and Plant Two collide again on a lot
   where every tier of the rulebook comes back tied. The graph pauses on
   a real `interrupt()` and escalates, by name, to Kavita Iyer's team —
   the one legitimate human-in-the-loop path in this design.

## Run the tests

```bash
python3 -m unittest test_coordination_graph.py -v
```

## Files

| File | What it is |
|---|---|
| `precedence_policy.py` | The pre-approved, deterministic rulebook: `resolve_precedence()` applies customer-commitment tier, then days-of-cover, then a timestamp tie-break, in that exact order, and returns a winner plus a human-readable explanation of which tier decided it — or flags the case for escalation if every tier is exhausted or data is missing. `suggest_alternate_cover()` looks up a specific next-best lot, alternate supplier, or expedite option for the losing claim from a small scripted catalog. |
| `lot_registry.py` | The shared registry: `LotRegistry` tracks every open hold per (supplier, lot) across any number of plants in real time, detects when an incoming claim collides with an existing or simultaneous hold on the same lot, and keeps the full cross-agent audit log. |
| `coordination_graph.py` | The LangGraph `StateGraph`: `submit_claim` → `check_registry` → (clear) `grant` → `log`, or (collision) `arbitrate` → `grant_winner` + `suggest_alternate_for_loser` → `log`. The one `interrupt()` in the graph lives in `escalate_to_kavitas_team`, reached only when `arbitrate` reports a case the rulebook genuinely cannot resolve. |
| `demo.py` | Drives all four cases above, streaming the graph via `stream_mode="updates"` and printing each node's output as it fires, in true chronological order, resuming the one interrupt case with `Command(resume=...)`. The scripted claims it replays are loaded at runtime from `data/coordination_scenarios.json`. |
| `data/coordination_scenarios.json` | The scripted sample data for the demo: the supplier name, SKU, and the full set of claims (plant, lot, commitment tier, days-of-cover, timestamp) used across the four cases in `demo.py`, kept as data rather than hardcoded in the script. |
| `test_coordination_graph.py` | Unit tests: commitment-tier-only resolution, tied-tier-resolved-by-cover, tied-tier-and-cover-resolved-by-timestamp, a losing claim's specific alternate-cover suggestion, a non-colliding claim granting with no arbitration and no interrupt, a genuine tie escalating via `interrupt()`, and a 3-plant scenario where only two of three claims actually collide. |
| `requirements.txt` | Just `langgraph`. Nothing else — the rulebook and registry are deliberately rule-based, not an LLM call, so the demo is deterministic and needs no API key. |

## Why LangGraph, and why `arbitrate()` isn't an LLM call

LangGraph is doing the job this design is actually about: a graph that
routes a *specific, narrow* case to a human via a real pause-and-resume
mechanism (`interrupt()` / `Command(resume=...)`), while handling the
overwhelming majority of collisions itself, deterministically, with a full
audit trail. Swapping `resolve_precedence()` for a model call would betray
the design's own argument — Kavita is explicit that "agent-to-agent
negotiation sounds elegant and becomes impossible to audit six months
later," and the fix landed on here is a rulebook a person could read
end to end in ten minutes, not a smarter model making the call.

## This design vs. a different approach used elsewhere in this project — deliberately different tradeoffs

A different design used elsewhere in this project — case-by-case
dual-human confirmation between two sites — looks similar to this one on
the surface — both are about two plants' agents reaching for the same
constrained resource — but they land on genuinely different architectures,
and the difference is deliberate, not an oversight:

| | Case-by-case dual-human confirmation | This design's arbitration layer |
|---|---|---|
| **Scale** | Exactly two plants (Pune and Nashik), pairwise by construction | Built for *N* plants — the registry keys collisions by `(supplier, lot)`, not by which two sites are involved; this code demos 4 plants with only 2 colliding and a 3rd/4th present but untouched |
| **Normal-case human involvement** | Every single cross-plant transfer requires two named humans (Neha and Shalini) to confirm it, case by case, before it executes | **No per-decision human involvement in the normal case.** The precedence rulebook is reviewed and signed off *once, in advance*, by Kavita's team — not re-approved per incident |
| **What's pre-approved vs. decided live** | Nothing is pre-decided; the boundary rule says a human must decide *this specific transfer*, every time | The decision rule itself (tier → cover → timestamp) is pre-approved; arbitration just *applies* it — no live human judgment call in the normal case |
| **Where a human still appears** | Confirming every crossing, by design — the whole point of that approach is that crossing a plant boundary always needs a named accountable person | Only the one case the rulebook cannot resolve on its own: a genuine dead heat, or a claim missing data the policy needs — see `escalate_to_kavitas_team` |

Case-by-case dual-human confirmation is right for its moment: two plants, a
boundary that had never been crossed before, and a case where the
organization explicitly wanted a human owning every crossing while trust in
the pattern was still being built. The design here deliberately rejects
carrying that same pattern forward unchanged to four-plus plants and a
resource collision that, once Kavita's team actually looked at it, turned
out to be resolvable by a short, explicit, human-reviewed rule — because
case-by-case human refereeing of *every* collision stops scaling long
before the fifth plant goes live, while a pre-approved rulebook, audited
the same way every time, keeps scaling. The accountability doesn't
disappear in this design — it moves from "a human confirms this specific
instance" to "a human signed off on the rule that governs every instance,
and a human is still the one named escalation when the rule runs out."

---

*Vimana Auto Components and the scenario replayed here are fictional. This
code is an original illustration of a general multi-agent arbitration
pattern and is not based on any vendor's proprietary implementation.*
