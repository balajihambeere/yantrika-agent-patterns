"""
Runnable companion demo, built on LangGraph.

Streams five scenarios through `policy_gate_graph.build_graph()`,
printing each node as it actually fires, in true chronological order
via `graph.stream(..., stream_mode="updates")`:

  1. A within-boundary Tier 2 action (Arjun's allocation agent, a single
     low-exposure claim) — auto-acts, no interrupt, logs a five-part
     record.
  2. An out-of-boundary action (two competing claims, exposure over the
     agreed cap) — escalates via a real `interrupt()` to Aditi Kulkarni,
     the agent's named escalation contact, before anything happens.
  3. Arjun's actual tier-widening proposal — all four policy-as-code
     conditions satisfied, proposer (Arjun) and approver
     (Suresh Rane) structurally different people, routed to Suresh via
     `interrupt()`, boundary widened, governance record logged.
  4. A follow-up widening proposal, rejected outright — missing both a
     sufficient track record AND a reversal trigger. The policy engine
     rejects it deterministically; no interrupt fires at all, Suresh is
     never even asked.
  5. A reversal-trigger check against a run of recent decisions that
     includes one missed commitment — the predefined trigger fires, and
     the agent's boundary rolls back automatically, logged as its own
     governance record, no human call involved.

Run with:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 demo.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from decision_ledger import DecisionLedger
from policy_engine import AutonomyTier, PolicyRegistry, ReversalTrigger, TierBoundary, TierChangeProposal
from policy_gate_graph import (
    build_graph,
    make_initial_governance_state,
    make_initial_operational_state,
    make_initial_reversal_state,
)

# The scripted sample/scenario data below (all five scenarios' inputs,
# proposals, and reversal history) lives in data/demo_scenarios.json,
# loaded once here at import time, so this module stays pure code.
_SCENARIOS = json.loads((Path(__file__).parent / "data" / "demo_scenarios.json").read_text())

# The story's "today" — set in mid-August. Kept as an explicit constant
# (never `date.today()`) so the demo's policy-as-code checks are
# reproducible regardless of when this script is actually run.
STORY_TODAY = date.fromisoformat(_SCENARIOS["story_today"])


def _reversal_trigger_from_json(data: dict | None) -> ReversalTrigger | None:
    if data is None:
        return None
    return ReversalTrigger(
        name=data["name"],
        metric=data["metric"],
        comparison=data["comparison"],
        threshold=data["threshold"],
        window_label=data["window_label"],
    )


def _proposal_from_json(data: dict) -> TierChangeProposal:
    return TierChangeProposal(
        agent_id=data["agent_id"],
        proposer=data["proposer"],
        approver=data["approver"],
        from_tier=AutonomyTier(data["from_tier"]),
        to_tier=AutonomyTier(data["to_tier"]),
        new_boundary=TierBoundary(
            max_competing_orders=data["new_boundary"].get("max_competing_orders"),
            max_exposure_inr=data["new_boundary"].get("max_exposure_inr"),
            notes=data["new_boundary"].get("notes", ""),
        ),
        track_record_count=data["track_record_count"],
        track_record_minimum=data["track_record_minimum"],
        track_record_label=data["track_record_label"],
        reversal_trigger=_reversal_trigger_from_json(data["reversal_trigger"]),
        re_review_date=date.fromisoformat(data["re_review_date"]) if data.get("re_review_date") else None,
        rationale=data.get("rationale", ""),
    )


def run_request(graph, config: dict, initial_state: dict, human_response_fn=None) -> list[str]:
    """
    Streams one request through the graph, printing every node as it
    fires. Resumes past any `interrupt()` using `Command(resume=...)`,
    asking `human_response_fn(payload)` for the response. Returns the
    list of decision_ids logged during this run (there's at most one per
    request, but kept as a list for symmetry).
    """
    stream_input: Any = initial_state
    decision_ids: list[str] = []

    while True:
        interrupt_payload = None
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                continue
            for node_name, node_update in chunk.items():
                print_node(node_name, node_update)
                if node_update and node_update.get("decision_id"):
                    decision_ids.append(node_update["decision_id"])

        if interrupt_payload is not None:
            assert human_response_fn is not None, "graph interrupted but no human_response_fn was supplied"
            response = human_response_fn(interrupt_payload)
            stream_input = Command(resume=response)
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return decision_ids


def print_node(node_name: str, node_update: dict) -> None:
    if node_name == "check_boundary":
        bc = node_update["boundary_check"]
        print(f"CHECK_BOUNDARY   within_boundary={bc['within_boundary']}  ({bc['reason']})")
    elif node_name == "auto_act":
        print("AUTO_ACT         acted autonomously - no human call needed")
    elif node_name == "escalate_operational":
        print("ESCALATE         -> awaiting human sign-off (interrupt fired)")
    elif node_name == "log_operational":
        print(f"LOG_OPERATIONAL  five-part record written: {node_update['decision_id']}")
        print()
    elif node_name == "validate_proposal":
        v = node_update["validation"]
        status = "ALL 4 CONDITIONS SATISFIED" if v["approved"] else "REJECTED"
        print(f"VALIDATE_PROPOSAL   {status}")
        for reason in v["failed_conditions"]:
            print(f"                    - {reason}")
    elif node_name == "reject_proposal":
        print(f"REJECT_PROPOSAL     deterministic rejection logged: {node_update['decision_id']}  (no interrupt ever fired)")
        print()
    elif node_name == "approver_signoff":
        print("APPROVER_SIGNOFF    -> routed to the named approver (interrupt fired)")
    elif node_name == "apply_tier_change":
        a = node_update["applied_state"]
        print(f"APPLY_TIER_CHANGE   new policy_version={a['new_policy_version']}  new_boundary=({a['new_boundary']})")
    elif node_name == "log_governance_approved":
        print(f"LOG_GOVERNANCE      approved tier-change record written: {node_update['decision_id']}")
        print()
    elif node_name == "log_governance_declined":
        print(f"LOG_GOVERNANCE      declined-by-approver record written: {node_update['decision_id']}")
        print()
    elif node_name == "evaluate_reversal":
        r = node_update["reversal_result"]
        print(f"EVALUATE_REVERSAL   fired={r['fired']}  ({r['explanation']})")
    elif node_name == "rollback_tier":
        print(f"ROLLBACK_TIER       automatic rollback logged: {node_update['decision_id']}  (no human call involved)")
        print()
    elif node_name == "no_rollback":
        print("NO_ROLLBACK         trigger did not fire - boundary unchanged")
        print()


def scenario_1_within_boundary(graph, ledger: DecisionLedger) -> None:
    print("=" * 76)
    print("SCENARIO 1 — within-boundary Tier 2 action (auto-act)")
    print("=" * 76)
    scenario = _SCENARIOS["scenario_1"]
    action = scenario["action"]
    state = make_initial_operational_state(scenario["agent_id"], action)
    config = {"configurable": {"thread_id": "scenario-1"}}
    run_request(graph, config, state)


def scenario_2_out_of_boundary(graph, ledger: DecisionLedger) -> None:
    print("=" * 76)
    print("SCENARIO 2 — out-of-boundary action (escalates before acting)")
    print("=" * 76)
    scenario = _SCENARIOS["scenario_2"]
    action = scenario["action"]
    state = make_initial_operational_state(scenario["agent_id"], action)
    config = {"configurable": {"thread_id": "scenario-2"}}

    def human_response(payload: dict) -> dict:
        contact = payload["escalation_contact"]
        print(f"  [{contact}] reviewing: {payload['action']['description']}")
        print(f"  [{contact}] boundary check said: {payload['boundary_check']['reason']}")
        print(f"  [{contact}] approving this one, logged under my name.\n")
        return {"approved": True, "approved_by": contact, "notes": "Reviewed and approved - within acceptable risk for this specific case."}

    run_request(graph, config, state, human_response)


def scenario_3_valid_widening(graph, ledger: DecisionLedger, registry: PolicyRegistry) -> None:
    print("=" * 76)
    print("SCENARIO 3 — Arjun's tier-widening proposal (all 4 conditions met)")
    print("=" * 76)
    proposal = _proposal_from_json(_SCENARIOS["scenario_3"]["proposal"])
    state = make_initial_governance_state(proposal, STORY_TODAY)
    config = {"configurable": {"thread_id": "scenario-3"}}

    def human_response(payload: dict) -> dict:
        print(f"  [{payload['approver']}] proposal from {payload['proposer']}: {payload['proposal']['rationale']}")
        print(f"  [{payload['approver']}] all 4 policy-as-code conditions came in satisfied - signing off.\n")
        return {"approved": True, "approved_by": payload["approver"], "notes": "Reviewed the 130-decision track record and the reversal trigger; approved."}

    run_request(graph, config, state, human_response)


def scenario_4_rejected_widening(graph, ledger: DecisionLedger) -> None:
    print("=" * 76)
    print("SCENARIO 4 — a further widening, REJECTED outright (no interrupt)")
    print("=" * 76)
    # reversal_trigger is null in the JSON - the missing condition.
    proposal = _proposal_from_json(_SCENARIOS["scenario_4"]["proposal"])
    state = make_initial_governance_state(proposal, STORY_TODAY)
    config = {"configurable": {"thread_id": "scenario-4"}}
    # No human_response_fn supplied on purpose: if this proposal somehow
    # reached an interrupt, this call would raise rather than silently
    # approve it. It should never need to.
    run_request(graph, config, state, human_response_fn=None)


def scenario_5_reversal_fires(graph, ledger: DecisionLedger) -> None:
    print("=" * 76)
    print("SCENARIO 5 — reversal trigger fires, automatic rollback (no human)")
    print("=" * 76)
    scenario = _SCENARIOS["scenario_5"]
    # recent_decisions[2] (missed_commitment=True) is the one that trips it.
    recent_decisions = scenario["recent_decisions"]
    state = make_initial_reversal_state(scenario["agent_id"], recent_decisions)
    config = {"configurable": {"thread_id": "scenario-5"}}
    run_request(graph, config, state, human_response_fn=None)


def main() -> None:
    registry = PolicyRegistry()
    ledger = DecisionLedger()
    graph = build_graph(registry, ledger).compile(checkpointer=InMemorySaver())

    scenario_1_within_boundary(graph, ledger)
    scenario_2_out_of_boundary(graph, ledger)

    arjun_before = registry.get("arjun-allocation-agent")
    print(f"Arjun's agent before scenario 3: policy_version={arjun_before.policy_version}, boundary=({arjun_before.boundary.describe()})\n")

    scenario_3_valid_widening(graph, ledger, registry)

    arjun_after = registry.get("arjun-allocation-agent")
    print(f"Arjun's agent after scenario 3:  policy_version={arjun_after.policy_version}, boundary=({arjun_after.boundary.describe()})\n")

    scenario_4_rejected_widening(graph, ledger)
    scenario_5_reversal_fires(graph, ledger)

    arjun_final = registry.get("arjun-allocation-agent")
    print(f"Arjun's agent after scenario 5:  policy_version={arjun_final.policy_version}, boundary=({arjun_final.boundary.describe()})")
    print(
        "(back to the original single-claim/Rs.25,000 boundary - the automatic "
        "reversal trigger rolled it back without anyone proposing, approving, "
        "or even being asked about it.)\n"
    )

    intact, broken_id = ledger.verify_chain()
    print("=" * 76)
    print(f"Decision ledger: {ledger.records_count()} records written, chain intact = {intact}" + ("" if intact else f" (broken at {broken_id})"))
    print(
        "\nNothing here removed a human from the decisions that actually needed "
        "one. Scenario 2's escalation and scenario 3's sign-off still went to a "
        "named person, with the full boundary check or the full policy-as-code "
        "validation attached. What moved is scenario 4 and scenario 5: a proposal "
        "missing a required condition, and a boundary that needed to roll back, "
        "were both handled by deterministic code before anyone had to notice, "
        "argue about it, or improvise a call under pressure."
    )


if __name__ == "__main__":
    main()
