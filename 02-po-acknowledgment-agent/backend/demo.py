"""
Runnable companion demo for the PO-acknowledgment agent, built on
LangGraph.

Drives the PO-acknowledgment agent through four worked-example scenarios
— a clean confirmation, a 48-hour no-reply chase, a schedule slip caught
by the hard invariant, and an ambiguous "noted, will advise" reply —
first through the two-week *supervised* go-live (every action queued for
Neha's approval), then again through the *earned-autonomy* stage
(routine actions fire on their own; escalations still always go to
Neha). A third part demonstrates the two guardrails that live entirely
inside perceive: the per-supplier exception table, and the
attachment-specific confidence score.

Run with:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 demo.py

Each graph run is streamed with `stream_mode="updates"` and printed
node-by-node, as it fires — not read back from the final state after the
fact — so the printed order is the true chronological order the graph
actually executed in.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent_graph import build_graph, make_initial_state

APPROVER = "Neha"

_SCENARIOS_PATH = Path(__file__).parent / "data" / "demo_scenarios.json"
with open(_SCENARIOS_PATH, encoding="utf-8") as _f:
    _SCENARIOS: dict[str, Any] = json.load(_f)


def _scenario(name: str) -> dict:
    """Return a fresh copy of a named scenario's PO dict, loaded from
    data/demo_scenarios.json, so repeated calls (e.g. across the
    supervised and autonomous runs of run_part) never share mutable
    state."""
    return copy.deepcopy(_SCENARIOS[name])


def approve_action(payload: dict[str, Any]) -> dict[str, Any]:
    print(f"  [APPROVAL QUEUE] {payload['po_number']} ({payload['supplier']}): "
          f"proposes '{payload['proposed_action']}'")
    print(f"  [APPROVAL QUEUE] rationale: {payload['rationale']}")
    print(f"  [APPROVAL QUEUE] {APPROVER} clicks approve\n")
    return {"approved": True, "approved_by": APPROVER}


def acknowledge_escalation(payload: dict[str, Any], note: str) -> dict[str, Any]:
    print(f"  [ESCALATION] {payload['po_number']} ({payload['supplier']}): {payload['action']}")
    print(f"  [ESCALATION] rationale: {payload['rationale']}")
    if payload["hard_invariant_triggered"]:
        print(
            f"  [ESCALATION] hard invariant: PO says {payload['ordered_qty']} units / "
            f"{payload['ordered_date']}; reply read as {payload['extracted_qty']} units / "
            f"{payload['extracted_date']}"
        )
    print(f"  [ESCALATION] {APPROVER} reviews: {note}\n")
    return {"acknowledged_by": APPROVER, "note": note}


def run_po(graph, thread_id: str, initial_state, escalation_note: str = "Reviewed, logged for follow-up.") -> list[dict]:
    """
    Streams one PO through the graph, printing each box of the anatomy as
    it actually fires, and resumes past every `interrupt()` with the
    scripted human response appropriate to its kind.
    """
    config = {"configurable": {"thread_id": thread_id}}
    stream_input = initial_state
    is_resuming = False

    while True:
        interrupt_payload = None
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                continue
            for node_name, update in chunk.items():
                if node_name == "trigger":
                    t = update["trigger"]
                    extra = f" via={t['matched_via']}" if t["matched_via"] else ""
                    print(f"[{thread_id}] TRIGGER   reason={t['reason']}{extra}")
                elif node_name == "perceive":
                    p = update["perception"]
                    print(
                        f"           PERCEIVE  situation={p['situation']} "
                        f"confidence={p['confidence']:.2f}"
                    )
                    print(f"                     {p['notes']}")
                elif node_name == "decide":
                    d = update["decision"]
                    print(f"           DECIDE    action={d['action']} [risk={d['risk']}]")
                    print(f"                     {d['rationale']}")
                elif node_name == "act":
                    print(f"           ACT       {update['action_result']['outcome']}")
                elif node_name == "escalate":
                    e = update["escalation_result"]
                    print(f"           ESCALATE  acknowledged_by={e['acknowledged_by']} note={e['note']!r}")
                elif node_name == "log":
                    print(f"           LOG       entry #{len(update['log'])} recorded\n")

        if interrupt_payload is not None:
            if interrupt_payload["kind"] == "action_approval":
                stream_input = Command(resume=approve_action(interrupt_payload))
            else:
                stream_input = Command(resume=acknowledge_escalation(interrupt_payload, escalation_note))
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values.get("log", [])


# --- Scenario data, grounded in the agent's worked examples ----------------


def clean_confirmation() -> dict:
    """Deccan Fasteners confirms exactly, but the reply is mis-threaded —
    filed under an old invoice thread rather than the PO's own thread.
    Guardrail #2 (reference-number matching across threads) is what
    makes this still resolve to log_only instead of looking like
    silence."""
    return _scenario("clean_confirmation")


def chase_needed() -> dict:
    """Konkan Metal Works: 48 hours with nothing resembling acknowledgment."""
    return _scenario("chase_needed")


def schedule_slip() -> dict:
    """Satpura Components confirms the quantity but quietly moves the
    delivery date by six days, buried inside routine-sounding text — a
    canonical "genuine slip missed as clean" failure mode, now caught by
    the hard invariant regardless of perceive's confidence."""
    return _scenario("schedule_slip")


def ambiguous_reply() -> dict:
    """Bharat Precision Forge's standard non-answer: commits to nothing."""
    return _scenario("ambiguous_reply")


def run_part(title: str, supervised: bool, graph) -> None:
    print("=" * 76)
    print(title)
    print("=" * 76)
    scenarios = [
        ("clean-confirmation", clean_confirmation(), "n/a"),
        ("chase-needed", chase_needed(), "n/a"),
        ("schedule-slip", schedule_slip(), "Called Satpura; six-day slip confirmed real, customer commitment date updated."),
        ("ambiguous-reply", ambiguous_reply(), "Chased Bharat Precision Forge by phone; they hadn't actually checked stock yet."),
    ]
    stage = "supervised" if supervised else "autonomous"
    for label, po, note in scenarios:
        state = make_initial_state(po, supervised=supervised)
        run_po(graph, f"{stage}-{label}", state, escalation_note=note)


def run_guardrails_in_action(graph) -> None:
    print("=" * 76)
    print("PART 3 -- guardrails that live inside perceive")
    print("=" * 76)

    # Guardrail #3: Neha's supplier exception, scoped to exactly one
    # supplier. Same date-less text, two suppliers, two different reads.
    exception_owner = _scenario("exception_owner")
    no_exception = _scenario("no_exception")
    print("-- same text, two suppliers: Neha's exception applies to Bharat Precision Forge only --")
    run_po(graph, "exception-scoped-to-one-supplier", make_initial_state(exception_owner, supervised=False),
           "Confirmed by phone -- he really hadn't checked yet, exactly the pattern Neha flagged.")
    run_po(graph, "exception-does-not-generalize", make_initial_state(no_exception, supervised=False))

    # Guardrail #1: the stamped-PDF attachment gets its own confidence.
    good_scan = _scenario("good_scan")
    bad_scan = _scenario("bad_scan")
    print("-- same supplier, two scan qualities: attachment confidence decides, not text confidence --")
    run_po(graph, "stamped-pdf-good-scan", make_initial_state(good_scan, supervised=False))
    run_po(graph, "stamped-pdf-bad-scan", make_initial_state(bad_scan, supervised=False),
           "Called to confirm -- scan was legible on their end, re-requesting a clean copy.")


def main() -> None:
    graph = build_graph().compile(checkpointer=InMemorySaver())

    run_part("PART 1 -- two-week supervised go-live (every action queued for Neha)", True, graph)
    print(
        "Every single action above -- including the clean log-only and the routine chase --\n"
        "sat in the approval queue. That is staged autonomy: trust is earned across real\n"
        "days, not declared in a design document.\n"
    )

    run_part("PART 2 -- after the exit criterion is met (earned autonomy)", False, graph)
    print(
        "Same four scenarios, same graph, one flag flipped. log_only and send_chase now\n"
        "fire without a per-item approval -- but escalate_unclear and escalate_mismatch\n"
        "still interrupted for Neha above, exactly as before: escalations and hard-invariant\n"
        "hits always go to a human, forever, by design, regardless of autonomy stage.\n"
    )

    run_guardrails_in_action(graph)


if __name__ == "__main__":
    main()
