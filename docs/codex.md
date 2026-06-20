# Running the toolbelt on the OpenAI Codex CLI

The toolbelt is **model-agnostic**: the same 16 agents and 11 skills that run on
Claude Code also run on the **OpenAI Codex CLI**. Components are defined **once**
— the canonical `agents/*.md` + `skills/*/SKILL.md` — and a generator
(`tools/build.py`) renders them into Codex's native forms. You never hand-edit a
Codex artifact; you edit the canonical source and regenerate.

## Two-track distribution (and why)

Codex's plugin manifest **cannot carry `agents` + `hooks`** — only skills. So the
Codex port ships on **two tracks**:

| Track | Carries | How you get it |
|-------|---------|----------------|
| **Marketplace / plugin** | the 11 skills | `codex plugin marketplace add …` + `codex plugin install …` |
| **Installer** | the 16 agents + the 4 hooks | `./install-codex.sh` |

This split is a Codex platform constraint, not a preference: the manifest format
forbids bundling agents and hooks, so the installer owns that track while the
marketplace owns skills.

## Install

### 1. Skills (marketplace — preferred)

```sh
codex plugin marketplace add Sfzmango/Maungs-agentic-toolbelt
codex plugin install maungs-agentic-toolbelt
```

The marketplace reads `.agents/plugins/marketplace.json`, whose plugin `source`
points at `plugins/maungs-agentic-toolbelt/`, where the skills-only manifest
(`.codex-plugin/plugin.json`) and the generated `skills/<name>/SKILL.md` live.

### 2. Agents + hooks (installer)

```sh
./install-codex.sh --dry-run     # preview first — changes nothing
./install-codex.sh               # install agents + hooks into ~/.codex
```

The installer:

1. copies each generated `codex-agents/<name>.toml` into `~/.codex/agents/`;
2. copies the five generated `codex-hooks/*.sh` into `~/.codex/hooks/`;
3. **merges** the generated `codex-hooks/hooks.json` into `~/.codex/hooks.json`
   — it never clobbers an existing `notify` / `mcp_servers` or your existing
   hooks — after substituting every `__TOOLBELT_HOOK_DIR__` placeholder with the
   absolute `~/.codex/hooks` install dir so each `command` resolves to the copied
   script;
4. prints MCP setup guidance (it does **not** run `codex mcp add` for you).

`--skills` is an opt-in fallback that also copies the skills locally when you are
not using the marketplace. `--target DIR` and `--dry-run` mirror `install.sh`.

### 3. MCP servers

Most agents expect a **github** MCP server; `@developer` uses **playwright** for
UI verification; `@code-translator` uses **context7** for doc grounding. Check
what you have and add what you need:

```sh
codex mcp list
codex mcp add …      # the installer prints the servers it expects
```

## Verify it is live

```sh
ls ~/.codex/agents            # 16 *.toml agents
@architect …                  # @mention an agent in a Codex thread
# trigger a skill in chat (model-invoked; no slash layer on Codex)
```

Confirm `@developer` / `@architect` still **PAUSE** on the commit/push gates —
on Codex the `AskUserQuestion` mechanic is rewritten to an explicit "ask the user
in chat and wait for an explicit 'yes' / confirmation before proceeding"
instruction, so the human gates survive.

### Install jq for full `PreToolUse` guard coverage

The `PreToolUse` guard (`pretooluse-guard.sh`) needs **jq** to parse the event
and decide deny/ask. With jq present, an unrecognized PreToolUse schema degrades
to **ask** (a human prompt). **Without jq the guard allows** — it exits early at
the top-of-file `command -v jq … || exit 0`, exactly as the canonical Claude
guard does. This is intentional (no noisy "ask on every command" fallback), so
**install jq for full guard coverage**. The installer already warns when jq is
absent (it also needs jq — or python3 — to merge `hooks.json` safely).

## How the artifacts are generated

```sh
python3 tools/build.py --target codex          # regenerate the Codex artifacts
python3 tools/build.py --target codex --check  # CI mode: fail on any drift
python3 tools/build.py --target claude --check # validate-only: Claude never rewritten
```

- **Agents** → `codex-agents/<name>.toml`. The body becomes a TOML literal
  `developer_instructions` string; `sandbox_mode` derives from the canonical
  `tools:` allowlist (`read-only` unless `Edit`/`Write`); `mcp_servers`
  enumerates every distinct `mcp__<server>__` prefix (so `@code-translator`
  carries `["context7"]`). `model` / `model_reasoning_effort` are omitted by
  design (model-agnostic) — an empty override hook is left in each file.
- **Skills** → `plugins/maungs-agentic-toolbelt/skills/<name>/SKILL.md`
  (+ `agents/openai.yaml` UI metadata), body-transformed,
  `disable-model-invocation` stripped.
- **Hooks** → `codex-hooks/*.sh` (genuinely generated, not copied — the bodies
  carry Claude-only assumptions) + a `codex-hooks/hooks.json` template using the
  `__TOOLBELT_HOOK_DIR__` placeholder.

A **CI drift guard** re-runs the generator and fails on any diff between the
freshly-generated and committed Codex artifacts, so a canonical `.md` edit that
isn't regenerated turns CI red with a "regenerate" message. **Edit canonical,
then regenerate** — never hand-edit a Codex artifact.

## Known divergence: telemetry writer vs. readers

Telemetry is opt-in and off by default. On Codex the generated `lib-telemetry.sh`
**writer** homes the usage log under `~/.codex/maungs-toolbelt/usage.jsonl` (not
`~/.claude`). The **readers** — `bin/toolbelt-metrics.sh` (the `/toolbelt
metrics` summarizer) and `statusline/toolbelt-statusline.sh` (the cockpit tally)
— still default to `~/.claude`. So on a Codex-only machine, reading the Codex
telemetry requires setting `MAUNGS_TOOLBELT_LOG` (both readers honor it):

```sh
export MAUNGS_TOOLBELT_LOG="$HOME/.codex/maungs-toolbelt/usage.jsonl"
```

A follow-up will port the reader defaults so this is no longer needed. The
writer/reader loop is **not** closed by the writer rewrite alone — documented,
not claimed closed.

The same applies to the **`@todo` backlog**: its store, the `SessionStart` loader
that resurfaces open todos, and the router suggestion all default to
`~/.claude/maungs-toolbelt/todos/<slug>.md` on Codex too. Because the `@todo`
writer and the loader/router readers all agree on that path, the feature works
end-to-end (a Codex-only machine just gets a `~/.claude/maungs-toolbelt/todos/`
directory). Re-homing it to `~/.codex` is the same kind of follow-up as the
telemetry readers above — documented, not claimed closed.

## Adding another target (cursor / aider / …)

The generator is a target-agnostic core (`build.py`, `common.py`, `transforms.py`)
plus per-target emitters (`emit/target_claude.py`, `emit/target_codex.py`).
Adding a target is **"add an emitter + a target-table row,"** not a
rearchitecture. cursor / aider / others are accommodated by the seam but not
built here.
