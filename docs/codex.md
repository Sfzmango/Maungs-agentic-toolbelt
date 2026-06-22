# Running the toolbelt on the OpenAI Codex CLI

The toolbelt is **model-agnostic**: the same 16 agents and 11 skills that run on
Claude Code also run on the **OpenAI Codex CLI**. Components are defined **once**
— the canonical `agents/*.md` + `skills/*/SKILL.md` — and a generator
(`tools/build.py`) renders them into Codex's native forms. You never hand-edit a
Codex artifact; you edit the canonical source and regenerate.

## Distribution model

Codex plugins can bundle skills, lifecycle hooks, and helper scripts. They do not
currently bundle custom TOML subagents, so the Codex port has two install pieces:

| Piece | Carries | Install |
|-------|---------|---------|
| **Marketplace plugin** | skills, lifecycle hooks, router, guard, telemetry, metrics helper | `codex plugin marketplace add …` then `codex plugin add …` |
| **Agent installer** | custom subagents under `~/.codex/agents/` | `./install-codex.sh` |

The plugin is the normal path. `./install-codex.sh --standalone` is a fallback
that also installs hooks and skills without the plugin.

## Install

```sh
codex plugin marketplace add Sfzmango/Maungs-agentic-toolbelt
codex plugin add maungs-agentic-toolbelt@maung-tools

./install-codex.sh --dry-run
./install-codex.sh
```

Then:

1. Open `/hooks`, review the plugin-bundled hooks, and trust them.
2. Start a new Codex thread so plugin skills, hooks, and custom agents are loaded.
3. Check MCP servers with `codex mcp list`.

Most workflows expect a GitHub MCP server. The `developer` subagent optionally
uses Playwright; `code-translator` uses Context7.

### Standalone fallback

```sh
./install-codex.sh --standalone
```

Standalone mode installs:

- custom agents to `~/.codex/agents/`;
- hooks to `~/.codex/hooks/` and merges them into `~/.codex/hooks.json`;
- skills to the documented user skill directory, `~/.agents/skills/`.

`--skills` remains a compatibility alias for `--standalone`. `--target DIR`
installs into `DIR/.codex` and `DIR/.agents`.

## Invocation on Codex

- Explicit skill invocation: `$toolbelt`, `$orchestrator <topic>`, `$todo`.
- Custom subagent: ask Codex to spawn it by type, for example “spawn the
  `architect` subagent to plan this issue.”
- Implicit skill invocation remains enabled through each skill's
  `agents/openai.yaml` metadata.

Claude's `/skill` and `@agent` shorthand are rewritten in generated Codex
artifacts; they are not the documented Codex invocation surface.

## Verify it is live

```sh
ls ~/.codex/agents
codex plugin list
```

In a new thread:

1. Run `$toolbelt`.
2. Ask Codex to spawn the `architect` subagent.
3. Confirm the `developer` and `architect` subagents still stop at commit/push
   confirmation gates.
4. Trigger a router-matched prompt and confirm the hook contributes one toolbelt
   suggestion.

## Hook behavior

The plugin registers:

- `UserPromptSubmit` → prompt router and explicit-skill telemetry;
- `PreToolUse` for Bash → command guard;
- `SessionStart` → project snapshot and private todo count;
- `SubagentStart` → custom-agent usage telemetry.

Hooks are trust-gated by Codex. If they do not run, check `/hooks` first.

The guard requires `jq`. Without it, parsing fails open and commands are allowed.
Codex `PreToolUse` supports `allow` and `deny`, not Claude's `ask`. For risky
ask-tier commands, the generated guard:

1. denies the first attempt with a detailed reason;
2. instructs Codex to ask the user and wait;
3. allows one confirmed retry prefixed with
   `MAUNGS_TOOLBELT_CONFIRMED=1`.

Hard-deny rules still run on the confirmed retry.

## Generated artifacts

```sh
python3 tools/build.py --target codex
python3 tools/build.py --target codex --check
python3 tools/build.py --target claude --check
python3 tools/validate_codex.py
```

- `validate_codex.py` checks the clean-install surface: wrappers, component
  frontmatter, `agents/openai.yaml`, JSON, TOML, shell syntax, and hook references.
- **Agents** → `codex-agents/<name>.toml`.
- **Skills** → `plugins/maungs-agentic-toolbelt/skills/<name>/SKILL.md` plus
  current `agents/openai.yaml` interface/policy metadata.
- **Hooks** → `plugins/maungs-agentic-toolbelt/hooks/`.
- **Metrics helper** → plugin `bin/` and the `$toolbelt` skill's `scripts/`.

Generated Codex artifacts use `$skill`, explicit named-subagent wording,
Codex-local state paths, Codex memories, and current hook schemas. The
`dossier-jobs` skill uses automation tools when available; in Codex CLI it
produces complete Codex app Automation configurations and never claims it
created them.

CI regenerates the owned roots and fails on missing, drifted, or stray files.
Edit canonical sources, regenerate, and commit both source and generated output.

## Local state

Codex-local toolbelt state is self-consistent:

- telemetry: `~/.codex/maungs-toolbelt/usage.jsonl`;
- private todos: `~/.codex/maungs-toolbelt/todos/<slug>.md`;
- metrics: `$toolbelt metrics` runs the plugin-bundled helper.

`MAUNGS_TOOLBELT_LOG` still overrides the telemetry path.

## Remaining platform differences

- **Custom agents require the separate installer.** Plugins do not package the
  TOML files under `~/.codex/agents/`.
- **MCP grants are server-granularity.** A canonical per-tool allowlist becomes
  a whole-server grant in Codex. Use least-privilege MCP credentials.
- **Custom Claude statusline parity is unavailable.** Codex's `/statusline`
  configures standard footer fields but does not consume the toolbelt's custom
  pipeline-status file.
- **CLI automation creation is unavailable.** `$dossier-jobs` emits Codex app
  Automation setup when no automation-management tools are present.

## Official Codex references

- [Build plugins](https://developers.openai.com/codex/plugins/build)
- [Lifecycle hooks](https://developers.openai.com/codex/hooks)
- [Skills](https://developers.openai.com/codex/skills)
- [Custom agents](https://developers.openai.com/codex/subagents)

## Adding another target (cursor / aider / …)

The generator is a target-agnostic core (`build.py`, `common.py`, `transforms.py`)
plus per-target emitters (`emit/target_claude.py`, `emit/target_codex.py`).
Adding a target is **"add an emitter + a target-table row,"** not a
rearchitecture. cursor / aider / others are accommodated by the seam but not
built here.
