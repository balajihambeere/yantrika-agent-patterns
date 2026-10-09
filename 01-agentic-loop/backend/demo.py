"""
Runnable companion demo, built on LangGraph.

Replays a compressed version of an overnight sequence through two
different systems:

  1. A frozen T-1 batch report plus a conversational chatbot stub — the
     world Aditi actually had on her desk that Tuesday morning.
  2. A LangGraph agent graph watching the same ledger continuously,
     handling the low-risk response itself and pausing on a real
     `interrupt()` for the one decision that actually needs a human — the
     structural difference an agentic system has over a chatbot.

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

from agentic_graph import PendingEvent, build_graph, make_initial_state
from chatbot import ConversationalStub

# The scripted overnight scenario (SKU, the frozen batch-report balance, and
# the three overnight transactions) lives in data/overnight_scenario.json —
# see that file for the per-event timestamps in clock form:
#   minutes_after_start=70  -> 00:10 (1h10m after the 11:00 PM batch run)
#   minutes_after_start=160 -> 01:40
#   minutes_after_start=455 -> 06:35
_SCENARIO_PATH = Path(__file__).parent / "data" / "overnight_scenario.json"
with _SCENARIO_PATH.open(encoding="utf-8") as _scenario_file:
    _scenario = json.load(_scenario_file)

SKU = _scenario["sku"]
BATCH_REPORT_BALANCE = _scenario["batch_report_balance"]  # frozen at 11:00 PM, never updates again
OVERNIGHT_EVENTS: list[PendingEvent] = _scenario["overnight_events"]


def minutes_to_clock(minutes_after_11pm: int) -> str:
    hour = (23 * 60 + minutes_after_11pm) // 60 % 24
    minute = (23 * 60 + minutes_after_11pm) % 60
    return f"{hour:02d}:{minute:02d}"


def run_chatbot_part() -> None:
    print("=" * 76)
    print("PART 1 — the chatbot, asked at 7:05 AM")
    print("=" * 76)
    chatbot = ConversationalStub()
    question = "Is there enough stock of the 4200 series harness for Line 3's run?"
    total_draw = sum(-e["delta"] for e in OVERNIGHT_EVENTS)
    print(f"Aditi asks the intranet chatbot: {question!r}")
    print(f"Chatbot answers: {chatbot.ask(question)!r}")
    print(
        f"\nThe batch report Aditi is holding still says {BATCH_REPORT_BALANCE} units. "
        f"The live ledger — which the chatbot never consulted — is about to be drawn "
        f"down by {total_draw} units overnight, to {BATCH_REPORT_BALANCE - total_draw}. "
        f"The chatbot's answer was fluent, on-brand, and useless: it had no path from "
        f"'here is an answer' to 'here is what's actually happening right now.'\n"
    )


def auto_approve(payload: dict) -> dict:
    """Stands in for a human clicking 'approve' in a real review UI."""
    print(f"  [HUMAN ESCALATION] action requested: {payload['action']}")
    print(f"  [HUMAN ESCALATION] rationale: {payload['rationale']}")
    response = {"approved": True, "approved_by": "Aditi Kulkarni"}
    print(f"  [HUMAN ESCALATION] approved by {response['approved_by']}\n")
    return response


def run_agent_part() -> list[dict]:
    print("=" * 76)
    print("PART 2 — the LangGraph agent, watching the same ledger overnight")
    print("=" * 76)

    graph = build_graph().compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "vimana-4200-harness-overnight"}}
    state = make_initial_state(
        sku=SKU,
        opening_balance=BATCH_REPORT_BALANCE,
        run_rate_per_minute=4,  # Line 3's planned draw rate once it's running
        pending_events=list(OVERNIGHT_EVENTS),
    )

    resume_value = state  # first call starts the graph; later calls resume it
    is_resuming = False

    while True:
        stream_input = Command(resume=resume_value) if is_resuming else resume_value
        interrupt_payload = None

        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                continue

            for node_name, node_update in chunk.items():
                if node_name == "observe" and node_update.get("observation"):
                    obs = node_update["observation"]
                    ts = minutes_to_clock(obs["minutes_after_start"])
                    print(f"[{ts}] OBSERVE  balance={obs['balance']:>4}  ({obs['last_transaction']})")
                elif node_name == "decide":
                    d = node_update["decision"]
                    print(f"        DECIDE   {d['action']} [{d['risk']}]")
                    print(f"                 {d['rationale']}")
                elif node_name == "act":
                    entry = node_update["log"][-1]
                    print(f"        ACT      {entry['outcome']}")
                    print()

        if interrupt_payload is not None:
            resume_value = auto_approve(interrupt_payload)
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:  # graph reached END — nothing left to run
            return snapshot.values.get("log", [])


def main() -> None:
    run_chatbot_part()
    log = run_agent_part()

    print("-" * 76)
    final_balance = log[-1]["observation"]["balance"] if log else BATCH_REPORT_BALANCE
    print(f"Final live balance:            {final_balance} units")
    print(f"Batch report still reads:      {BATCH_REPORT_BALANCE} units")
    print(f"Audit trail — log entries:     {len(log)} (observation, decision, rationale, outcome, each timestamped)")
    print(
        "\nNothing here removed Aditi from the decision — it moved her from reading a "
        "stale number after the fact to approving one specific, flagged, well-reasoned "
        "call before a line actually stopped."
    )


if __name__ == "__main__":
    main()
