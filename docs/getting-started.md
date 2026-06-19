# Getting started — zero to running

This guide takes you from a fresh clone to running the pipeline on your own repo. Most of it is automated: once installed, **`/orchestrator` runs an environment preflight (Step 0)** that detects what's missing, offers to set up the MCP servers for you behind a confirmation gate, and walks you through anything only you can do. The steps below are the manual reference for that same setup.

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

Or install as a plugin: `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` then `/plugin install maungs-agentic-toolbelt@maung-tools` (the plugin name is `maungs-agentic-toolbelt`; `maung-tools` is the marketplace it ships in).

These install **globally** into `~/.claude`, so they're available in every repo on your machine — you don't reinstall per project.

## 2. Authenticate the GitHub CLI

```bash
gh auth login           # interactive — pick GitHub.com, and a scope that includes 'repo'
gh auth status          # confirm the ACTIVE account is the one that can access your repos
```

If you have several GitHub accounts, make sure the **active** one has access to the repos you'll work on (`gh auth switch` to change it).

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

## Troubleshooting

- **`/mcp` shows a server disconnected** → re-run its `claude mcp add` command, then restart Claude Code.
- **A PR/issue agent says "GitHub MCP not connected"** → finish step 3 and restart.
- **Push denied to the wrong account** → check `gh auth status`; the **active** account must own/have write to the target repo.
- **`@developer` skips browser checks** → that's expected if no Playwright MCP is configured, or if the change has no UI surface. Add Playwright (step 3) to enable live verification.
