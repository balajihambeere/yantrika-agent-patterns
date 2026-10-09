"""
The policy gate every agent decision crosses, built as an actual
LangGraph `StateGraph`.

The core idea: nothing — no agent, no integration, no new capability —
crosses this gate without declaring what it depends on, clearing the
policy checkpoint for its tier, and writing its decision into the one
ledger everyone can audit. This module is the policy-checkpoint-plus-
ledger-write half of that idea (the data-contract layer is a separate
concern and isn't modeled here).

One graph, three request types, routed at the top:

    OPERATIONAL  — an agent proposes an action.
        check_boundary --(within boundary)--> auto_act --> log_operational
                       --(outside boundary)--> escalate_operational (interrupt!)
                                             --> log_operational
        The bounded-autonomy idea, enforced: within-boundary actions act
        and log themselves; out-of-boundary actions pause on a real
        `interrupt()` for a named human before anything happens.

    GOVERNANCE  — a tier-change / boundary-widening proposal.
        validate_proposal --(any of the 4 conditions missing)--> reject_proposal (no interrupt, ever)
                          --(all 4 present)--> approver_signoff (interrupt!)
                                              --(approved)--> apply_tier_change --> log_governance_approved
                                              --(declined)--> log_governance_declined

        `policy_engine.validate_tier_change_proposal()` is plain
        deterministic code — a proposal missing any of the four
        required conditions is rejected before a single human,
        including the named approver, ever sees it. Only a fully valid
        proposal reaches `interrupt()`, and only a named approver who is
        NOT the proposer can resolve it (enforced structurally inside
        `validate_proposal`, not left to convention).

    REVERSAL_CHECK — can be run after any operational decision.
        evaluate_reversal --(trigger fires)--> rollback_tier --> log_governance_rollback
                          --(trigger doesn't fire)--> no_rollback
        No `interrupt()` anywhere in this branch — the whole point about
        reversal triggers is that they were decided in advance, so
        firing one is arithmetic, not a fresh human call made under the
        pressure of an actual incident.

Every operational and governance decision — auto-acted, escalated,
approved, rejected, or auto-rolled-back — writes exactly one five-part
record to the shared `DecisionLedger` before the graph run finishes.
`check_boundary` / `validate_proposal` / `evaluate_reversal` stay plain,
deterministic rule checks — no LLM anywhere in this module.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from decision_ledger import DecisionLedger
from policy_engine import (
    PolicyRegistry,
    TierChangeProposal,
    deserialize_proposal,
    evaluate_reversal_trigger,
    proposal_to_dict,
    serialize_proposal,
    validate_tier_change_proposal,
)


class GraphState(TypedDict):
    request_type: Literal["operational", "governance", "reversal_check"]

    # -- operational --
    agent_id: Optional[str]
    action: Optional[dict[str, Any]]
    boundary_check: Optional[dict[str, Any]]
    operational_decision: Optional[dict[str, Any]]

    # -- governance --
    # `proposal` and `today` are kept as plain, msgpack/JSON-friendly
    # dicts/strings in graph state (see policy_engine.serialize_proposal),
    # never as raw dataclass/enum/date objects, so the checkpointer never
    # has to serialize a custom Python type. Nodes call
    # `policy_engine.deserialize_proposal` / `date.fromisoformat` to get
    # the real objects back before operating on them.
    proposal: Optional[dict[str, Any]]
    today: Optional[str]  # ISO date string - the story's "today," passed in explicitly
    validation: Optional[dict[str, Any]]
    approval: Optional[dict[str, Any]]
    applied_state: Optional[dict[str, Any]]

    # -- reversal check --
    recent_decisions: Optional[list[dict[str, Any]]]
    reversal_result: Optional[dict[str, Any]]

    # -- shared --
    decision_id: Optional[str]


def make_initial_operational_state(agent_id: str, action: dict[str, Any]) -> GraphState:
    return GraphState(
        request_type="operational",
        agent_id=agent_id,
        action=action,
        boundary_check=None,
        operational_decision=None,
        proposal=None,
        today=None,
        validation=None,
        approval=None,
        applied_state=None,
        recent_decisions=None,
        reversal_result=None,
        decision_id=None,
    )


def make_initial_governance_state(proposal: TierChangeProposal, today) -> GraphState:
    return GraphState(
        request_type="governance",
        agent_id=None,
        action=None,
        boundary_check=None,
        operational_decision=None,
        proposal=serialize_proposal(proposal),
        today=today.isoformat(),
        validation=None,
        approval=None,
        applied_state=None,
        recent_decisions=None,
        reversal_result=None,
        decision_id=None,
    )


def make_initial_reversal_state(agent_id: str, recent_decisions: list[dict[str, Any]]) -> GraphState:
    return GraphState(
        request_type="reversal_check",
        agent_id=agent_id,
        action=None,
        boundary_check=None,
        operational_decision=None,
        proposal=None,
        today=None,
        validation=None,
        approval=None,
        applied_state=None,
        recent_decisions=recent_decisions,
        reversal_result=None,
        decision_id=None,
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_graph(registry: PolicyRegistry, ledger: DecisionLedger):
    """
    Builds the policy gate's StateGraph against a specific
    `PolicyRegistry` and `DecisionLedger`. Both are real, shared,
    stateful objects (the thing a live deployment of this gate would
    call out to), not graph state, so they survive across however many
    requests are streamed through the compiled graph using the same
    `thread_id` or different ones.
    """

    # ---------------------------------------------------------------
    # entry routing
    # ---------------------------------------------------------------
    def route_entry(state: GraphState) -> Literal["check_boundary", "validate_proposal", "evaluate_reversal"]:
        return {
            "operational": "check_boundary",
            "governance": "validate_proposal",
            "reversal_check": "evaluate_reversal",
        }[state["request_type"]]

    # ---------------------------------------------------------------
    # OPERATIONAL flow
    # ---------------------------------------------------------------
    def check_boundary(state: GraphState) -> dict[str, Any]:
        agent = registry.get(state["agent_id"])
        within, reason = agent.boundary.covers(state["action"]["inputs"])
        return {
            "boundary_check": {
                "within_boundary": within,
                "reason": reason,
                "tier": int(agent.tier),
                "policy_version": agent.policy_version,
                "boundary_description": agent.boundary.describe(),
            }
        }

    def route_after_boundary(state: GraphState) -> Literal["auto_act", "escalate_operational"]:
        return "auto_act" if state["boundary_check"]["within_boundary"] else "escalate_operational"

    def auto_act(state: GraphState) -> dict[str, Any]:
        return {
            "operational_decision": {
                "acted": True,
                "acted_by": "system (autonomous)",
                "approved_by": None,
                "escalated": False,
                "notes": state["boundary_check"]["reason"],
            }
        }

    def escalate_operational(state: GraphState) -> dict[str, Any]:
        """The branch where a human intervenes before anything happens.
        `interrupt()` genuinely pauses the graph here."""
        agent = registry.get(state["agent_id"])
        response = interrupt(
            {
                "agent_id": state["agent_id"],
                "action": state["action"],
                "boundary_check": state["boundary_check"],
                "escalation_contact": agent.escalation_contact,
            }
        )
        acted = bool(response.get("approved", False))
        return {
            "operational_decision": {
                "acted": acted,
                "acted_by": response.get("approved_by") if acted else None,
                "approved_by": response.get("approved_by"),
                "escalated": True,
                "notes": response.get("notes", ""),
            }
        }

    def log_operational(state: GraphState) -> dict[str, Any]:
        agent = registry.get(state["agent_id"])
        action = state["action"]
        decision = state["operational_decision"]

        human_actions = []
        if decision["escalated"]:
            human_actions.append(
                {
                    "who": decision["approved_by"] or "unknown",
                    "when": _now(),
                    "action": "approved_escalated_action" if decision["acted"] else "declined_escalated_action",
                    "notes": decision.get("notes", ""),
                }
            )

        outcome = {
            "result": "acted" if decision["acted"] else "not_acted",
            "acted_by": decision["acted_by"],
            "escalated": decision["escalated"],
        }

        decision_id = ledger.log_decision(
            agent_id=agent.agent_id,
            tier=int(agent.tier),
            record_type="operational",
            inputs=action["inputs"],
            policy_version=agent.policy_version,
            model_version=action.get("model_version", "n/a"),
            reasoning_path=action.get("reasoning_path", []),
            human_actions=human_actions,
            outcome=outcome,
        )
        return {"decision_id": decision_id}

    # ---------------------------------------------------------------
    # GOVERNANCE flow
    # ---------------------------------------------------------------
    def validate_proposal(state: GraphState) -> dict[str, Any]:
        proposal = deserialize_proposal(state["proposal"])
        result = validate_tier_change_proposal(proposal, today=date.fromisoformat(state["today"]))
        return {
            "validation": {
                "approved": result.approved,
                "failed_conditions": result.failed_conditions,
                "checked_conditions": result.checked_conditions,
            }
        }

    def route_after_validate(state: GraphState) -> Literal["reject_proposal", "approver_signoff"]:
        return "approver_signoff" if state["validation"]["approved"] else "reject_proposal"

    def reject_proposal(state: GraphState) -> dict[str, Any]:
        """Deterministic rejection - the policy engine itself blocks this,
        no interrupt ever fires, no human (not even the named approver)
        is ever consulted."""
        proposal = deserialize_proposal(state["proposal"])
        current = registry.get(proposal.agent_id)
        reasoning_path = [
            {
                "factor": f"condition_{i + 1}",
                "weight": round(1.0 / max(len(state["validation"]["checked_conditions"]), 1), 2),
                "value": "failed",
                "note": reason,
            }
            for i, reason in enumerate(state["validation"]["failed_conditions"])
        ]
        decision_id = ledger.log_decision(
            agent_id=proposal.agent_id,
            tier=int(proposal.from_tier),
            record_type="governance",
            inputs={"proposal": proposal_to_dict(proposal)},
            policy_version=current.policy_version,
            model_version="n/a",
            reasoning_path=reasoning_path,
            human_actions=[],
            outcome={
                "result": "rejected_by_policy_engine",
                "reason": "; ".join(state["validation"]["failed_conditions"]),
            },
        )
        return {"decision_id": decision_id}

    def approver_signoff(state: GraphState) -> dict[str, Any]:
        """Only reached once all four conditions are satisfied. Routes to
        the NAMED approver - never the proposer, enforced structurally by
        `validate_tier_change_proposal`'s condition 2, not by convention."""
        proposal = deserialize_proposal(state["proposal"])
        response = interrupt(
            {
                "proposal": proposal_to_dict(proposal),
                "validation": state["validation"],
                "approver": proposal.approver,
                "proposer": proposal.proposer,
            }
        )
        return {
            "approval": {
                "approved": bool(response.get("approved", False)),
                "approved_by": response.get("approved_by"),
                "notes": response.get("notes", ""),
            }
        }

    def route_after_signoff(state: GraphState) -> Literal["apply_tier_change", "log_governance_declined"]:
        return "apply_tier_change" if state["approval"]["approved"] else "log_governance_declined"

    def apply_tier_change(state: GraphState) -> dict[str, Any]:
        proposal = deserialize_proposal(state["proposal"])
        new_state = registry.apply_tier_change(proposal, approved_by=state["approval"]["approved_by"])
        return {
            "applied_state": {
                "new_tier": int(new_state.tier),
                "new_policy_version": new_state.policy_version,
                "new_boundary": new_state.boundary.describe(),
            }
        }

    def log_governance_approved(state: GraphState) -> dict[str, Any]:
        proposal = deserialize_proposal(state["proposal"])
        applied = state["applied_state"]
        reasoning_path = [
            {"factor": "minimum_track_record", "weight": 0.25, "value": proposal.track_record_count,
             "note": f"{proposal.track_record_count} {proposal.track_record_label} >= required minimum {proposal.track_record_minimum}"},
            {"factor": "named_proposer_and_approver", "weight": 0.25, "value": f"{proposal.proposer} -> {proposal.approver}",
             "note": "proposer and approver are two different named people"},
            {"factor": "explicit_reversal_trigger", "weight": 0.25, "value": proposal.reversal_trigger.name,
             "note": proposal.reversal_trigger.describe()},
            {"factor": "scheduled_re_review_date", "weight": 0.25, "value": proposal.re_review_date.isoformat(),
             "note": f"re-review scheduled, relative to story-today {state['today']}"},
        ]
        decision_id = ledger.log_decision(
            agent_id=proposal.agent_id,
            tier=applied["new_tier"],
            record_type="governance",
            inputs={"proposal": proposal_to_dict(proposal)},
            policy_version=applied["new_policy_version"],
            model_version="n/a",
            reasoning_path=reasoning_path,
            human_actions=[
                {"who": state["approval"]["approved_by"], "when": _now(), "action": "approved_tier_change",
                 "notes": state["approval"].get("notes", "")}
            ],
            outcome={
                "result": "approved",
                "new_tier": applied["new_tier"],
                "new_policy_version": applied["new_policy_version"],
                "new_boundary": applied["new_boundary"],
            },
        )
        return {"decision_id": decision_id}

    def log_governance_declined(state: GraphState) -> dict[str, Any]:
        proposal = deserialize_proposal(state["proposal"])
        current = registry.get(proposal.agent_id)
        decision_id = ledger.log_decision(
            agent_id=proposal.agent_id,
            tier=int(current.tier),
            record_type="governance",
            inputs={"proposal": proposal_to_dict(proposal)},
            policy_version=current.policy_version,
            model_version="n/a",
            reasoning_path=[
                {"factor": "approver_signoff", "weight": 1.0, "value": "declined",
                 "note": f"all 4 conditions were satisfied, but approver {proposal.approver} declined to sign off"}
            ],
            human_actions=[
                {"who": state["approval"]["approved_by"], "when": _now(), "action": "declined_tier_change",
                 "notes": state["approval"].get("notes", "")}
            ],
            outcome={"result": "declined_by_approver"},
        )
        return {"decision_id": decision_id}

    # ---------------------------------------------------------------
    # REVERSAL-CHECK flow
    # ---------------------------------------------------------------
    def evaluate_reversal(state: GraphState) -> dict[str, Any]:
        agent = registry.get(state["agent_id"])
        result = evaluate_reversal_trigger(agent.reversal_trigger, state["recent_decisions"] or [])
        return {"reversal_result": result}

    def route_after_reversal(state: GraphState) -> Literal["rollback_tier", "no_rollback"]:
        return "rollback_tier" if state["reversal_result"]["fired"] else "no_rollback"

    def rollback_tier(state: GraphState) -> dict[str, Any]:
        agent_before = registry.get(state["agent_id"])
        trigger = agent_before.reversal_trigger
        new_state = registry.rollback(state["agent_id"])
        decision_id = ledger.log_decision(
            agent_id=new_state.agent_id,
            tier=int(new_state.tier),
            record_type="governance",
            inputs={"recent_decisions_checked": state["recent_decisions"]},
            policy_version=new_state.policy_version,
            model_version="n/a",
            reasoning_path=[
                {
                    "factor": trigger.name if trigger else "reversal_trigger",
                    "weight": 1.0,
                    "value": state["reversal_result"]["observed_value"],
                    "note": state["reversal_result"]["explanation"],
                }
            ],
            human_actions=[],  # automatic - no human sign-off required, by design
            outcome={
                "result": "automatic_rollback",
                "rolled_back_to_tier": int(new_state.tier),
                "rolled_back_to_policy_version": new_state.policy_version,
            },
        )
        return {"decision_id": decision_id}

    def no_rollback(state: GraphState) -> dict[str, Any]:
        return {}

    # ---------------------------------------------------------------
    # wiring
    # ---------------------------------------------------------------
    graph = StateGraph(GraphState)

    # Step 1: register the nodes for all three flows this gate handles —
    # operational (an agent's own decision), governance (a tier-change
    # proposal), and reversal_check (evaluating a rollback trigger).
    graph.add_node("check_boundary", check_boundary)
    graph.add_node("auto_act", auto_act)
    graph.add_node("escalate_operational", escalate_operational)
    graph.add_node("log_operational", log_operational)

    graph.add_node("validate_proposal", validate_proposal)
    graph.add_node("reject_proposal", reject_proposal)
    graph.add_node("approver_signoff", approver_signoff)
    graph.add_node("apply_tier_change", apply_tier_change)
    graph.add_node("log_governance_approved", log_governance_approved)
    graph.add_node("log_governance_declined", log_governance_declined)

    graph.add_node("evaluate_reversal", evaluate_reversal)
    graph.add_node("rollback_tier", rollback_tier)
    graph.add_node("no_rollback", no_rollback)

    # Step 2: wire the entry point — route_entry dispatches each incoming
    # request to the start of whichever of the three flows it belongs to.
    graph.add_conditional_edges(
        START,
        route_entry,
        {"check_boundary": "check_boundary", "validate_proposal": "validate_proposal", "evaluate_reversal": "evaluate_reversal"},
    )

    # Step 3: wire each flow's own internal routing and terminal edges.
    # Operational: within-boundary auto-acts, out-of-boundary escalates —
    # both converge on the same log node.
    graph.add_conditional_edges(
        "check_boundary", route_after_boundary, {"auto_act": "auto_act", "escalate_operational": "escalate_operational"}
    )
    graph.add_edge("auto_act", "log_operational")
    graph.add_edge("escalate_operational", "log_operational")
    graph.add_edge("log_operational", END)

    # Governance: a proposal missing a required condition is rejected
    # outright with no human involved; a valid one goes to the named
    # approver, who can still decline it.
    graph.add_conditional_edges(
        "validate_proposal", route_after_validate, {"reject_proposal": "reject_proposal", "approver_signoff": "approver_signoff"}
    )
    graph.add_edge("reject_proposal", END)
    graph.add_conditional_edges(
        "approver_signoff", route_after_signoff, {"apply_tier_change": "apply_tier_change", "log_governance_declined": "log_governance_declined"}
    )
    graph.add_edge("apply_tier_change", "log_governance_approved")
    graph.add_edge("log_governance_approved", END)
    graph.add_edge("log_governance_declined", END)

    # Reversal check: no human in this path at all — the trigger either
    # fires and rolls the tier back, or it doesn't.
    graph.add_conditional_edges(
        "evaluate_reversal", route_after_reversal, {"rollback_tier": "rollback_tier", "no_rollback": "no_rollback"}
    )
    graph.add_edge("rollback_tier", END)
    graph.add_edge("no_rollback", END)

    return graph
