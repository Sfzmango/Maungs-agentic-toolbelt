#!/usr/bin/env bash
#
# sessionstart-loader.sh — SessionStart hook for Maungs-agentic-toolbelt.
#
# Injects a concise, read-only project snapshot at session start so Claude
# begins warm instead of re-deriving the repo from scratch. Local git is
# instant; the optional `gh` PR lookup is best-effort and bounded by the hook
# timeout in hooks.json.
#
# Read-only, fail-safe (always exits 0; prints nothing on error so it can never
# block a session). Disable with:  export MAUNGS_TOOLBELT_LOADER=off

[ "${MAUNGS_TOOLBELT_LOADER:-on}" = "off" ] && exit 0
event="$(cat 2>/dev/null)"   # capture the SessionStart event JSON (for its source)
TB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"   # resolve before any cd

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0   # only in a repo
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" 2>/dev/null || exit 0

out=""
add() { out="${out}${1}
"; }

add "[Maungs-agentic-toolbelt] Project snapshot (auto-loaded at session start):"
b="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"; [ -n "$b" ] && add "- Branch: ${b}"
n="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"; add "- Uncommitted changes: ${n} file(s)"
rc="$(git log --oneline -3 2>/dev/null | sed 's/^/    /')"; [ -n "$rc" ] && add "- Recent commits:
${rc}"

if [ ! -f CLAUDE.md ] && [ ! -f CLAUDE.local.md ]; then
  add "- No CLAUDE.md found — run /agentic-onboard to generate agent context for this repo."
fi

plan="$(ls -t docs/plans/*.md 2>/dev/null | head -1)"; [ -n "$plan" ] && add "- Latest plan file: ${plan}"
hand="$(ls -t HANDOFF*.md docs/handoffs/*.md 2>/dev/null | head -1)"; [ -n "$hand" ] && add "- Pending handoff: ${hand}"

# private per-project to-do backlog (the /todo skill) — local only, never in the repo.
# Slug must match the /todo skill's canonical computation: repo root, non-alnum -> '-'.
tfile="${HOME}/.claude/maungs-toolbelt/todos/$(printf '%s' "$root" | sed 's#[^A-Za-z0-9]#-#g').md"
if [ -f "$tfile" ]; then
  topen="$(grep -c '^- \[ \] ' "$tfile" 2>/dev/null | tr -d ' ')"
  case "$topen" in ''|0) ;; *) add "- Open todos: ${topen} (private backlog — /todo to view)";; esac
fi

if command -v gh >/dev/null 2>&1; then
  prs="$(gh pr list --limit 3 --json number,title -q '.[] | "    #\(.number) \(.title)"' 2>/dev/null)"
  [ -n "$prs" ] && add "- Open PRs:
${prs}"
fi

# On a fresh launch (startup only), greet with the rotating hero banner first.
# Runs with no TTY here, so the banner prints plain (no escape codes in context).
# Fail-safe: if the banner script isn't found, the snapshot prints as usual.
if printf '%s' "$event" | grep -q '"source"[[:space:]]*:[[:space:]]*"startup"'; then
  _b="${TB_DIR}/../bin/toolbelt-banner.sh"   # hooks/ and bin/ are siblings in the plugin
  [ -f "$_b" ] && { bash "$_b" 2>/dev/null; printf '\n'; }
fi

printf '%s' "$out"
exit 0
