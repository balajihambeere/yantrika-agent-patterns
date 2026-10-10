import "./style.css";
import { projects, repoLink, REPO_URL } from "./projects";

const base = import.meta.env.BASE_URL;

function githubIcon(cls = "h-5 w-5"): string {
  return `<svg viewBox="0 0 24 24" class="${cls}" fill="currentColor" aria-hidden="true">
    <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.09 3.29 9.4 7.86 10.93.57.1.78-.25.78-.55v-2.17c-3.2.7-3.87-1.37-3.87-1.37-.53-1.33-1.29-1.69-1.29-1.69-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.76.12 3.05.74.81 1.18 1.84 1.18 3.1 0 4.43-2.69 5.4-5.26 5.69.42.36.78 1.07.78 2.15v3.19c0 .31.21.66.79.55A10.52 10.52 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z"/>
  </svg>`;
}

function header(): string {
  return `
    <header class="sticky top-0 z-20 border-b border-border/80 bg-bg/85 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
        <a href="#top" class="flex items-center gap-2 font-semibold tracking-tight">
          <span class="text-accent">◆</span>
          <span>Yantrika Agent Patterns</span>
        </a>
        <a
          href="${REPO_URL}"
          class="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-base text-soft transition-colors hover:border-accent hover:text-accent"
        >
          ${githubIcon("h-4 w-4")}
          <span class="hidden sm:inline">View on GitHub</span>
        </a>
      </div>
    </header>`;
}

function hero(): string {
  const stats: [string, string][] = [
    ["6", "working patterns"],
    ["0", "LLM calls in any core loop"],
    ["43+", "passing tests across all six"],
    ["100%", "real interrupt()/resume — never simulated"],
  ];

  return `
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
        ${stats
          .map(
            ([value, label]) => `
          <div>
            <dt class="sr-only">${label}</dt>
            <dd class="font-mono text-2xl font-semibold text-ink sm:text-3xl">${value}</dd>
            <dd class="mt-1 text-base leading-snug text-soft">${label}</dd>
          </div>`
          )
          .join("")}
      </dl>

      <div class="mt-14 flex items-center justify-center">
        <a href="#project-01" class="group flex flex-col items-center gap-2 text-soft transition-colors hover:text-accent">
          <span class="text-base font-mono uppercase tracking-widest">Explore the six</span>
          <span class="animate-bounce text-lg">↓</span>
        </a>
      </div>
    </section>`;
}

function badge(label: string): string {
  return `<span class="rounded-full border border-border px-2.5 py-1 font-mono text-base text-soft">${label}</span>`;
}

function labeledBlock(eyebrow: string, body: string, accentColor = false): string {
  return `
    <div>
      <p class="font-mono text-base uppercase tracking-[0.15em] ${accentColor ? "text-accent" : "text-soft"}">
        ${eyebrow}
      </p>
      <p class="mt-1.5 leading-relaxed text-ink">${body}</p>
    </div>`;
}

function projectSection(p: (typeof projects)[number], index: number): string {
  const reversed = index % 2 === 1;
  const textOrder = reversed ? "lg:order-2" : "lg:order-1";
  const videoOrder = reversed ? "lg:order-1" : "lg:order-2";

  return `
    <section id="project-${p.number}" class="project-section scroll-mt-16 py-16 sm:py-20">
      <div class="mx-auto max-w-6xl px-5 sm:px-8">
        <div class="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
          <div class="${textOrder}">
            <div class="flex items-baseline gap-4">
              <span class="font-mono text-5xl font-bold text-border sm:text-6xl">${p.number}</span>
              <div>
                <h2 class="text-2xl font-bold tracking-tight sm:text-3xl">${p.title}</h2>
                <p class="mt-1 font-mono text-base text-accent">${p.pattern}</p>
              </div>
            </div>

            <div class="mt-8 space-y-5 border-l-2 border-border pl-5">
              ${labeledBlock("Problem", p.problem)}
              ${labeledBlock("What it proves", p.proof, true)}
              ${labeledBlock("Outcome", p.outcome)}
            </div>

            <div class="mt-7 flex flex-wrap gap-2">
              ${p.stack.map(badge).join("")}
            </div>

            <a
              href="${repoLink(p.repoPath)}"
              class="mt-7 inline-flex items-center gap-1.5 font-mono text-base font-medium text-ink underline decoration-border decoration-2 underline-offset-4 transition-colors hover:text-accent hover:decoration-accent"
            >
              View the code
              <span aria-hidden="true">↗</span>
            </a>
          </div>

          <div class="${videoOrder}">
            <div class="overflow-hidden rounded-xl border border-border bg-panel shadow-lg">
              <video
                src="${base}videos/${p.video}"
                controls
                preload="metadata"
                class="aspect-video w-full bg-bg"
              ></video>
            </div>
          </div>
        </div>
      </div>
    </section>`;
}

function footer(): string {
  return `
    <footer class="border-t border-border py-12">
      <div class="mx-auto max-w-6xl px-5 text-center sm:px-8">
        <p class="text-base text-soft">
          Six original, independently-verified LangGraph implementations.
          No LLM calls in any core decision loop — every <code class="font-mono">decide()</code>
          is deterministic and reproducible.
        </p>
        <a
          href="${REPO_URL}"
          class="mt-4 inline-flex items-center gap-2 font-mono text-base text-ink transition-colors hover:text-accent"
        >
          ${githubIcon("h-4 w-4")}
          github.com/balajihambeere/yantrika-agent-patterns
        </a>
      </div>
    </footer>`;
}

document.querySelector<HTMLDivElement>("#app")!.innerHTML = `
  ${header()}
  <main>
    ${hero()}
    ${projects.map(projectSection).join("")}
  </main>
  ${footer()}
`;
