---
name: chore
description: Lightweight workflow for small, one-off chore PRs (docs, config, tooling, comment/typo fixes, agent/skill edits, trivial dependency bumps) that don't warrant the full @orchestrator pipeline. No plan file, no architect/developer/reviewer agents — you do the change inline, honor the commit/push gates, open a summary-only PR, and merge after green CI. `--concurrently` runs the whole chore in an isolated git worktree off the default branch so it's safe to ship alongside another session/agent working in the same checkout; `--bypass` (with `--concurrently`) admin-merges automatically once CI is green — an explicit "ship it now" hatch that skips the human-review gate, never the test gate. Invoke as `@chore <short description>`, `@chore --concurrently <description>`, or `@chore --concurrently --bypass <description>`.
---

# @chore — lightweight one-off chore PRs

The argument is in `$ARGUMENTS` — a short free-text description of the chore, optionally preceded by flags. If there's no description (empty, or only flags), ask what the chore is and stop.

**Parse flags first, then treat the remaining text as the description:**
- `--concurrently` — run the chore in an isolated git worktree off the default branch instead of editing the shared checkout in place. Use it whenever another session or agent may be working in the same working tree (or just to keep the active checkout untouched). See **Flags** below.
- `--bypass` — only meaningful together with `--concurrently`: once CI is green, admin-merge the PR automatically, skipping the human-review / branch-protection gate. The "I want this out ASAP" hatch, for changes that are 100% safe (a typo, a doc tweak). If `--bypass` is passed alone, treat it as `--concurrently --bypass` (an auto-merge always uses the isolated path). See **Flags** below.

An unrecognized `--flag` → echo it and stop; do not guess intent.

You do this work **inline** — no architect plan, no adversarial review. The whole point is to stay lightweight for changes that are too small to justify `@orchestrator`. But the project's cardinal rules still apply in full; "lightweight" never means "skip the gates."

## Auto-detection on every invocation

Before starting, detect the project's shape so the gates and conventions are right:

1. **`AGENTS.md / CLAUDE.md` + `CLAUDE.local.md`** — the project's cardinal rules and conventions. They override anything here on conflict.
2. **Pre-commit hook system** — `lefthook.yml` / `.pre-commit-config.yaml` / `.husky/` — this is the local quality gate that runs on commit and push. Honor it; never bypass.
3. **CI** — `.github/workflows/` — what must go green before merge.
4. **Default branch** — usually `main` (confirm via `git`); branch off it and target it.
5. **The project's auto-memory directory** (`~/.claude/projects/<project-slug>/memory/`) — captured feedback (commit-message style, PR-body conventions, attribution rules).

## Cardinal rules (non-negotiable — inherited from the project's AGENTS.md / CLAUDE.md / CLAUDE.local.md)

1. **Full local quality gate on every commit and every push** (whatever the project's pre-commit hook system runs — lint, build, full test suite). No bypass flags (`--no-verify`, etc.).
2. **Explicit per-commit AND per-push human confirmation.** Separate gates, fresh affirmation each time ("yes commit" / "yes push"). Never bundle them; never infer approval from an earlier "go."
3. **No Claude / Claude Code attribution** in commits, PR bodies, or output.
4. **Force-push uses `--force-with-lease`, never `--force`** (rarely needed for a chore).
5. **PR body is a factual summary only** — `Summary` + `Scope`; no agent/process references, no pivot / "how we got here" narrative, no reviewer-focus section.
6. **Never bundle unrelated changes.** Stage only the files this chore touches, even if the working tree carries other local edits.

## Is it actually a chore? (gate before starting)

Use `@chore` only when ALL of these hold:

- Single concern, small diff (roughly one file to a handful).
- No architectural decision to make, no migration, no new app behavior that needs a test or review.
- Low blast radius: docs, comments, README/SETUP, config, CI / pre-commit-hook tweaks, agent/skill definitions, a trivial dependency bump, a lint-fix.

If it touches app behavior that needs a plan, a migration, multi-file feature work, or anything security-sensitive → **stop and recommend `@orchestrator <id>` instead.** When in doubt, say so and let the user pick. A chore that grows mid-flight should be re-routed, not forced through.

## Flags — `--concurrently` and `--bypass`

Both are opt-in, per-invocation, and OFF by default. They change *where* the work happens and *how* it merges — never *whether* the safety checks run.

### `--concurrently` — isolated, conflict-free chore alongside other work

The default flow (Step 3) runs `git checkout -b` in the current checkout, which moves `HEAD` for the whole working tree — unsafe when another session or agent is mid-edit there. `--concurrently` instead does the entire chore in a throwaway **git worktree** based on the freshly-fetched default branch, so the active checkout's `HEAD`, index, and uncommitted edits are never touched.

- **Assume concurrency from the start — expect a dirty shared checkout.** Initialize on the premise that other sessions/agents are active, so the shared working tree will likely look *very* dirty: a `git status` full of unfamiliar modified/untracked files, a "N uncommitted changes" warning on `gh`. That is **expected and not a problem** — those edits belong to the other sessions. Do NOT treat the dirty tree as an error or anomaly, do NOT investigate it, and never clean / stash / reset / `git add` from it. Your status of record is your worktree's (`git -C <tmp-path> status`), which starts clean off the default branch — reason about *that*, not the shared checkout's noise.
- **Set up:** `git fetch origin <default-branch>` then `git worktree add -b chore/<slug> <tmp-path> origin/<default-branch>` (a path under the system temp dir, never inside the repo). This is your own isolated little workspace; everything below happens inside it.
- **Work in the worktree:** make the edit, stage ONLY the chore's files, commit, and push the branch — all via `git -C <tmp-path> …` so you never `cd` (or move `HEAD` in) the shared checkout.
- **Base off the default branch, not the in-progress branch**, so the chore is independent of whatever the other session is building and can merge on its own.
- **Tear down:** after the PR is open (and merged, if `--bypass`), `git worktree remove <tmp-path>`. Keep the branch — the PR needs it. Never leave an orphan worktree.
- **Overlap check:** if the chore touches a file the other in-flight branch also changed, say so — whoever merges first wins and the other side rebases. Low risk for docs/config, but flag it.

Everything else (the commit/push gates, summary-only PR, scoped staging) is unchanged — `--concurrently` only relocates the work to a worktree.

### `--bypass` — auto-merge once CI is green (the ASAP hatch)

`--bypass` means: the human has authorized the full commit → push → merge tail up front by passing the flag, so proceed without the per-step prompts AND merge automatically via an admin override the moment CI passes — even on a branch whose protection requires a review the author can't self-approve. Use it only for changes that genuinely cannot break anything (a typo, a comment, a doc line).

**What it bypasses:** the human-review / branch-protection *approval* requirement, plus the interactive commit/push gates (the flag is the explicit standing authorization for this one run). This does not violate the "explicit confirmation" cardinal rule — the flag is an unambiguous, per-invocation authorization, not an inferred "ok" or silence; that rule exists to forbid *ambiguous* or *stale* consent, which `--bypass` is not.

**What it NEVER bypasses — hard lines, even for an ASAP merge:**
- **CI must be GREEN.** Wait for the checks to finish; if any fail or error, **halt and surface verbatim — do NOT merge.** Shipping a red build breaks the default branch for the concurrent session too, which defeats the point. "Skip review" never means "skip the tests."
- **The "is it actually a chore?" gate** still applies — `--bypass` is about the merge, not about widening scope. A change that isn't chore-sized still re-routes to `@orchestrator`.
- **No `--no-verify`, no `git add -A`/`.`, no `git push --force`** (cardinal rules 1, 4, 6 stand).
- **No AI attribution** anywhere.

**How to merge:** once CI is green, `gh pr merge <n> --squash --admin --delete-branch` (or the GitHub MCP merge with the admin override). This requires the authenticated account to actually hold admin on the repo; if branch protection has `enforce_admins` enabled, even an admin merge is refused — **surface that verbatim, do not pretend it merged.**

**Be loud + auditable.** State explicitly in the output that the merge bypassed branch protection, which rule it overrode, and that CI was green at merge time. An ASAP merge is fine; a silent one is not.

## Steps

### 1 — Acknowledge + scope

Restate the chore in one sentence. Confirm it passes the "is it a chore?" gate; if not, recommend `@orchestrator` and stop. Identify the exact file(s) to change.

### 2 — Make the change inline

Edit the file(s). Keep it strictly scoped to the one concern. If the change reveals it's bigger than a chore, stop and re-route. (In `--concurrently` mode, create the worktree from Step 3 **first**, then make this edit inside it — so nothing lands in the shared checkout.)

### 3 — Branch (mode-aware)

- **Default (in-place):** `git checkout -b chore/<short-slug> origin/<default-branch>` (branch off the current trunk; the working-tree edit rides along). Verify with `git status` that only the intended files are modified — if other local changes are present, you'll stage selectively in step 4, never bundle.
- **`--concurrently`:** do NOT `checkout` in the shared tree. `git fetch origin <default-branch>` then `git worktree add -b chore/<short-slug> <tmp-path> origin/<default-branch>`, and make the Step 2 edit inside `<tmp-path>` (read the file there for an exact-match edit). Every subsequent git command uses `git -C <tmp-path> …`. See **Flags**.

### 4 — Commit gate

Show: (a) the file list (`git status --short` + `git diff --stat`, scoped to this chore's files), (b) the proposed commit message — `chore: <subject>` with a concise 1–2 sentence body if needed, (c) the target branch. Stage ONLY this chore's files (`git add <paths>`, not `-A`, if other edits exist). Wait for explicit **"yes commit."** The pre-commit hook runs the local gate on commit; surface any failure verbatim (don't bypass). **With `--bypass`:** the flag stands in for the "yes commit" affirmation — proceed without waiting, but still DISPLAY the staged file list + message + target branch first (transparent, never silent).

### 5 — Push gate

Show the commit summary (`git log -1`) + target remote/branch. Wait for explicit **"yes push."** The pre-push hook re-runs the suite. **With `--bypass`:** the flag stands in for "yes push" — push without waiting, after showing the commit summary + target.

### 6 — Open the PR

Open a PR to the default branch (via `gh` or the GitHub MCP) with title `chore: <subject>` and a **summary-only** body:

```
## Summary
<one or two sentences: what changed and why>

## Scope
<the file(s) touched; note what is explicitly NOT included if useful>
```

No agent/process narration. No attribution footer.

### 7 — Merge (mode-aware)

- **Default:** confirm the user wants it merged now. Branch protection typically requires green CI, so wait for CI to pass (poll briefly), then merge (squash or per project convention). If CI goes red, **halt and surface verbatim — do not merge.** If the branch needs a review the author can't give, say so and leave the PR open. After merge, report the PR URL + merged SHA.
- **`--bypass`:** wait for CI to finish; the instant it's GREEN, admin-merge automatically — `gh pr merge <n> --squash --admin --delete-branch` (no human merge prompt; the flag authorized it). If CI fails/errors, or the admin override is refused (`enforce_admins`), **halt and surface verbatim — never merge a red build, never fake a merge.** Report the PR URL + merged SHA, and state plainly that the merge overrode branch protection with CI green.
- **`--concurrently` cleanup (both paths):** once the PR is open (and merged, if `--bypass`), `git worktree remove <tmp-path>`; keep the branch for the PR. Then offer to delete the chore branch if it wasn't auto-deleted.

## Notes

- **Agent/skill edits:** many projects keep skill/agent definition edits local until the related feature merges — but a `@chore` PR is the sanctioned standalone vehicle for shipping them once you're ready, so committing them here is correct.
- **Token budget:** keep it small.
- **Multiple unrelated chores:** one PR per concern. Don't batch several unrelated tweaks into one chore PR.
- **The `--concurrently` / `--bypass` hatch is opt-in and loud.** `--concurrently` keeps a chore from colliding with concurrent work (isolated worktree off the default branch); `--bypass` ships it the moment CI is green without waiting for a review. Neither ever skips CI, the chore-scope gate, or the no-`--no-verify` / no-`-A` / no-`--force` rules. Default `@chore` (no flags) still gates every commit, push, and merge on explicit human confirmation.
