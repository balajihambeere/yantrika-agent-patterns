# Yantrika Agent Patterns

Six small, runnable [LangGraph](https://github.com/langchain-ai/langgraph) implementations of common agentic-system design patterns — each one a self-contained example with its own `demo.py`, test suite, and scripted sample data (no LLM calls, no API key required; every decision is deterministic and rule-based so the examples are reproducible).

| # | Example | Pattern |
|---|---|---|
| [01](./01-agentic-loop) | Agentic Loop | Observe → Decide → (human can intervene) → Act → Log, vs. a one-shot chatbot |
| [02](./02-po-acknowledgment-agent) | PO-Acknowledgment Agent | The six-box agent anatomy — Trigger → Perceive → Decide → Act → Escalate → Log — plus four distinct guardrail types (confidence scoring, scoped exceptions, hard invariants, staged autonomy) |
| [03](./03-reasoning-loop-allocation) | Reasoning Loop Allocation | A continuous Sense → Weigh → Recommend → Escalate → Log loop for decisions with no finish line, using explicit weighted factors instead of a fixed rule |
| [04](./04-policy-gate-and-ledger) | Policy Gate & Decision Ledger | Policy-as-code autonomy tiers (with a deterministic 4-condition gate on any tier change) plus a five-part, append-only, versioned audit record |
| [05](./05-federation-arbitration) | Federation Arbitration | Observe / recommend / act trust tiers between two independent site agents, with dual named-human confirmation required before any cross-boundary commit |
| [06](./06-registry-precedence-arbitration) | Registry Precedence Arbitration | A shared resource registry with a deterministic, pre-approved precedence rulebook resolving conflicts across N agents with no per-incident human in the loop |

## Running an example

Each folder is independent and self-contained:

```bash
cd 01-agentic-loop   # or any other example
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 demo.py
python3 -m unittest discover -p "test_*.py" -v
```

Some examples have an extra script worth running too — `02-po-acknowledgment-agent/shadow_mode.py`, `03-reasoning-loop-allocation/backtest.py`, and `04-policy-gate-and-ledger/mock_audit.py`.

## Design notes that hold across all six

- **No LLM calls anywhere.** Every `decide` / `weigh` / `perceive` step is plain, deterministic Python — threshold logic, weighted scoring, or rule lookups. The point of each example is the *orchestration shape* (the graph), not a model's judgment, so nothing here needs an API key and every run is reproducible.
- **`interrupt()` is a real pause, not a callback.** Wherever a human needs to sign off, the graph genuinely suspends via LangGraph's `interrupt()` and resumes only via `Command(resume=...)` — the same mechanism a real review UI would drive.
- **Sample data lives in `data/*.json`**, loaded at runtime, kept separate from the graph/business logic in each example.
- **Streamed output is chronological.** Each `demo.py` prints node output via `graph.stream(..., stream_mode="updates")` as each node actually fires, rather than batch-reading state after the fact.

## License

No license file is included yet — all code here is original and provided as-is for reference. Add a license before relying on this for anything beyond reading/learning from it.
