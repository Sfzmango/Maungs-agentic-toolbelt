#!/usr/bin/env python3
"""tools/validate_codex.py — validate the Codex manifest + marketplace wrappers.

Stdlib-only validator mirroring Codex ``plugin.json`` rules so CI can assert the
hand-maintained wrappers are well-formed:

  * allowed-keys (no unknown top-level keys),
  * strict-semver ``version``,
  * required fields present,
  * referenced paths EXIST — each file's references resolved against its OWN base
    dir (the manifest and marketplace live at different depths, so the validator
    derives each base dir from that file's path; the two never collide).

The one cross-wrapper reference is pinned: the marketplace entry's ``source`` key
must equal ``plugins/maungs-agentic-toolbelt/`` and resolve (from the repo root)
to the directory holding ``.codex-plugin/plugin.json``.

NEITHER wrapper carries a numeric component count (decision 14) — the CI count
assertion derives the count from the filesystem, so there is nothing to drift.

Usage:
    python3 tools/validate_codex.py
"""

from __future__ import annotations

import json
import os
import re
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_THIS_DIR)

MANIFEST_REL = "plugins/maungs-agentic-toolbelt/.codex-plugin/plugin.json"
MARKETPLACE_REL = ".agents/plugins/marketplace.json"
PINNED_SOURCE = "plugins/maungs-agentic-toolbelt/"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

MANIFEST_ALLOWED = {
    "name",
    "description",
    "version",
    "license",
    "author",
    "homepage",
    "keywords",
    "skills",
}
MANIFEST_REQUIRED = {"name", "description", "version", "skills"}

MARKETPLACE_ALLOWED = {"name", "description", "owner", "plugins"}
MARKETPLACE_REQUIRED = {"name", "plugins"}
MARKETPLACE_PLUGIN_ALLOWED = {
    "name",
    "source",
    "description",
    "author",
    "homepage",
    "license",
    "category",
    "keywords",
}
MARKETPLACE_PLUGIN_REQUIRED = {"name", "source"}


def _load_json(path: str, problems: list) -> dict:
    if not os.path.isfile(path):
        problems.append("missing file: %s" % os.path.relpath(path, REPO_ROOT))
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError) as exc:
        problems.append("%s: invalid JSON (%s)" % (os.path.relpath(path, REPO_ROOT), exc))
        return {}


def _check_keys(obj, allowed, required, label, problems):
    for key in obj:
        if key not in allowed:
            problems.append("%s: unexpected key '%s'" % (label, key))
    for key in required:
        if key not in obj:
            problems.append("%s: missing required key '%s'" % (label, key))


def validate_manifest(problems: list) -> None:
    """Validate the skills-only plugin manifest.

    Base dir for the manifest's internal references is its parent's parent —
    ``plugins/maungs-agentic-toolbelt/`` — so ``skills/<name>/SKILL.md`` resolves
    to ``plugins/maungs-agentic-toolbelt/skills/<name>/SKILL.md``.
    """
    path = os.path.join(REPO_ROOT, MANIFEST_REL)
    obj = _load_json(path, problems)
    if not obj:
        return
    _check_keys(obj, MANIFEST_ALLOWED, MANIFEST_REQUIRED, "manifest", problems)

    version = obj.get("version", "")
    if not _SEMVER.match(str(version)):
        problems.append("manifest: version '%s' is not strict semver X.Y.Z" % version)

    # Manifest forbids agents + hooks (Codex platform constraint) — skills only.
    for forbidden in ("agents", "hooks"):
        if forbidden in obj:
            problems.append("manifest: must NOT carry '%s' (skills-only)" % forbidden)

    # No numeric component count anywhere (decision 14).
    blob = json.dumps(obj)
    if re.search(r"\b\d+ (agents|subagents)\b|\b\d+ skills\b|\b\d+ components\b", blob):
        problems.append("manifest: carries a numeric component count (must not — decision 14)")

    # Manifest base dir = the dir TWO levels up from the manifest file.
    base = os.path.dirname(os.path.dirname(path))  # plugins/maungs-agentic-toolbelt/
    skills = obj.get("skills", [])
    if not isinstance(skills, list) or not skills:
        problems.append("manifest: 'skills' must be a non-empty list")
    else:
        for ref in skills:
            target = os.path.join(base, ref)
            if not os.path.isfile(target):
                problems.append(
                    "manifest: referenced skill path does not exist: %s "
                    "(resolved against %s)" % (ref, os.path.relpath(base, REPO_ROOT))
                )
        # COMPLETENESS (AC-2): the skills list is HAND-MAINTAINED, but the skill
        # FOLDERS under it are GENERATED from canonical. A skill added to canonical
        # (regenerated into a new ``skills/<name>/SKILL.md`` here) that is not also
        # added to this list would be SILENTLY dropped from the Codex marketplace
        # track — existence-only validation cannot catch that. Assert the referenced
        # set EQUALS the generated-folder set (a missing entry AND a stray entry both
        # fail), so the hand-maintained list can never drift from the generated tree.
        skills_dir = os.path.join(base, "skills")
        generated = set()
        if os.path.isdir(skills_dir):
            for name in sorted(os.listdir(skills_dir)):
                if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md")):
                    generated.add("skills/%s/SKILL.md" % name)
        referenced = set(skills)
        for missing in sorted(generated - referenced):
            problems.append(
                "manifest: generated skill not referenced in 'skills' (add it): %s" % missing
            )
        for stray in sorted(referenced - generated):
            problems.append(
                "manifest: 'skills' references a skill with no generated folder: %s" % stray
            )


def validate_marketplace(problems: list) -> None:
    """Validate the marketplace root + the pinned cross-wrapper ``source`` hop.

    Base dir for the marketplace is the REPO ROOT (where ``.agents/`` sits). The
    plugin entry's ``source`` must equal the pinned ``plugins/maungs-agentic-
    toolbelt/`` and resolve (from repo root) to the dir holding the manifest.
    """
    path = os.path.join(REPO_ROOT, MARKETPLACE_REL)
    obj = _load_json(path, problems)
    if not obj:
        return
    _check_keys(obj, MARKETPLACE_ALLOWED, MARKETPLACE_REQUIRED, "marketplace", problems)

    plugins = obj.get("plugins", [])
    if not isinstance(plugins, list) or not plugins:
        problems.append("marketplace: 'plugins' must be a non-empty list")
        return

    blob = json.dumps(obj)
    if re.search(r"\b\d+ (agents|subagents)\b|\b\d+ skills\b|\b\d+ components\b", blob):
        problems.append("marketplace: carries a numeric component count (must not — decision 14)")

    found_pinned = False
    for entry in plugins:
        _check_keys(
            entry,
            MARKETPLACE_PLUGIN_ALLOWED,
            MARKETPLACE_PLUGIN_REQUIRED,
            "marketplace plugin entry",
            problems,
        )
        source = entry.get("source", "")
        if entry.get("name") == "maungs-agentic-toolbelt":
            found_pinned = True
            # Pin the cross-wrapper reference exactly.
            if source != PINNED_SOURCE:
                problems.append(
                    "marketplace: plugin 'source' must equal '%s' (got '%s')"
                    % (PINNED_SOURCE, source)
                )
            # Resolve the source from the repo root and confirm it holds the manifest.
            plugin_dir = os.path.join(REPO_ROOT, source)
            if not os.path.isdir(plugin_dir):
                problems.append(
                    "marketplace: 'source' dir does not exist: %s" % source
                )
            else:
                manifest = os.path.join(plugin_dir, ".codex-plugin", "plugin.json")
                if not os.path.isfile(manifest):
                    problems.append(
                        "marketplace: 'source' dir does not contain "
                        ".codex-plugin/plugin.json: %s" % source
                    )
    if not found_pinned:
        problems.append(
            "marketplace: no plugin entry named 'maungs-agentic-toolbelt'"
        )

    # Assert the two base dirs do not collide: manifest base is two levels under
    # the marketplace base (repo root), so they are distinct by construction.
    manifest_base = os.path.dirname(os.path.dirname(os.path.join(REPO_ROOT, MANIFEST_REL)))
    marketplace_base = REPO_ROOT
    if os.path.abspath(manifest_base) == os.path.abspath(marketplace_base):
        problems.append("validator: manifest and marketplace base dirs collide")


def main(argv=None) -> int:
    problems: list = []
    validate_manifest(problems)
    validate_marketplace(problems)
    if problems:
        print("validate_codex: FAIL", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print("validate_codex: OK — manifest + marketplace are well-formed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
