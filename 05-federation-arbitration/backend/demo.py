"""
Runnable companion demo, built on LangGraph.

Runs three cycles through the federation graph in `federation_graph.py`,
against Pune and Nashik's shared fastener family and shared supplier:

  1. **The actual near-miss scenario.** Pune's agent, observing Nashik's
     live demand signal under the pilot connection, correctly sees its own
     surplus could cover Nashik's shortfall. In the same cycle, Nashik's
     agent, independently watching the shared supplier's open capacity,
     correctly sees it could rush-order its own shortfall closed. Both are
     individually right; together they'd over-commit. The connection's
     tier is `recommend` (this federation's default — never `act`), so
     the collision routes to two separate `interrupt()` calls: Neha, then
     Shalini. Both confirm, and the graph resolves it into one coordinated
     transfer instead of the duplicate, wasteful outcome.

  2. **A non-colliding cycle, showing the observe tier distinctly.** Pune
     has real surplus and genuinely looks at Nashik's position under the
     same pilot connection — but Nashik isn't short this cycle, so Pune's
     agent produces no cross-boundary recommendation at all. No collision,
     no interrupt, both sites simply act within their own tier. This is
     what "observe" is supposed to look like most of the time: visibility
     that informs a decision not to act, not a trigger for one.

  3. **The same near-miss, except Shalini declines.** Neha confirms
     Pune's side; Shalini, reviewing the transfer, isn't convinced it
     closes in time and declines. The graph falls back to each site
     handling its own shortfall independently — the pre-fix behavior, but
     now visible and logged instead of silently colliding — rather than
     crashing or silently doing nothing.

Every stage prints in true chronological order via
`graph.stream(..., stream_mode="updates")`, and every `interrupt()` is
resumed with a genuine `Command(resume=...)`.

Run with:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 demo.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from federation_graph import (
    DEFAULT_CONNECTION_TIER,
    NASHIK_CONFIRMER,
    PUNE_CONFIRMER,
    build_graph,
    make_initial_state,
)
from site_agents import SitePosition, SupplierCapacity

# The scripted sample data for the three demo cases below — the supplier's
# capacity and each site-position variant (Pune's surplus, Nashik's
# shortfall, Nashik's comfortable cycle) — lives in data/ as JSON and is
# loaded here at runtime, rather than being hardcoded in this module.
_DATA_PATH = Path(__file__).parent / "data" / "federation_scenarios.json"
with _DATA_PATH.open(encoding="utf-8") as _data_file:
    _SCENARIO_DATA = json.load(_data_file)

SKU_FAMILY = _SCENARIO_DATA["sku_family"]
SUPPLIER: SupplierCapacity = {
    "supplier": _SCENARIO_DATA["supplier"]["supplier"],
    "sku_family": SKU_FAMILY,
    "open_capacity": _SCENARIO_DATA["supplier"]["open_capacity"],
}


def _load_site_position(key: str) -> SitePosition:
    data = _SCENARIO_DATA["site_positions"][key]
    return {
        "site": data["site"],
        "sku_family": SKU_FAMILY,
        "on_hand": data["on_hand"],
        "buffer_target": data["buffer_target"],
    }


# Scenario 1 — the near-miss scenario: Pune sitting on real surplus,
# Nashik genuinely short, six weeks running.
PUNE_SURPLUS: SitePosition = _load_site_position("pune_surplus")
NASHIK_SHORT: SitePosition = _load_site_position("nashik_short")

# Scenario 2 — Pune still has surplus, but Nashik is comfortably within
# its own buffer target this cycle. Observe tier does real work (Pune
# looks), just doesn't find anything to recommend across the boundary.
NASHIK_COMFORTABLE: SitePosition = _load_site_position("nashik_comfortable")


def human_response(confirmer: str, confirmed: bool, note: str) -> dict[str, Any]:
    tag = "CONFIRMS" if confirmed else "DECLINES"
    print(f"  [{confirmer.upper()}] {tag} — {note}")
    return {"confirmed": confirmed, "confirmed_by": confirmer, "note": note}


def print_sense(node_name: str, node_update: dict[str, Any]) -> None:
    rec = node_update["pune_recommendation" if node_name == "sense_pune" else "nashik_recommendation"]
    print(f"SENSE    [{rec['site']}]  {rec['action']}  (qty={rec['quantity']})")
    print(f"                 {rec['rationale']}")


def print_arbitrate(node_update: dict[str, Any]) -> None:
    collision = node_update["collision"]
    print("ARBITRATE")
    if collision is None:
        print("                 no collision — the two recommendations don't touch the same resource.")
    else:
        print(f"                 COLLISION DETECTED on {collision['sku_family']}:")
        print(f"                 {collision['description']}")


def print_act(label: str, node_update: dict[str, Any]) -> None:
    decision = node_update["decision"]
    print(f"{label}  type={decision['type']}")
    print(f"                 {decision['note']}")


def print_log(node_update: dict[str, Any]) -> None:
    entry = node_update["log"][-1]
    print(
        f"LOG      entry recorded — tier={entry['connection_tier']}, "
        f"collision={'yes' if entry['collision'] else 'no'}, "
        f"decision={entry['decision']['type']}"
    )
    print()


def run_scenario(graph, thread_id: str, initial_state, confirmations: dict[str, dict]) -> list[dict]:
    """
    Streams one federation cycle to completion, printing each node's
    output as it fires in true chronological order, and resuming each
    `interrupt()` it hits with the matching named human's response from
    `confirmations` (keyed by confirmer name).
    """
    config = {"configurable": {"thread_id": thread_id}}
    stream_input = initial_state

    while True:
        interrupt_payload = None
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                continue
            for node_name, node_update in chunk.items():
                if node_name in ("sense_pune", "sense_nashik"):
                    print_sense(node_name, node_update)
                elif node_name == "arbitrate":
                    print_arbitrate(node_update)
                elif node_name == "act_independent":
                    print_act("ACT     ", node_update)
                elif node_name == "act_unilateral":
                    print_act("ACT     ", node_update)
                elif node_name == "coordinated_act":
                    print_act("ACT     ", node_update)
                elif node_name == "fallback_independent":
                    print_act("FALLBACK", node_update)
                elif node_name == "log":
                    print_log(node_update)

        if interrupt_payload is not None:
            print(f"        CONFIRM  [{interrupt_payload['role']}] {interrupt_payload['proposed_action']}")
            confirmer = interrupt_payload["confirmer"]
            response = confirmations[confirmer]
            stream_input = Command(resume=human_response(confirmer, **response))
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values.get("log", [])


def scenario_1_the_near_miss(graph) -> None:
    print("=" * 76)
    print("SCENARIO 1 — Pune's surplus, Nashik's rush order, the same cycle")
    print(f"             connection tier = {DEFAULT_CONNECTION_TIER!r} (this federation's default)")
    print("=" * 76)
    state = make_initial_state(
        pune_position=PUNE_SURPLUS,
        nashik_position=NASHIK_SHORT,
        supplier=SUPPLIER,
    )
    confirmations = {
        PUNE_CONFIRMER: {
            "confirmed": True,
            "note": "Pune can spare it — we'd rather it go to Nashik than sit here.",
        },
        NASHIK_CONFIRMER: {
            "confirmed": True,
            "note": "Transfer closes it just as fast as the rush order would have. Cancel the rush order.",
        },
    }
    log = run_scenario(graph, "scenario-1-near-miss", state, confirmations)
    entry = log[-1]
    print(
        f"Result: {entry['decision']['type']} — "
        f"{entry['decision']['quantity']} units Pune -> Nashik, rush order cancelled.\n"
    )


def scenario_2_observe_only(graph) -> None:
    print("=" * 76)
    print("SCENARIO 2 — Pune observes Nashik, finds nothing to recommend across the boundary")
    print("=" * 76)
    state = make_initial_state(
        pune_position=PUNE_SURPLUS,
        nashik_position=NASHIK_COMFORTABLE,
        supplier=SUPPLIER,
    )
    log = run_scenario(graph, "scenario-2-observe-only", state, confirmations={})
    entry = log[-1]
    print(
        f"Result: {entry['decision']['type']} — no collision, no interrupt, each site acted on "
        f"its own, even though Pune's agent genuinely looked at Nashik's position first.\n"
    )


def scenario_3_shalini_declines(graph) -> None:
    print("=" * 76)
    print("SCENARIO 3 — the same near-miss, except Shalini isn't convinced")
    print("=" * 76)
    state = make_initial_state(
        pune_position=PUNE_SURPLUS,
        nashik_position=NASHIK_SHORT,
        supplier=SUPPLIER,
    )
    confirmations = {
        PUNE_CONFIRMER: {
            "confirmed": True,
            "note": "Pune can spare it.",
        },
        NASHIK_CONFIRMER: {
            "confirmed": False,
            "note": "Transfer logistics from Pune won't clear customs in time for this week's build — keeping the rush order.",
        },
    }
    log = run_scenario(graph, "scenario-3-shalini-declines", state, confirmations)
    entry = log[-1]
    print(
        f"Result: {entry['decision']['type']} — declined by {', '.join(entry['decision']['declined_by'])}. "
        f"Nashik's rush order proceeds, Pune's surplus stays put. Logged, not lost.\n"
    )


def main() -> None:
    graph = build_graph().compile(checkpointer=InMemorySaver())

    scenario_1_the_near_miss(graph)
    scenario_2_observe_only(graph)
    scenario_3_shalini_declines(graph)

    print("=" * 76)
    print(
        "Nothing here made either site's agent smarter. Pune's and Nashik's local logic in "
        "site_agents.py didn't change between scenarios 1 and 3 — only the arbitration layer did: "
        "whether a collision was caught before it executed, and whether both Neha and Shalini — "
        "named, on both sides — signed off before anything crossed the boundary."
    )


if __name__ == "__main__":
    main()
