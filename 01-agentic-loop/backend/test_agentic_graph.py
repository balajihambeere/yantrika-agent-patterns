"""
Tests for the LangGraph agent in agentic_graph.py.

Run with (inside the venv described in README.md):
    python3 -m unittest test_agentic_graph.py -v
"""
from __future__ import annotations

import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agentic_graph import build_graph, make_initial_state


def drive_to_completion(graph, config, initial_state, human_response=None):
    """
    Runs the graph to completion, auto-resuming every interrupt with
    `human_response` (default: approve). Returns (final_log, interrupt_count).
    """
    human_response = human_response or {"approved": True, "approved_by": "test-human"}
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


class AgenticGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph().compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def test_low_risk_event_resolves_without_any_interrupt(self):
        state = make_initial_state(
            sku="widget",
            opening_balance=1000,
            run_rate_per_minute=1,
            pending_events=[{"minutes_after_start": 0, "delta": -10, "note": "small routine draw"}],
        )
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-low-risk"), state)
        self.assertEqual(interrupt_count, 0)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["decision"]["action"], "no_action")

    def test_repeated_shortfall_escalates_to_a_human(self):
        state = make_initial_state(
            sku="4200-series-harness",
            opening_balance=340,
            run_rate_per_minute=4,
            pending_events=[
                {"minutes_after_start": 70, "delta": -150, "note": "Line 1 pulls an urgent order forward"},
                {"minutes_after_start": 160, "delta": -90, "note": "quality hold miscredit"},
                {"minutes_after_start": 455, "delta": -88, "note": "Line 2 starts early"},
            ],
        )
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-escalation"), state)

        self.assertEqual(len(log), 3)
        self.assertEqual(log[-1]["observation"]["balance"], 12)  # matches the expected final balance
        self.assertEqual(log[0]["decision"]["action"], "alert_floor_and_stores")
        self.assertFalse(log[0]["decision"]["requires_human"])
        self.assertEqual(log[1]["decision"]["action"], "expedite_replacement_shipment")
        self.assertTrue(log[1]["decision"]["requires_human"])
        self.assertTrue(log[1]["decision"]["approved"])
        self.assertEqual(log[1]["decision"]["approved_by"], "test-human")
        self.assertGreaterEqual(interrupt_count, 2)  # cycles 2 and 3 both need sign-off

    def test_human_can_decline_and_the_action_is_not_executed(self):
        state = make_initial_state(
            sku="widget",
            opening_balance=10,
            run_rate_per_minute=1,
            pending_events=[
                {"minutes_after_start": 0, "delta": 0, "note": "already critical at start"},
                {"minutes_after_start": 5, "delta": 0, "note": "still critical, alert already raised"},
            ],
        )
        log, _ = drive_to_completion(
            self.graph,
            self._config("t-declined"),
            state,
            human_response={"approved": False, "approved_by": "test-human"},
        )
        self.assertEqual(len(log), 2)
        self.assertEqual(log[0]["decision"]["action"], "alert_floor_and_stores")
        self.assertEqual(log[1]["decision"]["action"], "expedite_replacement_shipment")
        self.assertFalse(log[1]["decision"]["approved"])
        self.assertIn("declined", log[1]["outcome"])

    def test_empty_event_queue_produces_an_empty_log(self):
        state = make_initial_state(
            sku="widget", opening_balance=500, run_rate_per_minute=1, pending_events=[]
        )
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-empty"), state)
        self.assertEqual(log, [])
        self.assertEqual(interrupt_count, 0)


if __name__ == "__main__":
    unittest.main()
