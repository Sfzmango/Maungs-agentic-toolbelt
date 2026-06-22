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
4. **Regenerate the Codex artifacts** — see [Editing canonical & regenerating Codex artifacts](#editing-canonical--regenerating-codex-artifacts) below.
5. **Update the counts + descriptions** — see [Keeping counts & descriptions in sync](#keeping-counts--descriptions-in-sync). The `validate` workflow fails until they match.

## Adding a new skill

Create `skills/<your-skill>/SKILL.md` with frontmatter (`name`, `description`,
`disable-model-invocation`). Skills are conductors — prefer delegating heavy
work to agents over doing it inline. Then **regenerate the Codex artifacts** (below)
and **update the counts + descriptions** (below).

## Editing canonical & regenerating Codex artifacts

`agents/*.md` + `skills/*/SKILL.md` + `hooks/` are the **single canonical source**.
The Codex artifacts under `codex-agents/` and
`plugins/maungs-agentic-toolbelt/{skills,hooks,bin}/` are **generated** from that
source by `tools/build.py` — never hand-edited. After ANY change to a canonical
`.md` or hook `.sh`, regenerate and commit the result:

```bash
python3 tools/build.py --target codex          # regenerate the Codex artifacts
python3 tools/build.py --target codex --check   # CI mode: fails on any drift
python3 tools/build.py --target claude --check  # validate-only: Claude never rewritten
python3 tools/validate_codex.py                 # clean-install artifact validation
python3 tests/test_codex_build.py               # generator + gate-semantics tests
```

CI's drift guard re-runs the generator and turns red with a "regenerate" message
if the committed Codex artifacts don't match canonical, so regenerating is not
optional. The Claude side stays untouched — the Claude emitter is validate-only
and writes nothing. See [`docs/codex.md`](docs/codex.md) and
[`docs/architecture.md`](docs/architecture.md).

## Keeping counts & descriptions in sync

Adding or removing a component changes the totals, and the `validate` workflow **fails**
until every in-repo description matches the real counts (derived at CI time from
`agents/*.md` + `skills/*/SKILL.md`). After adding an agent or skill, update:

- **the listing** — the README "Agents"/"Skills" section and the `docs/components.md` index;
- **the counts** (`N agents + M skills`, `N+M components`) in `README.md`, `docs/components.md`,
  `docs/architecture.md`, `docs/design-philosophy.md`, and `.claude-plugin/{plugin,marketplace}.json`;
- **the GitHub "About"** description — out-of-band metadata (not a file, and not writable by the
  default CI token), so `validate` only *warns* with the exact command to run:
  `gh repo edit <owner>/<repo> --description "…"`.

## House-style checklist

- [ ] Least-privilege tools (read-only unless it must write)
- [ ] Auto-detects conventions instead of hardcoding a stack
- [ ] Human confirmation gate before any commit / push / external post
- [ ] Circuit-breaker table for failure modes
- [ ] Token budget with checkpoints
- [ ] Fresh-eyes reviewers never read prior reviews of the same artifact
- [ ] Counts + descriptions updated (CI `validate` enforces the in-repo ones; update the GitHub About too)
