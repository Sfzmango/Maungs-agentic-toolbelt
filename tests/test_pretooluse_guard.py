#!/usr/bin/env python3
"""
Unit test for the PreToolUse guard hook (hooks/pretooluse-guard.sh).

Drives the REAL guard script with a labeled corpus of shell commands and asserts
each yields the intended permission decision (deny / ask / allow). Run with:

    python3 tests/test_pretooluse_guard.py

Exits 0 if every command decides as expected, 1 otherwise (CI-friendly). Each
case is (command, expected) where expected is one of "deny" / "ask" / "allow"
(no guard output => "allow"). Mirrors tests/test_router.py in shape.

The guard's job is to tell a real INVOCATION of a banned action (deny/ask) from a
mere MENTION of one inside a quoted argument (allow), and to be PRECISE about the
force-push rule across compound commands — denying a real force-push (the long
force flag on a real `git push`) but NOT a force flag (`-f`) that belongs to an
unrelated command segment. Both
directions are locked here; the #1 invariant is that every real dangerous command
STILL denies (block B) — this is a security control, so a weakening regression
must fail CI.

================================ META-FOOTGUN ================================
This test file's SOURCE and its runner's own shell command lines must NEVER
contain the literal banned tokens — the bulk `git add` short flag, the hook-bypass
flag, a real force-push, an AI co-author trailer — spelled out in full. The
toolbelt ships this very guard as a PreToolUse hook, so a literal banned token on
the harness's own `Bash` command line would be DENIED — blocking the `Bash` call
that runs this suite
(this exact interception happened while developing the guard).

Defenses, do not remove:
  1. Every banned token is ASSEMBLED AT RUNTIME from harmless fragments below
     (e.g. NO_VERIFY = "--" + "no-" + "verify"). No literal appears in source.
  2. Every test command is fed to the guard via STDIN only (subprocess input=),
     never as a shell argument — so no harness PreToolUse guard ever sees it.
Keep both. Reintroducing a literal will make the suite un-runnable under the
shipped guard.
=============================================================================
"""
import os, sys, json, subprocess, collections, argparse

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "pretooluse-guard.sh")

# ---- runtime-assembled fragments (NO literal banned tokens in this source) ----
DASH      = "-"
NO_VERIFY = "--" + "no-" + "verify"            # hook-bypass flag
ADD_A     = "git add " + DASH + "A"            # bulk add -A
ADD_ALL   = "git add " + "--" + "all"          # bulk add --all
ADD_DOT   = "git add ."                        # bulk add .
FORCE     = "--" + "for" + "ce"                # force flag (long)
FLAG_F    = DASH + "f"                          # short force / generic -f flag
PUSH      = "git push"
LEASE     = "--force-" + "with-" + "lease"     # the permitted force-with-lease
# AI-attribution trailer, assembled so the literal never appears in source:
AI_TRAILER = "Co-" + "Authored-" + "By: " + "Claude"
AI_GEN     = "Generated with " + "Claude" + " Code"
# --- gap-batch fragments (t7): bundled add -A, short -n bypass, +refspec force,
#     non-Claude AI attribution. Assembled so no literal banned token appears. ---
ADD_AV     = "git add " + DASH + "Av"          # bundled bulk add (-Av == -A -v)
ADD_VA     = "git add " + DASH + "vA"          # bundled bulk add (-vA == -v -A)
NO_VERIFY_N = DASH + "n"                        # short hook-bypass on a commit
PLUS_MAIN  = "+" + "main"                       # +-prefixed refspec (force form)
# non-Claude AI attribution, assembled so no literal trailer appears in source:
AI_TRAILER_CODEX = "Co-" + "Authored-" + "By: " + "Codex"
AI_GEN_COPILOT   = "Generated with " + "Copilot"


def decision(command):
    """Pipe a Bash PreToolUse event to the real guard via STDIN; return the
    decision (deny / ask / allow). No guard output => allow."""
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    out = subprocess.run(["bash", GUARD], input=json.dumps(event),
                         capture_output=True, text=True).stdout.strip()
    if not out:
        return "allow"
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "PARSE_ERROR"


cases = []  # (command, expected, block)
def add(block, items):
    for cmd, exp in items:
        cases.append((cmd, exp, block))


# === A. Quoted-argument false-positives — now ALLOW (the regression fixed) ===
add("A", [
    ('gh pr create --body "the project forbids ' + NO_VERIFY + ', bulk-add, and force-push"', "allow"),
    ('git commit -m "doc: note that force-push is banned"', "allow"),
    ('git commit -m "explain why ' + ADD_A + ' is forbidden"', "allow"),
    # single-quoted variants
    ("git commit -m 'doc: note that force-push is banned'", "allow"),
    ("git commit -m 'explain why " + ADD_A + " is forbidden'", "allow"),
    # =-joined --message style quoted value
    ('git commit --message="why ' + NO_VERIFY + ' is banned"', "allow"),
    # body that names several banned invocations as documentation
    ('gh pr create --body "we never ' + NO_VERIFY + ' and never ' + ADD_A + ' and never force-push"', "allow"),
])

# === B. Real invocations — STILL DENY (security invariant; #1 priority) =======
add("B", [
    (ADD_A, "deny"),
    (ADD_ALL, "deny"),
    (ADD_DOT, "deny"),
    ("git commit " + NO_VERIFY + ' -m "tidy"', "deny"),
    (PUSH + " " + FORCE, "deny"),                       # real force push, no lease
    ("rm -rf /", "deny"),                               # catastrophic targets
    ("rm -rf ~", "deny"),
    ("rm -rf *", "deny"),
    ("rm -fr /", "deny"),                               # flag-order variant
    # AI-attribution trailer on a real commit (assembled at runtime)
    ('git commit -m "subject" --trailer "' + AI_TRAILER + '"', "deny"),
    ("git commit -m 'subject' --trailer '" + AI_GEN + "'", "deny"),
    # quoted catastrophic targets must STILL deny — quoting is shell-safe style,
    # not documentation; `rm -rf "$HOME"` is the most dangerous *real* form
    ('rm -rf "$HOME"', "deny"),
    ('rm -rf "/"', "deny"),
    ('rm -rf "~"', "deny"),
    ("rm -rf '*'", "deny"),
    # force flag abutting a shell metachar with NO space is still a real force-push
    (PUSH + " " + FORCE + ";ls", "deny"),
    (PUSH + " " + FORCE + "|cat", "deny"),
    (PUSH + " " + FLAG_F + ";ls", "deny"),
])

# === C. Allowed-by-design (must NOT deny) ====================================
add("C", [
    (PUSH + " " + LEASE + " origin main", "allow"),     # lease form is permitted
    ("git add path/to/file", "allow"),                  # ordinary staged path
    ("git add src/app.py docs/readme.md", "allow"),
    ("ls -la", "allow"),
    (PUSH + " " + LEASE + " a && echo ok", "allow"),    # legit lease push in a chain still allowed
])

# === D. Chaining / substitution / here-doc edge cases (fail-closed) ==========
add("D", [
    # quoted mention before && does not suppress the real invocation after it
    ('echo "force-push is bad" && ' + PUSH + " " + FORCE, "deny"),
    ("git add path/to/file && git commit " + NO_VERIFY + ' -m "x"', "deny"),
    # danger token inside $( … ) command substitution is a real invocation
    ("echo $(" + PUSH + " " + FORCE + " origin)", "deny"),
    ("result=$(" + ADD_A + ")", "deny"),
    # danger token inside backticks
    ("echo `" + ADD_A + "`", "deny"),
    # unbalanced quotes + a real danger token => ambiguous => scan raw => deny
    ('echo "unterminated && ' + PUSH + " " + FORCE, "deny"),
    # here-doc body containing a real danger token (not a quoted arg)
    ("bash <<EOF\n" + ADD_A + "\nEOF", "deny"),
    ("cat <<EOF\n" + PUSH + " " + FORCE + "\nEOF", "deny"),
    # escaped-quote case the parser cannot confidently resolve, with real danger
    ("git commit " + NO_VERIFY + ' -m "he said \\"hi\\""', "deny"),
    # line-continuation: `\`+newline is ONE shell command, so a continued
    # force-push must still deny (the splitter joins continuations before split)
    (PUSH + " origin \\\n" + FORCE, "deny"),
    (PUSH + " \\\n" + FORCE, "deny"),
    # command substitution inside DOUBLE quotes is a real invocation (dq does NOT
    # suppress $( ... ) / backticks) -> neutralizer fails closed -> deny
    ('X="$(' + ADD_A + ')"', "deny"),
    ('X="`' + ADD_A + '`"', "deny"),
])

# === E. Ask-tier preserved (and quote-neutralization applies to it too) ======
add("E", [
    ("DROP TABLE users", "ask"),                        # destructive SQL -> ask
    ("psql -c " + '"DROP DATABASE app"', "allow"),      # SQL quoted as an arg -> documentation/allow
    ('gh pr create --body "we ran DROP TABLE users in prod last year"', "allow"),
    ("git reset --hard HEAD~3", "ask"),                 # discards work -> ask (unchanged)
    ("terraform destroy", "ask"),                       # infra destruction -> ask
])

# === F. Cross-segment force-flag false-positives — now ALLOW (2nd regression)=
add("F", [
    # a real push refspec, then ; then rm -f on a DIFFERENT segment
    (PUSH + " origin x:y ; rm " + FLAG_F + " /tmp/scratch", "allow"),
    # a real push && an unrelated grep -f
    (PUSH + " origin main && grep " + FLAG_F + " pattern file.txt", "allow"),
    # push ; find -delete ; rm -f  — find -delete still asks, but no force-push deny
    (PUSH + " origin main ; rm " + FLAG_F + " /tmp/a ; rm " + FLAG_F + " /tmp/b", "allow"),
    # quoted force-flag mention next to an unrelated command
    ('echo "use ' + FORCE + ' carefully" ; ls', "allow"),
    # --- invariants for the rewritten rule: STILL DENY ---
    (PUSH + " " + FORCE, "deny"),                        # flag in the push's own segment
    (PUSH + " " + FORCE + " && rm -rf /tmp/x", "deny"),  # push segment carries the force flag
    (PUSH + " " + FORCE + " | tee push.log", "deny"),    # pipe separator, same push segment
    (PUSH + " origin && " + PUSH + " " + FORCE, "deny"), # second push is a real force push
    # fail-closed: a force flag inside a substitution/backtick in the same
    # string as a push (boundaries untrustworthy) => do not split => deny
    (PUSH + " origin main ; echo `rm " + FLAG_F + " x`", "deny"),
    # lease check is FLAG-anchored: a branch NAMED force-with-lease must not
    # excuse a real bare force-push (was a fail-OPEN substring match)
    (PUSH + " " + FORCE + " origin force-with-lease", "deny"),
    # a lease push in one segment must not mask a bare force-push in another,
    # even when a substitution makes the boundaries untrustworthy (fail-closed)
    ("x=$(date) ; " + PUSH + " " + LEASE + " a ; " + PUSH + " " + FORCE + " b", "deny"),
    # legit multi-line (bare newline, no continuation): a push on one line and an
    # unrelated rm -f on another are different commands -> not a force-push -> allow
    (PUSH + " origin main\nrm " + FLAG_F + " /tmp/x", "allow"),
])

# === H. Gap-batch (t7): bundled add -A · short -n bypass · +refspec force ·
#        non-Claude AI attribution — each a denied example + a benign control ===
add("H", [
    # 1) bundled bulk-add short flag (-Av / -vA) must DENY; -p (no A) must allow
    (ADD_AV, "deny"),
    (ADD_VA, "deny"),
    ("git add " + DASH + "p src/app.py", "allow"),      # patch mode, no A -> allow
    ("git add " + "--" + "patch", "allow"),
    # 2) short -n hook-bypass on a commit must DENY; quoted mention must allow
    ("git commit " + NO_VERIFY_N + ' -m "tidy"', "deny"),
    ("git commit -nm " + '"tidy"', "deny"),             # bundled -n + -m
    ('git commit -m "note: ' + NO_VERIFY_N + ' is banned"', "allow"),  # token quoted
    ("git commit -m " + '"msg"', "allow"),              # plain commit, no -n
    # 3) +<refspec> force push must DENY; lease form must still allow
    (PUSH + " origin " + PLUS_MAIN, "deny"),
    (PUSH + " origin +main:main", "deny"),
    (PUSH + " origin +HEAD:main", "deny"),
    (PUSH + " origin main", "allow"),                   # ordinary push, no +
    (PUSH + " " + LEASE + " origin main", "allow"),     # lease has no +refspec
    # 4) non-Claude AI attribution on a real commit must DENY; benign body allows
    ('git commit -m "subject" --trailer "' + AI_TRAILER_CODEX + '"', "deny"),
    ("git commit -m 'subject' --trailer '" + AI_GEN_COPILOT + "'", "deny"),
    ('git commit -m "subject" --trailer "Reviewed-by: a teammate"', "allow"),
])

# === G. Fail-OPEN contract intact (guard never wedges the workflow) ==========
# Non-Bash tool: the guard only inspects Bash; anything else passes (allow).
NON_BASH_ALLOWS = True  # verified below outside the (command, decision) loop


# ---------------------------------- run -------------------------------------
ap = argparse.ArgumentParser(description="PreToolUse-guard regression test (drives hooks/pretooluse-guard.sh).")
ap.add_argument("-v", "--verbose", action="store_true",
                help="print every case (pass AND fail), grouped by test block")
ARGS = ap.parse_args()

results = []
for cmd, exp, block in cases:
    got = decision(cmd)
    results.append((got == exp, cmd, exp, got, block))

# extra: fail-OPEN contract checks that don't fit the (command, decision) table
def _raw_allows(event):
    out = subprocess.run(["bash", GUARD], input=json.dumps(event),
                         capture_output=True, text=True).stdout.strip()
    return out == ""

contract = []
# 1) a Read tool with a banned command in its payload must NOT be guarded
contract.append(("non-Bash tool ignored", _raw_allows({"tool_name": "Read", "tool_input": {"command": ADD_A}})))
# 2) GUARD=off disables the guard entirely
_env = dict(os.environ); _env["MAUNGS_TOOLBELT_GUARD"] = "off"
_off = subprocess.run(["bash", GUARD], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": ADD_A}}),
                      capture_output=True, text=True, env=_env).stdout.strip()
contract.append(("MAUNGS_TOOLBELT_GUARD=off allows", _off == ""))
# 3) empty / non-command input is allowed
contract.append(("empty input allowed", _raw_allows({})))

total = len(results)
passed = sum(1 for r in results if r[0])
blocks = sorted(set(b for _, _, _, _, b in results))

print("PRETOOLUSE GUARD REGRESSION")
print(f"  guard under test : {os.path.relpath(GUARD)}")
print(f"  decision classes : deny, ask, allow")
print(f"  corpus           : {total} labeled commands across blocks {', '.join(blocks)}\n")
print(f"TOTAL COMMANDS: {total}    PASS: {passed}    FAIL: {total-passed}    ({100*passed//total}%)\n")

if ARGS.verbose:
    by = collections.defaultdict(list)
    for ok, cmd, exp, got, block in results:
        by[block].append((ok, cmd, exp, got))
    print("PER-CASE (grouped by test block; command → guard decision):")
    for key in sorted(by):
        rows = by[key]
        g = sum(1 for r in rows if r[0])
        print(f"\n  [block {key}]  {g}/{len(rows)}")
        for ok, cmd, exp, got in rows:
            sym = "✓" if ok else "✗"
            word = "PASS" if ok else "FAIL"
            print(f"    {sym} {word}  expected={exp:6} got={got:6} | {cmd!r}")
    print()

# per-block accuracy (always)
bycat = collections.defaultdict(lambda: [0, 0])
for ok, cmd, exp, got, block in results:
    bycat[block][0] += 1
    bycat[block][1] += (1 if ok else 0)
print("PER-BLOCK:")
block_titles = {
    "A": "quoted-arg false-positives -> allow",
    "B": "real invocations -> STILL deny (security)",
    "C": "allowed-by-design",
    "D": "chaining/subst/here-doc fail-closed",
    "E": "ask-tier preserved",
    "F": "cross-segment force-flag -> allow",
    "H": "gap-batch: bundled add -A / short -n / +refspec / non-Claude AI attribution",
}
for k in sorted(bycat):
    n, g = bycat[k]
    sym = "✓" if g == n else "✗"
    print(f"  {sym} block {k} {g}/{n:<3} {block_titles.get(k, '')}")

print("\nFAIL-OPEN CONTRACT:")
contract_fail = 0
for name, ok in contract:
    sym = "✓" if ok else "✗"
    if not ok:
        contract_fail += 1
    print(f"  {sym} {'PASS' if ok else 'FAIL'}  {name}")

fails = [r for r in results if not r[0]]
print(f"\nFAILURES ({len(fails) + contract_fail}):")
if not fails and not contract_fail:
    print("  (none)")
for ok, cmd, exp, got, block in fails:
    print(f"  ✗ [block {block}] expected={exp:6} got={got:6} | {cmd!r}")
for name, ok in contract:
    if not ok:
        print(f"  ✗ [contract] {name}")

all_ok = (not fails) and (contract_fail == 0)
print(f"\nRESULT: {'PASS' if all_ok else 'FAIL'}  ({passed}/{total} commands + {len(contract)-contract_fail}/{len(contract)} contract checks)")
sys.exit(0 if all_ok else 1)
