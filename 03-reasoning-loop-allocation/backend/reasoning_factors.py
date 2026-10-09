"""
The five-factor weighing logic behind a continuous reasoning loop.

Five factors that Vimana's old two-tier priority rule
(Tier 1 contracted accounts always win) was quietly ignoring:

    1. Contract penalty exposure
    2. Strategic account value / trajectory — where the relationship is
       headed, not just where it's been
    3. Downstream production impact if the order ships short
    4. Confidence in the next replenishment — is tomorrow's delivery a
       promise or a certainty
    5. Cost to close the gap some other way (e.g. an expedite)

The core argument is that these weights have to be written down, on
purpose, defensibly — "a first pass, the way the decision-rights map
was a first pass two years ago" — rather than left to live, ungoverned,
in whoever happens to be in the room. The numbers below are that first
pass: explicit, commented, and meant to be argued with and revised, not
hidden inside a model nobody can inspect.

Everything in this module is plain arithmetic. No LLM call, no model
weights learned from data — kept rule-based deliberately, so the result
is deterministic and reproducible. The "reasoning" described here is
reasoning about *which explicit factors apply and how much*, not a
language model guessing at an allocation.
"""
from __future__ import annotations

from typing import Optional, TypedDict


class CompetingOrder(TypedDict):
    """One claim on a constrained SKU, carrying the raw inputs for all five factors."""

    account: str
    requested_units: int
    contract_penalty_inr: float  # Factor 1 — penalty exposure if this order ships short
    downstream_impact_inr: float  # Factor 3 — cost to the account's own downstream line if short
    strategic_score: float  # Factor 2 — trajectory, -2.0 (declining) .. +2.0 (strongly improving)
    replenishment_confidence: float  # Factor 4 — 0.0 (a hopeful promise) .. 1.0 (a near certainty)
    expedite_cost_inr: float  # Factor 5 — cost to close this order's gap some other way
    note: str  # one-line human context, carried into the audit log verbatim


class FactorScores(TypedDict):
    account: str
    requested_units: int
    factor_points: dict[str, float]  # each factor's weighted contribution, 0..~weight*100
    factor_percentiles: dict[str, float]  # each factor normalized to 0..100 before weighting
    weighted_total: float  # sum of factor_points, 0..100
    rationale: list[str]  # one human-readable line per factor


class AllocationResult(TypedDict):
    account: str
    requested_units: int
    allocated_units: int
    fraction: float
    status: str  # "complete" | "partial" | "held"
    message: Optional[str]


# ---------------------------------------------------------------------------
# The weights. Written down on purpose — Vikram's point that
# the hard part isn't the arithmetic, it's making Vimana's implicit values
# explicit enough to defend out loud and revise on purpose later.
#
# These five must sum to 1.0. Rationale for each is the one-line
# justification Aditi, Rohit, and Suresh's first draft would have had to
# survive being argued with in the Monday review.
# ---------------------------------------------------------------------------
WEIGHT_CONTRACT_PENALTY = 0.30
# Highest weight: a contract penalty is a promise Vimana already made in
# writing, with a dollar figure attached. It's the hardest, least arguable
# number of the five.

WEIGHT_DOWNSTREAM_IMPACT = 0.25
# Second highest: Rohit's history showed cases where the downstream cost of
# shorting an order — a stoppage on someone else's line — was several times
# the contractual penalty on the other side. This factor exists specifically
# because the old tier rule had no way to see it.

WEIGHT_STRATEGIC_TRAJECTORY = 0.20
# Where the relationship is headed, not just its current tier label. This is
# the factor that lets a growing Tier-2 prospect outweigh a shrinking Tier-1
# account, and the one Anand insisted be explicit rather than a gut feel.

WEIGHT_REPLENISHMENT_CONFIDENCE = 0.15
# Lower weight because it's a modifier on urgency, not a claim on the stock
# in its own right: a high-confidence next delivery makes it *safer* to
# defer this order, it doesn't make the order itself less legitimate.

WEIGHT_EXPEDITE_COST = 0.10
# Lowest weight, deliberately: this is the most reversible factor of the
# five — if a gap can be patched cheaply some other way, that should nudge
# the allocation call, not dominate it.

assert abs(
    WEIGHT_CONTRACT_PENALTY
    + WEIGHT_DOWNSTREAM_IMPACT
    + WEIGHT_STRATEGIC_TRAJECTORY
    + WEIGHT_REPLENISHMENT_CONFIDENCE
    + WEIGHT_EXPEDITE_COST
    - 1.0
) < 1e-9, "the five weights must sum to 1.0"

# Normalization scales. These convert each factor's raw unit (rupees, a
# -2..+2 trajectory score, a 0..1 confidence) onto a comparable 0..100
# percentile before the weight is applied. Like the weights themselves,
# these are a first pass calibrated against the kind of numbers in
# Vimana's own shortfall history — not a universal constant.
CONTRACT_PENALTY_NORM_INR = 200_000.0
DOWNSTREAM_IMPACT_NORM_INR = 100_000.0
EXPEDITE_COST_NORM_INR = 100_000.0

# The bounded autonomy threshold — agreed in writing by
# Suresh and Anand *before* anything ran live: the system may allocate on
# its own only when the exposure on the losing side of the call stays under
# this figure. Above it, a human decides, reasoning attached, every time.
AUTONOMY_EXPOSURE_THRESHOLD_INR = 25_000.0

# How close two competing orders' weighted totals have to be to count as a
# "close call" — two or more factors pulling in genuinely opposite
# directions — rather than a clear read. Anything inside this margin
# escalates regardless of exposure.
CLOSE_CALL_MARGIN_POINTS = 8.0


def _pct(value: float, norm: float) -> float:
    """Clamp a raw rupee figure onto a 0..100 percentile against its norm."""
    if norm <= 0:
        return 0.0
    return max(0.0, min(100.0, (value / norm) * 100.0))


def score_order(order: CompetingOrder) -> FactorScores:
    """
    Score one competing order against all five factors. Deterministic,
    rule-based arithmetic — no model, no API call. Every number that goes
    into the final weighted_total is retained in factor_points/
    factor_percentiles/rationale so the reasoning itself can be logged and
    reviewed later, not just the outcome.
    """
    contract_pct = _pct(order["contract_penalty_inr"], CONTRACT_PENALTY_NORM_INR)
    downstream_pct = _pct(order["downstream_impact_inr"], DOWNSTREAM_IMPACT_NORM_INR)
    strategic_pct = max(0.0, min(100.0, (order["strategic_score"] + 2.0) / 4.0 * 100.0))
    # Confidence is inverted into urgency: a near-certain next delivery
    # (confidence -> 1.0) makes it *safe to defer*, i.e. low urgency.
    confidence_urgency_pct = max(0.0, min(100.0, (1.0 - order["replenishment_confidence"]) * 100.0))
    expedite_pct = _pct(order["expedite_cost_inr"], EXPEDITE_COST_NORM_INR)

    factor_percentiles = {
        "contract_penalty": contract_pct,
        "downstream_impact": downstream_pct,
        "strategic_trajectory": strategic_pct,
        "replenishment_confidence": confidence_urgency_pct,
        "cost_to_close_gap": expedite_pct,
    }
    factor_points = {
        "contract_penalty": contract_pct * WEIGHT_CONTRACT_PENALTY,
        "downstream_impact": downstream_pct * WEIGHT_DOWNSTREAM_IMPACT,
        "strategic_trajectory": strategic_pct * WEIGHT_STRATEGIC_TRAJECTORY,
        "replenishment_confidence": confidence_urgency_pct * WEIGHT_REPLENISHMENT_CONFIDENCE,
        "cost_to_close_gap": expedite_pct * WEIGHT_EXPEDITE_COST,
    }
    weighted_total = round(sum(factor_points.values()), 2)

    rationale = [
        f"Contract penalty exposure: Rs.{order['contract_penalty_inr']:,.0f} -> "
        f"{contract_pct:.1f}/100 x weight {WEIGHT_CONTRACT_PENALTY} = {factor_points['contract_penalty']:.1f} pts.",
        f"Downstream production impact if shipped short: Rs.{order['downstream_impact_inr']:,.0f} -> "
        f"{downstream_pct:.1f}/100 x weight {WEIGHT_DOWNSTREAM_IMPACT} = {factor_points['downstream_impact']:.1f} pts.",
        f"Strategic trajectory score {order['strategic_score']:+.1f} (-2..+2) -> "
        f"{strategic_pct:.1f}/100 x weight {WEIGHT_STRATEGIC_TRAJECTORY} = {factor_points['strategic_trajectory']:.1f} pts.",
        f"Replenishment confidence {order['replenishment_confidence']:.2f} (1.0=certainty) -> "
        f"urgency {confidence_urgency_pct:.1f}/100 x weight {WEIGHT_REPLENISHMENT_CONFIDENCE} = "
        f"{factor_points['replenishment_confidence']:.1f} pts.",
        f"Cost to close the gap another way: Rs.{order['expedite_cost_inr']:,.0f} -> "
        f"{expedite_pct:.1f}/100 x weight {WEIGHT_EXPEDITE_COST} = {factor_points['cost_to_close_gap']:.1f} pts.",
    ]

    return FactorScores(
        account=order["account"],
        requested_units=order["requested_units"],
        factor_points=factor_points,
        factor_percentiles=factor_percentiles,
        weighted_total=weighted_total,
        rationale=rationale,
    )


def rank_orders(scored: list[FactorScores]) -> list[FactorScores]:
    """Highest weighted_total first; ties broken by account name for determinism."""
    return sorted(scored, key=lambda s: (-s["weighted_total"], s["account"]))


def allocate_units(available_units: int, orders: list[CompetingOrder], ranking: list[str]) -> dict[str, AllocationResult]:
    """
    Greedy fill in priority-rank order: the highest-ranked claim is filled
    first and completely if the batch can cover it, then the next, and so
    on, until the shrinking batch runs out. This is what turns a ranked
    list of five-factor scores into a realistic split — one order
    complete, one partially filled with a remainder promised for a
    specific day, one held entirely with an apology queued.
    """
    by_account = {o["account"]: o for o in orders}
    remaining = available_units
    result: dict[str, AllocationResult] = {}

    for account in ranking:
        order = by_account[account]
        requested = order["requested_units"]
        give = max(0, min(requested, remaining))
        remaining -= give
        fraction = (give / requested) if requested else 1.0

        if give == 0:
            status, message = "held", (
                "Held entirely for the next replenishment cycle — apology and "
                "revised delivery date queued."
            )
        elif give < requested:
            status, message = "partial", (
                f"Filled at {fraction * 100:.0f}% now; remainder promised for Thursday."
            )
        else:
            status, message = "complete", None

        result[account] = AllocationResult(
            account=account,
            requested_units=requested,
            allocated_units=give,
            fraction=round(fraction, 4),
            status=status,
            message=message,
        )
    return result


def exposure_on_losing_side(orders: list[CompetingOrder], allocation: dict[str, AllocationResult]) -> float:
    """
    Rupee exposure carried by whichever claim(s) don't get filled in full —
    the "financial exposure on the losing side" the bounded
    autonomy threshold is written against. Scaled by the fraction actually
    short, so an order short by 20% carries 20% of its contract-penalty-
    plus-downstream exposure, not all of it.
    """
    by_account = {o["account"]: o for o in orders}
    total = 0.0
    for account, result in allocation.items():
        short_fraction = 1.0 - result["fraction"]
        if short_fraction <= 0:
            continue
        order = by_account[account]
        total += short_fraction * (order["contract_penalty_inr"] + order["downstream_impact_inr"])
    return round(total, 2)


def factors_clearly_agree(ranked: list[FactorScores]) -> bool:
    """
    True when the top-ranked claim's weighted_total is not within
    CLOSE_CALL_MARGIN_POINTS of the runner-up's. A single uncontested claim
    trivially agrees with itself. Closer than that counts as two or more
    factors pulling in genuinely opposite directions — a close call that
    must go to a human regardless of exposure.
    """
    if len(ranked) <= 1:
        return True
    return (ranked[0]["weighted_total"] - ranked[1]["weighted_total"]) >= CLOSE_CALL_MARGIN_POINTS


def check_bounded_autonomy(
    ranked: list[FactorScores],
    orders: list[CompetingOrder],
    allocation: dict[str, AllocationResult],
) -> dict:
    """
    The bounded-autonomy-threshold logic, precisely: the
    system may act alone only when (a) the weighted factors point clearly
    in one direction, AND (b) the exposure on the losing side stays under
    the agreed rupee threshold. Either condition failing routes to a human,
    with the full reasoning attached rather than a bare recommendation.
    """
    clear = factors_clearly_agree(ranked)
    exposure = exposure_on_losing_side(orders, allocation)
    over_threshold = exposure > AUTONOMY_EXPOSURE_THRESHOLD_INR
    requires_human = (not clear) or over_threshold

    reasons = []
    if not clear:
        margin = (ranked[0]["weighted_total"] - ranked[1]["weighted_total"]) if len(ranked) > 1 else 0.0
        reasons.append(
            f"close call — top two weighted scores are only {margin:.1f} points apart "
            f"(< {CLOSE_CALL_MARGIN_POINTS} margin), i.e. two or more factors are pulling "
            f"in genuinely opposite directions"
        )
    if over_threshold:
        reasons.append(
            f"exposure on the losing side is Rs.{exposure:,.0f}, above the Rs."
            f"{AUTONOMY_EXPOSURE_THRESHOLD_INR:,.0f} bounded-autonomy threshold"
        )
    reason = "; and ".join(reasons) if reasons else (
        "factors clearly agree and exposure on the losing side is within the autonomy threshold"
    )

    return {
        "requires_human": requires_human,
        "clear_agreement": clear,
        "exposure_on_losing_side": exposure,
        "reason": reason,
    }
