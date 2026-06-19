#!/usr/bin/env bash
#
# toolbelt-router.sh — UserPromptSubmit hook for Maungs-agentic-toolbelt.
#
# On every prompt, it checks whether the request matches one of the toolbelt's
# capability areas. If so, it injects a SHORT, suggestive note so Claude can
# OFFER the relevant agent/skill. If nothing fits, it stays silent (no tokens,
# no noise).
#
# Safety contract:
#   - It NEVER blocks a prompt (always exits 0; exit 2 would erase the prompt).
#   - It only ADDS context. It cannot run agents itself — Claude (and the user)
#     decide whether to act on the suggestion.
#   - It is read-only: no writes, no network, no side effects.
#   - Disable it any time with:  export MAUNGS_TOOLBELT_ROUTER=off
#
# Read the JSON event on stdin, pull out .prompt, match, suggest, exit 0.

# --- off switch -------------------------------------------------------------
[ "${MAUNGS_TOOLBELT_ROUTER:-on}" = "off" ] && exit 0

input="$(cat 2>/dev/null)"
[ -z "$input" ] && exit 0

# --- extract the prompt text (jq, then python3, then a crude fallback) -------
HAVE_JQ=0
if command -v jq >/dev/null 2>&1; then HAVE_JQ=1; fi

prompt=""
if [ "$HAVE_JQ" = "1" ]; then
  prompt="$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)"
elif command -v python3 >/dev/null 2>&1; then
  prompt="$(printf '%s' "$input" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("prompt",""))
except Exception: pass' 2>/dev/null)"
else
  prompt="$(printf '%s' "$input" | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"\(.*\)"[^"]*}.*/\1/p')"
fi
[ -z "$prompt" ] && exit 0

# lowercase for matching
p="$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]')"

# --- emit: suppressed JSON additionalContext if jq is present, else stdout ---
emit() {
  if [ "$HAVE_JQ" = "1" ]; then
    jq -n --arg c "$1" '{suppressOutput:true,hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
  else
    printf '%s\n' "$1"
  fi
  exit 0
}

m() { printf '%s' "$p" | grep -qE "$1"; }

PREFIX="[Maungs-agentic-toolbelt] An installed toolbelt may help here. Offer the fitting option below to the user (do NOT auto-run workflows that commit/push/open PRs without confirmation). Ignore entirely if it does not fit the actual request."

# --- priority-ordered intent matching (first match wins) --------------------

# 0) Onboard / prep a repo for agentic development
if m 'claude\.?md|agents\.?md|onboard (this|the|my|a|our)|set ?up (this|the|my|a|our)[a-z ]*(repo|codebase|project)|make (this|the|my|our) (repo|codebase|project) agent|agent-ready|prep (this|the|my|a|our) (repo|codebase|project)|bootstrap (the )?(context|repo|project)|generate (a |the )?claude|there.?s no claude|missing (a )?claude|no (claude|agent|ai)[- ]?(context|config|setup)'; then
  emit "$PREFIX
Looks like preparing a repo for agentic development. Consider:
- /agentic-onboard — scans the repo and generates the agent-context files the rest of the toolbelt depends on (CLAUDE.md + AGENTS.md + a concise architecture map). Handles cold repos and refreshes stale/outdated context. Add --deep for a full docs/wiki."
fi

# 1) Security / compliance
if m 'security|secure\b|vulnerab|injection|xss|csrf|sql ?inj|owasp|soc ?2|pci|hipaa|nist|cve\b|secret(s)?\b|credential|encrypt|authn|authz|authoriz|authentic'; then
  emit "$PREFIX
Looks security/compliance-related. Consider:
- @security-reviewer PR <n> — cold security + compliance gate (SOC2/OWASP/PCI/NIST/CWE), ship/no-ship verdict.
- @security-mentor PR <n> — same review but explains the threat model + fix on each finding."
fi

# 2) Code / PR review
if m 'review (this|the|my|that)|pull request|\bpr #?[0-9]|\bpr\b|look over|code review|feedback on (this|my|the) (code|change|diff|pr)|is this (correct|right|safe|good)'; then
  emit "$PREFIX
Looks like a review request. Consider:
- @pr-reviewer PR <n> — fresh-eyes correctness/quality/tenant-safety review with inline comments + a SHIP / SHIP WITH FIXES / DO NOT SHIP verdict.
- @security-reviewer PR <n> — add this if security/compliance matters."
fi

# 3) Bug / defect
if m 'bug\b|broke(n)?\b|not working|does(n.?t| not) work|fail(s|ing|ed)?\b|error\b|exception\b|crash|regression|stack ?trace|traceback|flaky|why (is|does|did|are).*(fail|break|broke|wrong|error)'; then
  emit "$PREFIX
Looks like a bug/defect. Consider:
- /bug-catcher <symptom> — diagnoses the ROOT cause (not the symptom) with a file:line evidence chain, then adversarially verifies it before any fix is planned. It never edits code itself."
fi

# 4) Handoff / resume later
if m 'hand ?off|resume (this|it|later)|pick (this|it) (back )?up|continue (this )?later|context for (the|a|another|the next)|brief for|catch (someone|somebody|a teammate) up'; then
  emit "$PREFIX
Looks like transferring or resuming work. Consider:
- /handoff <issue-id|topic> — drafts a self-contained, drift-aware brief so a zero-context agent (or your future self) can resume cold."
fi

# 5) Chore-sized change
if m 'typo|\bbump\b|upgrade (the |a )?(depend|package|version|lib)|dependency (bump|update|upgrade)|rename (a|the|this|that)|small (fix|change|tweak)|one-?liner|config (change|tweak)|update (the )?(readme|comment|changelog|doc)'; then
  emit "$PREFIX
Looks like a small, single-concern change. Consider:
- /chore <description> — a lightweight PR flow that keeps the commit/push gates but skips the full pipeline. It re-routes to /orchestrator if the task turns out bigger than a chore."
fi

# 6) Understand / document a codebase
if m 'document (the|this)|write (the )?docs|\bwiki\b|how does (the|this).*(work|function)|explain (the|this) (codebase|module|service|system|architecture)|onboard|where (is|does)|walk me through (the|this) (code|repo|codebase)'; then
  emit "$PREFIX
Looks like understanding or documenting a codebase. Consider:
- /wiki-generator — builds/maintains a near-100% technical wiki (per-module analysis, schemas, diagrams, related files) at docs/wiki/. Best when the question is about THIS project's code; ignore for general questions."
fi

# 7) Plan / design / architecture
if m 'plan (this|the|out|a)|design (the|a|this)|architect\b|architecture|approach to|how should (i|we) (build|structure|design|approach)|rfc\b|proposal|spec out|scope (this|the|out)|requirements|acceptance criteria|write (an?|the) issue'; then
  emit "$PREFIX
Looks like planning / scoping / architecture. Consider:
- @architect — front-loads every architectural decision into a vetted plan file before any code is written.
- @product-owner — turns a fuzzy ask into a scoped issue with business-language acceptance criteria (and UI/UX wireframes for user-facing work)."
fi

# 8) Build / implement a feature
if m 'build (an?|the|this|me)|implement|add (an?|the).*(feature|page|endpoint|screen|form|flow|api)|create (an?|the).*(app|feature|service|endpoint|page)|new feature|scaffold|ship (an?|the|this)|develop (an?|the|this)|help me (build|make|create)'; then
  emit "$PREFIX
Looks like building or extending a feature. Consider OFFERING (do not auto-start — these open PRs and push):
- /orchestrator <issue|topic> — runs the full plan -> build -> review -> merge-ready cycle, human-gated at every commit/push.
- @architect — if scope is fuzzy, plan it first.
- @product-owner — if it isn't a scoped issue/requirements yet."
fi

# no match -> silent
exit 0
