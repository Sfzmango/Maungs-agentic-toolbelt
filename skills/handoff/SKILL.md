---
name: handoff
description: Write a Claude Code handoff document for the current project — a self-contained brief that lets a fresh agent pick up specific work cold. Invoke as `/handoff <issue-id-or-topic>` or when the user explicitly asks you to write a handoff (NEVER proactively — see cardinal rule below).
disable-model-invocation: false
---

# /handoff — write a project handoff document

The user invokes this as `/handoff <issue-id-or-topic>` or by typing a phrase like "write a handoff for issue 3" / "draft a handoff for the contact refactor." The argument is in `$ARGUMENTS` — extract the numeric issue ID if it's a bare number, otherwise treat it as a free-text topic.

You are producing a single file at `HANDOFF_<UPPERCASE_SLUG>.md` (or the project's existing handoff path convention — see Step 4 below) that briefs a fresh agent with zero context. The fresh agent will read ONLY this handoff + the files it points at; they will not see the conversation that produced it.

---

## Cardinal rule — never write proactively

You may only invoke this skill when the user has **explicitly** asked for a handoff in the current turn. Triggers:
- They typed `/handoff <...>` directly.
- They said "write a handoff for X" / "draft a handoff" / "create a Claude Code handoff" / equivalent.

Do NOT invoke this skill because the conversation feels like it produced handoff-worthy content. Do NOT auto-write a handoff at the end of a planning session as a "nice-to-have." Stale handoffs are worse than no handoffs — they get followed confidently with wrong instructions. The user owns the decision to materialize a handoff.

If you're tempted to suggest a handoff at the end of unrelated work, offer it as a single-line option ("Want me to write up a handoff for this?") — never spawn one without a fresh yes.

---

## Step 1 — Acknowledge and parse input

State back the topic/ID you parsed in one sentence so the user can catch a wrong target before you start gathering context.

Examples:
- "Drafting a handoff for issue 3." (numeric → assume GitHub/Linear/Jira issue ID; auto-detect source in Step 3)
- "Drafting a handoff for: contact-and-address refactor." (non-numeric → free-text topic)

If no argument: ask once for the topic, then proceed.

---

## Step 2 — Cardinal-rules audit of the project

Before gathering anything else, read the project's agent-context files in this order:

1. `CLAUDE.md` (or `claude.md`, case-insensitive) — public agent context.
2. `CLAUDE.local.md` if it exists — personal/owner override layer. On any conflict, the local file wins.
3. Any plan file the project uses as its source of truth — common names: `DEVELOPMENT_PLAN.md`, `ARCHITECTURE.md`, `PLAN.md`, `ROADMAP.md`, `docs/architecture.md`. Look for the one that's clearly the canonical project plan.
4. Any personal mirror of the plan — `EXECUTION_PLAN.md`, `INTERNAL_PLAN.md` — same gitignored-personal pattern.

Capture the cardinal rules / non-negotiable conventions (test gate behavior, commit/push confirmation policy, force-push discipline, attribution policy, mobile-responsive requirements, etc.). The handoff must surface these prominently — every fresh agent has to obey them.

If neither `CLAUDE.md` nor an obvious plan file exists, the project doesn't have an agent-context discipline yet. Surface this to the user before drafting; the handoff can still happen but will be skinnier (no "read these first" list).

---

## Step 3 — Auto-gather context (heavy)

Run these in parallel (single Bash call with `&&` chaining or multiple parallel calls):

```bash
git rev-parse --abbrev-ref HEAD             # current branch
git status                                  # working tree state
git log --oneline -10 main 2>/dev/null || git log --oneline -10  # recent commits
git branch -a --sort=-committerdate | head -20  # in-flight branches
```

If `gh` is available AND the repo is on GitHub (check `git remote -v`):

```bash
gh pr list --state open --limit 10            # in-flight PRs
gh pr list --state merged --limit 5           # recent merges
gh issue view <id> --json title,body,state,assignees,url   # if argument was numeric
```

If the argument looks like a Linear ticket key (e.g. `ENG-123`), try the Linear MCP if connected. Same for Jira (`PROJ-456`).

Scan for project-specific signals:

- `Procfile` (Heroku), `Dockerfile`, `fly.toml`, `vercel.json` → deployment context
- `Gemfile` / `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` → language/framework
- `spec/`, `test/`, `tests/`, `__tests__/` → test framework
- `.github/workflows/` → CI setup
- `docs/plans/` or `docs/proposals/` → per-issue architecture-plan convention
- Existing `HANDOFF_*.md` files at repo root → naming convention to match

Don't over-fetch. If the user gave a tight topic ("draft a handoff for the payments refactor") you don't need the full GitHub state.

**Surface non-obvious operational state.** This is the single most-valuable thing a handoff carries. Examples from prior projects:
- "Hotfix PR X is in flight at branch Y; new work assumes it merges first."
- "Prod was rebuilt on YYYY-MM-DD; there are no real users."
- "The deployment release-phase migration was added on YYYY-MM-DD; pre-existing deploys did not run migrations."
- "A subagent review surfaced N concerns that are intentionally deferred to a follow-up issue."

If you notice operational state like this during your context gathering, flag it explicitly in the handoff — the next agent has no way to discover it from code alone.

---

## Step 4 — Pick the output path

Detect the project's existing handoff convention:

- If `HANDOFF_*.md` files exist at repo root → use that pattern. Filename: `HANDOFF_<UPPERCASE_SCREAMING_SNAKE_SLUG>.md` (e.g., `docs/handoffs/team-invitations-step3.md`).
- If `docs/handoffs/*.md` exists → use that. Filename: `docs/handoffs/<lowercase-kebab-slug>.md`.
- If `.handoffs/` exists → use that.
- Otherwise → default to `HANDOFF_<UPPERCASE_SLUG>.md` at repo root and surface that choice to the user.

Check the project's `.gitignore` for an existing pattern (`/HANDOFF_*.md` or `/docs/handoffs/`). If handoffs are gitignored in the project, mention that fact in the chat output. If they're NOT gitignored and the user might want them to be, ask once.

**If the target file already exists**, do not silently overwrite. Show the user the existing file's first 20 lines + ask whether to (a) overwrite, (b) append a new section, (c) write to a new filename with a suffix, or (d) abort.

---

## Step 5 — Draft the outline, gate before writing

Draft an outline as a structured chat message — section names + 2–5 bullets per section showing what content will go in each. Use the canonical template below. Adapt freely based on Step 3's findings; omit sections that don't apply (e.g., "Operational tail" can be empty if there's no deploy story worth surfacing).

**Canonical template** (all sections optional except the first and last):

1. **Top brief** (1 paragraph) + **single entry-point command** the receiving agent should run (`/orchestrator 3`, `npm run dev`, "open issue X", etc.)
2. **Read these first — in order** — numbered list of files the fresh agent must read. Always include CLAUDE.md / CLAUDE.local.md if they exist + the project's canonical plan file + any per-issue plan doc that's already in place.
3. **Pre-flight checks** — what the agent should verify before starting (MCP server connectivity if relevant, expected current state of `main`, in-flight branches / PRs, operational state from Step 3).
4. **Recent history (what's already done — do NOT redo)** — condensed summary of prior work that produced the current state. The fresh agent needs this so they don't accidentally re-do something or assume something hasn't shipped.
5. **Scope** — what IS being built + what is EXPLICITLY out of scope. Out-of-scope is as important as in-scope; protects the agent from quietly expanding.
6. **Open decisions to surface at planning time** — N concrete things the user (not the agent) should decide. Each one phrased as a question with 2–4 enumerated options. Tells the agent "stop and ask here" rather than picking silently.
7. **Workflow walkthrough** — how the receiving agent should drive the work. Often just a pointer at the project's existing workflow skill ("`/orchestrator` 13-step workflow — see `.claude/skills/orchestrator/SKILL.md`"); sometimes a custom sequence for the specific handoff.
8. **Recurring patterns to apply by default** — patterns that emerged from prior iterations that the receiving agent should bake in without re-deriving (cross-org spec patterns, test-flake mitigations, attribution rules, force-push discipline, etc.). Cross-link to memory files or to existing pattern sections in the project's skill files when possible.
9. **What to surface during execution** — specific gotchas + things the agent should flag to the user mid-work (migration ordering, signup-transaction extension points, etc.).
10. **Operational tail** — deployment story, post-merge ops, prod-state assumptions, monitoring URLs, anything else the agent needs to think about after their PR merges.
11. **When this handoff is wrong** — drift-detection clauses: "if Procfile on main does NOT contain X, the hotfix hasn't merged yet"; "if `git log` shows commits beyond SHA Y, new work has landed." Gives the receiving agent a way to notice the handoff has gone stale.
12. **End-of-file marker** — repeat the single entry-point command from the top brief so the agent leaves the handoff knowing the next action.

Then call `AskUserQuestion` with:

- **Approve outline — write the full file**
- **Request changes** (user describes in chat what to change)
- **Abort**

Do NOT call `Write` until the user has explicitly approved the outline.

---

## Step 6 — Write the file

After approval, write the full file at the path picked in Step 4. Tone guidelines:

- **Self-contained.** Assume zero conversation context. Anything that can't be re-derived from the files referenced in section 2 must be spelled out in this handoff.
- **Tight prose, not bullets-everywhere.** Use paragraphs for narrative sections (Recent history, Scope, Operational tail). Use bullets for enumerable lists (Open decisions, Recurring patterns).
- **Cite paths + commits + SHAs precisely.** "`f2062a6`", "`app/services/billing/generate_invoice.rb`", "`docs/plans/42_team-invitations.md`", "PR #14." A handoff with vague references ("the auth files") is one the next agent has to re-discover.
- **No marketing tone, no padding.** "This comprehensive guide will walk you through..." is noise. Say what's true; the next agent will read it.
- **No attribution footers.** No `Co-Authored-By: Claude`, no `🤖 Generated with Claude Code`. Check the project's `CLAUDE.md` / memory for an attribution policy; respect it. Default is no attribution.
- **No fabrication.** If you don't know something, say "ask the user" or "check X to find out" rather than making it up. Stale-but-confident handoffs are worse than honest gaps.
- **Adapt length to scope.** A focused single-issue handoff is ~200–300 lines. A multi-part 3-issue handoff might be ~600 lines. A trivial-topic handoff might be ~80 lines. Don't pad to hit a target.

After writing, open the file in the user's IDE via `code <path>` if the `code` CLI is available. Don't dump the full handoff into chat — post a 3–6 bullet summary instead (sections covered, file path, recommended next action).

---

## Step 7 — Post-write follow-ups

In the chat summary, surface:

1. The full path to the new handoff.
2. Whether it's gitignored or tracked.
3. Any open decisions from section 6 that need user action before the receiving agent can start (e.g., "Decision 2 asks whether to merge the hotfix PR first — that's a you-call, not the next agent's call").
4. The single entry-point command repeated from the top brief.
5. If you noticed handoff-adjacent files (existing handoffs, memory files, plan files) that should be updated as part of writing this one — flag them, but do NOT silently edit them.

Do NOT commit the file. The user will commit (or not commit, since handoffs are usually gitignored).

---

## When something goes wrong

- **No `CLAUDE.md` / no plan file found:** the project doesn't have an agent-context discipline. Surface this; offer to write a thinner handoff that just covers Step 3's auto-gathered git/PR state. Don't pretend the project has conventions it doesn't.
- **Issue ID doesn't resolve in any tracker:** surface the error, ask the user for the canonical title + scope, write the handoff as a free-text topic instead.
- **Existing handoff file at target path:** do not overwrite. Step 4 already covers this — re-prompt.
- **User asks for a "quick" or "lightweight" handoff:** still draft the outline at Step 5 (gate behavior is non-negotiable), but propose a 2–3 section template (top brief + scope + entry-point command) rather than the full 12-section structure. The gate ensures the user actually gets what they asked for.
- **Project has multiple competing plan files** (e.g., `DEVELOPMENT_PLAN.md` AND `ROADMAP.md` AND `docs/architecture.md`): list them in section 2 in the order the user should read; surface in chat which file you treated as canonical.
- **Tempted to also write a Claude-Code-handoff and a separate engineer-readable doc:** don't. The handoff IS the document. One file, one purpose. If the user wants a different audience they'll ask for a separate doc.
