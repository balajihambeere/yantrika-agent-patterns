"""
The autonomy-tier registry and policy-as-code validator.

Every agent at Vimana sits in one of four autonomy tiers, defined by
the reversibility and blast radius of what it's allowed to do alone,
not by how sophisticated its model is.

    Tier 1 — fully autonomous, low-stakes, easily reversible
             (Neha's procurement follow-ups)
    Tier 2 — autonomous inside an explicit, bounded zone, with mandatory
             escalation outside it (Arjun's allocation agent)
    Tier 3 — recommend-only; a human must act before anything happens
             (the buffer and supplier-risk models)
    Tier 4 — no autonomy at all; pure human judgment, as a matter of
             policy rather than capability (Ganesh's quality-hold calls)

Moving an agent up a tier, or widening its boundary within Tier 2,
requires the same four things every time, per Kavita's draft policy:

    1. a minimum track record at the current boundary, stated as a
       number, not an impression;
    2. a named proposer and a named approver who are NOT the same
       person;
    3. an explicit, predefined reversal trigger — a specific named
       condition that automatically rolls the tier back if it fires,
       decided in advance, never improvised during an incident; and
    4. a scheduled re-review date, not an open-ended "we'll keep an
       eye on it."

`validate_tier_change_proposal()` below is exactly that policy-as-code:
a proposal missing any one of the four is rejected deterministically,
by code, before any human ever sees it — not a prose policy a reviewer
might interpret loosely under deadline pressure.

Everything here is plain, deterministic Python. No LLM, no model
judgment call — the whole point of policy-as-code is that the rule is
checkable by a machine, the same way a compiler enforces a type system
rather than asking a reviewer to eyeball it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime
from enum import IntEnum
from typing import Optional


class AutonomyTier(IntEnum):
    """
    The four autonomy tiers. Lower number = more autonomy: Tier 1 is the
    most autonomous tier that exists; Tier 4 is no autonomy at all. "Up
    a tier" means toward Tier 1, i.e. toward more autonomy — the
    numbering runs the other way, so tier changes in this module are
    always compared as "does the new tier/boundary carry more autonomy,"
    never assumed from the raw integer direction alone.
    """

    TIER_1_FULL_AUTONOMY = 1
    TIER_2_BOUNDED_AUTONOMY = 2
    TIER_3_RECOMMEND_ONLY = 3
    TIER_4_NO_AUTONOMY = 4


TIER_LABELS: dict[AutonomyTier, str] = {
    AutonomyTier.TIER_1_FULL_AUTONOMY: "Tier 1 - fully autonomous",
    AutonomyTier.TIER_2_BOUNDED_AUTONOMY: "Tier 2 - bounded autonomy",
    AutonomyTier.TIER_3_RECOMMEND_ONLY: "Tier 3 - recommend-only",
    AutonomyTier.TIER_4_NO_AUTONOMY: "Tier 4 - no autonomy",
}


def is_widening(from_tier: AutonomyTier, to_tier: AutonomyTier) -> bool:
    """True if `to_tier` carries strictly more autonomy than `from_tier`."""
    return int(to_tier) < int(from_tier)


@dataclass(frozen=True)
class ReversalTrigger:
    """
    A specific, named, checkable condition that automatically rolls an
    agent's tier/boundary back to its prior, safer state if met.

    The key point: this has to be decided in advance, in writing, as
    part of the widening proposal itself — never improvised during the
    stress of an actual incident, when the people involved are the
    least objective they'll ever be about their own system.
    """

    name: str
    metric: str  # e.g. "missed_commitments_count", "escalation_rate_pct"
    comparison: str  # "gt" | "gte"
    threshold: float
    window_label: str  # e.g. "trailing 20 decisions at the widened boundary"

    def describe(self) -> str:
        cmp_word = {"gt": "exceeds", "gte": "reaches or exceeds"}[self.comparison]
        return (
            f"'{self.name}': automatically rolls back if {self.metric} {cmp_word} "
            f"{self.threshold} over the {self.window_label}."
        )

    def fired(self, observed_value: float) -> bool:
        if self.comparison == "gt":
            return observed_value > self.threshold
        if self.comparison == "gte":
            return observed_value >= self.threshold
        raise ValueError(f"unknown comparison {self.comparison!r}")


@dataclass(frozen=True)
class TierBoundary:
    """
    What "in bounds" means for an agent at its current tier/widening —
    the thing `policy_gate_graph.check_boundary()` checks every proposed
    operational action against before letting it auto-act.

    `always_within` models Tier 1 (nothing to bound — fully autonomous).
    `never_within` models Tier 3/4 (every action requires a human, by
    policy, regardless of inputs). Tier 2 uses the numeric limits.
    """

    max_competing_orders: Optional[int] = None
    max_exposure_inr: Optional[float] = None
    always_within: bool = False
    never_within: bool = False
    notes: str = ""

    def covers(self, action_inputs: dict) -> tuple[bool, str]:
        if self.always_within:
            return True, "tier grants full autonomy - no boundary constraints apply"
        if self.never_within:
            return False, "tier grants no autonomy - every action requires a human, by policy"

        if self.max_competing_orders is not None:
            n = action_inputs.get("competing_orders", 1)
            if n > self.max_competing_orders:
                return False, (
                    f"{n} competing order(s) exceeds the boundary's max of "
                    f"{self.max_competing_orders}"
                )
        if self.max_exposure_inr is not None:
            exposure = action_inputs.get("exposure_inr", 0.0)
            if exposure > self.max_exposure_inr:
                return False, (
                    f"exposure Rs.{exposure:,.0f} exceeds the boundary's max of "
                    f"Rs.{self.max_exposure_inr:,.0f}"
                )
        return True, "within boundary on every declared dimension"

    def describe(self) -> str:
        if self.always_within:
            return "no constraints (Tier 1)"
        if self.never_within:
            return "no autonomy - always escalates (Tier 3/4)"
        parts = []
        if self.max_competing_orders is not None:
            parts.append(f"<= {self.max_competing_orders} competing order(s)")
        if self.max_exposure_inr is not None:
            parts.append(f"exposure <= Rs.{self.max_exposure_inr:,.0f}")
        return ", ".join(parts) if parts else (self.notes or "undeclared")


@dataclass
class AgentTierState:
    """The live, current tier assignment for one agent. Mutated only by
    PolicyRegistry.apply_tier_change() / .rollback() — never edited
    directly, so every change is forced through policy-as-code."""

    agent_id: str
    display_name: str
    tier: AutonomyTier
    boundary: TierBoundary
    escalation_contact: str  # named human operational escalations go to
    policy_version: str  # the version id currently governing this agent
    reversal_trigger: Optional[ReversalTrigger]
    re_review_date: Optional[date]
    track_record_count: int = 0
    track_record_label: str = "clean decisions at current boundary"


def default_registry_state() -> dict[str, AgentTierState]:
    """Vimana's agent roster, at the moment before Arjun's widening
    proposal is evaluated."""
    return {
        "neha-procurement-agent": AgentTierState(
            agent_id="neha-procurement-agent",
            display_name="Neha's procurement follow-up agent",
            tier=AutonomyTier.TIER_1_FULL_AUTONOMY,
            boundary=TierBoundary(
                always_within=True,
                notes="Low-stakes, easily reversible PO follow-ups.",
            ),
            escalation_contact="Neha Rao",
            policy_version="policy-v1",
            reversal_trigger=None,
            re_review_date=None,
            track_record_count=0,
            track_record_label="n/a - Tier 1 is exempt from the audit standard",
        ),
        "arjun-allocation-agent": AgentTierState(
            agent_id="arjun-allocation-agent",
            display_name="Arjun's allocation agent",
            tier=AutonomyTier.TIER_2_BOUNDED_AUTONOMY,
            boundary=TierBoundary(
                max_competing_orders=1,
                max_exposure_inr=25_000.0,
                notes="single-claim shortfalls only, exposure under Rs.25,000",
            ),
            escalation_contact="Aditi Kulkarni",
            policy_version="policy-v1",
            reversal_trigger=ReversalTrigger(
                name="original-boundary-reversal-trigger",
                metric="missed_commitments_count",
                comparison="gte",
                threshold=1,
                window_label="trailing 20 decisions at the original boundary",
            ),
            re_review_date=date(2026, 1, 15),
            track_record_count=130,
            track_record_label="clean decisions at the original boundary (4 months, no missed commitments)",
        ),
        "ganesh-quality-hold": AgentTierState(
            agent_id="ganesh-quality-hold",
            display_name="Ganesh's quality-hold judgment",
            tier=AutonomyTier.TIER_4_NO_AUTONOMY,
            boundary=TierBoundary(
                never_within=True,
                notes="No autonomy - pure human judgment, by policy, not capability.",
            ),
            escalation_contact="Ganesh Patil",
            policy_version="policy-v1",
            reversal_trigger=None,
            re_review_date=None,
            track_record_count=0,
            track_record_label="n/a - Tier 4 has no autonomy to track",
        ),
    }


@dataclass(frozen=True)
class PolicyVersionSnapshot:
    """A frozen, timestamped copy of one agent's tier/boundary at the
    moment a version became effective — the versioning guarantee in
    concrete form: an old decision's `policy_version` string can always
    be resolved back to exactly this, regardless of what the agent's
    *current* state has since become."""

    version_id: str
    effective_from: str
    agent_id: str
    tier: AutonomyTier
    boundary: TierBoundary
    reversal_trigger: Optional[ReversalTrigger]
    re_review_date: Optional[date]
    changed_by: str
    reason: str


@dataclass
class TierChangeProposal:
    """One tier-change / boundary-widening request, carrying everything
    `validate_tier_change_proposal()` needs to check. A proposal is just
    data — building one makes no change by itself; only a validated,
    signed-off proposal run through `PolicyRegistry.apply_tier_change()`
    does."""

    agent_id: str
    proposer: str
    approver: str
    from_tier: AutonomyTier
    to_tier: AutonomyTier
    new_boundary: TierBoundary
    track_record_count: Optional[int]
    track_record_minimum: Optional[int]
    track_record_label: str
    reversal_trigger: Optional[ReversalTrigger]
    re_review_date: Optional[date]
    rationale: str = ""


def _boundary_to_dict(boundary: TierBoundary) -> dict:
    return {
        "max_competing_orders": boundary.max_competing_orders,
        "max_exposure_inr": boundary.max_exposure_inr,
        "always_within": boundary.always_within,
        "never_within": boundary.never_within,
        "notes": boundary.notes,
    }


def _boundary_from_dict(d: dict) -> TierBoundary:
    return TierBoundary(**d)


def _trigger_to_dict(trigger: Optional[ReversalTrigger]) -> Optional[dict]:
    if trigger is None:
        return None
    return {
        "name": trigger.name,
        "metric": trigger.metric,
        "comparison": trigger.comparison,
        "threshold": trigger.threshold,
        "window_label": trigger.window_label,
    }


def _trigger_from_dict(d: Optional[dict]) -> Optional[ReversalTrigger]:
    return ReversalTrigger(**d) if d else None


def serialize_proposal(proposal: TierChangeProposal) -> dict:
    """
    A round-trip-safe, plain-dict rendering of a proposal — msgpack/JSON
    friendly (plain str/int/float/bool/dict/list only, no enums, no
    dataclasses, no `date` objects), for storing in LangGraph graph state
    so the checkpointer never has to serialize a custom Python type.
    See `deserialize_proposal` for the inverse.
    """
    return {
        "agent_id": proposal.agent_id,
        "proposer": proposal.proposer,
        "approver": proposal.approver,
        "from_tier": int(proposal.from_tier),
        "to_tier": int(proposal.to_tier),
        "new_boundary": _boundary_to_dict(proposal.new_boundary),
        "track_record_count": proposal.track_record_count,
        "track_record_minimum": proposal.track_record_minimum,
        "track_record_label": proposal.track_record_label,
        "reversal_trigger": _trigger_to_dict(proposal.reversal_trigger),
        "re_review_date": proposal.re_review_date.isoformat() if proposal.re_review_date else None,
        "rationale": proposal.rationale,
    }


def deserialize_proposal(d: dict) -> TierChangeProposal:
    """Inverse of `serialize_proposal` — rebuilds the real dataclass (with
    its enums, nested dataclasses, and `date`) that `policy_engine`'s own
    functions expect to operate on."""
    return TierChangeProposal(
        agent_id=d["agent_id"],
        proposer=d["proposer"],
        approver=d["approver"],
        from_tier=AutonomyTier(d["from_tier"]),
        to_tier=AutonomyTier(d["to_tier"]),
        new_boundary=_boundary_from_dict(d["new_boundary"]),
        track_record_count=d["track_record_count"],
        track_record_minimum=d["track_record_minimum"],
        track_record_label=d["track_record_label"],
        reversal_trigger=_trigger_from_dict(d["reversal_trigger"]),
        re_review_date=date.fromisoformat(d["re_review_date"]) if d["re_review_date"] else None,
        rationale=d["rationale"],
    )


def proposal_to_dict(proposal: TierChangeProposal) -> dict:
    """A clean, JSON-friendly rendering of a proposal for the decision
    ledger's `inputs` field - enum/date objects flattened to primitives."""
    d = asdict(proposal)
    d["from_tier"] = int(proposal.from_tier)
    d["to_tier"] = int(proposal.to_tier)
    d["re_review_date"] = proposal.re_review_date.isoformat() if proposal.re_review_date else None
    if proposal.reversal_trigger is not None:
        d["reversal_trigger"] = proposal.reversal_trigger.describe()
    d["new_boundary"] = proposal.new_boundary.describe()
    return d


@dataclass(frozen=True)
class ValidationResult:
    approved: bool
    failed_conditions: list[str]
    checked_conditions: list[str]


def validate_tier_change_proposal(proposal: TierChangeProposal, *, today: date) -> ValidationResult:
    """
    The policy-as-code gate: a deterministic check of all four required
    conditions. Any one missing or unsatisfied rejects the proposal
    outright, with a specific named reason, before it is ever routed to
    a human approver. `today` must be supplied explicitly by the caller
    (the story's "today," not the wall clock) so this stays reproducible
    regardless of when the code is actually run.
    """
    failed: list[str] = []
    checked: list[str] = [
        "minimum_track_record_at_current_boundary",
        "named_proposer_and_approver_are_different_people",
        "explicit_predefined_reversal_trigger",
        "scheduled_re_review_date",
    ]

    # Condition 1 - a minimum track record, stated as a number.
    if proposal.track_record_minimum is None or proposal.track_record_count is None:
        failed.append(
            "condition 1 (minimum track record) missing: both a numeric minimum "
            "and a numeric current count must be stated - an impression is not a number"
        )
    elif proposal.track_record_count < proposal.track_record_minimum:
        failed.append(
            f"condition 1 (minimum track record) not met: {proposal.track_record_count} "
            f"{proposal.track_record_label} is below the required minimum of "
            f"{proposal.track_record_minimum}"
        )

    # Condition 2 - a named proposer and a named approver, not the same person.
    if not proposal.proposer or not proposal.approver:
        failed.append("condition 2 (named proposer/approver) missing: both must be named")
    elif proposal.proposer.strip().casefold() == proposal.approver.strip().casefold():
        failed.append(
            f"condition 2 (named proposer/approver) failed: proposer and approver are "
            f"the same person ({proposal.proposer}) - structurally not allowed, by design, "
            f"regardless of how good that person's judgment is"
        )

    # Condition 3 - an explicit, predefined reversal trigger.
    if proposal.reversal_trigger is None:
        failed.append(
            "condition 3 (reversal trigger) missing: no predefined, named rollback "
            "condition was supplied - 'we'll keep an eye on it' does not qualify"
        )

    # Condition 4 - a scheduled re-review date, not open-ended.
    if proposal.re_review_date is None:
        failed.append("condition 4 (re-review date) missing: no scheduled re-review date was supplied")
    elif proposal.re_review_date <= today:
        failed.append(
            f"condition 4 (re-review date) invalid: {proposal.re_review_date.isoformat()} is "
            f"not in the future relative to {today.isoformat()}"
        )

    return ValidationResult(approved=not failed, failed_conditions=failed, checked_conditions=checked)


def evaluate_reversal_trigger(trigger: Optional[ReversalTrigger], recent_decisions: list[dict]) -> dict:
    """
    Evaluate whether `trigger`'s predefined condition has fired against a
    window of recent operational decision outcomes. Each entry in
    `recent_decisions` is a plain dict such as
    `{"missed_commitment": bool, "escalated": bool, ...}`, typically
    pulled straight from decision-ledger `outcome` fields by the caller.

    No human judgment involved anywhere in this function - that is the
    entire point: the trigger was decided in advance, so checking it is
    pure arithmetic against a pre-agreed threshold, never a fresh call
    made under the pressure of an actual incident.
    """
    if trigger is None:
        return {"fired": False, "observed_value": None, "explanation": "no reversal trigger is defined for this agent"}

    if trigger.metric == "missed_commitments_count":
        observed = float(sum(1 for d in recent_decisions if d.get("missed_commitment")))
    elif trigger.metric == "escalation_rate_pct":
        total = len(recent_decisions) or 1
        escalations = sum(1 for d in recent_decisions if d.get("escalated"))
        observed = round(escalations / total * 100.0, 1)
    else:
        raise ValueError(f"unknown reversal-trigger metric {trigger.metric!r}")

    fired = trigger.fired(observed)
    explanation = (
        f"{trigger.metric}={observed} over the {trigger.window_label}; trigger fires when "
        f"{trigger.comparison} {trigger.threshold} -> {'FIRED' if fired else 'not fired'}"
    )
    return {"fired": fired, "observed_value": observed, "explanation": explanation}


class PolicyRegistry:
    """
    The single source of truth for every agent's current tier/boundary,
    plus the full version history behind it - the policy-enforcement
    half of the policy gate every agent decision crosses, scoped here
    to tier assignment and version history.

    `apply_tier_change()` is the only way a tier/boundary changes, and it
    is only ever called after `validate_tier_change_proposal()` has
    passed AND a named approver has signed off via `policy_gate_graph`'s
    `interrupt()`. `rollback()` is the only way a tier/boundary reverts,
    and it needs no human call at all - matching the reversal trigger
    being "decided in advance."
    """

    def __init__(self, agents: Optional[dict[str, AgentTierState]] = None):
        self._agents: dict[str, AgentTierState] = agents or default_registry_state()
        self._history: dict[str, list[PolicyVersionSnapshot]] = {}
        self._version_counter: dict[str, int] = {}
        for agent_id, state in self._agents.items():
            self._version_counter[agent_id] = 1
            self._history[agent_id] = [
                self._snapshot_of(state, changed_by="initial policy seed", reason="initial boundary at system bring-up")
            ]

    def get(self, agent_id: str) -> AgentTierState:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise KeyError(f"no agent registered under id {agent_id!r}") from None

    def all_agents(self) -> list[AgentTierState]:
        return list(self._agents.values())

    def _snapshot_of(self, state: AgentTierState, *, changed_by: str, reason: str) -> PolicyVersionSnapshot:
        return PolicyVersionSnapshot(
            version_id=state.policy_version,
            effective_from=datetime.now().isoformat(timespec="seconds"),
            agent_id=state.agent_id,
            tier=state.tier,
            boundary=state.boundary,
            reversal_trigger=state.reversal_trigger,
            re_review_date=state.re_review_date,
            changed_by=changed_by,
            reason=reason,
        )

    def _bump_version(self, agent_id: str) -> str:
        self._version_counter[agent_id] += 1
        return f"policy-v{self._version_counter[agent_id]}"

    def apply_tier_change(self, proposal: TierChangeProposal, *, approved_by: str) -> AgentTierState:
        """Apply a validated, signed-off proposal. The track record counter
        resets to 0 at the new boundary - condition 1 is explicitly a
        track record "at the current boundary," and this is a new one."""
        new_version = self._bump_version(proposal.agent_id)
        current = self._agents[proposal.agent_id]
        new_state = replace(
            current,
            tier=proposal.to_tier,
            boundary=proposal.new_boundary,
            policy_version=new_version,
            reversal_trigger=proposal.reversal_trigger,
            re_review_date=proposal.re_review_date,
            track_record_count=0,
            track_record_label="clean decisions at the newly widened boundary",
        )
        self._agents[proposal.agent_id] = new_state
        self._history[proposal.agent_id].append(
            self._snapshot_of(
                new_state,
                changed_by=f"proposed by {proposal.proposer}, approved by {approved_by}",
                reason=proposal.rationale,
            )
        )
        return new_state

    def rollback(self, agent_id: str) -> AgentTierState:
        """Automatic rollback to the prior boundary snapshot. No human
        sign-off - this is the reversal trigger actually firing, not a
        new decision being made under pressure."""
        history = self._history[agent_id]
        if len(history) < 2:
            raise ValueError(f"no prior boundary recorded for {agent_id!r} to roll back to")
        prior = history[-2]
        new_version = self._bump_version(agent_id)
        current = self._agents[agent_id]
        rolled_back = replace(
            current,
            tier=prior.tier,
            boundary=prior.boundary,
            policy_version=new_version,
            reversal_trigger=prior.reversal_trigger,
            re_review_date=prior.re_review_date,
        )
        self._agents[agent_id] = rolled_back
        self._history[agent_id].append(
            self._snapshot_of(
                rolled_back,
                changed_by="automatic reversal trigger (no human sign-off)",
                reason=f"rolled back to the boundary recorded under {prior.version_id}",
            )
        )
        return rolled_back

    def snapshot_at(self, agent_id: str, version_id: str) -> PolicyVersionSnapshot:
        for snap in self._history[agent_id]:
            if snap.version_id == version_id:
                return snap
        raise KeyError(f"no snapshot {version_id!r} recorded for agent {agent_id!r}")

    def history(self, agent_id: str) -> list[PolicyVersionSnapshot]:
        return list(self._history[agent_id])
