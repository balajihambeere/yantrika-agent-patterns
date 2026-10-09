"""
The arbitration layer Kavita Iyer's team built after Pune and Plant Two
both placed a hold against the same Nashik supplier-lot within four minutes
of each other, expressed as an actual LangGraph `StateGraph`.

Each plant's allocation agent submits ONE claim per graph run (`submit_claim`
-> `check_registry`). If nothing else is holding the same supplier-lot, the
claim is granted immediately (`grant` -> `log`) — no arbitration, no human,
no delay. If the registry finds a collision, the claim is routed through
the pre-approved, deterministic precedence rulebook (`arbitrate`, using
`precedence_policy.resolve_precedence` — no `interrupt()` in this branch,
reflecting the design's explicit rejection of case-by-case human
refereeing):

    START -> submit_claim -> check_registry
                                 |-- clear ------> grant -----------------> log -> END
                                 `-- collision --> arbitrate
                                                      |-- resolved -------> grant_winner -> suggest_alternate_for_loser -> log -> END
                                                      `-- needs_escalation -> escalate_to_kavitas_team (interrupt!) -> grant_winner -> suggest_alternate_for_loser -> log -> END

The ONE genuine `interrupt()` in this graph is `escalate_to_kavitas_team`:
it fires only when the rulebook itself cannot resolve a case — a true dead
heat (identical commitment tier, identical days-of-cover, identical
timestamp) or a claim missing data the policy needs (no commitment tier on
file). That is a narrow, named exception, not a general human-in-the-loop
step for every collision — escalating exactly what a deterministic rule
can't resolve, and nothing more.

The registry (`lot_registry.LotRegistry`) is shared, real, cross-plant
state that persists across separate claim submissions — it is intentionally
NOT part of the LangGraph checkpointed state (which is scoped to one claim's
own journey through the graph). Each node closes over the same `LotRegistry`
instance, the same way a real deployment's nodes would close over a shared
database connection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from lot_registry import LotRegistry
from precedence_policy import resolve_precedence, suggest_alternate_cover


class Claim(TypedDict):
    claim_id: str
    plant: str
    supplier: str
    lot_id: str
    sku: str
    quantity_needed: int
    commitment_tier: Optional[int]
    days_of_cover: Optional[float]
    requested_at: float  # a monotonically increasing float; lower = earlier
    requested_at_display: str  # human-readable clock time for logs/printing


def make_claim(
    claim_id: str,
    plant: str,
    supplier: str,
    lot_id: str,
    sku: str,
    quantity_needed: int,
    requested_at: float,
    requested_at_display: str,
    commitment_tier: Optional[int] = None,
    days_of_cover: Optional[float] = None,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        plant=plant,
        supplier=supplier,
        lot_id=lot_id,
        sku=sku,
        quantity_needed=quantity_needed,
        commitment_tier=commitment_tier,
        days_of_cover=days_of_cover,
        requested_at=requested_at,
        requested_at_display=requested_at_display,
    )


class GraphState(TypedDict):
    claim: Claim
    collisions: list[Claim]
    arbitration: Optional[dict[str, Any]]
    outcome: Optional[dict[str, Any]]
    log: list[dict[str, Any]]


def make_initial_state(claim: Claim) -> GraphState:
    return GraphState(claim=claim, collisions=[], arbitration=None, outcome=None, log=[])


def build_graph(registry: LotRegistry):
    """
    Wire the arbitration graph together, bound to one shared `LotRegistry`.
    Every node below closes over `registry` rather than carrying it through
    checkpointed state, because the registry has to persist across many
    separate claim submissions (separate graph runs), not just one.
    """

    def submit_claim(state: GraphState) -> dict[str, Any]:
        """A plant's agent registers an allocation request against a lot."""
        claim = state["claim"]
        registry.register_pending(claim)
        return {
            "log": state["log"]
            + [{"event": "submit_claim", "plant": claim["plant"], "lot_id": claim["lot_id"], "claim": claim}]
        }

    def check_registry(state: GraphState) -> dict[str, Any]:
        """Does this claim collide with another open/confirmed claim on the same lot?"""
        collisions = registry.find_collisions(state["claim"])
        return {"collisions": collisions}

    def route_after_check(state: GraphState) -> Literal["grant", "arbitrate"]:
        return "arbitrate" if state["collisions"] else "grant"

    def grant(state: GraphState) -> dict[str, Any]:
        """No collision: confirm the hold immediately. No arbitration, no human."""
        claim = state["claim"]
        registry.confirm(claim)
        outcome = {
            "claim_id": claim["claim_id"],
            "plant": claim["plant"],
            "result": "granted",
            "reason": f"No open or confirmed claim exists elsewhere on {claim['supplier']} / lot {claim['lot_id']}.",
        }
        return {"outcome": outcome}

    def arbitrate(state: GraphState) -> dict[str, Any]:
        """
        Apply the pre-approved precedence rulebook deterministically.
        Supports more than one simultaneous competitor by folding the
        rulebook pairwise: the current claim is challenged by each
        colliding claim in turn, carrying the running winner forward.
        """
        current = state["claim"]
        computation: list[str] = []
        losers: list[Claim] = []
        for other in state["collisions"]:
            result = resolve_precedence(current, other)
            if result.needs_escalation:
                return {
                    "arbitration": {
                        "needs_escalation": True,
                        "escalation_reason": result.escalation_reason,
                        "computation": computation,
                        "competing_claims": [state["claim"]] + state["collisions"],
                    }
                }
            computation.append(result.explanation)
            losers.append(result.loser)
            current = result.winner

        return {
            "arbitration": {
                "needs_escalation": False,
                "winner_claim": current,
                "losers": losers,
                "computation": computation,
                "competing_claims": [state["claim"]] + state["collisions"],
            }
        }

    def route_after_arbitrate(state: GraphState) -> Literal["grant_winner", "escalate_to_kavitas_team"]:
        return "escalate_to_kavitas_team" if state["arbitration"]["needs_escalation"] else "grant_winner"

    def escalate_to_kavitas_team(state: GraphState) -> dict[str, Any]:
        """
        The ONE legitimate interrupt in this graph: the rulebook could not
        resolve the collision on its own (a genuine dead heat, or a claim
        missing data the policy needs). Pause for real, and hand it to a
        named human team instead of guessing.
        """
        arbitration = state["arbitration"]
        payload = {
            "reason": arbitration["escalation_reason"],
            "competing_claims": arbitration["competing_claims"],
            "escalated_to": "Kavita Iyer's team",
        }
        response = interrupt(payload)

        winner_plant = response["winner_plant"]
        all_claims = arbitration["competing_claims"]
        winner_claim = next(c for c in all_claims if c["plant"] == winner_plant)
        losers = [c for c in all_claims if c["plant"] != winner_plant]

        arbitration = dict(arbitration)
        arbitration["needs_escalation"] = False
        arbitration["winner_claim"] = winner_claim
        arbitration["losers"] = losers
        arbitration["resolved_by_human"] = response.get("decided_by", "Kavita Iyer's team")
        arbitration["human_note"] = response.get("note", "")
        arbitration["computation"] = arbitration["computation"] + [
            f"Escalated to {arbitration['resolved_by_human']}: {arbitration['human_note']} "
            f"-> {winner_plant} designated winner by human decision, not by the rulebook."
        ]
        return {"arbitration": arbitration}

    def grant_winner(state: GraphState) -> dict[str, Any]:
        arbitration = state["arbitration"]
        winner = arbitration["winner_claim"]
        registry.confirm(winner)
        outcome = {
            "claim_id": winner["claim_id"],
            "plant": winner["plant"],
            "result": "granted_after_arbitration",
            "reason": arbitration["computation"][-1],
        }
        return {"outcome": outcome}

    def suggest_alternate_for_loser(state: GraphState) -> dict[str, Any]:
        arbitration = dict(state["arbitration"])
        suggestions = []
        for loser in arbitration["losers"]:
            registry.close_lost(loser)
            suggestion = suggest_alternate_cover(loser)
            suggestions.append(suggestion)
        arbitration["alternate_suggestions"] = suggestions
        return {"arbitration": arbitration}

    def log(state: GraphState) -> dict[str, Any]:
        """
        Write the final audit entry to the SHARED registry log (not just
        this claim's own state) — every arbitration captures both competing
        claims, the precedence computation that resolved them, and the
        final resolution, logging the "conversation between agents," not
        just one agent's own reasoning.
        """
        claim = state["claim"]
        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "claim_id": claim["claim_id"],
            "plant": claim["plant"],
            "supplier": claim["supplier"],
            "lot_id": claim["lot_id"],
            "outcome": state["outcome"],
        }
        arbitration = state.get("arbitration")
        if arbitration:
            entry["type"] = "arbitrated"
            entry["competing_claims"] = arbitration["competing_claims"]
            entry["computation"] = arbitration["computation"]
            entry["winner"] = arbitration["winner_claim"]["plant"]
            entry["escalated_to_human"] = "resolved_by_human" in arbitration
            entry["alternate_suggestions"] = arbitration.get("alternate_suggestions", [])
        else:
            entry["type"] = "clear"

        registry.record_arbitration(entry)
        return {"log": state["log"] + [entry]}

    graph = StateGraph(GraphState)

    # Step 1: register the nodes — claim submission, the registry check,
    # the no-collision grant path, and the arbitration path (including the
    # one legitimate human-escalation node for a genuine dead heat).
    graph.add_node("submit_claim", submit_claim)
    graph.add_node("check_registry", check_registry)
    graph.add_node("grant", grant)
    graph.add_node("arbitrate", arbitrate)
    graph.add_node("escalate_to_kavitas_team", escalate_to_kavitas_team)
    graph.add_node("grant_winner", grant_winner)
    graph.add_node("suggest_alternate_for_loser", suggest_alternate_for_loser)
    graph.add_node("log", log)

    # Step 2: wire the entry point and the routing decisions — whether the
    # claim collides with another one on the same lot (grant vs. arbitrate),
    # and, if it does, whether the precedence rulebook can resolve it on its
    # own or has to escalate a genuine tie.
    graph.add_edge(START, "submit_claim")
    graph.add_edge("submit_claim", "check_registry")
    graph.add_conditional_edges(
        "check_registry", route_after_check, {"grant": "grant", "arbitrate": "arbitrate"}
    )
    graph.add_conditional_edges(
        "arbitrate",
        route_after_arbitrate,
        {"grant_winner": "grant_winner", "escalate_to_kavitas_team": "escalate_to_kavitas_team"},
    )

    # Step 3: wire the remaining fixed edges — every path converges on log,
    # and log ends the run.
    graph.add_edge("grant", "log")
    graph.add_edge("escalate_to_kavitas_team", "grant_winner")
    graph.add_edge("grant_winner", "suggest_alternate_for_loser")
    graph.add_edge("suggest_alternate_for_loser", "log")
    graph.add_edge("log", END)
    return graph
