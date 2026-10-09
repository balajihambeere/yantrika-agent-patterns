"""
A runnable companion demo of the shared-registry / precedence-rulebook
arbitration design, built on LangGraph.

Replays four claims against the shared `LotRegistry`, through the same
compiled `coordination_graph`, in true chronological order:

  1. THE DISCOVERY CASE — the original Monday collision: Pune and Plant Two
     both place a hold against the same Nashik Precision Fasteners lot,
     four minutes apart. Historically, the supplier's own system just
     honored whichever confirmation hit first (Pune's) and silently dropped
     the second — Plant Two's agent believed its hold was solid right up
     until a truck arrived short. Replayed here through the now-built
     registry, the rulebook reaches a different, better answer: tiers tie,
     so it falls to days-of-cover, and Plant Two — genuinely more urgent —
     is the one the rule says should have won. That gap between "who the
     supplier happened to confirm first" and "who the rulebook says should
     win" is exactly why this layer got built.

  2. THE SUCCESS CASE — three weeks later, Pune and the newest of the four
     plants reach for the same lot within minutes of each other again. This
     time the registry catches it before either request becomes a
     confirmed hold. Commitment tier alone resolves it, cleanly, and the
     losing plant gets an immediate alternate-cover suggestion instead of a
     hold that would have turned out to be worthless. This is the system
     working exactly as intended — the "boring" outcome Ganesh heard about
     secondhand.

  3. A NON-COLLIDING CLAIM — Plant Three requests a completely different
     lot. No other plant is anywhere near it. It grants immediately: no
     arbitration, no human, no delay.

  4. A GENUINE DEAD HEAT — Pune and Plant Two collide again, later, on a
     lot where every tier of the rulebook comes back tied. The graph
     genuinely pauses on `interrupt()` and escalates, by name, to Kavita
     Iyer's team — the one legitimate human-in-the-loop path in this
     design, reserved for exactly the case the deterministic rule cannot
     resolve on its own.

Run with:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 demo.py
"""
from __future__ import annotations

import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from coordination_graph import build_graph, make_claim, make_initial_state
from lot_registry import LotRegistry

_SCENARIOS_PATH = Path(__file__).parent / "data" / "coordination_scenarios.json"
with _SCENARIOS_PATH.open() as _f:
    _SCENARIOS = json.load(_f)

SUPPLIER = _SCENARIOS["supplier"]
BOLT_SKU = _SCENARIOS["bolt_sku"]
_CLAIMS = _SCENARIOS["claims"]


def run_claim(graph, claim, thread_id, human_responder=None):
    """
    Streams one claim through the graph via `stream_mode="updates"`,
    printing each node's output as it fires, in true chronological order.
    If the graph hits `interrupt()`, calls `human_responder(payload)` to get
    a response and resumes with `Command(resume=...)` — the same mechanism
    a real human-review UI would use.
    """
    config = {"configurable": {"thread_id": thread_id}}
    stream_input = make_initial_state(claim)
    is_resuming = False

    while True:
        chunk_input = Command(resume=stream_input) if is_resuming else stream_input
        interrupt_payload = None

        for chunk in graph.stream(chunk_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                continue
            for node_name, update in chunk.items():
                _print_node(node_name, update)

        if interrupt_payload is not None:
            if human_responder is None:
                raise RuntimeError(f"Claim {claim['claim_id']} hit an interrupt with no human_responder provided.")
            stream_input = human_responder(interrupt_payload)
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values


def _print_node(node_name: str, update: dict) -> None:
    if node_name == "submit_claim":
        entry = update["log"][-1]
        c = entry["claim"]
        print(
            f"  SUBMIT_CLAIM      {c['plant']:<10} lot={c['lot_id']:<14} sku={c['sku']:<22} "
            f"qty={c['quantity_needed']:<6} tier={c['commitment_tier']} cover={c['days_of_cover']} "
            f"at={c['requested_at_display']}"
        )
    elif node_name == "check_registry":
        collisions = update["collisions"]
        if collisions:
            others = ", ".join(f"{c['plant']} ({c['requested_at_display']})" for c in collisions)
            print(f"  CHECK_REGISTRY    collision detected against: {others}")
        else:
            print("  CHECK_REGISTRY    no open or confirmed claim elsewhere on this lot — clear")
    elif node_name == "grant":
        o = update["outcome"]
        print(f"  GRANT             {o['plant']} — {o['reason']}")
    elif node_name == "arbitrate":
        arbitration = update["arbitration"]
        if arbitration["needs_escalation"]:
            print(f"  ARBITRATE         cannot resolve — {arbitration['escalation_reason']}")
        else:
            for line in arbitration["computation"]:
                print(f"  ARBITRATE         {line}")
    elif node_name == "escalate_to_kavitas_team":
        arbitration = update["arbitration"]
        print(f"  ESCALATE          resolved by {arbitration['resolved_by_human']}: {arbitration['human_note']}")
    elif node_name == "grant_winner":
        o = update["outcome"]
        print(f"  GRANT_WINNER      {o['plant']} — hold confirmed")
    elif node_name == "suggest_alternate_for_loser":
        for suggestion in update["arbitration"]["alternate_suggestions"]:
            print(f"  ALTERNATE_COVER   {suggestion['message']}")
    elif node_name == "log":
        entry = update["log"][-1]
        print(f"  LOG               audit entry written ({entry['type']}, claim={entry['claim_id']})")
    print()


def kavitas_team_decision(payload: dict) -> dict:
    """Stands in for Kavita Iyer's team actually looking at the dead heat."""
    print("  [HUMAN ESCALATION] escalated to:", payload["escalated_to"])
    print("  [HUMAN ESCALATION] reason:", payload["reason"])
    for c in payload["competing_claims"]:
        print(f"  [HUMAN ESCALATION]   competing claim: {c['plant']} / {c['lot_id']} @ {c['requested_at_display']}")
    decision = {
        "winner_plant": "Pune",
        "decided_by": "Kavita Iyer",
        "note": (
            "Rulebook exhausted with a genuine tie. Pune carries the larger downstream line "
            "count for this part this week — breaking the tie manually in Pune's favor and "
            "logging the reason, rather than letting either agent guess."
        ),
    }
    print(f"  [HUMAN ESCALATION] decision: {decision['winner_plant']} wins — {decision['note']}\n")
    return decision


def main() -> None:
    registry = LotRegistry()
    graph = build_graph(registry).compile(checkpointer=InMemorySaver())

    # ------------------------------------------------------------------
    print("=" * 88)
    print("CASE 1 — THE DISCOVERY CASE: the original Monday collision, replayed")
    print("         through the registry that didn't exist yet when it happened.")
    print("=" * 88)

    pune_monday = make_claim(**_CLAIMS["pune_monday"])
    plant_two_monday = make_claim(**_CLAIMS["plant_two_monday"])
    run_claim(graph, pune_monday, "case1-pune")
    print("  -- four minutes pass --\n")
    run_claim(graph, plant_two_monday, "case1-plant2")
    print(
        "  NOTE: historically the supplier just confirmed whichever PO hit its system first\n"
        "  (Pune's) and silently dropped Plant Two's. Replayed through the rulebook, the\n"
        "  answer is different: tiers tie, so it falls to days-of-cover, and Plant Two — the\n"
        "  more urgent of the two — is the one the rule says should hold the lot. That gap is\n"
        "  exactly why Kavita's team built this layer.\n"
    )

    # ------------------------------------------------------------------
    print("=" * 88)
    print("CASE 2 — THE SUCCESS CASE: three weeks later, caught before either hold confirms")
    print("=" * 88)

    pune_later = make_claim(**_CLAIMS["pune_later"])
    plant_four_later = make_claim(**_CLAIMS["plant_four_later"])
    run_claim(graph, pune_later, "case2-pune")
    print("  -- three minutes pass --\n")
    run_claim(graph, plant_four_later, "case2-plant4")
    print(
        "  NOTE: Plant Four's claim never became a confirmed hold in the first place — the\n"
        "  registry caught the collision before that happened, resolved it by commitment tier\n"
        "  alone, and routed Plant Four straight to an alternate. Ganesh heard about this one\n"
        "  secondhand, described as 'boring.' That's the compliment.\n"
    )

    # ------------------------------------------------------------------
    print("=" * 88)
    print("CASE 3 — A NON-COLLIDING CLAIM: Plant Three, a different lot entirely")
    print("=" * 88)

    plant_three_claim = make_claim(**_CLAIMS["plant_three_claim"])
    run_claim(graph, plant_three_claim, "case3-plant3")
    print("  NOTE: nobody else is anywhere near this lot — granted immediately, no arbitration.\n")

    # ------------------------------------------------------------------
    print("=" * 88)
    print("CASE 4 — A GENUINE DEAD HEAT: the rulebook escalates instead of guessing")
    print("=" * 88)

    pune_tie = make_claim(**_CLAIMS["pune_tie"])
    plant_two_tie = make_claim(**_CLAIMS["plant_two_tie"])
    run_claim(graph, pune_tie, "case4-pune")
    run_claim(graph, plant_two_tie, "case4-plant2", human_responder=kavitas_team_decision)

    # ------------------------------------------------------------------
    print("=" * 88)
    print("REGISTRY STATE AT END OF DEMO")
    print("=" * 88)
    for lot, holds in registry.snapshot().items():
        print(f"  {lot}: {holds}")
    print(f"\n  Audit log entries: {len(registry.audit_log)} "
          f"(every one capturing both competing claims, the precedence computation, and the resolution)")


if __name__ == "__main__":
    main()
