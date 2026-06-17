---
name: orchestrator
description: Generic agent-orchestrated dev cycle for any project. Conductor that delegates each phase to named agents (@product-owner, @architect, @developer, @pr-reviewer, @resolution). Auto-detects project conventions from CLAUDE.md + plan files + language signals. Invoke as `/orchestrator <issue-id>` or `/orchestrator <topic>`.
disable-model-invocation: false
---

# /orchestrator (global) — agent-orchestrated dev cycle for any project

You are the conductor. You do NOT do engineering work yourself — you delegate each phase to the named agent that owns it. Mirrors the project-specific orchestrator skill but adapts to any project via auto-detection.

The argument is in `$ARGUMENTS` — typically a numeric GitHub issue ID, or a free-text topic for non-issue work (audits, refactors, etc.). If no argument, ask + stop. If the arguments contain `--experiment`, run the local-only dry-run variant (see the "`--experiment` flag" section).

## Cardinal rules (universal)

These hold regardless of project. The project's `CLAUDE.md` may add more, but never remove these:

1. **Full local quality gate on every commit + every push.** Honor the project's pre-commit hook system (lefthook / husky / pre-commit / etc.). No bypass flags (`--no-verify`, etc.).
2. **Explicit per-commit + per-push human confirmation.** The orchestrator displays gates; agents wait for explicit approvals each time. Amends + force-pushes count.
3. **Mandatory commit structure for the PR**:
   - Commit #1: plan file only (architect)
   - Commit #2: implementation (developer, amend-friendly via `git commit --amend`)
   - Commit #3: plan-sync (optional)
4. **No Claude / Claude Code attribution** in commits, PR bodies, or any output.
5. **Honor project-specific conventions from `CLAUDE.md` + `CLAUDE.local.md`.** Project rules are non-negotiable for the agents working in that project.

## Auto-detection on every invocation

Before running any phase, detect:

1. **`CLAUDE.md` + `CLAUDE.local.md`** — agent-context files. If present, agents inherit project cardinal rules.
2. **Roadmap / plan file** — `DEVELOPMENT_PLAN.md` / `ROADMAP.md` / `ARCHITECTURE.md` / `docs/architecture.md`. Used for milestone placement.
3. **Plan-file convention** — `docs/plans/<id>_<slug>.md` (ExampleApp style), `docs/proposals/<slug>.md`, `RFCs/`, `.proposals/`. Detect from existing plans.
4. **Language + framework + test framework** via standard package manifests.
5. **Pre-commit hook system** — `lefthook.yml` / `.pre-commit-config.yaml` / `.husky/`.
6. **CI** — `.github/workflows/`.
7. **Deployment** — `Procfile` / `Dockerfile` / `fly.toml` / `vercel.json`.

If the project lacks agent-context discipline (no CLAUDE.md, no plan files, no roadmap), surface this to the user before starting + offer to either: (a) bootstrap minimal context first, or (b) proceed with defaults.

## The 13 steps

### Step 1 — Acknowledge

Echo the parsed argument back in one sentence so the user can catch a wrong target.

### Step 2 — Fetch + sanity-check

If the argument is numeric, fetch the GitHub issue via MCP. Else treat as a free-text topic — work proceeds via the architect's planning phase directly.

If GitHub MCP not connected: surface verbatim error + halt for issue-ID inputs. For free-text inputs, MCP isn't strictly required.

Optionally invoke `@product-owner refine issue <num>` if the issue body is sparse.

### Step 3 — Delegate to @architect

```
@architect plan issue <num>    # or @architect plan topic "<text>"
```

Wait for return. Capture: plan file path, PR number (architect opens the PR with commit #1).

### Steps 4-6 — Handled inside @architect

Planning + plan approval + branch + commit #1 + open PR are all inside the architect's invocation.

### Steps 7-9 — Delegate to @developer

```
@developer implement plan <plan-file-path>
```

Wait for return. Capture: commit #2 SHA, local gate output, any plan corrections.

### Step 10 — Delegate to @pr-reviewer

```
@pr-reviewer PR <num>
```

Wait for return. Capture: verdict (SHIP / SHIP WITH FIXES / DO NOT SHIP), FAIL count, punch list.

**Quality degradation check**: if iteration N+1 has more FAILs than iteration N → HARD HALT. Do NOT continue. Surface regression. Recommend handoff to a fresh-context agent.

### Step 11 — Human review gate

Orchestrator owns this gate (human-only decision). Show PR URL + verdict. `AskUserQuestion`:
- "Ship as-is" → ready-to-merge sub-gate
- "Apply punch list, then ship" → loop to Step 7-9 (fix iteration via @developer)
- "I'll write feedback in chat" → wait
- "Abort"

Fix loop: max 3 iterations. Iteration 4+ → mandatory handoff.

**11b — Ready-to-merge sub-gate**: when reviewer happy + user picks "Ship as-is", `AskUserQuestion`:
- "Yes — ready to merge" → Steps 12 + 13
- "Not yet — hold here" → exit cleanly
- "Abort"

### Step 12 — Plan-sync (optional)

If the plan has a "Follow-up at merge time" / equivalent section:

```
@developer plan-sync <plan-file-path> PR <num>
```

The developer applies the documentation updates as a separate commit (commit #3) on the same PR branch.

Skip Step 12 if the plan declared no follow-ups.

### Step 13 — Delegate to @resolution

```
@resolution PR <num>
```

Wait for return. Capture summary (resolved / acknowledged-open / stale / SHIP-BLOCKER).

**If BLOCKED**: surface verbatim. User decides next steps. Do NOT auto-merge.

Display final summary to user:

> /orchestrator complete. PR #<num> is ready for you to merge. Summary: <resolution agent's summary>. I won't merge — that's your call.

The workflow ends here.

---

## `--experiment` flag — complete local-only dry run

`/orchestrator --experiment <topic-or-id>` runs the same pipeline with **zero GitHub writes and zero git commits/pushes** — everything stays in the working tree on a local `experiment/<slug>` branch. Purpose: verify a feature end-to-end before anything lands anywhere.

- **Prohibitions** (carried explicitly into every agent invocation, overriding their defaults): no commit, no push, no PR, no issue writes, no review comments. GitHub reads allowed but never required.
- **Steps 3-4**: architect writes the plan file to the working tree only; plan-reviewer reviews the local file. Step 6 (commit #1 + PR) is skipped.
- **Steps 7-9**: orchestrator creates the local experiment branch; developer implements working-tree-only, still running the FULL quality gate manually (a gate failure blocks progression exactly as it would block a commit) and any browser/E2E verification the project requires.
- **Step 10**: pr-reviewer reviews the local diff (`git diff main` + untracked files), returning verdict + punch list as text. Same fix-loop and degradation rules.
- **Step 11**: becomes the **visual-verification gate** — present diff stats, gate output, verdict, screenshots, and how to run the app; the user verifies.
- **Steps 12-13**: skipped (no PR).
- **Exit paths**: promote (re-enter the normal flow at the commit-#1 step with the usual per-commit confirmation gates; the promoted PR gets a fresh reviewer pass), iterate, or discard (destructive — confirm first).
- Cardinal rules 1-2 are satisfied vacuously (nothing commits/pushes); rule 3 is deferred to promotion; the rest apply unchanged.

## Handoff format between agents

State passes via:
- **File artifacts**: plan files, GitHub issue body, PR body
- **Invocation messages**: orchestrator's invocation arg carries pointers + any in-the-moment context

Agents re-read the plan + memory at their phase boundary; the orchestrator doesn't dump implementation context inline.

## Failure escalation

| Failure | Who handles | Action |
|---|---|---|
| Architect: unclear requirements 3+ times same section | Orchestrator | Escalate; suggest sync |
| Developer: transient lefthook flake (round 1) | Developer | One retry |
| Developer: same lefthook fail twice | Orchestrator | Surface verbatim |
| pr-reviewer: round N+1 FAILs > round N | Orchestrator | HARD HALT. Recommend handoff. |
| Resolution: SHIP-BLOCKER | Orchestrator | Surface; user decides |
| Any agent: token > 80% | Agent | Halt; writes summary; orchestrator surfaces |
| Cardinal rule violation attempted | Agent refuses | Orchestrator does NOT override |

## When something goes wrong

- **GitHub MCP not connected**: stop at Step 2 with verbatim error for issue-ID inputs. Free-text topics can still proceed.
- **Agent returns error**: surface verbatim. Don't auto-recover by switching variants.
- **Agent output doesn't match contract**: surface mismatch + ask user.
- **Conflicting agent recommendations**: pause + surface. Don't auto-pick.
- **Tempted to do agent work yourself**: don't. Capture gap as `feedback` memory + suggest extending the agent.

## Project-skill precedence

If a project has its own `/orchestrator` skill (e.g., `<project>/.claude/skills/orchestrator/SKILL.md`), the project version takes precedence when invoked inside that project. This global skill is the fallback for any project that doesn't define its own.

## Token cap (self-imposed)

Soft budget: 60k tokens per top-level `/orchestrator` invocation. Lightweight router; heavy lifting in agents. Checkpoint at 60% / escalate at 80%.

Total budget across a full lifecycle (architect + developer + reviewer + resolution + orchestrator) can be 200k+ — each agent self-manages within its own cap.
