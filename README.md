# Maungs-agentic-toolbelt

A project-agnostic, human-gated multi-agent workflow for [Claude Code](https://claude.com/claude-code): **16 agents + 11 skills** that take work from a raw idea to a security-reviewed, merge-ready pull request — and keep the codebase's docs current on their own. Every component auto-detects the host project's conventions at runtime, so nothing here is hardcoded to one stack.

Agents are invoked with `@name`, skills with `/name`.

## Install

```bash
git clone https://github.com/Sfzmango/Maungs-agentic-toolbelt.git
cd Maungs-agentic-toolbelt
./install.sh          # copy into ~/.claude  (use --symlink to track updates via git pull)
```

Or install as a Claude Code plugin: `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` then `/plugin install maungs-agentic-toolbelt@maung-tools` (the plugin is served from the repo's `maung-tools` marketplace).

> **Zero to running.** The agents use a **GitHub MCP** server (issue/PR tools) and, optionally, a **Playwright MCP** server (`@developer`'s browser checks). These do not need to be wired up by hand — running `/orchestrator` performs an environment **preflight** that detects what's missing, offers to add the MCP servers (behind a confirmation gate), and guides the user through anything that requires manual action (`gh auth login`, restarting Claude Code). Full walkthrough: **[`docs/getting-started.md`](docs/getting-started.md)**.

---

## Always-on hooks

Installed as a plugin, the toolbelt registers three lightweight hooks. The first — a `UserPromptSubmit` hook — inspects each prompt and — **only when it matches a toolbelt capability** — nudges Claude to offer the relevant component, so the right one surfaces without anyone remembering the command.

| A request like… | …surfaces |
| --- | --- |
| "set up / onboard this repo (no CLAUDE.md)" | `/agentic-onboard` |
| "build / implement this feature" | `/orchestrator`, `@architect`, `@product-owner` |
| "this test is failing / why does X error" | `/bug-catcher` |
| "review this PR" | `@pr-reviewer`, `@security-reviewer` |
| "is this secure / SOC 2 / injection" | `@security-reviewer`, `@security-mentor` |
| "how does this module work / document the codebase" | `/wiki-generator` |
| "bump a dependency / fix a typo" | `/chore` |
| "write a handoff / resume later" | `/handoff` |
| "table this / remind me later / add to my backlog" | `/todo` |
| "migrate / change the schema" | `/migration-planner` |
| "write tests / add missing tests" | `@test-author` |
| "what can this toolbelt do" | `/toolbelt` |
| "draft release notes / deploy summary" | `/release-notes` |

The hook stays **silent on anything that doesn't fit** (no token cost, no noise), only ever **suggests** — it never auto-runs workflows that commit, push, or open PRs — and is read-only with no network access. It can be disabled at any time:

```bash
export MAUNGS_TOOLBELT_ROUTER=off
```

Three more hooks come with the plugin:

**Guardrail (`PreToolUse`).** Before any shell command runs, it enforces two tiers. **Deny** (hard block) — the always-wrong cardinal-rule violations: `git add -A`/`.`, `git push --force` (without `--force-with-lease`), `--no-verify`, catastrophic `rm -rf` (on `/` `~` `*`), and AI-attributed commits. **Ask** (always prompts, with a detailed reason) — risky/data-loss ops that *might* be legitimate but must be confirmed first: destructive SQL (`DROP`/`TRUNCATE`/`DELETE`/`DROP COLUMN`), `db:drop`/`reset` & datastore flushes, `git reset --hard`/`clean -fd`/`branch -D`/`push --delete`, `rm -rf` of a non-disposable dir, `terraform destroy`/`kubectl delete`/`docker volume rm`, and bulk `find -delete`. It matches tokens in **invocation position**, so it is *not* tripped by a banned token quoted inside an argument — a PR body or commit message that merely *mentions* a rule (e.g. `gh pr create --body "we never --no-verify"`) is allowed — nor by a force flag (`-f`/`--force`) that belongs to an *unrelated command segment* in a compound invocation (e.g. a real push refspec followed by `; rm -f /tmp/x`); it stays **fail-closed** (matches as before) whenever the quoting is ambiguous. Everything else passes untouched. Disable with `export MAUNGS_TOOLBELT_GUARD=off`.

**Session loader (`SessionStart`).** At session start it injects a concise, read-only project snapshot — branch, uncommitted-file count, recent commits, the latest plan, any pending handoff, open PRs, and a nudge to run `/agentic-onboard` if there's no `CLAUDE.md` — so Claude starts warm instead of re-deriving the repo. Disable with `export MAUNGS_TOOLBELT_LOADER=off`.

**Usage telemetry (`PreToolUse` on `Task`/`Skill`).** A pass-through hook that records *when the toolbelt actually gets used* — paired with the router's *suggested* events, it answers "is this thing earning its keep?" It is **opt-in and off by default**: nothing is written unless you set `export MAUNGS_TOOLBELT_DEBUG=on` (or `=verbose`, which also traces each event to stderr — visible under `claude --debug`). When on, the router logs every component it **offers** and this hook logs every toolbelt agent/skill that actually **runs**, to an append-only JSONL log on your machine (`~/.claude/maungs-toolbelt/usage.jsonl`, override with `MAUNGS_TOOLBELT_LOG`) — never inside a project repo. It never blocks a tool, only counts our own components (built-in and third-party agents are ignored), and is read-only apart from that log. View a summary anytime with **`/toolbelt metrics`** — suggestions by intent, invocations by component, and the same-session suggestion→use conversion rate.

All four hooks ship with the **plugin** install; the copy / `install.sh` method installs the agents and skills without them.

---

## Cockpit statusline (optional)

A bundled status line, `statusline/toolbelt-statusline.sh`, renders a one-line cockpit: the active git branch (with dirty / ahead counts), session cost + duration, context-window usage, the live toolbelt hook state (`guard ● router ● loader ● debug ●`), the model — and, while `/orchestrator` is running, a **pipeline segment** showing the current phase, PR number, and review verdict. The `debug` dot reflects the usage-telemetry flag (dim `○` when off, yellow `●` while recording); when recording, it's followed by this session's `offered▸used` tally (e.g. `debug ● 3▸1`).

Unlike the hooks, it is **not** auto-enabled (Claude Code's status line is a user setting). Opt in by pointing `~/.claude/settings.json` at the script:

```json
"statusLine": {
  "type": "command",
  "command": "~/Maungs-agentic-toolbelt/statusline/toolbelt-statusline.sh"
}
```

The pipeline segment is driven by a small `~/.claude/toolbelt-status.json` that `/orchestrator` writes at each phase boundary — **always on your local machine, never inside a project repo** — and it shows only while fresh (< 30 min) and matching the current repo.

---

## Skills

**`/agentic-onboard`** — *`/agentic-onboard`* (lean) or *`/agentic-onboard --deep --target all`*. The on-ramp: scans an existing repo and generates the agent-context files the rest of the toolbelt depends on — `CLAUDE.md` + `AGENTS.md` (cross-agent) + a concise architecture map. It detects whether the repo is **cold** (no context) or **stale** (drifted, via `@context-auditor`) and diffs before writing; `--deep` also builds the full `docs/wiki`. Writes the working tree only — never commits.

**`/orchestrator`** — *`/orchestrator <issue-id>`* (or a topic; `--experiment` for a local dry run). The conductor: it runs a full issue→merge cycle by delegating each phase to the agents below and never writes code itself. It auto-detects the project's conventions and enforces the universal rules — a 3-commit PR structure, a full local quality gate, explicit per-commit/per-push confirmation, and a hard halt if review quality degrades.

**`/bug-catcher`** — *`/bug-catcher <symptom>`* (or `--global` to sweep the whole codebase). A diagnose-and-prove conductor that never fixes code itself. It runs a bounded debate between `@bug-catcher-rick` and `@bug-catcher-adversary`, assigns a severity, and hands a verified fix plan to `/orchestrator` or `/chore`.

**`/chore`** — *`/chore <short description>`* (also `--concurrently`, `--concurrently --bypass`). A lightweight path for small single-concern changes (docs, config, a typo, a dependency bump) that skip the full pipeline but keep the same safety rails: quality gate, per-commit/per-push confirmation, and a summary-only PR. It re-routes to `/orchestrator` if the task turns out to be bigger than a chore. **`--concurrently`** runs the whole chore in an isolated git worktree off the freshly-fetched default branch, so it ships safely *alongside* another session or agent editing the same checkout — the shared `HEAD`, index, and uncommitted work are never touched; **`--bypass`** (with `--concurrently`) admin-merges the moment CI is green. Neither flag ever skips CI, the chore-scope gate, or the no-`--no-verify`/no-`-A`/no-`--force` rules.

> **Spotlight — concurrency-safe chores.** `/chore --concurrently` is what lets the toolbelt run *in parallel with itself*: while `/orchestrator` is mid-build on one branch, you can land a docs or config fix on another — no `HEAD` collision, no stash dance, no waiting. The chore does its work in a throwaway worktree based on `origin/<default-branch>`, opens its own PR, then tears the worktree down (keeping the branch); with `--bypass` it even admin-merges once CI is green, loudly and auditably. Walkthrough: [`examples/sample-concurrent-chore/`](examples/sample-concurrent-chore/).

**`/handoff`** — *`/handoff <issue-id-or-topic>`*. Drafts one self-contained brief so a zero-context agent (or future self) can resume a specific piece of work cold. It auto-gathers git/PR/issue/deploy state and gates on an approved outline before writing — and is never produced proactively, because a stale handoff followed confidently is worse than none.

**`/todo`** — *`/todo`* (list), *`/todo <text>`* (add), *`/todo done <id>`* / *`/todo drop <id>`* (mutate). A private, per-project backlog for work you've tabled for later. It's stored **locally** at `~/.claude/maungs-toolbelt/todos/<project-slug>.md` — outside the repo, so a tabled task never becomes an issue, a PR, or a committed file. The session loader resurfaces the open count at the next session start and the prompt-router offers it when you talk about deferring work; nothing ever acts on an item — recording is the whole job.

**`/wiki-generator`** — *`/wiki-generator`* (full build), *`/wiki-generator --update`* (incremental, schedulable), or *`/wiki-generator --publish`* (publish to an external platform). Generates and maintains a near-100%-coverage technical wiki in Markdown at `docs/wiki/` — per-module business analysis, schemas, flow diagrams, related files per page, a glossary, and an onboarding guide. The `--update` mode re-syncs only the pages that drifted, so a scheduled run keeps the wiki current with no manual upkeep. The `--publish` mode ships the generated wiki — unchanged — to an external wiki platform through a pluggable, target-agnostic adapter seam (the GitHub repository wiki is shipped; Confluence and Azure DevOps wiki are documented future targets), always behind a dry-run preview and an explicit human approval gate. See [`docs/scheduling.md`](docs/scheduling.md) and [`docs/wiki-generator.md`](docs/wiki-generator.md).

**`/migration-planner`** — *`/migration-planner <described change | migration file>`*. A read-only pre-flight for risky data/schema migrations: it produces a risk dossier **before** the migration is written — data-loss and lock/downtime risks (flagged by database), a backfill plan, an expand/contract zero-downtime rollout, a rollback plan, and the blast radius of code touching the affected schema. It never writes or runs the migration.

**`/release-notes`** — *`/release-notes [<range> | PR <n>] [--format deploy-comment]`*. Generates grouped release notes (✨ features / 🐛 fixes / ⚠️ breaking / 🗄️ migrations) from a commit range or PRs, with a SemVer bump recommendation and a deploy checklist when migrations or env changes are detected. Read-only — it outputs text and never tags, commits, or posts; `--format deploy-comment` produces a compact block to enrich a deployment comment.

**`/overnight`** — *`/overnight [repo] [--bug --security --wiki] [--max-fixes n] [--time hh:mm --tz IANA] [--status --disable --run-now]`*. A conductor that stands up the toolbelt's overnight **cloud** routines for any target repo with one command, via the `RemoteTrigger` tool (the claude.ai/code routines API). By default it sets up three scheduled routines — bug · security · wiki — each its own routine, all feeding **one** rolling `[overnight] Dossier` tracking issue (each job owns its own marker-tagged comment, race-safe). The bug routine sweeps the codebase and auto-develops the top `--max-fixes` (default 5) non-SEV1 findings into **DRAFT, never-merged** fix PRs (SEV1 stays issue-only); the security routine runs a generic repo-wide compliance sweep (issue-only); the wiki routine runs a full-coverage build and opens **one** rolling propose-only PR. Reads and preflights for free; gates the one outward action (the routine create/update/run) behind an explicit human confirmation that shows the exact config first. Complementary to the local-daemon scheduler in [`docs/scheduling.md`](docs/scheduling.md).

**`/toolbelt`** — *`/toolbelt`* (inventory), *`/toolbelt <goal>`* (recommend a component), or *`/toolbelt status`* (environment check). The self-describing front door: it lists every component grouped by stage, recommends the best fit for a stated goal, and reports what's active (router/guard state, MCP servers, whether a `CLAUDE.md` exists). Read-only.

---

## Agents

### Onboarding

**`@context-writer`** — *delegated by `/agentic-onboard`*. Reads the repo and authors the context files (`CLAUDE.md`, `AGENTS.md`, a concise `docs/architecture.md`) from one canonical project profile, so they never disagree. Every command and claim is verified against the repo (it cites the manifest or script it came from); anything unverifiable is flagged, never invented. Read-only on source code; writes only the context files.

**`@context-auditor`** — *delegated by `/agentic-onboard` in stale mode*. A fresh-eyes drift detector: it re-derives the truth from the code and classifies each claim in an existing `CLAUDE.md` / `AGENTS.md` as CURRENT / STALE / INCORRECT / MISSING, with evidence, so `@context-writer` fixes only what drifted. Writes nothing.

### Plan

**`@product-owner`** — *`@product-owner draft an issue for <topic>`* (also `refine issue <num>`, `sequence issues <nums>`). Turns a fuzzy ask into a well-scoped GitHub issue with business-language acceptance criteria, plus a screen-flow diagram and low-fi wireframes for user-facing work. It's read-only on code — it manages issues, never the working tree.

**`@architect`** — *`@architect plan issue <num>`* (or a free-text topic). Turns an issue into an implementation plan file, front-loading every architectural decision up front (a mid-build pivot costs ~10× a planning-phase question), with a Mermaid flow diagram and UI/UX wireframes where relevant. It lands the plan as PR commit #1 and writes plans only, never application code.

**`@plan-reviewer`** — *`@plan-reviewer <plan-file-path>`*. A cold, context-blind second opinion on a plan before it's committed — it deliberately hasn't seen the planning discussion. It checks the plan against the issue and the live code on an 8-point rubric and returns a SOLID / REVISE / RETHINK verdict. Read-only.

### Build

**`@developer`** — *`@developer implement plan <path>`*. Implements an approved plan as a single amended commit on the PR branch, auto-detecting the project's test/lint/build stack and writing tests. It runs live Playwright browser verification for UI changes, drives explicit commit/push gates, and hard-halts if a fix-loop iteration makes things worse instead of better.

### Translation

**`@code-translator`** — *`@code-translator translate <file-or-snippet> from <lang> to <lang>[, …]`*. A read-only, documentation-grounded translation context provider: given source code and one or more target languages/frameworks, it fetches the real docs for every language involved (Context7 first, web fallback) and returns a translation bundle — translated code, a cited idiom map, and caveats — for you or the `/orchestrator` flow to act on. It resolves framework disambiguation, scales to N targets, works at snippet/file/module granularity, and writes nothing (it only provides grounded context).

### Testing

**`@test-author`** — *invoke directly, or when `@pr-reviewer` flags a missing test*. Authors tests — especially the negative-path and edge cases the happy path misses (validation failures, auth/tenant denial, boundary inputs, error paths) — runs them against the project's real test runner, and never weakens an assertion or deletes a test to make the suite pass. If a test reveals a real bug it reports it (pointing at `/bug-catcher`) rather than masking it. Read-only on source; writes only test files.

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
- [`docs/components.md`](docs/components.md) — one-table index of all 27 components
- [`docs/faq.md`](docs/faq.md) — how the toolbelt behaves in practice (e.g. how workers handle their adversary's feedback)
- [`examples/`](examples/) — a sample issue, plan (with wireframes), bug dossier, and generated wiki

**License:** [PolyForm Noncommercial 1.0.0](LICENSE) © 2026 Maung Htike. Free to use, run, and adapt for **noncommercial** purposes with attribution preserved; **commercial use requires a separate license** (contact via [github.com/Sfzmango](https://github.com/Sfzmango)). Original, project-agnostic agent designs — no proprietary code; compliance rubrics reference public standards (SOC 2, OWASP, PCI DSS, NIST, CWE).
