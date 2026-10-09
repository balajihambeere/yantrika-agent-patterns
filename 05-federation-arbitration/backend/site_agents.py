"""
The two site-scoped optimization agents behind a two-plant rollout:
Pune's allocation agent and Nashik's allocation agent, each with a fully
accurate view of only its own plant's demand and inventory.

Splitting allocation logic this way is the right call when there is one
plant. It stops being free once there are two: Pune's agent correctly
sees its own surplus of a fastener family; Nashik's agent, independently,
correctly sees it can cover its own shortfall of the same family via a
rush order against a shared supplier's open capacity. Neither is wrong by
its own narrow logic. The two functions below are exactly that narrow
logic, kept deliberately simple, explicit, and rule-based — no LLM, just
threshold/arithmetic. Nothing here resolves the conflict between the two
sites; that is `federation_graph.py`'s job (the arbitration layer built
to resolve exactly this kind of collision).

`evaluate_pune_position()` also models the one *legitimate* use of a
"limited pilot connection... approved for observation only": when
`observe_nashik` is True, Pune's agent may look at Nashik's position to
decide whether its own surplus is worth offering across the boundary.
Looking is cheap and low-risk (the "observe" tier); it is not, by itself,
permission to move anything — that distinction is exactly what the tier
model in `federation_graph.py` enforces.
"""
from __future__ import annotations

from typing import Optional, TypedDict

# How far a site's on-hand balance has to sit above its buffer target
# before the agent calls it "surplus" worth acting on, rather than normal
# day-to-day slack around the target.
SURPLUS_THRESHOLD_UNITS = 50

# How far a site's on-hand balance has to sit below its buffer target
# before the agent calls it a "shortfall" worth covering, rather than
# normal day-to-day slack around the target.
SHORTFALL_THRESHOLD_UNITS = 50


class SitePosition(TypedDict):
    """One plant's current, fully-accurate view of one fastener family."""

    site: str
    sku_family: str
    on_hand: int
    buffer_target: int


class SupplierCapacity(TypedDict):
    """A shared supplier's confirmed open capacity for one fastener family.

    This is infrastructure both plants can see without crossing any plant
    boundary — it is the supplier's schedule, not either site's private
    inventory data — which is why Nashik's agent can use it without any
    observe-tier grant into Pune."""

    supplier: str
    sku_family: str
    open_capacity: int


class LocalRecommendation(TypedDict):
    """A site-scoped agent's own, narrow recommendation.

    `action` is one of:
      - "no_action" — within buffer target, nothing to do.
      - "surplus_available" — surplus exists, but there is nothing (visible
        or in range) to use it for, so it stays local awareness only.
      - "offer_cross_boundary_transfer" — surplus exists AND, under the
        observe tier, a shortfall was seen at another named site worth
        offering it to. Touches another site's resources, but is only ever
        a recommendation here, never an execution.
      - "rush_order" — shortfall exists and can be covered by placing an
        order against a shared supplier's own open capacity, entirely
        within the site's own authority.
    """

    site: str
    sku_family: str
    action: str
    quantity: int
    rationale: str
    touches_other_site: Optional[str]


def _balance(position: SitePosition) -> int:
    """Positive = surplus above the buffer target, negative = shortfall below it."""
    return position["on_hand"] - position["buffer_target"]


def evaluate_pune_position(
    pune_position: SitePosition,
    nashik_position: Optional[SitePosition],
    observe_nashik: bool,
) -> LocalRecommendation:
    """
    Pune's allocation agent. Pune's own surplus/shortfall math never
    changes based on what it can or can't see elsewhere — that would be
    the agent inventing visibility it doesn't have. What *does* change is
    whether a surplus gets offered across the boundary: that requires an
    observe-tier grant into Nashik's position — a
    "limited pilot connection... approved for observation only."
    """
    surplus = _balance(pune_position)
    site, sku = pune_position["site"], pune_position["sku_family"]

    if surplus <= SURPLUS_THRESHOLD_UNITS:
        return LocalRecommendation(
            site=site,
            sku_family=sku,
            action="no_action",
            quantity=0,
            rationale=(
                f"On-hand {pune_position['on_hand']} vs. buffer target "
                f"{pune_position['buffer_target']} — within the normal band, nothing to act on."
            ),
            touches_other_site=None,
        )

    if not observe_nashik or nashik_position is None:
        return LocalRecommendation(
            site=site,
            sku_family=sku,
            action="surplus_available",
            quantity=surplus,
            rationale=(
                f"Surplus of {surplus} units on {sku} above the {pune_position['buffer_target']}-unit "
                f"buffer target. No visibility into any other site under the current connection — "
                f"the surplus sits local, unacted on, by design."
            ),
            touches_other_site=None,
        )

    nashik_shortfall = -_balance(nashik_position)
    if nashik_shortfall <= SHORTFALL_THRESHOLD_UNITS:
        return LocalRecommendation(
            site=site,
            sku_family=sku,
            action="surplus_available",
            quantity=surplus,
            rationale=(
                f"Surplus of {surplus} units on {sku}. Observed {nashik_position['site']}'s position "
                f"under the pilot connection ({nashik_position['on_hand']} on hand vs. "
                f"{nashik_position['buffer_target']} target) — no shortfall worth offering the surplus "
                f"against, so this stays local awareness only, not a cross-boundary recommendation."
            ),
            touches_other_site=None,
        )

    offer_quantity = min(surplus, nashik_shortfall)
    return LocalRecommendation(
        site=site,
        sku_family=sku,
        action="offer_cross_boundary_transfer",
        quantity=offer_quantity,
        rationale=(
            f"Surplus of {surplus} units on {sku}. Observed {nashik_position['site']}'s shortfall of "
            f"{nashik_shortfall} units on the same family under the pilot connection — recommending "
            f"{offer_quantity} units be offered across the boundary to cover it."
        ),
        touches_other_site=nashik_position["site"],
    )


def evaluate_nashik_position(
    nashik_position: SitePosition,
    supplier: SupplierCapacity,
) -> LocalRecommendation:
    """
    Nashik's allocation agent. It never needs to see Pune's data to reach
    this recommendation — it is watching its own shortfall against a
    supplier's confirmed, shared shipment schedule, both squarely inside
    its own authority. That is exactly why this recommendation can be
    individually correct and still collide with Pune's: Nashik's agent has
    no way of knowing, from inside its own boundary, that the shortfall it
    is about to rush-order against is about to be covered another way.
    """
    site, sku = nashik_position["site"], nashik_position["sku_family"]
    shortfall = -_balance(nashik_position)

    if shortfall <= SHORTFALL_THRESHOLD_UNITS:
        return LocalRecommendation(
            site=site,
            sku_family=sku,
            action="no_action",
            quantity=0,
            rationale=(
                f"On-hand {nashik_position['on_hand']} vs. buffer target "
                f"{nashik_position['buffer_target']} — within the normal band, nothing to act on."
            ),
            touches_other_site=None,
        )

    order_quantity = min(shortfall, supplier["open_capacity"])
    return LocalRecommendation(
        site=site,
        sku_family=sku,
        action="rush_order",
        quantity=order_quantity,
        rationale=(
            f"Shortfall of {shortfall} units on {sku}. {supplier['supplier']}'s confirmed shipment "
            f"schedule shows {supplier['open_capacity']} units of open capacity on the same family — "
            f"recommending a rush order for {order_quantity} units against it, entirely within Nashik's "
            f"own authority."
        ),
        touches_other_site=None,
    )
