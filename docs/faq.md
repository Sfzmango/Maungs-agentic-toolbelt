# FAQ

Frequently asked questions about the toolbelt — what it is, how to run it, how it keeps a repo safe, and how it stays honest. Each answer is grounded in the component definitions and cites where the behavior is specified; for the underlying design principles see [`design-philosophy.md`](design-philosophy.md).

Answers are grouped by topic and **collapsed by default** — click a question to expand it.

## What it is

<details>
<summary><strong>Is this an application, or a plugin — and what does it actually ship?</strong></summary>

It is a Claude Code **plugin**, not a standalone application (`CLAUDE.md`, Project overview). It ships **16 agents + 10 skills (26 components)** — agents are `@name` subagents (specialized workers) and skills are `/name` conductors (orchestrators) — that take work from a raw idea to a security-reviewed, merge-ready PR and keep a codebase's docs current (`CLAUDE.md`, Project overview). The deliverable itself is **Markdown prompt definitions** (`agents/*.md` and `skills/<name>/SKILL.md` with YAML frontmatter), backed by supporting Bash hooks/scripts, stdlib Python 3 tests, and JSON config; there is no package manager or build system in the repo (`CLAUDE.md`, Stack). It is distributed two ways: as a plugin via the `maung-tools` marketplace (`.claude-plugin/marketplace.json`) and via a copy/symlink `install.sh` into `~/.claude` (`CLAUDE.md`, Project overview), with `plugin.json` pinned at version `0.4.0` under the PolyForm-Noncommercial-1.0.0 license (`.claude-plugin/plugin.json`).

</details>

<details>
<summary><strong>What's the difference between an agent (@name) and a skill (/name)?</strong></summary>

Agents and skills are the two component types in the pipeline (`docs/architecture.md:9`):

- **Agents (`@name`) are workers.** Each owns exactly one phase, runs in its own context with a least-privilege scoped toolset, and is invoked as `@name` (`docs/architecture.md:14`, `docs/design-philosophy.md:3`). The capability boundary is enforced by the toolset itself, not just by prose — for example a read-only reviewer has no `Edit`/`Write` tool and so cannot modify the code it reviews (`docs/design-philosophy.md:30`).
- **Skills (`/name`) are conductors.** They orchestrate a multi-phase process and delegate every unit of real work to an agent — they route, gate, and sequence rather than doing the engineering themselves (`docs/architecture.md:11-12`, `docs/design-philosophy.md:3`).

The current inventory is 16 agents + 10 skills = 26 components (`docs/architecture.md:9`).

</details>

<details>
<summary><strong>Is the toolbelt tied to a specific programming language or framework?</strong></summary>

No. The toolbelt is project-agnostic: no component hardcodes a stack, and every agent and skill auto-detects the host project's stack and conventions at runtime rather than assuming one (`CLAUDE.md`, Conventions; `docs/design-philosophy.md` §1). Each component opens with an "Auto-detect project conventions" phase that runs before any real work, deriving the language, framework, test runner, lint command, build step, pre-commit hook system, CI, and plan-file location from files actually present — so the same `@developer` that ships a Rails feature ships a Go or Rust one because it reads the manifest instead of assuming one (`docs/design-philosophy.md` §1). When there is nothing to detect, auto-detection degrades honestly to a fallback (bootstrap minimal context or proceed with language defaults) rather than crashing, and any detected `CLAUDE.md` rules are treated as additive — a project can make the pipeline stricter but never opt out of a cardinal rule (`docs/design-philosophy.md` §1).

</details>

<details>
<summary><strong>Does it only work with Claude, or can it target other AI models?</strong></summary>

No — the toolbelt is model-agnostic and also targets the OpenAI Codex CLI; the same 16 agents and 10 skills run on both Claude Code and Codex (`docs/codex.md`). Components are defined once as canonical `agents/*.md` + `skills/*/SKILL.md`, and a pure-stdlib generator (`tools/build.py`) renders them into each target's native form via per-target emitters: `python3 tools/build.py --target codex|claude|all [--check]` (`tools/build.py`, header/docstring). Codex artifacts are **generated, never hand-edited** — edit canonical then regenerate, and a CI drift guard fails on any diff (`CLAUDE.md`, `tools/` section). The generator is a target-agnostic core (`build.py`, `common.py`, `transforms.py`) plus per-target emitters, so adding a target like cursor or aider is "add an emitter + a target-table row," not a rearchitecture (`docs/codex.md`).

</details>

## Getting started

<details>
<summary><strong>How do I install the toolbelt?</strong></summary>

The toolbelt installs two ways. The local installer copies (or symlinks) the agents and skills into Claude Code's config: clone the repo, then run `./install.sh` to copy into `~/.claude` (`README.md`, install section; `install.sh:6`). The installer accepts `--symlink` to symlink instead of copy so `git pull` tracks updates, `--target DIR` to install into `DIR/.claude` instead of `~/.claude`, and `--dry-run` to show what would happen without changing anything (`install.sh:7-9`). Agents land at `~/.claude/agents/<name>.md` and skills at `~/.claude/skills/<name>/SKILL.md` (`install.sh:11-12`). Alternatively, install it as a Claude Code plugin with `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` followed by `/plugin install maungs-agentic-toolbelt@maung-tools` (`README.md`, install section).

</details>

<details>
<summary><strong>Once it's installed, where do I start?</strong></summary>

Three entrypoints are documented: `/orchestrator` (the main dev-cycle conductor), `/agentic-onboard` (the on-ramp), and `/toolbelt` (discoverability); agents are reached via `@name` and skills via `/name` (`CLAUDE.md`, Entrypoints). For a starting overview, `/toolbelt` is the self-describing front door — with no argument it prints a stage-grouped inventory of every installed component with each one's purpose and exact invocation, and with a free-text goal it recommends the best-fit component(s) (`skills/toolbelt/SKILL.md`). If the current repo has no `CLAUDE.md`, the recommended first step is `/agentic-onboard`, which generates the agent-context files the rest of the toolbelt depends on (`skills/toolbelt/SKILL.md`; `README.md`). To start actual work, running `/orchestrator` also performs an environment preflight that detects missing GitHub/Playwright MCP servers and offers to add them behind a confirmation gate (`README.md`).

</details>

<details>
<summary><strong>My repo has no CLAUDE.md yet — can I still use it?</strong></summary>

Yes. A repo with no `CLAUDE.md` and no equivalent agent context is classified **COLD**, and `/agentic-onboard` routes it to "generate from scratch": it builds one canonical PROJECT PROFILE from cheap read-only probes (manifests, scripts, CI, structure) and hands it to the `@context-writer` agent to author the context layer fresh (`skills/agentic-onboard/SKILL.md`, COLD vs STALE). By default it emits the lean set — `CLAUDE.md`, the agent-neutral `AGENTS.md`, and a concise `docs/architecture.md` module map — establishing the on-ramp every other toolbelt component depends on (`skills/agentic-onboard/SKILL.md`, EMIT-TO-TARGETS). New files are written to the working tree only with no commit, and any value not derivable from the repo is marked **NEEDS CONFIRMATION** rather than fabricated (`skills/agentic-onboard/SKILL.md`, CARDINAL RULES). If the repo also lacks manifests so there is nothing to anchor on, the skill surfaces this and offers to proceed with code-derived facts only or pause for a seed instead of inventing a stack (`skills/agentic-onboard/SKILL.md`, circuit-breaker table).

</details>

<details>
<summary><strong>What external tools or MCP servers does it need?</strong></summary>

The toolbelt itself runs on Claude Code (or the OpenAI Codex CLI) and requires no third-party libraries, but its issue/PR workflow depends on a **GitHub MCP** server, which provides the `mcp__github__*` tools the issue and PR phases need — required for issue-ID inputs, optional for free-text topics (`skills/orchestrator/SKILL.md`, Step 0; `README.md`). A **Playwright MCP** server is optional, supplying `mcp__playwright__*` for `@developer`'s live UI verification; if declined, that browser verification is skipped (`skills/orchestrator/SKILL.md`, Step 0; `README.md`). The `gh` CLI (installed and authenticated via `gh auth login`) is also expected for GitHub access (`skills/orchestrator/SKILL.md`, Step 0). These do not need manual wiring: running `/orchestrator` performs an environment **preflight** that detects what is missing, offers to add the MCP servers behind a confirmation gate, and guides the user through manual steps like `gh auth login` and restarting Claude Code (`README.md`; `skills/orchestrator/SKILL.md`, Step 0).

</details>

## Safety & control

<details>
<summary><strong>Will it commit, push, or open PRs on its own without asking me?</strong></summary>

No. Every commit and every push is a separate, explicit human confirmation — never bundled, never inferred from an earlier "go," and never satisfied by silence (`docs/design-philosophy.md` §4). The `@developer` agent must show a commit gate (`git status` + `git diff --stat` + message + branch) before *every* commit and a separate push gate after the commit lands, requiring an explicit "yes commit" then "yes push" each time; even the lightweight `/chore` path keeps these gates ("'lightweight' never means 'skip the gates'"), and `/orchestrator` ends without merging ("that's your call") (`docs/design-philosophy.md` §4). The default is no AI attribution in commits — no `Co-Authored-By` / "Generated with Claude" footers (`CONTRIBUTING.md:28`). These rules are also enforced structurally: the shipped `PreToolUse` guard *denies* `git add -A/--all/.`, `git push --force` without `--force-with-lease`, `--no-verify`, and commits carrying AI attribution (`hooks/pretooluse-guard.sh`).

</details>

<details>
<summary><strong>What stops an agent from running a destructive shell command?</strong></summary>

A shipped `PreToolUse` hook, `hooks/pretooluse-guard.sh`, inspects every `Bash` command before it runs and structurally enforces the toolbelt's cardinal rules. It has a **deny tier** that blocks `git add -A/--all/.`, `git push --force` without `--force-with-lease`, `--no-verify` hook bypasses, catastrophic recursive deletes (`rm -rf` targeting `/`, `~`, `$HOME`, or `*`), and AI-attributed commits (`hooks/pretooluse-guard.sh`). It also has an **ask tier** that always prompts with a detailed reason — rather than silently running — for risky-but-possibly-legitimate operations: destructive SQL (`DROP`/`TRUNCATE`/`DELETE FROM`), database drops/resets, work-discarding git ops (`reset --hard`, `clean -f`, `branch -D`, `stash drop`), `rm -rf` of non-disposable paths, infrastructure teardown (`terraform destroy`, `kubectl delete`, `docker volume rm`), and bulk `find`/`xargs` deletes (`hooks/pretooluse-guard.sh`). The guard fails open — any parse error or missing `jq` exits 0 and allows the command — and it auto-approves nothing, so the normal permission flow still applies; it can be disabled with `MAUNGS_TOOLBELT_GUARD=off` (`hooks/pretooluse-guard.sh`).

</details>

<details>
<summary><strong>Does it phone home or collect usage data?</strong></summary>

No. The toolbelt makes no network calls and never phones home; its hooks are read-only and the only telemetry is local and opt-in (`CLAUDE.md`, Security / tenancy notes). Usage tracking is **off by default** and records nothing unless `MAUNGS_TOOLBELT_DEBUG` is set to `on`/`verbose` — any other value or unset means zero files and zero overhead (`hooks/lib-telemetry.sh`). When enabled, it appends `"suggested"` and `"invoked"` events as JSONL to `~/.claude/maungs-toolbelt/usage.jsonl` on the local machine only, never inside a project repo, viewable via `/toolbelt metrics` (`hooks/lib-telemetry.sh`). The `usage-tracker.sh` hook is a pure pass-through that logs and exits 0 with no permission decision, counts only this plugin's own agents and skills, and fails open on any error so the tool still runs (`hooks/usage-tracker.sh`).

</details>

<details>
<summary><strong>How does it keep secrets and private information out of the repo?</strong></summary>

A CI step in the `validate` workflow — "No private or employer references leak in" — runs a recursive, case-insensitive `grep` across the repo's Markdown, JSON, shell, TOML, and Python files and **fails the build on any match** against a small denylist (`.github/workflows/validate.yml`). The denylist covers two private/employer name fragments and the pattern for an absolute macOS home path, so a hardcoded personal path, an employer identity, or a private project name blocks the merge rather than landing in history (`.github/workflows/validate.yml`). Contributors are directed to use `~/...` or repo-relative paths instead of absolute home paths and to avoid the private fragments entirely — even documenting them literally would trip the grep (`CLAUDE.md`, Gotchas: leak-grep). The repo carries no secrets of its own; the gate keeps it that way (`CLAUDE.md`, Security / tenancy notes).

</details>

## Quality, licensing & extending

<details>
<summary><strong>How is quality enforced — are there tests and CI?</strong></summary>

Quality is enforced by a single CI workflow, `validate`, that runs on every push and pull request (`.github/workflows/validate.yml`). It executes a set of orthogonal checks — each reporting its own pass/fail row — covering frontmatter presence, a private/employer/home-path leak-grep, component-count consistency across six files, and the Codex generator's drift guard, validate-only Claude target, and generator tests (`.github/workflows/validate.yml`). Two Python 3 stdlib test suites back the behavioral checks: `tests/test_router.py` drives the real router hook against a labeled prompt corpus and asserts each prompt routes to the intended component, and `tests/translator_eval/eval.py` runs every `@code-translator` reference solution against known STDIN/STDOUT vectors per detected toolchain (`CLAUDE.md`, Commands / Testing). There is no lint, build, or local pre-commit step for this repo's own development — CI is the quality gate (`CLAUDE.md`, Commands).

</details>

<details>
<summary><strong>Can I use this commercially? What's the license?</strong></summary>

Commercial use is not permitted without a separate license. The software is released under the **PolyForm Noncommercial License 1.0.0** (`LICENSE`), under which any noncommercial purpose is free, but commercial use requires a separate license obtained by contacting the author (`LICENSE`; `README.md`). Noncommercial purposes include personal study, hobby and amateur projects, and use by charitable, educational, public-research, and government organizations (`LICENSE`). The required copyright notice — © 2026 Maung Htike — must be preserved on any copy distributed (`LICENSE`; `README.md`).

</details>

<details>
<summary><strong>How do I add my own agent or skill?</strong></summary>

Agents are flat files and skills are foldered. To add an **agent**, create `agents/<your-agent>.md` with YAML frontmatter declaring `name`, `description`, and least-privilege `tools` (grant only what it needs) (`CONTRIBUTING.md`; `CLAUDE.md`, Conventions). To add a **skill**, create `skills/<your-skill>/SKILL.md` with frontmatter `name`, `description`, and `disable-model-invocation` — skills are conductors, so delegate heavy work to agents rather than inlining it (`CONTRIBUTING.md`; `CLAUDE.md`, Conventions). Follow the house style (numbered cardinal rules, explicit auto-detection, a circuit-breaker table, a token budget, human gates for outward actions), then re-run `./install.sh` (or `git pull` if symlinked). Finally, regenerate the Codex artifacts with `python3 tools/build.py --target codex` and update the component counts + descriptions, since the `validate` workflow fails until they match (`CONTRIBUTING.md`; `CLAUDE.md`, Gotchas).

</details>

## How it behaves in practice

<details>
<summary><strong>Do worker agents apply their own judgement to what their adversary counterpart raises, or do they just comply?</strong></summary>

Several workers are paired with a deliberately adversarial counterpart:

- `@context-writer` ↔ `@context-auditor` (drift detector)
- `@architect` ↔ `@plan-reviewer` (cold plan review)
- `@developer` ↔ `@pr-reviewer` / `@security-reviewer` (cold PR gate)

**The short answer: neither.** A worker never silently complies with its adversary, and it never privately overrules it. The judgement deliberately lives in a third place — the **conductor skill** (`/agentic-onboard`, `/orchestrator`) and a **human gate** — not in a direct negotiation between the worker and its adversary.

**Why the worker is not the adjudicator.** The adversaries are spawned *fresh-eyes* on purpose: `@plan-reviewer`, `@pr-reviewer`, `@security-reviewer`, and `@context-auditor` never read prior reasoning or prior reviews of the artifact they evaluate (see [the fresh-eyes split, §3](design-philosophy.md)). That independence is the whole value of the second pass, so the system is biased toward *taking the adversary seriously*. But the step that converts findings into action is owned by the conductor and the human — not by the worker rubber-stamping or vetoing.

Within that frame, each worker keeps a **judgement floor** that stops it from being a pure rubber stamp:

**`@context-writer` — trusts *what* drifted, verifies *what's true*.** In STALE mode it applies **only** the auditor's delta list and does not re-litigate which sections were flagged (`agents/context-writer.md`). But it does not transcribe blindly: for each delta it independently re-verifies the new value against the repo and cites the source, and — per its accuracy-over-completeness cardinal rule — it refuses to write a claim it cannot verify even if a delta asks for it, marking it "needs confirmation" and reporting any unresolvable delta rather than inventing the section. It trusts the auditor on *which sections drifted* and exercises its own judgement on *what is actually true now*.

**`@architect` — the verdict routes to a human gate.** The architect definition contains no plan-reviewer handling; it does not auto-apply the verdict. The reviewer returns `SOLID / REVISE / RETHINK` plus findings, which surface at the architect's plan-approval gate (`agents/architect.md`, Phase 4), where a human decides what to accept. A revision re-spawns the architect to re-draft against the accepted subset. The architect neither obeys nor overrules — it re-plans against the human-accepted findings.

**`@developer` — a fix loop with a circuit breaker against blind compliance.** A reviewer's verdict and punch list go to the orchestrator's human review gate first (`skills/orchestrator/SKILL.md`, Step 11); only if the human chooses "apply punch list" does it loop back to the developer's fix loop (`agents/developer.md`, Phase 5). And the developer will stop complying when compliance is backfiring: its quality-degradation breaker hard-halts the moment a fix round produces *more* findings than the previous one, and hands off instead of grinding further (see [quality-degradation circuit breakers, §5](design-philosophy.md)). This is the clearest case of a worker exercising judgement *against* simply doing what it is told.

**The one real debate.** The exception is a pair not in the list above: `@bug-catcher-rick` ↔ `@bug-catcher-adversary`. The `/bug-catcher` conductor runs an actual **bounded debate** — it re-spawns Rick with the adversary's critique, re-runs the adversary on the revised dossier, and caps the exchange at **3 rounds** to force convergence or escalation (`skills/bug-catcher/SKILL.md`). Even there, the conductor runs the debate and the human makes the final call; the two agents do not settle it between themselves.

**The pattern, in one line.** Adversaries carry independent weight; conductors and humans adjudicate; workers re-execute and retain only a hard floor — verify-don't-fabricate, stop-if-regressing — that prevents pure compliance. This is the [conductor-never-codes split, §7](design-philosophy.md) applied to review feedback: the worker does the work, the conductor and the human own the decision.

</details>
