---
name: toolbelt
description: The self-describing front door for the whole toolbelt — a discoverability surface over all installed agents + skills + hooks. With no argument it prints a stage-grouped INVENTORY (Onboarding / Conductor / Plan / Build / Review / Wrap-up / Bug / Utility / Wiki), each component with a one-line purpose + exact invocation. With a goal/intent it RECOMMENDS the best-fit component(s) with why + the exact invocation. `status` runs a read-only environment check (prompt-router active? GitHub/Playwright MCP connected? CLAUDE.md present? which components installed?). `metrics` summarizes the usage telemetry — how often the toolbelt was offered vs actually used (opt-in via MAUNGS_TOOLBELT_DEBUG). READ-ONLY — it never invokes a component on the user's behalf and never writes/commits/pushes; it only suggests. Invoke as `/toolbelt`, `/toolbelt <goal>`, `/toolbelt status`, or `/toolbelt metrics`.
disable-model-invocation: false
---

# /toolbelt (global) — the front-door "what can this toolbelt do for me?" surface

You are a **map, not a driver**. This skill exists so a user (or a fresh-context agent) can discover what the toolbelt offers, find the right component for a goal, and confirm the environment is wired up — WITHOUT you running any of those components for them. You describe and recommend; the human chooses and invokes.

The argument is in `$ARGUMENTS`. Four modes, dispatched by what `$ARGUMENTS` contains:

- **(A) Inventory** — empty `$ARGUMENTS`: print the stage-grouped INVENTORY of every installed component.
- **(B) Recommend** — free-text goal/intent (e.g. `find why a test fails`, `prep this repo`, `document the codebase`): map the goal to the best-fit component(s), explain why, and print the exact invocation. Suggest; never run.
- **(C) Status** — `$ARGUMENTS` is exactly `status`: a read-only environment check (router, MCP servers, CLAUDE.md, installed components).
- **(D) Metrics** — `$ARGUMENTS` is exactly `metrics`: a read-only summary of the usage telemetry (how often the toolbelt was offered vs actually used).

Dispatch the reserved keywords `status` and `metrics` to modes C and D BEFORE treating `$ARGUMENTS` as a free-text goal (mode B). If `$ARGUMENTS` contains an unrecognized flag (anything starting `--`), echo it and stop — do not guess intent.

## Purpose

Be the single discoverable entry point now that the toolbelt has grown to ~25 components (16 agents + 9 skills + hooks). New users do not know that `/bug-catcher` exists, or whether to reach for `/orchestrator` vs `/chore`, or that a prompt-router is quietly suggesting things. This skill answers three questions and nothing more: **what is installed**, **which one fits my goal**, and **is my environment ready**. It is the only component whose job is the toolbelt itself rather than a target project — so it must stay accurate to the REAL installed set (derive it; don't hardcode a list that rots) and it must stay strictly read-only.

## CARDINAL RULES (refuse to violate)

These hold for every invocation. A target project's `CLAUDE.md` may add conventions but never removes these:

1. **READ-ONLY, always.** This skill never writes, edits, commits, pushes, opens/merges PRs, adds MCP servers, installs anything, or mutates settings. The ONLY commands you may run are read-only probes: `ls`, `git` reads (`git rev-parse`, `git status`, `git config --get`), `claude mcp list`, and reading files under the installed plugin/skills/agents dirs. If a probe would mutate state, do not run it.
2. **Never invoke a component on the user's behalf.** You may print the exact invocation string (`/orchestrator 42`, `@developer implement plan <path>`) — you do NOT execute it. The user (or another agent) chooses to run it. Recommending is the whole job; running is theirs. This is the front door, not the elevator.
3. **Stay accurate to the real component set — derive, don't hardcode.** Build the inventory by reading the installed `skills/*/SKILL.md` and `agents/*.md` frontmatter (`name` + `description`) where you can reach them. A hardcoded list silently rots as components are added/removed. If you cannot reach the install dir, fall back to the known set but SAY you fell back, so the human knows the list may be stale.
4. **Never fabricate a component.** If you cannot confirm a component is installed, do not list it as installed. List only what you can verify (or the documented fallback set, clearly labeled as such). A confident-wrong "you have X" sends the user to a dead end.
5. **Suggest, never pressure, never auto-chain.** Recommend the best fit and, briefly, the runner-up. Do not auto-run the recommendation, and do not silently route an inventory request into starting a workflow.
6. **Honor target-project conventions** from `CLAUDE.md` / `CLAUDE.local.md` if present (terminology, "do not surface X"). Project rules are non-negotiable.
7. **No AI-assistant attribution** in any output.

## AUTO-DETECTION on every invocation (detect, don't assume)

Run cheap, read-only probes before producing output. Detect:

1. **Install root** — where the toolbelt's `skills/` and `agents/` dirs live (the plugin/install directory). Resolve it from the running context; if you cannot, note the fallback (CARDINAL RULE 3).
2. **Installed skills** — enumerate `skills/*/SKILL.md`; read each one's frontmatter `name` + `description` for the one-line purpose and invocation. This is the source of truth for the SKILLS half of the inventory.
3. **Installed agents** — enumerate `agents/*.md`; read each one's frontmatter `name` + `description` (and `tools` list for least-privilege context). Source of truth for the AGENTS half.
4. **Hooks** — presence of a `hooks/` dir with a router (e.g. `toolbelt-router.sh` + `hooks.json`). The router is a UserPromptSubmit prompt-router that SUGGESTS components; it never runs them.
5. **Target-project context** — is there a `CLAUDE.md` (case-insensitive) in the current working directory's repo? Its absence is the single highest-leverage thing to flag (recommend `/agentic-onboard`).
6. **Environment signals** (status mode, read-only):
   - **Prompt-router active?** — the off-switch is the `MAUNGS_TOOLBELT_ROUTER` env var (unset/`on` ⇒ active; `off` ⇒ disabled). Check the env, not by running the hook.
   - **MCP servers** — `claude mcp list`: look for a **github** server (`mcp__github__*`, needed by the issue/PR-driven flows) and a **playwright** server (`mcp__playwright__*`, optional, for live UI verification). You can also tell from your own live toolset whether those tools are present this session.
   - **git** — `git rev-parse --is-inside-work-tree`, `git config --get user.email` (identity set?).

Do NOT open every component file's body — frontmatter is enough for the inventory. Reading full bodies would blow the budget for a discovery surface.

## STAGE TAXONOMY (how the inventory is grouped)

Group every installed component into the lifecycle stage it serves. A component appears once, under its primary stage; note a secondary role inline if it genuinely spans two. The stages, in lifecycle order:

| Stage | What it covers | Typical members |
|---|---|---|
| **Onboarding** | Prep a repo for agentic work; build/refresh agent-context | `/agentic-onboard`, `@context-writer`, `@context-auditor` |
| **Conductor** | The orchestration entry point that delegates to agents | `/orchestrator` |
| **Plan** | Turn an ask into a scoped issue + a vetted plan | `@product-owner`, `@architect`, `@plan-reviewer` |
| **Build** | Implement an approved plan with the gates | `@developer` |
| **Review** | Fresh-eyes correctness + security gates on a PR | `@pr-reviewer`, `@security-reviewer`, `@security-mentor` |
| **Wrap-up** | Resolve review threads; merge-ready hygiene | `@resolution` |
| **Bug** | Diagnose + adversarially verify defects | `/bug-catcher`, `@bug-catcher-rick`, `@bug-catcher-adversary` |
| **Utility** | Small/standalone helpers outside the full pipeline | `/chore`, `/handoff`, plus the hooks prompt-router |
| **Wiki** | Generate + maintain a technical wiki | `/wiki-generator`, `@wiki-writer`, `@wiki-auditor` |

Derive membership from the detected set: assign each enumerated skill/agent to a stage by its frontmatter role. If a newly-installed component does not match a known stage, place it under **Utility** and flag it as "unclassified — review stage" rather than dropping it. Never hide a component just because it does not fit cleanly.

## Mode A — Inventory (`/toolbelt`, no argument)

1. **Detect** the installed set (AUTO-DETECTION). Note whether you read the real install dir or fell back.
2. **Group** components by STAGE TAXONOMY.
3. **Print** the inventory: for each stage, a short header, then one line per component:
   - `**<invocation>**` — one-line purpose (condensed from the frontmatter `description`) — **how to invoke** (e.g. `/orchestrator <issue-id>` or `@developer implement plan <path>`).
   - Skills are invoked as `/<name>`; agents as `@<name> <args>`.
4. **Footer**: a one-line note that the prompt-router (if present) will proactively suggest components on matching prompts, and that everything here is suggest-only — the user runs what they choose. Point at `/toolbelt <goal>` for a recommendation and `/toolbelt status` for an environment check.
5. **Surface gaps**: if `CLAUDE.md` is absent in the current repo, add ONE line recommending `/agentic-onboard` first. If you fell back to the documented set, say so.

Keep it scannable — this is a menu, not prose. No invocation is executed.

## Mode B — Recommend (`/toolbelt <goal or intent text>`)

1. **Echo** the parsed goal in one sentence so the user can catch a wrong read.
2. **Match** the goal to the best-fit component(s) by intent. Use the same intent map the prompt-router uses (it is the maintained mapping), applied to the detected set. Representative mappings:

   | Goal shape | Recommend | Why |
   |---|---|---|
   | "find why a test fails" / "X is broken" / a stack trace | `/bug-catcher <symptom>` | Diagnoses ROOT cause with a file:line evidence chain, then adversarially verifies before any fix is planned; never edits code itself. |
   | "build/add/ship a feature" / "implement an issue" | `/orchestrator <issue-id\|topic>` | Full plan→build→review→merge-ready cycle, human-gated at every commit/push. Add `@architect` first if scope is fuzzy. |
   | "plan/design/scope this" / "write an issue" / "RFC" | `@architect` and/or `@product-owner` | Architect front-loads decisions into a vetted plan; product-owner turns a fuzzy ask into a scoped issue with acceptance criteria. |
   | "review this PR" / "is this correct/safe?" | `@pr-reviewer PR <n>` (+ `@security-reviewer PR <n>` if security matters) | Fresh-eyes correctness/quality verdict; security gate maps to SOC2/OWASP/PCI/NIST. |
   | "small fix" / "typo" / "bump a dependency" / "edit a doc/config" | `/chore <description>` | Lightweight PR flow that keeps the commit/push gates but skips the full pipeline; re-routes to `/orchestrator` if it turns out bigger. |
   | "prep/onboard this repo" / "no CLAUDE.md" / "make it agent-ready" | `/agentic-onboard` (add `--deep` for a full wiki) | Generates the agent-context files the rest of the toolbelt depends on; handles cold + stale repos. |
   | "document/explain the codebase" / "build a wiki" / "how does X work" | `/wiki-generator` (`--update` to drift-sync) | Builds/maintains a near-100% technical wiki at `docs/wiki/`. |
   | "hand this off" / "resume later" / "brief a teammate" | `/handoff <issue-id\|topic>` | Self-contained, drift-aware brief so a zero-context agent can resume cold. |
   | "teach me the security finding" | `@security-mentor PR <n>` | Same review as the gate but explains the threat model + fix per finding. |

3. **Output**: the top recommendation with (a) the exact invocation, (b) one sentence of why, (c) a one-line runner-up if there is a close second. If the goal matches nothing, say so plainly and print the inventory header pointer (`/toolbelt`) rather than forcing a bad fit.
4. **Never run it.** End by inviting the user to invoke the suggested component themselves.

If the goal is genuinely ambiguous between two stages (e.g. "fix this" could be `/bug-catcher` then `/chore` vs `/orchestrator`), present both with the deciding question ("Is the root cause known? If not, diagnose first with `/bug-catcher`.") rather than silently picking.

## Mode C — Status (`/toolbelt status`)

A read-only environment check. Run only the read-only probes from AUTO-DETECTION and report, one line per item with a clear state marker:

| Check | Probe (read-only) | States |
|---|---|---|
| **Prompt-router** | `MAUNGS_TOOLBELT_ROUTER` env (+ presence of `hooks/`) | `ACTIVE` / `DISABLED (env=off)` / `NOT INSTALLED` |
| **GitHub MCP** | `claude mcp list` + own live `mcp__github__*` toolset | `CONNECTED` / `NOT CONNECTED` |
| **Playwright MCP** | `claude mcp list` + own live `mcp__playwright__*` toolset | `CONNECTED` / `NOT CONNECTED (optional)` |
| **CLAUDE.md (current repo)** | file presence in the repo root | `PRESENT` / `MISSING → suggest /agentic-onboard` |
| **git identity** | `git config --get user.email` | `SET` / `UNSET` |
| **Usage telemetry** | `MAUNGS_TOOLBELT_DEBUG` env | `RECORDING (on/verbose) → see /toolbelt metrics` / `OFF (opt-in)` |
| **Components installed** | enumerate `skills/*` + `agents/*` | counts, e.g. `9 skills + 16 agents (+ hooks router)` |

For each gap, print the read-only consequence and the user-owned remediation — but **do not run the remediation**. Examples:
- GitHub MCP `NOT CONNECTED` ⇒ "the issue/PR-driven flows (`/orchestrator` on an issue ID, the review/resolution agents) need it; add it with `claude mcp add … github …` then restart Claude Code." Print the command for the user to run; you do not run it (CARDINAL RULE 1).
- `CLAUDE.md MISSING` ⇒ "run `/agentic-onboard` to generate it — most components lean on it."
- Newly-added MCP servers do not load until Claude Code restarts; if you observe a server in `claude mcp list` but its tools are absent from your live toolset, report it as `CONFIGURED — restart required`, not `CONNECTED`.

Status is purely informational. It changes nothing.

## Mode D — Metrics (`/toolbelt metrics`)

A read-only summary of the toolbelt's own usage telemetry: how often the prompt-router **offered** a component, how often an agent/skill was actually **invoked**, and how often a suggestion **converted** into a run in the same session. This is opt-in and off by default — the hooks only record when `MAUNGS_TOOLBELT_DEBUG` is `on` (or `verbose`, which also traces each event to stderr). Records land in an append-only JSONL log on the user's machine (`~/.claude/maungs-toolbelt/usage.jsonl`, override with `MAUNGS_TOOLBELT_LOG`) — never inside a project repo.

**How to produce the summary:** run the bundled read-only summarizer and print its output verbatim. It is the source of truth — do NOT hand-parse the JSONL yourself.

1. Locate it (in order): `"${CLAUDE_PLUGIN_ROOT}"/bin/toolbelt-metrics.sh`, else the `bin/toolbelt-metrics.sh` next to the detected install root.
2. Run it read-only: `bash "<path>/bin/toolbelt-metrics.sh"`. It needs `jq`. It only READS the log — it never writes, edits, or deletes (consistent with CARDINAL RULE 1).
3. Print its output. If telemetry is OFF or the log is empty, the script already prints the enable instructions — relay them. Add one line that the live state is also visible on the optional cockpit statusline as `debug ●` (yellow = recording) with a per-session `offered▸used` tally.

If you cannot run the script (no `bash`/`jq`, or the file isn't found), say so plainly and show the manual fallback — the log path above and `export MAUNGS_TOOLBELT_DEBUG=on` to start recording — rather than inventing numbers. Never fabricate metrics.

## OUTWARD-ACTION GATES (human-in-the-loop)

There are **no outward actions** in this skill — by design it is the read-only front door. It writes nothing, commits nothing, pushes nothing, opens no PR, and adds no MCP server. The only "actions" it produces are printed suggestions and printed remediation commands for the USER to run. If you ever feel pulled toward running a suggested component or a remediation command "to be helpful," STOP — that crosses CARDINAL RULES 1-2. Hand the user the exact string and let them decide.

## CIRCUIT-BREAKER table (failure modes)

| Failure mode | Action |
|---|---|
| **Cannot reach the install dir** (can't enumerate `skills/`/`agents/`) | Fall back to the documented component set, and SAY SO explicitly ("listing from the documented set — could not read the install dir, so this may be stale"). Never present a fallback list as if freshly verified. |
| **A component file has malformed/missing frontmatter** | Skip it for the per-line description but still LIST it by filename under its best-guess stage, flagged "frontmatter unreadable — review". Never silently drop it. |
| **`claude mcp list` errors or is unavailable** (status mode) | Report MCP checks as `UNKNOWN — could not query`, not `NOT CONNECTED`. Distinguish "couldn't check" from "checked and absent". |
| **Goal matches no component** (Mode B) | Say so plainly; point at `/toolbelt` for the full inventory. Do NOT force a bad-fit recommendation. |
| **Goal matches many components** (Mode B) | Present the top 2-3 with the deciding question, not a single forced pick. |
| **Tempted to run the recommended component or a remediation** | Refuse (CARDINAL RULES 1-2). Print the invocation/command; the user runs it. |
| **An unclassified new component appears** | Place under Utility, flag "unclassified — review stage"; never hide it. |
| **Token budget exceeded** (see below) | Checkpoint at 60%, escalate at 80%: stop reading more component bodies, finish the inventory from frontmatter already read, mark any unread component "listed by name only", and return. |

## TOKEN BUDGET (self-imposed)

Soft budget: **15k tokens** per `/toolbelt` invocation. This is a lightweight discovery surface, not a worker — it reads frontmatter + runs a few read-only probes and prints a menu. It must be cheap enough to run reflexively. NOT a harness-enforced hard limit.

- **60% checkpoint (~9k)**: stop opening any new files beyond frontmatter; finalize grouping with what you have; prefer the cached/known mapping over re-deriving.
- **80% escalation (~12k)**: stop all probing; emit the inventory/recommendation/status from what you already read; mark anything unread "listed by name only" so the gap is visible, and return.

If a single invocation is approaching this budget, you are over-reading — the inventory should come from frontmatter and a couple of probes, nothing more.

## Example invocations

> `/toolbelt`
Detect the installed set → group by stage → print the inventory (one line per component with purpose + how to invoke) → footer pointing at `/toolbelt <goal>` and `/toolbelt status`. Flag a missing `CLAUDE.md`. Nothing is executed.

> `/toolbelt I need to find why a test keeps failing`
Echo the goal → recommend `/bug-catcher <symptom>` (root-cause diagnosis + adversarial verification, never edits code) with `/chore` or `/orchestrator` noted as the fix path once the cause is known → invite the user to run it.

> `/toolbelt status`
Read-only check: router `ACTIVE`/`DISABLED`/`NOT INSTALLED`, GitHub + Playwright MCP `CONNECTED`/`NOT CONNECTED`, `CLAUDE.md` present?, git identity set?, telemetry `RECORDING`/`OFF`, and the installed component counts — each with the user-owned remediation for any gap. Changes nothing.

> `/toolbelt metrics`
Run the bundled `bin/toolbelt-metrics.sh` and print its summary — suggestions offered (by intent), agents/skills invoked (by component), and the same-session suggestion→use conversion. If telemetry is off, relay the one-line enable instructions (`export MAUNGS_TOOLBELT_DEBUG=on`). Reads the usage log; writes nothing.
