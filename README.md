# Maungs-agentic-toolbelt

A project-agnostic, human-gated **agentic software-development workflow engine** — a carpenter's toolbelt that helps one developer move like a whole team (the force multiplier behind a 10x developer; not just a hammer, but the whole belt to ship the job): **16 agents + 11 skills** that take work from a raw idea to a security-reviewed, merge-ready pull request — and keep the codebase's docs current on their own. It runs on multiple agent CLIs: [Claude Code](https://claude.com/claude-code) (the first and primary target) and the **OpenAI Codex CLI** (a shipped port), with the **Gemini CLI** as the next port in progress and others (e.g. the DeepSeek CLI) accommodated as future targets. Every component auto-detects the host project's conventions at runtime, so nothing here is hardcoded to one stack.

Agents are invoked with `@name`, skills with `/name`.

## Install

```bash
git clone https://github.com/Sfzmango/Maungs-agentic-toolbelt.git
cd Maungs-agentic-toolbelt
./install.sh          # copy into ~/.claude  (use --symlink to track updates via git pull)
```

Or install as a Claude Code plugin: `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` then `/plugin install maungs-agentic-toolbelt@maung-tools` (the plugin is served from the repo's `maung-tools` marketplace).

### Install on the OpenAI Codex CLI

The toolbelt is **model-agnostic** — the same components run on the **OpenAI Codex CLI**. Codex plugins carry the skills, lifecycle hooks, routing, guardrails, telemetry helpers, and metrics script. Custom TOML subagents are installed separately:

```bash
# Track 1 — plugin (skills + hooks + helper scripts):
codex plugin marketplace add Sfzmango/Maungs-agentic-toolbelt
codex plugin add maungs-agentic-toolbelt@maung-tools

# Track 2 — custom subagents:
./install-codex.sh --dry-run     # preview, changes nothing
./install-codex.sh               # installs into ~/.codex/agents
```

Open `/hooks` once, review the plugin hooks, and trust them. Then start a new thread. Verify: `ls ~/.codex/agents` shows the custom agents, invoke a skill with `$toolbelt`, ask Codex to spawn the `architect` subagent, and confirm the `developer` / `architect` subagents still **pause** on commit/push gates. Full walkthrough: **[`docs/codex.md`](docs/codex.md)**.

### Supported targets

| Target | Status | Components | Install |
|--------|--------|-----------|---------|
| **Claude Code** | shipped | agents + skills (+ hooks via plugin) | `./install.sh` or the `maung-tools` plugin |
| **OpenAI Codex CLI** | shipped | skills + hooks (plugin), custom subagents (installer) | `codex plugin add` + `./install-codex.sh` |
| **Gemini CLI** | work-in-progress — next port | — (in progress) | via the generator seam (add an emitter + a row); not yet shipped |
| DeepSeek CLI / cursor / aider / … | future | — | accommodated by the generator seam (add an emitter + a row); not built yet |

Codex artifacts are **generated** from the canonical `agents/*.md` + `skills/*/SKILL.md` + `hooks/` by `tools/build.py` — never hand-authored. See **[`docs/codex.md`](docs/codex.md)** and **[`docs/architecture.md`](docs/architecture.md)**.

> **Zero to running.** The agents use a **GitHub MCP** server (issue/PR tools) and, optionally, a **Playwright MCP** server (`@developer`'s browser checks). These do not need to be wired up by hand — running `/orchestrator` performs an environment **preflight** that detects what's missing, offers to add the MCP servers (behind a confirmation gate), and guides the user through anything that requires manual action (`gh auth login`, restarting Claude Code). Full walkthrough: **[`docs/getting-started.md`](docs/getting-started.md)**.

---

## Always-on hooks

Installed as a plugin, the toolbelt registers three lightweight hooks. The first — a `UserPromptSubmit` hook — inspects each prompt and — **only when it matches a toolbelt capability** — nudges the host agent to offer the relevant component, so the right one surfaces without anyone remembering the command.

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

On Codex, `PreToolUse` does not support an `ask` decision. The generated hook denies the first risky attempt with instructions to ask the user, then allows one explicitly confirmed retry prefixed with `MAUNGS_TOOLBELT_CONFIRMED=1`; hard-deny rules still apply to the retry.

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

This custom statusline is Claude-specific. Codex provides `/statusline` for its standard footer fields, but it does not consume the toolbelt pipeline-status file.

---

## Skills

| Skill | Use it for | Invocation |
|---|---|---|
| **`/agentic-onboard`** | Prepare a cold repo for agents or refresh stale `CLAUDE.md`, `AGENTS.md`, and architecture context. | `/agentic-onboard` · `/agentic-onboard --deep --target all` |
| **`/orchestrator`** | Run the human-gated issue-to-merge development cycle through planning, implementation, review, and resolution. | `/orchestrator <issue-id-or-topic>` · add `--experiment` for a local dry run |
| **`/bug-catcher`** | Diagnose one bug adversarially, or sweep the repository, then hand off a verified fix plan. | `/bug-catcher <symptom>` · `/bug-catcher --global` |
| **`/chore`** | Ship a small docs, config, tooling, typo, or dependency change without the full orchestrator pipeline. | `/chore <description>` · add `--concurrently` or `--concurrently --bypass` |
| **`/handoff`** | Produce a self-contained continuation brief for a specific issue or topic. | `/handoff <issue-id-or-topic>` |
| **`/todo`** | Maintain a private, local, per-project backlog that never enters the repository. | `/todo` · `/todo <text>` · `/todo done <id>` · `/todo drop <id>` |
| **`/wiki-generator`** | Build, incrementally update, or human-gate publication of a code-grounded technical wiki. | `/wiki-generator` · `/wiki-generator --update` · `/wiki-generator --publish` |
| **`/migration-planner`** | Analyze a proposed data or schema migration for loss, locking, rollout, rollback, and blast-radius risks. | `/migration-planner <change-or-file>` |
| **`/release-notes`** | Generate grouped release notes, a SemVer recommendation, and migration/env deployment checks. | `/release-notes [<range> \| PR <n>] [--format deploy-comment]` |
| **`/dossier-jobs`** | Configure scheduled cloud bug, security, and wiki routines that report into one tracking issue. | `/dossier-jobs [repo] [--bug --security --wiki] [--status --disable --run-now]` |
| **`/toolbelt`** | List components, recommend the right workflow, or inspect the toolbelt environment. | `/toolbelt` · `/toolbelt <goal>` · `/toolbelt status` |

> **Spotlight — concurrency-safe chores.** `/chore --concurrently` is what lets the toolbelt run *in parallel with itself*: while `/orchestrator` is mid-build on one branch, you can land a docs or config fix on another — no `HEAD` collision, no stash dance, no waiting. The chore does its work in a throwaway worktree based on `origin/<default-branch>`, opens its own PR, then tears the worktree down (keeping the branch); with `--bypass` it even admin-merges once CI is green, loudly and auditably. Walkthrough: [`examples/sample-concurrent-chore/`](examples/sample-concurrent-chore/).

`/todo` stores data outside the repo under the active product's home directory. `/wiki-generator` writes only `docs/wiki/`; publishing remains previewed and explicitly human-gated. On Codex, `$dossier-jobs` manages automations only when the active surface exposes those tools; Codex CLI otherwise emits complete copy/paste configurations.

---

## Agents

| Stage | Agent | Role | Typical invocation |
|---|---|---|---|
| Onboarding | **`@context-writer`** | Build verified `CLAUDE.md`, `AGENTS.md`, and architecture context from one project profile. | Delegated by `/agentic-onboard` |
| Onboarding | **`@context-auditor`** | Re-derive repository facts and classify existing context as current, stale, incorrect, or missing. | Delegated by `/agentic-onboard` in stale mode |
| Plan | **`@product-owner`** | Turn a fuzzy request into a scoped issue with acceptance criteria and user-flow artifacts. | `@product-owner draft an issue for <topic>` |
| Plan | **`@architect`** | Convert an issue or topic into an implementation plan with decisions, diagrams, and validation steps. | `@architect plan issue <num>` |
| Plan | **`@plan-reviewer`** | Independently review a plan against the issue and live code before implementation. | `@plan-reviewer <plan-file-path>` |
| Build | **`@developer`** | Implement an approved plan, add tests, run the detected quality gate, and enforce commit/push approval. | `@developer implement plan <path>` |
| Translation | **`@code-translator`** | Produce documentation-grounded translations and idiom guidance across languages or frameworks. | `@code-translator translate <source> from <lang> to <lang>` |
| Testing | **`@test-author`** | Add negative-path, edge-case, and regression tests without weakening existing assertions. | Invoke directly or delegate from `@pr-reviewer` |
| Review | **`@pr-reviewer`** | Perform a fresh-eyes adversarial PR review and issue a ship verdict. | `@pr-reviewer PR <num>` |
| Review | **`@security-reviewer`** | Run a cold security/compliance review with stack-matched scans and framework mappings. | `@security-reviewer PR <num>` |
| Review | **`@security-mentor`** | Explain each security finding's threat model, attack path, and structurally sound fix. | `@security-mentor PR <num>` · `@security-mentor diff` |
| Wrap-up | **`@resolution`** | Resolve addressed review threads, update completion state, and halt on remaining blockers. | `@resolution PR <num>` |
| Bug | **`@bug-catcher-rick`** | Diagnose symptoms into an evidence-backed root cause, severity, fix direction, and blast radius. | Delegated by `/bug-catcher` or `@bug-catcher-rick <symptom>` |
| Bug | **`@bug-catcher-adversary`** | Try to refute a diagnosis and verify that the proposed fix addresses the root cause. | Delegated by `/bug-catcher` or `@bug-catcher-adversary <dossier>` |
| Wiki | **`@wiki-writer`** | Author one code-grounded wiki page with diagrams, schemas, related files, and verification metadata. | Delegated by `/wiki-generator` |
| Wiki | **`@wiki-auditor`** | Detect drift between an existing wiki page and the current codebase. | Delegated by `/wiki-generator --update` |

---

## Learn more

- [`docs/recipes.md`](docs/recipes.md) — **synergy tips**: how to compose the components into a personal workflow (capture backlog with `/todo`, bug→fix, parallel chores, scheduled doc upkeep)
- [`docs/architecture.md`](docs/architecture.md) — how the agents hand off, with a full pipeline diagram
- [`docs/design-philosophy.md`](docs/design-philosophy.md) — the recurring design principles and the failure modes they prevent
- [`docs/components.md`](docs/components.md) — one-table index of all 27 components
- [`docs/faq.md`](docs/faq.md) — how the toolbelt behaves in practice (e.g. how workers handle their adversary's feedback)
- [`examples/`](examples/) — a sample issue, plan (with wireframes), bug dossier, and generated wiki

**License:** [PolyForm Noncommercial 1.0.0](LICENSE) © 2026 Maung Htike. Free to use, run, and adapt for **noncommercial** purposes with attribution preserved; **commercial use requires a separate license** (contact via [github.com/Sfzmango](https://github.com/Sfzmango)). Original, project-agnostic agent designs — no proprietary code; compliance rubrics reference public standards (SOC 2, OWASP, PCI DSS, NIST, CWE).
