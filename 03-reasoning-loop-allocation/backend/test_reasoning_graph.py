"""
Tests for the LangGraph reasoning loop in reasoning_graph.py.

Run with (inside the venv described in README.md):
    python3 -m unittest test_reasoning_graph.py -v
"""
from __future__ import annotations

import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from reasoning_graph import SensingCycle, build_graph, make_initial_state


def drive_to_completion(graph, config, initial_state, human_response=None):
    """
    Runs the graph to completion against a bounded pending_cycles queue,
    auto-resuming every interrupt with `human_response` (default:
    approve). Returns (final_log, interrupt_count).
    """
    human_response = human_response or {"decision": "approve", "decided_by": "test-human"}
    interrupt_count = 0
    stream_input = initial_state
    is_resuming = False

    while True:
        if is_resuming:
            stream_input = Command(resume=human_response)
        hit_interrupt = False
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                hit_interrupt = True
                interrupt_count += 1

        if hit_interrupt:
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values.get("log", []), interrupt_count


def one_cycle(label: str, available_units: int, orders: list[dict]) -> SensingCycle:
    return SensingCycle(label=label, available_units=available_units, orders=orders)


def order(account, requested, contract, downstream, strategic, confidence, expedite, note=""):
    return dict(
        account=account,
        requested_units=requested,
        contract_penalty_inr=contract,
        downstream_impact_inr=downstream,
        strategic_score=strategic,
        replenishment_confidence=confidence,
        expedite_cost_inr=expedite,
        note=note,
    )


class ReasoningGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph().compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def test_clear_agreement_low_exposure_allocates_autonomously(self):
        """Factors clearly agree AND exposure on the losing side is under
        threshold -> the system acts alone, no interrupt at all."""
        cycle = one_cycle(
            "low-stakes",
            35,
            [
                order("Deccan Motors", 30, 40_000, 15_000, 0.5, 0.6, 10_000, "steady repeat order"),
                order("Satpura Components", 10, 0, 2_000, -0.5, 0.9, 1_000, "small trial account"),
            ],
        )
        state = make_initial_state(sku="4200-series-harness", pending_cycles=[cycle])
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-autonomous"), state)

        self.assertEqual(interrupt_count, 0)
        self.assertEqual(len(log), 1)
        entry = log[0]
        self.assertFalse(entry["requires_human"])
        self.assertTrue(entry["clear_agreement"])
        self.assertLess(entry["exposure_on_losing_side"], 25_000)
        self.assertTrue(entry["decision"]["autonomous"])
        self.assertEqual(entry["decision"]["allocation"]["Deccan Motors"]["allocated_units"], 30)

    def test_close_call_escalates_even_with_zero_exposure(self):
        """Two near-identical competing orders, fully coverable (zero
        exposure either way) -> must still escalate, because the factors
        don't clearly agree. Exposure alone isn't the only gate."""
        cycle = one_cycle(
            "close-call",
            100,
            [
                order("Account A", 50, 60_000, 40_000, 0.6, 0.5, 20_000, "looks marginally stronger"),
                order("Account B", 50, 58_000, 38_000, 0.5, 0.5, 19_000, "almost identical numbers"),
            ],
        )
        state = make_initial_state(sku="4200-series-harness", pending_cycles=[cycle])
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-close-call"), state)

        self.assertEqual(interrupt_count, 1)
        entry = log[0]
        self.assertTrue(entry["requires_human"])
        self.assertFalse(entry["clear_agreement"])
        self.assertEqual(entry["exposure_on_losing_side"], 0)  # both orders fully fit — no one loses units
        self.assertIn("close call", entry["escalation_reason"])

    def test_high_exposure_escalates_even_when_factors_clearly_agree(self):
        """A wide, unambiguous gap between the two orders' weighted scores
        (clear agreement) but a large rupee exposure on the losing side ->
        exposure alone must force escalation."""
        cycle = one_cycle(
            "high-exposure",
            200,
            [
                order("BigWinner", 200, 180_000, 20_000, 1.0, 0.3, 20_000, "clear winner on every factor"),
                order("BigLoser", 100, 60_000, 80_000, -1.0, 0.5, 5_000, "big downstream exposure, held entirely"),
            ],
        )
        state = make_initial_state(sku="4200-series-harness", pending_cycles=[cycle])
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-high-exposure"), state)

        self.assertEqual(interrupt_count, 1)
        entry = log[0]
        self.assertTrue(entry["clear_agreement"])  # the factors DO agree...
        self.assertGreater(entry["exposure_on_losing_side"], 25_000)  # ...but exposure forces escalation anyway
        self.assertTrue(entry["requires_human"])
        self.assertIn("exposure", entry["escalation_reason"])

    def test_escalated_log_entry_records_actual_factor_scores_not_just_the_allocation(self):
        """The log must carry the actual
        weights/scores used, not only the final outcome, so the reasoning
        itself is auditable later."""
        cycle = one_cycle(
            "high-exposure-for-log-check",
            200,
            [
                order("BigWinner", 200, 180_000, 20_000, 1.0, 0.3, 20_000, "clear winner"),
                order("BigLoser", 100, 60_000, 80_000, -1.0, 0.5, 5_000, "held entirely"),
            ],
        )
        state = make_initial_state(sku="4200-series-harness", pending_cycles=[cycle])
        log, _ = drive_to_completion(self.graph, self._config("t-log-detail"), state)

        entry = log[0]
        self.assertIn("reasoning", entry)
        self.assertEqual(len(entry["reasoning"]), 2)
        for scores in entry["reasoning"]:
            self.assertIn("factor_points", scores)
            self.assertIn("factor_percentiles", scores)
            self.assertIn("weighted_total", scores)
            self.assertEqual(
                set(scores["factor_points"].keys()),
                {
                    "contract_penalty",
                    "downstream_impact",
                    "strategic_trajectory",
                    "replenishment_confidence",
                    "cost_to_close_gap",
                },
            )
            self.assertEqual(len(scores["rationale"]), 5)
        # Not just the outcome — the recommended allocation is logged too, separately
        # from whatever the human ultimately decided.
        self.assertIn("recommended_allocation", entry)

    def test_human_override_diverges_from_the_recommendation_and_is_logged(self):
        """Mirrors Arjun's divergence: the system flags a contracted
        account as urgent, but a human knows something the model's five
        inputs can't see (a plant mid-shutdown) and overrides it. The log
        must keep both the system's original recommendation and the
        human's final, different call."""
        cycle = one_cycle(
            "divergence",
            200,
            [
                order("Konkan Precision", 200, 150_000, 50_000, 0.8, 0.4, 60_000, "flagged urgent by the weights"),
                order("Orbit Drivetrain", 150, 20_000, 90_000, 1.2, 0.5, 15_000, "plant shutdown not visible to the model"),
            ],
        )
        state = make_initial_state(sku="4200-series-harness", pending_cycles=[cycle])
        override_response = {
            "decision": "override",
            "decided_by": "Arjun",
            "allocation": {"Konkan Precision": 50, "Orbit Drivetrain": 150},
            "reason": "Konkan's plant is mid-shutdown for maintenance and won't consume this shipment for a week.",
        }
        log, interrupt_count = drive_to_completion(
            self.graph, self._config("t-override"), state, human_response=override_response
        )

        self.assertEqual(interrupt_count, 1)
        entry = log[0]
        self.assertTrue(entry["requires_human"])

        recommended = entry["recommended_allocation"]
        final = entry["decision"]["allocation"]
        # The system's own recommendation protected Konkan Precision in full.
        self.assertEqual(recommended["Konkan Precision"]["allocated_units"], 200)
        self.assertEqual(recommended["Orbit Drivetrain"]["allocated_units"], 0)
        # The human's final call diverges from it.
        self.assertEqual(final["Konkan Precision"], 50)
        self.assertEqual(final["Orbit Drivetrain"], 150)
        self.assertNotEqual(final["Konkan Precision"], recommended["Konkan Precision"]["allocated_units"])

        self.assertTrue(entry["decision"]["overridden"])
        self.assertEqual(entry["decision"]["decided_by"], "Arjun")
        self.assertIn("shutdown", entry["decision"]["override_reason"])

    def test_empty_cycle_queue_produces_an_empty_log(self):
        state = make_initial_state(sku="4200-series-harness", pending_cycles=[])
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-empty"), state)
        self.assertEqual(log, [])
        self.assertEqual(interrupt_count, 0)


if __name__ == "__main__":
    unittest.main()
