"""
The pre-approved precedence rulebook Kavita Iyer's team signed off on once,
in advance, after Pune and Plant Two both placed a hold against the same
Nashik supplier-lot within four minutes of each other.

The design is explicit that the fix is NOT agent-to-agent negotiation
("sounds elegant and becomes impossible to audit six months later") and NOT
case-by-case human refereeing of every collision. It is a deterministic
rulebook, applied the same way every time, in this exact order:

    1. customer-commitment tier   — whichever claim is attached to the
                                     higher commitment tier wins outright.
    2. days-of-cover remaining    — if tiers tie, the plant with LESS cover
                                     (more urgent) wins.
    3. request timestamp          — if that also ties, the earliest request
                                     wins.

If all three tiers are exhausted and the claims are still genuinely
indistinguishable — or a claim is missing data the policy needs, such as no
commitment tier on file — this module refuses to guess. It reports back
that the case needs a named human, which is exactly the one legitimate
escalation path `coordination_graph.py` wires up with a real `interrupt()`.

No LLM, no API key: this follows the same rule-based, deterministic style
used throughout this project's companion code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Lower number = higher priority. This mapping, like the rest of the policy,
# is the thing Kavita's team reviewed and signed off on once, in advance —
# not something decided per incident.
COMMITMENT_TIER_LABELS: dict[int, str] = {
    1: "Tier 1 (contractual customer commitment, penalty exposure)",
    2: "Tier 2 (committed customer order, no penalty clause)",
    3: "Tier 3 (forecast / safety-stock replenishment)",
}


def tier_label(tier: Optional[int]) -> str:
    if tier is None:
        return "no commitment tier on file"
    return COMMITMENT_TIER_LABELS.get(tier, f"Tier {tier}")


@dataclass
class ArbitrationResult:
    """The outcome of running the rulebook against two competing claims."""

    winner: Optional[dict]
    loser: Optional[dict]
    decided_by: Optional[str]  # "commitment_tier" | "days_of_cover" | "timestamp"
    explanation: str
    needs_escalation: bool = False
    escalation_reason: Optional[str] = None


def resolve_precedence(claim_a: dict, claim_b: dict) -> ArbitrationResult:
    """
    Apply the three-step precedence rulebook to two claims against the same
    supplier-lot. Returns an ArbitrationResult naming the winner and exactly
    which tier of the rule decided it — or, if the rule genuinely cannot
    decide, an ArbitrationResult flagged `needs_escalation=True` instead of
    guessing.
    """
    lot = f"{claim_a['supplier']} / lot {claim_a['lot_id']}"

    # Guard: the policy needs a commitment tier on file for both claims
    # before it can even start. A missing value is exactly the kind of
    # data gap a deterministic rule should refuse to paper over.
    for claim in (claim_a, claim_b):
        if claim.get("commitment_tier") is None:
            return ArbitrationResult(
                winner=None,
                loser=None,
                decided_by=None,
                explanation=(
                    f"{claim_a['plant']} vs {claim_b['plant']} on {lot}: cannot apply "
                    f"the precedence rulebook — {claim['plant']}'s claim has no "
                    f"commitment tier on file."
                ),
                needs_escalation=True,
                escalation_reason=(
                    f"{claim['plant']}'s claim on {lot} is missing a commitment tier. "
                    f"The rulebook's first tier cannot be evaluated without it."
                ),
            )

    # Tier 1 — customer-commitment tier.
    if claim_a["commitment_tier"] != claim_b["commitment_tier"]:
        winner, loser = (
            (claim_a, claim_b)
            if claim_a["commitment_tier"] < claim_b["commitment_tier"]
            else (claim_b, claim_a)
        )
        explanation = (
            f"Resolved at TIER 1 (commitment tier) on {lot}: {winner['plant']}'s claim is "
            f"{tier_label(winner['commitment_tier'])} and outranks {loser['plant']}'s "
            f"{tier_label(loser['commitment_tier'])}. Higher commitment tier wins outright; "
            f"no further comparison needed."
        )
        return ArbitrationResult(winner, loser, "commitment_tier", explanation)

    # Commitment tiers tied — need days-of-cover for both before tier 2 runs.
    for claim in (claim_a, claim_b):
        if claim.get("days_of_cover") is None:
            return ArbitrationResult(
                winner=None,
                loser=None,
                decided_by=None,
                explanation=(
                    f"{claim_a['plant']} vs {claim_b['plant']} on {lot}: commitment tiers "
                    f"tied at {tier_label(claim_a['commitment_tier'])}, but "
                    f"{claim['plant']}'s claim has no days-of-cover figure on file."
                ),
                needs_escalation=True,
                escalation_reason=(
                    f"{claim['plant']}'s claim on {lot} is missing a days-of-cover figure, "
                    f"needed to break a commitment-tier tie."
                ),
            )

    # Tier 2 — days-of-cover remaining. Less cover = more urgent = wins.
    if claim_a["days_of_cover"] != claim_b["days_of_cover"]:
        winner, loser = (
            (claim_a, claim_b)
            if claim_a["days_of_cover"] < claim_b["days_of_cover"]
            else (claim_b, claim_a)
        )
        explanation = (
            f"Resolved at TIER 2 (days-of-cover) on {lot}: commitment tiers tied at "
            f"{tier_label(winner['commitment_tier'])}, so the rule moved to days-of-cover. "
            f"{winner['plant']} has {winner['days_of_cover']:.1f} days of cover remaining "
            f"versus {loser['plant']}'s {loser['days_of_cover']:.1f} days — less cover "
            f"(more urgent) wins."
        )
        return ArbitrationResult(winner, loser, "days_of_cover", explanation)

    # Tier 3 — timestamp tie-break. Earliest request wins.
    if claim_a["requested_at"] != claim_b["requested_at"]:
        winner, loser = (
            (claim_a, claim_b)
            if claim_a["requested_at"] < claim_b["requested_at"]
            else (claim_b, claim_a)
        )
        explanation = (
            f"Resolved at TIER 3 (timestamp tie-break) on {lot}: commitment tiers and "
            f"days-of-cover both tied, so the rule fell through to request time. "
            f"{winner['plant']} requested at {winner['requested_at_display']}, "
            f"{loser['plant']} requested at {loser['requested_at_display']} — earliest "
            f"request wins."
        )
        return ArbitrationResult(winner, loser, "timestamp", explanation)

    # Every tier exhausted and still identical: a genuine dead heat. The
    # rulebook does not guess past this point — it escalates by name.
    return ArbitrationResult(
        winner=None,
        loser=None,
        decided_by=None,
        explanation=(
            f"{claim_a['plant']} vs {claim_b['plant']} on {lot}: identical commitment "
            f"tier, identical days-of-cover, identical request timestamp to the precision "
            f"available. The rulebook has no further tier to apply."
        ),
        needs_escalation=True,
        escalation_reason=(
            f"Genuine dead heat between {claim_a['plant']} and {claim_b['plant']} on {lot} — "
            f"commitment tier, days-of-cover, and timestamp are all identical."
        ),
    )


# ---------------------------------------------------------------------------
# Alternate-cover suggestions for the losing claim.
#
# By design, the loser doesn't just get rejected — it gets an immediate,
# specific alternate-cover suggestion, not a hold that silently turns out to
# be worthless. This is a small, scripted inventory of alternatives, keyed
# by SKU, exactly as deterministic as the rest of this module.
# ---------------------------------------------------------------------------

ALTERNATE_COVER_CATALOG: dict[str, list[dict]] = {
    "M8x40-hex-flange-bolt": [
        {
            "type": "alternate_lot",
            "supplier": "Nashik Precision Fasteners",
            "lot_id": "NPF-LOT-4489",
            "available_qty": 18000,
            "lead_time_days": 1,
            "note": "Same supplier, different lot — already quality-cleared, sitting in the same Nashik warehouse.",
        },
        {
            "type": "alternate_supplier",
            "supplier": "Satara Fastener Works",
            "lot_id": "SFW-LOT-0094",
            "available_qty": 12000,
            "lead_time_days": 2,
            "note": "Approved alternate vendor on the supplier scorecard; slightly higher unit cost.",
        },
        {
            "type": "expedite",
            "supplier": "Nashik Precision Fasteners",
            "lot_id": "NPF-LOT-4502",
            "available_qty": 20000,
            "lead_time_days": 1,
            "note": "Air-expedite the next scheduled lot from the same supplier, arriving early for a freight surcharge.",
        },
    ],
    "connector-housing-14p": [
        {
            "type": "alternate_lot",
            "supplier": "Igatpuri Moulding Co.",
            "lot_id": "IMC-LOT-2210",
            "available_qty": 9000,
            "lead_time_days": 2,
            "note": "Same supplier, next lot off the same tool — already approved to the same part revision.",
        },
        {
            "type": "expedite",
            "supplier": "Igatpuri Moulding Co.",
            "lot_id": "IMC-LOT-2214",
            "available_qty": 9500,
            "lead_time_days": 1,
            "note": "Expedite freight on the lot already scheduled for next week.",
        },
    ],
}

_DEFAULT_ALTERNATES: list[dict] = [
    {
        "type": "expedite",
        "supplier": "unassigned — Stores to confirm",
        "lot_id": "n/a",
        "available_qty": 0,
        "lead_time_days": 3,
        "note": "No pre-scripted alternate on file for this SKU — route to Stores for a manual cover check.",
    }
]


def suggest_alternate_cover(losing_claim: dict) -> dict:
    """
    Return the best-ranked alternate-cover option for a losing claim's SKU:
    the first entry in the scripted catalog (ordered best-first), or a
    generic "route to Stores" fallback if the SKU isn't in the catalog.
    """
    options = ALTERNATE_COVER_CATALOG.get(losing_claim["sku"], _DEFAULT_ALTERNATES)
    best = options[0]
    suggestion = dict(best)
    suggestion["for_plant"] = losing_claim["plant"]
    suggestion["original_lot_id"] = losing_claim["lot_id"]
    suggestion["sku"] = losing_claim["sku"]
    suggestion["message"] = (
        f"{losing_claim['plant']}'s claim on {losing_claim['lot_id']} lost arbitration. "
        f"Immediate alternate cover: {suggestion['type']} — {suggestion['supplier']} "
        f"lot {suggestion['lot_id']} ({suggestion['available_qty']} units, "
        f"{suggestion['lead_time_days']}-day lead time). {suggestion['note']}"
    )
    return suggestion
