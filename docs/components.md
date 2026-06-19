# Components Reference Index

This is a reference index of all **20 components** that make up the pipeline: **14 agents** (invoked via `@name`) and **6 skills** (invoked via `/name`). Components are grouped by the stage of the dev cycle they serve.

## Onboarding

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| agentic-onboard | skill | Conductor that preps any repo for agentic development: scans it and emits the context files the toolbelt depends on (CLAUDE.md + AGENTS.md + concise architecture map). Cold-generate or stale-refresh (diff-before-write); `--deep` also builds the full wiki; pluggable `--target`. | `/agentic-onboard` |
| context-writer | agent | Authors the context files (CLAUDE.md, AGENTS.md, docs/architecture.md) from one verified project profile; read-only on source, writes only context files; never fabricates. | `@context-writer` |
| context-auditor | agent | Fresh-eyes drift detector for stale context → CURRENT/STALE/INCORRECT/MISSING + a delta list for context-writer; writes nothing. | `@context-auditor` |

The onboarding stage is the on-ramp every other component depends on — they all auto-detect `CLAUDE.md` and a plan-file convention. `/agentic-onboard` scans an existing repo (cold, or with stale context), builds one canonical project profile, and delegates authoring to `@context-writer` and drift-detection to `@context-auditor`, emitting the Claude (`CLAUDE.md`) and cross-agent (`AGENTS.md`) targets now and others later. It writes the working tree only and diffs before overwriting.

## Conductor

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| orchestrator | skill | Conductor that runs a full issue→merge dev cycle by delegating each phase to specialized agents; never codes itself. Runs a Step 0 environment preflight (gh auth + required MCP servers) that bootstraps or guides setup first. Enforces 3-commit PR, per-commit/per-push human gates, quality-degradation HARD-HALT, `--experiment` dry-run. | `/orchestrator` |

The conductor stage is the entry point for a complete development cycle. `/orchestrator` owns the end-to-end flow from issue to merge but writes no code itself — it delegates each phase to the specialized Plan, Build, Review, and Wrap-up agents, while enforcing the pipeline's hard guarantees: a 3-commit PR structure, human gates on every commit and push, a hard-halt on any quality degradation, and an `--experiment` dry-run mode. Before any of that, a **Step 0 environment preflight** detects missing dependencies (gh auth, and the GitHub / Playwright MCP servers), offers to set up the safe ones behind a confirmation gate, and guides the user through anything interactive — so a fresh clone can go from zero to running. See [`getting-started.md`](getting-started.md).

## Plan

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| product-owner | agent | Turns a fuzzy ask into a scoped GitHub issue with business-language acceptance criteria; read-only + issue tools only; now also emits UI/UX screen-flow + low-fi wireframes for user-facing work. | `@product-owner` |
| architect | agent | Turns an issue into a plan file, front-loading every architectural decision upfront (mid-build decisions ~10x costlier); lands the plan as PR commit #1; now also emits UI/UX screen-flow + wireframes. | `@architect` |
| plan-reviewer | agent | Cold, context-blind adversarial critique of the plan before commit; 8-point rubric → SOLID/REVISE/RETHINK; read-only. | `@plan-reviewer` |

The plan stage converts intent into a vetted, committed plan. `@product-owner` scopes a fuzzy ask into a concrete GitHub issue with business-language acceptance criteria (and UI/UX flows + wireframes for user-facing work). `@architect` then front-loads every architectural decision into a plan file — landing it as PR commit #1 — because decisions deferred to mid-build are roughly 10x more expensive. `@plan-reviewer` provides a cold, context-blind adversarial pass against an 8-point rubric, returning SOLID, REVISE, or RETHINK before the plan is locked in.

## Build

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| developer | agent | Implements the approved plan as one amended commit #2; auto-detects test/lint/build stack; live Playwright UI verification; quality-degradation circuit breaker; strict commit/push gates. | `@developer` |

The build stage is where the approved plan becomes working code. `@developer` implements the plan as a single amended commit #2, auto-detecting the project's test, lint, and build stack, verifying UI changes live with Playwright, and tripping a circuit breaker if quality degrades — all behind strict commit and push gates.

## Review

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| pr-reviewer | agent | Fresh-eyes PR review (never reads prior reviews); 7-point rubric with multi-tenant isolation as the top bug class → SHIP/SHIP WITH FIXES/DO NOT SHIP; inline comments. | `@pr-reviewer` |
| security-reviewer | agent | Cold compliance gatekeeper; SAST + dep-CVE + secret scan; maps findings to SOC2 CC1-CC9/OWASP/PCI DSS v4/NIST 800-63B/CWE → ship/no-ship/COMPLIANCE BLOCKER. | `@security-reviewer` |
| security-mentor | agent | Same review as security-reviewer but teaches the *why* on every finding (threat model + attacker payload + structurally-immune fix). | `@security-mentor` |

The review stage subjects the PR to independent, fresh-eyes scrutiny. `@pr-reviewer` evaluates the change against a 7-point rubric — treating multi-tenant isolation as the top bug class — and returns SHIP, SHIP WITH FIXES, or DO NOT SHIP with inline comments, never reading prior reviews. `@security-reviewer` acts as a cold compliance gatekeeper, running SAST, dependency CVE, and secret scans and mapping findings to SOC2, OWASP, PCI DSS v4, NIST 800-63B, and CWE frameworks. `@security-mentor` performs the same security review but teaches the why behind each finding, pairing a threat model and attacker payload with a structurally-immune fix.

## Wrap-up

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| resolution | agent | Pre-merge housekeeping; the inverse of pr-reviewer (its job IS reading review history); resolves fixed threads citing the fixing commit, flips checkboxes, HALTs on anything unaddressed. | `@resolution` |

The wrap-up stage gets the PR merge-ready. `@resolution` is the inverse of `@pr-reviewer` — its entire job is reading the review history. It resolves fixed threads while citing the commit that fixed them, flips acceptance-criteria checkboxes, and halts on anything still unaddressed.

## Bug side-flow

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| bug-catcher | skill | Diagnose-and-prove conductor; runs a bounded debate between rick and adversary, severity-ranks, and hands a verified fix plan to `/orchestrator` or `/chore`; `--global` sweeps the whole codebase. | `/bug-catcher` |
| bug-catcher-rick | agent | Produces an evidence-backed root-cause dossier (symptom vs cause, file:line evidence chain, SEV, fix direction, blast radius). | `@bug-catcher-rick` |
| bug-catcher-adversary | agent | Fresh-eyes refuter that tries to prove the diagnosis wrong → CONFIRMED/DISPUTED/WRONG-ROOT-CAUSE/INCONCLUSIVE. | `@bug-catcher-adversary` |

The bug side-flow is a self-contained diagnose-and-prove loop that feeds back into the main pipeline. `/bug-catcher` is the conductor: it runs a bounded debate between `@bug-catcher-rick`, which produces an evidence-backed root-cause dossier (symptom vs cause, a file:line evidence chain, severity, fix direction, and blast radius), and `@bug-catcher-adversary`, a fresh-eyes refuter that tries to prove the diagnosis wrong and returns CONFIRMED, DISPUTED, WRONG-ROOT-CAUSE, or INCONCLUSIVE. The conductor severity-ranks the results and hands a verified fix plan to `/orchestrator` or `/chore`; its `--global` flag sweeps the entire codebase.

## Utility

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| chore | skill | Lightweight escape hatch for small single-concern PRs that keep the same commit/push gates; re-routes to `/orchestrator` if it grows. | `/chore` |
| handoff | skill | Drafts a self-contained, drift-aware brief so a zero-context agent (or future self) can resume work cold; never written proactively. | `/handoff` |

The utility stage provides lightweight escape hatches around the main pipeline. `/chore` handles small, single-concern PRs without the full ceremony while keeping the same commit and push gates, and re-routes to `/orchestrator` if the change grows beyond chore size. `/handoff` drafts a self-contained, drift-aware brief that lets a zero-context agent — or a future self — resume work cold; it is never written proactively.

## Wiki side-flow

| Component | Kind | One-liner | Invocation |
| --- | --- | --- | --- |
| wiki-generator | skill | Conductor that generates & maintains a near-100% technical wiki for any codebase (per-module analysis, schemas, flow diagrams, UI mocks, related files, glossary, onboarding). Full-build + incremental `--update` mode; schedulable. Output: Markdown in `docs/wiki/`. | `/wiki-generator` |
| wiki-writer | agent | Authors/updates ONE wiki page from real code (business summary + technical deep-dive + mermaid + schema + related files@path + "verified against commit" stamp); read-only on code, writes only its page. | `@wiki-writer` |
| wiki-auditor | agent | Fresh-eyes drift detector for `--update`/scheduled mode; compares an existing page against current code → CURRENT/STALE/INCORRECT/ORPHANED + a delta list for `@wiki-writer`; writes nothing. | `@wiki-auditor` |

The wiki side-flow generates and maintains a near-100% technical wiki for any codebase. `/wiki-generator` is the conductor, producing per-module business analysis, schemas, flow diagrams, UI mocks, related-files-per-page, a glossary, and onboarding material as Markdown in `docs/wiki/`; it supports a full-build mode and an incremental `--update` mode that re-syncs only stale pages, and it is schedulable for self-maintenance. `@wiki-writer` authors or updates exactly one page from real code — pairing a business summary with a technical deep-dive, mermaid diagrams, schemas, related files referenced by path, and a "verified against commit" stamp — reading code but writing only its own page. `@wiki-auditor` is the fresh-eyes drift detector behind the update and scheduled modes: it compares an existing page against current code, classifies it as CURRENT, STALE, INCORRECT, or ORPHANED, and emits a delta list for `@wiki-writer` to fix while writing nothing itself.
