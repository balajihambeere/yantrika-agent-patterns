"""
Recreates Kavita's dramatized test directly: she picks a single decision
at random from eleven weeks back and asks Arjun to walk her through
exactly why the agent decided what it decided — which specific factors
tipped it, and which policy was actually live on that date, not today's.
In the original incident, it took Arjun almost twenty minutes of
cross-referencing three different logs and a change-history document
to answer even half of that, and he never fully answered the first
half.

This script proves the gap is closed: given nothing but a decision_id,
`decision_ledger.reconstruct()` / `print_full_record()` answers both
halves directly, in one lookup, no cross-referencing.

It seeds its own small scenario rather than depending on `demo.py`
having been run first — each script here is independently runnable:

  1. Logs ONE decision for Arjun's allocation agent, backdated eleven
     weeks before this script's "today," made under the ORIGINAL policy
     version (`policy-v1`).
  2. Simulates time passing and the policy changing (a tier-boundary
     widening, via `PolicyRegistry.apply_tier_change` directly — the
     same call `policy_gate_graph.apply_tier_change` makes once a
     proposal clears sign-off), so "today" the agent runs under
     `policy-v2`, a materially different boundary.
  3. Records the shipment's actual outcome, once known, as a separate
     linked ledger entry (the five-part record's fifth part), without
     touching the original record.
  4. Runs the audit: reconstructs the eleven-week-old decision and shows
     it is still correctly tied to `policy-v1` and the boundary that was
     actually live back then — not `policy-v2`, which is what's live
     today.
  5. Demonstrates the chain-of-custody check: the ledger verifies intact
     before any tampering, and after a direct, API-bypassing edit to a
     stored record's inputs, `verify_chain()` catches it and names
     exactly which record broke.

Run with:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 mock_audit.py
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from decision_ledger import DecisionLedger
from policy_engine import AutonomyTier, PolicyRegistry, ReversalTrigger, TierBoundary, TierChangeProposal

# The scripted sample scenario below (the backdated decision, the later
# policy change, and the outcome amendment) lives in
# data/mock_audit_scenario.json, loaded once here at import time, so
# this module stays pure code.
_SCENARIO = json.loads((Path(__file__).parent / "data" / "mock_audit_scenario.json").read_text())

AUDIT_TODAY = date.fromisoformat(_SCENARIO["audit_today"])  # the story's "today," set in September
ELEVEN_WEEKS_AGO = AUDIT_TODAY - timedelta(weeks=_SCENARIO["weeks_ago"])  # lands in early July


def seed_old_decision(ledger: DecisionLedger, registry: PolicyRegistry) -> str:
    """Logs the eleven-week-old decision under policy-v1 - Arjun's
    original, tight boundary (single claim, exposure under Rs.25,000)."""
    arjun_then = registry.get("arjun-allocation-agent")
    backdated_timestamp = datetime.combine(ELEVEN_WEEKS_AGO, datetime.min.time()).isoformat(timespec="seconds")

    old_decision = _SCENARIO["old_decision"]
    decision_id = ledger.log_decision(
        agent_id=arjun_then.agent_id,
        tier=int(arjun_then.tier),
        record_type="operational",
        inputs=old_decision["inputs"],
        policy_version=arjun_then.policy_version,  # "policy-v1" - captured at THIS moment, permanently
        model_version=old_decision["model_version"],
        reasoning_path=old_decision["reasoning_path"],
        human_actions=[],  # acted autonomously - within boundary, no escalation needed
        outcome=None,  # not yet known at decision time
        timestamp=backdated_timestamp,
    )
    return decision_id


def advance_policy_since_then(registry: PolicyRegistry) -> None:
    """Simulates a tier-boundary widening happening between the old
    decision and today - exactly the kind of policy drift the
    decision ledger has to survive without losing track of what was
    true when."""
    data = _SCENARIO["policy_change_proposal"]
    proposal = TierChangeProposal(
        agent_id=data["agent_id"],
        proposer=data["proposer"],
        approver=data["approver"],
        from_tier=AutonomyTier(data["from_tier"]),
        to_tier=AutonomyTier(data["to_tier"]),
        new_boundary=TierBoundary(
            max_competing_orders=data["new_boundary"]["max_competing_orders"],
            max_exposure_inr=data["new_boundary"]["max_exposure_inr"],
            notes=data["new_boundary"]["notes"],
        ),
        track_record_count=data["track_record_count"],
        track_record_minimum=data["track_record_minimum"],
        track_record_label=data["track_record_label"],
        reversal_trigger=ReversalTrigger(
            name=data["reversal_trigger"]["name"],
            metric=data["reversal_trigger"]["metric"],
            comparison=data["reversal_trigger"]["comparison"],
            threshold=data["reversal_trigger"]["threshold"],
            window_label=data["reversal_trigger"]["window_label"],
        ),
        re_review_date=date.fromisoformat(data["re_review_date"]),
        rationale=data["rationale"],
    )
    registry.apply_tier_change(proposal, approved_by=data["approved_by"])


def record_outcome_once_known(ledger: DecisionLedger, decision_id: str) -> None:
    """The five-part record's fifth part: the outcome, once known,
    linked back to the original decision - appended, never edited in."""
    outcome = _SCENARIO["outcome"]
    ledger.append_outcome(
        decision_id,
        outcome={
            "result": outcome["result"],
            "missed_commitment": outcome["missed_commitment"],
            "units_shipped": outcome["units_shipped"],
        },
        recorded_by=outcome["recorded_by"],
    )


def main() -> None:
    registry = PolicyRegistry()
    ledger = DecisionLedger()

    print("=" * 76)
    print(f"Seeding one operational decision, backdated to {ELEVEN_WEEKS_AGO.isoformat()} (eleven weeks before {AUDIT_TODAY.isoformat()})")
    print("=" * 76)
    decision_id = seed_old_decision(ledger, registry)
    print(f"Logged decision {decision_id} under policy_version="
          f"{registry.get('arjun-allocation-agent').policy_version}\n")

    print("Policy changes since then (a tier-boundary widening, simulated directly):")
    before_version = registry.get("arjun-allocation-agent").policy_version
    advance_policy_since_then(registry)
    after_version = registry.get("arjun-allocation-agent").policy_version
    print(f"  {before_version} -> {after_version}  (today's live boundary is now wider)\n")

    print("Recording the outcome, now that it's known, as a linked amendment:")
    record_outcome_once_known(ledger, decision_id)
    print("  done - original record untouched, new linked record appended\n")

    print("=" * 76)
    print("THE AUDIT — Kavita's question, asked of this ledger directly:")
    print(f'"Walk me through exactly why the agent decided what it decided, on '
          f'{ELEVEN_WEEKS_AGO.isoformat()}, for this specific order — and which '
          f'policy was live that day, not today\'s."')
    print("=" * 76)
    ledger.print_full_record(decision_id)

    print("\n" + "-" * 76)
    reconstructed_version = ledger.get(decision_id).policy_version
    current_version = registry.get("arjun-allocation-agent").policy_version
    print(f"Reconstructed decision's policy_version:  {reconstructed_version}")
    print(f"Today's live policy_version:               {current_version}")
    assert reconstructed_version != current_version, "the whole point is that these must differ"
    print("These differ ON PURPOSE - the record ties to the rules that were actually")
    print("live when the decision was made, never to whatever is live today.\n")

    old_snapshot = registry.snapshot_at("arjun-allocation-agent", reconstructed_version)
    print(f"What {reconstructed_version} actually said back then (resolved from policy_engine's version history):")
    print(f"  boundary: {old_snapshot.boundary.describe()}")
    print(f"  changed_by: {old_snapshot.changed_by}")

    current_state = registry.get("arjun-allocation-agent")
    print(f"\nWhat's live right now under {current_version}:")
    print(f"  boundary: {current_state.boundary.describe()}")
    print(
        "\nThis is the fix for that finding: one direct ledger lookup, not "
        "twenty minutes of cross-referencing three logs and a change-history document "
        "that was never built for this purpose."
    )

    print("\n" + "=" * 76)
    print("CHAIN OF CUSTODY — tamper-evidence check")
    print("=" * 76)
    intact, broken_id = ledger.verify_chain()
    print(f"Before any tampering: chain intact = {intact}")

    # Simulate someone editing a record's content directly, bypassing the
    # ledger's own API entirely - the thing "immutable by convention"
    # alone cannot stop, and the hash chain exists specifically to catch.
    tampered_record = ledger.get(decision_id)
    tampered_record.inputs["exposure_inr"] = _SCENARIO["tamper"]["exposure_inr"]  # mutating the dict in place

    intact_after, broken_id_after = ledger.verify_chain()
    print(f"After a direct, API-bypassing edit to {decision_id}'s inputs: chain intact = {intact_after}")
    if not intact_after:
        print(f"  -> verify_chain() correctly names the broken record: {broken_id_after}")
    print(
        "\nNothing in this ledger's Python API allows that edit - it only happened "
        "because this demonstration reached past the API directly. In a real "
        "deployment the records themselves would sit in genuinely write-once "
        "storage; the hash chain here is the same property, shown with the "
        "simplest honest tool available."
    )


if __name__ == "__main__":
    main()
