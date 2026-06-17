# claude-dev-pipeline

A project-agnostic, human-gated multi-agent workflow for [Claude Code](https://claude.com/claude-code): **12 agents + 5 skills** that take work from a raw idea to a security-reviewed, merge-ready pull request — and keep the codebase's docs current on their own. Every component auto-detects your project's conventions at runtime, so nothing here is hardcoded to one stack.

Agents are invoked with `@name`, skills with `/name`.

## Install

```bash
git clone https://github.com/Sfzmango/claude-dev-pipeline.git
cd claude-dev-pipeline
./install.sh          # copy into ~/.claude  (use --symlink to track updates via git pull)
```

Or install as a Claude Code plugin: `/plugin marketplace add Sfzmango/claude-dev-pipeline` then `/plugin install claude-dev-pipeline`.

> **Zero to running.** The agents use a **GitHub MCP** server (issue/PR tools) and, optionally, a **Playwright MCP** server (`@developer`'s browser checks). You don't have to wire these up by hand — running `/orchestrator` does an environment **preflight**: it detects what's missing, offers to add the MCP servers for you (behind a confirmation gate), and walks you through anything only you can do (`gh auth login`, restarting Claude Code). Full walkthrough: **[`docs/getting-started.md`](docs/getting-started.md)**.

---

## Skills

**`/orchestrator`** — *`/orchestrator <issue-id>`* (or a topic; `--experiment` for a local dry run). The conductor: it runs a full issue→merge cycle by delegating each phase to the agents below and never writes code itself. It auto-detects your conventions and enforces the universal rules — a 3-commit PR structure, a full local quality gate, explicit per-commit/per-push confirmation, and a hard halt if review quality degrades.

**`/bug-catcher`** — *`/bug-catcher <symptom>`* (or `--global` to sweep the whole codebase). A diagnose-and-prove conductor that never fixes code itself. It runs a bounded debate between `@bug-catcher-rick` and `@bug-catcher-adversary`, assigns a severity, and hands a verified fix plan to `/orchestrator` or `/chore`.

**`/chore`** — *`/chore <short description>`*. A lightweight path for small single-concern changes (docs, config, a typo, a dependency bump) that skip the full pipeline but keep the same safety rails: quality gate, per-commit/per-push confirmation, and a summary-only PR. It re-routes to `/orchestrator` if the task turns out to be bigger than a chore.

**`/handoff`** — *`/handoff <issue-id-or-topic>`*. Drafts one self-contained brief so a zero-context agent (or future you) can resume a specific piece of work cold. It auto-gathers git/PR/issue/deploy state and gates on an approved outline before writing — and is never produced proactively, because a stale handoff followed confidently is worse than none.

**`/wiki-generator`** — *`/wiki-generator`* (full build) or *`/wiki-generator --update`* (incremental, schedulable). Generates and maintains a near-100%-coverage technical wiki in Markdown at `docs/wiki/` — per-module business analysis, schemas, flow diagrams, related files per page, a glossary, and an onboarding guide. The `--update` mode re-syncs only the pages that drifted, so a scheduled run keeps the wiki current with no manual upkeep. See [`docs/scheduling.md`](docs/scheduling.md).

---

## Agents

### Plan

**`@product-owner`** — *`@product-owner draft an issue for <topic>`* (also `refine issue <num>`, `sequence issues <nums>`). Turns a fuzzy ask into a well-scoped GitHub issue with business-language acceptance criteria, plus a screen-flow diagram and low-fi wireframes for user-facing work. It's read-only on code — it manages issues, never the working tree.

**`@architect`** — *`@architect plan issue <num>`* (or a free-text topic). Turns an issue into an implementation plan file, front-loading every architectural decision up front (a mid-build pivot costs ~10× a planning-phase question), with a Mermaid flow diagram and UI/UX wireframes where relevant. It lands the plan as PR commit #1 and writes plans only, never application code.

**`@plan-reviewer`** — *`@plan-reviewer <plan-file-path>`*. A cold, context-blind second opinion on a plan before it's committed — it deliberately hasn't seen the planning discussion. It checks the plan against the issue and the live code on an 8-point rubric and returns a SOLID / REVISE / RETHINK verdict. Read-only.

### Build

**`@developer`** — *`@developer implement plan <path>`*. Implements an approved plan as a single amended commit on the PR branch, auto-detecting your test/lint/build stack and writing tests. It runs live Playwright browser verification for UI changes, drives explicit commit/push gates, and hard-halts if a fix-loop iteration makes things worse instead of better.

### Review

**`@pr-reviewer`** — *`@pr-reviewer PR <num>`*. A fresh-eyes adversarial review of a pull request — it's forbidden from reading earlier reviews so it stays an independent signal. It reads every changed file against a 7-point rubric (treating multi-tenant isolation as the top bug class), posts inline comments, and gives a SHIP / SHIP WITH FIXES / DO NOT SHIP verdict.

**`@security-reviewer`** — *`@security-reviewer PR <num>`* (optional `--scope auth|payments|tenancy|deps`). A cold security and compliance gatekeeper. It runs stack-matched static analysis, dependency-CVE, and secret scans, maps every finding to SOC 2 / OWASP / PCI DSS / NIST / CWE, and posts a verdict that can hard-block on a compliance gap.

**`@security-mentor`** — *`@security-mentor PR <num>`* (or `@security-mentor diff` for a local diff). The same adversarial security review, but it teaches: every finding explains the threat model, the attack, and the structurally-immune fix. It runs alongside `@security-reviewer` — this one is the pedagogy, that one is the cold gate.

### Wrap-up

**`@resolution`** — *`@resolution PR <num>`* (after ready-to-merge is confirmed, before merge). Pre-merge housekeeping, and the exact inverse of `@pr-reviewer`: reading the full review history is its job. It replies to and resolves fixed threads (citing the fixing commit), flips done checkboxes, and HALTs if it finds anything genuinely unaddressed.

### Bug diagnosis

**`@bug-catcher-rick`** — *delegated by `/bug-catcher`* (or `@bug-catcher-rick <symptom>`). Diagnoses a bug and returns a structured dossier separating symptom from root cause, with a file:line evidence chain, severity, fix direction, and blast radius. Read-only — it diagnoses, never fixes.

**`@bug-catcher-adversary`** — *delegated by `/bug-catcher`* (or `@bug-catcher-adversary <dossier>`). A fresh-eyes rival that tries to *refute* the diagnosis — re-deriving the evidence, trying alternative causes, and checking the fix actually resolves the bug rather than masks it. Returns CONFIRMED / DISPUTED / WRONG-ROOT-CAUSE / INCONCLUSIVE.

### Wiki

**`@wiki-writer`** — *delegated by `/wiki-generator`*. Authors one wiki page from the real code: a plain-business summary, a technical deep-dive, a Mermaid diagram, schema tables, a list of real related files, and a "last verified against commit" stamp. Read-only on code; it writes only its assigned page.

**`@wiki-auditor`** — *delegated by `/wiki-generator --update`*. A fresh-eyes drift detector that compares an existing wiki page against the current code and classifies it CURRENT / STALE / INCORRECT / ORPHANED, with a precise delta list for `@wiki-writer` to fix. Writes nothing.

---

## Learn more

- [`docs/architecture.md`](docs/architecture.md) — how the agents hand off, with a full pipeline diagram
- [`docs/design-philosophy.md`](docs/design-philosophy.md) — the recurring design principles and the failure modes they prevent
- [`docs/components.md`](docs/components.md) — one-table index of all 17 components
- [`examples/`](examples/) — a sample issue, plan (with wireframes), bug dossier, and generated wiki

**License:** [PolyForm Noncommercial 1.0.0](LICENSE) © 2026 Maung Htike. Free to use, run, and adapt for **noncommercial** purposes (so employers can fully evaluate it) with attribution preserved; **commercial use requires a separate license** — contact via [github.com/Sfzmango](https://github.com/Sfzmango). Original, project-agnostic agent designs — no proprietary code; compliance rubrics reference public standards (SOC 2, OWASP, PCI DSS, NIST, CWE).
