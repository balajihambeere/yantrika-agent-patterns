"""
A continuous reasoning loop, built as an actual LangGraph `StateGraph`.

A bounded-task agent anatomy — Trigger -> Perceive -> Decide -> Act ->
Escalate -> Log — fits a task with a finish line: a PO lands, the agent
reacts, logs the outcome, and is done until the next one arrives. A
system reasoning continuously about a shifting trade-off has no single
trigger and no finished state; the situation it's reasoning about never
stops changing. What it needs instead, in Vikram's
words, is "a loop instead of a line":

    Sense -> Weigh -> Recommend -> Escalate (what exceeds its authority)
    -> Log (the reasoning itself, not just the outcome) -> back to Sense.

This module is that loop, expressed as a LangGraph StateGraph:

    START -> sense --(nothing left to sense)--> END
                |--(a sensing cycle to react to)--> weigh
    weigh -> recommend
    recommend --(factors clearly agree AND exposure under threshold)--> act
    recommend --(close call OR exposure over threshold)--> escalate --> act
    act -> log -> sense   (back to the top of the loop)

`escalate` uses LangGraph's `interrupt()` — the graph genuinely pauses and
hands control back to whatever is driving it. Resuming requires a
`Command(resume=...)`. The payload carried into that interrupt is the
*full* per-factor reasoning (every weighted score, every rationale line),
never a bare recommendation — escalating without the reasoning attached
would defeat the point of escalating at all.

`weigh()` and `recommend()` call straight into `reasoning_factors.py` —
plain, deterministic arithmetic, no LLM call. The "reasoning" here is
reasoning over explicit, revisable, named factors, not a language model
guessing at an allocation. Swapping in a model later would be a change to
that one module; the graph topology — sense, weigh, recommend, escalate,
log, back to sense — is the part that wouldn't need to move at all.

There is no natural END for a continuous reasoning system (the whole
point is that the situation it reasons about never finishes changing).
`sense()` pulls the next scripted sensing cycle off a bounded queue so a
demo or test can run a fixed number of cycles and stop cleanly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from reasoning_factors import (
    AllocationResult,
    CompetingOrder,
    FactorScores,
    allocate_units,
    check_bounded_autonomy,
    rank_orders,
    score_order,
)


class SensingCycle(TypedDict):
    label: str
    available_units: int
    orders: list[CompetingOrder]


class GraphState(TypedDict):
    sku: str
    pending_cycles: list[SensingCycle]
    cycle: Optional[SensingCycle]
    reasoning: Optional[list[FactorScores]]
    recommendation: Optional[dict[str, Any]]
    decision: Optional[dict[str, Any]]
    log: list[dict[str, Any]]


def make_initial_state(sku: str, pending_cycles: list[SensingCycle]) -> GraphState:
    return GraphState(
        sku=sku,
        pending_cycles=pending_cycles,
        cycle=None,
        reasoning=None,
        recommendation=None,
        decision=None,
        log=[],
    )


def sense(state: GraphState) -> dict[str, Any]:
    """Pull the next competing-claims snapshot off the queue. Clears last cycle's transients."""
    pending = state["pending_cycles"]
    if not pending:
        return {"cycle": None}

    cycle, remaining = pending[0], pending[1:]
    return {
        "pending_cycles": remaining,
        "cycle": cycle,
        "reasoning": None,
        "recommendation": None,
        "decision": None,
    }


def route_after_sense(state: GraphState) -> Literal["weigh", "__end__"]:
    return END if state["cycle"] is None else "weigh"


def weigh(state: GraphState) -> dict[str, Any]:
    """Score every competing order against all five factors. Deterministic, no model."""
    cycle = state["cycle"]
    scored = [score_order(order) for order in cycle["orders"]]
    return {"reasoning": scored}


def recommend(state: GraphState) -> dict[str, Any]:
    """
    Turn the per-order factor scores into a ranked, weighted allocation
    recommendation, and run the bounded-autonomy-threshold check: clear
    factor agreement AND exposure under the agreed threshold routes
    straight to `act`; anything else must be escalated to a human with
    the full reasoning attached.
    """
    cycle = state["cycle"]
    ranked = rank_orders(state["reasoning"])
    ranking = [s["account"] for s in ranked]
    allocation = allocate_units(cycle["available_units"], cycle["orders"], ranking)
    autonomy = check_bounded_autonomy(ranked, cycle["orders"], allocation)

    recommendation = {
        "sku": state["sku"],
        "cycle_label": cycle["label"],
        "available_units": cycle["available_units"],
        "ranking": ranking,
        "allocation": allocation,
        "requires_human": autonomy["requires_human"],
        "clear_agreement": autonomy["clear_agreement"],
        "exposure_on_losing_side": autonomy["exposure_on_losing_side"],
        "reason": autonomy["reason"],
    }
    return {"recommendation": recommendation}


def route_after_recommend(state: GraphState) -> Literal["escalate", "act"]:
    return "escalate" if state["recommendation"]["requires_human"] else "act"


def escalate(state: GraphState) -> dict[str, Any]:
    """
    The one branch where a human can intervene. `interrupt()` genuinely
    pauses the graph — nothing is acted on until the caller resumes it with
    `Command(resume=...)`. The payload is the full weighted reasoning, not
    a bare recommendation — anything less would defeat the point of
    escalating at all.
    """
    rec = state["recommendation"]
    response = interrupt(
        {
            "sku": state["sku"],
            "cycle_label": rec["cycle_label"],
            "reason": rec["reason"],
            "exposure_on_losing_side": rec["exposure_on_losing_side"],
            "clear_agreement": rec["clear_agreement"],
            "reasoning": state["reasoning"],
            "recommended_allocation": rec["allocation"],
        }
    )

    decided_by = response.get("decided_by", "unknown")
    if response.get("decision") == "override":
        final_allocation = response["allocation"]
        overridden = True
        override_reason = response.get("reason", "")
    else:
        final_allocation = rec["allocation"]
        overridden = False
        override_reason = None

    decision = {
        "allocation": final_allocation,
        "decided_by": decided_by,
        "autonomous": False,
        "overridden": overridden,
        "override_reason": override_reason,
    }
    return {"decision": decision}


def act(state: GraphState) -> dict[str, Any]:
    """
    Carry out the decision — the escalated human's call if this cycle was
    escalated, otherwise the system's own recommendation, since clearing
    the bounded-autonomy threshold *is* the authorization to act alone.
    """
    if state["decision"] is not None:
        decision = state["decision"]
    else:
        rec = state["recommendation"]
        decision = {
            "allocation": rec["allocation"],
            "decided_by": "system (autonomous)",
            "autonomous": True,
            "overridden": False,
            "override_reason": None,
        }
    return {"decision": decision}


def log(state: GraphState) -> dict[str, Any]:
    """
    Record the actual weights and scores used for this decision, not just
    the final allocation — the reasoning itself, not only the outcome,
    has to be auditable later.
    """
    cycle = state["cycle"]
    rec = state["recommendation"]
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sku": state["sku"],
        "cycle_label": cycle["label"],
        "available_units": cycle["available_units"],
        "reasoning": state["reasoning"],  # every factor score + rationale, per order
        "ranking": rec["ranking"],
        "recommended_allocation": rec["allocation"],
        "requires_human": rec["requires_human"],
        "clear_agreement": rec["clear_agreement"],
        "exposure_on_losing_side": rec["exposure_on_losing_side"],
        "escalation_reason": rec["reason"],
        "decision": state["decision"],
    }
    return {"log": state["log"] + [entry]}


def build_graph():
    """Wire the loop: START -> sense -> weigh -> recommend -> (escalate) -> act -> log -> sense ..."""
    graph = StateGraph(GraphState)

    # Step 1: register the nodes — sense, weigh, recommend, escalate, act, log.
    graph.add_node("sense", sense)
    graph.add_node("weigh", weigh)
    graph.add_node("recommend", recommend)
    graph.add_node("escalate", escalate)
    graph.add_node("act", act)
    graph.add_node("log", log)

    # Step 2: wire the entry point and the two routing decisions — whether
    # there's a cycle left to sense, and whether the bounded-autonomy
    # threshold clears (straight to act) or needs a human (escalate first).
    graph.add_edge(START, "sense")
    graph.add_conditional_edges("sense", route_after_sense, {"weigh": "weigh", END: END})
    graph.add_edge("weigh", "recommend")
    graph.add_conditional_edges("recommend", route_after_recommend, {"escalate": "escalate", "act": "act"})

    # Step 3: wire the remaining fixed edges, including the one that
    # closes the loop — log always sends control back to sense.
    graph.add_edge("escalate", "act")
    graph.add_edge("act", "log")
    graph.add_edge("log", "sense")  # back to the top of the loop
    return graph
