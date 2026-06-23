#!/usr/bin/env python3
"""Enforce the every-PR version-bump rule: head version must be strictly greater
than base version.

This repo's plugin is distributed by ``.claude-plugin/plugin.json`` ``version``,
and Claude Code caches installed plugins by that version — so a shipped change
that does not bump the version never reaches installs. The rule for developing
THIS repo (not a behavior imposed on host projects the toolbelt operates on) is
therefore: every PR bumps the version. CI calls this checker with the base and
head versions; the comparison logic lives here, pure and stdlib-only, so
``tests/test_version_bump.py`` can exercise it without GitHub.

Versions are strict semver ``MAJOR.MINOR.PATCH`` (the repo convention); anything
else is rejected loudly rather than guessed at. Ordering is numeric per field
(so ``0.9.0`` < ``0.10.0``, which a string compare would get wrong).

Usage:  python3 tools/check_version_bump.py <base_version> <head_version>
Exit:   0 = head > base (bump present) · 1 = not bumped · 2 = malformed version
"""
from __future__ import annotations

import sys


def parse(version: str) -> tuple:
    """Parse a strict ``MAJOR.MINOR.PATCH`` semver into an int tuple.

    Raises ``ValueError`` on anything that is not exactly three dot-separated
    non-negative integers (no pre-release/build metadata — this repo pins plain
    X.Y.Z).
    """
    parts = version.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(
            "not strict semver MAJOR.MINOR.PATCH: %r" % version
        )
    return tuple(int(p) for p in parts)


def is_bump(base: str, head: str) -> bool:
    """True iff ``head`` is a strictly higher version than ``base``."""
    return parse(head) > parse(base)


def main(argv) -> int:
    if len(argv) != 3:
        print(
            "usage: check_version_bump.py <base_version> <head_version>",
            file=sys.stderr,
        )
        return 2
    base, head = argv[1], argv[2]
    try:
        bumped = is_bump(base, head)
    except ValueError as exc:
        print("version-bump check: %s" % exc, file=sys.stderr)
        return 2
    if not bumped:
        print(
            "version-bump check FAILED: .claude-plugin/plugin.json version must "
            "increase on every PR — base=%s head=%s. Bump it (and keep the Codex "
            "manifest plugins/maungs-agentic-toolbelt/.codex-plugin/plugin.json "
            "in parity)." % (base, head),
            file=sys.stderr,
        )
        return 1
    print("version-bump check OK: %s -> %s" % (base, head))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
