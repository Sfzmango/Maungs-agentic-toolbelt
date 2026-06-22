"""Claude target — VALIDATE-ONLY. Writes NOTHING.

The Claude artifacts (``agents/*.md``, ``skills/*/SKILL.md``, ``.claude-plugin/*``,
``hooks/*``, ``install.sh``) ARE the canonical source — there is nothing to
re-emit. This emitter's job (AC-7) is to confirm the canonical source still
PARSES into well-formed Components, so a malformed canonical edit (broken
frontmatter, a missing ``name:``) is caught as a Claude regression rather than
silently shipping.

Because the generator physically cannot rewrite Claude source (this module has
no write path), "no Claude regression" is a STRUCTURAL guarantee, not a
discipline (decision 6).

``validate()`` returns a list of problem strings; an empty list means PASS.
"""

from __future__ import annotations

from typing import List

from . import common


def validate(root: str) -> List[str]:
    """Validate that canonical source still yields today's Claude components.

    Checks every agent + skill parses, declares a ``name:`` matching its
    filename slug, and (for agents) declares a non-empty ``tools:`` list. Returns
    a list of problem descriptions; empty == PASS. Writes nothing.
    """
    problems: List[str] = []

    for comp in common.load_agents(root):
        expected = comp.source_path.split("/")[-1][: -len(".md")]
        if not comp.name:
            problems.append("%s: missing 'name:' in frontmatter" % comp.source_path)
        elif comp.name != expected:
            problems.append(
                "%s: name '%s' does not match filename slug '%s'"
                % (comp.source_path, comp.name, expected)
            )
        if not comp.tools:
            problems.append(
                "%s: agent declares no 'tools:' (least-privilege list required)"
                % comp.source_path
            )
        if not comp.frontmatter.get("description"):
            problems.append("%s: missing 'description:'" % comp.source_path)

    for comp in common.load_skills(root):
        # skill slug = the folder name = parent dir of SKILL.md
        parts = comp.source_path.split("/")
        expected = parts[-2] if len(parts) >= 2 else ""
        if not comp.name:
            problems.append("%s: missing 'name:' in frontmatter" % comp.source_path)
        elif comp.name != expected:
            problems.append(
                "%s: name '%s' does not match folder slug '%s'"
                % (comp.source_path, comp.name, expected)
            )
        if not comp.frontmatter.get("description"):
            problems.append("%s: missing 'description:'" % comp.source_path)

    return problems
