"""
Tests for the LangGraph agent in agent_graph.py.

Run with (inside the venv described in README.md):
    python3 -m unittest test_agent_graph.py -v
"""
from __future__ import annotations

import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent_graph import build_graph, make_initial_state


def drive_to_completion(graph, config, initial_state, approval_response=None, escalation_response=None):
    """
    Runs the graph to completion, auto-resuming every interrupt with a
    response appropriate to its kind (`action_approval` vs `escalation`).
    Returns (final_log, interrupt_count).
    """
    approval_response = approval_response or {"approved": True, "approved_by": "Neha"}
    escalation_response = escalation_response or {"acknowledged_by": "Neha", "note": "reviewed"}
    interrupt_count = 0
    stream_input = initial_state
    is_resuming = False
    pending_response = None

    while True:
        if is_resuming:
            stream_input = Command(resume=pending_response)
        hit_interrupt = False
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                hit_interrupt = True
                interrupt_count += 1
                payload = chunk["__interrupt__"][0].value
                pending_response = (
                    approval_response if payload.get("kind") == "action_approval" else escalation_response
                )

        if hit_interrupt:
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values.get("log", []), interrupt_count


class AgentGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph().compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _po(self, **overrides) -> dict:
        po = {
            "po_number": "VAC-PO-9000",
            "supplier": "Deccan Fasteners",
            "ordered_qty": 500,
            "ordered_date": "2026-10-20",
            "hours_since_po": 20,
            "inbox": [],
        }
        po.update(overrides)
        return po

    # --- Clean confirmation -------------------------------------------------

    def test_clean_confirmation_autonomous_mode_logs_without_interrupt(self):
        po = self._po(inbox=[{
            "thread_id": "VAC-PO-9000", "po_reference": "VAC-PO-9000", "supplier": "Deccan Fasteners",
            "body": "Confirming PO VAC-PO-9000 -- 500 units, delivery 2026-10-20 as ordered.",
            "attachment": None, "received_at_hours": 5,
        }])
        state = make_initial_state(po, supervised=False)
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-clean"), state)

        self.assertEqual(interrupt_count, 0)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["decision"]["action"], "log_only")
        self.assertFalse(log[0]["decision"]["requires_escalation"])

    # --- 48h no-reply chase --------------------------------------------------

    def test_48h_no_reply_sends_chase(self):
        po = self._po(supplier="Konkan Metal Works", hours_since_po=52, inbox=[])
        state = make_initial_state(po, supervised=False)
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-chase"), state)

        self.assertEqual(interrupt_count, 0)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["decision"]["action"], "send_chase")
        self.assertIn("sent standard chase template", log[0]["action_result"]["outcome"])

    # --- Ambiguous reply escalates -------------------------------------------

    def test_ambiguous_low_confidence_reply_escalates(self):
        po = self._po(supplier="Bharat Precision Forge", inbox=[{
            "thread_id": "VAC-PO-9000", "po_reference": "VAC-PO-9000", "supplier": "Bharat Precision Forge",
            "body": "Noted, will advise.", "attachment": None, "received_at_hours": 5,
        }])
        state = make_initial_state(po, supervised=False)
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-ambiguous"), state)

        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["decision"]["action"], "escalate_unclear")
        self.assertTrue(log[0]["decision"]["requires_escalation"])
        self.assertFalse(log[0]["decision"]["hard_invariant_triggered"])
        self.assertGreaterEqual(interrupt_count, 1)  # escalations always interrupt

    # --- The hard invariant: the central point --------------------------------

    def test_mismatch_above_tolerance_escalates_even_with_high_confidence(self):
        """
        A date mismatch escalates via the hard invariant *regardless* of
        how confident perceive is about the rest of the message. This is
        the central point: the hard invariant is not a probability and
        cannot be out-voted by confidence.
        """
        po = self._po(supplier="Satpura Components", inbox=[{
            "thread_id": "VAC-PO-9000", "po_reference": "VAC-PO-9000", "supplier": "Satpura Components",
            "body": (
                "Hi team, everything proceeding as usual this week. One small update -- "
                "delivery now 2026-10-26 (was 2026-10-20), 500 units as before."
            ),
            "attachment": None, "received_at_hours": 5,
        }])
        state = make_initial_state(po, supervised=False)
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-mismatch"), state)

        self.assertEqual(len(log), 1)
        entry = log[0]
        # Perceive read this confidently -- both fields were explicit text.
        self.assertGreaterEqual(entry["perception"]["confidence"], 0.7)
        # ...but it still escalates, because the hard invariant doesn't
        # consult confidence at all.
        self.assertEqual(entry["decision"]["action"], "escalate_mismatch")
        self.assertTrue(entry["decision"]["hard_invariant_triggered"])
        self.assertTrue(entry["decision"]["requires_escalation"])
        self.assertGreaterEqual(interrupt_count, 1)

    # --- Supplier exception table: scoped to exactly one supplier -----------

    def test_supplier_exception_overrides_only_for_that_supplier(self):
        dateless_reply = {
            "thread_id": "VAC-PO-9100", "po_reference": "VAC-PO-9100",
            "body": "Confirmed, will process as usual.", "attachment": None, "received_at_hours": 5,
        }

        owner_po = self._po(
            po_number="VAC-PO-9100", supplier="Bharat Precision Forge",
            inbox=[{**dateless_reply, "supplier": "Bharat Precision Forge"}],
        )
        owner_state = make_initial_state(owner_po, supervised=False)
        owner_log, _ = drive_to_completion(self.graph, self._config("t-exception-owner"), owner_state)
        self.assertEqual(owner_log[0]["decision"]["action"], "escalate_unclear")
        self.assertIn("overridden by Neha's supplier exception", owner_log[0]["perception"]["notes"])

        other_po = self._po(
            po_number="VAC-PO-9100", supplier="Girnar Components",
            inbox=[{**dateless_reply, "supplier": "Girnar Components"}],
        )
        other_state = make_initial_state(other_po, supervised=False)
        other_log, _ = drive_to_completion(self.graph, self._config("t-exception-other"), other_state)
        self.assertEqual(other_log[0]["decision"]["action"], "log_only")
        self.assertNotIn("overridden by Neha's supplier exception", other_log[0]["perception"]["notes"])

    # --- Staged autonomy: same input, different interrupt behavior ----------

    def test_supervised_mode_queues_even_a_clean_confirmation_for_approval(self):
        po = self._po(inbox=[{
            "thread_id": "VAC-PO-9000", "po_reference": "VAC-PO-9000", "supplier": "Deccan Fasteners",
            "body": "Confirming PO VAC-PO-9000 -- 500 units, delivery 2026-10-20 as ordered.",
            "attachment": None, "received_at_hours": 5,
        }])

        supervised_state = make_initial_state(po, supervised=True)
        supervised_log, supervised_interrupts = drive_to_completion(
            self.graph, self._config("t-stage-supervised"), supervised_state
        )
        self.assertEqual(supervised_interrupts, 1)  # queued for Neha's approval, even though it's clean
        self.assertEqual(supervised_log[0]["decision"]["action"], "log_only")
        self.assertEqual(supervised_log[0]["decision"]["approved_by"], "Neha")

        autonomous_state = make_initial_state(po, supervised=False)
        autonomous_log, autonomous_interrupts = drive_to_completion(
            self.graph, self._config("t-stage-autonomous"), autonomous_state
        )
        self.assertEqual(autonomous_interrupts, 0)  # earned autonomy: fires on its own
        self.assertEqual(autonomous_log[0]["decision"]["action"], "log_only")
        self.assertEqual(autonomous_log[0]["decision"]["approved_by"], "autonomous_mode")

    def test_escalation_always_interrupts_regardless_of_supervised_flag(self):
        po = self._po(supplier="Bharat Precision Forge", inbox=[{
            "thread_id": "VAC-PO-9000", "po_reference": "VAC-PO-9000", "supplier": "Bharat Precision Forge",
            "body": "Noted, will advise.", "attachment": None, "received_at_hours": 5,
        }])

        for supervised in (True, False):
            with self.subTest(supervised=supervised):
                state = make_initial_state(po, supervised=supervised)
                log, interrupt_count = drive_to_completion(
                    self.graph, self._config(f"t-escalate-always-{supervised}"), state
                )
                self.assertEqual(interrupt_count, 1)
                self.assertEqual(log[0]["decision"]["action"], "escalate_unclear")

    # --- Edge case: nothing to react to yet ----------------------------------

    def test_nothing_to_react_to_yet_produces_no_log_entry(self):
        po = self._po(hours_since_po=10, inbox=[])  # under 48h, no reply
        state = make_initial_state(po, supervised=False)
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-nothing-yet"), state)

        self.assertEqual(log, [])
        self.assertEqual(interrupt_count, 0)


if __name__ == "__main__":
    unittest.main()
