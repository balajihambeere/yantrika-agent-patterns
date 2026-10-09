"""
The shared lot registry.

This is the piece that didn't exist the Monday Pune and Plant Two both put a
hold on the same Nashik supplier-lot, four minutes apart, with neither agent
able to see the other. The fix here is deliberate: not smarter agents,
not agent-to-agent negotiation, but a registry that tracks every open hold
against every supplier-lot combination, in real time, across every plant —
so a collision gets caught at the moment a second claim arrives, instead of
being discovered later when a truck shows up short.

`LotRegistry` is built for N plants, not two: any number of plants can hold
claims in it at once, and a claim only collides with another claim on the
*same* (supplier, lot) key, from a *different* plant. Unrelated claims from
a third or fourth plant never touch each other. That's the deliberate
contrast with a different design used elsewhere in this project: a pairwise
arbitration layer built for exactly two plants (Pune and Nashik) that
required a named human to confirm every single cross-plant transfer — see
README.md for the full contrast.

No LLM here either: this is a plain in-memory index with one job — tell
`coordination_graph.py` whether a new claim collides with anything else
already on file for that lot.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldRecord:
    claim: dict
    status: str  # "pending" -> "confirmed" or "closed_lost"


class LotRegistry:
    """
    Shared, real-time index of open holds per (supplier, lot) across all
    plants, plus a full arbitration audit log: every decision, win or lose,
    logged with both competing claims and the precedence computation that
    resolved them — not just each agent's own private reasoning.
    """

    def __init__(self) -> None:
        self._holds: dict[tuple[str, str], list[HoldRecord]] = {}
        self.audit_log: list[dict] = []

    @staticmethod
    def _key(claim: dict) -> tuple[str, str]:
        return (claim["supplier"], claim["lot_id"])

    def find_collisions(self, claim: dict) -> list[dict]:
        """
        Return the claims of every OTHER plant with an open (pending or
        confirmed) hold against the same supplier-lot as `claim`. An empty
        list means this claim is clear to grant immediately.
        """
        key = self._key(claim)
        records = self._holds.get(key, [])
        return [
            record.claim
            for record in records
            if record.status in ("pending", "confirmed") and record.claim["plant"] != claim["plant"]
        ]

    def register_pending(self, claim: dict) -> None:
        """Record that a plant's agent has just placed a hold request."""
        key = self._key(claim)
        self._holds.setdefault(key, []).append(HoldRecord(claim=claim, status="pending"))

    def _record_for(self, claim: dict) -> HoldRecord:
        for record in self._holds.get(self._key(claim), []):
            if record.claim["claim_id"] == claim["claim_id"]:
                return record
        raise KeyError(f"No registry record for claim {claim['claim_id']!r} — was it ever submitted?")

    def confirm(self, claim: dict) -> None:
        """Mark a claim's hold as the confirmed winner for its supplier-lot."""
        self._record_for(claim).status = "confirmed"

    def close_lost(self, claim: dict) -> None:
        """Mark a losing claim's hold as closed — it will not be fulfilled from this lot."""
        self._record_for(claim).status = "closed_lost"

    def record_arbitration(self, entry: dict) -> None:
        """Append one full audit-log entry — every arbitration, win or lose."""
        self.audit_log.append(entry)

    def snapshot(self) -> dict[str, list[dict]]:
        """A human-readable view of every open/confirmed/closed hold, for the demo."""
        return {
            f"{supplier} / {lot_id}": [
                {"plant": r.claim["plant"], "status": r.status} for r in records
            ]
            for (supplier, lot_id), records in self._holds.items()
        }
