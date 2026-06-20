#!/usr/bin/env python3
"""Stdlib test suite for the Codex generator (tools/build.py + emitters + transforms).

Plain Python 3 stdlib (no pytest), matching the repo's existing test style. Run:

    python3 tests/test_codex_build.py

Covers (per docs/plans/6_codex-port.md "Test plan"):
  * committed-tree drift check (the real CI mode) + two symmetric negatives
    (canonical-ahead / generated-ahead);
  * generator determinism (two-run byte-identical, no host path/timestamp,
    shuffled readdir, CRLF + trailing-newline normalization);
  * validate_codex (well-formed manifest + marketplace, pinned source hop);
  * transforms unit coverage (claude->codex mcp, AskUserQuestion gate prose,
    server-agnostic mcp prose rewrite incl. context7, ToolSearch neutralization,
    /skill left-boundary, with-arguments, BOTH tools serializations,
    mcp_servers enumeration, hook-body rules, attribution broadening,
    router additionalContext+stdout+anti-autonomy prefix, lib-telemetry codex
    path + override);
  * gate-semantics preservation (developer/architect commit/push/PR + architect
    plan-approval + orchestrator merge + handoff + migration-planner; product-owner
    is a design question, not a gate).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_THIS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.emit import common  # noqa: E402
from tools.emit import target_codex  # noqa: E402
from tools.emit import target_claude  # noqa: E402
from tools import transforms  # noqa: E402

FAILURES = []
PASSES = 0


def check(name, cond, detail=""):
    global PASSES
    if cond:
        PASSES += 1
        print("  ok   %s" % name)
    else:
        FAILURES.append((name, detail))
        print("  FAIL %s%s" % (name, (" — " + detail) if detail else ""))


def run_build(args, cwd=REPO_ROOT):
    """Run tools/build.py with args; return (returncode, stdout+stderr)."""
    proc = subprocess.run(
        [sys.executable, os.path.join("tools", "build.py")] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def copy_repo_subset(dst):
    """Copy the canonical source + generated tree + tools into a temp repo copy."""
    for sub in (
        "agents",
        "skills",
        "hooks",
        "tools",
        "codex-agents",
        "codex-hooks",
        os.path.join("plugins"),
        ".agents",
    ):
        src = os.path.join(REPO_ROOT, sub)
        if os.path.exists(src):
            shutil.copytree(src, os.path.join(dst, sub))


# ---------------------------------------------------------------------------
# Drift checks
# ---------------------------------------------------------------------------

def test_committed_drift():
    print("\n[committed-tree drift check]")
    rc, out = run_build(["--target", "codex", "--check"])
    check("committed tree --check exits 0", rc == 0, out.strip())


def test_drift_negative_canonical_ahead():
    print("\n[negative (a): canonical edited, generated stale -> AC-5]")
    tmp = tempfile.mkdtemp()
    try:
        copy_repo_subset(tmp)
        # Mutate a canonical agent body; leave the generated tree untouched.
        canon = os.path.join(tmp, "agents", "developer.md")
        with open(canon, "a", encoding="utf-8") as fh:
            fh.write("\n\nSENTINEL_CANONICAL_DRIFT_MARKER\n")
        rc, out = run_build(["--target", "codex", "--check"], cwd=tmp)
        check("canonical-ahead --check exits non-zero", rc != 0, out.strip()[:200])
        check("regenerate message present", "regenerate" in out.lower(), out.strip()[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_drift_negative_generated_ahead():
    print("\n[negative (b): generated edited, canonical untouched -> AC-4]")
    tmp = tempfile.mkdtemp()
    try:
        copy_repo_subset(tmp)
        gen = os.path.join(tmp, "codex-agents", "developer.toml")
        with open(gen, "a", encoding="utf-8") as fh:
            fh.write("\n# HAND_EDITED_GENERATED_ARTIFACT\n")
        rc, out = run_build(["--target", "codex", "--check"], cwd=tmp)
        check("generated-ahead --check exits non-zero", rc != 0, out.strip()[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_determinism_two_runs():
    print("\n[determinism: two runs byte-identical]")
    a = target_codex.build_artifacts(REPO_ROOT)
    b = target_codex.build_artifacts(REPO_ROOT)
    check("two builds same key set", set(a) == set(b))
    diffs = [k for k in a if a[k] != b[k]]
    check("two builds byte-identical content", not diffs, "differ: %s" % diffs[:3])


def test_determinism_no_host_path_or_timestamp():
    print("\n[determinism: no host path / timestamp in any emitted artifact]")
    a = target_codex.build_artifacts(REPO_ROOT)
    host_re = re.compile(r"/Users/[A-Za-z]")
    # A *captured* timestamp value (a real date emitted at build time). The
    # epoch literal (1970-...) and the strftime format spec (%Y-...) in the
    # canonical lib-telemetry.sh are CODE, not captured values, so they are
    # excluded — they are byte-stable across runs and carry no build-time data.
    ts_re = re.compile(r"\b(19[7-9]\d|20\d\d)-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def _has_real_timestamp(text):
        for m in ts_re.finditer(text):
            if m.group(0).startswith("1970-01-01T00:00:00"):
                continue  # epoch fallback literal in lib-telemetry.sh
            return True
        return False

    bad_host = [k for k, v in a.items() if host_re.search(v)]
    bad_ts = [k for k, v in a.items() if _has_real_timestamp(v)]
    check("no emitted artifact carries a host path", not bad_host, str(bad_host[:3]))
    check("no emitted artifact carries a literal timestamp", not bad_ts, str(bad_ts[:3]))


def test_determinism_shuffled_readdir():
    print("\n[determinism: shuffled readdir order -> identical output]")
    real_listdir = os.listdir

    def shuffled_listdir(path):
        items = list(real_listdir(path))
        return list(reversed(items))  # deterministic non-sorted order

    baseline = target_codex.build_artifacts(REPO_ROOT)
    os.listdir = shuffled_listdir
    try:
        shuffled = target_codex.build_artifacts(REPO_ROOT)
    finally:
        os.listdir = real_listdir
    check("shuffled readdir same key set", set(baseline) == set(shuffled))
    diffs = [k for k in baseline if baseline[k] != shuffled[k]]
    check("shuffled readdir byte-identical", not diffs, str(diffs[:3]))


def test_determinism_newline_normalization():
    print("\n[determinism: CRLF + trailing-newline source -> identical artifact]")
    tmp = tempfile.mkdtemp()
    try:
        copy_repo_subset(tmp)
        # Baseline emit from the LF source.
        baseline = target_codex.build_artifacts(tmp)
        # Re-save one canonical agent with CRLF endings + a doubled trailing newline.
        canon = os.path.join(tmp, "agents", "developer.md")
        with open(canon, "r", encoding="utf-8") as fh:
            text = fh.read()
        crlf = text.replace("\n", "\r\n") + "\r\n\r\n"
        with open(canon, "w", encoding="utf-8", newline="") as fh:
            fh.write(crlf)
        mutated = target_codex.build_artifacts(tmp)
        rel = "codex-agents/developer.toml"
        check(
            "CRLF + doubled-trailing-newline source emits byte-identical TOML",
            baseline[rel] == mutated[rel],
        )
        check("no \\r survives in emitted artifact", "\r" not in mutated[rel])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# validate_codex
# ---------------------------------------------------------------------------

def test_validate_codex():
    print("\n[validate_codex: manifest + marketplace well-formed]")
    proc = subprocess.run(
        [sys.executable, os.path.join("tools", "validate_codex.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    check("validate_codex exits 0", proc.returncode == 0, (proc.stdout + proc.stderr).strip())


def test_manifest_lists_every_generated_skill():
    print("\n[manifest: .codex-plugin/plugin.json lists EVERY generated skill (AC-2 completeness)]")
    import json
    base = os.path.join(REPO_ROOT, "plugins", "maungs-agentic-toolbelt")
    with open(os.path.join(base, ".codex-plugin", "plugin.json"), encoding="utf-8") as fh:
        referenced = set(json.load(fh).get("skills", []))
    skills_dir = os.path.join(base, "skills")
    generated = set(
        "skills/%s/SKILL.md" % n
        for n in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, n, "SKILL.md"))
    )
    canonical = {c.name for c in common.load_skills(REPO_ROOT)}
    # The skills LIST is hand-maintained but the FOLDERS are generated — a new
    # canonical skill that is regenerated but not added to the manifest would be
    # silently dropped from the Codex marketplace track (the bug this guards).
    check("manifest references EVERY generated skill (no silent drop)",
          referenced == generated,
          "missing=%s stray=%s" % (sorted(generated - referenced), sorted(referenced - generated)))
    check("manifest skill count == canonical skill count",
          len(referenced) == len(canonical),
          "manifest=%d canonical=%d" % (len(referenced), len(canonical)))
    for s in ("overnight", "todo"):
        check("manifest lists %s" % s, "skills/%s/SKILL.md" % s in referenced)


# ---------------------------------------------------------------------------
# Transforms unit coverage
# ---------------------------------------------------------------------------

def test_transforms_claude_mcp_cli():
    print("\n[transforms: claude mcp -> codex mcp]")
    out = transforms.rewrite_claude_mcp_cli("run `claude mcp list` then `claude mcp add github`")
    check("claude mcp list -> codex mcp list", "codex mcp list" in out and "claude mcp" not in out)
    check("claude mcp add -> codex mcp add", "codex mcp add" in out)


def test_transforms_mcp_prose_server_agnostic():
    print("\n[transforms: server-agnostic mcp prose rewrite]")
    out = transforms.rewrite_mcp_prose("read via `mcp__github__issue_read` and mcp__context7__* docs")
    check("mcp__github__ prose -> the github MCP server", "the `github` MCP server" in out)
    check("mcp__context7__* prose -> the context7 MCP server", "the context7 MCP server" in out)
    check("no stale mcp__ token survives", "mcp__" not in out, out)


def test_transforms_context7_emitted_body():
    print("\n[transforms: code-translator emitted body — context7 prose + ToolSearch neutralized]")
    comps = {c.name: c for c in common.load_agents(REPO_ROOT)}
    ct = comps["code-translator"]
    body = transforms.transform_body(ct.body, ct.name)
    check("no mcp__context7__ prose survives in emitted body", "mcp__context7__" not in body, body[:120])
    check("ToolSearch token neutralized in emitted body", "ToolSearch" not in body)


def test_transforms_skill_left_boundary():
    print("\n[transforms: /skill -> @skill left-boundary]")
    text = (
        "run /orchestrator now\n"
        "see skills/orchestrator/SKILL.md and developer/orchestrator and "
        "@playwright/mcp@latest\n"
    )
    out = transforms.rewrite_skill_invocations(text)
    check("bare /orchestrator (whitespace-left) -> @orchestrator", "run @orchestrator now" in out)
    check("skills/orchestrator/SKILL.md left untouched", "skills/orchestrator/SKILL.md" in out)
    check("developer/orchestrator left untouched", "developer/orchestrator" in out)
    check("@playwright/mcp@latest left untouched", "@playwright/mcp@latest" in out)


def test_transforms_skill_backtick_and_paren_boundary():
    print("\n[transforms: /skill -> @skill backtick + paren left-boundary (AC-3)]")
    # Backtick-wrapped invocations are the dominant surviving form in generated
    # SKILL/agent bodies — the rule must reach them, not just bare `/orchestrator`.
    cases_rewrite = {
        "`/orchestrator`": "`@orchestrator`",
        "`/wiki-generator <topic>`": "`@wiki-generator <topic>`",
        "(/wiki-generator now)": "(@wiki-generator now)",
        "`/orchestrator`.": "`@orchestrator`.",
        "`/toolbelt metrics`": "`@toolbelt metrics`",
        # double-quote left boundary — the mermaid node-label form (a quoted
        # invocation in a flow diagram) and flush-quoted invocations.
        'A["/overnight [repo] [flags]"]': 'A["@overnight [repo] [flags]"]',
        '"/orchestrator"': '"@orchestrator"',
    }
    for src, want in cases_rewrite.items():
        out = transforms.rewrite_skill_invocations(src)
        check("'%s' -> '%s'" % (src, want), out == want, out)
    # A PATH component must stay byte-for-byte even when backtick- or quote-wrapped:
    # the delimiter precedes `skills`, not the `/orchestrator`, so it must NOT match.
    cases_unchanged = [
        "`skills/orchestrator/SKILL.md`",
        '"/orchestrator/SKILL.md"',  # quoted PATH -> trailing '/' fails right boundary
        "`/handoffs`",       # trailing 's' -> longer slug, right boundary fails
        "`/chores`",         # trailing 's'
        '"/chores"',         # quoted, trailing 's'
        "bin/toolbelt-metrics",  # trailing '-' -> compound name
    ]
    for src in cases_unchanged:
        out = transforms.rewrite_skill_invocations(src)
        check("'%s' left intact" % src, out == src, out)


def test_generated_tree_no_slash_skill_invocation():
    print("\n[AC-3: zero opening-delimiter `/<skill>` invocations survive in the generated tree]")
    artifacts = target_codex.build_artifacts(REPO_ROOT)
    names = "|".join(re.escape(n) for n in transforms.SKILL_NAMES)
    # Any /<skill> preceded by an OPENING delimiter (line-start / whitespace /
    # backtick / open-paren / double-quote) with the strict right boundary — bare,
    # backtick-, paren-, AND quote-wrapped (the mermaid node-label form) all count
    # as a surviving slash invocation. Scans the WHOLE generated tree (agent TOMLs,
    # skill SKILL.md bodies, and the hooks), not just toml/SKILL.md.
    inv = re.compile(r'(^|[\s`("])/(' + names + r')(?=[\s`.,;:!?)\]"]|$)', re.MULTILINE)
    offenders = []
    for rel, content in artifacts.items():
        if rel.startswith("codex-agents/") or rel.startswith("codex-hooks/") or "/skills/" in rel:
            for m in inv.finditer(content):
                offenders.append("%s: %s" % (rel, m.group(0).strip()))
    check("no opening-delimiter `/<skill>` invocation in any generated artifact",
          not offenders, "found: %s" % offenders[:5])
    # And the @mention form IS present (skills still surface, Codex-correct).
    joined = "\n".join(artifacts.values())
    check("backtick `@orchestrator` present in emitted tree", "`@orchestrator`" in joined)


def test_transforms_skill_with_arguments():
    print("\n[transforms: /skill with trailing args rewrites token only]")
    cases = {
        "/orchestrator <topic>": "@orchestrator <topic>",
        "/toolbelt metrics": "@toolbelt metrics",
        "/agentic-onboard --deep --target all": "@agentic-onboard --deep --target all",
    }
    for src, want in cases.items():
        out = transforms.rewrite_skill_invocations(src)
        check("'%s' -> '%s'" % (src, want), out == want, out)


def test_transforms_dynamic_skill_names_new_skills():
    print("\n[transforms: SKILL_NAMES is dynamic — new skills (overnight, todo) rewrite]")
    # SKILL_NAMES is DERIVED from the canonical skills/ dir (not a hand-maintained
    # list), so skills added to main AFTER the Codex generator was written
    # (overnight, todo) flow through the /skill->@skill rewrite automatically.
    # This is the regression guard against the old hardcoded 9-item list — without
    # the dynamic fix, /overnight and /todo would survive un-rewritten as invalid
    # slash-forms on Codex (AC-3 violation).
    fs_skills = {c.name for c in common.load_skills(REPO_ROOT)}
    check("SKILL_NAMES == canonical skills/ enumeration (single source, no drift)",
          set(transforms.SKILL_NAMES) == fs_skills,
          "SKILL_NAMES=%s fs=%s" % (sorted(transforms.SKILL_NAMES), sorted(fs_skills)))
    for new_skill in ("overnight", "todo"):
        check("%s present in canonical skills/" % new_skill, new_skill in fs_skills)
        check("%s present in SKILL_NAMES (picked up dynamically)" % new_skill,
              new_skill in transforms.SKILL_NAMES)
        # Bare, backtick-wrapped, and with-args forms all rewrite the token only.
        check("bare /%s -> @%s" % (new_skill, new_skill),
              transforms.rewrite_skill_invocations("run /%s now" % new_skill)
              == "run @%s now" % new_skill)
        check("backtick `/%s` -> `@%s`" % (new_skill, new_skill),
              transforms.rewrite_skill_invocations("`/%s`" % new_skill)
              == "`@%s`" % new_skill)
        check("with-args /%s --flag -> @%s --flag" % (new_skill, new_skill),
              transforms.rewrite_skill_invocations("/%s --status" % new_skill)
              == "@%s --status" % new_skill)


def test_parser_both_tools_serializations():
    print("\n[common: tools parser handles BOTH serializations]")
    inline_fm = "name: x\ntools: Read, Grep, Bash, mcp__context7__resolve-library-id, mcp__context7__get-library-docs"
    block_fm = "name: x\ntools:\n  - Read\n  - Grep\n  - Bash\n  - mcp__context7__resolve-library-id\n  - mcp__context7__get-library-docs"
    _, inline_tools = common.parse_frontmatter(inline_fm)
    _, block_tools = common.parse_frontmatter(block_fm)
    want = ["Read", "Grep", "Bash", "mcp__context7__resolve-library-id", "mcp__context7__get-library-docs"]
    check("inline form parses to tool list", inline_tools == want, str(inline_tools))
    check("block-list form parses to same list", block_tools == want, str(block_tools))


def test_mcp_servers_enumeration():
    print("\n[emitter: mcp_servers enumeration]")
    comps = {c.name: c for c in common.load_agents(REPO_ROOT)}
    # code-translator (inline form) -> ["context7"]
    ct_toml = target_codex.render_agent_toml(comps["code-translator"])
    check("code-translator carries mcp_servers = [\"context7\"]",
          'mcp_servers = ["context7"]' in ct_toml, ct_toml.split("\n")[6] if len(ct_toml.split("\n")) > 6 else "")
    # an agent with NO mcp tools omits mcp_servers (context-auditor declares none)
    ca_servers = common.derive_mcp_servers(comps["context-auditor"].tools)
    ca_toml = target_codex.render_agent_toml(comps["context-auditor"])
    check("context-auditor (no mcp tools) omits mcp_servers", ca_servers == [] and "mcp_servers" not in ca_toml)
    # developer DOES declare github + playwright mcp tools -> carries both.
    dev_servers = common.derive_mcp_servers(comps["developer"].tools)
    check("developer carries github + playwright", dev_servers == ["github", "playwright"], str(dev_servers))
    # a github+playwright agent carries both (synthetic)
    both = common.derive_mcp_servers(["Read", "mcp__github__x", "mcp__playwright__y"])
    check("github+playwright -> both servers sorted", both == ["github", "playwright"], str(both))


def test_sandbox_mode_derivation():
    print("\n[emitter: sandbox_mode from tools allowlist]")
    comps = {c.name: c for c in common.load_agents(REPO_ROOT)}
    check("developer (Edit/Write) -> workspace-write",
          common.derive_sandbox_mode(comps["developer"].tools) == "workspace-write")
    check("pr-reviewer (no Edit/Write) -> read-only",
          common.derive_sandbox_mode(comps["pr-reviewer"].tools) == "read-only")


def test_agent_no_triple_quote():
    print("\n[emitter: every agent body emits as a TOML literal (no embedded ''')]")
    bad = []
    for comp in common.load_agents(REPO_ROOT):
        try:
            target_codex.render_agent_toml(comp)
        except ValueError as exc:
            bad.append("%s: %s" % (comp.name, exc))
    check("all 16 agent bodies render without a ''' clash", not bad, str(bad[:2]))


def test_hook_usage_tracker():
    print("\n[hook: usage-tracker CLAUDE_PLUGIN_ROOT rewritten, skill fallback agent-only]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("usage-tracker.sh", bodies["usage-tracker.sh"])
    check("CLAUDE_PLUGIN_ROOT gone", "CLAUDE_PLUGIN_ROOT" not in out)
    check("agent membership checks .toml", "agents/${slug}.toml" in out)
    check("bare-slug skill filesystem fallback dropped", "skills/${slug}" not in out)


def test_hook_pretooluse_guard():
    print("\n[hook: pretooluse-guard broadened attribution + fail-open-to-ask]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("pretooluse-guard.sh", bodies["pretooluse-guard.sh"])
    check("attribution branch broadened beyond Claude (matches copilot/codex/gpt)",
          "copilot" in out and "codex" in out and "gpt" in out)
    check("fails open to 'ask' on no-jq", 'decision":"ask"' in out, out[:120])
    # Functional: a non-Claude Co-Authored-By trailer is denied.
    tmp = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
    tmp.write(out)
    tmp.close()
    try:
        payload = '{"tool_name":"Bash","tool_input":{"command":"git commit -m \\"x\\n\\nCo-Authored-By: Copilot <x@github.com>\\""}}'
        proc = subprocess.run(["bash", tmp.name], input=payload, capture_output=True, text=True)
        check("generated guard DENIES a non-Claude (Copilot) attribution",
              '"permissionDecision": "deny"' in proc.stdout, proc.stdout[:120])
    finally:
        os.unlink(tmp.name)


def test_hook_pretooluse_guard_attribution_wholeword():
    print("\n[hook: guard attribution denylist — whole-word, no name false-positive]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("pretooluse-guard.sh", bodies["pretooluse-guard.sh"])
    tmp = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
    tmp.write(out)
    tmp.close()

    def run_commit(trailer):
        # Build a git-commit Bash payload carrying the trailer; assert the guard's
        # decision. JSON-escape the message so the payload stays valid.
        import json
        msg = "feat: thing\n\n" + trailer
        cmd = 'git commit -m %s' % json.dumps(msg)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        proc = subprocess.run(["bash", tmp.name], input=payload, capture_output=True, text=True)
        return '"permissionDecision": "deny"' in proc.stdout

    try:
        # (b) false-ALLOW fix: an AI tool NOT in first position is now DENIED.
        check("DENIES 'Co-Authored-By: GitHub Copilot' (not first position)",
              run_commit("Co-Authored-By: GitHub Copilot <x@github.com>"))
        # Baseline: the literal Claude trailer still DENIED.
        check("DENIES 'Co-Authored-By: Claude'",
              run_commit("Co-Authored-By: Claude <noreply@anthropic.com>"))
        # (a) false-DENY fix: a human whose NAME starts with an AI token is ALLOWED.
        check("ALLOWS human 'Co-Authored-By: Aishwarya Patel' (name starts 'Ai')",
              not run_commit("Co-Authored-By: Aishwarya Patel <a@x.com>"))
        # And another ordinary human name beginning with an AI-token prefix.
        check("ALLOWS human 'Co-Authored-By: Gemma Liu' (name starts 'Gem')",
              not run_commit("Co-Authored-By: Gemma Liu <g@x.com>"))
        # name-scoped match ([^<]*): an AI token appearing ONLY in the email DOMAIN
        # (the name is a real human) is ALLOWED — a real attribution trailer carries
        # the tool in the NAME, not merely the address.
        check("ALLOWS 'Co-Authored-By: Jane Smith <jane@openai.com>' (token only in email)",
              not run_commit("Co-Authored-By: Jane Smith <jane@openai.com>"))
        # ...but the AI tool IN THE NAME is still DENIED even with a benign email.
        check("DENIES 'Co-Authored-By: Claude <user@gmail.com>' (tool in name)",
              run_commit("Co-Authored-By: Claude <user@gmail.com>"))
    finally:
        os.unlink(tmp.name)


def test_hook_router():
    print("\n[hook: router emits additionalContext + stdout + anti-autonomy prefix]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("toolbelt-router.sh", bodies["toolbelt-router.sh"])
    check("additionalContext envelope present", "additionalContext" in out)
    check("stdout fallback always emitted (printf after jq, no else)",
          "printf '%s\\n' \"$3\"\n  exit 0" in out)
    check("anti-autonomy PREFIX guard survives",
          "do NOT auto-run workflows that commit/push/open PRs without confirmation" in out)


def test_hook_router_skill_suggestions_at_mention():
    print("\n[hook: router /skill suggestions rewritten to @skill (decision 16 router exception)]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("toolbelt-router.sh", bodies["toolbelt-router.sh"])
    # No BARE /<skill> suggestion (whitespace/line-start prefixed) survives — those
    # are invalid on Codex (no slash layer; skills are @mention/model-triggered).
    bare_slash = re.compile(
        r"(^|\s)/(" + "|".join(re.escape(n) for n in transforms.SKILL_NAMES) + r")\b",
        re.MULTILINE,
    )
    leftover = bare_slash.findall(out)
    check("no bare /<skill> suggestion left in generated router",
          not leftover, "found bare slash skills: %s" % [s for _, s in leftover][:5])
    # The @mention forms ARE present (suggestions still surface, Codex-correct).
    check("router suggests @orchestrator (not /orchestrator)",
          re.search(r"(^|\s)@orchestrator\b", out) is not None)
    check("router suggests @agentic-onboard (not /agentic-onboard)",
          "@agentic-onboard" in out)
    # Path tokens + non-skill slashes are NOT mangled by the rewrite.
    check("docs/wiki/ path intact (not mangled to docs@wiki)",
          "docs@wiki" not in out and "docs/wiki/" in out)
    check("non-skill 'commit/push' slash intact",
          "commit/push" in out)


def test_hook_lib_telemetry():
    print("\n[hook: lib-telemetry default path -> ~/.codex, override preserved]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("lib-telemetry.sh", bodies["lib-telemetry.sh"])
    check("default usage-log under ~/.codex",
          "${MAUNGS_TOOLBELT_LOG:-${HOME}/.codex/maungs-toolbelt/usage.jsonl}" in out)
    check("no ~/.claude default remains in writer", "${HOME}/.claude/maungs-toolbelt" not in out)
    check("MAUNGS_TOOLBELT_LOG override preserved", "MAUNGS_TOOLBELT_LOG:-" in out)


def test_hook_sessionstart_loader_skill_invocation_at_mention():
    print("\n[hook: sessionstart-loader skill nudges -> @mention (AC-3: /agentic-onboard + /todo), CLAUDE.md filename + /todos/ path kept]")
    bodies = common.load_hook_bodies(REPO_ROOT)
    out = transforms.transform_hook_body("sessionstart-loader.sh", bodies["sessionstart-loader.sh"])
    check("agentic-onboard nudge rewritten to @agentic-onboard", "@agentic-onboard" in out)
    check("todo backlog nudge rewritten to @todo", "@todo" in out)
    # No BARE/wrapped /<skill> slash-form invocation survives for ANY canonical
    # skill (whitespace/line-start/backtick/paren left boundary): invalid on Codex
    # (no slash layer; violates AC-3). Anchored to the dynamic SKILL_NAMES so a new
    # loader nudge (e.g. /todo, added on main) is covered with no per-skill edit.
    names = "|".join(re.escape(n) for n in transforms.SKILL_NAMES)
    bare_slash = re.compile(r"(^|[\s`(])/(" + names + r")(?=[\s`.,;:!?)\]]|$)", re.MULTILINE)
    leftover = [m.group(0).strip() for m in bare_slash.finditer(out)]
    check("no bare/wrapped /<skill> invocation remains (incl. /todo)",
          not leftover, "found: %s" % leftover[:5])
    # The CLAUDE.md FILENAME reference is intentionally preserved (informational
    # filename the user looks for — decision 16's filename disposition).
    check("CLAUDE.md filename reference preserved (filename, not invocation)",
          "CLAUDE.md" in out, out[:80])
    # The /todos/ STORAGE PATH must NOT be mangled to @todos (trailing 's' -> not a
    # skill invocation; the left-boundary rule leaves the path token intact).
    check("/todos/ storage path preserved (not rewritten to @todos)",
          "todos/" in out and "@todos" not in out)


def test_neutralization_claude_md():
    print("\n[transforms: layer-1 CLAUDE.md neutralization (agent/skill bodies)]")
    out = transforms.neutralize_body("read CLAUDE.md and restart Claude Code")
    check("CLAUDE.md -> AGENTS.md / CLAUDE.md", "AGENTS.md / CLAUDE.md" in out)
    check("restart Claude Code -> restart your agent", "restart your agent" in out)
    # Idempotent.
    check("neutralization idempotent", transforms.neutralize_body(out) == out)


# ---------------------------------------------------------------------------
# Gate-semantics preservation (AC-8)
# ---------------------------------------------------------------------------

_WAIT_RE = re.compile(r"wait for an explicit", re.IGNORECASE)


def _emitted_agent_body(name):
    comps = {c.name: c for c in common.load_agents(REPO_ROOT)}
    return transforms.transform_body(comps[name].body, name)


def _emitted_skill_body(name):
    comps = {c.name: c for c in common.load_skills(REPO_ROOT)}
    return transforms.transform_body(comps[name].body, name)


def test_gate_developer():
    print("\n[gate: developer commit/push points still block]")
    body = _emitted_agent_body("developer")
    check("AskUserQuestion literal gone from developer", "AskUserQuestion" not in body)
    # The commit gate line and push gate line each carry a wait imperative.
    check("commit-gate line carries wait imperative",
          'Commit these changes' in body and _WAIT_RE.search(body) is not None)
    check("push-gate line carries wait imperative", 'Push commit' in body)
    # count: at least the two numbered gate steps carry the wait phrase
    check("multiple wait-for-confirmation instructions present",
          len(_WAIT_RE.findall(body)) >= 2, str(len(_WAIT_RE.findall(body))))


def test_gate_architect_plan_approval():
    print("\n[gate: architect plan-approval gate (distinct) + commit/push]")
    body = _emitted_agent_body("architect")
    check("AskUserQuestion literal gone from architect", "AskUserQuestion" not in body)
    # The plan-approval site ("Show the plan summary ...") still has a wait/block.
    idx = body.find("Show the plan summary")
    check("plan-summary site present", idx != -1)
    window = body[idx: idx + 400]
    check("plan-approval gate carries wait/block instruction",
          _WAIT_RE.search(window) is not None, window[:160])
    # commit gate + push gate still block
    check("architect commit gate wait imperative", "Wait for an explicit \"yes commit.\"" in body or "yes commit" in body)
    check("architect push gate wait imperative", "yes push" in body)


def test_gate_orchestrator_merge():
    print("\n[gate: orchestrator merge gate (Step 11 + 11b) survives]")
    body = _emitted_skill_body("orchestrator")
    check("AskUserQuestion literal gone from orchestrator", "AskUserQuestion" not in body)
    idx11 = body.find("Step 11 — Human review gate")
    check("Step 11 present", idx11 != -1)
    window = body[idx11: idx11 + 600]
    check("merge gate carries wait/block instruction",
          _WAIT_RE.search(window) is not None, window[:160])


def test_gate_handoff_and_migration():
    print("\n[gate: handoff write-gate + migration-planner handoff-gate survive]")
    h = _emitted_skill_body("handoff")
    check("handoff AskUserQuestion gone", "AskUserQuestion" not in h)
    check("handoff still says do NOT Write until approved",
          "Do NOT call `Write` until the user has explicitly approved" in h)
    check("handoff carries wait/block instruction", _WAIT_RE.search(h) is not None)
    m = _emitted_skill_body("migration-planner")
    check("migration-planner AskUserQuestion gone", "AskUserQuestion" not in m)
    check("migration-planner still requires an explicit pick", "Require an explicit pick" in m)
    check("migration-planner carries wait/block instruction", _WAIT_RE.search(m) is not None)


def test_gate_product_owner_is_design_not_gate():
    print("\n[gate: product-owner scope-clarification is a DESIGN question, not a gate]")
    body = _emitted_agent_body("product-owner")
    check("product-owner AskUserQuestion gone", "AskUserQuestion" not in body)
    check("product-owner uses plain 'ask the user in chat' (no fabricated wait-gate)",
          "ask the user in chat" in body and not _WAIT_RE.search(body),
          "wait phrase wrongly injected" if _WAIT_RE.search(body) else "")


def main():
    tests = [
        test_committed_drift,
        test_drift_negative_canonical_ahead,
        test_drift_negative_generated_ahead,
        test_determinism_two_runs,
        test_determinism_no_host_path_or_timestamp,
        test_determinism_shuffled_readdir,
        test_determinism_newline_normalization,
        test_validate_codex,
        test_manifest_lists_every_generated_skill,
        test_transforms_claude_mcp_cli,
        test_transforms_mcp_prose_server_agnostic,
        test_transforms_context7_emitted_body,
        test_transforms_skill_left_boundary,
        test_transforms_skill_backtick_and_paren_boundary,
        test_generated_tree_no_slash_skill_invocation,
        test_transforms_skill_with_arguments,
        test_transforms_dynamic_skill_names_new_skills,
        test_parser_both_tools_serializations,
        test_mcp_servers_enumeration,
        test_sandbox_mode_derivation,
        test_agent_no_triple_quote,
        test_hook_usage_tracker,
        test_hook_pretooluse_guard,
        test_hook_pretooluse_guard_attribution_wholeword,
        test_hook_router,
        test_hook_router_skill_suggestions_at_mention,
        test_hook_lib_telemetry,
        test_hook_sessionstart_loader_skill_invocation_at_mention,
        test_neutralization_claude_md,
        test_gate_developer,
        test_gate_architect_plan_approval,
        test_gate_orchestrator_merge,
        test_gate_handoff_and_migration,
        test_gate_product_owner_is_design_not_gate,
    ]
    for t in tests:
        t()
    print("\n" + "=" * 60)
    total = PASSES + len(FAILURES)
    print("TOTAL: %d/%d checks passed" % (PASSES, total))
    if FAILURES:
        print("FAILURES:")
        for name, detail in FAILURES:
            print("  - %s%s" % (name, (": " + detail) if detail else ""))
        return 1
    print("ALL GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
