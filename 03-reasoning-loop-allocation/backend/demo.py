"""
Runnable companion demo for a continuous reasoning loop, built on LangGraph.

Runs three sensing cycles through the Sense -> Weigh -> Recommend ->
Escalate -> Act -> Log loop from `reasoning_graph.py`, against the
4200-series harness category:

  1. A low-stakes cycle (Deccan Motors vs. Satpura Components) where the
     five weighted factors clearly agree and the exposure on the losing
     side is comfortably under the bounded-autonomy threshold — the
     system allocates on its own, no interrupt, no human in the loop.

  2. The three-way scenario: Bosch's regular shipment, a
     mid-tier account's smaller order (already slipped once this quarter),
     and Continental Fasteners' second order, all competing for the same
     shrinking harness batch. Exposure is well above threshold, so the
     system escalates with its full line-by-line reasoning attached.
     Arjun — reasoning independently —
     reaches the identical call, including the 80% Continental split.

  3. The divergence that surfaces at the end of the month: a case
     where the weighted factors flag a contracted account as urgent, but
     Arjun knows something the model has no input for — that account's
     plant is mid-shutdown and won't consume the shipment for another
     week. He overrides the recommendation. The log keeps both: what the
     system weighed, and what actually got decided and why.

Every stage prints in true chronological order via
`graph.stream(..., stream_mode="updates")`, as each node actually fires,
rather than in some fixed, assumed schedule.

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

from reasoning_graph import SensingCycle, build_graph, make_initial_state

SKU = "4200-series-harness"

_DATA_PATH = Path(__file__).parent / "data" / "sensing_cycles.json"
with _DATA_PATH.open(encoding="utf-8") as _f:
    CYCLES: list[SensingCycle] = json.load(_f)


def human_response_for(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Stands in for Arjun at the point of escalation. Cycle 2: he reasons
    independently and reaches the system's identical split, so he simply
    approves it. Cycle 3: he knows something the model's five inputs
    couldn't capture — a plant mid-shutdown — and overrides it.
    """
    if payload["cycle_label"] == CYCLES[2]["label"]:
        print(
            "  [ARJUN] Konkan Precision's plant is mid-shutdown for maintenance — it won't "
            "consume this shipment for another week. The 'urgent' priority the weights gave "
            "it is wrong this week. Protecting Orbit's shipment instead."
        )
        return {
            "decision": "override",
            "allocation": {
                "Konkan Precision": 50,
                "Orbit Drivetrain": 150,
            },
            "decided_by": "Arjun",
            "reason": (
                "Konkan Precision's plant is mid-shutdown for maintenance and won't consume "
                "this shipment for another week — current operational status isn't one of the "
                "model's five inputs yet. Protecting Orbit Drivetrain's shipment instead."
            ),
        }

    print(
        "  [ARJUN] Reasoning through this independently before reading the system's output: "
        "Bosch complete, hold the mid-tier order for tomorrow, Continental at eighty percent "
        "with Thursday for the rest. That's the same call."
    )
    return {"decision": "approve", "decided_by": "Arjun"}


def print_weigh(node_update: dict[str, Any]) -> None:
    print("        WEIGH")
    for scores in node_update["reasoning"]:
        print(f"                 {scores['account']:<24} weighted total = {scores['weighted_total']:.1f}/100")
        for line in scores["rationale"]:
            print(f"                     - {line}")


def print_recommend(node_update: dict[str, Any]) -> None:
    rec = node_update["recommendation"]
    print("        RECOMMEND")
    print(f"                 ranking (highest priority first): {', '.join(rec['ranking'])}")
    for account, alloc in rec["allocation"].items():
        msg = f" — {alloc['message']}" if alloc["message"] else ""
        print(
            f"                 {account:<24} {alloc['allocated_units']}/{alloc['requested_units']} "
            f"units [{alloc['status']}]{msg}"
        )
    print(
        f"                 clear_agreement={rec['clear_agreement']}  "
        f"exposure_on_losing_side=Rs.{rec['exposure_on_losing_side']:,.0f}"
    )
    print(f"                 autonomy check: {rec['reason']}")
    print(f"                 -> {'ESCALATE to a human' if rec['requires_human'] else 'ACT autonomously'}")


def print_act(node_update: dict[str, Any]) -> None:
    decision = node_update["decision"]
    print("        ACT")
    tag = "overridden by " + decision["decided_by"] if decision["overridden"] else (
        "approved by " + decision["decided_by"] if not decision["autonomous"] else "autonomous — no human call needed"
    )
    print(f"                 decision ({tag}):")
    for account, value in decision["allocation"].items():
        units = value["allocated_units"] if isinstance(value, dict) else value
        print(f"                     {account:<24} -> {units} units")
    if decision["overridden"]:
        print(f"                     override reason: {decision['override_reason']}")


def print_log(node_update: dict[str, Any]) -> None:
    entry = node_update["log"][-1]
    print(
        f"        LOG      entry recorded — {len(entry['reasoning'])} orders scored across all "
        f"5 factors, full rationale retained, requires_human={entry['requires_human']}"
    )
    print()


def run_cycle(graph, config, stream_input) -> bool:
    """Streams one pass through the graph. Returns True if an interrupt fired."""
    for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            payload = chunk["__interrupt__"][0].value
            print(f"        ESCALATE  reason: {payload['reason']}")
            print(f"                  exposure_on_losing_side=Rs.{payload['exposure_on_losing_side']:,.0f}")
            response = human_response_for(payload)
            return True, response
        for node_name, node_update in chunk.items():
            if node_name == "sense" and node_update.get("cycle"):
                print("=" * 76)
                print(f"SENSE    {node_update['cycle']['label']}  (available={node_update['cycle']['available_units']})")
            elif node_name == "weigh":
                print_weigh(node_update)
            elif node_name == "recommend":
                print_recommend(node_update)
            elif node_name == "act":
                print_act(node_update)
            elif node_name == "log":
                print_log(node_update)
    return False, None


def main() -> None:
    graph = build_graph().compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "vimana-4200-harness-allocation"}}
    state = make_initial_state(sku=SKU, pending_cycles=list(CYCLES))

    stream_input = state
    while True:
        interrupted, response = run_cycle(graph, config, stream_input)
        if interrupted:
            stream_input = Command(resume=response)
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:  # graph reached END — nothing left to sense
            log = snapshot.values.get("log", [])
            break

    print("=" * 76)
    print(f"Cycles run: {len(log)}  |  escalations: {sum(1 for e in log if e['requires_human'])}")
    print(
        "\nNote on shadow mode here: this isn't the familiar 'log predictions, grade them "
        "later against a fixed historical set' kind of shadow mode. A continuous reasoning "
        "system has to run alongside live human calls in real time and compare outcomes "
        "directly, because the ground truth for a shifting trade-off keeps shifting too — "
        "which is exactly what cycles 2 and 3 above just did: Arjun deciding independently, "
        "once agreeing and once overriding, with both outcomes logged next to the system's "
        "own reasoning."
    )
    print(
        "\nNothing here removed Arjun from the decision. It moved him from reaching the call "
        "alone in his head to reviewing one specific, fully-reasoned recommendation — and, in "
        "Cycle 3, catching the one thing the model's five inputs couldn't see."
    )


if __name__ == "__main__":
    main()
