# Adapting & extending the pipeline

These agents and skills are **project-agnostic by design** — they auto-detect a
project's stack and conventions at runtime rather than hardcoding one. You
usually don't need to edit them to use them on a new repo. This guide covers the
few things you *may* want to configure, and how to add your own components.

## How auto-detection works

On each run, the agents/skills infer the project's shape from, in order:

1. **`CLAUDE.md` / `CLAUDE.local.md`** — cardinal rules, house voice, gotchas.
2. **Package manifests** — `package.json`, `Gemfile`, `pyproject.toml`,
   `go.mod`, `Cargo.toml`, etc. → language, framework, test runner, lint, build.
3. **Pre-commit hook config** — `lefthook.yml`, `.husky/`, `.pre-commit-config.yaml`.
4. **CI / deploy** — `.github/workflows/`, `Procfile`, Dockerfiles.
5. **Plan/roadmap files** — to match the plan-file convention.

The single highest-leverage thing you can add to a target project is a good
**`CLAUDE.md`**: it's where these agents learn your cardinal rules.

## What you might configure

| Assumption | Default behaviour | Where to change it |
| --- | --- | --- |
| Plan-file path | auto-detected, falls back to `docs/plans/<id>_<slug>.md` | your `CLAUDE.md` / existing plan files |
| Default branch | auto-detected from `git` | n/a (detected) |
| Commit attribution | **no** `Co-Authored-By` / "Generated with Claude" footers | the relevant agent/skill's rules |
| Pre-commit hook system | auto-detected | n/a (detected) |
| Wiki location | `docs/wiki/` | `skills/wiki-generator/SKILL.md` |

## Adding a new agent

1. Create `agents/<your-agent>.md` with YAML frontmatter:
   ```yaml
   ---
   name: your-agent
   description: One sentence on when to invoke it (this is what routing reads).
   tools: Read, Grep, Bash   # least-privilege — grant only what it needs
   ---
   ```
2. Follow the house style (see `docs/design-philosophy.md`): numbered cardinal
   rules, explicit auto-detection, a circuit-breaker table, a token budget, and
   human gates for any outward-facing action.
3. Re-run `./install.sh` (or `git pull` if you symlinked).

## Adding a new skill

Create `skills/<your-skill>/SKILL.md` with frontmatter (`name`, `description`,
`disable-model-invocation`). Skills are conductors — prefer delegating heavy
work to agents over doing it inline.

## House-style checklist

- [ ] Least-privilege tools (read-only unless it must write)
- [ ] Auto-detects conventions instead of hardcoding a stack
- [ ] Human confirmation gate before any commit / push / external post
- [ ] Circuit-breaker table for failure modes
- [ ] Token budget with checkpoints
- [ ] Fresh-eyes reviewers never read prior reviews of the same artifact
