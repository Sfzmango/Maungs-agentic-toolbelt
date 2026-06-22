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
      * ``/skill`` -> ``@skill`` via a LEFT-BOUNDARY rule (whitespace/line-start
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
# rewrites to ``@name``. Derived DYNAMICALLY from the canonical ``skills/``
# directory (the same single source ``common.load_skills`` enumerates), so a NEW
# skill — ``overnight``, ``todo``, or any future one — is picked up automatically
# with no hand-maintained list to drift out of sync with the emitter. Sorted;
# longest-first matching is enforced in the regex build so e.g.
# ``/migration-planner`` is not partially matched by a shorter name.
#
# Enumeration is rooted at ``common.REPO_ROOT`` (the build always runs from the
# repo root). The generator's temp-root tests copy the IDENTICAL skill set into
# their fixture, so this REPO_ROOT-derived list matches whatever root the emitter
# renders — there is no real code path where the two diverge.
SKILL_NAMES = sorted(comp.name for comp in common.load_skills())


# ---------------------------------------------------------------------------
# Layer 1 — canonical-safe neutralization (agent/skill BODIES only)
# ---------------------------------------------------------------------------

def neutralize_body(text: str) -> str:
    """Apply the canonical-safe neutralization (safe on Claude too).

    Scoped to agent/skill bodies — NOT hook scripts (decision 16). Idempotent:
    re-running does not double-rewrite, because the replacement target already
    contains the source token.
    """
    # "restart Claude Code" -> "restart your agent" (do this BEFORE the
    # CLAUDE.md rule so "Claude Code" is consumed first; case-insensitive on the
    # verb phrase but we only target the exact prose form used in the repo).
    text = text.replace("restart Claude Code", "restart your agent")
    # CLAUDE.md -> AGENTS.md / CLAUDE.md, but only when not already part of the
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
        r"(?<!/ )(?<![\w/.~-])CLAUDE\.md\b",
        "AGENTS.md / CLAUDE.md",
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
# Layer 2 — /skill -> @skill (LEFT-BOUNDARY rule)
# ---------------------------------------------------------------------------

def _skill_alternation() -> str:
    # Longest names first so the alternation never partially matches.
    names = sorted(SKILL_NAMES, key=len, reverse=True)
    return "|".join(re.escape(n) for n in names)


# Left boundary = start-of-string OR a whitespace char OR an OPENING delimiter
# (backtick / open-paren / double-quote). Broadening past bare-whitespace is what
# lets the rule reach backtick-wrapped (`` `/orchestrator` ``), parenthesized
# (``(/wiki-generator …)``) AND double-quoted invocations — the latter is the
# mermaid node-label form ``A["/overnight [repo]"]`` (a quoted invocation depicted
# in a flow diagram), so the diagram label is rewritten to ``@overnight`` too. We
# rewrite the leading skill TOKEN only (``/orchestrator`` -> ``@orchestrator``) and
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
    """Rewrite a bare/wrapped ``/skill`` invocation -> ``@skill`` (left-boundary only).

    Rewrites ``/orchestrator`` when preceded by whitespace/line-start OR an opening
    delimiter (backtick / open-paren) to ``@orchestrator`` — so `` `/orchestrator` ``
    -> `` `@orchestrator` `` and ``(/wiki-generator …)`` -> ``(@wiki-generator …)`` —
    while leaving ``skills/orchestrator/SKILL.md``,
    `` `skills/orchestrator/SKILL.md` ``, ``developer/orchestrator``, and
    ``@playwright/mcp@latest`` untouched (each has a path component, not an opening
    boundary, immediately left of the slash). The trailing args / sub-commands /
    flags / closing backtick to the right are left exactly as-is —
    ``/orchestrator <topic>`` -> ``@orchestrator <topic>``.
    """
    return _SKILL_LEFT_BOUNDARY.sub(lambda m: m.group(1) + "@" + m.group(2), text)


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
    text = neutralize_body(text)               # layer 1
    text = rewrite_mcp_prose(text)             # layer 2
    text = neutralize_toolsearch(text)         # layer 2
    text = rewrite_claude_mcp_cli(text)        # layer 2
    text = rewrite_skill_invocations(text)     # layer 2
    text = rewrite_askuserquestion(text, component_name in GATE_BODIES)
    return text


def transform_description(text: str, component_name: str) -> str:
    """Run a frontmatter ``description`` through the body transforms.

    The description is carried into the TOML ``description`` field and the skill
    frontmatter, so it gets the same adaptation as the body.
    """
    return transform_body(text, component_name)


# ---------------------------------------------------------------------------
# Hook-body transforms (env-var + output-schema + log-path rules)
# ---------------------------------------------------------------------------

# The Codex hook-root placeholder. The committed template carries this literal;
# the installer substitutes the real install dir at install time. NEVER an
# absolute path at build time (determinism + leak-grep).
HOOK_DIR_PLACEHOLDER = "__TOOLBELT_HOOK_DIR__"


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
    # AC-3 "no slash layer": the comment guidance "View it with `/toolbelt
    # metrics`." names a slash command that is invalid on Codex (skills are
    # @mention/model-triggered). Rewrite the backtick-wrapped slash form to the
    # @mention form, the same way the router-suggestion exception does for the
    # router hook. _replace_or_die fires if the canonical comment ever moves.
    body = _replace_or_die(body, "`/toolbelt metrics`", "`@toolbelt metrics`")
    return body


def transform_usage_tracker(body: str) -> str:
    """Adapt ``usage-tracker.sh`` for Codex.

    * Rewrite the ``CLAUDE_PLUGIN_ROOT`` membership check to a hook-root the
      installed Codex layout actually has, and the agent membership file to the
      ``.toml`` form.
    * Degrade the bare-slug SKILL filesystem fallback to AGENT-ONLY on Codex (the
      marketplace skill root is a separate, installer-unowned dir — decision 15).
      The explicit ``maungs-agentic-toolbelt:`` namespace branch is unchanged.
    """
    # Resolve a Codex hook root from the script's own directory (BASH_SOURCE),
    # the same dir the installer copies the script into. Insert it right after
    # the TB_DIR resolution that already exists in the canonical body.
    body = _replace_or_die(
        body,
        '. "${TB_DIR}/lib-telemetry.sh" 2>/dev/null || exit 0',
        '. "${TB_DIR}/lib-telemetry.sh" 2>/dev/null || exit 0\n'
        '# Codex hook root: this script\'s own install dir (installer-owned).\n'
        'TB_HOOK_ROOT="${TB_DIR}"',
    )
    # Replace the Claude env-var-keyed membership block with a Codex hook-root
    # block: agent membership checks the installed `.toml`; the skill bare-slug
    # filesystem fallback is dropped (agent-only on Codex).
    old_block = (
        'if [ "$is_ours" = "0" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then\n'
        '  case "$kind" in\n'
        '    agent) [ -f "${CLAUDE_PLUGIN_ROOT}/agents/${slug}.md" ] && is_ours=1 ;;\n'
        '    skill) [ -d "${CLAUDE_PLUGIN_ROOT}/skills/${slug}" ]    && is_ours=1 ;;\n'
        '  esac\n'
        'fi'
    )
    new_block = (
        '# Codex: agents + hooks live under the installer-owned hook root, but\n'
        '# skills install via the SEPARATE marketplace plugin dir the installer\n'
        '# does not own — so the bare-slug filesystem fallback is AGENT-ONLY here.\n'
        '# The explicit "maungs-agentic-toolbelt:" namespace branch above still\n'
        '# counts a skill; only the bare-slug skill filesystem fallback is dropped\n'
        '# on Codex (telemetry is opt-in / best-effort, so a missed bare-slug\n'
        '# skill event is non-fatal).\n'
        'if [ "$is_ours" = "0" ] && [ -n "${TB_HOOK_ROOT:-}" ]; then\n'
        '  case "$kind" in\n'
        '    agent) [ -f "${TB_HOOK_ROOT}/agents/${slug}.toml" ] && is_ours=1 ;;\n'
        '  esac\n'
        'fi'
    )
    body = _replace_or_die(body, old_block, new_block)
    # Update the header comment that referenced ~/.claude for the log dir.
    body = _replace_or_die(
        body,
        "#   - Read-only except for the append-only log under ~/.claude (see lib-telemetry).",
        "#   - Read-only except for the append-only log under ~/.codex (see lib-telemetry).",
    )
    # AC-3 "no slash layer": the comment "so `/toolbelt metrics` can show what
    # gets used" names a slash command invalid on Codex — rewrite to the @mention
    # form (router-suggestion exception). _replace_or_die fires if it ever moves.
    body = _replace_or_die(body, "`/toolbelt metrics`", "`@toolbelt metrics`")
    return body


def transform_pretooluse_guard(body: str) -> str:
    """Adapt ``pretooluse-guard.sh`` for Codex.

    * Emit the deny/ask decision in BOTH the canonical ``hookSpecificOutput``
      envelope and a flat ``{decision,reason}`` shape, so an unrecognized Codex
      PreToolUse schema still surfaces a ``deny``/``ask`` to the user rather than
      no-opping. Accuracy note (decision 12): the guard runs its rules ONLY when
      jq is present — the canonical top-of-file ``command -v jq … || exit 0``
      ALLOWS (matching the canonical Claude guard) on a jq-less host, so the
      deny/ask helpers are never reached there. Because the helpers are reached
      ONLY with jq present, each emits the jq line DIRECTLY (no jq-less branch to
      under-escape). Install jq for full guard coverage.
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
    old_attr = (
        "if hasraw 'git([[:space:]]|.)*commit' && hasraw "
        "'Co-Authored-By:[[:space:]]*Claude|Generated with[[:space:]].*Claude|🤖'; then"
    )
    new_attr = (
        "if hasraw 'git([[:space:]]|.)*commit' && hasrawi '" + _attr_pattern + "'; then"
    )
    body = _replace_or_die(body, old_attr, new_attr)
    body = _replace_or_die(
        body,
        'deny "Toolbelt cardinal rule: no AI attribution in commits/PRs (no \'Co-Authored-By: Claude\' / \'Generated with Claude Code\'). Remove it from the commit message. (MAUNGS_TOOLBELT_GUARD=off to override.)"',
        'deny "Toolbelt cardinal rule: no AI/assistant attribution in commits/PRs (no \'Co-Authored-By:\' naming any AI/assistant/model, no \'Generated with/by <any AI tool>\', no robot marker). Remove it from the commit message. (MAUNGS_TOOLBELT_GUARD=off to override.)"',
    )
    # Make the deny/ask emit Codex's PreToolUse form. The canonical helpers emit
    # only the hookSpecificOutput envelope; on Codex we ALSO emit a flat
    # {decision,reason} shape so an unrecognized schema still surfaces a decision.
    # The helpers are reached ONLY with jq present (the top-of-file
    # `command -v jq … || exit 0` allows on a jq-less host, matching the canonical
    # Claude guard), so the jq line is emitted DIRECTLY — there is no jq-less
    # branch to under-escape. See the docstring + decision 12.
    old_deny = (
        'deny() {\n'
        '  jq -n --arg r "$1" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}\'\n'
        '  exit 0\n'
        '}'
    )
    new_deny = (
        'deny() {\n'
        '  # Codex PreToolUse: emit the structured decision (both the canonical\n'
        '  # envelope and a flat {decision,reason}). Reached ONLY with jq present;\n'
        '  # a jq-less host already exited 0 (ALLOW) at the top-of-file jq guard,\n'
        '  # matching the canonical Claude guard. Install jq for full coverage.\n'
        '  jq -n --arg r "$1" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r},decision:"deny",reason:$r}\'\n'
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
        '  # Codex PreToolUse "ask" — emit structured + flat. Reached ONLY with jq\n'
        '  # present; a jq-less host already exited 0 (ALLOW) at the top-of-file jq\n'
        '  # guard, matching the canonical Claude guard. Install jq for coverage.\n'
        '  jq -n --arg r "$1" \'{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r},decision:"ask",reason:$r}\'\n'
        '  exit 0\n'
        '}'
    )
    body = _replace_or_die(body, old_ask, new_ask)
    return body


def transform_toolbelt_router(body: str) -> str:
    """Adapt ``toolbelt-router.sh`` for Codex.

    Emit BOTH the JSON ``additionalContext`` shape AND the plain-stdout fallback
    (the canonical body already has the stdout branch) so the suggestion surfaces
    whichever channel Codex consumes. Keep the anti-autonomy PREFIX guard ("do
    NOT auto-run ... without confirmation") verbatim.

    The router is the ONE hook whose stdout/additionalContext SUGGESTS skill
    invocations to the user (``- /orchestrator``, ``- /agentic-onboard``, …). On
    Codex there is no slash layer — skills are ``@mention``/model-triggered — so a
    ``/skill`` suggestion is invalid and contradicts docs/codex.md. Apply the SAME
    left-boundary ``/skill`` -> ``@skill`` rewrite the agent/skill BODIES get
    (decision 16's router-suggestion exception) so the emitted suggestion prose
    offers ``@orchestrator`` etc. The left-boundary rule (whitespace/line-start to
    the left, anchored to the canonical skill names) leaves any ``skills/<name>/...``
    path token intact; the guard/loader/tracker hooks emit no skill suggestions, so
    this is scoped to the router only.
    """
    # Router-suggestion exception to decision 16: rewrite the /skill suggestion
    # tokens in the router body so Codex sees @mention-form skill offers.
    body = rewrite_skill_invocations(body)
    # Make emit() print BOTH channels on Codex: the structured additionalContext
    # JSON AND the stdout fallback. The canonical body emits one OR the other;
    # the Codex form emits both (JSON when jq is present, then ALWAYS the stdout
    # line) so neither channel is lost.
    old_emit_tail = (
        '  if [ "$HAVE_JQ" = "1" ]; then\n'
        '    jq -n --arg c "$3" \'{suppressOutput:true,hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}\'\n'
        '  else\n'
        '    printf \'%s\\n\' "$3"\n'
        '  fi\n'
        '  exit 0'
    )
    new_emit_tail = (
        '  # Codex: emit BOTH the structured additionalContext envelope AND the\n'
        '  # plain-stdout fallback, so the suggestion surfaces whichever channel\n'
        '  # Codex consumes (additionalContext consumption on Codex is unverified).\n'
        '  if [ "$HAVE_JQ" = "1" ]; then\n'
        '    jq -n --arg c "$3" \'{suppressOutput:false,hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}\'\n'
        '  fi\n'
        '  printf \'%s\\n\' "$3"\n'
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
    ``@mention`` form via the SAME left-boundary skill-name rule the
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
    return rewrite_skill_invocations(body)


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
