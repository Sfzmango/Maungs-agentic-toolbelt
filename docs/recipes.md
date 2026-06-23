# Recipes — composing the toolbelt (synergy tips)

The other docs cover each component on its own: [`components.md`](components.md) is **what** each one is, [`design-philosophy.md`](design-philosophy.md) is **why** it's built this way, and [`getting-started.md`](getting-started.md) is **how to set it up**. This page is the missing piece — **how the components compose into a personal workflow**, so one developer moves like a whole team.

> **New to the toolbelt? Start here.** This page doubles as a guided tour of what the toolbelt can do. Skim the recipes top-to-bottom to see the moves available to you, or jump to the one that matches what you're doing right now. (`/toolbelt` highlights a few of these and links back here.)

Every recipe below is a real chain you can run today. They lean on three pieces of "connective tissue" that make the parts work together:

- **`CLAUDE.md`** — every agent and skill auto-detects the host project's conventions from it. Onboard once and the whole toolbelt speaks your project's language.
- **The prompt-router** (a `UserPromptSubmit` hook) — silently *suggests* the right component when your prompt fits an intent (e.g. "table this for later" → `/todo`). It never auto-runs anything.
- **`/todo`** — a private, per-project backlog that persists across sessions. It's the thread that ties one session to the next and one component to another.

---

## A note on how components interact with your backlog

`/todo` is deliberately a **list-keeper, not a doer** — it records, lists, and edits items, but it never *acts* on one and never writes a plan into itself. Turning a todo into work is always a separate, explicit step you take. What makes it synergize is everything *around* it:

| Mechanism | What it does |
|---|---|
| `SessionStart` loader hook | Adds `Open todos: N (private backlog — /todo to view)` to the session snapshot, so a tabled item resurfaces at the **start of the next session** and can't be silently dropped. |
| Prompt-router | Suggests `/todo` when a prompt sounds like tabling work ("remind me later…", "add this to my backlog"). |
| Conductors read it for context | `/orchestrator`, `/chore`, and `/bug-catcher` may **read** the backlog to guide you — but only you direct what goes on it. |
| Stored outside the repo | The backlog lives under the active product's home directory (per-project), so a private note never leaks into the repo's context, issues, or PRs. |

Keep this division of labor in mind as you read: **`/todo` records; the conductors act.**

---

## Recipe 1 — Onboard first, always

Before you run anything else on a new repo, give the toolbelt a `CLAUDE.md` to read.

```
/agentic-onboard                 # lean: CLAUDE.md + AGENTS.md + a concise module map
/agentic-onboard --deep --target all   # also build a full docs/wiki/
```

**Why it works:** every other component auto-detects stack and conventions from `CLAUDE.md`. Onboarding once is the single highest-leverage thing you can do — it's what lets `@architect`, `@developer`, the reviewers, and the bug-catchers all behave like they already know your codebase. Skip it and each component falls back to generic auto-detection; do it and the whole belt is tuned to your project.

---

## Recipe 2 — The capture → backlog → tackle loop

You're deep in `/orchestrator` and a reviewer (`@pr-reviewer`) flags a real-but-out-of-scope issue. You don't want to derail the current PR — but you don't want to lose the finding either.

| Step | Command | What makes it work |
|---|---|---|
| 1. Capture it the moment it's mentioned | `/todo add <the finding>` | The prompt-router already nudges `/todo` when you say "table this / remind me later." Stored privately, outside the repo — never leaks into the open PR. |
| 2. Forget about it | *(nothing)* | Next session, the `SessionStart` loader resurfaces `Open todos: N (private backlog — /todo to view)`. |
| 3. Come back to it | `/todo` | Lists what you tabled, newest first. |
| 4. Turn it into work | `/chore <it>` (small) · `/orchestrator <it>` (feature) · `/bug-catcher <it>` (bug) | These read the backlog for context but never mutate it — turning a todo into work is always *your* explicit step. |
| 5. Close the loop | `/todo done <id>` | Moves it to Done with a date. |

**The principle:** `/todo` is the connective tissue between sessions and between components — it *records*; the conductors *act*. (This very page was built from a `/todo` backlog this way.)

---

## Recipe 3 — `/todo` as a master personal tracker

Use the backlog as your private, per-project work tracker — the inverse of the ephemeral in-session todo list Claude Code shows while working a task. That one disappears; this one persists and is **yours**.

```
/todo add reword the export-flow docs once the API stabilizes
/todo add revisit the caching strategy — flaky under load
/todo                # review your open list (newest first)
/todo all            # include completed items
/todo done 3         # close one out
/todo drop 5         # remove one (asks to confirm first)
```

**Why it works:** the list is scoped to the current repo (a slug derived from the git root), persists across sessions, and is surfaced at session start by the loader hook — so a thing you tabled three weeks ago greets you when you come back. It's private by design: it never becomes an issue, a PR, or a committed `TODO.md`. Think of it as durable intent that lives *next to* the repo, not in it.

> **Backlog vs. memory:** the backlog holds **transient, completable work items** *you* maintain; auto-memory holds **durable facts and decisions** the agent maintains. A finished todo gets cleared; a memory persists. If you want the agent to *remember a fact*, that's memory — not `/todo`.

---

## Recipe 4 — From a chunky todo → plan → PR

A backlog item is too big to just hand to `/chore`. Promote it through the planning chain — and let `/todo` hold the pointer.

| Step | Command | Result |
|---|---|---|
| 1. The todo is a one-liner | `/todo` shows `(t7) rework the auth-token refresh path` | A terse reminder, no plan. |
| 2. Have an agent draft the plan | `/orchestrator rework the auth-token refresh path` (or `@architect` directly) | `@architect` front-loads the design decisions and writes a plan to `docs/plans/<id>_<slug>.md`; `@plan-reviewer` gives it a cold SOLID/REVISE/RETHINK pass. |
| 3. Point the todo at the plan | `/todo edit 7 rework auth-token refresh — see docs/plans/<id>_<slug>.md` | The plan is the reviewable repo artifact; the todo stays a private pointer to it. |
| 4. Build it | `/orchestrator` continues → `@developer` implements behind commit/push gates → reviewers gate the PR | A merge-ready PR. |
| 5. Close it | `/todo done 7` | Backlog reflects reality. |

**The principle:** the **plan** is a first-class repo artifact (versioned, reviewable); the **todo** is the private bookmark that survives between the day you noticed the work and the day you do it. `/todo` never writes the plan — the workflow does.

---

## Recipe 5 — Bug → fix, end to end

```
/bug-catcher <symptom>        # @bug-catcher-rick diagnoses; @bug-catcher-adversary tries to refute it
                              # → an approved fix plan, handed to /orchestrator or /chore
/bug-catcher --global         # sweep the whole codebase + tests + docs → a severity-ranked backlog
```

**Why it works:** the targeted mode runs a bounded debate (diagnosis vs. cold refutation) so you fix the *root cause*, not a symptom, then hands off the approved plan. The `--global` sweep produces more findings than you can fix at once — so **defer the rest to `/todo`** (`/todo add SEV3: <finding>`) and tackle them on your own cadence. Capture-and-defer keeps the sweep honest without forcing you to fix everything in one sitting.

---

## Recipe 6 — Ship small things in parallel

When you have several independent, chore-sized changes, run them at once instead of in series.

```
/chore --concurrently fix the broken mermaid block in docs/architecture.md
/chore --concurrently bump the lint config to ignore generated files
/chore --concurrently --bypass correct the typo in the install banner   # auto-merge after green CI
```

**Why it works:** `--concurrently` runs each chore in its **own isolated git worktree** off the default branch, so two (or more) can't clobber each other or your main checkout — safe to ship alongside another session. Each opens a summary-only PR; `--bypass` admin-merges once CI is green (the explicit "ship it now" hatch — it skips the human-review gate, never the test gate). This is exactly how the t7–t9 and t4 fixes shipped as two concurrent PRs.

---

## Recipe 7 — Keep docs honest on a schedule

Documentation rots silently. Make keeping it current a background job.

```
/dossier-jobs                 # stand up nightly cloud routines: bug · security · wiki sweeps
                              # → one rolling tracking issue
/wiki-generator --update      # incremental drift-sync + a repo-wide documentation-drift sweep
```

**Why it works:** `/dossier-jobs` schedules cloud routines that sweep the codebase while you sleep and funnel findings into a single tracking issue (the bug routine even opens draft fix PRs for the top non-critical findings). `/wiki-generator --update` re-derives the truth from code via `@wiki-auditor` and routes each fix to the tool that owns the path. Pair it with Recipe 2: when a sweep surfaces something you want to handle yourself, `/todo add` it and pull it into a `/orchestrator` run later.

---

## Recipe 8 — Defer a whole chunk: handoff → backlog → a future run

A PR is merge-ready, but it surfaced a sizeable follow-up — a refactor, a second feature — too big to tack on. Hand it off to your future self without losing the thread.

| Step | Command | What makes it work |
|---|---|---|
| 1. At wrap-up, the conductor offers it | *(suggested by `/orchestrator`)* | After the review/wrap-up phase, `/orchestrator` **suggests** capturing out-of-scope follow-ups — it never writes to the backlog itself. |
| 2. Draft a resume-from-cold brief | `/handoff <topic>` | Writes a self-contained brief a fresh agent can pick up cold — the full context, not just a one-liner. |
| 3. Drop a pointer on your backlog | `/todo add <one-line summary> — see the handoff` | The todo is the short, scannable reminder; the handoff is the deep context it points at. |
| 4. Later, run it off the list | `/todo` → `/orchestrator <the item>` | A future session pulls the item off the backlog and runs it with the handoff as its brief — no re-deriving where you left off. |

**The principle:** the **handoff** carries the *context*, the **todo** carries the *pointer*, and `/orchestrator` only ever *suggests* the capture — turning it into work stays your explicit step.

---

## Recipe 9 — Work dossier findings in the background

Let the scheduled routines find the work while you're elsewhere, then fan the fixes out in parallel.

| Step | Command | What makes it work |
|---|---|---|
| 1. Stand up the nightly sweeps | `/dossier-jobs` | Schedules cloud routines (bug · security · wiki) that sweep the repo and funnel findings into one rolling tracking issue. |
| 2. Triage when you're back | read the tracking issue | One issue, marker-tagged per routine — your queue of candidate work. |
| 3. Fan the safe fixes out | `/chore --concurrently <finding>` ×N | Each chore runs in its **own isolated worktree**, so several fixes proceed at once without colliding — you "work" the backlog in the background. |
| 4. Ship the obvious ones hands-off | `/chore --concurrently --bypass <finding>` | Admin-merges once CI is green — the "ship it now" hatch for low-risk fixes (skips review, never the test gate). |

**The principle:** the routines *generate* a backlog of findings; concurrent chores *drain* it in parallel. Pair with Recipe 2 — anything you'd rather handle yourself, `/todo add` and pull into an `/orchestrator` run later.

---

## Putting it together

A typical week, composed:

1. **`/agentic-onboard`** once per repo — so everything speaks your project's language.
2. **`/orchestrator <issue>`** for features; **`/bug-catcher`** for failures; **`/chore --concurrently`** for the small stuff.
3. **`/todo`** as the spine — capture every out-of-scope finding the agents surface, let the loader resurface it, and pull items into the conductors on your own cadence.
4. **`/dossier-jobs`** + **`/wiki-generator --update`** keeping docs honest in the background.
5. **`@resolution`** → **`/release-notes`** → **`/handoff`** to wrap up and hand off.

Not sure which component fits a given goal? Ask the front door: **`/toolbelt <goal>`** recommends the best-fit component with the exact invocation, and **`/toolbelt status`** checks your environment.

## See also

- [`components.md`](components.md) — the one-table reference index of every component
- [`design-philosophy.md`](design-philosophy.md) — the principles these recipes lean on
- [`getting-started.md`](getting-started.md) — install, auth, and first run
