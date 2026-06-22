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

The cross-wrapper reference is pinned to Codex's current structured local-source
schema: ``source.source`` must be ``local`` and ``source.path`` must equal
``./plugins/maungs-agentic-toolbelt``. The path resolves from the repo root to
the directory holding ``.codex-plugin/plugin.json``.

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
PINNED_SOURCE_PATH = "./plugins/maungs-agentic-toolbelt"
PINNED_SKILLS_PATH = "./skills/"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# Broadened component-count denylist (BUG-12): case-insensitive, singular/plural
# forms of agent(s)/subagent(s)/skill(s)/component(s) preceded by a number.
_COUNT_RX = re.compile(r"(?i)\b\d+\s+(agents?|subagents?|skills?|components?)\b")

# Sentinel returned by ``_load_json`` to signal a LOAD FAILURE (missing file or
# invalid JSON) distinctly from a valid-but-falsy top-level value (``{}``, ``[]``,
# ``0``, ``""``). BUG-9/10: a falsy-but-valid JSON document must not be silently
# skipped — only a true load failure short-circuits validation.
_LOAD_FAILED = object()

MANIFEST_ALLOWED = {
    "name",
    "description",
    "version",
    "license",
    "author",
    "homepage",
    "repository",
    "keywords",
    "skills",
    "hooks",
    "interface",
}
MANIFEST_REQUIRED = {"name", "description", "version", "skills", "hooks", "interface"}

MARKETPLACE_ALLOWED = {"name", "interface", "plugins"}
MARKETPLACE_REQUIRED = {"name", "plugins"}
MARKETPLACE_PLUGIN_ALLOWED = {"name", "source", "policy", "category"}
MARKETPLACE_PLUGIN_REQUIRED = {"name", "source", "policy", "category"}
MARKETPLACE_SOURCE_ALLOWED = {"source", "path"}
MARKETPLACE_SOURCE_REQUIRED = {"source", "path"}
MARKETPLACE_POLICY_ALLOWED = {"installation", "authentication", "products"}
MARKETPLACE_POLICY_REQUIRED = {"installation", "authentication"}
INSTALLATION_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
AUTHENTICATION_POLICIES = {"ON_INSTALL", "ON_USE"}


def _load_json(path: str, problems: list):
    """Load JSON, appending a problem and returning ``_LOAD_FAILED`` on failure.

    Returns the parsed value on success (which MAY be falsy — ``{}``, ``[]``,
    ``0``, ``""`` — and the caller must distinguish those from a load failure via
    the ``_LOAD_FAILED`` sentinel, NOT a falsy check).
    """
    if not os.path.isfile(path):
        problems.append("missing file: %s" % os.path.relpath(path, REPO_ROOT))
        return _LOAD_FAILED
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError) as exc:
        problems.append("%s: invalid JSON (%s)" % (os.path.relpath(path, REPO_ROOT), exc))
        return _LOAD_FAILED


def _check_keys(obj, allowed, required, label, problems):
    for key in obj:
        if key not in allowed:
            problems.append("%s: unexpected key '%s'" % (label, key))
    for key in required:
        if key not in obj:
            problems.append("%s: missing required key '%s'" % (label, key))


def validate_manifest(problems: list) -> None:
    """Validate the skills-and-hooks plugin manifest.

    Base dir for the manifest's internal references is its parent's parent —
    ``plugins/maungs-agentic-toolbelt/`` — so ``skills/<name>/SKILL.md`` resolves
    to ``plugins/maungs-agentic-toolbelt/skills/<name>/SKILL.md``.
    """
    path = os.path.join(REPO_ROOT, MANIFEST_REL)
    obj = _load_json(path, problems)
    if obj is _LOAD_FAILED:
        return
    if not isinstance(obj, dict):
        problems.append("manifest: top-level must be a JSON object")
        return
    _check_keys(obj, MANIFEST_ALLOWED, MANIFEST_REQUIRED, "manifest", problems)

    version = obj.get("version", "")
    if not _SEMVER.match(str(version)):
        problems.append("manifest: version '%s' is not strict semver X.Y.Z" % version)

    # Version PARITY (BUG-23): the Codex manifest version must track the Claude
    # plugin version. Read .claude-plugin/plugin.json WITHOUT polluting `problems`
    # for that file (a missing/unreadable Claude manifest just skips the parity
    # check — that file has its own CI gate).
    claude_version = None
    try:
        claude_path = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")
        with open(claude_path, "r", encoding="utf-8") as fh:
            claude_version = json.load(fh).get("version")
    except (ValueError, OSError, AttributeError):
        claude_version = None
    if version and claude_version is not None and str(version) != str(claude_version):
        problems.append(
            "manifest: version '%s' must match .claude-plugin/plugin.json version "
            "'%s' (keep parity)" % (version, claude_version)
        )

    # Codex plugins do not package custom TOML subagents. Those are installed
    # separately by install-codex.sh; skills and lifecycle hooks live here.
    if "agents" in obj:
        problems.append("manifest: must NOT carry 'agents' (installed separately)")

    # No numeric component count anywhere (decision 14).
    blob = json.dumps(obj)
    if _COUNT_RX.search(blob):
        problems.append("manifest: carries a numeric component count (must not — decision 14)")

    # Manifest base dir = the dir TWO levels up from the manifest file.
    base = os.path.dirname(os.path.dirname(path))  # plugins/maungs-agentic-toolbelt/
    skills = obj.get("skills", "")
    if skills != PINNED_SKILLS_PATH:
        problems.append(
            "manifest: 'skills' must equal '%s' (got '%s')"
            % (PINNED_SKILLS_PATH, skills)
        )
    else:
        skills_dir = os.path.normpath(os.path.join(base, skills))
        if not os.path.isdir(skills_dir):
            problems.append(
                "manifest: referenced skills directory does not exist: %s "
                "(resolved against %s)" % (skills, os.path.relpath(base, REPO_ROOT))
            )
        elif not any(
            os.path.isfile(os.path.join(skills_dir, name, "SKILL.md"))
            for name in os.listdir(skills_dir)
        ):
            problems.append("manifest: referenced skills directory contains no skills")

    hooks = obj.get("hooks", "")
    if hooks != "./hooks/hooks.json":
        problems.append(
            "manifest: 'hooks' must equal './hooks/hooks.json' (got '%s')" % hooks
        )
    else:
        hooks_path = os.path.normpath(os.path.join(base, hooks))
        if not os.path.isfile(hooks_path):
            problems.append("manifest: referenced hooks file does not exist: %s" % hooks)

    interface = obj.get("interface", {})
    if not isinstance(interface, dict):
        problems.append("manifest: 'interface' must be a JSON object")
    else:
        for required in ("displayName", "shortDescription", "longDescription",
                         "developerName", "category", "capabilities", "websiteURL"):
            if required not in interface:
                problems.append("manifest interface: missing required key '%s'" % required)


def validate_marketplace(problems: list) -> None:
    """Validate the marketplace root + pinned structured local-source hop.

    Base dir for the marketplace is the REPO ROOT (where ``.agents/`` sits). The
    plugin entry's ``source.path`` must equal the pinned
    ``./plugins/maungs-agentic-toolbelt`` and resolve from the repo root to the
    directory holding the manifest.
    """
    path = os.path.join(REPO_ROOT, MARKETPLACE_REL)
    obj = _load_json(path, problems)
    if obj is _LOAD_FAILED:
        return
    if not isinstance(obj, dict):
        problems.append("marketplace: top-level must be a JSON object")
        return
    _check_keys(obj, MARKETPLACE_ALLOWED, MARKETPLACE_REQUIRED, "marketplace", problems)

    plugins = obj.get("plugins", [])
    if not isinstance(plugins, list) or not plugins:
        problems.append("marketplace: 'plugins' must be a non-empty list")
        return

    blob = json.dumps(obj)
    if _COUNT_RX.search(blob):
        problems.append("marketplace: carries a numeric component count (must not — decision 14)")

    found_pinned = False
    for entry in plugins:
        if not isinstance(entry, dict):
            problems.append("marketplace: plugin entry must be a JSON object")
            continue
        _check_keys(
            entry,
            MARKETPLACE_PLUGIN_ALLOWED,
            MARKETPLACE_PLUGIN_REQUIRED,
            "marketplace plugin entry",
            problems,
        )
        source = entry.get("source", {})
        if not isinstance(source, dict):
            problems.append("marketplace plugin entry: 'source' must be a JSON object")
            source = {}
        else:
            _check_keys(
                source,
                MARKETPLACE_SOURCE_ALLOWED,
                MARKETPLACE_SOURCE_REQUIRED,
                "marketplace plugin source",
                problems,
            )

        policy = entry.get("policy", {})
        if not isinstance(policy, dict):
            problems.append("marketplace plugin entry: 'policy' must be a JSON object")
            policy = {}
        else:
            _check_keys(
                policy,
                MARKETPLACE_POLICY_ALLOWED,
                MARKETPLACE_POLICY_REQUIRED,
                "marketplace plugin policy",
                problems,
            )
            if policy.get("installation") not in INSTALLATION_POLICIES:
                problems.append(
                    "marketplace plugin policy: invalid installation value '%s'"
                    % policy.get("installation")
                )
            if policy.get("authentication") not in AUTHENTICATION_POLICIES:
                problems.append(
                    "marketplace plugin policy: invalid authentication value '%s'"
                    % policy.get("authentication")
                )

        if entry.get("name") == "maungs-agentic-toolbelt":
            found_pinned = True
            if source.get("source") != "local":
                problems.append(
                    "marketplace: plugin 'source.source' must equal 'local' (got '%s')"
                    % source.get("source")
                )
            source_path = source.get("path", "")
            if source_path != PINNED_SOURCE_PATH:
                problems.append(
                    "marketplace: plugin 'source.path' must equal '%s' (got '%s')"
                    % (PINNED_SOURCE_PATH, source_path)
                )
            plugin_dir = os.path.normpath(os.path.join(REPO_ROOT, source_path))
            if not os.path.isdir(plugin_dir):
                problems.append(
                    "marketplace: 'source.path' dir does not exist: %s" % source_path
                )
            else:
                manifest = os.path.join(plugin_dir, ".codex-plugin", "plugin.json")
                if not os.path.isfile(manifest):
                    problems.append(
                        "marketplace: 'source.path' dir does not contain "
                        ".codex-plugin/plugin.json: %s" % source_path
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
