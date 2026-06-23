#!/usr/bin/env python3
"""Stdlib test suite for the every-PR version-bump checker (tools/check_version_bump.py).

Plain Python 3 stdlib (no pytest), matching the repo's existing test style. Run:

    python3 tests/test_version_bump.py

Covers the comparison logic the CI gate (validate.yml check 13) relies on:
  * a bump in each field passes (patch / minor / major);
  * equal or decreased versions fail (the forgotten-bump case CI must catch);
  * ordering is numeric, not lexical (0.9.0 < 0.10.0);
  * malformed / non-strict-semver versions are rejected (exit 2), not guessed.
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_THIS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import check_version_bump as cvb  # noqa: E402

# (base, head, expected is_bump result)
BUMP_CASES = [
    ("0.10.0", "0.10.1", True),    # patch
    ("0.10.0", "0.11.0", True),    # minor
    ("0.10.0", "1.0.0", True),     # major
    ("0.9.0", "0.10.0", True),     # numeric, not lexical ("10" > "9")
    ("1.2.3", "1.2.4", True),
    ("0.10.0", "0.10.0", False),   # equal — the forgotten-bump case
    ("0.10.1", "0.10.0", False),   # decreased
    ("0.11.0", "0.10.9", False),   # minor outranks patch
    ("1.0.0", "0.99.99", False),   # major outranks the rest
]

# versions that must raise ValueError (CI maps this to exit 2)
MALFORMED = ["0.10", "1.2.3.4", "0.1.x", "v0.1.0", "", "1.2.-3", "01.2.x"]


def main() -> int:
    results = []  # (ok, label)

    for base, head, expected in BUMP_CASES:
        try:
            got = cvb.is_bump(base, head)
            ok = got == expected
            label = "is_bump(%r, %r) == %s" % (base, head, expected)
        except ValueError as exc:
            ok = False
            label = "is_bump(%r, %r) raised unexpectedly: %s" % (base, head, exc)
        results.append((ok, label))

    for bad in MALFORMED:
        try:
            cvb.parse(bad)
            ok = False
            label = "parse(%r) should have raised ValueError" % bad
        except ValueError:
            ok = True
            label = "parse(%r) rejected" % bad
        results.append((ok, label))

    # main() exit-code contract: 0 on bump, 1 on no-bump, 2 on malformed/usage.
    contract = [
        (cvb.main(["x", "0.10.0", "0.10.1"]) == 0, "main bump -> 0"),
        (cvb.main(["x", "0.10.0", "0.10.0"]) == 1, "main no-bump -> 1"),
        (cvb.main(["x", "0.10.0", "0.1.x"]) == 2, "main malformed -> 2"),
        (cvb.main(["x", "0.10.0"]) == 2, "main bad-arity -> 2"),
    ]
    results.extend(contract)

    fails = [label for ok, label in results if not ok]
    total = len(results)
    passed = total - len(fails)

    print("FAILURES (%d):" % len(fails))
    if not fails:
        print("  (none)")
    for label in fails:
        print("  ✗ %s" % label)

    all_ok = not fails
    print("\nRESULT: %s  (%d/%d checks)" % ("PASS" if all_ok else "FAIL", passed, total))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
