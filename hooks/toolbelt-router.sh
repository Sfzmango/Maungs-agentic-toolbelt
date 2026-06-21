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

# --- usage telemetry (opt-in; off unless MAUNGS_TOOLBELT_DEBUG is set) -------
TB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
# shellcheck source=/dev/null
. "${TB_DIR}/lib-telemetry.sh" 2>/dev/null || true

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

# session + cwd, for telemetry (best-effort; empty if jq is absent)
TB_SESSION=""; TB_CWD=""
if [ "$HAVE_JQ" = "1" ]; then
  TB_SESSION="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)"
  TB_CWD="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
fi

# lowercase for matching
p="$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]')"

# --- emit: log the suggestion (opt-in), then surface it to Claude -----------
# Args: <intent-id> <offered-component-slugs,csv> <content>
# The first two feed `/toolbelt metrics`; the third is what Claude actually sees.
emit() {
  if [ "$HAVE_JQ" = "1" ] && command -v tb_debug_on >/dev/null 2>&1 && tb_debug_on; then
    tb_append "$(jq -nc \
      --arg ts "$(tb_now)" --arg intent "$1" --arg offers "$2" \
      --arg session "$TB_SESSION" --arg cwd "$TB_CWD" \
      '{ts:$ts,event:"suggested",kind:"router",intent:$intent,offers:$offers,session:$session,cwd:$cwd}' 2>/dev/null)"
  fi
  if [ "$HAVE_JQ" = "1" ]; then
    jq -n --arg c "$3" '{suppressOutput:true,hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
  else
    printf '%s\n' "$3"
  fi
  exit 0
}

m() { printf '%s' "$p" | grep -qE "$1"; }

PREFIX="[Maungs-agentic-toolbelt] An installed toolbelt may help here. Offer the fitting option below to the user (do NOT auto-run workflows that commit/push/open PRs without confirmation). Ignore entirely if it does not fit the actual request."

# --- priority-ordered intent matching (first match wins) --------------------

# 00) Greenfield / from-scratch build — HIGHEST priority on purpose: it must beat
#     block 0 (onboard), which is for EXISTING repos. A brand-new build has no repo
#     or issue yet, so it routes to the planning agents, which take a free-text topic.
if m 'from scratch|greenfield|from the ground up|build .* from scratch|brand[- ]?new (app|project|site|store|service|repo|codebase|product|business|startup|platform)|new ([a-z-]+ ){0,3}(app|project|repo|codebase|saas|web ?app|website|storefront|startup|platform)'; then
  emit "greenfield" "architect,product-owner,orchestrator" "$PREFIX
Looks like a greenfield / from-scratch build (likely no repo or issue yet). These take a free-text TOPIC — no GitHub repo or issue required:
- @architect — plan the whole build up front from a one-line description; writes a vetted plan with diagrams. The right first step when starting from scratch.
- @product-owner — turn \"build X\" into sequenced milestones + scoped issues with acceptance criteria.
- /orchestrator <topic> — runs the full plan -> build -> review cycle on a free-text topic (no issue needed; add --experiment for a local, no-PR/no-commit dry run). Human-gated at every commit/push."
fi

# 0) Onboard / prep a repo for agentic development
if m 'claude\.?md|agents\.?md|onboard (this|the|my|a|our)|set ?up (this|the|my|a|our)[a-z ]*(repo|codebase|project)|make (this|the|my|our) (repo|codebase|project) agent|agent-ready|prep (this|the|my|a|our) (repo|codebase|project)|bootstrap (the )?([a-z]+ )?(context|repo|project)|generate (a |the )?claude|there.?s no claude|missing (a )?claude|no (claude|agent|ai)[- ]?(context|config|setup)'; then
  emit "onboard" "agentic-onboard" "$PREFIX
Looks like preparing a repo for agentic development. Consider:
- /agentic-onboard — scans the repo and generates the agent-context files the rest of the toolbelt depends on (CLAUDE.md + AGENTS.md + a concise architecture map). Handles cold repos and refreshes stale/outdated context. Add --deep for a full docs/wiki."
fi

# 0c) Personal to-do / tabled work — a private, per-project backlog. Placed HIGH on
#     purpose: "remind me later / table this / add to my backlog" means the user is
#     DEFERRING work, so it must beat the action blocks (bug/build/review) below. The
#     negative guard keeps "build a todo app" out — that's a feature, not a tabled task.
if m '\bbacklog\b|(to-?do|task)s?[ -]?list|table (this|that|it|these|them)|remind me (to|later)|(save|note|jot|stash|park).{0,20}for later|put (this|that|it|them) on (the|my|a) (list|backlog)|add .*to (my|the) (to-?do|todo|backlog|task ?list)|(show|view|see|check|clear|finish|complete) (me )?(my|the) (to-?do|todo)s?|what.?s on (my|the) (to-?do|todo|list)|(keep|make|create|add|jot|new|start) (a |an |my )?(to-?do|todo)\b' \
   && ! m '(build|implement|develop|scaffold|create|make|design|code|program|generate) .{0,25}(to-?do|todo|task).{0,18}(app|application|feature|component|page|api|crud|module|service|widget|website|site|clone|tool|program|software|system|board|tracker|manager|ui|frontend|backend)'; then
  emit "todo" "todo" "$PREFIX
Looks like tabling work for a later session. Consider:
- /todo <text> — saves it to your private, per-project backlog (stored locally at ~/.claude/maungs-toolbelt/todos/, never committed to the repo). /todo alone lists what you've tabled; /todo done <id> / /todo drop <id> manage it. It only records — turning a todo into work is a separate step you take later."
fi

# 0b) Schema / data migration
#     Guard: the loose "add/drop/rename column" triggers also match UI grid/table
#     columns; exclude clear frontend phrasings so a UI task isn't routed here.
if m 'migrat(e|ion|ing)|schema change|alter table|add (a |the )?[a-z_-]* ?column|drop (a |the )?[a-z_-]* ?(column|table)|rename (a |the )?[a-z_-]* ?column|backfill|change the (db|database|schema)|new migration' \
   && ! m 'data ?grid|datagrid|table component|grid component|ag-?grid|react[- ]?table|css|tailwind|flexbox'; then
  emit "migration" "migration-planner" "$PREFIX
Looks like a database/schema migration. Consider:
- /migration-planner — a read-only pre-flight that produces a risk dossier BEFORE the migration is written: data-loss + lock/downtime risks, a backfill + expand/contract rollout, and a rollback plan. It never writes the migration itself."
fi

# 1) Security / compliance
if m 'security|secure\b|vulnerab|injection|xss|csrf|sql ?inj|owasp|soc ?2|pci|hipaa|nist|cve\b|secret(s)?\b|credential|encrypt|authn|authz|authoriz|authentic'; then
  emit "security" "security-reviewer,security-mentor" "$PREFIX
Looks security/compliance-related. Consider:
- @security-reviewer PR <n> — cold security + compliance gate (SOC2/OWASP/PCI/NIST/CWE), ship/no-ship verdict.
- @security-mentor PR <n> — same review but explains the threat model + fix on each finding."
fi

# 2) Code / PR review
if m 'review (this|the|my|that)|pull request|\bpr #?[0-9]|\bpr\b|look over|code review|feedback on (this|my|the) (code|change|diff|pr)|is this[a-z ]* (correct|right|safe|good)'; then
  emit "review" "pr-reviewer,security-reviewer" "$PREFIX
Looks like a review request. Consider:
- @pr-reviewer PR <n> — fresh-eyes correctness/quality/tenant-safety review with inline comments + a SHIP / SHIP WITH FIXES / DO NOT SHIP verdict.
- @security-reviewer PR <n> — add this if security/compliance matters."
fi

# 2b) Translate / port code between languages (read-only context). Scoped to a
#     programming-language target so "translate this to French" stays silent.
if m 'translate .*(to|into) (ruby|rails|python|django|flask|fastapi|node|express|java|javascript|typescript|go|golang|rust|php|laravel|kotlin|swift|scala|elixir|phoenix|c\+\+|c#|dotnet)|(port|convert|rewrite)(ing|s)? .*(to|into|in) (ruby|rails|python|django|flask|fastapi|node|express|java|javascript|typescript|go|golang|rust|php|laravel|kotlin|swift|scala|elixir|phoenix|c\+\+|c#|dotnet)|from (ruby|rails|python|django|flask|fastapi|node|express|java|javascript|typescript|go|golang|rust|php|laravel|kotlin|swift|scala|elixir|phoenix|c\+\+|c#|dotnet) .*(to|into)'; then
  emit "translate" "code-translator" "$PREFIX
Looks like translating / porting code between languages. Consider:
- @code-translator — read-only: fetches the real docs for BOTH languages first, then returns a doc-grounded translation bundle (translated code + a cited idiom map + caveats) for you or the /orchestrator flow. It writes nothing; it only provides grounded context."
fi

# 3) Bug / defect
#     Guard: "error" is also a feature noun ("add error handling", "build an error
#     page"). Exclude when a build verb governs an error feature, so a build task
#     isn't routed here. Symptom phrasings ("the error page is broken", "I get an
#     error") still match because they carry no build verb.
if m 'bug\b|broke(n)?\b|not working|n.?t work|does(n.?t| not) work|fail(s|ing|ed)?\b|error\b|exception\b|crash|regression|stack ?trace|traceback|flaky|why (is|does|did|are).*(fail|break|broke|wrong|error)' \
   && ! m 'add (an? )?error|add (a |an )?(toast|banner|alert|modal|spinner|skeleton|loader)|(build|implement|create|need|want|design|adding) (an? )?error[- ]?(handling|page|boundary|screen|state|view|message|toast|banner)'; then
  emit "bug" "bug-catcher" "$PREFIX
Looks like a bug/defect. Consider:
- /bug-catcher <symptom> — diagnoses the ROOT cause (not the symptom) with a file:line evidence chain, then adversarially verifies it before any fix is planned. It never edits code itself."
fi

# 3b) Author tests
if m 'write (a |unit |some |more )?tests?|add ([a-z]+ ){0,4}tests?|test coverage|missing tests?|cover .* with (a )?tests?|need (more )?tests?|test cases? for'; then
  emit "tests" "test-author" "$PREFIX
Looks like adding test coverage. Consider:
- @test-author — authors tests (especially the negative-path/edge cases the happy path misses), runs them against the project's real test runner, and never weakens an assertion to pass. Read-only on source; writes only test files."
fi

# 4) Handoff / resume later
if m 'hand ?off|resume (this|it|later)|pick (this|it) (back )?up|continue (this )?later|context for (the|a|another|the next)|brief for|catch (someone|somebody|a teammate) up'; then
  emit "handoff" "handoff" "$PREFIX
Looks like transferring or resuming work. Consider:
- /handoff <issue-id|topic> — drafts a self-contained, drift-aware brief so a zero-context agent (or your future self) can resume cold."
fi

# 4b) Release notes / changelog / deploy summary
if m 'release notes?|changelog|cut a release|prepare (a |the )?release|draft (the )?release|deploy(ment)? (comment|notes|description|summary)|what.?s in (this|the) (release|deploy)|release summary'; then
  emit "release-notes" "release-notes" "$PREFIX
Looks like preparing release notes or a deploy summary. Consider:
- /release-notes — generates grouped release notes (features / fixes / breaking / migrations) from a commit range or PRs, with a SemVer bump recommendation. Read-only (outputs text; never tags or posts). Add --format deploy-comment to enrich a deployment comment."
fi

# 5) Chore-sized change
if m 'typo|\bbump\b|upgrade (the |a )?([a-z]+ )?(depend|package|version|lib|gem)|dependency (bump|update|upgrade)|rename (a|the|this|that)|small (fix|change|tweak)|one-?liner|(tweak|edit|change|update) (the )?([a-z]+ )?config|config (change|tweak)|update (the |a )?([a-z]+ )?(readme|comment|changelog|doc)'; then
  emit "chore" "chore" "$PREFIX
Looks like a small, single-concern change. Consider:
- /chore <description> — a lightweight PR flow that keeps the commit/push gates but skips the full pipeline. It re-routes to /orchestrator if the task turns out bigger than a chore."
fi

# 6) Understand / document a codebase
if m 'document (the|this)|write (the )?docs|\bwiki\b|how does (the|this).*(work|function)|explain (the|this) (codebase|module|service|system|architecture)|where (is|does)|walk me through (the|this) (code|repo|codebase)'; then
  emit "document" "wiki-generator" "$PREFIX
Looks like understanding or documenting a codebase. Consider:
- /wiki-generator — builds/maintains a near-100% technical wiki (per-module analysis, schemas, diagrams, related files) at docs/wiki/. Best when the question is about THIS project's code; ignore for general questions."
fi

# 7) Plan / design / architecture
if m 'plan (this|the|out|a)|design (the|a|this)|architect\b|architecture|approach to|how should (i|we) (build|structure|design|approach)|rfc\b|proposal|spec out|scope (this|the|out)|requirements|acceptance criteria|write (an?|the) issue'; then
  emit "plan" "architect,product-owner" "$PREFIX
Looks like planning / scoping / architecture. Consider:
- @architect — front-loads every architectural decision into a vetted plan file before any code is written.
- @product-owner — turns a fuzzy ask into a scoped issue with business-language acceptance criteria (and UI/UX wireframes for user-facing work)."
fi

# 7b) What can the toolbelt do (meta / discovery)
if m 'what can (this|the|your|you).*(toolbelt|do|help)|what (tools|agents|skills|commands|components) (do|are|does|can|you)|which (component|agent|skill|tool|command)|what.?s in (the|your) toolbelt|list (the )?([a-z]+ )?(agents|skills|tools|components|commands)|toolbelt (help|status|inventory)'; then
  emit "meta" "toolbelt" "$PREFIX
Looks like a question about the toolbelt itself. Consider:
- /toolbelt — lists the full inventory, recommends the best component for a stated goal, and shows status (router state, MCP servers, whether a CLAUDE.md exists)."
fi

# 8) Build / implement a feature
if m 'build (an?|the|this|me)|implement\b|add (an?|the).*(feature|page|endpoint|screen|form|flow|api|component|button|modal)|create (an?|the).*(app|feature|service|endpoint|page|screen|form|flow|component)|new feature|scaffold|ship (an?|the|this)|develop (an?|the|this)|help me (build|make|create)'; then
  emit "build" "orchestrator,architect,product-owner" "$PREFIX
Looks like building or extending a feature. Consider OFFERING (do not auto-start — these open PRs and push):
- /orchestrator <issue|topic> — runs the full plan -> build -> review -> merge-ready cycle, human-gated at every commit/push.
- @architect — if scope is fuzzy, plan it first.
- @product-owner — if it isn't a scoped issue/requirements yet."
fi

# no match -> silent
exit 0
