"""
The five-part decision record and append-only ledger.

Kavita's finding, boiled down: Vimana's logs recorded *outcomes*, not
reasoning. Asked to reconstruct, within twenty minutes, exactly why one
specific eleven-week-old decision went the way it did — and which policy
was actually live on that date, not today's — Arjun couldn't do either
to her satisfaction. The gap had three separate parts: reconstructability
(the reasoning chain wasn't laid out, just the inputs and the result),
versioning (the logs didn't tie a decision to the exact policy version
active when it was made), and retention (some lower-level logs rotated
out after thirty days — an inherited default, never revisited).

The fix settled on here is a five-part record, required for every
decision any agent above Tier 1 makes (Tier 1 is exempt — the audit
burden isn't worth it there):

    1. the specific inputs the agent actually consulted
    2. the exact policy AND model version in force at that moment,
       permanently tied to the record regardless of what changes after
    3. the reasoning path a person can follow — decisive factors and how
       they were weighted, not necessarily every internal calculation
    4. any human action taken in response (approvals, overrides,
       escalations), with who and when
    5. the outcome, once known, linked back to the original decision

`DecisionLedger` below is append-only: nothing already written is ever
edited. An outcome that becomes known later is appended as a NEW record
that links back to the original via `amends`, and a lightweight
stdlib-hashlib hash chain over every record appended gives a tamper-
evidence check — a "chain of custody" property (not real cryptographic
signing, the simplest honest tool that demonstrates the same property:
if anything already written changes, the chain no longer verifies).

Retention itself is a storage/ops policy, not code; it isn't modeled
here beyond the comment that nothing in this
ledger ever expires or rotates — every record and every amendment stays
exactly where it was written, for as long as the ledger exists.
"""
from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class DecisionRecord:
    """
    One immutable-by-convention entry. `reasoning_path` and
    `human_actions` are tuples of plain dicts (tuples so nothing can be
    appended/removed after the fact; the dicts inside are a convention,
    not a cryptographic guarantee — `DecisionLedger.verify_chain()` is
    the backstop that actually catches tampering with their contents).

    `amends` is None for an original record, or the decision_id of the
    record this one links onto (see `DecisionLedger.append_outcome`).
    """

    decision_id: str
    agent_id: str
    tier: int
    timestamp: str
    record_type: str  # "operational" | "governance"
    inputs: dict
    policy_version: str
    model_version: str
    reasoning_path: tuple  # tuple[dict]: {"factor","weight","value","note"}
    human_actions: tuple  # tuple[dict]: {"who","when","action","notes"}
    outcome: Optional[dict]
    amends: Optional[str]
    prev_hash: str
    record_hash: str


class DecisionLedger:
    """
    Append-only store, keyed by decision_id. `log_decision()` is the only
    way a new original record is created; `append_outcome()` is the only
    way an outcome is attached to one later — both add, never edit.
    """

    def __init__(self):
        self._records: dict[str, DecisionRecord] = {}
        self._order: list[str] = []
        self._last_hash: str = GENESIS_HASH
        self._counter = itertools.count(1)

    # -- construction -------------------------------------------------

    def _next_id(self, prefix: str = "dec") -> str:
        return f"{prefix}-{next(self._counter):06d}"

    def _payload_fields(self, record_or_payload) -> dict:
        """The canonical set of fields that go into the hash, in a stable
        order, whether called with a fresh payload dict or an existing
        DecisionRecord (used by both creation and verify_chain)."""
        get = record_or_payload.get if isinstance(record_or_payload, dict) else (
            lambda k: getattr(record_or_payload, k)
        )
        return {
            "decision_id": get("decision_id"),
            "agent_id": get("agent_id"),
            "tier": get("tier"),
            "timestamp": get("timestamp"),
            "record_type": get("record_type"),
            "inputs": get("inputs"),
            "policy_version": get("policy_version"),
            "model_version": get("model_version"),
            "reasoning_path": get("reasoning_path"),
            "human_actions": get("human_actions"),
            "outcome": get("outcome"),
            "amends": get("amends"),
        }

    def _hash_record(self, payload: dict, prev_hash: str) -> str:
        canonical = repr(sorted(payload.items(), key=lambda kv: kv[0])) + "|" + prev_hash
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def log_decision(
        self,
        *,
        agent_id: str,
        tier: int,
        record_type: str,
        inputs: dict,
        policy_version: str,
        model_version: str,
        reasoning_path: list[dict],
        human_actions: list[dict],
        outcome: Optional[dict] = None,
        timestamp: Optional[str] = None,
        amends: Optional[str] = None,
        decision_id: Optional[str] = None,
    ) -> str:
        """
        Write one new, original decision record. This is the direct
        implementation of the five-part record: `inputs` is part 1,
        `policy_version` + `model_version` together are part 2,
        `reasoning_path` is part 3, `human_actions` is part 4, and
        `outcome` (often None at write time, filled in later via
        `append_outcome`) is part 5.
        """
        decision_id = decision_id or self._next_id("dec" if record_type == "operational" else "gov")
        timestamp = timestamp or datetime.now().isoformat(timespec="seconds")
        payload = {
            "decision_id": decision_id,
            "agent_id": agent_id,
            "tier": tier,
            "timestamp": timestamp,
            "record_type": record_type,
            "inputs": dict(inputs),
            "policy_version": policy_version,
            "model_version": model_version,
            "reasoning_path": tuple(dict(step) for step in reasoning_path),
            "human_actions": tuple(dict(h) for h in human_actions),
            "outcome": dict(outcome) if outcome is not None else None,
            "amends": amends,
        }
        record_hash = self._hash_record(payload, self._last_hash)
        record = DecisionRecord(**payload, prev_hash=self._last_hash, record_hash=record_hash)
        self._records[decision_id] = record
        self._order.append(decision_id)
        self._last_hash = record_hash
        return decision_id

    def append_outcome(self, decision_id: str, outcome: dict, *, recorded_by: str, when: Optional[str] = None) -> str:
        """
        Attach a now-known outcome to a past decision WITHOUT touching the
        original record: appends a brand-new, fully independent record
        that `amends` the root decision, carrying the root's original
        inputs/policy_version/model_version/reasoning_path forward
        unchanged (what was true at decision time never gets rewritten),
        plus the new outcome and a human action noting who recorded it.
        """
        root = self._resolve_root(decision_id)
        when = when or datetime.now().isoformat(timespec="seconds")
        human_actions = [{"who": recorded_by, "when": when, "action": "recorded_outcome", "notes": ""}]
        return self.log_decision(
            agent_id=root.agent_id,
            tier=root.tier,
            record_type=root.record_type,
            inputs=root.inputs,
            policy_version=root.policy_version,
            model_version=root.model_version,
            reasoning_path=list(root.reasoning_path),
            human_actions=human_actions,
            outcome=outcome,
            timestamp=when,
            amends=root.decision_id,
        )

    # -- lookup ---------------------------------------------------------

    def records_count(self) -> int:
        return len(self._order)

    def get(self, decision_id: str) -> DecisionRecord:
        try:
            return self._records[decision_id]
        except KeyError:
            raise KeyError(f"no decision record found for id {decision_id!r}") from None

    def _resolve_root(self, decision_id: str) -> DecisionRecord:
        record = self.get(decision_id)
        while record.amends is not None:
            record = self.get(record.amends)
        return record

    def reconstruct(self, decision_id: str) -> dict:
        """
        The direct lookup for "walk me through exactly why." Resolves
        `decision_id` to its root record
        (works whether you hand it the original id or a later amendment's
        id), then folds in every amendment chained onto that root, in
        append order — human actions accumulate, the latest outcome wins
        — while inputs / policy_version / model_version / reasoning_path
        stay pinned to the ORIGINAL record. Those four are never
        re-evaluated against today's rules; they are what was true at the
        moment the decision was made, permanently.
        """
        root = self._resolve_root(decision_id)
        chain = [self._records[rid] for rid in self._order if self._records[rid].decision_id == root.decision_id or self._records[rid].amends == root.decision_id]

        human_actions: list[dict] = []
        outcome = root.outcome
        for rec in chain:
            human_actions.extend(dict(h) for h in rec.human_actions)
            if rec.outcome is not None:
                outcome = dict(rec.outcome)

        return {
            "decision_id": root.decision_id,
            "agent_id": root.agent_id,
            "tier": root.tier,
            "timestamp": root.timestamp,
            "record_type": root.record_type,
            "inputs": dict(root.inputs),
            "policy_version": root.policy_version,
            "model_version": root.model_version,
            "reasoning_path": [dict(s) for s in root.reasoning_path],
            "human_actions": human_actions,
            "outcome": outcome,
            "amendment_count": len(chain) - 1,
        }

    def print_full_record(self, decision_id: str) -> None:
        """Prints the reconstructed five-part record. This is the entire
        answer to Kavita's "walk me through exactly why" test — one
        lookup, not twenty minutes cross-referencing three logs and a
        change-history document."""
        full = self.reconstruct(decision_id)
        print(f"Decision {full['decision_id']}  |  agent={full['agent_id']}  |  tier={full['tier']}  |  type={full['record_type']}")
        print(f"Decided at: {full['timestamp']}")
        print(f"Policy version in force at that moment:  {full['policy_version']}")
        print(f"Model version in force at that moment:   {full['model_version']}")

        print("\n1. INPUTS actually consulted:")
        for k, v in full["inputs"].items():
            print(f"   - {k}: {v}")

        print("\n2. POLICY/MODEL VERSION:")
        print(f"   policy_version={full['policy_version']}  model_version={full['model_version']}")
        print("   (tied permanently to this record - see policy_engine.PolicyRegistry.snapshot_at()")
        print("    to resolve exactly what that version meant, even if it has since changed)")

        print("\n3. REASONING PATH (decisive factors and how they were weighted):")
        if not full["reasoning_path"]:
            print("   (no scored factors recorded for this decision)")
        for step in full["reasoning_path"]:
            print(f"   - {step['factor']}: weight={step['weight']}  value={step['value']} -- {step['note']}")

        print("\n4. HUMAN ACTIONS:")
        if not full["human_actions"]:
            print("   (none - this decision was acted on autonomously)")
        for h in full["human_actions"]:
            print(f"   - {h['when']}  {h['who']}  {h['action']}  {h.get('notes', '')}".rstrip())

        print("\n5. OUTCOME:")
        print(f"   {full['outcome'] if full['outcome'] is not None else '(not yet known)'}")
        if full["amendment_count"]:
            print(f"\n   ({full['amendment_count']} linked amendment(s) folded in above - original record untouched)")

    # -- chain of custody ------------------------------------------------

    def verify_chain(self) -> tuple[bool, Optional[str]]:
        """
        Recomputes the hash chain over every record in append order and
        confirms nothing has been altered since it was written. Returns
        (intact, first_broken_decision_id). This is the tamper-evidence
        half of "chain of custody" - not a replacement for
        real write-once storage or access logging, but the same property,
        demonstrated with the simplest honest tool: if the content a hash
        was computed over changes, the stored hash stops matching.
        """
        prev = GENESIS_HASH
        for decision_id in self._order:
            record = self._records[decision_id]
            payload = self._payload_fields(record)
            expected_hash = self._hash_record(payload, prev)
            if record.prev_hash != prev or record.record_hash != expected_hash:
                return False, decision_id
            prev = record.record_hash
        return True, None
