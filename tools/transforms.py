"""Table-driven body-adaptation rules for the Codex target.

Two layers (see the plan's "Body adaptation" section):

  Layer 1 — canonical-safe NEUTRALIZATION, scoped to agent/skill BODIES (NOT
  hook scripts). Safe on Claude too:
      * ``CLAUDE.md`` -> ``AGENTS.md / CLAUDE.md``
      * ``restart Claude Code`` -> ``restart your agent``

  Layer 2 — CODEX-ONLY transforms, applied only on the Codex path:
      * ``claude mcp add``/``claude mcp list`` -> ``codex mcp ...``
      * EVERY ``mcp__<server>__*`` PROSE reference -> "the ``<server>`` MCP
        server" (server-name AGNOSTIC — github / playwright / context7 / any
        future server, via one rule)
      * the Claude-only ``ToolSearch`` mechanic token -> generic phrasing
      * ``AskUserQuestion`` -> "ask the user in chat and wait" — PRESERVING the
        verbatim wait-for-explicit-confirmation wording on every gate
      * ``/skill`` -> ``$skill`` via a LEFT-BOUNDARY rule (whitespace/line-start
        only; never a path component, never the right-hand args)
      * strip ``disable-model-invocation`` (handled at frontmatter level)

Hook BODIES are adapted by the layer-2 ``transform_hook_body`` set (env-var +
output-schema + log-path rules), kept here so agent bodies, skill bodies, and
hook bodies all adapt through one module.

Pure Python 3 stdlib.
"""

from __future__ import annotations

import re
from typing import List

from .emit import common

# The canonical skill names — the only ``/name`` tokens the left-boundary rule
# rewrites to ``$name``. Derived DYNAMICALLY from the canonical ``skills/``
# directory (the same single source ``common.load_skills`` enumerates), so a NEW
# skill — ``dossier-jobs``, ``todo``, or any future one — is picked up automatically
# with no hand-maintained list to drift out of sync with the emitter. Sorted;
# longest-first matching is enforced in the regex build so e.g.
# ``/migration-planner`` is not partially matched by a shorter name.
#
# Enumeration is rooted at ``common.REPO_ROOT`` (the build always runs from the
# repo root). The generator's temp-root tests copy the IDENTICAL skill set into
# their fixture, so this REPO_ROOT-derived list matches whatever root the emitter
# renders — there is no real code path where the two diverge.
SKILL_NAMES = sorted(comp.name for comp in common.load_skills())
AGENT_NAMES = sorted(comp.name for comp in common.load_agents())


# ---------------------------------------------------------------------------
# Layer 1 — canonical-safe neutralization (agent/skill BODIES only)
# ---------------------------------------------------------------------------

def neutralize_body(text: str) -> str:
    """Apply the canonical-safe neutralization (safe on Claude too).

    Scoped to agent/skill bodies — NOT hook scripts (decision 16). Idempotent:
    re-running does not double-rewrite, because the replacement target already
    contains the source token.
    """
    # "restart Claude Code" -> "restart Codex" (do this BEFORE the
    # CLAUDE.md rule so "Claude Code" is consumed first; case-insensitive on the
    # verb phrase but we only target the exact prose form used in the repo).
    text = text.replace("restart Claude Code", "restart Codex")
    text = text.replace("Write a Claude Code handoff", "Write a coding-agent handoff")
    text = text.replace("Claude Code handoff", "coding-agent handoff")
    # CLAUDE.md -> AGENTS.md (with CLAUDE.md as an optional compatibility source),
    # but only when not already part of the
    # combined token (idempotency) and not CLAUDE.local.md (leave that as-is so
    # the combined phrasing reads cleanly). We rewrite the bare "CLAUDE.md"
    # filename token; "CLAUDE.local.md" is left untouched.
    # Use a regex with a negative lookahead so "CLAUDE.md" inside the already
    # combined "AGENTS.md / CLAUDE.md" is not re-expanded, and "CLAUDE.local.md"
    # is excluded. The SECOND lookbehind ``(?<![\w/.~-])`` rejects a path-prefixed
    # form (``docs/CLAUDE.md``, ``~/.claude/CLAUDE.md``, ``a/b/CLAUDE.md``) so a
    # path token is NOT corrupted into ``docs/AGENTS.md / CLAUDE.md`` (BUG-8); a
    # standalone `` CLAUDE.md`` / `` `CLAUDE.md` `` / ``(CLAUDE.md`` still rewrites.
    text = re.sub(
        r"(?<!AGENTS\.md \(and )(?<![\w/.~-])CLAUDE\.md\b",
        "AGENTS.md (and CLAUDE.md when present)",
        text,
    )
    return text


# ---------------------------------------------------------------------------
# Layer 2 — MCP prose + ToolSearch + claude-mcp CLI
# ---------------------------------------------------------------------------

def rewrite_mcp_prose(text: str) -> str:
    """Rewrite every ``mcp__<server>__*`` PROSE reference -> "the <server> MCP server".

    Server-name agnostic (one rule, not an enumerated github/playwright pair).
    Matches the wildcard form (``mcp__context7__*``), a backtick-wrapped specific
    tool (`` `mcp__github__issue_read` ``), and a bare specific tool. The trailing
    tool segment (``__resolve-library-id``, ``__*``, ``__issue_read``) is consumed
    so no stale tool name survives.
    """
    # Backtick-wrapped form: `mcp__server__anything` -> the `server` MCP server
    text = re.sub(
        r"`mcp__([a-z0-9]+)__[A-Za-z0-9_*-]+`",
        r"the `\1` MCP server",
        text,
    )
    # Bare form (including the wildcard `mcp__server__*` without backticks).
    text = re.sub(
        r"\bmcp__([a-z0-9]+)__[A-Za-z0-9_*-]+",
        r"the \1 MCP server",
        text,
    )
    return text


def neutralize_toolsearch(text: str) -> str:
    """Neutralize the Claude-only ``ToolSearch`` mechanic to generic phrasing.

    Specifically rewrites the ``code-translator`` parenthetical
    "(via ToolSearch for the `context7` MCP server if not already loaded)" — the
    MCP token having already been rewritten by ``rewrite_mcp_prose`` — into a
    plain "discover the MCP tools" instruction, dropping the ``ToolSearch`` token.
    """
    # Collapse a "(via ToolSearch for ... if not already loaded)" parenthetical
    # to a generic phrasing.
    text = re.sub(
        r"\(via ToolSearch[^)]*\)",
        "(discover the MCP tools if not already loaded)",
        text,
    )
    # Any remaining bare ToolSearch mentions -> generic "tool discovery".
    text = text.replace("ToolSearch", "tool discovery")
    return text


def rewrite_claude_mcp_cli(text: str) -> str:
    """``claude mcp add``/``claude mcp list`` -> ``codex mcp add``/``codex mcp list``."""
    text = text.replace("claude mcp add", "codex mcp add")
    text = text.replace("claude mcp list", "codex mcp list")
    return text


# ---------------------------------------------------------------------------
# Layer 2 — /skill -> $skill (LEFT-BOUNDARY rule)
# ---------------------------------------------------------------------------

def _skill_alternation() -> str:
    # Longest names first so the alternation never partially matches.
    names = sorted(SKILL_NAMES, key=len, reverse=True)
    return "|".join(re.escape(n) for n in names)


# Left boundary = start-of-string OR a whitespace char OR an OPENING delimiter
# (backtick / open-paren / double-quote). Broadening past bare-whitespace is what
# lets the rule reach backtick-wrapped (`` `/orchestrator` ``), parenthesized
# (``(/wiki-generator …)``) AND double-quoted invocations — the latter is the
# mermaid node-label form ``A["/dossier-jobs [repo]"]`` (a quoted invocation depicted
# in a flow diagram), so the diagram label is rewritten to ``$dossier-jobs`` too. We
# rewrite the leading skill TOKEN only (``/orchestrator`` -> ``$orchestrator``) and
# leave everything to its right (args, sub-commands, flags, the closing delimiter)
# intact. The STRICT right boundary — whitespace | end | one of .,;:!? | a closing
# delimiter `` ` `` / `)` / `]` / `"` — prevents matching a longer slug:
# ``/handoffs`` (trailing ``s``), ``/chores`` (trailing ``s``), ``/toolbelt-metrics``
# (trailing ``-``), ``/orchestrator/SKILL.md`` (trailing ``/``) all FAIL the right
# boundary and are left intact. Crucially the rule still does NOT fire on a PATH
# component: ``skills/orchestrator`` and `` `skills/orchestrator/SKILL.md` `` (and
# ``"/some/path"``) have a non-delimiter char (a letter / a path slug) to the left
# of the matched ``/skill`` slug, so the path token stays byte-for-byte — a quoted
# PATH like ``"/orchestrator/SKILL.md"`` still fails the right boundary on the
# trailing ``/``.
_SKILL_LEFT_BOUNDARY = re.compile(
    r'(^|[\s`("])/(' + _skill_alternation() + r')(?=[\s`.,;:!?)\]"]|$)',
    re.MULTILINE,
)


def rewrite_skill_invocations(text: str) -> str:
    """Rewrite a bare/wrapped ``/skill`` invocation -> ``$skill`` (left-boundary only).

    Codex CLI and IDE use ``$skill`` for explicit skill invocation. Rewrites
    ``/orchestrator`` when preceded by whitespace/line-start OR an opening
    delimiter to ``$orchestrator`` while leaving path components untouched.
    while leaving ``skills/orchestrator/SKILL.md``,
    `` `skills/orchestrator/SKILL.md` ``, ``developer/orchestrator``, and
    ``@playwright/mcp@latest`` untouched (each has a path component, not an opening
    boundary, immediately left of the slash). The trailing args / sub-commands /
    flags / closing backtick to the right are left exactly as-is —
    ``/orchestrator <topic>`` -> ``$orchestrator <topic>``.
    """
    return _SKILL_LEFT_BOUNDARY.sub(lambda m: m.group(1) + "$" + m.group(2), text)


def _agent_alternation() -> str:
    names = sorted(AGENT_NAMES, key=len, reverse=True)
    return "|".join(re.escape(n) for n in names)


_AGENT_CODE_SPAN = re.compile(
    r"`@(" + _agent_alternation() + r")([^`]*)`"
)
_AGENT_LINE = re.compile(
    r"^@(" + _agent_alternation() + r")([^\n]*)$",
    re.MULTILINE,
)
_AGENT_WITH_THE = re.compile(
    r"\bthe\s+@(" + _agent_alternation() + r")(?:\s+agent)?\b",
)
_AGENT_WITH_AGENT = re.compile(
    r"@(" + _agent_alternation() + r")\s+agent\b",
)
_AGENT_BARE = re.compile(
    r"@(" + _agent_alternation() + r")\b"
)


def rewrite_agent_invocations(text: str) -> str:
    """Rewrite Claude ``@agent`` shorthand into explicit Codex spawn wording.

    Codex custom agents are selected by agent type when a user or conductor asks
    Codex to spawn them; ``@agent`` is not the custom-agent invocation surface.
    """
    text = _AGENT_CODE_SPAN.sub(
        lambda m: "`spawn %s subagent%s`" % (m.group(1), m.group(2)),
        text,
    )
    text = _AGENT_LINE.sub(
        lambda m: "spawn %s subagent%s" % (m.group(1), m.group(2)),
        text,
    )
    text = _AGENT_WITH_THE.sub(
        lambda m: "the %s subagent" % m.group(1),
        text,
    )
    text = _AGENT_WITH_AGENT.sub(
        lambda m: "%s subagent" % m.group(1),
        text,
    )
    text = _AGENT_BARE.sub(lambda m: "%s subagent" % m.group(1), text)
    # Canonical prose often wraps ``@agent`` in a code span and then appends the
    # noun "agent"; after conversion the role is already explicit.
    text = re.sub(
        r"(`spawn (?:%s) subagent[^`]*`)\s+agent\b" % _agent_alternation(),
        r"\1",
        text,
    )
    text = re.sub(
        r"(# or )((?:%s) subagent)\b" % _agent_alternation(),
        r"\1spawn \2",
        text,
    )
    return text


def rewrite_skill_arguments(text: str) -> str:
    """Replace Claude command-placeholder syntax unsupported by Codex skills."""
    return text.replace(
        "$ARGUMENTS",
        "the invocation arguments from the user's request",
    )


def rewrite_codex_memories(text: str) -> str:
    """Replace Claude's project-memory filesystem contract with Codex memories.

    Codex injects enabled memories into the thread and stores generated state
    under ``~/.codex/memories/``. Generated agents should use the injected
    context, not assume Claude's project-slug/MEMORY.md layout exists.
    """
    text = re.sub(
        r"\(`~/.claude/projects/<project-slug>/memory/MEMORY\.md`"
        r"(?: \+ cited entries)?\)",
        "(Codex-injected memories, when enabled)",
        text,
    )
    text = text.replace(
        "(`~/.claude/projects/<project-slug>/memory/`)",
        "(Codex-injected memories, when enabled)",
    )
    text = text.replace(
        "(`~/.claude/projects/<slug>/memory/`)",
        "(`~/.codex/memories/`)",
    )
    text = text.replace(
        "`~/.claude/memory/MEMORY.md`",
        "Codex-injected memories",
    )
    text = text.replace(
        "the project's auto-memory `MEMORY.md` "
        "(Codex-injected memories, when enabled) + cited entries",
        "Codex-injected memories when enabled",
    )
    text = text.replace(
        "the project's auto-memory index "
        "(Codex-injected memories, when enabled) + all cited entries",
        "Codex-injected memories when enabled",
    )
    text = text.replace(
        "load the project's auto-memory index if present "
        "(Codex-injected memories, when enabled), falling back to "
        "Codex-injected memories",
        "use Codex-injected memories when enabled",
    )
    text = text.replace(
        "auto-memory directory exists (Codex-injected memories, when enabled), "
        "load it + cited entries",
        "Codex memories are injected, use the relevant entries",
    )
    text = text.replace(
        "Load the project's auto-memory "
        "(Codex-injected memories, when enabled) at the start if present",
        "Use Codex-injected memories when enabled",
    )
    text = text.replace(
        "Load the project's auto-memory "
        "(Codex-injected memories, when enabled) at the start of every review "
        "if present",
        "Use Codex-injected memories when enabled at the start of every review",
    )
    text = text.replace(
        "Load the project's auto-memory "
        "(Codex-injected memories, when enabled) at the start of every invocation",
        "Use Codex-injected memories when enabled at the start of every invocation",
    )
    text = text.replace(
        "The project's auto-memory directory "
        "(Codex-injected memories, when enabled)",
        "Codex-injected memories, when enabled",
    )
    text = text.replace(
        "The project's **auto-memory** "
        "(Codex-injected memories, when enabled)",
        "**Codex-injected memories**, when enabled",
    )
    text = text.replace(
        "`MEMORY.md` + cited entries",
        "relevant durable entries",
    )
    text = text.replace(
        "auto-memory",
        "memory context",
    )
    text = text.replace("Claude maintains", "Codex maintains")
    return text


def rewrite_codex_local_paths(text: str) -> str:
    """Move toolbelt-owned local state and diagnostics to Codex conventions."""
    text = text.replace(
        "~/.claude/maungs-toolbelt/",
        "~/.codex/maungs-toolbelt/",
    )
    text = text.replace(
        "${HOME}/.claude/maungs-toolbelt/",
        "${HOME}/.codex/maungs-toolbelt/",
    )
    text = text.replace(
        "$HOME/.claude/maungs-toolbelt/",
        "$HOME/.codex/maungs-toolbelt/",
    )
    text = text.replace(
        '"${CLAUDE_PLUGIN_ROOT}"/bin/toolbelt-metrics.sh',
        "the bundled scripts/toolbelt-metrics.sh next to this skill",
    )
    text = text.replace(
        "Newly-added MCP servers do not load until Claude Code restarts",
        "Newly-added MCP servers may require a new Codex thread",
    )
    text = text.replace("restart Codex", "start a new Codex thread")
    text = text.replace("restarting Claude Code", "starting a new Codex thread")
    text = text.replace("restart Claude Code", "start a new Codex thread")
    text = text.replace(
        "~/.claude/toolbelt-status.json",
        "~/.codex/toolbelt-status.json",
    )
    text = text.replace(
        "No Claude / Claude Code attribution",
        "No AI-assistant attribution",
    )
    text = text.replace(
        "Claude / Claude Code attribution",
        "AI-assistant attribution",
    )
    text = text.replace(
        "the in-session todo list Claude Code shows",
        "Codex's in-session task tracking",
    )
    text = text.replace(
        "the same scheme Claude Code uses for `~/.claude/projects/<slug>/`",
        "a stable path-derived scheme shared with the session loader",
    )
    text = text.replace(
        'No `Co-Authored-By: Claude`, no `🤖 Generated with Claude Code`.',
        "No AI co-author trailers or AI-generated footers.",
    )
    text = text.replace(
        "If a project has its own `$orchestrator` skill "
        "(e.g., `<project>/.claude/skills/orchestrator/SKILL.md`)",
        "If a project has its own `$orchestrator` skill "
        "(e.g., `<project>/.agents/skills/orchestrator/SKILL.md`)",
    )
    text = text.replace(".claude/skills/", ".agents/skills/")
    text = text.replace(
        "Skills are invoked as `/<name>`; agents as `@<name> <args>`.",
        "Skills are invoked as `$<name>`; custom agents by asking Codex to "
        "spawn the named subagent.",
    )
    text = text.replace(
        "enumerate `skills/*/SKILL.md` and `agents/*.md` frontmatter",
        "enumerate plugin `skills/*/SKILL.md` frontmatter and "
        "`~/.codex/agents/*.toml` metadata",
    )
    text = text.replace(
        "enumerate `agents/*.md`; read each one's frontmatter `name` + `description` "
        "(and `tools` list for least-privilege context).",
        "enumerate `~/.codex/agents/*.toml`; read each file's `name` + "
        "`description` and sandbox/MCP settings.",
    )
    text = text.replace(
        '`bash "<path>/bin/toolbelt-metrics.sh"`',
        '`bash "<skill-dir>/scripts/toolbelt-metrics.sh"`',
    )
    return text


def rewrite_orchestrator_codex(text: str, component_name: str) -> str:
    """Remove Claude's custom status-file contract and fix Codex reload guidance."""
    if component_name != "orchestrator":
        return text
    text = re.sub(
        r"## Local statusline status file \(write on every phase — LOCAL only\)\n"
        r".*?(?=\n## Auto-detection on every invocation)",
        "## Codex status line\n\n"
        "Codex provides a built-in `/statusline` command for standard footer "
        "fields such as model, context, limits, git state, tokens, and session. "
        "It does not consume the Claude toolbelt's custom pipeline-status file, "
        "so do not write `~/.codex/toolbelt-status.json`.\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\*\*Critical — newly added MCP servers.*?Do NOT pretend a just-added "
        r"server is usable in the current (?:session|thread)\.",
        "**Critical — newly added MCP servers may require a new Codex thread.** "
        "After adding any server, STOP and tell the user to start a new thread "
        "and re-run `$orchestrator <arg>`; Step 0 will re-check and pass. Do NOT "
        "pretend a just-added server is usable in the current thread.",
        text,
        flags=re.DOTALL,
    )
    return text


def rewrite_component_specific_codex(text: str, component_name: str) -> str:
    """Clean up target-specific semantics that cannot be expressed generically."""
    if component_name == "agentic-onboard":
        text = text.replace(
            "AGENTS.md (and CLAUDE.md when present)",
            "CLAUDE.md",
        )
        text = text.replace(
            "Every other component — `$orchestrator`, `$wiki-generator`, "
            "`$bug-catcher` — auto-detects `CLAUDE.md` plus a plan-file "
            "convention",
            "Every other component — `$orchestrator`, `$wiki-generator`, "
            "`$bug-catcher` — auto-detects `AGENTS.md`, reads `CLAUDE.md` when "
            "present, and uses a plan-file convention",
        )
        text = text.replace(
            "The target project's `CLAUDE.md` may add conventions",
            "The target project's `AGENTS.md` (and `CLAUDE.md` when present) "
            "may add conventions",
        )
        text = text.replace(
            "Honor target-project conventions already present in `CLAUDE.md` / "
            "`CLAUDE.local.md` / equivalent",
            "Honor target-project conventions already present in `AGENTS.md` / "
            "`CLAUDE.md` / `CLAUDE.local.md` / equivalent",
        )
    elif component_name in {"context-writer", "context-auditor"}:
        text = text.replace(
            "AGENTS.md (and CLAUDE.md when present)",
            "CLAUDE.md",
        )
    elif component_name == "handoff":
        text = text.replace(
            "write a Claude-Code-handoff and a separate engineer-readable doc",
            "write a second agent-specific handoff and a separate "
            "engineer-readable doc",
        )
    elif component_name == "toolbelt":
        text = text.replace(
            "reading the installed `skills/*/SKILL.md` and `agents/*.md` "
            "frontmatter",
            "reading plugin `skills/*/SKILL.md` frontmatter and installed "
            "`~/.codex/agents/*.toml` metadata",
        )
        text = text.replace(
            "enumerate `skills/*` + `agents/*`",
            "enumerate plugin `skills/*` + `~/.codex/agents/*.toml`",
        )
        text = re.sub(
            r" Add one line that the live state is also visible on the optional "
            r"cockpit statusline as `debug ●` \(yellow = recording\) with a "
            r"per-session `offered▸used` tally\.",
            "",
            text,
        )
        text = text.replace(
            "`CONFIGURED — restart required`",
            "`CONFIGURED — new thread required`",
        )
    return text


_CODEX_DOSSIER_BODY = """\
# Codex adapter

This is the Codex version of the scheduled dossier workflow. Codex CLI does not
expose Claude's `RemoteTrigger` API. Never call or simulate `RemoteTrigger`.

## Inputs

Read the repository, selected jobs (`--bug`, `--security`, `--wiki`), schedule,
timezone, model, `--max-fixes`, and action flags from the user's request text
after the skill name. Resolve the repository from the positional argument or the
current checkout's `origin` remote.

## Supported behavior

1. Build the same three job prompts as the Claude workflow:
   - **bug**: run `$bug-catcher --global`; keep SEV1 issue-only; draft, never
     merge, at most `--max-fixes` non-SEV1 fix PRs.
   - **security**: run the `security-reviewer` subagent for a repository-wide
     compliance sweep; issue/comment output only.
   - **wiki**: run `$wiki-generator --update`; produce one rolling proposal PR.
2. Keep one rolling `[dossier-jobs] Dossier` issue and one marker-delimited
   comment per job so reruns update rather than duplicate.
3. Show the exact repository, local and UTC schedule, model, prompts, and outward
   actions before any creation/update/run action. Wait for explicit confirmation.
4. If the current Codex surface exposes automation-management tools, use them
   after confirmation and report the created automation identifiers.
5. In Codex CLI, where automation creation is unavailable, output a complete
   copy/paste configuration for three Codex app automations and the exact steps:
   open Codex app → Automations → New automation → select the repository and
   local environment → paste the prompt and schedule. Do not claim the
   automations were created.
6. `--status`, `--disable`, and `--run-now` operate only when automation tools are
   available. In CLI-only mode, print the exact Codex app action required.

## Safety

- Reads and preflight are free. Creation, update, disable, run-now, issue writes,
  and PR creation remain human-gated.
- Never auto-merge generated PRs.
- Never use `--dangerously-bypass-approvals-and-sandbox` to make a scheduled CLI
  job work.
- If unattended CLI execution would require bypassing approvals, stop and route
  the user to Codex app Automations instead.

## Output

Return a table for each selected job: action, repository, schedule, model,
prompt summary, automation id or `MANUAL APP SETUP REQUIRED`, and rollback
instructions. Clearly distinguish completed actions from generated setup.
"""


def rewrite_dossier_jobs(text: str, component_name: str) -> str:
    if component_name != "dossier-jobs":
        return text
    return _CODEX_DOSSIER_BODY


# ---------------------------------------------------------------------------
# Layer 2 — AskUserQuestion (gate-preserving)
# ---------------------------------------------------------------------------

# The verbatim blocking imperative carried onto every outward-action GATE. The
# gate-semantics test asserts a wait-for-confirmation instruction survives at
# each gate point, so this phrasing is load-bearing. Phrased as a VERB clause so
# it reads grammatically wherever the canonical used the tool name imperatively
# (sentence-initial "Call `AskUserQuestion`", "then `AskUserQuestion`", a bare
# "`AskUserQuestion`:" prompt).
_GATE_PHRASE = (
    "ask the user in chat and wait for an explicit “yes” / confirmation "
    "before proceeding (never interpret silence as approval)"
)
_DESIGN_PHRASE = "ask the user in chat"

# A concise NOUN phrase for the mechanic-name-as-noun sites ("an `AskUserQuestion`
# with concrete options", "per `AskUserQuestion` call", "verbatim `AskUserQuestion`
# shape", "iterative `AskUserQuestion` turns"). These are META references to the
# question mechanic, NOT gate imperatives — fabricating the long wait clause here
# would read as broken grammar ("Frame as an ask the user in chat … with"), so
# they collapse to a plain noun. The real gate's wait wording lives in the
# adjacent imperative sentence and is untouched.
_GATE_NOUN = "in-chat question"


def rewrite_askuserquestion(text: str, is_gate_body: bool) -> str:
    """Rewrite ``AskUserQuestion`` -> gate-preserving, GRAMMATICAL prose.

    The token appears in two grammatical roles in the canonical bodies, and a
    blanket token swap mangles one of them:

      * IMPERATIVE / gate role — "Call `AskUserQuestion`:", "then `AskUserQuestion`
        for approval", "via `AskUserQuestion`", a bare "`AskUserQuestion`:" prompt.
        On a GATE body these MUST keep the blocking ``_GATE_PHRASE`` (its
        wait-for-explicit-yes wording is load-bearing and reinforced, never
        softened). The verb/preposition that precedes the token is folded into the
        phrase so the result reads cleanly ("call ask the user…" -> "ask the
        user…"; "via ask the user…" -> "by asking the user…").
      * NOUN / mechanic-reference role — "an `AskUserQuestion` with options", "per
        `AskUserQuestion` call", "verbatim `AskUserQuestion` shape", "iterative
        `AskUserQuestion` turns". These collapse to the plain ``_GATE_NOUN`` noun;
        they describe the question mechanic, they do not gate an action, so no wait
        clause is fabricated (and the blanket phrase would be ungrammatical here).

    On a NON-gate body (product-owner's scope-clarification design question) the
    imperative role uses the ordinary ``_DESIGN_PHRASE`` — no blocking instruction
    is fabricated where none is warranted.

    Order matters: the multi-word NOUN + verb-prefixed forms are rewritten BEFORE
    the bare-token fallback so the longer, grammar-correct match wins.
    """
    phrase = _GATE_PHRASE if is_gate_body else _DESIGN_PHRASE

    # 1) NOUN / mechanic-reference forms -> plain noun (gate-neutral, grammatical).
    #    Capital + lowercase, backticked + bare, longest-first.
    for noun_form in (
        "an `AskUserQuestion`",          # "Frame as an `AskUserQuestion` with …"
        "an AskUserQuestion",
        "per `AskUserQuestion` call",    # "up to 4 questions per `AskUserQuestion` call"
        "per AskUserQuestion call",
        "verbatim `AskUserQuestion` shape",
        "verbatim AskUserQuestion shape",
        "iterative `AskUserQuestion` turns",
        "iterative AskUserQuestion turns",
        "separate `AskUserQuestion`",    # "push gate (separate `AskUserQuestion`)"
        "separate AskUserQuestion",
        "`AskUserQuestion` shape",
        "AskUserQuestion shape",
        "`AskUserQuestion` turns",
        "AskUserQuestion turns",
        "`AskUserQuestion` call",
        "AskUserQuestion call",
    ):
        if noun_form in text:
            if noun_form.startswith("an "):
                repl = "an " + _GATE_NOUN
            elif noun_form.startswith("per "):
                # "up to 4 questions per `AskUserQuestion` call" -> "… per round"
                # (a question batch); "per in-chat question" would read redundantly.
                repl = "per round"
            elif noun_form.startswith("verbatim "):
                repl = "verbatim " + _GATE_NOUN + " shape"
            elif noun_form.startswith("iterative "):
                repl = "iterative " + _GATE_NOUN + " turns"
            elif noun_form.startswith("separate "):
                repl = "separate " + _GATE_NOUN
            elif noun_form.endswith(" shape"):
                repl = _GATE_NOUN + " shape"
            elif noun_form.endswith(" turns"):
                repl = _GATE_NOUN + " turns"
            else:  # "… call"
                repl = _GATE_NOUN
            text = text.replace(noun_form, repl)

    # 2) VERB / preposition-prefixed IMPERATIVE forms -> fold the verb in so the
    #    gate phrase reads grammatically while keeping the wait wording.
    #    "via X"  -> "by asking the user in chat …"  (preposition + gerund). The
    #    blocking wait wording is kept verbatim in a trailing parenthetical so the
    #    exact "wait for an explicit …" string survives (gate-semantics test +
    #    real blocking behavior both depend on that literal substring).
    via_phrase = (
        "by asking the user in chat (wait for an explicit “yes” / confirmation "
        "before proceeding; never interpret silence as approval)"
        if is_gate_body
        # Non-gate (design question): embed the plain `_DESIGN_PHRASE` literally so
        # it reads "Surface scope questions — ask the user in chat — if vague" with
        # NO fabricated wait clause.
        else "— " + _DESIGN_PHRASE + " —"
    )
    text = text.replace("via `AskUserQuestion`", via_phrase)
    text = text.replace("via AskUserQuestion", via_phrase)
    #    "Call X" / "call X" -> drop the redundant verb; the phrase already starts
    #    with the verb "ask". Capital form keeps the sentence-initial capital.
    text = text.replace("Call `AskUserQuestion`", phrase[0].upper() + phrase[1:])
    text = text.replace("Call AskUserQuestion", phrase[0].upper() + phrase[1:])
    text = text.replace("call `AskUserQuestion`", phrase)
    text = text.replace("call AskUserQuestion", phrase)

    # 3) Bare-token fallback (e.g. a leading "`AskUserQuestion`:" prompt line).
    #    A sentence-INITIAL bare token must keep a capital (BUG-7) — an
    #    unconditional lowercase replace would drop the capital at a sentence /
    #    list-item start ("3. `AskUserQuestion`:" -> "3. ask the user…"). Use a
    #    boundary-aware sub that capitalizes `phrase` when the token is
    #    sentence-initial (start-of-string, start-of-line, or after ". " / "? " /
    #    "! " or a list-number like "3. "), else emits `phrase` verbatim —
    #    mirroring the capital handling already done for the Call/call forms above.
    #    The backticked form is rewritten before the bare form so the longer match
    #    wins. The leading boundary is CONSUMED in group(1) and re-emitted so the
    #    "sentence-initial" decision works without a variable-width lookbehind.
    cap_phrase = phrase[0].upper() + phrase[1:]
    _initial_prefix = r"(^|\n|[.?!] |\d\. )"

    def _make_repl():
        def _repl(m):
            prefix = m.group(1)
            # group(1) is None when the optional prefix did not match (mid-sentence
            # token -> lowercase). It is a (possibly EMPTY, from the ``^`` anchor)
            # string when the token is sentence-initial -> capitalize. The empty
            # string is falsy, so test ``is not None`` explicitly.
            if prefix is None:
                return phrase
            return prefix + cap_phrase
        return _repl

    # Backticked form first, then the bare form. The prefix is captured only when
    # the token is sentence-initial; otherwise it is None and the lowercase
    # ``phrase`` is emitted.
    text = re.sub(
        r"(?:" + _initial_prefix + r")?`AskUserQuestion`",
        _make_repl(),
        text,
    )
    text = re.sub(
        r"(?:" + _initial_prefix + r")?AskUserQuestion",
        _make_repl(),
        text,
    )
    return text


# Bodies whose AskUserQuestion sites gate an outward action (must BLOCK).
GATE_BODIES = {
    "developer",
    "architect",
    "orchestrator",
    "handoff",
    "migration-planner",
}


# ---------------------------------------------------------------------------
# Public: full agent/skill body transform
# ---------------------------------------------------------------------------

def transform_body(text: str, component_name: str) -> str:
    """Apply layer-1 + layer-2 to an agent or skill body (Codex path)."""
    text = rewrite_dossier_jobs(text, component_name)
    text = neutralize_body(text)               # layer 1
    text = rewrite_mcp_prose(text)             # layer 2
    text = neutralize_toolsearch(text)         # layer 2
    text = rewrite_claude_mcp_cli(text)        # layer 2
    text = rewrite_skill_invocations(text)     # layer 2
    text = rewrite_agent_invocations(text)     # layer 2
    text = rewrite_skill_arguments(text)       # layer 2
    text = rewrite_codex_memories(text)         # layer 2
    text = rewrite_codex_local_paths(text)      # layer 2
    text = rewrite_orchestrator_codex(text, component_name)
    text = rewrite_component_specific_codex(text, component_name)
    text = rewrite_askuserquestion(text, component_name in GATE_BODIES)
    return text


def transform_description(text: str, component_name: str) -> str:
    """Run a frontmatter ``description`` through the body transforms.

    The description is carried into the TOML ``description`` field and the skill
    frontmatter, so it gets the same adaptation as the body.
    """
    if component_name == "dossier-jobs":
        text = (
            "Prepare the bug, security, and wiki scheduled-dossier workflows for "
            "Codex Automations. Uses automation-management tools when available; "
            "in Codex CLI it generates complete copy/paste Codex app automation "
            "configurations without claiming they were created. Invoke with "
            "`$dossier-jobs [repo] [flags]`."
        )
        text = neutralize_body(text)
        text = rewrite_skill_invocations(text)
        text = rewrite_agent_invocations(text)
        text = rewrite_skill_arguments(text)
        return rewrite_codex_local_paths(text)
    return transform_body(text, component_name)


# ---------------------------------------------------------------------------
# Hook-body transforms (env-var + output-schema + log-path rules)
# ---------------------------------------------------------------------------

def _replace_or_die(body: str, old: str, new: str) -> str:
    """Like ``str.replace`` but FAILS LOUDLY when ``old`` is not present.

    A hook-body ``.replace`` whose ``old`` token has drifted out of the canonical
    source is a silent no-op — the transform would quietly stop applying and the
    generated artifact would carry stale (un-adapted) text. This fire-check turns
    that into a build-time ``AssertionError`` so a canonical edit that moves a
    matched token can never slip through unnoticed. Every assert must PASS against
    today's canonical (the build loop runs them on every emit).
    """
    assert old in body, "transform expected token not found: %r…" % (old[:40],)
    return body.replace(old, new)


def transform_lib_telemetry(body: str) -> str:
    """Rewrite the WRITER's default usage-log root from ``~/.claude`` to ``~/.codex``.

    Only the default in ``tb_log_path`` is rewritten; the ``MAUNGS_TOOLBELT_LOG``
    override branch is preserved verbatim (it must keep winning, platform-
    independent). The readers (bin/, statusline/) are out of scope (decision 15).
    """
    body = _replace_or_die(
        body,
        "${MAUNGS_TOOLBELT_LOG:-${HOME}/.claude/maungs-toolbelt/usage.jsonl}",
        "${MAUNGS_TOOLBELT_LOG:-${HOME}/.codex/maungs-toolbelt/usage.jsonl}",
    )
    # Also adjust the comment block that documents the default path so docs match.
    body = _replace_or_die(
        body,
        "~/.claude/maungs-toolbelt/usage.jsonl   — always on your local machine,",
        "~/.codex/maungs-toolbelt/usage.jsonl    — always on your local machine,",
    )
    # Presence-only guard: the override comment line is intentionally unchanged
    # (override branch is preserved verbatim), but a fire-check still ensures the
    # canonical line we anchor docs against has not silently moved.
    assert (
        "# Log location (override with MAUNGS_TOOLBELT_LOG):" in body
    ), "transform expected the MAUNGS_TOOLBELT_LOG override comment line"
    body = _replace_or_die(
        body,
        "(env override → default under ~/.claude).",
        "(env override → default under ~/.codex).",
    )
    body = _replace_or_die(body, "`/toolbelt metrics`", "`$toolbelt metrics`")
    body = body.replace(
        "(visible under `claude --debug`)",
        "(visible in the hook diagnostics)",
    )
    body = body.replace(
        "PreToolUse on Task / Skill",
        "SubagentStart / explicit skill prompt",
    )
    return body


def transform_usage_tracker(body: str) -> str:
    """Render a Codex ``SubagentStart`` invocation tracker.

    Codex does not expose Claude's ``Task`` or ``Skill`` tools to PreToolUse.
    Custom-agent starts have a first-class hook event; explicit skill mentions
    are recorded by the UserPromptSubmit router.
    """
    names = "|".join(AGENT_NAMES)
    script = """#!/usr/bin/env bash
#
# usage-tracker.sh — SubagentStart telemetry for Maungs-agentic-toolbelt.
# Records invocations of this toolbelt's installed custom subagents.

TB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
. "${TB_DIR}/lib-telemetry.sh" 2>/dev/null || exit 0
tb_debug_on || exit 0
command -v jq >/dev/null 2>&1 || exit 0

input="$(cat 2>/dev/null)"; [ -n "$input" ] || exit 0
event="$(printf '%s' "$input" | jq -r '.hook_event_name // empty' 2>/dev/null)"
[ "$event" = "SubagentStart" ] || exit 0
raw="$(printf '%s' "$input" | jq -r '.agent_type // empty' 2>/dev/null)"
case "$raw" in
  __AGENT_CASES__) ;;
  *) exit 0 ;;
esac

session="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
rec="$(jq -nc --arg ts "$(tb_now)" --arg component "$raw" \
  --arg session "$session" --arg cwd "$cwd" \
  '{ts:$ts,event:"invoked",kind:"agent",component:$component,raw:$component,session:$session,cwd:$cwd}' 2>/dev/null)"
tb_append "$rec"
exit 0
"""
    return script.replace("__AGENT_CASES__", names)


def transform_pretooluse_guard(body: str) -> str:
    """Adapt ``pretooluse-guard.sh`` for Codex.

    * Emit only Codex's supported ``hookSpecificOutput.permissionDecision`` form.
    * Codex PreToolUse cannot return ``ask``. Emulate the Claude ask tier by
      denying the first attempt with an instruction to ask the user, then allowing
      a confirmed retry prefixed with ``MAUNGS_TOOLBELT_CONFIRMED=1``. Hard-deny
      rules still run on confirmed retries.
    * Broaden the attribution denylist (rule 5) to be MODEL-AGNOSTIC — deny any
      AI/assistant co-author trailer or "Generated with <any AI tool>" line, not
      just the literal "Claude" string.
    """
    # Broaden rule 5's attribution pattern to be MODEL-AGNOSTIC while avoiding the
    # two failure modes of a naive widening:
    #   (a) SUBSTRING false-DENY — a human whose name merely CONTAINS an AI token
    #       as a substring (``Co-Authored-By: Aishwarya Patel`` — ``ai`` inside
    #       ``Aishwarya``). Fixed by anchoring every AI-tool token with a word
    #       boundary ``\b…\b`` and dropping the over-broad bare tokens
    #       (``ai``/``llm``/``assistant``/``model``/``bot``) — ``ai`` survives ONLY
    #       inside the multiword phrases ``ai assistant`` / ``ai tool`` / ``ai agent``.
    #       A residual WHOLE-WORD false-DENY remains for a human whose NAME equals
    #       an AI token (``Co-Authored-By: Devin Wong``; or ``Claude``, which the
    #       canonical guard already denies in first position) — those product names
    #       ARE also AI coding tools, so this is an ACCEPTED fail-closed trade-off
    #       (escape hatch ``MAUNGS_TOOLBELT_GUARD=off``). The match is SCOPED to the
    #       name part via ``[^<]*`` (everything up to the ``<email>``), so an AI
    #       token appearing ONLY in the email DOMAIN — ``Jane Smith
    #       <jane@openai.com>`` — does NOT false-DENY: a real attribution trailer
    #       carries the tool in the name, not merely the address.
    #   (b) false-ALLOW — an AI tool NOT in first position after the colon
    #       (``Co-Authored-By: GitHub Copilot`` — the old ``[[:space:]]*`` tied the
    #       token to the head of the trailer). Fixed by matching the AI token
    #       anywhere in the NAME part via ``Co-Authored-By:[^<]*\bTOKEN\b``.
    # The curated AI-tool set is matched as WHOLE WORDS; the 🤖 marker and the
    # "Generated with/by <AI tool>" footer are kept. ``\b`` is the same portability
    # bar the canonical guard already relies on (see its add/-A and --no-verify
    # rules). Uses ``hasrawi`` — raw (scans ``$cmd``, NOT the quote-neutralized
    # ``scan``, because the trailer is inside the quoted commit message) AND
    # case-insensitive — so the lowercase literals match any-case attribution.
    _ai_words = (
        "claude|gpt|chatgpt|copilot|codex|cursor|gemini|llama|aider|"
        "anthropic|openai|devin|tabnine"
    )
    _ai_phrases = (
        "ai[[:space:]]+assistant|ai[[:space:]]+tool|ai[[:space:]]+agent|"
        "coding[[:space:]]+agent|language[[:space:]]+model"
    )
    _attr_pattern = (
        "Co-Authored-By:[^<]*\\b(" + _ai_words + ")\\b"
        "|Co-Authored-By:[^<]*(" + _ai_phrases + ")"
        "|Generated (with|by)[[:space:]].*(\\b(" + _ai_words + ")\\b|"
        + _ai_phrases + ")"
        "|🤖"
    )
    # The broadened attribution rule must scan the RAW $cmd — the trailer lives
    # inside the quoted -m commit message, which the guard's quote-neutralization
    # (added to the canonical guard for invocation-precision) turns into a
    # placeholder in `scan`, so a `scan`-based match would MISS it — AND
    # case-insensitively (the AI-tool token set is lowercase). The canonical
    # `hasraw` is raw but case-SENSITIVE, so inject a raw + case-insensitive
    # sibling `hasrawi` right next to it and anchor the broadened rule on that.
    # The canonical attribution rule itself uses `hasraw` (not `has`) for the same
    # reason, so `old_attr` matches that.
    body = _replace_or_die(
        body,
        'hasraw() { printf \'%s\' "$cmd" | grep -qE -- "$1"; }',
        'hasraw() { printf \'%s\' "$cmd" | grep -qE -- "$1"; }\n'
        '# Codex: raw (un-neutralized) + case-INSENSITIVE attribution matcher —\n'
        '# the model-agnostic rule below needs both (see rule 5).\n'
        'hasrawi() { printf \'%s\' "$cmd" | grep -qiE -- "$1"; }',
    )
    # The canonical guard already names several AI assistants (a $AI_NAMES list)
    # and matches case-insensitively. The Codex rule broadens that further (more
    # tools + AI-assistant phrase forms) and routes through `hasrawi`; anchor on
    # the canonical two-line block (the $AI_NAMES assignment + the inline grep).
    old_attr = (
        "AI_NAMES='Claude|Codex|Copilot|GPT|Grok|Gemini|DeepSeek|Mistral|Llama|Anthropic|OpenAI'\n"
        "if hasraw 'git([[:space:]]|.)*commit' && printf '%s' \"$cmd\" | grep -qiE -- "
        "\"Co-Authored-By:[[:space:]]*($AI_NAMES)|Generated with[[:space:]].*($AI_NAMES)|🤖\"; then"
    )
    new_attr = (
        "if hasraw 'git([[:space:]]|.)*commit' && hasrawi '" + _attr_pattern + "'; then"
    )
    body = _replace_or_die(body, old_attr, new_attr)
    body = _replace_or_die(
        body,
        'deny "Toolbelt cardinal rule: no AI attribution in commits/PRs (no \'Co-Authored-By: <AI>\' / \'Generated with <AI>\'). Remove it from the commit message. (MAUNGS_TOOLBELT_GUARD=off to override.)"',
        'deny "Toolbelt cardinal rule: no AI/assistant attribution in commits/PRs (no \'Co-Authored-By:\' naming any AI/assistant/model, no \'Generated with/by <any AI tool>\', no robot marker). Remove it from the commit message. (MAUNGS_TOOLBELT_GUARD=off to override.)"',
    )
    body = _replace_or_die(
        body,
        '[ -z "$cmd" ] && exit 0',
        '[ -z "$cmd" ] && exit 0\n\n'
        '# Codex has no PreToolUse "ask" decision. After the hook blocks an\n'
        '# ask-tier command and the user explicitly confirms it, retry exactly\n'
        '# once with this environment prefix. The prefix is stripped only for\n'
        '# guard analysis; the shell still receives the original command.\n'
        'TB_CONFIRMED=0\n'
        'case "$cmd" in\n'
        '  MAUNGS_TOOLBELT_CONFIRMED=1[[:space:]]*)\n'
        '    TB_CONFIRMED=1\n'
        '    cmd="${cmd#MAUNGS_TOOLBELT_CONFIRMED=1}"\n'
        '    cmd="${cmd# }" ;;\n'
        'esac',
    )
    old_deny = (
        'deny() {\n'
        '  jq -n --arg r "$1" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}\'\n'
        '  exit 0\n'
        '}'
    )
    new_deny = (
        'deny() {\n'
        '  jq -n --arg r "$1" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}\'\n'
        '  exit 0\n'
        '}'
    )
    body = _replace_or_die(body, old_deny, new_deny)
    old_ask = (
        'ask() {\n'
        '  jq -n --arg r "$1" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}\'\n'
        '  exit 0\n'
        '}'
    )
    new_ask = (
        'ask() {\n'
        '  [ "$TB_CONFIRMED" = "1" ] && exit 0\n'
        '  r="$1 Ask the user in chat and wait for explicit confirmation. After\n'
        'confirmation, retry the exact command once with the prefix\n'
        'MAUNGS_TOOLBELT_CONFIRMED=1."\n'
        '  jq -n --arg r "$r" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}\'\n'
        '  exit 0\n'
        '}'
    )
    body = _replace_or_die(body, old_ask, new_ask)
    return body


def transform_toolbelt_router(body: str) -> str:
    """Adapt ``toolbelt-router.sh`` for Codex.

    Emit one valid Codex ``additionalContext`` JSON object when jq is present,
    with plain text as the jq-less fallback. Also record explicit ``$skill``
    mentions because Codex has no Skill invocation hook event.
    """
    body = rewrite_skill_invocations(body)
    body = rewrite_agent_invocations(body)
    body = rewrite_codex_local_paths(body)
    body = body.replace("so Claude can", "so Codex can")
    body = body.replace("Claude (and the user)", "Codex (and the user)")
    body = body.replace("what Claude actually sees", "what Codex actually sees")
    body = body.replace("surface it to Claude", "surface it to Codex")
    for name in SKILL_NAMES:
        body = body.replace("$" + name, "\\$" + name)
    explicit_block = """
# Codex has no Skill hook event. Count explicit $skill mentions at prompt submit.
if [ "$HAVE_JQ" = "1" ] && command -v tb_debug_on >/dev/null 2>&1 && tb_debug_on; then
  for slug in __SKILL_NAMES__; do
    case "$prompt" in
      *'$'"$slug"*|*'@maungs-agentic-toolbelt:'"$slug"*)
        tb_append "$(jq -nc --arg ts "$(tb_now)" --arg component "$slug" \
          --arg session "$TB_SESSION" --arg cwd "$TB_CWD" \
          '{ts:$ts,event:"invoked",kind:"skill",component:$component,raw:$component,session:$session,cwd:$cwd}' 2>/dev/null)"
        ;;
    esac
  done
fi
""".replace("__SKILL_NAMES__", " ".join(SKILL_NAMES))
    body = _replace_or_die(
        body,
        "# lowercase for matching\np=",
        explicit_block + "\n# lowercase for matching\np=",
    )
    old_emit_tail = (
        '  if [ "$HAVE_JQ" = "1" ]; then\n'
        '    jq -n --arg c "$3" \'{suppressOutput:true,hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}\'\n'
        '  else\n'
        '    printf \'%s\\n\' "$3"\n'
        '  fi\n'
        '  exit 0'
    )
    new_emit_tail = (
        '  # Codex: stdout must be either one JSON object or plain text, not both.\n'
        '  if [ "$HAVE_JQ" = "1" ]; then\n'
        '    jq -n --arg c "$3" \'{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}\'\n'
        '  else\n'
        '    printf \'%s\\n\' "$3"\n'
        '  fi\n'
        '  exit 0'
    )
    body = _replace_or_die(body, old_emit_tail, new_emit_tail)
    return body


def transform_sessionstart_loader(body: str) -> str:
    """Adapt ``sessionstart-loader.sh`` for Codex.

    Per decision 16, the ``CLAUDE.md`` / ``CLAUDE.local.md`` filename check and
    its "No CLAUDE.md found" nudge are DELIBERATELY left as-is at the FILENAME
    level (layer-1 filename neutralization does not reach hook scripts; the
    ``CLAUDE.md`` filename is an informational string the user looks for, so it
    stays verbatim). There is no env-var or output-schema token to rewrite.

    What this transform DOES rewrite is EVERY skill invocation embedded in the
    loader's nudges: the ``/agentic-onboard`` nudge ("No CLAUDE.md found …") AND
    the ``/todo`` nudges main added (the private-backlog resurfacing — "Open todos:
    N … /todo to view") are non-functional slash forms on Codex (no slash layer —
    skills are ``@mention``/model-triggered), so each is rewritten to its
    ``$skill`` form via the SAME left-boundary skill-name rule the
    router-suggestion exception uses (decision 16). Applying the general rule
    (anchored to the canonical skill names) rather than per-skill ``_replace_or_die``
    means any FUTURE skill the loader surfaces is handled with no edit here, and
    closes AC-3 fidelity (zero bare ``/<skill>`` invocations in the generated tree).
    The ``CLAUDE.md`` FILENAME reference and the ``…/todos/`` storage-PATH token are
    left intact by the left-boundary rule (a path component / trailing ``s`` is not
    an opening boundary). The presence-assert below fires loud if the canonical
    ``/agentic-onboard`` nudge — the loader's original skill nudge — ever drifts
    away, so the transform can never silently no-op.
    """
    assert "run /agentic-onboard to generate" in body, (
        "transform expected the sessionstart /agentic-onboard nudge line"
    )
    body = rewrite_skill_invocations(body)
    body = rewrite_codex_local_paths(body)
    for name in SKILL_NAMES:
        body = body.replace("$" + name, "\\$" + name)
    body = _replace_or_die(
        body,
        "if [ ! -f CLAUDE.md ] && [ ! -f CLAUDE.local.md ]; then\n"
        '  add "- No CLAUDE.md found — run \\$agentic-onboard to generate agent context for this repo."\n'
        "fi",
        "if [ ! -f AGENTS.md ] && [ ! -f CLAUDE.md ] && [ ! -f CLAUDE.local.md ]; then\n"
        '  add "- No AGENTS.md or CLAUDE.md found — run \\$agentic-onboard to generate agent context for this repo."\n'
        "fi",
    )
    body = body.replace("so Claude\n# begins warm", "so Codex\n# begins warm")
    return body


# Per-hook transform dispatch (keyed by canonical filename). The placeholder
# rewrite + shebang are applied uniformly afterward by the emitter.
HOOK_TRANSFORMS = {
    "lib-telemetry.sh": transform_lib_telemetry,
    "pretooluse-guard.sh": transform_pretooluse_guard,
    "sessionstart-loader.sh": transform_sessionstart_loader,
    "toolbelt-router.sh": transform_toolbelt_router,
    "usage-tracker.sh": transform_usage_tracker,
}


def transform_hook_body(filename: str, body: str) -> str:
    """Apply the per-hook transform for ``filename`` to ``body``."""
    fn = HOOK_TRANSFORMS.get(filename)
    if fn is None:
        return body
    return fn(body)
