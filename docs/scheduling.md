# Scheduling `/wiki-generator --update` (self-maintaining wiki)

A wiki is only useful while it tracks the code. The drift-detection machinery already
lives in the wiki side-flow — `@wiki-auditor` classifies each existing page as
`CURRENT`, `STALE`, `INCORRECT`, or `ORPHANED`, and `@wiki-writer` rewrites only the
pages that moved — so the natural next step is to run that incremental pass *on a
schedule* instead of by hand. Wire it to the cadence of your delivery cycle (for
example, at the end of every 2-week sprint) and the wiki re-syncs itself.

This document describes **how to schedule the incremental update**, the **idempotent
flow** a scheduled run performs, what it **requires**, and its **safety posture**.

> **What this repo ships vs. what you wire up.** This repo ships the *schedulable
> design* — the `/wiki-generator --update` entry point, the auditor/writer agents, and
> the config shape below. It does **not** ship a live job pinned to your calendar.
> Standing up an actual recurring run is a **per-environment step**: it depends on your
> daemon, your repo credentials, and which project you point it at. The snippets here
> are project-agnostic templates — fill in the paths and cadence for your environment.

---

## 1. Claude Code supports cron-style background jobs

Claude Code can enqueue a prompt to fire on a recurring wall-clock schedule via its
**task scheduler** (a cron mechanism backed by a running daemon). The relevant
properties:

- **Standard 5-field cron**, evaluated in your **local timezone** —
  `minute hour day-of-month month day-of-week`. No UTC conversion needed.
- **Durable / in-memory.** A durable job is persisted (e.g. to
  `.claude/scheduled_tasks.json`) and survives restarts; an in-memory job lives only
  for the current session. **A self-maintaining wiki wants a durable job.**
- **Daemon-gated.** Jobs only fire while the daemon/REPL is alive and idle (not
  mid-query). If the host is asleep or the daemon is down at fire time, that occurrence
  is skipped — which is exactly why the flow below is built to be idempotent and to
  catch up from the last-synced commit rather than from "14 days ago".

> A scheduled `--update` re-runs the *same prompt* at fixed intervals. That is the
> right tool here: the wiki should re-sync on a calendar boundary, not stream every
> file save. (For live "notify me the instant X changes" watching you'd reach for a
> monitor instead — that is a different use case and not what this doc covers.)

---

## 2. Concrete schedule: every 14 days

A 2-week sprint boundary maps cleanly to a 14-day interval. Cron's day-of-month field
can't express "every 14 days" directly (months aren't 14-divisible), so the robust
pattern is a **weekly trigger guarded by a 2-week parity check**, or simply a job that
fires more often than needed and **no-ops when nothing changed** (the flow in §3 is a
no-op when the wiki is already current — see §4).

Recommended: fire on a fixed weekday and let the idempotent flow decide whether work is
needed. To land on a true 14-day rhythm, gate the run on sprint parity.

```cron
# Every other Monday at 09:13 local — end-of-sprint wiki sync.
# (Off-minute on purpose: avoid the :00 stampede where every job on the
#  planet hits at the same instant.)
13 9 * * 1
```

If your scheduler doesn't support bi-weekly parity natively, fire **weekly** and let
the parity guard (or the "nothing changed → no-op" property) absorb the off-week:

```cron
# Every Monday 09:13 local; the run itself no-ops if the wiki is already
# in sync with HEAD, so an off-sprint week is cheap.
13 9 * * 1
```

> Pick an **off-minute** (here `:13`, not `:00`/`:30`). Round times concentrate load;
> a few minutes of jitter is invisible to humans and kinder to shared infrastructure.

---

## 3. Sample config snippet

The scheduled job is just a stored prompt plus a cron expression. Conceptually:

```jsonc
// .claude/scheduled_tasks.json  (illustrative shape — adapt to your environment)
{
  "tasks": [
    {
      "id": "wiki-sync-biweekly",
      "cron": "13 9 * * 1",          // every Monday 09:13 local (see §2 for bi-weekly)
      "recurring": true,
      "durable": true,                // survive daemon/session restarts
      "timezone": "local",
      "project": "/abs/path/to/target-repo",   // the repo whose wiki self-maintains
      "prompt": "/wiki-generator --update --since last-synced --open-pr"
    }
  ]
}
```

The load-bearing parts:

- **`durable: true`** — the wiki should keep syncing across restarts, not vanish with a
  session.
- **`project`** — the **target repo** whose `docs/wiki/` is maintained. The scheduler
  must have working-tree access to it (see §5).
- **`prompt`** — invokes the existing incremental entry point. `--since last-synced`
  tells it to diff from the commit the wiki was last verified against (not a fixed time
  window), and `--open-pr` keeps it in propose-only mode (see §6).

> Field names above are illustrative. The contract that matters: a durable, recurring,
> local-time cron entry that runs `/wiki-generator --update` against one configured
> project and opens a PR rather than pushing.

---

## 4. The idempotent flow a scheduled run performs

Every scheduled occurrence runs the same four steps, and the run is a **no-op when the
wiki is already current** — so re-running it (after a skipped occurrence, a retry, or
two fires in one sprint) never double-writes or corrupts state.

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. DIFF since last-synced SHA                                         │
│    Read the "verified against commit <sha>" stamp on existing wiki    │
│    pages → git diff <last-synced-sha>..HEAD → set of changed paths.   │
│    If HEAD == last-synced-sha for every page → NOTHING CHANGED → exit │
│    cleanly (no PR, no commit). This is what makes off-sprint fires    │
│    and catch-up runs cheap and safe.                                  │
├─────────────────────────────────────────────────────────────────────┤
│ 2. AUDIT the affected pages (@wiki-auditor)                           │
│    For each wiki page touching a changed path, classify against       │
│    current code: CURRENT / STALE / INCORRECT / ORPHANED, with a       │
│    per-page delta list. CURRENT pages are left untouched.             │
├─────────────────────────────────────────────────────────────────────┤
│ 3. REWRITE only the stale pages (@wiki-writer)                        │
│    For each STALE/INCORRECT page, rewrite from real code and re-stamp  │
│    "verified against commit HEAD". ORPHANED pages are flagged for      │
│    removal. Untouched pages keep their old stamp — the diff stays      │
│    minimal and reviewable.                                            │
├─────────────────────────────────────────────────────────────────────┤
│ 4. OPEN a wiki-sync PR for human review                               │
│    Commit the rewritten pages on a branch (e.g. wiki-sync/<date>) and  │
│    open a PR. If a previous open wiki-sync PR exists, update it rather │
│    than stacking duplicates. Then exit.                               │
└─────────────────────────────────────────────────────────────────────┘
```

Why this is idempotent:

- It keys off the **last-synced SHA stamped on the pages**, not off the clock. Two runs
  against the same `HEAD` produce the same result — the second sees nothing changed and
  exits.
- It rewrites **only** pages the auditor marks non-`CURRENT`, so an unnecessary run
  touches nothing.
- It **reuses** the existing open wiki-sync PR instead of opening a new one each fire,
  so a missed-then-caught-up cadence converges to a single PR rather than a pile.

---

## 5. Requirements

To stand up a live scheduled run you need all of:

1. **A running daemon.** The scheduler only fires while the Claude Code daemon/REPL is
   alive and idle. A laptop that sleeps will skip occurrences — prefer an always-on host
   (or accept that the idempotent flow catches up on the next successful fire).
2. **Repo access.** The job needs a working-tree checkout of the target repo plus
   credentials to **read code, push a branch, and open a PR** (e.g. a `gh`/token with
   `contents` + `pull_requests` scope). It does **not** need permission to push to the
   default branch.
3. **A configured target project.** Exactly one repo per job, pointed at via the
   `project` path. That repo must already have a wiki (run a full `/wiki-generator`
   build once) so there are stamped pages to diff against. Without an initial build,
   the first scheduled `--update` has no last-synced SHA to anchor on.

---

## 6. Safety posture: propose, never force-push

The scheduled run is deliberately **propose-only**:

- It writes changes onto a **dedicated branch** and **opens a PR** for human review. It
  **does not** commit to the default branch and **does not** force-push.
- A human reviews and merges the wiki-sync PR. The schedule keeps the wiki *fresh*; it
  does not grant an unattended job authority to mutate your main branch.
- If nothing changed, it opens **no PR** (see §4) — no empty-diff noise.
- Because the flow is idempotent and PR-gated, a misfire, a double-fire, or a
  catch-up after downtime is harmless: worst case you get one wiki-sync PR to review,
  never a surprise rewrite of `main`.

In short: **the daemon proposes, a human disposes.** Automation handles the tedious
diff-audit-rewrite loop on every sprint boundary; the merge decision stays with a
person.

---

## 7. Wiring it up (per-environment checklist)

This repo ships the design and the config shape. To make it live in *your* environment:

1. Run a one-time full build: `/wiki-generator` against the target repo (creates
   `docs/wiki/` with stamped pages).
2. Add a **durable, recurring** scheduler entry like §3, pointed at that repo, running
   `/wiki-generator --update --open-pr`.
3. Pick a cadence (§2) on a sprint boundary, using an off-minute.
4. Ensure the daemon runs on an always-on host with repo + PR credentials (§5).
5. Review and merge the wiki-sync PR each sprint.

Everything above the checklist is portable and project-agnostic; only steps 1–4 are
environment-specific.
