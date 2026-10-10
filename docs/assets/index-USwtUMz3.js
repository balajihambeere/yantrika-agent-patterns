(function(){const a=document.createElement("link").relList;if(a&&a.supports&&a.supports("modulepreload"))return;for(const t of document.querySelectorAll('link[rel="modulepreload"]'))r(t);new MutationObserver(t=>{for(const o of t)if(o.type==="childList")for(const s of o.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&r(s)}).observe(document,{childList:!0,subtree:!0});function n(t){const o={};return t.integrity&&(o.integrity=t.integrity),t.referrerPolicy&&(o.referrerPolicy=t.referrerPolicy),t.crossOrigin==="use-credentials"?o.credentials="include":t.crossOrigin==="anonymous"?o.credentials="omit":o.credentials="same-origin",o}function r(t){if(t.ep)return;t.ep=!0;const o=n(t);fetch(t.href,o)}})();const c="https://github.com/balajihambeere/yantrika-agent-patterns",d=[{number:"01",slug:"agentic-loop",title:"Agentic Loop",pattern:"Observe → Decide → Act, with a real pause",problem:"A chatbot answers once and stops. It has no path from “here's an answer” to “here's what's actually happening right now.”",proof:"A LangGraph interrupt() genuinely pauses execution server-side — not a simulated loading spinner — and waits for an actual human decision before resuming.",outcome:"Low-risk decisions fire automatically. The one call that's irreversible and costly stops and waits for a person.",stack:["LangGraph","FastAPI","Next.js","TypeScript","Tailwind"],video:"01-agentic-loop-demo.mp4",repoPath:"01-agentic-loop"},{number:"02",slug:"po-acknowledgment-agent",title:"PO-Acknowledgment Agent",pattern:"A six-box anatomy, plus one hard invariant",problem:"Most supplier-reply triage is repetitive — but guessing wrong on a quantity or delivery-date mismatch is expensive.",proof:"A hard invariant — always escalate a mismatch, no matter how confident the model is — can't be out-voted by confidence. Staged autonomy earns trust before it's granted, not after.",outcome:"Clean confirmations log silently and move on. Genuine ambiguity, or any mismatch at all, always reaches a person.",stack:["LangGraph","FastAPI","Next.js","TypeScript","Tailwind"],video:"02-po-acknowledgment-agent-demo.mp4",repoPath:"02-po-acknowledgment-agent"},{number:"03",slug:"reasoning-loop-allocation",title:"Reasoning-Loop Allocation",pattern:"Weighted reasoning, not a fixed rule",problem:"One fixed priority rule — “contracted accounts always win” — got the real call wrong in 15 of 41 historical cases.",proof:"Five explicit, weighted factors — with the full reasoning attached, not just the outcome — beat the fixed rule 36-to-26 on the exact same history.",outcome:"Clear-cut cases allocate autonomously. Close calls hand a human the actual math behind the recommendation, not a black box.",stack:["LangGraph","FastAPI","Next.js","TypeScript","Tailwind"],video:"03-reasoning-loop-allocation-demo.mp4",repoPath:"03-reasoning-loop-allocation"},{number:"04",slug:"policy-gate-and-ledger",title:"Policy Gate & Ledger",pattern:"Policy-as-code, plus a decision record that survives",problem:"“We believe the decision was right, but we can't show you why” is a sentence that has ended careers that didn't deserve to end.",proof:"Four checkable conditions, enforced in code, gate every autonomy-tier change. Every decision stays reconstructible afterward — even once the policy that governed it has since changed.",outcome:"A proposal missing even one condition gets rejected automatically. No human is even asked until the rule is actually satisfied.",stack:["LangGraph","FastAPI","Next.js","TypeScript","Tailwind"],video:"04-policy-gate-and-ledger-demo.mp4",repoPath:"04-policy-gate-and-ledger"},{number:"05",slug:"federation-arbitration",title:"Federation Arbitration",pattern:"Two named humans, in sequence — not one rubber stamp",problem:"Two individually correct site agents can jointly over-commit a shared resource that neither one can see the other reaching for.",proof:"The fix isn't a smarter model. It's two separate, named people — one on each side — who must both sign off, in order, before any cross-boundary action proceeds.",outcome:"A near-miss collision resolves into one coordinated transfer — instead of a double-commit discovered on a loading dock.",stack:["LangGraph","FastAPI","Next.js","TypeScript","Tailwind"],video:"05-federation-arbitration-demo.mp4",repoPath:"05-federation-arbitration"},{number:"06",slug:"registry-precedence-arbitration",title:"Registry Precedence Arbitration",pattern:"A pre-approved rulebook, scaled to N plants",problem:"Past three or four sites, asking a human every single time doesn't scale — but a silent collision is still expensive.",proof:"A deterministic, pre-approved rulebook — commitment tier, then days-of-cover, then a timestamp tiebreak — resolves almost every collision automatically. Only a genuine, every-tier-identical tie ever needs a person.",outcome:"The losing claim doesn't just get rejected — it gets a concrete alternate-cover suggestion immediately, before it ever becomes a worthless hold.",stack:["LangGraph","FastAPI","Next.js","TypeScript","Tailwind"],video:"06-registry-precedence-arbitration-demo.mp4",repoPath:"06-registry-precedence-arbitration"}];function p(e){return`${c}/tree/main/${e}`}const m="/yantrika-agent-patterns/";function l(e="h-5 w-5"){return`<svg viewBox="0 0 24 24" class="${e}" fill="currentColor" aria-hidden="true">
    <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.09 3.29 9.4 7.86 10.93.57.1.78-.25.78-.55v-2.17c-3.2.7-3.87-1.37-3.87-1.37-.53-1.33-1.29-1.69-1.29-1.69-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.76.12 3.05.74.81 1.18 1.84 1.18 3.1 0 4.43-2.69 5.4-5.26 5.69.42.36.78 1.07.78 2.15v3.19c0 .31.21.66.79.55A10.52 10.52 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z"/>
  </svg>`}function u(){return`
    <header class="sticky top-0 z-20 border-b border-border/80 bg-bg/85 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
        <a href="#top" class="flex items-center gap-2 font-semibold tracking-tight">
          <span class="text-accent">◆</span>
          <span>Yantrika Agent Patterns</span>
        </a>
        <a
          href="${c}"
          class="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-base text-soft transition-colors hover:border-accent hover:text-accent"
        >
          ${l("h-4 w-4")}
          <span class="hidden sm:inline">View on GitHub</span>
        </a>
      </div>
    </header>`}function g(){return`
    <section id="top" class="mx-auto max-w-4xl px-5 pb-16 pt-20 text-center sm:px-8 sm:pb-24 sm:pt-28">
      <p class="mb-5 font-mono text-base uppercase tracking-[0.2em] text-accent">
        Six LangGraph patterns for the manufacturing ERP domain
      </p>
      <h1 class="text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl md:text-6xl">
        When should an agent act alone —
        <span class="text-accent">and when should it stop and ask?</span>
      </h1>
      <p class="mx-auto mt-6 max-w-2xl text-balance text-lg leading-relaxed text-soft">
        Six working, full-stack demos grounded in real manufacturing ERP workflows —
        PO acknowledgment, material allocation, cross-plant arbitration, shared lot
        registries — each with a real server-side <code class="font-mono text-ink">interrupt()</code>
        that genuinely pauses for a human, not a loading-spinner impression of one.
      </p>

      <dl class="mx-auto mt-14 grid max-w-3xl grid-cols-2 gap-6 sm:grid-cols-4">
        ${[["6","working patterns"],["0","LLM calls in any core loop"],["43+","passing tests across all six"],["100%","real interrupt()/resume — never simulated"]].map(([a,n])=>`
          <div>
            <dt class="sr-only">${n}</dt>
            <dd class="font-mono text-2xl font-semibold text-ink sm:text-3xl">${a}</dd>
            <dd class="mt-1 text-base leading-snug text-soft">${n}</dd>
          </div>`).join("")}
      </dl>

      <div class="mt-14 flex items-center justify-center">
        <a href="#project-01" class="group flex flex-col items-center gap-2 text-soft transition-colors hover:text-accent">
          <span class="text-base font-mono uppercase tracking-widest">Explore the six</span>
          <span class="animate-bounce text-lg">↓</span>
        </a>
      </div>
    </section>`}function h(e){return`<span class="rounded-full border border-border px-2.5 py-1 font-mono text-base text-soft">${e}</span>`}function i(e,a,n=!1){return`
    <div>
      <p class="font-mono text-base uppercase tracking-[0.15em] ${n?"text-accent":"text-soft"}">
        ${e}
      </p>
      <p class="mt-1.5 leading-relaxed text-ink">${a}</p>
    </div>`}function f(e,a){const n=a%2===1,r=n?"lg:order-2":"lg:order-1",t=n?"lg:order-1":"lg:order-2";return`
    <section id="project-${e.number}" class="project-section scroll-mt-16 py-16 sm:py-20">
      <div class="mx-auto max-w-6xl px-5 sm:px-8">
        <div class="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
          <div class="${r}">
            <div class="flex items-baseline gap-4">
              <span class="font-mono text-5xl font-bold text-border sm:text-6xl">${e.number}</span>
              <div>
                <h2 class="text-2xl font-bold tracking-tight sm:text-3xl">${e.title}</h2>
                <p class="mt-1 font-mono text-base text-accent">${e.pattern}</p>
              </div>
            </div>

            <div class="mt-8 space-y-5 border-l-2 border-border pl-5">
              ${i("Problem",e.problem)}
              ${i("What it proves",e.proof,!0)}
              ${i("Outcome",e.outcome)}
            </div>

            <div class="mt-7 flex flex-wrap gap-2">
              ${e.stack.map(h).join("")}
            </div>

            <a
              href="${p(e.repoPath)}"
              class="mt-7 inline-flex items-center gap-1.5 font-mono text-base font-medium text-ink underline decoration-border decoration-2 underline-offset-4 transition-colors hover:text-accent hover:decoration-accent"
            >
              View the code
              <span aria-hidden="true">↗</span>
            </a>
          </div>

          <div class="${t}">
            <div class="overflow-hidden rounded-xl border border-border bg-panel shadow-lg">
              <video
                src="${m}videos/${e.video}"
                controls
                preload="metadata"
                class="aspect-video w-full bg-bg"
              ></video>
            </div>
          </div>
        </div>
      </div>
    </section>`}function x(){return`
    <footer class="border-t border-border py-12">
      <div class="mx-auto max-w-6xl px-5 text-center sm:px-8">
        <p class="text-base text-soft">
          Six original, independently-verified LangGraph implementations.
          No LLM calls in any core decision loop — every <code class="font-mono">decide()</code>
          is deterministic and reproducible. Each demo also ships an optional
          OpenAI-powered chat panel for asking questions about the running scenario,
          tested against a real API key and kept entirely outside the decision path.
        </p>
        <a
          href="${c}"
          class="mt-4 inline-flex items-center gap-2 font-mono text-base text-ink transition-colors hover:text-accent"
        >
          ${l("h-4 w-4")}
          github.com/balajihambeere/yantrika-agent-patterns
        </a>
      </div>
    </footer>`}document.querySelector("#app").innerHTML=`
  ${u()}
  <main>
    ${g()}
    ${d.map(f).join("")}
  </main>
  ${x()}
`;
