"""
Tests for the LangGraph arbitration layer in federation_graph.py.

Run with (inside the venv described in README.md):
    python3 -m unittest test_federation_graph.py -v
"""
from __future__ import annotations

import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from federation_graph import (
    DEFAULT_CONNECTION_TIER,
    NASHIK_CONFIRMER,
    PUNE_CONFIRMER,
    TIER_ACT,
    TIER_RECOMMEND,
    build_graph,
    make_initial_state,
)
from site_agents import SitePosition, SupplierCapacity

SKU_FAMILY = "fastener_family_F12"

SUPPLIER: SupplierCapacity = {
    "supplier": "Supplier S-9",
    "sku_family": SKU_FAMILY,
    "open_capacity": 200,
}

PUNE_SURPLUS: SitePosition = {
    "site": "Pune",
    "sku_family": SKU_FAMILY,
    "on_hand": 620,
    "buffer_target": 400,
}

NASHIK_SHORT: SitePosition = {
    "site": "Nashik",
    "sku_family": SKU_FAMILY,
    "on_hand": 130,
    "buffer_target": 300,
}

NASHIK_COMFORTABLE: SitePosition = {
    "site": "Nashik",
    "sku_family": SKU_FAMILY,
    "on_hand": 310,
    "buffer_target": 300,
}


def drive_to_completion(graph, config, initial_state, confirmations=None):
    """
    Runs the graph to completion, resuming every interrupt it hits with
    the matching confirmer's response from `confirmations` (keyed by
    confirmer name; defaults to an unconditional confirm if not given).
    Returns (final_log, interrupt_count).
    """
    confirmations = confirmations or {}
    interrupt_count = 0
    stream_input = initial_state

    while True:
        interrupt_payload = None
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                interrupt_count += 1

        if interrupt_payload is not None:
            confirmer = interrupt_payload["confirmer"]
            response = confirmations.get(confirmer, {"confirmed": True, "confirmed_by": confirmer})
            stream_input = Command(resume=response)
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values.get("log", []), interrupt_count


class FederationGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph().compile(checkpointer=InMemorySaver())

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def test_default_connection_tier_is_recommend_not_act(self):
        """Most organizations should not
        grant a federation of agents the unilateral 'act' tier before the
        simpler tiers have earned trust, if ever. This federation's
        default must reflect that caution."""
        self.assertEqual(DEFAULT_CONNECTION_TIER, TIER_RECOMMEND)
        self.assertNotEqual(DEFAULT_CONNECTION_TIER, TIER_ACT)

        state = make_initial_state(
            pune_position=PUNE_SURPLUS, nashik_position=NASHIK_SHORT, supplier=SUPPLIER
        )
        self.assertEqual(state["connection_tier"], TIER_RECOMMEND)

    def test_collision_requires_both_confirmations_before_acting(self):
        """The actual near-miss scenario: Pune's surplus offer collides
        with Nashik's independent rush order on the same family. Both
        Neha and Shalini must confirm before the coordinated transfer
        executes."""
        state = make_initial_state(
            pune_position=PUNE_SURPLUS, nashik_position=NASHIK_SHORT, supplier=SUPPLIER
        )
        confirmations = {
            PUNE_CONFIRMER: {"confirmed": True, "confirmed_by": PUNE_CONFIRMER},
            NASHIK_CONFIRMER: {"confirmed": True, "confirmed_by": NASHIK_CONFIRMER},
        }
        log, interrupt_count = drive_to_completion(
            self.graph, self._config("t-collision"), state, confirmations
        )

        self.assertEqual(interrupt_count, 2)  # one interrupt per named human, on each side
        entry = log[-1]
        self.assertIsNotNone(entry["collision"])
        self.assertEqual(entry["pune_recommendation"]["action"], "offer_cross_boundary_transfer")
        self.assertEqual(entry["nashik_recommendation"]["action"], "rush_order")
        self.assertEqual(entry["decision"]["type"], "coordinated_transfer")
        self.assertTrue(entry["decision"]["coordinated"])
        self.assertTrue(entry["decision"]["rush_order_cancelled"])
        self.assertEqual(entry["decision"]["quantity"], 170)
        self.assertEqual(
            set(entry["decision"]["confirmed_by"]), {PUNE_CONFIRMER, NASHIK_CONFIRMER}
        )

    def test_only_one_confirmation_does_not_act_yet(self):
        """After Neha confirms but before Shalini has responded, the
        graph must be paused on Shalini's interrupt, with no decision
        made yet — not proceed on one signature alone."""
        config = self._config("t-partial-confirmation")
        state = make_initial_state(
            pune_position=PUNE_SURPLUS, nashik_position=NASHIK_SHORT, supplier=SUPPLIER
        )

        first_interrupt = None
        for chunk in self.graph.stream(state, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                first_interrupt = chunk["__interrupt__"][0].value
        self.assertIsNotNone(first_interrupt)
        self.assertEqual(first_interrupt["confirmer"], PUNE_CONFIRMER)

        second_interrupt = None
        for chunk in self.graph.stream(
            Command(resume={"confirmed": True, "confirmed_by": PUNE_CONFIRMER}),
            config=config,
            stream_mode="updates",
        ):
            if "__interrupt__" in chunk:
                second_interrupt = chunk["__interrupt__"][0].value
        self.assertIsNotNone(second_interrupt)
        self.assertEqual(second_interrupt["confirmer"], NASHIK_CONFIRMER)

        # Neha has confirmed; Shalini has not. The graph must still be
        # paused, with no final decision and no coordinated action taken.
        snapshot = self.graph.get_state(config)
        self.assertTrue(snapshot.next)  # graph has not reached END
        self.assertIsNotNone(snapshot.values["neha_confirmation"])
        self.assertTrue(snapshot.values["neha_confirmation"]["confirmed"])
        self.assertIsNone(snapshot.values["shalini_confirmation"])
        self.assertIsNone(snapshot.values["decision"])

    def test_neha_decline_falls_back_without_asking_shalini(self):
        """If Pune's own confirmer declines, there is nothing left to
        offer — the graph must fall back to independent handling rather
        than crash or silently do nothing."""
        state = make_initial_state(
            pune_position=PUNE_SURPLUS, nashik_position=NASHIK_SHORT, supplier=SUPPLIER
        )
        confirmations = {PUNE_CONFIRMER: {"confirmed": False, "confirmed_by": PUNE_CONFIRMER}}
        log, interrupt_count = drive_to_completion(
            self.graph, self._config("t-neha-declines"), state, confirmations
        )

        self.assertEqual(interrupt_count, 1)
        entry = log[-1]
        self.assertEqual(entry["decision"]["type"], "fallback_independent")
        self.assertFalse(entry["decision"]["coordinated"])
        self.assertEqual(entry["decision"]["declined_by"], [PUNE_CONFIRMER])
        # Nashik's own rush order recommendation is still there, untouched.
        self.assertEqual(entry["nashik_recommendation"]["action"], "rush_order")

    def test_shalini_decline_falls_back_to_independent_handling(self):
        """Neha confirms Pune's side, but Shalini declines the transfer.
        The fix must fall back to each site handling its own shortfall
        independently — visible and logged, not a silent collision and
        not a crash."""
        state = make_initial_state(
            pune_position=PUNE_SURPLUS, nashik_position=NASHIK_SHORT, supplier=SUPPLIER
        )
        confirmations = {
            PUNE_CONFIRMER: {"confirmed": True, "confirmed_by": PUNE_CONFIRMER},
            NASHIK_CONFIRMER: {"confirmed": False, "confirmed_by": NASHIK_CONFIRMER},
        }
        log, interrupt_count = drive_to_completion(
            self.graph, self._config("t-shalini-declines"), state, confirmations
        )

        self.assertEqual(interrupt_count, 2)
        entry = log[-1]
        self.assertEqual(entry["decision"]["type"], "fallback_independent")
        self.assertFalse(entry["decision"]["coordinated"])
        self.assertEqual(entry["decision"]["declined_by"], [NASHIK_CONFIRMER])
        self.assertEqual(entry["nashik_recommendation"]["action"], "rush_order")
        self.assertEqual(entry["pune_recommendation"]["action"], "offer_cross_boundary_transfer")

    def test_non_colliding_case_never_reaches_arbitration_or_an_interrupt(self):
        """Pune has surplus but Nashik is within its own buffer target
        this cycle — the two recommendations don't touch the same
        resource, so this never escalates to a human at all."""
        state = make_initial_state(
            pune_position=PUNE_SURPLUS, nashik_position=NASHIK_COMFORTABLE, supplier=SUPPLIER
        )
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-no-collision"), state)

        self.assertEqual(interrupt_count, 0)
        entry = log[-1]
        self.assertIsNone(entry["collision"])
        self.assertEqual(entry["decision"]["type"], "independent_action")
        self.assertIsNone(entry["neha_confirmation"])
        self.assertIsNone(entry["shalini_confirmation"])

    def test_observe_tier_produces_local_awareness_without_cross_boundary_recommendation(self):
        """Pune's agent genuinely looks at Nashik's position under the
        pilot connection (observe tier) but, finding no shortfall worth
        acting on, produces no cross-boundary recommendation at all —
        just local awareness, not an offer."""
        state = make_initial_state(
            pune_position=PUNE_SURPLUS,
            nashik_position=NASHIK_COMFORTABLE,
            supplier=SUPPLIER,
            observe_nashik_from_pune=True,
        )
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-observe-only"), state)

        self.assertEqual(interrupt_count, 0)
        entry = log[-1]
        self.assertEqual(entry["pune_recommendation"]["action"], "surplus_available")
        self.assertIsNone(entry["pune_recommendation"]["touches_other_site"])
        self.assertIn("Observed", entry["pune_recommendation"]["rationale"])

    def test_act_tier_would_bypass_confirmation_entirely(self):
        """Contrast case: if the connection were configured at the 'act'
        tier (which this federation's default deliberately is not), the
        same collision would resolve with no interrupt at all — a
        unilateral cross-boundary commitment with no named human on
        either side. This is the risk most
        organizations should not accept."""
        state = make_initial_state(
            pune_position=PUNE_SURPLUS,
            nashik_position=NASHIK_SHORT,
            supplier=SUPPLIER,
            connection_tier=TIER_ACT,
        )
        log, interrupt_count = drive_to_completion(self.graph, self._config("t-act-tier"), state)

        self.assertEqual(interrupt_count, 0)
        entry = log[-1]
        self.assertIsNotNone(entry["collision"])
        self.assertEqual(entry["decision"]["type"], "unilateral_cross_boundary_act")
        self.assertFalse(entry["decision"]["coordinated"])


if __name__ == "__main__":
    unittest.main()
