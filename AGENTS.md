# AGENTS.md — Maungs-agentic-toolbelt

Guidance for any coding agent working in this repo. Verified against commit `cf4d0e9`.

## Overview

This repo is a project-agnostic, human-gated multi-agent workflow for Claude Code, and is itself a Claude Code **plugin** rather than an application. It ships **16 agents + 9 skills (25 components)**: agents are `@name` subagents (specialized workers) and skills are `/name` conductors (orchestrators). Each component auto-detects the host project's stack and conventions at runtime — nothing is hardcoded to one language. It is distributed as a plugin via the `maung-tools` marketplace and via a copy/symlink `install.sh` into `~/.claude`.

## Setup / commands

Every command is cited to its source. There is no install/build/lint/format toolchain to wrap.

- **Install into `~/.claude`:** `./install.sh` (copy). Variants: `--symlink` (track updates via `git pull`), `--target DIR`, `--dry-run`. *(from `install.sh:6-9`)*
- **Install as a plugin:** `/plugin marketplace add Sfzmango/Maungs-agentic-toolbelt` then `/plugin install maungs-agentic-toolbelt@maung-tools`. *(from `README.md:15`)*
- **Test — router regression:** `python3 tests/test_router.py`. *(from `.github/workflows/validate.yml:39`)*
- **Test — translator eval:** `python3 tests/translator_eval/eval.py`; `--check` is the default deterministic mode, `--live --from <lang> --to <lang,...|all>` invokes the translator. *(from `.github/workflows/validate.yml:42`, `tests/translator_eval/eval.py:22-24`)*

**Run ONE test:** these two scripts are the granular suites. `eval.py` can be scoped by source/target **language** (`--from`/`--to`) but has **no single-problem selector** — running it runs every problem.

**Lint / build / typecheck / format: NONE.** No such tooling exists in this repo — do not invent or run one.

**Pre-commit hooks: NONE configured for this repo's own development** (no `lefthook.yml`, `.husky/`, or `.pre-commit-config.yaml`; only stock `.git/hooks` samples). The quality gate is the CI `validate` workflow — run the two test scripts locally before pushing.

## Structure

- **`agents/`** — 16 subagent defs (`*.md`, flat; frontmatter `name`/`description`/`tools`).
- **`skills/`** — 9 skill conductors (`<name>/SKILL.md`, foldered; frontmatter `name`/`description`/`disable-model-invocation`).
- **`hooks/`** — `toolbelt-router.sh` (UserPromptSubmit suggester), `pretooluse-guard.sh` (deny+ask guard), `usage-tracker.sh` (opt-in telemetry), `sessionstart-loader.sh`, `lib-telemetry.sh`, `hooks.json`.
- **`docs/`** — `architecture.md` (the canonical module map + flows), `components.md`, `design-philosophy.md`, `getting-started.md`, `scheduling.md`, `wiki-generator.md`.
- **`tests/`** — `test_router.py` (router) and `translator_eval/` (`eval.py` + 10 problems, each with `reference/` solutions and `spec.json` I/O vectors).
- **`examples/`** — sample outputs per component.
- **`bin/toolbelt-metrics.sh`**, **`statusline/toolbelt-statusline.sh`**, **`.claude-plugin/`** (`plugin.json` + `marketplace.json`), **`.github/workflows/validate.yml`**.
- **Root:** `README.md`, `CONTRIBUTING.md`, `LICENSE`, `install.sh`.

**Entrypoints:** users start at `/orchestrator`, `/agentic-onboard`, or `/toolbelt`; agents via `@name`, skills via `/name`. Test entrypoints are `tests/test_router.py` and `tests/translator_eval/eval.py`. See `docs/architecture.md` for the full inventory and end-to-end flow.

## Conventions

*(verified against `CONTRIBUTING.md` and `docs/design-philosophy.md`)*

- **New agent →** `agents/<name>.md`, frontmatter `name`/`description`/`tools`, **least-privilege** tool grants.
- **New skill →** `skills/<name>/SKILL.md`, frontmatter `name`/`description`/`disable-model-invocation`; skills delegate heavy work to agents.
- **House style:** numbered cardinal rules, explicit auto-detection, a circuit-breaker table, a token budget, human gates for outward actions, and fresh-eyes reviewers that never read prior reviews of the same artifact.
- Agents are flat, skills are foldered. Everything is project-agnostic — auto-detect, never hardcode a stack.
- Counts and descriptions are kept in sync (CI-enforced — see Gotchas).

## Testing

- **Framework:** plain Python 3 stdlib (no pytest); tests live in `tests/`.
- **Suites:** `python3 tests/test_router.py` and `python3 tests/translator_eval/eval.py`; CI runs both on push and PR.
- **Verify a change before pushing:** run `test_router.py` for routing changes and `eval.py` for translator/eval changes (both must exit 0); for changes to `agents/*.md` / `skills/*/SKILL.md` / counts, confirm every file starts with `---`+`name:` frontmatter and the component counts stay consistent.

## Gotchas

- **Leak-grep (CI hard-fail):** CI greps `*.md`/`*.json`/`*.sh` and fails on absolute home paths like `/Users/...` or private reference strings. Use `~/...` or repo-relative paths. *(`.github/workflows/validate.yml:30`)*
- **Component counts are load-bearing (CI hard-fail):** adding/removing an agent or skill requires updating the count strings in `README.md`, `docs/components.md`, `docs/architecture.md`, `docs/design-philosophy.md`, `.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json` (plus the GitHub "About", which CI only warns on). Today: **16 agents + 9 skills = 25 components**. *(`.github/workflows/validate.yml:44-72`)*
- **No AI-assistant attribution** in commits, PR bodies, or files (the shipped guard denies AI-attributed commits). *(`CONTRIBUTING.md:28`)*
- **Frontmatter is mandatory:** every `agents/*.md` and `skills/*/SKILL.md` must start with `---` and a `name:` field. *(`.github/workflows/validate.yml:13-24`)*
- **Do not** use `git add -A`/`.`, `git push --force` (use `--force-with-lease`), or `--no-verify` — the shipped guard denies all three.
- The "product" is prompt markdown; tests validate routing and the translator eval, not application logic. `plugin.json` uses strict semver (currently `0.3.0`).
