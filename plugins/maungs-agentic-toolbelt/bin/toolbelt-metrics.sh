#!/usr/bin/env bash
#
# toolbelt-metrics.sh — read-only summary of Maungs-agentic-toolbelt usage.
#
# Backs `$toolbelt metrics`. Reads the append-only JSONL log the hooks write when
# MAUNGS_TOOLBELT_DEBUG is on (see hooks/lib-telemetry.sh) and prints a human
# report: how often the router OFFERED a component, what actually RAN, and how
# often a suggestion converted into a run in the same session.
#
# READ-ONLY — it never writes, edits, or deletes anything (not even the log).
# Requires jq. Override the log path with MAUNGS_TOOLBELT_LOG or `--log <path>`.

set -u

LOG="${MAUNGS_TOOLBELT_LOG:-${HOME}/.codex/maungs-toolbelt/usage.jsonl}"
while [ $# -gt 0 ]; do
  case "$1" in
    --log) LOG="${2:-$LOG}"; shift 2 ;;
    -h|--help)
      printf 'usage: toolbelt-metrics.sh [--log <path>]\n'
      printf 'Summarizes the toolbelt usage log (default: %s).\n' "$LOG"
      exit 0 ;;
    *) shift ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  printf 'toolbelt metrics: jq is required to read the usage log.\n' >&2
  exit 1
fi

state="${MAUNGS_TOOLBELT_DEBUG:-off}"

if [ ! -s "$LOG" ]; then
  printf '⚒  Maungs-agentic-toolbelt — usage metrics\n'
  printf 'No telemetry recorded yet.\n\n'
  if [ "$state" = "off" ]; then
    printf 'Telemetry is OFF. Turn it on, then use the toolbelt for a while:\n'
    printf '    export MAUNGS_TOOLBELT_DEBUG=on        # record to the log\n'
    printf '    export MAUNGS_TOOLBELT_DEBUG=verbose   # also trace each event to stderr\n'
  else
    printf 'Telemetry is ON (MAUNGS_TOOLBELT_DEBUG=%s) but no events are logged yet.\n' "$state"
    printf 'Trigger the router (type a matching prompt) or run an agent/skill, then re-check.\n'
  fi
  printf 'Log: %s\n' "$LOG"
  exit 0
fi

# --- headline counts --------------------------------------------------------
suggested="$(jq -rs '[.[]|select(.event=="suggested")]|length' "$LOG" 2>/dev/null)"
invoked="$(jq -rs '[.[]|select(.event=="invoked")]|length' "$LOG" 2>/dev/null)"
sessions="$(jq -rs '[.[].session]|map(select(.!=null and .!=""))|unique|length' "$LOG" 2>/dev/null)"
first="$(jq -rs '[.[].ts]|min // "?"' "$LOG" 2>/dev/null)"
last="$(jq -rs '[.[].ts]|max // "?"' "$LOG" 2>/dev/null)"

# --- suggestion → use conversion (same session) -----------------------------
read -r sug conv <<EOF
$(jq -rs '
  (map(select(.event=="invoked"))) as $inv
  | [ .[] | select(.event=="suggested") | . as $s
      | (($s.offers // "") | split(",")) as $offs
      | ( ($s.session // "") != ""
          and ($inv | any(. as $i
                | $i.session == $s.session
                  and (($offs | index($i.component)) != null))) ) ]
  | "\(length) \([.[]|select(.)]|length)"
' "$LOG" 2>/dev/null)
EOF
sug="${sug:-0}"; conv="${conv:-0}"
if [ "${sug:-0}" -gt 0 ] 2>/dev/null; then
  pct="$(awk "BEGIN{printf \"%d\", ($conv*100)/$sug}")"
else
  pct="0"
fi

# --- render -----------------------------------------------------------------
printf '⚒  Maungs-agentic-toolbelt — usage metrics\n'
printf 'Log: %s   (debug: %s)\n' "$LOG" "$state"
printf 'Window: %s → %s   ·   %s session(s)\n\n' "$first" "$last" "${sessions:-0}"

printf 'Suggested  (router offered a component) ......... %s\n' "${suggested:-0}"
jq -r 'select(.event=="suggested")|.intent // "?"' "$LOG" 2>/dev/null \
  | sort | uniq -c | sort -rn \
  | awk '{printf "    %-18s %s\n", $2, $1}'

printf '\nInvoked    (agent/skill actually ran) ........... %s\n' "${invoked:-0}"
jq -r 'select(.event=="invoked")|"\(.kind // "?") \(.component // "?")"' "$LOG" 2>/dev/null \
  | sort | uniq -c | sort -rn \
  | awk '{printf "    %-6s %-18s %s\n", $2, $3, $1}'

printf '\nSuggestion → use conversion (same session)\n'
printf '    %s / %s suggestions led to an offered component being used  (%s%%)\n' \
  "$conv" "$sug" "$pct"

printf '\nRecent activity\n'
tail -n 8 "$LOG" 2>/dev/null | jq -r '
  "    \(.ts)  " + (if .event=="suggested"
                    then "offered " + (.intent // "?")
                    else "ran     " + ((.kind // "") + " " + (.component // "?")) end)
' 2>/dev/null

exit 0
