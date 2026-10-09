export type Project = {
  number: string;
  slug: string;
  title: string;
  pattern: string;
  problem: string;
  proof: string;
  outcome: string;
  stack: string[];
  video: string;
  repoPath: string;
};

const REPO_URL = "https://github.com/balajihambeere/yantrika-agent-patterns";

export const projects: Project[] = [
  {
    number: "01",
    slug: "agentic-loop",
    title: "Agentic Loop",
    pattern: "Observe → Decide → Act, with a real pause",
    problem:
      "A chatbot answers once and stops. It has no path from “here's an answer” to “here's what's actually happening right now.”",
    proof:
      "A LangGraph interrupt() genuinely pauses execution server-side — not a simulated loading spinner — and waits for an actual human decision before resuming.",
    outcome:
      "Low-risk decisions fire automatically. The one call that's irreversible and costly stops and waits for a person.",
    stack: ["LangGraph", "FastAPI", "Next.js", "TypeScript", "Tailwind"],
    video: "01-agentic-loop-demo.mp4",
    repoPath: "01-agentic-loop",
  },
  {
    number: "02",
    slug: "po-acknowledgment-agent",
    title: "PO-Acknowledgment Agent",
    pattern: "A six-box anatomy, plus one hard invariant",
    problem:
      "Most supplier-reply triage is repetitive — but guessing wrong on a quantity or delivery-date mismatch is expensive.",
    proof:
      "A hard invariant — always escalate a mismatch, no matter how confident the model is — can't be out-voted by confidence. Staged autonomy earns trust before it's granted, not after.",
    outcome:
      "Clean confirmations log silently and move on. Genuine ambiguity, or any mismatch at all, always reaches a person.",
    stack: ["LangGraph", "FastAPI", "Next.js", "TypeScript", "Tailwind"],
    video: "02-po-acknowledgment-agent-demo.mp4",
    repoPath: "02-po-acknowledgment-agent",
  },
  {
    number: "03",
    slug: "reasoning-loop-allocation",
    title: "Reasoning-Loop Allocation",
    pattern: "Weighted reasoning, not a fixed rule",
    problem:
      "One fixed priority rule — “contracted accounts always win” — got the real call wrong in 15 of 41 historical cases.",
    proof:
      "Five explicit, weighted factors — with the full reasoning attached, not just the outcome — beat the fixed rule 36-to-26 on the exact same history.",
    outcome:
      "Clear-cut cases allocate autonomously. Close calls hand a human the actual math behind the recommendation, not a black box.",
    stack: ["LangGraph", "FastAPI", "Next.js", "TypeScript", "Tailwind"],
    video: "03-reasoning-loop-allocation-demo.mp4",
    repoPath: "03-reasoning-loop-allocation",
  },
  {
    number: "04",
    slug: "policy-gate-and-ledger",
    title: "Policy Gate & Ledger",
    pattern: "Policy-as-code, plus a decision record that survives",
    problem:
      "“We believe the decision was right, but we can't show you why” is a sentence that has ended careers that didn't deserve to end.",
    proof:
      "Four checkable conditions, enforced in code, gate every autonomy-tier change. Every decision stays reconstructible afterward — even once the policy that governed it has since changed.",
    outcome:
      "A proposal missing even one condition gets rejected automatically. No human is even asked until the rule is actually satisfied.",
    stack: ["LangGraph", "FastAPI", "Next.js", "TypeScript", "Tailwind"],
    video: "04-policy-gate-and-ledger-demo.mp4",
    repoPath: "04-policy-gate-and-ledger",
  },
  {
    number: "05",
    slug: "federation-arbitration",
    title: "Federation Arbitration",
    pattern: "Two named humans, in sequence — not one rubber stamp",
    problem:
      "Two individually correct site agents can jointly over-commit a shared resource that neither one can see the other reaching for.",
    proof:
      "The fix isn't a smarter model. It's two separate, named people — one on each side — who must both sign off, in order, before any cross-boundary action proceeds.",
    outcome:
      "A near-miss collision resolves into one coordinated transfer — instead of a double-commit discovered on a loading dock.",
    stack: ["LangGraph", "FastAPI", "Next.js", "TypeScript", "Tailwind"],
    video: "05-federation-arbitration-demo.mp4",
    repoPath: "05-federation-arbitration",
  },
  {
    number: "06",
    slug: "registry-precedence-arbitration",
    title: "Registry Precedence Arbitration",
    pattern: "A pre-approved rulebook, scaled to N plants",
    problem:
      "Past three or four sites, asking a human every single time doesn't scale — but a silent collision is still expensive.",
    proof:
      "A deterministic, pre-approved rulebook — commitment tier, then days-of-cover, then a timestamp tiebreak — resolves almost every collision automatically. Only a genuine, every-tier-identical tie ever needs a person.",
    outcome:
      "The losing claim doesn't just get rejected — it gets a concrete alternate-cover suggestion immediately, before it ever becomes a worthless hold.",
    stack: ["LangGraph", "FastAPI", "Next.js", "TypeScript", "Tailwind"],
    video: "06-registry-precedence-arbitration-demo.mp4",
    repoPath: "06-registry-precedence-arbitration",
  },
];

export function repoLink(path: string): string {
  return `${REPO_URL}/tree/main/${path}`;
}

export { REPO_URL };
