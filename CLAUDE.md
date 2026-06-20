> This repo is prepped for agentic development: the context below is verified against the tree and is meant to be acted on without re-deriving it from source. Last verified against commit `cf4d0e9`.

# CLAUDE.md — Maungs-agentic-toolbelt

## Project overview

This repo is a project-agnostic, human-gated multi-agent workflow **for** Claude Code — and it is itself a Claude Code **plugin**, not an application. It ships **16 agents + 10 skills (26 components)**: agents are `@name` subagents (specialized workers) and skills are `/name` conductors (orchestrators). Together they take a piece of work from a raw idea to a security-reviewed, merge-ready PR, and keep a codebase's docs current. Every component auto-detects the **host** project's stack and conventions at runtime — nothing is hardcoded to one language or framework. It is distributed two ways: as a Claude Code plugin via the `maung-tools` marketplace, and via a copy/symlink `install.sh` into `~/.claude`.

## Stack

The "product" is **Markdown prompt definitions**: `agents/*.md` and `skills/<name>/SKILL.md`, each with YAML frontmatter. Supporting code:

- **Bash** — `hooks/*.sh`, `install.sh`, `bin/toolbelt-metrics.sh`, `statusline/toolbelt-statusline.sh`.
- **Python 3, stdlib only** (no pytest, no third-party deps) — `tests/test_router.py`, `tests/translator_eval/eval.py`.
- **JSON** — `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `hooks/hooks.json`.

There is **no package manager and no build system** — there is no `package.json`, `Gemfile`, `pyproject.toml`, `go.mod`, `Cargo.toml`, or equivalent in the repo.

## Commands

Every command below is cited to its source. There is no install/build/lint/format toolchain to wrap — see the explicit note at the end.

- **Install into `~/.claude`:** `./install.sh` — copy form. *(from `install.sh:6`, `README.md:12`)*
  - `./install.sh --symlink` — symlink instead of copy, so `git pull` tracks updates. *(from `install.sh:7`)*
  - `./install.sh --target DIR` — install into `DIR/.claude` instead of `~/.claude`. *(from `install.sh:8`)*
  - `./install.sh --dry-run` — show what would happen, change nothing. *(from `install.sh:9`)*
- **Install as a plugin:** `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` then `/plugin install maungs-agentic-toolbelt@maung-tools`. *(from `README.md:15`)*
- **Test — router regression:** `python3 tests/test_router.py` — drives the real router hook against a labeled corpus (16 intents, 100+ cases). *(from `.github/workflows/validate.yml:39`)*
- **Test — translator eval:** `python3 tests/translator_eval/eval.py` — runs every reference solution against its I/O vectors across the supported languages. *(from `.github/workflows/validate.yml:42`)*
  - The eval accepts `--check` (default, deterministic, no LLM, CI-able) and `--live --from <lang> --to <lang,...|all>` to invoke `@code-translator`. *(from `tests/translator_eval/eval.py:22-24,193-196`)*

**Run ONE test:** these two scripts **are** the granular suites; `test_router.py` runs the full router corpus and `eval.py --check` runs all 10 problems. The eval can be scoped by source/target **language** (`--from`/`--to`) but exposes **no single-problem selector** — running it runs every problem. *(verified `tests/translator_eval/eval.py`; no per-problem arg found)*

**Lint / build / typecheck / format: NONE.** No such tooling exists in this repo — do not invent or run one. The quality gate is CI (`validate.yml`), not a local formatter.

**Pre-commit hook system: NONE configured for this repo's own development.** There is no `lefthook.yml`, `.husky/`, or `.pre-commit-config.yaml`; `.git/hooks/` holds only the stock samples. (Note: the repo *ships* a `PreToolUse` guard hook for **consumers** of the plugin, but installs no git hook for developing this repo.) The effective quality gate is the CI `validate` workflow — run the two test scripts locally before pushing.

## Project structure / module map

Top-level layout (roles below; for the full component inventory and the end-to-end flow diagram, see [`docs/architecture.md`](docs/architecture.md) — it is the canonical map and is CI-load-bearing, so this section references it rather than duplicating it):

- **`agents/`** — 16 subagent definitions (`*.md`, flat directory; frontmatter `name`/`description`/`tools`). The specialized workers invoked as `@name`.
- **`skills/`** — 10 skill conductors (`<name>/SKILL.md`, foldered; frontmatter `name`/`description`/`disable-model-invocation`). Model-invocable and slash-invoked orchestrators. Includes `overnight` (stands up overnight cloud routines via `RemoteTrigger`).
- **`hooks/`** — `toolbelt-router.sh` (UserPromptSubmit suggester), `pretooluse-guard.sh` (PreToolUse/Bash deny+ask guard), `usage-tracker.sh` (PreToolUse on Task/Skill, opt-in telemetry), `sessionstart-loader.sh` (SessionStart snapshot), `lib-telemetry.sh` (shared lib), `hooks.json` (registration).
- **`docs/`** — `architecture.md`, `components.md`, `design-philosophy.md`, `getting-started.md`, `scheduling.md`, `wiki-generator.md`.
- **`tests/`** — `test_router.py` (router: 16 intents, 100+ cases) and `translator_eval/` (`eval.py` + 10 problems, each with `reference/` solutions across ~11 languages and `spec.json` I/O vectors).
- **`examples/`** — sample outputs per component (e.g. `sample-plan.md`, `sample-pr-review.md`, `sample-onboarding/`, `sample-wiki/`).
- **`bin/toolbelt-metrics.sh`** — usage-telemetry summarizer behind `/toolbelt metrics`.
- **`statusline/toolbelt-statusline.sh`** — cockpit status line.
- **`.claude-plugin/`** — `plugin.json` + `marketplace.json` (distribution).
- **`.github/workflows/validate.yml`** — the one CI workflow.
- **Root:** `README.md`, `CONTRIBUTING.md`, `LICENSE` (PolyForm-Noncommercial-1.0.0), `install.sh`, `.gitignore`.

**Entrypoints:** users start at `/orchestrator` (main dev-cycle conductor), `/agentic-onboard` (on-ramp), or `/toolbelt` (discoverability); agents are reached via `@name`, skills via `/name`. Plugin registration is via `.claude-plugin/plugin.json` + `hooks/hooks.json`; local install via `install.sh`. The test entrypoints are `tests/test_router.py` and `tests/translator_eval/eval.py`.

## Conventions

*(verified against `CONTRIBUTING.md` and `docs/design-philosophy.md`)*

- **New agent →** `agents/<name>.md` with frontmatter `name`/`description`/`tools`, using **least-privilege** `tools` (grant only what it needs).
- **New skill →** `skills/<name>/SKILL.md` with frontmatter `name`/`description`/`disable-model-invocation`. Skills are conductors — prefer delegating heavy work to agents over inlining it.
- **House style** (see `docs/design-philosophy.md`): numbered cardinal rules, explicit auto-detection, a circuit-breaker failure-mode table, a token budget with checkpoints, human gates before any outward action, and **fresh-eyes** reviewers that never read prior reviews of the same artifact.
- **Layout invariant:** agents are flat, skills are foldered.
- **Project-agnostic:** auto-detect the host project's conventions; never hardcode a stack.
- **Counts and descriptions stay in sync** — CI enforces this (see Gotchas).

## Testing + how to verify a change

- **Framework:** plain Python 3 stdlib (no pytest). Tests live in `tests/`.
- **The two suites:** `python3 tests/test_router.py` (router routing) and `python3 tests/translator_eval/eval.py` (translator reference solutions vs. I/O vectors). CI runs both on push and PR.
- **How to verify a change before you push** (the quality bar — meet it before claiming a change is done):
  1. **For a routing change:** run `python3 tests/test_router.py` and ensure it exits 0.
  2. **For a translator/eval change:** run `python3 tests/translator_eval/eval.py` and ensure it exits 0.
  3. **For any change** to `agents/*.md`, `skills/*/SKILL.md`, or counts: confirm CI's structure checks would pass locally — every agent/skill file starts with `---` frontmatter including a `name:` field, and component counts remain consistent (see Gotchas). The CI `validate` workflow is the gate; there is no local pre-commit hook, so running these checks yourself is the substitute.

## Gotchas

*(lead footguns first — these are the ones CI hard-fails on)*

- **Leak-grep (CI hard-fail):** CI runs a case-insensitive `grep` across `*.md`/`*.json`/`*.sh` and fails on any match against a small denylist — two private/employer name fragments plus the pattern for an absolute macOS home path (`/Users/<lowercase>`). The exact regex lives in `.github/workflows/validate.yml:30`. **Never** write an absolute home path (use `~/...` or a repo-relative path), and never write the private name fragments. Note: even *documenting* these strings literally would trip the grep, so refer to them by description, not by spelling them out. *(`.github/workflows/validate.yml:26-36`)*
- **Component counts are load-bearing (CI hard-fail):** adding or removing an agent or skill changes the totals, and CI derives the real counts from the filesystem and asserts the exact strings in **six files** — `README.md`, `docs/components.md`, `docs/architecture.md`, `docs/design-philosophy.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`. Update all six (and update the GitHub "About" via `gh repo edit <owner>/<repo> --description "…"`, which CI only *warns* on). Today the count is **16 agents + 10 skills = 26 components**. *(`.github/workflows/validate.yml:44-72`, `CONTRIBUTING.md:54-65`)*
- **No AI-assistant attribution** in commit messages, PR bodies, or files — and the shipped `pretooluse-guard.sh` *denies* commits that carry an AI co-author trailer or a "generated by an AI assistant" footer. *(`CONTRIBUTING.md:28`, `hooks/pretooluse-guard.sh:67-69`)*
- **Frontmatter is mandatory:** every `agents/*.md` and `skills/*/SKILL.md` must start with `---` and declare a `name:` field, or CI fails. *(`.github/workflows/validate.yml:13-24`)*
- **The "product" is prompt markdown** — the test suite validates **routing** and the **translator eval**, not application logic. There is nothing to "build."
- **`plugin.json` uses strict semver** (currently `0.4.0`). *(`.claude-plugin/plugin.json`)*

## Plan-file convention

> Proposed default (already documented as the auto-detection fallback, not yet a populated directory). There is no `docs/plans/` in the repo today.

When the toolbelt's own architect/orchestrator write a plan for work in this repo, use **`docs/plans/<id>_<slug>.md`** — the convention these agents auto-detect and fall back to. *(documented at `CONTRIBUTING.md:26`; the directory does not yet exist — create it on first use.)*

## Commit & PR policy

- **No AI attribution** — the default and the rule: no AI co-author trailer and no "generated by an AI assistant" footer, anywhere. *(`CONTRIBUTING.md:28`; enforced by `hooks/pretooluse-guard.sh:67-69`)*
- **Never bypass hooks** — do not use `--no-verify` (the shipped guard denies it).
- **No `git add -A`/`--all`/`.`** — stage the specific paths you changed. *(`hooks/pretooluse-guard.sh:11,47`)*
- **No `git push --force`** — use `--force-with-lease`. *(`hooks/pretooluse-guard.sh:11,51`)*
- **Branch naming** — proposed `<id>-<short-slug>` (the toolbelt architect's own convention). *(proposed — needs confirmation; no enforced convention found in-repo.)*
- **Commit prefixes** seen in history: `feat` / `CI` / `Docs` / `Fix`.
- **Outward actions are human-gated** — commit, push, and PR require explicit human confirmation; no autonomous outward actions.

## Security / tenancy notes

This is not a multi-tenant application. The security surface is the hook layer:

- **Hooks** are read-only and make no network calls.
- **`pretooluse-guard.sh`** has a **deny tier** (`git add -A/.`, `git push --force` without lease, `--no-verify`, catastrophic `rm -rf` of `/ ~ $HOME *`, AI-attributed commits) and an **ask tier** (destructive SQL, resets, `terraform destroy`, etc.). *(`hooks/pretooluse-guard.sh`)*
- **Least-privilege** tool grants per agent (frontmatter `tools`).
- **Telemetry is opt-in**, off by default, and writes local JSONL only.
- **No secrets in the repo** — the leak-grep gate enforces this.
- **License:** PolyForm-Noncommercial-1.0.0.
