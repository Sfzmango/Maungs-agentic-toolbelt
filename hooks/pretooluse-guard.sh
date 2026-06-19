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
# Asks (ALWAYS prompts with a detailed reason — never silently runs): destructive
#         SQL (DROP / TRUNCATE / DELETE / DROP COLUMN) · db:drop/reset · redis
#         FLUSHALL · git reset --hard / clean -fd / branch -D / push --delete /
#         stash drop · rm -rf of a non-disposable dir · terraform destroy /
#         kubectl delete / docker volume rm · bulk find -delete / xargs rm.
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
hasi() { printf '%s' "$cmd" | grep -qiE -- "$1"; }
ask() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

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

# ============================================================================
# ASK tier — risky / data-loss operations that MAY be legitimate but must
# ALWAYS be confirmed first. Emits permissionDecision "ask" + a detailed reason
# (it PROMPTS the user; it does not block). The deny rules above take precedence.
# ============================================================================

# Destructive SQL — DROP / TRUNCATE / DELETE FROM / DROP COLUMN
if hasi 'drop[[:space:]]+(table|database|schema|view|index|column)|truncate[[:space:]]+(table[[:space:]]+)?["a-z0-9_.]|delete[[:space:]]+from[[:space:]]|alter[[:space:]]+table[[:space:]].+drop[[:space:]]+(column|constraint)'; then
  ask "DATA LOSS — this runs a destructive SQL statement (DROP / TRUNCATE / DELETE FROM / DROP COLUMN) that permanently removes data and is not recoverable once committed. Confirm you intend this, and that it targets the correct database/environment (not production by accident), before approving."
fi

# Database drop/reset via Rails/Rake, or a datastore flush
if hasi '(rails|rake|bin/rails|bin/rake)[[:space:]].*db:(drop|reset|purge|schema:load|migrate:reset)|(^|[[:space:];&|])db:(drop|reset|migrate:reset)([[:space:]]|$)|\bdropdb\b|flushall|flushdb|heroku[[:space:]].*pg:reset'; then
  ask "DATA LOSS — this drops/resets a database or flushes a datastore (db:drop/reset/schema:load, dropdb, redis FLUSHALL, heroku pg:reset). Every row in that environment is destroyed. Confirm the exact target environment before approving — a wrong env here wipes real data."
fi

# Git ops that discard uncommitted work or delete refs
if has 'git([[:space:]]|.)*reset[[:space:]]+--hard|git([[:space:]]|.)*clean[[:space:]]+-[a-zA-Z]*f|git([[:space:]]|.)*checkout[[:space:]]+(--[[:space:]]+)?\.([[:space:]]|$)|git([[:space:]]|.)*branch[[:space:]]+-D|git([[:space:]]|.)*push[[:space:]].*--delete|git([[:space:]]|.)*stash[[:space:]]+(clear|drop)'; then
  ask "DISCARDS WORK — this git command throws away uncommitted changes or deletes a branch/ref (reset --hard / clean -fd / checkout . / branch -D / push --delete / stash drop). The discarded work is usually unrecoverable. Confirm you have nothing unsaved you need before approving."
fi

# rm -rf of a non-disposable path (catastrophic / ~ * targets are DENIED above)
if has 'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[fF]|rm[[:space:]]+-[a-zA-Z]*[fF][a-zA-Z]*[rR]'; then
  has '(node_modules|dist/|/dist|build/|/build|\.next|target/|coverage/|/tmp|tmp/|\.cache|out/|vendor/bundle|\.turbo|\.venv|__pycache__)' \
    || ask "RECURSIVE DELETE — 'rm -rf' permanently removes an entire directory tree with no undo, and the target doesn't look like a disposable build/cache dir. Confirm the path is exactly what you intend before approving."
fi

# Infrastructure / container / volume destruction
if hasi 'terraform[[:space:]]+destroy|kubectl[[:space:]]+delete|docker[[:space:]]+system[[:space:]]+prune|docker[[:space:]]+volume[[:space:]]+(rm|prune)'; then
  ask "INFRA DESTRUCTION — this tears down infrastructure, containers, or volumes (terraform destroy / kubectl delete / docker volume rm / system prune) and can delete running services and their data. Confirm the target context/namespace/cluster before approving."
fi

# Bulk file deletion via find / xargs
if has 'find[[:space:]].*-delete|find[[:space:]].*-exec[[:space:]]+rm|xargs[[:space:]].*[[:space:]]rm[[:space:]]+-[a-zA-Z]*[rRfF]'; then
  ask "BULK DELETE — this deletes many files at once (find -delete / find -exec rm / xargs rm); an over-broad pattern can remove far more than intended. Confirm the match set (dry-run without -delete first) before approving."
fi

exit 0
