#!/usr/bin/env python3
"""tools/validate_codex.py — validate clean-install Codex artifacts.

Stdlib-only validator for the complete install surface:

  * manifest + marketplace schemas and referenced paths;
  * canonical and generated component frontmatter;
  * generated ``agents/openai.yaml`` files;
  * every JSON and TOML document;
  * every shell script via ``bash -n``;
  * hook registrations and their referenced scripts.

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
import subprocess
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover - Python <3.11 compatibility
    tomllib = None

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_THIS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.emit import common  # noqa: E402

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
HOOK_EVENTS = {"UserPromptSubmit", "PreToolUse", "SessionStart", "SubagentStart"}
_HOOK_COMMAND_RX = re.compile(
    r'^bash "\$\{PLUGIN_ROOT\}/hooks/([A-Za-z0-9._-]+\.sh)"$'
)


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


def _repo_files(suffix: str):
    """Yield repo-relative files with ``suffix``, excluding Git internals."""
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for filename in sorted(filenames):
            if filename.endswith(suffix):
                path = os.path.join(dirpath, filename)
                yield os.path.relpath(path, REPO_ROOT), path


def validate_component_frontmatter(problems: list) -> None:
    """Validate the repo's deterministic YAML-frontmatter subset."""
    component_paths = [
        os.path.join(REPO_ROOT, "agents", name)
        for name in sorted(os.listdir(os.path.join(REPO_ROOT, "agents")))
        if name.endswith(".md")
    ]
    skills_root = os.path.join(REPO_ROOT, "skills")
    component_paths.extend(
        os.path.join(skills_root, name, "SKILL.md")
        for name in sorted(os.listdir(skills_root))
        if os.path.isfile(os.path.join(skills_root, name, "SKILL.md"))
    )
    generated_root = os.path.join(
        REPO_ROOT, "plugins", "maungs-agentic-toolbelt", "skills"
    )
    component_paths.extend(
        os.path.join(generated_root, name, "SKILL.md")
        for name in sorted(os.listdir(generated_root))
        if os.path.isfile(os.path.join(generated_root, name, "SKILL.md"))
    )

    for path in component_paths:
        rel = os.path.relpath(path, REPO_ROOT)
        try:
            block, _body = common.split_frontmatter(common.read_text(path))
            scalars, _tools = common.parse_frontmatter(block)
        except (OSError, ValueError) as exc:
            problems.append("%s: invalid YAML frontmatter (%s)" % (rel, exc))
            continue
        if not scalars.get("name"):
            problems.append("%s: frontmatter missing non-empty name" % rel)
        if not scalars.get("description"):
            problems.append("%s: frontmatter missing non-empty description" % rel)

        if rel.startswith("plugins/maungs-agentic-toolbelt/skills/"):
            lines = block.splitlines()
            name_line = next((line for line in lines if line.startswith("name:")), "")
            desc_line = next(
                (line for line in lines if line.startswith("description:")), ""
            )
            if not name_line.startswith('name: "') or not desc_line.startswith(
                'description: "'
            ):
                problems.append(
                    "%s: generated name/description must use quoted YAML scalars" % rel
                )


def validate_skill_metadata(problems: list) -> None:
    """Validate the exact supported schema of every generated openai.yaml."""
    metadata = [
        item
        for item in _repo_files(".yaml")
        if os.path.basename(item[1]) == "openai.yaml"
    ]
    skills_dir = os.path.join(
        REPO_ROOT, "plugins", "maungs-agentic-toolbelt", "skills"
    )
    skill_count = sum(
        os.path.isfile(os.path.join(skills_dir, name, "SKILL.md"))
        for name in os.listdir(skills_dir)
    )
    if len(metadata) != skill_count:
        problems.append(
            "plugin skill metadata count mismatch: %d openai.yaml for %d skills"
            % (len(metadata), skill_count)
        )
    expected_keys = ("display_name", "short_description", "default_prompt")
    for rel, path in metadata:
        lines = common.read_text(path).splitlines()
        if lines and lines[0].startswith("#"):
            lines = lines[1:]
        expected_count = 6
        if len(lines) != expected_count:
            problems.append(
                "%s: expected %d metadata lines, got %d"
                % (rel, expected_count, len(lines))
            )
            continue
        if lines[0] != "interface:" or lines[4] != "policy:":
            problems.append("%s: invalid interface/policy YAML structure" % rel)
            continue
        for index, key in enumerate(expected_keys, start=1):
            prefix = "  %s: " % key
            if not lines[index].startswith(prefix):
                problems.append("%s: missing metadata key '%s'" % (rel, key))
                continue
            raw = lines[index][len(prefix):]
            try:
                value = json.loads(raw)
            except ValueError as exc:
                problems.append(
                    "%s: '%s' is not a valid quoted YAML scalar (%s)"
                    % (rel, key, exc)
                )
                continue
            if not isinstance(value, str) or not value:
                problems.append("%s: '%s' must be a non-empty string" % (rel, key))
            if key == "short_description" and len(value) > 120:
                problems.append("%s: short_description exceeds 120 characters" % rel)
            if key == "default_prompt" and len(value) > 128:
                problems.append("%s: default_prompt exceeds 128 characters" % rel)
        if lines[5] != "  allow_implicit_invocation: true":
            problems.append("%s: invalid allow_implicit_invocation policy" % rel)


def validate_serialized_files(problems: list) -> None:
    """Parse every JSON/TOML file and syntax-check every shell script."""
    for rel, path in _repo_files(".json"):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                json.load(fh)
        except (OSError, ValueError) as exc:
            problems.append("%s: invalid JSON (%s)" % (rel, exc))

    if tomllib is not None:
        for rel, path in _repo_files(".toml"):
            try:
                with open(path, "rb") as fh:
                    tomllib.load(fh)
            except (OSError, ValueError) as exc:
                problems.append("%s: invalid TOML (%s)" % (rel, exc))

    for rel, path in _repo_files(".sh"):
        proc = subprocess.run(
            ["bash", "-n", path],
            capture_output=True,
            text=True,
        )
        if proc.returncode:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            problems.append(
                "%s: invalid shell syntax (%s)"
                % (rel, detail[0] if detail else "bash -n failed")
            )


def validate_hooks(problems: list) -> None:
    """Validate hook event names, command schema, and script references."""
    rel = "plugins/maungs-agentic-toolbelt/hooks/hooks.json"
    path = os.path.join(REPO_ROOT, rel)
    obj = _load_json(path, problems)
    if obj is _LOAD_FAILED:
        return
    hooks = obj.get("hooks") if isinstance(obj, dict) else None
    if not isinstance(hooks, dict) or not hooks:
        problems.append("%s: 'hooks' must be a non-empty JSON object" % rel)
        return
    unknown = sorted(set(hooks) - HOOK_EVENTS)
    if unknown:
        problems.append("%s: unsupported hook events: %s" % (rel, ", ".join(unknown)))

    referenced = set()
    for event, groups in hooks.items():
        if not isinstance(groups, list) or not groups:
            problems.append("%s: event '%s' must contain hook groups" % (rel, event))
            continue
        for group in groups:
            entries = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(entries, list) or not entries:
                problems.append("%s: event '%s' has an invalid hook group" % (rel, event))
                continue
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("type") != "command":
                    problems.append("%s: event '%s' hook must be a command" % (rel, event))
                    continue
                match = _HOOK_COMMAND_RX.fullmatch(str(entry.get("command", "")))
                if not match:
                    problems.append(
                        "%s: event '%s' has an invalid plugin-relative command"
                        % (rel, event)
                    )
                    continue
                script = match.group(1)
                referenced.add(script)
                script_path = os.path.join(os.path.dirname(path), script)
                if not os.path.isfile(script_path):
                    problems.append("%s: referenced hook script missing: %s" % (rel, script))
                timeout = entry.get("timeout")
                if not isinstance(timeout, int) or timeout <= 0:
                    problems.append(
                        "%s: event '%s' timeout must be a positive integer"
                        % (rel, event)
                    )

    hook_dir = os.path.dirname(path)
    executable_hooks = {
        name
        for name in os.listdir(hook_dir)
        if name.endswith(".sh") and name != "lib-telemetry.sh"
    }
    if referenced != executable_hooks:
        problems.append(
            "%s: registered hook scripts differ from packaged hooks "
            "(missing=%s, unregistered=%s)"
            % (
                rel,
                sorted(referenced - executable_hooks),
                sorted(executable_hooks - referenced),
            )
        )


def main(argv=None) -> int:
    problems: list = []
    validate_manifest(problems)
    validate_marketplace(problems)
    validate_component_frontmatter(problems)
    validate_skill_metadata(problems)
    validate_serialized_files(problems)
    validate_hooks(problems)
    if problems:
        print("validate_codex: FAIL", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print(
        "validate_codex: OK — wrappers, YAML/frontmatter, JSON, TOML, shell, "
        "and hook references are well-formed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
