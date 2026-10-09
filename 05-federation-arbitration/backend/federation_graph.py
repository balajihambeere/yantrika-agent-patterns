"""
The cross-plant arbitration layer for a two-plant rollout, built as an
actual LangGraph `StateGraph`.

A near-miss scenario, precisely: under a limited pilot connection
(observe-only), Pune's agent correctly sees its own surplus of a fastener
family could cover Nashik's shortfall. In the same cycle, Nashik's agent —
watching the same shared supplier's confirmed shipment schedule — just as
correctly sees it could solve its own shortfall with a rush order against
that supplier's open capacity. Both recommendations are individually
right. Acted on simultaneously, with neither side knowing about the
other, they would jointly over-commit: Nashik over-receiving, Pune losing
surplus it might want back, and an unnecessary rush order. Vikram names it
directly as the same mechanism as the stale-report problem, one level
up — multiple locally-accurate actors, no shared visibility, a jointly
wrong outcome.

The fix here is not more intelligence. It is an explicit
observe / recommend / act tier model for cross-boundary
autonomy (see the three `TIER_*` constants below), plus an arbitration
rule: a plant-level agent may observe another plant's data and surface a
cross-boundary recommendation, but no agent may commit another plant's
resources without a *named* human on *both* sides confirming the
transfer — Neha Joshi (Pune's procurement lead) and Shalini Rao (Nashik's
procurement lead), specifically, exactly as they were already doing
informally by picking up the phone.

This module is that layer, expressed as a LangGraph StateGraph:

    START --> sense_pune   --\\
    START --> sense_nashik --+--> arbitrate
    arbitrate --(no collision)--------------------------> act_independent
    arbitrate --(collision, tier == "act")---------------> act_unilateral
    arbitrate --(collision, tier <= "recommend")---------> confirm_neha
    confirm_neha --(declined)-----------------------------> fallback_independent
    confirm_neha --(confirmed)----------------------------> confirm_shalini
    confirm_shalini --(declined)--------------------------> fallback_independent
    confirm_shalini --(confirmed)--------------------------> coordinated_act
    {act_independent, act_unilateral, coordinated_act, fallback_independent} --> log --> END

`confirm_neha` and `confirm_shalini` each use LangGraph's `interrupt()` —
two genuinely separate pauses, one per named human, one per side of the
boundary. The graph does not proceed to `coordinated_act` until *both*
have resumed with a confirmation; declining either one — at either step —
routes to `fallback_independent`: each site handling its own shortfall on
its own, the pre-fix behavior, but now visible and logged instead of
silently colliding.

`sense_pune` / `sense_nashik` / the collision test all stay plain,
deterministic logic (`site_agents.py` and `detect_collision()` below) —
no LLM, no API key.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from site_agents import (
    LocalRecommendation,
    SitePosition,
    SupplierCapacity,
    evaluate_nashik_position,
    evaluate_pune_position,
)

# The three escalating tiers of cross-boundary autonomy: observe
# (low-risk, default-safe) < recommend (surfaced to humans on both sides,
# no auto-action) < act (unilateral, no human confirmation). Each must be
# granted deliberately and separately.
TIER_OBSERVE = "observe"
TIER_RECOMMEND = "recommend"
TIER_ACT = "act"
_TIER_RANK = {TIER_OBSERVE: 0, TIER_RECOMMEND: 1, TIER_ACT: 2}

# Most organizations should not grant the
# "act" tier to a federation of agents before the simpler tiers have
# earned trust over time, if ever. This federation's default reflects
# that caution: recommend, not act. See test_federation_graph.py's
# `test_default_connection_tier_is_recommend_not_act`.
DEFAULT_CONNECTION_TIER = TIER_RECOMMEND

PUNE_CONFIRMER = "Neha Joshi"
NASHIK_CONFIRMER = "Shalini Rao"


class CollisionReport(TypedDict):
    sku_family: str
    description: str
    pune_recommendation: LocalRecommendation
    nashik_recommendation: LocalRecommendation


class FederationState(TypedDict):
    pune_position: SitePosition
    nashik_position: SitePosition
    supplier: SupplierCapacity
    connection_tier: str
    observe_nashik_from_pune: bool
    pune_recommendation: Optional[LocalRecommendation]
    nashik_recommendation: Optional[LocalRecommendation]
    collision: Optional[CollisionReport]
    neha_confirmation: Optional[dict[str, Any]]
    shalini_confirmation: Optional[dict[str, Any]]
    decision: Optional[dict[str, Any]]
    log: list[dict[str, Any]]


def make_initial_state(
    pune_position: SitePosition,
    nashik_position: SitePosition,
    supplier: SupplierCapacity,
    connection_tier: str = DEFAULT_CONNECTION_TIER,
    observe_nashik_from_pune: bool = True,
) -> FederationState:
    return FederationState(
        pune_position=pune_position,
        nashik_position=nashik_position,
        supplier=supplier,
        connection_tier=connection_tier,
        observe_nashik_from_pune=observe_nashik_from_pune,
        pune_recommendation=None,
        nashik_recommendation=None,
        collision=None,
        neha_confirmation=None,
        shalini_confirmation=None,
        decision=None,
        log=[],
    )


def sense_pune(state: FederationState) -> dict[str, Any]:
    """Pune's allocation agent, run in parallel with sense_nashik."""
    rec = evaluate_pune_position(
        state["pune_position"], state["nashik_position"], state["observe_nashik_from_pune"]
    )
    return {"pune_recommendation": rec}


def sense_nashik(state: FederationState) -> dict[str, Any]:
    """Nashik's allocation agent, run in parallel with sense_pune."""
    rec = evaluate_nashik_position(state["nashik_position"], state["supplier"])
    return {"nashik_recommendation": rec}


def detect_collision(
    pune_rec: LocalRecommendation, nashik_rec: LocalRecommendation
) -> Optional[CollisionReport]:
    """
    The exact near-miss, generalized: Pune offering a transfer
    to cover the same fastener family that Nashik, independently, is
    about to rush-order against the same supplier. Both are individually
    correct; together they would over-commit — Nashik receiving the
    transfer *and* the rush order, Pune losing surplus it might want
    back, a rush order that didn't need to be rushed.
    """
    if (
        pune_rec["action"] == "offer_cross_boundary_transfer"
        and nashik_rec["action"] == "rush_order"
        and pune_rec["sku_family"] == nashik_rec["sku_family"]
    ):
        return CollisionReport(
            sku_family=pune_rec["sku_family"],
            description=(
                f"Pune recommends offering {pune_rec['quantity']} units of {pune_rec['sku_family']} "
                f"surplus to Nashik, while Nashik independently recommends a rush order for "
                f"{nashik_rec['quantity']} units of the same family against the shared supplier. "
                f"Acted on simultaneously, Nashik would over-receive, Pune would lose surplus it "
                f"might want back, and the rush order would have been unnecessary."
            ),
            pune_recommendation=pune_rec,
            nashik_recommendation=nashik_rec,
        )
    return None


def arbitrate(state: FederationState) -> dict[str, Any]:
    """The convergence point for sense_pune and sense_nashik. Checks only
    whether the two independent recommendations collide — it does not
    decide anything on its own; routing below decides what happens next."""
    collision = detect_collision(state["pune_recommendation"], state["nashik_recommendation"])
    return {"collision": collision}


def route_after_arbitrate(
    state: FederationState,
) -> Literal["act_independent", "act_unilateral", "confirm_neha"]:
    if state["collision"] is None:
        return "act_independent"
    if _TIER_RANK[state["connection_tier"]] >= _TIER_RANK[TIER_ACT]:
        return "act_unilateral"
    return "confirm_neha"


def confirm_neha(state: FederationState) -> dict[str, Any]:
    """
    Pune's side of the dual confirmation. `interrupt()` genuinely pauses
    the graph here — nothing is committed until the caller resumes with
    `Command(resume=...)`. This is Neha's call specifically, because the
    resource being committed (Pune's surplus) is hers to release.
    """
    collision = state["collision"]
    response = interrupt(
        {
            "confirmer": PUNE_CONFIRMER,
            "role": "Pune procurement lead",
            "collision": collision["description"],
            "proposed_action": (
                f"Release {collision['pune_recommendation']['quantity']} units of "
                f"{collision['sku_family']} surplus from Pune to Nashik, instead of letting "
                f"Nashik's independent rush order proceed."
            ),
        }
    )
    confirmation = {
        "confirmed": bool(response.get("confirmed", False)),
        "confirmed_by": response.get("confirmed_by", PUNE_CONFIRMER),
        "note": response.get("note", ""),
    }
    return {"neha_confirmation": confirmation}


def route_after_neha(state: FederationState) -> Literal["confirm_shalini", "fallback_independent"]:
    return "confirm_shalini" if state["neha_confirmation"]["confirmed"] else "fallback_independent"


def confirm_shalini(state: FederationState) -> dict[str, Any]:
    """
    Nashik's side of the dual confirmation — a second, genuinely separate
    `interrupt()`. The graph does not reach `coordinated_act` on Neha's
    confirmation alone; both named humans, on both sides, have to sign off
    before a cross-boundary commitment proceeds.
    """
    collision = state["collision"]
    response = interrupt(
        {
            "confirmer": NASHIK_CONFIRMER,
            "role": "Nashik procurement lead",
            "collision": collision["description"],
            "proposed_action": (
                f"Accept the {collision['pune_recommendation']['quantity']}-unit transfer from "
                f"Pune and cancel the independent rush order for "
                f"{collision['nashik_recommendation']['quantity']} units against "
                f"{state['supplier']['supplier']}."
            ),
        }
    )
    confirmation = {
        "confirmed": bool(response.get("confirmed", False)),
        "confirmed_by": response.get("confirmed_by", NASHIK_CONFIRMER),
        "note": response.get("note", ""),
    }
    return {"shalini_confirmation": confirmation}


def route_after_shalini(state: FederationState) -> Literal["coordinated_act", "fallback_independent"]:
    return "coordinated_act" if state["shalini_confirmation"]["confirmed"] else "fallback_independent"


def act_independent(state: FederationState) -> dict[str, Any]:
    """No collision: each site's own recommendation executes as-is, within
    its own tier, no human needed — the normal, uneventful case."""
    decision = {
        "type": "independent_action",
        "coordinated": False,
        "pune_action": state["pune_recommendation"],
        "nashik_action": state["nashik_recommendation"],
        "note": (
            "No cross-boundary collision detected — each site acted within its own authority, "
            "no human confirmation required."
        ),
    }
    return {"decision": decision}


def act_unilateral(state: FederationState) -> dict[str, Any]:
    """
    Only reachable if the connection were configured at the 'act' tier —
    an agent committing another site's resources with no human
    confirmation at all. This federation's default (`DEFAULT_CONNECTION_
    TIER`) is deliberately `recommend`, never this; this path exists so
    the risk of granting unilateral autonomy is modeled, not hand-waved
    away.
    """
    collision = state["collision"]
    quantity = collision["pune_recommendation"]["quantity"]
    decision = {
        "type": "unilateral_cross_boundary_act",
        "coordinated": False,
        "quantity": quantity,
        "sku_family": collision["sku_family"],
        "note": (
            "Connection tier is 'act' — the federation committed Pune's surplus to Nashik's "
            "shortfall unilaterally, with no named human confirming on either side. This is "
            "exactly the blast radius most organizations should not grant to a federation of "
            "agents before the simpler tiers have earned trust."
        ),
    }
    return {"decision": decision}


def coordinated_act(state: FederationState) -> dict[str, Any]:
    """Both Neha and Shalini confirmed: the collision resolves into one
    coordinated transfer, and Nashik's now-redundant rush order is
    cancelled instead of both actions executing side by side."""
    collision = state["collision"]
    quantity = collision["pune_recommendation"]["quantity"]
    decision = {
        "type": "coordinated_transfer",
        "coordinated": True,
        "quantity": quantity,
        "sku_family": collision["sku_family"],
        "from_site": state["pune_position"]["site"],
        "to_site": state["nashik_position"]["site"],
        "rush_order_cancelled": True,
        "confirmed_by": [
            state["neha_confirmation"]["confirmed_by"],
            state["shalini_confirmation"]["confirmed_by"],
        ],
        "note": (
            f"Both {state['neha_confirmation']['confirmed_by']} and "
            f"{state['shalini_confirmation']['confirmed_by']} confirmed — {quantity} units "
            f"transferred {state['pune_position']['site']} -> {state['nashik_position']['site']}, "
            f"Nashik's independent rush order against {state['supplier']['supplier']} cancelled."
        ),
    }
    return {"decision": decision}


def fallback_independent(state: FederationState) -> dict[str, Any]:
    """Either human declined: fall back to each site handling its own
    shortfall independently — the pre-fix behavior, but now visible and
    logged instead of silently colliding."""
    declined_by = []
    neha = state.get("neha_confirmation")
    shalini = state.get("shalini_confirmation")
    if neha and not neha["confirmed"]:
        declined_by.append(neha["confirmed_by"])
    if shalini and not shalini["confirmed"]:
        declined_by.append(shalini["confirmed_by"])

    decision = {
        "type": "fallback_independent",
        "coordinated": False,
        "declined_by": declined_by,
        "pune_action": state["pune_recommendation"],
        "nashik_action": state["nashik_recommendation"],
        "note": (
            f"{' and '.join(declined_by)} declined the cross-boundary transfer — falling back to "
            f"each site handling its own shortfall independently. Visible and logged this time, "
            f"instead of the two recommendations silently colliding."
        ),
    }
    return {"decision": decision}


def log(state: FederationState) -> dict[str, Any]:
    """
    Captures the full cross-plant picture, per the arbitration
    rule: both original local recommendations, the detected collision (or
    its absence), both human confirmations (or the decline), and the
    final coordinated action — not just the outcome.
    """
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connection_tier": state["connection_tier"],
        "pune_position": state["pune_position"],
        "nashik_position": state["nashik_position"],
        "pune_recommendation": state["pune_recommendation"],
        "nashik_recommendation": state["nashik_recommendation"],
        "collision": state["collision"],
        "neha_confirmation": state.get("neha_confirmation"),
        "shalini_confirmation": state.get("shalini_confirmation"),
        "decision": state["decision"],
    }
    return {"log": state["log"] + [entry]}


def build_graph():
    """Wire the layer together: fan out to sense_pune / sense_nashik,
    converge on arbitrate, branch on collision + tier, and converge every
    terminal branch on log."""
    graph = StateGraph(FederationState)

    # Step 1: register the nodes — both sites' local sensing, the shared
    # arbitrate node, the two named-human confirmations, the three possible
    # act outcomes, the independent fallback, and the shared log.
    graph.add_node("sense_pune", sense_pune)
    graph.add_node("sense_nashik", sense_nashik)
    graph.add_node("arbitrate", arbitrate)
    graph.add_node("confirm_neha", confirm_neha)
    graph.add_node("confirm_shalini", confirm_shalini)
    graph.add_node("act_independent", act_independent)
    graph.add_node("act_unilateral", act_unilateral)
    graph.add_node("coordinated_act", coordinated_act)
    graph.add_node("fallback_independent", fallback_independent)
    graph.add_node("log", log)

    # Step 2: wire the entry point and the routing decisions — fan out to
    # both sites' sensing in parallel, converge on arbitrate, then route
    # on whether there's a collision and, if so, walk through Neha's and
    # Shalini's confirmations one at a time before any coordinated action.
    graph.add_edge(START, "sense_pune")
    graph.add_edge(START, "sense_nashik")
    graph.add_edge("sense_pune", "arbitrate")
    graph.add_edge("sense_nashik", "arbitrate")

    graph.add_conditional_edges(
        "arbitrate",
        route_after_arbitrate,
        {
            "act_independent": "act_independent",
            "act_unilateral": "act_unilateral",
            "confirm_neha": "confirm_neha",
        },
    )
    graph.add_conditional_edges(
        "confirm_neha",
        route_after_neha,
        {"confirm_shalini": "confirm_shalini", "fallback_independent": "fallback_independent"},
    )
    graph.add_conditional_edges(
        "confirm_shalini",
        route_after_shalini,
        {"coordinated_act": "coordinated_act", "fallback_independent": "fallback_independent"},
    )

    # Step 3: wire the remaining fixed edges — every terminal action,
    # whichever branch produced it, converges on log, and log ends the run.
    for terminal in ("act_independent", "act_unilateral", "coordinated_act", "fallback_independent"):
        graph.add_edge(terminal, "log")
    graph.add_edge("log", END)
    return graph
