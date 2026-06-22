#!/usr/bin/env bash
#
# install-codex.sh — install this toolbelt's AGENTS + HOOKS into the OpenAI
# Codex CLI config (~/.codex). Skills ship via the Codex marketplace/plugin
# manifest, NOT this installer (the Codex plugin manifest cannot carry agents +
# hooks), so this is the agents+hooks track. See docs/codex.md for the two-track
# story.
#
#   ./install-codex.sh              # install agents + hooks into ~/.codex
#   ./install-codex.sh --target DIR # install into DIR/.codex instead of ~/.codex
#   ./install-codex.sh --dry-run    # show what would happen, change nothing
#   ./install-codex.sh --skills     # ALSO copy the generated skills locally
#                                   #   (fallback when you are not using the
#                                   #    marketplace; the marketplace is preferred)
#
# It:
#   1. copies each generated codex-agents/<name>.toml  -> ~/.codex/agents/
#   2. copies the five generated codex-hooks/*.sh       -> ~/.codex/hooks/
#   3. MERGES codex-hooks/hooks.json into ~/.codex/hooks.json (never clobbers an
#      existing notify / mcp_servers), AFTER substituting every
#      __TOOLBELT_HOOK_DIR__ placeholder with the absolute ~/.codex/hooks dir, so
#      each command entry resolves to the copied script.
#   4. prints MCP setup guidance (it does NOT run `codex mcp add` for you).
#
# jq is used for the hooks.json merge; without jq it PRINTS the generated hooks
# block and the target path so you can merge by hand (jq is not a hard dep).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.codex"
DRY_RUN="false"
WITH_SKILLS="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)  [[ $# -ge 2 ]] || { echo "Missing DIR for --target" >&2; exit 1; }; TARGET="${2%/}/.codex"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    --skills)  WITH_SKILLS="true"; shift ;;
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

AGENTS_SRC="$SCRIPT_DIR/codex-agents"
HOOKS_SRC="$SCRIPT_DIR/codex-hooks"
SKILLS_SRC="$SCRIPT_DIR/plugins/maungs-agentic-toolbelt/skills"

if [[ ! -d "$AGENTS_SRC" || ! -d "$HOOKS_SRC" ]]; then
  echo "Generated artifacts not found. Run: python3 tools/build.py --target codex" >&2
  exit 1
fi

# nullglob so an EMPTY codex-agents/ or codex-hooks/ expands to nothing (not a
# literal `*.toml`/`*.sh` that `cp` would choke on and abort under `set -e`).
shopt -s nullglob
AGENT_FILES=("$AGENTS_SRC"/*.toml)
HOOK_FILES=("$HOOKS_SRC"/*.sh)
if [[ ${#AGENT_FILES[@]} -eq 0 || ${#HOOK_FILES[@]} -eq 0 ]]; then
  echo "Generated artifacts not found. Run: python3 tools/build.py --target codex" >&2
  exit 1
fi

echo "Installing Maungs-agentic-toolbelt (Codex) into ${TARGET/#$HOME/~}"
if [[ "$DRY_RUN" == "true" ]]; then echo "  (dry-run — nothing will change)"; fi

# 1) Agents -> ~/.codex/agents/
echo "Agents:"
run mkdir -p "$TARGET/agents"
for f in "${AGENT_FILES[@]}"; do
  name="$(basename "$f")"
  run cp "$f" "$TARGET/agents/$name"
  info "agent: agents/$name"
done

# 2) Hooks -> ~/.codex/hooks/
echo "Hooks:"
HOOK_DIR="$TARGET/hooks"
run mkdir -p "$HOOK_DIR"
for f in "${HOOK_FILES[@]}"; do
  name="$(basename "$f")"
  run cp "$f" "$HOOK_DIR/$name"
  run chmod +x "$HOOK_DIR/$name"
  info "hook: hooks/$name"
done

# 3) Merge hooks.json (substitute the placeholder with the absolute hook dir).
GEN_HOOKS_JSON="$HOOKS_SRC/hooks.json"
DST_HOOKS_JSON="$TARGET/hooks.json"

# Resolve the __TOOLBELT_HOOK_DIR__ placeholder to the real install hook dir.
# $HOOK_DIR is user-controlled (--target DIR), so the substitution MUST be
# metacharacter-safe: a raw `sed s#…#$HOOK_DIR#` would mis-substitute on `&` or
# `\N` and abort if the path contained `#` (CWE-150). We substitute with jq's
# --arg (a literal string bind, no regex/metachar interpretation) when jq is
# present, falling back to a Python literal str.replace when it is not — both are
# safe against `&` / `#` / backslash in the path. We never feed $HOOK_DIR to sed.
subst_placeholder() {
  # Reads the template on stdin, writes the placeholder-substituted text to
  # stdout. $1 = the replacement dir.
  if command -v jq >/dev/null 2>&1; then
    # jq builds the result entirely from string VALUES bound via --arg, so the
    # path is never parsed as a pattern. walk every string, replacing the exact
    # placeholder token with the literal $dir.
    jq --arg dir "$1" '
      def subst: if type == "string" then sub("__TOOLBELT_HOOK_DIR__"; $dir) else . end;
      walk(subst)
    '
  elif command -v python3 >/dev/null 2>&1; then
    # Parse the template as JSON, literal-replace the placeholder inside every
    # string value, and re-serialize — so the path is bound as data (never a
    # regex/sed pattern) AND a path with a backslash stays valid JSON.
    python3 -c 'import sys, json
d = sys.argv[1]
def walk(x):
    if isinstance(x, str):
        return x.replace("__TOOLBELT_HOOK_DIR__", d)
    if isinstance(x, list):
        return [walk(v) for v in x]
    if isinstance(x, dict):
        return {k: walk(v) for k, v in x.items()}
    return x
json.dump(walk(json.load(sys.stdin)), sys.stdout, indent=2, ensure_ascii=False)
sys.stdout.write("\n")' "$1"
  else
    # No jq and no python3: the placeholder cannot be substituted safely, so do
    # NOT emit a half-substituted template. Signal the caller to skip + warn.
    return 3
  fi
}

echo "hooks.json:"
if command -v jq >/dev/null 2>&1; then
  SUBBED="$(subst_placeholder "$HOOK_DIR" < "$GEN_HOOKS_JSON")"
  if [[ "$DRY_RUN" == "true" ]]; then
    info "[dry-run] would merge the toolbelt hooks into ${DST_HOOKS_JSON/#$HOME/~} (preserving notify / mcp_servers)"
  else
    if [[ -f "$DST_HOOKS_JSON" ]]; then
      # Deep-merge, IDEMPOTENTLY: keep existing top-level keys (notify, mcp_servers,
      # …) and the user's OWN hook groups, but for each event we register, first
      # DROP any prior entry whose command EQUALS one we are adding before appending
      # the fresh ones — so re-running the installer (e.g. after a `git pull`)
      # REPLACES the toolbelt's own entries instead of STACKING duplicates, while
      # PRESERVING a user's own hook that merely lives under the same hook dir (a
      # substring-on-dir match would have wrongly dropped that). Dedup is by exact
      # command equality against the commands we are installing.
      merged="$(jq -s '
        .[0] as $cur | .[1] as $new |
        $cur * {hooks: (
          ($cur.hooks // {}) as $ch | ($new.hooks // {}) as $nh |
          reduce ($nh | keys[]) as $k ($ch;
            ([ $nh[$k][] | .hooks[]?.command ]) as $newcmds |
            .[$k] = ( [ ($ch[$k] // [])[] | select([.hooks[]?.command] | any(. as $c | $newcmds | index($c)) | not) ] + $nh[$k] ))
        )}
      ' "$DST_HOOKS_JSON" <(printf '%s' "$SUBBED"))"
      printf '%s\n' "$merged" > "$DST_HOOKS_JSON"
      info "merged toolbelt hooks into ${DST_HOOKS_JSON/#$HOME/~} (preserved existing keys)"
    else
      printf '%s\n' "$SUBBED" > "$DST_HOOKS_JSON"
      info "wrote ${DST_HOOKS_JSON/#$HOME/~}"
    fi
  fi
else
  # jq-absent fallback: print the (safely-substituted) block + skip the merge.
  warn "jq not found — cannot auto-merge hooks.json. Merge this block into ${DST_HOOKS_JSON/#$HOME/~} by hand:"
  if SUBBED="$(subst_placeholder "$HOOK_DIR" < "$GEN_HOOKS_JSON")"; then
    printf '%s\n' "$SUBBED"
  else
    # No jq AND no python3 — substitute nothing rather than risk a metacharacter
    # mangle. Print the raw template and tell the user the exact replacement.
    warn "python3 also not found — printing the template UNSUBSTITUTED; replace every '__TOOLBELT_HOOK_DIR__' with: ${HOOK_DIR}"
    cat "$GEN_HOOKS_JSON"
  fi
fi

# 4) Optional: skills locally (marketplace is preferred).
if [[ "$WITH_SKILLS" == "true" ]]; then
  echo "Skills (local fallback — marketplace is preferred):"
  if [[ -d "$SKILLS_SRC" ]]; then
    run mkdir -p "$TARGET/skills"
    for d in "$SKILLS_SRC"/*/; do
      name="$(basename "$d")"
      # rm-then-copy so the copy is IDEMPOTENT: a plain `cp -R` over an existing
      # skill dir would NEST or leave stale files dropped across versions. The
      # `run` wrapper keeps --dry-run honest (it only prints the rm + cp).
      run rm -rf "$TARGET/skills/$name"
      run cp -R "${d%/}" "$TARGET/skills/$name"
      info "skill: skills/$name"
    done
  else
    warn "generated skills not found at $SKILLS_SRC — run: python3 tools/build.py --target codex"
  fi
fi

cat <<'EOF'

Done. Next steps:
  1. Restart your agent (Codex CLI) so it picks up the new agents + hooks.
  2. Skills: add the marketplace + install the plugin (preferred over --skills):
       codex plugin marketplace add Sfzmango/Maungs-agentic-toolbelt
       codex plugin install maungs-agentic-toolbelt
  3. These agents assume MCP servers are configured. Check + add as needed:
       codex mcp list
       # GitHub MCP   — issue/PR read+write (used by most agents)
       # Playwright MCP — browser verification (used by @developer for UI changes)
       # Context7 MCP  — doc grounding (used by @code-translator)
     The installer does NOT run `codex mcp add` for you — add the servers you need.
  4. Try it:  @architect plan a small change   ·   trigger a skill in chat
EOF
