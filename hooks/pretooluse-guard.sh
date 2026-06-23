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
# Matching precision (INVOCATION position, not quoted text):
#   The matchers run against a NEUTRALIZED "scan" string, not the raw command.
#   The contents of single- and double-quoted spans are replaced with a fixed
#   placeholder before matching, so a danger token that merely appears INSIDE a
#   quoted argument — e.g. `gh pr create --body "... --no-verify ..."` or
#   `git commit -m "doc: force-push is banned"` — is NOT treated as an
#   invocation and is allowed. A token in command/operator position (a real
#   invocation) is unquoted and still matches. The deny/ask regex BODIES are
#   unchanged; only the string they scan changes.
#
#   FAIL-CLOSED on ambiguity: quote-neutralization runs ONLY when the quoting is
#   unambiguous (balanced single/double quotes, no here-doc, no unterminated
#   command substitution `$( … )` / backtick). When parsing is ambiguous —
#   unbalanced quotes, a here-doc (`<<EOF … EOF`), or an open `$(`/backtick —
#   the scan string is the RAW command, i.e. exactly today's behavior, so a real
#   danger token still matches and still denies. Command-substitution bodies
#   (`$(…)`, backticks) and here-doc bodies are NOT treated as quoted arguments:
#   a danger token inside `$(git push --force)` is a real invocation and denies.
#
#   FORCE-PUSH is SEGMENT-SCOPED: it is the only rule built from two independent
#   checks (`git…push` AND a force flag) that could otherwise match in unrelated
#   parts of the command. It now denies ONLY when `git…push`, a force flag
#   (`--force` / `-f`), and NO `force-with-lease` co-occur in ONE top-level
#   command segment. `scan` is split on top-level `&&`, `||`, `;`, `|`, and
#   newlines; the split does NOT descend into `$( … )` / backtick / here-doc
#   bodies — if those constructs are present (ambiguous boundaries), the rule
#   falls back to today's whole-string behavior (deny), preserving fail-closed.
#   So `git push origin x:y ; rm -f /tmp/x` allows (the `-f` is on `rm`, a
#   different segment) while a real `git push --force` (flag in the push's own
#   segment) still denies.
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

# ----------------------------------------------------------------------------
# Quote-neutralization preprocessing (pure Bash, fail-CLOSED on ambiguity).
#
# Walk $cmd character by character. Outside quotes, copy each char to `scan`.
# Inside a single- or double-quoted span, replace the span's CONTENTS with a
# fixed placeholder so a danger token quoted as an argument cannot match an
# invocation regex. The opening/closing quote chars themselves are preserved
# (kept as quotes) so surrounding structure is intact.
#
# Constructs that make quoting ambiguous force fail-CLOSED — scan := raw $cmd:
#   · unbalanced quotes (a span left open at end of string),
#   · a here-doc (`<<` / `<<-`), whose body is NOT a quoted arg,
#   · an unterminated command substitution `$( … )` or backtick, whose body is
#     a real invocation (and may itself contain quotes we must not strip).
# A backslash escapes the next char while OUTSIDE quotes and inside double
# quotes (so an escaped quote does not open/close a span); inside single quotes
# Bash treats backslash literally, matching shell semantics.
#
# NOTE: this only neutralizes TOP-LEVEL quoted spans. We deliberately do NOT
# descend into `$( … )` / backtick bodies — those are real invocations. If such
# a construct is present we cannot confidently neutralize, so we fall back to the
# raw command (deny stays intact). Here-docs likewise force the raw fallback.
# ----------------------------------------------------------------------------
QUOTE_PLACEHOLDER='__Q__'

neutralize_quotes() {
  # Reads $cmd; sets the global `scan`. On any ambiguity, sets scan="$cmd".
  local s="$cmd"
  local out=""          # accumulated neutralized output
  local i=0 n=${#s}
  local ch
  local in_squote=0 in_dquote=0

  # Fail-CLOSED on constructs whose body is a real invocation (not a quoted arg)
  # or whose boundaries we cannot trust to parse confidently. When any are seen we
  # do NOT neutralize — scan := raw $cmd (today's behavior, still denies):
  #   · here-doc operator  <<  (or  <<-  )  — detected up front below
  #   · command substitution  $( … )        — detected in the walk (on `$(`)
  #   · backtick command substitution ` … ` — detected in the walk (on the first `)
  # The walk bails to the raw command the moment it meets a `$(` or a backtick,
  # which is strictly conservative (we never try to neutralize inside them).
  case "$s" in
    *'<<'*) scan="$cmd"; return 0 ;;        # here-doc -> fail closed
  esac

  # Walk the string. Track quote state and validate balance.
  while [ "$i" -lt "$n" ]; do
    ch="${s:$i:1}"

    if [ "$in_squote" -eq 1 ]; then
      # Inside single quotes: backslash is literal; only ' closes the span.
      if [ "$ch" = "'" ]; then
        out="$out'"
        in_squote=0
      fi
      # else: drop the content char (already represented by placeholder)
      i=$((i+1))
      continue
    fi

    if [ "$in_dquote" -eq 1 ]; then
      # Inside double quotes: backslash escapes the next char; " closes.
      if [ "$ch" = "\\" ]; then
        # skip the escaped char too (it is span content, neutralized)
        i=$((i+2))
        continue
      fi
      # Double quotes do NOT suppress command substitution: "$( ... )" and the
      # backtick form run a real command, so a danger token inside is a real
      # invocation, not quoted text. Fail CLOSED (scan := raw $cmd) exactly like
      # the outside-quote branch, instead of neutralizing the span and hiding it.
      if [ "$ch" = '`' ]; then
        scan="$cmd"; return 0
      fi
      if [ "$ch" = '$' ] && [ "${s:$((i+1)):1}" = "(" ]; then
        scan="$cmd"; return 0
      fi
      if [ "$ch" = '"' ]; then
        out="$out\""
        in_dquote=0
      fi
      i=$((i+1))
      continue
    fi

    # --- outside any quote ---
    case "$ch" in
      '\\')
        # backslash escapes the next char outside quotes; copy both verbatim
        out="$out$ch${s:$((i+1)):1}"
        i=$((i+2))
        continue
        ;;
      '`')
        # backtick command substitution -> real invocation, fail closed
        scan="$cmd"; return 0
        ;;
      '$')
        # detect $( … ) command substitution -> real invocation, fail closed
        if [ "${s:$((i+1)):1}" = "(" ]; then
          scan="$cmd"; return 0
        fi
        out="$out$ch"
        i=$((i+1))
        continue
        ;;
      "'")
        # open single-quoted span: emit opening quote + placeholder
        out="$out'$QUOTE_PLACEHOLDER"
        in_squote=1
        i=$((i+1))
        continue
        ;;
      '"')
        # open double-quoted span: emit opening quote + placeholder
        out="$out\"$QUOTE_PLACEHOLDER"
        in_dquote=1
        i=$((i+1))
        continue
        ;;
      *)
        out="$out$ch"
        i=$((i+1))
        continue
        ;;
    esac
  done

  # If a quote span was left open, quoting is unbalanced -> fail closed.
  if [ "$in_squote" -eq 1 ] || [ "$in_dquote" -eq 1 ]; then
    scan="$cmd"
    return 0
  fi

  scan="$out"
  return 0
}

neutralize_quotes

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
has() { printf '%s' "$scan" | grep -qE -- "$1"; }
hasi() { printf '%s' "$scan" | grep -qiE -- "$1"; }
# Raw matcher — scans the ORIGINAL $cmd (quoted content included). Used ONLY by
# the AI-attribution rule: an AI co-author/"Generated with" trailer is, by
# definition, commit-MESSAGE content (always inside the quoted -m/--trailer arg),
# so it must be detected INSIDE quotes — neutralizing it would make a banned
# attribution slip through. The invocation rules (bulk-add / force-push /
# --no-verify) correctly scan the neutralized `scan` instead, since a token there
# only matters in invocation position. A block-A "documentation" body that merely
# MENTIONS the rules carries no AI-attribution string, so the raw scan here does
# not reintroduce that false-positive.
hasraw() { printf '%s' "$cmd" | grep -qE -- "$1"; }
ask() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

# Force-push rule helper — evaluates per TOP-LEVEL command segment of `scan`.
# Splits `scan` on &&, ||, ;, |, and newlines, then denies iff a SINGLE segment
# contains all of: git…push, a force signal (--force / -f / a +<refspec>), and
# NO force-with-lease. The +<refspec> form (e.g. `git push origin +main`,
# `+main:main`, `+HEAD:main`) is a force push too; --force-with-lease carries no
# leading-+ refspec, so it is never matched by the +<refspec> branch.
# Fail-CLOSED: if `scan` still carries a substitution/backtick/here-doc construct
# (e.g. the raw fallback ran), do NOT split — fall back to whole-string matching
# so a force flag inside such a construct still denies.
FORCE_SIGNAL='(--force([[:space:]=;|&)<>]|$)|[[:space:]]-f([[:space:]=;|&)<>]|$)|[[:space:]]\+[A-Za-z0-9_./~^@{}-]+(:|[[:space:]]|$))'
force_push_denies() {
  # whole-string force-push signal first (cheap pre-filter)
  printf '%s' "$scan" | grep -qE -- 'git([[:space:]]|.)*push' || return 1
  printf '%s' "$scan" | grep -qE -- "$FORCE_SIGNAL" || return 1

  # If the scan string contains constructs whose boundaries we cannot trust to
  # split on (command substitution / backticks / here-doc), fall back to today's
  # whole-string behavior: deny when force flag present and no lease anywhere.
  case "$scan" in
    *'$('*|*'`'*|*'<<'*)
      # Untrustworthy segment boundaries (command substitution / backtick /
      # here-doc): the pre-filter already confirmed a BARE force flag (not the
      # --force-with-lease form) is present somewhere, so fail CLOSED and DENY —
      # a lease in one segment must NOT excuse a bare force-push in another.
      return 0
      ;;
  esac

  # Split on top-level separators and evaluate each segment independently.
  # NOTE: feed the loop a NEWLINE-TERMINATED stream (printf '%s\n'); a stream
  # without a trailing newline would make `read` silently drop the final (or
  # only) segment — i.e. fail OPEN on a bare `git push --force`.
  local seg
  while IFS= read -r seg; do
    printf '%s' "$seg" | grep -qE -- 'git([[:space:]]|.)*push' || continue
    printf '%s' "$seg" | grep -qE -- "$FORCE_SIGNAL" || continue
    printf '%s' "$seg" | grep -qE -- '--force-with-lease([[:space:]=]|$)' && continue
    return 0   # this segment is a real force-push without lease
  # Join shell line-continuations (a trailing backslash + newline is ONE command,
  # not two) AND split on top-level separators (&& || ; |) — BOTH done inside awk
  # so we don't depend on the sed dialect turning \n into a real newline (classic
  # BSD sed emits a literal 'n', which would silently degrade the split). A
  # continued push ... --force stays one segment and denies; a bare newline stays
  # a real separator, so a legit multi-line script (a push on one line, an
  # unrelated rm -f on another) stays precise and is not over-denied.
  done < <(printf '%s\n' "$scan" \
    | awk '{ if (h!=""){ $0=h $0; h="" } if ($0 ~ /\\$/){ h=substr($0,1,length($0)-1) " "; next } gsub(/(\&\&|\|\||;|\|)/,"\n"); print } END{ if(h!=""){ gsub(/(\&\&|\|\||;|\|)/,"\n",h); print h } }')

  return 1
}

# 1) bulk git add — the short-flag branch matches a SINGLE-dash cluster that
#    contains 'A' (so -A, -Av, -vA all deny) but not --all (handled by its own
#    branch) and not an A-less cluster like -p/--patch.
if has 'git[[:space:]]+add[[:space:]]+(-[a-zA-Z]*A[a-zA-Z]*\b|--all\b|\.([[:space:]]|$)|-- \.)'; then
  deny "Toolbelt cardinal rule: do not 'git add -A/--all/.'. Stage the specific paths you changed instead (e.g. 'git add path/to/file'). Disable the guard with MAUNGS_TOOLBELT_GUARD=off if you really need this."
fi

# 2) force push without lease (segment-scoped — see force_push_denies)
if force_push_denies; then
  deny "Toolbelt cardinal rule: no 'git push --force'. Use '--force-with-lease', which refuses to clobber commits you haven't seen. (MAUNGS_TOOLBELT_GUARD=off to override.)"
fi

# 3) hook-bypass — the long --no-verify form, OR the short -n form on a commit.
#    For the short form, match a single-dash cluster containing 'n' with NO 'm'
#    before the n in that cluster (so -n / -nm / -vn deny, but -mn — where -m
#    takes n as its message value — does NOT). Scans the neutralized `scan`, so
#    `git commit -m "note: -n"` (token inside a quoted arg) does not trip.
if has '--no-verify\b'; then
  deny "Toolbelt cardinal rule: never bypass the pre-commit/pre-push hooks with --no-verify. Fix what the hook flags instead. (MAUNGS_TOOLBELT_GUARD=off to override.)"
fi
if has 'git([[:space:]]|.)*commit' && has '[[:space:]]-[a-ln-z]*n[a-zA-Z]*([[:space:]=]|$)'; then
  deny "Toolbelt cardinal rule: never bypass the pre-commit/pre-push hooks with --no-verify (or its short -n form). Fix what the hook flags instead. (MAUNGS_TOOLBELT_GUARD=off to override.)"
fi

# 4) catastrophic recursive delete — matched against the RAW command with quote
#    characters stripped (rm_scan), NOT the neutralized `scan`. A dangerous target
#    is commonly QUOTED in real, recommended usage — `rm -rf "$HOME"` is the
#    canonical safe-quoting style — and neutralizing that span would turn the single
#    most dangerous form (a quoted /, ~, $HOME or *) from a hard DENY into a mere
#    ask. Stripping the quote chars keeps the real target visible to the same regex.
#    Erring toward DENY on a bare documentation mention (`echo "rm -rf /"`) is the
#    safe, fail-closed direction for a catastrophic delete. (Same rationale as the
#    hasraw AI-attribution rule: the dangerous content lives inside quotes.)
rm_scan="$(printf '%s' "$cmd" | tr -d "\"'")"
rmhas() { printf '%s' "$rm_scan" | grep -qE -- "$1"; }
if rmhas 'rm[[:space:]]+-[a-zA-Z]*[rR][a-zA-Z]*[fF]|rm[[:space:]]+-[a-zA-Z]*[fF][a-zA-Z]*[rR]|rm[[:space:]].*--no-preserve-root'; then
  if rmhas 'rm[[:space:]].*[[:space:]](/|~|\$HOME|\*)([[:space:]]|$)|--no-preserve-root|rm[[:space:]]+-[rRfF]+[[:space:]]+(/|~|\*)'; then
    deny "Refusing a catastrophic recursive delete (rm -rf targeting / ~ \$HOME or *). Delete a specific subdirectory instead. (MAUNGS_TOOLBELT_GUARD=off to override.)"
  fi
fi

# 5) AI attribution in a commit (scans RAW $cmd — the attribution lives in the
#    quoted commit message itself; see hasraw above). The name set covers the
#    common AI assistants (not just Claude), matched case-insensitively, in both
#    the Co-Authored-By: trailer and the "Generated with …" footer; 🤖 kept.
AI_NAMES='Claude|Codex|Copilot|GPT|Grok|Gemini|DeepSeek|Mistral|Llama|Anthropic|OpenAI'
if hasraw 'git([[:space:]]|.)*commit' && printf '%s' "$cmd" | grep -qiE -- "Co-Authored-By:[[:space:]]*($AI_NAMES)|Generated with[[:space:]].*($AI_NAMES)|🤖"; then
  deny "Toolbelt cardinal rule: no AI attribution in commits/PRs (no 'Co-Authored-By: <AI>' / 'Generated with <AI>'). Remove it from the commit message. (MAUNGS_TOOLBELT_GUARD=off to override.)"
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
