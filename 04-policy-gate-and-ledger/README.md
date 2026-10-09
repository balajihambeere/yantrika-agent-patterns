# Code Companion

A runnable implementation of two genuinely code-shaped ideas: **policy-as-code
autonomy tiers** and the **five-part auditable decision record** — wired
together as **the policy gate every agent decision crosses**.

It's built on **LangGraph**, running against a small scripted replay of
Vimana's scenarios: Arjun's allocation agent, its original bounded-autonomy
boundary, the widening proposal that goes through Suresh Rane as the named
approver, and the eleven-week-old decision Kavita picks at random to test
whether Arjun can reconstruct it in twenty minutes (he can't, in the original
incident — this code proves the gap is closed).

## Demo video

<video src="../demo-videos/04-policy-gate-and-ledger-demo.mp4" controls width="100%"></video>

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the demo

```bash
python3 demo.py
```

Streams five scenarios through `policy_gate_graph.build_graph()`, printing
every node as it actually fires, in true chronological order:

1. **A within-boundary Tier 2 action** — a single, low-exposure claim on
   Arjun's allocation agent. `check_boundary` finds it inside the
   agreed zone; it auto-acts, no interrupt, and a five-part record is
   written.
2. **An out-of-boundary action** — two competing claims, exposure over
   the agreed cap. The graph genuinely pauses on `interrupt()` and
   routes to Aditi Kulkarni, the agent's named escalation contact,
   before anything happens.
3. **Arjun's actual tier-widening proposal** — all four policy-as-code
   conditions satisfied (a numeric 130-decision track record, Arjun as
   proposer and Suresh Rane as a structurally different named approver,
   an explicit reversal trigger, a scheduled re-review date). It routes
   to Suresh via `interrupt()`, the boundary widens, and a governance
   record is logged.
4. **A follow-up widening, REJECTED outright** — missing a sufficient
   track record and a reversal trigger. `policy_engine` rejects it
   deterministically; no `interrupt()` fires at all, and Suresh is
   never even asked.
5. **A reversal-trigger check that fires** — a run of recent decisions
   including one missed commitment trips the predefined trigger from
   scenario 3, and the boundary rolls back automatically to its
   pre-widening state, logged as its own governance record, with no
   human call involved anywhere in the branch.

## Run the mock audit

```bash
python3 mock_audit.py
```

Recreates Kavita's dramatized audit test directly: seeds one decision,
backdated eleven weeks, under `policy-v1`; advances the policy twice
(simulating tier-boundary widenings happening since); records the decision's
real-world outcome later as a linked ledger amendment; then runs
Kavita's actual question — "walk me through exactly why, and which
policy was live that day, not today's" — as a single
`decision_ledger.reconstruct()` / `print_full_record()` call. It also
demonstrates the chain-of-custody hash check catching a direct,
API-bypassing edit to a stored record.

## Run the tests

```bash
python3 -m unittest test_policy_gate_graph.py -v
```

## Files

| File | What it is |
|---|---|
| `policy_engine.py` | The four-tier `AutonomyTier` registry (`PolicyRegistry`), `TierBoundary` / `ReversalTrigger` as explicit, checkable conditions, `validate_tier_change_proposal()` — the policy-as-code gate that rejects any proposal missing one of the four required conditions — and `evaluate_reversal_trigger()`, which checks a predefined trigger against recent decision history for automatic rollback. Also carries the versioned `PolicyVersionSnapshot` history the audit depends on. |
| `decision_ledger.py` | The five-part `DecisionRecord` (inputs, policy+model version, reasoning path, human actions, outcome) and the append-only `DecisionLedger`: `log_decision()` writes new originals, `append_outcome()` links a later-known outcome without touching history, `reconstruct()` / `print_full_record()` answer "walk me through exactly why" directly, and `verify_chain()` is the chain-of-custody tamper-evidence check. |
| `policy_gate_graph.py` | The LangGraph `StateGraph`: one graph, three request types (`operational`, `governance`, `reversal_check`), routed at `START`. Operational actions auto-act or escalate via a real `interrupt()`; governance proposals are validated deterministically before a real `interrupt()` ever reaches the named approver; reversal checks roll a tier back automatically with no `interrupt()` at all. Every branch ends by writing exactly one five-part record to the shared ledger. |
| `demo.py` | Drives the five scenarios above, streaming every node in order and resuming past each `interrupt()` with `Command(resume=...)`. |
| `mock_audit.py` | Standalone recreation of Kavita's dramatized audit test, including an older decision made under a prior policy version, proving the versioning gap it names is closed. |
| `test_policy_gate_graph.py` | Unit tests: within-boundary auto-act (no interrupt, five-part record), out-of-boundary escalation (interrupt fires, human response recorded), a valid widening reaching the approver interrupt, a proposal rejected for a missing condition (no interrupt), a proposal rejected for proposer==approver, a reversal trigger firing and rolling back automatically, a reversal trigger not firing leaving the boundary untouched, an `append_outcome` amendment that doesn't mutate the original, and the versioning test — reconstructing an old decision under its *original* policy version after two further policy changes. Its scenario fixtures stay inline and self-contained, deliberately not sharing the JSON files below. |
| `data/demo_scenarios.json` | The scripted sample data behind `demo.py`'s five scenarios — each scenario's action inputs/reasoning path or tier-change proposal, plus scenario 5's recent-decisions run and the `STORY_TODAY` date — loaded at runtime instead of being hardcoded in the script. |
| `data/mock_audit_scenario.json` | The scripted sample data behind `mock_audit.py` — the eleven-week-old decision's inputs, the later tier-boundary-widening proposal, the linked outcome, the tamper value, and the `AUDIT_TODAY` date/`weeks_ago` offset used to derive `ELEVEN_WEEKS_AGO` — loaded at runtime instead of being hardcoded in the script. |
| `requirements.txt` | Just `langgraph`. Nothing else — every check in this repo (`validate_tier_change_proposal`, `TierBoundary.covers`, `evaluate_reversal_trigger`) is deliberately plain, deterministic Python, not an LLM call, so the demo is reproducible and needs no API key. |

## Why policy validation is deterministic code, not an LLM judgment call

The entire argument here is that "the evidence felt good enough" is a
decision made by whoever happens to be confident that week — not a
policy anyone could point to afterward. `validate_tier_change_proposal()`
checks exactly four named, numeric, structural conditions and rejects a
proposal missing any one of them with a specific reason, before a
single human — including the named approver — ever sees it. An LLM
asked to "use judgment" about whether a proposal looks ready would
reintroduce precisely the thing Kavita is trying to close off: a call
that depends on whoever is reviewing it that day, impossible to audit
or defend consistently five years later under a team that's never met
the person who originally earned the boundary. Policy-as-code here means
exactly that, literally — the rule is a function, not a paragraph a
reviewer might interpret generously under deadline pressure.

The same logic applies to `evaluate_reversal_trigger()`: the trigger's
metric, comparison, and threshold are all fixed at proposal time, so
checking whether it has fired is arithmetic against a pre-agreed number,
never a fresh human call made during the stress of an actual incident —
"decided in advance."

## Why the decision ledger is append-only

Versioning only stays fixed if a decision record's `policy_version` can
never quietly drift to mean "whatever is live now." `DecisionLedger.log_decision()`
creates records, never edits them; `append_outcome()` is the only way a
later-known fact (a shipment landed, a commitment was missed) gets
attached, and it does so by writing a brand-new record that links back
via `amends`, leaving the original's inputs, policy_version,
model_version, and reasoning_path exactly as they were the moment the
decision was made. `DecisionLedger.verify_chain()` backs this with a
plain stdlib-hashlib hash chain over every record in append order — not
real write-once storage or cryptographic signing, but the same
chain-of-custody property, demonstrated with the simplest tool that
honestly shows it: if any already-written record's content changes, the
stored hash for it stops matching, and `verify_chain()` names exactly
which one broke. `mock_audit.py` exercises this directly.

## Why the policy gate is one graph with three request types, not three separate programs

The policy gate is the single layer "every agent decision crosses" —
not four separate per-agent systems that each reinvent boundary-checking,
approval routing, and logging. `policy_gate_graph.py`
reflects that structurally: `PolicyRegistry` and `DecisionLedger` are
shared, real, stateful objects passed into `build_graph()`, not data
carried inside the graph's own checkpointed state, so one gate serves
every operational action, every governance proposal, and every reversal
check, writing to the one ledger every one of them shares — the exact
shape a unified decision ledger describes.

---

*Vimana Auto Components and the scenario replayed here are fictional.
This code is an original illustration of general policy-as-code and
auditable-decision-ledger patterns and is not based on any vendor's
proprietary implementation.*
