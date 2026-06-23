#!/usr/bin/env bash
#
# install-codex.sh — install this toolbelt's AGENTS + HOOKS into the OpenAI
# Codex CLI config (~/.codex). The plugin carries skills + lifecycle hooks; this
# installer carries the custom subagents Codex does not currently package in
# third-party plugins. See docs/codex.md.
#
#   ./install-codex.sh              # install custom agents into ~/.codex
#   ./install-codex.sh --target DIR # install into DIR/.codex instead of ~/.codex
#   ./install-codex.sh --dry-run    # show what would happen, change nothing
#   ./install-codex.sh --standalone # also install skills + hooks without plugin
#   ./install-codex.sh --skills     # compatibility alias for --standalone
#
# It:
#   1. copies each generated codex-agents/<name>.toml  -> ~/.codex/agents/
#   2. with --standalone, copies plugin hooks             -> ~/.codex/hooks/
#   3. with --standalone, MERGES hooks.json into ~/.codex/hooks.json (never clobbers an
#      existing notify / mcp_servers), AFTER substituting every
#      ${PLUGIN_ROOT}/hooks reference with the absolute ~/.codex/hooks dir, so
#      each command entry resolves to the copied script.
#   4. with --standalone, copies skills                   -> ~/.agents/skills/
#   5. prints MCP setup guidance (it does NOT run `codex mcp add` for you).
#
# jq is used for the hooks.json merge; without jq it PRINTS the generated hooks
# block and the target path so you can merge by hand (jq is not a hard dep).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="${HOME}"
TARGET="${BASE}/.codex"
DRY_RUN="false"
STANDALONE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)  [[ $# -ge 2 ]] || { echo "Missing DIR for --target" >&2; exit 1; }; BASE="${2%/}"; TARGET="${BASE}/.codex"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    --standalone|--skills) STANDALONE="true"; shift ;;
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
HOOKS_SRC="$SCRIPT_DIR/plugins/maungs-agentic-toolbelt/hooks"
SKILLS_SRC="$SCRIPT_DIR/plugins/maungs-agentic-toolbelt/skills"

if [[ ! -d "$AGENTS_SRC" ]]; then
  echo "Generated artifacts not found. Run: python3 tools/build.py --target codex" >&2
  exit 1
fi

# nullglob so an EMPTY codex-agents/ or plugin hooks directory expands to nothing (not a
# literal `*.toml`/`*.sh` that `cp` would choke on and abort under `set -e`).
shopt -s nullglob
AGENT_FILES=("$AGENTS_SRC"/*.toml)
HOOK_FILES=("$HOOKS_SRC"/*.sh)
if [[ ${#AGENT_FILES[@]} -eq 0 ]]; then
  echo "Generated artifacts not found. Run: python3 tools/build.py --target codex" >&2
  exit 1
fi

# Reject schema-invalid generated files before copying them into Codex. A plain
# TOML parse is insufficient here: an mcp_servers array is valid TOML but Codex
# rejects it, while a partial map without a transport is also malformed.
# Portable agents must inherit complete MCP config from the parent.
VALIDATOR="$SCRIPT_DIR/tools/validate_codex.py"
if command -v python3 >/dev/null 2>&1 && [[ -f "$VALIDATOR" ]]; then
  if ! python3 "$VALIDATOR"; then
    echo "Codex artifact validation failed. Regenerate before installing:" >&2
    echo "  python3 tools/build.py --target codex" >&2
    exit 1
  fi
else
  warn "python3 validator unavailable — generated Codex schema checks were skipped"
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

# 2) Standalone fallback: hooks -> ~/.codex/hooks/
if [[ "$STANDALONE" == "true" ]]; then
echo "Hooks (standalone fallback — plugin install is preferred):"
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

# Resolve the plugin-root hook path to the standalone install hook dir.
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
      def subst: if type == "string" then sub("\\$\\{PLUGIN_ROOT\\}/hooks"; $dir) else . end;
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
        return x.replace("${PLUGIN_ROOT}/hooks", d)
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
    warn "python3 also not found — printing the template UNSUBSTITUTED; replace every '\${PLUGIN_ROOT}/hooks' with: ${HOOK_DIR}"
    cat "$GEN_HOOKS_JSON"
  fi
fi
fi

# 4) Standalone fallback: skills in Codex's documented user skill directory.
if [[ "$STANDALONE" == "true" ]]; then
  echo "Skills (standalone fallback — plugin install is preferred):"
  if [[ -d "$SKILLS_SRC" ]]; then
    SKILL_TARGET="$BASE/.agents/skills"
    run mkdir -p "$SKILL_TARGET"
    for d in "$SKILLS_SRC"/*/; do
      name="$(basename "$d")"
      # rm-then-copy so the copy is IDEMPOTENT: a plain `cp -R` over an existing
      # skill dir would NEST or leave stale files dropped across versions. The
      # `run` wrapper keeps --dry-run honest (it only prints the rm + cp).
      run rm -rf "$SKILL_TARGET/$name"
      run cp -R "${d%/}" "$SKILL_TARGET/$name"
      info "skill: .agents/skills/$name"
    done
  else
    warn "generated skills not found at $SKILLS_SRC — run: python3 tools/build.py --target codex"
  fi
fi

cat <<'EOF'

Done. Next steps:
  1. Add the marketplace + install the plugin (skills + lifecycle hooks):
       codex plugin marketplace add Sfzmango/Maungs-agentic-toolbelt
       codex plugin add maungs-agentic-toolbelt@maung-tools
  2. Open /hooks, review the plugin-bundled hooks, and trust them.
  3. Start a new Codex thread so it picks up the custom agents and plugin.
  4. These agents assume MCP servers are configured. Check + add as needed:
       codex mcp list
       # GitHub MCP   — issue/PR read+write (used by most agents)
       # Playwright MCP — browser verification (used by the developer subagent)
       # Context7 MCP  — doc grounding (used by the code-translator subagent)
     The installer does NOT run `codex mcp add` for you — add the servers you need.
  5. Try it:  ask Codex to spawn the architect subagent, or run $toolbelt.
EOF
