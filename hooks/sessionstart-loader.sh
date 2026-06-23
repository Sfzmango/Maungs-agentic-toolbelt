#!/usr/bin/env bash
#
# sessionstart-loader.sh — SessionStart hook for Maungs-agentic-toolbelt.
#
# Injects a concise, read-only project snapshot at session start so Claude
# begins warm instead of re-deriving the repo from scratch. Local git is
# instant; the optional `gh` PR lookup is best-effort and bounded by the hook
# timeout in hooks.json.
#
# On a fresh launch it also runs a best-effort UPDATE PREFLIGHT: it compares the
# installed plugin version against the latest published version and, when a newer
# one exists, surfaces a notice plus a directive asking Claude to OFFER the update
# on the user's first turn (apply is human-gated; a restart is required to load
# new hooks). The check is bounded, throttled, and fail-safe.
#
# Read-only on the repo, fail-safe (always exits 0; prints nothing on error so it
# can never block a session).
#
# Env switches:
#   MAUNGS_TOOLBELT_LOADER=off          disable this loader entirely
#   MAUNGS_TOOLBELT_UPDATE_CHECK=off    disable just the update preflight
#   MAUNGS_TOOLBELT_UPDATE_CHECK=force  bypass the throttle (check every launch)
#   MAUNGS_TOOLBELT_UPDATE_FAKE=X.Y.Z   simulate "latest" = X.Y.Z (no network; for testing the UX)

[ "${MAUNGS_TOOLBELT_LOADER:-on}" = "off" ] && exit 0
event="$(cat 2>/dev/null)"   # capture the SessionStart event JSON (for its source)
TB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"   # resolve before any cd

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0   # only in a repo
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" 2>/dev/null || exit 0

out=""
add() { out="${out}${1}
"; }

# true (0) iff $1 is a strictly-greater semver than $2 (MAJOR.MINOR.PATCH); tolerant of missing parts.
_ver_gt() {
  local A="$1" B="$2" IFS=. a1 a2 a3 b1 b2 b3
  set -- $A; a1=${1:-0}; a2=${2:-0}; a3=${3:-0}
  set -- $B; b1=${1:-0}; b2=${2:-0}; b3=${3:-0}
  a1=${a1//[!0-9]/}; a2=${a2//[!0-9]/}; a3=${a3//[!0-9]/}
  b1=${b1//[!0-9]/}; b2=${b2//[!0-9]/}; b3=${b3//[!0-9]/}
  [ "${a1:-0}" -gt "${b1:-0}" ] && return 0; [ "${a1:-0}" -lt "${b1:-0}" ] && return 1
  [ "${a2:-0}" -gt "${b2:-0}" ] && return 0; [ "${a2:-0}" -lt "${b2:-0}" ] && return 1
  [ "${a3:-0}" -gt "${b3:-0}" ] && return 0
  return 1
}

# Print the latest published plugin version (or nothing). Best-effort, bounded (~5s), silent on failure.
_latest_version() {
  [ -n "${MAUNGS_TOOLBELT_UPDATE_FAKE:-}" ] && { printf '%s' "$MAUNGS_TOOLBELT_UPDATE_FAKE"; return 0; }
  command -v gh >/dev/null 2>&1 || return 0
  local mkt slug tmpf pid killer v
  mkt="${HOME}/.claude/plugins/marketplaces/maung-tools"
  slug="$(git -C "$mkt" config --get remote.origin.url 2>/dev/null \
            | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
  [ -n "$slug" ] || slug="Sfzmango/Maungs-agentic-toolbelt"
  tmpf="$(mktemp 2>/dev/null)" || return 0
  ( gh api "repos/${slug}/contents/.claude-plugin/plugin.json" \
        -H "Accept: application/vnd.github.raw" >"$tmpf" 2>/dev/null ) & pid=$!
  ( sleep 5; kill -TERM "$pid" 2>/dev/null ) & killer=$!
  wait "$pid" 2>/dev/null
  kill -TERM "$killer" 2>/dev/null; wait "$killer" 2>/dev/null
  v="$(grep -m1 '"version"' "$tmpf" 2>/dev/null | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/')"
  rm -f "$tmpf" 2>/dev/null
  printf '%s' "$v"
}

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

# On a fresh launch (startup only), greet with the rotating hero banner first, then
# run the update preflight. Both are gated to startup so resume/clear stay quiet and
# the network check runs at most once per launch.
if printf '%s' "$event" | grep -q '"source"[[:space:]]*:[[:space:]]*"startup"'; then
  _b="${TB_DIR}/../bin/toolbelt-banner.sh"   # hooks/ and bin/ are siblings in the plugin
  [ -f "$_b" ] && { bash "$_b" 2>/dev/null; printf '\n'; }

  # --- update preflight (best-effort, throttled, fail-safe) ---
  if [ "${MAUNGS_TOOLBELT_UPDATE_CHECK:-on}" != "off" ]; then
    reg="${HOME}/.claude/plugins/installed_plugins.json"
    installed="$(grep -A8 '"maungs-agentic-toolbelt@maung-tools"' "$reg" 2>/dev/null \
                  | grep -m1 '"version"' | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/')"
    if [ -n "$installed" ]; then
      state="${HOME}/.claude/maungs-toolbelt/update-check"   # "<epoch> <latest>" — throttles the network call
      now="$(date +%s 2>/dev/null)"; throttle=14400          # re-check at most every 4h
      cached_at=""; latest=""
      [ -f "$state" ] && { cached_at="$(awk '{print $1}' "$state" 2>/dev/null)"; latest="$(awk '{print $2}' "$state" 2>/dev/null)"; }
      fresh=0
      if [ -n "${MAUNGS_TOOLBELT_UPDATE_FAKE:-}" ] || [ "${MAUNGS_TOOLBELT_UPDATE_CHECK:-on}" = "force" ]; then
        fresh=0   # always re-evaluate
      elif [ -n "$cached_at" ] && [ -n "$now" ] && [ $((now - cached_at)) -lt "$throttle" ]; then
        fresh=1   # within throttle window — reuse cached "latest", no network
      fi
      if [ "$fresh" -eq 0 ]; then
        latest="$(_latest_version)"
        # Persist only a real, successful fetch. Skip when FAKE (never poison the cache with a
        # simulated value) and skip on empty (a failed/timed-out fetch must retry next launch,
        # not stay throttled-silent for 4h).
        if [ -n "$now" ] && [ -n "$latest" ] && [ -z "${MAUNGS_TOOLBELT_UPDATE_FAKE:-}" ]; then
          mkdir -p "${HOME}/.claude/maungs-toolbelt" 2>/dev/null
          printf '%s %s\n' "$now" "$latest" > "$state" 2>/dev/null
        fi
      fi
      if [ -n "$latest" ] && _ver_gt "$latest" "$installed"; then
        add "- ⬆️  Toolbelt update available: ${installed} → ${latest}  (I'll offer to update on your first message — or just say \"update the toolbelt\")"
        add "  ↳ [for Claude] A newer plugin version (${latest}) is available; installed is ${installed}. On your FIRST reply this session, use AskUserQuestion to ask whether to update now. If YES: have the user run \`/plugin marketplace update maung-tools\` then \`/plugin install maungs-agentic-toolbelt@maung-tools\`; then verify the new install is not stale (banner script present + loader has the update-preflight wiring + installed version == ${latest}); then tell them to RESTART Claude Code so the new hooks load. If NO: continue normally and do not re-ask this session."
      fi
    fi
  fi
fi

printf '%s' "$out"
exit 0
