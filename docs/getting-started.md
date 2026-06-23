# Getting started — zero to running

This guide takes you from a fresh clone to running the pipeline on your own repo on **Claude Code** (the toolbelt's first/primary target; for the OpenAI Codex CLI port, see [`codex.md`](codex.md)). Most of it is automated: once installed, **`/orchestrator` runs an environment preflight (Step 0)** that detects what's missing, offers to set up the MCP servers for you behind a confirmation gate, and walks you through anything only you can do. The steps below are the manual reference for that same setup.

## Prerequisites

- **[Claude Code](https://claude.com/claude-code)** installed.
- **[`gh`](https://cli.github.com/) (GitHub CLI)** — used by the issue/PR agents' auth and by `@resolution`'s fallback.
- **Node.js / `npx`** — only if you want the optional Playwright MCP (browser verification).

## 1. Install the agents & skills

```bash
git clone https://github.com/Sfzmango/Maungs-agentic-toolbelt.git
cd Maungs-agentic-toolbelt
./install.sh                 # copy into ~/.claude   (use --symlink to track updates via git pull)
```

Or install as a Claude Code plugin: `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` then `/plugin install maungs-agentic-toolbelt@maung-tools` (the plugin name is `maungs-agentic-toolbelt`; `maung-tools` is the marketplace it ships in). On the OpenAI Codex CLI, install via `codex plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` + `codex plugin add maungs-agentic-toolbelt@maung-tools`, then `./install-codex.sh` for the custom subagents (see [`codex.md`](codex.md)).

These install **globally** into `~/.claude`, so they're available in every repo on your machine — you don't reinstall per project.

## 2. Authenticate the GitHub CLI

```bash
gh auth login           # interactive — pick GitHub.com, and a scope that includes 'repo'
gh auth status          # confirm the ACTIVE account is the one that can access your repos
```

If you have several GitHub accounts, make sure the **active** one has access to the repos you'll work on (`gh auth switch` to change it).

### GitHub token permission baseline

The toolbelt reaches GitHub through a token (the `gh`-stored credential the GitHub MCP server reuses on Claude Code, and the GitHub MCP server's own token on the Codex CLI). Grant that token **least privilege** — only what the issue/PR agents actually use:

- **Issues** read+write — `@product-owner` drafts/refines issues; the dossier routines file tracking issues.
- **Pull requests** read+write+review — `@architect` opens the PR; `@developer` updates it; `@pr-reviewer` / `@security-reviewer` post inline review comments.
- **Repository contents** read+write — branches and commits for the PR.
- **Metadata** read — required baseline for any repository access.
- **Workflows** read+write — **only** if a change edits files under `.github/workflows/`.

Two equivalent ways to grant this:

| Token type | Grant |
|---|---|
| **Classic PAT** | the `repo` scope (covers contents + issues + PRs); add `workflow` only if you edit CI files. |
| **Fine-grained PAT** (preferred — narrower) | repository permissions: **Contents** RW, **Pull requests** RW, **Issues** RW, **Metadata** RO; add **Workflows** RW only if you edit CI files. |

A fine-grained PAT scoped to just the repos you work on is the tighter default. Whichever you use, **merge safety should come from the repo's branch protection, not from withholding token scopes** — the agents are human-gated and never auto-merge, but branch protection (required reviews + green CI) is the control that actually blocks a bad merge.

Inspect what your current token can do with `gh auth status` — for a `gh`-stored classic token it prints a `Token scopes:` line (e.g. `'repo', 'workflow'`). (Fine-grained PATs carry per-permission grants rather than classic scopes, so no scope line is shown; check them in the GitHub PAT settings page. An env-var `GITHUB_TOKEN` also shows no scope line.)

**On the Codex CLI** the same issue/PR/contents/review access applies, but the GitHub MCP server is granted at **whole-server** granularity rather than Claude's per-tool allowlist — so the **token scopes are the real least-privilege control** there, and the points above are not optional refinements but the primary boundary. As on Claude Code, merge safety must come from branch protection, not from token scopes.

## 3. Add the MCP servers

You can let `/orchestrator` do this for you (it proposes the exact command and runs it after you approve), or do it by hand:

```bash
# GitHub MCP — REQUIRED for issue/PR work. Provides the mcp__github__* tools
# (pull_request_read, create_pull_request, pull_request_review_write, …):
claude mcp add --transport http github https://api.githubcopilot.com/mcp/ \
  --header "Authorization: Bearer $(gh auth token)"

# Playwright MCP — OPTIONAL, only for @developer's live UI verification:
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

> **Restart Claude Code after adding MCP servers** — newly added servers don't load into a running session. Then verify with `/mcp` (both should show **connected**).

## 4. (Recommended) Add a `CLAUDE.md` to your project

It's the single highest-leverage thing you can do: it's where the agents learn your cardinal rules, plan-file path, and house style. The agents work without it (they auto-detect from manifests), but they're sharper with it. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## 5. Run it

From inside **your** repo, launch Claude Code and invoke:

```
/orchestrator 128          # whole feature: issue → plan → build → review → merge-ready
```

On the first run, Step 0 reports your environment and helps you finish any setup. Once green, the pipeline proceeds with human gates at every commit, push, and merge.

Other entry points:

```
@pr-reviewer PR 128        # review an existing pull request (fresh-eyes + inline comments)
@security-reviewer PR 128  # security / compliance gate
@resolution PR 128         # resolve fixed threads before merge
/bug-catcher <symptom>     # diagnose (and adversarially verify) a bug
/chore <small change>      # lightweight single-concern PR
/wiki-generator            # build a docs/wiki/ for the repo
/handoff <id>              # write a resume-from-cold brief
```

**Composing them:** see [recipes](recipes.md) for end-to-end workflows — capturing backlog with `/todo`, bug→fix, shipping small changes in parallel, and keeping docs current on a schedule.

## 6. (Optional) Enable the cockpit statusline

The toolbelt bundles a status-line script that shows a one-line cockpit — git branch, session cost, context usage, hook state, model, and a live `/orchestrator` pipeline segment (phase · PR · verdict). It is not auto-enabled; opt in by pointing `~/.claude/settings.json` at it:

```json
"statusLine": {
  "type": "command",
  "command": "~/Maungs-agentic-toolbelt/statusline/toolbelt-statusline.sh"
}
```

See [the README](../README.md#cockpit-statusline-optional) for what each segment means.

## Troubleshooting

- **`/mcp` shows a server disconnected** → re-run its `claude mcp add` command, then restart Claude Code.
- **A PR/issue agent says "GitHub MCP not connected"** → finish step 3 and restart.
- **Push denied to the wrong account** → check `gh auth status`; the **active** account must own/have write to the target repo.
- **`@developer` skips browser checks** → that's expected if no Playwright MCP is configured, or if the change has no UI surface. Add Playwright (step 3) to enable live verification.
