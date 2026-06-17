---
name: chore
description: Lightweight workflow for small, one-off chore PRs (docs, config, tooling, comment/typo fixes, agent/skill edits, trivial dependency bumps) that don't warrant the full /orchestrator pipeline. No plan file, no architect/developer/reviewer agents — you do the change inline, honor the commit/push gates, open a summary-only PR, and merge after green CI. Invoke as `/chore <short description>` or by typing "make a chore PR for X".
disable-model-invocation: false
---
# /chore — lightweight one-off chore PRs

The argument is in `$ARGUMENTS` — a short free-text description of the chore. If empty, ask what the chore is and stop.

You do this work **inline** — no architect plan, no adversarial review. The whole point is to stay lightweight for changes that are too small to justify `/orchestrator`. But the project's cardinal rules still apply in full; "lightweight" never means "skip the gates."

## Auto-detection on every invocation

Before starting, detect the project's shape so the gates and conventions are right:

1. **`CLAUDE.md` + `CLAUDE.local.md`** — the project's cardinal rules and conventions. They override anything here on conflict.
2. **Pre-commit hook system** — `lefthook.yml` / `.pre-commit-config.yaml` / `.husky/` — this is the local quality gate that runs on commit and push. Honor it; never bypass.
3. **CI** — `.github/workflows/` — what must go green before merge.
4. **Default branch** — usually `main` (confirm via `git`); branch off it and target it.
5. **The project's auto-memory directory** (`~/.claude/projects/<project-slug>/memory/`) — captured feedback (commit-message style, PR-body conventions, attribution rules).

## Cardinal rules (non-negotiable — inherited from the project's CLAUDE.md / CLAUDE.local.md)

1. **Full local quality gate on every commit and every push** (whatever the project's pre-commit hook system runs — lint, build, full test suite). No bypass flags (`--no-verify`, etc.).
2. **Explicit per-commit AND per-push human confirmation.** Separate gates, fresh affirmation each time ("yes commit" / "yes push"). Never bundle them; never infer approval from an earlier "go."
3. **No Claude / Claude Code attribution** in commits, PR bodies, or output.
4. **Force-push uses `--force-with-lease`, never `--force`** (rarely needed for a chore).
5. **PR body is a factual summary only** — `Summary` + `Scope`; no agent/process references, no pivot / "how we got here" narrative, no reviewer-focus section.
6. **Never bundle unrelated changes.** Stage only the files this chore touches, even if the working tree carries other local edits.

## Is it actually a chore? (gate before starting)

Use `/chore` only when ALL of these hold:

- Single concern, small diff (roughly one file to a handful).
- No architectural decision to make, no migration, no new app behavior that needs a test or review.
- Low blast radius: docs, comments, README/SETUP, config, CI / pre-commit-hook tweaks, agent/skill definitions, a trivial dependency bump, a lint-fix.

If it touches app behavior that needs a plan, a migration, multi-file feature work, or anything security-sensitive → **stop and recommend `/orchestrator <id>` instead.** When in doubt, say so and let the user pick. A chore that grows mid-flight should be re-routed, not forced through.

## Steps

### 1 — Acknowledge + scope

Restate the chore in one sentence. Confirm it passes the "is it a chore?" gate; if not, recommend `/orchestrator` and stop. Identify the exact file(s) to change.

### 2 — Make the change inline

Edit the file(s). Keep it strictly scoped to the one concern. If the change reveals it's bigger than a chore, stop and re-route.

### 3 — Branch off current default branch

`git checkout -b chore/<short-slug> origin/<default-branch>` (branch off the current trunk; the working-tree edit rides along). Verify with `git status` that only the intended files are modified — if other local changes are present, you'll stage selectively in step 4, never bundle.

### 4 — Commit gate

Show: (a) the file list (`git status --short` + `git diff --stat`, scoped to this chore's files), (b) the proposed commit message — `chore: <subject>` with a concise 1–2 sentence body if needed, (c) the target branch. Stage ONLY this chore's files (`git add <paths>`, not `-A`, if other edits exist). Wait for explicit **"yes commit."** The pre-commit hook runs the local gate on commit; surface any failure verbatim (don't bypass).

### 5 — Push gate

Show the commit summary (`git log -1`) + target remote/branch. Wait for explicit **"yes push."** The pre-push hook re-runs the suite.

### 6 — Open the PR

Open a PR to the default branch (via `gh` or the GitHub MCP) with title `chore: <subject>` and a **summary-only** body:

```
## Summary
<one or two sentences: what changed and why>

## Scope
<the file(s) touched; note what is explicitly NOT included if useful>
```

No agent/process narration. No attribution footer.

### 7 — Merge

Confirm the user wants it merged now. Branch protection typically requires green CI, so wait for CI to pass (poll briefly), then merge (squash or per project convention). If CI goes red, **halt and surface verbatim — do not merge.** After merge, report the PR URL + merged SHA. Offer to delete the chore branch.

## Notes

- **Agent/skill edits:** many projects keep skill/agent definition edits local until the related feature merges — but a `/chore` PR is the sanctioned standalone vehicle for shipping them once you're ready, so committing them here is correct.
- **Token budget:** keep it small.
- **Multiple unrelated chores:** one PR per concern. Don't batch several unrelated tweaks into one chore PR.
