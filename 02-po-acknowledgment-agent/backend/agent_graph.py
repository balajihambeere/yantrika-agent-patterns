"""
The PO-acknowledgment agent — built as an actual LangGraph `StateGraph`.

The six-box productivity-agent anatomy — Trigger -> Perceive -> Decide ->
Act -> Escalate -> Log — is what every productivity agent needs. This
module is that anatomy as real graph structure, not an if/else buried in
one function:

    START -> trigger --(nothing to react to yet)--> END
                |--(a reply arrived, or 48h elapsed)--> perceive
    perceive -> decide
    decide --(hard invariant OR unclear/low-confidence)--> escalate -> log -> END
    decide --(log_only / send_chase, supervised)--> human_approval -> act -> log -> END
    decide --(log_only / send_chase, autonomous)--> act -> log -> END

Two LangGraph `interrupt()` call sites do the real human-in-the-loop work:

  * `human_approval` — the staged-autonomy approval queue. During the
    supervised go-live, EVERY action the agent proposes (even a clean
    "log only, no action") pauses here for Neha to approve before it
    fires. `state["supervised"]` is the knob: flip it to `False` once the
    exit criterion (a 95% match rate against Neha's own judgment, over a
    minimum volume) is met, and routine, low-risk actions (`log_only`,
    `send_chase`) go straight to `act` without per-item approval.
  * `escalate` — always interrupts, in BOTH stages: escalations and
    anything hitting the hard invariant always still go to a human,
    forever, by design, regardless of autonomy stage. `supervised` never
    gates this node at all.

`decide()` enforces the hard invariant unconditionally and first, before
it ever looks at perceive's confidence score — a date or quantity
mismatch above a small, fixed tolerance escalates full stop, regardless
of how confident perceive otherwise is. That is the central point, and
the reason the check sits at the top of the function, independent of
every other branch.

`perceive()` (in perception.py) is the only place supplier-specific tacit
knowledge (Neha's exception table) and attachment-specific confidence
live — `decide()` never reads raw text or attachments, only what perceive
already classified.

Everything here is deterministic and rule-based — no LLM call, no API
key required.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from perception import CONFIDENCE_ESCALATION_THRESHOLD, classify_reply, find_supplier_message

# The hard invariant: any perceived date or quantity difference between
# a confirmation and its original PO, above a small fixed tolerance,
# escalates automatically, full stop. The tolerance here is zero days /
# zero units on purpose — a worked example of this same rule showed it
# would have flagged two genuinely trivial one-day slips that didn't
# matter, along with the real six-day one that did, which only happens
# if the tolerance sits below one day. This is explicitly NOT a
# probability threshold; see decide() below, where it is checked first
# and unconditionally, independent of confidence.
QTY_TOLERANCE_UNITS = 0
DATE_TOLERANCE_DAYS = 0


class AgentState(TypedDict):
    po: dict[str, Any]
    supervised: bool
    trigger: Optional[dict[str, Any]]
    matched_message: Optional[dict[str, Any]]
    perception: Optional[dict[str, Any]]
    decision: Optional[dict[str, Any]]
    action_result: Optional[dict[str, Any]]
    escalation_result: Optional[dict[str, Any]]
    log: list[dict[str, Any]]


def make_initial_state(po: dict[str, Any], supervised: bool = True) -> AgentState:
    """
    `po` carries everything one PO-acknowledgment cycle needs: po_number,
    supplier, ordered_qty, ordered_date, hours_since_po, and an `inbox`
    list of every known message (across every thread) to search for a
    reply. `supervised=True` is the two-week supervised go-live stage;
    `supervised=False` is the earned-autonomy stage after the exit
    criterion is met.
    """
    return AgentState(
        po=po,
        supervised=supervised,
        trigger=None,
        matched_message=None,
        perception=None,
        decision=None,
        action_result=None,
        escalation_result=None,
        log=[],
    )


def _days_between(extracted: Optional[str], ordered: str) -> int:
    if extracted is None:
        return 0
    return abs((date.fromisoformat(extracted) - date.fromisoformat(ordered)).days)


# --- Trigger -------------------------------------------------------------


def trigger(state: AgentState) -> dict[str, Any]:
    """
    What starts the agent: a PO crossing 48 hours with no acknowledgment,
    or a supplier reply arriving. The reply search itself already carries
    guardrail #2 — `find_supplier_message` matches by reference number
    across the whole inbox, not just the thread this PO was originally
    filed under.
    """
    po = state["po"]
    message = find_supplier_message(po["po_number"], po["supplier"], po.get("inbox", []))

    if message is not None:
        reason = "supplier_reply_received"
        matched_via = (
            "same_thread"
            if message.get("thread_id") == po["po_number"]
            else "reference_number_match_across_threads"
        )
    elif po["hours_since_po"] >= 48:
        reason, matched_via = "48h_elapsed_no_acknowledgment", None
    else:
        reason, matched_via = "nothing_to_do_yet", None

    return {
        "trigger": {
            "po_number": po["po_number"],
            "supplier": po["supplier"],
            "reason": reason,
            "matched_via": matched_via,
            "hours_since_po": po["hours_since_po"],
        },
        "matched_message": message,
    }


def route_after_trigger(state: AgentState) -> Literal["perceive", "__end__"]:
    return END if state["trigger"]["reason"] == "nothing_to_do_yet" else "perceive"


# --- Perceive --------------------------------------------------------------


def perceive(state: AgentState) -> dict[str, Any]:
    """Classify the matched message (or its absence) with a confidence signal."""
    result = classify_reply(state["po"], state["matched_message"])
    return {"perception": result}


# --- Decide ----------------------------------------------------------------


def decide(state: AgentState) -> dict[str, Any]:
    """
    Match the perceived situation to one of four pre-approved actions —
    the bounded action space: log_only, send_chase, escalate_unclear,
    escalate_mismatch. Nothing else is a legal output of this function.

    The hard invariant is checked FIRST and INDEPENDENTLY of every other
    branch, including confidence. This is the central point: a hard
    invariant is not a probability, and cannot be out-voted by how
    confident perceive otherwise is.
    """
    po = state["po"]
    p = state["perception"]

    qty_diff = abs(p["extracted_qty"] - po["ordered_qty"]) if p.get("extracted_qty") is not None else 0
    date_diff = _days_between(p.get("extracted_date"), po["ordered_date"])

    if qty_diff > QTY_TOLERANCE_UNITS or date_diff > DATE_TOLERANCE_DAYS:
        decision = {
            "action": "escalate_mismatch",
            "requires_escalation": True,
            "hard_invariant_triggered": True,
            "risk": "high",
            "approved": None,
            "approved_by": None,
            "rationale": (
                f"HARD INVARIANT: confirmation on {po['po_number']} differs from the PO by "
                f"{qty_diff} unit(s) and {date_diff} day(s) — above the fixed tolerance "
                f"(qty>{QTY_TOLERANCE_UNITS}, date>{DATE_TOLERANCE_DAYS} day). Escalates "
                f"unconditionally regardless of perceive's confidence ({p['confidence']:.2f}). "
                f"This is a rule, not a threshold — it cannot be out-voted by confidence."
            ),
        }
    elif p["situation"] == "no_acknowledgment":
        decision = {
            "action": "send_chase",
            "requires_escalation": False,
            "hard_invariant_triggered": False,
            "risk": "low",
            "approved": None,
            "approved_by": None,
            "rationale": (
                f"48 hours elapsed with no acknowledgment on {po['po_number']} — "
                f"sending the standard chase template."
            ),
        }
    elif p["situation"] == "confirmed_as_ordered" and p["confidence"] >= CONFIDENCE_ESCALATION_THRESHOLD:
        decision = {
            "action": "log_only",
            "requires_escalation": False,
            "hard_invariant_triggered": False,
            "risk": "low",
            "approved": None,
            "approved_by": None,
            "rationale": (
                f"Confirmation on {po['po_number']} matches the PO exactly on quantity and "
                f"date (confidence {p['confidence']:.2f}) — log only, no action."
            ),
        }
    else:
        decision = {
            "action": "escalate_unclear",
            "requires_escalation": True,
            "hard_invariant_triggered": False,
            "risk": "medium",
            "approved": None,
            "approved_by": None,
            "rationale": (
                f"Perceive read '{p['situation']}' at confidence {p['confidence']:.2f} on "
                f"{po['po_number']} — below the bounded action space's confidence threshold "
                f"({CONFIDENCE_ESCALATION_THRESHOLD}), or nothing in the bounded action space "
                f"clearly applies. Escalating as unclear reply, needs review. ({p['notes']})"
            ),
        }
    return {"decision": decision}


def route_after_decide(state: AgentState) -> Literal["escalate", "human_approval", "act"]:
    decision = state["decision"]
    if decision["requires_escalation"]:
        return "escalate"
    return "human_approval" if state["supervised"] else "act"


# --- Human approval (staged autonomy) --------------------------------------


def human_approval(state: AgentState) -> dict[str, Any]:
    """
    The supervised-go-live approval queue. Only reached for log_only /
    send_chase while `supervised=True` — escalations never route through
    here, they go straight to `escalate`, which always interrupts
    regardless of stage.
    """
    decision = dict(state["decision"])
    po = state["po"]
    response = interrupt(
        {
            "kind": "action_approval",
            "po_number": po["po_number"],
            "supplier": po["supplier"],
            "proposed_action": decision["action"],
            "rationale": decision["rationale"],
        }
    )
    decision["approved"] = bool(response.get("approved", False))
    decision["approved_by"] = response.get("approved_by")
    return {"decision": decision}


# --- Act ---------------------------------------------------------------------


def act(state: AgentState) -> dict[str, Any]:
    """
    Execute the one chosen action. If `decision["approved"]` is still
    `None`, no approval gate ran (autonomous stage) — routine, low-risk
    actions fire on their own, exactly as the earned-autonomy stage
    describes.
    """
    decision = dict(state["decision"])
    po = state["po"]

    if decision["approved"] is None:
        decision["approved"] = True
        decision["approved_by"] = "autonomous_mode"

    if decision["approved"]:
        if decision["action"] == "log_only":
            outcome = f"logged confirmation on {po['po_number']} — no message sent"
        else:  # send_chase
            outcome = f"sent standard chase template to {po['supplier']} for {po['po_number']}"
        if decision["approved_by"] and decision["approved_by"] != "autonomous_mode":
            outcome += f" (approved by {decision['approved_by']})"
    else:
        outcome = f"held '{decision['action']}' on {po['po_number']} — not approved"

    return {"decision": decision, "action_result": {"outcome": outcome}}


# --- Escalate ----------------------------------------------------------------


def escalate(state: AgentState) -> dict[str, Any]:
    """
    Routes anything outside the bounded action space to a human with
    specific context — this PO, this reply, this is why — never a bare
    alert. This node ALWAYS interrupts, in both supervised and autonomous
    stages: escalations (and anything hitting the hard invariant) always
    go to a human, forever, by design.
    """
    decision = state["decision"]
    po = state["po"]
    p = state["perception"]
    payload = {
        "kind": "escalation",
        "po_number": po["po_number"],
        "supplier": po["supplier"],
        "action": decision["action"],
        "rationale": decision["rationale"],
        "perceived_situation": p["situation"],
        "confidence": p["confidence"],
        "extracted_qty": p.get("extracted_qty"),
        "extracted_date": p.get("extracted_date"),
        "ordered_qty": po["ordered_qty"],
        "ordered_date": po["ordered_date"],
        "hard_invariant_triggered": decision["hard_invariant_triggered"],
    }
    response = interrupt(payload)
    escalation_result = {
        "acknowledged_by": response.get("acknowledged_by"),
        "note": response.get("note"),
    }
    return {"escalation_result": escalation_result}


# --- Log ---------------------------------------------------------------------


def log(state: AgentState) -> dict[str, Any]:
    """
    Every trigger, perception, decision, action, and escalation —
    recorded, in order, attributable. The last of the six boxes, and
    never optional.
    """
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "po_number": state["po"]["po_number"],
        "supplier": state["po"]["supplier"],
        "trigger": state["trigger"],
        "perception": state["perception"],
        "decision": state["decision"],
        "action_result": state.get("action_result"),
        "escalation_result": state.get("escalation_result"),
    }
    return {"log": state["log"] + [entry]}


# --- Graph assembly ----------------------------------------------------------


def build_graph():
    """Wire the six-box anatomy together as a LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    # Step 1: register the nodes — the six boxes of the anatomy, plus the
    # human_approval node that sits on the staged-autonomy approval queue.
    graph.add_node("trigger", trigger)
    graph.add_node("perceive", perceive)
    graph.add_node("decide", decide)
    graph.add_node("human_approval", human_approval)
    graph.add_node("act", act)
    graph.add_node("escalate", escalate)
    graph.add_node("log", log)

    # Step 2: wire the entry point and the two routing decisions — whether
    # there's actually something to trigger on, and which of the three
    # outcomes decide() produced (escalate / needs approval / act directly).
    graph.add_edge(START, "trigger")
    graph.add_conditional_edges("trigger", route_after_trigger, {"perceive": "perceive", END: END})
    graph.add_edge("perceive", "decide")
    graph.add_conditional_edges(
        "decide",
        route_after_decide,
        {"escalate": "escalate", "human_approval": "human_approval", "act": "act"},
    )

    # Step 3: wire the remaining fixed edges — every path, approved or
    # escalated, converges on log, and log ends the run.
    graph.add_edge("human_approval", "act")
    graph.add_edge("act", "log")
    graph.add_edge("escalate", "log")
    graph.add_edge("log", END)
    return graph
