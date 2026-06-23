# Examples — try the pipeline end-to-end

This folder lets you **see the pipeline work, then run it yourself** against a
throwaway repo. It contains two things:

1. **Static sample artifacts** — real output the pipeline produces (an issue, a
   plan, a bug dossier, a generated wiki). Read these first to know what "good"
   looks like before you run anything.
2. **A guided end-to-end walkthrough** — install the components, then drive a
   feature, a bug, and a wiki build against a disposable copy of your own repo.

Everything below uses **one fictional app — "ExampleApp"** — so the artifacts
and the walkthrough cohere. You don't need ExampleApp to follow along; it's a
narrative device. The pipeline is project-agnostic and auto-detects whatever
repo you point it at.

---

## The example app: ExampleApp

> **ExampleApp** is a multi-tenant **B2B SaaS helpdesk**. It is fictional and
> resembles no real company, product, or person.

**Domain model**

```
Organization (the tenant)
  └─ Member            roles: owner · agent · viewer
        └─ Ticket      has many Comments; status: open · pending · resolved · closed
  └─ Billing
        ├─ Plan        free · team · business
        └─ Invoice     issued per billing period
```

**The one rule that matters most:** every record is **scoped to an
Organization**. A Member of org A must never read, write, or even discover a
Ticket, Comment, Invoice, or Member belonging to org B. **Cross-tenant access
must return 404, not 403** (a 403 leaks the existence of the resource).

**Plausible stack** (kept stack-light in the examples so they transfer to your
project): Ruby on Rails + PostgreSQL with a React front-end. The pipeline
auto-detects the real stack of whatever repo you run it in — RSpec/Jest/pytest,
lefthook/husky, CI workflows, and so on — so none of this is hard-coded.

Multi-tenant isolation is the pipeline's **top bug class**: `@pr-reviewer`
treats it as the #1 thing to break, `@bug-catcher-rick` auto-rates a
cross-tenant leak **SEV1**, and that SEV1 can never be downgraded or routed to a
quick `/chore`. The samples below are built around exactly this class of bug.

---

## Static sample artifacts (read these first)

Each file is a frozen, representative example of one stage's real output for
ExampleApp. They're documentation, not executable — but they're the same format
the live agents emit.

The samples are ordered by the lifecycle stage they belong to, and most ride **one running feature** — EX-218 "team invitations" — so they chain into a single story (onboard → issue → plan → review → tests → migration → release → handoff). The bug dossier and wiki use the same ExampleApp domain.

| Artifact | What it is | Produced by |
| --- | --- | --- |
| [`sample-onboarding/`](./sample-onboarding/) | The agent-context files the on-ramp generates for ExampleApp — a `CLAUDE.md` + `AGENTS.md` capturing the stack, the 404-not-403 tenant rule, the domain model, and commands (with `(needs confirmation)` tags where a real pass would still be inferring). | `/agentic-onboard` → `@context-writer` |
| [`sample-issue.md`](./sample-issue.md) | A scoped GitHub issue for **team invitations** — business-language acceptance criteria, lifecycle + screen-flow diagrams, a low-fidelity wireframe, and a UX-flow note. | `@product-owner` |
| [`sample-plan.md`](./sample-plan.md) | The architect's plan file for that issue (lands as **PR commit #1**), written to `docs/plans/218_team-invitations.md` — design, migrations, UI/UX, test plan, blast radius. | `@architect` |
| [`sample-plan-review.md`](./sample-plan-review.md) | A cold, context-blind review of the plan above — a verdict (**SOLID**) + findings, before a line of code is written. | `@plan-reviewer` |
| [`sample-pr-review.md`](./sample-pr-review.md) | A fresh-eyes review of the invitations PR (#218) — inline `file:line` findings by severity + a verdict (**SHIP WITH FIXES**); multi-tenant isolation is the #1 check. | `@pr-reviewer` |
| [`sample-security-review.md`](./sample-security-review.md) | A compliance-mapped security review of PR #218 — findings tagged to SOC 2 CC#, OWASP Top 10, NIST 800-63B, and CWE, plus a verdict. | `@security-reviewer` |
| [`sample-tests/`](./sample-tests/) | Negative-path-first RSpec for the invitations feature — cross-tenant 404, expired / single-use token, owner-only denial, the partial-unique index. | `@test-author` |
| [`sample-migration-dossier.md`](./sample-migration-dossier.md) | A migration risk dossier — data-loss / lock / backfill / expand-contract / rollback analysis for the `invitations` table plus a risky `members.joined_via` backfill. | `/migration-planner` |
| [`sample-release-notes.md`](./sample-release-notes.md) | Release notes derived from the invitations PR set — grouped entries, a SemVer bump, and a deploy checklist. Text only; never tags/commits/pushes. | `/release-notes` |
| [`sample-handoff.md`](./sample-handoff.md) | A resume-from-cold brief for the in-flight invitations work — an entry-point command, what's done, the outstanding review punch list, and precise citations. | `/handoff` |
| [`sample-bug-dossier.md`](./sample-bug-dossier.md) | An evidence-backed root-cause dossier for a **cross-tenant ticket leak** — symptom vs. cause, a `file:line` evidence chain, **SEV1**, fix direction, and blast radius. | `@bug-catcher-rick` (verified by `@bug-catcher-adversary`) |
| [`sample-translation-bundle.md`](./sample-translation-bundle.md) | A read-only, **doc-grounded** code-translation bundle (Rails → FastAPI) — translated code + a cited idiom map + caveats + a framework-disambiguation prompt. Context only; writes nothing. | `@code-translator` |
| [`sample-translation-stress.md`](./sample-translation-stress.md) | A doc-grounded **stress test** of the translator — baseline esolang translations (Brainfuck · x86-64 asm · Shakespeare), verifiable **control experiments** (factorial → Go/Rust; uppercase → sed/awk, run + confirmed here), and **limit tests** (Befunge 2D · recursion→Brainfuck · Malbolge) that show where doc-grounding holds vs. where the honest output is a caveat or a refusal. | `@code-translator` |
| [`sample-wiki/`](./sample-wiki/) | A generated technical wiki for ExampleApp — per-module pages (Organizations, Members, Tickets, Billing), schemas, mermaid flow diagrams, a glossary, and an onboarding page, each stamped "verified against commit". | `/wiki-generator` → `@wiki-writer` |
| [`sample-concurrent-chore/`](./sample-concurrent-chore/) | A concurrency-safe chore shipped **while EX-218 is mid-build** — `/chore --concurrently` does the whole fix in an isolated worktree off `origin/main`, opens its own PR, and never touches the in-flight branch's `HEAD` (`--bypass` variant included). | `/chore --concurrently` |

Use them as **acceptance criteria for your own run**: when you drive the
walkthrough below, your output should look like these.

---

## Before you start: prerequisites

### Install the components

Pick one. Both make the 16 agents (`@architect`, `@developer`, `@pr-reviewer`,
…) and 11 skills (`/orchestrator`, `/bug-catcher`, `/wiki-generator`, `/chore`,
`/handoff`, `/dossier-jobs`) available in any project.

**Option A — `install.sh` (copies into `~/.claude`)**

```bash
# from the repo root
./install.sh                 # copy agents + skills into ~/.claude
./install.sh --symlink       # symlink instead, so `git pull` tracks updates
./install.sh --dry-run       # preview, change nothing
```

**Option B — as a plugin (one command)**

This repo ships a `.claude-plugin/plugin.json`, so it installs as the
`maungs-agentic-toolbelt` plugin on Claude Code. See the repo root README's "Install as a plugin"
section for the marketplace/add command. The OpenAI Codex CLI port ships the same components via `codex plugin marketplace add …` + `codex plugin add …` (plus `./install-codex.sh` for the custom subagents) — see [`../docs/codex.md`](../docs/codex.md).

After either, **restart your agent CLI** — on Claude Code, restart it (or run `/agents` and `/skills`); on the Codex CLI, restart `codex` — so the
new components are discovered.

### Required MCP servers

The agents call GitHub and (for UI work) a browser through MCP. Configure these
in the **target repo** you're running against:

| MCP server | Used by | What it powers |
| --- | --- | --- |
| **GitHub MCP** | `@product-owner`, `@architect`, `@pr-reviewer`, `@security-reviewer`, `@resolution`, and the conductor skills | Reading and writing **issues and PRs** — fetching the issue, opening the PR, posting inline review comments, flipping acceptance-criteria checkboxes, resolving threads. |
| **Playwright MCP** | `@developer` | **Live browser verification** of UI changes — e.g. logging in as an ExampleApp `agent`, reassigning a ticket, and confirming the change actually renders before the commit gate. |

**gh-CLI fallback.** If GitHub MCP isn't connected, the pipeline degrades
rather than dies:

- The `@resolution` agent **falls back to the `gh` CLI** for thread resolution
  and PR housekeeping.
- `/orchestrator` on a **free-text topic** (not a numeric issue ID) doesn't
  strictly require GitHub MCP at all — planning proceeds directly.
- `/orchestrator <numeric-issue-id>` **does** want issue access: with neither
  GitHub MCP nor `gh` available it surfaces the verbatim error and halts so you
  can fix the connection instead of guessing.

Make sure `gh auth status` is green if you intend to rely on the fallback.

### Use a throwaway repo

Run all of this against a **disposable fork or scratch copy** — the pipeline
opens real PRs, pushes branches, and (for `/wiki-generator`) writes files under
`docs/wiki/`. Every commit and push is human-gated, but a throwaway repo means
you can experiment freely.

```bash
# example: a scratch clone you don't mind churning
gh repo fork your-org/your-app --clone --fork-name exampleapp-pipeline-trial
cd exampleapp-pipeline-trial
```

> For **zero** side effects on the first pass, run
> `/orchestrator --experiment <topic>` — a local-only dry run that writes the
> plan to the working tree and skips every commit, push, PR, and GitHub write.

---

## End-to-end walkthrough

Three flows, in a natural order to try them: **build a
feature**, **catch a bug**, **document the codebase**. Each maps to one of the
static artifacts above.

### 1. Ship a feature — `/orchestrator <issue>`

The conductor. It runs a full **issue → merge** dev cycle and **writes no code
itself** — it delegates each phase to the agent that owns it, enforcing a
3-commit PR and a human gate on every commit and push.

```text
/orchestrator 218       # a numeric GitHub issue id (needs GitHub MCP or gh)
# — or —
/orchestrator "let an organization owner invite a teammate by email"
```

What happens (compare against `sample-issue.md` and `sample-plan.md`):

1. **Fetch + sanity-check** the issue (GitHub MCP). Sparse? It can call
   `@product-owner` to refine it into something like `sample-issue.md`.
2. **`@architect`** front-loads the design into a plan file
   (`docs/plans/218_team-invitations.md`, like `sample-plan.md`), lands it as
   **commit #1**, and opens the PR. `@plan-reviewer` gives a cold,
   context-blind verdict (SOLID / REVISE / RETHINK) first — like
   `sample-plan-review.md`.
3. **`@developer`** implements the plan as **commit #2**, auto-detecting the
   test/lint/build stack and **verifying the UI live via Playwright MCP** —
   e.g. reassigning a ticket as an ExampleApp `agent` in a real browser.
4. **`@pr-reviewer`** does a fresh-eyes review (multi-tenant isolation is the #1
   check) → SHIP / SHIP WITH FIXES / DO NOT SHIP, with inline comments.
   `@security-reviewer` runs the compliance gate.
5. **`@resolution`** resolves fixed threads (citing the fixing commit), flips
   the acceptance-criteria checkboxes, and halts on anything unaddressed.
6. The conductor reports the PR is **ready for you to merge** — it never merges
   for you.

Every commit and push pauses for an explicit "yes." Commits carry **no
AI-assistant attribution**.

### 2. Catch a bug — `/bug-catcher <symptom>`

A diagnose-and-prove side-flow that hands a verified fix plan back into
`/orchestrator` (or `/chore` for tiny fixes). It **never commits or pushes
itself**.

```text
/bug-catcher "an agent in org A can open a ticket belonging to org B by id"
# — or, sweep the whole codebase + tests for bugs —
/bug-catcher --global authorization
```

The three-phase debate (its output looks like `sample-bug-dossier.md`):

1. **`@bug-catcher-rick`** reproduces/locates the failure and returns a
   structured **dossier**: symptom vs. root cause, an `EVIDENCE CHAIN` at
   `file:line`, a proposed **SEV**, a fix direction, and the blast radius. A
   cross-tenant leak like ExampleApp's is auto-rated **SEV1**.
2. **`@bug-catcher-adversary`** (cold, fresh eyes) tries to **refute** the
   diagnosis → CONFIRMED / DISPUTED / WRONG-ROOT-CAUSE / INCONCLUSIVE.
3. The conductor runs a **bounded debate** between them. Only a *confirmed*
   diagnosis becomes an approved fix plan; an unresolved one escalates to you
   with both positions — never a guess routed downstream.

Then, behind an explicit gate, it hands the plan to **`/orchestrator`** (SEV1/SEV2
always) or **`/chore`** (SEV4, genuinely one file, no security/migration
surface). The actual fix rides through that downstream flow under the normal
commit/push gates.

### 3. Document the codebase — `/wiki-generator`

Generates and maintains a near-100% technical wiki as Markdown under
**`docs/wiki/`**. Compare the result against [`sample-wiki/`](./sample-wiki/).

```text
/wiki-generator            # full build of docs/wiki/
/wiki-generator --update   # incremental: re-sync only the pages that drifted
```

- **`@wiki-writer`** authors **one page at a time** from real code — a business
  summary + technical deep-dive + mermaid diagram + schema + related-files
  (referenced by path) + a **"verified against commit"** stamp. For ExampleApp
  you'd get pages like *Organizations & Tenancy*, *Members & Roles*, *Tickets &
  Comments*, and *Billing*.
- **`@wiki-auditor`** powers `--update`: fresh eyes compare each existing page
  against current code → CURRENT / STALE / INCORRECT / ORPHANED, emitting a
  delta list for `@wiki-writer` to fix. This is what makes the wiki
  **self-maintaining** (and schedulable).

---

## Suggested order for a first sitting

1. **Read** the artifacts in lifecycle order so you know the target output:
   `sample-onboarding/` → `sample-issue.md` → `sample-plan.md` →
   `sample-plan-review.md` → `sample-pr-review.md` →
   `sample-security-review.md` → `sample-tests/` →
   `sample-migration-dossier.md` → `sample-release-notes.md` →
   `sample-handoff.md` → `sample-bug-dossier.md` → `sample-wiki/`.
2. **Install** (`install.sh` or the plugin) and wire up **GitHub MCP** +
   **Playwright MCP** (or confirm the `gh` fallback).
3. On a **throwaway repo**, run `/orchestrator --experiment "<small change>"`
   to watch the plan phase with zero side effects.
4. Run a real `/orchestrator <issue>`, then `/bug-catcher "<symptom>"`, then
   `/wiki-generator`.
5. Compare each result against the matching sample artifact above.

> A note on scope: `/orchestrator` is the heavyweight path. For a one-line docs
> or config fix, `/chore` keeps the same commit/push gates without the full
> ceremony — and `/chore --concurrently` lands that fix in an isolated worktree
> so it can ship *while* an `/orchestrator` run is in flight, without colliding
> (see [`sample-concurrent-chore/`](./sample-concurrent-chore/)); for handing the
> work to a fresh agent, `/handoff` writes a self-contained brief.
