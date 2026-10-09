"""
The agentic loop pattern, built as an actual LangGraph graph.

There are two shapes to contrast: a conversational system is a line
that stops (ask -> answer -> a human reads it, decides, and acts entirely
outside the system), while an agentic system is a loop that doesn't
(Observe -> Decide -> Act -> Log -> back to Observe), with one branch where
a human can intervene before a decision is acted on.

This module is that loop, expressed as a LangGraph StateGraph:

    START -> observe --(nothing left to see)--> END
                |--(something to react to)--> decide
    decide --(low/medium risk)--> act
    decide --(high risk)--> human_review --> act
    act -> observe   (back to the top of the loop)

`human_review` uses LangGraph's `interrupt()` — the graph genuinely pauses
and hands control back to whatever is driving it, instead of calling an
automated "approver" function. Resuming requires a `Command(resume=...)`,
the same mechanism a real human-in-the-loop UI would use to approve or
reject an agent's proposed action.

decide() itself stays rule-based (simple threshold logic) — LangGraph here
is doing the orchestration job the pattern describes, not standing in for
a language model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

SAFETY_THRESHOLD_MINUTES = 60


class PendingEvent(TypedDict):
    minutes_after_start: int
    delta: int  # negative = stock drawn, positive = stock added
    note: str


class GraphState(TypedDict):
    sku: str
    run_rate_per_minute: float
    balance: int
    pending_events: list[PendingEvent]
    alerted: bool
    observation: Optional[dict[str, Any]]
    decision: Optional[dict[str, Any]]
    log: list[dict[str, Any]]


def make_initial_state(
    sku: str,
    opening_balance: int,
    run_rate_per_minute: float,
    pending_events: list[PendingEvent],
) -> GraphState:
    return GraphState(
        sku=sku,
        run_rate_per_minute=run_rate_per_minute,
        balance=opening_balance,
        pending_events=pending_events,
        alerted=False,
        observation=None,
        decision=None,
        log=[],
    )


def observe(state: GraphState) -> dict[str, Any]:
    """Pull the next transaction off the queue and apply it to the live balance."""
    pending = state["pending_events"]
    if not pending:
        return {"observation": None}

    event, remaining = pending[0], pending[1:]
    new_balance = state["balance"] + event["delta"]
    return {
        "pending_events": remaining,
        "balance": new_balance,
        "observation": {
            "minutes_after_start": event["minutes_after_start"],
            "balance": new_balance,
            "last_transaction": event["note"],
        },
    }


def route_after_observe(state: GraphState) -> Literal["decide", "__end__"]:
    return END if state["observation"] is None else "decide"


def decide(state: GraphState) -> dict[str, Any]:
    """Turn the latest observation into a proposed decision."""
    observation = state["observation"]
    sku = state["sku"]
    balance = observation["balance"]
    minutes_of_cover = balance / state["run_rate_per_minute"] if state["run_rate_per_minute"] else float("inf")

    if minutes_of_cover >= SAFETY_THRESHOLD_MINUTES:
        decision = {
            "action": "no_action",
            "rationale": f"{minutes_of_cover:.0f} min of cover on {sku} — above the "
            f"{SAFETY_THRESHOLD_MINUTES}-min threshold.",
            "risk": "low",
            "requires_human": False,
            "approved": True,
            "approved_by": None,
        }
    elif not state["alerted"]:
        decision = {
            "action": "alert_floor_and_stores",
            "rationale": (
                f"Cover on {sku} has dropped to {minutes_of_cover:.0f} min after "
                f"'{observation['last_transaction']}'. Below threshold — raising now "
                f"instead of waiting for tonight's batch report to catch it."
            ),
            "risk": "medium",
            "requires_human": False,
            "approved": True,
            "approved_by": None,
        }
    else:
        decision = {
            "action": "expedite_replacement_shipment",
            "rationale": (
                f"Cover on {sku} is {minutes_of_cover:.0f} min and still falling after an "
                f"alert was already raised. An alert alone won't prevent a line stop — "
                f"this needs an irreversible, cost-bearing call that a human should make."
            ),
            "risk": "high",
            "requires_human": True,
            "approved": False,
            "approved_by": None,
        }

    update: dict[str, Any] = {"decision": decision}
    if decision["action"] == "alert_floor_and_stores":
        update["alerted"] = True
    return update


def route_after_decide(state: GraphState) -> Literal["human_review", "act"]:
    return "human_review" if state["decision"]["requires_human"] else "act"


def human_review(state: GraphState) -> dict[str, Any]:
    """
    The one branch in the agentic-loop diagram where a human can intervene.
    `interrupt()` genuinely pauses the graph here — execution does not
    continue until the caller resumes it with `Command(resume=...)`.
    """
    decision = dict(state["decision"])
    response = interrupt(
        {
            "action": decision["action"],
            "rationale": decision["rationale"],
            "risk": decision["risk"],
        }
    )
    decision["approved"] = bool(response.get("approved", False))
    decision["approved_by"] = response.get("approved_by")
    return {"decision": decision}


def act(state: GraphState) -> dict[str, Any]:
    """Carry out the decision (if approved) and append an audit-log entry."""
    decision = state["decision"]
    observation = state["observation"]

    if decision["approved"]:
        outcome = f"executed '{decision['action']}'"
        if decision.get("approved_by"):
            outcome += f" (approved by {decision['approved_by']})"
    else:
        outcome = f"declined '{decision['action']}' — not approved"

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "observation": observation,
        "decision": decision,
        "outcome": outcome,
    }
    return {"log": state["log"] + [entry]}


def build_graph(decide_fn=None):
    """Wire the loop together: START -> observe -> decide -> (human_review) -> act -> observe ...

    `decide_fn` lets a caller swap in an alternate "decide" node (e.g. an
    LLM-backed one — see decide_llm.py) without touching this module or the
    deterministic `decide()` above. It defaults to `decide`, so every
    existing call to `build_graph()` keeps producing the exact same graph.
    """
    if decide_fn is None:
        decide_fn = decide

    graph = StateGraph(GraphState)

    # Step 1: register the nodes — observe, decide, human_review, act.
    graph.add_node("observe", observe)
    graph.add_node("decide", decide_fn)
    graph.add_node("human_review", human_review)
    graph.add_node("act", act)

    # Step 2: wire the entry point and the two routing decisions —
    # where to go after observe (decide, or END if there's nothing left),
    # and where to go after decide (human_review, or straight to act).
    graph.add_edge(START, "observe")
    graph.add_conditional_edges("observe", route_after_observe, {"decide": "decide", END: END})
    graph.add_conditional_edges("decide", route_after_decide, {"human_review": "human_review", "act": "act"})

    # Step 3: wire the remaining fixed edges, including the one that
    # closes the loop — act always sends control back to observe.
    graph.add_edge("human_review", "act")
    graph.add_edge("act", "observe")  # back to the top of the loop
    return graph
