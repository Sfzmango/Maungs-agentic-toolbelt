#!/usr/bin/env bash
#
# install.sh — copy (or symlink) this repo's agents and skills into your
# Claude Code config so you can use them in any project.
#
#   ./install.sh              # copy agents + skills into ~/.claude
#   ./install.sh --symlink    # symlink instead of copy (track repo updates with git pull)
#   ./install.sh --target DIR # install into DIR/.claude instead of ~/.claude
#   ./install.sh --dry-run    # show what would happen, change nothing
#
# Agents are installed as ~/.claude/agents/<name>.md and skills as
# ~/.claude/skills/<name>/SKILL.md — both valid, auto-discovered layouts.
#
# Prefer a one-command install? This repo is also a Claude Code plugin — see
# the README's "Install as a plugin" section.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.claude"
MODE="copy"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --symlink) MODE="symlink"; shift ;;
    --target)  TARGET="${2%/}/.claude"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

info() { printf '  %s\n' "$1"; }
warn() { printf '  ⚠️  %s\n' "$1" >&2; }

run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    info "[dry-run] $*"
  else
    "$@"
  fi
}

place() { # place <src> <dst>
  local src="$1" dst="$2"
  if [[ -e "$dst" || -L "$dst" ]]; then
    warn "exists, skipping: ${dst/#$HOME/~}  (remove it first to reinstall)"
    return
  fi
  run mkdir -p "$(dirname "$dst")"
  if [[ "$MODE" == "symlink" ]]; then
    run ln -s "$src" "$dst"
  else
    run cp -R "$src" "$dst"
  fi
  info "${MODE}: ${dst/#$HOME/~}"
}

echo "Installing claude-dev-pipeline into ${TARGET/#$HOME/~}  (mode: $MODE)"

echo "Agents:"
for f in "$SCRIPT_DIR"/agents/*.md; do
  name="$(basename "$f")"
  # Warn if the folder form (~/.claude/agents/<name>/agent.md) already exists.
  base="${name%.md}"
  if [[ -d "$TARGET/agents/$base" ]]; then
    warn "folder-form agent already installed: agents/$base/  (would duplicate '$base')"
  fi
  place "$f" "$TARGET/agents/$name"
done

echo "Skills:"
for d in "$SCRIPT_DIR"/skills/*/; do
  name="$(basename "$d")"
  place "${d%/}" "$TARGET/skills/$name"
done

cat <<'EOF'

Done. Next steps:
  1. Restart Claude Code (or run /agents and /skills) to pick up the new components.
  2. These agents assume two MCP servers are configured in your project:
       • GitHub MCP   — issue/PR read+write (used by most agents)
       • Playwright MCP — browser verification (used by @developer for UI changes)
     The @resolution agent falls back to the `gh` CLI for thread resolution.
  3. Try it:  /orchestrator <issue-id>   ·   /bug-catcher <symptom>   ·   /wiki-generator
EOF
