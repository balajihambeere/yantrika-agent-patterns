"""
Tests for the LangGraph arbitration layer in coordination_graph.py.

Run with (inside the venv described in README.md):
    python3 -m unittest test_coordination_graph.py -v
"""
from __future__ import annotations

import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from coordination_graph import build_graph, make_claim, make_initial_state
from lot_registry import LotRegistry

SUPPLIER = "Nashik Precision Fasteners"
SKU = "M8x40-hex-flange-bolt"


def drive_to_completion(graph, thread_id, claim, human_response=None):
    """
    Runs one claim through the graph to completion, auto-resuming any
    interrupt with `human_response`. Returns (final_state_values,
    interrupt_count).
    """
    config = {"configurable": {"thread_id": thread_id}}
    stream_input = make_initial_state(claim)
    is_resuming = False
    interrupt_count = 0

    while True:
        chunk_input = Command(resume=stream_input) if is_resuming else stream_input
        hit_interrupt = False
        for chunk in graph.stream(chunk_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                hit_interrupt = True
                interrupt_count += 1

        if hit_interrupt:
            if human_response is None:
                raise AssertionError(f"Claim {claim['claim_id']} hit an unexpected interrupt.")
            stream_input = human_response
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values, interrupt_count


class CoordinationGraphTests(unittest.TestCase):
    def setUp(self):
        self.registry = LotRegistry()
        self.graph = build_graph(self.registry).compile(checkpointer=InMemorySaver())

    def _claim(self, claim_id, plant, lot_id="NPF-LOT-0001", **overrides):
        defaults = dict(
            supplier=SUPPLIER,
            sku=SKU,
            quantity_needed=10000,
            commitment_tier=2,
            days_of_cover=1.0,
            requested_at=100.0,
            requested_at_display="10:00",
        )
        defaults.update(overrides)
        return make_claim(claim_id=claim_id, plant=plant, lot_id=lot_id, **defaults)

    # ------------------------------------------------------------------

    def test_collision_resolved_by_commitment_tier_alone(self):
        first = self._claim("c1", "Pune", commitment_tier=1, days_of_cover=5.0, requested_at=100.0)
        second = self._claim("c2", "Plant Two", commitment_tier=2, days_of_cover=0.1, requested_at=101.0)

        drive_to_completion(self.graph, "t-tier-1", first)
        values, interrupts = drive_to_completion(self.graph, "t-tier-2", second)

        self.assertEqual(interrupts, 0)
        entry = values["log"][-1]
        self.assertEqual(entry["type"], "arbitrated")
        self.assertEqual(entry["winner"], "Pune")  # tier 1 beats tier 2 regardless of cover
        self.assertIn("TIER 1 (commitment tier)", entry["computation"][0])

    def test_tied_commitment_tier_resolved_by_days_of_cover(self):
        first = self._claim("c1", "Pune", commitment_tier=2, days_of_cover=3.0, requested_at=100.0)
        second = self._claim(
            "c2", "Plant Two", commitment_tier=2, days_of_cover=0.4, requested_at=101.0
        )

        drive_to_completion(self.graph, "t-cover-1", first)
        values, interrupts = drive_to_completion(self.graph, "t-cover-2", second)

        self.assertEqual(interrupts, 0)
        entry = values["log"][-1]
        self.assertEqual(entry["winner"], "Plant Two")  # less cover remaining = more urgent = wins
        self.assertIn("TIER 2 (days-of-cover)", entry["computation"][0])

    def test_tied_tier_and_cover_resolved_by_timestamp(self):
        first = self._claim("c1", "Pune", commitment_tier=3, days_of_cover=2.0, requested_at=50.0)
        second = self._claim("c2", "Plant Two", commitment_tier=3, days_of_cover=2.0, requested_at=55.0)

        drive_to_completion(self.graph, "t-ts-1", first)
        values, interrupts = drive_to_completion(self.graph, "t-ts-2", second)

        self.assertEqual(interrupts, 0)
        entry = values["log"][-1]
        self.assertEqual(entry["winner"], "Pune")  # earliest request wins
        self.assertIn("TIER 3 (timestamp tie-break)", entry["computation"][0])

    def test_losing_claim_gets_a_specific_alternate_cover_suggestion(self):
        first = self._claim("c1", "Pune", commitment_tier=1, requested_at=100.0)
        second = self._claim("c2", "Plant Two", commitment_tier=2, requested_at=101.0)

        drive_to_completion(self.graph, "t-alt-1", first)
        values, _ = drive_to_completion(self.graph, "t-alt-2", second)

        entry = values["log"][-1]
        suggestions = entry["alternate_suggestions"]
        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        # Not a bare rejection: a concrete lot/supplier/expedite option is named.
        self.assertIn(suggestion["type"], ("alternate_lot", "alternate_supplier", "expedite"))
        self.assertNotEqual(suggestion["lot_id"], second["lot_id"])
        self.assertEqual(suggestion["for_plant"], "Plant Two")
        self.assertIn("Plant Two", suggestion["message"])

    def test_non_colliding_claim_grants_with_no_arbitration_and_no_interrupt(self):
        claim = self._claim("c1", "Plant Three", lot_id="IMC-LOT-9999")
        values, interrupts = drive_to_completion(self.graph, "t-clear", claim)

        self.assertEqual(interrupts, 0)
        entry = values["log"][-1]
        self.assertEqual(entry["type"], "clear")
        self.assertEqual(entry["outcome"]["result"], "granted")
        self.assertNotIn("competing_claims", entry)

    def test_genuine_tie_escalates_via_interrupt_instead_of_guessing(self):
        first = self._claim("c1", "Pune", commitment_tier=2, days_of_cover=1.0, requested_at=100.0)
        second = self._claim(
            "c2", "Plant Two", commitment_tier=2, days_of_cover=1.0, requested_at=100.0
        )

        drive_to_completion(self.graph, "t-dead-1", first)
        human_response = {"winner_plant": "Pune", "decided_by": "Kavita Iyer", "note": "manual call"}
        values, interrupts = drive_to_completion(
            self.graph, "t-dead-2", second, human_response=human_response
        )

        self.assertEqual(interrupts, 1)
        entry = values["log"][-1]
        self.assertTrue(entry["escalated_to_human"])
        self.assertEqual(entry["winner"], "Pune")

    def test_three_plants_only_two_collide_third_is_untouched(self):
        pune = self._claim("c1", "Pune", lot_id="NPF-LOT-7777", commitment_tier=1, requested_at=100.0)
        plant_two = self._claim(
            "c2", "Plant Two", lot_id="NPF-LOT-7777", commitment_tier=2, requested_at=101.0
        )
        plant_three = self._claim(
            "c3", "Plant Three", lot_id="IMC-LOT-5555", commitment_tier=2, requested_at=102.0
        )

        drive_to_completion(self.graph, "t-n1", pune)
        collided_values, interrupts_a = drive_to_completion(self.graph, "t-n2", plant_two)
        untouched_values, interrupts_b = drive_to_completion(self.graph, "t-n3", plant_three)

        self.assertEqual(interrupts_a, 0)
        self.assertEqual(interrupts_b, 0)

        collided_entry = collided_values["log"][-1]
        self.assertEqual(collided_entry["type"], "arbitrated")
        self.assertEqual(collided_entry["winner"], "Pune")

        untouched_entry = untouched_values["log"][-1]
        self.assertEqual(untouched_entry["type"], "clear")
        self.assertEqual(untouched_entry["outcome"]["result"], "granted")

        # Plant Three's claim never shows up anywhere in the registry's record of
        # the Nashik lot that Pune and Plant Two actually collided over.
        nashik_lot_key = f"{SUPPLIER} / NPF-LOT-7777"
        snapshot = self.registry.snapshot()
        plants_on_nashik_lot = {h["plant"] for h in snapshot[nashik_lot_key]}
        self.assertNotIn("Plant Three", plants_on_nashik_lot)


if __name__ == "__main__":
    unittest.main()
