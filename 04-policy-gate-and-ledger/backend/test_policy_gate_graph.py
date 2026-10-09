"""
Tests for the policy gate — policy_engine.py, decision_ledger.py, and
policy_gate_graph.py.

Run with (inside the venv described in README.md):
    python3 -m unittest test_policy_gate_graph.py -v
"""
from __future__ import annotations

import unittest
from datetime import date

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from decision_ledger import DecisionLedger
from policy_engine import AutonomyTier, PolicyRegistry, ReversalTrigger, TierBoundary, TierChangeProposal
from policy_gate_graph import (
    build_graph,
    make_initial_governance_state,
    make_initial_operational_state,
    make_initial_reversal_state,
)

STORY_TODAY = date(2026, 8, 15)


def run_once(graph, config: dict, initial_state: dict, human_response: dict | None = None):
    """
    Runs one request through the graph to completion, resuming at most
    one `interrupt()` with `Command(resume=human_response)`. Returns
    (decision_id, interrupted: bool).
    """
    stream_input = initial_state
    interrupted = False
    decision_id = None

    while True:
        interrupt_payload = None
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                continue
            for node_update in chunk.values():
                if node_update and node_update.get("decision_id"):
                    decision_id = node_update["decision_id"]

        if interrupt_payload is not None:
            interrupted = True
            assert human_response is not None, "graph interrupted but no human_response was supplied"
            stream_input = Command(resume=human_response)
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return decision_id, interrupted


class OperationalFlowTests(unittest.TestCase):
    def setUp(self):
        self.registry = PolicyRegistry()
        self.ledger = DecisionLedger()
        self.graph = build_graph(self.registry, self.ledger).compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def test_within_boundary_action_auto_acts_with_no_interrupt_and_a_five_part_record(self):
        action = {
            "inputs": {"sku": "4200-series-harness", "account": "Deccan Motors",
                       "competing_orders": 1, "exposure_inr": 9_500.0},
            "model_version": "allocation-model v1.3",
            "reasoning_path": [
                {"factor": "exposure_inr", "weight": 1.0, "value": 9_500.0, "note": "under the cap"},
            ],
        }
        state = make_initial_operational_state("arjun-allocation-agent", action)
        decision_id, interrupted = run_once(self.graph, self._config("t-within"), state)

        self.assertFalse(interrupted)
        self.assertIsNotNone(decision_id)

        record = self.ledger.get(decision_id)
        self.assertEqual(record.record_type, "operational")
        self.assertEqual(record.inputs["account"], "Deccan Motors")  # part 1: inputs
        self.assertEqual(record.policy_version, "policy-v1")  # part 2: policy version
        self.assertTrue(len(record.reasoning_path) >= 1)  # part 3: reasoning path
        self.assertEqual(record.human_actions, ())  # part 4: no human action - autonomous
        self.assertEqual(record.outcome["result"], "acted")  # part 5: outcome

    def test_out_of_boundary_action_escalates_and_records_the_human_response(self):
        action = {
            "inputs": {"sku": "4200-series-harness", "account": "Continental Fasteners",
                       "competing_orders": 2, "exposure_inr": 42_000.0},
            "model_version": "allocation-model v1.3",
            "reasoning_path": [
                {"factor": "exposure_inr", "weight": 1.0, "value": 42_000.0, "note": "over the cap"},
            ],
        }
        state = make_initial_operational_state("arjun-allocation-agent", action)
        human_response = {"approved": True, "approved_by": "Aditi Kulkarni", "notes": "approved this one"}
        decision_id, interrupted = run_once(self.graph, self._config("t-escalate"), state, human_response)

        self.assertTrue(interrupted)
        record = self.ledger.get(decision_id)
        self.assertEqual(len(record.human_actions), 1)
        self.assertEqual(record.human_actions[0]["who"], "Aditi Kulkarni")
        self.assertEqual(record.outcome["result"], "acted")
        self.assertTrue(record.outcome["escalated"])


class GovernanceFlowTests(unittest.TestCase):
    def setUp(self):
        self.registry = PolicyRegistry()
        self.ledger = DecisionLedger()
        self.graph = build_graph(self.registry, self.ledger).compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _valid_proposal(self, **overrides) -> TierChangeProposal:
        defaults = dict(
            agent_id="arjun-allocation-agent",
            proposer="Arjun",
            approver="Suresh Rane",
            from_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY,
            to_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY,
            new_boundary=TierBoundary(max_competing_orders=3, max_exposure_inr=25_000.0),
            track_record_count=130,
            track_record_minimum=100,
            track_record_label="clean decisions at the original boundary",
            reversal_trigger=ReversalTrigger(
                name="widened-zone-reversal-trigger", metric="missed_commitments_count",
                comparison="gte", threshold=1, window_label="trailing 20 decisions",
            ),
            re_review_date=date(2026, 11, 15),
            rationale="widen to medium-complexity cases",
        )
        defaults.update(overrides)
        return TierChangeProposal(**defaults)

    def test_valid_proposal_with_different_proposer_and_approver_reaches_the_approver_interrupt(self):
        proposal = self._valid_proposal()
        state = make_initial_governance_state(proposal, STORY_TODAY)
        human_response = {"approved": True, "approved_by": "Suresh Rane", "notes": "approved"}
        decision_id, interrupted = run_once(self.graph, self._config("t-valid"), state, human_response)

        self.assertTrue(interrupted)  # it genuinely reached the approver
        record = self.ledger.get(decision_id)
        self.assertEqual(record.outcome["result"], "approved")
        self.assertEqual(self.registry.get("arjun-allocation-agent").policy_version, "policy-v2")
        self.assertEqual(record.human_actions[0]["who"], "Suresh Rane")

    def test_proposal_missing_reversal_trigger_is_rejected_outright_with_no_interrupt(self):
        proposal = self._valid_proposal(reversal_trigger=None)
        state = make_initial_governance_state(proposal, STORY_TODAY)
        decision_id, interrupted = run_once(self.graph, self._config("t-missing-trigger"), state, human_response=None)

        self.assertFalse(interrupted)  # the policy engine never even asked a human
        record = self.ledger.get(decision_id)
        self.assertEqual(record.outcome["result"], "rejected_by_policy_engine")
        self.assertTrue(any("reversal trigger" in reason for reason in record.outcome["reason"].split(";")))
        # the tier/boundary must be untouched
        self.assertEqual(self.registry.get("arjun-allocation-agent").policy_version, "policy-v1")

    def test_proposal_with_proposer_equal_to_approver_is_rejected_outright(self):
        proposal = self._valid_proposal(proposer="Arjun", approver="Arjun")
        state = make_initial_governance_state(proposal, STORY_TODAY)
        decision_id, interrupted = run_once(self.graph, self._config("t-same-person"), state, human_response=None)

        self.assertFalse(interrupted)
        record = self.ledger.get(decision_id)
        self.assertEqual(record.outcome["result"], "rejected_by_policy_engine")
        self.assertIn("same person", record.outcome["reason"])

    def test_proposal_missing_track_record_minimum_is_rejected_outright(self):
        proposal = self._valid_proposal(track_record_count=5, track_record_minimum=100)
        state = make_initial_governance_state(proposal, STORY_TODAY)
        decision_id, interrupted = run_once(self.graph, self._config("t-weak-record"), state, human_response=None)

        self.assertFalse(interrupted)
        record = self.ledger.get(decision_id)
        self.assertEqual(record.outcome["result"], "rejected_by_policy_engine")
        self.assertIn("track record", record.outcome["reason"])


class ReversalTriggerTests(unittest.TestCase):
    def setUp(self):
        self.registry = PolicyRegistry()
        self.ledger = DecisionLedger()
        self.graph = build_graph(self.registry, self.ledger).compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def test_reversal_trigger_firing_rolls_back_the_tier_automatically_with_no_human(self):
        # A reversal trigger rolls back to the PRIOR boundary - which only
        # exists once a widening has actually happened (the trigger is
        # defined *as part of* the widening proposal, to protect against
        # the newly widened zone). Apply that widening first, same as
        # demo.py's scenario 3 before its scenario 5.
        widen_proposal = TierChangeProposal(
            agent_id="arjun-allocation-agent", proposer="Arjun", approver="Suresh Rane",
            from_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY, to_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY,
            new_boundary=TierBoundary(max_competing_orders=3, max_exposure_inr=25_000.0),
            track_record_count=130, track_record_minimum=100, track_record_label="clean decisions",
            reversal_trigger=ReversalTrigger(
                name="widened-zone-reversal-trigger", metric="missed_commitments_count",
                comparison="gte", threshold=1, window_label="trailing 20 decisions at the widened boundary",
            ),
            re_review_date=date(2026, 11, 15), rationale="widen",
        )
        self.registry.apply_tier_change(widen_proposal, approved_by="Suresh Rane")
        self.assertEqual(self.registry.get("arjun-allocation-agent").policy_version, "policy-v2")

        recent_decisions = [
            {"missed_commitment": False, "escalated": False},
            {"missed_commitment": True, "escalated": False},  # trips the trigger
        ]
        state = make_initial_reversal_state("arjun-allocation-agent", recent_decisions)
        decision_id, interrupted = run_once(self.graph, self._config("t-reversal"), state, human_response=None)

        self.assertFalse(interrupted)
        record = self.ledger.get(decision_id)
        self.assertEqual(record.outcome["result"], "automatic_rollback")
        self.assertEqual(record.human_actions, ())  # no human sign-off involved
        self.assertEqual(self.registry.get("arjun-allocation-agent").policy_version, "policy-v3")
        self.assertEqual(self.registry.get("arjun-allocation-agent").boundary.max_competing_orders, 1)

    def test_reversal_trigger_not_firing_leaves_the_boundary_untouched(self):
        recent_decisions = [{"missed_commitment": False, "escalated": False} for _ in range(5)]
        state = make_initial_reversal_state("arjun-allocation-agent", recent_decisions)
        decision_id, interrupted = run_once(self.graph, self._config("t-no-reversal"), state, human_response=None)

        self.assertFalse(interrupted)
        self.assertIsNone(decision_id)  # no_rollback logs nothing
        self.assertEqual(self.registry.get("arjun-allocation-agent").policy_version, "policy-v1")


class LedgerVersioningTests(unittest.TestCase):
    """
    The versioning guarantee, tested directly against the ledger and
    registry: an old decision must be reconstructed under the policy
    version that was actually live when it was made, even after the
    policy has since changed multiple times.
    """

    def test_reconstructing_an_old_decision_recovers_its_original_policy_version_not_todays(self):
        registry = PolicyRegistry()
        ledger = DecisionLedger()

        arjun_v1 = registry.get("arjun-allocation-agent")
        old_decision_id = ledger.log_decision(
            agent_id=arjun_v1.agent_id,
            tier=int(arjun_v1.tier),
            record_type="operational",
            inputs={"account": "Orbit Drivetrain", "exposure_inr": 14_200.0},
            policy_version=arjun_v1.policy_version,  # "policy-v1"
            model_version="allocation-model v1.2",
            reasoning_path=[{"factor": "exposure_inr", "weight": 1.0, "value": 14_200.0, "note": "under the v1 cap"}],
            human_actions=[],
            outcome=None,
            timestamp="2026-07-05T09:00:00",
        )

        # Policy changes twice after the old decision was made.
        widen_proposal = TierChangeProposal(
            agent_id="arjun-allocation-agent", proposer="Arjun", approver="Suresh Rane",
            from_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY, to_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY,
            new_boundary=TierBoundary(max_competing_orders=3, max_exposure_inr=25_000.0),
            track_record_count=130, track_record_minimum=100, track_record_label="clean decisions",
            reversal_trigger=ReversalTrigger(name="t1", metric="missed_commitments_count", comparison="gte",
                                              threshold=1, window_label="trailing 20"),
            re_review_date=date(2026, 11, 15), rationale="widen",
        )
        registry.apply_tier_change(widen_proposal, approved_by="Suresh Rane")  # -> policy-v2

        widen_again = TierChangeProposal(
            agent_id="arjun-allocation-agent", proposer="Arjun", approver="Suresh Rane",
            from_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY, to_tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY,
            new_boundary=TierBoundary(max_competing_orders=5, max_exposure_inr=30_000.0),
            track_record_count=200, track_record_minimum=150, track_record_label="clean decisions",
            reversal_trigger=ReversalTrigger(name="t2", metric="missed_commitments_count", comparison="gte",
                                              threshold=1, window_label="trailing 20"),
            re_review_date=date(2027, 2, 1), rationale="widen again",
        )
        registry.apply_tier_change(widen_again, approved_by="Suresh Rane")  # -> policy-v3

        # Today's live policy is v3. The old decision must still show v1.
        current_version = registry.get("arjun-allocation-agent").policy_version
        self.assertEqual(current_version, "policy-v3")

        reconstructed = ledger.reconstruct(old_decision_id)
        self.assertEqual(reconstructed["policy_version"], "policy-v1")
        self.assertNotEqual(reconstructed["policy_version"], current_version)

        # And policy_engine can still resolve exactly what policy-v1 meant.
        old_snapshot = registry.snapshot_at("arjun-allocation-agent", "policy-v1")
        self.assertEqual(old_snapshot.boundary.max_exposure_inr, 25_000.0)
        self.assertEqual(old_snapshot.boundary.max_competing_orders, 1)

        current_snapshot = registry.snapshot_at("arjun-allocation-agent", current_version)
        self.assertEqual(current_snapshot.boundary.max_competing_orders, 5)  # today's wider rule
        self.assertNotEqual(old_snapshot.boundary.max_competing_orders, current_snapshot.boundary.max_competing_orders)

    def test_append_outcome_links_a_new_record_without_mutating_the_original(self):
        ledger = DecisionLedger()
        decision_id = ledger.log_decision(
            agent_id="arjun-allocation-agent", tier=2, record_type="operational",
            inputs={"x": 1}, policy_version="policy-v1", model_version="m1",
            reasoning_path=[], human_actions=[], outcome=None,
        )
        original_before = ledger.get(decision_id)
        self.assertIsNone(original_before.outcome)

        new_id = ledger.append_outcome(decision_id, {"result": "shipped"}, recorded_by="Vikram")
        self.assertNotEqual(new_id, decision_id)

        original_after = ledger.get(decision_id)
        self.assertIsNone(original_after.outcome)  # untouched

        reconstructed = ledger.reconstruct(decision_id)
        self.assertEqual(reconstructed["outcome"], {"result": "shipped"})
        self.assertEqual(reconstructed["amendment_count"], 1)


if __name__ == "__main__":
    unittest.main()
