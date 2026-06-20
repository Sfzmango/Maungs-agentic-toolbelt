#!/usr/bin/env bash
#
# toolbelt-statusline.sh — "Cockpit" status line for Maungs-agentic-toolbelt.
#
# Renders:  ⚒  ⎇ <branch> ✚<dirty> ↑<ahead>  │  $<cost> · <dur>m  │  guard● router●  │  <model>
#
# It is NOT auto-enabled by the plugin (Claude Code's main status line is a user
# setting). Enable it in ~/.claude/settings.json:
#
#   "statusLine": {
#     "type": "command",
#     "command": "~/Maungs-agentic-toolbelt/statusline/toolbelt-statusline.sh"
#   }
#
# Reads the status JSON on stdin (model, cost, duration), runs git itself for
# branch/dirty/ahead, and reflects the toolbelt hooks' on/off state. Read-only,
# fast, no network. Nerd-Font glyphs degrade gracefully without one.

input="$(cat 2>/dev/null)"

esc=$'\033'
mark="${esc}[38;5;208m"; cyan="${esc}[36m"; yel="${esc}[33m"; dim="${esc}[2m"
grn="${esc}[32m"; red="${esc}[31m"; rst="${esc}[0m"
sep="  ${dim}│${rst}  "

jget() { command -v jq >/dev/null 2>&1 && printf '%s' "$input" | jq -r "$1 // empty" 2>/dev/null; }

model="$(jget '.model.display_name')"; [ -z "$model" ] && model="Claude"
cost="$(jget '.cost.total_cost_usd')"
dur_ms="$(jget '.cost.total_duration_ms')"
sid="$(jget '.session_id')"

line="${mark}⚒${rst}"

# git segment
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  br="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  dirty="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  ahead="$(git rev-list --count '@{u}..HEAD' 2>/dev/null)"
  g="${cyan}⎇ ${br}${rst}"
  if [ "${dirty:-0}" -gt 0 ] 2>/dev/null; then g="${g} ${yel}✚${dirty}${rst}"; else g="${g} ${grn}✓${rst}"; fi
  if [ -n "$ahead" ] && [ "$ahead" -gt 0 ] 2>/dev/null; then g="${g} ↑${ahead}"; fi
  line="${line}  ${g}"
fi

# cost + duration segment
if [ -n "$cost" ]; then
  costfmt="$(printf '$%.2f' "$cost" 2>/dev/null)"
  durm=""
  [ -n "$dur_ms" ] && durm="$(awk "BEGIN{printf \"%dm\", ${dur_ms}/60000}" 2>/dev/null)"
  line="${line}${sep}${dim}${costfmt}${durm:+ · $durm}${rst}"
fi

# context-window usage segment (green < 60%, yellow 60–85%, red > 85%)
ctx="$(jget '.context_window.used_percentage')"
if [ -n "$ctx" ]; then
  ctxi="${ctx%%.*}"
  cc="$grn"; [ "${ctxi:-0}" -ge 60 ] 2>/dev/null && cc="$yel"; [ "${ctxi:-0}" -ge 85 ] 2>/dev/null && cc="$red"
  line="${line}${sep}${dim}ctx${rst} ${cc}${ctxi}%${rst}"
fi

# pipeline cockpit segment — populated by /orchestrator on the user's local
# machine (~/.claude/toolbelt-status.json; never written into a project repo).
# Shown only when the status is fresh (< 30 min) and matches the current repo.
st="$HOME/.claude/toolbelt-status.json"
if [ -f "$st" ] && command -v jq >/dev/null 2>&1; then
  s_repo="$(jq -r '.repo // empty' "$st" 2>/dev/null)"
  s_upd="$(jq -r '.updated // 0' "$st" 2>/dev/null)"; s_upd="${s_upd%.*}"
  now="$(date +%s 2>/dev/null)"; cur="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -n "$s_repo" ] && [ "$s_repo" = "$cur" ] && [ $((now - ${s_upd:-0})) -lt 1800 ] 2>/dev/null; then
    sp="$(jq -r '.phase // empty' "$st" 2>/dev/null)"
    spr="$(jq -r '.pr // empty' "$st" 2>/dev/null)"
    sv="$(jq -r '.verdict // empty' "$st" 2>/dev/null)"
    seg="${cyan}◷ ${sp}${rst}"
    [ -n "$spr" ] && seg="${seg} ${dim}PR#${rst}${spr}"
    if [ -n "$sv" ]; then
      case "$sv" in *"DO NOT"*|*BLOCK*) vc="$red";; *FIXES*) vc="$yel";; *SHIP*|*ready*) vc="$grn";; *) vc="$dim";; esac
      seg="${seg} ${vc}${sv}${rst}"
    fi
    line="${line}${sep}${seg}"
  fi
fi

# toolbelt hook state (guard / router / loader / debug)
gs="${grn}●${rst}"; [ "${MAUNGS_TOOLBELT_GUARD:-on}" = "off" ] && gs="${red}○${rst}"
rs="${grn}●${rst}"; [ "${MAUNGS_TOOLBELT_ROUTER:-on}" = "off" ] && rs="${red}○${rst}"
ls="${grn}●${rst}"; [ "${MAUNGS_TOOLBELT_LOADER:-on}" = "off" ] && ls="${red}○${rst}"
# debug telemetry is opt-in (off by default → dim ○); yellow ● = actively recording.
ds="${dim}○${rst}"; dbg_on=0
case "${MAUNGS_TOOLBELT_DEBUG:-off}" in on|1|true|yes|verbose) ds="${yel}●${rst}"; dbg_on=1 ;; esac
line="${line}${sep}${dim}guard${rst} ${gs} ${dim}router${rst} ${rs} ${dim}loader${rst} ${ls} ${dim}debug${rst} ${ds}"

# while recording, append this session's tally — offered ▸ used (from the usage log)
if [ "$dbg_on" = "1" ] && [ -n "$sid" ] && command -v jq >/dev/null 2>&1; then
  tbl="${MAUNGS_TOOLBELT_LOG:-$HOME/.claude/maungs-toolbelt/usage.jsonl}"
  if [ -s "$tbl" ]; then
    tally="$(jq -rs --arg s "$sid" '[.[]|select(.session==$s)] | "\([.[]|select(.event=="suggested")]|length) \([.[]|select(.event=="invoked")]|length)"' "$tbl" 2>/dev/null)"
    tb_off="${tally%% *}"; tb_use="${tally##* }"
    if [ "${tb_off:-0}" -gt 0 ] 2>/dev/null || [ "${tb_use:-0}" -gt 0 ] 2>/dev/null; then
      line="${line} ${dim}${tb_off:-0}▸${tb_use:-0}${rst}"
    fi
  fi
fi

# model
line="${line}${sep}${dim}${model}${rst}"

printf '%s' "$line"
