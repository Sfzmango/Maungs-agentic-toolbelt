"""Shared core for the toolbelt's per-target generator.

Pure Python 3 stdlib (no third-party imports, no package manager) — matching the
repo's no-build-system constraint. This module carries:

  * the frontmatter parser (the same ``---``-block logic CI's frontmatter check
    relies on), whose ``tools:`` reader normalizes BOTH serializations — the YAML
    block-list form (15 agents) AND the inline comma-separated form
    (``agents/code-translator.md`` alone) — into one tool-token list;
  * the ``Component`` dataclass;
  * deterministic file IO (newline normalization on read, single-trailing-newline
    on write) so the CI drift guard never flags a spurious diff.

Determinism rules enforced here (see the plan's "Determinism" section):
  1. all directory enumeration goes through ``sorted(...)``;
  2. line endings normalized to ``\n`` on read (every ``\r`` stripped);
  3. emitted content ends with exactly one trailing ``\n``;
  4. no timestamps, no host paths, no environment-derived values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Repo root = the parent of tools/ . Derived from this file's location, NOT from
# cwd or an env var, so the generator is location-stable regardless of where it
# is invoked. (This path is used for READING canonical source and WRITING
# generated artifacts; it never lands inside emitted CONTENT.)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class Component:
    """One canonical component (an agent or a skill).

    ``kind`` is "agent" or "skill". ``name`` is the slug. ``frontmatter`` is the
    parsed key->value map (scalars only; ``tools`` is handled separately).
    ``tools`` is the normalized tool-token list (empty when none declared).
    ``body`` is the markdown body BELOW the closing frontmatter ``---``, with
    ``\n``-only line endings and no trailing blank lines beyond a single ``\n``.
    ``source_path`` is the repo-relative path of the canonical file.
    """

    kind: str
    name: str
    frontmatter: Dict[str, str]
    tools: List[str]
    body: str
    source_path: str
    raw: str = ""  # the full normalized source text (frontmatter + body)


# ---------------------------------------------------------------------------
# Deterministic file IO
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize line endings to ``\n`` (strip every ``\r``).

    Idempotent. Used on every read so a canonical ``.md`` saved with CRLF does
    not flip the drift guard.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: str) -> str:
    """Read a file and normalize its line endings to ``\n``."""
    with open(path, "r", encoding="utf-8") as fh:
        return normalize_text(fh.read())


def finalize_emitted(text: str) -> str:
    """Pin trailing-newline state: exactly one trailing ``\n``, ``\n``-only.

    Strips any ``\r`` then trims all trailing newlines and appends exactly one,
    so a source with a missing or doubled trailing newline emits identically.
    """
    text = normalize_text(text)
    return text.rstrip("\n") + "\n"


def write_text(path: str, text: str) -> None:
    """Write emitted content with the pinned trailing-newline rule.

    Creates parent directories as needed. Never writes a host path or timestamp
    (that is the caller's contract; this helper only pins newline handling).
    """
    text = finalize_emitted(text)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def split_frontmatter(text: str) -> "tuple[str, str]":
    """Split a component file into (frontmatter_block, body).

    Mirrors CI's ``---``-block logic: the file MUST start with a ``---`` line,
    and the frontmatter ends at the next lone ``---`` line. The body is
    everything after that closing fence. Raises ``ValueError`` when the file does
    not open with ``---`` or has no closing fence.
    """
    text = normalize_text(text)
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        raise ValueError("file does not start with '---' frontmatter")
    closing = None
    for idx in range(1, len(lines)):
        if lines[idx].rstrip() == "---":
            closing = idx
            break
    if closing is None:
        raise ValueError("frontmatter has no closing '---'")
    fm_block = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1:])
    # Strip a single leading blank line in the body (the blank that follows the
    # closing fence in every canonical file) so emitted bodies are stable.
    if body.startswith("\n"):
        body = body[1:]
    # Pin the body's trailing-newline state: no trailing blank lines (the emitter
    # re-adds exactly the newline the artifact format needs). This is what makes
    # a source with a doubled/missing trailing newline emit a byte-identical
    # body — both collapse to the same rstripped form.
    body = body.rstrip("\n")
    return fm_block, body


def _normalize_tools_value(value: str) -> List[str]:
    """Parse the INLINE ``tools:`` value (comma-separated on one line).

    e.g. ``Read, Grep, Bash, mcp__context7__resolve-library-id`` ->
    ``["Read", "Grep", "Bash", "mcp__context7__resolve-library-id"]``.
    """
    return [tok.strip() for tok in value.split(",") if tok.strip()]


def parse_frontmatter(fm_block: str) -> "tuple[Dict[str, str], List[str]]":
    """Parse a frontmatter block into (scalars, tools).

    Handles BOTH ``tools:`` serializations:
      * INLINE comma-separated on the ``tools:`` line itself
        (``agents/code-translator.md`` alone), and
      * a YAML BLOCK LIST (``tools:`` bare, then indented ``  - Read`` lines).

    Both normalize to one tool-token list, since ``sandbox_mode`` (Edit/Write
    detection) and ``mcp_servers`` (distinct ``mcp__<server>__`` enumeration)
    both derive from it — and the marquee ``code-translator`` ->
    ``mcp_servers = ["context7"]`` parity case is exactly the inline form, so a
    block-list-only reader would silently drop Context7.

    Other scalar keys are kept verbatim (value side trimmed). List-valued keys
    other than ``tools`` are not used by any emitter, so they are skipped.
    """
    scalars: Dict[str, str] = {}
    tools: List[str] = []
    lines = fm_block.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        # A top-level key has no leading whitespace and contains a ':'.
        if not line.startswith((" ", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "tools":
                if value:
                    # INLINE form: tools listed on this same line.
                    tools = _normalize_tools_value(value)
                    i += 1
                else:
                    # BLOCK-LIST form: consume the indented '- item' lines.
                    i += 1
                    while i < n:
                        item = lines[i]
                        stripped = item.strip()
                        if item.startswith((" ", "\t")) and stripped.startswith("- "):
                            tools.append(stripped[2:].strip())
                            i += 1
                        elif not stripped:
                            i += 1
                        else:
                            break
            else:
                scalars[key] = value
                i += 1
        else:
            # An indented or non key:value line outside a tools block — skip it.
            i += 1
    return scalars, tools


# ---------------------------------------------------------------------------
# Component loading
# ---------------------------------------------------------------------------

def load_component(path: str, kind: str) -> Component:
    """Load one canonical component file into a ``Component``."""
    raw = read_text(path)
    fm_block, body = split_frontmatter(raw)
    scalars, tools = parse_frontmatter(fm_block)
    name = scalars.get("name", "")
    rel = os.path.relpath(path, REPO_ROOT)
    return Component(
        kind=kind,
        name=name,
        frontmatter=scalars,
        tools=tools,
        body=body,
        source_path=rel,
        raw=raw,
    )


def load_agents(root: Optional[str] = None) -> List[Component]:
    """Load every ``agents/*.md`` as an agent Component, sorted by filename."""
    root = root or REPO_ROOT
    agents_dir = os.path.join(root, "agents")
    out: List[Component] = []
    for fn in sorted(os.listdir(agents_dir)):
        if not fn.endswith(".md"):
            continue
        out.append(load_component(os.path.join(agents_dir, fn), "agent"))
    return out


def load_skills(root: Optional[str] = None) -> List[Component]:
    """Load every ``skills/<name>/SKILL.md`` as a skill Component, sorted."""
    root = root or REPO_ROOT
    skills_dir = os.path.join(root, "skills")
    out: List[Component] = []
    for name in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, name, "SKILL.md")
        if os.path.isfile(skill_md):
            out.append(load_component(skill_md, "skill"))
    return out


def load_hook_bodies(root: Optional[str] = None) -> Dict[str, str]:
    """Load the five canonical hook ``.sh`` bodies, sorted by filename.

    Returns a dict keyed by filename (e.g. ``"pretooluse-guard.sh"``) -> the
    normalized body text. Includes ``lib-telemetry.sh`` (sourced, not registered)
    because the generated hooks source it.
    """
    root = root or REPO_ROOT
    hooks_dir = os.path.join(root, "hooks")
    wanted = [
        "lib-telemetry.sh",
        "pretooluse-guard.sh",
        "sessionstart-loader.sh",
        "toolbelt-router.sh",
        "usage-tracker.sh",
    ]
    out: Dict[str, str] = {}
    for fn in sorted(wanted):
        path = os.path.join(hooks_dir, fn)
        out[fn] = read_text(path)
    return out


# ---------------------------------------------------------------------------
# Tool-derived facts (shared by the Codex emitter)
# ---------------------------------------------------------------------------

def derive_sandbox_mode(tools: List[str]) -> str:
    """``read-only`` unless the tools list grants Edit or Write."""
    if "Edit" in tools or "Write" in tools:
        return "workspace-write"
    return "read-only"


def derive_mcp_servers(tools: List[str]) -> List[str]:
    """Enumerate every DISTINCT ``mcp__<server>__`` prefix in the tools list.

    Server-name-agnostic: ``mcp__github__*`` -> ``github``,
    ``mcp__context7__*`` -> ``context7``, etc. Sorted + de-duplicated. Empty when
    the agent declares no ``mcp__*`` tool (the caller then OMITS ``mcp_servers``).
    """
    servers = set()
    for tok in tools:
        if tok.startswith("mcp__"):
            rest = tok[len("mcp__"):]
            server = rest.split("__", 1)[0]
            if server:
                servers.add(server)
    return sorted(servers)
