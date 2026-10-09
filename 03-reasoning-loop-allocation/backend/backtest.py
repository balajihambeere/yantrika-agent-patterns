"""
Standalone backtest companion for the weighted allocation model.

The original backtest this illustration is based on ran the weighted
model against 41 historical shortfall events the old Tier 1/Tier 2 rule
had been tested against: the tier rule got 26/41 right; the weighted
model got 36/41, including all 8 of the two-Tier-1 standoffs the tier
rule couldn't resolve at all. The 5 it still missed were honestly
accounted for — 3 depended on a relationship read nobody had logged
anywhere the model could see, and 2 were cases two human reviewers
disagreed about even in hindsight.

This script is NOT that backtest. Rebuilding 41 real fulfillment records
isn't something this companion code can do honestly. What it does instead
is recreate a small, labeled-as-illustrative set of 10 representative
shortfall cases at the same *shape* as that history — clean single-
factor-dominant cases, two-Tier-1 standoffs, cases where a second or third
factor overturns what the tier rule would have said, and a couple of
genuinely hard misses — and compares, case by case, what the naive tier
rule would have said against what `reasoning_factors.score_order()` (the
actual weighing logic the system uses, called directly here, no graph,
no interrupt) says.

It calls the plain scoring function directly, not the full interrupting
graph — this backtest is explicitly a test of the *weighing logic*, not
of the escalation plumbing around it.

Run with:
    python3 backtest.py
"""
from __future__ import annotations

import json
from pathlib import Path

from reasoning_factors import CompetingOrder, rank_orders, score_order


class Case:
    def __init__(self, case_id: str, label: str, orders: list[CompetingOrder], ground_truth: str, note: str):
        self.case_id = case_id
        self.label = label
        self.orders = orders
        self.ground_truth = ground_truth
        self.note = note


def _order(account: str, requested: int, contract: float, downstream: float,
           strategic: float, confidence: float, expedite: float, note: str) -> CompetingOrder:
    return CompetingOrder(
        account=account,
        requested_units=requested,
        contract_penalty_inr=contract,
        downstream_impact_inr=downstream,
        strategic_score=strategic,
        replenishment_confidence=confidence,
        expedite_cost_inr=expedite,
        note=note,
    )


# ---------------------------------------------------------------------------
# 10 illustrative shortfall cases, recreated at the shape — not the scale —
# of Rohit's 41-event history. ground_truth is the editorial "what actually
# turned out to be the right call, in hindsight" label the original
# backtest graded both approaches against. Loaded from data/backtest_cases.json
# at runtime so the case data lives alongside the demo's scenario data.
# ---------------------------------------------------------------------------
_DATA_PATH = Path(__file__).parent / "data" / "backtest_cases.json"
with _DATA_PATH.open(encoding="utf-8") as _f:
    _RAW_CASES: list[dict] = json.load(_f)

CASES: list[Case] = [
    Case(
        case_id=raw["case_id"],
        label=raw["label"],
        orders=[
            _order(
                o["account"],
                o["requested_units"],
                o["contract_penalty_inr"],
                o["downstream_impact_inr"],
                o["strategic_score"],
                o["replenishment_confidence"],
                o["expedite_cost_inr"],
                o["note"],
            )
            for o in raw["orders"]
        ],
        ground_truth=raw["ground_truth"],
        note=raw["note"],
    )
    for raw in _RAW_CASES
]


def tier_rule_pick(orders: list[CompetingOrder]) -> str:
    """The naive rule this all replaces: Tier 1 (has a contract penalty) always beats Tier 2.
    If every side is the same tier, the rule has no answer at all."""
    tier1 = [o["account"] for o in orders if o["contract_penalty_inr"] > 0]
    tier2 = [o["account"] for o in orders if o["contract_penalty_inr"] <= 0]
    if tier1 and tier2:
        # Multiple Tier-1 accounts with Tier-2 others is out of scope for these two-order
        # cases; with exactly one Tier-1 side, the rule hands it the win outright.
        if len(tier1) == 1:
            return tier1[0]
    return "NO_CALL"  # both Tier 1, or both Tier 2 — the rule can't resolve it


def run_backtest() -> None:
    print("=" * 76)
    print("Backtest: weighted model vs. the naive Tier 1 / Tier 2 rule")
    print(f"({len(CASES)} illustrative cases — a small, honestly-labeled echo of the")
    print(" original 41-event backtest, not a reproduction of it)")
    print("=" * 76)

    model_correct = 0
    rule_correct = 0

    for case in CASES:
        scored = [score_order(o) for o in case.orders]
        ranked = rank_orders(scored)
        model_pick = ranked[0]["account"]
        rule_pick = tier_rule_pick(case.orders)

        model_hit = model_pick == case.ground_truth
        rule_hit = rule_pick == case.ground_truth
        model_correct += model_hit
        rule_correct += rule_hit

        print(f"\n[{case.case_id}] {case.label}")
        for s in ranked:
            print(f"    {s['account']:<28} weighted_total={s['weighted_total']:.1f}")
        print(f"    tier rule says:   {rule_pick:<28} {'MATCH' if rule_hit else 'miss'}")
        print(f"    model says:       {model_pick:<28} {'MATCH' if model_hit else 'miss'}")
        print(f"    ground truth:     {case.ground_truth}")
        print(f"    note: {case.note}")

    print("\n" + "=" * 76)
    print(f"Tier rule matched ground truth:   {rule_correct}/{len(CASES)}")
    print(f"Weighted model matched ground truth: {model_correct}/{len(CASES)}")
    print(
        "\nFor scale: the original backtest, run against 41 real shortfall events, had the "
        "tier rule correct in 26/41 (~63%) and the weighted model correct in 36/41 (~88%), "
        "including all 8 two-Tier-1 standoffs the rule couldn't resolve at all. This 10-case "
        "set is deliberately small and illustrative — it reproduces the *shape* of that result "
        "(the model clearly ahead, both approaches honestly imperfect, the rule specifically "
        "blind to same-tier standoffs) without pretending to be the real 41-event history."
    )


if __name__ == "__main__":
    run_backtest()
