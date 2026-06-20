#!/usr/bin/env python3
"""tools/build.py — the toolbelt's per-target artifact generator.

Reads the single canonical source (``agents/*.md`` + ``skills/*/SKILL.md`` +
``hooks/``) and emits per-target artifacts. Pure Python 3 stdlib.

Usage:
    python3 tools/build.py [--target codex|claude|all] [--check]

  --target codex   emit the Codex artifacts to disk (default)
  --target claude  run the VALIDATE-ONLY Claude emitter (writes nothing)
  --target all     do both
  --check          regenerate into memory and EXIT NON-ZERO on any diff against
                   the committed tree (the exact mode CI runs); writes nothing.
                   For --target claude, --check is implied (it never writes).

The Codex drift guard: ``--target codex`` (no --check) writes the artifacts;
CI then fails if ``git diff`` is non-empty. ``--target codex --check`` is the
in-memory differ used by the determinism / staleness tests.
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running as a script (``python3 tools/build.py``) by ensuring the repo
# root is importable for the ``tools`` package.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from tools.emit import common  # noqa: E402
from tools.emit import target_codex  # noqa: E402
from tools.emit import target_claude  # noqa: E402


REGENERATE_MSG = (
    "Codex artifacts drifted from canonical — regenerate with "
    "'python3 tools/build.py --target codex' and commit the result."
)


def _emit_codex(root: str, check: bool) -> int:
    """Emit (or --check) the Codex artifacts. Returns a process exit code."""
    artifacts = target_codex.build_artifacts(root)

    if check:
        diffs = []
        for rel, content in sorted(artifacts.items()):
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                diffs.append("MISSING: %s (would be generated)" % rel)
                continue
            existing = common.read_text(path)
            existing = common.finalize_emitted(existing)
            if existing != content:
                diffs.append("DRIFT:   %s" % rel)
        if diffs:
            print(REGENERATE_MSG, file=sys.stderr)
            for d in diffs:
                print("  " + d, file=sys.stderr)
            return 1
        print("Codex --check: OK — %d artifacts match canonical." % len(artifacts))
        return 0

    written = 0
    for rel, content in sorted(artifacts.items()):
        path = os.path.join(root, rel)
        common.write_text(path, content)
        written += 1
    print("Codex emit: wrote %d artifacts." % written)
    return 0


def _emit_claude(root: str) -> int:
    """Run the validate-only Claude emitter. Returns a process exit code."""
    problems = target_claude.validate(root)
    if problems:
        print(
            "Claude validate-only: FAIL — canonical no longer reproduces today's "
            "Claude artifacts:",
            file=sys.stderr,
        )
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print("Claude validate-only: OK — canonical reproduces today's Claude artifacts.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-target artifact generator for the toolbelt (stdlib-only)."
    )
    parser.add_argument(
        "--target",
        choices=["codex", "claude", "all"],
        default="codex",
        help="which target to emit (default: codex).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and exit non-zero on any diff (writes nothing).",
    )
    args = parser.parse_args(argv)

    root = common.REPO_ROOT
    rc = 0

    if args.target in ("claude", "all"):
        # The Claude emitter is always validate-only; --check is implied.
        rc |= _emit_claude(root)

    if args.target in ("codex", "all"):
        rc |= _emit_codex(root, check=args.check)

    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
