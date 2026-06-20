#!/usr/bin/env bash
#
# usage-tracker.sh — PreToolUse(Task, Skill) telemetry for Maungs-agentic-toolbelt.
#
# Records an "invoked" event whenever one of THIS toolbelt's agents (a Task with
# a maungs-agentic-toolbelt subagent_type) or skills (a Skill call) actually runs,
# so `/toolbelt metrics` can show what gets used — and, joined with the router's
# "suggested" events, how often a suggestion converts into a real run.
#
# Contract:
#   - PURE PASS-THROUGH. It logs and exits 0 with NO permission decision, so it
#     never blocks, allows, or asks — the normal permission flow is untouched.
#   - OPT-IN. Silent and zero-overhead unless MAUNGS_TOOLBELT_DEBUG is on/verbose.
#   - Read-only except for the append-only log under ~/.claude (see lib-telemetry).
#   - Only counts OUR components: a "maungs-agentic-toolbelt:" namespace, or a bare
#     slug that resolves to a file in this plugin's agents/ or skills/ dir. Other
#     plugins' and built-in agents (Explore, general-purpose, …) are ignored.
#
# Fail-OPEN: any parse error / missing jq exits 0 (the tool still runs).

# Source the shared telemetry helper from this script's own directory.
TB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
# shellcheck source=/dev/null
. "${TB_DIR}/lib-telemetry.sh" 2>/dev/null || exit 0

tb_debug_on || exit 0                       # off by default → do nothing
command -v jq >/dev/null 2>&1 || exit 0     # need jq for safe parsing

input="$(cat 2>/dev/null)"; [ -z "$input" ] && exit 0

tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)"
session="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"

case "$tool" in
  Task)
    raw="$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // .tool_input.agent_type // empty' 2>/dev/null)"
    kind="agent" ;;
  Skill)
    raw="$(printf '%s' "$input" | jq -r '.tool_input.skill // .tool_input.command // .tool_input.name // empty' 2>/dev/null)"
    kind="skill" ;;
  *) exit 0 ;;
esac
[ -z "$raw" ] && exit 0

# slug = component name with any "plugin:" namespace prefix stripped.
slug="${raw##*:}"

# Is this one of OURS? Prefer the explicit plugin namespace; otherwise (e.g. a
# copy/install.sh install with no namespace) resolve the bare slug against the
# real installed set so the list never goes stale.
is_ours=0
case "$raw" in
  maungs-agentic-toolbelt:*) is_ours=1 ;;
esac
if [ "$is_ours" = "0" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  case "$kind" in
    agent) [ -f "${CLAUDE_PLUGIN_ROOT}/agents/${slug}.md" ] && is_ours=1 ;;
    skill) [ -d "${CLAUDE_PLUGIN_ROOT}/skills/${slug}" ]    && is_ours=1 ;;
  esac
fi
[ "$is_ours" = "1" ] || exit 0

rec="$(jq -nc \
  --arg ts "$(tb_now)" \
  --arg kind "$kind" \
  --arg component "$slug" \
  --arg raw "$raw" \
  --arg session "$session" \
  --arg cwd "$cwd" \
  '{ts:$ts,event:"invoked",kind:$kind,component:$component,raw:$raw,session:$session,cwd:$cwd}' 2>/dev/null)"
tb_append "$rec"

exit 0
