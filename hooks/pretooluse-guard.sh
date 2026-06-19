#!/usr/bin/env bash
#
# pretooluse-guard.sh — PreToolUse hook for Maungs-agentic-toolbelt.
#
# Turns the toolbelt's cardinal rules into a STRUCTURAL guardrail: it inspects
# Bash commands before they run and DENIES the clearly-dangerous ones that the
# agents are forbidden to do. Everything else passes through untouched (it does
# NOT auto-approve anything — denied-or-defer only, so the normal permission
# flow still applies to ordinary commands).
#
# Blocks: git add -A/--all/.   ·   git push --force (use --force-with-lease)
#         --no-verify (hook bypass)   ·   catastrophic rm -rf (/ ~ $HOME *)
#         AI-attribution in a commit message (Co-Authored-By: Claude / "Generated with Claude")
#
# Safety: fail-OPEN — any parse error or missing jq exits 0 (allows), so the
# guard can never wedge the workflow. Disable entirely with:
#   export MAUNGS_TOOLBELT_GUARD=off

[ "${MAUNGS_TOOLBELT_GUARD:-on}" = "off" ] && exit 0
input="$(cat 2>/dev/null)"; [ -z "$input" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0   # no jq -> cannot parse safely -> allow

tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)"
[ "$tool" = "Bash" ] || exit 0            # only guard shell commands
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
has() { printf '%s' "$cmd" | grep -qE -- "$1"; }

# 1) bulk git add
if has 'git[[:space:]]+add[[:space:]]+(-A\b|--all\b|\.([[:space:]]|$)|-- \.)'; then
  deny "Toolbelt cardinal rule: do not 'git add -A/--all/.'. Stage the specific paths you changed instead (e.g. 'git add path/to/file'). Disable the guard with MAUNGS_TOOLBELT_GUARD=off if you really need this."
fi

# 2) force push without lease
if has 'git([[:space:]]|.)*push' && has '(--force([[:space:]=]|$)|[[:space:]]-f([[:space:]]|$))' && ! has 'force-with-lease'; then
  deny "Toolbelt cardinal rule: no 'git push --force'. Use '--force-with-lease', which refuses to clobber commits you haven't seen. (MAUNGS_TOOLBELT_GUARD=off to override.)"
fi

# 3) hook-bypass
if has '--no-verify\b'; then
  deny "Toolbelt cardinal rule: never bypass the pre-commit/pre-push hooks with --no-verify. Fix what the hook flags instead. (MAUNGS_TOOLBELT_GUARD=off to override.)"
fi

# 4) catastrophic recursive delete
if has 'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[fF]|rm[[:space:]]+-[a-zA-Z]*[fF][a-zA-Z]*[rR]|rm[[:space:]].*--no-preserve-root'; then
  if has 'rm[[:space:]].*[[:space:]](/|~|\$HOME|\*)([[:space:]]|$)|--no-preserve-root|rm[[:space:]]+-[rRfF]+[[:space:]]+(/|~|\*)'; then
    deny "Refusing a catastrophic recursive delete (rm -rf targeting / ~ \$HOME or *). Delete a specific subdirectory instead. (MAUNGS_TOOLBELT_GUARD=off to override.)"
  fi
fi

# 5) AI attribution in a commit
if has 'git([[:space:]]|.)*commit' && has 'Co-Authored-By:[[:space:]]*Claude|Generated with[[:space:]].*Claude|🤖'; then
  deny "Toolbelt cardinal rule: no AI attribution in commits/PRs (no 'Co-Authored-By: Claude' / 'Generated with Claude Code'). Remove it from the commit message. (MAUNGS_TOOLBELT_GUARD=off to override.)"
fi

exit 0
