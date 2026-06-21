#!/usr/bin/env python3
"""
Unit test for the prompt router hook (hooks/toolbelt-router.sh).

Drives the REAL router script with a large labeled corpus of prompts and asserts
each routes to the intended toolbelt component (or stays silent). Run with:

    python3 tests/test_router.py

Exits 0 if every prompt routes as expected, 1 otherwise (CI-friendly). Each case is
(prompt, expected) where expected is a single label OR a set of acceptable labels.
Labels are the router's intent blocks; "SILENT" means the router emits nothing.
Most cases are template-expanded (label-correct by construction); the rest are
hand-authored edge / mis-route / priority / negative cases.
"""
import os, sys, json, subprocess, itertools, collections, argparse

ROUTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "toolbelt-router.sh")

# Exact "Looks like ..." lead phrases each block emits -> canonical label.
LEADS = {
    "Looks like a greenfield / from-scratch build": "greenfield",
    "Looks like preparing a repo for agentic development": "onboard",
    "Looks like a database/schema migration": "migration",
    "Looks security/compliance-related": "security",
    "Looks like a review request": "review",
    "Looks like a bug/defect": "bug",
    "Looks like adding test coverage": "tests",
    "Looks like transferring or resuming work": "handoff",
    "Looks like preparing release notes or a deploy summary": "release",
    "Looks like a small, single-concern change": "chore",
    "Looks like understanding or documenting a codebase": "document",
    "Looks like planning / scoping / architecture": "plan",
    "Looks like a question about the toolbelt itself": "meta",
    "Looks like building or extending a feature": "build",
    "Looks like translating / porting code between languages": "translate",
    "Looks like tabling work for a later session": "todo",
}

def fired(out):
    for phrase, label in LEADS.items():
        if phrase in out:
            return label
    return "SILENT"

cases = []  # (prompt, expected) ; expected = str or set of acceptable labels
def add(label, prompts):
    for p in prompts:
        cases.append((p, label))

# ---------------- template expansion (label-correct by construction) ----------
def expand(tmpl, slots):
    keys = list(slots)
    for combo in itertools.product(*[slots[k] for k in keys]):
        yield tmpl.format(**dict(zip(keys, combo)))

# greenfield
add("greenfield", expand("build a {t} from scratch", {"t":["merch store","blog","SaaS app","booking site","portfolio site","recipe app"]}))
add("greenfield", expand("start a new {t} project", {"t":["ecommerce","analytics","chat","crm","inventory"]}))
add("greenfield", expand("create a new repo for a {t}", {"t":["todo app","storefront","marketing site","dashboard"]}))
add("greenfield", expand("spin up a new {t} app", {"t":["payments","scheduling","notes","fitness"]}))
add("greenfield", ["I want to create a new repo and build an ecommerce app from scratch selling merch",
                   "let's build a brand new storefront for digital downloads",
                   "from the ground up, build a website for a restaurant",
                   "start a brand new product for invoicing",
                   "scaffold a new storefront from scratch"])
# build (in-repo feature; NO greenfield cue)
add("build", expand("add a {f} page to the app", {"f":["checkout","search","profile","settings","pricing"]}))
add("build", expand("implement a {f} endpoint", {"f":["webhook","export","login","upload"]}))
add("build", expand("build a {f} feature", {"f":["analytics","dark mode","filtering","tagging"]}))
add("build", expand("create a {f} screen", {"f":["order history","admin","onboarding"]}))
add("build", ["scaffold a component for the cart","ship a password reset flow","develop a recommendation widget",
              "help me build a CSV import","add an api for notifications"])
# security
add("security", expand("is the {x} secure", {"x":["login flow","payment flow","admin api","session handling"]}))
add("security", expand("check {x} for vulnerabilities", {"x":["this endpoint","the upload handler","our auth"]}))
add("security", ["review the security of our authentication","do we have any XSS holes","check for SQL injection here",
                 "is this PR OWASP compliant","we need a SOC2 review of this","are there hardcoded secrets",
                 "PCI compliance check for the payment code","is this CSRF protected","audit the authz on this controller"])
# review
add("review", expand("{v} this PR", {"v":["review","look over","can you check","give feedback on"]}))
add("review", expand("review {x}", {"x":["my pull request","PR 218","this diff","the changes in this branch"]}))
add("review", ["is this implementation correct","look over this change before I merge","code review for my latest commit"])
# bug
add("bug", expand("the {x} is broken", {"x":["checkout","login","cart","search","dashboard"]}))
add("bug", expand("{x} isn't working", {"x":["sign up","payment","file upload","export"]}))
add("bug", ["this test keeps failing","I'm getting a 500 error on submit","the app crashes on startup",
            "why does the payment fail intermittently","there's a regression after the last deploy",
            "here's a stack trace, what's wrong","this spec is flaky in CI","orders aren't saving, something is broken"])
# tests
add("tests", expand("write tests for the {x}", {"x":["user model","cart","order service","discount logic"]}))
add("tests", expand("add unit tests for {x}", {"x":["the validator","auth","the api"]}))
add("tests", ["we're missing tests for checkout","improve test coverage for payments","add edge case tests for the parser",
              "need more tests for the webhook handler","add negative tests for the form"])
# handoff
add("handoff", ["write a handoff for this work","I need to resume this later","create a brief so someone can pick this up",
                "hand off the invitations feature","context for the next agent","catch a teammate up on this",
                "draft a handoff document","pick this back up tomorrow, give me a brief","continue this later, write a summary"])
# release
add("release", ["generate release notes","write a changelog for this release","cut a release","prepare the release notes for v2",
                "draft the deploy summary","what's in this release","release summary for the team",
                "changelog since the last tag","deployment notes for this push"])
# chore
add("chore", ["fix a typo in the README","bump the lodash version","upgrade the rails dependency","rename this variable",
              "small config change to eslint","update a stale comment","one-liner fix for the footer","dependency bump for axios",
              "rename the helper function","tweak the prettier config","update the readme install steps"])
# document
add("document", ["document this codebase","write docs for the API","build a wiki for the repo","how does the auth system work",
                 "explain this module","walk me through the codebase","where is the payment logic","explain the architecture of this app",
                 "generate a wiki","write the docs for our services"])
# plan
add("plan", ["help me plan this feature","design the data model for orders","what's the architecture for a notifications system",
             "how should we structure the payments module","write an RFC for the new search","scope out the reporting feature",
             "draft a proposal for caching","spec out the messaging feature","what are the requirements for checkout",
             "write an issue for the dashboard","plan the approach for multi-tenancy"])
# migration
add("migration", expand("add a column to the {x} table", {"x":["users","orders","products","members"]}))
add("migration", ["I need a database migration","drop the legacy_id column","rename the email column","backfill the new field",
                  "change the database schema for soft deletes","write a new migration to add indexes","alter table orders to add status",
                  "schema change to split the name field","add a not-null column to members"])
# meta
add("meta", ["what can this toolbelt do","which agent should I use","what's in your toolbelt","list the available skills",
             "toolbelt status","what tools do you have","which skill fits my goal","show me the toolbelt inventory"])
# onboard
add("onboard", ["onboard this repo","set up this codebase for agents","generate a CLAUDE.md for my project",
                "there's no claude.md here","make this repo agent-ready","prep this project for agentic work",
                "bootstrap the agent context","create an AGENTS.md","this repo is missing a claude.md","onboard my existing repo"])

# translate / port code between languages (the @code-translator intent)
add("translate", ["translate this ruby file to python", "port the rails service to fastapi",
                  "convert this javascript to typescript", "rewrite this python script in go",
                  "translate from rails to django", "convert my express app to fastapi",
                  "translate this go code into rust", "port this java class to kotlin"])

# todo / tabled work (the /todo private-backlog intent) — placed HIGH so a tabling
# phrasing beats the action blocks (bug/build/review) it might otherwise overlap.
add("todo", ["add a new readme section to my todo list", "remind me to refactor the auth module later",
             "table this for later", "put this on my backlog", "add 'write integration tests' to my todo list",
             "what's on my todo list", "show my todos", "save this idea for later", "note this down for later",
             "add the export feature to my backlog", "remind me later to bump the dependencies",
             "make a todo to revisit the caching strategy"])

# ---------------- regression / mis-route fixes (the bugs we just fixed) -------
# greenfield must beat onboard
add("greenfield", ["set up a new project from scratch","set up a new rails project","start a new codebase for a chat app"])
# error-as-feature must NOT route to bug (build or silent both acceptable; NOT bug)
for p in ["add error handling to the checkout flow","build an error page for 404s","implement an error boundary in react",
          "add a toast for error messages","add an error banner to the upload screen"]:
    cases.append((p, {"build","SILENT"}))
# "design X" legitimately routes to plan (block 7), like "design the data model"
cases.append(("design an error state for the form", {"build","SILENT","plan"}))
# UI column must NOT route to migration
for p in ["add a column to the data grid","add a column to the react-table","add a column to the dashboard layout with tailwind",
          "add a column to the css grid"]:
    cases.append((p, {"build","SILENT"}))

# ---------------- priority/ambiguity (expected reflects first-match-wins) -----
cases.append(("review this PR for security issues", "security"))   # security(1) beats review(2)
cases.append(("plan a new app from scratch", "greenfield"))        # greenfield(00) beats plan
cases.append(("build a new SaaS from scratch", "greenfield"))
cases.append(("fix the bug and also write tests", "bug"))          # bug(3) beats tests(3b)
cases.append(("review the architecture of this proposal", "review")) # review(2) beats plan(7)
cases.append(("the migration keeps failing in CI", {"migration","bug"}))  # migration(0b) wins; bug acceptable
cases.append(("remind me to fix the login bug later", "todo"))     # todo(0c) beats bug(3): tabling, not debugging now
cases.append(("add 'review PR 5' to my todo list", "todo"))        # todo(0c) beats review(2): tabling a review
cases.append(("build a todo list app", {"build"}))                 # NOT todo — building a feature; guard routes to build
cases.append(("create a task management app", {"build"}))          # NOT todo — feature build, not a tabled task

# ---------------- known out-of-scope gaps (documented, expected SILENT) -------
for p in ["refactor the auth module","refactor this messy function","audit the codebase for performance",
          "audit our dependencies"]:
    cases.append((p, {"SILENT"}))   # refactor/audit intentionally not routed in this scope

# ---------------- negatives: must stay SILENT --------------------------------
add("SILENT", ["what's the capital of France","explain how TCP works","thanks, that's helpful","what time is it",
               "tell me a joke","what's the weather today","translate this sentence to French","who won the world cup",
               "recommend a good book","what's 2+2","how are you doing","what's the difference between TCP and UDP",
               "explain quantum computing simply","write a poem about the ocean","what should I eat for lunch",
               "is it going to rain tomorrow","help me write an email to my boss","give me a recipe for pasta",
               "what's a good name for a cat","summarize this article for me","convert 10 miles to kilometers",
               "define photosynthesis","what's the population of Japan","suggest a workout routine"])

# ---------------- run -------------------------------------------------------
ap = argparse.ArgumentParser(description="Prompt-router regression test (drives hooks/toolbelt-router.sh).")
ap.add_argument("-v", "--verbose", action="store_true",
                help="print every case (pass AND fail), grouped by expected intent")
ARGS = ap.parse_args()

results = []
for p, exp in cases:
    out = subprocess.run(["bash", ROUTER], input=json.dumps({"prompt": p}),
                         capture_output=True, text=True).stdout
    got = fired(out)
    exp_set = exp if isinstance(exp, (set, list, tuple)) else {exp}
    results.append((got in exp_set, p, exp_set, got))

total = len(results)
passed = sum(1 for r in results if r[0])
intents = sorted(set(LEADS.values())) + ["SILENT"]

print("PROMPT ROUTER REGRESSION")
print(f"  router under test : {os.path.relpath(ROUTER)}")
print(f"  intents under test: {', '.join(intents)} ({len(intents)} labels)")
print(f"  corpus            : {total} labeled prompts\n")
print(f"TOTAL PROMPTS: {total}    PASS: {passed}    FAIL: {total-passed}    ({100*passed//total}%)\n")

# per-case detail (pass AND fail), grouped by expected intent — only under -v
if ARGS.verbose:
    by = collections.defaultdict(list)
    for ok, p, exp, got in results:
        by["/".join(sorted(exp))].append((ok, p, got))
    print("PER-CASE (grouped by expected intent; what was passed → what the router returned):")
    for key in sorted(by):
        rows = by[key]
        g = sum(1 for r in rows if r[0])
        print(f"\n  [{key}]  {g}/{len(rows)}")
        for ok, p, got in rows:
            sym = "✓" if ok else "✗"
            word = "PASS" if ok else "FAIL"
            print(f"    {sym} {word}  passed={p!r}  expected={key}  returned={got}")
    print()

# per-expected-category accuracy (always)
bycat = collections.defaultdict(lambda: [0,0])
for ok,p,exp,got in results:
    key = "/".join(sorted(exp))
    bycat[key][0]+=1; bycat[key][1]+= (1 if ok else 0)
print("PER-EXPECTATION:")
for k in sorted(bycat):
    n,g = bycat[k]
    sym = "✓" if g == n else "✗"
    print(f"  {sym} {k:28} {g}/{n}")

fails = [r for r in results if not r[0]]
print(f"\nFAILURES ({len(fails)}):")
if not fails:
    print("  (none)")
for ok,p,exp,got in fails:
    print(f"  ✗ expected={'/'.join(sorted(exp)):20} got={got:10} | {p}")

print(f"\nRESULT: {'PASS' if not fails else 'FAIL'}  ({passed}/{total} prompts routed as expected)")
sys.exit(0 if not fails else 1)
